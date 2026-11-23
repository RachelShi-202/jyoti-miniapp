import time
import pytest
from fastapi import HTTPException
import payments,entitlements,rectification
from storage import Store

@pytest.fixture
def env(tmp_path,monkeypatch):
 yield Store(tmp_path/'payments.sqlite3')

def paid_payload(order,amount,product_mchid='merchant-1'):
 return {'out_trade_no':order['outTradeNo'],'transaction_id':'wx-'+order['id'],'trade_state':'SUCCESS','mchid':product_mchid,'appid':'app-1','amount':{'total':amount}}

def test_server_prices_all_paid_products(env,monkeypatch):
 owner='owner'
 annual=payments.create_local(env,owner,'annual',2026);topic=payments.create_local(env,owner,'topic')
 assert annual['amountFen']==290 and topic['amountFen']==1990
 assert payments.create_local(env,owner,'single')['amountFen']==490
 assert payments.create_local(env,owner,'consult')['amountFen']==2990
 assert payments.create_local(env,owner,'explorer_starter')['amountFen']==990
 assert payments.create_local(env,owner,'explorer_deep')['amountFen']==3990
 assert payments.create_local(env,owner,'rectification')['amountFen']==3990

def test_two_399_products_have_distinct_product_and_order_ids(env):
 package=payments.create_local(env,'owner','explorer_deep')
 service=payments.create_local(env,'owner','rectification')
 assert package['amountFen']==service['amountFen']==3990
 assert package['id']!=service['id'] and package['outTradeNo']!=service['outTradeNo']
 assert payments.account_order(env,'owner',package['id'])['product']=='explorer_deep'
 assert payments.account_order(env,'owner',service['id'])['product']=='rectification'

def test_deep_package_order_cannot_start_rectification(env,monkeypatch):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 rectification.initialize(env)
 package=payments.create_local(env,'owner','explorer_deep');payments.mark_paid(env,paid_payload(package,3990))
 with pytest.raises(HTTPException):rectification.start(env,'owner',package['id'])

def test_paid_callback_is_idempotent_and_grants_exact_entitlement(env,monkeypatch):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 owner='owner';order=payments.create_local(env,owner,'annual',2027);data=paid_payload(order,100)
 assert payments.mark_paid(env,data) is True
 assert payments.mark_paid(env,data) is True
 summary=entitlements.summary(env,owner)
 assert summary['annual:2027']==1 and summary.get('annual:2026',0)==0
 assert len(payments.account_orders(env,owner))==1
 with pytest.raises(HTTPException):payments.mark_paid(env,{**data,'amount':{'total':1}})

def test_topic_payment_grants_one_topic_credit(env,monkeypatch):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 order=payments.create_local(env,'owner','topic');payments.mark_paid(env,paid_payload(order,1990))
 assert entitlements.summary(env,'owner')['topic']==1

def test_bundle_callback_grants_independent_accumulating_rights_once(env,monkeypatch):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 first=payments.create_local(env,'owner','explorer_deep');payload=paid_payload(first,3990)
 assert payments.mark_paid(env,payload);assert payments.mark_paid(env,payload)
 rights=entitlements.summary(env,'owner')
 assert rights['annual:any']==1 and rights['single']==3 and rights['topic']==1
 second=payments.create_local(env,'owner','explorer_deep');payments.mark_paid(env,paid_payload(second,3990))
 rights=entitlements.summary(env,'owner')
 assert rights['annual:any']==2 and rights['single']==6 and rights['topic']==2
 with env.connect() as db:
  grants=db.execute("SELECT product,amount,order_id FROM credit_grants WHERE owner='owner' AND order_id IS NOT NULL ORDER BY product,order_id").fetchall()
 assert len(grants)==6 and {row[0] for row in grants}=={'annual:any','single','topic'}

def test_starter_bundle_grants_only_configured_matrix(env,monkeypatch):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 order=payments.create_local(env,'owner','explorer_starter');payload=paid_payload(order,990)
 payments.mark_paid(env,payload);payments.mark_paid(env,payload)
 rights=entitlements.summary(env,'owner')
 assert rights['annual:any']==1 and rights['single']==1 and rights['followup']==3 and rights['topic']==0
 second=payments.create_local(env,'owner','explorer_starter');payments.mark_paid(env,paid_payload(second,990))
 rights=entitlements.summary(env,'owner')
 assert rights['annual:any']==2 and rights['single']==2 and rights['followup']==6

@pytest.mark.parametrize(('product','amount'),(('single',490),('topic',1990),('consult',2990),('rectification',3990)))
def test_core_product_payment_unlocks_login_account(env,monkeypatch,product,amount):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 order=payments.create_local(env,'account-owner',product);payments.mark_paid(env,paid_payload(order,amount))
 assert entitlements.summary(env,'account-owner')[product]==1

def test_paid_rectification_order_starts_service_without_second_charge(env,monkeypatch):
 monkeypatch.setenv('WECHATPAY_MCHID','merchant-1');monkeypatch.setenv('WECHATPAY_APPID','app-1')
 rectification.initialize(env)
 order=payments.create_local(env,'rectification-owner','rectification')
 payments.mark_paid(env,paid_payload(order,3990))
 task=rectification.start(env,'rectification-owner',order['id'])
 assert task['status']=='draft' and task['orderId']==order['id']

def test_alipay_signature_channel_isolation_and_idempotent_delivery(env,monkeypatch,tmp_path):
 from cryptography.hazmat.primitives.asymmetric import rsa
 from cryptography.hazmat.primitives import serialization
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 private=tmp_path/'alipay-private.pem';public=tmp_path/'alipay-public.pem'
 private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
 monkeypatch.setenv('ALIPAY_APP_ID','app-a');monkeypatch.setenv('ALIPAY_SELLER_ID','seller-a');monkeypatch.setenv('ALIPAY_PRIVATE_KEY_PATH',str(private));monkeypatch.setenv('ALIPAY_PUBLIC_KEY_PATH',str(public))
 wx=payments.create_local(env,'owner','annual',2028,'wechat');ali=payments.create_local(env,'owner','annual',2028,'alipay')
 assert wx['id']!=ali['id']
 data={'out_trade_no':ali['outTradeNo'],'trade_no':'ali-transaction','trade_status':'TRADE_SUCCESS','total_amount':'1.00','app_id':'app-a','seller_id':'seller-a','notify_time':'2026-11-06 12:00:00'}
 message='&'.join(f'{k}={data[k]}' for k in sorted(data));data['sign_type']='RSA2';data['sign']=payments._rsa_sign(message,str(private))
 payments.verify_alipay_notification(data)
 assert payments.mark_alipay_paid(env,data);assert payments.mark_alipay_paid(env,data)
 assert entitlements.summary(env,'owner')['annual:2028']==1
