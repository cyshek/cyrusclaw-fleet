# Connors RSI(2) on SPY — Walk-Forward Report

**Date:** 2026-05-27
**Candidate:** `strategies_candidates/connors_rsi2_spy/`
**Author:** trading-bench subagent (coach call fork 1: Connors RSI(2) port)
**Status:** 🔴 **FAILED FITNESS GATE — DO NOT PROMOTE**
**Sibling history:** Follows the failed `RSI_MEAN_REVERT_STOCK_PORT.md`
(rsi_mean_revert_eth port to SPY 1Day, 2026-05-27 late). Same
pre-registration discipline; same disposition.

---

## TL;DR

Built the canonical Connors RSI(2) strategy on SPY 1Day per pre-registered
spec (200-SMA regime filter + RSI(2)<10 entry + SMA(5) exit, no stops). Ran
the standard 8-window walk-forward once. **Zero trades fired across all 8
windows** because the walk-forward harness provides only the in-window bars
(41–63 bars per 60–90-day window) with no warmup prefix, so `sma(closes,
200)` returns `None` for every bar and the entry leg is blocked everywhere.

Gate FAIL, three of three binding criteria miss. Per pre-registration: no
tuning, no QQQ fallback, no harness modification. The candidate stays in
quarantine and is not promoted.

**The finding is not "Connors RSI(2) has no edge on SPY."** The finding is
**"the bench's walk-forward harness cannot evaluate strategies whose
indicators need >~60 bars of history."** That's an infra-quality issue, not
a strategy-quality issue, and is the correct next-step work for the
post-Saturday moratorium window per `HANDOFF.md`.

---

## Symbol decision (pre-registered before any code)

**SPY** chosen over QQQ. One-line rationale (full version in
`strategies_candidates/connors_rsi2_spy/NOTES.md`):

> SPY is Connors's own canonical test vehicle and the symbol his
> published edge claims attach to; QQQ would conflate the 200-SMA
> regime filter with Mag-7 drift and bias the test toward whichever
> regime tech happened to be in.

This decision was locked **before** running any backtest. The brief
explicitly forbids testing both and picking the winner — that's
lookahead in disguise. SPY-fail does not become QQQ-attempt.

---

## Pre-registered acceptance gate

`runner.walk_forward.passes_fitness_gate(agg)` must return `(True, ...)`.
Specifically:

| Criterion | Threshold | Post-cost |
|---|---|---|
| Median return | > 0.00% | ✅ required |
| % windows positive | ≥ 50% | ✅ required |
| % beat BH-SPY | ≥ 50% | ✅ required |
| Median Sharpe | > 0.50 | ✅ required |

Cost model: `CostModel.alpaca_stocks()` → `spread_bps=2.0, fee_bps=0.0`
(~4bps round-trip). Same cost model used for every other stock strategy
in the bench.

---

## The canonical strategy (as built, unmodified)

```
Universe: SPY (single symbol)
Timeframe: 1Day bars
Entry (all must be true):
  - close > SMA(close, 200)         ← long-term uptrend regime
  - RSI(close, 2) < 10              ← extreme short-term oversold
Exit:
  - close > SMA(close, 5)           ← short-term mean-reversion done
Position: $100 notional (capped by runner risk module)
No stops, no cooldowns, no additional filters.
```

`decide()` implementation in
`strategies_candidates/connors_rsi2_spy/strategy.py`. Uses `closes`,
`rsi`, and `sma` from `strategies/_lib/indicators.py` unchanged.

Synthetic-input smoke test passed all 5 cases (empty bars, insufficient
history, uptrend+dip → buy gated by RSI, downtrend → regime off, holding
+ short-term pop → close).

---

## Warmup-bars limitation (THE KEY FINDING — read this first)

The walk-forward harness calls:

```python
bars_cache.get_bars(symbol, timeframe, days=days, end_dt=end_dt)
```

with `days=90` for 7 of 8 windows and `days=60` for the 2026-recent
window. A 90-day calendar window contains ~61 trading-day SPY 1Day bars;
a 60-day window contains ~41 bars. **No warmup prefix is added by the
harness or the backtester.**

I verified this directly:

```
$ python3 -c "from runner import bars_cache; from datetime import datetime, timezone; \
              bars = bars_cache.get_bars('SPY','1Day',days=90,end_dt=datetime(2022,7,1,tzinfo=timezone.utc)); \
              print(len(bars), bars[0]['t'], bars[-1]['t'])"
61 2022-04-04T04:00:00Z 2022-06-30T04:00:00Z
```

