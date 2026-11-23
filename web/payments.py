"""Server-owned WeChat H5 orders, signature verification and entitlement delivery."""
import base64,hashlib,json,os,re,secrets,time
from pathlib import Path
from urllib.parse import quote,urlencode
from decimal import Decimal,InvalidOperation
import httpx
from fastapi import HTTPException

PRODUCTS={
 'annual':{'amount':290,'description':'星序印占年运报告','enabled':True},
 'topic':{'amount':1990,'description':'星序多盘专题分析','enabled':True},
 'single':{'amount':490,'description':'星序AI单项解读','enabled':True},
 'consult':{'amount':2990,'description':'星序全盘AI咨询','enabled':True},
 'explorer_starter':{'amount':990,'description':'星序探索体验包','enabled':True},
 'explorer_deep':{'amount':3990,'description':'星序深度探索包','enabled':True},
 'rectification':{'amount':3990,'description':'星序出生时间校准服务','enabled':True},
}
PRODUCT_ENTITLEMENTS={
 'single':{'single':1},'topic':{'topic':1},'consult':{'consult':1},'rectification':{'rectification':1},
 'explorer_starter':{'annual:any':1,'single':1,'followup':3},
 'explorer_deep':{'annual:any':1,'single':3,'topic':1},
}

def _valid_days(product):
 key={'explorer_starter':'JYOTI_EXPLORER_STARTER_VALID_DAYS','explorer_deep':'JYOTI_EXPLORER_DEEP_VALID_DAYS'}.get(product)
 if not key or not os.getenv(key):return None
 try:return max(1,int(os.environ[key]))
 except ValueError:raise RuntimeError(key+' must be a positive integer')

def initialize(db):
 db.executescript('''CREATE TABLE IF NOT EXISTS payment_orders(
id TEXT PRIMARY KEY,out_trade_no TEXT UNIQUE NOT NULL,owner TEXT NOT NULL,product TEXT NOT NULL,product_ref TEXT NOT NULL,
amount_fen INTEGER NOT NULL,channel TEXT NOT NULL,status TEXT NOT NULL,prepay_url TEXT,transaction_id TEXT UNIQUE,
created REAL NOT NULL,updated REAL NOT NULL,paid_at REAL,expires REAL NOT NULL);
CREATE INDEX IF NOT EXISTS payment_owner ON payment_orders(owner,created);
CREATE INDEX IF NOT EXISTS payment_status ON payment_orders(status,updated);
CREATE TABLE IF NOT EXISTS payment_events(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,event_type TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payment_handoffs(
digest TEXT PRIMARY KEY,owner TEXT NOT NULL,product TEXT NOT NULL,product_ref TEXT NOT NULL,
channel TEXT NOT NULL,expires REAL NOT NULL,used REAL
);''')

def cleanup(store):
 """Remove short-lived failed/unstarted records while preserving paid audit data."""
 cutoff=time.time()-600
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  doomed=[row[0] for row in db.execute("SELECT id FROM payment_orders WHERE (status IN ('failed','closed') AND updated<?) OR (status='created' AND created<?)",(cutoff,cutoff)).fetchall()]
  if doomed:
   marks=','.join('?' for _ in doomed)
   db.execute(f'DELETE FROM payment_events WHERE order_id IN ({marks})',doomed)
   db.execute(f'DELETE FROM payment_orders WHERE id IN ({marks})',doomed)
  db.execute('DELETE FROM payment_handoffs WHERE expires<? OR (used IS NOT NULL AND used<?)',(time.time(),time.time()-86400))

PAYMENT_SITE_URL=os.getenv('PAYMENT_SITE_URL','https://xingxujyoti.com').rstrip('/')
JYOTI_PUBLIC_URL=os.getenv('JYOTI_PUBLIC_URL','https://jyoti.xingxujyoti.com').rstrip('/')

def configured():
 names=('WECHATPAY_MCHID','WECHATPAY_APPID','WECHATPAY_MERCHANT_SERIAL','WECHATPAY_API_V3_KEY','WECHATPAY_PRIVATE_KEY_PATH','WECHATPAY_PLATFORM_KEY_ID','WECHATPAY_PLATFORM_PUBLIC_KEY_PATH')
 if not all(os.getenv(x) for x in names):return False
 return all(Path(os.environ[x]).is_file() for x in ('WECHATPAY_PRIVATE_KEY_PATH','WECHATPAY_PLATFORM_PUBLIC_KEY_PATH'))

