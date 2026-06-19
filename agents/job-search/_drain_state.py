import sqlite3
c = sqlite3.connect('tracker.db')
print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
print('--- status census ---')
for s, n in c.execute("SELECT COALESCE(NULLIF(status,''),'(empty)'), COUNT(*) FROM roles GROUP BY 1 ORDER BY 2 DESC"):
    print('  %-14s %d' % (s, n))
print('--- residential drain set (live state) ---')
ids = [944, 946, 947, 1237, 2549, 2727, 2758, 1434, 891]
ph = ','.join('?' * len(ids))
q = c.execute("SELECT id,company,title,status,response_status,block_reason,app_url FROM roles WHERE id IN (%s) ORDER BY id" % ph, ids)
for rid, co, title, st, ru, br, url in q:
    print('  %s %-16s st=%-9s resp=%-5s | %-32s | %s' % (rid, (co or '')[:16], st or '(empty)', str(ru)[:5], (title or '')[:32], (br or '')[:38]))
    print('        url=%s' % url)
c.close()
