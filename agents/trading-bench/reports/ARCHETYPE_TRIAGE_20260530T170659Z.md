# Strategy Archetype Triage — 2026-05-30 17:07 UTC

**Author:** trading-bench (subagent)
**Venue assumed:** Alpaca paper, US equities (IEX), ~2 bps round-trip cost, long-only, daily/minute bars from Alpaca.
**Asset class:** US stocks only. Crypto explicitly excluded (Alpaca ~4% spreads — structurally dead).
**Goal of doc:** Shortlist of 8–12 strategy archetypes worth (or not worth) backtesting next. Triage only — no code.

---

## Summary table

| # | Archetype | One-line thesis | Citation | Long-only feasible? | Recommendation |
|---|---|---|---|---|---|
| 1 | Cross-sectional momentum (12-1 ranking) | Past 12m winners (skip last month) keep winning ~1%/mo over losers | VERIFIED (Jegadeesh & Titman 1993) | Yes (top decile only) | **BACKTEST** |
| 2 | Time-series / vol-targeted trend following | Each asset's own past 12m return predicts next month; size 1/σ | VERIFIED (Moskowitz/Ooi/Pedersen 2012) | Yes (long when trend up, flat else) | **BACKTEST** |
| 3 | Low-volatility anomaly | Low-vol / low-beta names earn higher risk-adjusted returns than CAPM predicts | VERIFIED (Ang/Hodrick/Xing/Zhang 2006; Frazzini-Pedersen "Betting Against Beta") | Yes (natural long-only tilt) | **BACKTEST** |
| 4 | Short-horizon mean-reversion (1–5 day) | Big 1–5d losers bounce; behavioral overreaction + liquidity provision premium | VERIFIED (Jegadeesh 1990; Lehmann 1990; Lo-MacKinlay 1990) | Yes (buy losers, no shorts needed) | **BACKTEST** |
| 5 | Pairs / stat-arb (cointegrated pairs) | Two co-moving names diverge → revert; market-neutral edge | VERIFIED (Gatev/Goetzmann/Rouwenhorst 2006) | Partial — pair is long/short by construction; long-only = pseudo-pair vs ETF benchmark | **DEFER** |
| 6 | Post-earnings announcement drift (PEAD) | Prices under-react to earnings surprises; drift in surprise direction for ~60 days | VERIFIED (Bernard & Thomas 1989, 1990) | Yes (long positive-surprise only) | **BACKTEST** |
| 7 | Overnight vs intraday drift | Overnight returns positive on average; intraday near-zero/negative; structural premium for holding through close | VERIFIED (Lou/Polk/Skouras 2019; Knuteson; Cliff/Cooper/Gulen) | Yes (buy MOC, sell MOO) | **BACKTEST** |
| 8 | Sector / industry relative-strength rotation | Sector momentum slower-decaying than single-name; rotates into leading sectors via ETFs | TRAINING-MEMORY (well-known practitioner work; Faber "Quantitative Approach to Tactical Asset Allocation" 2007 closest cite) | Yes (rotate among sector ETFs) | **BACKTEST** |
| 9 | Quality + momentum combo | "Junk-momentum" is fragile; combining profitability/quality with momentum stabilizes Sharpe | VERIFIED (Asness/Frazzini/Pedersen "Quality Minus Junk" 2019; Asness/Moskowitz/Pedersen 2013) | Yes (top decile on composite) | **DEFER** |
| 10 | Calendar effects (turn-of-month, sell-in-May) | Persistent recurring flows around month-end and seasonal patterns | TRAINING-MEMORY (Ariel 1987 turn-of-month; Bouman-Jacobsen 2002 "Halloween effect") | Yes (timing only, long/flat) | **DEFER** |
| 11 | Breadth thrust / market-internals reactive | Sudden broad participation (e.g. Zweig Breadth Thrust) signals durable rallies | TRAINING-MEMORY (Martin Zweig "Winning on Wall Street" 1986; widely cited practitioner; no clean academic paper) | Yes (long SPY on signal) | **DEFER** |
| 12 | News sentiment reactive (NLP feed) | Negative sentiment headlines predict short-term continuation; positive sentiment fades | TRAINING-MEMORY (Tetlock 2007 "Giving Content to Investor Sentiment" academic; live needs paid feed) | Yes | **SKIP** (data cost) |

