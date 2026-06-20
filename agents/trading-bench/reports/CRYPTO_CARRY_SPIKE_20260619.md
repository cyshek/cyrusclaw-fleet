# Crypto Funding Rate Carry — Feasibility Spike
**Date:** 2026-06-19  
**Author:** trading-bench subagent  
**Data:** Binance public data (Jan 2020 – May 2026, 7,029 obs/symbol) + OKX (Mar–Jun 2026)

---

## 🟡 VERDICT: CONDITIONAL-GO

**The strategy is structurally sound but materially impaired in the current regime (2026).**  
Historical gross yield: 12% (BTC), 14% (ETH). Post-2025 gross yield: ~2–5% annualized — barely above costs.  
Go if: (1) you enter during the next bull-market funding spike, or (2) you add ETH/altcoins to diversify funding exposure.  
No-go if: you need steady yield right now without timing the entry.

---

## 1. Funding Rate History

### BTC-USDT (Binance USDT-M Perpetual, Jan 2020 – May 2026)
| Metric | Value |
|--------|-------|
| Observations | 7,029 (8-hourly) |
| Period | 2020-01-01 → 2026-05-31 |
| Average 8h rate | +0.0110% |
| **Avg annualized (gross)** | **+12.0%** |
| % periods positive (longs pay shorts) | **85.6%** |

### ETH-USDT (Binance USDT-M Perpetual)
| Metric | Value |
|--------|-------|
| Average 8h rate | +0.0131% |
| **Avg annualized (gross)** | **+14.4%** |
| % periods positive | **86.3%** |

### Distribution (8h rates, annualized) — BTC
| Percentile | 8h Rate | Annualized |
|------------|---------|------------|
| Min (worst) | -0.30% | -328% |
| P5 | -0.0053% | -5.8% |
| P25 | +0.0027% | +3.0% |
| **P50 (median)** | **+0.0098%** | **+10.8%** |
| P75 | +0.0100% | +10.9% |
| P95 | +0.0486% | +53% |
| Max (best) | +0.30% | +328% |

> **Note:** The P75 = P50 = 10.9% annualized because Binance has a 0.01% cap on the standard funding rate — rates pile up at the ceiling during bull runs.

### Year-by-Year Breakdown (BTC)
| Year | N | Gross Ann% | % Positive | Median Ann% |
|------|---|-----------|------------|-------------|
| 2020 | 1,098 | 17.2% | 85.7% | 10.9% |
| 2021 | 1,095 | **30.6%** | 92.7% | 10.9% |
| 2022 | 1,095 | 4.2% | 77.9% | 5.6% |
| 2023 | 1,095 | 7.9% | 89.9% | 9.1% |
| 2024 | 1,098 | 11.9% | 91.6% | 10.9% |
| 2025 | 1,095 | 5.1% | 87.1% | 5.3% |
| **2026 (Jan–May)** | **453** | **0.9%** | **58.9%** | **1.4%** |
| **2026-Jun (OKX)** | **55** | **0.4%** | **50.9%** | — |

### Quarterly Trend (BTC) — Recent History
| Quarter | Gross Ann% | % Positive |
|---------|-----------|------------|
| 2024Q1 | 22.3% | 100% |
| 2024Q2 | 9.3% | 94.9% |
| 2024Q3 | 3.5% | 73.9% |
| 2024Q4 | 12.6% | 97.8% |
| 2025Q1 | 5.2% | 87.0% |
| 2025Q2 | 3.5% | 81.3% |
| 2025Q3 | 7.0% | 96.4% |
| 2025Q4 | 4.7% | 83.7% |
| 2026Q1 | 1.2% | 62.6% |
| **2026Q2 (partial)** | **0.3%** | **53.6%** |

**The decay signal is clear:** 2026 Q1–Q2 shows rate compression to near-zero, with multiple consecutive months going NEGATIVE (Feb: -0.8%, Mar: -1.1%, Apr: -2.2% annualized).

### Is the Decay Structural?
Likely yes — for now. Causes:
1. **Market maturation:** More sophisticated arb capital has compressed the basis. In 2020-21, the perp premium was large (crypto was retail-dominated, longs were reckless). As institutional and arb capital grew, the premium compressed.
2. **Current market regime (2026):** BTC consolidating/ranging after 2024-25 run — less speculative fever = less demand to go long perp = lower funding.
3. **History suggests it recovers:** Every bear/flat year (2022, mid-2024, 2025H1) was followed by a resurgence during the next bull run. Funding is mean-reverting around market sentiment.

