import os,json,math,httpx
from fastapi import HTTPException
PROVINCES={'11','12','13','14','15','21','22','23','31','32','33','34','35','36','37','41','42','43','44','45','46','50','51','52','53','54','61','62','63','64','65'}
def gcj_to_wgs(lat,lon):
 # Numerical inverse of conventional GCJ-02 transform, approximate (not a survey conversion).
 def forward(a,b):
  x=b-105;y=a-35
  dlat=-100+2*x+3*y+.2*y*y+.1*x*y+.2*math.sqrt(abs(x))
  dlon=300+x+2*y+.1*x*x+.1*x*y+.1*math.sqrt(abs(x))
  dlat+=(20*math.sin(6*x*math.pi)+20*math.sin(2*x*math.pi))*2/3
  dlat+=(20*math.sin(y*math.pi)+40*math.sin(y/3*math.pi))*2/3
  dlat+=(160*math.sin(y/12*math.pi)+320*math.sin(y*math.pi/30))*2/3
  dlon+=(20*math.sin(6*x*math.pi)+20*math.sin(2*x*math.pi))*2/3
  dlon+=(20*math.sin(x*math.pi)+40*math.sin(x/3*math.pi))*2/3
  dlon+=(150*math.sin(x/12*math.pi)+300*math.sin(x/30*math.pi))*2/3
  rad=a/180*math.pi;magic=1-.00669342162296594323*math.sin(rad)**2
  dlat=dlat*180/((6378245*(1-.00669342162296594323))/(magic*math.sqrt(magic))*math.pi)
  dlon=dlon*180/(6378245/math.sqrt(magic)*math.cos(rad)*math.pi)
  return a+dlat,b+dlon
 a,b=lat,lon
 for _ in range(8):
  la,lo=forward(a,b);a-=la-lat;b-=lo-lon
 return round(a,7),round(b,7)
async def geocode(address):
 key=os.getenv('TENCENT_MAP_KEY')
 if not key:raise HTTPException(503,'请先在后端配置腾讯地图 Key')
 try:
  async with httpx.AsyncClient(timeout=12) as c:
   resp=await c.get('https://apis.map.qq.com/ws/geocoder/v1/',params={'address':address,'key':key});resp.raise_for_status();data=resp.json()
 except (httpx.HTTPError,ValueError):raise HTTPException(502,'地点服务暂不可用，请稍后重试')
 if data.get('status')!=0:raise HTTPException(502,'地点查询失败，请检查地址、地图 Key 及服务配额')
 result=data.get('result',{});ad=result.get('ad_info',{});code=str(ad.get('adcode',''))
 if len(code)!=6 or code[:2] not in PROVINCES:raise HTTPException(422,'当前仅支持中国大陆出生地点')
 try:
  glat=float(result['location']['lat']);glon=float(result['location']['lng'])
  if not math.isfinite(glat+glon) or not (0<glat<60 and 70<glon<140):raise ValueError()
  lat,lon=gcj_to_wgs(glat,glon)
 except (KeyError,ValueError,TypeError):raise HTTPException(502,'地点服务未返回有效坐标')
 return {'placeLabel':result.get('title') or address,'matchedAddress':result.get('address_components',{}),'latitude':lat,'longitude':lon,'timezone':'Asia/Shanghai','coordinateSystem':'WGS84','adcode':code,'source':'腾讯地图 GCJ-02 → WGS84 近似转换'}
