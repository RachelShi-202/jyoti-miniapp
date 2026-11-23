import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from datetime import datetime
from vargas import sign_for,enrich,VARGAS
from astro import calculate

# Hand-derived sign assignments, not a second implementation of the formulas.
@pytest.mark.parametrize('n,longitude,expected',[
 (2,0,4),(2,14.999999,4),(2,15,3),(2,30,3),(2,45,4),
 (3,0,0),(3,10,4),(3,20,8),(3,30,1),(3,50,9),
 (7,0,0),(7,30,7),(7,59.999999,1),(7,29.999999,6),
 (9,0,0),(9,30,9),(9,60,6),(9,90,3),
 (10,0,0),(10,3,1),(10,30,9),(10,57,6),
 (12,0,0),(12,2.5,1),(12,30,1),(12,57.5,0),
 (24,0,4),(24,1.25,5),(24,28.75,3),(24,30,3),(24,31.25,4),(24,58.75,2),
 (30,0,0),(30,5,10),(30,10,8),(30,18,2),(30,25,6),
 (30,30,1),(30,35,5),(30,42,11),(30,50,9),(30,55,7),
 (30,4.999999,0),(30,9.999999,10),(30,17.999999,8),(30,24.999999,2),
 (30,34.999999,1),(30,41.999999,5),(30,49.999999,11),(30,54.999999,9)
])
def test_reference_assignments(n,longitude,expected):assert sign_for(longitude,n)==expected

def test_all_signs_and_normalization():
 for n in VARGAS:
  for s in range(12):
   assert 0<=sign_for(s*30,n)<12
   assert sign_for(s*30,n)==sign_for(s*30+360,n)
   assert 0<=sign_for(s*30+29.99999999,n)<12
  assert sign_for(-1,n)==sign_for(359,n)
 with pytest.raises(ValueError):sign_for(float('nan'),2)
 with pytest.raises(ValueError):sign_for(0,5)

P={'date':'1990-06-15','time':'12:30','placeLabel':'上海','latitude':31.23,'longitude':121.47,'timezone':'Asia/Shanghai','accuracy':0,'consent':True,'coordinateSystem':'WGS84'}
def test_chart_d9_compatibility_and_houses():
 c=enrich(calculate(P));assert len(c['divisions'])==15
 assert [p['signIndex'] for p in c['divisions']['d9']['planets']]==[p['signIndex'] for p in c['d9']]
 for d in c['divisions'].values():
  assert len(d['planets'])==9
  for p in d['planets']:
   assert p['house']==(p['signIndex']-d['ascendant']['signIndex'])%12+1
   assert 'degree' not in p
 assert enrich(calculate(dict(P,accuracy=1)))['divisions']=={}

def test_dasha_subperiod_coverage():
 c=calculate(P)
 for major in c['dashas']:
  subs=major['subperiods'];assert len(subs)==9 and subs[0]['lord']==major['lord']
  assert subs[0]['start']==major['start']
  assert abs((datetime.fromisoformat(subs[-1]['end'])-datetime.fromisoformat(major['end'])).total_seconds())<.001
  for a,b in zip(subs,subs[1:]):assert a['end']==b['start']


@pytest.mark.parametrize('n,longitude,expected',[
 (4,0,0),(4,7.5,3),(4,15,6),(4,22.5,9),(4,30,1),
 (16,0,0),(16,1.875,1),(16,30,4),(16,60,8),(16,90,0),(16,29.999999,3),
 (20,0,0),(20,1.5,1),(20,30,8),(20,60,4),(20,90,0),(20,29.999999,7),
 (27,0,0),(27,30/27,1),(27,30,3),(27,60,6),(27,90,9),(27,120,0),(27,29.999999,2),
 (40,0,0),(40,.75,1),(40,30,6),(40,60,0),(40,29.999999,3),
 (45,0,0),(45,30/45,1),(45,30,4),(45,60,8),(45,90,0),(45,29.999999,8),
 (60,0,0),(60,.5,1),(60,30,1),(60,60,2),(60,29.999999,11)
])
def test_shodashavarga_reference_points(n,longitude,expected):
 assert sign_for(longitude,n)==expected

def test_complete_shodashavarga_and_picker():
 from pathlib import Path
 assert set(VARGAS)=={2,3,4,7,9,10,12,16,20,24,27,30,40,45,60}
 html=(Path(__file__).resolve().parents[1]/'static/index.html').read_text()
 import re
 ids=re.findall(r'data-varga="d(\d+)"',html)
 assert len(ids)==16 and set(map(int,ids))=={1,*VARGAS}
 assert '居所、房产与安居基础' in html and '信念、精神生活与修习' in html
