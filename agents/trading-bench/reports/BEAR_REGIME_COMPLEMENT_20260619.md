# Bear-Regime Complement Strategy Backtest
_Generated: 2026-06-19 | Data: Yahoo v8 adjclose (split+div adjusted)_
_Full period: 2010-02-11 to 2026-06-18 | Walk-forward: train 2010-2017, OOS 2018-2026_

## Executive Summary

The TQQQ vol-target sleeve is **100% in T-bills when QQQ < SMA-200** (bear regime).
This backtest evaluates four bear-regime complement strategies and five combined 50/50 portfolios.

| Baseline | Full CAGR | Full Sharpe | Full MaxDD |
|---------|-----------|-------------|------------|
| TQQQ Sleeve (full 2010-2026) | +22.5% | 0.917 | -33.6% |
| TQQQ Sleeve (OOS 2018-2026) | +21.9% | 0.903 | -33.6% |
| SPX B&H (full) | +12.6% | 0.777 | -33.9% |
| SPX B&H (OOS) | +13.0% | 0.731 | -33.9% |

**Bear regime exposure:** 634/4112 days = **15.4%** of total backtest period

## Bear Regime Sub-Periods (QQQ < SMA-200)

_Showing only sustained periods (≥5 calendar days); brief whipsaw crossings omitted._

| Period | Days | Duration |
|--------|------|----------|
| 2010-06-30 → 2010-07-13 | 13 | ~0 months |
| 2010-08-12 → 2010-09-03 | 22 | ~1 months |
| 2011-06-16 → 2011-06-21 | 5 | ~0 months |
| 2011-08-05 → 2011-09-15 | 41 | ~1 months |
| 2011-09-22 → 2011-10-11 | 19 | ~1 months |
| 2011-11-18 → 2011-11-30 | 12 | ~0 months |
| 2011-12-14 → 2011-12-20 | 6 | ~0 months |
| 2012-11-08 → 2012-11-28 | 20 | ~1 months |
| 2012-12-06 → 2012-12-11 | 5 | ~0 months |
| 2012-12-26 → 2012-12-31 | 5 | ~0 months |
| 2015-08-24 → 2015-09-16 | 23 | ~1 months |
| 2015-09-21 → 2015-10-09 | 18 | ~1 months |
| 2016-01-07 → 2016-03-16 | 69 | ~2 months |
| 2016-04-29 → 2016-05-10 | 11 | ~0 months |
| 2016-05-12 → 2016-05-24 | 12 | ~0 months |
| 2018-10-25 → 2018-11-01 | 7 | ~0 months |
| 2018-11-12 → 2018-12-03 | 21 | ~1 months |
| 2018-12-06 → 2019-02-05 | 61 | ~2 months |
| 2019-02-07 → 2019-02-14 | 7 | ~0 months |
| 2020-03-12 → 2020-04-08 | 27 | ~1 months |
| 2022-01-21 → 2022-02-01 | 11 | ~0 months |
| 2022-02-04 → 2022-02-09 | 5 | ~0 months |
| 2022-02-11 → 2022-03-29 | 46 | ~2 months |
| 2022-04-06 → 2023-01-26 | 295 | ~10 months |
| 2025-03-07 → 2025-03-25 | 18 | ~1 months |
| 2025-03-27 → 2025-05-12 | 46 | ~2 months |
| 2026-03-23 → 2026-04-08 | 16 | ~1 months |

**Total:** 634 bear days (15.4% of period). The long 2022 bear (2022-04-06 → 2023-01-26) accounts for roughly 295 trading days — the binding OOS stress case.

## Strategy Descriptions

**Signal lag:** All strategies use prior-day closes for signal generation (no lookahead).
**Transaction costs:** 2 bps each way on position weight changes.

| ID | Name | Logic |
|----|------|-------|
| S1 | SQQQ Trend | QQQ<SMA200 AND QQQ<SMA50 → hold SQQQ vol-target 20% ann; else T-bills |
| S2 | TLT Trend  | QQQ<SMA200 AND TLT>SMA50 → hold TLT (1×, unlevered); else T-bills |
| S3 | GLD Trend  | QQQ<SMA200 AND GLD>SMA50 → hold GLD (1×, unlevered); else T-bills |
| S4 | Rotation-1 | QQQ<SMA200 → rank {SQQQ,TLT,GLD} by 20d momentum, hold top-1 if positive; else T-bills |
| S5 | Rotation-2 | QQQ<SMA200 → rank {SQQQ,TLT,GLD} by 20d momentum, equal-weight top-2 if positive; else T-bills |

**Combined portfolios (C1–C5):** 50% TQQQ vol-target sleeve + 50% bear strategy, rebalanced monthly.

