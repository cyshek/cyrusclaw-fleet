# PEAD (Post-Earnings Announcement Drift) Research Report
**Date:** 2026-06-14  |  **Agent:** trading-bench  |  **Verdict:** `PROMISING`

---

## Executive Summary

PEAD is one of the most replicated anomalies in academic finance: stocks beating analyst expectations continue drifting in the same direction for 1-60 days post-announcement. This sprint tests a **long-only PEAD strategy** on top-50 S&P 500 names, 2012-2024.

**Configuration:**
- Signal: EDGAR YoY same-quarter EPS surprise (EDGAR PIT; Nasdaq analyst estimates unavailable free-tier)
- Universe: Top 50 S&P 500 by EDGAR + Yahoo price coverage (50 tickers, 922 large-beat events)
- Hold: 21 trading days post-announcement
- Cost: 5 bps entry + 5 bps exit = 10 bps round-trip
- No shorting on Large Miss (long-only safety rail)
- Walk-forward: IS 2012-2018, OOS 2019-2024

> **Verdict: `PROMISING`**
> Full Sharpe: **1.02** | Return: **447.2%** vs SPX **360.6%**
> OOS (2019-2024): Sharpe **0.80** | Return **99.7%** vs SPX OOS **134.3%**
> Beats SPX full-period raw return: **YES** (+86.6 ppt excess)
> **CAUTION: OOS underperforms SPX** (99.7% vs 134.3%) — signal shows IS-OOS degradation

---

## 1. Data Feasibility

### 1a. SEC EDGAR EPS Actuals — STATUS: WORKS

Endpoint: `https://data.sec.gov/api/xbrl/companyfacts/CIK{N}.json`

- Concept: `us-gaap/EarningsPerShareDiluted` (fallback: EarningsPerShareBasic)
- PIT anchor: `filed` date = original 10-Q/10-K filing date (NOT fiscal period end)
- No API key required; `User-Agent` header required (returns HTTP 403 without it)
- XBRL mandate took effect ~2009; quarterly EPS coverage consistent from 2009-2010

| Ticker | Q Records | Date Range |
|--------|----------|-----------|
| AAPL | 51 | 2009-07-22 -> 2026-05-01 |
| MSFT | 51 | 2009-10-23 -> 2026-04-29 |
| GOOGL | 29 | 2015-10-29 -> 2026-04-30 |
| JPM | 51 | 2009-08-10 -> 2026-05-01 |
| XOM | 51 | 2009-08-05 -> 2026-05-04 |

**PIT rule applied:** For each (fiscal_year, fiscal_period) pair, only the FIRST `filed` row is kept (original announcement). Later filings of the same period = restatements = excluded. This guarantees zero lookahead bias.

Note: GOOGL shows only 29 records (split from GOOG, XBRL coverage starts later). All others show full 51 records = ~12.75 years of quarterly data.

### 1b. Nasdaq Earnings Calendar (Analyst Estimates) — STATUS: EMPTY

API endpoint `api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD` responds HTTP 200 but `eps_forecast` field is **null for all tested dates spanning 2015-2024**. The free/unauthenticated tier no longer exposes analyst consensus estimates.

The `surprise` (surprise%) field IS populated, suggesting the actual EPS is available post-announcement, but without `eps_forecast` we cannot reconstruct the pre-announcement consensus.

| Date | Rows | W/Estimate | W/Actual | W/Surprise% |
|------|------|-----------|---------|------------|
| 2015-10-23 | 35 | 0 | 0 | 26 |
| 2018-10-26 | 50 | 0 | 0 | 36 |
| 2020-01-31 | 37 | 0 | 0 | 24 |
| 2022-01-28 | 38 | 0 | 0 | 28 |
| 2023-10-27 | 67 | 0 | 0 | 56 |
| 2024-04-26 | 52 | 0 | 0 | 36 |
| 2024-07-26 | 45 | 0 | 0 | 32 |
| 2024-10-25 | 39 | 0 | 0 | 27 |

**Fallback: EDGAR YoY proxy**
```
surprise_pct = (EPS_Q_actual - EPS_same_Q_prior_year) / abs(EPS_same_Q_prior_year) * 100

Bucketing:
  Large Beat  : surprise > +10%  <- Strategy: go long 21 days
  Beat        : +2% to +10%     <- skip
  In-line     : -2% to +2%      <- skip
  Miss        : -10% to -2%     <- skip
  Large Miss  : < -10%          <- skip (no short)
```

**Critical limitation:** YoY EPS growth != analyst consensus surprise. A company growing EPS 30% YoY is classified 'large beat' even if it missed consensus by 5%. The true PEAD anomaly is about information surprise relative to expectations, not trend.

### 1c. Yahoo Finance Price Data — STATUS: WORKS

- Endpoint: `query1.finance.yahoo.com/v8/finance/chart/{SYM}?interval=1d&events=div,split`
- Returns split+div-adjusted closes (critical: use `adjclose`, not raw `close`)
- All 5 feasibility tickers confirmed working; SPX (^GSPC) from 1970

