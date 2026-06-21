#!/usr/bin/env bash
# daily_apply.sh — drain the open queue every day at 8am PDT
# Runs inline_submit.py --batch 200 (all ATS types) and re-renders XLSX.
# Separate from the Mon/Thu full crawl so the queue drains continuously.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/.venv/bin/python"
LOG="$SCRIPT_DIR/output/daily_apply.log"
mkdir -p "$SCRIPT_DIR/output"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Daily apply run start ==="

APPLY_OUT=$($PY "$SCRIPT_DIR/inline_submit.py" --batch 200 2>&1)
APPLY_RC=$?
echo "$APPLY_OUT" >> "$LOG"

APPLY_OK=$(echo "$APPLY_OUT" | grep -c '"ok": true' 2>/dev/null || echo 0)
log "Submitted: $APPLY_OK (exit $APPLY_RC)"

$PY "$SCRIPT_DIR/render_xlsx.py" 2>&1 | grep -E 'Wrote:|Applied:|Open:' | tee -a "$LOG"

log "=== Daily apply run done ==="