**RECOMMENDED FOR BACKTEST: 7** archetypes (#1, #2, #3, #4, #6, #7, #8).
**DEFER: 4** (#5, #9, #10, #11).
**SKIP: 1** (#12).

---

## 1. Cross-sectional momentum (12-1 ranking)

- **Thesis:** Stocks that outperformed their peers over the past 12 months (skipping the most recent month to dodge short-term reversal) tend to keep outperforming for 3–12 months.
- **Mechanism:** Behavioral under-reaction to fundamental news (slow diffusion of information); possibly a risk premium for crash exposure. The "skip-1-month" rule controls for the short-horizon reversal effect in #4.
- **Citation:** VERIFIED. Jegadeesh & Titman, *Journal of Finance* 48(1), 1993, "Returns to Buying Winners and Selling Losers." https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x . Replicated by Fama-French 2008/2012 and hundreds of follow-ups.
- **Data:** Daily OHLCV for ~500–3000 names (S&P 1500 or Russell 3000). Monthly rebalance OK. Alpaca free tier sufficient.
- **Compute:** **S–M.** Universe screen + rolling-return rank, monthly rebalance.
- **Long-only?** Yes. Long-only top decile/quintile captures ~half the gross long-short premium and avoids the painful short side (momentum crashes are dominated by short-leg losses, e.g. 2009).
- **Recommendation:** **BACKTEST.** Best-documented equity anomaly. Long-only version is robust, low-turnover-ish (~monthly), and our 2 bps cost is fine.

## 2. Time-series / vol-targeted trend following

- **Thesis:** Each asset's own past 1–12 month return positively predicts its next-month return. Sizing positions inversely to realized volatility (vol-targeting) flattens the equity curve dramatically.
- **Mechanism:** Same underlying behavioral story as #1 (under-reaction → delayed price discovery), but applied per-asset instead of cross-sectionally. Vol-targeting is a risk-management overlay, not the alpha source.
- **Citation:** VERIFIED. Moskowitz, Ooi, Pedersen, "Time Series Momentum," *Journal of Financial Economics* 104(2), 2012. Tested across 58 instruments over 25 years. Also Hurst/Ooi/Pedersen "A Century of Evidence on Trend-Following Investing" (AQR 2017).
- **Data:** Daily OHLCV per name or ETF basket. Realized-vol estimator needs ~20–60 days of returns.
- **Compute:** **S.** Per-asset rolling return + rolling stdev.
- **Long-only?** Yes (long when 12m return > 0, flat otherwise). Loses the short-leg P&L in bear markets but avoids needing a borrow desk.
- **Recommendation:** **BACKTEST.** Mechanically simple, well-documented, and the vol-target makes Sharpe comparable across runs in tournament scoring. Apply to a basket of liquid sector ETFs first, then single names.

## 3. Low-volatility anomaly

- **Thesis:** Low-volatility (or low-beta) stocks earn higher Sharpe ratios than high-vol stocks — the opposite of CAPM's prediction. Long-only investor can capture this by tilting toward boring names.
- **Mechanism:** Leverage constraints (Frazzini-Pedersen): unlevered investors who want higher returns buy high-beta names, bidding them up and depressing their forward returns. Also behavioral preference for lottery-like stocks.
- **Citation:** VERIFIED. Ang, Hodrick, Xing, Zhang, "The Cross-Section of Volatility and Expected Returns," *Journal of Finance* 61(1), 2006. https://onlinelibrary.wiley.com/doi/full/10.1111/j.1540-6261.2006.00836.x . Also Frazzini & Pedersen, "Betting Against Beta," *JFE* 2014. Wikipedia overview: https://en.wikipedia.org/wiki/Low-volatility_anomaly
- **Data:** Daily OHLCV → 1–12 month realized vol or rolling beta. Free.
- **Compute:** **S.** Sort, take bottom quintile, hold monthly.
- **Long-only?** Yes — this is literally the long-only version of the academic factor. ETFs like USMV/SPLV already commercialize it.
- **Recommendation:** **BACKTEST.** Pairs well with momentum (#1) as a defensive tilt. Low turnover.

## 4. Short-horizon mean-reversion (1–5 days)

- **Thesis:** Stocks that drop sharply over 1–5 days tend to bounce back over the next 1–5 days. Behavioral overreaction + the bouncer earns a liquidity-provision premium.
- **Mechanism:** Liquidity providers / market-makers need compensation for absorbing forced selling (margin calls, fund outflows). The "reversion premium" is the payment for that service.
- **Citation:** VERIFIED. Jegadeesh, "Evidence of Predictable Behavior of Security Returns," *Journal of Finance* 45(3), 1990. Also Lehmann, "Fads, Martingales, and Market Efficiency," *QJE* 1990. Lo & MacKinlay 1990 on contrarian profits.
- **Data:** Daily OHLCV; minute bars are an upgrade not a requirement at 1–5d horizon.
- **Compute:** **S.** Rank by N-day return, long bottom decile, hold 1–5 days.
- **Long-only?** Yes — buy the losers. Skip the "short the winners" side (winners-reversal is weaker and exposed to momentum crashes anyway).
- **Recommendation:** **BACKTEST.** Higher turnover (~5–20x/year) means our 2 bps cost matters more — but still very tractable. Counter-cyclical to #1/#2 which is good for tournament diversification.

## 5. Pairs trading / stat-arb (cointegrated pairs)

- **Thesis:** Two stocks whose prices co-move long-term will revert when they diverge by >2 σ; trade the spread.
- **Mechanism:** Microstructure / temporary liquidity dislocations; sector co-movement from common factor exposure.
- **Citation:** VERIFIED. Gatev, Goetzmann, Rouwenhorst, "Pairs Trading: Performance of a Relative-Value Arbitrage Rule," *Review of Financial Studies* 19(3), 2006. https://www.nber.org/papers/w7032
- **Data:** Daily OHLCV for a wide universe (need to scan all N×N pairs for cointegration). Pair-formation is O(N²) but tractable for N≤500.
- **Compute:** **M.** Cointegration tests (Engle-Granger / Johansen) + spread z-score monitor.
- **Long-only?** **NO, fundamentally.** A pair trade is by definition long one leg / short the other. Workarounds: (a) long-only "pseudo-pair" where you go long the cheap leg vs holding cash (loses ~half the alpha and exposes you to market beta), or (b) long the cheap leg vs short the sector ETF — but we can't short.
- **Recommendation:** **DEFER.** Re-evaluate when shorting becomes available. Long-only version is unattractive vs simpler alternatives.

## 6. Post-earnings announcement drift (PEAD)

- **Thesis:** Stocks with large positive earnings surprises continue drifting up for ~60 days post-announcement; large negative surprises drift down. Market under-reacts.
- **Mechanism:** Investor inattention; analyst forecast stickiness; gradual position-building by funds restricted to acting on confirmed fundamentals.
- **Citation:** VERIFIED. Bernard & Thomas, "Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?," *Journal of Accounting Research* 27, 1989. https://www.jstor.org/stable/2491062 . Plus Bernard & Thomas 1990 (*Journal of Accounting and Economics*).
- **Data:** **Event data required.** Need earnings dates and (ideally) consensus estimates to compute surprise. Alpaca does NOT provide consensus estimates. Free workarounds: NASDAQ earnings calendar (dates only) + price-based "earnings reaction" as a surprise proxy (drift of 2-day window around announcement).
- **Compute:** **M.** Event-time aggregation per name.
- **Long-only?** Yes — long the positive-surprise decile only. Negative-surprise drift is weaker and would require shorting.
- **Recommendation:** **BACKTEST** using the price-reaction proxy for surprise (no paid data needed). One of the most replicated equity anomalies in academia.

## 7. Overnight vs intraday drift anomaly

- **Thesis:** Equity returns are almost entirely earned overnight (close → next open); intraday returns are roughly flat or negative on average. Holding through the close systematically pays.
- **Mechanism:** Demand pressure at the close from passive/end-of-day flows; risk premium for bearing overnight gap risk when liquidity is absent; possibly a structural artifact of how earnings/news drop after-hours.
- **Citation:** VERIFIED. Lou, Polk & Skouras, "A Tug of War: Overnight Versus Intraday Expected Returns," *JFE* 2019. Earlier: Cliff, Cooper & Gulen, "Return Differences between Trading and Non-Trading Hours" (working paper 2008). Knuteson "Information Asymmetry" 2017 also documents it.
- **Data:** Need open and close prices per day. Free from Alpaca.
- **Compute:** **S.** Buy MOC, sell MOO, rinse-repeat (or selectively, only when overnight expected return is highest, e.g. small-caps or names with momentum).
- **Long-only?** Yes — pure long-only by construction (buy at close, sell at open).
- **Recommendation:** **BACKTEST.** Important caveat: real-world spread/slippage on MOC/MOO orders can eat the anomaly. With Alpaca IEX routing this needs careful execution modeling. But the academic edge is real and worth measuring.

## 8. Sector / industry relative-strength rotation

- **Thesis:** Sector ETFs that have outperformed over 3–6 months continue to outperform over the next 1–3 months. Rotate capital into the top 1–3 sectors monthly.
- **Mechanism:** Same under-reaction story as cross-sectional momentum, but at a coarser unit. Sector momentum is more persistent and lower-turnover than single-name momentum.
- **Citation:** TRAINING-MEMORY. Closest formal cite: Faber, "A Quantitative Approach to Tactical Asset Allocation," *Journal of Wealth Management* 2007 (timing variant). Also Moskowitz & Grinblatt, "Do Industries Explain Momentum?" *JF* 1999 — they argue industry momentum drives much of single-stock momentum. Practitioner literature (O'Neil, IBD) heavy but not academically clean.
- **Data:** Daily OHLCV for ~11 sector SPDR ETFs (XLK, XLF, XLE, etc.). Trivially free.
- **Compute:** **S.** Tiny universe, monthly rebalance.
- **Long-only?** Yes — rotate among long-only ETF positions.
- **Recommendation:** **BACKTEST.** Cheap, simple, low-turnover. Good "control" archetype to compare against single-name momentum (#1). If #1 doesn't beat #8 net of costs, #1 isn't worth the complexity.

## 9. Quality + momentum combo

- **Thesis:** Pure momentum suffers periodic crashes ("momentum crash" 2009). Filtering momentum winners to only those with high quality (profitability, low leverage, stable earnings) reduces tail risk and improves Sharpe.
- **Mechanism:** Quality screens proxy for fundamental health; combining with momentum filters out "junk rallies" where weak companies rally on speculation.
- **Citation:** VERIFIED. Asness, Frazzini, Pedersen, "Quality Minus Junk," *Review of Accounting Studies* 24, 2019. Asness, Moskowitz, Pedersen, "Value and Momentum Everywhere," *JF* 2013. Novy-Marx "The Other Side of Value" 2013 on profitability.
- **Data:** Requires fundamentals (gross profit/assets, ROE, debt/equity). Alpaca doesn't ship fundamentals natively — need an external feed (free options: SimFin, SEC EDGAR scraping; both add infra cost).
- **Compute:** **M.** Two-factor composite scoring + monthly rebalance.
- **Long-only?** Yes (top decile of composite).
- **Recommendation:** **DEFER.** Real edge, but the fundamentals-data plumbing is its own project. Revisit after we have a baseline momentum (#1) working — then add quality as an overlay.

## 10. Calendar effects (turn-of-month, sell-in-May, etc.)

- **Thesis:** Returns concentrate in predictable calendar windows: last 1 + first 3 trading days of the month, the Nov–Apr "winter" period, etc.
- **Mechanism:** Recurring fund flows (401(k) contributions on payroll dates, mutual-fund window dressing); seasonal liquidity / risk-appetite cycles.
- **Citation:** TRAINING-MEMORY (some borderline VERIFIED). Ariel "A Monthly Effect in Stock Returns," *JFE* 1987 (turn-of-month). Bouman & Jacobsen, "The Halloween Indicator, Sell in May and Go Away: Another Puzzle," *AER* 2002. Lakonishok-Smidt 1988 on seasonality. Half of these are now suspected of data-mining / decay post-publication.
- **Data:** Daily OHLCV on SPY. Trivially free.
- **Compute:** **S.** Calendar-rule timing only.
- **Long-only?** Yes (long/flat timing).
- **Recommendation:** **DEFER.** Effects are real-ish historically but small in magnitude and likely arbitraged down. Worth a backtest eventually as a *combinator* (e.g., only trade #1 in the turn-of-month window), but not as standalone alpha.

## 11. Breadth thrust / market-internals reactive

- **Thesis:** When market breadth (advancing/declining issues, % above 50d MA, etc.) spikes from oversold to extreme positive in <10 days, the next 6–12 months are unusually strong. Famous: Zweig Breadth Thrust signal.
- **Mechanism:** Reflects regime change in risk appetite and forced re-allocation by underweighted funds. Rare but high-conviction.
- **Citation:** TRAINING-MEMORY. Martin Zweig, *Winning on Wall Street* (1986). Practitioner cite, not academic. Whaley/Stivers have studied related "breadth as predictor" but with mixed support.
- **Data:** Daily advance/decline data for NYSE — Alpaca doesn't provide; need Yahoo or Stooq scrape. ~moderate infra.
- **Compute:** **S.** Signal fires once every few years.
- **Long-only?** Yes (long SPY when signal fires).
- **Recommendation:** **DEFER.** Too few signals in our backtest window (50 years would only give ~10 events) — statistically inconclusive. Better as a regime overlay than a standalone strategy. Revisit after we have base strategies running.

## 12. News sentiment reactive (NLP feed)

- **Thesis:** Real-time news sentiment predicts short-term return drift; negative shocks under-react more than positive.
- **Mechanism:** Information processing latency; retail vs institutional reaction speed differences.
- **Citation:** TRAINING-MEMORY (academic basis exists). Tetlock, "Giving Content to Investor Sentiment: The Role of Media in the Stock Market," *JF* 2007. Tetlock, Saar-Tsechansky, Macskassy 2008. RavenPack / Bloomberg-news vendor studies.
- **Data:** **Expensive.** Real-time tagged news feed (RavenPack, Bloomberg, Refinitiv) = thousands/month minimum. Free alternatives (news RSS + DIY LLM sentiment) are noisy and have latency.
- **Compute:** **L.** NLP pipeline + event-driven trading.
- **Long-only?** Yes (long positive-surprise side).
- **Recommendation:** **SKIP** (for now). Data and infra cost vastly outweigh expected edge at our scale. Re-evaluate only after we have proven alpha that justifies the budget.

---

## Cross-cutting notes for the manager

1. **Backtest order suggestion** (cheapest → most expensive infra):
   1. **#7 Overnight drift** — fastest to validate, smallest universe (SPY first), pure long-only.
   2. **#8 Sector rotation** — 11 ETFs, monthly cadence, trivial code.
   3. **#3 Low-vol anomaly** — single-factor sort, monthly.
   4. **#2 Vol-targeted trend** — per-name TSMOM.
   5. **#1 Cross-sectional momentum** — needs proper universe definition (S&P 500 / liquid 1000).
   6. **#4 Short-horizon reversal** — higher turnover, needs careful cost model.
   7. **#6 PEAD** — needs earnings-date scrape (NASDAQ calendar is free).

2. **Cost sensitivity ranking** (worst → best for our 2bps regime):
   - High-turnover: #4 (mean-rev), #7 (overnight, daily turnover).
   - Medium: #1, #6 (monthly to weekly).
   - Low: #2, #3, #8, #9 (monthly).

3. **Data infra dependencies to flag for build queue:**
   - Earnings calendar scrape (NASDAQ/Earnings Whispers free) → needed for #6.
   - Fundamentals feed (SimFin or EDGAR) → needed for #9.
   - Advance/decline series → needed for #11.

4. **What's missing from the original list that I'd consider adding later:**
   - **52-week-high effect** (George & Hwang 2004) — variant of momentum, very simple.
   - **Idiosyncratic momentum** (Blitz/Huij/Martens 2011) — residual-return momentum, less correlated to factor momentum.
   - **Defensive-equity / quality-only** — orthogonal to all the above; would be #13.

5. **What I'd actively NOT do even on request:**
   - Anything requiring live news/sentiment feeds at current budget.
   - Anything requiring shorting (#5 pure form, #6 negative-surprise leg, #1 long-short).
   - Sub-minute timeframes — per AGENTS.md policy.

---

*Triage produced 2026-05-30 17:07 UTC. No code written. No live trading files touched. Citations spot-checkable via the URLs above.*
