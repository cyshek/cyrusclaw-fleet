#!/usr/bin/env bash
# disk_alert_check.sh — continuous low-disk space monitor.
# Fires a Discord alert if free space drops below 20% (~6GB on 29GB disk).
# Designed to be called by a cron job (e.g. every 6 hours).
# Silent when healthy — only posts when threshold is breached.
#
# Owner: openclaw-updates agent. Built 2026-06-15.

set -uo pipefail

ALERT_THRESHOLD_PCT=20   # alert if free% drops below this
DISCORD_CHANNEL="channel:1502552885756432496"

used_pct() { df --output=pcent / | tail -1 | tr -dc '0-9'; }
avail_h()  { df -h --output=avail / | tail -1 | tr -d ' '; }
size_h()   { df -h --output=size / | tail -1 | tr -d ' '; }

USED=$(used_pct)
FREE=$((100 - USED))
AVAIL=$(avail_h)
TOTAL=$(size_h)

if [[ $FREE -lt $ALERT_THRESHOLD_PCT ]]; then
  # Top 5 consumers
  TOP=$(du -sh /home/azureuser/.openclaw/agents/*/ 2>/dev/null | sort -rh | head -5 \
        | awk '{print "  " $1 "  " $2}' | sed 's|.*/agents/||')

  MSG="⚠️ **Low disk alert** — ${FREE}% free (${AVAIL} of ${TOTAL})
Disk is ${USED}% full — below the ${ALERT_THRESHOLD_PCT}% threshold.

Top space consumers:
${TOP}

Run \`disk_cleanup.sh\` or expand the OS disk."

  openclaw message send --channel discord --target "$DISCORD_CHANNEL" "$MSG" 2>/dev/null || true
  echo "ALERT sent: ${USED}% used, ${FREE}% free"
  exit 1
else
  echo "OK: ${USED}% used, ${FREE}% free (${AVAIL} available) — above ${ALERT_THRESHOLD_PCT}% threshold"
  exit 0
fi
