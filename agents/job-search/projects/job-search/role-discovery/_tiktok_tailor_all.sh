#!/usr/bin/env bash
# Parallel tailor TikTok resumes. 4 concurrent workers, isolated LO profiles.
# tiktok-scale 2026-06-02
set -u
ROOT=/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search
VP=$ROOT/role-discovery/.venv/bin/python
TASKS=/tmp/tiktok_tasks2.txt
LOG=/tmp/tiktok_tailor.log
: > "$LOG"

tailor_one() {
  local line="$1" slot="$2"
  local rid jid fam title
  IFS='|' read -r rid jid fam title <<< "$line"
  local loprof="/tmp/lo_tiktok_$jid"
  mkdir -p "$loprof"
  local pdf="$ROOT/applications/queued/tiktok-$jid/Cyrus_Shekari_Resume_tiktok_${jid}_v2.pdf"
  if [ -f "$pdf" ] && [ "$(find "$pdf" -newer "$ROOT/applications/queued/tiktok-$jid/JD.md" 2>/dev/null)" ]; then
    echo "SKIP $rid/$jid pdf already fresh" >> "$LOG"; return
  fi
  echo "START $rid/$jid fam=$fam slot=$slot" >> "$LOG"
  "$VP" "$ROOT/role-discovery/tailor_resume.py" --org tiktok --job-id "$jid" \
       --family "$fam" --auto-rewrite --max-loops 2 \
       --user-install "$loprof" > "/tmp/tiktok_tailor_$jid.out" 2>&1
  local rc=$?
  if [ -f "$pdf" ]; then echo "DONE  $rid/$jid rc=$rc PDF-OK" >> "$LOG";
  else echo "FAIL  $rid/$jid rc=$rc NO-PDF" >> "$LOG"; fi
}
export -f tailor_one
export ROOT VP LOG

cat "$TASKS" | xargs -d '\n' -P 4 -I{} bash -c 'tailor_one "$@"' _ {} "$$_$BASHPID"
echo "ALL-TAILOR-DONE" >> "$LOG"
