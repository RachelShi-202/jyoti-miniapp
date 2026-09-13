"""Durable member storage. SQLite remains an explicit development option."""
import os,sqlite3,re
from pathlib import Path
from contextlib import contextmanager

def backend():return os.getenv('JYOTI_STORAGE','sqlite').strip().lower()
# Identifiers are hashes or fixed-format strings; JSON payloads need LONGTEXT.
SCHEMA={
 'users':'id VARCHAR(191) PRIMARY KEY,profile LONGTEXT,chart LONGTEXT,revision VARCHAR(191)',
 'sessions':'hash VARCHAR(191) PRIMARY KEY,uid VARCHAR(191),expires DOUBLE',
 'reports':'uid VARCHAR(191),revision VARCHAR(191),period VARCHAR(191),body LONGTEXT,PRIMARY KEY(uid,revision,period)',
 'activity':'uid VARCHAR(191),day VARCHAR(191),PRIMARY KEY(uid,day)',
 'members':'uid VARCHAR(191) PRIMARY KEY,expires DOUBLE',
 'history':'id VARCHAR(191) PRIMARY KEY,uid VARCHAR(191),created DOUBLE,body LONGTEXT',
}
class Row(dict):
 def __getitem__(self,key):return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
class Result:
 def __init__(self,rows,rowcount):self.rows=rows;self.rowcount=rowcount
 def fetchone(self):return self.rows.pop(0) if self.rows else None
 def fetchall(self):rows=self.rows;self.rows=[];return rows
 def __iter__(self):return iter(self.rows)
class MySQLConnection:
 def __init__(self,conn):self.conn=conn
 def execute(self,sql,params=()):
  # Only the application's fixed SQL subset is accepted; values stay parameters.
  sql=sql.replace('INSERT OR REPLACE INTO','REPLACE INTO').replace('INSERT OR IGNORE INTO','INSERT IGNORE INTO').replace('?','%s')
  with self.conn.cursor() as cur:
   cur.execute(sql,params)
   rows=[Row(row) for row in cur.fetchall()] if cur.description else []
   return Result(rows,cur.rowcount)

def mysql_connect():
 import pymysql
 required=('MYSQL_HOST','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD')
 missing=[k for k in required if not os.getenv(k)]
 if missing:raise RuntimeError('Missing database settings: '+','.join(missing))
 options=dict(host=os.environ['MYSQL_HOST'].strip(),port=int(os.getenv('MYSQL_PORT','3306')),user=os.environ['MYSQL_USER'],password=os.environ['MYSQL_PASSWORD'],database=os.environ['MYSQL_DATABASE'],charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,connect_timeout=10,read_timeout=15,write_timeout=15,autocommit=False)
 ca=os.getenv('MYSQL_SSL_CA')
 if ca:options.update(ssl_ca=ca,ssl_verify_cert=True,ssl_verify_identity=True)
 return pymysql.connect(**options)

@contextmanager
def database(sqlite_path):
 kind=backend()
 if kind=='mysql':
  raw=mysql_connect();conn=MySQLConnection(raw)
 elif kind=='sqlite':
  Path(sqlite_path).parent.mkdir(parents=True,exist_ok=True)
  raw=sqlite3.connect(sqlite_path,timeout=10);raw.row_factory=sqlite3.Row
  raw.execute('PRAGMA secure_delete=ON');raw.execute('BEGIN IMMEDIATE');conn=raw
 else:raise RuntimeError('JYOTI_STORAGE must be sqlite or mysql')
 try:
  yield conn
  raw.commit()
 except Exception:
  raw.rollback();raise
 finally:raw.close()

def initialize(sqlite_path):
 with database(sqlite_path) as c:
  for table,columns in SCHEMA.items():
   suffix=' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin' if backend()=='mysql' else ''
   c.execute(f'CREATE TABLE IF NOT EXISTS {table} ({columns})'+suffix)
