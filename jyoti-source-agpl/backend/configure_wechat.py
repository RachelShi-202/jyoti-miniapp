import getpass,os,re,json
from pathlib import Path
p=Path(__file__).with_name('.env')
appid=json.loads((p.parent.parent/'project.config.json').read_text())['appid']
print('当前项目 AppID：'+appid+'；请填写该账号的 AppSecret。')
secret=getpass.getpass('请输入微信 AppSecret（输入不显示）：').strip()
if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',secret):raise SystemExit('格式不符合预期，未写入。')
values={}
if p.exists():
 for line in p.read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1);values[k.strip()]=v.strip()
values.update(WX_APP_ID=appid,WX_APP_SECRET=secret)
values.setdefault('JYOTI_ENV','development');values.setdefault('ALLOW_LOCAL_LOGIN','0')
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
os.chmod(p,0o600)
with os.fdopen(fd,'w') as f:f.write('\n'.join(k+'='+v for k,v in values.items())+'\n')
print('已保存到 backend/.env。密钥不会写入小程序前端。重启后端使配置生效。')