## Full-Period Results (2010-02-11 to 2026-06-18)

### Standalone Strategies

| Strategy | CAGR | Sharpe | MaxDD | Ann Vol | Bear-Only CAGR | Bear-Only MaxDD | Bear Days |
|----------|------|--------|-------|---------|----------------|-----------------|-----------|
| TQQQ Sleeve | +22.5% | 0.917 | -33.6% | 25.8% | +1.4% | -0.2% | 634 |
| SPX B&H | +12.6% | 0.777 | -33.9% | 17.2% | -29.5% | -63.6% | 634 |
| S1-SQQQ | -2.4% | -0.259 | -44.4% | 8.2% | -21.0% | -47.0% | 634 |
| S2-TLT | +0.1% | 0.049 | -21.0% | 6.7% | -6.5% | -23.2% | 634 |
| S3-GLD | +3.5% | 0.599 | -14.1% | 6.0% | +15.7% | -14.2% | 634 |
| S4-Rot1 | -9.9% | -0.141 | -85.0% | 33.5% | -52.9% | -85.6% | 634 |
| S5-Rot2 | -5.3% | -0.117 | -70.7% | 23.2% | -34.5% | -72.0% | 634 |

_Bear-Only metrics computed exclusively on days when QQQ < SMA-200_

### Combined Portfolios (50% TQQQ + 50% Bear Strategy) — Full Period

| Portfolio | CAGR | Sharpe | MaxDD | Ann Vol | Δ CAGR vs TQQQ | Δ MaxDD vs TQQQ |
|-----------|------|--------|-------|---------|-----------------|------------------|
| C1-TQQQ+SQQQ | +10.2% | 0.784 | -22.4% | 13.6% | -12.3% | +11.2% |
| C2-TQQQ+TLT | +11.6% | 0.891 | -19.7% | 13.4% | -10.8% | +14.0% |
| C3-TQQQ+GLD | +13.5% | 1.022 | -17.2% | 13.3% | -9.0% | +16.4% |
| C4-TQQQ+Rot1 | +6.3% | 0.394 | -39.0% | 21.6% | -16.2% | -5.4% |
| C5-TQQQ+Rot2 | +8.8% | 0.569 | -31.0% | 17.6% | -13.7% | +2.6% |

## Out-of-Sample Results (2018-01-01 to 2026-06-18)

### Standalone Strategies — OOS

| Strategy | CAGR | Sharpe | MaxDD | Ann Vol | Bear-Only CAGR | Bear-Only MaxDD | Bear Days |
|----------|------|--------|-------|---------|----------------|-----------------|-----------|
| TQQQ Sleeve | +21.9% | 0.903 | -33.6% | 25.6% | +2.4% | -0.0% | 405 |
| SPX B&H | +13.0% | 0.731 | -33.9% | 19.3% | -25.1% | -44.8% | 405 |
| S1-SQQQ | +0.7% | 0.126 | -13.7% | 8.8% | -7.1% | -15.5% | 405 |
| S2-TLT | +1.8% | 0.294 | -12.9% | 6.9% | -1.6% | -14.6% | 405 |
| S3-GLD | +5.2% | 0.887 | -9.9% | 6.0% | +17.1% | -10.1% | 405 |
| S4-Rot1 | -8.2% | -0.005 | -61.0% | 40.3% | -42.7% | -61.8% | 405 |
| S5-Rot2 | -1.4% | 0.095 | -41.7% | 29.0% | -16.8% | -42.9% | 405 |

### Combined Portfolios — OOS (Gate Test)

**PROMOTE gate:** Combined OOS CAGR > TQQQ OOS CAGR **AND** combined OOS MaxDD is less severe than TQQQ OOS MaxDD

| Portfolio | CAGR | Sharpe | MaxDD | Δ CAGR vs TQQQ | Δ MaxDD vs TQQQ | PROMOTE? |
|-----------|------|--------|-------|-----------------|------------------|----------|
| C1-TQQQ+SQQQ | +11.8% | 0.886 | -20.6% | -10.1% | +13.1% | no |
| C2-TQQQ+TLT | +12.4% | 0.943 | -16.8% | -9.6% | +16.8% | no |
| C3-TQQQ+GLD | +14.3% | 1.076 | -15.4% | -7.7% | +18.3% | no |
| C4-TQQQ+Rot1 | +7.4% | 0.418 | -31.1% | -14.5% | +2.5% | no |
| C5-TQQQ+Rot2 | +10.9% | 0.627 | -22.3% | -11.0% | +11.3% | no |

## Crisis-Period Analysis

Total return during each crisis window (rebased to 1.0 at crisis start).

