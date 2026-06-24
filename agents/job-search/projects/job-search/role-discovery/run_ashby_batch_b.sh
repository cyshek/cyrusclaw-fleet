#!/usr/bin/env bash
# Ashby residential drain - Batch B
set -euo pipefail

WORKDIR="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
DB="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
CAPSOLVER_API_KEY=$(cat "${WORKDIR}/../.capsolver-key" 2>/dev/null)
export CAPSOLVER_API_KEY ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223"

cd "$WORKDIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="output/drain_ashby_pass7b_${TIMESTAMP}.log"
mkdir -p output

SUBMITTED=0
HARD_RECAPTCHA=0
OTHER_FAIL=0

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

update_db_success() {
  local role_id="$1"
  sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto-residential', applied_on='2026-06-23', prep_status='submitted', response_status='submitted-residential' WHERE id=${role_id};"
  log "DB updated for role_id=${role_id}: submitted"
}

update_db_hard_recaptcha() {
  local role_id="$1"
  sqlite3 "$DB" "UPDATE roles SET status='blocked', block_reason='ashby-hard-recaptcha:RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential' WHERE id=${role_id};"
  log "DB updated for role_id=${role_id}: blocked (hard-recaptcha)"
}

update_status_md() {
  local slug="$1" status_line="$2"
  local statusfile="applications/submitted/${slug}/STATUS.md"
  echo "" >> "$statusfile"
  echo "## Auto-submit result ($(date '+%Y-%m-%d %H:%M:%S'))" >> "$statusfile"
  echo "$status_line" >> "$statusfile"
}

declare -A SLUGS=(
  [otter-8543629002]="3238"
  [polyai-4874048101]="3226"
  [probably-genetic-18b4a05f-1482-4db1-92b1-dd19b4b06ac6]="3273"
  [promise-ac4259d7-1276-440f-b918-851ef3e0faa5]="3258"
  [raft-5996858004]="3333"
  [ramp-cf3516f6-4d6b-4872-831f-c8ef4a3078ee]="3110"
  [rillet-a182464e-76c1-4f0b-af78-76ba8a611281]="1427"
  [sentilink-a63dcae1-7f42-498b-8845-e2bf5820bbe6]="2330"
  [sentry-2cdc2ba7-8406-452a-b84f-d94d8e7a09bb]="3170"
  [sesame-f54a7538-34d3-4572-90ad-e9867c36461c]="3330"
  [sigma-computing-7776721003]="3162"
  [skydio-f1554474-0c49-49f3-9847-33f52238fc4a]="3223"
  [snowflake-86570858-e425-4144-9aef-8838cefd18c3]="3251"
  [snowflake-9cf335c9-f99d-4ddb-b307-0dcd3a162a09]="3252"
  [solace-6f9534b6-1a96-4d4c-9434-0db094d0e87d]="3243"
  [solva-bd13a1e4-6ec2-4b16-a34d-259e6ea4c9e6]="3395"
  [spoton-e98aef00-2fad-40c1-b0f7-b09a2bc9f47d]="3323"
  [stytch-034cefe3-df7c-4297-9dd2-bb6c0eeb0824]="3365"
  [substack-cf626dcf-0c76-4ad5-a738-3fbc72e4da06]="3174"
  [synthesia-163816a3-11d0-4f20-b138-6629c73e3886]="1568"
  [tailor-b69e751a-d3ea-426f-8bd7-962116162534]="3389"
  [taktile-e89c4e62-fabf-47e1-95a7-91061b6c0705]="3382"
  [talos-trading-6bfa5c2e-dbd1-4b6a-93b5-3592c264ff40]="3435"
  [talos-trading-9df7b493-c34f-4250-a646-af1b5ebbcc2a]="3434"
  [together-ai-5131941007]="2518"
  [twenty-3486ffc9-bd3e-4229-a649-b321694d9d57]="3247"
  [workos-dc23fd7b-ee4c-4e6a-959a-209b2eab8b17]="3366"
  [writer-07259efd-497e-4fd3-9931-f651ec6128a9]="3185"
  [writer-a1d96909-a580-4fd6-b099-bfc8a8dfa6e3]="3184"
  [zip-d28dc61e-b4fa-4517-b61e-a31bccefddba]="3248"
)

