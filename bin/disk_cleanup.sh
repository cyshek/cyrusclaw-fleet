#!/usr/bin/env bash
# disk_cleanup.sh — self-managing disk cleanup for the OpenClaw VM.
# Owner: openclaw-updates agent. Built 2026-06-10 per Cyrus-approved spec.
#
# WHAT IT DOES (in order):
#   1. Prunes SESSION TRANSCRIPTS older than 30 days under agents/*/sessions/
#      (*.jsonl and *.trajectory.jsonl ONLY), skipping anything modified in the
#      last 48h (active-session guard) regardless of the 30-day rule.
#   2. Vacuums the systemd SYSTEM journal to ~50 MB via sudo -n (the --user scope
#      frees 0B here — journal is root-owned at /var/log/journal).
#   3. Clears stale cron .bak / .migrated files older than 14 days in ~/.openclaw/cron/.
#   4. Prints free-space before/after + total reclaimed. Emits an ALERT: line if
#      free space is still < 15% after cleanup (signal to resize the Azure OS disk).
#
# HARD GUARDRAILS:
#   - ONLY touches files under agents/*/sessions/ matching the transcript glob.
#     NEVER workspace/, memory/, MEMORY.md, HANDOFF.md, AGENTS.md, SOUL.md, USER.md,
#     IDENTITY.md, TOOLS.md, BACKLOG.md, or anything outside sessions/.
#   - 30-day age floor + 48h active-session skip are the safety model.
#   - Never recursive-wipes an agent dir; deletes individual matching files only.
#   - NO gateway restart. Scheduler/hot work only.
#
# USAGE:
#   disk_cleanup.sh --dry-run   # list what WOULD be removed + total reclaim, change nothing
#   disk_cleanup.sh             # real run
#
set -uo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]] && DRY_RUN=1

AGENTS_DIR="/home/azureuser/.openclaw/agents"
CRON_DIR="/home/azureuser/.openclaw/cron"
JOURNAL_SIZE="50M"
AGE_DAYS=30          # transcript age floor for pruning
ACTIVE_SKIP_DAYS=2   # never touch anything modified within this many days (48h)
CRON_BAK_AGE_DAYS=14
FREE_PCT_ALERT=15    # alert if free% below this after cleanup
DISK_ALERT_PCT=31   # alert if used% exceeds this (i.e. free < ~20%, ~6GB on 29GB disk)
TOP_CONSUMERS_THRESHOLD_MB=500  # flag any single dir above this size in the report

mountpoint_for() { df --output=target / | tail -1; }
free_pct() { df --output=pcent / | tail -1 | tr -dc '0-9'; }   # USED percent
avail_h()  { df -h --output=avail / | tail -1 | tr -d ' '; }
used_h()   { df -h --output=used / | tail -1 | tr -d ' '; }

human() { numfmt --to=iec --suffix=B "${1:-0}" 2>/dev/null || echo "${1:-0}B"; }

echo "=================================================================="
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DISK CLEANUP — DRY RUN (no changes will be made)"
else
  echo "DISK CLEANUP — LIVE RUN"
fi
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=================================================================="

# ---- BEFORE snapshot ----
USED_PCT_BEFORE=$(free_pct)
FREE_PCT_BEFORE=$((100 - USED_PCT_BEFORE))
echo
echo "BEFORE: / is ${USED_PCT_BEFORE}% used, $(avail_h) free (${FREE_PCT_BEFORE}% free)"
df -h / | sed 's/^/  /'

TOTAL_RECLAIM=0

# ===================================================================
# 1. SESSION TRANSCRIPT PRUNE
# ===================================================================
echo
echo "------------------------------------------------------------------"
echo "[1] SESSION TRANSCRIPTS  (>${AGE_DAYS}d old, skip <${ACTIVE_SKIP_DAYS}d active)"
echo "    scope: ${AGENTS_DIR}/*/sessions/  glob: *.jsonl, *.trajectory.jsonl"
echo "------------------------------------------------------------------"

