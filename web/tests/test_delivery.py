import smtplib
import pytest
import delivery
from configure_login import netease_settings

@pytest.fixture
def email_env(monkeypatch):
 for key,value in {'SMTP_HOST':'smtp.163.com','SMTP_PORT':'465','SMTP_FROM':'sender@163.com','SMTP_USER':'sender@163.com','SMTP_PASSWORD':'private-authorization'}.items():monkeypatch.setenv(key,value)

@pytest.mark.parametrize('domain,host',[('163.com','smtp.163.com'),('126.com','smtp.126.com'),('yeah.net','smtp.yeah.net')])
def test_netease_presets(domain,host):
 settings=netease_settings('sender@'+domain,' private ')
 assert settings['SMTP_HOST']==host and settings['SMTP_PORT']=='465'
 assert settings['SMTP_USER']==settings['SMTP_FROM']
 assert settings['SMTP_PASSWORD']=='private'

def test_invalid_preset():
 with pytest.raises(ValueError):netease_settings('a@unknown.com','secret')
 with pytest.raises(ValueError):netease_settings('a@163.com','')

def test_ssl_email_and_no_send_check(email_env,monkeypatch):
 sent=[];logins=[]
 class Fake:
  def __init__(self,*args,**kwargs):assert args[:2]==('smtp.163.com',465) and kwargs['context'].check_hostname
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def login(self,user,password):logins.append((user,password))
  def send_message(self,msg):sent.append(msg);return {}
 monkeypatch.setattr(delivery.smtplib,'SMTP_SSL',Fake)
 delivery.check_smtp();assert not sent
 delivery.send_code('email','recipient@example.com','123456')
 assert len(logins)==2 and sent[0]['To']=='recipient@example.com'
 assert '123456' in sent[0].get_content()

def test_starttls_before_auth(email_env,monkeypatch):
 monkeypatch.setenv('SMTP_PORT','587');events=[]
 class Fake:
  def __init__(self,*a,**kw):pass
  def starttls(self,context):assert context.check_hostname;events.append('tls')
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def login(self,*a):events.append('auth')
 monkeypatch.setattr(delivery.smtplib,'SMTP',Fake)
 delivery.check_smtp();assert events==['tls','auth']

def test_failures_are_sanitized(email_env,monkeypatch):
 def fail(*a,**kw):raise smtplib.SMTPAuthenticationError(535,b'private-authorization')
 monkeypatch.setattr(delivery.smtplib,'SMTP_SSL',fail)
 with pytest.raises(delivery.DeliveryError) as exc:delivery.send_code('email','r@example.com','123456')
 assert str(exc.value)=='EMAIL_AUTH' and 'private' not in str(exc.value)
 monkeypatch.delenv('SMTP_PASSWORD')
 with pytest.raises(delivery.DeliveryError) as exc:delivery.check_smtp()
 assert exc.value.category=='EMAIL_NOT_CONFIGURED'

def test_public_status_contains_no_credentials(email_env):
 result=delivery.readiness()
 assert result['email']['configured'] is True
 assert 'private-authorization' not in str(result)

def test_tencent_request_and_rejection(monkeypatch):
 import json
 from tencentcloud.sms.v20210111 import sms_client
 values={'TENCENT_SECRET_ID':'test-id','TENCENT_SECRET_KEY':'test-secret','SMS_APP_ID':'1400000000','SMS_SIGN_NAME':'测试签名','SMS_TEMPLATE_ID':'123456'}
 for key,value in values.items():monkeypatch.setenv(key,value)
 requests=[];accepted=[True]
 class Response:
  def to_json_string(self):return json.dumps({'SendStatusSet':[{'Code':'Ok' if accepted[0] else 'FailedOperation.SignatureIncorrectOrUnapproved'}]})
 class Fake:
  def __init__(self,*args):pass
  def SendSms(self,req):requests.append(json.loads(req.to_json_string()));return Response()
 monkeypatch.setattr(sms_client,'SmsClient',Fake)
 delivery.send_code('phone','+8613800138000','123456')
 assert requests[0]['PhoneNumberSet']==['+8613800138000']
 assert requests[0]['TemplateParamSet']==['123456']
 assert requests[0]['SignName']=='测试签名'
 accepted[0]=False
 with pytest.raises(delivery.DeliveryError) as exc:delivery.send_code('phone','+8613800138000','123456')
 assert exc.value.category=='SMS_REJECTED'