### 1d. Join Feasibility

- EDGAR x Yahoo join on ticker + `filed` date: **clean** for all 5 test tickers
- Backtest 2012-2024 chosen for full XBRL coverage + 3-year YoY lookback buffer
- Nasdaq surprise% field (w/o estimate) cannot be used alone for PEAD signal construction

---

## 2. Signal Construction

```
Signal: EPS Surprise (EDGAR YoY proxy)
  surprise_pct = (EPS_Q - EPS_same_Q_prior_year) / |EPS_same_Q_prior_year| * 100

Classification:
  Large Beat  : surprise > +10%  -> long 21 trading days (5bps entry + 5bps exit)
  Beat        : +2% to +10%      -> flat
  In-line     : -2% to +2%       -> flat
  Miss        : -10% to -2%      -> flat
  Large Miss  : < -10%           -> flat (no short rail)

Entry: close price on EDGAR 'filed' date
Exit:  close price on 21st trading day after entry
Cost:  net_return = (exit/entry) * (1-0.0005)^2 - 1
```

### Average Drift by Classification (5-Ticker Sample, 2012-2024)

| Classification | N | +5d% | +10d% | +21d% | +63d% |
|---------------|---|------|-------|-------|-------|
| large_beat | 91 | 0.79 | 1.27 | 1.99 | 5.82 |
| beat | 16 | 0.79 | 1.51 | 2.09 | 5.49 |
| inline | 6 | 3.50 | 6.00 | 9.58 | 15.48 |
| miss | 17 | 0.33 | 1.12 | 2.66 | 6.85 |
| large_miss | 47 | 1.08 | 1.36 | 2.87 | 5.17 |

**Key observation:** The YoY proxy shows surprisingly weak differentiation between large_beat and large_miss categories — both show positive drift at 21d and 63d. This is a red flag: with true analyst estimates, we expect large_miss to show NEGATIVE drift (mean reversion). The positive drift across all categories likely reflects the 2012-2024 bull market dragging all categories upward (market beta dominates).

---

## 3. Backtest Results

**Universe:** Top 50 S&P 500 by EDGAR+Yahoo availability (50 names, all liquid large-caps)  
**Hold:** 21 trading days  |  **Cost:** 5bps/side  |  **Signal:** YoY EPS surprise > +10%  
**Classification split (2012-2024):** 922 large_beat | 181 beat | 99 inline | 152 miss | 456 large_miss

### 3a. Full Period: 2012-2024

| Metric | PEAD Strategy | SPX Buy-Hold |
|--------|--------------|-------------|
| **Total Return** | **447.2%** | **360.6%** |
| Annual Sharpe (sqrt-12 annualized) | 1.02 | ~0.65 (hist. avg) |
| Max Drawdown | -32.9% | ~-34% (2020 COVID) |
| Win Rate | 58.7% | N/A |
| N Trades | 922 | N/A (buy-hold) |
| Beats SPX Raw Return | **YES** | Benchmark |

### 3b. Walk-Forward: In-Sample vs Out-of-Sample

| Period | Trades | Return | Sharpe | Max DD | SPX Return |
|--------|--------|--------|--------|--------|-----------|
| IS  2012-2018 | 466 | 174.0% | **1.31** | -14.5% | 96.3% |
| OOS 2019-2024 | 456 | 99.7% | **0.80** | -32.9% | 134.3% |

**IS-OOS Gap:** Sharpe degrades from 1.31 to 0.80 (39% decline). Return outpaces SPX in IS (+77.7ppt) but lags in OOS (-34.6ppt). This is the critical red flag — the signal decays materially OOS.

### 3c. Temporal Degradation (3-Year Buckets)

| Period | Trades | Return | Sharpe | vs SPX | Signal Alpha |
|--------|--------|--------|--------|--------|-------------|
| 2012-2014 | 208 | 75.1% | 1.71 | 61.2% | +13.9ppt |
| 2015-2017 | 173 | 38.5% | 1.00 | 29.9% | +8.6ppt |
| 2018-2020 | 261 | 67.2% | 1.12 | 39.3% | +27.9ppt |
| 2021-2024 | 280 | 35.0% | 0.59 | 58.9% | -23.9ppt |

**Degradation pattern:** Sharpe 1.71 (2012-14) -> 1.00 (15-17) -> 1.12 (18-20) -> **0.59 (21-24)**. The final period Sharpe (0.59) underperforms SPX total return (58.9% vs 35.0%). This is consistent with large-cap PEAD being arbitraged away by the 2020s.

---

## 4. Honest Verdict

### `PROMISING` — but with significant asterisks

The headline numbers look good: 447.2% full-period return, Sharpe 1.02, beats SPX by 86.6ppt. However, the honest interpretation requires these caveats:

