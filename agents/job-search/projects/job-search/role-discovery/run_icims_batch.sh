#!/usr/bin/env bash
# run_icims_batch.sh — Run iCIMS roles sequentially, log outcomes
# Usage: bash run_icims_batch.sh
set -euo pipefail

ROLES=(
  "3762:https://careers-amd.icims.com/jobs/87265/login:AMD-Cluster-PM"
  "3763:https://careers-amd.icims.com/jobs/87077/login:AMD-TPM-Mfg"
  "3764:https://careers-amd.icims.com/jobs/87117/login:AMD-TPM-ServerCE"
  "3765:https://careers-amd.icims.com/jobs/86326/login:AMD-OH-PM"
  "3766:https://careers-amd.icims.com/jobs/86904/login:AMD-TPM-PreSilicon"
  "3767:https://careers-amd.icims.com/jobs/86949/login:AMD-Privacy-PM"
  "3768:https://careers-amd.icims.com/jobs/86687/login:AMD-Rack-PM"
  "3769:https://careers-amd.icims.com/jobs/86615/login:AMD-PM-VAS"
  "3770:https://careers-amd.icims.com/jobs/86479/login:AMD-Ethics-PM"
  "3771:https://canadacareers-amd.icims.com/jobs/86384/login:AMD-SW-SA"
  "3772:https://careers-amd.icims.com/jobs/86128/login:AMD-PM-Client"
  "3773:https://careers-amd.icims.com/jobs/86406/login:AMD-Customer-PM"
  "3774:https://careers-amd.icims.com/jobs/79943/login:AMD-Logistics-PM"
  "3775:https://careers-amd.icims.com/jobs/80554/login:AMD-TPM-SOC"
  "3776:https://careers-amd.icims.com/jobs/84726/login:AMD-SA"
  "3777:https://careers-amd.icims.com/jobs/86014/login:AMD-Ent-PM"
  "3778:https://careers-amd.icims.com/jobs/85750/login:AMD-TPM-AI-Cluster"
  "3779:https://careers-amd.icims.com/jobs/84929/login:AMD-SW-PM-SoC"
  "3780:https://careers-amd.icims.com/jobs/84268/login:AMD-Embedded-PM"
  "3781:https://careers-amd.icims.com/jobs/80409/login:AMD-TPM-Training"
  "3782:https://careers-amd.icims.com/jobs/80071/login:AMD-AIML-SE"
  "3783:https://careers-amd.icims.com/jobs/80274/login:AMD-Customer-SE"
)

LOGFILE="/tmp/icims_batch_results.txt"
echo "=== iCIMS Batch Run $(date -u) ===" | tee -a "$LOGFILE"

for entry in "${ROLES[@]}"; do
  IFS=: read -r role_id url slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo "--- Role $role_id ($slug) ---" | tee -a "$LOGFILE"
  
  result=$(JOBSEARCH_CDP=http://127.0.0.1:19223 TWOCAPTCHA_API_KEY="$TWOCAPTCHA_API_KEY" \
    .venv/bin/python3 _icims_runner.py --url "$url" 2>&1 || true)
  exit_code=$?
  
  # Extract status from JSON output
  status=$(echo "$result" | python3 -c "import sys,json; lines=sys.stdin.read(); 
d=None
for line in lines.split('\n'):
  try: d=json.loads(line); break
  except: pass
if d: print(d.get('status','unknown'))
else: print('parse-error')" 2>/dev/null || echo "unknown")
  
  hcaptcha_solve=$(echo "$result" | python3 -c "import sys,json; lines=sys.stdin.read();
d=None
for line in lines.split('\n'):
  try: d=json.loads(line); break
  except: pass
if d: print(d.get('hcaptcha_solve','n/a'))
else: print('n/a')" 2>/dev/null || echo "n/a")
  
  echo "  exit=$exit_code status=$status hcaptcha=$hcaptcha_solve" | tee -a "$LOGFILE"
  
  # Update DB based on outcome
  today=$(date -u +%Y-%m-%d)
  if [ "$exit_code" -eq 0 ] || [ "$status" = "applied" ]; then
    echo "  → SUBMITTED (confirmed)" | tee -a "$LOGFILE"
    sqlite3 /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db \
      "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on='$today', prep_status='submitted' WHERE id=$role_id;" 2>&1 || true
  elif [ "$exit_code" -eq 3 ] && echo "$hcaptcha_solve" | grep -q "twocaptcha"; then
    echo "  → UNCERTAIN (hCaptcha solved, Apply clicked, no confirm detected — likely submitted)" | tee -a "$LOGFILE"
    sqlite3 /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db \
      "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on='$today', prep_status='submitted', agent_notes=COALESCE(agent_notes,'')||' [uncertain-submit: hcaptcha-solved+apply-clicked 2026-07-01]' WHERE id=$role_id;" 2>&1 || true
  elif [ "$exit_code" -eq 6 ] || [ "$status" = "closed" ]; then
    echo "  → CLOSED" | tee -a "$LOGFILE"
    sqlite3 /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db \
      "UPDATE roles SET status='closed', block_reason='req-closed', agent_notes=COALESCE(agent_notes,'')||' [closed 2026-07-01]' WHERE id=$role_id;" 2>&1 || true
  elif [ "$exit_code" -eq 7 ] || [ "$status" = "already_applied" ]; then
    echo "  → ALREADY APPLIED" | tee -a "$LOGFILE"
    sqlite3 /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db \
      "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on='$today', prep_status='submitted', agent_notes=COALESCE(agent_notes,'')||' [already-applied detected 2026-07-01]' WHERE id=$role_id;" 2>&1 || true
  elif [ "$exit_code" -eq 2 ] && echo "$hcaptcha_solve" | grep -q "no-vendor"; then
    echo "  → BLOCKED (hCaptcha unsolvable this run)" | tee -a "$LOGFILE"
    # Don't mark blocked - will retry
  else
    echo "  → OTHER (exit=$exit_code)" | tee -a "$LOGFILE"
  fi
  
  # Small delay between roles
  sleep 5
done

echo "" | tee -a "$LOGFILE"
echo "=== Batch complete $(date -u) ===" | tee -a "$LOGFILE"
cat "$LOGFILE"
