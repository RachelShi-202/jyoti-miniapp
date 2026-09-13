import os,time,secrets,threading,json,asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
from fastapi import Header,HTTPException
from astro import calculate,monthly,VERSION
import providers
TTL=7200
LOCK=threading.RLock();CURRENT={};PLACES={};JOBS={};LIMITS={}
POOL=ThreadPoolExecutor(max_workers=2)
class PlaceRequest(BaseModel):
 address:str=Field(min_length=4,max_length=200)
class Birth(BaseModel):
 model_config=ConfigDict(extra='forbid')
 date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
 time:str=Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
 placeToken:str=Field(min_length=1,max_length=100)
 fold:Literal[0,1]|None=None
 consent:Literal[True]
class AIRequest(BaseModel):
 kind:Literal['natal','transit','month','year','synastry']
 period:str=Field(default='',max_length=7)
 consent:Literal[True]
 partner:Birth|None=None
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
 def facts_for(chart,prefix):
  facts=[]
  for p in chart['planets']:
   facts.append({'id':prefix+p['name'],'text':f"{prefix} {p['name']}：{p['sign']} {p['degree']}°，本命第{p['house']}宫，逆行={p['retrograde']}"})
  facts.append({'id':prefix+'asc','text':f"{prefix}上升：{chart['ascendant']['sign']} {chart['ascendant']['degree']}°；月宿：{chart['moonNakshatra']['name']} Pada {chart['moonNakshatra']['pada']}"})
  return facts
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
 @app.post('/v1/ai/jobs')
 def ai(body:AIRequest,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization);v=get_current(key);core.licensing()
  if not os.getenv('AI_API_KEY'):raise HTTPException(503,'AI 服务尚未配置，请先在本机填写 DeepSeek Key')
  facts=facts_for(v['chart'],'A-')
  if body.kind in ('month','year','transit'):
   period=body.period or datetime.now().strftime('%Y-%m')
   if body.kind=='year' and len(period)!=4:raise HTTPException(422,'年度分析请选择年份')
   if body.kind in ('month','transit') and len(period)!=7:raise HTTPException(422,'月度/星象分析请选择月份')
   b=basic(v['chart'],period)
   for i,s in enumerate(b['sections']):facts.append({'id':'period-'+str(i),'text':s['title']+' '+s['text']+' '+s.get('basis','')})
  if body.kind=='synastry':
   if not body.partner:raise HTTPException(422,'请填写并确认对方出生资料与授权')
   try:other=calculate(payload(body.partner,key))
   except ValueError as e:raise HTTPException(422,str(e))
   facts+=facts_for(other,'B-')
   for p in v['chart']['planets']:
    for q in other['planets']:
     if p['name'] in ('太阳','月亮','金星','火星') and q['name'] in ('太阳','月亮','金星','火星'):
      angle=abs(p['longitude']-q['longitude']);angle=min(angle,360-angle)
      facts.append({'id':'pair-'+p['name']+'-'+q['name'],'text':f"A的{p['name']}与B的{q['name']}黄经最小夹角 {angle:.2f}°；为几何关系，非印占特殊相位或婚配评分。"})
  signature=core.digest(json.dumps(['five-dimensions-v1',body.kind,body.period,facts],ensure_ascii=False))
  with LOCK:
   prune()
   for jid,j in JOBS.items():
    if j['owner']==key and j['signature']==signature and j['status'] in ('pending','done'):return {'jobId':jid,'status':j['status']}
   limit=LIMITS.setdefault('ai:'+uid,{'expires':time.time()+86400,'count':0})
   if limit['count']>=int(os.getenv('AI_DAILY_LIMIT','10')):raise HTTPException(429,'今日 AI 试用次数已用完')
   if sum(j['status']=='pending' for j in JOBS.values())>=4:raise HTTPException(429,'AI 正忙，请稍后重试')
   limit['count']+=1;jid=secrets.token_urlsafe(24)
   JOBS[jid]={'owner':key,'signature':signature,'status':'pending','expires':time.time()+TTL,'kind':body.kind}
  def work():
   try:result=providers.explain(facts,body.kind);state='done'
   except Exception as e:result={'message':str(e) if isinstance(e,ValueError) else 'AI 服务异常，请重试'};state='failed'
   with LOCK:
    if jid in JOBS:
     JOBS[jid].update(status=state,result=result)
     if state=='done':persist(uid,v,result)
  POOL.submit(work);return {'jobId':jid,'status':'pending'}
 @app.get('/v1/ai/jobs/{jid}')
 def job(jid:str,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  with LOCK:
   prune();j=JOBS.get(jid)
   if not j or j['owner']!=key:raise HTTPException(404,'分析不存在或已结束')
   return {'jobId':jid,'status':j['status'],'result':j.get('result')}
 @app.post('/v1/history')
 def save(body:SaveRequest,authorization:str|None=Header(default=None)):
  uid,key=auth(authorization)
  if not member(uid):raise HTTPException(403,'只有会员可以保存查询记录；本次分析仍可免费查看')
  v=get_current(key);value={'profile':v['profile'],'chart':v['chart']}
  if body.jobId:
   j=job(body.jobId,authorization)
   if j['status']!='done':raise HTTPException(409,'分析尚未完成')
   value['analysis']=j['result']
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
