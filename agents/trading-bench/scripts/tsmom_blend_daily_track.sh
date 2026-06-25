#!/bin/bash
# Daily 80/20 TSMOM-blend PAPER-clock tracker (PAPER ONLY; NO live orders).
# Re-runs the validated vol-normalized equity-book x core4-TSMOM blend engine to
# the latest close and logs an idempotent daily snapshot to tsmom_blend_paper.db.
# Mirrors the allocator paper clock, but on a DAILY cadence (the blend marks a new
# day only at the daily close, and the recompute is heavy ~8 backtests), so it runs
# once after the US cash close instead of every 30-min tick. Non-fatal: a tracker
# failure is logged but never affects live trading. Logs to logs/tsmom_blend_track.log.

cd /home/azureuser/.openclaw/agents/trading-bench/workspace || exit 1

TS=$(date -u +%Y%m%dT%H%M%SZ)
{
    echo "=== tsmom_blend_paper_tracker @ $TS ==="
} >> logs/tsmom_blend_track.log

# Snapshot the latest markable day (idempotent on date).
python3 runner/tsmom_blend_paper_tracker.py >> logs/tsmom_blend_track.log 2>&1
SNAP_RC=$?
echo "snapshot rc: $SNAP_RC" >> logs/tsmom_blend_track.log

# Silent-clock guard: warn (rc 3) if the clock hasn't written a row in >4 days
# (the daily cron likely stopped). Surfaces to stderr so cron mail / main notices.
STALE_OUT=$(python3 runner/tsmom_blend_paper_tracker.py --check-staleness 2>&1)
STALE_RC=$?
{
    echo "staleness (rc=$STALE_RC): $STALE_OUT"
    echo "=== end tsmom_blend @ $TS ==="
} >> logs/tsmom_blend_track.log
if [ "$STALE_RC" -eq 3 ]; then
    echo "[tsmom_blend] STALE CLOCK: 80/20 blend paper clock has not written a row in >4 days -- see logs/tsmom_blend_track.log" >&2
fi

exit 0
