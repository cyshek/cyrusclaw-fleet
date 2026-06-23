#!/usr/bin/env bash
# cron_tick.sh — direct-shell cron wrapper for trading-bench ticks.
# Replaces the agentTurn cron wrappers so we don't depend on an LLM round-trip
# just to invoke ./tick.sh + post trade receipts. Posts via `openclaw message
# send` directly. If posting fails, exits non-zero so cron logs it locally.
#
# Usage: ./cron_tick.sh <strategy_name> [strategy_name ...]
#
# Behavior:
#  - Runs `./tick.sh <strategies>` and captures stdout/stderr.
#  - Greps for lines starting with `[<name>] BUY ` / `[<name>] SELL ` and posts
#    them verbatim, one message containing all of them.
#  - Greps for `[<name>] ERROR:` lines and posts a brief ack listing them.
#  - If neither: silent (exit 0).
#  - Per AGENTS.md: NEVER posts about holds / skips / "all quiet" — only
#    trades and errors.

set -u

WORKSPACE="/home/azureuser/.openclaw/agents/trading-bench/workspace"
CHANNEL_ID="channel:1508503706545557656"
LOG_DIR="$WORKSPACE/logs"
mkdir -p "$LOG_DIR"
TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG="$LOG_DIR/cron_tick_${TS}.log"

cd "$WORKSPACE" || { echo "FATAL: cd failed" >&2; exit 1; }

# Fill-reconcile pass: update any non-terminal orders from prior ticks before
# running this tick. Idempotent and silent on nothing-to-do. Errors are
# logged but non-fatal (don't block the tick).
RECON_OUT=$(python3 -m runner.reconcile 2>&1)
RECON_RC=$?
{
    echo "=== reconcile @ $TS ==="
    echo "rc: $RECON_RC"
    echo "$RECON_OUT"
} >> "$LOG"
if [ "$RECON_RC" -ne 0 ]; then
    echo "[reconcile] WARNING: reconcile exited rc=$RECON_RC (non-fatal, continuing tick)" >&2
fi

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <strategy_name> [strategy_name ...]" >&2
    exit 2
fi

# Run tick, capture both stdout & stderr. Tick is expected to exit 0 on
# normal ops including no-trade ticks.
TICK_OUT=$(./tick.sh "$@" 2>&1)
TICK_RC=$?

# Always log the full output so we can debug later.
{
    echo "=== cron_tick.sh @ $TS ==="
    echo "strategies: $*"
    echo "tick rc: $TICK_RC"
    echo "--- tick output ---"
    echo "$TICK_OUT"
    echo "=== end ==="
} >> "$LOG"

# --- Allocator paper-clock tracker (out-of-band; NO live orders) -------------
# Re-runs the validated inv-vol blend engine to the latest close and logs an
# idempotent daily snapshot to allocator_paper.db. Safe to run any day: the DB
# insert is keyed on the latest TRADING date, so a weekend/holiday run just
# re-confirms the last trading day's row (no double-insert). Non-fatal: a tracker
# failure is logged but never blocks or fails the tick.
ALLOC_OUT=$(python3 runner/allocator_paper_tracker.py 2>&1)
ALLOC_RC=$?
{
    echo "=== allocator_paper_tracker @ $TS (rc=$ALLOC_RC) ==="
    echo "$ALLOC_OUT"
    echo "=== end allocator_paper ==="
} >> "$LOG_DIR/allocator_paper.log"
if [ "$ALLOC_RC" -ne 0 ]; then
    echo "[allocator_paper] WARNING: tracker exited rc=$ALLOC_RC (non-fatal; see $LOG_DIR/allocator_paper.log)" >&2
fi

# Build the message body. Trade receipts first, errors second.
TRADE_LINES=$(echo "$TICK_OUT" | grep -E '^\[[^]]+\] (BUY|SELL) ' || true)
ERROR_LINES=$(echo "$TICK_OUT" | grep -E '^\[[^]]+\] ERROR:' || true)

POST=""
if [ -n "$TRADE_LINES" ]; then
    POST="$TRADE_LINES"
fi
if [ -n "$ERROR_LINES" ]; then
    if [ -n "$POST" ]; then
        POST="$POST"$'\n'"⚠️ errors:"$'\n'"$ERROR_LINES"
    else
        POST="⚠️ tick errors:"$'\n'"$ERROR_LINES"
    fi
fi

# Also surface a non-zero tick exit (rare; tick.sh normally swallows per-strategy
# failures into ERROR lines, so this catches catastrophic-bash failures).
if [ "$TICK_RC" -ne 0 ] && [ -z "$ERROR_LINES" ]; then
    if [ -n "$POST" ]; then
        POST="$POST"$'\n'"⚠️ tick.sh exited rc=$TICK_RC (no error lines)"
    else
        POST="⚠️ tick.sh exited rc=$TICK_RC (no error lines parsed; see $LOG)"
    fi
fi

if [ -z "$POST" ]; then
    # Quiet tick — exit silently, AGENTS.md "scroll-past, don't post."
    exit 0
fi

# Post via openclaw CLI. --json so we get a structured ack we can log.
SEND_OUT=$(openclaw message send \
    --channel discord \
    --target "$CHANNEL_ID" \
    --message "$POST" \
    --json 2>&1)
SEND_RC=$?

{
    echo "--- post rc: $SEND_RC ---"
    echo "$SEND_OUT"
    echo "=== posted ==="
} >> "$LOG"

exit "$SEND_RC"