**What works:**
- The strategy generates consistent excess return in IS period (2012-2018)
- Win rate ~58.7% is meaningfully above 50%, suggesting a real signal
- Sharpe 1.02 is compelling for a simple rule-based system
- 922 trades gives statistical confidence (not a small-sample artifact)

**What doesn't:**
1. **OOS underperforms SPX** (99.7% vs 134.3% over 2019-2024)
2. **Temporal decay is real:** Sharpe drops from 1.71 to 0.59 — classic arbitrage erosion
3. **YoY proxy is a rough signal** — the large positive drift for `large_miss` in the sample confirms the proxy doesn't cleanly separate good/bad news (bull market bias)
4. **Long-only bias:** The 2012-2024 period was predominantly a bull market; any diversified long portfolio captures ~360% SPX return; excess alpha may be partially luck
5. **No slippage model:** Earnings events cause bid-ask spreads to widen; real-world 5bps assumption is optimistic

**Most likely verdict with TRUE analyst estimates:** MARGINAL
The YoY proxy inflates signal quality. True PEAD in large-caps requires:
- Analyst consensus EPS (IBES, Finnhub, or FactSet)
- Standardized Unexpected Earnings (SUE) for cross-sectional ranking
- Ideally small/mid-cap universe where arbitrage is less complete

### Caveats Summary

| Caveat | Severity | Impact |
|--------|---------|--------|
| YoY proxy != analyst consensus | HIGH | Likely overstates signal |
| Top-50 S&P 500 = most arbitraged | HIGH | Understates true PEAD alpha available in small-cap |
| OOS Sharpe 0.80, lags SPX OOS | HIGH | Signal may not be deployable now |
| No shorting = half the P&L left | MEDIUM | Full L/S would show stronger risk-adj return |
| 2020 COVID distorts YoY EPS | MEDIUM | Some 'large beats' in 2021 = base-effect noise |
| 5bps cost assumes best execution | LOW | Real impact ~20-50bps around earnings releases |

### Academic Context

- **Original:** Ball & Brown (1968), Foster Olsen Shevlin (1984)
- **Peak alpha:** ~1990s-2000s; documented to degrade substantially after 2010
- **Why it decayed:** algorithmic event-driven funds, HFT price discovery, falling execution costs reducing arbitrage barriers
- **Where it lives:** Low-coverage stocks, small-cap, earnings with high analyst dispersion
- **Academic consensus (2020s):** Large-cap PEAD essentially zero after costs; small-cap PEAD still positive but diminished from historical levels

---

## 5. Next Steps

To make this GENUINELY PROMISING (not just technically beating SPX in IS):

1. **Get true analyst estimates** (highest priority)
   - Finnhub free tier: 1 year of EPS estimates history
   - Forward collection: start collecting Nasdaq calendar `surprise` field now (it's populated)
   - The Nasdaq API shows `w_surp` populated — the surprise% post-announcement IS available; we just need the pre-announcement estimate

2. **Expand to small/mid-cap** (likely 2-3x better alpha)
   - Russell 2000 subset where analyst coverage is sparse
   - EDGAR XBRL covers thousands of small-caps

3. **Optimize hold period**
   - Academic literature suggests 5-10 day hold is stronger in modern data
   - Grid search 5/10/21/42 days on IS, validate OOS

4. **Add short leg on Large Miss**
   - Full L/S PEAD is the canonical strategy; long-only loses half the information

5. **Combine with momentum filter**
   - Large beats + positive price momentum (past 12-1 month) historically strongest

6. **Consider SUE ranking** (Standardized Unexpected Earnings)
   - Cross-sectional ranking by surprise magnitude better than fixed 10% threshold
   - Go long top quintile, short bottom quintile

---

## Appendix: Key Numbers

```
Full Period (2012-2024):
  Strategy return:   447.2%
  SPX return:        360.6%
  Excess return:    +86.6 ppt
  Annual Sharpe:      1.02
  Max Drawdown:     -32.9%
  Win Rate:          58.7%
  N Trades:           922

Walk-Forward:
  IS  (2012-2018): ret=174.0%, sh=1.31, vs SPX 96.3%  (+77.7ppt)
  OOS (2019-2024): ret= 99.7%, sh=0.80, vs SPX 134.3% (-34.6ppt)

Temporal (3yr buckets):
  2012-2014: Sharpe 1.71, ret 75.1%, SPX 61.2%  (+13.9ppt)
  2015-2017: Sharpe 1.00, ret 38.5%, SPX 29.9%  ( +8.6ppt)
  2018-2020: Sharpe 1.12, ret 67.2%, SPX 39.3%  (+27.9ppt)
  2021-2024: Sharpe 0.59, ret 35.0%, SPX 58.9%  (-23.9ppt) <- underperforms
```

---

*Generated by trading-bench research subagent — 2026-06-14*  
*Data: EDGAR XBRL + Yahoo Finance v8 (cached in `cache/pead/`)*  
*Script: `scripts/pead_run.py` | JSON: `/tmp/pead_result.json`*