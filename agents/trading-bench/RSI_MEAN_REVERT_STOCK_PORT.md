# RSI Mean-Revert Stock Port — Walk-Forward Report

**Date:** 2026-05-27
**Candidate:** `strategies_candidates/rsi_mean_revert_spy/`
**Author:** trading-bench subagent (fork 1 of design discussion with main)
**Status:** 🔴 **FAILED FITNESS GATE — DO NOT PROMOTE**

---

## Pre-registered port decisions

All choices made BEFORE running any backtest (see
`strategies_candidates/rsi_mean_revert_spy/NOTES.md` for full reasoning):

| Decision | Choice | Reasoning (one-liner) |
|---|---|---|
| Symbol | **SPY** | Canonical academic dip-buy target; deepest IEX history; comparable to BH-SPY bench |
| Timeframe | **1Day** | Avoids RTH overnight-gap contamination of rolling RSI; matches published mean-rev literature |
| RSI buy threshold | **< 30** | Direct port from crypto parent; canonical Wilder oversold |
| RSI exit threshold | **> 55** | Direct port from crypto parent (asymmetric for faster exits on mean-reversion) |
| RSI period | **14** | Direct port from crypto parent (Wilder default) |

**Cost model:** `CostModel.alpaca_stocks()` (`spread_bps=2.0, fee_bps=0.0`) — applied to every fill.

**No tuning was performed.** Single run, single set of thresholds, pre-registered.

---

## Walk-forward results (8 named regime windows)

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 61 | 1 | **-1.20** | -2.33 | -1.48 | -1.74 | ✅ |
| 2022-Q3 chop | chop | 63 | 1 | **-0.30** | -2.13 | -0.36 | -0.65 | ✅ |
| 2023-H1 recovery | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.74 | ❌ |
| 2023-Q3 chop | chop | 63 | 0 | +0.00 | 0.00 | 0.00 | -0.38 | ✅ |
| 2024-Q2 bull | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 62 | 1 | **-0.12** | -0.20 | -1.40 | -0.80 | ✅ |
| 2025-Q3 bull | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.65 | ❌ |
| 2026-recent bull | bull | 41 | 0 | +0.00 | 0.00 | 0.00 | +1.55 | ❌ |

**Aggregate**
- Median return: **+0.00%**
- % windows positive: **0%**
- % windows beat BH-SPY: 50%
- Median Sharpe: 0.00
- Worst window: -1.20% (2022-H1 bear)
- Best window: +0.00% (5-way tie — strategy was flat in 5/8 windows)
- Total trades across all windows: **3** (all losses)

---

## Fitness gate: 🔴 FAIL

`runner.walk_forward.passes_fitness_gate(agg) → (False, ...)`

Failure reasons (multiple, each individually disqualifying):
1. **Median return +0.00% ≤ +0.00%** (gate requires strictly >0).
2. **0% of windows positive** (gate requires ≥50%).
3. **Median Sharpe 0.00 ≤ 0.50** (gate requires >0.5).

The `% beat BH-SPY = 50%` line is the only metric that clears its threshold,
and it does so for the wrong reason: in 4 of 8 windows the strategy didn't
trade at all and SPY was negative, so "0% beats negative" counts as a win.
That's a denominator artifact, not edge.

---

## Loss-mechanism analysis

Two pathologies, working together:

### 1. Signal sparsity — RSI(14) < 30 on SPY 1Day almost never fires

In 5 of 8 windows the strategy generated **zero entries**. RSI(14)<30 on
SPY daily bars is rare (≈2-5% of trading days historically) and our
90-day windows often contain none. This is exactly what we'd expect:
since 2010 the SPY drift has been positive and deep RSI oversold readings
cluster around shock events (Mar 2020, Q4 2018, 2022 H1). Our window
panel only hits the 2022 H1 / Q3 and 2025 Q1 episodes; the rest of the
panel is too benign for RSI<30 to trigger.

A strategy that doesn't trade can't make money. Conditional return
*given a trade* would be a much smaller-n statistic — only 3 entries
across the full 8-window panel.

### 2. The 3 trades it did take all lost money

| Window | Entry context | Outcome |
|---|---|---|
| 2022-H1 bear  | RSI<30 fired into the *middle* of the bear leg | -1.20% (entered too early, RSI never recovered above 55) |
| 2022-Q3 chop  | RSI<30 fired during the August-September leg down | -0.30% (held into further decline) |
| 2025-Q1 tariff bear | RSI<30 fired into the tariff-news selloff | -0.12% (similar story; tape kept selling) |

