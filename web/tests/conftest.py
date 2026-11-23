import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))


def login_client(client,identity='test-owner@example.com'):
 import app,hashlib,secrets,time
 token=secrets.token_urlsafe(32)
 with app.store.connect() as db:
  user=db.execute('SELECT id FROM users WHERE identity=?',(identity,)).fetchone()
  uid=user[0] if user else secrets.token_urlsafe(24)
  if not user:db.execute('INSERT INTO users VALUES (?,?,?)',(uid,identity,time.time()))
  db.execute('INSERT INTO login_sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,time.time()+3600))
 client.cookies.set('jyoti_login',token)
 return uid
