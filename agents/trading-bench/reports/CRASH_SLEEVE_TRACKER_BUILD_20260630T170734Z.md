# Crash-Sleeve (regime-gated) PAPER-CLOCK tracker — BUILD REPORT

**Date:** 2026-06-30 (UTC stamp 20260630T170734Z)
**Builder:** opus subagent (paper-research infra)
**Task:** Out-of-band forward paper clock for the regime-gated crash-insurance 3rd sleeve, mirroring `runner/allocator_paper_tracker.py` verbatim. Read-only, no live orders, side DB, no crontab edits.

---

## What was built

- **`runner/crash_sleeve_paper_tracker.py`** — the forward paper-clock tracker. Mirrors the allocator template's structure verbatim (module docstring, `_refresh_bars`, `compute_*_state`, `snapshot_today`, `paper_clock_stats`, `clock_staleness`, CLI with `--stats` / `--check-staleness` / default snapshot). Reuses `_allocator_blend_tests.build_sleeves()` + `blend_portfolio()` DIRECTLY — **zero sleeve-math reimplementation**.
- **`tests/test_crash_sleeve_paper_tracker.py`** — 17 unit tests (offline, deterministic), written **tests-first**.
- **`crash_sleeve_paper.db`** — side DB at workspace root, created via the one real snapshot run (1 forward row logged).

No other files touched. `_allocator_blend_tests.py`, `runner/allocator_paper_tracker.py`, the crontab, and all other `.db` files are unchanged.

## Config tracked (the conservative "value pick" — probe verdict GO-WITH-CAP)

Source probe: `reports/CRASH_SLEEVE_PROBE_20260630T164742Z.md`.

- **`HEDGE_WEIGHT = 0.15`** (wh15) — the report's explicitly-recommended conservative engaged weight (NOT the maximized wh25; the −10% threshold is fitted on n=1 OOS crash regime, so size conservatively).
- **`DD_TRIGGER_PCT = -0.10`** — SPX trailing-drawdown breach (depth gate). The SMA-200 trigger was REJECTED (didn't break the tradeoff); the −10%-DD gate did (~2.2 OOS-DD-pp per 100pp raw vs static-haven's ~1.49).
- **`HEDGE_INSTRUMENT = "CASH"`** — 0 return when engaged (cleanest de-risk). NOT the haven basket, NOT TLT (TLT rejected — deepens DD in rate-shock bears).
- Risk sleeves: SAME inv-vol(63d) + smooth_3mo (`WEIGHT_SMOOTH_MONTHS=3`) base weighting as the live 2-sleeve tracker, `BLEND_COST_BPS=2.0` (hedge on/off transitions pay turnover).

Backtest target this clock forward-tests: OOS maxDD −20.02% → **−18.84%**, raw 968% → 914% (−54pp), +1-bar canary CLEAN.

Each daily row logs the **GATED** 3-sleeve blend, the **UNGATED** 2-sleeve baseline, AND SPX — so we can measure forward, directly, whether the gate helps on new crash regimes the backtest couldn't fit.

## No-lookahead guard (verified)

