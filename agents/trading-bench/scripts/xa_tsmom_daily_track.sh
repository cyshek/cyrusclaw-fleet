#!/bin/bash
# Daily cross-asset 12-1 TSMOM PAPER-clock tracker (PAPER ONLY; NO live orders).
# Re-runs the VALIDATED 5-asset {SPY,TLT,GLD,DBC,UUP} 12-1 absolute-momentum engine
# (reports/_xa_tsmom_driver.py, reused verbatim) to the latest close and logs an
# idempotent daily snapshot to xa_tsmom_paper.db. Mirrors tsmom_blend_daily_track.sh:
# the book is monthly-rebalanced but we mark a daily forward equity curve vs SPY, so
# it runs ONCE after the US cash close (21:30 UTC, after settle) rather than every
# 30-min tick. Non-fatal: a tracker failure is logged but never affects live trading.
# Gate verdict: reports/XA_TSMOM_12_1_GATE_20260626T164538Z.md
#   (OOS Sharpe 1.14 > SPY 0.90, maxDD -10.6% vs -23.9%, 2022 -1% vs SPY -18%;
#    loses SPY on raw return -> tracked as a risk-orthogonal diversifier, paper-only).
# Logs to logs/xa_tsmom_track.log.

cd /home/azureuser/.openclaw/agents/trading-bench/workspace || exit 1

mkdir -p logs

TS=$(date -u +%Y%m%dT%H%M%SZ)
{
    echo "=== xa_tsmom_paper_tracker @ $TS ==="
} >> logs/xa_tsmom_track.log

# Snapshot the latest markable day (idempotent on date).
python3 runner/xa_tsmom_paper_tracker.py >> logs/xa_tsmom_track.log 2>&1
SNAP_RC=$?
echo "snapshot rc: $SNAP_RC" >> logs/xa_tsmom_track.log

# Silent-clock guard: warn (rc 3) if the clock hasn't written a row in >4 trading
# days (the daily cron likely stopped). Surfaces to stderr so cron mail / main notices.
STALE_OUT=$(python3 runner/xa_tsmom_paper_tracker.py --check-staleness 2>&1)
STALE_RC=$?
{
    echo "staleness (rc=$STALE_RC): $STALE_OUT"
    echo "=== end xa_tsmom @ $TS ==="
} >> logs/xa_tsmom_track.log
if [ "$STALE_RC" -eq 3 ]; then
    echo "[xa_tsmom] STALE CLOCK: cross-asset 12-1 TSMOM paper clock has not written a row in >4 days -- see logs/xa_tsmom_track.log" >&2
fi

exit 0
