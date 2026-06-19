#!/bin/bash
# Produces a digest of every peer agent's latest daily memory + current BACKLOG.md.
# Writes to /home/azureuser/.openclaw/workspace/PEER_STATE.md (main agent's workspace).
# Stdout is also the digest (so cron can pipe it as a systemEvent).
set -euo pipefail

OUT="/home/azureuser/.openclaw/workspace/PEER_STATE.md"
PEERS=(job-search openclaw-updates travel trading-bench making-money)
NOW=$(date -u +"%Y-%m-%d %H:%M UTC")

{
  echo "# PEER_STATE.md"
  echo
  echo "_Auto-generated digest of peer agents' latest daily memory + current BACKLOG.md._"
  echo "_Generated: ${NOW}_"
  echo

  for agent in "${PEERS[@]}"; do
    ws="/home/azureuser/.openclaw/agents/$agent/workspace"
    echo "---"
    echo
    echo "## $agent"
    echo

    # Latest daily memory
    latest=$(ls -1 "$ws/memory/" 2>/dev/null | grep -E '^20[0-9]{2}-[0-9]{2}-[0-9]{2}\.md$' | sort | tail -1 || true)
    if [ -n "$latest" ]; then
      echo "### Latest daily memory: \`memory/$latest\`"
      echo
      # Cap each daily at 80 lines so digest stays readable
      head -80 "$ws/memory/$latest"
      lines=$(wc -l < "$ws/memory/$latest")
      if [ "$lines" -gt 80 ]; then
        echo
        echo "_…(truncated; $lines total lines in source)_"
      fi
    else
      echo "_No daily memory files found._"
    fi
    echo

    # BACKLOG.md
    if [ -f "$ws/BACKLOG.md" ]; then
      echo "### BACKLOG.md"
      echo
      head -120 "$ws/BACKLOG.md"
      blines=$(wc -l < "$ws/BACKLOG.md")
      if [ "$blines" -gt 120 ]; then
        echo
        echo "_…(truncated; $blines total lines in source)_"
      fi
    else
      echo "_No BACKLOG.md._"
    fi
    echo
  done
} > "$OUT"

cat "$OUT"
