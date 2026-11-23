import time
from storage import Store

def test_restart_persistence_and_private_token(tmp_path):
 path=tmp_path/'records.sqlite3'
 store=Store(path)
 value={'expires':time.time()+3600,'chart':{'test':True},'reports':{'natal:':'已完成'},'followups':{'natal:':[{'question':'问题','answer':'回答'}]},'busy':True,'jobs':{'annual:2026':{'state':'pending'}}}
 store.save('private-token',value)
 restored=Store(path).load('private-token')
 assert restored['reports']==value['reports']
 assert restored['followups']==value['followups']
 assert not restored['busy']
 assert restored['jobs']['annual:2026']['state']=='failed'
 assert store.load('wrong-token') is None
 with store.connect() as db:
  assert db.execute('SELECT token_hash FROM sessions').fetchone()[0]!='private-token'
 store.delete('private-token')
 assert store.load('private-token') is None

def test_expiry_cleanup(tmp_path):
 store=Store(tmp_path/'records.sqlite3')
 store.save('expired',{'expires':0})
 assert store.load('expired') is None
 store.cleanup()
 with store.connect() as db:assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0

def test_api_restores_after_cache_loss():
 import app
 from fastapi.testclient import TestClient
 client=TestClient(app.app)
 from conftest import login_client
 login_client(client)
 p={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'consent':True}
 token=client.post('/api/chart',json=p).json()['session']
 app.sessions.clear()
 headers={'X-Jyoti-Session':token}
 restored=client.get('/api/session',headers=headers)
 assert restored.status_code==200 and restored.json()['profile']['date']==p['date']
 assert client.get('/api/session',headers={'X-Jyoti-Session':'wrong'}).status_code==410
 assert client.delete('/api/session',headers=headers).status_code==200
 assert client.get('/api/session',headers=headers).status_code==410