---

## 2. Net Yield After Costs

### Cost Structure
| Cost Item | Amount | Basis |
|-----------|--------|-------|
| Perp short entry (taker + slippage) | 0.06% | 0.05% taker + 0.01% slip |
| Spot long entry (fee + slippage) | 0.11% | 0.10% spot fee + 0.01% slip |
| Round-trip (entry + exit) | 0.34% | Both legs both ways |
| Amortized over 1yr holding period | 0.34%/yr | One entry + one exit per year |
| Weekly delta rebalancing (52×) | 0.063%/yr | 2% delta drift × 0.06% cost/event |
| **Total annual costs** | **0.40%/yr** | — |
| *Alt: spot ETF hedge (0% spot fee)* | *0.20%/yr* | — |

### Net Yield by Year (BTC)
| Year | Gross% | Costs% | Net% | Net (ETF hedge) |
|------|--------|--------|------|----------------|
| 2020 | 17.2% | 0.40% | **16.8%** | 17.0% |
| 2021 | 30.6% | 0.40% | **30.2%** | 30.4% |
| 2022 | 4.2% | 0.40% | **3.8%** | 4.0% |
| 2023 | 7.9% | 0.40% | **7.5%** | 7.7% |
| 2024 | 11.9% | 0.40% | **11.5%** | 11.7% |
| 2025 | 5.1% | 0.40% | **4.7%** | 4.9% |
| **2026 (YTD)** | **0.9%** | **0.40%** | **+0.5%** | **+0.7%** |

**2026 reality check:** At current rates, $100k capital earns ~$500/yr net. This is not worth the operational complexity + exchange risk + margin monitoring.

---

## 3. Automability Assessment

### Can Alpaca do this?
**NO.** Alpaca is equity paper trading + crypto SPOT only. No perpetual futures, no funding rate mechanism.

### Exchange API Support
| Exchange | Perp API | Paper/Demo | Status from VM |
|----------|----------|------------|----------------|
| **OKX** | ✅ Full REST + WS | ✅ Demo with `x-simulated-trading: 1` header | ✅ **ACCESSIBLE** |
| Binance USDT-M | ✅ Full REST + WS | ✅ Testnet at testfapi.binance.com | ❌ 451 geo-blocked (US restriction) |
| Bybit | ✅ Full REST + WS | ✅ Testnet | ❌ 403 CloudFront geo-block |
| dYdX v4 | ✅ Decentralized | ✅ No geo-block | ⚠️ Unstable connection from VM |

**Best choice: OKX.** Their API is accessible from this Azure VM, they offer a full paper trading environment (identical API, just add `x-simulated-trading: 1` header), and they have full perpetual swap support with public funding rate history.

### Paper Tracking (No Real Account)
**Fully possible.** The P&L simulation is trivial:
```python
# P&L per period = funding_rate × notional (received when short)
# Update mark-to-market on spot leg vs perp leg
# Track cumulative funding received + unrealized P/L from basis drift
```
We can simulate live paper positions using OKX's real-time funding rates + price feeds without any real capital.

### Minimum Capital for Practicality
| Capital | Net Yield (~12% historical) | Net (2026 ~0.5%) |
|---------|----------------------------|------------------|
| $10k | $1,160/yr | $50/yr |
| $50k | $5,800/yr | $250/yr |
| $100k | $11,600/yr | $500/yr |
| $500k | $58,000/yr | $2,500/yr |

**Minimum contract sizes:** BTC-PERP min lot = 0.001 BTC ≈ $100; practically trade 0.01–0.1 BTC lots ($1k–$10k notional). No meaningful capital floor technically, but below $10k the per-trade costs dominate.

---

## 4. Key Risks

### 1. Funding Rate Compression (CURRENT STATE — most critical)
- **Risk:** Funding rate has compressed to near-zero/negative in 2026.
- **Evidence:** Feb 2026: -0.8% ann, Mar: -1.1%, Apr: -2.2%, May recovered to +2.7%, Jun +0.4%.
- **Worst negative run:** 8 consecutive days (Mar 2020 crash), P&L impact: -1.04% on notional.
- **Frequency of negative streaks ≥ 3 days:** 2.8% of runs; ≥ 7 days: 0.2% of runs.
- **Mitigation:** Set a minimum rate threshold (e.g., annualized < 3%) to exit position and wait.