# Build the candidate list with the HARD guardrails:
#  - must be under a */sessions/ path
#  - name matches *.jsonl OR *.trajectory.jsonl
#  - mtime older than AGE_DAYS
#  - NOT modified within ACTIVE_SKIP_DAYS (active guard)
#  - belt-and-suspenders: exclude any path containing /workspace/ or /memory/
mapfile -d '' CANDIDATES < <(
  find "${AGENTS_DIR}"/*/sessions/ \
       -type f \
       \( -name '*.jsonl' -o -name '*.trajectory.jsonl' \) \
       -mtime +"${AGE_DAYS}" \
       ! -newermt "-${ACTIVE_SKIP_DAYS} days" \
       -print0 2>/dev/null
)

PRUNE_COUNT=0
PRUNE_BYTES=0
declare -a SAFE_LIST=()
for f in "${CANDIDATES[@]}"; do
  [[ -z "$f" ]] && continue
  # Belt-and-suspenders guard: refuse anything that smells like a protected path.
  case "$f" in
    */workspace/*|*/memory/*|*MEMORY.md|*HANDOFF.md|*AGENTS.md|*SOUL.md|*USER.md|*IDENTITY.md|*TOOLS.md|*BACKLOG.md)
      echo "  !! SKIP (protected pattern, should not match): $f"
      continue ;;
  esac
  # Must literally be inside a /sessions/ directory.
  [[ "$f" == */sessions/* ]] || { echo "  !! SKIP (not in sessions dir): $f"; continue; }
  sz=$(stat -c '%s' "$f" 2>/dev/null || echo 0)
  SAFE_LIST+=("$f")
  PRUNE_COUNT=$((PRUNE_COUNT + 1))
  PRUNE_BYTES=$((PRUNE_BYTES + sz))
done

if [[ $PRUNE_COUNT -eq 0 ]]; then
  echo "  Nothing to prune (no transcripts older than ${AGE_DAYS}d outside the ${ACTIVE_SKIP_DAYS}d active window)."
else
  echo "  ${PRUNE_COUNT} transcript file(s), $(human "$PRUNE_BYTES") total:"
  for f in "${SAFE_LIST[@]}"; do
    printf '    %s  %s\n' "$(date -r "$f" '+%Y-%m-%d')" "$f"
  done
  if [[ $DRY_RUN -eq 0 ]]; then
    DELETED=0
    for f in "${SAFE_LIST[@]}"; do
      if rm -f -- "$f" 2>/dev/null; then DELETED=$((DELETED+1)); else echo "    ERROR removing: $f"; fi
    done
    echo "  -> deleted ${DELETED}/${PRUNE_COUNT} files, reclaimed ~$(human "$PRUNE_BYTES")"
    TOTAL_RECLAIM=$((TOTAL_RECLAIM + PRUNE_BYTES))
  else
    echo "  -> DRY RUN: would delete ${PRUNE_COUNT} files, reclaim ~$(human "$PRUNE_BYTES")"
  fi
fi

# ===================================================================
# 2. SYSTEMD USER JOURNAL VACUUM
# ===================================================================
echo
echo "------------------------------------------------------------------"
echo "[2] SYSTEMD JOURNAL  (vacuum system journal to ${JOURNAL_SIZE})"
echo "------------------------------------------------------------------"
# NOTE: on this box the journal lives at /var/log/journal (root/systemd-journal
# owned). `journalctl --user --vacuum-size` runs but frees 0B (Permission denied),
# so we vacuum the SYSTEM journal with passwordless sudo (sudo -n), which is the
# equivalent that actually reclaims space here. Verified 2026-06-10: freed 368M.
jrnl_usage() { journalctl --disk-usage 2>/dev/null | grep -oiE 'take up [0-9.]+ ?[KMGT]?B?' | grep -oiE '[0-9.]+ ?[KMGT]?B?' | tail -1 || echo "?"; }
JRNL_BEFORE=$(jrnl_usage)
echo "  system journal usage before: ${JRNL_BEFORE}"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "  -> DRY RUN: would run: sudo -n journalctl --vacuum-size=${JOURNAL_SIZE}"
else
  if sudo -n journalctl --vacuum-size="${JOURNAL_SIZE}" 2>&1 | tail -3 | sed 's/^/    /'; then
    JRNL_AFTER=$(jrnl_usage)
    echo "  -> system journal usage after: ${JRNL_AFTER}"
  else
    echo "  -> journal vacuum returned non-zero (non-fatal; check sudo -n availability)"
  fi
fi

# ===================================================================
# 3. STALE CRON BACKUP FILES
# ===================================================================
echo
echo "------------------------------------------------------------------"
echo "[3] STALE CRON BACKUPS  (>${CRON_BAK_AGE_DAYS}d old in ${CRON_DIR})"
echo "    glob: jobs.json.bak*, *.migrated"
echo "------------------------------------------------------------------"
mapfile -d '' CRON_STALE < <(
  find "${CRON_DIR}" -maxdepth 1 -type f \
       \( -name 'jobs.json.bak*' -o -name '*.migrated' \) \
       -mtime +"${CRON_BAK_AGE_DAYS}" \
       -print0 2>/dev/null
)
CRON_COUNT=0; CRON_BYTES=0
declare -a CRON_LIST=()
for f in "${CRON_STALE[@]}"; do
  [[ -z "$f" ]] && continue
  sz=$(stat -c '%s' "$f" 2>/dev/null || echo 0)
  CRON_LIST+=("$f"); CRON_COUNT=$((CRON_COUNT+1)); CRON_BYTES=$((CRON_BYTES+sz))
done
if [[ $CRON_COUNT -eq 0 ]]; then
  echo "  Nothing to clear (no .bak/.migrated older than ${CRON_BAK_AGE_DAYS}d)."
else
  echo "  ${CRON_COUNT} file(s), $(human "$CRON_BYTES") total:"
  for f in "${CRON_LIST[@]}"; do printf '    %s  %s\n' "$(date -r "$f" '+%Y-%m-%d')" "$f"; done
  if [[ $DRY_RUN -eq 0 ]]; then
    for f in "${CRON_LIST[@]}"; do rm -f -- "$f" 2>/dev/null; done
    echo "  -> cleared ${CRON_COUNT} files, reclaimed ~$(human "$CRON_BYTES")"
    TOTAL_RECLAIM=$((TOTAL_RECLAIM + CRON_BYTES))
  else
    echo "  -> DRY RUN: would clear ${CRON_COUNT} files, reclaim ~$(human "$CRON_BYTES")"
  fi
fi

# ===================================================================
# AFTER snapshot + alert decision
# ===================================================================
echo
echo "------------------------------------------------------------------"
USED_PCT_AFTER=$(free_pct)
FREE_PCT_AFTER=$((100 - USED_PCT_AFTER))
if [[ $DRY_RUN -eq 1 ]]; then
  echo "AFTER (dry-run, unchanged): / is ${USED_PCT_AFTER}% used, $(avail_h) free (${FREE_PCT_AFTER}% free)"
  echo "PROJECTED reclaim if run for real: ~$(human "$((PRUNE_BYTES + CRON_BYTES))")"
else
  echo "AFTER: / is ${USED_PCT_AFTER}% used, $(avail_h) free (${FREE_PCT_AFTER}% free)"
  echo "TOTAL reclaimed this run: ~$(human "$TOTAL_RECLAIM")"
fi
echo "------------------------------------------------------------------"

# ===================================================================
# 4. TOP SPACE CONSUMERS REPORT
# ===================================================================
echo
echo "------------------------------------------------------------------"
echo "[4] TOP SPACE CONSUMERS"
echo "------------------------------------------------------------------"
echo "  Per-agent workspace sizes:"
du -sh /home/azureuser/.openclaw/agents/*/  2>/dev/null | sort -rh | while read -r size dir; do
  agent=$(basename "$dir")
  size_mb=$(du -sm "$dir" 2>/dev/null | cut -f1)
  if [[ $size_mb -ge $TOP_CONSUMERS_THRESHOLD_MB ]]; then
    echo "  ⚠️  ${size}  ${agent}  (above ${TOP_CONSUMERS_THRESHOLD_MB}MB threshold)"
  else
    echo "      ${size}  ${agent}"
  fi
done
echo
echo "  Top-level .openclaw dirs:"
du -sh /home/azureuser/.openclaw/*/  2>/dev/null | sort -rh | head -8 | sed 's/^/      /'

# ===================================================================
# AFTER snapshot + alert decision
# ===================================================================
echo
echo "------------------------------------------------------------------"
USED_PCT_AFTER=$(free_pct)
FREE_PCT_AFTER=$((100 - USED_PCT_AFTER))
if [[ $DRY_RUN -eq 1 ]]; then
  echo "AFTER (dry-run, unchanged): / is ${USED_PCT_AFTER}% used, $(avail_h) free (${FREE_PCT_AFTER}% free)"
  echo "PROJECTED reclaim if run for real: ~$(human "$((PRUNE_BYTES + CRON_BYTES))")"
else
  echo "AFTER: / is ${USED_PCT_AFTER}% used, $(avail_h) free (${FREE_PCT_AFTER}% free)"
  echo "TOTAL reclaimed this run: ~$(human "$TOTAL_RECLAIM")"
fi
echo "------------------------------------------------------------------"

# Alert line (machine-parseable). Uses the AFTER free% for live runs; the current
# free% for dry-runs (dry-run won't have reclaimed anything yet).
CHECK_PCT=$FREE_PCT_AFTER
if [[ $CHECK_PCT -lt $FREE_PCT_ALERT ]]; then
  echo "ALERT: free space ${CHECK_PCT}% is below ${FREE_PCT_ALERT}% even after cleanup. Pruning alone is not keeping up — time to resize the Azure OS disk."
  DISK_ALERT=1
elif [[ $USED_PCT_AFTER -ge $DISK_ALERT_PCT ]]; then
  echo "WARN: disk ${USED_PCT_AFTER}% used (free < 20%). Getting tight — monitor closely."
  DISK_ALERT=1
else
  echo "OK: free space ${CHECK_PCT}% is at/above the ${FREE_PCT_ALERT}% floor. No resize needed."
  DISK_ALERT=0
fi
echo "=================================================================="

# Post summary to Discord if there's anything worth flagging
if [[ $DRY_RUN -eq 0 ]]; then
  DISCORD_CHANNEL="channel:1502552885756432496"
  # Build top consumers summary
  TOP_CONSUMERS=$(du -sh /home/azureuser/.openclaw/agents/*/ 2>/dev/null | sort -rh | head -5 | awk '{print "  " $1 "  " $2}' | sed 's|.*/agents/||')
  if [[ ${DISK_ALERT:-0} -eq 1 ]]; then
    openclaw message send --channel discord --target "$DISCORD_CHANNEL" \
      "⚠️ **Disk alert** — ${USED_PCT_AFTER}% used, $(avail_h) free after cleanup.\n\nTop consumers:\n${TOP_CONSUMERS}\n\nReclaimed: ~$(human "$TOTAL_RECLAIM") this run." 2>/dev/null || true
  fi
fi
