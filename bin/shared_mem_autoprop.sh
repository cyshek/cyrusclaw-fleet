#!/usr/bin/env bash
# shared_mem_autoprop.sh — auto-propagation for the cross-agent shared-memory corpus.
# Owner: openclaw-updates. Built 2026-06-10 per Cyrus-approved "auto propagation" spec.
#
# TWO JOBS, gated by change-detection so it's near-zero cost when idle:
#
#   PART B (auto-WRITE / curate): promote agent inbox files
#     (shared-memory/_inbox/<agent>.md) into the canonical corpus. Single-writer
#     safety: only THIS script (run by the main-owned curator cron) writes canonical
#     files; agents only ever append to their own inbox file. Secret-scans every line
#     and DROPS anything that looks like a credential. Promoted lines are appended to
#     facts/_inbox_promoted.md (dated, atomic) and the inbox file is truncated.
#
#   PART A (auto-REINDEX): if the shared corpus changed since the last run (hash of
#     all .md mtimes+sizes), reindex all 8 agents (~5s each) so new facts are
#     searchable fleet-wide within the cron interval. If nothing changed, do nothing
#     (no API calls -> embedding cache means idle runs are ~free).
#
# MODES:
#   shared_mem_autoprop.sh            # full run: curate inbox, then reindex-if-changed
#   shared_mem_autoprop.sh --dry-run  # show what WOULD be promoted/reindexed, change nothing
#   shared_mem_autoprop.sh --reindex-only   # skip curation, just reindex-if-changed
#   shared_mem_autoprop.sh --curate-only    # just curate inbox (no reindex)
#
# OUTPUT: prints a STATUS line the cron parses:
#   CHANGED: reindexed N agents (promoted P facts, dropped D)   -> something happened
#   NOCHANGE                                                     -> idle, cron stays silent
#
set -uo pipefail

SHARED="/home/azureuser/.openclaw/shared-memory"
INBOX="${SHARED}/_inbox"
PROMOTED="${SHARED}/facts/_inbox_promoted.md"
STAMP="/home/azureuser/.openclaw/.shared-mem-autoprop.stamp"   # last-seen corpus hash
AGENTS=(interview-prep job-search main making-money openclaw-updates resume-tailor trading-bench travel)

DRY_RUN=0; MODE="full"
case "${1:-}" in
  --dry-run|-n) DRY_RUN=1 ;;
  --reindex-only) MODE="reindex" ;;
  --curate-only) MODE="curate" ;;
esac

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

# Secret scanner: returns 0 (match=IS secret) if a line looks like a credential.
# Conservative — better to drop a borderline line than leak a token.
looks_like_secret() {
  local line="$1"
  # common secret patterns: long hex/base64 blobs, key-ish assignments, known prefixes
  echo "$line" | grep -qiE '(api[_-]?key|secret|password|passwd|token|bearer|authorization|private[_-]?key|client[_-]?secret|access[_-]?key)' && return 0
  echo "$line" | grep -qE '(sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' && return 0
  # long opaque token-looking blob (>=32 chars of base64/hex with no spaces)
  echo "$line" | grep -qE '[A-Za-z0-9+/=_-]{40,}' && ! echo "$line" | grep -qE ' ' && return 0
  return 1
}

# ---- corpus hash (mtime+size of every .md EXCLUDING the inbox, since inbox churn
#       is handled by curation; we want reindex to fire on CANONICAL changes and on
#       freshly-promoted content) ----
corpus_hash() {
  find "${SHARED}" -type f -name '*.md' ! -path "${INBOX}/*" -printf '%p:%T@:%s\n' 2>/dev/null \
    | sort | sha256sum | awk '{print $1}'
}

echo "=================================================================="
echo "SHARED-MEM AUTO-PROP  ($([ $DRY_RUN -eq 1 ] && echo DRY-RUN || echo LIVE), mode=$MODE)  $(ts)"
echo "=================================================================="

PROMOTED_COUNT=0
DROPPED_COUNT=0