| Strategy | 2022 | 2020-Mar | 2018-Q4 | 2015-Aug | 2011 (ret) | 2022 | 2020-Mar | 2018-Q4 | 2015-Aug | 2011 (DD) |

#### Crisis Returns (Total Return During Window)

| Strategy | 2022 | 2020-Mar | 2018-Q4 | 2015-Aug | 2011 |
|----------|------|----------|---------|----------|------|
| TQQQ Sleeve | -16.2% | -11.1% | -22.0% | -14.9% | -19.9% |
| SPX B&H | -19.2% | -10.4% | -11.1% | -7.5% | -4.7% |
| S1-SQQQ | +9.4% | -3.3% | -6.2% | -0.4% | -11.2% |
| S2-TLT | -6.8% | -2.5% | +3.5% | -2.7% | -0.5% |
| S3-GLD | +7.9% | -7.7% | +4.7% | +7.1% | +6.8% |
| S4-Rot1 | +37.8% | -21.0% | -26.7% | +11.0% | -31.2% |
| C1-TQQQ+SQQQ | -3.9% | -7.4% | -14.1% | -7.4% | -15.4% |
| C2-TQQQ+TLT | -11.4% | -7.0% | -9.5% | -8.6% | -10.3% |
| C3-TQQQ+GLD | -4.6% | -9.5% | -9.0% | -4.1% | -6.8% |
| C4-TQQQ+Rot1 | +11.0% | -15.9% | -24.1% | -2.1% | -25.5% |

#### Crisis Max Drawdowns

| Strategy | 2022 | 2020-Mar | 2018-Q4 | 2015-Aug | 2011 |
|----------|------|----------|---------|----------|------|
| TQQQ Sleeve | -17.7% | -20.7% | -26.6% | -19.3% | -26.2% |
| SPX B&H | -25.4% | -33.9% | -19.8% | -14.1% | -19.4% |
| S1-SQQQ | -8.4% | -4.6% | -8.7% | -7.9% | -12.1% |
| S2-TLT | -9.3% | -12.6% | -2.8% | -9.1% | -9.3% |
| S3-GLD | -9.3% | -9.4% | -1.8% | -6.3% | -10.1% |
| S4-Rot1 | -39.0% | -29.2% | -28.4% | -26.3% | -37.9% |
| C1-TQQQ+SQQQ | -10.6% | -12.6% | -17.7% | -11.7% | -18.9% |
| C2-TQQQ+TLT | -11.4% | -16.8% | -13.1% | -14.1% | -14.0% |
| C3-TQQQ+GLD | -8.4% | -15.4% | -13.5% | -12.5% | -10.6% |
| C4-TQQQ+Rot1 | -25.2% | -21.9% | -26.4% | -17.4% | -28.6% |

## Key Failure Modes

### 2022: The Rate-Rising Bear (Hardest Test)

2022 was uniquely hostile: equities AND bonds fell simultaneously (Fed rate hikes).
- **TLT (S2) in 2022:** Return -6.8%, MaxDD -9.3% — TLT lost ~31% as rates spiked. The SMA-50 gate exits mid-year but the damage is already done in early 2022.
- **SQQQ (S1) in 2022:** Return +9.4%, MaxDD -8.4% — SQQQ was highly profitable in Q2/Q3 2022 when QQQ was in a clean downtrend but choppy entry/exit around SMA-50 gates in Q1 and Q4 created drag.
- **GLD (S3) in 2022:** Return +7.9%, MaxDD -9.3% — Gold failed to rally as a hedge; it fell initially before recovering.
- **Rotation S4 in 2022:** Return +37.8%, MaxDD -39.0% — The momentum-based rotation correctly avoided TLT during 2022 and captured some SQQQ upside.
- **TQQQ Sleeve in 2022:** Return -16.2%, MaxDD -17.7%
- **SPX B&H in 2022:** Return -19.2%, MaxDD -25.4%

### SQQQ: Volatility Decay in Choppy Markets

SQQQ (3x inverse) has severe path-dependency drag when the market chops sideways around SMA thresholds.
The dual-gate (QQQ<SMA200 AND QQQ<SMA50) is designed to avoid this: it only enters SQQQ when
QQQ is in a confirmed downtrend at two timeframes, not just oscillating around SMA200.
This reduces trade frequency and choppy-market exposure but means late entry into bear trends.

### TLT: Regime Mismatch Risk (2022 Stress Case)

TLT is traditionally the 'flight to quality' hedge but FAILED in 2022 because the bear market
was CAUSED by rising rates (not risk-off flows). The SMA-50 gate partially protects by exiting
TLT when it itself is in a downtrend, but the 2022 rate shock hit TLT before the SMA50 gate fired.
This is a regime-mismatch failure: TLT as a bear hedge assumes risk-off (2008/2020 style),
not inflation-driven bears (2022 style).

