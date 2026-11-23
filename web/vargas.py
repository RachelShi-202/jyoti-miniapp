"""Parashari sign assignments. Divisional positions are symbolic, not sky longitudes.
References and method choices: VARGA_METHODS.md. Zero-based sign indices.
"""
import math
from astro import SIGNS

VARGAS={
 2:('Hora 二分盘','资源与价值','采用太阳／月亮 Hora：只映射至狮子与巨蟹。观察资源管理的传统象征，不预测财富数额。'),
 3:('Drekkana 三分盘','协作与行动','从本命星座起，依次映射至第一、第五、第九星座。可讨论同辈互动与行动方式，不判定他人命运。'),
 7:('Saptamsa 七分盘','照顾与创造','传统关联养育与延续；这里用于理解照顾、创造与责任，不推断生育能力、子女性别或数量。'),
 9:('Navamsa 九分盘','关系与内在取向','作为本命盘的辅助视角阅读价值与承诺，不单凭此盘判断婚姻结局。'),
 10:('Dasamsa 十分盘','工作与社会角色','传统用于讨论职业与行动。适合反思职责和投入，不保证职位、晋升或事业结果。'),
 12:('Dwadasamsa 十二分盘','家庭与传承','从本命星座起顺排十二段。用于回顾家庭经验与代际影响，不推断父母健康或寿命。'),
 24:('Siddhamsa 二十四分盘','学习与知识','奇数星座从狮子起、偶数从巨蟹起，均顺排。用于讨论学习投入，不判断智力或考试成败。'),
 30:('Trimsamsa 三十分盘','压力与应对','采用 Parashari 五段不等分法，不是三十个一度段。用于反思压力与应对方式，不预测灾祸、疾病或厄运。'),
 4:('Chaturthamsa 田宅盘', '居所、房产与安居基础', '四等分，依次映射本座及第四、第七、第十座。补充居住环境与安居主题，不保证房产收益。'),
 16:('Shodashamsa 十六分盘', '车辆、出行与生活享受', '活动、固定、双体星座分别从白羊、狮子、射手顺排。补充生活舒适感与出行主题，不预测交通事故。'),
 20:('Vimshamsa 二十分盘', '信念、精神生活与修习', '活动、固定、双体星座分别从白羊、射手、狮子顺排。补充信念和精神生活，不评判宗教或宣称超自然能力。'),
 27:('Bhamsa 二十七分盘', '优势、短板与承压方式', '火、土、风、水象分别从白羊、巨蟹、天秤、摩羯顺排。补充优势和应对困难的传统主题，不作能力排名。'),
 40:('Khavedamsa 四十分盘', '母系传承与内在福祉', '奇数星座从白羊、偶数从天秤顺排。对出生时刻敏感，不替母系家人判断命运。'),
 45:('Akshavedamsa 四十五分盘', '父系传承与品性禀赋', '活动、固定、双体星座分别从白羊、狮子、射手顺排。对出生时刻敏感，不替父系家人判断命运。'),
 60:('Shashtyamsa 六十分盘', '深层禀赋与人生底色', '六十等分，从本命所在星座顺排，与小红书版一致；不采用白羊起算或偶数逆排变体。对出生时刻高度敏感，不断定前世或宿命。'),
}

def sign_for(longitude, division):
 if division not in VARGAS:raise ValueError('不支持的分盘')
 if not math.isfinite(longitude):raise ValueError('黄经必须是有限值')
 lon=longitude%360; s=int(lon//30); d=lon-s*30; odd=s%2==0
 if division==30:
  bounds=(5,10,18,25,30) if odd else (5,12,20,25,30)
  targets=(0,10,8,2,6) if odd else (1,5,11,9,7)
  return targets[next(i for i,end in enumerate(bounds) if d<end)]
 scaled=d*division/30
 nearest=round(scaled)
 part=min(division-1,nearest if abs(scaled-nearest)<1e-12 else math.floor(scaled))
 if division==2:return (4 if part==0 else 3) if odd else (3 if part==0 else 4)
 if division==3:return (s+4*part)%12
 if division==4:return (s+3*part)%12
 if division in (16,45):return ((s%3)*4+part)%12
 if division==20:return ((0,8,4)[s%3]+part)%12
 if division==27:return ((s%4)*3+part)%12
 if division==40:return ((0 if odd else 6)+part)%12
 if division==60:return (s+part)%12
 if division==7:return (s+(0 if odd else 6)+part)%12
 if division==9:return (s*9+part)%12
 if division==10:return (s+(0 if odd else 8)+part)%12
 if division==12:return (s+part)%12
 if division==24:return ((4 if odd else 3)+part)%12

def enrich(chart):
 chart['vargaVersion']='parashari-shodashavarga-v2'
 chart['divisions']={}
 if chart['status']!='calculated':return chart
 for n,(title,theme,note) in sorted(VARGAS.items()):
  asc=sign_for(chart['ascendant']['longitude'],n)
  planets=[]
  for p in chart['planets']:
   sign=sign_for(p['longitude'],n)
   planets.append({'name':p['name'],'signIndex':sign,'sign':SIGNS[sign],'house':(sign-asc)%12+1})
  chart['divisions']['d'+str(n)]={'title':f'D{n} · {title}','theme':theme,'note':note,'ascendant':{'signIndex':asc,'sign':SIGNS[asc]},'planets':planets}
 return chart