The common failure mode: **on stocks, deep RSI oversold readings are
serial-autocorrelated with continued downside.** Equity bear markets
don't bounce on the first oversold reading the way crypto often does;
they exhibit "oversold can stay oversold" behavior driven by macro
flows. The parent crypto strategy works in part because crypto's
funding-driven liquidations create sharp V-bottoms; SPY 1Day has no
analog.

The strategy's exit_above=55 also means once an entry is held into
further weakness, the position drifts down without a stop and only
exits when RSI eventually recovers to 55 — which can be much lower
on the price axis (-1.4% MaxDD on a -0.12% net return in the 2025-Q1
window tells that story: round-tripped a ~1.4% drawdown to net ~0).

### 3. Why the crypto parent works (and the stock port doesn't)

The ETH version operates on 1Hour bars where mean-reversion happens
on a 4-8-hour timescale aligned with retail-flow rebalancing. SPY 1Day
operates on a daily timescale where macro-flow dominates and RSI<30
is a *trend-acceleration* signal more often than a *reversion* signal.
Same indicator, different statistical population, different sign of edge.

---

## Honest read

**This strategy should not be promoted.** Reasons, in priority order:

1. **It fails the pre-registered acceptance gate** on all three of its
   binding criteria (median, %positive, Sharpe). Per the directive,
   that's a hard stop.

2. **The underlying hypothesis is statistically wrong on this venue.**
   It's not "needs better thresholds" or "needs a regime filter" — it's
   "deep-RSI-oversold on SPY 1Day is not a positive-expectancy entry
   point in the 2022-2026 sample." Tuning thresholds would be
   overfitting to the same windows used to judge pass/fail.

3. **Adding it to `GATE_PASSING_PARENTS` would actively harm the
   mutation pipeline.** The point of broadening the parent pool was to
   give directive #16 (post-loss cooldown) a parent it can engage with.
   But a parent that loses on 3/3 trades isn't a useful mutation
   substrate — every mutant inherits the broken signal hypothesis.

## Recommendation to parent

**Do not promote.** Do not add to `GATE_PASSING_PARENTS`. Do not deploy.

Consider for fork 3 (write better human strategies):
- **Try a different mean-reversion formulation:** Connors-style RSI(2)
  on daily SPY (much higher signal frequency, different statistics)
  or 5-bar lowest-low on a 1Hour QQQ/SPY (intraday mean reversion is
  better-documented in equity literature than daily-RSI).
- **Try a different symbol:** XLP/XLU (defensive, do mean-revert on
  daily bars per published research) or single defensive names
  (PEP, JNJ). These weren't tested here because the brief was "one
  port, one shot, no tuning."
- **Consider whether the bench has a mean-reversion-shaped problem at
  all.** The 8-window panel is regime-balanced but skewed toward
  trending episodes (5 bull/bear of 8 windows); mean-reverters
  structurally underperform in trending tape. A purpose-built
  mean-reversion bench (chop-heavy window panel) might be needed to
  fairly evaluate this strategy family.

## Verification

- ✅ `python3 -m pytest tests/ -q` → **107 passed** (unchanged from
  pre-work baseline).
- ✅ Candidate dir exists: `strategies_candidates/rsi_mean_revert_spy/`
  contains `strategy.py`, `params.json`, `__init__.py`, `NOTES.md`,
  `walk_forward_result.json` (raw per-window numbers).
- ✅ All numbers in this report come from `_wf_rsi_spy.py` against the
  real `runner/backtest.py` + `runner/walk_forward.py` + Alpaca-stocks
  `CostModel`. No estimates.
- ✅ Write scope honored: `strategies/`, `runner/`, `GATE_PASSING_PARENTS`,
  cron, `runner/strategy_gen.py`, `runner/walk_forward.py` all untouched.

## Artifacts

- `strategies_candidates/rsi_mean_revert_spy/strategy.py`
- `strategies_candidates/rsi_mean_revert_spy/params.json`
- `strategies_candidates/rsi_mean_revert_spy/__init__.py`
- `strategies_candidates/rsi_mean_revert_spy/NOTES.md` (port reasoning)
- `strategies_candidates/rsi_mean_revert_spy/walk_forward_result.json` (raw)
- `_wf_rsi_spy.py` (one-shot runner script, repeatable)
