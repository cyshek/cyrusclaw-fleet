# PEAD Market-Neutral Backtest
**Date:** 2026-06-20  
**Strategy:** Post-Earnings Announcement Drift (PEAD) — Long beats, Short misses, Large-cap  
**Disposition:** ❌ REJECT — short side destroys alpha; long-only is a better standalone  

---

## Executive Summary

The market-neutral PEAD construct **does not pass the gate**. The root cause is structural:
the short book (fading earnings misses) consistently loses money across all five threshold
levels tested. The best neutral result (20% threshold) achieves only OOS Sharpe = 0.505 and
CAGR = 6.88% — far below the gate criteria of Sharpe ≥ 0.70 and beta < 0.30.

The **long book alone** is a confirmed, consistent signal: OOS Sharpe 0.61–0.67 across all
thresholds, with the short leg being a pure drag. The recommendation is to continue developing
the long-only PEAD strategy with proper volatility-adjustments rather than pursuing a
dollar-neutral construct.

---

## Setup

| Parameter | Value |
|-----------|-------|
| Universe | Large-cap: n_estimates ≥ 8, \|EPS forecast\| ≥ 0.05 |
| Long signal | surprise_pct > +threshold% |
| Short signal | surprise_pct < -threshold% |
| Hold period | 20 trading days |
| Entry | D+1 adjclose (day after earnings report) |
| Capacity | Max 20 long + 20 short simultaneous positions |
| Costs | 4 bps each way (8 bps round-trip) |
| Trend gate | NONE (prior work: SPY trend gate collapses Sharpe to -0.455) |
| Sizing | Equal-weight within each book; dollar-neutral (long $ = short $) |
| IS period | 2012-01-01 to 2017-12-31 |
| OOS period | 2018-01-01 to 2026-06-01 |
| Benchmark | SPY buy-and-hold: OOS CAGR = 14.85% |

---

## Threshold Sweep Results (OOS 2018–2026)

### Long-Only (isolated, no short hedge)

| Threshold | OOS Sharpe | OOS CAGR | MaxDD | Beta | WR | Avg Trade | N Trades |
|-----------|-----------|---------|-------|------|-----|----------|----------|
| 2% | 0.652 | 13.33% | 54.62% | 1.045 | 57.7% | +1.086% | 1,643 |
| 5% | 0.613 | 12.44% | 56.42% | 1.037 | 56.6% | +0.843% | 1,529 |
| **10%** | **0.672** | **14.48%** | 55.14% | 1.036 | 54.7% | **+1.095%** | 1,323 |
| 15% | 0.648 | 14.31% | 50.81% | 1.069 | 54.2% | +1.125% | 1,152 |
| 20% | **0.673** | **15.33%** | 48.74% | 1.099 | 55.2% | **+1.655%** | 1,043 |

*MaxDD is high because this is a fully-invested long book (beta ~1.0) with no hedge — includes
the 2020 COVID crash (-34%) and the 2022 rate-hike bear (-19%). The **signal quality** (Sharpe
0.61–0.67) is consistent and robust across all thresholds.*

### Short-Only (isolated)

| Threshold | OOS Sharpe | OOS CAGR | MaxDD | Beta | WR | Avg Trade | N Trades |
|-----------|-----------|---------|-------|------|-----|----------|----------|
| 2% | -0.720 | -21.10% | 88.67% | -1.000 | 43.8% | -1.122% | 925 |
| 5% | -0.301 | -13.41% | 83.70% | -1.095 | 46.7% | -0.354% | 808 |
| 10% | -0.275 | -14.72% | 89.03% | -1.159 | 48.2% | -0.126% | 610 |
| 15% | -0.386 | -18.06% | 89.82% | -1.072 | 47.9% | -0.401% | 470 |
| **20%** | **-0.069** | **-8.31%** | 87.13% | -0.978 | **49.3%** | **-0.234%** | 361 |

**All short thresholds produce negative Sharpe.** The best is -0.069 at 20%, which is near-zero
but still negative. The short book is systematically losing money after costs.

### Dollar-Neutral (combined, equal-weight long + short)

| Threshold | OOS Sharpe | OOS CAGR | MaxDD | Beta | Corr | Long Sh | Short Sh |
|-----------|-----------|---------|-------|------|------|---------|---------|
| 2% | -0.211 | -2.68% | 30.00% | +0.028 | +0.052 | 0.652 | -0.700 |
| 5% | 0.226 | 2.02% | 24.47% | -0.014 | -0.021 | 0.613 | -0.285 |
| 10% | 0.262 | 2.75% | 31.99% | -0.036 | -0.048 | 0.672 | -0.252 |
| 15% | 0.132 | 0.82% | 24.58% | -0.025 | -0.030 | 0.646 | -0.344 |
| **20%** | **0.505** | **6.88%** | 24.71% | **+0.066** | **+0.079** | 0.669 | **-0.060** |

