# Hold-the-Dip Audit of live `rsi_oversold_spy` — VERDICT: keep signal, but parent is WEAK on the raw-return bar

_2026-06-27 · trading-bench (Tessera) · main-greenlit P1 lane from the 2026-06-26 AQR reading sprint (`AQR_READING_SPRINT_2_20260626.md` #2)_

## TL;DR — two findings, one nuanced

1. **AQR's proposed fixes do NOT help our instrument — mild empirical REBUTTAL of
   "Hold the Dip" on SPY 1Hour.** Neither the SMA-200 trend-gate nor the
   momentum-entry flip beats the live RSI dip-buy OOS:
   - **gated_sma200**: OOS FP-Sharpe 1.447 vs baseline **1.477** (−0.030). Trend-
     gating the dip-buy *slightly hurts* (filters profitable sub-200d-SMA dips);
     it halves an already-tiny maxDD (−1.41%→−0.71%) but gives up return
     (4.37%→3.38%). Canary-clean (drop +0.000).
   - **flip_momentum** (buy strength not weakness): OOS 1.271 vs 1.477 (−0.206),
     FULL 0.447 vs 0.902 (−0.455). **Buying strength is clearly WORSE than buying
     dips on SPY 1Hour** — a direct rebuttal of AQR's central momentum>dip claim
     *at this intraday horizon*. Mean-reversion legitimately wins here.

2. **BUT the live dip-buy is a WEAK strategy on the actual mission bar (beat SPX
   raw).** It is NOT a swap candidate — it's a roster-review candidate:
   - **6.86% total return over 7.6 years** vs **SPY buy&hold +127.7%** (11.4%/yr).
   - Deploys capital only **13.9% of the time** (1,731/12,444 bars in market;
     avg hold 19.9 bars ≈ the 20-bar time-stop almost always fires).
   - Edge-while-deployed ≈ **6.5%/yr** — *below* SPY's 11.4% CAGR. So sizing it up
     would NOT fix it; the per-unit-time edge is worse than just holding SPY.
   - Its flattering Sharpe (FULL 0.902 / OOS 1.477) is a **mostly-in-cash
     artifact** (tiny return-vol denominator), not a real risk-adjusted edge.

**Recommendation:** keep the dip-buy SIGNAL as-is (no AQR fix improves it), but
**flag `rsi_oversold_spy` for live-roster review** — it's a structural raw-return
underperformer, joining `breakout_xlk` on the watchlist. The honest read is "the
fix AQR proposes doesn't apply to us, AND the parent is weak for a different,
more damning reason."

## Method (honest harness — production engine)

- **Engine:** `runner.backtest.backtest()` (the SAME engine as the live book) →
  cost model, fill convention, position accounting, and Sharpe ruler
  (`bars_per_year("1Hour")`) are identical to every other backtest. Three arms
  share the SPY 1Hour path (12,444 bars, 2020-07-27→2026-06-26, Alpaca floor),
  `CostModel.alpaca_stocks()` = 2 bps/side, IS≤2023-12-31 / OOS≥2024-01-01.
- **BASELINE** = the live strategy's own `decide()` unchanged (RSI(14)<28 enter,
  RSI>70 | 20-bar time-stop exit, notional 159.65).
- **(a) GATED** = same `decide()`, BUY vetoed unless SPY > its **daily** 200d SMA
  (lookahead-safe: most recent daily adjclose STRICTLY before the bar's calendar
  day vs its 200d SMA). + **1-day-lag canary** (daily SMA read lagged one extra
  trading day).
- **(b) FLIP** = momentum entry (RSI>70), exit on weakness (RSI<30) | 20-bar
  stop — same RSI/period/notional/time-stop for an apples-to-apples flip.
- Benchmark: SPY buy&hold on the same 1Hour path (one round-trip cost).

## Results

| Arm | FULL fpS | OOS fpS | FULL ret | OOS ret | trades | maxDD | win |
|---|---|---|---|---|---|---|---|
| **baseline_dipbuy (live)** | **0.902** | **1.477** | 6.86% | 4.37% | 174 | −1.53% | 60.9% |
| gated_sma200 | 0.893 | 1.447 | 4.77% | 3.38% | 120 | −0.93% | 63.3% |
| flip_momentum | 0.447 | 1.271 | 2.63% | 2.33% | 310 | −2.15% | 56.1% |
| **SPY buy&hold (dumb bar)** | 0.920 | 1.220 | **127.57%** | **54.99%** | — | — | — |

- gated_sma200 canary OOS fpS = 1.447 (drop +0.000 — robust, but moot since it
  doesn't beat baseline).
- Capital-efficiency forensics (baseline): 87 closed trades, 0.49%/trade,
  13.9% time-in-market, ~6.5%/yr-while-deployed (< SPY 11.4% CAGR).

## Interpretation

- **On Sharpe**, the live dip-buy looks fine (beats SPY-BH full 0.902 vs 0.920 is
  ~tie; OOS 1.477 vs 1.220 it "wins") — BUT that is the classic
  **mostly-in-cash mirage**: a strategy in the market 14% of the time with −1.5%
  maxDD has a tiny return-vol denominator, so any positive drift prints a high
  Sharpe. This is exactly the "median-of-windows / low-exposure Sharpe = mirage"
  trap in MEMORY.md, surfacing as a low-time-in-market artifact.
- **On the mission bar (raw return), it's not close**: 6.86% vs 127.7% over 7.6y.
  And it's not a deploy-more-capital fix, because edge-while-deployed (6.5%/yr)
  is itself below SPY's CAGR.
- **AQR rebuttal is real but narrow**: at the **1Hour** horizon on SPY,
  mean-reversion beats momentum-entry (flip is strictly worse), and trend-gating
  doesn't help. AQR's "Hold the Dip" is framed for the daily/multi-day horizon;
  our intraday child is a different regime. We've empirically shown their fix
  doesn't port to SPY 1Hour — a useful internal data point, not a refutation of
  their daily-horizon thesis.

## Recommendation & next steps

1. **Do NOT swap** — no variant beats the live dip-buy; the AQR fix is a
   no-improvement on our instrument.
2. **Flag `rsi_oversold_spy` for live-roster review** (raw-return underperformer;
   high Sharpe is a low-exposure artifact). This is a mandate-level roster call
   for main/Cyrus, same bucket as the `breakout_xlk` OOS-fragility flag from the
   combo sprint. The roster's job is to beat SPX raw; a 6.86%-over-7.6y member
   that can't be sized into relevance is a weak tile.
3. If kept, its ONLY honest role is as a **low-correlation cash-parking
   micro-sleeve** in a book-level blend (it's flat 86% of the time), NOT as a
   standalone return engine. Worth testing its correlation contribution to the
   allocator_blend if main wants to retain it.

## Artifacts (workspace, no orders, no spend, rails intact)

- `_holddip_audit.py` → `_holddip_results.json` — 3 arms × full/IS/OOS + gated
  canary + SPY-BH benchmark, all via the production `backtest()` engine.
- Reuses live `rsi_oversold_spy.decide()`, `CostModel.alpaca_stocks()`,
  `bars_per_year` ruler; daily-SMA gate is lookahead-safe (strictly-prior close).
- Paper-only + `STOP_TRADING` killswitch intact.
