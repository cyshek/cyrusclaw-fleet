#!/bin/bash
# run_gh_drain.sh - Run GH drain for specific PREP-READY roles
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
CAPSOLVER_KEY=$(cat /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.capsolver-key 2>/dev/null || echo "")
LOG_FILE="${1:-output/drain_gh_$(date -u +%Y%m%d_%H%M%S).log}"
TODAY=$(date -u +%Y-%m-%d)

export JOBSEARCH_CDP="http://127.0.0.1:18800"
export ENABLE_CAPSOLVER=1
export CAPSOLVER_API_KEY="$CAPSOLVER_KEY"

cd "$SCRIPT_DIR"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

submitted=0
failed=0
closed=0
SUBMITTED_SLUGS=()
FAILED_SLUGS=()

# GH roles to drain (slug:role_id pairs)
declare -a GH_ROLES=(
    "chime-8530421002:1437"
    "figma-5837760004:1089"
    "figma-6009613004:2344"
    "nice-4847972101:3296"
    "nice-4849399101:3297"
    "otter-8402672002:3239"
    "path-robotics-8571279002:3478"
    "securitize-4173649009:1030"
    "yipitdata-8002296:2974"
    "ziprecruiter-7354406:2409"
)

log "=== GH DRAIN START | $(date -u) ==="
log "CDP: $JOBSEARCH_CDP"
log "Roles: ${#GH_ROLES[@]}"

for entry in "${GH_ROLES[@]}"; do
    slug="${entry%%:*}"
    role_id="${entry##*:}"
    plan="output/inline-plan-${slug}.json"
    status_dir="../../applications/submitted/${slug}"
    status_file="${status_dir}/STATUS.md"

    log ""
    log "=== $slug (role_id=$role_id) ==="

    if [ ! -f "$plan" ]; then
        log "  SKIP: plan missing"
        FAILED_SLUGS+=("$slug:no-plan")
        ((failed++)) || true
        continue
    fi

    log "  Running _gh_submit.py..."
    t0=$(date +%s)
    runner_output=$(.venv/bin/python3 _gh_submit.py "$plan" 2>&1)
    rc=$?
    t1=$(date +%s)
    elapsed=$((t1-t0))
    log "  Exit code: $rc (${elapsed}s)"

    # Check for success patterns
    if echo "$runner_output" | grep -qiE '"confirmed":\s*true|"status":\s*"submitted"'; then
        log "  SUCCESS: confirmed=true"
        # Write SUBMITTED STATUS.md
        mkdir -p "$status_dir"
        runner_tail=$(echo "$runner_output" | tail -20)
        cat > "$status_file" << STATUSEOF
SUBMITTED

submitted_by: auto
applied_on: $TODAY
role_id: $role_id
submitted_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Runner tail:
$runner_tail
STATUSEOF
        # Update DB
        sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto', applied_on='$TODAY', prep_status='submitted' WHERE id=$role_id;"
        log "  DB updated: submitted"
        SUBMITTED_SLUGS+=("$slug")
        ((submitted++)) || true
    elif echo "$runner_output" | grep -qiE '"status":\s*"closed"|no longer open|CLOSED|already_applied|ALREADY_APPLIED'; then
        log "  CLOSED/ALREADY-APPLIED"
        sqlite3 "$DB" "UPDATE roles SET status='closed' WHERE id=$role_id;" 2>/dev/null || true
        ((closed++)) || true
        FAILED_SLUGS+=("$slug:closed")
    elif echo "$runner_output" | grep -qiE '"status":\s*"email_otp"|email-otp|security-input'; then
        log "  BLOCKED: email-OTP gate"
        sqlite3 "$DB" "UPDATE roles SET status='blocked', blocked_reason='email-otp-gate' WHERE id=$role_id;" 2>/dev/null || true
        ((failed++)) || true
        FAILED_SLUGS+=("$slug:email-otp")
    else
        log "  FAILED (non-confirmed): check runner output"
        log "  Last 5 lines: $(echo "$runner_output" | tail -5 | tr '\n' '|')"
        ((failed++)) || true
        FAILED_SLUGS+=("$slug:runner-failed")
    fi

    # Log runner tail to file always
    echo "--- $slug runner output ---" >> "$LOG_FILE"
    echo "$runner_output" | tail -40 >> "$LOG_FILE"
    echo "--- end ---" >> "$LOG_FILE"
done

log ""
log "=== GH DRAIN RESULTS ==="
log "Submitted ($submitted): ${SUBMITTED_SLUGS[*]:-none}"
log "Failed    ($failed): ${FAILED_SLUGS[*]:-none}"
log "Closed    ($closed) roles detected"
log "=== DONE ==="
