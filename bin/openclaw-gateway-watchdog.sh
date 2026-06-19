#!/usr/bin/env bash
set -u

HEALTH_FAIL_FILE=/tmp/openclaw-gw-healthfails
LLM_STATE_FILE=/tmp/openclaw-gw-llm-watchdog-state
LOG_FILE="$HOME/.openclaw/logs/gateway-watchdog.log"
ERROR_PATTERN='error="LLM request failed|error=LLM request failed|rawError=.*model_not_supported|providerErrorType=invalid_request_error|No API key found|Missing API key|Couldn.t sign in'

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG_FILE"
}

restart_gateway() {
  local reason="$1"
  log "restarting openclaw-gateway.service: $reason"
  rm -f "$HEALTH_FAIL_FILE" "$LLM_STATE_FILE"
  systemctl --user restart openclaw-gateway.service
  sleep 5
  if systemctl --user is-active --quiet openclaw-gateway.service; then
    log "gateway restart complete; service is active"
  else
    log "gateway restart attempted, but service is not active"
    return 1
  fi
}

check_health() {
  if curl -fsS --max-time 30 http://127.0.0.1:18789/healthz >/dev/null 2>&1; then
    rm -f "$HEALTH_FAIL_FILE"
    return 0
  fi

  local failures
  failures=$(( $(cat "$HEALTH_FAIL_FILE" 2>/dev/null || echo 0) + 1 ))
  echo "$failures" > "$HEALTH_FAIL_FILE"

  if [ "$failures" -ge 3 ]; then
    restart_gateway "healthcheck failed ${failures}x consecutively"
  else
    log "healthcheck failed (${failures}/3); waiting before restart"
  fi
}

check_llm_errors() {
  local now last_check consecutive since count
  now=$(date +%s)
  last_check=0
  consecutive=0

  if [ -f "$LLM_STATE_FILE" ]; then
    # shellcheck disable=SC1090
    . "$LLM_STATE_FILE" 2>/dev/null || true
    last_check=${LAST_CHECK:-0}
    consecutive=${CONSECUTIVE_ERROR_WINDOWS:-0}
  fi

  if ! [[ "$last_check" =~ ^[0-9]+$ ]] || [ "$last_check" -le 0 ]; then
    last_check=$((now - 180))
  fi

  # Overlap slightly so timer jitter cannot miss errors between runs.
  since=$((last_check - 10))
  count=$(journalctl --user -u openclaw-gateway.service --since "@$since" --no-pager 2>/dev/null \
    | grep -Ei "$ERROR_PATTERN" \
    | grep -Eiv 'Operational handoff|Debugging playbook|If agents fail|Please remember this operational context|watchdog' \
    | wc -l)

  if [ "$count" -gt 0 ]; then
    consecutive=$((consecutive + 1))
    log "detected $count recent LLM/provider/auth error log line(s); consecutive_windows=$consecutive"
  else
    consecutive=0
  fi

  printf 'LAST_CHECK=%s\nCONSECUTIVE_ERROR_WINDOWS=%s\n' "$now" "$consecutive" > "$LLM_STATE_FILE"

  if [ "$count" -ge 6 ] || [ "$consecutive" -ge 2 ]; then
    restart_gateway "recent repeated LLM/provider/auth errors count=$count consecutive_windows=$consecutive"
  fi
}

check_health
check_llm_errors
