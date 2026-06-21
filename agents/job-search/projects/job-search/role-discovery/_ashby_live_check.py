import sqlite3, requests, re, time
conn=sqlite3.connect('../tracker.db');cur=conn.cursor()
rows=cur.execute("""SELECT id,company,role,app_url FROM roles WHERE prep_status='manual_ready' AND (block_reason IS NULL OR block_reason='') AND (app_url LIKE '%ashbyhq.com%' OR source_key LIKE 'ashby:%') AND status='' ORDER BY id""").fetchall()
conn.close()
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0'})
def parse(u):
    m=re.search(r'ashbyhq\.com/([^/]+)/([0-9a-f-]{30,})', u or '')
    return (m.group(1), m.group(2)) if m else (None,None)
for rid,co,role,url in rows:
    org,jid=parse(url)
    live='?'
    if org and jid:
        try:
            r=S.get(f'https://api.ashbyhq.com/posting-api/job-board/{org}', timeout=8)
            if r.status_code==200:
                ids={j.get('id') for j in r.json().get('jobs',[])}
                live='LIVE' if jid in ids else 'GONE(closed)'
            else:
                live=f'board-{r.status_code}'
        except Exception as e:
            live=f'err:{str(e)[:30]}'
    print(f"{rid:5} | {co[:18]:18} | {live:14} | {org}/{jid[:8] if jid else '?'}")
    time.sleep(0.3)
