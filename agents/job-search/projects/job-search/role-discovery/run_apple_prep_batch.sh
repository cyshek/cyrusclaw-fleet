#!/bin/bash
# run_apple_prep_batch.sh — Run Apple prep-only lane in sequential batches of 5
# until all blocked Apple roles are prepped. Logs to /tmp/apple_prep_batch.log
# Usage: bash run_apple_prep_batch.sh [--batch-size N]
set -euo pipefail

BATCH_SIZE="${1:-5}"
LOG="/tmp/apple_prep_batch.log"
PYTHON=".venv/bin/python"
SCRIPT="inline_submit.py"
MAX_ROUNDS=120   # safety ceiling: 120 * 5 = 600 roles max

cd "$(dirname "$0")"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Apple prep batch runner starting. batch_size=$BATCH_SIZE" | tee -a "$LOG"

for ((round=1; round<=MAX_ROUNDS; round++)); do
    REMAINING=$("$PYTHON" -c "
import sqlite3
c = sqlite3.connect('../tracker.db')
n = c.execute(\"SELECT count(*) FROM roles WHERE source_key LIKE 'apple:%' AND status='blocked' AND (prep_status IS NULL OR prep_status='')\").fetchone()[0]
print(n)
c.close()
")
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Round $round — $REMAINING unprepped Apple roles remaining" | tee -a "$LOG"
    
    if [ "$REMAINING" -eq 0 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] All Apple roles prepped. Done." | tee -a "$LOG"
        break
    fi
    
    # Run one batch
    "$PYTHON" "$SCRIPT" --batch "$BATCH_SIZE" --ats apple 2>&1 | tee -a "$LOG"
    RC=$?
    
    if [ $RC -ne 0 ]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] inline_submit.py exited $RC — continuing anyway" | tee -a "$LOG"
    fi
    
    # Brief pause between batches to avoid hammering the browser
    sleep 5
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Batch runner finished." | tee -a "$LOG"

# Print final summary
"$PYTHON" -c "
import sqlite3
c = sqlite3.connect('../tracker.db')
c.row_factory = sqlite3.Row
rows = c.execute(\"SELECT prep_status, count(*) as cnt FROM roles WHERE source_key LIKE 'apple:%' GROUP BY prep_status\").fetchall()
print('=== FINAL APPLE PREP SUMMARY ===')
for r in rows:
    print(f'  {r[\"prep_status\"]}: {r[\"cnt\"]}')
c.close()
" | tee -a "$LOG"
