import httpx

import os,sys,time,json,asyncio
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['JYOTI_DB']=os.environ['TEST_JYOTI_DB']
os.environ['ALLOW_LOCAL_LOGIN']='1'
import main,features,providers
from fastapi.testclient import TestClient
client=TestClient(main.app)
P={'date':'1995-05-12','time':'08:30','fold':None,'consent':True}
def auth(uid):return {'Authorization':'Bearer '+main.create_session(uid)['token']}
@pytest.fixture(autouse=True)
def geo(monkeypatch):
 async def fake(address):return {'placeLabel':address,'latitude':23.1291,'longitude':113.2644,'timezone':'Asia/Shanghai','coordinateSystem':'WGS84','adcode':'440106'}
 monkeypatch.setattr(providers,'geocode',fake)
def profile(headers,date='1995-05-12'):
 place=client.post('/v1/places/resolve',headers=headers,json={'address':'广东省广州市天河区'}).json()
 p=dict(P,date=date,placeToken=place['placeToken'])
 response=client.put('/v1/profile',headers=headers,json=p);assert response.status_code==200,response.text
 return p,response.json()
def test_guest_blocked():
 assert client.post('/v1/places/resolve',json={'address':'广东省广州市'}).status_code==401
 assert client.get('/v1/reports/2026-09').status_code==401

def test_free_not_persisted_and_reset():
 a=auth('free');p,result=profile(a)
 assert result['chart']['status']=='calculated'
 assert client.get('/v1/reports/2026-09',headers=a).status_code==200
 assert client.post('/v1/history',headers=a,json={}).status_code==403
 with main.db() as c:
  assert c.execute('SELECT profile FROM users WHERE id=?',('free',)).fetchone()['profile'] is None
  assert c.execute('SELECT COUNT(*) FROM reports WHERE uid=?',('free',)).fetchone()[0]==0
 assert client.post('/v1/session/reset',headers=a).status_code==200
 assert client.get('/v1/reports/2026-09',headers=a).status_code==409

def test_member_history_and_isolation():
 a=auth('member');b=auth('outsider')
 with main.db() as c:c.execute('INSERT OR REPLACE INTO members VALUES(?,?)',('member',time.time()+3600))
 profile(a);hid=client.post('/v1/history',headers=a,json={}).json()['id']
 client.post('/v1/session/reset',headers=a)
 assert client.get('/v1/history/'+hid,headers=a).status_code==200
 assert client.get('/v1/history/'+hid,headers=b).status_code==403
 client.delete('/v1/account/data',headers=a)
 with main.db() as c:assert not c.execute('SELECT 1 FROM history WHERE uid=?',('member',)).fetchone()

def test_location_token_cannot_cross_accounts():
 a=auth('placeA');b=auth('placeB')
 token=client.post('/v1/places/resolve',headers=a,json={'address':'广东省广州市'}).json()['placeToken']
 assert client.put('/v1/profile',headers=b,json=dict(P,placeToken=token)).status_code==422
 assert client.put('/v1/profile',headers=a,json=dict(P,placeToken=token,accuracy=2)).status_code==422

def test_ai_consent_async_idempotency_and_pair(monkeypatch):
 a=auth('ai');b=auth('ai-other');p,_=profile(a)
 monkeypatch.setenv('AI_API_KEY','fake-test-key')
 seen=[]
 def explain(facts,kind):
  seen.append((facts,kind));return {'title':'Test','summary':'Test','sections':[],'isAI':True}
 monkeypatch.setattr(providers,'explain',explain)
 assert client.post('/v1/ai/jobs',headers=a,json={'kind':'natal','consent':False}).status_code==422
 body={'kind':'synastry','consent':True,'partner':dict(p,date='1996-06-02')}
 reply=client.post('/v1/ai/jobs',headers=a,json=body);assert reply.status_code==200,reply.text
 jid=reply.json()['jobId']
 for _ in range(20):
  j=client.get('/v1/ai/jobs/'+jid,headers=a).json()
  if j['status']=='done':break
  time.sleep(.01)
 assert j['status']=='done'
 assert client.get('/v1/ai/jobs/'+jid,headers=b).status_code==404
 assert client.post('/v1/ai/jobs',headers=a,json=body).json()['jobId']==jid
 assert any(f['id'].startswith('B-') for f in seen[0][0])
 assert not any('广东' in f['text'] or '1995-05-12' in f['text'] for f in seen[0][0])
 client.post('/v1/session/reset',headers=a)
 assert client.get('/v1/ai/jobs/'+jid,headers=a).status_code==404

