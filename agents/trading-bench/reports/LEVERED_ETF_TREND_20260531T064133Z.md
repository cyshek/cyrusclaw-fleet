# LEVERED ETF TREND — Backtest Memo

**UTC timestamp:** 20260531T064133Z
**Author:** Tessera (trading-bench), levered_etf_trend research subagent
**Discipline:** Bar A (backtest → walk-forward → net of realistic cost). This memo is the **backtest** stage only. **Zero promotions.** Candidates land in `strategies_candidates/` for the record.

---

## TL;DR VERDICT

**No leveraged-ETF trend or rotation strategy beats buy-and-hold SPY on a risk-adjusted basis over the real data span.** Every variant tested loses to SPY on **both** Sharpe **and** max drawdown — the exact double-bar this exercise was designed to enforce. The big raw returns some variants post (+170% to +200%) are bull-market 3x beta, not timing alpha, and they come bundled with **-60% to -98% drawdowns**. The edge is "bull beta," not skill. **Recommend: do NOT advance either archetype to walk-forward or promotion.**

---

## 1. Universe & data span actually used

Universe (leveraged long ETFs, traded as ordinary LONG positions — leverage lives inside the instrument):

| Symbol | Exposure | Inception | First REAL bar in cache |
|---|---|---|---|
| TQQQ | 3x Nasdaq-100 | 2010-02 | 2020-07-27 |
| SOXL | 3x semis | 2010-03 | 2020-07-27 |
| UPRO | 3x S&P 500 | 2009-06 | 2020-07-27 |
| TECL | 3x tech | 2008-12 | 2020-07-27 |
| SPY (benchmark) | 1x S&P 500 | 1993 | 2020-07-27 |

