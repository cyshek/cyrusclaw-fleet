#!/usr/bin/env python
"""Helper: resolve/unresolve row + append to log."""
import sqlite3, sys, datetime, os
DB = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db'
LOG = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/_linkedin-resolve-20260524.log'

def main():
    mode = sys.argv[1]  # 'resolve' or 'unresolve'
    rid = int(sys.argv[2])
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute('SELECT company, role FROM roles WHERE id=?', (rid,))
    co, title = cur.fetchone()
    ts = datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    if mode == 'resolve':
        url = sys.argv[3]; source_key = sys.argv[4]; tactic = sys.argv[5]; reason = sys.argv[6]
        notes = f'LINKEDIN-RESOLVE 2026-05-24: resolved via tactic{tactic} ({reason}): {url}'
        cur.execute('UPDATE roles SET app_url=?, source_key=?, agent_notes=? WHERE id=?', (url, source_key, notes, rid))
        line = f'{ts} | id={rid} | {co} | {title} | RESOLVED via tactic{tactic}: {url}'
    else:
        reason = sys.argv[3]
        notes = f'LINKEDIN-RESOLVE 2026-05-24: UNRESOLVED ({reason})'
        cur.execute('UPDATE roles SET agent_notes=? WHERE id=?', (notes, rid))
        line = f'{ts} | id={rid} | {co} | {title} | UNRESOLVED ({reason})'
    con.commit(); con.close()
    with open(LOG, 'a') as f:
        f.write(line + '\n')
    print(line)

if __name__ == '__main__':
    main()
