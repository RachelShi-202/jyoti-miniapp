import concurrent.futures,json
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
import app,operations
from storage import Store
from auth import Auth
from conftest import login_client

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 store=Store(tmp_path/'private.sqlite3');monkeypatch.setattr(app,'store',store);monkeypatch.setattr(app,'auth',Auth(store));app.sessions.clear();app.limits.clear()
 return store

def request(peer,headers):return Request({'type':'http','client':(peer,1),'headers':[(k.encode(),v.encode()) for k,v in headers.items()]})
def test_forwarded_ip_requires_token_and_trusted_peer(monkeypatch):
 monkeypatch.setenv('TRUSTED_PROXY_TOKEN','secret')
 headers={'x-xingxu-client-ip':'8.8.8.8','x-xingxu-proxy-token':'secret'}
 assert operations.client_ip(request('172.17.0.1',headers))=='8.8.8.8'
 assert operations.client_ip(request('1.2.3.4',headers))=='1.2.3.4'
 assert operations.client_ip(request('172.17.0.1',{'x-forwarded-for':'8.8.8.8'}))=='172.17.0.1'
 assert operations.client_ip(request('172.17.0.1',{**headers,'x-xingxu-client-ip':'8.8.8.8,1.1.1.1'}))=='172.17.0.1'

def test_metrics_are_aggregate_and_allowlisted(isolated):
 operations.record(isolated,'ai_timeout');operations.record(isolated,'USER_EMAIL_SECRET')
 v=operations.snapshot(operations.path(isolated));assert v['counts']=={'ai_timeout':1}
 assert 'USER_EMAIL_SECRET' not in json.dumps(v)

def test_persistent_account_limits_are_independent(isolated):
 request_=request('127.0.0.1',{})
 def burst(owner):
  context=app.viewer.set(owner)
  try:
   accepted=0
   for _ in range(20):app.throttle(request_,'ai',20);accepted+=1
   return accepted
  finally:app.viewer.reset(context)
 with concurrent.futures.ThreadPoolExecutor(8) as pool:assert sum(pool.map(burst,[f'u{i}' for i in range(40)]))==800
 token=app.viewer.set('u0')
 try:
  with pytest.raises(app.HTTPException):app.throttle(request_,'ai',20)
  app.limits.clear()
  with pytest.raises(app.HTTPException):app.throttle(request_,'ai',20)
 finally:app.viewer.reset(token)
 assert operations.snapshot(operations.path(isolated))['counts']['service_ai_limit']==2

def test_provider_1113_is_balance_not_rate(isolated,monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test');c=TestClient(app.app);login_client(c)
 p={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'consent':True}
 token=c.post('/api/chart',json=p).json()['session']
 class Fake:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def post(self,url,**kwargs):return app.httpx.Response(429,json={'error':{'code':'1113','message':'SECRET_DETAIL'}},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 response=c.post('/api/interpret',json={'session':token,'consent':True})
 assert response.status_code==502 and 'AI_BALANCE' in response.json()['detail'] and 'SECRET_DETAIL' not in response.text
 assert operations.snapshot(operations.path(isolated))['counts']['ai_balance']==1
 assert c.get('/api/account/entitlements').json()['remaining']['natal']==1

def test_mail_send_failures_and_success_are_counted_without_target(isolated,monkeypatch):
 import auth as auth_module
 c=TestClient(app.app)
 def fail(*args):raise RuntimeError('PRIVATE_EMAIL_AND_SECRET')
 monkeypatch.setattr(auth_module,'send_code',fail)
 r=c.post('/api/auth/code',json={'channel':'email','target':'private@example.com'})
 assert r.status_code==503 and 'PRIVATE_EMAIL_AND_SECRET' not in r.text
 v=operations.snapshot(operations.path(isolated));assert v['counts']['mail_failure']==1 and 'private@example.com' not in json.dumps(v)
 monkeypatch.setattr(auth_module,'send_code',lambda *args:None)
 assert c.post('/api/auth/code',json={'channel':'email','target':'another@example.com'}).status_code==200
 assert operations.snapshot(operations.path(isolated))['counts']['mail_success']==1