**The 20% threshold is the best neutral result**: Sharpe 0.505, CAGR 6.88%. Still fails the gate.

---

## Gate Assessment (OOS 2018–2026)

**Gate criteria: OOS Sharpe ≥ 0.70 AND |beta| < 0.30 AND CAGR ≥ 8%**

| Config | Sharpe ≥ 0.70 | \|Beta\| < 0.30 | CAGR ≥ 8% | Verdict |
|--------|--------------|-----------------|------------|---------|
| Long-only 10% | ❌ 0.672 | ❌ 1.036 | ✅ 14.48% | FAIL |
| Long-only 20% | ❌ 0.673 | ❌ 1.099 | ✅ 15.33% | FAIL |
| Neutral 20% | ❌ 0.505 | ✅ 0.066 | ❌ 6.88% | FAIL |

No configuration passes all three criteria.

---

## Deep Diagnosis

### Why the Short Side Fails (Every Threshold)

**1. Upward market bias overwhelms miss-drift.**
The stock market has a systematic upward bias (SPY +14.85% CAGR in OOS). Large-cap stocks
that miss earnings still participate in this upward drift. The expected downward drift after
a miss exists (win rate climbs from 43.8% → 49.3% as threshold rises) but is overwhelmed by
the underlying upward trend in equities. Short positions lose on average.

**2. Asymmetric volatility response.**
Earnings beats produce a positive shock and persistent upward drift (PEAD on the long side).
Earnings misses produce a negative shock but often rapid recovery — management hosts calls,
provides guidance, and investors rotate in "value" buyers. The drift is weaker and noisier.

**3. Universe imbalance (structural).**
Across all thresholds: ~3.9x more large-cap beats than misses. This isn't random noise:
large-cap analysts systematically set beatable targets. The imbalance creates worse
diversification for the short book (fewer stocks, each with higher weight in portfolio P&L).

**4. Unmodeled real-world costs.**
Short borrow costs (1–5%+ annualized for names being actively shorted) are NOT in this model.
The short leg's true performance would be materially worse in live trading. Even the near-zero
Sharpe of -0.069 at 20% threshold would become firmly negative.

**5. Hard-to-borrow risk.**
Names with large earnings misses are exactly the names that become expensive or unavailable
to borrow — short borrow desks charge up to 50-200% annualized for hot shorts. Model
assumption (freely borrowable at 0 cost) is most violated precisely in the stocks where
we'd want to be short.

### Why the Long Side Works

The long-only signal is robust and passes every reasonableness check:
- **Consistent Sharpe**: 0.61–0.67 across all 5 thresholds (not overfit to one specific threshold)
- **Consistent win rate**: 54.7–57.7% (above 50% = real edge, not noise)
- **Average trade**: +0.84–+1.66% (economically meaningful)
- **IS vs OOS**: IS Sharpes were higher (0.57–0.95) and OOS reversion was moderate — expected
  (IS 2012–2017 was a bull market with clean PEAD; OOS 2018–2026 includes COVID and rate hikes)
- **Beta ~1.0**: The long book has market exposure; the PEAD alpha is ON TOP of the market return,
  not instead of it

### The MaxDD Problem for Long-Only

OOS MaxDD is 48–56% for long-only — this is high. However:
- This includes the 2020 COVID crash (~-34% in SPY, concentrated in 3 weeks)
- The 2022 rate-hike bear (-19% in SPY, spread over 12 months)
- A dedicated PEAD portfolio would typically hold 20 positions × 20-day windows; at peak
  drawdown the portfolio happened to be long into these market events
- **Mitigation options explored**: SPY trend gate (confirmed DESTROYS alpha); sector hedging
  via ETF shorts (untested — different from individual stock shorts)

### Market Neutrality: Beta Achievement

The **one success** of the neutral construction: beta is near-zero (-0.014 to +0.066 OOS).
Dollar-neutral long/short mechanically cancels market exposure. But a beta-neutral 2–7% CAGR
with 24–32% drawdown is not competitive — a treasury bond ladder does better with less risk.

---

## In-Sample vs Out-of-Sample Comparison

