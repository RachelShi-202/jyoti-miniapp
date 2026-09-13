import os,json,secrets,hashlib,sqlite3,time,re,socket,ssl,errno
from pathlib import Path
from contextlib import contextmanager
import swisseph
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException,Header,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,ConfigDict
from typing import Literal
import httpx
from astro import calculate,monthly,VERSION
from tls_config import wechat_context

DB=os.getenv('JYOTI_DB','./data/jyoti.sqlite3')
import storage
@contextmanager
def db():
 with storage.database(DB) as connection:yield connection
storage.initialize(DB)
app=FastAPI(title='Jyoti calculation API',docs_url=None,redoc_url=None,openapi_url=None)
@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):return JSONResponse(status_code=422,content={'detail':'请求字段不完整或格式无效，请检查出生资料'})

def digest(token):return hashlib.sha256(token.encode()).hexdigest()
GUESTS={}
def user(authorization):
 if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'请先登录')
 guest=GUESTS.get(digest(authorization[7:]))
 if guest and guest['expires']>time.time():return guest['uid']
 with db() as c:
  row=c.execute('SELECT uid FROM sessions WHERE hash=? AND expires>?',(digest(authorization[7:]),time.time())).fetchone()
 if not row:raise HTTPException(401,'登录已过期，请重新登录')
 return row['uid']
def create_session(uid):
 token=secrets.token_urlsafe(32)
 with db() as c:
  c.execute('INSERT OR IGNORE INTO users(id) VALUES(?)',(uid,))
  c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
  c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),uid,time.time()+7*86400))
 return {'token':token,'expiresAt':int(time.time()+7*86400)}
def touch(uid):
 if uid.startswith('guest:'):return
 # UTC day boundary, authenticated substantive reads only.
 with db() as c:c.execute('INSERT OR IGNORE INTO activity VALUES(?,?)',(uid,datetime.now(timezone.utc).date().isoformat()))
from release_info import SOURCE_URL, RELEASE, API_VERSION
def config_value(name):
 return os.getenv(name,'').strip()
def licensing():
 # This project is distributed under AGPL-3.0-or-later, not a vendor activation system.
 # Publication obligations are documented in SOURCE_RELEASE.md and retained in the image.
 pass
@app.get('/source')
def source():return {'license':'AGPL-3.0-or-later','sourceUrl':SOURCE_URL,'release':RELEASE}


@app.get('/health')
def health():return {'ok':True,'release':RELEASE,'apiVersion':API_VERSION,'storageBackend':storage.backend(),'memberStoragePersistent':storage.backend()=='mysql','transientState':'process-memory','wechatConfigured':bool(config_value('WX_APP_ID') and config_value('WX_APP_SECRET')),'wechatAppId':config_value('WX_APP_ID'),'wechatSecretPresent':bool(config_value('WX_APP_SECRET')),'calculationVersion':VERSION,'licenseMode':'AGPL-3.0-or-later','sourceUrl':SOURCE_URL,'aiConfigured':bool(config_value('AI_API_KEY')),'mapConfigured':bool(config_value('TENCENT_MAP_KEY'))}
def connection_failure(exc):
 # Classify locally; never expose exception strings, URLs, codes or credentials.
 queue=[exc];seen=set();kinds=set();verify_code=None
 while queue:
  current=queue.pop()
  if id(current) in seen:continue
  seen.add(id(current))
  message=str(current).lower()
  if isinstance(current,ssl.SSLCertVerificationError):
   code=getattr(current,'verify_code',None)
   if isinstance(code,int):verify_code=code
  if isinstance(current,ssl.SSLCertVerificationError) or 'certificate_verify_failed' in message:kinds.add('CERTIFICATE')
  elif isinstance(current,ssl.SSLError):kinds.add('TLS')
  if isinstance(current,socket.gaierror):kinds.add('DNS')
  if isinstance(current,OSError):
   if current.errno in (errno.ENETUNREACH,errno.EHOSTUNREACH):kinds.add('UNREACHABLE')
   elif current.errno==errno.ECONNREFUSED:kinds.add('REFUSED')
  for child in (current.__cause__,current.__context__,*getattr(current,'exceptions',())):
   if isinstance(child,BaseException):queue.append(child)
 for kind in ('CERTIFICATE','DNS','TLS','UNREACHABLE','REFUSED'):
  if kind in kinds:return '微信连接诊断（WX_CONNECT_'+kind+('_'+str(verify_code) if kind=='CERTIFICATE' and verify_code is not None else '')+'）'
 return '微信连接失败，底层未提供可识别原因（WX_CONNECT_UNKNOWN）'

