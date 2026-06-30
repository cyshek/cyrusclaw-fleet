#!/bin/bash
# Run greenhouse_iframe submissions one at a time, logging results
# Usage: ./run_iframe_batch.sh

WORKSPACE="/home/azureuser/.openclaw/agents/job-search/workspace"
ROLE_DIR="$WORKSPACE/projects/job-search/role-discovery"
DB="$WORKSPACE/projects/job-search/tracker.db"
RESULTS="/tmp/gh_drain_results.txt"
LOG="/tmp/iframe_batch.log"

cd "$ROLE_DIR"

# Role ID → slug mapping
declare -A ID_TO_SLUG=(
  [877]="stripe-7815794"
  [3021]="stripe-7975723"
  [3025]="stripe-7377101"
  [3105]="brex-8443298002"
  [3369]="waymo-7922962"
  [3371]="waymo-7902413"
  [3372]="waymo-7917617"
  [3373]="waymo-7939648"
  [3374]="waymo-7403855"
  [3375]="waymo-7733791"
  [3446]="ixl-learning-8444833002"
  [3453]="intersystems-7679435003"
  [3455]="intersystems-7735610003"
  [3456]="intersystems-7735588003"
)

echo "=== IFRAME BATCH SUBMISSION: $(date) ===" | tee -a "$LOG"

for role_id in 877 3021 3025 3105 3369 3371 3372 3373 3374 3375 3446 3453 3455 3456; do
  slug="${ID_TO_SLUG[$role_id]}"
  echo "" | tee -a "$LOG"
  echo "--- Role $role_id: $slug ---" | tee -a "$LOG"
  
  # Run the iframe runner
  timeout 180 .venv/bin/python greenhouse_iframe_runner.py --slug "$slug" 2>&1 | tee /tmp/iframe_result_${role_id}.json
  EXIT=$?
  
  # Parse result
  STATUS=$(python3 -c "import json,sys; d=json.load(open('/tmp/iframe_result_${role_id}.json')); print(d.get('status','UNKNOWN'))" 2>/dev/null || echo "ERROR")
  CONFIRM_URL=$(python3 -c "import json; d=json.load(open('/tmp/iframe_result_${role_id}.json')); print(d.get('confirmation_url', d.get('final_url','')))" 2>/dev/null || echo "")
  
  echo "  Result: $STATUS (exit=$EXIT)" | tee -a "$LOG"
  
  if [ "$STATUS" = "SUBMITTED" ]; then
    echo "  ✅ SUBMITTED: $CONFIRM_URL" | tee -a "$LOG"
    # Update DB
    sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now') WHERE id=$role_id;"
    echo "  DB updated for role $role_id" | tee -a "$LOG"
  else
    echo "  ❌ NOT SUBMITTED: $STATUS" | tee -a "$LOG"
  fi
done

echo "" | tee -a "$LOG"
echo "=== IFRAME BATCH DONE: $(date) ===" | tee -a "$LOG"
