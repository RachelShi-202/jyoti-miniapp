"""Account credits and one-use invitations. No client-controlled payment grants."""
import hashlib,json,secrets,time
from fastapi import HTTPException

def initialize(db):
 db.executescript('''CREATE TABLE IF NOT EXISTS credit_grants(id TEXT PRIMARY KEY,owner TEXT NOT NULL,product TEXT NOT NULL,source TEXT UNIQUE NOT NULL,amount INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS credit_uses(id TEXT PRIMARY KEY,owner TEXT NOT NULL,product TEXT NOT NULL,grant_id TEXT NOT NULL,state TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS invite_codes(digest TEXT PRIMARY KEY,expires REAL NOT NULL,max_uses INTEGER NOT NULL,disabled INTEGER NOT NULL DEFAULT 0,product TEXT NOT NULL DEFAULT 'topic');
CREATE TABLE IF NOT EXISTS invite_redemptions(digest TEXT NOT NULL,owner TEXT NOT NULL,created REAL NOT NULL,UNIQUE(digest,owner));
CREATE INDEX IF NOT EXISTS credit_owner ON credit_uses(owner,product,state);''')
 grant_columns={row[1] for row in db.execute('PRAGMA table_info(credit_grants)').fetchall()}
 for name,kind in [('order_id','TEXT'),('expires','REAL'),('created','REAL')]:
  if name not in grant_columns:db.execute(f'ALTER TABLE credit_grants ADD COLUMN {name} {kind}')
 use_columns={row[1] for row in db.execute('PRAGMA table_info(credit_uses)').fetchall()}
 for name,kind in [('task_ref','TEXT'),('report_ref','TEXT'),('updated','REAL')]:
  if name not in use_columns:db.execute(f'ALTER TABLE credit_uses ADD COLUMN {name} {kind}')
 db.execute('CREATE INDEX IF NOT EXISTS credit_grant_order ON credit_grants(owner,order_id)')
 if 'product' not in {row[1] for row in db.execute('PRAGMA table_info(invite_codes)').fetchall()}:
  db.execute("ALTER TABLE invite_codes ADD COLUMN product TEXT NOT NULL DEFAULT 'topic'")
 # Deployment runs one worker. An interrupted generation must not burn a credit.
 db.execute("UPDATE credit_uses SET state='released' WHERE state='reserved'")
 for owner,payload in db.execute('SELECT owner_id,payload FROM sessions WHERE owner_id IS NOT NULL').fetchall():
  if json.loads(payload).get('reports',{}).get('natal:'):
   grant=ensure_free(db,owner)
   if not db.execute("SELECT 1 FROM credit_uses WHERE grant_id=? AND state='consumed'",(grant,)).fetchone():
    now=time.time();db.execute('INSERT INTO credit_uses(id,owner,product,grant_id,state,created,updated) VALUES (?,?,?,?,?,?,?)',('legacy:'+owner,owner,'natal',grant,'consumed',now,now))
 db.execute('INSERT OR IGNORE INTO schema_version VALUES (5)')
 db.execute('INSERT OR IGNORE INTO schema_version VALUES (8)')

def _product_for_code(row):
 # Codes created before product-aware invites are treated as the legacy topic
 # product.  Unknown values are never allowed to create client-controlled
 # credits.
 product = row[0] if row else 'topic'
 return product if product in ('single','topic','consult','rectification','annual:any') else 'topic'

def repair_redeemed_grants(db):
 """Backfill a grant if an older deployment recorded redemption first.

 A previous version could persist invite_redemptions without its matching
 credit_grants row during an interrupted update.  Redemption is still the
 source of truth, so rebuilding the missing account grant makes the redeemed
 entitlement survive logout, restart, and container replacement.
 """
 rows = db.execute('''SELECT r.digest,r.owner,COALESCE(c.product,'topic')
                      FROM invite_redemptions r
                      LEFT JOIN invite_codes c ON c.digest=r.digest''').fetchall()
 for digest, owner, product in rows:
  product = product if product in ('single','topic','consult','rectification','annual:any') else 'topic'
  source = 'invite:'+digest+':'+owner
  grant(db, owner, product, source, 1)