Every weight decision at a month-open index `idx` uses ONLY `dates[:idx]` / `sleeves[k][:idx]` (blend_portfolio's hard past-only guard). The **regime flag at `idx`** is computed from an SPX price index reconstructed by compounding `spx_r`, with the running-peak drawdown evaluated through **`idx-1` (strictly before** the rebalance) — verbatim mirror of the probe's `build_dd_flags`. The cash sleeve return is identically `0.0`. The hedge weight chosen at `idx` is applied only to FORWARD returns. A future SPX move cannot change the current month's flag or weights. The probe's +1-bar canary proved the −10%-DD gate survives lagged information; this file implements the SAME past-only gate, with no same-bar peeking. A dedicated test (`test_regime_flags_past_only_*`) pins that a deep drop at index t does NOT flip the flag at any month-open ≤ t, and `test_regime_flags_extra_lag_shifts_one_more_bar` confirms `extra_lag=1` flips strictly one bar later (never earlier).

## DB schema (side DB `crash_sleeve_paper.db`)

`date` (UNIQUE), `regime_on`, `trailing_dd_pct`, `w_tqqq`, `w_rot`, `w_hedge`, `gated_daily_ret`, `cum_gated_since_start`, `baseline_daily_ret`, `cum_baseline_since_start`, `spx_daily_ret`, `cum_spx_since_start`, `engine_full_sharpe`, `created_at` (+ `id`). Idempotent on `date`; cum-since-start compounds 3 streams (gated / baseline / spx) from the paper-clock's first row forward.

## Tests

**17 new tests added**, all offline/deterministic (mirror the allocator/staleness convention — NO live engine call in unit tests; only the pure regime-gate, cum-compounding, and staleness helpers are exercised):

- regime gate is PAST-ONLY (deep drop at t doesn't flip flag at any month-open ≤ t; only after the DD is visible through idx-1); shallow drop below −10% never engages; +1-bar lag shifts strictly later.
- gated weights sum to 1 in both regime states; hedge exactly 0.0 when OFF and exactly 0.15 when ON; the two risk sleeves keep their inv-vol RATIO when the hedge engages.
- `snapshot_today` idempotent on date (2nd same-day call inserts 0 rows).
- 3-stream cum-since-start compounds correctly (fed synthetic daily rows, checked the product).
- `paper_clock_stats` reports all 3 cum streams + forward Sharpe + regime engage rate.
- staleness guard `trading_days_behind` / `stale` across current / 1-behind / 2-behind / holiday-gap / empty / unreadable-calendar (mirrors `test_allocator_paper_staleness.py` verbatim).

**Full suite result: `899 passed, 3 skipped`** (baseline was 882 passed / 3 skipped → exactly +17 new, zero regressions). 296 warnings are pre-existing `utcnow()` deprecations in unrelated modules.

## First real snapshot (end-to-end proof)

```
[crash_sleeve_paper] bar refresh: {"^GSPC": "2026-06-30", "TQQQ": "2026-06-30", "QQQ": "2026-06-30", "SPY": "2026-06-30", "GLD": "2026-06-30", "TLT": "2026-06-30"}
[crash_sleeve_paper] config: CASH hedge wh15 / DD-trigger -10% / invvol_63d_crashgated (probe reports/CRASH_SLEEVE_PROBE_20260630T164742Z.md)
[crash_sleeve_paper] mark_date=2026-06-30 inserted=1 rows_logged=1
[crash_sleeve_paper] staleness: current (last logged == latest closed SPX bar 2026-06-30)
[crash_sleeve_paper] REGIME: OFF (no hedge) | SPX trailing DD -2.23% (trigger -10%)
[crash_sleeve_paper] gated sleeve weights: TQQQ-voltarget 55.6% / rotation 44.4% / cash-hedge 0.0%
[crash_sleeve_paper] mark_date daily return: gated 1.3008% | baseline 1.3008% | SPX 0.7709%
[crash_sleeve_paper] cum since paper-clock start: gated 1.3008% | baseline 1.3008% | SPX 0.7709%
[crash_sleeve_paper] engine full backtest Sharpe (gated, drift check) = 1.044
[crash_sleeve_paper] backtest window ['2010-02-12', '2026-06-30'] (4119 days)
```

`--check-staleness` → `trading_days_behind: 0`, `stale: false`, **exit 0**. Second snapshot run → `inserted=0` (idempotent confirmed on the real DB).

**Sanity:** regime OFF today (SPX trailing DD −2.23%, well above −10% — markets near highs, as expected). w_hedge 0.0% when OFF. Gated daily == baseline daily (1.3008%) — correct: with the gate OFF the 3-sleeve book is identical to the ungated 2-sleeve baseline, which validates the wiring.

## Hard rails — confirmed clean

- **Protected files md5 UNCHANGED:** runner `0f763975` · risk `e303317e` · backtest `717c36e6` · backtest_xsec `d8927364` · walk_forward_xsec `8c3df32c` · safety_backstop `bccefaba` — all 6 match.
- Did NOT edit `_allocator_blend_tests.py`, `runner/allocator_paper_tracker.py`, the crontab, or any other `.db`. Crontab has 0 crash_sleeve lines (parent wires it).
- Created exactly: `runner/crash_sleeve_paper_tracker.py`, `tests/test_crash_sleeve_paper_tracker.py`, `crash_sleeve_paper.db`.

## Deviations from spec

None material. Note: `compute_crash_sleeve_state` returns a fresh dict per call (as the template does); the idempotency unit test uses `side_effect` rather than `return_value` to mirror that fresh-dict semantics (a shared mutable return_value would alias one dict across both calls). This matches real runtime behavior — no production code change implied.
