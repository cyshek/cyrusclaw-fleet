#!/usr/bin/env bash
# memory_log_staleness_check.sh
# A SMOKE DETECTOR for the LOG-EVERY-INTERACTION policy (Cyrus, 2026-06-08).
#
# WHY THIS EXISTS: logging to memory/YYYY-MM-DD.md is policy-and-discipline-driven,
# NOT machine-enforced (there is no per-turn hook in OpenClaw yet — main + job-search
# reconciled this 2026-06-08). This script does NOT capture conversation (an isolated
# run can't see the live transcript and would hallucinate). Instead it only reads FILE
# MTIME and flags when the daily log has gone stale while the agent was plausibly active.
# It converts a SILENT logging miss into a VISIBLE channel nudge.
#
# Exit/print contract for the cron wrapper:
#   - prints "STALE <minutes>min <file>"  when the freshest daily log is older than
#     THRESHOLD_MIN and we're inside active hours -> cron should ping the channel.
#   - prints "OK <minutes>min <file>"      when fresh enough -> cron stays silent.
#   - prints "QUIET-HOURS ..." / "NO-FILE ..." for the no-alert cases -> cron stays silent.
#
# It is INTENTIONALLY conservative: it only alarms when BOTH (a) the log is clearly
# stale AND (b) it's daytime-ish, so it won't page about overnight idle windows where
# no interactions are expected.

set -euo pipefail

WS="/home/azureuser/.openclaw/agents/job-search/workspace"
MEMDIR="$WS/memory"
THRESHOLD_MIN="${MEMLOG_STALE_THRESHOLD_MIN:-180}"   # default: alarm if >3h stale during active hours
ACTIVE_START_HOUR_PST="${MEMLOG_ACTIVE_START:-7}"     # 07:00 PST
ACTIVE_END_HOUR_PST="${MEMLOG_ACTIVE_END:-23}"        # 23:00 PST

now_epoch=$(date +%s)

# Consider BOTH the PST-dated and UTC-dated daily files. Around the date boundary the
# host UTC clock and PST disagree (e.g. 9pm PST == next-day UTC), and the agent may be
# writing to either filename. We grade the FRESHEST of the candidates so we never cry
# wolf just because we looked at yesterday's file.
pst_date=$(TZ=America/Los_Angeles date +%Y-%m-%d)
utc_date=$(date -u +%Y-%m-%d)

best_file=""
best_mtime=0
for d in "$pst_date" "$utc_date"; do
  f="$MEMDIR/$d.md"
  if [ -f "$f" ]; then
    mt=$(stat -c %Y "$f")
    if [ "$mt" -gt "$best_mtime" ]; then
      best_mtime="$mt"
      best_file="$f"
    fi
  fi
done

# Active-hours gate (PST). Outside active hours we never alarm (overnight idle is fine).
pst_hour=$(TZ=America/Los_Angeles date +%-H)
in_active_hours=0
if [ "$pst_hour" -ge "$ACTIVE_START_HOUR_PST" ] && [ "$pst_hour" -lt "$ACTIVE_END_HOUR_PST" ]; then
  in_active_hours=1
fi

if [ -z "$best_file" ]; then
  # No daily file for today at all. Only meaningful as an alarm during active hours.
  if [ "$in_active_hours" -eq 1 ]; then
    echo "NO-FILE today=$pst_date (no daily log exists yet during active hours)"
  else
    echo "QUIET-HOURS no-file pst_hour=$pst_hour"
  fi
  exit 0
fi

age_min=$(( (now_epoch - best_mtime) / 60 ))

if [ "$in_active_hours" -ne 1 ]; then
  echo "QUIET-HOURS ${age_min}min $(basename "$best_file") pst_hour=$pst_hour"
  exit 0
fi

if [ "$age_min" -gt "$THRESHOLD_MIN" ]; then
  echo "STALE ${age_min}min $(basename "$best_file") (threshold ${THRESHOLD_MIN}min)"
else
  echo "OK ${age_min}min $(basename "$best_file")"
fi
exit 0
