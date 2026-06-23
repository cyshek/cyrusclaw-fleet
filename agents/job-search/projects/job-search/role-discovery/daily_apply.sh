#!/usr/bin/env bash
# daily_apply.sh — drain the open queue every day at midnight PDT
# Phase 1: inline_submit.py --batch 500 (prep all ATS types → writes PREP-READY packets)
# Phase 2: drain_prep_ready.py --limit 200 (actually submit the PREP-READY packets)
# Phase 3: render_xlsx.py (re-render tracker spreadsheet)
#
# NOTE: inline_submit.py is PREP-ONLY (no browser/submit). The submit happens
# in Phase 2 via drain_prep_ready.py which dispatches _ashby_runner.py / _gh_submit.py.

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/.venv/bin/python"
LOG="$SCRIPT_DIR/output/daily_apply.log"
mkdir -p "$SCRIPT_DIR/output"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Daily apply run start ==="

# --- Phase 1: Prep (generate PREP-READY packets for open queue) ---
log "Phase 1: prep batch-500..."
PREP_OUT=$($PY "$SCRIPT_DIR/inline_submit.py" --batch 500 2>&1)
PREP_RC=$?
echo "$PREP_OUT" >> "$LOG"
PREP_OK=$(echo "$PREP_OUT" | grep -c '"ok": true' 2>/dev/null || echo 0)
log "Prep done: ${PREP_OK} prepped (exit ${PREP_RC})"

# --- Phase 2: Submit (drain PREP-READY packets through actual ATS runners) ---
log "Phase 2: drain PREP-READY -> submit (limit 200)..."
DRAIN_OUT=$($PY "$SCRIPT_DIR/drain_prep_ready.py" --limit 200 2>&1)
DRAIN_RC=$?
echo "$DRAIN_OUT" >> "$LOG"
SUBMITTED=$(echo "$DRAIN_OUT" | grep -oP 'Submitted \(\K[0-9]+' | tail -1 || echo 0)
log "Drain done: ${SUBMITTED} submitted (exit ${DRAIN_RC})"

# --- Phase 3: Render XLSX ---
log "Phase 3: render xlsx..."
$PY "$SCRIPT_DIR/render_xlsx.py" 2>&1 | grep -E 'Wrote:|Applied:|Open:|Submitted:' | tee -a "$LOG"

log "=== Daily apply run done (prep=${PREP_OK} submitted=${SUBMITTED}) ==="