ORDERED_SLUGS=(
  otter-8543629002
  polyai-4874048101
  probably-genetic-18b4a05f-1482-4db1-92b1-dd19b4b06ac6
  promise-ac4259d7-1276-440f-b918-851ef3e0faa5
  raft-5996858004
  ramp-cf3516f6-4d6b-4872-831f-c8ef4a3078ee
  rillet-a182464e-76c1-4f0b-af78-76ba8a611281
  sentilink-a63dcae1-7f42-498b-8845-e2bf5820bbe6
  sentry-2cdc2ba7-8406-452a-b84f-d94d8e7a09bb
  sesame-f54a7538-34d3-4572-90ad-e9867c36461c
  sigma-computing-7776721003
  skydio-f1554474-0c49-49f3-9847-33f52238fc4a
  snowflake-86570858-e425-4144-9aef-8838cefd18c3
  snowflake-9cf335c9-f99d-4ddb-b307-0dcd3a162a09
  solace-6f9534b6-1a96-4d4c-9434-0db094d0e87d
  solva-bd13a1e4-6ec2-4b16-a34d-259e6ea4c9e6
  spoton-e98aef00-2fad-40c1-b0f7-b09a2bc9f47d
  stytch-034cefe3-df7c-4297-9dd2-bb6c0eeb0824
  substack-cf626dcf-0c76-4ad5-a738-3fbc72e4da06
  synthesia-163816a3-11d0-4f20-b138-6629c73e3886
  tailor-b69e751a-d3ea-426f-8bd7-962116162534
  taktile-e89c4e62-fabf-47e1-95a7-91061b6c0705
  talos-trading-6bfa5c2e-dbd1-4b6a-93b5-3592c264ff40
  talos-trading-9df7b493-c34f-4250-a646-af1b5ebbcc2a
  together-ai-5131941007
  twenty-3486ffc9-bd3e-4229-a649-b321694d9d57
  workos-dc23fd7b-ee4c-4e6a-959a-209b2eab8b17
  writer-07259efd-497e-4fd3-9931-f651ec6128a9
  writer-a1d96909-a580-4fd6-b099-bfc8a8dfa6e3
  zip-d28dc61e-b4fa-4517-b61e-a31bccefddba
)

for slug in "${ORDERED_SLUGS[@]}"; do
  role_id="${SLUGS[$slug]}"
  plan="output/inline-plan-${slug}.json"
  
  log "--- START ${slug} (role_id=${role_id}) ---"
  
  if [ ! -f "$plan" ]; then
    log "SKIP ${slug}: plan file missing: ${plan}"
    ((OTHER_FAIL++)) || true
    continue
  fi
  
  # Run the runner with retry on 503/connection-refused
  attempt=1
  while true; do
    set +e
    OUTPUT=$(CAPSOLVER_API_KEY="$CAPSOLVER_API_KEY" ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223" .venv/bin/python3 _ashby_runner.py "$plan" 2>&1)
    EXIT_CODE=$?
    set -e
    
    # Check for 503/connection error and retry once
    if echo "$OUTPUT" | grep -qiE "503|connection.refused|browser.*not.*running|Cannot connect" && [ "$attempt" -eq 1 ]; then
      log "RETRY ${slug}: CDP connection error on attempt 1, waiting 10s..."
      sleep 10
      ((attempt++)) || true
      continue
    fi
    break
  done
  
  log "EXIT_CODE=${EXIT_CODE} for ${slug}"
  echo "$OUTPUT" >> "$LOGFILE"
  
  if [ "$EXIT_CODE" -eq 0 ]; then
    log "SUBMITTED: ${slug}"
    update_db_success "$role_id"
    update_status_md "$slug" "status: SUBMITTED via auto-residential (pass7b)"
    # Update STATUS.md prep_status line
    sed -i 's/^prep_status:.*/prep_status: submitted/' "applications/submitted/${slug}/STATUS.md" 2>/dev/null || true
    ((SUBMITTED++)) || true
  elif echo "$OUTPUT" | grep -q "RECAPTCHA_SCORE_BELOW_THRESHOLD"; then
    log "HARD-RECAPTCHA: ${slug}"
    update_db_hard_recaptcha "$role_id"
    update_status_md "$slug" "status: BLOCKED-HARD-RECAPTCHA (RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential)"
    sed -i 's/^prep_status:.*/prep_status: blocked-hard-recaptcha/' "applications/submitted/${slug}/STATUS.md" 2>/dev/null || true
    ((HARD_RECAPTCHA++)) || true
  else
    log "FAILED (exit=${EXIT_CODE}): ${slug}"
    update_status_md "$slug" "status: FAILED-${EXIT_CODE} (see log)"
    ((OTHER_FAIL++)) || true
  fi
  
  log "--- END ${slug} ---"
  echo "" >> "$LOGFILE"
done

log "=== BATCH B COMPLETE ==="
log "Submitted: ${SUBMITTED}"
log "Hard-recaptcha: ${HARD_RECAPTCHA}"
log "Other-fail: ${OTHER_FAIL}"

# Backfill and render
log "Running _backfill_drain_status.py..."
.venv/bin/python3 _backfill_drain_status.py >> "$LOGFILE" 2>&1 || log "WARNING: _backfill_drain_status.py failed"

log "Running render_xlsx.py..."
.venv/bin/python3 render_xlsx.py >> "$LOGFILE" 2>&1 || log "WARNING: render_xlsx.py failed"

echo ""
echo "=== BATCH B SUMMARY ==="
echo "Submitted:     ${SUBMITTED}"
echo "Hard-recaptcha: ${HARD_RECAPTCHA}"
echo "Other-fail:    ${OTHER_FAIL}"
echo "Log: ${LOGFILE}"
