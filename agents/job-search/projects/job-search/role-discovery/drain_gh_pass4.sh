#!/bin/bash
# Drain GH Pass 4 — 18 roles
set -euo pipefail

WD="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
DB="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
LOGDIR="$WD/output"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOGDIR/drain_gh_pass4_${TIMESTAMP}.log"
CAPSOLVER_API_KEY=$(cat "$WD/.capsolver-key" 2>/dev/null || echo "")

mkdir -p "$LOGDIR"

SUBMITTED=0
FAILED=0
CLOSED=0
UNCERTAIN=0

declare -A SLUGS=(
  ["addepar-8479674002"]=3298
  ["axon-5414654003"]=3098
  ["axon-6559527003"]=3102
  ["axon-6591183003"]=3103
  ["glean-4591195005"]=2237
  ["instabase-8337459002"]=3431
  ["instabase-8391125002"]=3432
  ["path-robotics-8571384002"]=3479
  ["pure-storage-8004221"]=3290
  ["scale-ai-4699806005"]=3008
  ["scale-ai-4703275005"]=3009
  ["scale-ai-4704555005"]=3007
  ["scopely-5116884008"]=3291
  ["superset-5273586008"]=3284
  ["verkada-4964448007"]=3292
  ["verkada-5167243007"]=3293
  ["yipitdata-7892101"]=2756
  ["zscaler-5162497007"]=3189
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"; }

log "=== GH Drain Pass 4 starting — ${#SLUGS[@]} roles ==="
log "Log: $LOGFILE"

for slug in "${!SLUGS[@]}"; do
  role_id="${SLUGS[$slug]}"
  status_file="$WD/applications/submitted/$slug/STATUS.md"
  plan_file=$(grep "^plan:" "$status_file" 2>/dev/null | awk '{print $2}')
  
  if [[ -z "$plan_file" ]]; then
    log "ERROR: No plan found for $slug"
    continue
  fi
  
  log "--- $slug (role_id=$role_id) ---"
  log "  plan: $plan_file"
  
  # Run the submit
  set +e
  OUTPUT=$(CAPSOLVER_API_KEY="$CAPSOLVER_API_KEY" ENABLE_CAPSOLVER=1 JOBSEARCH_CDP="http://127.0.0.1:18900" \
    "$WD/.venv/bin/python3" "$WD/_gh_submit.py" "$plan_file" 2>&1)
  EXIT_CODE=$?
  set -e
  
  LAST20=$(echo "$OUTPUT" | tail -20)
  log "  exit_code=$EXIT_CODE"
  log "  last_output:"
  echo "$LAST20" | while IFS= read -r line; do log "    $line"; done
  
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  
  if [[ $EXIT_CODE -eq 0 ]]; then
    # Parse confirmed from JSON output
    CONFIRMED=$(echo "$OUTPUT" | grep -oP '"confirmed"\s*:\s*\K(true|false)' | tail -1 || echo "false")
    CLOSED_FLAG=$(echo "$OUTPUT" | grep -oP '"closed"\s*:\s*\K(true|false)' | tail -1 || echo "false")
    
    if [[ "$CONFIRMED" == "true" ]]; then
      log "  ✅ SUBMITTED"
      SUBMITTED=$((SUBMITTED + 1))
      
      # Update STATUS.md
      cat > "$status_file" << EOF
SUBMITTED — $NOW
submitted_by: auto
confirmed: true

role_id: $role_id
slug:    $slug
plan:    $plan_file
EOF
      
      # Update DB
      sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto', applied_on='$(date +%Y-%m-%d)', prep_status='submitted' WHERE id=$role_id;"
      log "  DB updated for role_id=$role_id"
      
    else
      log "  ⚠️  UNCERTAIN (exit 0 but confirmed=false)"
      UNCERTAIN=$((UNCERTAIN + 1))
      echo "UNCERTAIN — $NOW" > "$status_file"
      echo "exit_code: 0" >> "$status_file"
      echo "confirmed: false" >> "$status_file"
      echo "" >> "$status_file"
      echo "role_id: $role_id" >> "$status_file"
      echo "slug:    $slug" >> "$status_file"
      echo "plan:    $plan_file" >> "$status_file"
      echo "" >> "$status_file"
      echo "last_output:" >> "$status_file"
      echo "$LAST20" >> "$status_file"
    fi
    
  else
    # Check for closed/already-applied in output
    if echo "$OUTPUT" | grep -qiE '"closed"\s*:\s*true|job.*not.*found|no longer available|position.*closed|req.*closed'; then
      log "  🔒 CLOSED"
      CLOSED=$((CLOSED + 1))
      echo "CLOSED — $NOW" > "$status_file"
      echo "role_id: $role_id" >> "$status_file"
      echo "slug:    $slug" >> "$status_file"
      sqlite3 "$DB" "UPDATE roles SET status='closed', prep_status='closed' WHERE id=$role_id;" 2>/dev/null || true
    else
      log "  ❌ FAILED (exit=$EXIT_CODE)"
      FAILED=$((FAILED + 1))
      echo "FAILED-$EXIT_CODE — $NOW" > "$status_file"
      echo "exit_code: $EXIT_CODE" >> "$status_file"
      echo "" >> "$status_file"
      echo "role_id: $role_id" >> "$status_file"
      echo "slug:    $slug" >> "$status_file"
      echo "plan:    $plan_file" >> "$status_file"
      echo "" >> "$status_file"
      echo "last_output:" >> "$status_file"
      echo "$LAST20" >> "$status_file"
      
      # Try to get block reason
      BLOCK=$(echo "$OUTPUT" | grep -oP '"reason"\s*:\s*"\K[^"]+' | tail -1 || echo "")
      if [[ -n "$BLOCK" ]]; then
        sqlite3 "$DB" "UPDATE roles SET block_reason='$BLOCK' WHERE id=$role_id;" 2>/dev/null || true
      fi
    fi
  fi
  
  log ""
done

log "=== Running _backfill_drain_status.py ==="
"$WD/.venv/bin/python3" "$WD/_backfill_drain_status.py" 2>&1 | tee -a "$LOGFILE" || log "backfill script not found or errored"

log "=== Running render_xlsx.py ==="
"$WD/.venv/bin/python3" "$WD/render_xlsx.py" 2>&1 | tee -a "$LOGFILE" || log "render_xlsx errored"

log ""
log "=== SUMMARY ==="
log "  SUBMITTED:  $SUBMITTED"
log "  UNCERTAIN:  $UNCERTAIN"
log "  FAILED:     $FAILED"
log "  CLOSED:     $CLOSED"
log "  TOTAL:      $((SUBMITTED + UNCERTAIN + FAILED + CLOSED))"
log ""
log "Full log: $LOGFILE"

echo ""
echo "=== DRAIN PASS 4 COMPLETE ==="
echo "Submitted: $SUBMITTED | Uncertain: $UNCERTAIN | Failed: $FAILED | Closed: $CLOSED"
echo "Log: $LOGFILE"
