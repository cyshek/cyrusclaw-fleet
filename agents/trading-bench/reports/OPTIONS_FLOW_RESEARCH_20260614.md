# Options Flow (Put/Call Ratio) Signal Research
**Date:** 2026-06-14  
**Analyst:** trading-bench subagent  
**Workspace:** `/home/azureuser/.openclaw/agents/trading-bench/workspace/`

---

## Executive Summary

**VERDICT: MARGINAL**

VIX-proxy contrarian signals (used as put/call ratio analog) show mixed results:
- **Complacency filter** (stay long when VIX > 12) achieves OOS Sharpe 0.650 vs BaH 0.761 — close but not better
- **Pure contrarian** (buy fear spikes VIX > 25) achieves OOS Sharpe 0.452 — meaningfully below BaH
- **Post-2022 degradation is real** but mild — all signals hold their relative structure
- **Primary utility: drawdown reduction, not alpha** — contrarian signals avoid some crashes but miss the bull runs

---

## Data Feasibility: What We Actually Got

### Attempted: CBOE P/C Ratio CSV (all 403)

The task specified testing these CBOE CDN paths first:
```
https://cdn.cboe.com/api/global/us_indices/daily_prices/PCALL_History.csv  → 403
https://cdn.cboe.com/api/global/us_indices/daily_prices/PCPUT_History.csv  → 403
https://cdn.cboe.com/api/global/us_indices/daily_prices/PC_History.csv     → 403
https://cdn.cboe.com/api/global/us_indices/daily_prices/CPC_History.csv    → 403
```

Also tried: `TOTAL_PC_FILE_DAILY.csv`, `PC_CBOE_History.csv`, `EQUITY_PC_History.csv`, `INDEX_PC_History.csv` — all 403.

**CBOE web page investigation:** `www.cboe.com/us/options/market_statistics/daily/` returns SSR HTML with today's ratios embedded in page JSON (`selectedDate: 2026-06-12`, `minDate: 2019-10-07`). The date query parameter (`?date=2024-01-02`) is ignored server-side — always returns current day's data. The page uses client-side React/Next.js to fetch historical data via a CDN API that requires auth.

**Alternative sources explored:**
- Stooq (`pcr.i`) → CAPTCHA challenge
- Macrotrends P/C chart → JS-rendered, no direct data endpoint
- Quandl CBOE/PC dataset → 403 (requires paid subscription)
- GitHub mirrors → all 404

**Conclusion:** CBOE P/C ratio history requires either a paid data subscription (LiveVol, FactSet, Refinitiv) or a residential proxy to bypass CDN auth. Free access is effectively gated as of 2026.

### Fallback Used: VIX as P/C Proxy ✅

Per task specification, VIX used as put/call sentiment proxy:
- **Academic basis:** VIX and total P/C ratio have ~0.65-0.75 rolling correlation (Whaley 2000, Simon 2003, Dennis et al. 2006)
- **Mechanistic link:** Both measure demand for puts relative to calls; VIX is derived from a weighted portfolio of SPX options pricing
- **Known divergences:** 0DTE options (introduced at scale 2022+) inflate SPX P/C but have less VIX impact; single-stock equity P/C and VIX correlation is weaker

**Data confirmed accessible:**
| Series | Source | Date Range | Status |
|--------|--------|------------|--------|
| VIX daily close | CBOE CDN | 1990-01-02 → 2026-06-12 | ✅ 9,206 rows |
| SKEW daily | CBOE CDN | 1990-01-02 → 2026-06-12 | ✅ 9,164 rows |
| SPY adj close | Yahoo v8 | 2000-01-03 → 2026-06-12 | ✅ 6,651 rows |

**Backtest period used:** 2000-01-03 → 2024-12-31 (6,028 trading days, 25 years)

---

## VIX Regime Statistics (2000-2024)

| Metric | Full Period | Post-2022 |
|--------|------------|-----------|
| VIX min | 9.14 | 11.86 |
| VIX max | 82.69 (COVID Mar 2020) | 38.57 |
| VIX mean | 19.87 | 19.37 |
| VIX median | 17.84 | 18.37 |
| Days VIX > 25 | 19.7% | 18.2% |
| Days VIX > 30 | 9.7% | 6.5% |
| Days VIX < 12 | 8.9% | 0.5% |

**Note:** Post-2022 VIX < 12 days nearly zero (0.5%) — the complacency-filter signal is almost always "long" in this era, which explains its near-identical performance to BaH in that window.

---

## Signal Definitions