def alipay_configured():
 # 手机网站支付使用网页应用 AppID 与 RSA2 密钥即可。seller_id/商户 UID
 # 并不是创建订单的必填配置；若运营方主动配置，通知阶段再额外核验。
 names=('ALIPAY_APP_ID','ALIPAY_PRIVATE_KEY_PATH','ALIPAY_PUBLIC_KEY_PATH')
 return all(os.getenv(x) for x in names) and all(Path(os.environ[x]).is_file() for x in ('ALIPAY_PRIVATE_KEY_PATH','ALIPAY_PUBLIC_KEY_PATH'))

PAYPAL_PRODUCTS={'annual':{'usd':'2.90','description':'Xingxu Annual Reading'},'single':{'usd':'4.90','description':'Xingxu AI Single Reading'},'topic':{'usd':'19.90','description':'Xingxu Multi-chart Topic Analysis'},'consult':{'usd':'29.90','description':'Xingxu Full-chart AI Consultation'},'explorer_starter':{'usd':'9.90','description':'Xingxu Explorer Starter Pack'},'explorer_deep':{'usd':'39.90','description':'Xingxu Deep Explorer Pack'},'rectification':{'usd':'39.90','description':'Xingxu Birth Time Rectification'}}
def paypal_configured():
 return all(os.getenv(x) for x in ('PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET','PAYPAL_WEBHOOK_ID'))
def paypal_api_configured():
 return all(os.getenv(x) for x in ('PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET'))
def _paypal_base():
 return 'https://api-m.paypal.com' if os.getenv('PAYPAL_ENV','live').lower()=='live' else 'https://api-m.sandbox.paypal.com'
async def _paypal_token():
 if not paypal_api_configured(): raise HTTPException(503,'PayPal API 尚未配置（PAYPAL_NOT_CONFIGURED）')
 try:
  async with httpx.AsyncClient(timeout=20,trust_env=False) as client:
   r=await client.post(_paypal_base()+'/v1/oauth2/token',auth=(os.environ['PAYPAL_CLIENT_ID'],os.environ['PAYPAL_CLIENT_SECRET']),data={'grant_type':'client_credentials'},headers={'Accept':'application/json','Accept-Language':'zh_CN'})
 except httpx.HTTPError: raise HTTPException(502,'暂时无法连接 PayPal')
 if r.status_code!=200: raise HTTPException(502,'PayPal API 认证失败')
 return r.json()['access_token']
