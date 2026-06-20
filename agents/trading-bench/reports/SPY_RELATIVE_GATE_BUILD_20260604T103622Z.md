# SPY-Relative Gate Metric — First-Class Reporting Build

**UTC:** 2026-06-04T10:36:22Z
**Build subagent:** build-spy-relative-gate
**BACKLOG item:** P1 — "Add beat-SPY-risk-adjusted as a FIRST-CLASS gate metric."

## Why

Tonight's 9 research lanes were all (correctly) rejected partly on "below passive
SPX risk-adjusted." But that SPY comparison was computed **ad-hoc** inside each
throwaway driver. This build makes it **mechanical**: every walk-forward candidate
now automatically reports its SPY-relative annualized excess return AND information
ratio, alongside the existing Sharpe/FP output. **Reporting only — not a binding
gate** (that's a separate future decision for Cyrus/main).

## What was added

### New module: `runner/spy_relative.py`
Pure helper, no I/O, well-documented. Public API:
- `spy_relative_metrics(strategy_returns, spy_returns, *, timeframe, is_crypto=False)`
  → dict with `strategy_ann_return`, `spy_ann_return`, `excess_return_annualized`,
  `information_ratio` (None when undefined), `n_periods`.
- `information_ratio(strategy_returns, spy_returns, bars_per_yr)` → float | None.
- `annualized_return(per_period_returns, bars_per_yr)` → geometric/compounded ann return.
- `returns_from_closes(closes)` → close-to-close simple returns.
- `align_returns_by_date(strategy_by_date, spy_by_date)` → aligned arrays on common
  dates, chronological, **no lookahead** (pure set-intersection of realized returns).

### IR formula + annualization choice
```
excess_i = strategy_i − spy_i                          (per period, aligned by date)
IR = mean(excess) / stdev_sample(excess) * sqrt(bars_per_year)
excess_return_annualized = ann(strategy) − ann(spy)
ann(r) = prod(1 + r_i)^(bars_per_year / n) − 1         (geometric/compounded)
```
- **Annualization uses the harness's own `bars_per_year(timeframe, is_crypto)`**
  imported from `runner.backtest`. **NOT** hardcoded `sqrt(252)` — intraday timeframes
  and crypto would otherwise be mis-annualized. (1Day equities → 252; verified in tests.)
- IR uses **sample** stdev (ddof=1), matching backtest.py's Sharpe convention
  (var divides by len−1), so IR and Sharpe sit on the same statistical footing.

### Edge cases handled
- **Zero / near-zero tracking error** (strategy tracks SPY exactly, or any
  constant-additive-excess series) → IR is **None** (no divide-by-zero / inf).
- **< 2 aligned periods** → sample stdev undefined → IR **None**.
- **Empty or length-mismatched series** → **ValueError** (loud — caller bug).
- **No overlapping dates** in `align_returns_by_date` → **ValueError**.
- Growth factor going non-positive (a −100%+ wipeout) is floored at −100% so we never
  take a root of a negative number.

## Wiring (REPORTING-ONLY, additive)

Both sites are non-protected (already edited tonight for the $1000 notional bump).
**No pass/fail logic, gate decision, or existing metric/field was changed, removed,
or renamed.** Strictly additive output.

### `runner/walk_forward.py`
- Strategy per-period returns from `BacktestResult.equity_curve` (the same equity-return
  series the harness already uses for Sharpe), keyed by bar timestamp.
- SPY buy-and-hold per-period returns from `bars_cache.get_bars('SPY', timeframe, days, end_dt)`
  close-to-close, same window → **no lookahead**. Aligned by date.
- New `WindowResult` fields: `spy_excess_ann_return`, `spy_information_ratio`,
  `spy_rel_n_periods`; new aggregate medians; surfaced in the per-strategy MD table
  (2 new columns), the `**SPY-relative ...**` aggregate line, the CLI stderr summary
  (`spyExcessAnn=`, `medIR=`), and the JSON dump.
- Best-effort: any data shortfall degrades to excess=0/IR=None — it can **never** break
  the walk-forward run or any gate.

### `runner/walk_forward_xsec.py`
- Per-tick portfolio equity returns from `XSecBacktestResult.equity_curve`, keyed by the
  tick clock (`build_clock(bars_by_sym)`), aligned to SPY by calendar date (YYYY-MM-DD).
- Same additive fields, MD columns, aggregate line, stderr summary, and JSON keys.

## Files touched
- **NEW** `runner/spy_relative.py`
- **NEW** `tests/test_spy_relative.py`
- `runner/walk_forward.py`  (reporting wiring only)
- `runner/walk_forward_xsec.py`  (reporting wiring only)

## Tests
- New `tests/test_spy_relative.py`: 13 pinning tests — identical-to-SPY (excess≈0, IR=None
  for zero TE), constant additive excess (positive excess, IR undefined), near-constant
  excess (very high finite IR), zero-TE→None, length-mismatch/empty→ValueError, single
  period→None, **hand-computed IR pinned to 6.480740698** (3–4 period example), hand-computed
  annualized excess, `returns_from_closes`, `align_returns_by_date` intersection/order,
  no-common-dates→ValueError, and an intraday-vs-daily annualization scaling check (proves
  we did NOT hardcode sqrt(252)).
- **Full suite: 289 → 302 passed (+13). Green.**
- `tests/test_walk_forward.py` + `tests/test_walk_forward_xsec.py` (the two wired sites):
  33 passed.
- Live smoke: `python3 -m runner.walk_forward --strategy breakout_xlk` emitted
  `spyExcessAnn=-128.27% medIR=-3.11` end-to-end on real data — confirming the low-exposure
  ($100 notional / $1000 equity) strategy transparently trails SPY risk-adjusted, exactly the
  signal this metric is meant to surface.

## Protected files — md5 verified UNCHANGED at finish
```
4be185e4bdcb6f432d99b71b21a4859c  runner/runner.py
9444ee5be64d9fd2639fd8cb0a28e002  runner/backtest.py
2278a4c8d8a66703da5cd6f2a0880061  runner/backtest_xsec.py
e4c227e019c99e7e52224eb2f91389b8  runner/risk.py
```
All four match the expected hashes. No protected file was edited.
