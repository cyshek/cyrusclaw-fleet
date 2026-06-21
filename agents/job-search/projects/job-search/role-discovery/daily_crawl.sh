#!/usr/bin/env bash
# daily_crawl.sh — Lightweight daily delta crawl for top-tier companies.
# Runs Tue-Sun at 07:00 PDT (14:00 UTC) via crontab.
# Monday is covered by the full weekly_run.sh sweep.
#
# Crawls only the 46 high-signal companies in daily_companies.json,
# merges new roles into tracker.db, runs the LLM classifier, and reports
# a one-line status to the job-search Discord channel.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Env: source openclaw + workspace .env so API keys are visible ---
if [ -r /home/azureuser/.openclaw/.env ]; then
  set -a; source /home/azureuser/.openclaw/.env; set +a
fi
if [ -r /home/azureuser/.openclaw/agents/job-search/workspace/.env ]; then
  set -a; source /home/azureuser/.openclaw/agents/job-search/workspace/.env; set +a
fi

PY=".venv/bin/python"
LOG="output/daily_runs.log"
NAMES_FILE="daily_companies.json"
TODAY=$(date -u +%Y-%m-%d)

stamp() { date -u '+%Y-%m-%d %H:%M:%S'; }
log()   { echo "$(stamp) $*" | tee -a "$LOG"; }

mkdir -p output

log "=== Daily delta crawl started ==="

# --- 1. Crawl top-tier companies only ---
log "Step 1: Crawling $(python3 -c "import json; d=json.load(open('$NAMES_FILE')); print(len(d))") companies..."
CRAWL_OUT=$($PY run.py --names-file "$NAMES_FILE" --workers 8 2>&1)
CRAWL_RC=$?
echo "$CRAWL_OUT" | tee -a "$LOG" >/dev/null
if [ $CRAWL_RC -ne 0 ]; then
  log "WARN: crawl exited $CRAWL_RC — continuing"
fi
NEW_ROLES=$(echo "$CRAWL_OUT" | grep -oP 'Total qualifying: \K\d+' | tail -1 || echo "?")
log "  Qualifying roles found: $NEW_ROLES"

# --- 2. Merge into tracker.db ---
log "Step 2: Merging into tracker.db..."
MERGE_OUT=$($PY tracker_merger.py 2>&1)
echo "$MERGE_OUT" | tee -a "$LOG" >/dev/null
INSERTED=$(echo "$MERGE_OUT" | grep -oP 'inserted \K\d+' | awk '{s+=$1} END{print s+0}')
log "  Inserted: $INSERTED new roles"

# --- 3. LLM classifier (skips already-classified by default) ---
log "Step 3: LLM JD classifier (unclassified only)..."
LLM_OUT=$($PY jd_llm_classifier.py --limit 200 2>&1)
echo "$LLM_OUT" | tee -a "$LOG" >/dev/null
echo "$LLM_OUT" | grep -E "^LLM classifier:" | tee -a "$LOG"

# --- 4. Report to Discord ---
DISCORD_CHAN="1501827950474166332"
STATUS_MSG="📊 Daily delta crawl ($TODAY): $INSERTED new roles inserted from ${NEW_ROLES} qualifying found across 46 top-tier companies."
command -v openclaw >/dev/null 2>&1 && \
  openclaw message send --channel discord --target "$DISCORD_CHAN" --message "$STATUS_MSG" 2>&1 | sed 's/^/  /' | tee -a "$LOG" || \
  log "  (openclaw message send unavailable — skipping Discord notify)"

log "=== Daily delta crawl done ==="
log ""

# --- 4b. Auto-apply: submit next 30 open roles after each delta crawl ---
log "Step 4b: Auto-apply batch (up to 30 roles)..."
APPLY_OUT=$($PY inline_submit.py --batch 30 2>&1)
APPLY_RC=$?
echo "$APPLY_OUT" | tee -a "$LOG" >/dev/null
APPLY_OK=$(echo "$APPLY_OUT" | grep -c '"ok": true' || echo 0)
APPLY_TOTAL=$(echo "$APPLY_OUT" | grep -oP '"total": \K\d+' | tail -1 || echo 0)
log "  Auto-apply: ${APPLY_OK}/${APPLY_TOTAL} submitted (exit $APPLY_RC)"

# Re-render XLSX after apply
$PY render_xlsx.py 2>&1 | tee -a "$LOG" | grep -E 'Wrote:|Applied:|Open:' | sed 's/^/  /' | tee -a "$LOG" >/dev/null

# Report updated status to Discord
STATUS_MSG="📊 Daily delta crawl ($TODAY): $INSERTED new roles inserted. Auto-applied: ${APPLY_OK}/${APPLY_TOTAL}."
command -v openclaw >/dev/null 2>&1 && \
  openclaw message send --channel discord --target "$DISCORD_CHAN" --message "$STATUS_MSG" 2>&1 | sed 's/^/  /' | tee -a "$LOG" || \
  log "  (openclaw message send unavailable — skipping Discord notify)"

# Step 5: Gmail response tracker removed 2026-06-20 (Cyrus handles interview tracking manually)
