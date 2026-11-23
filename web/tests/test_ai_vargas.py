from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import ai_reading
from astro import calculate

PROFILE={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'timezone':'Asia/Shanghai','accuracy':0,'consent':True,'coordinateSystem':'WGS84'}

def test_natal_uses_static_prompt_core_divisions_and_no_timing():
 chart=calculate(PROFILE);before=deepcopy(chart)
 system,facts=ai_reading.build_reading(chart,'natal')
 assert system==ai_reading.NATAL_PROMPT
 assert hashlib.sha256(system.encode()).hexdigest()=='3023c38bc59dcfe75725db07a3a955f8cc9f6313954ca63bead2c74a20330fd1'
 assert set(facts['divisions'])=={'d2','d4','d9','d10'}
 assert set(facts)=={'planets','ascendant','moonNakshatra','settings','houseRulers','verifiedD1','verifiedHouseLords','divisions','divisionTopics','divisionMethodVersion','dashaContext'}
 forbidden={'periods','periodWindows','periodLordEvidence','currentPeriodAtReferenceUTC','analysisWindowUTC','annual','annualEvidence','annualTransitTimeline','annualIndependentTiming','resolvedTargetYear','varshaphala','pratyantardashas','sookshmaDashas','gochara','ashtakavarga','crossWindows','referenceDateUTC'}
 assert forbidden.isdisjoint(facts)
 assert facts['divisionTopics']=={
  '感情与承诺':['d1','d9'],'事业与责任':['d1','d10'],'财富与资源':['d1','d2'],
  '居所与房产':['d1','d4']}
 assert chart==before

def test_natal_current_and_next_dasha_metadata(monkeypatch):
 class Fixed(datetime):
  @classmethod
  def now(cls,tz=None):return cls(2026,10,20,tzinfo=timezone.utc)
 monkeypatch.setattr(ai_reading,'datetime',Fixed)
 chart=calculate(PROFILE)
 chart['dashas']=[
  {'lord':'金星','start':'2025-01-01T00:00:00+00:00','end':'2030-01-01T00:00:00+00:00','subperiods':[
   {'lord':'水星','start':'2025-01-01T00:00:00+00:00','end':'2026-10-20T00:00:00+00:00'},
   {'lord':'月亮','start':'2026-10-20T00:00:00+00:00','end':'2028-01-01T00:00:00+00:00'},
   {'lord':'火星','start':'2028-01-01T00:00:00+00:00','end':'2030-01-01T00:00:00+00:00'}]},
  {'lord':'太阳','start':'2030-01-01T00:00:00+00:00','end':'2036-01-01T00:00:00+00:00','subperiods':[
   {'lord':'太阳','start':'2030-01-01T00:00:00+00:00','end':'2036-01-01T00:00:00+00:00'}]}]
 _,facts=ai_reading.build_reading(chart,'natal')
 context=facts['dashaContext']
 assert context['currentMahadasha']['lord']=='金星'
 assert context['currentAntardasha']['lord']=='月亮'
 assert context['nextAntardashaMetadata']=={'lord':'火星','start':'2028-01-01T00:00:00+00:00','end':'2030-01-01T00:00:00+00:00'}
 assert context['nextMahadashaMetadata']=={'lord':'太阳','start':'2030-01-01T00:00:00+00:00','end':'2036-01-01T00:00:00+00:00'}

def test_time_aware_products_keep_divisions_and_period_timing():
 chart=calculate(PROFILE);before=deepcopy(chart)
 for kind in ('annual','single','topic','consult'):
  system,facts=ai_reading.build_reading(chart,kind,2026)
  if kind=='annual':assert set(facts['divisions'])=={'d2','d4','d9','d10'}
  else:assert len(facts['divisions'])==15
  assert facts['periodWindows'] and facts['periods']
  assert facts['divisionTopics']['感情与承诺']==['d1','d9']
  for window in facts['periodWindows']:
   for lord in (window['majorLord'],window['minorLord']):
    evidence=facts['periodLordEvidence'][lord]
    assert set(evidence)=={'d1',*facts['divisions']}
    assert evidence['d1']['house']==next(p['house'] for p in chart['planets'] if p['name']==lord)
  assert system==(ai_reading.ANNUAL_PROMPT if kind=='annual' else ai_reading.SYSTEM)
 assert chart==before

def test_annual_window_does_not_substitute_current_period(monkeypatch):
 class Fixed(datetime):
  @classmethod
  def now(cls,tz=None):return cls(2026,10,20,tzinfo=timezone.utc)
 monkeypatch.setattr(ai_reading,'datetime',Fixed)
 _,facts=ai_reading.build_reading(calculate(PROFILE),'annual',2020)
 assert facts['analysisWindowUTC']=={'start':'2019-01-01','end':'2022-01-01','endExclusive':True}
 assert facts['currentPeriodAtReferenceUTC'] is None
 assert all(w['minorStart']<'2022-01-01' and w['minorEnd']>'2019-01-01' for w in facts['periodWindows'])

def test_minor_boundary_and_verified_lord_positions(monkeypatch):
 class Fixed(datetime):
  @classmethod
  def now(cls,tz=None):return cls(2026,10,20,tzinfo=timezone.utc)
 monkeypatch.setattr(ai_reading,'datetime',Fixed)
 chart=calculate(PROFILE)
 chart['dashas']=[{'lord':'金星','start':'2025-01-01T00:00:00+00:00','end':'2028-01-01T00:00:00+00:00','subperiods':[
 {'lord':'水星','start':'2025-01-01T00:00:00+00:00','end':'2026-10-20T00:00:00+00:00'},
 {'lord':'月亮','start':'2026-10-20T00:00:00+00:00','end':'2028-01-01T00:00:00+00:00'}]}]
 _,facts=ai_reading.build_reading(chart,'single')
 assert facts['currentPeriodAtReferenceUTC']['minorLord']=='月亮'
 assert facts['currentPeriodAtReferenceUTC']['majorLord']=='金星'

def test_global_frameworks_and_complete_annual_transits():
 chart=calculate(PROFILE)
 natal,natal_facts=ai_reading.build_reading(chart,'natal')
 expected=['第一步：D1 本命盘底层格局拆解','第二步：分盘交叉印证（Varga Cross-Checking）','第三步：大运与小运（Dasha）动态激活分析','第四步：综合落地建议']
 positions=[natal.index('## '+title) for title in expected]
 assert positions==sorted(positions)
 assert natal==ai_reading.NATAL_PROMPT and ai_reading.NATAL_PROMPT_VERSION=='2026-11-21-natal-life-first-v6'
 assert '用 Markdown 表格梳理核心行星' not in natal and '本命报告禁止输出 Markdown 表格' not in natal
 assert '当前大运/小运（Vimshottari Dasha）' in natal
 annual,facts=ai_reading.build_reading(chart,'annual',2024)
 assert annual==ai_reading.ANNUAL_PROMPT
 assert hashlib.sha256(annual.encode()).hexdigest()=='d51f3eab278939ccd418563c0ede7d4ae31b24e36d282167ef018326a7f47dbe'
 assert ai_reading.PROMPT_VERSION=='2026-11-23-annual-stage-v3'
 assert '正文1500—1800个中文字符' in annual and '未来三年阶段位置' in annual and '年度综合判断' in annual
 assert '生活化、预测性的文字分析不少于80%' in annual and '不使用表格、月份时间轴、月份窗口、项目符号或清单' in annual
 assert 'annualTransitTimeline' not in facts
 assert 'annualTransitTimeline' not in natal_facts and 'periodWindows' not in natal_facts
