"""Run only on the server. Never expose this as a public HTTP endpoint."""
import argparse,csv,hashlib,os,secrets,sqlite3,time
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--count',type=int,default=10)
p.add_argument('--days',type=int,default=0,help='0 means no expiry')
p.add_argument('--product',choices=('single','topic','consult','annual','rectification'),default='topic')
p.add_argument('--output',required=True)
p.add_argument('--disable',help='Disable a code using hidden input; set to yes')
a=p.parse_args()
if not 1<=a.count<=1000 or not 0<=a.days<=3650:raise SystemExit('数量须1–1000，有效期须0–3650天；0表示无期限')
path=Path(os.getenv('JYOTI_DB_PATH',Path(__file__).parent/'data/jyoti.sqlite3'))
if not path.exists():raise SystemExit('请先启动更新后的服务完成数据库初始化')
with sqlite3.connect(path,timeout=15) as db:
 if not db.execute("SELECT 1 FROM sqlite_master WHERE name='invite_codes'").fetchone():raise SystemExit('请先部署新版服务')
 if a.disable:
  import getpass
  code=getpass.getpass('输入需要停用的体验码：').strip().upper()
  n=db.execute('UPDATE invite_codes SET disabled=1 WHERE digest=?',(hashlib.sha256(code.encode()).hexdigest(),)).rowcount
  print('已停用' if n else '未找到体验码');raise SystemExit()
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 # Never overwrite or print invitations into terminal logs.
 fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 try:
  with os.fdopen(fd,'w',newline='') as file:
   w=csv.writer(file);w.writerow(['邀请码','权益','兑换截止时间UTC','可兑换账号数'])
   expires=time.time()+a.days*86400 if a.days else 0
   product={'annual':'annual:any'}.get(a.product,a.product)
   labels={'single':'¥4.9单项AI解读1份＋2轮追问','topic':'¥19.9多盘专题分析1份＋5轮追问','consult':'¥29.9全盘AI咨询1次＋30轮连续咨询','annual:any':'¥1年运解读1份（任选一个年份）','rectification':'¥39.9出生时间校准1次'}
   for _ in range(a.count):
    prefix={'single':'DX','topic':'ZT','consult':'QP','annual:any':'NY','rectification':'JZ'}[product]
    code='XY-'+prefix+'-'+secrets.token_hex(12).upper()
    db.execute('INSERT INTO invite_codes(digest,expires,max_uses,disabled,product) VALUES (?,?,1,0,?)',(hashlib.sha256(code.encode()).hexdigest(),expires,product))
    w.writerow([code,labels[product],time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(expires)) if expires else '无期限',1])
 except BaseException:
  out.unlink(missing_ok=True);raise
print(f'已生成{a.count}个{a.product}单次邀请码，明文仅保存于指定私有文件，请勿公开上传。')