class Login(BaseModel):
 code:str=Field(min_length=1,max_length=256)
@app.post('/v1/auth/wechat')
async def login(body:Login):
 secret=config_value('WX_APP_SECRET');appid=config_value('WX_APP_ID')
 if not appid:raise HTTPException(503,'服务器尚未配置当前小程序 AppID')
 if not secret:raise HTTPException(503,'服务器尚未配置微信 AppSecret，请联系开发者')
 try:
  # Use verified direct HTTPS; do not inherit container HTTP_PROXY settings.
  async with httpx.AsyncClient(timeout=httpx.Timeout(15,connect=10),trust_env=False,verify=wechat_context()) as client:
   response=await client.get('https://api.weixin.qq.com/sns/jscode2session',params={'appid':appid,'secret':secret,'js_code':body.code,'grant_type':'authorization_code'})
   response.raise_for_status();data=response.json()
 except httpx.TimeoutException:
  raise HTTPException(502,'微信接口请求超时（WX_TIMEOUT）') from None
 except httpx.HTTPStatusError as exc:
  raise HTTPException(502,f'微信接口返回异常状态（WX_HTTP_{exc.response.status_code}）') from None
 except httpx.ConnectError as exc:
  raise HTTPException(502,connection_failure(exc)) from None
 except httpx.HTTPError:
  raise HTTPException(502,'微信接口通信异常（WX_TRANSPORT）') from None
 except ValueError:
  raise HTTPException(502,'微信接口返回内容无法解析（WX_RESPONSE）') from None
 if not isinstance(data,dict):
  raise HTTPException(502,'微信接口返回结构异常（WX_RESPONSE）')
 # Keep only numeric error codes; raw errmsg may include sensitive request context.
 try: error_code=int(data.get('errcode',0))
 except (TypeError,ValueError):error_code=-999
 if error_code or not data.get('openid'):
  messages={
   40013:'微信 AppID 无效，请检查小程序和后端配置',
   40125:'微信 AppSecret 无效，请重新配置当前小程序的密钥并重启服务',
   40001:'微信凭证校验失败，请检查当前小程序的 AppSecret',
   40029:'微信临时登录凭证无效，请重新编译后登录，并确认开发者工具使用正式 AppID',
   40163:'微信临时登录凭证已使用，请重新点击登录获取新凭证',
   45011:'微信登录请求过于频繁，请稍后重试',
   40226:'微信限制了本次登录，请在微信平台核实账户状态',
   40164:'微信拒绝了服务器 IP，请核实平台 IP 白名单',
   -1:'微信系统繁忙，请稍后重试'
  }
  message=messages.get(error_code,'微信未完成登录，请将此错误码反馈给开发者')
  raise HTTPException(502, f'{message}（微信错误码：{error_code}）')
 # Never persist or return WeChat session_key / openid. Stable pseudonymous identity.
 uid=digest(appid+':'+data['openid'])
 with db() as c:c.execute('INSERT OR REPLACE INTO members VALUES(?,?)',(uid,253402300799))
 return create_session(uid)
@app.post('/v1/auth/guest')
def guest_login():
 now=time.time()
 for k,v in list(GUESTS.items()):
  if v['expires']<=now:GUESTS.pop(k,None)
 if len(GUESTS)>=1000:raise HTTPException(429,'游客服务繁忙，请稍后重试')
 token=secrets.token_urlsafe(32);expires=now+7200
 GUESTS[digest(token)]={'uid':'guest:'+secrets.token_urlsafe(24),'expires':expires}
 return {'token':token,'expiresAt':int(expires),'guest':True}
@app.post('/v1/auth/local')
def local_login(request:Request):
 if os.getenv('JYOTI_ENV')=='production' or os.getenv('ALLOW_LOCAL_LOGIN')!='1' or not request.client or request.client.host not in ('127.0.0.1','::1','testclient'):raise HTTPException(404,'Not found')
 return create_session('local-developer')
from features import install
install(app, __import__(__name__))
