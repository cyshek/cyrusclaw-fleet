#!/usr/bin/env bash
# post-restart-allclear.sh
# Fires once after the OpenClaw gateway (re)starts. Waits for the gateway HTTP
# port to be ready, then sends an "all-clear, resume parked work" agentTurn to
# each peer agent so agents that parked themselves in a "waiting for the gateway
# to come back" state auto-resume instead of sitting silent.
#
# Wired as a systemd ExecStartPost drop-in on openclaw-gateway.service so it
# fires on EVERY restart cause (config swap, crash, manual restart).
#
# Idempotency: writes a stamp keyed to the gateway process start-time. If the
# stamp already matches the current gateway boot, it exits without re-sending,
# so a manual re-run or a duplicate ExecStartPost won't double-broadcast.

set -uo pipefail

OPENCLAW_BIN="/usr/lib/node_modules/openclaw/dist/index.js"
NODE="$(command -v node || echo /usr/bin/node)"
GW_PORT="18789"
GW_URL="http://127.0.0.1:${GW_PORT}"
STATE_DIR="/home/azureuser/.openclaw/state"
STAMP="${STATE_DIR}/post-restart-allclear.stamp"
LOG="${STATE_DIR}/post-restart-allclear.log"
ENV_FILE="/home/azureuser/.openclaw/.env"

mkdir -p "$STATE_DIR"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >>"$LOG"; }

# --- Peers that should be told to resume parked work. main is excluded: the
# --- gateway already pings main's last active session post-restart. ---
# Format: "agentId|channelId"
PEERS=(
  "job-search|1501827950474166332"
  "openclaw-updates|1502552885756432496"
  "travel|1504222524093894727"
  "trading-bench|1508503706545557656"
  "making-money|1508695851697049812"
)

# --- Idempotency: key off the gateway process start-time. ---
GPID="$(pgrep -f 'openclaw.*gateway' | head -1)"
if [ -z "$GPID" ]; then
  # Gateway not up yet from our point of view; wait below will handle readiness.
  BOOT_KEY="unknown-$(date -u +%s)"
else
  BOOT_KEY="$(stat -c '%Y' /proc/"$GPID" 2>/dev/null || echo "pid${GPID}")"
fi

if [ -f "$STAMP" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$BOOT_KEY" ]; then
  log "stamp matches current boot ($BOOT_KEY); already broadcast, exiting."
  exit 0
fi

# --- Wait for the gateway HTTP port to accept connections (max ~90s). ---
ready=0
for i in $(seq 1 45); do
  if curl -fsS -m 2 "${GW_URL}/health" >/dev/null 2>&1 \
     || curl -fsS -m 2 "${GW_URL}/" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  log "gateway port ${GW_PORT} not ready after ~90s; aborting broadcast (will retry on next restart)."
  exit 1
fi

# Small settle delay so agent sessions are fully wired before we message them.
sleep 5

# Re-resolve boot key now that the gateway is confirmed up.
GPID="$(pgrep -f 'openclaw.*gateway' | head -1)"
[ -n "$GPID" ] && BOOT_KEY="$(stat -c '%Y' /proc/"$GPID" 2>/dev/null || echo "pid${GPID}")"

MSG='Gateway is back up and stable after a restart. If you parked yourself waiting for the gateway to return (a "holding until the gateway is back" or "awaiting confirmation to resume" state), this is your all-clear: resume the work you were holding NOW. Per standing orders, do not wait for a human go-ahead on queue/research work that is not real-money, destructive, or externally-risky. Pick the highest-leverage unblocked item from your BACKLOG/RESUME-FROM notes and execute, and status-post to your Discord channel when you start. If nothing was parked (you were already idle, working, or had no held state), reply with ONLY the exact token NO_REPLY and emit NO other text whatsoever — do not post any "idle" / "nothing parked" / status line to the channel. A visible status line on this all-clear is spam; stay silent unless you are actually resuming parked work.'

sent=0
for entry in "${PEERS[@]}"; do
  agent="${entry%%|*}"
  chan="${entry##*|}"
  skey="agent:${agent}:discord:channel:${chan}"
  log "sending all-clear to agent=${agent} session=${skey}"
  # Real agentTurn into the peer's Discord channel session (the one Cyrus
  # watches), with reply delivered to that channel. Backgrounded so one slow
  # peer doesn't block the rest; short timeout keeps each turn bounded.
  (
    "$NODE" "$OPENCLAW_BIN" agent \
        --agent "$agent" \
        --session-key "$skey" \
        --message "$MSG" \
        --deliver \
        --reply-channel discord \
        --reply-to "channel:${chan}" \
        --timeout 180 >>"$LOG" 2>&1 \
      && log "all-clear delivered: ${agent}" \
      || log "WARN: agent send failed for ${agent} (session ${skey})"
  ) &
  sent=$((sent+1))
done
wait

echo "$BOOT_KEY" >"$STAMP"
log "broadcast complete: ${sent}/${#PEERS[@]} peers notified; stamped boot=${BOOT_KEY}."

# --- Part B residual: wake any agent whose restart-recovery FAILED (non-resumable
# --- transcript tail). The gateway's built-in main-session-restart-recovery
# --- resumes resumable sessions automatically, but a turn that died with an
# --- assistant-role tail is marked failed + left parked (the openclaw-updates
# --- failure mode on 2026-05-27/05-31). The all-clear agentTurn above already
# --- gives every peer a fresh user turn, which IS the wake those parked sessions
# --- need — so this is just an observability log, not a second kick.
FAILED_RECOVERY=$(journalctl --user -u openclaw-gateway.service --since '3 min ago' 2>/dev/null \
  | grep -iE 'marked interrupted .* failed|restart recovery .*failed=[1-9]' | tail -5)
if [ -n "$FAILED_RECOVERY" ]; then
  log "NOTE: restart-recovery reported failed/non-resumable sessions (all-clear turn above re-kicks them):"
  echo "$FAILED_RECOVERY" | while IFS= read -r line; do log "  $line"; done
fi
exit 0
