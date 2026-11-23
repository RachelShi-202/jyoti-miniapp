import time

import pytest
from fastapi.testclient import TestClient
import analytics
import app
from auth import Auth
from storage import Store


@pytest.fixture
def isolated(tmp_path,monkeypatch):
 store=Store(tmp_path/'analytics.sqlite3')
 analytics.initialize(store)
 monkeypatch.setattr(app,'store',store)
 monkeypatch.setattr(app,'auth',Auth(store))
 app.sessions.clear();app.limits.clear()
 return app


def test_summary_is_aggregate_currency_safe_and_token_protected(isolated,monkeypatch):
 app=isolated
 token='analytics-test-token'
 monkeypatch.setenv('ANALYTICS_ADMIN_TOKEN',token)
 now=time.time()
 with app.store.connect() as db:
  db.execute("INSERT INTO users VALUES ('email-user','email:one@example.com',?)",(now,))
  db.execute("INSERT INTO users VALUES ('phone-user','phone:+8613800000000',?)",(now,))
  app.analytics.touch(app.store,'email-user',now)
  app.analytics.touch(app.store,'email-user',now)
  app.analytics.touch(app.store,'phone-user',now)
  db.execute("INSERT INTO payment_orders VALUES ('cny','cny-trade','email-user','topic','',1990,'alipay','paid',NULL,'cny-tx',?,?,?,?)",(now,now,now,now+600))
  db.execute("INSERT INTO payment_orders VALUES ('usd','usd-trade','phone-user','consult','',2990,'paypal','paid',NULL,'usd-tx',?,?,?,?)",(now,now,now,now+600))
  db.execute("INSERT INTO saved_reports VALUES ('r1','chart','email-user','natal','natal','free','text','[]',?,?)",(now,now))
 client=TestClient(app.app)
 assert client.get('/api/admin/analytics/summary').status_code==401
 response=client.get('/api/admin/analytics/summary',headers={'X-Analytics-Token':token})
 assert response.status_code==200
 data=response.json()
 assert data['users']['total']==2
 assert data['users']['emailVerified']==1
 assert data['users']['phoneVerified']==1
 assert data['orders']['paid']==2
 assert data['orders']['paidInPeriod']==2
 assert data['gmv']['net']['cnyFen']==1990
 assert data['gmv']['net']['usdCents']==2990
 assert data['gmv']['periodNet']['cnyFen']==1990
 assert data['reports']['total']==1
 assert data['activity']['dau']==2
 assert data['activity']['mau30Days']==2
 assert all('identity' not in str(value).lower() for value in data.values())


def test_dashboard_login_uses_secure_cookie_and_logout(isolated,monkeypatch):
 token='dashboard-test-token-that-is-long-enough-123456'
 monkeypatch.setenv('ANALYTICS_ADMIN_TOKEN',token)
 client=TestClient(isolated.app)
 response=client.post('/api/admin/analytics/login',json={'token':token})
 assert response.status_code==200
 assert 'HttpOnly' in response.headers['set-cookie']
 assert 'Secure' in response.headers['set-cookie']
 assert 'SameSite=strict' in response.headers['set-cookie']
 assert client.get('/api/admin/analytics/summary?days=7').status_code==200
 assert client.post('/api/admin/analytics/logout',json={}).status_code==200
 assert client.get('/api/admin/analytics/summary?days=7').status_code==401


def test_days_range_is_limited(isolated,monkeypatch):
 monkeypatch.setenv('ANALYTICS_ADMIN_TOKEN','token')
 client=TestClient(isolated.app)
 assert client.get('/api/admin/analytics/summary?days=0',headers={'X-Analytics-Token':'token'}).status_code==422
 assert client.get('/api/admin/analytics/summary?days=367',headers={'X-Analytics-Token':'token'}).status_code==422
