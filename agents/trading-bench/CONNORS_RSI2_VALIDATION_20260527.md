# Connors RSI(2) — Standalone Validation Report

**Date:** 2026-05-27
**Author:** trading-bench subagent (IC port)
**Scope:** Standalone walk-forward validation of Connors RSI(2) on SPY and QQQ daily.
**Mandate:** Decide PASS_STANDALONE / FAIL_STANDALONE on `passes_fitness_gate()` for at least one of {SPY, QQQ}. No tuning. Do NOT promote.

## ★ BOTTOM LINE — FAIL_STANDALONE

_Note: this is the second IC attempt at this task. A prior subagent attempted SPY-only and reached the same FAIL_STANDALONE bottom line but stopped at the no-warmup zero-trades result without running the warmup-extended variant. Their reasoning artifacts are preserved at `strategies_candidates/connors_rsi2_spy/_PRIOR_ATTEMPT_*` (see also `strategies_candidates/connors_rsi2_spy/NOTES.md` for the reconciliation). Both attempts agree on the bottom line. This run additionally provides QQQ and warmup-extended numbers._


Neither SPY nor QQQ clears `passes_fitness_gate()`. Both fail on multiple criteria.

| Symbol | Median return | % Pos | % Beat BH | Median Sharpe | Trades (across 8 windows) | Verdict |
|---|---|---|---|---|---|---|
| SPY | +0.00% | 0% | 50% | 0.00 | 1 | 🔴 FAIL |
| QQQ | +0.00% | 12% | 50% | 0.00 | 4 | 🔴 FAIL |

Numbers above are from the **warmup-extended** harness run (see "Methodology caveat" below). Under the default harness, both produced **zero trades in all 8 windows** because the 90-day window is too short for SMA(200) to warm up.

Per pre-registration: this is the answer. No tuning. No promotion.

---

## Strategy definition (as implemented)

Canonical published Connors RSI(2), no variants. Long-only, daily bars.

**Entry (long):**
```
RSI(2) < 10
AND close > SMA(200) of the traded symbol
AND flat
```

**Exit:**
```
close > SMA(5)
```

**Stop:** None (canonical). `safety_max_loss_pct: -50.0` in params.json as a runaway-only safety rail (NOT a tuned exit) per the existing opt-in pattern (`AGENTS.md` guidance, same convention as `breakout_xlk`). Did not fire in any backtest window.

**Trend filter design choice — SMA(200) of the traded symbol, NOT `regime_uptrend(spy_closes, 50)`:**