# ===================================================================
# PART B — CURATE INBOX (auto-write)
# ===================================================================
if [[ "$MODE" == "full" || "$MODE" == "curate" ]]; then
  echo
  echo "[B] CURATE INBOX -> canonical"
  shopt -s nullglob
  inbox_files=("${INBOX}"/*.md)
  shopt -u nullglob
  any_inbox_content=0
  for inf in "${inbox_files[@]}"; do
    base="$(basename "$inf")"
    [[ "$base" == "README.md" ]] && continue
    # eligible non-empty, non-comment lines
    mapfile -t lines < <(grep -vE '^\s*(#|<!--|$)' "$inf" 2>/dev/null)
    [[ ${#lines[@]} -eq 0 ]] && continue
    any_inbox_content=1
    echo "  ${base}: ${#lines[@]} candidate line(s)"
    declare -a keep=()
    for ln in "${lines[@]}"; do
      [[ -z "${ln// }" ]] && continue
      if looks_like_secret "$ln"; then
        echo "    DROP (secret-like): ${ln:0:60}..."
        DROPPED_COUNT=$((DROPPED_COUNT+1))
        continue
      fi
      # dedupe against already-promoted + canonical files
      needle="$(echo "$ln" | sed 's/^[[:space:]]*-\?[[:space:]]*//' | sed 's/#shared//g' | xargs 2>/dev/null)"
      if [[ -n "$needle" ]] && grep -qiF "$needle" "${PROMOTED}" 2>/dev/null; then
        echo "    SKIP (already promoted): ${ln:0:50}..."
        continue
      fi
      keep+=("$ln")
    done
    if [[ ${#keep[@]} -gt 0 ]]; then
      echo "    -> promote ${#keep[@]} line(s)"
      if [[ $DRY_RUN -eq 0 ]]; then
        {
          echo ""
          echo "### from _inbox/${base} @ $(ts)"
          for k in "${keep[@]}"; do echo "$k"; done
        } >> "${PROMOTED}"
        # truncate the inbox file but keep a dated marker so provenance/debug is clear
        {
          echo "<!-- ${base} inbox: ${#keep[@]} line(s) promoted @ $(ts); cleared -->"
        } > "$inf"
      fi
      PROMOTED_COUNT=$((PROMOTED_COUNT + ${#keep[@]}))
    fi
  done
  [[ $any_inbox_content -eq 0 ]] && echo "  (inbox empty — nothing to curate)"
fi

# ===================================================================
# PART A — REINDEX IF CHANGED
# ===================================================================
REINDEXED=0
if [[ "$MODE" == "full" || "$MODE" == "reindex" ]]; then
  echo
  echo "[A] REINDEX-IF-CHANGED"
  NEWHASH="$(corpus_hash)"
  OLDHASH="$(cat "$STAMP" 2>/dev/null || echo none)"
  echo "  corpus hash: old=${OLDHASH:0:12} new=${NEWHASH:0:12}"
  if [[ "$NEWHASH" == "$OLDHASH" ]]; then
    echo "  -> no corpus change since last run; skipping reindex (idle = free)."
  else
    echo "  -> corpus CHANGED; reindexing all ${#AGENTS[@]} agents (sequential, keep box calm)"
    if [[ $DRY_RUN -eq 0 ]]; then
      for a in "${AGENTS[@]}"; do
        if openclaw memory index --agent "$a" >/dev/null 2>&1; then
          REINDEXED=$((REINDEXED+1))
          printf '     ok  %s\n' "$a"
        else
          printf '     ERR %s\n' "$a"
        fi
      done
      echo "$NEWHASH" > "$STAMP"
      echo "  -> reindexed ${REINDEXED}/${#AGENTS[@]} agents; stamp updated"
    else
      echo "  -> DRY RUN: would reindex ${#AGENTS[@]} agents and update stamp"
    fi
  fi
fi

# ---- STATUS line for the cron ----
echo
if [[ $DRY_RUN -eq 1 ]]; then
  echo "STATUS(dry-run): would promote ${PROMOTED_COUNT}, drop ${DROPPED_COUNT}; reindex=$([ "${NEWHASH:-}" != "${OLDHASH:-}" ] && echo yes || echo no)"
elif [[ $REINDEXED -gt 0 || $PROMOTED_COUNT -gt 0 || $DROPPED_COUNT -gt 0 ]]; then
  echo "CHANGED: reindexed ${REINDEXED} agents (promoted ${PROMOTED_COUNT} facts, dropped ${DROPPED_COUNT})"
else
  echo "NOCHANGE"
fi
echo "=================================================================="
