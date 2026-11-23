import time
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from auth import Auth
from storage import Store
import auth as module
import app

@pytest.fixture
def setup(tmp_path,monkeypatch):
 a=Auth(Store(tmp_path/'auth.sqlite3'));sent=[]
 monkeypatch.setattr(module,'send_code',lambda channel,target,code:sent.append((channel,target,code)))
 return a,sent

def test_one_use_and_restart(setup):
 a,sent=setup;a.issue('email','USER@example.com','a');code=sent[-1][2]
 token=a.verify('email','user@example.com',code,'a')
 assert Auth(a.store).user(token)
 with pytest.raises(HTTPException):a.verify('email','user@example.com',code,'a')
 a.logout(token);assert not a.user(token)

def test_attempt_limits_expiration_and_no_echo(setup):
 a,sent=setup;r=a.issue('phone','13800138000','a');assert 'code' not in r
 code=sent[-1][2];wrong='000000' if code!='000000' else '111111'
 for i in range(5):
  with pytest.raises(HTTPException):a.verify('phone','13800138000',wrong,'a')
 with pytest.raises(HTTPException):a.verify('phone','13800138000',code,'a')
 with pytest.raises(HTTPException) as e:a.issue('phone','13800138000','a')
 assert e.value.status_code==429
 a.issue('email','expiry@example.com','a');code=sent[-1][2]
 with a.store.connect() as db:db.execute('UPDATE login_codes SET expires=0')
 with pytest.raises(HTTPException):a.verify('email','expiry@example.com',code,'a')

def test_delivery_failure_does_not_enable_login(setup,monkeypatch):
 a,sent=setup
 def fail(*args):raise RuntimeError()
 monkeypatch.setattr(module,'send_code',fail)
 with pytest.raises(HTTPException) as e:a.issue('email','failed@example.com','x')
 assert e.value.status_code==503
 with a.store.connect() as db:assert db.execute('SELECT count(*) FROM login_codes').fetchone()[0]==0

def test_account_isolation_cookie_csrf(setup,monkeypatch):
 a,sent=setup;monkeypatch.setattr(app,'auth',a)
 # Share the same isolated database for auth and charts.
 monkeypatch.setattr(app,'store',a.store);app.sessions.clear();app.limits.clear()
 c=TestClient(app.app,base_url='https://testserver');other=TestClient(app.app,base_url='https://testserver')
 assert c.post('/api/auth/code',json={'channel':'email','target':'a@example.com'},headers={'Origin':'https://evil.test'}).status_code==403
 for client,email in [(c,'a@example.com'),(other,'b@example.com')]:
  assert client.post('/api/auth/code',json={'channel':'email','target':email}).status_code==200
  r=client.post('/api/auth/login',json={'channel':'email','target':email,'code':sent[-1][2]})
  assert r.status_code==200 and 'HttpOnly' in r.headers['set-cookie'] and 'Secure' in r.headers['set-cookie']
 p={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'consent':True}
 token=c.post('/api/chart',json=p).json()['session'];h={'X-Jyoti-Session':token}
 assert other.get('/api/session',headers=h).status_code==403
 assert other.post('/api/account/claim',json={},headers=h).status_code==403
 records=c.get('/api/account/charts').json()['items'];assert len(records)==1
 assert other.post('/api/account/charts/'+records[0]['id']+'/open',json={}).status_code==404
 app.sessions.clear()
 opened=c.post('/api/account/charts/'+records[0]['id']+'/open',json={});assert opened.status_code==200
 assert c.get('/api/session',headers={'X-Jyoti-Session':opened.json()['session']}).status_code==200
 assert c.post('/api/auth/logout',json={}).status_code==200
 assert c.get('/api/account/charts').status_code==401
