# COT (Commitments of Traders) Macro Factor Timing Research

**Date:** 2026-06-14  
**Type:** Research sprint — backtest feasibility + walk-forward  
**Verdict:** ⚠️ **MARGINAL** — best OOS Sharpe 0.929 vs BAH 0.836, but **does NOT beat BAH total return**  
**Prior study:** 2026-06-05 (same data, different scoring — GATE test; FP-cont Sharpe = 0.930, REJECT)  
**Script:** `/tmp/cot_macro_backtest.py`  
**Results:** `/tmp/cot_result.json`

---

## 1. Data Feasibility

### Source
CFTC Commitments of Traders — **Traders in Financial Futures (TFF)** format.  
Already cached from prior research (2026-06-05).

| Property | Value |
|---|---|
| Data source | CFTC bulk annual zips (`fut_fin_txt_YYYY.zip`) |
| Cache location | `data_cache/cot/parsed_YYYY.json` (2010–2026) |
| COT records (ES) | **829 weekly snapshots** |
| COT date range | 2010-07-20 → 2026-06-02 |
| SPY price range | 2007-01-03 → 2026-06-12 (4,892 trading days) |
| Backtest window | **2011-01-01 → 2024-12-31** (needs z-score warmup) |

### Critical caveat: TFF starts 2010, NOT 2006
The task spec mentioned data back to 2006. That applies to a **different** CFTC file format (Disaggregated Futures). **TFF format (Traders in Financial Futures) begins July 2010.** This means:
- The **2008 GFC is not covered** — the most decisive stress test for any market-timing signal.
- The 2007 pre-crisis period is also excluded from backtest.
- Walk-forward train window (2011–2016) misses the GFC entirely.

### Publication lag enforcement
COT snapshots positions as of **Tuesday's close**, published following **Friday** (~3 calendar days). The backtest strictly enforces this: a Tuesday snapshot dated `YYYY-MM-DD` is only available from the following Friday. No lookahead. This was verified via the existing `runner/cot_cache.py` infrastructure (`CotLookaheadError` canary).

### Signal construction
Three trader categories extracted:
- `lev_net_pct` = (Leveraged Funds long - short) / OI — hedge-fund/CTA positioning
- `am_net_pct` = (Asset Manager long - short) / OI — institutional real money
- Z-scores computed with 52-week (1yr) and 104-week (2yr) rolling lookbacks

Weekly signals forward-filled to daily (no interpolation — future-free forward fill).

---

## 2. Signals Tested

| Signal | Description | Direction |
|---|---|---|
| `am_momentum` | AM net increases WoW → long SPY | Momentum |
| `lev_contrarian_z52` | Lev funds extreme short (z < −1.5, 52w) → long | Contrarian |
| `lev_contrarian_z104` | Lev funds extreme short (z < −1.5, 104w) → long | Contrarian |
| `combined` | AM WoW > 0 AND lev z104 > −1.5 → long | Combined |
| `lev_momentum_z104` | Lev funds net long (z > 0) → long | Momentum |
| `am_contrarian_z52` | Fade extreme lev-fund longs (z52 > 1.5 → cash) | Defensive |

---

## 3. Backtest Results

### 3a. Full Period (2011–2024, ~14 years)

| Signal | Sharpe | Return | CAGR | Max DD | Avg Deployed | Trades |
|---|---|---|---|---|---|---|
| **BUY & HOLD** | **0.837** | **496.0%** | **13.7%** | **33.7%** | 100% | 1 |
| am_momentum | 0.772 | 165.1% | 7.3% | 14.1% | 45% | 373 |
| am_contrarian_z52 | 0.697 | 283.2% | 10.2% | 31.2% | 89% | 71 |
| lev_momentum_z104 | 0.681 | 215.2% | 8.6% | 28.7% | 55% | 98 |
| combined | 0.556 | 85.7% | 4.5% | 14.5% | 38% | 337 |
| lev_contrarian_z104 | 0.446 | 36.7% | 2.3% | 15.3% | 9% | 40 |
| lev_contrarian_z52 | 0.044 | 1.3% | 0.1% | 14.2% | 8% | 42 |

**BAH is the dominant strategy on full-period total return by a wide margin** (496% vs. best signal 283%).

### 3b. Train Period (2011–2016, ~6 years)

| Signal | Sharpe | Return | CAGR | Max DD |
|---|---|---|---|---|
| **BUY & HOLD** | **0.843** | **99.1%** | **12.4%** | **18.6%** |
| am_contrarian_z52 | 0.761 | 79.5% | 10.4% | 17.3% |
| lev_contrarian_z104 | 0.734 | 12.7% | 2.0% | 2.4% |
| lev_contrarian_z52 | 0.637 | 12.9% | 2.0% | 3.0% |
| lev_momentum_z104 | 0.621 | 48.7% | 6.8% | 14.4% |
| am_momentum | 0.540 | 30.7% | 4.7% | 13.6% |
| combined | 0.315 | 15.0% | 2.4% | 14.5% |

### 3c. OOS Period (2017–2024, ~8 years — the crucial test)

| Signal | Sharpe | Return | CAGR | Max DD | Beats BAH? |
|---|---|---|---|---|---|
| **am_momentum** | **0.929** | **102.8%** | **9.2%** | **14.1%** | ❌ Sharpe✓/Return✗ |
| **BUY & HOLD** | **0.836** | **197.1%** | **14.7%** | **33.7%** | — |
| combined | 0.738 | 61.4% | 6.2% | 13.7% | ❌ |
| lev_momentum_z104 | 0.716 | 110.3% | 9.8% | 28.7% | ❌ |
| am_contrarian_z52 | 0.659 | 113.5% | 10.0% | 31.2% | ❌ |
| lev_contrarian_z104 | 0.399 | 21.4% | 2.5% | 15.3% | ❌ |
| lev_contrarian_z52 | −0.214 | −10.3% | −1.4% | 14.2% | ❌ |

