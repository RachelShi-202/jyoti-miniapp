"""Server-local admin only. Does not expose an HTTP grant endpoint."""
import sqlite3,os,argparse,time
p=argparse.ArgumentParser();p.add_argument('uid',help='existing pseudonymous user ID');p.add_argument('--days',type=int,required=True);a=p.parse_args()
if a.days<0 or a.days>3650:raise SystemExit('days must be 0..3650')
with sqlite3.connect(os.getenv('JYOTI_DB','./data/jyoti.sqlite3')) as c:
 if not c.execute('SELECT 1 FROM users WHERE id=?',(a.uid,)).fetchone():raise SystemExit('Unknown user')
 c.execute('INSERT OR REPLACE INTO members VALUES(?,?)',(a.uid,time.time()+a.days*86400))
print('Membership updated; days=0 revokes access. No payment was processed.')
