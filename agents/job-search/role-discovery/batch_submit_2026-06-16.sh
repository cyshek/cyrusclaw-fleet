#!/bin/bash
# Batch submit script for 2026-06-16 new roles
# Run from role-discovery/ directory

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source ~/.openclaw/.env 2>/dev/null
export JOBSEARCH_CDP="http://127.0.0.1:18800"
export ENABLE_CAPSOLVER=1
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
DB="$SCRIPT_DIR/../tracker.db"
TODAY="2026-06-16"
LOG="$SCRIPT_DIR/batch_submit_$TODAY.log"

# Residential CDP (for strict Ashby cohort)
RESI_CDP="http://127.0.0.1:19223"

submitted=0
blocked=0
skipped=0
failed_resi=()

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

mark_applied() {
  local role_id="$1" slug="$2" method="$3"
  python3 -c "
import sqlite3, sys
db = sqlite3.connect('$DB')
db.execute(\"UPDATE roles SET status='applied', applied_by='$method', applied_on='$TODAY', prep_status='submitted' WHERE id=$role_id\")
db.commit()
print(f'DB updated: role $role_id -> applied')
"
}

prep_role() {
  local role_id="$1"
  log "  [prep] role $role_id"
  # Prep with 5 min timeout (model calls can be slow)
  "$VENV_PY" inline_submit.py --role-id "$role_id" 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}
  return $rc
}

get_slug() {
  local role_id="$1"
  python3 -c "
import sqlite3
db = sqlite3.connect('$DB')
row = db.execute('SELECT source_key, company FROM roles WHERE id=$role_id').fetchone()
if row:
    import re
    sk = row[0] if row[0] else ''
    # extract slug from source_key or app_url
    # source_key IS the url typically; extract org+jid
    m = re.search(r'greenhouse\.io/([^/]+)/jobs/(\d+)', sk)
    if m: print(f'{m.group(1)}-{m.group(2)}'); exit()
    m = re.search(r'ashbyhq\.com/([^/]+)/([0-9a-f-]+)', sk)
    if m: 
        import re as re2
        co = re2.sub(r'[^a-z0-9]+','-', m.group(1).lower()).strip('-')
        jid = m.group(2)
        print(f'{co}-{jid}'); exit()
    m = re.search(r'uber\.com/careers/list/(\d+)', sk)
    if m: print(f'uber-{m.group(1)}'); exit()
    m = re.search(r'myworkdayjobs\.com/[^/]+/job/[^/]+/[^/]+_(REQ-\d+)', sk)
    if m: 
        co = row[1].lower().replace(' ','')
        print(f'{co}-{m.group(1)}'); exit()
print('')
" 2>/dev/null
}

check_plan() {
  local slug="$1"
  local plan="output/inline-plan-${slug}.json"
  if [[ -f "$plan" ]]; then
    echo "$plan"
  else
    echo ""
  fi
}

run_gh_submit() {
  local plan_path="$1" slug="$2"
  log "  [gh_submit] $slug"
  timeout 120 "$VENV_PY" _gh_submit.py "$plan_path" 2>&1 | tee -a "$LOG"
  return ${PIPESTATUS[0]}
}

run_ashby_submit() {
  local plan_path="$1" cdp="$2" slug="$3"
  log "  [ashby] $slug via $cdp"
  JOBSEARCH_CDP="$cdp" timeout 180 "$VENV_PY" _ashby_runner.py "$plan_path" 2>&1 | tee -a "$LOG"
  return ${PIPESTATUS[0]}
}

get_status_file() {
  local slug="$1"
  echo "../applications/submitted/${slug}/STATUS.md"
}

# ----------------------------------------
# Process each role
# ----------------------------------------

