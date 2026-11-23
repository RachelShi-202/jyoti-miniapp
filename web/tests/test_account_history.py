import json,time,sqlite3
from fastapi.testclient import TestClient
import app
from auth import Auth
from storage import Store
from conftest import login_client
import pytest

P={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'consent':True}

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 store=Store(tmp_path/'private.sqlite3');monkeypatch.setattr(app,'store',store);monkeypatch.setattr(app,'auth',Auth(store));app.sessions.clear();app.limits.clear()
 yield store
 app.sessions.clear();app.limits.clear()

def test_every_service_requires_login(isolated):
 c=TestClient(app.app)
 for method,url,body in [('post','/api/chart',P),('post','/api/place',{'address':'上海市人民广场'}),('get','/api/annual/2026',None),('get','/api/session',None),('post','/api/interpret',{'session':'x','consent':True}),('post','/api/interpret/start',{'session':'x','consent':True}),('get','/api/interpret/result',None),('get','/api/account/reports',None)]:
  assert c.request(method,url,json=body).status_code==401
 assert c.get('/').status_code==200
 assert c.get('/api/auth/me').json()['user'] is None

def test_free_paid_archive_restart_isolation_and_stable_ids(isolated,monkeypatch):
 c=TestClient(app.app);owner=login_client(c);token=c.post('/api/chart',json=P).json()['session']
 assert c.get('/api/annual/2026',headers={'X-Jyoti-Session':token}).status_code==200
 app.sessions[token]['reports']['annual-basic:2026']='过去免费生成的流年基础报告'
 value=app.sessions[token];value['reports'].update({'natal:':'免费本命正文','paid:topic:1':'已生成的专题正文'})
 value['reportProducts']={'paid:topic:1':{'product':'topic','kind':'topic'}}
 value['followups']={'natal:':[{'question':'追问','answer':'已保存回答'}]}
 isolated.save(token,value)
 chart_id=value['recordId']
 items=c.get('/api/account/reports').json()['items'];assert len(items)==3
 paid=next(item for item in items if item['product']=='topic')
 other=TestClient(app.app);login_client(other,'another@example.com')
 assert other.get('/api/account/reports').json()['items']==[]
 assert other.get('/api/account/reports/'+paid['id']).status_code==404
 # Reload database and auth while retaining the signed-in browser's opaque cookie.
 app.sessions.clear();reopened=Store(isolated.path);monkeypatch.setattr(app,'store',reopened);monkeypatch.setattr(app,'auth',Auth(reopened))
 reopened.cleanup()
 assert c.get('/api/account/charts').json()['items'][0]['id']==chart_id
 opened=c.post('/api/account/charts/'+chart_id+'/open',json={}).json()['session']
 assert c.get('/api/account/charts').json()['items'][0]['id']==chart_id
 assert len(c.get('/api/account/reports').json()['items'])==3
 assert c.get('/api/account/reports/'+paid['id']).json()['text']=='已生成的专题正文'
 natal=next(item for item in items if item['scope']=='natal:')
 assert c.get('/api/account/reports/'+natal['id']).json()['followups'][0]['answer']=='已保存回答'
 c.post('/api/auth/logout',json={})
 assert c.get('/api/account/reports/'+paid['id']).status_code==401
 login_client(c)
 assert c.delete('/api/session',headers={'X-Jyoti-Session':opened}).status_code==200
 assert c.get('/api/account/reports').json()['items']==[]

def test_existing_owner_record_migrates_without_expiry(tmp_path):
 path=tmp_path/'legacy.sqlite3';value={'owner':'existing-user','expires':1,'chart':{},'reports':{'natal:':'旧报告'},'followups':{}}
 with sqlite3.connect(path) as db:
  db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,payload TEXT NOT NULL,expires REAL NOT NULL,updated REAL NOT NULL)')
  db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('old-hash',json.dumps(value),1,time.time()))
 store=Store(path);store.cleanup()
 with store.connect() as db:
  row=db.execute('SELECT record_id,expires FROM sessions').fetchone()
  assert row[0]=='old-hash' and row[1]>time.time()+365*86400
  assert db.execute('SELECT text FROM saved_reports').fetchone()[0]=='旧报告'

