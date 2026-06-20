#!/bin/bash
# Prep + submit + mark a single gh_jid careers-page row.
# Usage: _ghjid_one.sh <role_id>
set -o pipefail
RID="$1"
cd "$(dirname "$0")"
echo "===== ROLE $RID : PREP ====="
timeout 600 python3 inline_submit.py --role-id "$RID" 2>&1 | tail -25
PREP=$?
# find the plan path (most recent inline-plan for this role's slug)
SLUG=$(python3 - "$RID" <<'PY'
import sqlite3,sys,re
sys.path.insert(0,'adapters')
from greenhouse_iframe import host_to_gh_slug, extract_gh_jid
c=sqlite3.connect('../tracker.db'); c.row_factory=sqlite3.Row
r=c.execute("SELECT company,app_url,jd_url FROM roles WHERE id=?", (sys.argv[1],)).fetchone()
u=r['app_url'] or r['jd_url']
jid=extract_gh_jid(u)
comp=re.sub(r'[^a-z0-9]+','-',(r['company'] or '').lower()).strip('-')
print(f"{comp}-{jid}")
PY
)
PLAN="output/inline-plan-${SLUG}.json"
echo "PLAN=$PLAN"
if [ ! -f "$PLAN" ]; then
  echo "RESULT $RID: NO-PLAN (prep failed / dryrun-blockers) slug=$SLUG"
  exit 2
fi
echo "===== ROLE $RID : SUBMIT ====="
OUT=$(timeout 400 python3 _gh_submit.py "$PLAN" 2>&1)
echo "$OUT" | tail -30
if echo "$OUT" | grep -q '"status": "SUBMITTED"' && echo "$OUT" | grep -q '"confirmed": true'; then
  python3 mark_applied.py --id "$RID" --method greenhouse-iframe --notes "inline_submit gh_jid careers-page cohort; confirmed=true" 2>&1 | tail -3
  echo "RESULT $RID: SUBMITTED slug=$SLUG"
else
  echo "RESULT $RID: SUBMIT-FAIL slug=$SLUG"
fi