def test_mainland_response_restriction(monkeypatch):
 # Restore actual geocoder for this test.
 import importlib
 importlib.reload(providers);monkeypatch.setenv('TENCENT_MAP_KEY','test')
 class Fake:
  def __init__(self,**k):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def get(self,*a,**k):return type('R',(),{'raise_for_status':lambda s:None,'json':lambda s:{'status':0,'result':{'ad_info':{'adcode':'810000'},'location':{'lat':22.3,'lng':114.2}}}})()
 monkeypatch.setattr(providers.httpx,'AsyncClient',Fake)
 from fastapi import HTTPException
 with pytest.raises(HTTPException) as e:asyncio.run(providers.geocode('Hong Kong'))
 assert e.value.status_code==422

def test_gcj_conversion_and_expiration():
 lat,lon=providers.gcj_to_wgs(39.910226,116.403714)
 assert abs(lat-39.908823)<.0001 and abs(lon-116.397470)<.0001
 a=auth('expired');profile(a)
 key=main.digest(a['Authorization'][7:]);features.CURRENT[key]['expires']=time.time()-1
 assert client.get('/v1/reports/2026-09',headers=a).status_code==409

def test_ai_provider_schema_and_evidence(monkeypatch):
 monkeypatch.setenv('AI_API_KEY','provider-test-only')
 response={'title':'测试','summary':'摘要','sections':[{'title':title,'strengths':'优势解释','cautions':'留意沟通习惯','evidenceIds':['A-太阳']} for title in ['性格','事业','爱情','婚姻','财富']]}
 class Fake:
  def __init__(self,**k):pass
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def post(self,url,headers,json):
   assert url=='https://api.deepseek.com/chat/completions'
   assert json['response_format']=={'type':'json_object'}
   return type('R',(),{'status_code':200,'raise_for_status':lambda s:None,'json':lambda s:{'choices':[{'finish_reason':'stop','message':{'content':__import__('json').dumps(response)}}]}})()
 monkeypatch.setattr(providers.httpx,'Client',Fake)
 result=providers.explain([{'id':'A-太阳','text':'太阳白羊'}],'natal')
 assert result['isAI'] and result['sections'][0]['strengths']=='优势解释'
 assert all('basis' not in s and 'evidenceIds' not in s for s in result['sections'])
 response['sections'][0]['evidenceIds']=['fabricated']
 with pytest.raises(ValueError,match='无效依据'):providers.explain([{'id':'A-太阳','text':'太阳白羊'}],'natal')

def test_guest_session_has_no_persistent_identity_or_history():
 session=client.post('/v1/auth/guest').json();a={'Authorization':'Bearer '+session['token']}
 uid=main.user(a['Authorization']);assert uid.startswith('guest:')
 profile(a)
 assert client.get('/v1/reports/2026-09',headers=a).status_code==200
 with main.db() as c:
  for table,col in [('users','id'),('history','uid'),('activity','uid'),('sessions','uid')]:
   assert not c.execute(f'SELECT 1 FROM {table} WHERE {col}=?',(uid,)).fetchone()
 assert client.post('/v1/history',headers=a,json={}).status_code==403
 client.post('/v1/auth/logout',headers=a)
 assert client.get('/v1/me',headers=a).status_code==401