process_gh() {
  local role_id="$1"
  log "=== GH role $role_id ==="
  
  prep_role "$role_id"
  local slug
  slug=$(get_slug "$role_id")
  if [[ -z "$slug" ]]; then
    log "  FAIL: could not determine slug for $role_id"
    ((blocked++))
    return
  fi
  
  local status_file
  status_file=$(get_status_file "$slug")
  
  if [[ ! -f "$status_file" ]] || ! grep -q "PREP-READY" "$status_file" 2>/dev/null; then
    log "  BLOCKED: prep failed for $role_id / $slug"
    ((blocked++))
    return
  fi
  
  local plan_path
  plan_path=$(check_plan "$slug")
  if [[ -z "$plan_path" ]]; then
    log "  BLOCKED: no plan for $slug"
    ((blocked++))
    return
  fi
  
  run_gh_submit "$plan_path" "$slug"
  local rc=$?
  
  # Check confirmation
  if grep -qi "confirmation\|submitted\|thank you\|success" "$LOG" 2>/dev/null | tail -5 | grep -qi "confirm\|submit\|success"; then
    log "  SUBMITTED: $slug"
    mark_applied "$role_id" "$slug" "auto"
    ((submitted++))
  else
    # Check STATUS.md for success markers
    local status_content
    status_content=$(cat "$status_file" 2>/dev/null)
    if echo "$status_content" | grep -qi "SUBMITTED\|SUCCESS"; then
      log "  SUBMITTED (from STATUS.md): $slug"
      mark_applied "$role_id" "$slug" "auto"
      ((submitted++))
    else
      log "  BLOCKED/FAILED rc=$rc: $slug"
      ((blocked++))
    fi
  fi
}

process_ashby() {
  local role_id="$1" strict="${2:-0}"
  log "=== ASHBY role $role_id (strict=$strict) ==="
  
  prep_role "$role_id"
  local slug
  slug=$(get_slug "$role_id")
  if [[ -z "$slug" ]]; then
    log "  FAIL: could not determine slug for $role_id"
    ((blocked++))
    return
  fi
  
  local status_file
  status_file=$(get_status_file "$slug")
  
  if [[ ! -f "$status_file" ]] || ! grep -q "PREP-READY" "$status_file" 2>/dev/null; then
    log "  BLOCKED: prep failed for $role_id / $slug"
    ((blocked++))
    return
  fi
  
  local plan_path
  plan_path=$(check_plan "$slug")
  if [[ -z "$plan_path" ]]; then
    log "  BLOCKED: no plan for $slug"
    ((blocked++))
    return
  fi
  
  # Try standard CDP first
  run_ashby_submit "$plan_path" "$JOBSEARCH_CDP" "$slug"
  local rc=$?
  local last_output
  last_output=$(tail -5 "$LOG")
  
  local success=0
  if echo "$last_output" | grep -qi "FormSubmitSuccess\|SUBMITTED\|submitted"; then
    success=1
  fi
  
  # If strict OR failed, try residential
  if [[ $success -eq 0 && ( $strict -eq 1 || $rc -ne 0 ) ]]; then
    log "  Retrying $slug via residential CDP..."
    # Ensure residential browser is up
    source _residential_browser.sh 2>&1 | tee -a "$LOG"
    JOBSEARCH_CDP="$RESI_CDP" timeout 180 "$VENV_PY" _ashby_runner.py "$plan_path" 2>&1 | tee -a "$LOG"
    rc=$?
    last_output=$(tail -5 "$LOG")
    if echo "$last_output" | grep -qi "FormSubmitSuccess\|SUBMITTED\|submitted"; then
      success=1
    fi
  fi
  
  if [[ $success -eq 1 ]]; then
    log "  SUBMITTED: $slug"
    mark_applied "$role_id" "$slug" "auto"
    ((submitted++))
  else
    log "  BLOCKED rc=$rc: $slug"
    if [[ $strict -eq 1 ]]; then
      failed_resi+=("$role_id:$slug")
    fi
    ((blocked++))
  fi
}

log "=== Batch submit 2026-06-16 starting ==="

# Note: The actual processing is done by inline calls below
log "DONE: submitted=$submitted blocked=$blocked skipped=$skipped"
echo "failed_resi: ${failed_resi[*]:-none}"
