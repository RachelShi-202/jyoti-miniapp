import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import pytest
from storage import Store
from auth import Auth
from fastapi.testclient import TestClient
from conftest import login_client
client=TestClient(app.app)
P={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'consent':True}
VALID_NATAL_REPORT='命'*1800
@pytest.fixture(autouse=True)
def isolated_web(tmp_path,monkeypatch):
 store=Store(tmp_path/'test.sqlite3');monkeypatch.setattr(app,'store',store);monkeypatch.setattr(app,'auth',Auth(store))
 app.sessions.clear();app.limits.clear();client.cookies.clear();login_client(client)
 yield
 app.sessions.clear();app.limits.clear()
def test_mobile_and_privacy():
 r=client.get('/');assert r.status_code==200 and '选择更适合你的浏览方式' in r.text
 mobile=client.get('/mobile');assert mobile.status_code==200 and 'width=device-width' in mobile.text
 assert "frame-ancestors 'none'" in r.headers['content-security-policy']
 assert client.get('/static/app.js').status_code==200
 assert client.post('/api/chart',json=dict(P,consent=False)).status_code==422

def test_public_ai_copy_and_grouped_report_library():
 page=client.get('/mobile').text
 scripts=''.join(client.get(path).text for path in ('/static/app.js','/static/account.js','/static/experience.js'))
 assert '智谱' not in page+scripts
 assert '第三方 AI 服务接口' in page
 assert '报告按类型分类保存' in page
 assert all(label in scripts for label in ('本命解读','年度与流年','多盘专题','全盘咨询','report-group'))
 natal=page.split('<span class="badge">每张星盘免费一次 · 本命AI解读</span>',1)[1].split('<div class="card"><span class="badge">¥1 / 所选年度',1)[0]
 assert '本命深度分析' in natal and 'D1本命盘、D9、D10、D2、D4与当前大小运' in natal
 assert '同意将本命盘、核心分盘及当前大小运等派生数据发送至AI生成本命分析。内容仅供文化学习与自我探索。' in natal
 assert '生成本命深度分析 ✧' in natal
 assert '无需体验码' not in natal and 'natal-complete-dialog' not in page and '进入星序服务' not in page

def test_markdown_table_renderer_uses_safe_dom_nodes():
 script=client.get('/static/app.js').text
 renderer=script[script.index('function inlineText'):script.index('let planSequence')]
 assert 'innerHTML' not in renderer
 assert "node('table'" in renderer and "node('thead')" in renderer and "node('tbody')" in renderer
 assert "node('tr')" in renderer and "node('th')" in renderer and "node('td')" in renderer
 assert 'document.createTextNode' in renderer and 'markdownTableAt(lines,index)' in renderer
 assert 'reading-table-scroll' in renderer and 'separator.every' in renderer

def test_real_chart_and_annual():
 r=client.post('/api/chart',json=P);assert r.status_code==200
 c=r.json()['chart'];assert len(c['planets'])==9 and len(c['d9'])==9 and c['ascendant']
 t=r.json()['session'];v=client.get('/api/annual/2026',headers={'X-Jyoti-Session':t})
 assert v.status_code==200 and v.json()['priceFen']==290 and not v.json()['purchased']
 assert len(app.annual(c,'2026')['sections'])==5
 assert client.get('/api/annual/2026').status_code==410
 assert client.post('/api/chart',json=dict(P,latitude=100)).status_code==422
 assert client.post('/api/chart',json=dict(P,date='1800-01-01')).status_code==422

def test_ai_configuration(monkeypatch):
 monkeypatch.delenv('ZHIPU_API_KEY',raising=False)
 assert client.post('/api/interpret',json={'session':'x','consent':True}).status_code==503

