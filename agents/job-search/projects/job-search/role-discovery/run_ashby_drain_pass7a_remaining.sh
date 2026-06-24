#!/usr/bin/env bash
# Ashby residential drain - pass7a (batch A, roles 2-30)
# anrok (role_id 1563) already submitted manually

WORKDIR="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
cd "$WORKDIR"

CAPSOLVER_API_KEY=$(cat ../.capsolver-key 2>/dev/null || echo "")
export CAPSOLVER_API_KEY ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223"

LOGDIR="output"
LOGFILE="$LOGDIR/drain_ashby_pass7a_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOGDIR"

submitted=1  # anrok already submitted
hard_recaptcha=0
other_fail=0
declare -a submitted_list=("anrok-469eea33-473b-461d-9a54-4b74b1922f1d:1563") hard_list fail_list

echo "=== Ashby Residential Drain Pass7a ===" | tee "$LOGFILE"
echo "Start: $(date)" | tee -a "$LOGFILE"
echo "Note: anrok-1563 already submitted in probe run" | tee -a "$LOGFILE"

run_role() {
  local slug="$1"
  local f="applications/submitted/$slug/STATUS.md"

  if [ ! -f "$f" ]; then
    echo "[SKIP] $slug — no STATUS.md" | tee -a "$LOGFILE"
    ((other_fail++)) || true
    fail_list+=("$slug:NO_STATUS_MD")
    return
  fi

  local plan role_id
  plan=$(grep "^plan:" "$f" 2>/dev/null | awk '{print $2}' || echo "")
  role_id=$(grep "^role_id:" "$f" 2>/dev/null | awk '{print $2}' || echo "")

  if [ -z "$plan" ] || [ -z "$role_id" ]; then
    echo "[SKIP] $slug — missing plan or role_id" | tee -a "$LOGFILE"
    ((other_fail++)) || true
    fail_list+=("$slug:MISSING_PLAN_OR_ROLEID")
    return
  fi

  echo "" | tee -a "$LOGFILE"
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') | $slug | role_id=$role_id ===" | tee -a "$LOGFILE"

  set +e
  output=$(CAPSOLVER_API_KEY="$CAPSOLVER_API_KEY" ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:19223" \
    timeout 180 .venv/bin/python3 _ashby_runner.py "$plan" 2>&1)
  exit_code=$?
  set -e

  # Log last 30 lines of output (full output in the detailed section)
  echo "$output" | tail -30 >> "$LOGFILE"
  echo "[EXIT $exit_code] $slug" | tee -a "$LOGFILE"

  if [ $exit_code -eq 0 ]; then
    echo "[SUCCESS] $slug submitted" | tee -a "$LOGFILE"
    ((submitted++)) || true
    submitted_list+=("$slug:$role_id")

    cat >> "$f" << EOMD

## Auto-submitted (pass7a residential)
submitted_on: 2026-06-23
submitted_by: auto-residential
exit_code: 0
EOMD

    sqlite3 ../tracker.db "UPDATE roles SET status='submitted', applied_by='auto-residential', applied_on='2026-06-23', prep_status='submitted', response_status='submitted-residential' WHERE id=$role_id;" 2>>"$LOGFILE" && \
      echo "[DB] Updated role $role_id to submitted" | tee -a "$LOGFILE" || \
      echo "[DB-ERR] Failed to update role $role_id" | tee -a "$LOGFILE"

  elif echo "$output" | grep -q "RECAPTCHA_SCORE_BELOW_THRESHOLD"; then
    echo "[HARD-RECAPTCHA] $slug" | tee -a "$LOGFILE"
    ((hard_recaptcha++)) || true
    hard_list+=("$slug:$role_id")

    cat >> "$f" << EOMD

## Blocked (pass7a residential)
blocked_on: 2026-06-23
block_reason: ashby-hard-recaptcha:RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential
exit_code: $exit_code
EOMD

    sqlite3 ../tracker.db "UPDATE roles SET status='blocked', block_reason='ashby-hard-recaptcha:RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential' WHERE id=$role_id;" 2>>"$LOGFILE" && \
      echo "[DB] Updated role $role_id to hard-recaptcha blocked" | tee -a "$LOGFILE" || \
      echo "[DB-ERR] Failed to update role $role_id" | tee -a "$LOGFILE"

  else
    echo "[FAIL-$exit_code] $slug" | tee -a "$LOGFILE"
    ((other_fail++)) || true
    fail_list+=("$slug:$role_id:exit$exit_code")

    # Detailed output for diagnosis
    echo "--- FULL OUTPUT for $slug ---" >> "$LOGFILE"
    echo "$output" >> "$LOGFILE"
    echo "--- END OUTPUT ---" >> "$LOGFILE"

    cat >> "$f" << EOMD

## Failed (pass7a residential)
failed_on: 2026-06-23
exit_code: $exit_code
EOMD
  fi
}

REMAINING_SLUGS=(
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
  omni-d42d1f2e-86ce-4d7d-84fc-84e03da25e60
  op-885091c2-2f56-4d46-aa01-efe49a065dee
  opengov-c94cccf1-408c-44da-8f12-7cca6667e583
)

for slug in "${REMAINING_SLUGS[@]}"; do
  run_role "$slug"
done

echo "" | tee -a "$LOGFILE"
echo "=== DRAIN COMPLETE $(date) ===" | tee -a "$LOGFILE"
echo "Submitted: $submitted" | tee -a "$LOGFILE"
echo "Hard-recaptcha: $hard_recaptcha" | tee -a "$LOGFILE"
echo "Other-fail: $other_fail" | tee -a "$LOGFILE"

if [ ${#submitted_list[@]} -gt 0 ]; then
  echo "" | tee -a "$LOGFILE"
  echo "SUBMITTED:" | tee -a "$LOGFILE"
  for s in "${submitted_list[@]}"; do echo "  $s" | tee -a "$LOGFILE"; done
fi

if [ ${#hard_list[@]} -gt 0 ]; then
  echo "" | tee -a "$LOGFILE"
  echo "HARD-RECAPTCHA:" | tee -a "$LOGFILE"
  for s in "${hard_list[@]}"; do echo "  $s" | tee -a "$LOGFILE"; done
fi

if [ ${#fail_list[@]} -gt 0 ]; then
  echo "" | tee -a "$LOGFILE"
  echo "OTHER-FAIL:" | tee -a "$LOGFILE"
  for s in "${fail_list[@]}"; do echo "  $s" | tee -a "$LOGFILE"; done
fi

echo "" | tee -a "$LOGFILE"
echo "--- Running _backfill_drain_status.py ---" | tee -a "$LOGFILE"
.venv/bin/python3 _backfill_drain_status.py 2>&1 | tee -a "$LOGFILE" || echo "[WARN] _backfill_drain_status.py exited non-zero" | tee -a "$LOGFILE"

echo "--- Running render_xlsx.py ---" | tee -a "$LOGFILE"
.venv/bin/python3 render_xlsx.py 2>&1 | tee -a "$LOGFILE" || echo "[WARN] render_xlsx.py exited non-zero" | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "Log: $LOGFILE"
echo "=== SUMMARY: submitted=$submitted hard_recaptcha=$hard_recaptcha other_fail=$other_fail ==="
