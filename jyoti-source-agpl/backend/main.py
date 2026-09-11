import os,json,secrets,hashlib,sqlite3,time,re
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

DB=os.getenv('JYOTI_DB','./data/jyoti.sqlite3')
Path(DB).parent.mkdir(parents=True,exist_ok=True)
@contextmanager
def db():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row
 c.execute('PRAGMA secure_delete=ON')
 try:
  yield c
  c.commit()
 except Exception:
  c.rollback();raise
 finally:c.close()
with db() as c:
 c.executescript('''
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,profile TEXT,chart TEXT,revision TEXT);
 CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,uid TEXT,expires REAL);
 CREATE TABLE IF NOT EXISTS reports(uid TEXT,revision TEXT,period TEXT,body TEXT,PRIMARY KEY(uid,revision,period));
 CREATE TABLE IF NOT EXISTS activity(uid TEXT,day TEXT,PRIMARY KEY(uid,day));
 ''')
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
def licensing():
 if os.getenv('JYOTI_ENV')=='production' and os.getenv('ASTRO_LICENSE_CONFIRMED')!='1':raise HTTPException(503,'计算引擎授权尚未配置')

@app.get('/health')
def health():return {'ok':True,'wechatConfigured':bool(os.getenv('WX_APP_SECRET')),'calculationVersion':VERSION,'aiConfigured':bool(os.getenv('AI_API_KEY')),'mapConfigured':bool(os.getenv('TENCENT_MAP_KEY'))}
class Login(BaseModel):
 code:str=Field(min_length=1,max_length=256)
@app.post('/v1/auth/wechat')
async def login(body:Login):
 secret=os.getenv('WX_APP_SECRET');appid=os.getenv('WX_APP_ID')
 if not appid:raise HTTPException(503,'服务器尚未配置当前小程序 AppID')
 if not secret:raise HTTPException(503,'服务器尚未配置微信 AppSecret，请联系开发者')
 try:
  async with httpx.AsyncClient(timeout=10) as client:
   response=await client.get('https://api.weixin.qq.com/sns/jscode2session',params={'appid':appid,'secret':secret,'js_code':body.code,'grant_type':'authorization_code'})
   response.raise_for_status();data=response.json()
 except (httpx.HTTPError,ValueError):raise HTTPException(502,'微信登录服务暂不可用，请重试')
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
