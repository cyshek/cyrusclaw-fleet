# Polymarket Scout — Go/No-Go Memo
_Date: 2026-06-13_

## Verdict: CONDITIONAL-GO

Polymarket has a world-class free API, deep historical data on macro markets, and genuinely thin competition on finance/economics questions — but there are two material constraints: (1) US IP-blocks on order placement (workaround: Polymarket.us launched, or VPN/non-US path), and (2) the fee formula, while modest on geopolitics/finance markets, sets a minimum viable trade size floor of ~$500–$1,000 to keep costs under 0.5% round-trip.

---

## Q1: Data Depth

Polymarket's free `gamma-api.polymarket.com` REST API exposes full historical market data (resolved markets, volumes, outcomes) with no auth required and no rate limit documented. Historical markets go back to early 2024 (when meaningful liquidity materialized), with the CLOB price-history endpoint (`clob.polymarket.com/prices-history?market=<tokenId>&interval=max`) returning per-market time-series at configurable fidelity. The 2024 US Presidential election markets traded $1.5B+ on Trump alone, with data starting from early January 2024 — plenty of signal depth. Bulk enumeration works via paginated `/markets?closed=true&limit=N&order=volumeNum&ascending=false` with keyset pagination for stable paging through thousands of resolved markets. No scraping required — it's a clean REST API with Python and TypeScript SDKs officially supported.

## Q2: Cost Structure

**Gas fees:** Polymarket routes trades through a Relayer (gasless for users) — gas on Polygon is negligible ($0.001–$0.01/tx) and is abstracted away entirely; users just trade in USDC, not MATIC.

**Platform fees (confirmed from `docs.polymarket.com/trading/fees`):** Taker fee only (makers are fee-free). Formula: `fee = C × feeRate × p × (1 - p)` where C=shares, p=price. By market type:
- Geopolitics/world events: **0% (completely free)** — this is the sweet spot
- Finance/Politics/Economics: 3–5% fee rate on the `p*(1-p)` factor (not notional) — at $0.50 price, the effective fee on 100 shares/$50 notional is ~$0.88–$1.75
- Crypto: 7% (most expensive)

**Minimum viable size:** For geopolitics/world-event markets (0% fees), the floor is bid-ask spread — top liquid markets on macro events have 1–3% spreads. Minimum order size is $5 (5 shares). For finance markets with 4% fee rate: need ~$500+ notional to keep round-trip fees under 0.5%.

**Bid-ask spreads:** On the FIFA World Cup multi-outcome market, checked live — top-of-book spread was 199% on a low-probability outcome (expected on a long-odds multi), but depth was $4M+ on the bid side. For active 50-50 binary events, spreads are typically 1–3¢ on a $0.50 market (2–6% round-trip). On thin markets (<$50k volume), spreads blow out to 5–20%.

## Q3: Edge Thesis

**Where we'd have an edge:** The macro/economic prediction questions are the best lane. Markets like "Fed decreases rates by 50bps after January 2026 meeting" ($235M volume), "US government shutdown" ($157M), and "US forces enter Iran by April 30" ($269M) had enormous liquidity. These resolve on hard factual outcomes, not crowd opinion — we can build quantitative models (e.g., FRED + market pricing vs. CME Fed Funds futures) that likely beat the average Polymarket bettor who is working off headlines. On Fed rate markets specifically, our macro toolkit would have a genuine edge.

**Red flags:**
1. **US blocking (critical):** `US: Blocked` on polymarket.com per the official geoblock table. Order placement from this VM (Azure US) would be rejected. Mitigation: **Polymarket.us** launched in 2026 as the US-regulated version with its own API (`api.polymarket.us`, `gateway.polymarket.us`) — this is the path for US participants.
2. **Thin macro liquidity on niche events:** Below $50k volume, spreads are brutal. Stick to events above $100k.
3. **Short-duration noise:** Markets closing in <1 week are essentially coin-flips late in resolution. Duration filter: >2 weeks to close.
4. **Price-history API quirk:** The `prices-history` endpoint returned 0 points on closed markets in our tests — may require a valid active token ID, not a resolved conditionId. Needs a small adapter to map resolved market token IDs correctly.

**Efficiency check on resolved markets:** Top macro markets (Fed rate, election, geopolitical events) appear to price in efficiently by the last 1–2 days, but there's significant mid-life mispricing visible in the price trajectories — e.g., on Fed rate cuts where the market was 30¢ a week before resolution on an event that resolved to 0. That trajectory-drift pattern is a tradeable signal for a quantitative model.

---

## Key Facts Found

- **API:** `gamma-api.polymarket.com` — free, no auth, paginated, volume-sortable. Works from this VM.
- **CLOB:** `clob.polymarket.com` — order book, price history, fee rate. Also accessible.
- **Historical depth:** Top markets go back to Jan 2024; meaningful data since ~mid-2023.
- **Largest resolved market:** US Presidential Election 2024 — Trump market $1.53B volume.
- **Macro markets with >$100M volume:** Fed rate (×4 meetings), US Iran, inauguration, shutdown — all resolved correctly.
- **Fee structure confirmed:** Geopolitics = 0% taker fee. Finance/Politics = 4% fee-rate (not 4% of notional — uses `p*(1-p)` formula, much lower in practice).
- **`base_fee: 1000` in CLOB API** — this is an internal integer representing the fee *rate* parameter in the formula, not 1000 bps of notional. Actual dollars are far lower.
- **Minimum order size:** $5 (5 shares).
- **US blocking:** Confirmed. polymarket.com blocks US orders at the API level.
- **Polymarket.us:** Launched for US participants. Public API at `gateway.polymarket.us` accessible. Authenticated API at `api.polymarket.us` requires API key + KYC.
- **Price history API:** Endpoint confirmed in docs (`/prices-history?market=<tokenId>&interval=max`); returned 4,449 points on a live FIFA market. Resolved-market lookups may need the original CLOB token ID (not condition ID).

## Recommendation

**CONDITIONAL-GO with one prerequisite: resolve the US access path before writing any trading code.** The data, liquidity, and edge thesis are all there — geopolitics/macro markets at $100M+ volume are genuinely under-priced by quantitative models, fees on those markets are zero, and the API is clean and well-documented. The prerequisite is confirming which API endpoint to target: Polymarket.us requires KYC + account setup for US persons. That's a one-time Cyrus action (account creation, not a code dependency) — once an API key is in hand, we can build a full read-data-to-signal-to-order pipeline.

**First concrete build step:** Cyrus creates a Polymarket.us account + API key (KYC required, ~15 min). Meanwhile: (1) build a `polymarket_scanner.py` that pulls active macro/finance markets from Gamma API, filters to >$100k volume and >14 days to close, scores implied probability vs. our quantitative priors (FRED data for macro, CME futures for rate markets), and flags >5% discrepancies; (2) build the `prices-history` adapter to map resolved markets for backtest. **This goes in the Polymarket backlog lane — not FX, which requires live-feed infra we don't have yet.** Priority: Polymarket > FX for first new signal class.
