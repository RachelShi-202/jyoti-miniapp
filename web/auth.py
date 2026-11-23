"""Passwordless login: single-use codes, persistent limits, opaque cookies."""
import hashlib,hmac,re,secrets,time
import operations
from delivery import send_code,DeliveryError
from fastapi import HTTPException

class Auth:
 def __init__(self,store):
  self.store=store
  with store.connect() as db:
   db.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, identity TEXT UNIQUE NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_codes(identity TEXT PRIMARY KEY, salt TEXT NOT NULL, digest TEXT NOT NULL, expires REAL NOT NULL, attempts INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS login_sessions(digest TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS auth_limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS account_consents(user_id TEXT PRIMARY KEY,version TEXT NOT NULL,accepted REAL NOT NULL);
INSERT OR IGNORE INTO schema_version VALUES (2);''')
 def identity(self,channel,target):
  target=target.strip()
  if channel=='email':
   target=target.lower()
   if len(target)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',target):raise HTTPException(422,'请输入有效邮箱')
  elif channel=='phone':
   target=target.removeprefix('+86')
   if not re.fullmatch(r'1[3-9]\d{9}',target):raise HTTPException(422,'目前支持中国大陆11位手机号')
   target='+86'+target
  else:raise HTTPException(422,'请选择邮箱或手机号')
  return channel+':'+target
 def limit(self,key,maximum,seconds):
  now=time.time()
  with self.store.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   db.execute('DELETE FROM auth_limits WHERE expires<=?',(now,))
   db.execute('DELETE FROM login_sessions WHERE expires<=?',(now,))
   db.execute('DELETE FROM login_codes WHERE expires<=?',(now,))
   row=db.execute('SELECT count,expires FROM auth_limits WHERE key=?',(key,)).fetchone()
   count,expiry=row if row and row[1]>now else (0,now+seconds)
   if count>=maximum:
    operations.record(self.store,operations.limit_event(key))
    raise HTTPException(429,'操作频繁，请稍后再试')
   db.execute('INSERT OR REPLACE INTO auth_limits VALUES (?,?,?)',(key,count+1,expiry))
 def issue(self,channel,target,ip):
  identity=self.identity(channel,target)
  self.limit('ip:'+ip,200,3600);self.limit('day:'+identity,10,86400);self.limit('cooldown:'+identity,1,60)
  code=f'{secrets.randbelow(1000000):06d}';salt=secrets.token_hex(32)
  # Store only a salted, expensive digest to slow offline guessing.
  digest=hashlib.pbkdf2_hmac('sha256',code.encode(),salt.encode(),200000).hex()
  with self.store.connect() as db:db.execute('INSERT OR REPLACE INTO login_codes VALUES (?,?,?,?,0)',(identity,salt,digest,time.time()+300))
  try:send_code(channel,identity.split(':',1)[1],code)
  except Exception as exc:
   operations.record(self.store,'mail_failure' if channel=='email' else 'sms_failure')
   with self.store.connect() as db:db.execute('DELETE FROM login_codes WHERE identity=? AND salt=?',(identity,salt))
   category=exc.category if isinstance(exc,DeliveryError) else 'DELIVERY_FAILED'
   messages={'EMAIL_NOT_CONFIGURED':'邮箱验证码服务尚未配置','SMS_NOT_CONFIGURED':'短信服务尚未开通或配置','EMAIL_AUTH':'发件邮箱认证失败，请管理员检查SMTP授权码','EMAIL_CONNECTION':'邮件服务暂时连接失败，请稍后重试','EMAIL_REJECTED':'邮件未被发送服务接受，请检查收件邮箱或稍后重试','SMS_SDK_MISSING':'短信发送组件尚未安装','SMS_REJECTED':'短信未被接受，请管理员检查签名、模板和发送额度','SMS_UPSTREAM':'短信服务暂不可用，请稍后重试'}
   raise HTTPException(503,messages.get(category,'验证码发送未成功，请联系管理员检查发送服务配置')) from None
  if channel=='email':operations.record(self.store,'mail_success')
  return {'sent':True,'expiresIn':300,'retryAfter':60}
 def verify(self,channel,target,code,ip):
  identity=self.identity(channel,target);self.limit('verify:'+ip,400,3600);self.limit('verify-target:'+identity,40,3600)
  error=False;now=time.time()
  with self.store.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   row=db.execute('SELECT salt,digest,expires,attempts FROM login_codes WHERE identity=?',(identity,)).fetchone()
   if not row or row[2]<=now or row[3]>=5:error=True
   else:
    actual=hashlib.pbkdf2_hmac('sha256',code.encode(),row[0].encode(),200000).hex()
    if not hmac.compare_digest(actual,row[1]):
     db.execute('UPDATE login_codes SET attempts=attempts+1 WHERE identity=?',(identity,));error=True
    else:
     db.execute('DELETE FROM login_codes WHERE identity=?',(identity,))
     user=db.execute('SELECT id FROM users WHERE identity=?',(identity,)).fetchone()
     uid=user[0] if user else secrets.token_urlsafe(24)
     if not user:db.execute('INSERT INTO users VALUES (?,?,?)',(uid,identity,now))
     token=secrets.token_urlsafe(32)
     db.execute('INSERT INTO login_sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,now+30*86400))
  if error:raise HTTPException(400,'验证码错误、已过期或尝试次数过多，请重新获取')
  return token
 def accept_consent(self,token,version='2026-11-08-data-processing-v1'):
  user=self.user(token)
  if not user:raise HTTPException(401,'登录已失效，请重新登录')
  with self.store.connect() as db:
   db.execute('INSERT OR REPLACE INTO account_consents VALUES (?,?,?)',(user['id'],version,time.time()))
 def consented(self,user_id):
  with self.store.connect() as db:
   return bool(db.execute('SELECT 1 FROM account_consents WHERE user_id=?',(user_id,)).fetchone())
 def user(self,token):
  with self.store.connect() as db:
   row=db.execute('SELECT u.id,u.identity FROM login_sessions s JOIN users u ON s.user_id=u.id WHERE s.digest=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
  return {'id':row[0],'identity':row[1]} if row else None
 def logout(self,token):
  with self.store.connect() as db:db.execute('DELETE FROM login_sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),))