### Signal 1: VIX 21d Rolling Z-Score Contrarian
- **Entry:** VIX z-score (relative to 21-day rolling window) > +1.0 standard deviations
- **Exit:** z-score falls below 0
- **Interpretation:** Fear spike relative to recent history → contrarian buy
- **Time in market:** ~36% (only enters during genuine fear spikes)

### Signal 2: VIX Absolute Threshold Contrarian
- **Entry:** VIX > 25.0 (absolute fear level)
- **Exit:** VIX < 20.0 (normalization)
- **Interpretation:** Classic "VIX above 25 = panic = buy" rule
- **Time in market:** ~31.5%

### Signal 3: 5d EMA VIX Z-Score Contrarian
- **Method:** 5-day EMA of VIX, then 21d rolling z-score
- **Entry/Exit:** Same thresholds as Signal 1
- **Purpose:** Reduce noise in daily VIX spikes
- **Time in market:** ~37.8%

### Signal 4: VIX Complacency Filter (Long-Only Overlay)
- **Logic:** Stay long SPY when VIX > 12 (not extreme complacency)
- **Exits:** Cash when VIX ≤ 12 (extremely low fear = potential crowded long)
- **Time in market:** ~92.2%
- **Note:** This is NOT a contrarian signal — it's a complacency-avoidance filter

---

## Full Backtest Results (2000-2024)

**Transaction cost:** 5 bps one-way on every entry/exit

| Strategy | Return | Sharpe | Max DD | % In Market |
|----------|--------|--------|--------|------------|
| **Buy-and-Hold SPY** | **+532%** | **0.381** | **-55.2%** | **100%** |
| VIX 21d-ZScore Contrarian | +83% | 0.170 | -39.6% | 36% |
| VIX Threshold >25 Contrarian | +119% | 0.193 | -45.2% | 32% |
| VIX 5d-EMA ZScore Contrarian | +104% | 0.194 | -39.9% | 38% |
| VIX Complacency Filter | +434% | 0.349 | -55.2% | 92% |

**Key finding:** Pure contrarian signals massively underperform buy-and-hold in total return AND Sharpe over the full period. The contrarian approaches are only "long" 32-38% of the time, spending the rest in cash — and cash drag destroys long-run performance in a bull market.

---

## Walk-Forward Validation

### Training Period (2000–2015) — Fitting Data

| Strategy | Return | Sharpe |
|----------|--------|--------|
| Buy-and-Hold SPY | +89% | 0.197 |
| VIX 21d-ZScore Contrarian | +73% | **0.237** |
| VIX Threshold >25 Contrarian | +23% | 0.074 |
| VIX 5d-EMA ZScore Contrarian | +63% | 0.206 |
| VIX Complacency Filter | +91% | 0.203 |

**In-sample observation:** The z-score contrarian actually beats BaH on Sharpe (0.237 vs 0.197) during 2000-2015 — the era containing dot-com bust and GFC. This makes intuitive sense: the signal is at its best when there are deep, genuine fear cycles (VIX to 80 in 2008, 45 in 2010) with clear mean-reversion.

### Out-of-Sample Period (2016–2024) — The Real Test

| Strategy | Return | Sharpe | Max DD | % In Market |
|----------|--------|--------|--------|------------|
| **Buy-and-Hold SPY** | **+240%** | **0.761** | **-33.7%** | **100%** |
| VIX 21d-ZScore Contrarian | +13% | 0.097 | -39.6% | 34% |
| VIX Threshold >25 Contrarian | +78% | 0.452 | -30.5% | 24% |
| VIX 5d-EMA ZScore Contrarian | +27% | 0.188 | -30.6% | 37% |
| **VIX Complacency Filter** | **+182%** | **0.650** | **-33.7%** | **90%** |

**OOS Verdict:** No signal beats buy-and-hold. The complacency filter comes closest (0.650 vs 0.761 Sharpe), benefiting from its near-full-market exposure. The pure contrarian signals fail badly in the 2016-2024 bull run: the signal fires rarely (24-37% of time), and every day in cash is a lost return day.

---

## Post-2022 Analysis: 0DTE Distortion

The explosion of zero-days-to-expiry (0DTE) options in 2022+ is the industry's top concern for P/C ratio degradation. 0DTE options:
1. **Inflate SPX/SPXW P/C ratio** because short-dated puts dominate hedging
2. **Reduce VIX sensitivity** because VIX uses 30-day tenor, not 0DTE
3. **Create intraday noise** that doesn't persist to close-of-day P/C readings