def test_wechat_free_member_and_automatic_history(monkeypatch):
 monkeypatch.setenv('WX_APP_SECRET','test-secret')
 monkeypatch.setenv('WX_APP_ID','wx-test-fixture')
 class Fake:
  def __init__(self,**k):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def get(self,*a,**k):return type('R',(),{'raise_for_status':lambda s:None,'json':lambda s:{'openid':'member-fixture'}})()
 monkeypatch.setattr(main.httpx,'AsyncClient',Fake)
 session=client.post('/v1/auth/wechat',json={'code':'test-code'}).json();a={'Authorization':'Bearer '+session['token']}
 assert client.get('/v1/me',headers=a).json()['member']
 profile(a)
 assert len(client.get('/v1/history',headers=a).json()['items'])==1
 client.get('/v1/reports/2026-09',headers=a)
 assert len(client.get('/v1/history',headers=a).json()['items'])==2
 monkeypatch.setenv('AI_API_KEY','test-only')
 monkeypatch.setattr(providers,'explain',lambda *a:{'title':'自动AI保存','summary':'test','sections':[]})
 jid=client.post('/v1/ai/jobs',headers=a,json={'kind':'natal','consent':True}).json()['jobId']
 for _ in range(100):
  if client.get('/v1/ai/jobs/'+jid,headers=a).json()['status']=='done':break
  time.sleep(.01)
 assert len(client.get('/v1/history',headers=a).json()['items'])==3
 client.post('/v1/session/reset',headers=a)
 assert len(client.get('/v1/history',headers=a).json()['items'])==3

def test_open_source_release_no_legacy_activation(monkeypatch):
 monkeypatch.setenv('JYOTI_ENV','production')
 monkeypatch.setenv('ASTRO_LICENSE_CONFIRMED','0')
 main.licensing()
 assert client.get('/source').json()['license']=='AGPL-3.0-or-later'

def test_health_requires_both_wechat_settings_and_hides_secret(monkeypatch):
 monkeypatch.setenv('WX_APP_SECRET','test-sensitive-fixture')
 monkeypatch.delenv('WX_APP_ID',raising=False)
 r=client.get('/health')
 assert not r.json()['wechatConfigured']
 assert 'test-sensitive-fixture' not in r.text

def test_wechat_strips_copy_whitespace_and_keeps_error_code(monkeypatch):
 monkeypatch.setenv('WX_APP_ID',' wx-fixture \n')
 monkeypatch.setenv('WX_APP_SECRET',' test-sensitive-fixture \n')
 class Fake:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def get(self,url,params):
   assert params['appid']=='wx-fixture'
   assert params['secret']=='test-sensitive-fixture'
   return type('R',(),{'raise_for_status':lambda s:None,'json':lambda s:{'errcode':40125,'errmsg':'test-sensitive-fixture'}})()
 monkeypatch.setattr(main.httpx,'AsyncClient',Fake)
 r=client.post('/v1/auth/wechat',json={'code':'fixture'})
 assert r.status_code==502 and '40125' in r.text
 assert 'test-sensitive-fixture' not in r.text

@pytest.mark.parametrize('failure,expected',[(httpx.TimeoutException('secret-fixture'),'WX_TIMEOUT'),(httpx.ConnectError('secret-fixture'),'WX_CONNECT'),(ValueError('secret-fixture'),'WX_RESPONSE')])
def test_wechat_safe_transport_diagnostics(monkeypatch,failure,expected):
 monkeypatch.setenv('WX_APP_ID','wx-fixture')
 monkeypatch.setenv('WX_APP_SECRET','secret-fixture')
 class Fake:
  def __init__(self,**kwargs):assert kwargs['trust_env'] is False
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def get(self,*args,**kwargs):raise failure
 monkeypatch.setattr(main.httpx,'AsyncClient',Fake)
 response=client.post('/v1/auth/wechat',json={'code':'fixture'})
 assert response.status_code==502 and expected in response.text
 assert 'secret-fixture' not in response.text