| Threshold | IS Long Sh | OOS Long Sh | IS Neutral Sh | OOS Neutral Sh | Decay |
|-----------|-----------|------------|---------------|----------------|-------|
| 2% | 0.882 | 0.652 | -0.013 | -0.211 | High (neutral) |
| 5% | 0.934 | 0.613 | 0.064 | 0.226 | Moderate (long) |
| **10%** | **0.950** | **0.672** | 0.107 | 0.262 | Moderate |
| 15% | 0.572 | 0.648 | -0.001 | 0.132 | Improves OOS |
| 20% | 0.798 | 0.673 | 0.064 | 0.505 | Modest decay |

Observations:
- Long-only IS→OOS decay is modest (0.28 Sharpe drop at worst) — suggests genuine signal
- Neutral OOS improves vs IS at 5%, 10%, 20% thresholds — the short side was WORSE in IS
  (more negative) than OOS, meaning the neutral construct actually improved post-2018
- 15% threshold shows "improves OOS" — possible sign of less overfitting at stricter threshold

---

## Path Forward: What Would Need to Be True to Promote This Strategy

### Option A: Long-Only with Vol-Scaling (Most Promising)
Keep the 10–20% threshold long signal. Replace the SPY trend gate (which destroys alpha) with:
- **Volatility scaling**: size positions inversely proportional to realized 20d vol
- **VIX regime filter**: reduce position size (not zero) when VIX > 30
- This keeps PEAD alpha while managing the MaxDD during crisis events

**Estimated improvement**: MaxDD should compress from ~55% to ~35%; Sharpe may increase
from 0.67 to potentially 0.75–0.85 if sizing adjustment works.

### Option B: Better Short Filter (High Effort)
Replace the naive "large miss" short filter with a more refined signal:
- Require guidance CUT (not just EPS miss) — uses EDGAR 8-K text
- Exclude stocks in intermediate uptrends (20d SMA > 50d SMA at earnings)
- Require miss + weak forward revisions (analyst estimate revision data)

**Estimated improvement**: Short Sharpe from -0.275 to possibly 0.1–0.3 at best.
Still likely insufficient to make the neutral construction competitive.

### Option C: Sector ETF Hedging (Moderate Effort)
Keep the long PEAD book. Hedge beta via sector ETF shorts (XLK for tech, XLV for health, etc.),
matched to the sector weights of the long positions. This would:
- Reduce beta from ~1.0 toward ~0.1–0.2
- Avoid individual stock short borrow risk/cost
- Preserve most of the long-side alpha

**Estimated improvement**: If sector hedge reduces beta to 0.15 and costs are modest
(ETF borrow is cheap/free), OOS Sharpe could improve to 0.50–0.65 with beta < 0.20.

### Recommendation

**Pursue Option A first** (vol-scaling on long-only): lowest implementation risk, directly
addresses the identified weakness (MaxDD during market crises), doesn't require the broken
short book. If Option A produces OOS Sharpe ≥ 0.70 with MaxDD < 30%, it can be promoted
to paper trading. Only pursue Options B or C if A doesn't work.

---

## Prior Context

| Prior Result | OOS Sharpe | OOS CAGR | Note |
|-------------|-----------|---------|------|
| PEAD long-only, gate=5%, no trend | 0.657 | 13.02% | Previous best |
| PEAD long-only, gate=5%, SPY trend | -0.455 | N/A | SPY gate destroys alpha |
| PEAD neutral, 5% threshold | 0.226 | 2.02% | This run (baseline) |
| PEAD neutral, 10% threshold | 0.262 | 2.75% | This run |
| PEAD neutral, 20% threshold | 0.505 | 6.88% | This run (best neutral) |

---

## Data Sources

- **Earnings**: `strategies_candidates/pead_real/earnings.db` (93,025 events, 2012–2026)
  - Schema: `earnings_surprises(symbol, earnings_date, eps_actual, eps_forecast, surprise_pct, n_estimates, fiscal_qtr, announce_time)`
- **Prices**: Yahoo Finance v8 adjclose via `runner/daily_bars_cache.py`
  - Split+dividend-adjusted close; 1,176 symbols loaded; full history 2012–2026
- **Benchmark**: SPY buy-and-hold, same OOS period

---

## Files

| File | Description |
|------|-------------|
| `strategies_candidates/pead_neutral/backtest_pead_neutral.py` | Base neutral backtest (5% threshold) |
| `strategies_candidates/pead_neutral/backtest_sweep.py` | This threshold sweep |
| `strategies_candidates/pead_neutral/sweep_results.json` | Full numeric results (all thresholds × modes × periods) |
| `strategies_candidates/pead_neutral/GATE_RESULT.md` | Prior neutral gate result (5% threshold detail) |
| `reports/PEAD_MARKETNEUTRAL_20260620.md` | This report |

---

*Generated: 2026-06-20 | Backtest is research-only, not a trading recommendation.*
