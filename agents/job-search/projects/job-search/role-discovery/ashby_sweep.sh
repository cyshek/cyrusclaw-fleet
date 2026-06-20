#!/usr/bin/env bash
# Ashby sweep: for each role id, ensure plan exists (inline_submit), then live-run via _ashby_runner.
# Captures classify result per role. Marks DB only via the runner's authoritative output (we parse + update here).
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
DB=../tracker.db
IDS="$@"
for rid in $IDS; do
  echo "=================== ROLE $rid ==================="
  # find slug -> plan path
  slug=$($PY - "$rid" <<'EOF'
import sys,sqlite3,glob,os
rid=sys.argv[1]
# plan files are inline-plan-<slug>.json; slug embeds the ashby id. Match by role's app_url id.
c=sqlite3.connect('../tracker.db')
url=c.execute("SELECT app_url FROM roles WHERE id=?",(rid,)).fetchone()[0]
c.close()
import re
m=re.search(r'/([0-9a-f-]{36})',url or '')
jid=m.group(1) if m else ''
cands=glob.glob(f'output/inline-plan-*{jid}*.json') if jid else []
print(cands[0] if cands else '')
EOF
)
  if [ -z "$slug" ]; then
    echo "  no plan for $rid; building..."
    timeout 300 $PY inline_submit.py --role-id "$rid" >/tmp/prep-$rid.log 2>&1
    slug=$($PY - "$rid" <<'EOF'
import sys,sqlite3,glob,re
rid=sys.argv[1]
c=sqlite3.connect('../tracker.db');url=c.execute("SELECT app_url FROM roles WHERE id=?",(rid,)).fetchone()[0];c.close()
m=re.search(r'/([0-9a-f-]{36})',url or '');jid=m.group(1) if m else ''
cands=glob.glob(f'output/inline-plan-*{jid}*.json') if jid else []
print(cands[0] if cands else '')
EOF
)
  fi
  if [ -z "$slug" ]; then echo "  PLAN BUILD FAILED for $rid (see /tmp/prep-$rid.log)"; tail -5 /tmp/prep-$rid.log; continue; fi
  echo "  plan: $slug"
  timeout 360 $PY _ashby_runner.py "$slug" >/tmp/run-$rid.json 2>&1
  # extract classify + error
  $PY - "$rid" /tmp/run-$rid.json <<'EOF'
import sys,json,re,sqlite3,datetime
rid=int(sys.argv[1]); fn=sys.argv[2]
raw=open(fn).read()
# the runner prints a JSON object at the end; find last {...}
classify=None;err=None
try:
    # grab from the trailing JSON
    s=raw.rfind('\n{'); 
    obj=json.loads(raw[raw.index('{'):]) if raw.strip().startswith('{') else None
except Exception:
    obj=None
m=re.search(r'"classify":\s*"([^"]+)"',raw)
if m: classify=m.group(1)
me=re.search(r'"error":\s*"([^"]*)"',raw)
if me: err=me.group(1)
print(f"  -> classify={classify} error={(err or '')[:80]}")
c=sqlite3.connect('../tracker.db')
today=datetime.date.today().isoformat()
if classify=='submitted':
    note=f"SUBMITTED {today} ashby-sweep: classify=submitted (on-page success)."
    c.execute("UPDATE roles SET status='applied',applied_by='agent',applied_on=?,agent_notes=? WHERE id=?",(today,note,rid))
    print("     MARKED APPLIED")
elif classify=='spam-flag':
    note=f"BLOCKED {today} ashby-sweep: RECAPTCHA_SCORE_BELOW_THRESHOLD (strict score-gate, proxy-walled)."
    c.execute("UPDATE roles SET status='blocked',agent_notes=? WHERE id=?",(note,rid))
    print("     strict score-gate")
elif classify in ('form-validation','block-message'):
    note=f"ATTEMPTED {today} ashby-sweep: classify={classify} | {(err or '')[:160]}"
    c.execute("UPDATE roles SET status='blocked',agent_notes=? WHERE id=?",(note,rid))
else:
    note=f"ATTEMPTED {today} ashby-sweep: no-classify (see /tmp/run-{rid}.json tail)"
    c.execute("UPDATE roles SET status='blocked',agent_notes=? WHERE id=?",(note,rid))
c.commit();c.close()
EOF
done
echo "=== sweep done ==="