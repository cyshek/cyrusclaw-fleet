#!/usr/bin/env bash
# config-guard.sh
# Runs as ExecStartPre on openclaw-gateway.service. Prevents the 2026-05-27
# "bad config crash-loop until manual SSH" incident at the SOURCE: if the live
# openclaw.json fails validation, restore the last-known-good config BEFORE the
# gateway tries to boot, so it never enters a fast-fail loop on bad config.
#
# On a VALID config it refreshes the last-good snapshot, so last-good always
# tracks the most recent config that actually validated.
#
# This is belt-and-suspenders with:
#   - resilience.conf  (systemd never permanently gives up restarting)
#   - watchdog.timer   (force-restart if health port goes dead)
# Those keep a healthy gateway alive; THIS keeps a bad config from being the
# thing that kills it in the first place.

set -uo pipefail

OC_DIR="/home/azureuser/.openclaw"
CFG="${OC_DIR}/openclaw.json"
LASTGOOD="${OC_DIR}/openclaw.json.last-good"
SAFETY="${OC_DIR}/openclaw.json.prebad"   # snapshot of the bad config we replaced
NODE="$(command -v node || echo /usr/bin/node)"
OC_BIN="/usr/lib/node_modules/openclaw/dist/index.js"
LOG="${OC_DIR}/state/config-guard.log"
mkdir -p "${OC_DIR}/state"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >>"$LOG"; }

# Validate the live config. Exit 0 = valid.
if "$NODE" "$OC_BIN" config validate >/dev/null 2>&1; then
  # Valid: refresh last-good snapshot so it tracks the newest validated config.
  if ! cmp -s "$CFG" "$LASTGOOD" 2>/dev/null; then
    cp -f "$CFG" "$LASTGOOD" 2>/dev/null && log "config valid; refreshed last-good snapshot."
  else
    # Heartbeat on the valid+unchanged path so the log proves the guard ran at
    # THIS boot (otherwise an unchanged-config run is silent and the stale last
    # log line falsely reads as 'guard never runs' during later verification).
    log "config valid; unchanged from last-good (guard ran, no refresh needed)."
  fi
  exit 0
fi

# --- Live config is INVALID. ---
log "WARN: live openclaw.json FAILED validation. Attempting last-good restore."

if [ ! -f "$LASTGOOD" ]; then
  log "ERROR: no last-good snapshot to restore. Letting gateway start (will fail) so the operator sees it. NOT looping silently."
  # Don't block startup forever; surface the failure. resilience.conf will keep
  # retrying, but at least we logged the root cause loudly.
  exit 0
fi

# Validate the last-good itself before trusting it.
if ! OPENCLAW_CONFIG_PATH="$LASTGOOD" "$NODE" "$OC_BIN" config validate >/dev/null 2>&1; then
  log "ERROR: last-good snapshot ALSO fails validation. Not restoring. Surfacing failure to operator."
  exit 0
fi

# Preserve the bad config for forensics, then restore last-good.
cp -f "$CFG" "$SAFETY" 2>/dev/null && log "saved bad config to $(basename "$SAFETY") for forensics."
if cp -f "$LASTGOOD" "$CFG" 2>/dev/null; then
  log "RESTORED last-good config. Gateway will boot on it instead of crash-looping on the bad one. Operator should review ${SAFETY} vs ${CFG}."
else
  log "ERROR: failed to write restored config to $CFG (permissions?). Surfacing failure."
fi
exit 0
