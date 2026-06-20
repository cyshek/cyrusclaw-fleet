#!/usr/bin/env bash
# _drain_one.sh <ROLE_ID> <UUID>
# Preps + submits one Ashby row on the residential browser. Prints a parseable verdict.
set -uo pipefail
ROLE_ID="$1"; UUID="$2"
cd /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery
source ./_residential_browser.sh >/dev/null 2>&1
EIP=$(curl -s --max-time 15 -x http://127.0.0.1:18901 https://api.ipify.org)
echo "EGRESS=$EIP"
if [ "$EIP" != "82.23.97.223" ]; then echo "VERDICT=$ROLE_ID|ABORT|egress-not-residential:$EIP"; exit 9; fi
# prep (no-head-probe to avoid the long hang; prep still does LLM+pdf ~150s)
echo "--- PREP $ROLE_ID ---"
timeout 220 .venv/bin/python inline_submit.py --role-id "$ROLE_ID" --ats ashby --dry-run --no-head-probe > /tmp/prep_$ROLE_ID.log 2>&1
PREP_RC=$?
PREP_OK=$(grep -c '"ok": true' /tmp/prep_$ROLE_ID.log)
BLOCKERS=$(grep -oE '"blockers": [0-9]+' /tmp/prep_$ROLE_ID.log | head -1)
echo "prep_rc=$PREP_RC prep_ok_lines=$PREP_OK $BLOCKERS"
# locate plan
PLAN=$(ls -t output/inline-plan-*${UUID}*.json 2>/dev/null | head -1)
if [ -z "$PLAN" ]; then echo "VERDICT=$ROLE_ID|PREP-FAIL|no-plan-file (rc=$PREP_RC)"; tail -8 /tmp/prep_$ROLE_ID.log; exit 8; fi
echo "PLAN=$PLAN"
echo "--- SUBMIT $ROLE_ID ---"
JOBSEARCH_CDP="$JOBSEARCH_CDP" ENABLE_CAPSOLVER=1 CAPSOLVER_API_KEY="$CAPSOLVER_API_KEY" timeout 320 .venv/bin/python _ashby_runner.py "$PLAN" > /tmp/sub_$ROLE_ID.log 2>&1
SUB_RC=$?
# parse result
if grep -q 'SUBMIT SUCCESS (server: FormSubmitSuccess' /tmp/sub_$ROLE_ID.log && grep -qE '^  "ok": true' /tmp/sub_$ROLE_ID.log; then
  SOLVE=$(grep -oE '"solve_ms": [0-9]+' /tmp/sub_$ROLE_ID.log | head -1)
  echo "VERDICT=$ROLE_ID|SUBMITTED|FormSubmitSuccess $SOLVE egress=$EIP"
  exit 0
fi
ERRLINE=$(grep -oE '"error": "[^"]*"' /tmp/sub_$ROLE_ID.log | head -1)
CLASS=$(grep -oE '"classify": "[^"]*"' /tmp/sub_$ROLE_ID.log | head -1)
if grep -qiE 'RECAPTCHA_SCORE_BELOW_THRESHOLD|spam-flag' /tmp/sub_$ROLE_ID.log; then
  echo "VERDICT=$ROLE_ID|SCORE-GATE|$ERRLINE $CLASS (sub_rc=$SUB_RC)"
  exit 1
fi
echo "VERDICT=$ROLE_ID|OTHER-FAIL|$ERRLINE $CLASS (sub_rc=$SUB_RC)"
tail -12 /tmp/sub_$ROLE_ID.log
exit 2