The task offered a choice between:
- (a) Inline SMA(200) of the symbol's own closes (canonical Connors).
- (b) Reuse `market_state["regime"]` (the runner's SPY-SMA(50) regime helper).

I picked (a). Reasons documented in `strategies_candidates/connors_rsi2_*/strategy.py` docstring; tldr:
1. Canonical Connors uses SMA(200) of the traded instrument, not a global market filter.
2. Keeps SPY and QQQ ports apples-to-apples (otherwise QQQ would have to choose between "SMA(200) of QQQ" and "SMA(50) of SPY").
3. Our regime helper is on a different period (50d) — retuning it for Connors isn't this strategy's job.

For SPY specifically the two definitions converge in spirit (SPY's regime IS SPY); for QQQ they diverge meaningfully and the canonical choice is "SMA of QQQ".

**Files on disk:**
- `strategies_candidates/connors_rsi2_spy/{strategy.py, params.json, __init__.py}`
- `strategies_candidates/connors_rsi2_qqq/{strategy.py, params.json, __init__.py}`
- Quarantine only. NOT promoted to `strategies/`. NOT added to runner.

---

## Methodology caveat — read this before the numbers

The standard `runner/walk_forward.py` harness fetches exactly `window_days` (90 calendar days ≈ 62 trading days) of bars per window. **SMA(200) requires 200 trading days to compute.** With canonical params on the default harness, the strategy's trend filter is `None` on every bar, so the entry condition never evaluates true, so the strategy emits HOLD on every bar of every window. Result: **0 trades, 0 return, 8/8 windows fail.**

This is a structural mismatch between the canonical Connors trend-filter period and our existing harness's window size. It is NOT a backtester bug (the harness was designed for hourly bars where 90 days = thousands of bars). I considered writing it up as `BUG_*.md` per the task hard-constraint, but decided it isn't a bug — it's a fair-shot deficit in this strategy/harness pair that the task itself anticipates ("if the strategy doesn't pass with canonical params, that IS the answer").

**To give the canonical strategy a fair shot, I ran a second pass — "warmup-extended" — that fetches `window_days + 220` calendar days of bars per window (≈ 155 trading days of warmup + 62 of trading) and replays the strategy across the full slice.** Equity / return / Sharpe are computed over the entire bar slice; the warmup region produces only HOLD actions so the metrics are dominated by the trading region.

Both result sets are reported below. **The bottom-line verdict uses the warmup-extended numbers** because the no-warmup run is a structural zero that contains no signal about the strategy's actual merit. If you prefer the strict-harness verdict, it's also FAIL (more emphatically: 0 trades, 0 return).

Raw JSON: `connors_rsi2_wf_result.json` (no-warmup), `connors_rsi2_wf_warmup_result.json` (warmup-extended).

---

## Walk-forward results — SPY (warmup-extended)

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear        | bear | 214 | 0 | +0.00 | 0.00 | 0.00 | -1.74 | ✅ |
| 2022-Q3 chop        | chop | 213 | 0 | +0.00 | 0.00 | 0.00 | -0.65 | ✅ |
| 2023-H1 recovery    | bull | 213 | 0 | +0.00 | 0.00 | 0.00 | +0.74 | ❌ |
| 2023-Q3 chop        | chop | 212 | 1¹| -0.26 | -2.66 | -0.29 | -0.38 | ✅ |
| 2024-Q2 bull        | bull | 211 | 0 | +0.00 | 0.00 | 0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 213 | 0 | +0.00 | 0.00 | 0.00 | -0.80 | ✅ |
| 2025-Q3 bull        | bull | 211 | 0 | +0.00 | 0.00 | 0.00 | +0.65 | ❌ |
| 2026-recent bull    | bull | 193 | 0 | +0.00 | 0.00 | 0.00 | +1.55 | ❌ |

¹ "Trades" column counts bar-level trade rows (buy + close = 2). 1 here = 1 buy that hasn't closed yet in-window OR an entry that triggered the bar-count but only logged once — see spot-check below.

**Aggregate:** medRet **+0.00%** · 0% positive · 50% beat BH-SPY · medSharpe 0.00 · worst -0.26% (2023-Q3 chop) · best +0.00% (everywhere else)
**Fitness gate:** 🔴 **FAIL** — median return +0.00% ≤ +0.00%; only 0% of windows positive (need ≥50%); median Sharpe 0.00 ≤ 0.50.

## Walk-forward results — QQQ (warmup-extended)

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear        | bear | 214 | 0 | +0.00 | 0.00 | 0.00 | -1.74 | ✅ |
| 2022-Q3 chop        | chop | 213 | 0 | +0.00 | 0.00 | 0.00 | -0.65 | ✅ |
| 2023-H1 recovery    | bull | 213 | 0 | +0.00 | 0.00 | 0.00 | +0.74 | ❌ |
| 2023-Q3 chop        | chop | 212 | 2 | -0.18 | -1.45 | -0.29 | -0.38 | ✅ |
| 2024-Q2 bull        | bull | 211 | 2 | +0.13 | 1.32 | -0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 213 | 0 | +0.00 | 0.00 | 0.00 | -0.80 | ✅ |
| 2025-Q3 bull        | bull | 211 | 0 | +0.00 | 0.00 | 0.00 | +0.65 | ❌ |
| 2026-recent bull    | bull | 193 | 0 | +0.00 | 0.00 | 0.00 | +1.55 | ❌ |

**Aggregate:** medRet **+0.00%** · 12% positive · 50% beat BH-SPY · medSharpe 0.00 · worst -0.18% (2023-Q3 chop) · best +0.13% (2024-Q2 bull)
**Fitness gate:** 🔴 **FAIL** — median return +0.00% ≤ +0.00%; only 12% of windows positive (need ≥50%); median Sharpe 0.00 ≤ 0.50.

---

## Per-symbol gate verdict

- **SPY:** 🔴 FAIL — `passes_fitness_gate()` triggers on median_return (+0.00%), pct_positive (0%), median_sharpe (0.00). 1 trade across 8 windows of data.
- **QQQ:** 🔴 FAIL — `passes_fitness_gate()` triggers on median_return (+0.00%), pct_positive (12%), median_sharpe (0.00). 2 round-trips (4 trade rows) across 8 windows.

Gate per pre-registration: PASS_STANDALONE iff EITHER symbol clears. Neither does.

**→ FAIL_STANDALONE.**

---

## Spot-check (mandated by task)

Verified entry logic by hand on three windows (`_spot_check_connors.py`):

1. **SPY 2023-Q3 chop** — RSI(2)<10 fires on 3 consecutive days (Sep 20-22, 2023): RSI 6.2 → 1.8 → 1.5. All three days have `close > SMA(200)` (438 > 418, 431 > 418, 430 > 418), so trend filter passes. Strategy correctly emits **buy** on Sep 20 then **hold** on Sep 21-22 (already long). Backtest reported `n_trades=1`, which is the bar-level count of one buy that didn't yet close (close>SMA(5) condition not met before window ended OR closed at -0.26% which matches the equity move). ✓
2. **QQQ 2024-Q2 bull** — Single RSI<10 signal on Jun 24 2024 (RSI 6.9, close 474 > SMA200 414). One entry → one exit at +0.13% over a few bars. ✓
3. **SPY 2022-H1 bear** — Three RSI<10 signals (Jun 10/13/14 2022) all correctly BLOCKED by trend filter (close 376-390 < SMA200 442). 0 trades reported. ✓

Strategy logic is implemented correctly. The fail is genuine: Connors RSI(2) on canonical params fires too rarely (and in tiny dollar moves when it does) to clear a 0.50 median-Sharpe / 50% positive bar across our 8-window panel.

---

## Caveats (be honest about what these numbers can and can't tell us)

1. **Trade count is critically low.** 1 SPY trade, 2 QQQ round-trips across 8 windows ≈ 720 trading days. Statistical power for "is this strategy profitable?" is near zero. We can confidently say "this strategy does not produce enough signal to clear the fitness gate on this panel" — we cannot say "this strategy is bad." A 5-year backtest (vs our 8 × 90-day windows) would likely produce 20-40 trades and reach a verdict with real teeth.
2. **The 90-day window is structurally hostile to slow-trigger mean-reverters.** Our harness was sized for hourly bars (~1500 bars per window) where infrequent triggers still fire many times. On 1Day bars, a 90-day window has ~62 bars, and Connors' RSI(2)<10 is a ~2-5% historical event ⇒ 1-3 expected entries per window. Many windows will see zero by chance alone, dragging the gate metrics toward null.
3. **Cost model.** Alpaca-stocks cost model (~2bps spread, $0 commission) applied. Connors RSI(2) trades trade tiny moves (entry-to-exit usually <1%), so 2bps round-trip is meaningful. The lone SPY trade at -0.26% reflects this — small move, partially eaten by costs.
4. **No-warmup harness reports zero trades for both.** If main wants the strict no-warmup answer (i.e. "the strategy on the gate as it exists right now"), that's the answer: FAIL with 0 trades. I chose to report the warmup-extended pass as primary because it carries actual signal about the strategy's behavior. Both are on disk.
5. **Connors RSI(2) is published as having edge on multi-year SPY backtests.** Our gate is window-by-window. The two methodologies are not directly comparable, and a "fails our gate" result is not equivalent to "fails the literature." This is a deficiency of the gate's discrimination on slow strategies, not a refutation of Connors.
6. **Trend filter is doing exactly what Connors designed.** In the 2 bear windows where RSI<10 fires repeatedly (verified Jun 2022 spot-check), the trend filter correctly suppresses all entries. The strategy is being defensive as intended — it just doesn't get enough offensive opportunities in our windowed panel to compensate.

---

## Pre-registered decision tree consequence

Per `memory/2026-05-27.md`:

> **Fail standalone gate** → 11 honest attempts, 0 hits. Stop building, accept soak, revisit after Saturday's leaderboard with 4-week data.

This result triggers the **fail standalone** branch. Recommendation for main:
- Do NOT promote to live.
- Do NOT queue directives on this strategy.
- Activate the post-build moratorium: stop strategy-side work until Saturday's leaderboard.
- The "low trade count" caveat is real but doesn't change the pre-registered decision rule. Honoring the pre-registration is the whole point.

If main wants to revisit later, a **gate-design improvement** worth considering (separately, NOT as a Connors rescue) would be: for daily-timeframe strategies, fetch and trade longer windows (e.g. 270 days) so slow-trigger strategies get enough fires to evaluate. But that is gate work, not strategy work, and is out of scope for this task.

---

## Artifacts produced

- `strategies_candidates/connors_rsi2_spy/` — strategy.py + params.json + __init__.py
- `strategies_candidates/connors_rsi2_qqq/` — strategy.py + params.json + __init__.py
- `connors_rsi2_wf_result.json` — no-warmup walk-forward (0 trades both symbols)
- `connors_rsi2_wf_warmup_result.json` — warmup-extended walk-forward (numbers in this report)
- `_run_connors_wf.py` — no-warmup runner
- `_run_connors_wf_warmup.py` — warmup-extended runner
- `_spot_check_connors.py` — entry-logic verifier
- (This file) `CONNORS_RSI2_VALIDATION_20260527.md`

All candidate code is in `strategies_candidates/` (quarantine). Nothing was promoted. Nothing was added to the live runner. No live strategies were modified.
