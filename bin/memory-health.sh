#!/usr/bin/env bash
# memory-health.sh
# Reports each agent's "brain" health: how fresh their daily log + MEMORY.md are.
# Flags agents that did work but haven't logged it (stale brain = learning failure).
#
# Output is a compact table to stdout. main's memory-health-watchdog cron runs
# this and nudges any agent whose brain has gone stale.

set -uo pipefail

AGENTS_DIR="/home/azureuser/.openclaw/agents"
MAIN_WS="/home/azureuser/.openclaw/workspace"
NOW=$(date -u +%s)
STALE_HOURS=30   # a daily log older than this = flag (covers a missed nightly distill + margin)

age_hours() {  # $1 = epoch mtime -> integer hours ago
  local m="$1"
  echo $(( (NOW - m) / 3600 ))
}

row() {  # name workspace
  local name="$1" ws="$2"
  local memdir="$ws/memory" memfile="$ws/MEMORY.md"
  local latest_daily="" daily_age="-" daily_count=0 mem_age="-" flag=""

  if [ -d "$memdir" ]; then
    latest_daily=$(ls -1t "$memdir"/*.md 2>/dev/null | head -1)
    daily_count=$(ls -1 "$memdir"/*.md 2>/dev/null | wc -l | tr -d ' ')
    if [ -n "$latest_daily" ]; then
      daily_age=$(age_hours "$(stat -c '%Y' "$latest_daily")")
    fi
  fi
  if [ -f "$memfile" ]; then
    mem_age=$(age_hours "$(stat -c '%Y' "$memfile")")
  fi

  # Flag logic: stale daily log, or no daily dir, or near-empty MEMORY.md
  if [ -z "$latest_daily" ]; then
    flag="NO-DAILY-LOG"
  elif [ "$daily_age" != "-" ] && [ "$daily_age" -gt "$STALE_HOURS" ]; then
    flag="STALE(${daily_age}h)"
  fi
  if [ -f "$memfile" ]; then
    local sz=$(stat -c '%s' "$memfile")
    if [ "$sz" -lt 1500 ]; then
      flag="${flag:+$flag,}THIN-MEMORY(${sz}b)"
    fi
  else
    flag="${flag:+$flag,}NO-MEMORY.md"
  fi

  printf '%-18s daily:%-14s age:%-5s count:%-4s MEMORY.md_age:%-5s %s\n' \
    "$name" "$(basename "${latest_daily:-none}")" "${daily_age}h" "$daily_count" "${mem_age}h" "${flag:+⚠️ $flag}"
}

echo "=== Agent brain health  ($(date -u +%Y-%m-%dT%H:%MZ), stale threshold ${STALE_HOURS}h) ==="
row "main" "$MAIN_WS"
for d in "$AGENTS_DIR"/*/; do
  a="$(basename "$d")"
  [ -d "$d/workspace" ] && row "$a" "$d/workspace"
done

# --- Cron execution-failure check ---------------------------------------
# A journaling cron can FAIL to run (e.g. isolated-setup timeout) while the
# files just sit there stale. Stale-file detection misses that. Surface any
# mem-distill-* cron with consecutiveErrors>0 so it doesn't fail silently.
CRON_STATE="/home/azureuser/.openclaw/cron/jobs.json"
echo
echo "=== Journaling cron execution health ==="
if [ -f "$CRON_STATE" ] && command -v jq >/dev/null 2>&1; then
  fails=$(jq -r '
    (if type=="array" then . else (.jobs // []) end)
    | map(select((.name // "") | startswith("mem-distill")))
    | map(select((.state.consecutiveErrors // 0) > 0))
    | .[] | "\u26a0\ufe0f CRON-FAIL \(.name): consecutiveErrors=\(.state.consecutiveErrors) lastError=\(.state.lastError // .state.lastErrorReason // "?")"
  ' "$CRON_STATE" 2>/dev/null)
  if [ -n "$fails" ]; then
    echo "$fails"
  else
    echo "all mem-distill crons: no consecutive errors"
  fi
elif [ -f "$CRON_STATE" ]; then
  # jq-free fallback via node (always present in this env)
  node -e '
    const fs=require("fs");
    let d; try{d=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));}catch(e){console.log("(cron state parse error — skipped)");process.exit(0);}
    const jobs=Array.isArray(d)?d:(d.jobs||[]);
    const bad=jobs.filter(j=>(j.name||"").startsWith("mem-distill") && ((j.state&&j.state.consecutiveErrors)||0)>0);
    if(!bad.length){console.log("all mem-distill crons: no consecutive errors");}
    else{for(const j of bad){const s=j.state||{};console.log(`\u26a0\ufe0f CRON-FAIL ${j.name}: consecutiveErrors=${s.consecutiveErrors} lastError=${s.lastError||s.lastErrorReason||"?"}`);}}
  ' "$CRON_STATE" 2>/dev/null || echo "(node check failed — skipped)"
else
  echo "(cron state not found at $CRON_STATE — skipped execution-failure check)"
fi
