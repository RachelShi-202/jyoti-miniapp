"""Package the allowlisted source archive's backend, with explicit Unix modes."""
from pathlib import Path
import subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/package_source.py')],check=True)
out=ROOT/'dist/jyoti-backend.zip'
with zipfile.ZipFile(ROOT/'dist/jyoti-source.zip') as src,zipfile.ZipFile(out,'w') as dst:
 for name in src.namelist():
  if not name.startswith('backend/') or name.startswith('backend/tests/'):
   continue
  info=zipfile.ZipInfo(name[len('backend/'):])
  info.create_system=3
  info.external_attr=0o100644 << 16
  info.compress_type=zipfile.ZIP_DEFLATED
  dst.writestr(info,src.read(name))
with zipfile.ZipFile(out) as z:
 assert {'Dockerfile','main.py','astro.py','features.py','providers.py','LICENSE'} <= set(z.namelist())
 assert all(((i.external_attr >> 16) & 0o777)==0o644 for i in z.infolist())
print('Backend archive verified: regular files have mode 0644.')
