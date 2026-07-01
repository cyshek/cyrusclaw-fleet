#!/bin/bash
# Daily Keller/Keuning DAA (Defensive Asset Allocation) canary PAPER-clock tracker (PAPER ONLY; NO live orders).
# Re-runs the VALIDATED DAA cascade engine (_daa_confirm.run_daa, reused verbatim) to the latest
# close and logs an idempotent daily snapshot to daa_paper.db. Logs BOTH the DAA canary book AND
# our validated rotation sleeve (control = run_sector_rotation top-2 {SPY,QQQ,GLD,TLT}) plus SPX,
# so forward regimes directly test whether DAA's de-risking canary helps on the path observed.
# Mirrors crash_sleeve_daily_track.sh / xa_tsmom_daily_track.sh: the book is monthly-rebalanced
# but we mark a daily forward equity curve, and the recompute is heavy, so it runs ONCE after the
# US cash close (21:55 UTC, staggered clear of the 21:30/21:35/21:45/21:50 heavy engine + tracker
# jobs) rather than every 30-min tick. Non-fatal: a tracker failure is logged but never affects
# live trading. This is READ-ONLY forward evidence; it is NOT wired into the live roster.
# Confirm-or-kill driver: _daa_confirm.py (DAA = crash-insurance de-risk, orthogonal to allocator_blend).
# Logs to logs/daa_track.log.

cd /home/azureuser/.openclaw/agents/trading-bench/workspace || exit 1

mkdir -p logs

TS=$(date -u +%Y%m%dT%H%M%SZ)
{
    echo "=== daa_paper_tracker @ $TS ==="
} >> logs/daa_track.log

# Snapshot the latest markable day (idempotent on date).
python3 runner/daa_paper_tracker.py >> logs/daa_track.log 2>&1
SNAP_RC=$?
echo "snapshot rc: $SNAP_RC" >> logs/daa_track.log

# Silent-clock guard: warn (rc 3) if the clock hasn't written a row in >=2 trading
# days (the daily cron likely stopped). Surfaces to stderr so cron mail / main notices.
STALE_OUT=$(python3 runner/daa_paper_tracker.py --check-staleness 2>&1)
STALE_RC=$?
{
    echo "staleness (rc=$STALE_RC): $STALE_OUT"
    echo "=== end daa @ $TS ==="
} >> logs/daa_track.log
if [ "$STALE_RC" -eq 3 ]; then
    echo "[daa] STALE CLOCK: DAA canary paper clock has not written a row in >=2 days -- see logs/daa_track.log" >&2
fi

exit 0
