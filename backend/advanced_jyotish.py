"""Auditable Jyotish derived charts and screening rules built on verified D1 positions."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from astro import SIGNS,NAK,SIGN_LORDS,planetary,moment_chart,resolve_time

VERSION='advanced-jyotish-operational-v1'
CLASSICAL=('太阳','月亮','火星','水星','木星','金星','土星')
OWN={'太阳':{4},'月亮':{3},'火星':{0,7},'水星':{2,5},'木星':{8,11},'金星':{1,6},'土星':{9,10}}
EXALT={'太阳':0,'月亮':1,'火星':9,'水星':5,'木星':3,'金星':11,'土星':6}
NATURAL={'太阳':60.0,'月亮':51.43,'金星':42.86,'木星':34.29,'水星':25.71,'火星':17.14,'土星':8.57}
DIG_HOUSE={'太阳':10,'火星':10,'月亮':4,'金星':4,'木星':1,'水星':1,'土星':7}
YOGA_NAMES=('Vishkambha','Priti','Ayushman','Saubhagya','Shobhana','Atiganda','Sukarma','Dhriti','Shula','Ganda','Vriddhi','Dhruva','Vyaghata','Harshana','Vajra','Siddhi','Vyatipata','Variyana','Parigha','Shiva','Siddha','Sadhya','Shubha','Shukla','Brahma','Indra','Vaidhriti')
VARA=('星期一','星期二','星期三','星期四','星期五','星期六','星期日')

def _angle(a,b):return abs((a-b+180)%360-180)
def _planet(chart,name):return next(item for item in chart['planets'] if item['name']==name)
def _house_from(sign,origin):return (sign-origin)%12+1

def panchanga(utc,tzname):
 """Five limbs at a moment: vara, tithi, nakshatra, yoga and karana."""
 if isinstance(utc,str):utc=datetime.fromisoformat(utc)
 if utc.tzinfo is None:raise ValueError('五历时刻必须包含时区')
 utc=utc.astimezone(timezone.utc);local=utc.astimezone(ZoneInfo(tzname));bodies={item['name']:item for item in planetary(utc)}
 sun=bodies['太阳']['longitude'];moon=bodies['月亮']['longitude'];elong=(moon-sun)%360
 tithi_index=int(elong//12);tithi_progress=(elong%12)/12
 half=int(elong//6)
 if half==0:karana='Kimstughna'
 elif half>=57:karana=('Shakuni','Chatushpada','Naga')[half-57]
 else:karana=('Bava','Balava','Kaulava','Taitila','Gara','Vanija','Vishti')[(half-1)%7]
 nak_index=int(moon//(360/27));yoga_index=int(((sun+moon)%360)//(360/27))
 return {'utc':utc.isoformat(),'local':local.isoformat(),'vara':{'index':local.weekday(),'name':VARA[local.weekday()]},'tithi':{'index':tithi_index+1,'paksha':'Shukla' if tithi_index<15 else 'Krishna','number':tithi_index%15+1,'progress':round(tithi_progress,6)},'nakshatra':{'index':nak_index+1,'name':NAK[nak_index],'pada':int((moon%(360/27))/(360/108))+1},'yoga':{'index':yoga_index+1,'name':YOGA_NAMES[yoga_index]},'karana':{'halfTithiIndex':half+1,'name':karana},'ruleVersion':'panchanga-five-limbs-moment-v1','note':'这是指定时刻的五历状态；未加入日出归日、Rahu Kalam、Hora及地方节庆规则。'}

def moon_lagna(chart):
 moon=_planet(chart,'月亮');origin=moon['signIndex']
 return {'ascendant':{'signIndex':origin,'sign':SIGNS[origin],'source':'natal Moon'},'planets':[{**item,'house':_house_from(item['signIndex'],origin)} for item in chart['planets']],'ruleVersion':'chandra-lagna-whole-sign-v1'}

def _arudha_for_house(chart,house):
 asc=chart['ascendant']['signIndex'];base=(asc+house-1)%12;lord=SIGN_LORDS[base];lord_sign=_planet(chart,lord)['signIndex'];distance=(lord_sign-base)%12;result=(lord_sign+distance)%12
 if distance in (0,6):result=(lord_sign+9)%12
 return {'sourceHouse':house,'sourceSign':SIGNS[base],'lord':lord,'lordSign':SIGNS[lord_sign],'signIndex':result,'sign':SIGNS[result],'houseFromLagna':_house_from(result,asc)}

def arudha_upapada(chart):
 return {'arudhaLagna':_arudha_for_house(chart,1),'upapadaLagna':_arudha_for_house(chart,12),'ruleVersion':'parashari-arudha-exception-v1','note':'采用整宫、宫主等距投射；宫主同宫或第七宫时取宫主星起第十宫。'}

def _aspects(planet):
 offsets={6}
 if planet['name']=='火星':offsets|={3,7}
 if planet['name']=='木星':offsets|={4,8}
 if planet['name']=='土星':offsets|={2,9}
 return {(planet['signIndex']+offset)%12 for offset in offsets}

def shadbala(chart):
 """Operational six-component strength; transparent, not a claim of full BPHS subcomponent parity."""
 local=datetime.fromisoformat(chart['utc']).astimezone(ZoneInfo(chart.get('timezone','UTC')));day=6<=local.hour<18
 benefic={'木星','金星','水星'};malefic={'太阳','火星','土星'};rows=[]
 for name in CLASSICAL:
  p=_planet(chart,name);sign=p['signIndex'];house=p['house'];debil=(EXALT[name]+6)%12
  sthana=60 if sign==EXALT[name] else 45 if sign in OWN[name] else 15 if sign==debil else 30
  distance=min((house-DIG_HOUSE[name])%12,(DIG_HOUSE[name]-house)%12);dig=round(max(0,60-distance*10),2)
  if name=='水星':kala=40
  else:kala=50 if (day and name in {'太阳','木星','金星'}) or (not day and name in {'月亮','火星','土星'}) else 20
  if name in ('太阳','月亮'):cheshta=30
  else:cheshta=60 if p.get('retrograde') else min(45,15+abs(float(p.get('speed',0)))*12)
  support=sum(1 for other in chart['planets'] if other['name'] in benefic and sign in _aspects(other));pressure=sum(1 for other in chart['planets'] if other['name'] in malefic and other['name']!=name and sign in _aspects(other));drik=max(0,min(60,30+support*10-pressure*10))
  components={'sthana':round(sthana,2),'dig':dig,'kala':round(kala,2),'cheshta':round(cheshta,2),'naisargika':NATURAL[name],'drik':round(drik,2)};total=round(sum(components.values()),2)
  rows.append({'planet':name,'componentsVirupas':components,'totalVirupas':total,'totalRupas':round(total/60,3)})
 return {'planets':rows,'isClassicalComplete':False,'ruleVersion':'shadbala-operational-six-component-v1','limitations':['Sthana、Kala、Cheshta与Drik使用可审计的简化子项','未实现完整Ayana/Ojayugma/Kendradi/Drekkana/Hora等全部古典细项'],'use':'可用于相对强弱排序，不得冒充完整古典Shadbala认证值。'}

def bhava_bala(chart,shad=None):
 shad=shad or shadbala(chart);strength={item['planet']:item['totalVirupas'] for item in shad['planets']};maximum=max(strength.values()) or 1;asc=chart['ascendant']['signIndex'];rows=[]
 for house in range(1,13):
  sign=(asc+house-1)%12;lord=SIGN_LORDS[sign];lord_score=60*strength[lord]/maximum
  placement=60 if house in (1,4,7,10) else 45 if house in (5,9) else 35 if house in (2,11) else 20
  support=sum(1 for p in chart['planets'] if p['name'] in {'木星','金星','水星'} and sign in _aspects(p));pressure=sum(1 for p in chart['planets'] if p['name'] in {'太阳','火星','土星'} and sign in _aspects(p));drishti=max(0,min(60,30+support*10-pressure*10));total=round(lord_score+placement+drishti,2)
  rows.append({'house':house,'sign':SIGNS[sign],'lord':lord,'componentsVirupas':{'lordStrength':round(lord_score,2),'placement':placement,'drishti':drishti},'totalVirupas':total})
 return {'houses':rows,'isClassicalComplete':False,'ruleVersion':'bhava-bala-operational-v1','limitations':['宫主力继承operational Shadbala','宫位方向力与视力为整宫制简化模型'],'use':'用于同一张盘内宫位相对排序。'}

def yoga_detection(chart):
 asc=chart['ascendant']['signIndex'];positions={p['name']:p for p in chart['planets']};detected=[];seen=set()
 def add(code,name,evidence):
  key=(code,str(evidence))
  if key not in seen:seen.add(key);detected.append({'code':code,'name':name,'evidence':evidence})
 for name in ('火星','水星','木星','金星','土星'):
  p=positions[name]
  if p['house'] in (1,4,7,10) and (p['signIndex'] in OWN[name] or p['signIndex']==EXALT[name]):add('pancha_mahapurusha','Pancha Mahapurusha',{'planet':name,'house':p['house'],'sign':p['sign']})
 if _house_from(positions['木星']['signIndex'],positions['月亮']['signIndex']) in (1,4,7,10):add('gajakesari','Gajakesari Yoga',{'moonSign':positions['月亮']['sign'],'jupiterSign':positions['木星']['sign']})
 if _angle(positions['木星']['longitude'],positions['Rahu']['longitude'])<=8 or _angle(positions['木星']['longitude'],positions['Ketu']['longitude'])<=8:add('guru_chandal','Guru Chandal combination',{'orbLimit':8})
 for i,left in enumerate(CLASSICAL):
  for right in CLASSICAL[i+1:]:
   if SIGN_LORDS[positions[left]['signIndex']]==right and SIGN_LORDS[positions[right]['signIndex']]==left:add('parivartana','Parivartana Yoga',{'planets':[left,right]})
 lords={house:SIGN_LORDS[(asc+house-1)%12] for house in range(1,13)}
 for trine in (1,5,9):
  for angle in (1,4,7,10):
   a,b=lords[trine],lords[angle]
   if a!=b and _angle(positions[a]['longitude'],positions[b]['longitude'])<=8:add('raja','Raja Yoga',{'houseLords':[trine,angle],'planets':[a,b],'orb':round(_angle(positions[a]['longitude'],positions[b]['longitude']),3)})
 for left in (2,5,9,11):
  for right in (2,5,9,11):
   if left>=right:continue
   a,b=lords[left],lords[right]
   if a!=b and _angle(positions[a]['longitude'],positions[b]['longitude'])<=8:add('dhana','Dhana Yoga',{'houseLords':[left,right],'planets':[a,b],'orb':round(_angle(positions[a]['longitude'],positions[b]['longitude']),3)})
 dusthana={6,8,12}
 for house in dusthana:
  lord=lords[house]
  if positions[lord]['house'] in dusthana:add('viparita_raja','Viparita Raja Yoga condition',{'lordOfHouse':house,'planet':lord,'placedHouse':positions[lord]['house']})
 return {'detected':detected,'ruleVersion':'parashari-yoga-evidence-v1','scope':['Pancha Mahapurusha','Gajakesari','Guru Chandal','Parivartana','Raja','Dhana','Viparita Raja'],'note':'只返回满足程序化条件的配置与证据，不自动宣称现实结果。'}

def advanced_natal(chart):
 shad=shadbala(chart)
 return {'moonLagna':moon_lagna(chart),'arudha':arudha_upapada(chart),'shadbala':shad,'bhavaBala':bhava_bala(chart,shad),'yogas':yoga_detection(chart),'version':VERSION}

EVENT_WEIGHTS={
 'general':{'vara':{0,2,3,4},'tithi':{2,3,5,7,10,11,13}},
 'marriage':{'vara':{0,2,3,4},'tithi':{2,3,5,7,10,11,13}},
 'contract':{'vara':{2,3,4},'tithi':{2,3,5,10,11,13}},
 'business':{'vara':{2,3,4},'tithi':{2,3,5,7,10,11}},
 'travel':{'vara':{0,2,3,4},'tithi':{2,3,5,7,10,11}},
 'house':{'vara':{0,2,3,4},'tithi':{2,3,5,7,10,11,13}},
}
INHARMONIOUS_YOGA={'Atiganda','Shula','Ganda','Vyaghata','Vajra','Vyatipata','Parigha','Vaidhriti'}

def muhurta_screen(start,end,tzname,latitude,longitude,event_type='general',step_minutes=60,limit=12,daily_start='06:00',daily_end='22:00'):
 """Rank transparent Panchanga screening slots; final election still needs expert/context review."""
 if start.tzinfo is None or end.tzinfo is None or not start<end:raise ValueError('择时区间无效')
 if end-start>timedelta(days=14):raise ValueError('单次择时区间最多14天')
 if step_minutes not in (30,60,90,120):raise ValueError('择时间隔须为30、60、90或120分钟')
 start_min=int(daily_start[:2])*60+int(daily_start[3:]);end_min=int(daily_end[:2])*60+int(daily_end[3:])
 if start_min>=end_min:raise ValueError('每日择时结束时间必须晚于开始时间')
 rules=EVENT_WEIGHTS.get(event_type,EVENT_WEIGHTS['general']);items=[];point=start
 while point<=end:
  local=point.astimezone(ZoneInfo(tzname));minute=local.hour*60+local.minute
  if not start_min<=minute<=end_min:point+=timedelta(minutes=step_minutes);continue
  pan=panchanga(point.astimezone(timezone.utc),tzname);score=50;reasons=[]
  if pan['vara']['index'] in rules['vara']:score+=10;reasons.append('weekday_supported')
  if pan['tithi']['number'] in rules['tithi']:score+=15;reasons.append('tithi_supported')
  if pan['karana']['name']=='Vishti':score-=20;reasons.append('vishti_caution')
  if pan['yoga']['name'] in INHARMONIOUS_YOGA:score-=15;reasons.append('yoga_caution')
  items.append({'utc':point.astimezone(timezone.utc).isoformat(),'local':point.astimezone(ZoneInfo(tzname)).isoformat(),'score':max(0,min(100,score)),'reasons':reasons,'panchanga':pan});point+=timedelta(minutes=step_minutes)
 selected=sorted(items,key=lambda item:(-item['score'],item['utc']))[:limit]
 for item in selected:item['chart']=moment_chart(item['utc'],latitude,longitude,tzname)
 return {'eventType':event_type,'candidates':selected,'evaluatedSlots':len(items),'ruleVersion':'muhurta-panchanga-screen-v1','status':'screening_only','limitations':['未实现Rahu Kalam、日出归日、Tarabala、Chandrabala与事件专属全部禁忌','分数用于筛选候选时刻，不构成最终吉凶结论']}
