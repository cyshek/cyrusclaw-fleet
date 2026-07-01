#!/usr/bin/env bash
# run_amd_batch.sh — Run remaining AMD iCIMS roles sequentially
set -euo pipefail

WORKDIR="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
DB="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
cd "$WORKDIR"

# AMD roles not yet run (3763-3783 minus 3771 Canada)
# 3762 already ran: uncertain, hcaptcha-solved -> treating as submitted
# Start from 3763
ROLES=(
  "3763:https://careers-amd.icims.com/jobs/87077/login"
  "3764:https://careers-amd.icims.com/jobs/87117/login"
  "3765:https://careers-amd.icims.com/jobs/86326/login"
  "3766:https://careers-amd.icims.com/jobs/86904/login"
  "3767:https://careers-amd.icims.com/jobs/86949/login"
  "3768:https://careers-amd.icims.com/jobs/86687/login"
  "3769:https://careers-amd.icims.com/jobs/86615/login"
  "3770:https://careers-amd.icims.com/jobs/86479/login"
  "3771:https://canadacareers-amd.icims.com/jobs/86384/login"
  "3772:https://careers-amd.icims.com/jobs/86128/login"
  "3773:https://careers-amd.icims.com/jobs/86406/login"
  "3774:https://careers-amd.icims.com/jobs/79943/login"
  "3775:https://careers-amd.icims.com/jobs/80554/login"
  "3776:https://careers-amd.icims.com/jobs/84726/login"
  "3777:https://careers-amd.icims.com/jobs/86014/login"
  "3778:https://careers-amd.icims.com/jobs/85750/login"
  "3779:https://careers-amd.icims.com/jobs/84929/login"
  "3780:https://careers-amd.icims.com/jobs/84268/login"
  "3781:https://careers-amd.icims.com/jobs/80409/login"
  "3782:https://careers-amd.icims.com/jobs/80071/login"
  "3783:https://careers-amd.icims.com/jobs/80274/login"
)

LOGFILE="/tmp/amd_icims_results.txt"
TODAY=$(date -u +%Y-%m-%d)
echo "=== AMD iCIMS Batch Run $TODAY $(date -u +%H:%M:%S) ===" | tee "$LOGFILE"

update_db_submitted() {
  local id="$1"
  sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on='$TODAY', prep_status='submitted', agent_notes=COALESCE(agent_notes,'')||' [uncertain-submit: hcaptcha-solved+apply-clicked $TODAY]' WHERE id=$id;" 2>&1 || true
}

update_db_closed() {
  local id="$1"
  sqlite3 "$DB" "UPDATE roles SET status='closed', block_reason='req-closed', agent_notes=COALESCE(agent_notes,'')||' [closed $TODAY]' WHERE id=$id;" 2>&1 || true
}

update_db_already_applied() {
  local id="$1"
  sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on='$TODAY', prep_status='submitted', agent_notes=COALESCE(agent_notes,'')||' [already-applied $TODAY]' WHERE id=$id;" 2>&1 || true
}

write_status_submitted() {
  local id="$1"
  local url="$2"
  local hcap="$3"
  local slug=$(sqlite3 "$DB" "SELECT COALESCE(prep_path,'') FROM roles WHERE id=$id;")
  local company=$(sqlite3 "$DB" "SELECT company FROM roles WHERE id=$id;")
  local role=$(sqlite3 "$DB" "SELECT role FROM roles WHERE id=$id;")
  local dir="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/$(basename "$slug" 2>/dev/null || echo "amd-$id")"
  mkdir -p "$dir"
  cat > "$dir/STATUS.md" << STATEOF
SUBMITTED — $TODAY

role_id: $id
company: $company
role: $role
url: $url
submitted_by: auto-icims (_icims_runner.py)
confirmation: uncertain (hCaptcha solved via 2Captcha, Apply button clicked)
hcaptcha_solve: $hcap
resume_attached: iCIMS profile-apply (no file input)
exit_code: 3
STATEOF
  echo "  STATUS.md written: $dir"
}

for entry in "${ROLES[@]}"; do
  IFS=: read -r role_id url <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo "--- Role $role_id: $url ---" | tee -a "$LOGFILE"
  
  # Run the runner
  set +e
  result=$(JOBSEARCH_CDP=http://127.0.0.1:19223 TWOCAPTCHA_API_KEY="$TWOCAPTCHA_API_KEY" \
    .venv/bin/python3 _icims_runner.py --url "$url" 2>&1)
  exit_code=$?
  set -e
  
  # Parse JSON from last line or search for it
  status=$(echo "$result" | python3 -c "
import sys,json
data = sys.stdin.read()
for line in reversed(data.split('\n')):
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            print(d.get('status','unknown'))
            break
        except: pass
else:
    print('parse-error')
" 2>/dev/null || echo "unknown")

  hcap=$(echo "$result" | python3 -c "
import sys,json
data = sys.stdin.read()
for line in reversed(data.split('\n')):
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            print(d.get('hcaptcha_solve','n/a'))
            break
        except: pass
else:
    print('n/a')
" 2>/dev/null || echo "n/a")
  
  echo "  exit=$exit_code status=$status hcaptcha=$hcap" | tee -a "$LOGFILE"
  echo "  Last output: $(echo "$result" | tail -3 | tr '\n' ' ')" | tee -a "$LOGFILE"
  
  # Book keeping
  if [ "$status" = "applied" ] || [ "$exit_code" -eq 0 ]; then
    echo "  RESULT: SUBMITTED (confirmed)" | tee -a "$LOGFILE"
    update_db_submitted "$role_id"
    write_status_submitted "$role_id" "$url" "$hcap"
  elif [ "$exit_code" -eq 3 ] && echo "$hcap" | grep -q "twocaptcha\|nopecha"; then
    echo "  RESULT: UNCERTAIN-SUBMITTED (hcap solved, Apply clicked)" | tee -a "$LOGFILE"
    update_db_submitted "$role_id"
    write_status_submitted "$role_id" "$url" "$hcap"
  elif [ "$status" = "closed" ] || [ "$exit_code" -eq 6 ]; then
    echo "  RESULT: CLOSED" | tee -a "$LOGFILE"
    update_db_closed "$role_id"
  elif [ "$status" = "already_applied" ] || [ "$exit_code" -eq 7 ]; then
    echo "  RESULT: ALREADY_APPLIED" | tee -a "$LOGFILE"
    update_db_already_applied "$role_id"
  else
    echo "  RESULT: FAILED/BLOCKED (exit=$exit_code, hcap=$hcap)" | tee -a "$LOGFILE"
    echo "$result" | tail -20 | tee -a "$LOGFILE"
  fi
  
  # Brief pause between roles
  sleep 3
done

echo "" | tee -a "$LOGFILE"
echo "=== AMD batch complete $(date -u) ===" | tee -a "$LOGFILE"
cat "$LOGFILE"
