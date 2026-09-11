import sys
from pathlib import Path
from datetime import datetime
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from astro import calculate,resolve_time,monthly,position
P={'date':'1995-05-12','time':'08:30','accuracy':0,'placeLabel':'Guangzhou','latitude':23.1291,'longitude':113.2644,'timezone':'Asia/Shanghai','coordinateSystem':'WGS84','consent':True}
def test_uncertainty_never_invents_ascendant():
 c=calculate(dict(P,accuracy=2,time=''));assert not c['planets'] and c['ascendant'] is None
 assert not monthly(c,'2026-09')['events']
 c=calculate(dict(P,accuracy=1));assert c['planets'] and not c['d9'] and not c['dashas'] and c['ascendant'] is None

def test_historical_time_conversion():
 assert resolve_time('1990-07-01','12:00','Asia/Shanghai').hour==3 # China DST
 assert resolve_time('1995-07-01','12:00','Asia/Shanghai').hour==4
 with pytest.raises(ValueError,match='重复'):resolve_time('2020-11-01','01:30','America/New_York')
 a=resolve_time('2020-11-01','01:30','America/New_York',0)
 b=resolve_time('2020-11-01','01:30','America/New_York',1)
 assert (b-a).total_seconds()==3600
 with pytest.raises(ValueError,match='跳时'):resolve_time('2020-03-08','02:30','America/New_York')

def test_chart_invariants_and_dasha_continuity():
 c=calculate(P)
 assert len(c['planets'])==9 and len(c['d9'])==9
 assert c['utc']=='1995-05-12T00:30:00+00:00'
 # Sidereal Sun near 27 Aries in mid-May, broad astronomical sanity bound.
 assert 26<c['planets'][0]['longitude']<28
 assert abs((c['planets'][-1]['longitude']-c['planets'][-2]['longitude'])%360-180)<1e-6
 for a,b in zip(c['dashas'],c['dashas'][1:]):assert a['end']==b['start']
 for d in c['dashas']:
  assert abs((datetime.fromisoformat(d['end'])-datetime.fromisoformat(d['subperiods'][-1]['end'])).total_seconds())<.01
 assert position(360)['signIndex']==0
