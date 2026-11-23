"""Privacy-preserving product analytics for the operator dashboard."""
import hmac
import hashlib
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException


TZ = ZoneInfo("Asia/Shanghai")
ADMIN_COOKIE = 'xingxu_analytics_admin'
ADMIN_SESSION_TTL = 12*3600


def _local_day(timestamp=None):
 return datetime.fromtimestamp(timestamp or time.time(), TZ).date().isoformat()


def initialize(store):
 now=time.time()
 with store.connect() as db:
  db.executescript('''CREATE TABLE IF NOT EXISTS analytics_activity(
user_id TEXT NOT NULL,day TEXT NOT NULL,first_seen REAL NOT NULL,last_seen REAL NOT NULL,request_count INTEGER NOT NULL,
PRIMARY KEY(user_id,day));
CREATE INDEX IF NOT EXISTS analytics_activity_day ON analytics_activity(day,user_id);
CREATE TABLE IF NOT EXISTS analytics_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
  db.execute('INSERT OR IGNORE INTO analytics_meta VALUES (?,?)',('tracking_started_at',str(now)))


def touch(store,user_id,now=None):
 """Record one authenticated activity without retaining identity or request content."""
 if not user_id:return
 now=now or time.time();day=_local_day(now)
 with store.connect() as db:
  db.execute('''INSERT INTO analytics_activity(user_id,day,first_seen,last_seen,request_count)
VALUES (?,?,?,?,1)
ON CONFLICT(user_id,day) DO UPDATE SET last_seen=excluded.last_seen,request_count=request_count+1''',(user_id,day,now,now))


def create_admin_session(token,now=None):
 expected=os.getenv('ANALYTICS_ADMIN_TOKEN','')
 if not expected:raise HTTPException(503,'数据统计接口尚未配置管理员令牌')
 if not token or not hmac.compare_digest(token,expected):raise HTTPException(401,'管理员口令不正确')
 expires=int((now or time.time())+ADMIN_SESSION_TTL)
 signature=hmac.new(expected.encode(),str(expires).encode(),hashlib.sha256).hexdigest()
 return f'{expires}.{signature}'


def valid_admin_session(value,now=None):
 expected=os.getenv('ANALYTICS_ADMIN_TOKEN','')
 if not expected or not value:return False
 try:
  expires_text,signature=value.split('.',1);expires=int(expires_text)
 except (ValueError,TypeError):return False
 current=int(now or time.time())
 if expires<current or expires>current+ADMIN_SESSION_TTL+60:return False
 wanted=hmac.new(expected.encode(),expires_text.encode(),hashlib.sha256).hexdigest()
 return hmac.compare_digest(signature,wanted)


def require_admin(request):
 expected=os.getenv('ANALYTICS_ADMIN_TOKEN','')
 supplied=request.headers.get('x-analytics-token','')
 if not expected:raise HTTPException(503,'数据统计接口尚未配置管理员令牌')
 if supplied and hmac.compare_digest(supplied,expected):return
 if valid_admin_session(request.cookies.get(ADMIN_COOKIE,'')):return
 raise HTTPException(401,'请先登录数据后台')


def _periods(now=None):
 current=datetime.fromtimestamp(now or time.time(),TZ)
 today=current.replace(hour=0,minute=0,second=0,microsecond=0)
 return today.timestamp(),(today-timedelta(days=29)).timestamp(),today.date().isoformat(),(today.date()-timedelta(days=29)).isoformat()


def _money(rows):
 result={'cnyFen':0,'usdCents':0}
 for channel,amount in rows:
  result['usdCents' if channel=='paypal' else 'cnyFen']+=int(amount or 0)
 result['cnyYuan']=f"{result['cnyFen']/100:.2f}"
 result['usd']=f"{result['usdCents']/100:.2f}"
 return result


def _group(rows):return {str(key):int(value) for key,value in rows}


def summary(store,days=30,now=None):
 if days<1 or days>366:raise HTTPException(422,'统计区间应为1至366天')
 now=now or time.time();today_ts,month_ts,today_day,month_day=_periods(now)
 start_day=(datetime.fromtimestamp(now,TZ).date()-timedelta(days=days-1)).isoformat()
 period_ts=datetime.fromisoformat(start_day).replace(tzinfo=TZ).timestamp()
 with store.connect() as db:
  tracking=db.execute("SELECT value FROM analytics_meta WHERE key='tracking_started_at'").fetchone()
  users={
   'total':db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
   'emailVerified':db.execute("SELECT COUNT(*) FROM users WHERE identity LIKE 'email:%'").fetchone()[0],
   'phoneVerified':db.execute("SELECT COUNT(*) FROM users WHERE identity LIKE 'phone:%'").fetchone()[0],
   'newToday':db.execute('SELECT COUNT(*) FROM users WHERE created>=?',(today_ts,)).fetchone()[0],
   'new30Days':db.execute('SELECT COUNT(*) FROM users WHERE created>=?',(month_ts,)).fetchone()[0],
   'newInPeriod':db.execute('SELECT COUNT(*) FROM users WHERE created>=?',(period_ts,)).fetchone()[0],
  }
  orders={
   'total':db.execute('SELECT COUNT(*) FROM payment_orders').fetchone()[0],
   'paid':db.execute("SELECT COUNT(*) FROM payment_orders WHERE status='paid'").fetchone()[0],
   'paidUsers':db.execute("SELECT COUNT(DISTINCT owner) FROM payment_orders WHERE status='paid'").fetchone()[0],
   'createdToday':db.execute('SELECT COUNT(*) FROM payment_orders WHERE created>=?',(today_ts,)).fetchone()[0],
   'created30Days':db.execute('SELECT COUNT(*) FROM payment_orders WHERE created>=?',(month_ts,)).fetchone()[0],
   'paidInPeriod':db.execute("SELECT COUNT(*) FROM payment_orders WHERE status='paid' AND paid_at>=?",(period_ts,)).fetchone()[0],
   'paidUsersInPeriod':db.execute("SELECT COUNT(DISTINCT owner) FROM payment_orders WHERE status='paid' AND paid_at>=?",(period_ts,)).fetchone()[0],
   'byStatus':_group(db.execute('SELECT status,COUNT(*) FROM payment_orders GROUP BY status').fetchall()),
   'byChannel':_group(db.execute('SELECT channel,COUNT(*) FROM payment_orders GROUP BY channel').fetchall()),
   'byProduct':_group(db.execute('SELECT product,COUNT(*) FROM payment_orders GROUP BY product').fetchall()),
   'byChannelInPeriod':_group(db.execute("SELECT channel,COUNT(*) FROM payment_orders WHERE status='paid' AND paid_at>=? GROUP BY channel",(period_ts,)).fetchall()),
   'byProductInPeriod':_group(db.execute("SELECT product,COUNT(*) FROM payment_orders WHERE status='paid' AND paid_at>=? GROUP BY product",(period_ts,)).fetchall()),
  }
  reports={
   'total':db.execute('SELECT COUNT(*) FROM saved_reports').fetchone()[0],
   'creators':db.execute('SELECT COUNT(DISTINCT owner_id) FROM saved_reports').fetchone()[0],
   'createdToday':db.execute('SELECT COUNT(*) FROM saved_reports WHERE created>=?',(today_ts,)).fetchone()[0],
   'created30Days':db.execute('SELECT COUNT(*) FROM saved_reports WHERE created>=?',(month_ts,)).fetchone()[0],
   'createdInPeriod':db.execute('SELECT COUNT(*) FROM saved_reports WHERE created>=?',(period_ts,)).fetchone()[0],
   'byProduct':_group(db.execute('SELECT product,COUNT(*) FROM saved_reports GROUP BY product').fetchall()),
   'byProductInPeriod':_group(db.execute('SELECT product,COUNT(*) FROM saved_reports WHERE created>=? GROUP BY product',(period_ts,)).fetchall()),
  }
  gross=_money(db.execute("SELECT channel,amount_fen FROM payment_orders WHERE paid_at IS NOT NULL").fetchall())
  net=_money(db.execute("SELECT channel,amount_fen FROM payment_orders WHERE status='paid'").fetchall())
  refunded=_money(db.execute("SELECT channel,amount_fen FROM payment_orders WHERE status='refunded'").fetchall())
  period_net=_money(db.execute("SELECT channel,amount_fen FROM payment_orders WHERE status='paid' AND paid_at>=?",(period_ts,)).fetchall())
  gmv={'gross':gross,'net':net,'refunded':refunded,'periodNet':period_net}
  activity={
   'dau':db.execute('SELECT COUNT(*) FROM analytics_activity WHERE day=?',(today_day,)).fetchone()[0],
   'mau30Days':db.execute('SELECT COUNT(DISTINCT user_id) FROM analytics_activity WHERE day>=?',(month_day,)).fetchone()[0],
   'activeInPeriod':db.execute('SELECT COUNT(DISTINCT user_id) FROM analytics_activity WHERE day>=?',(start_day,)).fetchone()[0],
   'trackingStartedAt':float(tracking[0]) if tracking else None,
   'definition':'已登录且当天至少完成一次站内 API 操作的唯一账号',
  }
  daily_rows={row[0]:row[1:] for row in db.execute('''SELECT day,COUNT(DISTINCT user_id),SUM(request_count)
FROM analytics_activity WHERE day>=? GROUP BY day''',(start_day,)).fetchall()}
  new_users={row[0]:row[1] for row in db.execute("SELECT date(created,'unixepoch','+8 hours'),COUNT(*) FROM users WHERE created>=? GROUP BY 1",(datetime.fromisoformat(start_day).replace(tzinfo=TZ).timestamp(),)).fetchall()}
  paid_orders={row[0]:(row[1],row[2],row[3]) for row in db.execute("""SELECT date(paid_at,'unixepoch','+8 hours'),COUNT(*),
SUM(CASE WHEN channel='paypal' THEN 0 ELSE amount_fen END),SUM(CASE WHEN channel='paypal' THEN amount_fen ELSE 0 END)
FROM payment_orders WHERE paid_at IS NOT NULL AND paid_at>=? GROUP BY 1""",(datetime.fromisoformat(start_day).replace(tzinfo=TZ).timestamp(),)).fetchall()}
  report_rows={row[0]:row[1] for row in db.execute("SELECT date(created,'unixepoch','+8 hours'),COUNT(*) FROM saved_reports WHERE created>=? GROUP BY 1",(datetime.fromisoformat(start_day).replace(tzinfo=TZ).timestamp(),)).fetchall()}
 daily=[];day=datetime.fromisoformat(start_day).date()
 for offset in range(days):
  key=(day+timedelta(days=offset)).isoformat();active=daily_rows.get(key,(0,0));paid=paid_orders.get(key,(0,0,0))
  daily.append({'date':key,'activeUsers':int(active[0] or 0),'authenticatedRequests':int(active[1] or 0),'newUsers':int(new_users.get(key,0)),'paidOrders':int(paid[0] or 0),'cnyGmvFen':int(paid[1] or 0),'usdGmvCents':int(paid[2] or 0),'reports':int(report_rows.get(key,0))})
 return {'generatedAt':now,'timezone':'Asia/Shanghai','periodDays':days,'users':users,'orders':orders,'gmv':gmv,'reports':reports,'activity':activity,'daily':daily}