async def create_paypal(store,owner,product,year=None):
 spec=PAYPAL_PRODUCTS.get(product)
 if not spec: raise HTTPException(422,'该服务未配置 PayPal 价格')
 order=create_local(store,owner,product,year,'paypal')
 token=await _paypal_token()
 payload={'intent':'CAPTURE','purchase_units':[{'reference_id':order['outTradeNo'],'custom_id':owner,'description':spec['description'],'amount':{'currency_code':'USD','value':spec['usd']}}],'application_context':{'brand_name':'Xingxu JYOTI','user_action':'PAY_NOW','return_url':PAYMENT_SITE_URL+'/api/payment/paypal/return?order_id='+quote(order['id'],safe=''),'cancel_url':JYOTI_PUBLIC_URL+'/#payment'}}
 try:
  async with httpx.AsyncClient(timeout=20,trust_env=False) as client:r=await client.post(_paypal_base()+'/v2/checkout/orders',json=payload,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Prefer':'return=representation'})
 except httpx.HTTPError: raise HTTPException(502,'PayPal 创建订单失败')
 if r.status_code not in (200,201): raise HTTPException(502,'PayPal 创建订单失败，请检查 Live API 配置')
 data=r.json();provider=data.get('id');approve=next((x.get('href') for x in data.get('links',[]) if x.get('rel')=='approve'),None)
 if not provider or not approve: raise HTTPException(502,'PayPal 未返回付款地址')
 with store.connect() as db:
  db.execute("UPDATE payment_orders SET status='pending',prepay_url=?,updated=? WHERE id=?",(approve,time.time(),order['id']))
  db.execute('INSERT OR IGNORE INTO payment_events VALUES (?,?,?,?)',('paypal:'+provider,order['id'],'paypal_order',time.time()))
 return {**order,'status':'pending','h5Url':approve,'paypalOrderId':provider}
def _paypal_local(store,provider):
 with store.connect() as db:
  row=db.execute("SELECT order_id FROM payment_events WHERE id=? AND event_type='paypal_order'",('paypal:'+provider,)).fetchone()
 return row[0] if row else None
async def capture_paypal(store,provider):
 token=await _paypal_token()
 try:
  async with httpx.AsyncClient(timeout=20,trust_env=False) as client:r=await client.post(_paypal_base()+'/v2/checkout/orders/'+quote(provider,safe='')+'/capture',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Prefer':'return=representation'})
 except httpx.HTTPError: raise HTTPException(502,'PayPal 付款确认失败')
 if r.status_code not in (200,201): raise HTTPException(502,'PayPal 付款尚未完成')
 data=r.json();purchase=(data.get('purchase_units') or [{}])[0];capture=((purchase.get('payments') or {}).get('captures') or [{}])[0]
 if data.get('status')!='COMPLETED' or capture.get('status')!='COMPLETED': return {'status':'pending'}
 oid=_paypal_local(store,provider)
 if not oid: raise HTTPException(404,'PayPal 本地订单不存在')
 with store.connect() as db:
  row=db.execute('SELECT owner,product,product_ref,status FROM payment_orders WHERE id=?',(oid,)).fetchone()
  if not row: raise HTTPException(404,'本地订单不存在')
  if row[3]!='paid':
   db.execute("UPDATE payment_orders SET status='paid',transaction_id=?,paid_at=?,updated=? WHERE id=?",(capture.get('id'),time.time(),time.time(),oid));_grant(db,oid,row[0],row[1],row[2],'paypal:'+capture.get('id'))
 return account_order_by_id(store,oid)
async def verify_paypal_webhook(headers,body):
 token=await _paypal_token();event=json.loads(body)
 payload={'transmission_id':headers.get('paypal-transmission-id'),'transmission_time':headers.get('paypal-transmission-time'),'cert_url':headers.get('paypal-cert-url'),'auth_algo':headers.get('paypal-auth-algo'),'transmission_sig':headers.get('paypal-transmission-sig'),'webhook_id':os.environ.get('PAYPAL_WEBHOOK_ID'),'webhook_event':event}
 if not all(payload.get(k) for k in ('transmission_id','transmission_time','cert_url','auth_algo','transmission_sig','webhook_id')): return False
 try:
  async with httpx.AsyncClient(timeout=20,trust_env=False) as client:r=await client.post(_paypal_base()+'/v1/notifications/verify-webhook-signature',json=payload,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 except httpx.HTTPError:return False
 return r.status_code==200 and r.json().get('verification_status')=='SUCCESS'
def mark_paypal_refunded(store,capture_id):
 with store.connect() as db:
  return db.execute("UPDATE payment_orders SET status='refunded',updated=? WHERE transaction_id=? AND status='paid'",(time.time(),capture_id)).rowcount==1
def account_order_by_id(store,oid):
 with store.connect() as db:r=db.execute('SELECT id,product,product_ref,amount_fen,status,created,paid_at,channel FROM payment_orders WHERE id=?',(oid,)).fetchone()
 if not r: raise HTTPException(404,'订单不存在')
 return {'id':r[0],'product':r[1],'productRef':r[2],'amountFen':r[3],'status':r[4],'created':r[5],'paidAt':r[6],'channel':r[7]}

def unlock_rectification_invite(store,owner,code):
 """Create one auditable zero-price paid order after a valid code redemption."""
 digest=hashlib.sha256(code.strip().upper().encode()).hexdigest();key=hashlib.sha256((digest+':'+owner).encode()).hexdigest()
 oid='invite-'+key[:24];trade='IV'+key[:30].upper();transaction='invite-'+key
 now=time.time()
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  valid=db.execute("""SELECT 1 FROM invite_redemptions r JOIN invite_codes c ON c.digest=r.digest
WHERE r.digest=? AND r.owner=? AND c.product='rectification' AND c.disabled=0""",(digest,owner)).fetchone()
  if not valid:raise HTTPException(400,'出生时间校准内测码尚未成功兑换')
  db.execute('''INSERT OR IGNORE INTO payment_orders
(id,out_trade_no,owner,product,product_ref,amount_fen,channel,status,prepay_url,transaction_id,created,updated,paid_at,expires)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(oid,trade,owner,'rectification','',0,'invite','paid',None,transaction,now,now,now,now))
  db.execute('INSERT OR IGNORE INTO payment_events VALUES (?,?,?,?)',('invite-unlock:'+key,oid,'invite_paid',now))
 return account_order_by_id(store,oid)

def _crypto():
 try:
  from cryptography.hazmat.primitives import hashes,serialization
  from cryptography.hazmat.primitives.asymmetric import padding
  from cryptography.hazmat.primitives.ciphers.aead import AESGCM
  return hashes,serialization,padding,AESGCM
 except ImportError:raise HTTPException(503,'支付加密组件尚未安装（PAYMENT_CRYPTO_MISSING）')

def _private_key():
 _,serialization,_,_=_crypto()
 return serialization.load_pem_private_key(Path(os.environ['WECHATPAY_PRIVATE_KEY_PATH']).read_bytes(),password=None)

def _platform_key():
 _,serialization,_,_=_crypto()
 raw=Path(os.environ['WECHATPAY_PLATFORM_PUBLIC_KEY_PATH']).read_bytes()
 try:return serialization.load_pem_public_key(raw)
 except ValueError:
  from cryptography import x509
  return x509.load_pem_x509_certificate(raw).public_key()

def _sign(message):
 hashes,_,padding,_=_crypto()
 return base64.b64encode(_private_key().sign(message.encode(),padding.PKCS1v15(),hashes.SHA256())).decode()

def _rsa_sign(message,path):
 hashes,serialization,padding,_=_crypto()
 key=serialization.load_pem_private_key(Path(path).read_bytes(),password=None)
 return base64.b64encode(key.sign(message.encode('utf-8'),padding.PKCS1v15(),hashes.SHA256())).decode()

def _rsa_verify(message,signature,path):
 hashes,serialization,padding,_=_crypto();raw=Path(path).read_bytes()
 try:key=serialization.load_pem_public_key(raw)
 except ValueError:
  from cryptography import x509
  key=x509.load_pem_x509_certificate(raw).public_key()
 try:key.verify(base64.b64decode(signature),message.encode('utf-8'),padding.PKCS1v15(),hashes.SHA256());return True
 except Exception:return False

def _verify(message,signature):
 hashes,_,padding,_=_crypto()
 try:_platform_key().verify(base64.b64decode(signature),message.encode(),padding.PKCS1v15(),hashes.SHA256());return True
 except Exception:return False

def authorization(method,path,body):
 timestamp=str(int(time.time()));nonce=secrets.token_hex(16)
 signature=_sign(f'{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n')
 token=f'mchid="{os.environ["WECHATPAY_MCHID"]}",nonce_str="{nonce}",timestamp="{timestamp}",serial_no="{os.environ["WECHATPAY_MERCHANT_SERIAL"]}",signature="{signature}"'
 return 'WECHATPAY2-SHA256-RSA2048 '+token

def verify_response(headers,body):
 timestamp=headers.get('Wechatpay-Timestamp','');nonce=headers.get('Wechatpay-Nonce','');signature=headers.get('Wechatpay-Signature','')
 key_id=headers.get('Wechatpay-Serial','')
 return bool(key_id==os.getenv('WECHATPAY_PLATFORM_KEY_ID') and timestamp and nonce and signature and _verify(f'{timestamp}\n{nonce}\n{body}\n',signature))

def verify_notification(headers,body):
 timestamp=headers.get('Wechatpay-Timestamp','');nonce=headers.get('Wechatpay-Nonce','');signature=headers.get('Wechatpay-Signature','')
 key_id=headers.get('Wechatpay-Serial','')
 try:fresh=abs(time.time()-int(timestamp))<=300
 except ValueError:fresh=False
 if key_id!=os.getenv('WECHATPAY_PLATFORM_KEY_ID') or not fresh or not nonce or not signature or not _verify(f'{timestamp}\n{nonce}\n{body}\n',signature):raise HTTPException(401,'微信支付通知验签失败')

def decrypt_resource(resource):
 _,_,_,AESGCM=_crypto();key=os.environ['WECHATPAY_API_V3_KEY'].encode()
 if len(key)!=32:raise HTTPException(503,'微信支付 APIv3 密钥配置无效')
 try:
  value=AESGCM(key).decrypt(resource['nonce'].encode(),base64.b64decode(resource['ciphertext']),resource.get('associated_data','').encode())
  return json.loads(value)
 except Exception:raise HTTPException(400,'微信支付通知解密失败')

def _ref(product,year):
 if product=='annual':
  if not isinstance(year,int) or not 1900<=year<=2100:raise HTTPException(422,'请选择要购买的年度')
  return str(year)
 return ''

def create_handoff(store,owner,product,channel,year=None):
 if product not in PRODUCTS:raise HTTPException(422,'未知服务')
 if channel not in ('wechat','alipay','paypal'):raise HTTPException(422,'不支持的支付渠道')
 ref=_ref(product,year);token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest();now=time.time()
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  db.execute('DELETE FROM payment_handoffs WHERE expires<? OR (used IS NOT NULL AND used<?)',(now,now-86400))
  db.execute('INSERT INTO payment_handoffs VALUES (?,?,?,?,?,?,NULL)',(digest,owner,product,ref,channel,now+300))
 return token

def consume_handoff(store,token):
 if not token or len(token)>100:raise HTTPException(400,'支付凭证无效')
 digest=hashlib.sha256(token.encode()).hexdigest();now=time.time()
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  row=db.execute('SELECT owner,product,product_ref,channel,expires,used FROM payment_handoffs WHERE digest=?',(digest,)).fetchone()
  if not row or row[4]<=now or row[5] is not None:raise HTTPException(400,'支付凭证已失效，请返回星序重新发起')
  db.execute('UPDATE payment_handoffs SET used=? WHERE digest=? AND used IS NULL',(now,digest))
 return {'owner':row[0],'product':row[1],'year':int(row[2]) if row[1]=='annual' else None,'channel':row[3]}

def create_local(store,owner,product,year=None,channel='wechat'):
 spec=PRODUCTS.get(product)
 if not spec:raise HTTPException(422,'未知服务')
 if not spec['enabled'] and channel!='paypal':raise HTTPException(409,'该服务仍在完善交付流程，暂未开放付款')
 ref=_ref(product,year);now=time.time()
 amount=spec['amount'] if channel!='paypal' else round(float(PAYPAL_PRODUCTS[product]['usd'])*100)
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  row=db.execute("SELECT id,out_trade_no,amount_fen,status,prepay_url,expires FROM payment_orders WHERE owner=? AND product=? AND product_ref=? AND channel=? AND status IN ('created','pending') AND expires>? ORDER BY created DESC LIMIT 1",(owner,product,ref,channel,now)).fetchone()
  if row:return {'id':row[0],'outTradeNo':row[1],'amountFen':row[2],'status':row[3],'h5Url':row[4]}
  oid=secrets.token_urlsafe(18);trade='XX'+time.strftime('%Y%m%d%H%M%S')+secrets.token_hex(5).upper()
  db.execute('INSERT INTO payment_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,trade,owner,product,ref,amount,channel,'created',None,None,now,now,None,now+600))
 return {'id':oid,'outTradeNo':trade,'amountFen':amount,'status':'created','h5Url':None}

def _wechat_error(response):
 try:
  error=response.json();code=str(error.get('code','UNKNOWN'))[:80];message=' '.join(str(error.get('message','请求未通过')).split())[:160]
 except (ValueError,AttributeError,TypeError):return 'UNKNOWN','请求未通过'
 if not re.fullmatch(r'[A-Za-z0-9_.-]+',code):code='UNKNOWN'
 # Repair a response that was decoded as latin-1 by an upstream proxy.
 if any(x in message for x in ('å','æ','è','ç','Â')):
  try:message=message.encode('latin-1').decode('utf-8')
  except (UnicodeEncodeError,UnicodeDecodeError):pass
 return code,message

async def create_wechat(store,owner,product,client_ip,year=None,native=False):
 if not configured():raise HTTPException(503,'微信支付服务尚未完成密钥配置（PAYMENT_NOT_CONFIGURED）')
 order=create_local(store,owner,product,year)
 if order['h5Url']:
  existing_native=order['h5Url'].startswith('weixin://')
  if existing_native==native:
   mode='native' if native else 'h5'
   return {**order,'payMode':mode,'codeUrl':order['h5Url'] if native else None}
  with store.connect() as db:db.execute("UPDATE payment_orders SET status='closed',updated=? WHERE id=? AND status!='paid'",(time.time(),order['id']))
  order=create_local(store,owner,product,year)
 mode='native' if native else 'h5';path='/v3/pay/transactions/'+mode;spec=PRODUCTS[product]
 payload={'appid':os.environ['WECHATPAY_APPID'],'mchid':os.environ['WECHATPAY_MCHID'],'description':spec['description'],'out_trade_no':order['outTradeNo'],'notify_url':os.getenv('WECHATPAY_NOTIFY_URL',PAYMENT_SITE_URL+'/api/payment/wechat/notify'),'amount':{'total':spec['amount'],'currency':'CNY'}}
 if not native:payload['scene_info']={'payer_client_ip':client_ip,'h5_info':{'type':'Wap','app_name':'星序','app_url':PAYMENT_SITE_URL}}
 body=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
 headers={'Authorization':authorization('POST',path,body),'Accept':'application/json','Content-Type':'application/json','User-Agent':'Xingxu-H5/1.0'}
 try:
  async with httpx.AsyncClient(timeout=20,trust_env=False) as client:r=await client.post('https://api.mch.weixin.qq.com'+path,content=body.encode(),headers=headers)
 except httpx.HTTPError:raise HTTPException(502,'暂时无法连接微信支付，请稍后重试')
 text=r.content.decode('utf-8','replace')
 if r.status_code!=200:
  code,message=_wechat_error(r)
  raise HTTPException(502,f'微信支付下单失败：{code} · {message}')
 if not verify_response(r.headers,text):raise HTTPException(502,'微信支付响应验签失败')
 pay_url=r.json().get('code_url' if native else 'h5_url')
 if not pay_url:raise HTTPException(502,'微信支付未返回付款链接')
 with store.connect() as db:db.execute("UPDATE payment_orders SET status='pending',prepay_url=?,updated=? WHERE id=? AND status='created'",(pay_url,time.time(),order['id']))
 return {**order,'status':'pending','h5Url':pay_url,'payMode':mode,'codeUrl':pay_url if native else None}

def native_order(store,oid):
 with store.connect() as db:r=db.execute("SELECT id,prepay_url,status,expires FROM payment_orders WHERE id=? AND channel='wechat'",(oid,)).fetchone()
 if not r or not r[1] or not r[1].startswith('weixin://'):raise HTTPException(404,'扫码订单不存在')
 return {'id':r[0],'codeUrl':r[1],'status':r[2],'expires':r[3]}

def _alipay_params(method,biz_content,notify=True,return_url=None):
 params={'app_id':os.environ['ALIPAY_APP_ID'],'method':method,'format':'JSON','charset':'utf-8','sign_type':'RSA2','timestamp':time.strftime('%Y-%m-%d %H:%M:%S'),'version':'1.0','biz_content':json.dumps(biz_content,ensure_ascii=False,separators=(',',':'))}
 if notify:params['notify_url']=os.getenv('ALIPAY_NOTIFY_URL',PAYMENT_SITE_URL+'/api/payment/alipay/notify')
 if return_url:params['return_url']=return_url
 message='&'.join(f'{k}={params[k]}' for k in sorted(params));params['sign']=_rsa_sign(message,os.environ['ALIPAY_PRIVATE_KEY_PATH'])
 return params

def create_alipay(store,owner,product,year=None):
 if not alipay_configured():raise HTTPException(503,'支付宝服务尚未完成密钥配置（ALIPAY_NOT_CONFIGURED）')
 order=create_local(store,owner,product,year,'alipay');spec=PRODUCTS[product]
 biz={'out_trade_no':order['outTradeNo'],'total_amount':f'{spec["amount"]/100:.2f}','subject':spec['description'],'product_code':'QUICK_WAP_WAY','quit_url':JYOTI_PUBLIC_URL+'/#payment'}
 params=_alipay_params('alipay.trade.wap.pay',biz,True,JYOTI_PUBLIC_URL+'/?payment_order='+quote(order['id'],safe='')+'#payment')
 url=os.getenv('ALIPAY_GATEWAY','https://openapi.alipay.com/gateway.do')+'?'+urlencode(params)
 with store.connect() as db:db.execute("UPDATE payment_orders SET status='pending',prepay_url=?,updated=? WHERE id=? AND status='created'",(url,time.time(),order['id']))
 return {**order,'status':'pending','h5Url':url}

def verify_alipay_notification(params):
 signature=params.get('sign','');message='&'.join(f'{k}={params[k]}' for k in sorted(params) if k not in ('sign','sign_type'))
 if not signature or not _rsa_verify(message,signature,os.environ['ALIPAY_PUBLIC_KEY_PATH']):raise HTTPException(401,'支付宝通知验签失败')

def mark_alipay_paid(store,data):
 trade=data.get('out_trade_no','');transaction=data.get('trade_no','');status=data.get('trade_status','')
 try:amount_fen=int(Decimal(data.get('total_amount',''))*100)
 except (InvalidOperation,ValueError):raise HTTPException(400,'支付宝订单金额无效')
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE');row=db.execute("SELECT id,owner,product,product_ref,amount_fen,status FROM payment_orders WHERE out_trade_no=? AND channel='alipay'",(trade,)).fetchone()
  if not row:raise HTTPException(404,'订单不存在')
  expected_seller=os.getenv('ALIPAY_SELLER_ID','').strip()
  if data.get('app_id')!=os.getenv('ALIPAY_APP_ID') or (expected_seller and data.get('seller_id')!=expected_seller):raise HTTPException(400,'支付宝商户信息不匹配')
  if amount_fen!=row[4]:raise HTTPException(400,'订单金额校验失败')
  if status not in ('TRADE_SUCCESS','TRADE_FINISHED'):return False
  if not transaction:raise HTTPException(400,'支付宝通知缺少交易号')
  if row[5]!='paid':
   db.execute("UPDATE payment_orders SET status='paid',transaction_id=?,paid_at=?,updated=? WHERE id=?",(transaction,time.time(),time.time(),row[0]));_grant(db,row[0],row[1],row[2],row[3],transaction)
 return True

def _grant(db,order_id,owner,product,ref,transaction):
 import entitlements
 grants={'annual:'+ref:1} if product=='annual' else PRODUCT_ENTITLEMENTS.get(product,{product:1})
 paid_at=db.execute('SELECT paid_at FROM payment_orders WHERE id=?',(order_id,)).fetchone()
 days=_valid_days(product);expires=(paid_at[0]+days*86400) if days and paid_at and paid_at[0] else None
 for entitlement,amount in grants.items():entitlements.grant(db,owner,entitlement,'payment:'+transaction+':'+entitlement,amount,order_id,expires)
 db.execute('INSERT OR IGNORE INTO payment_events VALUES (?,?,?,?)',('paid:'+transaction,order_id,'paid',time.time()))

def mark_paid(store,data):
 trade=data.get('out_trade_no','');transaction=data.get('transaction_id','');amount=data.get('amount',{}).get('total')
 if not trade or not transaction:raise HTTPException(400,'支付通知缺少订单标识')
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  row=db.execute('SELECT id,owner,product,product_ref,amount_fen,status FROM payment_orders WHERE out_trade_no=?',(trade,)).fetchone()
  if not row:raise HTTPException(404,'订单不存在')
  if amount!=row[4]:raise HTTPException(400,'订单金额校验失败')
  if data.get('mchid')!=os.getenv('WECHATPAY_MCHID') or data.get('appid')!=os.getenv('WECHATPAY_APPID'):raise HTTPException(400,'订单商户信息不匹配')
  if data.get('trade_state')!='SUCCESS':return False
  if row[5]!='paid':
   db.execute("UPDATE payment_orders SET status='paid',transaction_id=?,paid_at=?,updated=? WHERE id=?",(transaction,time.time(),time.time(),row[0]));_grant(db,row[0],row[1],row[2],row[3],transaction)
 return True

def account_orders(store,owner):
 cleanup(store);cutoff=time.time()-600
 with store.connect() as db:rows=db.execute("SELECT id,product,product_ref,amount_fen,status,created,paid_at,channel FROM payment_orders WHERE owner=? AND (status IN ('paid','refunding','refunded') OR created>=?) ORDER BY created DESC LIMIT 100",(owner,cutoff)).fetchall()
 return [{'id':r[0],'product':r[1],'productRef':r[2],'amountFen':r[3],'status':r[4],'created':r[5],'paidAt':r[6],'channel':r[7]} for r in rows]

def account_order(store,owner,oid):
 with store.connect() as db:r=db.execute('SELECT id,product,product_ref,amount_fen,status,created,paid_at,channel FROM payment_orders WHERE owner=? AND id=?',(owner,oid)).fetchone()
 if not r:raise HTTPException(404,'订单不存在')
 return {'id':r[0],'product':r[1],'productRef':r[2],'amountFen':r[3],'status':r[4],'created':r[5],'paidAt':r[6],'channel':r[7]}

async def query_wechat(store,owner,oid):
 order=account_order(store,owner,oid)
 if order['channel']!='wechat' or order['status']=='paid' or not configured():return order
 with store.connect() as db:r=db.execute('SELECT out_trade_no FROM payment_orders WHERE id=? AND owner=?',(oid,owner)).fetchone()
 path='/v3/pay/transactions/out-trade-no/'+quote(r[0],safe='')+'?mchid='+quote(os.environ['WECHATPAY_MCHID'],safe='')
 headers={'Authorization':authorization('GET',path,''),'Accept':'application/json','User-Agent':'Xingxu-H5/1.0'}
 try:
  async with httpx.AsyncClient(timeout=15,trust_env=False) as client:response=await client.get('https://api.mch.weixin.qq.com'+path,headers=headers)
 except httpx.HTTPError:return order
 if response.status_code==200 and verify_response(response.headers,response.text):
  data=response.json()
  if data.get('trade_state')=='SUCCESS':mark_paid(store,data)
  elif data.get('trade_state') in ('CLOSED','REVOKED','PAYERROR'):
   with store.connect() as db:db.execute("UPDATE payment_orders SET status='closed',updated=? WHERE id=? AND status!='paid'",(time.time(),oid))
 return account_order(store,owner,oid)

async def query_wechat_native(store,oid):
 with store.connect() as db:r=db.execute("SELECT owner FROM payment_orders WHERE id=? AND channel='wechat'",(oid,)).fetchone()
 if not r:raise HTTPException(404,'订单不存在')
 return await query_wechat(store,r[0],oid)

def _alipay_response(text,node):
 marker='"'+node+'":';position=text.find(marker)
 if position<0:raise ValueError('missing response node')
 start=position+len(marker);value,end=json.JSONDecoder().raw_decode(text,start)
 envelope=json.loads(text);signature=envelope.get('sign','')
 if not signature or not _rsa_verify(text[start:end],signature,os.environ['ALIPAY_PUBLIC_KEY_PATH']):raise HTTPException(502,'支付宝响应验签失败')
 return value

async def query_alipay(store,owner,oid):
 order=account_order(store,owner,oid)
 if order['channel']!='alipay' or order['status']=='paid' or not alipay_configured():return order
 with store.connect() as db:r=db.execute('SELECT out_trade_no FROM payment_orders WHERE id=? AND owner=?',(oid,owner)).fetchone()
 params=_alipay_params('alipay.trade.query',{'out_trade_no':r[0]},False)
 try:
  async with httpx.AsyncClient(timeout=15,trust_env=False) as client:response=await client.post(os.getenv('ALIPAY_GATEWAY','https://openapi.alipay.com/gateway.do'),data=params)
 except httpx.HTTPError:return order
 if response.status_code==200:
  try:data=_alipay_response(response.text,'alipay_trade_query_response')
  except (ValueError,json.JSONDecodeError,HTTPException):return order
  if data.get('trade_status') in ('TRADE_SUCCESS','TRADE_FINISHED'):
   data.update(app_id=os.environ['ALIPAY_APP_ID'])
   if os.getenv('ALIPAY_SELLER_ID'):data['seller_id']=os.environ['ALIPAY_SELLER_ID']
   mark_alipay_paid(store,data)
  elif data.get('trade_status')=='TRADE_CLOSED':
   with store.connect() as db:db.execute("UPDATE payment_orders SET status='closed',updated=? WHERE id=? AND status!='paid'",(time.time(),oid))
 return account_order(store,owner,oid)

async def reconcile_alipay(store,owner):
 """Recover paid Alipay orders even when the browser return/callback was missed."""
 cutoff=time.time()-7*86400
 with store.connect() as db:
  # Repair any historical paid order whose entitlement write was missed by an
  # older deployment. grant() is idempotent because its payment source is unique.
  paid=db.execute("SELECT id,product,product_ref,transaction_id FROM payment_orders WHERE owner=? AND channel='alipay' AND status='paid' AND transaction_id IS NOT NULL",(owner,)).fetchall()
  for order_id,product,ref,transaction in paid:_grant(db,order_id,owner,product,ref,transaction)
  rows=db.execute("SELECT id FROM payment_orders WHERE owner=? AND channel='alipay' AND status IN ('created','pending') AND created>? ORDER BY created DESC LIMIT 8",(owner,cutoff)).fetchall()
 reconciled=0
 for (oid,) in rows:
  before=account_order(store,owner,oid)['status']
  after=(await query_alipay(store,owner,oid))['status']
  if before!='paid' and after=='paid':reconciled+=1
 return reconciled

def checkout_url(h5_url,order_id):
 return h5_url+('&' if '?' in h5_url else '?')+'redirect_url='+quote(JYOTI_PUBLIC_URL+'/?payment_order='+order_id+'#payment',safe='')
