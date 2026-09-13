import storage
"""Run on the server. Aggregate only; no user identifiers printed."""
import os, sqlite3, json
from datetime import datetime,timezone,timedelta
now=datetime.now(timezone.utc).date()
with storage.database(os.environ.get('JYOTI_DB','./data/jyoti.sqlite3')) as c:
 print(json.dumps({'utcDay':str(now),'DAU':c.execute('SELECT COUNT(DISTINCT uid) FROM activity WHERE day=?',(str(now),)).fetchone()[0],'rolling30DayMAU':c.execute('SELECT COUNT(DISTINCT uid) FROM activity WHERE day BETWEEN ? AND ?',(str(now-timedelta(days=29)),str(now))).fetchone()[0]}))
