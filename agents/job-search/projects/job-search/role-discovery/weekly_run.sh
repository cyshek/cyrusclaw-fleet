#!/usr/bin/env bash
# Weekly role discovery + tracker rollup pipeline (SQLite-backed, 2026-05-11+).
# Runs every Monday at 14:00 UTC via cron.
set -uo pipefail

# --- Env: source /home/azureuser/.openclaw/.env so cron-launched runs see
#     CAPSOLVER_API_KEY / ENABLE_CAPSOLVER (and any other secrets the
#     pipeline relies on). `set -a` exports every var defined in the file.
#     capsolver_client.py also has its own .env fallback, but sourcing here
#     keeps env consistent across every downstream subprocess.
if [ -r /home/azureuser/.openclaw/.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /home/azureuser/.openclaw/.env
  set +a
fi
# Also source workspace .env for BRAVE_SEARCH_API_KEY and other agent-level secrets.
if [ -r /home/azureuser/.openclaw/agents/job-search/workspace/.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /home/azureuser/.openclaw/agents/job-search/workspace/.env
  set +a
fi

RD=/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery
PROJ=/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search
PY="$RD/.venv/bin/python"
LOG="$RD/output/daily_runs.log"
DB="$PROJ/tracker.db"

cd "$RD"

stamp() { date -u '+%Y-%m-%d %H:%M:%S'; }
log()   { echo "$(stamp) $*" | tee -a "$LOG" ; }

log "=== Weekly run started ==="

# --- 1. Crawl ATS adapters ---
log "Step 0: Himalayas net-new company discovery (auto-apply, 2026-06-15)..."
HIM_OUT=$($PY himalayas_discover.py --us-only --max-jobs 3000 --apply 2>&1)
HIM_RC=$?
if [ $HIM_RC -eq 0 ]; then
  HIM_NEW=$(echo "$HIM_OUT" | grep -c 'appended\|Adding' || true)
  log "  Himalayas: done (${HIM_NEW} net-new companies added)"
else
  log "  Himalayas: WARN (exit $HIM_RC) — continuing"
fi

log "Step 1: Crawling..."
$PY run.py --workers 12 2>&1 | tee -a "$LOG" | grep -E "Done|Total qualifying|Wrote" | sed 's/^/  /' | tee -a "$LOG" >/dev/null

# --- 1b. Discovery delta sanity check (>50% per-adapter drop = WARN) ---
log "Step 1b: Delta sanity check..."
DELTA_OUT=$($PY delta_check.py 2>&1)
DELTA_RC=$?
echo "$DELTA_OUT" | tee -a "$LOG" >/dev/null
if [ $DELTA_RC -ne 0 ]; then
  log "WARN: discovery delta anomalies detected — see output/_delta-anomalies-*.md"
  # Best-effort Discord WARN. Channel id is the job-search agent channel.
  ANOMALY_FILE=$(ls -t "$RD/output/_delta-anomalies-"*.md 2>/dev/null | head -1)
  if [ -n "$ANOMALY_FILE" ]; then
    BODY="⚠️ Weekly crawl: per-adapter role count drop >50% detected. See $ANOMALY_FILE"
    # Use openclaw CLI if available, else just log; do not block crawl.
    command -v openclaw >/dev/null 2>&1 && openclaw message send --channel discord --target 1501827950474166332 --message "$BODY" 2>&1 | sed 's/^/  /' | tee -a "$LOG" >/dev/null || true
  fi
fi

# --- 2. Backup tracker.db before merge (rotate to last 14) ---
if [ -f "$DB" ]; then
  BAK="$PROJ/tracker.db.$(date -u +%Y%m%d-%H%M).bak"
  cp "$DB" "$BAK"
  log "Step 2: Backed up tracker.db -> $(basename $BAK)"
  ls -t $PROJ/tracker.db.*.bak 2>/dev/null | tail -n +15 | xargs -r rm -f
fi

# --- 3. Merge new roles into tracker.db ---
log "Step 3: Merging into tracker.db..."
$PY tracker_merger.py 2>&1 | tee -a "$LOG" | grep -E "matched|inserted|backfill|Auto-closed" | sed 's/^/  /' | tee -a "$LOG" >/dev/null

# --- 3a0. LinkedIn-stranded DB cross-link resolver (NEW 2026-06-09) ---
# Cheapest tier, runs FIRST: ZERO network. Many freshly-merged LinkedIn rows are
# for a company+role we ALREADY crawled directly from that company's public ATS
# board (a separate non-LinkedIn row in this same tracker.db). For those we just
# copy the known ATS app_url (no LinkedIn fetch, no HTTP probe -> cannot be rate-
# limited). Only rewrites app_url+agent_notes on an UNAMBIGUOUS same-company+title
# match; preserves the UNIQUE linkedin:<id> source_key; skips MS/Amazon (Cyrus-
# handled). Every row it resolves is one fewer HTTP probe steps 3a/3a2 must make.
log "Step 3a0: LinkedIn-stranded DB cross-link resolver (zero-HTTP, apply)..."
LCL_OUT=$($PY linkedin_db_crosslink_resolver.py --apply --quiet 2>&1)
echo "$LCL_OUT" | tee -a "$LOG" >/dev/null
echo "$LCL_OUT" | grep -E '"resolved"|"ambiguous_or_miss"|"stranded_attempted"' | sed 's/^/  /' | tee -a "$LOG"

# --- 3a. LinkedIn → ATS resolver (one-off ported 2026-05-26) ---
# Replaces linkedin.com app_urls on newly-inserted rows with real ATS URLs so
# the LLM classifier (Step 3b) and downstream auto-apply can pick them up.
# Free-tactic ladder: companies.yaml lookup -> LinkedIn JD scrape -> careers probe.
# Hard cap 900s; writes agent_notes (never cyrus_notes).
log "Step 3a: LinkedIn → ATS resolver pipeline..."
LNR_OUT=$($PY linkedin_resolver_pipeline.py --apply --max-seconds 900 2>&1)
echo "$LNR_OUT" | tee -a "$LOG" >/dev/null
echo "$LNR_OUT" | grep -E '"resolved"|"unresolved"|"attempted"' | sed 's/^/  /' | tee -a "$LOG"

# --- 3a2. LinkedIn ATS resolver v2 (Brave Search fallback, 2026-06-14) ---
# Tactic ladder per row: (1) companies.yaml ATS board API fuzzy-match,
# (2) careers-page scrape, (3) Brave Search API (BRAVE_SEARCH_API_KEY),
# (4) LinkedIn JD scrape. Replaces the old brute resolver.
# Cap at 1800s wall-clock; 1 req/s Brave rate limit respected internally.
log "Step 3a2: LinkedIn ATS resolver v2 (Brave fallback)..."
LBR_OUT=$($PY linkedin_ats_resolver_v2.py --apply --max-seconds 1800 --quiet 2>&1)
echo "$LBR_OUT" | tee -a "$LOG" >/dev/null
echo "$LBR_OUT" | grep -E '"resolved"|"unresolved"|"no_ats"|"errored"|"attempted"|"tactic"' | sed 's/^/  /' | tee -a "$LOG"

# --- 3b. LLM JD classifier on newly-inserted roles (post-merge, pre-render) ---
log "Step 3b: LLM JD classifier..."
LLM_OUT=$($PY jd_llm_classifier.py --limit 500 2>&1)
echo "$LLM_OUT" | tee -a "$LOG" >/dev/null
echo "$LLM_OUT" | grep -E "^LLM classifier:" | tee -a "$LOG"

# --- 4. Render styled XLSX ---
log "Step 4: Rendering XLSX..."
$PY render_xlsx.py 2>&1 | tee -a "$LOG" | sed 's/^/  /' | tee -a "$LOG" >/dev/null

# --- 5. Delta digest (still reads from output/*-roles.json) ---
log "Step 5: Delta digest..."
$PY delta_digest.py 2>&1 | tee -a "$LOG" | grep -E "NEW:|Markdown summary" | sed 's/^/  /' | tee -a "$LOG" >/dev/null

# --- 5b. Email Cyrus newly-discovered REFERRAL-HOLD roles (NEVER apply) ---
# Cyrus 2026-06-01: discover Uber/ByteDance/TikTok but hold for referral. This
# step tailors a resume for each NEW fit and emails him link + HIS referral link
# + PDF (cyshekari@gmail.com), then flags the row `emailed-referral` so it never
# re-sends. Best-effort: email/SMTP issues must NOT fail the weekly run.
log "Step 5b: Referral-hold email (Uber/ByteDance/TikTok)..."
REF_OUT=$($PY email_referral_roles.py 2>&1)
echo "$REF_OUT" | tee -a "$LOG" >/dev/null
echo "$REF_OUT" | grep -E "EMAILED|No new|Nothing|ready:|skip" | sed 's/^/  /' | tee -a "$LOG"

log "=== Weekly run complete ==="
log ""

# --- 6. Auto-apply: submit next 50 open roles across all ATS ---
# Runs immediately after crawl+classify so freshly-discovered roles get submitted
# the same run. Capped at 50 per full-crawl run to stay under rate limits.
log "Step 6: Auto-apply batch (up to 200 roles)..."
APPLY_OUT=$($PY inline_submit.py --batch 200 2>&1)
APPLY_RC=$?
echo "$APPLY_OUT" | tee -a "$LOG" >/dev/null
APPLY_OK=$(echo "$APPLY_OUT" | grep -c '"ok": true' || echo 0)
APPLY_TOTAL=$(echo "$APPLY_OUT" | grep -oP '"total": \K\d+' | tail -1 || echo 0)
log "  Auto-apply: ${APPLY_OK}/${APPLY_TOTAL} submitted (exit $APPLY_RC)"

# Re-render XLSX after apply batch so sheet counts are current
$PY render_xlsx.py 2>&1 | tee -a "$LOG" | grep -E 'Wrote:|Applied:|Open:' | sed 's/^/  /' | tee -a "$LOG" >/dev/null

# Step 6b: Gmail response tracker removed 2026-06-20 (Cyrus handles interview tracking manually)

log "=== Weekly run fully complete ==="
log ""
