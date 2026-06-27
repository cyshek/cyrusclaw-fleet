#!/usr/bin/env python3
import sqlite3, re, json
from pathlib import Path

DB_PATH = '../tracker.db'
OUTPUT_DIR = Path('output')
SUBMITTED_DIR = Path('../applications/submitted')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("""
    SELECT id, company, role, app_url
    FROM roles
    WHERE status='open' AND (app_url LIKE '%ashbyhq%')
    ORDER BY id
""")
rows = [dict(r) for r in c.fetchall()]
conn.close()

ASHBY_RX = re.compile(r'jobs\.ashbyhq\.com/([^/]+)/([0-9a-fA-F-]{36})')

prepped = []
needs_prep = []

for row in rows:
    url = row['app_url'] or ''
    m = ASHBY_RX.search(url)
    if not m:\n        needs_prep.append(row)\n        continue\n    ash_org = m.group(1)\n    ash_jid = m.group(2)\n    # Look for existing plan (exact UUID or first 8 chars)
    plan_exact = OUTPUT_DIR / f"inline-plan-{ash_org}-{ash_jid}.json"
    plan_short = OUTPUT_DIR / f"inline-plan-{ash_org}-{ash_jid[:8]}.json"
    
    found_plan = None
    if plan_exact.exists():
        found_plan = str(plan_exact)
    elif plan_short.exists():
        found_plan = str(plan_short)
    
    if found_plan:
        prepped.append((row, found_plan, ash_org, ash_jid))
        continue
    
    # Check submitted/STATUS.md
    slug_exact = f"{ash_org}-{ash_jid}"
    slug_short = f"{ash_org}-{ash_jid[:8]}"
    already = False
    for slug in [slug_exact, slug_short]:
        p = SUBMITTED_DIR / slug / "STATUS.md"
        if p.exists():
            status = p.read_text()
            if 'SUBMITTED' in status:
                prepped.append((row, f"already-submitted:{slug}", ash_org, ash_jid))
                already = True
                break
    
    if not already:
        needs_prep.append((row, None))

print(f"Roles with existing plans/submitted: {len(prepped)}")
for row, plan, org, jid in prepped[:20]:
    print(f"  {row['id']} {row['company'][:20]} -> {plan[:60]}")

print(f"\nRoles needing prep: {len(needs_prep)}")
for row, _ in needs_prep[:20]:
    url = row['app_url'] or ''
    m = ASHBY_RX.search(url)
    org = m.group(1) if m else '?'
    print(f"  {row['id']} {row['company'][:20]} ({org})")
