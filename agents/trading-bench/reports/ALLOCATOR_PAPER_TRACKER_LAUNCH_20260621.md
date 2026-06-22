# Allocator Paper-Clock Tracker — Launch Verification (2026-06-21)

**Status:** ✅ LIVE. Built, wired to the daily cron, seeded with today's first snapshot.

## What this is

An **out-of-band daily paper-clock tracker** (BACKLOG Path A) for the promoted
inv-vol allocator blend (TQQQ vol-target sleeve × sector-rotation top-2 sleeve,
inverse-vol 63d weighting). The blend cleared the gate on backtest
(full Sharpe **1.014** / OOS **1.147** / maxDD **−23.9%**, report:
`reports/ALLOCATOR_BLEND_20260621.md`) but **cannot be faithfully wired to the live
runner** — it's a continuously multi-asset-reweighted book and `runner.py` only
supports BUY-notional + CLOSE-to-flat per (strategy, symbol). Rather than fake-wire it
(dishonest model↔record divergence), this tracker re-runs the **validated** blend
engine to the latest close each day and logs the simulated daily P&L + target weights
to a side DB. **Zero live Alpaca orders.**

The rows this tracker writes from today forward = the honest forward paper clock
(out-of-sample, marked-at-close, no refit). Gate progress is measured on those rows.

## Files

- **`runner/allocator_paper_tracker.py`** — module + CLI. Reuses
  `_allocator_blend_tests.build_sleeves()` + `blend_portfolio()` **directly** (no sleeve-logic
  reimplementation), which themselves reuse the validated `run_backtest_voltarget` +
  `run_sector_rotation` engines. Idempotent per trading date.
- **`allocator_paper.db`** — side DB, table `daily_snapshots`
  `(id, date UNIQUE, w_tqqq, w_rot, rot_holds, daily_ret, cum_ret_since_start,
  spx_daily_ret, cum_spx_since_start, engine_full_sharpe, created_at)`.
- **`cron_tick.sh`** — one line added (see Cron wiring below).

## Today's first snapshot (mark_date = 2026-06-18, latest close)

| field | value |
|---|---|
| **w_tqqq** (TQQQ vol-target sleeve) | **0.442** (44.2%) |
| **w_rot** (rotation sleeve) | **0.558** (55.8%) |
| **rot_holds** | **SPY, QQQ** |
| decomposed target weights | TQQQ 0.1319 · SPY 0.279 · QQQ 0.279 · cash 31.0% |
| voltarget internal TQQQ weight | 0.30 |
| **daily_ret** (blend, on mark_date) | **+1.8936%** |
| **spx_daily_ret** (on mark_date) | **+1.0846%** |
| engine_full_sharpe (drift check) | **1.0144** ✅ (reproduces report's 1.014) |
| backtest window | 2010-02-12 → 2026-06-18 (4112 days) |

The decomposition: the TQQQ leg = `w_tqqq × voltarget_internal_w` = 0.442 × 0.30 ≈
0.1319; the rotation leg splits `w_rot` (0.558) equally across the current top-2 holds
(SPY, QQQ) → 0.279 each; remainder (31%) is the vol-target sleeve's cash.

## Since-inception paper-clock stats (1 day so far — expected)

```json
{
  "start_date": "2026-06-18",
  "n_days": 1,
  "cum_ret_pct": 1.8936,
  "spx_cum_ret_pct": 1.0846,
  "sharpe_since_start": 0.0,      // needs >=2 days; 0 by construction on day 1
  "current_w_tqqq": 0.442,
  "current_w_rot": 0.558,
  "current_rot_holds": ["SPY", "QQQ"]
}
```

`cum_ret_since_start` / `cum_spx_since_start` compound only over rows this tracker has
logged (paper-clock inception), NOT the full backtest equity. They will accumulate
honestly forward. `sharpe_since_start` is 0 on day 1 (needs ≥2 daily returns) and
becomes meaningful as rows accrue — it is the forward, out-of-sample Sharpe the gate
cares about, distinct from the backtest Sharpe.

## Cron wiring (confirmed)

Added to `cron_tick.sh` (after tick-output logging, before message-build / both exit
paths, so it runs on every tick):

```bash
ALLOC_OUT=$(python3 runner/allocator_paper_tracker.py 2>&1)
ALLOC_RC=$?
{ echo "=== allocator_paper_tracker @ $TS (rc=$ALLOC_RC) ==="; echo "$ALLOC_OUT"; echo "=== end allocator_paper ==="; } >> "$LOG_DIR/allocator_paper.log"
# non-fatal: a tracker failure is logged but never blocks/fails the tick
```

- **`cron_tick.sh` is the live dispatch** (crontab: `*/30 7-13 * * 1-5` → every 30 min,
  7am–1pm, **Mon–Fri only**). So the tracker naturally runs only on weekdays during
  market hours.
- **Idempotent / weekend-safe**: the DB insert is keyed on the latest TRADING date.
  The 13 intraday ticks/day just re-confirm the same row (`inserted=0`); only the first
  tick after a fresh close inserts. A weekend/holiday run (if ever invoked) re-fetches
  cached bars and skips the insert.
- **Non-fatal**: tracker errors are logged to `logs/allocator_paper.log` and never break
  the trading tick.

## Validation performed

- ✅ Module syntax clean; `bash -n cron_tick.sh` passes.
- ✅ Seed run: no errors, `allocator_paper.db` created, 1 row for 2026-06-18, all
  columns populated.
- ✅ **Engine drift check**: reproduces the report's full Sharpe **1.014** exactly →
  tracker calls the same validated engines, no silent divergence.
- ✅ **Idempotency**: re-run → `inserted=0`, `rows_logged=1`, row count stays 1.
- ✅ **`--stats` CLI** + importable `paper_clock_stats()` / `current_target_weights()`
  return all spec-required keys.
- ✅ **SPX-lag fix**: `^GSPC` cache lagged the tradeable ETFs by a day, which would have
  logged a spurious flat SPX return on day 1. Added a `_refresh_bars()` step
  (force-refresh ^GSPC/TQQQ/QQQ/SPY/GLD/TLT before computing, resilient to Yahoo
  hiccups) → SPX now correctly shows +1.0846% on mark_date (7500.58/7420.10−1).
- ✅ **Protected files untouched** (runner.py, backtest.py, risk.py, backtest_xsec.py —
  mtimes all pre-task). Only `runner/allocator_paper_tracker.py` + `cron_tick.sh` changed.

## Note / follow-up

The headline `engine_full_sharpe` (1.014) is the BACKTEST Sharpe and is the same
backtest already in the report — it is NOT new out-of-sample evidence; it's logged each
day only as a drift sentinel. The REAL evidence is the forward `daily_ret` rows
accumulating from today. Revisit `paper_clock_stats()` once ~20–40 trading days have
accrued to read the first meaningful forward Sharpe vs SPX.