def test_ai_derived_data_only(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only');monkeypatch.setenv('WEB_AI_ACCESS_CODE','test-code')
 token=client.post('/api/chart',json=P).json()['session'];calls=[]
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):
   assert url=='https://open.bigmodel.cn/api/paas/v4/chat/completions'
   assert kw['json']['model']=='glm-5.3-flash'
   assert 'thinking' not in kw['json']
   assert kw['json']['reasoning_effort']=='low'
   assert kw['json']['max_tokens']==5200
   calls.append(kw['json'])
   return app.httpx.Response(200,json={'choices':[{'message':{'content':VALID_NATAL_REPORT}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 body={'session':token,'consent':True}
 assert client.post('/api/interpret',json=body).status_code==200
 cached=client.post('/api/interpret',json=body);assert cached.status_code==200 and cached.json()['cached'] is True
 assert len(calls)==1
 assert calls[0]['messages'][0]['content']==app.NATAL_PROMPT
 payload=json.loads(calls[0]['messages'][1]['content'])
 assert set(payload)=={'planets','ascendant','moonNakshatra','settings','houseRulers','verifiedD1','verifiedHouseLords','divisions','divisionTopics','divisionMethodVersion','dashaContext','userIdentity'}
 assert 'houseRulers' in payload and set(payload['divisions'])=={'d2','d4','d9','d10'}
 assert all(key not in payload for key in ('periods','periodWindows','currentPeriodAtReferenceUTC','periodLordEvidence','analysisWindowUTC','annual','annualIndependentTiming','gochara','ashtakavarga'))
 serialized=json.dumps(payload,ensure_ascii=False)
 assert '1990-06-15' not in serialized and '上海' not in serialized and 'latitude' not in serialized

def test_expiry():
 t=client.post('/api/chart',json=P).json()['session'];app.sessions[t]['expires']=0
 assert client.get('/api/annual/2026',headers={'X-Jyoti-Session':t}).status_code==410

def test_upstream_auth_is_actionable(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only');monkeypatch.setenv('WEB_AI_ACCESS_CODE','test-code')
 token=client.post('/api/chart',json=P).json()['session']
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):return app.httpx.Response(401,json={'error':{'message':'PRIVATE_PROVIDER_DETAIL'}},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 r=client.post('/api/interpret',json={'session':token,'consent':True})
 assert r.status_code==502 and 'AI_AUTH' in r.json()['detail']
 assert 'PRIVATE_PROVIDER_DETAIL' not in r.text
 assert not app.sessions[token]['busy']

def test_health_check():
 r=client.get('/health');assert r.status_code==200 and r.json()['version']=='web-0.3.10'
 assert r.json()['natalPromptVersion']=='2026-11-21-natal-life-first-v6'
 assert r.json()['promptVersion']=='2026-11-23-annual-stage-v3'


def test_annual_ai_and_followup_gate(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only')
 token=client.post('/api/chart',json=P).json()['session']
 body={'session':token,'kind':'annual','year':2026,'consent':True}
 assert client.post('/api/interpret',json={**body,'year':None}).status_code==422
 for route in ('/api/interpret','/api/interpret/start'):
  r=client.post(route,json=body)
  assert r.status_code==402 and '购买' in r.json()['detail']
 app.sessions[token]['reports']['annual:2026']='历史年度报告'
 app.store.save(token,app.sessions[token])
 assert client.post('/api/interpret',json=body).json()['cached'] is True
 assert client.post('/api/interpret',json={**body,'round':2,'question':'新增问题'}).status_code==402
 monkeypatch.setenv('WEB_FOLLOWUP_TEST','0')
 assert client.post('/api/interpret',json={**body,'round':2,'question':'新增问题'}).status_code==503
 assert client.get('/api/status').json()['annualPriceFen']==290

def test_annual_retries_once_with_own_length_and_model_settings(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only')
 token=client.post('/api/chart',json=P).json()['session'];value=app.sessions[token];calls=[]
 with app.store.connect() as db:app.entitlements.grant(db,value['owner'],'annual:2026','test:annual-length',1)
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):
   calls.append(kw['json']);content='过短' if len(calls)==1 else '年'*1600
   return app.httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':content}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 result=client.post('/api/interpret',json={'session':token,'kind':'annual','year':2026,'consent':True})
 assert result.status_code==200 and len(calls)==2
 assert calls[0]['thinking']=={'type':'enabled'} and calls[0]['temperature']==0.65
 assert '目标控制在1600—1700个中文可见字符' in calls[1]['messages'][-1]['content']
 facts=json.loads(calls[0]['messages'][1]['content']);timing=facts['annualIndependentTiming']
 assert set(facts['divisions'])=={'d2','d4','d9','d10'} and 'sookshmaDashas' not in timing
 assert [item['year'] for item in timing['solarReturns']]==[2025,2026]
 assert timing['calendarWindowUTC']['start'].startswith('2026-01-01') and timing['calendarWindowUTC']['end'].startswith('2027-01-01')
 assert {item['planet'] for item in timing['gochara']['events']}<= {'木星','土星','Rahu','Ketu'}
 assert app._valid_annual_length('年'*1500) and app._valid_annual_length('年'*1800) and not app._valid_annual_length('年'*1499)


def test_ai_incomplete_can_retry(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only')
 token=client.post('/api/chart',json=P).json()['session'];calls=[]
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):
   calls.append(kw['json'])
   content='过短' if len(calls)<=2 else VALID_NATAL_REPORT
   return app.httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':content}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 body={'session':token,'consent':True}
 assert client.post('/api/interpret',json=body).status_code==502
 assert app.sessions[token]['reports']=={} and not app.sessions[token]['busy']
 assert client.get('/api/account/entitlements').json()['remaining']['natal']==1
 assert app.entitlements.history(app.store,app.sessions[token]['owner'])[0]['state']=='released'
 assert client.post('/api/interpret',json=body).status_code==200
 assert len(calls)==3
 assert calls[1]['messages'][0]['content']==app.NATAL_PROMPT
 assert '1800–2400个中文可见字符' in calls[1]['messages'][-1]['content']
 assert app._visible_chinese_count('甲乙，abc\n丙')==3
 assert app._valid_natal_length(VALID_NATAL_REPORT)


def test_background_report_state(monkeypatch):
 import asyncio
 monkeypatch.setenv('ZHIPU_API_KEY','test-only')
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):
   await asyncio.sleep(0.02)
   return app.httpx.Response(200,json={'choices':[{'message':{'content':VALID_NATAL_REPORT}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 with TestClient(app.app) as c:
  login_client(c)
  token=c.post('/api/chart',json=P).json()['session'];body={'session':token,'consent':True}
  assert c.post('/api/interpret/start',json=body).status_code==202
  assert c.post('/api/interpret/start',json=body).json()['state'] in ('pending','completed')
  import time
  for _ in range(50):
   result=c.get('/api/interpret/result',headers={'X-Jyoti-Session':token}).json()
   if result['state']=='completed':break
   time.sleep(.01)
  assert result['state']=='completed' and result['text']==VALID_NATAL_REPORT
  assert c.post('/api/interpret/start',json=body).json()['state']=='completed'
  assert c.get('/api/interpret/result').status_code==410
  monkeypatch.setenv('WEB_FOLLOWUP_TEST','0')
  assert c.post('/api/interpret/start',json={**body,'round':2}).status_code==422
  assert c.post('/api/interpret/start',json={**body,'round':2,'question':'继续深入'}).status_code==402


def test_followup_context_and_quota(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only');monkeypatch.setenv('WEB_FOLLOWUP_TEST','1')
 token=client.post('/api/chart',json=P).json()['session'];calls=[]
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):
   calls.append(kw['json'])
   content=VALID_NATAL_REPORT if len(calls)==1 else '回答'+str(len(calls))
   return app.httpx.Response(200,json={'choices':[{'message':{'content':content}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 body={'session':token,'consent':True}
 assert client.post('/api/interpret',json={**body,'round':2,'question':'问题一'}).status_code==409
 assert client.post('/api/interpret',json=body).json()['text']==VALID_NATAL_REPORT
 assert client.post('/api/interpret',json={**body,'round':2,'question':'问题一'}).status_code==402
 with app.store.connect() as db:app.entitlements.grant(db,app.sessions[token]['owner'],'followup','test:paid-followups',3)
 for q in ('问题一','问题一','问题二','问题三'):
  result=client.post('/api/interpret',json={**body,'round':2,'question':q})
  assert result.status_code==200 and not result.json()['testing'] and not result.json()['free'] and result.json()['entitlementProduct']=='followup'
 assert len(calls)==4
 import json
 facts=json.loads(calls[2]['messages'][1]['content'])
 assert facts['currentQuestion']=='问题二' and facts['firstRoundReading']==VALID_NATAL_REPORT
 assert facts['previousQuestions']==[{'question':'问题一','answer':'回答2'}]
 assert app.entitlements.summary(app.store,app.sessions[token]['owner'])['followup']==0
 assert client.post('/api/interpret',json={**body,'round':2,'question':'问题四'}).status_code==402
 assert client.post('/api/interpret',json={**body,'round':2,'question':'问题一'}).status_code==200
 assert client.post('/api/interpret',json={**body,'round':2,'question':'  '}).status_code==422
 assert client.post('/api/interpret',json={**body,'kind':'annual','year':2027,'round':2,'question':'问题一'}).status_code==409
 assert client.post('/api/interpret',json=body).json()['text']==VALID_NATAL_REPORT


def test_paid_natal_followup_failure_restores_credit_and_keeps_report(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only');monkeypatch.setenv('WEB_FOLLOWUP_TEST','0')
 token=client.post('/api/chart',json=P).json()['session'];value=app.sessions[token]
 value['reports']['natal:']='本命首轮';app.store.save(token,value)
 with app.store.connect() as db:app.entitlements.grant(db,value['owner'],'followup','test:failed-followup',1)
 class Fail:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):raise app.httpx.ReadTimeout('timeout')
 monkeypatch.setattr(app.httpx,'AsyncClient',Fail)
 result=client.post('/api/interpret',json={'session':token,'consent':True,'round':2,'question':'继续深入'})
 assert result.status_code==504
 assert value['reports']['natal:']=='本命首轮' and value.get('followups',{}).get('natal:',[])==[]
 assert app.entitlements.summary(app.store,value['owner'])['followup']==1
 history=app.entitlements.history(app.store,value['owner'])
 assert history[0]['product']=='followup' and history[0]['state']=='released'


def test_followup_plan_is_grounded_and_does_not_consume_round(monkeypatch):
 monkeypatch.setenv('ZHIPU_API_KEY','test-only');monkeypatch.setenv('WEB_FOLLOWUP_TEST','1')
 token=client.post('/api/chart',json=P).json()['session'];value=app.sessions[token]
 value['reports']['natal:']='## 事业方向\n你需要在长期积累与短期机会之间作出选择。'
 value.setdefault('followups',{})['natal:']=[{'question':'之前的问题','answer':'之前的回答'}]
 calls=[]
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):
   calls.append(kw['json'])
   content='{"questions":[{"layer":"understand","label":"理解","question":"你在这段事业结论里最需要先确认的重点是什么？"},{"layer":"map","label":"映射","question":"这个倾向在你近期的工作选择中可能怎样具体表现？"},{"layer":"connect","label":"连接","question":"你的事业方向与当前大运小运之间有哪些支持或限制？"},{"layer":"reflect","label":"反思","question":"面对长期积累与短期机会，你最需要观察哪个现实条件？"}],"refinedQuestion":"未来半年，你在换工作与继续积累之间最需要判断哪些现实条件？"}'
   return app.httpx.Response(200,json={'choices':[{'message':{'content':content}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 body={'session':token,'kind':'natal','chapterTitle':'事业方向','chapterText':'长期积累与短期机会','direction':'事业与学习','draftQuestion':'工作怎么办','consent':True}
 assert client.post('/api/followup/plan',json=body).status_code==402
 with app.store.connect() as db:app.entitlements.grant(db,value['owner'],'followup','test:plan-followups',2)
 result=client.post('/api/followup/plan',json=body)
 assert result.status_code==200
 data=result.json();assert [q['layer'] for q in data['questions']]==['understand','map','connect','reflect']
 assert data['rounds']=={'used':1,'limit':3,'remaining':2} and data['refinedQuestion']
 assert len(value['followups']['natal:'])==1
 import json
 payload=json.loads(calls[0]['messages'][1]['content'])
 assert payload['currentChapter']['title']=='事业方向' and payload['direction']=='事业与学习'
 assert payload['previousQuestions'][0]['question']=='之前的问题' and 'chartContext' in payload
 assert app.entitlements.summary(app.store,value['owner'])['followup']==2


def test_background_followup_isolated_by_job(monkeypatch):
 import time
 monkeypatch.setenv('ZHIPU_API_KEY','test-only');monkeypatch.setenv('WEB_FOLLOWUP_TEST','1')
 class Fake:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):return app.httpx.Response(200,json={'choices':[{'message':{'content':'深度回答'}}]},request=app.httpx.Request('POST',url))
 monkeypatch.setattr(app.httpx,'AsyncClient',Fake)
 with TestClient(app.app) as c:
  login_client(c)
  token=c.post('/api/chart',json=P).json()['session'];app.sessions[token]['reports']['natal:']='本命首轮'
  with app.store.connect() as db:app.entitlements.grant(db,app.sessions[token]['owner'],'followup','test:background-followup',1)
  body={'session':token,'kind':'natal','round':2,'question':'请解释关系中的沟通方式','consent':True}
  job=c.post('/api/interpret/start',json=body).json()['jobId']
  assert '沟通' not in job
  for _ in range(50):
   result=c.get('/api/interpret/result',params={'jobId':job},headers={'X-Jyoti-Session':token}).json()
   if result['state']=='completed':break
   time.sleep(.01)
  assert result['state']=='completed' and result['round']==2
  other=c.post('/api/chart',json=P).json()['session']
  assert c.get('/api/interpret/result',params={'jobId':job},headers={'X-Jyoti-Session':other}).json()['state']=='missing'
