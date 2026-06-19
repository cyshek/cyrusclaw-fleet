#!/usr/bin/env bash
# resume-pipeline-guard.sh
# Last-known-good snapshot + restore for the SHARED resume-tailoring pipeline.
#
# The tailoring engine (tailor_resume.py, bullet_rewriter.py) and the master
# resume are shared, read-only, by BOTH job-search and resume-tailor. They are
# NOT tracked by the workspace git repo, so there was no recovery net if an
# edit went bad. This is that net — same spirit as config-guard.sh for
# openclaw.json.
#
# Usage:
#   resume-pipeline-guard.sh snapshot   # save current files as a new snapshot,
#                                        # and refresh "last-good" IF tests pass
#   resume-pipeline-guard.sh verify     # run the tailoring test suite only
#   resume-pipeline-guard.sh restore    # restore files from last-good snapshot
#   resume-pipeline-guard.sh list       # list available snapshots
#
# Recommended flow when editing the pipeline:
#   1) resume-pipeline-guard.sh snapshot   (capture good state BEFORE editing)
#   2) ...make your edit...
#   3) resume-pipeline-guard.sh verify     (must pass)
#   4) resume-pipeline-guard.sh snapshot   (promotes new state to last-good)
#   If step 3 fails: resume-pipeline-guard.sh restore

set -uo pipefail

RD="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"
RES="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/resume"
STORE="/home/azureuser/.openclaw/state/resume-pipeline-guard"
LASTGOOD="${STORE}/last-good"
LOG="${STORE}/guard.log"

# Files under guard (engine + master, all three master forms)
FILES=(
  "${RD}/tailor_resume.py"
  "${RD}/bullet_rewriter.py"
  "${RES}/Cyrus_Shekari_Resume_master.docx"
  "${RES}/Cyrus_Shekari_Resume_master.md"
  "${RES}/Cyrus_Shekari_Resume.txt"
)

mkdir -p "$STORE"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >>"$LOG"; }

copy_set() {  # copy_set <destdir>
  local dest="$1"; mkdir -p "$dest"
  for f in "${FILES[@]}"; do
    if [[ -f "$f" ]]; then
      cp -f "$f" "${dest}/$(basename "$f")"
    fi
  done
}

run_tests() {
  ( cd "$RD" && .venv/bin/python -m pytest test_tailor_resume.py -q ) 
}

case "${1:-}" in
  verify)
    echo ">> Running tailoring test suite (test_tailor_resume.py)..."
    if run_tests; then
      echo "VERIFY: PASS"; log "verify PASS"; exit 0
    else
      echo "VERIFY: FAIL"; log "verify FAIL"; exit 1
    fi
    ;;

  snapshot)
    # Always capture a timestamped snapshot.
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    SNAP="${STORE}/snap-${TS}"
    copy_set "$SNAP"
    log "snapshot captured -> ${SNAP}"
    echo ">> Snapshot saved: ${SNAP}"
    # Promote to last-good ONLY if tests pass against the live files.
    echo ">> Verifying live files before promoting to last-good..."
    if run_tests >/dev/null 2>&1; then
      copy_set "$LASTGOOD"
      log "last-good refreshed from live (tests passed)"
      echo ">> last-good REFRESHED (tailoring tests passed)."
    else
      log "last-good NOT refreshed (tests failed); snapshot kept at ${SNAP}"
      echo ">> WARNING: tailoring tests FAILED on live files."
      echo ">> last-good was NOT updated. Snapshot kept for forensics: ${SNAP}"
      echo ">> If live is broken, run: $0 restore"
      exit 1
    fi
    ;;

  restore)
    if [[ ! -d "$LASTGOOD" ]]; then
      echo "ERROR: no last-good snapshot exists yet at ${LASTGOOD}"; exit 1
    fi
    # Back up current (possibly-bad) state first.
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    copy_set "${STORE}/prebad-${TS}"
    for f in "${FILES[@]}"; do
      src="${LASTGOOD}/$(basename "$f")"
      [[ -f "$src" ]] && cp -f "$src" "$f"
    done
    log "RESTORED files from last-good (prev state saved to prebad-${TS})"
    echo ">> Restored from last-good. Previous state saved to ${STORE}/prebad-${TS}"
    echo ">> Re-verifying..."
    run_tests && echo ">> Post-restore tests PASS" || echo ">> WARNING: tests still failing after restore"
    ;;

  list)
    echo "Snapshots in ${STORE}:"; ls -1dt "${STORE}"/snap-* "${STORE}"/prebad-* 2>/dev/null
    echo "last-good:"; ls -la "${LASTGOOD}" 2>/dev/null || echo "  (none yet)"
    ;;

  *)
    echo "usage: $0 {snapshot|verify|restore|list}"; exit 2;;
esac
