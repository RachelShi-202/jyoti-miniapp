"""Build an allowlisted source archive; fail if known local secrets are present."""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]
files=[]
if (ROOT/'backend/.env.example').exists():files.append(ROOT/'backend/.env.example')
for name in ('LICENSE','NOTICE','THIRD_PARTY.md','SOURCE_RELEASE.md','project.config.json'):
 files.append(ROOT/name)
for dirname in ('miniprogram','backend','tests','tools','third_party'):
 for p in (ROOT/dirname).rglob('*'):
  if not p.is_file() or p.is_symlink():continue
  parts=p.relative_to(ROOT/dirname).parts
  if any(x.startswith('.') or x in ('data','__pycache__','node_modules') for x in parts):continue
  if p.suffix in ('.py','.js','.json','.wxml','.wxss','.png','.jpg','.svg','.gz') or p.name in ('Dockerfile','requirements.txt'):
   files.append(p)
secrets=[]
env=ROOT/'backend/.env'
if env.exists():
 for line in env.read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1)
   if any(x in k.upper() for x in ('SECRET','API_KEY','MAP_KEY','PASSWORD')) and len(v.strip())>=12:secrets.append(v.strip().encode())
manifest={}
for p in files:
 blob=p.read_bytes()
 if any(secret in blob for secret in secrets):raise SystemExit('检测到私有配置值，停止打包：'+str(p.relative_to(ROOT)))
 manifest[str(p.relative_to(ROOT))]=hashlib.sha256(blob).hexdigest()
out=ROOT/'dist';out.mkdir(exist_ok=True)
with zipfile.ZipFile(out/'jyoti-source.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):z.write(p,str(p.relative_to(ROOT)))
 z.writestr('SOURCE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
print('已生成不含已知本地密钥的源码包，共 '+str(len(files))+' 个文件。')