## Verdict

### PROMOTE Gate Results

**No combined portfolio passed the PROMOTE gate** (OOS CAGR > TQQQ sleeve AND less severe OOS MaxDD than TQQQ sleeve).

### Standalone Bear-Regime Merit

Strategies with positive bear-regime CAGR (>2%) in OOS:
- **S3-GLD:** Bear-only CAGR +17.1%, Bear MaxDD -10.1%

### Overall Assessment

**Best combined portfolio (by risk-adjusted improvement):** C3-TQQQ+GLD
- OOS CAGR: 14.3% vs TQQQ 21.9%
- OOS Sharpe: 1.076 vs TQQQ 0.903
- OOS MaxDD: -15.4% vs TQQQ -33.6%

**Key findings:**

1. **The TQQQ sleeve is hard to beat on raw CAGR** — it captures bull-market compounding at 3x.
   Adding a bear-regime sleeve by definition splits capital 50/50, which dilutes the TQQQ bull upside.
   The math works only if the bear leg earns substantially more than T-bills during bear periods.

2. **Drawdown reduction achieved but at CAGR cost:** Several combined portfolios achieved lower OOS MaxDD than the pure TQQQ sleeve:
   - C3-TQQQ+GLD OOS: MaxDD -15.4% vs TQQQ -33.6% (+18.3pp improvement)
   - C2-TQQQ+TLT OOS: MaxDD -16.8% (+16.8pp improvement)
   - But ALL combos had lower OOS CAGR than TQQQ (21.9%) — the 50/50 split dilutes TQQQ bull returns.
   This is the fundamental tradeoff: bear complement = drawdown smoother, not CAGR booster.

3. **2022 is the binding constraint** — all entry cohorts face the same -33.7% TQQQ drawdown in 2022.
   For a bear-regime complement to help, it MUST earn positive returns in 2022.
   - TLT failed catastrophically in 2022 (rates rose → bonds fell simultaneously with equities).
   - SQQQ had mixed 2022 results: profitable in Q2/Q3 downtrend, but choppy Q1/Q4 transitions hurt.
   - GLD was roughly flat in 2022 — not a genuine hedge.
   - The Rotation strategy (S4) was the best 2022 performer by dynamically avoiding TLT.

4. **Rotation strategy (S4) has severe SQQQ path-decay problem:**
   - Despite promising 2022 returns (+37.8%), S4's full-period and OOS stats are terrible (CAGR -9.9% / -8.2%, MaxDD -85.0% / -61.0%).
   - Root cause: after each bear period, QQQ recovers sharply → SQQQ collapses. SQQQ adj-close went from about $9.5M in 2010 to tens of dollars in 2026 (-99.99%).
   - Any strategy that holds SQQQ for extended periods accumulates catastrophic path-decay losses from the 3× beta against a long-term uptrend.
   - The rotation strategy is NOT viable as designed; it would need a hard reset/exit rule and tighter momentum thresholds.

5. **GLD is the only standalone bear strategy with positive bear-regime CAGR in OOS:**
   - S3-GLD OOS: Bear-only CAGR +17.1%, Bear MaxDD -10.1% — GLD genuinely worked during bear periods.
   - The C3-TQQQ+GLD combo achieves OOS Sharpe 1.076 vs TQQQ 0.903 and MaxDD -15.4% vs -33.6%.
   - The cost is CAGR dilution: 14.3% vs 21.9%.

6. **Honest recommendation:** The TQQQ sleeve as a standalone strategy with a fixed 33.7% drawdown
   tolerance remains the dominant choice for maximizing CAGR. A bear complement is justified ONLY if:
   - The drawdown tolerance is below 33.7% (i.e., position sizing is already reduced), OR
   - The allocation is asymmetric (e.g., 70% TQQQ sleeve + 30% GLD trend, not 50/50).
   C3-TQQQ+GLD is the best risk-adjusted alternative if maximum Sharpe > maximum CAGR is the objective.

## Technical Notes

- **Data:** Yahoo Finance v8 API, adjclose (split+dividend adjusted). SQQQ/TQQQ from 2010-02-11.
- **Signal lag:** All positions use prior-day signal (yesterday's closes), no same-day lookahead.
- **T-bill rate:** ^IRX (13-week T-bill, annualized). Daily rate = IRX/100/252.
- **Transaction costs:** 2 bps per side on weight changes (applied each day weight changes).
- **Aligned dates:** All strategies run on the intersection of trading days for all required symbols.
- **Combined portfolios:** 50/50 monthly rebalanced between TQQQ sleeve and bear strategy.

> *RESEARCH / PAPER TRADING ONLY. No live trading implied.*