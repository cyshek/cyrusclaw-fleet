#!/usr/bin/env bash
# disk_cleanup.sh — monthly workspace pruning for job-search
# Cutoffs (Cyrus 2026-06-15):
#   outputs/proof/                  → 30 days
#   role-discovery/jd_cache/        → 14 days
#   role-discovery/__pycache__/     → always (stale bytecode)
#   applications/submitted/         → 90 days (keep for callback context)
#   sessions/                       → 30 days (distilled into memory/ already)
#
# Safe: never touches MEMORY.md, memory/, AGENTS.md, SOUL.md, IDENTITY.md,
#       USER.md, HANDOFF.md, TOOLS.md, tracker.db, companies.yaml, .venv,
#       or any Python source files.
#
# Usage: bash disk_cleanup.sh [--dry-run]
#        --dry-run  print what would be deleted without deleting anything

set -euo pipefail

WORKSPACE="/home/azureuser/.openclaw/agents/job-search/workspace"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
freed=0

prune() {
    local label="$1" path="$2" days="$3" extra_args="${4:-}"
    if [[ ! -d "$path" ]]; then
        log "SKIP $label — directory not found: $path"
        return
    fi
    log "--- $label (cutoff: ${days}d) ---"
    local before after delta
    before=$(du -sb "$path" 2>/dev/null | awk '{print $1}')
    # shellcheck disable=SC2086
    if [[ $DRY_RUN -eq 1 ]]; then
        find "$path" -mindepth 1 $extra_args -mtime "+${days}" -print | head -20
        local count
        count=$(find "$path" -mindepth 1 $extra_args -mtime "+${days}" | wc -l)
        log "  DRY-RUN: would delete $count items from $path"
    else
        find "$path" -mindepth 1 $extra_args -mtime "+${days}" -delete 2>/dev/null || true
        # Remove empty subdirectories left behind
        find "$path" -mindepth 1 -type d -empty -delete 2>/dev/null || true
        after=$(du -sb "$path" 2>/dev/null | awk '{print $1}')
        delta=$(( before - after ))
        freed=$(( freed + delta ))
        log "  freed $(numfmt --to=iec $delta) (was $(numfmt --to=iec $before), now $(numfmt --to=iec $after))"
    fi
}

prune_files_in_dir() {
    # For flat dirs where each entry is a dated directory (e.g. YYYY-MM-DD-slug/)
    # Deletes whole subdirs older than N days based on mtime of the dir itself
    local label="$1" path="$2" days="$3"
    if [[ ! -d "$path" ]]; then
        log "SKIP $label — directory not found: $path"
        return
    fi
    log "--- $label (cutoff: ${days}d, pruning subdirs) ---"
    local before after delta
    before=$(du -sb "$path" 2>/dev/null | awk '{print $1}')
    if [[ $DRY_RUN -eq 1 ]]; then
        find "$path" -mindepth 1 -maxdepth 1 -type d -mtime "+${days}" | sort | head -20
        local count
        count=$(find "$path" -mindepth 1 -maxdepth 1 -type d -mtime "+${days}" | wc -l)
        log "  DRY-RUN: would delete $count subdirs from $path"
    else
        find "$path" -mindepth 1 -maxdepth 1 -type d -mtime "+${days}" -exec rm -rf {} + 2>/dev/null || true
        after=$(du -sb "$path" 2>/dev/null | awk '{print $1}')
        delta=$(( before - after ))
        freed=$(( freed + delta ))
        log "  freed $(numfmt --to=iec $delta) (was $(numfmt --to=iec $before), now $(numfmt --to=iec $after))"
    fi
}

log "=== job-search disk_cleanup.sh starting ==="
[[ $DRY_RUN -eq 1 ]] && log "*** DRY-RUN MODE — nothing will be deleted ***"

df -h / | tail -1 | awk '{print "[INFO] disk before: used=" $3 " avail=" $4}' || true

# 1. proof screenshots — 30 days
prune_files_in_dir \
    "outputs/proof" \
    "$WORKSPACE/outputs/proof" \
    30

# 2. JD cache — 14 days (job listings expire fast)
prune \
    "role-discovery/jd_cache" \
    "$WORKSPACE/projects/job-search/role-discovery/jd_cache" \
    14

# 3. Python bytecode — always stale, always rebuildable
log "--- __pycache__ (always prune) ---"
if [[ $DRY_RUN -eq 1 ]]; then
    find "$WORKSPACE/projects/job-search/role-discovery" -type d -name "__pycache__" | head -10
    log "  DRY-RUN: would remove all __pycache__ dirs"
else
    before=$(du -sb "$WORKSPACE/projects/job-search/role-discovery/__pycache__" 2>/dev/null | awk '{print $1}' || echo 0)
    find "$WORKSPACE/projects/job-search/role-discovery" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    freed=$(( freed + before ))
    log "  done (approx $(numfmt --to=iec $before) freed)"
fi

# 4. Submitted application artifacts — 90 days
#    Keeps the subdir structure intact for recent roles (callback context)
prune_files_in_dir \
    "applications/submitted" \
    "$WORKSPACE/projects/job-search/applications/submitted" \
    90

# 5. Session transcripts — 30 days (distilled into memory/ by nightly cron)
#    Targets the sessions/ dir if it exists at workspace root or common locations
for sessions_dir in \
    "$WORKSPACE/sessions" \
    "/home/azureuser/.openclaw/sessions/agent:job-search"; do
    if [[ -d "$sessions_dir" ]]; then
        prune "sessions" "$sessions_dir" 30
        break
    fi
done

log "=== cleanup complete ==="
if [[ $DRY_RUN -eq 0 ]]; then
    log "total freed: $(numfmt --to=iec $freed)"
    df -h / | tail -1 | awk '{print "[INFO] disk after: used=" $3 " avail=" $4}'
fi
