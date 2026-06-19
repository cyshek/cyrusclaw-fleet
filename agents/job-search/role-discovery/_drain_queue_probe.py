import sqlite3
c = sqlite3.connect('../tracker.db')
HARD = {891, 944, 946, 947, 1237, 2549}
rows = c.execute("SELECT id,company,role,app_url FROM roles WHERE prep_status='manual_ready'").fetchall()

def is_fde(role):
    r = (role or '').lower()
    return 'forward deployed' in r or r.strip() == 'fde'

q = []
for rid, co, role, url in rows:
    if 'ashby' not in (url or '').lower():
        continue
    if rid in HARD:
        continue
    if (co or '').lower() == 'openai':
        continue
    if is_fde(role):
        continue
    q.append((rid, co, role))

print('DRAIN QUEUE (target Ashby, residential path):', len(q))
print('IDS:', ','.join(str(r[0]) for r in q))
print('---')
for rid, co, role in q:
    print('%5d | %-20s | %s' % (rid, (co or '')[:20], (role or '')[:42]))
