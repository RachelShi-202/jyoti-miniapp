import getpass,os
from pathlib import Path
p=Path(__file__).with_name('.env');v={}
if p.exists():
 for line in p.read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,x=line.split('=',1);v[k.strip()]=x.strip()
for key,label in [('TENCENT_MAP_KEY','腾讯地图 WebService Key'),('AI_API_KEY','DeepSeek API Key')]:
 value=getpass.getpass(label+'（输入隐藏，留空保留原配置）：').strip()
 if value:v[key]=value
v.setdefault('AI_MODEL','deepseek-v4-flash');v.setdefault('AI_DAILY_LIMIT','10')
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);os.chmod(p,0o600)
with os.fdopen(fd,'w') as f:f.write('\n'.join(k+'='+x for k,x in v.items())+'\n')
print('已保存。请重启后端；未显示任何密钥。')
