import os,sys,subprocess,json,sqlite3
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import storage,migrate_members

def test_records_and_sessions_survive_process_restart(tmp_path):
 path=tmp_path/'persistent.sqlite3'
 env=dict(os.environ,JYOTI_STORAGE='sqlite',JYOTI_DB=str(path))
 cwd=str(Path(storage.__file__).parent)
 script="""import storage,os
p=os.environ['JYOTI_DB'];storage.initialize(p)
with storage.database(p) as c:
 c.execute('INSERT INTO users(id) VALUES(?)',('member',))
 c.execute('INSERT INTO members VALUES(?,?)',('member',253402300799))
 c.execute('INSERT INTO sessions VALUES(?,?,?)',('hash-only','member',253402300799))
 c.execute('INSERT INTO history VALUES(?,?,?,?)',('history','member',1,'{}'))
"""
 subprocess.run([sys.executable,'-c',script],cwd=cwd,env=env,check=True)
 subprocess.run([sys.executable,'-c',"""import storage,os
with storage.database(os.environ['JYOTI_DB']) as c:
 assert c.execute('SELECT uid FROM sessions WHERE hash=?',('hash-only',)).fetchone()['uid']=='member'
 assert c.execute('SELECT COUNT(*) FROM history WHERE uid=?',('member',)).fetchone()[0]==1
"""],cwd=cwd,env=env,check=True)

def test_sqlite_transaction_rolls_back(tmp_path,monkeypatch):
 monkeypatch.setenv('JYOTI_STORAGE','sqlite');path=str(tmp_path/'db')
 storage.initialize(path)
 with pytest.raises(RuntimeError):
  with storage.database(path) as c:
   c.execute('INSERT INTO users(id) VALUES(?)',('rollback',))
   raise RuntimeError('fail')
 with storage.database(path) as c:assert c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0

def test_mysql_adapter_keeps_values_parameterized():
 seen=[]
 class Cursor:
  description=None;rowcount=1
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def execute(self,sql,params):seen.append((sql,params))
 class Raw:
  def cursor(self):return Cursor()
 c=storage.MySQLConnection(Raw())
 c.execute('INSERT OR REPLACE INTO history VALUES(?,?,?,?)',('id','owner',1,"don't interpolate %s ?"))
 assert seen==[('REPLACE INTO history VALUES(%s,%s,%s,%s)',('id','owner',1,"don't interpolate %s ?"))]

def test_migration_plan_is_read_only(tmp_path,monkeypatch):
 monkeypatch.setenv('JYOTI_STORAGE','sqlite');path=str(tmp_path/'source')
 storage.initialize(path)
 with storage.database(path) as c:c.execute('INSERT INTO users(id) VALUES(?)',('u',))
 before=Path(path).read_bytes()
 monkeypatch.setenv('JYOTI_STORAGE','mysql')
 monkeypatch.setattr(storage,'mysql_connect',lambda:pytest.fail('plan must not connect'))
 assert migrate_members.migrate(path)['users']==1
 assert Path(path).read_bytes()==before

def test_migration_apply_and_existing_target_rejected(tmp_path,monkeypatch):
 from contextlib import contextmanager
 monkeypatch.setenv('JYOTI_STORAGE','sqlite')
 source=str(tmp_path/'source');target=str(tmp_path/'target')
 storage.initialize(source);storage.initialize(target)
 with storage.database(source) as c:
  c.execute('INSERT INTO users(id) VALUES(?)',('member',))
  c.execute('INSERT INTO history VALUES(?,?,?,?)',('id','member',1,'{}'))
 @contextmanager
 def target_db(_):
  c=sqlite3.connect(target);c.row_factory=sqlite3.Row
  try:
   yield c;c.commit()
  except Exception:c.rollback();raise
  finally:c.close()
 monkeypatch.setenv('JYOTI_STORAGE','mysql')
 monkeypatch.setattr(storage,'initialize',lambda _:None)
 monkeypatch.setattr(storage,'database',target_db)
 assert migrate_members.migrate(source,True)['history']==1
 with pytest.raises(ValueError,match='empty'):migrate_members.migrate(source,True)
 with target_db(None) as c:assert c.execute('SELECT COUNT(*) FROM history').fetchone()[0]==1
