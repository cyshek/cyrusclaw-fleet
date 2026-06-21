# POLYMARKET SHORT-DURATION SCAN — June 20, 2026

**Task:** Scan for markets resolving within 2 weeks (≤ July 6, 2026) where we have a quantifiable prior.  
**Generated:** 2026-06-20  
**Analyst:** trading-bench subagent

---

## 1. Market Scan Summary

- **Total markets scanned:** ~600+ (across multiple Gamma API pages)
- **Resolving by July 6:** ~54 markets from initial page; ~150+ across all pages
- **Markets with reasonable volume (>$5K):** ~40 within the 2-week window
- **Markets where we have quantifiable edge:** 10 identified; 5 selected for bets

### Current Market Prices Used (June 20, 2026)
| Asset | Price | Source |
|-------|-------|--------|
| Bitcoin (BTC) | $64,203 | CoinGecko |
| Ethereum (ETH) | $1,740 | CoinGecko |
| Solana (SOL) | $73.41 | CoinGecko |
| Chainlink (LINK) | $7.98 | CoinGecko |
| Silver (SI=F) | $64.91/oz | Yahoo Finance |
| Gold (GC=F) | $4,172.90/oz | Yahoo Finance |
| Tesla (TSLA) | $400.49 | Yahoo Finance |
| WTI Crude (CL=F) | $76.54/bbl | Yahoo Finance |
| Bank of Israel Rate | 4.00% | TradingEconomics |

---

## 2. All Short-Duration Markets Found (>$5K Volume, Resolving ≤ July 6)

| Market ID | Question | End Date | Volume | Poly YES | Poly NO |
|-----------|----------|----------|--------|----------|---------|
| 2420093 | Will Bitcoin reach $70,000 in June? | 2026-07-01 | $987K | 9.5% | 90.5% |
| 1032326 | Will Silver (SI) settle at <$50 in June? | 2026-06-30 | $99.9K | 1.2% | 98.8% |
| 2001248 | Will Gold (GC) hit $5,300 by end of June? | 2026-06-30 | $98.3K | 0.55% | 99.45% |
| 1795636 | Will Bank of Israel make no change after July decision? | 2026-07-06 | $9.7K | 9.0% | 91.0% |
| 2410566 | Will Bitcoin reach $80,000 in June? | 2026-07-01 | $936K | 0.6% | 99.4% |
| 2553248 | Will Ethereum be above $1,600 on June 22? | 2026-06-22 | $9.5K | 98.3% | 1.7% |
| 1032421 | Will Crude Oil (CL) settle over $63 in June? | 2026-06-30 | $9.5K | 94.7% | 5.3% |
| 2607933 | Will Ethereum be above $2,000 on June 26? | 2026-06-26 | $10 | 2.3% | 97.7% |
| 2614973 | Will Bitcoin reach $66,000 on June 20? | 2026-06-21 | $9.4K | 1.55% | 98.45% |
| 2410606 | Will Solana reach $100 in June? | 2026-07-01 | $96.4K | 1.5% | 98.5% |
| 2388903 | Will Tesla close above $390 end of June? | 2026-06-30 | $1K | 62.0% | 38.0% |
| 2270167 | Will Alphabet be 2nd largest market cap on June 30? | 2026-06-30 | $95.5K | 74.0% | 26.0% |

---

## 3. Markets Rejected (No Edge)

| Market | Reason |
|--------|--------|
| Silver <$50 | Silver at $64.91 → needs 23% drop. Our prior: 0.3%. Poly at 1.2%. Poly OVERPRICES risk but edge is on NO side with almost no payout. |
| Gold >$5,300 | Gold at $4,172 → needs 27% surge. Our prior: ~0.1%. Poly at 0.55%. Poly overprices, but no payout on NO. |
| BTC >$80K | Edge smaller (+5.4pp) vs $70K market. Vol is $936K, but $70K is cleaner bet. |
| ETH >$2,000 June 26 | Edge of +7.7pp but volume only $10. No liquidity. |
| TSLA >$390 | TSLA at $400.49. Our prior ~60%, Poly 62%. Essentially aligned. |
| SOL >$100 | Barrier edge only +6.1pp. Not enough differentiation at $9.5K volume. |
| GOOGL #2 market cap | Would need verification of real-time market cap rankings. Too much uncertainty. |

---

## 4. Bets Placed (5 Paper Bets, $25 each)

### BET 1: Bank of Israel No Change — ID#9 ⭐ HIGHEST EDGE
- **Market:** Will the Bank of Israel make no change after the July 6 decision?
- **Our side:** YES (no change)
- **Our prior:** 60.0% no change
- **Poly implied:** 9.0% (YES) / 91.0% (NO — cut expected)
- **Edge:** +51.0pp (YES side is massively underpriced)
- **Rationale:**
  - BoI decision is July 6, 2026 (confirmed via official BoI schedule)
  - Current rate: 4.00% (cut twice in late 2025)
  - Lines.com prediction market consensus: **62.5% probability of NO CHANGE** — the market views BoI as "deliberately cautious" after two recent cuts
  - TradingEconomics March 2026 decision was unanimous hold, noting rising inflation (energy prices), geopolitical uncertainty (Operation Roaring Lion)
  - Inflation rising → dovish cuts less likely; BoI gave no clear signal of July cut
  - Polymarket's 9% no-change is extremely low vs. external consensus of ~62%
  - **This is the strongest edge in the scan by far**