Connors RSI(2) needs 200 prior closes for SMA(200). With ≤61 bars
available per window, `sma(closes, 200)` returns `None` for **every bar
in every window**. The entry leg `decide()` therefore returns `HOLD`
universally, and the strategy never trades.

This is exactly the failure mode the brief flagged in advance
("THIS IS THE MOST LIKELY FAILURE MODE OF THIS TASK"). Per the brief's
option (b) I documented the issue, ran anyway with the partial-data
caveat, and flagged it here.

**Why I didn't work around it:**

1. Modifying `runner/walk_forward.py` to inject warmup bars is **out of
   write scope** per the brief.
2. Having the strategy self-fetch warmup inside `decide()` via
   `bars_cache.get_bars` would (a) break backtest/live contract symmetry,
   (b) silently fudge the pre-registered test, and (c) constitute
   "Connors RSI(2) with my improvements" — the exact variant-invention
   the brief explicitly forbids.
3. Testing QQQ instead would fail identically (same harness, same
   bar count) AND violate the "no variant-shopping" rule.
4. Pre-registration discipline is more valuable than a comforting number.
   If the harness can't fairly evaluate this strategy, the honest
   finding is "the harness can't fairly evaluate this strategy."

---

## Walk-forward results (8 named regime windows)

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear        | bear | 61 | 0 | +0.00 | 0.00 | 0.00 | -1.74 | ✅ |
| 2022-Q3 chop        | chop | 63 | 0 | +0.00 | 0.00 | 0.00 | -0.65 | ✅ |
| 2023-H1 recovery    | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.74 | ❌ |
| 2023-Q3 chop        | chop | 63 | 0 | +0.00 | 0.00 | 0.00 | -0.38 | ✅ |
| 2024-Q2 bull        | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 62 | 0 | +0.00 | 0.00 | 0.00 | -0.80 | ✅ |
| 2025-Q3 bull        | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.65 | ❌ |
| 2026-recent bull    | bull | 41 | 0 | +0.00 | 0.00 | 0.00 | +1.55 | ❌ |

**Aggregate**
- Median return: **+0.00%**
- % windows positive: **0%**
- % windows beat BH-SPY: 50% (a denominator artifact: in 4/8 windows
  SPY was negative and our flat strategy "beat" it by not trading)
- Median Sharpe: 0.00
- Total trades across all windows: **0**

---

## Fitness gate: 🔴 FAIL

`runner.walk_forward.passes_fitness_gate(agg) → (False, ...)`

Failure reasons (each individually disqualifying):
1. **Median return +0.00% ≤ +0.00%** (gate requires strictly > 0).
2. **0% of windows positive** (gate requires ≥ 50%).
3. **Median Sharpe 0.00 ≤ 0.50** (gate requires > 0.5).

The `% beat BH-SPY = 50%` is the only metric that clears its threshold,
and it clears it for the wrong reason: the strategy doesn't trade, so in
windows where SPY went down, "0% return beats -0.8%" by definition.
That's lack of exposure, not edge — identical to the same artifact in
the previous `rsi_mean_revert_spy` port.

---

## Failure-mechanism analysis

**One mechanism, full stop:** the SMA(200) regime filter cannot be
computed from a 41–63-bar input window, so the entry condition is
permanently false and `decide()` returns `HOLD` on every bar. Zero
entries → zero exits → zero P&L → fail on median, %positive, and
Sharpe simultaneously.

This is NOT "RSI(2)<10 never fires" — RSI(2)<10 is actually quite
frequent (canonically fires several times per 60-day window on SPY).
We just never get a chance to check it because the prior condition
`close > SMA(200)` returns `None > something → False` for every bar.
(Strictly: my implementation short-circuits on `sma200 is None` with a
HOLD-with-reason, so we don't even evaluate RSI in that case — but
either way, no entry.)

This is distinct from the previous RSI-mean-revert port failure, which
was a *strategy* failure (the few trades that did fire all lost money).
This is a *harness* failure: the strategy doesn't get to demonstrate
anything because the harness's eval window is shorter than the
strategy's indicator warmup requirement.

---

## Honest read

**This strategy should not be promoted.** Reasons:

1. **It fails the pre-registered gate on three of three criteria.** Per
   the brief, that's a hard stop. No tuning, no symbol swap.

2. **The result tells us almost nothing about Connors RSI(2)'s edge on
   SPY.** It tells us instead that the bench's walk-forward harness is
   structurally incompatible with long-warmup strategies. The honest
   interpretation is "untested," not "no edge."

3. **The failure mode was foreseeable and was foreseen.** The brief
   itself flagged it. That doesn't make it less of a fail — the gate is
   a binary contract, not a graded one — but it does change what we
   should *do* about it.

