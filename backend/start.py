"""Local launcher. Reads private .env without printing values or executing shell code."""
import os
from pathlib import Path
allowed={'WX_OPENAPI_HOST','WX_APP_ID','WX_APP_SECRET','JYOTI_ENV','JYOTI_DB','ALLOW_LOCAL_LOGIN','ASTRO_LICENSE_CONFIRMED','TENCENT_MAP_KEY','AI_API_KEY','AI_MODEL','AI_DAILY_LIMIT'}
p=Path(__file__).with_name('.env')
if p.exists():
 for line in p.read_text().splitlines():
  if line.strip().startswith('#') or '=' not in line:continue
  key,value=line.split('=',1)
  if key.strip() in allowed:os.environ.setdefault(key.strip(),value.strip())
if __name__=='__main__':
 from sync_lan import sync
 try:sync()
 except Exception as e:print('局域网地址同步失败：'+str(e))
 import json
 project=Path(__file__).parent.parent/'project.config.json'
 if project.exists() and os.getenv('WX_APP_ID')!=json.loads(project.read_text())['appid']:
  raise SystemExit('前后端 AppID 不一致，请先运行配置微信密钥.command，填写当前账号密钥。')
 import uvicorn
 os.chdir(Path(__file__).parent)
 uvicorn.run('main:app',host='0.0.0.0',port=8000,access_log=False,proxy_headers=False)