**Honest span statement (PATTERNS.md Pattern #4 compliance):** although these ETFs inception as early as 2008–2010, the bars cache (Alpaca free IEX feed) floors at **2020-07-27**. Every metric below is computed over the **aligned common span 2020-07-27 → 2026-05-28 (1,463 daily bars, ~5.8 years)**. No claim extends before the cache floor. This span is a near-worst-case advertisement for leveraged-ETF trend: it contains the 2020–2021 melt-up (where 3x looks god-tier) **and** the 2022 bear + 2025 tariff bear (where it gives it all back) — exactly the regime mix needed to separate beta from skill.

---

## 2. Archetypes tested

1. **SMA trend overlay on the 3x ETF itself** — hold LONG when prior close > SMA(N), flat (cash) otherwise. N ∈ {20, 50, 100, 200}, each of the 4 ETFs. The SMA flat-rule is the entire thesis: vol-decay destroys buy-and-hold-3x in chop, so the timing overlay must sidestep drawdowns.
2. **Cross-sectional momentum rotation** across the 3x basket — hold top-K by trailing return (lookback ∈ {63,126,252} trading days), monthly rebalance, K ∈ {1,2}, always invested.

A SPY-regime-gated SMA variant was also spot-checked (gate buys on SPY > SMA(N)). It did not improve the verdict.

**Cost model:** `alpaca_stocks` — 2 bps one-way spread (liquid US ETFs), 0 per-side fee. **Expense drag** (~0.9%/yr for 3x ETFs) modeled in the standalone NAV analysis as a daily multiplicative haircut applied only while invested. Spread is charged on every position flip.

---

## 3. Full results table (standalone NAV, fully-invested basis, expense-adjusted)

All metrics over **2020-07-27 → 2026-05-28**. Sharpe/Sortino annualized (√252). "BEATS SPY" requires Sharpe > 0.96 **AND** maxDD better than -25.4%.

### Benchmark
| Series | Total ret | Sharpe | Sortino | maxDD |
|---|---|---|---|---|
| **BH-SPY** (the BAR) | +133.5% | **0.96** | 1.38 | **-25.4%** |

### Buy-and-hold the 3x ETF (no timing — shows vol-decay directly)
| Series | Total ret | Sharpe | Sortino | maxDD | IR vs SPY |
|---|---|---|---|---|---|
| BH TQQQ | **-29.0%** | 0.36 | 0.47 | -92.0% | 0.19 |
| BH SOXL | -1.7% | 0.78 | 1.08 | -99.0% | 0.72 |
| BH UPRO | +178.1% | 0.62 | 0.83 | -82.1% | 0.45 |
| BH TECL | -11.0% | 0.60 | 0.79 | -95.9% | 0.49 |

> **Vol-decay smoking gun:** over a span where SPY (1x) is **+133.5%**, buy-and-hold 3x-Nasdaq (TQQQ) is **-29.0%** and 3x-tech (TECL) is **-11.0%**. Three of four 3x ETFs *underperformed the 1x index in absolute terms* despite 3x leverage, because the 2022 drawdown compounding (geometric decay in choppy/down tapes) ate the bull gains. This is the canonical leveraged-ETF trap.

### SMA trend overlay (best N per ETF shown; full sweep run)
| Series | Trades | % invested | Total ret | Sharpe | Sortino | maxDD | IR vs SPY | Beats SPY? |
|---|---|---|---|---|---|---|---|---|
| TQQQ SMA20 | — | 59% | +190% | 0.66 | — | -62.2% | — | **NO** |
| TQQQ SMA50 | 77 | 59% | +171.1% | 0.63 | 0.83 | -65.2% | 0.31 | **NO** |
| SOXL SMA200 | 41 | 42% | +163.7% | 0.58 | 0.85 | -70.2% | 0.34 | **NO** |
| UPRO SMA200 | 23 | 59% | +77.2% | 0.50 | 0.60 | -62.6% | 0.04 | **NO** |
| TECL SMA20 | — | 59% | +272% | 0.72 | — | -62.8% | — | **NO** |
| TECL SMA200 | 41 | 50% | +69.9% | 0.43 | 0.60 | -58.0% | 0.06 | **NO** |

Best Sharpe across **all** single-ETF SMA variants = **0.72** (TECL SMA20), vs SPY 0.96. Best (least-bad) maxDD = **-58%** (TECL SMA200), vs SPY -25.4%. **Not one variant clears either bar, let alone both.**

### Cross-sectional rotation across the 3x basket
| Variant | Trades | % invested | Total ret | Sharpe | Sortino | maxDD | IR vs SPY | Beats SPY? |
|---|---|---|---|---|---|---|---|---|
| lb=63 K=1 | 49 | 95% | +66.2% | **0.82** | 1.09 | -97.8% | 0.72 | **NO** |
| lb=126 K=2 | 32 | 91% | +159.8% | 0.60 | 0.84 | -83.5% | 0.47 | **NO** |
| lb=252 K=1 | 29 | 83% | +197.7% | 0.64 | 0.90 | -86.6% | 0.51 | **NO** |
| lb=252 K=2 | 40 | 83% | +18.0% | 0.42 | 0.56 | -90.6% | 0.23 | **NO** |

Best rotation Sharpe = **0.82** (lb=63 K=1) — still under SPY's 0.96, and it carries a **-97.8%** drawdown because it is *always invested* in a 3x sleeve with no flat escape. Rotation is **strictly worse on drawdown** than the single-ETF SMA overlay (which at least goes to cash ~45% of the time).

---

## 4. Vol-decay commentary

Leveraged ETFs rebalance daily to maintain constant leverage, which makes their compounded return path-dependent: in trending tapes they can exceed N× the index, but in choppy/mean-reverting tapes they bleed ("volatility decay" / "beta slippage"). This span demonstrates it brutally — **BH TQQQ returned -29% while SPY returned +134%.** The SMA overlay's job is to be flat during the decay-heavy chop. It partially works (cutting TQQQ's -92% BH drawdown to ~-65%) **but a daily-cadence SMA cannot react fast enough**: by the time a 50-/200-day SMA flips, a 3x ETF has already fallen 30–50%, and whipsaws in chop trigger repeated buy-high/sell-low flips (47–97 round trips). The overlay improves on naive BH-3x but **never closes the gap to plain BH-SPY.**