def make_archived_chart(c,store):
 token=c.post('/api/chart',json=P).json()['session'];value=app.sessions[token]
 value['reports']={'natal:':'本命正文','natal::round2:abc':'追问正文','annual:2026':'年度正文'}
 value['followups']={'natal:':[{'question':'问题','answer':'答案'}]}
 value['jobs']={'natal:':{'state':'completed','text':'本命正文'},'natal::round2:abc':{'state':'completed','text':'追问正文'}}
 store.save(token,value)
 reports=c.get('/api/account/reports').json()['items']
 return token,value,next(r for r in reports if r['scope']=='annual:2026')

def test_delete_report_preserves_chart_and_other_report_without_resurrection(isolated,monkeypatch):
 c=TestClient(app.app);login_client(c)
 token,value,report=make_archived_chart(c,isolated)
 assert c.delete('/api/account/reports/'+report['id']).status_code==200
 assert c.get('/api/account/reports/'+report['id']).status_code==404
 assert c.delete('/api/account/reports/'+report['id']).status_code==404
 assert value['reports']=={'natal:':'本命正文','natal::round2:abc':'追问正文'}
 assert value['followups']=={'natal:':[{'question':'问题','answer':'答案'}]} and set(value['jobs'])=={'natal:','natal::round2:abc'}
 assert c.get('/api/account/charts').json()['items'][0]['reportCount']==1
 # A later save and a process restart must not recreate the deleted archive.
 isolated.save(token,value);app.sessions.clear()
 restarted=Store(isolated.path);monkeypatch.setattr(app,'store',restarted)
 assert [r['scope'] for r in c.get('/api/account/reports').json()['items']]==['natal:']
 restored=c.post('/api/account/charts/'+value['recordId']+'/open',json={}).json()['session']
 state=c.get('/api/session',headers={'X-Jyoti-Session':restored}).json()
 assert state['reports']=={'natal:':'本命正文','natal::round2:abc':'追问正文'} and state['followups']=={'natal:':[{'question':'问题','answer':'答案'}]}

def test_natal_report_cannot_be_deleted_separately(isolated):
 c=TestClient(app.app);login_client(c)
 token,value,annual=make_archived_chart(c,isolated)
 natal=next(r for r in c.get('/api/account/reports').json()['items'] if r['scope']=='natal:')
 assert c.delete('/api/account/reports/'+natal['id']).status_code==409
 assert c.get('/api/account/reports/'+natal['id']).status_code==200

def test_delete_chart_cascades_and_invalidates_session(isolated):
 c=TestClient(app.app);login_client(c)
 token,value,report=make_archived_chart(c,isolated)
 other_token=c.post('/api/chart',json=P).json()['session']
 chart_id=value['recordId']
 assert c.delete('/api/account/charts/'+chart_id).status_code==200
 assert c.get('/api/account/reports').json()['items']==[]
 assert len(c.get('/api/account/charts').json()['items'])==1
 assert c.get('/api/session',headers={'X-Jyoti-Session':token}).status_code==410
 assert c.post('/api/account/charts/'+chart_id+'/open',json={}).status_code==404
 assert c.get('/api/session',headers={'X-Jyoti-Session':other_token}).status_code==200
 isolated.save(token,value)
 assert isolated.load(token) is None

def test_delete_requires_owner_and_blocks_pending_generation(isolated):
 c=TestClient(app.app);login_client(c)
 token,value,report=make_archived_chart(c,isolated)
 other=TestClient(app.app);login_client(other,'other-delete@example.com')
 for path in ('charts/'+value['recordId'],'reports/'+report['id']):
  assert TestClient(app.app).delete('/api/account/'+path).status_code==401
  assert other.delete('/api/account/'+path).status_code==404
 value['jobs']['natal:']={'state':'pending'}
 for path in ('charts/'+value['recordId'],'reports/'+report['id']):assert c.delete('/api/account/'+path).status_code==409
 value['jobs'].clear();value['busy']=True
 assert c.delete('/api/account/reports/'+report['id']).status_code==409
 value['busy']=False
 assert c.get('/api/account/reports/'+report['id']).status_code==200

def test_delete_report_after_restart_without_loaded_cache(isolated,monkeypatch):
 c=TestClient(app.app);login_client(c)
 token,value,report=make_archived_chart(c,isolated);chart_id=value['recordId']
 app.sessions.clear();monkeypatch.setattr(app,'store',Store(isolated.path))
 assert c.delete('/api/account/reports/'+report['id']).status_code==200
 reopened=c.post('/api/account/charts/'+chart_id+'/open',json={}).json()['session']
 assert 'annual:2026' not in c.get('/api/session',headers={'X-Jyoti-Session':reopened}).json()['reports']
 assert len(c.get('/api/account/reports').json()['items'])==1
