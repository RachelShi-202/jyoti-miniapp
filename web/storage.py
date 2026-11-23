"""Private single-process SQLite persistence for the testing deployment."""
import hashlib
import json
import os
import sqlite3
import time
import secrets
from pathlib import Path
from contextlib import nullcontext
import entitlements
import payments

class Store:
 def __init__(self, path):
  self.path=Path(path)
  self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  with self.connect() as db:
   db.execute('PRAGMA journal_mode=WAL')
   db.execute('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)')
   db.execute('INSERT OR IGNORE INTO schema_version VALUES (1)')
   db.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL NOT NULL, updated REAL NOT NULL)')
   db.execute('CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires)')
   columns={row[1] for row in db.execute('PRAGMA table_info(sessions)')}
   for name,kind in [('owner_id','TEXT'),('record_id','TEXT'),('created','REAL')]:
    if name not in columns:db.execute(f'ALTER TABLE sessions ADD COLUMN {name} {kind}')
   db.execute('CREATE TABLE IF NOT EXISTS saved_reports (id TEXT PRIMARY KEY, chart_id TEXT NOT NULL, owner_id TEXT NOT NULL, scope TEXT NOT NULL, kind TEXT NOT NULL, product TEXT NOT NULL, text TEXT NOT NULL, followups TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(chart_id,scope))')
   db.execute('CREATE INDEX IF NOT EXISTS account_charts ON sessions(owner_id,updated)')
   db.execute('CREATE INDEX IF NOT EXISTS account_reports ON saved_reports(owner_id,updated)')
   # Preserve existing account records before the old 30-day cleanup runs.
   for token_hash,payload,updated in db.execute('SELECT token_hash,payload,updated FROM sessions WHERE record_id IS NULL').fetchall():
    value=json.loads(payload);value['recordId']=token_hash;value.setdefault('created',updated)
    if value.get('owner'):value['expires']=253402300799.0
    db.execute('UPDATE sessions SET payload=?,owner_id=?,record_id=?,created=?,expires=? WHERE token_hash=?',(json.dumps(value,ensure_ascii=False),value.get('owner'),token_hash,updated,value['expires'],token_hash))
   db.execute('INSERT OR IGNORE INTO schema_version VALUES (3)')
   for (payload,) in db.execute('SELECT payload FROM sessions WHERE owner_id IS NOT NULL').fetchall():self.archive(db,json.loads(payload),time.time())
   entitlements.initialize(db)
   payments.initialize(db)
  os.chmod(self.path,0o600)
 def connect(self):
  return sqlite3.connect(self.path,timeout=15)
 def save(self, token, value, database=None):
  if value.get("_deleted"):return
  value.setdefault('recordId',secrets.token_urlsafe(24))
  value.setdefault('created',time.time())
  if value.get('owner'):value['expires']=253402300799.0
  now=time.time()
  with (self.connect() if database is None else nullcontext(database)) as db:
   db.execute('INSERT INTO sessions(token_hash,payload,expires,updated,owner_id,record_id,created) VALUES (?,?,?,?,?,?,?) ON CONFLICT(token_hash) DO UPDATE SET payload=excluded.payload, expires=excluded.expires, updated=excluded.updated,owner_id=excluded.owner_id,record_id=excluded.record_id,created=excluded.created',
    (hashlib.sha256(token.encode()).hexdigest(),json.dumps(value,ensure_ascii=False),value['expires'],now,value.get('owner'),value['recordId'],value['created']))
   self.archive(db,value,now)

 def archive(self,db,value,now):
  if value.get('owner'):
   for scope,text in value.get('reports',{}).items():
    if ':round2:' in scope or not isinstance(text,str) or not text.strip():continue
    meta=value.get('reportProducts',{}).get(scope,{})
    db.execute('INSERT INTO saved_reports VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(chart_id,scope) DO UPDATE SET text=excluded.text,followups=excluded.followups,updated=excluded.updated,product=excluded.product',
     (hashlib.sha256((value['recordId']+':'+scope).encode()).hexdigest(),value['recordId'],value['owner'],scope,meta.get('kind',scope.split(':')[0]),meta.get('product','free'),text,json.dumps(value.get('followups',{}).get(scope,[]),ensure_ascii=False),now,now))
 def load(self, token):
  with self.connect() as db:
   row=db.execute('SELECT payload FROM sessions WHERE token_hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
  if not row:return None
  value=json.loads(row[0]);value['busy']=False
  for job in value.get('jobs',{}).values():
   if job.get('state')=='pending':job.update(state='failed',detail='服务已重启，任务中断；请点击原生成按钮重试，本次未收费。')
  self.save(token,value)
  return value
 def cleanup(self):
  with self.connect() as db:db.execute('DELETE FROM sessions WHERE expires<=?',(time.time(),))
 def delete(self,token):
  with self.connect() as db:
   digest=hashlib.sha256(token.encode()).hexdigest()
   row=db.execute('SELECT record_id FROM sessions WHERE token_hash=?',(digest,)).fetchone()
   if row:db.execute('DELETE FROM saved_reports WHERE chart_id=?',(row[0],))
   db.execute('DELETE FROM sessions WHERE token_hash=?',(digest,))

 def delete_account_chart(self,record_id,owner):
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   rows=db.execute('SELECT payload FROM sessions WHERE record_id=? AND owner_id=?',(record_id,owner)).fetchall()
   if not rows:return False
   db.execute('DELETE FROM saved_reports WHERE chart_id=? AND owner_id=?',(record_id,owner))
   db.execute('DELETE FROM sessions WHERE record_id=? AND owner_id=?',(record_id,owner))
  return True

 def delete_account_report(self,report_id,owner):
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   row=db.execute('SELECT chart_id,scope FROM saved_reports WHERE id=? AND owner_id=?',(report_id,owner)).fetchone()
   if not row:return None
   chart_id,scope=row
   rows=db.execute('SELECT token_hash,payload FROM sessions WHERE record_id=? AND owner_id=?',(chart_id,owner)).fetchall()
   for digest,payload in rows:
    value=json.loads(payload)
    self.remove_report(value,scope)
    db.execute('UPDATE sessions SET payload=?,updated=? WHERE token_hash=?',(json.dumps(value,ensure_ascii=False),time.time(),digest))
   db.execute('DELETE FROM saved_reports WHERE id=? AND owner_id=?',(report_id,owner))
  return chart_id,scope

 @staticmethod
 def remove_report(value,scope):
  for field in ('reports','jobs'):
   entries=value.get(field,{})
   for key in list(entries):
    if key==scope or key.startswith(scope+':round2:'):entries.pop(key,None)
  value.get('followups',{}).pop(scope,None)
  value.get('reportProducts',{}).pop(scope,None)
