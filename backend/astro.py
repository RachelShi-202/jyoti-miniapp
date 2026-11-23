"""Deterministic Lahiri chart calculation, with explicit uncertainty handling."""
import calendar
import math
import threading
from datetime import datetime, date, timezone, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import swisseph as swe
import tzdata
from zoneinfo import reset_tzpath
reset_tzpath(()) # pinned tzdata package, not host-dependent system tzdb

LOCK=threading.RLock()
SIGNS=['白羊','金牛','双子','巨蟹','狮子','处女','天秤','天蝎','射手','摩羯','水瓶','双鱼']
NAK=['Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra','Punarvasu','Pushya','Ashlesha','Magha','Purva Phalguni','Uttara Phalguni','Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha','Mula','Purva Ashadha','Uttara Ashadha','Shravana','Dhanishta','Shatabhisha','Purva Bhadrapada','Uttara Bhadrapada','Revati']
LORDS=['Ketu','金星','太阳','月亮','火星','Rahu','木星','土星','水星']
YEARS=[7,20,6,10,7,18,16,19,17]
SIGN_LORDS=['火星','金星','水星','月亮','太阳','水星','金星','火星','木星','土星','土星','木星']
BODIES=[('太阳',swe.SUN),('月亮',swe.MOON),('水星',swe.MERCURY),('金星',swe.VENUS),('火星',swe.MARS),('木星',swe.JUPITER),('土星',swe.SATURN),('Rahu',swe.MEAN_NODE)]
VERSION='lahiri-moshier-mean-node-365.25-v1'
TIMING_VERSION='sookshma-gochara-ashtakavarga-tajika-v2'

def resolve_time(day,clock,tzname,fold=None):
 try: zone=ZoneInfo(tzname)
 except (ZoneInfoNotFoundError,ValueError): raise ValueError('无效的 IANA 时区，例如 Asia/Shanghai')
 naive=datetime.fromisoformat(day+'T'+clock)
 candidates={}
 for f in (0,1):
  local=naive.replace(tzinfo=zone,fold=f); utc=local.astimezone(timezone.utc)
  if utc.astimezone(zone).replace(tzinfo=None)==naive:candidates[f]=utc
 if not candidates:raise ValueError('该当地时刻处于夏令时跳时区间，请核实时刻')
 if len(set(candidates.values()))>1 and fold is None:raise ValueError('该时刻在夏令时切换时重复出现，请选择第一次或第二次')
 return candidates.get(fold if fold is not None else 0,next(iter(candidates.values())))

def validate(p):
 try:d=date.fromisoformat(p['date'])
 except (KeyError,ValueError,TypeError):raise ValueError('日期无效')
 if d<date(1900,1,1) or d>datetime.now(timezone.utc).date():raise ValueError('日期须介于 1900 年与今天之间')
 if p.get('accuracy') not in (0,1,2):raise ValueError('时间准确程度无效')
 if p.get('consent') is not True:raise ValueError('需同意资料处理说明')
 for key,limit in [('latitude',90),('longitude',180)]:
  try:v=float(p[key])
  except (KeyError,ValueError,TypeError):raise ValueError('请填写有效经纬度')
  if not math.isfinite(v) or abs(v)>limit:raise ValueError('经纬度超出范围')
 if p.get('coordinateSystem')!='WGS84':raise ValueError('请确认坐标为 WGS84')
 try: ZoneInfo(p.get('timezone',''))
 except (ValueError,ZoneInfoNotFoundError):raise ValueError('无效的 IANA 时区')
 if not p.get('placeLabel','').strip():raise ValueError('请填写地点名称')
 if p['accuracy']!=2:
  try: datetime.strptime(p.get('time',''),'%H:%M')
  except (ValueError,TypeError):raise ValueError('时间须为 HH:MM')
 return p