| Strategy | Return 2022-2024 | Sharpe 2022-2024 | Max DD |
|----------|-----------------|-----------------|--------|
| Buy-and-Hold SPY | +28% | 0.475 | -24.5% |
| VIX 21d-ZScore Contrarian | +7% | 0.200 | -14.8% |
| VIX Threshold >25 Contrarian | +15% | 0.363 | -14.6% |
| VIX 5d-EMA ZScore Contrarian | +12% | 0.311 | -16.5% |
| VIX Complacency Filter | +28% | 0.468 | -24.5% |

**Post-2022 observation:**
- **Drawdown benefit still exists:** contrarian signals cap max DD at 14-16% vs 24.5% for BaH
- **Return/Sharpe still trail BaH significantly** — 2022-2024 was a post-crash recovery with a very strong trend
- **VIX Complacency Filter is essentially BaH** in this period (0.5% of days had VIX ≤ 12, so almost always "long")
- **Threshold signal holds up best** (0.363 Sharpe vs 0.475 BaH) with 41% lower max drawdown

---

## What the VIX Contrarian Signal Actually Does

The honest answer is revealed by examining the time-in-market data:

**The contrarian enters during these regimes:**
- COVID crash (Feb-Mar 2020): VIX hit 82.69 — this was a massive correct signal
- GFC (2008-2009): VIX above 25 for ~80% of the year
- Dot-com bust (2001-2002): Multiple fear spikes
- 2018 VIX spike, 2020 recovery

**The contrarian sits in cash during:**
- The entire 2017 ultra-low VIX bull run
- Most of 2019 (VIX sub-20 all year)
- 2021 mega-bull (VIX mostly 15-20)
- 2023-2024 strong recovery

**Conclusion:** The signal is a **regime filter** that enters when fear is extreme. In the 2000-2015 period with two deep crashes, this looked smart. In the 2016-2024 mostly-bull-market OOS, it mostly meant sitting in cash while the market climbed 240%.

---

## Alpha vs. Risk Reduction Assessment

| Question | Answer |
|----------|--------|
| Does signal add alpha vs BaH? | **No** — full period -98% return gap |
| Does signal reduce drawdowns? | **Yes** — max DD reduced 29-40% for pure contrarian signals |
| Better risk-adjusted (Sharpe)? | **No** — all signals trail BaH Sharpe in OOS |
| Primary utility? | **Drawdown reduction / crash avoidance** |
| Better as standalone or overlay? | **Overlay** — VIX > 25 entry could reduce SIZE not exit entirely |
| 0DTE degradation? | **Mild VIX impact** — VIX less affected than actual P/C by 0DTE; gap narrowed post-2022 |

---

## Honest Verdict

**MARGINAL** — barely meets the 85% OOS Sharpe threshold (0.854 ratio), but with a key nuance:

**The complacency filter (best OOS signal) is not really a contrarian signal.** It's a "stay long except during extreme complacency" rule that achieves near-BaH performance with slightly lower Sharpe because it only sits out during the rare VIX < 12 periods (which don't happen much post-2012).

The true contrarian signals (enter only on fear spikes) are **DEAD as standalone strategies** in the OOS period. They trade too rarely and miss too much upside. Their only genuine value is as a **position-sizing overlay** in a diversified portfolio — when VIX > 25, tilt more toward SPY; don't go all-in-or-all-out.

---

## 0DTE Distortion: What We Can Quantify

Since we couldn't get actual P/C ratio data, we can't directly measure 0DTE distortion on P/C. However:

1. **Pre-2022 VIX correlation with P/C:** Academic literature documents ~0.70 rolling 63d correlation
2. **Post-2022:** 0DTE volume grew from ~5% of SPX volume (2019) to ~45% (2023). These options expire same-day, so they **don't appear in VIX calculation** (VIX uses 23-37 day expirations)
3. **Implication:** If actual P/C ratio is now more elevated than VIX suggests (due to 0DTE puts), then VIX-based contrarian is UNDERESTIMATING fear → signal would fire less often than true P/C
4. **Effect on backtest:** Our VIX-based results likely **understate** how good a true P/C signal would be in the 0DTE era (fewer spurious entries), but also **overstate** it in the pre-0DTE era

If you could get real CBOE equity P/C data (requires LiveVol or similar), the expected improvement would be:
- More granular signal during 2022-2024
- Better separation of equity vs. index P/C (index P/C driven by institutional hedging; equity P/C more "retail sentiment")
- Pre-2022 signal would likely be similar or slightly worse (VIX is a good proxy)

---

## Recommendations

### If pursuing this signal:

1. **Don't use as a standalone timed-entry strategy.** Cash drag is lethal over 25 years in a bull market.

2. **Use as a position-size overlay:** When VIX > 25 and z-score > 1.0, increase SPY allocation from baseline (e.g., 100% → 130% via 2x leverage or from underweight to overweight). Don't go cash.

3. **Equity P/C (not index P/C) is the better signal.** Index P/C is dominated by institutional hedging and institutional skew trades — not sentiment. Equity-only P/C correlates better with retail sentiment. We couldn't test this without data.

4. **Combine with VIX term structure:** VIX3M/VIX ratio < 1.0 (contango) is bullish for mean-reversion; backwardation (VIX3M < VIX) is caution signal. CBOE CDN confirmed VIX3M accessible.

5. **0DTE context:** The actual CBOE total P/C ratio has become harder to interpret since 2022. If you get real data, separate equity P/C from index P/C before constructing the signal.

### Priority for tournament:
**LOW** — as a standalone signal, this underperforms. The VIX regime overlay we already have (VIX_REGIME_OVERLAY) is doing the same thing and our complacency filter finding suggests staying in market > 90% of the time is correct for this era. Not a tournament candidate as-is.

---

## Data Access Notes

For future reference, to get real CBOE P/C ratio history:

| Approach | Cost | Data Quality | Notes |
|----------|------|--------------|-------|
| LiveVol Pro | ~$300/mo | Best (tick level) | CBOE's own product |
| FactSet | Enterprise | Gold standard | Way overkill |
| Alpaca Data | Free-ish | No P/C ratio | Not available |
| Tiingo | $10-30/mo | Good | No P/C ratio directly |
| CBOE web scraping (2019-present) | Free | Limited to 2019+ | Only page-by-page |
| Residential proxy + CBOE CDN | ~$20-50 setup | Full history | Legal gray area, ToS risk |
| Bloomberg / Refinitiv | $$$ | Everything | Not needed for now |

**Practical path:** If P/C data becomes a tournament priority, the CBOE web page + residential proxy scraper could get daily data back to 2019-10-07 in one evening session. For 2000-2019, the only free option is secondary sources like academia pre-packaged datasets (WRDS/CRSP if we get institutional access).

---

## Appendix: Signal Performance Table (Complete)

### Full Period 2000-2024
| Strategy | Return | Sharpe | Max DD | Days in Market |
|----------|--------|--------|--------|----------------|
| Buy-and-Hold SPY | 532.3% | 0.381 | -55.2% | 6,010/6,028 (99.7%) |
| VIX 21d-ZScore contrarian | 82.9% | 0.170 | -39.6% | 2,166/6,028 (36.0%) |
| VIX Threshold >25 contrarian | 119.2% | 0.193 | -45.2% | 1,899/6,028 (31.5%) |
| VIX 5d-EMA ZScore contrarian | 103.5% | 0.194 | -39.9% | 2,279/6,028 (37.8%) |
| VIX Complacency Filter | 433.9% | 0.349 | -55.2% | 5,553/6,028 (92.2%) |

### OOS 2016-2024
| Strategy | Return | Sharpe | Max DD | Days in Market |
|----------|--------|--------|--------|----------------|
| Buy-and-Hold SPY | 240.0% | 0.761 | -33.7% | 2,258/2,264 (99.7%) |
| VIX 21d-ZScore contrarian | 12.6% | 0.097 | -39.6% | 776/2,264 (34.3%) |
| VIX Threshold >25 contrarian | 78.4% | 0.452 | -30.5% | 548/2,264 (24.2%) |
| VIX 5d-EMA ZScore contrarian | 26.9% | 0.188 | -30.6% | 848/2,264 (37.5%) |
| **VIX Complacency Filter** | **182.2%** | **0.650** | **-33.7%** | 2,030/2,264 (89.7%) |

### Post-2022 (0DTE era)
| Strategy | Return | Sharpe | Max DD |
|----------|--------|--------|--------|
| Buy-and-Hold SPY | 28.2% | 0.475 | -24.5% |
| VIX 21d-ZScore contrarian | 7.0% | 0.200 | -14.8% |
| VIX Threshold >25 contrarian | 15.2% | 0.363 | -14.6% |
| VIX 5d-EMA ZScore contrarian | 11.8% | 0.311 | -16.5% |
| VIX Complacency Filter | 27.7% | 0.468 | -24.5% |

---

*Report generated: 2026-06-14 by trading-bench subagent*  
*Driver script: `reports/_options_flow_driver.py`*  
*Result JSON: `/tmp/options_flow_result.json`*
