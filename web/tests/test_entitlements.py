import asyncio,hashlib,json,time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
import app,entitlements
from auth import Auth
from storage import Store
from conftest import login_client

P={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'consent':True}
VALID_NATAL_REPORT='命'*1800
@pytest.fixture
def env(tmp_path,monkeypatch):
 store=Store(tmp_path/'test.sqlite3');monkeypatch.setattr(app,'store',store);monkeypatch.setattr(app,'auth',Auth(store));monkeypatch.setenv('ZHIPU_API_KEY','test')
 app.sessions.clear();app.limits.clear()
 calls=[]
 class Fake:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def post(self,url,**kwargs):
   calls.append(kwargs['json'])
   return app.httpx.Response(200,json={'choices':[{'message':{'content':VALID_NATAL_REPORT}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 yield store,calls
 app.sessions.clear();app.limits.clear()

def invitation(store,code='XY-TEST-VALID-CODE',expires=None):
 with store.connect() as db:db.execute('INSERT INTO invite_codes VALUES (?,?,1,0)',(hashlib.sha256(code.encode()).hexdigest(),expires or time.time()+3600))
 return code

def chart(c):return c.post('/api/chart',json=P).json()['session']
def body(token,**kwargs):return {'session':token,'consent':True,**kwargs}

def test_each_chart_gets_one_cached_natal_and_restart_preserves_usage(env,monkeypatch):
 store,calls=env;c=TestClient(app.app);login_client(c)
 token=chart(c);b=body(token)
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==1
 assert c.post('/api/interpret',json=b).status_code==200
 assert c.post('/api/interpret',json=b).json()['cached']
 assert len(calls)==1
 token2=chart(c)
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==1
 assert c.post('/api/interpret',json=body(token2)).status_code==200
 assert c.post('/api/interpret',json=body(token2)).json()['cached']
 assert len(calls)==2
 app.sessions.clear();monkeypatch.setattr(app,'store',Store(store.path))
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==0
 assert c.post('/api/interpret',json=body(token2)).json()['cached']
 token3=chart(c)
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==1
 assert c.post('/api/interpret',json=body(token3)).status_code==200
 assert len(calls)==3

def test_failure_restores_credit(env,monkeypatch):
 store,calls=env;c=TestClient(app.app);login_client(c);token=chart(c)
 class Fail:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def post(self,url,**kwargs):raise app.httpx.ReadTimeout('timeout')
 previous=app.httpx.AsyncClient;monkeypatch.setattr(app.httpx,'AsyncClient',Fail)
 assert c.post('/api/interpret',json=body(token)).status_code==504
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==1
 monkeypatch.setattr(app.httpx,'AsyncClient',previous)
 assert c.post('/api/interpret',json=body(token)).status_code==200
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==0
 history=c.get('/api/account/entitlements').json()['history']
 assert any(item['state']=='released' for item in history) and any(item['state']=='consumed' and item['taskRef'] and item['reportRef'] for item in history)

def test_reservations_are_atomic_and_recover_after_restart(env):
 store,_=env
 store.save('atomic-token',{'owner':'owner','recordId':'chart-1','expires':time.time()+3600,'reports':{},'followups':{},'reportProducts':{}})
 def reserve():
  try:return entitlements.reserve(store,'owner','natal','chart-1')
  except app.HTTPException:return None
 with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:reserve(),range(2)))
 assert sum(r is not None for r in results)==1
 assert entitlements.summary(store,'owner')['natal']==0
 reopened=Store(store.path)
 assert entitlements.summary(reopened,'owner')['natal']==1

def test_login_required_single_use_idempotent_and_no_client_grants(env):
 store,_=env;code=invitation(store)
 c=TestClient(app.app)
 assert c.post('/api/account/redeem',json={'code':code}).status_code==401
 login_client(c)
 first=c.post('/api/account/redeem',json={'code':code.lower()}).json()
 assert first['remaining']['topic']==1 and not first['alreadyRedeemed']
 assert c.post('/api/account/redeem',json={'code':code}).json()['alreadyRedeemed']
 assert c.get('/api/account/entitlements').json()['remaining']['topic']==1
 other=TestClient(app.app);login_client(other,'second@example.com')
 assert other.post('/api/account/redeem',json={'code':code}).status_code==400
 assert other.get('/api/account/entitlements').json()['remaining']['topic']==0
 assert other.post('/api/interpret',json=body(chart(other),kind='topic',topicQuestion='事业',question='事业',selectedCharts=['d1','d10','d2'],isMember=True,paid=True)).status_code==402

def test_expired_revoked_concurrent_and_limit(env):
 store,_=env;expired=invitation(store,'XY-EXPIRED-CODE',time.time()-1);revoked=invitation(store,'XY-REVOKED-CODE')
 with store.connect() as db:db.execute('UPDATE invite_codes SET disabled=1 WHERE digest=?',(hashlib.sha256(revoked.encode()).hexdigest(),))
 for code in (expired,revoked):
  with pytest.raises(app.HTTPException):entitlements.redeem(store,'a',code)
 code=invitation(store,'XY-CONCURRENT-CODE')
 def redeem(owner):
  try:return entitlements.redeem(store,owner,code)
  except app.HTTPException:return None
 with ThreadPoolExecutor(2) as pool:assert sum(x is not None for x in pool.map(redeem,['a','b']))==1
 c=TestClient(app.app);login_client(c)
 for _ in range(10):assert c.post('/api/account/redeem',json={'code':'INVALID-CODE'}).status_code==400
 assert c.post('/api/account/redeem',json={'code':'INVALID-CODE'}).status_code==429

def test_topic_actual_report_five_followups_context_and_archive(env,monkeypatch):
 store,calls=env;c=TestClient(app.app);login_client(c);code=invitation(store)
 c.post('/api/account/redeem',json={'code':code});token=chart(c)
 request=body(token,kind='topic',topicQuestion='工作与收入怎样兼顾？',question='工作与收入怎样兼顾？',selectedCharts=['d1','d10','d2'],year=2026)
 assert c.post('/api/interpret',json=request).status_code==200
 assert c.get('/api/account/entitlements').json()['remaining']['topic']==0
 assert c.post('/api/interpret',json=request).json()['cached']
 for i in range(5):assert c.post('/api/interpret',json={**request,'round':2,'question':f'追问{i}'}).status_code==200
 assert c.post('/api/interpret',json={**request,'round':2,'question':'追问0'}).json()['cached']
 assert c.post('/api/interpret',json={**request,'round':2,'question':'追问6'}).status_code==429
 facts=json.loads(calls[-1]['messages'][1]['content'])
 assert len(facts['previousQuestions'])==4
 assert set(facts['divisions'])=={'d2','d10'} and facts['periodWindows']
 reports=c.get('/api/account/reports').json()['items'];assert len(reports)==1 and reports[0]['product']=='topic'
 report=c.get('/api/account/reports/'+reports[0]['id']).json()
 assert report['topicRequest']['selectedCharts']==['d1','d10','d2'] and len(report['followups'])==5
 app.sessions.clear();monkeypatch.setattr(app,'store',Store(store.path))
 assert c.get('/api/account/entitlements').json()['remaining']['topic']==0
 assert len(c.get('/api/account/reports/'+reports[0]['id']).json()['followups'])==5
 assert c.delete('/api/account/reports/'+reports[0]['id']).status_code==200
 assert c.post('/api/interpret',json=request).status_code==402

def test_legacy_completed_natal_counts_as_used(env):
 store,_=env;c=TestClient(app.app);owner=login_client(c);token=chart(c)
 value=app.sessions[token];value['reports']['natal:']='旧版免费报告';store.save(token,value)
 reopened=Store(store.path)
 assert entitlements.summary(reopened,owner)['natal']==0