def position(lon):
 lon=lon%360;sign=int(lon//30)
 return {'longitude':round(lon,8),'signIndex':sign,'sign':SIGNS[sign],'degree':round(lon%30,5)}

def dashas(moon,utc):
 segment=360/27; nak=int(moon/segment); fraction=(moon%segment)/segment; ix=nak%9
 start=utc-timedelta(days=fraction*YEARS[ix]*365.25);result=[]
 # two 120-year cycles ensure coverage even when birth occurs late in a long dasha.
 for k in range(18):
  i=(ix+k)%9;end=start+timedelta(days=YEARS[i]*365.25);sub=[];substart=start
  for j in range(9):
   si=(i+j)%9;subend=substart+timedelta(days=YEARS[i]*YEARS[si]/120*365.25)
   sub.append({'lord':LORDS[si],'start':substart.isoformat(),'end':subend.isoformat()});substart=subend
  result.append({'lord':LORDS[i],'start':start.isoformat(),'end':end.isoformat(),'subperiods':sub});start=end
 return result

def _period_children(start,end,first_lord):
 """Nine proportional Vimshottari children, closed exactly at the parent end."""
 first=LORDS.index(first_lord);span=end-start;children=[];elapsed=0
 for offset in range(9):
  lord=LORDS[(first+offset)%9];child_start=start+span*(elapsed/120);elapsed+=YEARS[LORDS.index(lord)]
  child_end=end if offset==8 else start+span*(elapsed/120)
  children.append({'lord':lord,'start':child_start.isoformat(),'end':child_end.isoformat()})
 return children

def pratyantardashas(chart,start,end):
 """Return third-level Vimshottari periods overlapping [start, end)."""
 start=datetime.fromisoformat(start) if isinstance(start,str) else start
 end=datetime.fromisoformat(end) if isinstance(end,str) else end
 if start.tzinfo is None or end.tzinfo is None or start>=end:raise ValueError('三级运查询区间无效')
 result=[]
 for major in chart.get('dashas',[]):
  major_start=datetime.fromisoformat(major['start']);major_end=datetime.fromisoformat(major['end'])
  if major_start>=end or major_end<=start:continue
  for minor in major.get('subperiods',[]):
   minor_start=datetime.fromisoformat(minor['start']);minor_end=datetime.fromisoformat(minor['end'])
   if minor_start>=end or minor_end<=start:continue
   for child in _period_children(minor_start,minor_end,minor['lord']):
    child_start=datetime.fromisoformat(child['start']);child_end=datetime.fromisoformat(child['end'])
    if child_start<end and child_end>start:
     result.append({'mahadasha':major['lord'],'antardasha':minor['lord'],'pratyantardasha':child['lord'],'start':child['start'],'end':child['end']})
 return result

def sookshma_dashas(chart,start,end):
 """Fourth-level Vimshottari periods overlapping [start, end)."""
 start=datetime.fromisoformat(start) if isinstance(start,str) else start
 end=datetime.fromisoformat(end) if isinstance(end,str) else end
 result=[]
 for parent in pratyantardashas(chart,start,end):
  parent_start=datetime.fromisoformat(parent['start']);parent_end=datetime.fromisoformat(parent['end'])
  for child in _period_children(parent_start,parent_end,parent['pratyantardasha']):
   child_start=datetime.fromisoformat(child['start']);child_end=datetime.fromisoformat(child['end'])
   if child_start<end and child_end>start:
    result.append({**{k:parent[k] for k in ('mahadasha','antardasha','pratyantardasha')},'sookshmaDasha':child['lord'],'start':child['start'],'end':child['end']})
 return result

# Classical, unreduced Bhinnashtakavarga bindu rules. Nodes are not contributors.
ASHTAKAVARGA_RULES={
 '太阳':{'太阳':(1,2,4,7,8,9,10,11),'月亮':(3,6,10,11),'火星':(1,2,4,7,8,9,10,11),'水星':(3,5,6,9,10,11,12),'木星':(5,6,9,11),'金星':(6,7,12),'土星':(1,2,4,7,8,9,10,11),'Lagna':(3,4,6,10,11,12)},
 '月亮':{'太阳':(3,6,7,8,10,11),'月亮':(1,3,6,7,10,11),'火星':(2,3,5,6,9,10,11),'水星':(1,3,4,5,7,8,10,11),'木星':(1,4,7,8,10,11,12),'金星':(3,4,5,7,9,10,11),'土星':(3,5,6,11),'Lagna':(3,6,10,11)},
 '火星':{'太阳':(3,5,6,10,11),'月亮':(3,6,11),'火星':(1,2,4,7,8,10,11),'水星':(3,5,6,11),'木星':(6,10,11,12),'金星':(6,8,11,12),'土星':(1,4,7,8,9,10,11),'Lagna':(1,3,6,10,11)},
 '水星':{'太阳':(5,6,9,11,12),'月亮':(2,4,6,8,10,11),'火星':(1,2,4,7,8,9,10,11),'水星':(1,3,5,6,9,10,11,12),'木星':(6,8,11,12),'金星':(1,2,3,4,5,8,9,11),'土星':(1,2,4,7,8,9,10,11),'Lagna':(1,2,4,6,8,10,11)},
 '木星':{'太阳':(1,2,3,4,7,8,9,10,11),'月亮':(2,5,7,9,11),'火星':(1,2,4,7,8,10,11),'水星':(1,2,4,5,6,9,10,11),'木星':(1,2,3,4,7,8,10,11),'金星':(2,5,6,9,10,11),'土星':(3,5,6,12),'Lagna':(1,2,4,5,6,7,9,10,11)},
 '金星':{'太阳':(8,11,12),'月亮':(1,2,3,4,5,8,9,11,12),'火星':(3,5,6,9,11,12),'水星':(3,5,6,9,11),'木星':(5,8,9,10,11),'金星':(1,2,3,4,5,8,9,10,11),'土星':(3,4,5,8,9,10,11),'Lagna':(1,2,3,4,5,8,9,11)},
 '土星':{'太阳':(1,2,4,7,8,10,11),'月亮':(3,6,11),'火星':(3,5,6,10,11,12),'水星':(6,8,9,10,11,12),'木星':(5,6,11,12),'金星':(6,11,12),'土星':(3,5,6,11),'Lagna':(1,3,4,6,10,11)},
}

def ashtakavarga(chart):
 """Unreduced BAV and SAV; sign arrays are Aries through Pisces."""
 signs={p['name']:p['signIndex'] for p in chart['planets'] if p['name'] in ASHTAKAVARGA_RULES}
 signs['Lagna']=chart['ascendant']['signIndex'];bav={}
 for target,contributors in ASHTAKAVARGA_RULES.items():
  points=[0]*12
  for contributor,houses in contributors.items():
   origin=signs[contributor]
   for house in houses:points[(origin+house-1)%12]+=1
  bav[target]=points
 sav=[sum(bav[planet][sign] for planet in bav) for sign in range(12)]
 return {'signOrder':SIGNS,'bhinnashtakavarga':bav,'sarvashtakavarga':sav,'total':sum(sav),'reductionsApplied':False,'ruleVersion':'classical-bav-unreduced-v1'}

def julian(utc):
 return swe.utc_to_jd(utc.year,utc.month,utc.day,utc.hour,utc.minute,utc.second+utc.microsecond/1e6,swe.GREG_CAL)[1]

def planetary(utc):
 # Explicit Moshier analytical ephemeris: no silent missing-file fallback.
 with LOCK:
  swe.set_sid_mode(swe.SIDM_LAHIRI)
  jd=julian(utc);out=[]
  for name,body in BODIES:
   xx,flags=swe.calc_ut(jd,body,swe.FLG_MOSEPH|swe.FLG_SIDEREAL|swe.FLG_SPEED)
   out.append(dict(name=name,retrograde=xx[3]<0,speed=round(xx[3],8),**position(xx[0])))
  node=out[-1];out.append(dict(name='Ketu',retrograde=node['retrograde'],speed=node['speed'],**position(node['longitude']+180)))
  return out

def moment_chart(utc,latitude,longitude,tzname):
 """Sidereal event chart for Prashna/Muhurta; unlike natal input it may be future-dated."""
 if isinstance(utc,str):utc=datetime.fromisoformat(utc)
 if utc.tzinfo is None:raise ValueError('事件时刻必须包含时区')
 try:ZoneInfo(tzname)
 except (ValueError,ZoneInfoNotFoundError):raise ValueError('无效的 IANA 时区')
 latitude=float(latitude);longitude=float(longitude)
 if not math.isfinite(latitude) or not math.isfinite(longitude) or abs(latitude)>90 or abs(longitude)>180:raise ValueError('经纬度超出范围')
 utc=utc.astimezone(timezone.utc);planets=planetary(utc)
 with LOCK:
  swe.set_sid_mode(swe.SIDM_LAHIRI)
  _,ascmc=swe.houses_ex(julian(utc),latitude,longitude,b'W',swe.FLG_SIDEREAL)
 asc=position(ascmc[0])
 for planet in planets:planet['house']=(planet['signIndex']-asc['signIndex'])%12+1
 moon=next(item for item in planets if item['name']=='月亮')['longitude'];nak=int(moon/(360/27));pada=int((moon%(360/27))/(360/108))+1
 return {'version':VERSION,'engineVersion':swe.version,'ephemeris':'Moshier analytical','settings':{'ayanamsa':'Lahiri','houses':'Whole sign','nodes':'Mean node'},'utc':utc.isoformat(),'timezone':tzname,'status':'calculated','ascendant':asc,'planets':planets,'moonNakshatra':{'name':NAK[nak],'pada':pada},'dashas':[],'isEventChart':True,'isDemo':False}

def _body_state(name,utc):
 body=dict(BODIES).get(name)
 if name=='Ketu':
  node=_body_state('Rahu',utc);return dict(name='Ketu',retrograde=node['retrograde'],speed=node['speed'],**position(node['longitude']+180))
 if body is None:raise ValueError('未知行星')
 with LOCK:
  swe.set_sid_mode(swe.SIDM_LAHIRI)
  xx,_=swe.calc_ut(julian(utc),body,swe.FLG_MOSEPH|swe.FLG_SIDEREAL|swe.FLG_SPEED)
 return dict(name=name,retrograde=xx[3]<0,speed=round(xx[3],8),**position(xx[0]))

def _refine_sign_change(name,left,right,left_sign):
 for _ in range(40):
  middle=left+(right-left)/2
  if _body_state(name,middle)['signIndex']==left_sign:left=middle
  else:right=middle
 return right

def _refine_station(name,left,right,left_speed):
 for _ in range(40):
  middle=left+(right-left)/2;speed=_body_state(name,middle)['speed']
  if (speed>=0)==(left_speed>=0):left=middle
  else:right=middle
 return right

def gochara_calendar(chart,start,end,tzname,av=None):
 """Exact sign ingresses/stations plus monthly states, with natal Lagna/Moon and AV scores."""
 if isinstance(start,str):start=datetime.fromisoformat(start)
 if isinstance(end,str):end=datetime.fromisoformat(end)
 if start.tzinfo is None or end.tzinfo is None or start>=end:raise ValueError('行运查询区间无效')
 av=av or ashtakavarga(chart);natal_asc=chart['ascendant']['signIndex'];natal_moon=next(p['signIndex'] for p in chart['planets'] if p['name']=='月亮')
 names=('太阳','月亮','水星','金星','火星','木星','土星','Rahu','Ketu');events=[]
 previous={name:_body_state(name,start) for name in names};left=start;step=timedelta(hours=6)
 while left<end:
  right=min(left+step,end)
  for name in names:
   before=previous[name];after=_body_state(name,right)
   if after['signIndex']!=before['signIndex']:
    when=_refine_sign_change(name,left,right,before['signIndex']);state=_body_state(name,when+timedelta(seconds=1));sign=state['signIndex']
    events.append({'type':'ingress','planet':name,'utc':when.isoformat(),'local':when.astimezone(ZoneInfo(tzname)).isoformat(),'fromSign':before['sign'],'toSign':state['sign'],'direction':'retrograde' if state['retrograde'] else 'direct','fromLagnaHouse':(sign-natal_asc)%12+1,'fromMoonHouse':(sign-natal_moon)%12+1,'sarvashtakavarga':av['sarvashtakavarga'][sign],'planetBAV':av['bhinnashtakavarga'].get(name,[None]*12)[sign]})
   if name not in ('太阳','月亮','Rahu','Ketu') and (after['speed']>=0)!=(before['speed']>=0):
    when=_refine_station(name,left,right,before['speed']);state=_body_state(name,when+timedelta(seconds=1));sign=state['signIndex']
    events.append({'type':'station','planet':name,'utc':when.isoformat(),'local':when.astimezone(ZoneInfo(tzname)).isoformat(),'motionAfter':'retrograde' if state['retrograde'] else 'direct','sign':state['sign'],'degree':state['degree'],'fromLagnaHouse':(sign-natal_asc)%12+1,'fromMoonHouse':(sign-natal_moon)%12+1,'sarvashtakavarga':av['sarvashtakavarga'][sign],'planetBAV':av['bhinnashtakavarga'][name][sign]})
   previous[name]=after
  left=right
 zone=ZoneInfo(tzname);first=start.astimezone(zone);month=datetime(first.year,first.month,1,12,tzinfo=zone)
 if month<first:month=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
 snapshots=[]
 while month.astimezone(timezone.utc)<end:
  point=month.astimezone(timezone.utc);items=[]
  for name in names:
   state=_body_state(name,point);sign=state['signIndex']
   items.append({**state,'fromLagnaHouse':(sign-natal_asc)%12+1,'fromMoonHouse':(sign-natal_moon)%12+1,'sarvashtakavarga':av['sarvashtakavarga'][sign],'planetBAV':av['bhinnashtakavarga'].get(name,[None]*12)[sign]})
  snapshots.append({'utc':point.isoformat(),'local':month.isoformat(),'planets':items})
  month=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
 return {'start':start.isoformat(),'end':end.isoformat(),'timezone':tzname,'ayanamsa':'Lahiri','referenceFrames':['D1 Lagna','natal Moon'],'events':sorted(events,key=lambda x:x['utc']),'monthlySnapshots':snapshots,'ashtakavarga':av,'ruleVersion':'gochara-exact-ingress-station-av-v1'}

def _sun_longitude(utc):
 with LOCK:
  swe.set_sid_mode(swe.SIDM_LAHIRI)
  xx,_=swe.calc_ut(julian(utc),swe.SUN,swe.FLG_MOSEPH|swe.FLG_SIDEREAL|swe.FLG_SPEED)
  return xx[0]%360

def _sun_crossing(start,end,target):
 """First forward sidereal-Sun crossing in [start, end), to sub-second precision."""
 if start.tzinfo is None or end.tzinfo is None or start>=end:raise ValueError('太阳换座查询区间无效')
 target%=360;left=start;left_lon=_sun_longitude(left);step=timedelta(hours=12)
 while left<end:
  right=min(left+step,end);right_lon=_sun_longitude(right)
  advance=(right_lon-left_lon)%360;distance=(target-left_lon)%360
  if distance<=advance+1e-10 and distance<5:
   anchor=left;anchor_lon=left_lon;wanted=distance
   if wanted<1e-10:return left
   for _ in range(42):
    middle=left+(right-left)/2;travelled=(_sun_longitude(middle)-anchor_lon)%360
    if travelled>=wanted:right=middle
    else:left=middle
   return right
  left=right;left_lon=right_lon
 raise ValueError('查询区间内未找到太阳黄经交点')

def _sun_ingresses(start,end,tzname):
 """Exact Lahiri sidereal sign ingresses in a UTC interval."""
 events=[];left=start;left_lon=_sun_longitude(left);left_sign=int(left_lon//30);step=timedelta(hours=12)
 while left<end:
  right=min(left+step,end);right_lon=_sun_longitude(right);right_sign=int(right_lon//30)
  if right_sign!=left_sign:
   target=(right_sign*30)%360;crossing=_sun_crossing(left,right,target)
   local=crossing.astimezone(ZoneInfo(tzname))
   events.append({'signIndex':right_sign,'sign':SIGNS[right_sign],'fromSignIndex':left_sign,'fromSign':SIGNS[left_sign],'targetLongitude':target,'utc':crossing.isoformat(),'local':local.isoformat()})
  left=right;left_lon=right_lon;left_sign=right_sign
 return events

@lru_cache(maxsize=128)
def sankranti_calendar(year,tzname='Asia/Shanghai'):
 """Twelve exact sidereal solar ingresses for a civil calendar year."""
 if not 1900<=int(year)<=2101:raise ValueError('太阳换座年份应在1900—2101之间')
 zone=ZoneInfo(tzname);start=datetime(int(year),1,1,tzinfo=zone).astimezone(timezone.utc);end=datetime(int(year)+1,1,1,tzinfo=zone).astimezone(timezone.utc)
 events=[item for item in _sun_ingresses(start,end,tzname) if int(item['local'][:4])==int(year)]
 if len(events)!=12:raise RuntimeError('太阳换座日历未得到完整十二次换座')
 return {'year':int(year),'timezone':tzname,'ayanamsa':'Lahiri','events':events,'ruleVersion':'sankranti-lahiri-exact-v1'}

def _solar_return(chart,profile,target_year):
 birth_local=date.fromisoformat(profile['date']);day=min(birth_local.day,calendar.monthrange(target_year,birth_local.month)[1])
 zone=ZoneInfo(profile['timezone']);anchor=datetime(target_year,birth_local.month,day,int(profile['time'][:2]),int(profile['time'][3:]),tzinfo=zone).astimezone(timezone.utc)
 natal_sun=next(item['longitude'] for item in chart['planets'] if item['name']=='太阳')
 return _sun_crossing(anchor-timedelta(days=3),anchor+timedelta(days=3),natal_sun)

def _annual_chart(utc,profile):
 planets=planetary(utc)
 with LOCK:
  swe.set_sid_mode(swe.SIDM_LAHIRI)
  _,ascmc=swe.houses_ex(julian(utc),float(profile['latitude']),float(profile['longitude']),b'W',swe.FLG_SIDEREAL)
 asc=position(ascmc[0])
 for planet in planets:planet['house']=((planet['signIndex']-asc['signIndex'])%12)+1
 return {'utc':utc.isoformat(),'local':utc.astimezone(ZoneInfo(profile['timezone'])).isoformat(),'ascendant':asc,'planets':planets}

EXALT_SIGNS={'太阳':0,'月亮':1,'火星':9,'水星':5,'木星':3,'金星':11,'土星':6}
OWN_SIGNS={'太阳':(4,),'月亮':(3,),'火星':(0,7),'水星':(2,5),'木星':(8,11),'金星':(1,6),'土星':(9,10)}
WEEKDAY_LORDS=('月亮','火星','水星','木星','金星','土星','太阳')

def _tajika_evidence(annual_chart,natal_chart,muntha,return_utc):
 planets={p['name']:p for p in annual_chart['planets'] if p['name'] in OWN_SIGNS};names=list(planets);aspects=[]
 aspect_defs=((0,'合相'),(60,'六合'),(90,'刑相'),(120,'三合'),(180,'对冲'))
 for i,left_name in enumerate(names):
  for right_name in names[i+1:]:
   left=planets[left_name];right=planets[right_name];distance=abs((left['longitude']-right['longitude']+180)%360-180)
   angle,label=min(aspect_defs,key=lambda item:abs(distance-item[0]));orb=abs(distance-angle)
   if orb>8:continue
   later_left=_body_state(left_name,return_utc+timedelta(hours=12));later_right=_body_state(right_name,return_utc+timedelta(hours=12))
   later_distance=abs((later_left['longitude']-later_right['longitude']+180)%360-180);later_orb=abs(later_distance-angle)
   applying=later_orb<orb
   aspects.append({'planets':[left_name,right_name],'aspect':label,'angle':angle,'orb':round(orb,5),'applying':applying,'tajikaMotion':'Itthasala' if applying else 'Isarapha','quality':'supportive' if angle in (60,120) else 'challenging' if angle in (90,180) else 'mixed'})
 annual_lord=SIGN_LORDS[annual_chart['ascendant']['signIndex']];natal_lord=SIGN_LORDS[natal_chart['ascendant']['signIndex']];day_lord=WEEKDAY_LORDS[return_utc.weekday()]
 roles=[('Varsha Lagna lord',annual_lord),('Janma Lagna lord',natal_lord),('Muntha lord',muntha['lord']),('weekday lord',day_lord)]
 candidates=[]
 for role,lord in roles:
  planet=planets[lord];score=0;reasons=[]
  if planet['signIndex'] in OWN_SIGNS[lord]:score+=3;reasons.append('own sign')
  if planet['signIndex']==EXALT_SIGNS[lord]:score+=4;reasons.append('exalted')
  if planet['house'] in (1,4,7,10):score+=2;reasons.append('angular')
  if planet['house'] in (1,5,9):score+=1;reasons.append('trinal')
  candidates.append({'role':role,'lord':lord,'score':score,'sign':planet['sign'],'house':planet['house'],'reasons':reasons})
 winner=max(candidates,key=lambda item:item['score'])
 return {'aspects':aspects,'yogas':{'itthasala':[x for x in aspects if x['applying']],'isarapha':[x for x in aspects if not x['applying']]},'yearLordCandidates':candidates,'yearLord':winner,'munthaLordState':next(item for item in candidates if item['role']=='Muntha lord'),'ruleVersion':'tajika-aspects-officers-v2','note':'年度主星按候选星尊贵度与角宫/三方宫强度排序；相位采用返照时刻的应用/分离运动。'}

def _mudda_dashas(chart,start,end,completed_years):
 moon=next(item['longitude'] for item in chart['planets'] if item['name']=='月亮');segment=360/27
 nakshatra_index=int(moon/segment);fraction=(moon%segment)/segment
 first_index=(nakshatra_index%9+completed_years)%9;first_lord=LORDS[first_index]
 nominal={lord:YEARS[i]*3 for i,lord in enumerate(LORDS)}
 opening=nominal[first_lord]*(1-fraction);segments=[]
 if opening>1e-9:segments.append((first_lord,opening,'opening_balance'))
 for offset in range(1,9):
  lord=LORDS[(first_index+offset)%9];segments.append((lord,nominal[lord],'full'))
 closing=nominal[first_lord]-opening
 if closing>1e-9:segments.append((first_lord,closing,'closing_balance'))
 span=end-start;elapsed=0;periods=[]
 for i,(lord,days,part) in enumerate(segments):
  period_start=start+span*(elapsed/360);elapsed+=days;period_end=end if i==len(segments)-1 else start+span*(elapsed/360)
  periods.append({'lord':lord,'segment':part,'nominalSolarDays':round(days,8),'start':period_start.isoformat(),'end':period_end.isoformat()})
 return {'startingLord':first_lord,'birthNakshatraIndex':nakshatra_index+1,'birthNakshatra':NAK[nakshatra_index],'birthNakshatraTraversed':round(fraction,10),'completedYears':completed_years,'nominalYearDays':360,'periods':periods,'ruleVersion':'vimshottari-mudda-natal-moon-v1'}

def varshaphala(chart,profile,target_year):
 """Tajika annual return chart with Muntha and Vimshottari Mudda Dasha."""
 if chart.get('status')!='calculated':raise ValueError('年度返照盘需要准确出生时刻')
 birth_year=date.fromisoformat(profile['date']).year
 if not birth_year<=int(target_year)<=2100:raise ValueError('年度返照年份不能早于出生年份，且不得晚于2100年')
 start=_solar_return(chart,profile,int(target_year));end=_solar_return(chart,profile,int(target_year)+1)
 annual_chart=_annual_chart(start,profile);completed=int(target_year)-birth_year
 natal_asc=chart['ascendant'];muntha_sign=(natal_asc['signIndex']+completed)%12
 muntha={'signIndex':muntha_sign,'sign':SIGNS[muntha_sign],'degree':natal_asc['degree'],'longitude':round(muntha_sign*30+natal_asc['degree'],5),'house':(muntha_sign-annual_chart['ascendant']['signIndex'])%12+1,'lord':SIGN_LORDS[muntha_sign],'completedYears':completed}
 return {'year':int(target_year),'ageAtReturn':completed,'returnUTC':start.isoformat(),'returnLocal':annual_chart['local'],'nextReturnUTC':end.isoformat(),'natalSunLongitude':next(item['longitude'] for item in chart['planets'] if item['name']=='太阳'),'chart':annual_chart,'muntha':muntha,'muddaDasha':_mudda_dashas(chart,start,end,completed),'tajika':_tajika_evidence(annual_chart,chart,muntha,start),'settings':{'ayanamsa':'Lahiri','ephemeris':'Moshier analytical','houses':'Whole sign','returnDefinition':'exact sidereal Sun return to natal longitude','location':'birth place'},'ruleVersion':'varshaphala-tajika-operational-v2'}

def _period_at(periods,point,start_key='start',end_key='end'):
 return next((item for item in periods if datetime.fromisoformat(item[start_key])<=point<datetime.fromisoformat(item[end_key])),None)

def timing_calendar(chart,profile,target_year):
 """Independent annual chart plus exact cross-windows for the natal and annual clocks."""
 annual_result=varshaphala(chart,profile,int(target_year));start=datetime.fromisoformat(annual_result['returnUTC']);end=datetime.fromisoformat(annual_result['nextReturnUTC'])
 pratyantara=pratyantardashas(chart,start,end);sookshma=sookshma_dashas(chart,start,end);ingresses=_sun_ingresses(start,end,profile['timezone']);mudda=annual_result['muddaDasha']['periods'];av=ashtakavarga(chart)
 boundaries={start,end}
 for item in (*pratyantara,*sookshma,*mudda):
  boundaries.add(max(start,datetime.fromisoformat(item['start'])));boundaries.add(min(end,datetime.fromisoformat(item['end'])))
 for item in ingresses:boundaries.add(datetime.fromisoformat(item['utc']))
 points=sorted(point for point in boundaries if start<=point<=end);windows=[]
 for left,right in zip(points,points[1:]):
  if left>=right:continue
  middle=left+(right-left)/2;natal=_period_at(pratyantara,middle);subtle=_period_at(sookshma,middle);annual_period=_period_at(mudda,middle);sun=position(_sun_longitude(middle))
  natal_track={k:natal[k] for k in ('mahadasha','antardasha','pratyantardasha')} if natal else None
  if natal_track and subtle:natal_track['sookshmaDasha']=subtle['sookshmaDasha']
  windows.append({'start':left.isoformat(),'end':right.isoformat(),'sunSignIndex':sun['signIndex'],'sunSign':sun['sign'],'natalTrack':natal_track,'annualTrack':{'muddaLord':annual_period['lord'],'muddaSegment':annual_period['segment']} if annual_period else None})
 return {'year':int(target_year),'varshaphala':annual_result,'sankrantiCalendar':sankranti_calendar(int(target_year),profile['timezone']),'annualCycleSankrantis':ingresses,'pratyantardashas':pratyantara,'sookshmaDashas':sookshma,'ashtakavarga':av,'gochara':gochara_calendar(chart,start,end,profile['timezone'],av),'crossWindows':windows,'ruleVersion':TIMING_VERSION,'note':'时间证据包含四级运、Mudda、精确换座/停滞、月度行运与未约减八分盘点数；具体事件仍需多层证据共同支持。'}

def calculate(p):
 validate(p)
 if p['accuracy']==2:
  return {'version':VERSION,'status':'needs_time','message':'时刻未知，暂不计算个人星盘与周期数据。补充时刻后可继续。','planets':[],'dashas':[],'d9':[],'ascendant':None,'isDemo':False}
 utc=resolve_time(p['date'],p['time'],p['timezone'],p.get('fold'));planets=planetary(utc)
 exact=p['accuracy']==0;asc=None
 if exact:
  with LOCK:
   swe.set_sid_mode(swe.SIDM_LAHIRI)
   _,ascmc=swe.houses_ex(julian(utc),float(p['latitude']),float(p['longitude']),b'W',swe.FLG_SIDEREAL)
   asc=position(ascmc[0])
 for planet in planets:
  planet['house']=((planet['signIndex']-asc['signIndex'])%12)+1 if asc else None
 moon=planets[1]['longitude'];nak=int(moon/(360/27));pada=int((moon%(360/27))/(360/108))+1
 return {'version':VERSION,'tzdbVersion':tzdata.__version__,'engineVersion':swe.version,'ephemeris':'Moshier analytical','settings':{'ayanamsa':'Lahiri','houses':'Whole sign','nodes':'Mean node','dashaYearDays':365.25},'utc':utc.isoformat(),'timezone':p['timezone'],'status':'calculated' if exact else 'approximate','message':'' if exact else '使用估计时刻计算行星位置；上升、宫位、D9 与大运暂不提供。','ascendant':asc,'planets':planets,'moonNakshatra':{'name':NAK[nak],'pada':pada},'d9':[dict(name=x['name'],**position((x['longitude']*9)%360)) for x in planets] if exact else [],'dashas':dashas(moon,utc) if exact else [],'isDemo':False}

THEMES=['个人目标','资源与金钱习惯','表达与学习','家庭与归属','创造与兴趣','日常安排','合作与关系','共享与信任','学习与视野','工作与方向','社交与长期目标','休息与内在整理']
def monthly(chart,period):
 year,month=map(int,period.split('-'));point=datetime(year,month,15,12,tzinfo=timezone.utc)
 if chart['status']!='calculated':return {'period':period,'theme':'先补充准确时刻','summary':chart['message'],'events':[],'sections':[],'isDemo':False,'free':True}
 trans=planetary(point);asc=chart['ascendant']['signIndex'];events=[]
 for planet in trans:
  if planet['name'] not in ('木星','土星'):continue
  house=(planet['signIndex']-asc)%12+1;theme=THEMES[house-1]
  events.append({'id':period+'-'+planet['name'],'label':period+' · 月中行运快照','title':theme,'body':'本月可围绕「'+theme+'」记录一个关注点，并回顾自己的行动。','basis':f"{point.isoformat()}，恒星黄道 {planet['name']} 位于{planet['sign']} {planet['degree']:.2f}°，相对本命上升为第 {house} 宫。基于月中采样，不代表整月持续，也不是事件发生日期。"})
 current=next((x for x in chart['dashas'] if x['start']<=point.isoformat()<x['end']),None)
 sub=next((x for x in current['subperiods'] if x['start']<=point.isoformat()<x['end']),None) if current else None
 return {'period':period,'theme':' / '.join(e['title'] for e in events),'summary':f"月中参考周期：{current['lord']}大运 · {sub['lord']}分运。" if current and sub else '该月份超出当前大运展示区间。','events':events,'sections':[{'title':e['title'],'text':e['body'],'basis':e['basis']} for e in events],'ruleVersion':'monthly-snapshot-v1','isDemo':False,'free':True,'note':'基础规则试用版：行运位置是真实计算值，解读是娱乐性主题提示；尚未实现精确星象事件搜寻及完整专业论断。'}

def annual(chart,period):
 """Summarize daily noon UTC samples, not twelve monthly interpretations."""
 from collections import Counter
 year=int(period)
 if chart['status']!='calculated':
  return {'period':period,'theme':'请补充准确时刻','summary':chart['message'],'sections':[],'events':[],'free':True,'note':''}
 names=('木星','土星','金星')
 counts={n:Counter() for n in names};signs={n:Counter() for n in names}
 point=datetime(year,1,1,12,tzinfo=timezone.utc);end=datetime(year+1,1,1,12,tzinfo=timezone.utc)
 asc=chart['ascendant']['signIndex'];days=0
 while point<end:
  for p in planetary(point):
   if p['name'] in counts:
    counts[p['name']][(p['signIndex']-asc)%12+1]+=1
    signs[p['name']][p['sign']]+=1
  point+=timedelta(days=1);days+=1
 def dominant(name):return counts[name].most_common(1)[0][0]
 def evidence(name):
  return name+'：'+ '、'.join(f'第{h}宫 {n}/{days}次采样' for h,n in sorted(counts[name].items()))
 def focus(name):
  h=dominant(name);return f'{name}全年采样中最常落在本命第{h}宫，对应「{THEMES[h-1]}」主题。'
 overview='\n'.join(n+'全年采样涉及'+ '、'.join(signs[n])+'座；'+focus(n) for n in names)
 sections=[{'title':'年度星象','text':overview+'\n木星的传统象征偏向拓展与学习，土星偏向责任与边界，金星偏向关系与价值。本报告概括全年分布，不将这些象征作为事件预测。','basis':'；'.join(evidence(n) for n in names)},
 {'title':'整体周期变化','text':focus('木星')+focus('土星')+'将想尝试的方向和能够承担的责任放在一起审视：选择少量长期目标，定期记录实际进展。不同领域的投入需要平衡，不给全年吉凶评分。','basis':evidence('木星')+'；'+evidence('土星')},
 {'title':'感情','text':focus('金星')+('关系与共同活动可作为今年的反思重点，关注彼此需求、沟通边界和日常陪伴。' if dominant('金星') in (5,7,11) else '可从上述生活领域观察自己的关系需求，主动表达期待，尊重彼此的节奏。')+'单身与有伴用户都可使用这些提示；不据此预测相遇、婚期或分合。','basis':evidence('金星')},
 {'title':'财富','text':focus('木星')+('资源主题在采样中较突出，可梳理收支、共享支出和储备安排。' if dominant('木星') in (2,8,11) else '本报告不将其他宫位主题换算为收入结论；可回顾学习、工作和生活安排对预算的实际影响。')+'预设说明不预测收益或亏损，不构成投资建议。','basis':evidence('木星')},
 {'title':'健康','text':'健康状态不能从星盘推断。本模块仅提供生活反思，不生成疾病、寿命或风险判断。'+focus('土星')+'可围绕对应生活安排检查是否留有休息和恢复空间，实际健康问题请依据医疗评估处理。','basis':evidence('土星')+'；宫位分布不作为健康证据。'}]
 return {'period':period,'theme':period+' 年度参考','summary':'先看全年星象分布，再从整体、感情、财富与健康四个模块阅读预设说明。','sections':sections,'events':[],'free':True,'isDemo':False,'ruleVersion':'annual-daily-distribution-v1','sampleCount':days,'note':'采用 Lahiri 恒星黄道，每日 UTC 12:00 采样；采样比例不等于精确停留时长，不提供精确换座或事件日期。固定规则解说，仅供文化学习与自我探索。'}

@lru_cache(maxsize=8)
def public_annual(year):
 """Nonpersonal sidereal snapshots with clearly separated cultural commentary."""
 samples=[]
 for month in (1,4,7,10):
  point=datetime(year,month,1,12,tzinfo=timezone.utc)
  positions=[{'name':p['name'],'sign':p['sign'],'degree':p['degree']} for p in planetary(point) if p['name'] in ('木星','土星','Rahu','Ketu')]
  samples.append({'date':point.strftime('%Y-%m-%d'),'positions':positions})
 return {'year':year,'title':f'{year} 年度星象','summary':'印度占星采用恒星黄道描述天体位置。以下为四个季度起点的计算快照，并非完整换座或逆行事件表。','samples':samples,'method':'Lahiri 恒星黄道 · 地心位置 · UTC 12:00 · 平均月交点','topics':[{'title':'教育与知识传播','text':'印度占星传统常以木星象征知识与拓展。可以观察公共教育、研究与跨文化交流中的真实变化；这不意味着今年必然发生某项改革。'},{'title':'公共制度与长期建设','text':'土星在传统解说中常关联责任与约束。可关注制度执行、基础设施与长期项目的公开进展，不据此预言政策调整或社会危机。'},{'title':'技术与信息环境','text':'月交点在传统解释中带有变化与不确定性的象征。可将信息辨识、技术使用与公共讨论作为观察话题，不据此预测战争、灾害或市场涨跌。'}],'notice':'社会观察是传统象征的文化解说，不是新闻事实或重大事件预测。现实事件应以可靠公开信息为准。'}