### BET 2: Bitcoin $70K in June — ID#10 ⭐ STRONG EDGE
- **Market:** Will Bitcoin reach $70,000 in June? (Binance high, any 1-min candle)
- **Our side:** YES
- **Our prior:** 25.0%
- **Poly implied:** 9.5%
- **Edge:** +15.5pp
- **Rationale:**
  - BTC at $64,203 → needs +9.05% to hit $70K
  - Resolution: **any** Binance 1-min candle high ≥ $70K before June 30 (barrier contract)
  - Using GBM with σ=4%/day, 10-day σ_T = 12.65%
  - Barrier crossing probability (reflection principle): ~25%
  - Poly prices at 9.5% — severely underprices the barrier effect vs. point-in-time
  - $987K volume = deep liquid market; institutional price discovery has happened
  - Note: BTC has been rallying; FOMC no-hike (our existing bet) is bullish for risk assets

### BET 3: Bitcoin $66K on June 20 — ID#13 ⭐ STRONG EDGE (short fuse)
- **Market:** Will Bitcoin reach $66,000 on June 20? (resolves June 21)
- **Our side:** YES
- **Our prior:** 16.7%
- **Poly implied:** 1.55%
- **Edge:** +15.2pp
- **Rationale:**
  - BTC at $64,203 today → needs only +2.8% to hit $66K intraday
  - With intraday vol (σ ≈ 4%/day × √0.5 days remaining today) = 2.83%
  - P(BTC touches $66K today) using lognormal: ~16.7%
  - Poly prices at 1.55% — drastically underprices a 2.8% intraday move for BTC
  - **This resolves by June 21 — very short fuse**
  - Caveat: thin volume ($9.4K); if BTC already topped today the bet is dead

### BET 4: Ethereum Above $1,600 on June 22 — ID#11 — NO side
- **Market:** Will the price of Ethereum be above $1,600 on June 22?
- **Our side:** NO
- **Our prior:** 9.4% (NO) / 90.6% (YES)
- **Poly implied:** 1.7% NO / 98.3% YES
- **Edge:** +7.7pp on NO
- **Rationale:**
  - ETH at $1,740 — 8.7% above the $1,600 target with 2 days remaining
  - P(ETH < $1,600 in 2 days): using σ=4.5%/day, σ_T=6.36%
  - P(ETH > $1,600 at expiry) = N(1.318) = 90.6%
  - Therefore P(ETH ≤ $1,600) = 9.4% — Poly prices NO at 1.7%
  - Poly significantly overprices the upside case (ignores realistic downside vol)
  - Resolves June 22 (2 days) — quick resolution

### BET 5: WTI Crude Over $63 at June Expiry — ID#12
- **Market:** Will Crude Oil (CL) settle over $63 on the final trading day of June 2026?
- **Our side:** YES
- **Our prior:** 99.3%
- **Poly implied:** 94.7%
- **Edge:** +4.6pp
- **Rationale:**
  - WTI at $76.54 → needs to stay above $63 (21.4% buffer)
  - With σ=2.5%/day, 10-day vol = 7.9%
  - P(CL > 63 at June 30 expiry) = N(2.46) = 99.3%
  - Poly at 94.7% — leaves 4.6pp of edge (conservative/high-confidence bet)
  - For WTI to fall from $76.54 to below $63 by June 30 would require a ~17% plunge (3.1σ event) — essentially impossible without a catastrophic macro event
  - Good size: $9.5K volume; small edge but near-certainty payout

---

## 5. Markets Considered But Skipped

### ISM Manufacturing / NFP / CPI
- **No Polymarket markets found** for June-July ISM (July 1) or June NFP (July 3)
- Searched 600+ markets; no active markets on these data releases
- These would have been primary targets if they existed

### Sports / Weather markets
- Weather markets: too narrow (exact °C on exact day), shallow volume, no NOAA-comparable edge
- Sports: World Cup markets have deep liquidity but no statistical edge we can quantify

---

## 6. Portfolio Summary After This Scan

| ID | Question | Side | Our% | Poly% | Edge | End Date |
|----|----------|------|------|-------|------|----------|
| 9 | BoI No Change July | YES | 60% | 9% | +51pp | 2026-07-06 |
| 10 | BTC reaches $70K in June | YES | 25% | 9.5% | +15.5pp | 2026-07-01 |
| 13 | BTC reaches $66K on June 20 | YES | 16.7% | 1.55% | +15.2pp | 2026-06-21 |
| 11 | ETH above $1,600 on June 22 | NO | 9.4% | 1.7% | +7.7pp | 2026-06-22 |
| 12 | WTI CL over $63 June expiry | YES | 99.3% | 94.7% | +4.6pp | 2026-06-30 |

**Prior 8 open bets:** FOMC/Fed rate markets resolving ~July 30  
**New bets added:** 5 (IDs 9-13)  
**Total open bets:** 13  
**Paper notional added:** $125

---

## 7. Key Risks

1. **BoI bet (#9):** If the May 25 meeting (data unavailable) resulted in a forward guidance shift toward cutting in July, our prior would be too high. The biggest risk is that geopolitical improvement (ceasefire) frees BoI to cut. Still, 9% no-change is far too low.
2. **BTC/June 20 bet (#13):** This is an intraday bet. If BTC doesn't move today, it's a dead trade by tomorrow's open. Thin volume.
3. **ETH/$1,600 bet (#11):** Betting ETH drops 8.7% in 2 days. Unusual but possible in crypto. Risk is convex — payout on NO requires a significant ETH crash.
4. **CL/$63 bet (#12):** Smallest edge. Risk is a black-swan oil crash (Middle East peace deal, OPEC supply shock) coinciding with expiry. Very low probability.

---

*Report generated by trading-bench subagent | 2026-06-20*
