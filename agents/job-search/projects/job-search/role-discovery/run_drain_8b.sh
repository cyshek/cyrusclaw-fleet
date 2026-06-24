#!/bin/bash
# Ashby residential drain pass 8B
set -euo pipefail

WORKDIR="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
cd "$WORKDIR"

CAPSOLVER_KEY=$(cat ../.capsolver-key 2>/dev/null | tr -d '\n')
LOG_FILE="output/drain_ashby_pass8b_$(date +%Y%m%d_%H%M%S).log"
mkdir -p output

SUBMITTED=0
HARD_RECAPTCHA=0
OTHER_FAIL=0

declare -a SUBMITTED_LIST=()
declare -a HARD_LIST=()
declare -a FAIL_LIST=()

SLUGS=(
  omni-d42d1f2e-86ce-4d7d-84fc-84e03da25e60
  op-885091c2-2f56-4d46-aa01-efe49a065dee
  opengov-c94cccf1-408c-44da-8f12-7cca6667e583
  ramp-cf3516f6-4d6b-4872-831f-c8ef4a3078ee
  rillet-a182464e-76c1-4f0b-af78-76ba8a611281
  sentilink-a63dcae1-7f42-498b-8845-e2bf5820bbe6
  sentry-2cdc2ba7-8406-452a-b84f-d94d8e7a09bb
  sesame-f54a7538-34d3-4572-90ad-e9867c36461c
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
  twenty-3486ffc9-bd3e-4229-a649-b321694d9d57
  workos-dc23fd7b-ee4c-4e6a-959a-209b2eab8b17
  writer-07259efd-497e-4fd3-9931-f651ec6128a9
  writer-a1d96909-a580-4fd6-b099-bfc8a8dfa6e3
  zip-d28dc61e-b4fa-4517-b61e-a31bccefddba
)

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"
}

log "=== Ashby Residential Drain Pass 8B ==="
log "Total slugs: ${#SLUGS[@]}"

for SLUG in "${SLUGS[@]}"; do
  STATUS_FILE="applications/submitted/$SLUG/STATUS.md"
  
  if [ ! -f "$STATUS_FILE" ]; then
    log "ERROR: STATUS.md not found for $SLUG"
    FAIL_LIST+=("$SLUG:missing-status")
    OTHER_FAIL=$((OTHER_FAIL + 1))
    continue
  fi

  PLAN=$(grep "^plan:" "$STATUS_FILE" | awk '{print $2}')
  ROLE_ID=$(grep "^role_id:" "$STATUS_FILE" | awk '{print $2}')

  if [ -z "$PLAN" ] || [ -z "$ROLE_ID" ]; then
    log "ERROR: Missing plan or role_id for $SLUG"
    FAIL_LIST+=("$SLUG:missing-plan-or-roleid")
    OTHER_FAIL=$((OTHER_FAIL + 1))
    continue
  fi

  log "--- Processing $SLUG (role_id=$ROLE_ID) ---"
  log "Plan: $PLAN"

  # Run the ashby runner, retry once on CDP connection refused
  set +e
  OUTPUT=$(CAPSOLVER_API_KEY="$CAPSOLVER_KEY" ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223" \
    .venv/bin/python3 _ashby_runner.py "$PLAN" 2>&1)
  EXIT_CODE=$?
  set -e

  if echo "$OUTPUT" | grep -q "Connection refused" && [ $EXIT_CODE -ne 0 ]; then
    log "CDP connection refused for $SLUG — waiting 15s and retrying..."
    sleep 15
    set +e
    OUTPUT=$(CAPSOLVER_API_KEY="$CAPSOLVER_KEY" ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223" \
      .venv/bin/python3 _ashby_runner.py "$PLAN" 2>&1)
    EXIT_CODE=$?
    set -e
  fi

  echo "$OUTPUT" >> "$LOG_FILE"
  log "Exit code: $EXIT_CODE for $SLUG"

  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  if [ $EXIT_CODE -eq 0 ]; then
    log "SUBMITTED: $SLUG"
    sed -i "1s|^PREP-READY.*|SUBMITTED — ${NOW}|" "$STATUS_FILE"
    sed -i "2i submitted_by: auto-residential\nconfirmed: true" "$STATUS_FILE"
    sqlite3 ../tracker.db "UPDATE roles SET status='submitted', applied_by='auto-residential', applied_on='2026-06-23', prep_status='submitted', response_status='submitted-residential' WHERE id=$ROLE_ID;"
    SUBMITTED=$((SUBMITTED + 1))
    SUBMITTED_LIST+=("$SLUG")
  elif echo "$OUTPUT" | grep -qi "RECAPTCHA_SCORE_BELOW_THRESHOLD"; then
    log "HARD-RECAPTCHA: $SLUG"
    sed -i "1s|^PREP-READY.*|BLOCKED-HARD-RECAPTCHA|" "$STATUS_FILE"
    sqlite3 ../tracker.db "UPDATE roles SET status='blocked', block_reason='ashby-hard-recaptcha:RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential' WHERE id=$ROLE_ID;"
    HARD_RECAPTCHA=$((HARD_RECAPTCHA + 1))
    HARD_LIST+=("$SLUG")
  else
    log "FAILED (exit=$EXIT_CODE): $SLUG"
    sed -i "1s|^PREP-READY.*|FAILED-${EXIT_CODE}|" "$STATUS_FILE"
    OTHER_FAIL=$((OTHER_FAIL + 1))
    FAIL_LIST+=("$SLUG:exit$EXIT_CODE")
  fi

  log "Completed $SLUG"
done

log ""
log "=== POST-PROCESSING ==="
log "Running _backfill_drain_status.py..."
.venv/bin/python3 _backfill_drain_status.py >> "$LOG_FILE" 2>&1 || log "WARNING: _backfill_drain_status.py failed"

log "Running render_xlsx.py..."
.venv/bin/python3 render_xlsx.py >> "$LOG_FILE" 2>&1 || log "WARNING: render_xlsx.py failed"

log ""
log "=== SUMMARY ==="
log "SUBMITTED: $SUBMITTED"
log "HARD-RECAPTCHA: $HARD_RECAPTCHA"
log "OTHER-FAIL: $OTHER_FAIL"

if [ ${#SUBMITTED_LIST[@]} -gt 0 ]; then
  log "Submitted slugs:"
  for s in "${SUBMITTED_LIST[@]}"; do log "  + $s"; done
fi

if [ ${#HARD_LIST[@]} -gt 0 ]; then
  log "Hard-recaptcha slugs:"
  for s in "${HARD_LIST[@]}"; do log "  ! $s"; done
fi

if [ ${#FAIL_LIST[@]} -gt 0 ]; then
  log "Failed slugs:"
  for s in "${FAIL_LIST[@]}"; do log "  x $s"; done
fi

echo ""
echo "=== FINAL SUMMARY ==="
echo "submitted $SUBMITTED / hard-recaptcha $HARD_RECAPTCHA / other-fail $OTHER_FAIL"
echo "Log: $LOG_FILE"
