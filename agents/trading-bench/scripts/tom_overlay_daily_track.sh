#!/bin/bash
# Daily TOM (Turn-of-Month) leverage-concentration OVERLAY PAPER-clock tracker (PAPER ONLY; NO live orders).
# Re-runs the RECOMMENDED SHELF CONFIG overlay (1x base every day + a +0.5 tilt realized by rotating
# w=0.25 of the book into a 3x ETF -- UPRO for the S&P book, TQQQ for the Nasdaq book -- ONLY during the
# last 2 + first 3 trading days of the month-turn) to the latest close and logs an idempotent daily
# snapshot to tom_overlay_paper.db. Logs BOTH the TOM-overlay book AND its B&H 1x control for each index
# (SPY & QQQ) plus SPX, so the forward clock measures DIRECTLY whether the calendar tilt adds RAW RETURN
# over plain buy-&-hold on the path observed (the headline claim is a raw-return claim). Mirrors
# crash_sleeve_daily_track.sh / daa_daily_track.sh: the recompute is heavy and only marks a new day at the
# daily close, so it runs ONCE after the US cash close (22:00 UTC Mon-Fri, staggered +5min clear of the
# 21:55 daa / 21:50 crash_sleeve / 21:45 gate-dashboard / 21:35 xa_tsmom / 21:30 tsmom_blend jobs) rather
# than every 30-min tick. Non-fatal: a tracker failure is logged but never affects live trading.
#
# Config (recommended shelf per production harness GO-for-paper):
#   pre=2/post=3, tilt=0.5, 3x ETF (UPRO/TQQQ) at w=0.25, 2bps one-way rotation cost.
#   Cyrus loosened the paper leverage rail 2026-06-30: ETF-form leverage on paper is the agent's call;
#   this clock is READ-ONLY forward evidence and is NOT wired into the live roster.
# Production harness / go-no-go: reports/TOM_OVERLAY_PRODUCTION_HARNESS_20260630T050146Z.md
# Logs to logs/tom_overlay_track.log.

cd /home/azureuser/.openclaw/agents/trading-bench/workspace || exit 1

mkdir -p logs

TS=$(date -u +%Y%m%dT%H%M%SZ)
{
    echo "=== tom_overlay_paper_tracker @ $TS ==="
} >> logs/tom_overlay_track.log

# Snapshot the latest markable day (idempotent on date).
python3 runner/tom_overlay_paper_tracker.py >> logs/tom_overlay_track.log 2>&1
SNAP_RC=$?
echo "snapshot rc: $SNAP_RC" >> logs/tom_overlay_track.log

# Silent-clock guard: warn (rc 3) if the clock hasn't written a row in >=2 trading days
# (the daily cron likely stopped). Surfaces to stderr so cron mail / main notices.
STALE_OUT=$(python3 runner/tom_overlay_paper_tracker.py --check-staleness 2>&1)
STALE_RC=$?
{
    echo "staleness (rc=$STALE_RC): $STALE_OUT"
    echo "=== end tom_overlay @ $TS ==="
} >> logs/tom_overlay_track.log
if [ "$STALE_RC" -eq 3 ]; then
    echo "[tom_overlay] STALE CLOCK: TOM overlay paper clock has not written a row in >=2 days -- see logs/tom_overlay_track.log" >&2
fi

exit 0