## 5. Execution-cost reality

- **Spread:** 2 bps one-way modeled (liquid mega-ETFs; TQQQ/SOXL/UPRO/TECL all trade tight). At $100 notional and 75–97 flips, total spread cost is ~$1.50 on a $1000 base — negligible relative to the strategy's swings. Cost is NOT what kills these; the drawdowns are.
- **Expense drag:** ~0.9%/yr for 3x ETFs, modeled as a daily NAV haircut while invested. Over ~5.8 years that's a ~5% cumulative drag on a fully-invested sleeve — real but second-order vs the -60%+ drawdowns.
- **Harness cross-check:** running `levered_trend_tqqq` (TQQQ SMA50) through the production `runner/backtest.py` over the same span gives Sharpe **0.67** (matches standalone 0.63), 75 trades, 0 risk-skips, $1.52 costs. **Caveat:** the harness reports portfolio-level maxDD of only **-9.6%** because it deploys ~$100 against a $1000 cash base, diluting drawdown. The instrument-level NAV drawdown (the figure that's apples-to-apples vs BH-SPY NAV) is **~-65%**. The harness number is not wrong, it's just measuring a 90%-cash portfolio; do not cite it as the strategy's risk.

---

## 6. VERDICT per archetype

**Archetype 1 — SMA trend overlay on the 3x ETF: REJECT (does not beat SPY risk-adjusted).**
- Beats SPY on Sharpe? **No** (best 0.72 vs 0.96). Beats SPY on maxDD? **No** (best -58% vs -25%). Fails the double-bar on both axes for every (ETF, N) combination.
- Worth a real walk-forward / promotion? **No.** It improves on naive BH-3x but the residual is bull-market beta with catastrophic tail risk. A walk-forward across the 8 NAMED_WINDOWS would near-certainly show it lives or dies by the 2020–2021 bull window — not worth the compute given the full-period result already fails decisively.

**Archetype 2 — cross-sectional 3x rotation: REJECT (does not beat SPY risk-adjusted, and is worse than Archetype 1).**
- Beats SPY on Sharpe? **No** (best 0.82 vs 0.96). Beats SPY on maxDD? **No** (best -83.5%, most -97%+). The always-invested design removes the one risk control (going flat) that made Archetype 1 tolerable.
- Worth a real walk-forward / promotion? **No.** Strictly dominated by the single-ETF overlay on drawdown.

**Bottom line:** the leveraged-ETF trend thesis fails on this bench's risk-adjusted bar. If the goal were raw return in a known bull, UPRO/TECL trend posts big numbers — but "I knew it would be a bull market" is not a strategy. On Sharpe-and-drawdown, **plain BH-SPY wins outright.** No promotion. Candidates shipped for the record only.

---

## 7. Deliverables

- **Candidate dirs (NO promotion, candidate-only):**
  - `strategies_candidates/levered_trend_tqqq/` — single-ETF SMA50 trend overlay on TQQQ. Matches single-symbol `decide()` interface (≡ `sma_crossover_qqq`). Validated through `runner/backtest.py`.
  - `strategies_candidates/levered_rotate_3x/` — top-K monthly rotation across the 3x basket. Matches `decide_xsec()` interface (≡ `xsec_momentum_xa_38d2b2`); includes `xsec_basket_size`.
- **Analysis driver:** `_levered_etf_analysis.py` (standalone, offline, reproduces every NAV figure above).
- **Test suite:** **226 passed** (no candidate-specific tests added; candidate files don't touch protected runner logic). risk.py / runner files untouched.

*Span integrity: every number herein computed over 2020-07-27 → 2026-05-28, span start ≥ cache floor 2020-07-27 (Pattern #4 compliant).*