4. **The Saturday-moratorium directive in HANDOFF.md fits this exactly.**
   The right next step is NOT another strategy attempt; it's
   harness-quality work (specifically: a `warmup_days` or
   `warmup_bars` parameter on `walk_forward()` that fetches an
   indicator-prefix before the window starts, kept out of the
   strategy-visible bars for fairness measurement).

   That work IS in scope for the post-Saturday infra-quality window
   per the standing moratorium. It is NOT in scope for me in this task.

---

## Recommendation to parent (Tessera-main)

**Do not promote.** Do not add to `GATE_PASSING_PARENTS`. Do not deploy.

Per the coach call's pre-registered decision rule:
- ❌ Pass standalone gate → would have added to pool + queued 2
  directives. **N/A — failed.**
- ❌ Fail standalone gate → 11 honest attempts, 0 hits. Stop building,
  accept soak, revisit after Saturday's leaderboard.

The pre-registered branch fires: **stop strategy building until
Saturday's leaderboard.** The 3-day timebox is honored; this came in
well under 4 hours from spawn. The post-build moratorium engages
regardless of outcome and is honored as written.

Whether the warmup-bars finding constitutes a "12th hit" depends on
interpretation. My honest read: it's not a strategy attempt at all in
the bench's existing terms; it's a discovered infra limitation. The
tally remains 11 strategy attempts → 0 promotions, plus 1
discovered-blocker. Up to main to decide how to count it. Either way,
the moratorium activates.

---

## Suggested follow-ups for the moratorium / post-Saturday window

Not in scope for me to ship — surfacing in case main wants to schedule.

1. **Add `warmup_days` to `walk_forward()`.** Fetch `days + warmup_days`
   bars, pass the full series to `backtest()`, but have `backtest()`
   only START EVALUATING METRICS from bar index `warmup_days`. The
   strategy sees the full prefix in `market_state["bars"]` from the
   first metric-eligible bar onward, so all indicators are warm.
   Re-run this candidate with `warmup_days=250` (or `warmup_bars`
   = `regime_sma_period + 50`) and see if the real Connors edge
   appears.

2. **Audit all live strategies for warmup-vs-window assumptions.** Any
   strategy in `strategies/` whose indicators look back >60 bars is
   probably under-evaluated by current walk-forward and may have a
   different real fitness than the harness suggests. (Most current
   live strategies are short-warmup — SMA/RSI 14/20, breakouts 20 —
   so this is largely a "future-proof the harness" concern, not a
   "current strategies are wrong" concern. But worth confirming.)

3. **Document the harness contract.** `runner/walk_forward.py` does not
   currently say in its module docstring what warmup it provides
   (none). A future strategy author (human or LLM) will repeat my
   mistake. One-paragraph addition would prevent it.

---

## Verification

- ✅ `python3 -m pytest tests/ -q` → **107 passed** (unchanged from
  pre-work baseline; no `strategies/`, `runner/`, `_lib/`,
  `tournament_loop`, `strategy_gen`, or cron files touched).
- ✅ Candidate dir on disk:
  ```
  strategies_candidates/connors_rsi2_spy/
    NOTES.md                 # port reasoning, pre-registration, warmup caveat
    __init__.py              # empty (package marker)
    params.json              # canonical Connors params, no tuning
    strategy.py              # decide() implementing the canonical formulation
    walk_forward_result.json # raw per-window numbers from the actual run
  ```
- ✅ `walk_forward_result.json` is a real run artifact, not a paraphrase
  — generated by `_wf_connors_rsi2.py` against the real
  `runner/backtest.py` + `runner/walk_forward.py` + `CostModel.alpaca_stocks()`.
- ✅ Write scope honored: `strategies/`, `runner/`,
  `runner/walk_forward.py`, `runner/strategy_gen.py`,
  `GATE_PASSING_PARENTS`, `strategies/_lib/`, cron, and all other
  candidates untouched.
- ✅ No tuning. No QQQ attempt. No second run. Single canonical-params
  walk-forward, result accepted as-is.

## Artifacts

- `strategies_candidates/connors_rsi2_spy/strategy.py`
- `strategies_candidates/connors_rsi2_spy/params.json`
- `strategies_candidates/connors_rsi2_spy/__init__.py`
- `strategies_candidates/connors_rsi2_spy/NOTES.md`
- `strategies_candidates/connors_rsi2_spy/walk_forward_result.json`
- `_wf_connors_rsi2.py` (workspace root, one-shot runner script, repeatable)
