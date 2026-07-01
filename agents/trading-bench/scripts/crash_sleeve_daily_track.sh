#!/bin/bash
# Daily crash-sleeve (regime-gated 3rd-sleeve) PAPER-clock tracker (PAPER ONLY; NO live orders).
# Re-runs the live inv-vol 2-sleeve allocator blend WITH a regime-gated cash hedge
# (3rd sleeve) to the latest close and logs an idempotent daily snapshot to
# crash_sleeve_paper.db. Mirrors xa_tsmom_daily_track.sh / tsmom_blend_daily_track.sh:
# the blend marks a new day only at the daily close and the recompute is heavy, so it
# runs ONCE after the US cash close (21:50 UTC, staggered clear of the 21:30/21:35/21:45
# heavy engine jobs) rather than every 30-min tick. Non-fatal: a tracker failure is
# logged but never affects live trading.
#
# Config (conservative "value pick" per probe GO-WITH-CAP):
#   HEDGE_WEIGHT=0.15 (wh15), DD_TRIGGER=-0.10 (SPX trailing-drawdown breach), hedge=CASH.
# Logs BOTH the GATED 3-sleeve blend AND the UNGATED live 2-sleeve baseline daily, so
# forward crash regimes directly test whether the gate helps (the backtest win is
# OOS-DD-only and rests on a single 2022 crash regime; this clock accumulates new ones).
# This is READ-ONLY forward evidence; it is NOT wired into the live roster.
# Probe verdict: reports/CRASH_SLEEVE_PROBE_20260630T164742Z.md
# Logs to logs/crash_sleeve_track.log.

cd /home/azureuser/.openclaw/agents/trading-bench/workspace || exit 1

mkdir -p logs

TS=$(date -u +%Y%m%dT%H%M%SZ)
{
    echo "=== crash_sleeve_paper_tracker @ $TS ==="
} >> logs/crash_sleeve_track.log

# Snapshot the latest markable day (idempotent on date).
python3 runner/crash_sleeve_paper_tracker.py >> logs/crash_sleeve_track.log 2>&1
SNAP_RC=$?
echo "snapshot rc: $SNAP_RC" >> logs/crash_sleeve_track.log

# Silent-clock guard: warn (rc 3) if the clock hasn't written a row in >=2 trading
# days (the daily cron likely stopped). Surfaces to stderr so cron mail / main notices.
STALE_OUT=$(python3 runner/crash_sleeve_paper_tracker.py --check-staleness 2>&1)
STALE_RC=$?
{
    echo "staleness (rc=$STALE_RC): $STALE_OUT"
    echo "=== end crash_sleeve @ $TS ==="
} >> logs/crash_sleeve_track.log
if [ "$STALE_RC" -eq 3 ]; then
    echo "[crash_sleeve] STALE CLOCK: regime-gated crash-sleeve paper clock has not written a row in >=2 days -- see logs/crash_sleeve_track.log" >&2
fi

exit 0
