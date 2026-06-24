#!/bin/bash
set -euo pipefail

WORKDIR="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
cd "$WORKDIR"

CAPSOLVER_KEY=$(cat ../.capsolver-key 2>/dev/null)
LOG_FILE="output/drain_ashby_pass8a_$(date +%Y%m%d_%H%M%S).log"
mkdir -p output

SUBMITTED=0
HARD_RECAPTCHA=0
OTHER_FAIL=0

declare -a SLUGS=(
  artie-9ed7587a-0653-4e81-ab50-5136a2516639
  ashby-2fc178fc-fa92-463a-b788-1c66e3f32a00
  boom-b6f53406-66b9-45aa-bcd9-9adbf5436a26
  braintrust-8f7560d2-cfb1-4e3a-92d1-8e24b532d10c
  braintrust-e1bc9095-2460-4cf4-957f-ba076b6cb5ba
  cartesia-d45f51e9-e7eb-42c5-b986-d3b5d50454c5
  clera-a165ab9a-fb5f-4663-914b-9a7a5921966d
  cohere-1fa01a03-9253-4f62-8f10-0fe368b38cb9
  dust-4258daef-22e3-42cf-9de1-54bf500f5801
  duvoai-e2156092-50f1-4181-87fb-9e4bc299dde3
  e2b-a9ddb7bc-9cc7-43d2-8e46-9c8de4666a04
  forge-ca54fd9a-55eb-45ae-ba48-f666747a24e8
  handshake-c91b7ebf-2c69-4d91-809d-a30ea0b9dc18
  harper-a5e08fb7-a266-4aaf-a9df-a58a4787e292
  hyperbound-2781ed68-e7cc-48d8-b10f-1e9dd3c850db
  interface-aebdf0e6-599f-4e0a-b2c4-e19fb7f1d226
  inworld-ai-9aef36c8-55e5-4e05-b3a7-00992ad69647
  kombo-b2fa5229-f320-44a0-be22-edcfb42b024f
  langchain-b8dead31-212a-4b92-82a7-c42df16ae877
  legora-f3c0712a-f8e2-4dc1-8e83-23da7891a1c2
  litellm-c91a9f7c-310b-4ac3-b494-80874bc75568
  mach9-e09c4604-583b-424f-9526-9f62f42439de
  mondaycom-068bbb1e-ea53-46a9-8faf-cb48765ba9c6
  norm-ai-366d4079-4842-469d-a5e0-3cc891a136b4
  notion-10437426-14c8-4c45-8075-67959ce80393
  notion-a6a91521-87cd-41aa-b800-24dc8808d375
)

{
echo "=== Ashby Residential Drain Pass 8A ==="
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Total roles: ${#SLUGS[@]}"
echo ""

for SLUG in "${SLUGS[@]}"; do
  STATUS_FILE="applications/submitted/$SLUG/STATUS.md"
  
  if [ ! -f "$STATUS_FILE" ]; then
    echo "[$SLUG] ERROR: STATUS.md not found, skipping"
    OTHER_FAIL=$((OTHER_FAIL+1))
    continue
  fi
  
  PLAN=$(grep "^plan:" "$STATUS_FILE" | awk '{print $2}')
  ROLE_ID=$(grep "^role_id:" "$STATUS_FILE" | awk '{print $2}')
  
  if [ -z "$PLAN" ] || [ -z "$ROLE_ID" ]; then
    echo "[$SLUG] ERROR: missing plan or role_id in STATUS.md, skipping"
    OTHER_FAIL=$((OTHER_FAIL+1))
    continue
  fi
  
  echo "--- Processing $SLUG (role_id=$ROLE_ID) ---"
  echo "Plan: $PLAN"
  
  # Run the ashby runner
  set +e
  OUTPUT=$(CAPSOLVER_API_KEY="$CAPSOLVER_KEY" ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223" .venv/bin/python3 _ashby_runner.py "$PLAN" 2>&1)
  EXIT_CODE=$?
  set -e
  
  echo "Exit code: $EXIT_CODE"
  echo "Output (last 30 lines):"
  echo "$OUTPUT" | tail -30
  echo ""
  
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  
  if [ $EXIT_CODE -eq 0 ]; then
    echo "[$SLUG] SUBMITTED ✓"
    sed -i "1s|^PREP-READY.*|SUBMITTED — ${NOW}|" "$STATUS_FILE"
    sed -i "2i submitted_by: auto-residential\nconfirmed: true" "$STATUS_FILE"
    sqlite3 ../tracker.db "UPDATE roles SET status='submitted', applied_by='auto-residential', applied_on='2026-06-23', prep_status='submitted', response_status='submitted-residential' WHERE id=$ROLE_ID;"
    SUBMITTED=$((SUBMITTED+1))
  elif echo "$OUTPUT" | grep -q "RECAPTCHA_SCORE_BELOW_THRESHOLD"; then
    echo "[$SLUG] HARD-RECAPTCHA ✗"
    sed -i "1s|^PREP-READY.*|BLOCKED-HARD-RECAPTCHA|" "$STATUS_FILE"
    sqlite3 ../tracker.db "UPDATE roles SET status='blocked', block_reason='ashby-hard-recaptcha:RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential' WHERE id=$ROLE_ID;"
    HARD_RECAPTCHA=$((HARD_RECAPTCHA+1))
  else
    echo "[$SLUG] FAILED (exit $EXIT_CODE) ✗"
    sed -i "1s|^PREP-READY.*|FAILED-${EXIT_CODE}|" "$STATUS_FILE"
    OTHER_FAIL=$((OTHER_FAIL+1))
  fi
  
  echo ""
  # Small delay between roles
  sleep 3
done

echo "=== SUMMARY ==="
echo "Submitted:      $SUBMITTED"
echo "Hard-recaptcha: $HARD_RECAPTCHA"
echo "Other-fail:     $OTHER_FAIL"
echo "Total:          $((SUBMITTED + HARD_RECAPTCHA + OTHER_FAIL))"
echo "Completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

} 2>&1 | tee "$LOG_FILE"

echo ""
echo "Log written to: $LOG_FILE"

# Post-processing
echo "Running backfill drain status..."
.venv/bin/python3 _backfill_drain_status.py

echo "Running render_xlsx..."
.venv/bin/python3 render_xlsx.py

echo "Done."