### 2. Exchange Counterparty Risk (HIGH SEVERITY)
- **FTX precedent:** FTX collapsed Nov 2022, wiping out customers. This is not theoretical.
- **Mitigation:** Use only top-tier exchanges (OKX, Binance), keep 50% of hedge in spot (not on the same exchange as the perp), use non-custodial spot (e.g., on-chain or separate cold storage). Never keep all capital on one exchange.

### 3. Liquidation Risk
- **Scenario:** Price spikes rapidly (+20% in hours). Perp short margin gets called before spot leg can be sold to add margin.
- **Mitigation:** Use ≤2x leverage on perp (never close to liquidation price). Standard carry trade uses 1x — just enough to hold the short — so liquidation risk is low if managed.
- **Buffer needed:** Maintain 2–3x the initial margin as buffer. At 1x leverage with $50k notional, liquidation is only triggered by near-total loss scenario.

### 4. Basis Risk (Perp vs Spot Divergence)
- **Risk:** During market stress, perp can trade at significant discount to spot (perp price ≠ index). Your hedge won't be 1:1.
- **Typical deviation:** <0.1% under normal conditions. During extreme stress, can be 0.5–2%.
- **Impact:** Low on a single-position, meaningful if you're running high leverage.

### 5. Operational/Automation Risk
- **API changes, rate limits, connectivity failures** can cause the hedge to break temporarily.
- **Mitigation:** Monitor hedge ratio continuously, alert on deviation >2%.

---

## 5. Verdict Deep-Dive and Recommended Next Step

### Why CONDITIONAL-GO (not NO-GO)
The strategy is NOT dead. 2026's low rate is consistent with every previous flat/bear crypto period (2022, Aug-Sep 2024), and the rate recovered each time sentiment shifted. The mechanism is structural — as long as crypto attracts leveraged retail longs, the positive carry bias persists.

The question is not "does it work?" (it does, historically 12% gross) — it's "does it work *right now*?" Current answer: barely. 0.5% net is below opportunity cost.

### CONDITIONAL on:
1. **Rate threshold trigger:** Wait for BTC funding to show ≥1% annualized for ≥30 days before entering. Don't enter during current near-zero regime.
2. **Multi-asset:** Don't just do BTC. Altcoins (ETH, SOL, DOGE during meme frenzies) often have 3-5x higher funding rates than BTC when retail is active. Diversifying across 5-10 assets smooths variance.
3. **Use OKX with paper trading first:** Implement paper simulation against OKX live data before touching real capital.

### Recommended Next Steps (if GO)
1. **Paper trade simulation:** Build a live paper portfolio tracking OKX BTC/ETH carry using `x-simulated-trading: 1` for 30 days. Confirms operational mechanics + realistic slippage.
2. **Rate monitor:** Set up a daily alert: if BTC+ETH combined annualized funding ≥ 5% for 7 days → flag as entry signal.
3. **Alt exposure:** Add ETH (higher funding historically), plus 2-3 small alts during bull market periods.
4. **Capital sizing:** Minimum $25k–$50k to be meaningful; can start paper with any size.
5. **Exchange choice:** OKX for paper (accessible from this VM); Binance testnet for Binance-specific development.

---

## Summary Statistics Reference
| Metric | BTC | ETH |
|--------|-----|-----|
| Data period | Jan 2020 – Jun 2026 | Jan 2020 – Jun 2026 |
| Records | 7,029 | 7,029 |
| Full-period gross ann | **12.0%** | **14.4%** |
| 2026 YTD gross ann | **0.9%** | **0.4%** |
| % periods positive (full) | 85.6% | 86.3% |
| % periods positive (2026) | 58.9% | 58.3% |
| Longest negative streak | 8.0 days | 8.3 days |
| Net yield after costs (full period) | **11.6%** | ~14.0% |
| Net yield (2026 current) | **~0.5%** | **~0.0%** |
| Exchange accessible from VM | OKX ✅ | OKX ✅ |
| Paper tradeable | Yes (OKX demo) | Yes (OKX demo) |
| Alpaca compatible | ❌ No | ❌ No |

---

*Data source: Binance public data S3 (data.binance.vision) for Jan 2020 – May 2026; OKX public API for Jun 2026. No authentication required.*
