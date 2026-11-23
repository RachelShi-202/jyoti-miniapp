from datetime import datetime,timezone
from astro import calculate,moment_chart,resolve_time
from vargas import enrich
from advanced_jyotish import VERSION,advanced_natal,panchanga,muhurta_screen

PROFILE={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'timezone':'Asia/Shanghai','accuracy':0,'consent':True,'coordinateSystem':'WGS84'}

def test_panchanga_has_five_limb_bounds():
 value=panchanga(datetime(2026,11,23,4,tzinfo=timezone.utc),'Asia/Shanghai')
 assert 1<=value['tithi']['index']<=30 and 1<=value['nakshatra']['index']<=27
 assert 1<=value['yoga']['index']<=27 and value['karana']['name'] and value['vara']['name']

def test_natal_advanced_has_moon_arudha_strengths_and_yogas():
 chart=enrich(calculate(PROFILE));value=advanced_natal(chart)
 assert value['version']==VERSION and len(value['moonLagna']['planets'])==9
 assert next(item for item in value['moonLagna']['planets'] if item['name']=='月亮')['house']==1
 assert value['arudha']['arudhaLagna']['sign'] and value['arudha']['upapadaLagna']['sign']
 assert len(value['shadbala']['planets'])==7 and not value['shadbala']['isClassicalComplete']
 assert len(value['bhavaBala']['houses'])==12 and not value['bhavaBala']['isClassicalComplete']
 assert value['yogas']['ruleVersion']=='parashari-yoga-evidence-v1'

def test_future_event_chart_and_muhurta_screen():
 utc=resolve_time('2027-01-02','09:00','Asia/Shanghai');chart=moment_chart(utc,31.23,121.47,'Asia/Shanghai')
 assert chart['isEventChart'] and chart['ascendant'] and len(chart['planets'])==9
 result=muhurta_screen(utc,resolve_time('2027-01-02','12:00','Asia/Shanghai'),'Asia/Shanghai',31.23,121.47,'contract',60,3,'06:00','22:00')
 assert result['status']=='screening_only' and result['evaluatedSlots']==4 and len(result['candidates'])==3
 assert all(item['chart']['isEventChart'] for item in result['candidates'])
