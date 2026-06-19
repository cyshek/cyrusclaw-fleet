#!/usr/bin/env bash
# patch-cron-watchdog.sh — make OpenClaw's hardcoded cron-agent SETUP / PRE-EXECUTION
# watchdog timeouts env-configurable, and apply our raised values.
#
# WHY: openclaw's isolated-agent cron runner has a hardcoded 60s "setup watchdog"
# (CRON_AGENT_SETUP_WATCHDOG_MS = 6e4) that fires BEFORE the runner starts and is
# NOT tunable via cron config or per-job timeoutSeconds (the setup phase ignores
# jobTimeoutMs entirely — verified in dist). Under setup-phase contention (global
# sessions index / embeddings / disk I/O) isolated crons intermittently lose the
# race vs this 60s wall and error with:
#   "cron: isolated agent setup timed out before runner start" (durationMs ~60299)
# This was the standing "Issue A" in main's BACKLOG.md — store-size-independent,
# fleet-wide, biting distill + cadence crons (travel cb472847, job-search aadd3efe, ...).
#
# WHAT THIS DOES (idempotent):
#   1. Replaces the two hardcoded `6e4` consts in the cron dist bundle with reads of
#      env vars OPENCLAW_CRON_AGENT_SETUP_WATCHDOG_MS / _PRE_EXECUTION_WATCHDOG_MS,
#      falling back to 6e4 if the env var is unset/non-numeric. (Safe default = old
#      behaviour, so an un-set env after an update degrades gracefully to 60s.)
#   2. Is safe to run repeatedly — detects already-patched files and no-ops.
#
# It deliberately does NOT set the values — those live in gateway.systemd.env so they
# survive restarts and are visible to the systemd unit (EnvironmentFile). This script
# only makes the code *honour* them.
#
# Designed to be run as an ExecStartPre on the gateway unit so it self-heals after
# `openclaw update` overwrites dist. Needs sudo to write the root-owned dist file.
set -uo pipefail

DIST="/usr/lib/node_modules/openclaw/dist/server-cron-BDussCwQ.js"
LOG_PREFIX="[patch-cron-watchdog]"

log() { echo "${LOG_PREFIX} $*"; }

if [[ ! -f "$DIST" ]]; then
  # Bundle filename can change across builds — locate by content signature.
  FOUND="$(grep -rl 'CRON_AGENT_SETUP_WATCHDOG_MS' /usr/lib/node_modules/openclaw/dist/ 2>/dev/null | head -1 || true)"
  if [[ -z "$FOUND" ]]; then
    log "no dist file containing CRON_AGENT_SETUP_WATCHDOG_MS found; nothing to patch (build may have changed). Skipping."
    exit 0
  fi
  DIST="$FOUND"
  log "located cron bundle at $DIST"
fi

SETUP_OLD='const CRON_AGENT_SETUP_WATCHDOG_MS = 6e4;'
SETUP_NEW='const CRON_AGENT_SETUP_WATCHDOG_MS = (Number(process.env.OPENCLAW_CRON_AGENT_SETUP_WATCHDOG_MS) > 0 ? Number(process.env.OPENCLAW_CRON_AGENT_SETUP_WATCHDOG_MS) : 6e4);'
PREEXEC_OLD='const CRON_AGENT_PRE_EXECUTION_WATCHDOG_MS = 6e4;'
PREEXEC_NEW='const CRON_AGENT_PRE_EXECUTION_WATCHDOG_MS = (Number(process.env.OPENCLAW_CRON_AGENT_PRE_EXECUTION_WATCHDOG_MS) > 0 ? Number(process.env.OPENCLAW_CRON_AGENT_PRE_EXECUTION_WATCHDOG_MS) : 6e4);'

already_setup=0
already_preexec=0
grep -qF "$SETUP_NEW" "$DIST" && already_setup=1
grep -qF "$PREEXEC_NEW" "$DIST" && already_preexec=1

if [[ $already_setup -eq 1 && $already_preexec -eq 1 ]]; then
  log "already patched ($DIST); no-op."
  exit 0
fi

# Verify the exact original substrings are present (guard against build drift).
need_setup=0; need_preexec=0
if [[ $already_setup -eq 0 ]]; then
  grep -qF "$SETUP_OLD" "$DIST" && need_setup=1 || { log "WARN: setup const signature not found and not already patched — build drift? Leaving setup watchdog untouched."; }
fi
if [[ $already_preexec -eq 0 ]]; then
  grep -qF "$PREEXEC_OLD" "$DIST" && need_preexec=1 || { log "WARN: pre-exec const signature not found and not already patched — build drift? Leaving pre-exec watchdog untouched."; }
fi

if [[ $need_setup -eq 0 && $need_preexec -eq 0 ]]; then
  log "nothing to do (no matching unpatched signatures)."
  exit 0
fi

TMP="$(mktemp)"
cp "$DIST" "$TMP" || { log "ERROR: cannot copy dist to temp"; rm -f "$TMP"; exit 1; }

# Use perl for literal, single-occurrence-safe replacement (no regex metachar surprises).
if [[ $need_setup -eq 1 ]]; then
  OLD="$SETUP_OLD" NEW="$SETUP_NEW" perl -0777 -pi -e 'my $o=quotemeta($ENV{OLD}); s/$o/$ENV{NEW}/g' "$TMP" \
    && log "patched SETUP watchdog -> env-configurable" \
    || { log "ERROR: setup patch failed"; rm -f "$TMP"; exit 1; }
fi
if [[ $need_preexec -eq 1 ]]; then
  OLD="$PREEXEC_OLD" NEW="$PREEXEC_NEW" perl -0777 -pi -e 'my $o=quotemeta($ENV{OLD}); s/$o/$ENV{NEW}/g' "$TMP" \
    && log "patched PRE-EXECUTION watchdog -> env-configurable" \
    || { log "ERROR: pre-exec patch failed"; rm -f "$TMP"; exit 1; }
fi

# Sanity: file must still be valid-ish JS (node --check on a single ESM chunk isn't
# reliable for a partial bundle, so we just confirm the new substrings landed).
ok=1
[[ $need_setup -eq 1 ]] && { grep -qF "$SETUP_NEW" "$TMP" || ok=0; }
[[ $need_preexec -eq 1 ]] && { grep -qF "$PREEXEC_NEW" "$TMP" || ok=0; }
if [[ $ok -ne 1 ]]; then
  log "ERROR: post-patch verification failed; not installing."
  rm -f "$TMP"
  exit 1
fi

# Install atomically. Needs sudo because dist is root-owned.
SUDO=""
if [[ "$(id -u)" != "0" ]]; then SUDO="sudo -n"; fi
if $SUDO cp "$TMP" "$DIST" 2>/dev/null; then
  log "installed patched bundle -> $DIST"
  rm -f "$TMP"
  exit 0
else
  log "ERROR: could not write $DIST (sudo denied?). Temp left at $TMP"
  exit 1
fi
