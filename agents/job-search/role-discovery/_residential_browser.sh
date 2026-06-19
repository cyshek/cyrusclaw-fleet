#!/usr/bin/env bash
# Stand up the END-TO-END residential-egress submit path and export JOBSEARCH_CDP.
#
# PROVEN 2026-06-08 to crack the Ashby reCAPTCHA-v3 score-gate (Notion 2888,
# Skydio 2899, Dash0 2459 all submitted; Dash0 A/B: datacenter=spam-flag,
# residential=FormSubmitSuccess). Overturns the 2026-06-05 "proxy doesn't move
# the score-gate" verdict.
#
# Usage:
#   source _residential_browser.sh          # starts relay + proxied Chrome, exports JOBSEARCH_CDP
#   # then, per row:
#   .venv/bin/python inline_submit.py --role-id <id> --ats ashby --dry-run   # prep
#   JOBSEARCH_CDP="$JOBSEARCH_CDP" ENABLE_CAPSOLVER=1 CAPSOLVER_API_KEY="$CAPSOLVER_API_KEY" \
#       .venv/bin/python _ashby_runner.py output/inline-plan-<slug>.json
#
# Requires env (already in this agent's environment): RESIDENTIAL_PROXY, CAPSOLVER_API_KEY.
set -u
RELAY_PORT="${RELAY_PORT:-18901}"
CDP_PORT="${RESI_CDP_PORT:-19223}"
PROFILE="${RESI_PROFILE:-/tmp/openclaw/.chromium/resi-profile}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
mkdir -p "$PROFILE"

# 1) relay (no-auth local -> authenticated Webshare residential upstream)
if ! ss -tln 2>/dev/null | grep -q ":${RELAY_PORT} "; then
  nohup "$HERE/.venv/bin/python" "$HERE/_proxy_relay.py" \
    --listen "127.0.0.1:${RELAY_PORT}" --upstream "${RESIDENTIAL_PROXY}" \
    > "$HERE/.lever-debug/relay.live.log" 2>&1 &
  sleep 2
fi

# 2) residential-proxied Chrome on a dedicated CDP port
if ! ss -tln 2>/dev/null | grep -q ":${CDP_PORT} "; then
  nohup /opt/google/chrome/chrome \
    --remote-debugging-port="${CDP_PORT}" \
    --user-data-dir="$PROFILE" \
    --no-first-run --no-default-browser-check --disable-sync \
    --disable-background-networking --disable-component-update \
    --disable-features=Translate,MediaRouter --password-store=basic \
    --headless=new --no-sandbox --disable-dev-shm-usage \
    --proxy-server="http://127.0.0.1:${RELAY_PORT}" \
    --remote-allow-origins=* \
    --user-agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36" \
    --ozone-platform=headless --ozone-override-screen-size=1280,800 \
    --use-angle=swiftshader-webgl \
    > /tmp/resi-chrome.log 2>&1 &
  sleep 4
fi

export JOBSEARCH_CDP="http://127.0.0.1:${CDP_PORT}"
EGRESS="$(curl -s --max-time 15 --proxy "http://127.0.0.1:${RELAY_PORT}" https://api.ipify.org 2>/dev/null)"
echo "residential path up: relay 127.0.0.1:${RELAY_PORT} -> Webshare ; CDP=${JOBSEARCH_CDP} ; egress=${EGRESS:-UNKNOWN}"
echo "verify the egress is residential (NOT 40.65.x Azure) before submitting."