---

## 4. Honest Verdict

### What works and what doesn't

**`am_momentum` is the best cell:** When Asset Managers increase their net S&P futures position WoW → go long SPY. OOS Sharpe 0.929 vs BAH 0.836 — **better risk-adjusted return** — but it's only deployed 45% of the time, so the **absolute return (102.8%) is half of BAH (197.1%).** 

The strategy has genuinely attractive risk properties:
- Max DD 14.1% vs BAH 33.7% — **half the drawdown**
- CAGR 9.2% on 45% deployment — reasonable capital efficiency

But it is a **timing/DD-reduction tool, NOT an alpha generator.** On risk-adjusted basis it edges out BAH; on raw return it decisively loses.

### Is the 3-day lag fatal?
No. The AM-momentum signal survives after enforcing the publication lag strictly. The signal appears to capture intermediate-term institutional flow (weeks to months), not the initial market move. The 3-day lag doesn't kill it.

### Why can't it beat BAH return?
Simple math: deployed only 45% of the time in a bull market means capturing only ~half the upside. The 2011–2024 period was massively skewed toward equity gains (S&P 5× in 14 years). A timing signal that goes to cash frequently in a secular bull market will lose on absolute return regardless of Sharpe.

### Does COT positioning add alpha vs buy-and-hold?
- **Risk-adjusted (Sharpe):** Yes, marginally. OOS Sharpe 0.929 vs 0.836 — but that's a ~11% improvement, not transformative.
- **Total return:** No. Every signal underperforms BAH on raw return in OOS.
- **Drawdown reduction:** Yes, significantly. Max DD 14.1% vs 33.7% — this is real.

### Structural weaknesses
1. **Missing 2008 GFC** — TFF data starts July 2010. A signal that can't be tested on the largest drawdown of the era is structurally incomplete. We don't know if AM-momentum would have signaled correctly in 2008.
2. **Signal correlation vs. vol** — Per prior study (2026-06-05), lev-fund positioning z-scores correlate ~0.45–0.53 with SPY realized vol, meaning the "orthogonal" signal partially re-encodes what the vol regime already knows.
3. **Low deployment on bull markets** — The strategy works by avoiding drawdowns, which means it systematically sits out bull runs. In a secular bear or choppy market it would likely shine; in a secular bull it's a performance drag.
4. **OOS Sharpe inconsistency** — `am_momentum` Sharpe jumps from 0.540 (train) to 0.929 (OOS), suggesting possible regime dependency rather than a stable structural edge.

### Comparison to prior study (2026-06-05)
| | Jun-05 Study | Jun-14 Study |
|---|---|---|
| Best signal | `lev_momentum_z104` (lev-fund momentum) | `am_momentum` (AM momentum) |
| Best FP Sharpe | 0.930 (FP-cont, GATE metric) | 0.772 (annualized daily) |
| Best OOS Sharpe | — (not computed separately) | 0.929 |
| Verdict | REJECT (< 1.0 GATE) | MARGINAL |
| Data start | 2010-07 | 2010-07 |

The two studies are consistent: COT provides some signal but not enough to clear a strict gate. The Jun-14 study uses a traditional Sharpe + walk-forward framing, the Jun-05 study used the internal GATE metric. Both find the same result: promising but not convincingly alpha-generative.

---

## 5. Final Verdict

### **MARGINAL**

**COT is a timing/drawdown-reduction tool, not an alpha generator.**

- OOS Sharpe edges BAH (0.929 vs 0.836) — genuinely better risk-adjusted
- Max DD roughly halved (14% vs 34%) — genuine defensive value
- Absolute return lags BAH (103% vs 197% OOS) — not an alpha source
- Missing 2008 GFC data prevents definitive stress-test assessment
- Signal appears to be partially proxying vol regime (not fully orthogonal)
- Consistent with Jun-05 REJECT finding at the 1.0 FP-cont GATE

**Decision:** Do not promote to live strategies. Maintain `runner/cot_cache.py` as reusable infrastructure. Consider COT as **one input into a composite signal** (e.g., macro regime gate) rather than a standalone timing signal.

**If COT should be revisited:** The highest-leverage improvement would be obtaining pre-2010 data (CFTC Disaggregated format + legacy reports back to 1986/2006) and translating to net positioning, which would expose the 2008–2009 GFC regime and provide a definitive stress test.

---

## 6. Reusable Infrastructure

The following artifacts from the Jun-05 study remain valid and are NOT throwaway:

| File | Status | Purpose |
|---|---|---|
| `runner/cot_cache.py` | ✅ Keep | PIT-correct COT ingest, publication-lag enforced |
| `data_cache/cot/` | ✅ Keep | 829 ES records 2010–2026, no re-download needed |
| `tests/test_cot_cache.py` | ✅ Keep | 5/5 pass, locks no-lookahead contract |
| `strategies_candidates/cot_*` | 🚫 Quarantine | Do not promote |

---

*Report generated: 2026-06-14 by trading-bench subagent (model: github-copilot/claude-sonnet-4.6)*  
*Backtest script: `/tmp/cot_macro_backtest.py` · Raw results: `/tmp/cot_result.json`*