def ensure_free(db,owner):
 key='free-natal:'+owner
 db.execute('INSERT OR IGNORE INTO credit_grants(id,owner,product,source,amount,created) VALUES (?,?,?,?,1,?)',(key,owner,'natal',key,time.time()))
 return key

def ensure_chart_free(db,owner,record_id):
 source='free-natal-chart:'+owner+':'+record_id
 key='free-natal-chart:'+hashlib.sha256((owner+'\0'+record_id).encode()).hexdigest()
 db.execute('INSERT OR IGNORE INTO credit_grants(id,owner,product,source,amount,created) VALUES (?,?,?,?,1,?)',(key,owner,'natal',source,time.time()))
 return key

def balance(db,owner,product):
 amount=db.execute('SELECT COALESCE(SUM(amount),0) FROM credit_grants WHERE owner=? AND product=? AND (expires IS NULL OR expires>?)',(owner,product,time.time())).fetchone()[0]
 used=db.execute("""SELECT COUNT(*) FROM credit_uses u JOIN credit_grants g ON g.id=u.grant_id
 WHERE u.owner=? AND g.product=? AND u.state IN ('reserved','consumed') AND (g.expires IS NULL OR g.expires>?)""",(owner,product,time.time())).fetchone()[0]
 return max(0,amount-used)

def _chart_natal_available(db,owner,record_id):
 if not db.execute('SELECT 1 FROM sessions WHERE owner_id=? AND record_id=? LIMIT 1',(owner,record_id)).fetchone():return 0
 if db.execute("SELECT 1 FROM saved_reports WHERE owner_id=? AND chart_id=? AND scope='natal:' LIMIT 1",(owner,record_id)).fetchone():return 0
 grant_id=ensure_chart_free(db,owner,record_id)
 used=db.execute("SELECT 1 FROM credit_uses WHERE grant_id=? AND state IN ('reserved','consumed') LIMIT 1",(grant_id,)).fetchone()
 return 0 if used else 1

def natal_available(store,owner,record_id):
 with store.connect() as db:return _chart_natal_available(db,owner,record_id)

def natal_balance(db,owner):
 record_ids=[row[0] for row in db.execute('SELECT DISTINCT record_id FROM sessions WHERE owner_id=? AND record_id IS NOT NULL',(owner,)).fetchall()]
 return sum(_chart_natal_available(db,owner,record_id) for record_id in record_ids)

def summary(store,owner):
 with store.connect() as db:
  repair_redeemed_grants(db)
  products=['single','topic','consult','rectification','followup','annual:any']+[row[0] for row in db.execute("SELECT DISTINCT product FROM credit_grants WHERE owner=? AND product LIKE 'annual:%'",(owner,)).fetchall()]
  result={p:balance(db,owner,p) for p in products};result['natal']=natal_balance(db,owner)
  return result

def grant(db,owner,product,source,amount=1,order_id=None,expires=None):
 now=time.time()
 db.execute('INSERT OR IGNORE INTO credit_grants(id,owner,product,source,amount,order_id,expires,created) VALUES (?,?,?,?,?,?,?,?)',(secrets.token_urlsafe(24),owner,product,source,amount,order_id,expires,now))
 if order_id:db.execute('UPDATE credit_grants SET order_id=COALESCE(order_id,?) WHERE source=?',(order_id,source))

