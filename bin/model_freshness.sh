#!/usr/bin/env bash
# Weekly MODEL FRESHNESS pass (consolidated 2026-06-09 per Cyrus).
# Does TWO things in one run:
#   (1) FALLBACKS  -> auto-bump to newest copilot sonnet+gpt, hot-reload if changed.
#   (2) PRIMARY    -> ALERT-ONLY check for a newer top-tier Opus. NEVER auto-switches.
#
# Emits one combined block on stdout. The cron parses it:
#   FALLBACK: ALERT: <summary>      (fallbacks were bumped + gateway reloaded)
#   FALLBACK: NOCHANGE
#   PRIMARY: PRIMARY_UPDATE: <newer> available (currently <cur>)
#   PRIMARY: NOCHANGE...
# Cron posts a Discord line only for the parts that are NOT NOCHANGE.
set -uo pipefail
BIN=/home/azureuser/.openclaw/bin
CFG=/home/azureuser/.openclaw/openclaw.json

# --- (1) Fallback auto-bump (auto-applies) ---
FB_RAW="$(python3 "$BIN/fallback_autobump.py" 2>&1)"
if echo "$FB_RAW" | grep -q '^BUMPED'; then
  if python3 -c "import json;json.load(open('$CFG'))" 2>/dev/null; then
    openclaw gateway restart --reason "auto-bump fallback model tier" >/dev/null 2>&1 \
      || systemctl --user reload openclaw-gateway 2>/dev/null
    echo "FALLBACK: ALERT: $FB_RAW (config valid, gateway reloaded)"
  else
    echo "FALLBACK: ALERT: autobump produced INVALID json — NOT reloaded, check backup"
  fi
else
  echo "FALLBACK: NOCHANGE"
fi

# --- (2) Primary alert-only check (NEVER auto-switches) ---
PR_RAW="$(python3 "$BIN/primary_newer_check.py" 2>&1)"
echo "PRIMARY: $PR_RAW"
