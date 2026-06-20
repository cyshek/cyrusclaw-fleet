import sqlite3, sys, datetime
rid=int(sys.argv[1]); note=sys.argv[2]
c=sqlite3.connect('../tracker.db')
cur=c.execute('SELECT agent_notes FROM roles WHERE id=?',(rid,)).fetchone()
prev=(cur[0] or '') if cur else ''
stamp=f"TRIED 2026-06-09: {note}"
newnotes=(prev+' | '+stamp).strip(' |')
c.execute("UPDATE roles SET status='blocked', agent_notes=? WHERE id=?",(newnotes,rid))
c.commit()
print('tagged:', rid, '| status=blocked')
print('note:', stamp)
print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
