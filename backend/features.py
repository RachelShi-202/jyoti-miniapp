import os,time,secrets,threading,json,asyncio
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
from fastapi import Header,HTTPException
from astro import calculate,monthly,VERSION
import providers
TTL=7200
LOCK=threading.RLock();CURRENT={};PLACES={};JOBS={};LIMITS={}
class PlaceRequest(BaseModel):
 address:str=Field(min_length=4,max_length=200)
class Birth(BaseModel):
 model_config=ConfigDict(extra='forbid')
 date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
 time:str=Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
 placeToken:str=Field(min_length=1,max_length=100)
 fold:Literal[0,1]|None=None
 consent:Literal[True]
class SaveRequest(BaseModel):
 jobId:str|None=Field(default=None,max_length=100)

def install(app,core):
 with core.db() as c:
  # New policy: existing nonmember birth records and reports must not remain on disk.
  c.execute('UPDATE users SET profile=NULL,chart=NULL,revision=NULL WHERE id NOT IN (SELECT uid FROM members WHERE expires>?)',(time.time(),))
  c.execute('DELETE FROM reports WHERE uid NOT IN (SELECT uid FROM members WHERE expires>?)',(time.time(),))
 def member(uid):
  with core.db() as c:return bool(c.execute('SELECT 1 FROM members WHERE uid=? AND expires>?',(uid,time.time())).fetchone())
 def persist(uid,v,analysis=None):
  value={'profile':v['profile'],'chart':v['chart']}
  if analysis is not None:value['analysis']=analysis
  hid=core.digest(uid+json.dumps(value,sort_keys=True))
  with core.db() as c:
   # Serialize against account deletion so an in-flight AI job cannot restore history.
   lock=' FOR UPDATE' if core.storage.backend()=='mysql' else ''
   if not c.execute('SELECT uid FROM members WHERE uid=? AND expires>?'+lock,(uid,time.time())).fetchone():return
   c.execute('INSERT OR REPLACE INTO history VALUES(?,?,?,?)',(hid,uid,time.time(),json.dumps(value)))
 def auth(header):return core.user(header),core.digest(header[7:])
 def prune():
  now=time.time()
  for collection in (CURRENT,PLACES,JOBS,LIMITS):
   for k,v in list(collection.items()):
    if v['expires']<now:collection.pop(k,None)
 def janitor():
  while True:
   time.sleep(60)
   with LOCK:prune()
 threading.Thread(target=janitor,daemon=True).start()
 def get_current(key):
  with LOCK:
   prune();v=CURRENT.get(key)
   if not v:raise HTTPException(409,'本次查询已结束，请重新填写出生资料')
   return v
 def clear(key):
  with LOCK:
   CURRENT.pop(key,None)
   for col in (PLACES,JOBS):
    for k,v in list(col.items()):
     if v.get('owner')==key:col.pop(k,None)
 def payload(body,key):
  with LOCK:
   prune();place=PLACES.get(body.placeToken)
   if not place or place['owner']!=key:raise HTTPException(422,'地点确认已失效，请重新查询地点')
   p=place['value']
  return {'date':body.date,'time':body.time,'accuracy':0,'placeLabel':p['placeLabel'],'latitude':p['latitude'],'longitude':p['longitude'],'timezone':'Asia/Shanghai','coordinateSystem':'WGS84','fold':body.fold,'consent':True}
 def period_check(period):
  import re
  if not re.fullmatch(r'(19\d{2}|20\d{2}|2100)(-(0[1-9]|1[0-2]))?',period):raise HTTPException(422,'请选择有效年份或月份')
 def basic(chart,period):
  period_check(period)
  if len(period)==4:
   months=[monthly(chart,f'{period}-{m:02}') for m in range(1,13)]
   return {'period':period,'theme':'年度个人周期','summary':'按月中行运快照阅读这一年','sections':[{'title':m['period']+' · '+m['theme'],'text':m['summary'],'basis':'\n'.join(e['basis'] for e in m['events'])} for m in months],'events':[],'free':True,'note':'月中采样，不代表精确事件日期。'}
  return monthly(chart,period)
 @app.get('/v1/me')
 def me(authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  return {'member':member(uid),'profile':None,'chart':None}
 @app.post('/v1/session/reset')
 def reset(authorization:str|None=Header(default=None)):
  uid,key=auth(authorization);clear(key);return {'ok':True,'member':member(uid)}
 @app.post('/v1/places/resolve')
 async def resolve(body:PlaceRequest,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  with LOCK:
   prune();limit=LIMITS.setdefault('geo:'+uid,{'expires':time.time()+60,'count':0})
   if limit['count']>=15:raise HTTPException(429,'地点查询过于频繁，请稍后再试')
   limit['count']+=1
  value=await providers.geocode(body.address);token=secrets.token_urlsafe(24)
  with LOCK:PLACES[token]={'owner':key,'value':value,'expires':time.time()+TTL}
  return dict(value,placeToken=token)
 @app.put('/v1/profile')
 def profile(body:Birth,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization);core.licensing();p=payload(body,key)
  try:chart=calculate(p)
  except (ValueError,OverflowError) as e:raise HTTPException(422,str(e))
  revision=core.digest(json.dumps(p,sort_keys=True)+VERSION)
  with LOCK:
   # A new chart invalidates outstanding AI requests for the previous one.
   for k,v in list(JOBS.items()):
    if v['owner']==key:JOBS.pop(k,None)
   CURRENT[key]={'profile':dict(p,revision=revision),'chart':chart,'expires':time.time()+TTL,'reports':{}}
  persist(uid,get_current(key))
  core.touch(uid)
  return {'profile':dict(p,revision=revision),'chart':chart,'member':member(uid)}
 @app.get('/v1/reports/{period}')
 def report(period:str,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization);core.licensing();v=get_current(key);period_check(period)
  with LOCK:result=v['reports'].get(period)
  if result is None:
   result=basic(v['chart'],period);result['generatedAt']=datetime.now(timezone.utc).isoformat()
   with LOCK:v['reports'][period]=result
  persist(uid,v,dict(result,title=result.get('theme','周期报告'),isAI=False))
  core.touch(uid);return result
 @app.post('/v1/history')
 def save(body:SaveRequest,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  if not member(uid):raise HTTPException(403,'只有会员可以保存查询记录；本次分析仍可免费查看')
  v=get_current(key);value={'profile':v['profile'],'chart':v['chart']}
  if body.jobId:raise HTTPException(410,'本版本不再支持在线生成任务')
  hid=core.digest(uid+json.dumps(value,sort_keys=True))
  with core.db() as c:c.execute('INSERT OR REPLACE INTO history VALUES(?,?,?,?)',(hid,uid,time.time(),json.dumps(value)))
  return {'id':hid}
 @app.get('/v1/history')
 def history(authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  if not member(uid):raise HTTPException(403,'请微信登录成为免费会员后查看历史记录')
  with core.db() as c:rows=c.execute('SELECT id,created,body FROM history WHERE uid=? ORDER BY created DESC LIMIT 100',(uid,)).fetchall()
  return {'items':[{'id':x['id'],'created':datetime.fromtimestamp(x['created'],timezone.utc).isoformat(),'title':json.loads(x['body']).get('analysis',{}).get('title','星盘查询'),'date':json.loads(x['body'])['profile']['date']} for x in rows]}
 @app.get('/v1/history/{hid}')
 def history_detail(hid:str,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  if not member(uid):raise HTTPException(403,'会员权益已失效')
  with core.db() as c:row=c.execute('SELECT body FROM history WHERE id=? AND uid=?',(hid,uid)).fetchone()
  if not row:raise HTTPException(404,'记录不存在')
  return json.loads(row['body'])
 @app.post('/v1/auth/logout')
 def logout(authorization:str|None=Header(default=None)):
  uid,key=auth(authorization);clear(key);core.GUESTS.pop(key,None)
  with core.db() as c:c.execute('DELETE FROM sessions WHERE hash=?',(key,))
  return {'ok':True}
 @app.delete('/v1/account/data')
 def delete(authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  with core.db() as c:
   lock=' FOR UPDATE' if core.storage.backend()=='mysql' else ''
   c.execute('SELECT uid FROM members WHERE uid=?'+lock,(uid,)).fetchone()
   keys=[x['hash'] for x in c.execute('SELECT hash FROM sessions WHERE uid=?',(uid,))]
   for table,col in [('sessions','uid'),('reports','uid'),('activity','uid'),('history','uid'),('members','uid'),('users','id')]:c.execute(f'DELETE FROM {table} WHERE {col}=?',(uid,))
  for key in keys:clear(key)
  return {'ok':True}
