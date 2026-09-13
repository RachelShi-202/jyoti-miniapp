"""Offline SQLite -> MySQL copy. Defaults to read-only planning, never deletes source."""
import argparse,sqlite3,os
from pathlib import Path
import storage
TABLES=tuple(storage.SCHEMA)
def migrate(source,apply=False):
 if not Path(source).is_file():raise ValueError('SQLite source does not exist')
 if storage.backend()!='mysql':raise ValueError('Configure JYOTI_STORAGE=mysql for the destination')
 src=sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True);src.row_factory=sqlite3.Row
 try:
  data={t:[dict(r) for r in src.execute('SELECT * FROM '+t)] for t in TABLES}
  counts={t:len(rows) for t,rows in data.items()}
  if not apply:return counts
  storage.initialize('unused')
  with storage.database('unused') as dst:
   if any(dst.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in TABLES):
    raise ValueError('Destination must be empty; existing records will not be overwritten')
   for table,rows in data.items():
    for row in rows:
     columns=','.join(row);marks=','.join('?' for _ in row)
     dst.execute(f'INSERT INTO {table} ({columns}) VALUES ({marks})',tuple(row.values()))
   for table,n in counts.items():
    if dst.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]!=n:raise ValueError('Migration count verification failed')
  return counts
 finally:src.close()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--apply',action='store_true');a=p.parse_args()
 try:print({'applied':a.apply,'counts':migrate(a.source,a.apply)})
 except Exception as e:raise SystemExit('Migration failed ('+type(e).__name__+'). No credentials or record contents are printed; check source and database settings.')
