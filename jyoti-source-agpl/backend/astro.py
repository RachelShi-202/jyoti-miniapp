"""Deterministic Lahiri chart calculation, with explicit uncertainty handling."""
import math
import threading
from datetime import datetime, date, timezone, timedelta
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
BODIES=[('太阳',swe.SUN),('月亮',swe.MOON),('水星',swe.MERCURY),('金星',swe.VENUS),('火星',swe.MARS),('木星',swe.JUPITER),('土星',swe.SATURN),('Rahu',swe.MEAN_NODE)]
VERSION='lahiri-moshier-mean-node-365.25-v1'

def resolve_time(day,clock,tzname,fold=None):
 try: zone=ZoneInfo(tzname)
 except (ZoneInfoNotFoundError,ValueError): raise ValueError('无效的 IANA 时区，例如 Asia/Shanghai')
 naive=datetime.fromisoformat(day+'T'+clock)
 candidates={}
 for f in (0,1):
  local=naive.replace(tzinfo=zone,fold=f); utc=local.astimezone(timezone.utc)
  if utc.astimezone(zone).replace(tzinfo=None)==naive:candidates[f]=utc
 if not candidates:raise ValueError('该当地时刻处于夏令时跳时区间，请核实出生时刻')
 if len(set(candidates.values()))>1 and fold is None:raise ValueError('该时刻在夏令时切换时重复出现，请选择第一次或第二次')
 return candidates.get(fold if fold is not None else 0,next(iter(candidates.values())))

def validate(p):
 try:d=date.fromisoformat(p['date'])
 except (KeyError,ValueError,TypeError):raise ValueError('出生日期无效')
 if d<date(1900,1,1) or d>datetime.now(timezone.utc).date():raise ValueError('出生日期须介于 1900 年与今天之间')
 if p.get('accuracy') not in (0,1,2):raise ValueError('时间准确程度无效')
 if p.get('consent') is not True:raise ValueError('需同意资料处理说明')
 for key,limit in [('latitude',90),('longitude',180)]:
  try:v=float(p[key])
  except (KeyError,ValueError,TypeError):raise ValueError('请填写有效经纬度')
  if not math.isfinite(v) or abs(v)>limit:raise ValueError('经纬度超出范围')
 if p.get('coordinateSystem')!='WGS84':raise ValueError('请确认坐标为 WGS84')
 try: ZoneInfo(p.get('timezone',''))
 except (ValueError,ZoneInfoNotFoundError):raise ValueError('无效的 IANA 时区')
 if not p.get('placeLabel','').strip():raise ValueError('请填写出生地点名称')
 if p['accuracy']!=2:
  try: datetime.strptime(p.get('time',''),'%H:%M')
  except (ValueError,TypeError):raise ValueError('出生时间须为 HH:MM')
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

def calculate(p):
 validate(p)
 if p['accuracy']==2:
  return {'version':VERSION,'status':'needs_time','message':'出生时刻未知，暂不计算个人星盘与周期数据。补充时刻后可继续。','planets':[],'dashas':[],'d9':[],'ascendant':None,'isDemo':False}
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
 if chart['status']!='calculated':return {'period':period,'theme':'先补充准确出生时刻','summary':chart['message'],'events':[],'sections':[],'isDemo':False,'free':True}
 trans=planetary(point);asc=chart['ascendant']['signIndex'];events=[]
 for planet in trans:
  if planet['name'] not in ('木星','土星'):continue
  house=(planet['signIndex']-asc)%12+1;theme=THEMES[house-1]
  events.append({'id':period+'-'+planet['name'],'label':period+' · 月中行运快照','title':theme,'body':'本月可围绕「'+theme+'」记录一个关注点，并回顾自己的行动。','basis':f"{point.isoformat()}，恒星黄道 {planet['name']} 位于{planet['sign']} {planet['degree']:.2f}°，相对本命上升为第 {house} 宫。基于月中采样，不代表整月持续，也不是事件发生日期。"})
 current=next((x for x in chart['dashas'] if x['start']<=point.isoformat()<x['end']),None)
 sub=next((x for x in current['subperiods'] if x['start']<=point.isoformat()<x['end']),None) if current else None
 return {'period':period,'theme':' / '.join(e['title'] for e in events),'summary':f"月中参考周期：{current['lord']}大运 · {sub['lord']}分运。" if current and sub else '该月份超出当前大运展示区间。','events':events,'sections':[{'title':e['title'],'text':e['body'],'basis':e['basis']} for e in events],'ruleVersion':'monthly-snapshot-v1','isDemo':False,'free':True,'note':'基础规则试用版：行运位置是真实计算值，解读是娱乐性主题提示；尚未实现精确星象事件搜寻及完整专业论断。'}