def reserve(store,owner,product,record_id=None,task_ref=None,report_ref=None):
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  if db.execute("SELECT 1 FROM credit_uses WHERE owner=? AND state='reserved'",(owner,)).fetchone():raise HTTPException(409,'账号已有解读生成中，请等待完成')
  if product=='natal':
   if not record_id:raise HTTPException(422,'缺少当前星盘记录')
   row=(ensure_chart_free(db,owner,record_id),) if _chart_natal_available(db,owner,record_id) else None
  else:
   row=db.execute("SELECT g.id FROM credit_grants g WHERE owner=? AND product=? AND (g.expires IS NULL OR g.expires>?) AND amount>(SELECT COUNT(*) FROM credit_uses u WHERE u.grant_id=g.id AND state IN ('reserved','consumed')) ORDER BY g.expires IS NULL,g.expires,g.rowid LIMIT 1",(owner,product,time.time())).fetchone()
  if not row and product.startswith('annual:') and product!='annual:any':
   row=db.execute("SELECT g.id FROM credit_grants g WHERE owner=? AND product='annual:any' AND (g.expires IS NULL OR g.expires>?) AND amount>(SELECT COUNT(*) FROM credit_uses u WHERE u.grant_id=g.id AND state IN ('reserved','consumed')) ORDER BY g.expires IS NULL,g.expires,g.rowid LIMIT 1",(owner,time.time())).fetchone()
  if not row:raise HTTPException(402,'本张星盘的免费本命解读已使用；可调阅历史报告' if product=='natal' else '请先购买对应服务或兑换体验码')
  key=secrets.token_urlsafe(24);now=time.time()
  db.execute('INSERT INTO credit_uses(id,owner,product,grant_id,state,created,task_ref,report_ref,updated) VALUES (?,?,?,?,?,?,?,?,?)',(key,owner,product,row[0],'reserved',now,task_ref,report_ref,now))
 return key

def complete(store,key,token,value,task_ref=None,report_ref=None):
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  if db.execute("UPDATE credit_uses SET state='consumed',task_ref=COALESCE(?,task_ref),report_ref=COALESCE(?,report_ref),updated=? WHERE id=? AND state='reserved'",(task_ref,report_ref,time.time(),key)).rowcount!=1:raise HTTPException(409,'额度状态已变化，请重新查看账号权益')
  store.save(token,value,database=db)

def release(store,key):
 with store.connect() as db:db.execute("UPDATE credit_uses SET state='released',updated=? WHERE id=? AND state='reserved'",(time.time(),key))

def history(store,owner,limit=100):
 with store.connect() as db:
  rows=db.execute('''SELECT u.id,u.product,u.state,u.created,u.updated,u.task_ref,u.report_ref,g.order_id,g.expires,g.source
   FROM credit_uses u JOIN credit_grants g ON g.id=u.grant_id
   WHERE u.owner=? ORDER BY u.created DESC LIMIT ?''',(owner,max(1,min(int(limit),200)))).fetchall()
 return [{'id':row[0],'product':row[1],'state':row[2],'created':row[3],'updated':row[4] or row[3],
  'taskRef':row[5],'reportRef':row[6],'sourceOrderId':row[7],'expiresAt':row[8],
  'source':'order' if row[7] else ('invite' if str(row[9]).startswith('invite:') else 'system')} for row in rows]

def redeem(store,owner,code):
 digest=hashlib.sha256(code.strip().upper().encode()).hexdigest()
 with store.connect() as db:
  db.execute('BEGIN IMMEDIATE')
  row=db.execute('SELECT expires,max_uses,disabled,product FROM invite_codes WHERE digest=?',(digest,)).fetchone()
  if not row or row[2] or (row[0]>0 and row[0]<=time.time()):raise HTTPException(400,'体验码无效、已停用或已过期')
  product=_product_for_code((row[3],))
  if db.execute('SELECT 1 FROM invite_redemptions WHERE digest=? AND owner=?',(digest,owner)).fetchone():return {'redeemed':True,'alreadyRedeemed':True,'product':product}
  if db.execute('SELECT COUNT(*) FROM invite_redemptions WHERE digest=?',(digest,)).fetchone()[0]>=row[1]:raise HTTPException(400,'体验码已被使用')
  db.execute('INSERT INTO invite_redemptions VALUES (?,?,?)',(digest,owner,time.time()))
  source='invite:'+digest+':'+owner
  grant(db,owner,product,source,1)
 return {'redeemed':True,'alreadyRedeemed':False,'product':product}
