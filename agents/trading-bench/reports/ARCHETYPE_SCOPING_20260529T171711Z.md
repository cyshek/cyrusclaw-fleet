# Archetype Scoping — Weekend Backtest Sprint

**Author:** Tessera (subagent, depth 1/1)
**Generated:** 2026-05-29 17:17 UTC (10:17 PDT)
**Mandate ref:** parent task `dc782d23-993e-4f23-8a0a-ee27f759c53d`
**Goal:** Enumerate 15–20 DIVERSE trading-strategy archetypes to broaden the parent pool. The current pool (SMA crossover, RSI mean-revert, breakout, momentum, trend-follow, buy-and-hold) is exhausted — 9 rounds of LLM mutation, 0 net-positive promotions. We need NEW families, not more variations of the existing ones.

**Out of scope:** writing strategy code, running backtests, promoting anything, spawning subagents. Research + design only.

**Gate this feeds into:** `GATE.md` Bar A (new-archetype graduation: walk-forward pass on 8 named regimes, cost-aware Sharpe ≥ 0.5, ≥30 trades, max DD ≤ 30% post-cost, AST + smoke pass).

**Cost regime:** Alpaca paper, IEX execution. Stocks ~2 bps round-trip. Crypto ~4% round-trip (toxic — anything crypto must clear costs by miles). $100 notional per position, max 4 trades/strategy/day. Long-only or long/flat per current runner. (Short capability is a runner-extension question, not part of this scope.)

**Honesty caveat on citations:** SearXNG dropped after 4 queries. I have direct URLs for archetypes #1, #5, #11, #12. The rest are cited to canonical academic / quant-blog sources from my training data — subagent implementers should re-verify the Sharpe numbers when they read the paper before encoding any threshold. Where uncertain, I labeled the Sharpe range "literature memory; verify."

---

## Section 1 — Archetype Catalog (18 entries)

For each: **Thesis · Features · Data · Lit Sharpe · Cost sensitivity · Diversity vs current pool**

Diversity rubric: an archetype is "diverse" if its return stream has plausibly low correlation to the current parent pool, which is dominated by long-only trend/momentum on a single ETF held for days–weeks. Concretely we need archetypes that (a) are mean-reverting on a different timescale, (b) take cross-sectional rather than time-series signals, (c) trigger on a calendar/event rather than price, or (d) are market-neutral.

---

### A1. Bollinger Z-Score Mean Reversion (daily)
- **Thesis:** Closing price reverts when it deviates far from its rolling mean. Buy when close < mean - k·σ on a high-liquidity ETF; exit on mean touch or stop.
- **Features:** SMA(20), rolling std(20), z-score = (close − μ) / σ. Optional: ADX < 25 regime filter to avoid mean-reverting *into* trends.
- **Data:** Daily bars, single symbol (SPY/QQQ/IWM). Already in `bars_cache`.
- **Lit Sharpe:** ~0.4–0.8 on equity ETFs in mean-reverting regimes, often near 0 in trending years. (Connors / Larry Connors, *Short Term Trading Strategies That Work*, 2008 — same family as our failed CRSI2 port; verify.) Source: literature memory; verify before encoding.
- **Cost sensitivity:** Low at daily frequency (~10–30 trades/yr on a single ETF). 2 bps round-trip is negligible vs typical 0.5–1.5% mean-reversion targets.
- **Diversity:** Negatively correlated to our trend pool in chop regimes. Same data, opposite signal. Risk: CRSI2 port already failed (`CONNORS_RSI2_VALIDATION_20260527`); Bollinger is a slightly different parameterization but same family — moderate novelty only.

### A2. Opening Range Breakout (5-min ORB, intraday)
- **Thesis:** First 5–30 min of NYSE session establishes a high/low range; close above the high in the next 30 min predicts session-end drift up; close below low predicts drift down. Strong on high-volume / news days.
- **Features:** 9:30–9:35 high & low, ATR(14) daily, optional volume filter (today's first-5-min vol > 2× 20d avg).
- **Data:** **1-minute bars** (or 5-min). Alpaca IEX provides these but harness window-size needs to support intraday — **PREREQ FROM HANDOFF SAT TASK LIST (a)**: audit `bars_cache`/`backtest.py` for intraday support before this archetype is implementable.
- **Lit Sharpe:** QuantConnect research on filtered ORB across 1000 stocks reports **Sharpe ~2.4** (https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/). VolatilityBox reports 55–62% win rate, 1.5–2:1 RR on filtered ES/NQ futures (https://volatilitybox.com/research/opening-range-volatility-breakout/). Single-ETF unfiltered will be much lower (~0.5–1.0).
- **Cost sensitivity:** HIGH. Intraday strategy = 1–2 round-trips/day = ~250–500/yr. At 2 bps each = 50–100 bps/yr drag. Need ≥150 bps/yr gross to clear. Filtered version (only trade abnormal-volume days) drops trade count and improves edge per trade.
- **Diversity:** Intraday timeframe is uncorrelated with our daily/hourly trend pool. Different cycle entirely. HIGH novelty.

### A3. Overnight Drift Capture (buy-MOC, sell-MOO)
- **Thesis:** ~68% of SPY's total return historically occurs in the close-to-open session, not 9:30–4 (alphaticaio analysis of 22 years, https://x.com/alphaticaio/status/2042401233067995201). Mechanism debated (overnight news flow + low-liquidity premium). Strategy: buy at market-on-close, sell at market-on-open next day.
- **Features:** Day-of-week filter (Monday/Friday typically weaker), VIX regime filter (drift weakens in high-vol regimes per Elm Wealth https://elmwealth.com/night-shift/).
- **Data:** Daily OHLC bars (open + previous close are sufficient). Optional VIX.
- **Lit Sharpe:** Trading Time Machine reports 879% cumulative overnight vs negative intraday for SPY 1996–2025 (https://www.tradingtimemachine.com/studies.html) — implied raw Sharpe ~0.6–0.9; AlphaTica recent analysis suggests post-2022 decay ("the overnight drift is dead" claim, contested). Verify on most-recent regime window.
- **Cost sensitivity:** MODERATE. ~250 round-trips/yr at 2 bps = 50 bps drag. Gross overnight drift on SPY ~3–5%/yr; net edge ~2.5–4.5%/yr at 100% allocation. **Big risk:** MOC/MOO fills on Alpaca paper may not be available, may slip. Verify execution model.
- **Diversity:** Calendar/microstructure trigger, not price-based. Orthogonal to our current pool. HIGH novelty. **Caveat:** if drift has decayed post-2022 (per AlphaTica), this is a fading edge — should test specifically on 2023–2025 windows.

### A4. Turn-of-the-Month (TOM)
- **Thesis:** US equities earn the bulk of their excess return in the 4-day window from last trading day of month through 3rd trading day of next month, driven by pension/401k inflows (Lakonishok & Smidt 1988; McConnell & Xu 2008 — https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf, https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes).
- **Features:** Trading day of month (calendar), nothing else strictly required.
- **Data:** Daily bars + NYSE calendar (already in `runner/market_hours.py`).
- **Lit Sharpe:** McConnell & Xu: TOM 4-day window captured essentially ALL the equity risk premium 1926–2005. Standalone strategy Sharpe ~0.5–0.8 long-only on SPY (verify); higher with cross-sectional or leveraged variants.
- **Cost sensitivity:** VERY LOW. ~12 round-trips/yr × 2 bps = 2 bps/yr drag. Essentially free.
- **Diversity:** Pure calendar trigger. Completely uncorrelated with our trend pool (it'll be flat 80% of the year). HIGH novelty.

### A5. Post-Earnings Announcement Drift (PEAD)
- **Thesis:** After a positive earnings surprise, stock continues to drift up for weeks (and the inverse for negative surprises). Ball & Brown 1968 original; Quantpedia summary at https://quantpedia.com/strategies/post-earnings-announcement-effect.
- **Features:** Earnings date, earnings surprise (actual − consensus EPS, normalized). Hold 1–60 days post-announcement.
- **Data:** **Earnings calendar + analyst consensus EPS.** Alpaca does NOT provide this natively; need FMP, Polygon, or Finnhub (free tiers exist). This is a non-trivial data dependency.
- **Lit Sharpe:** Long-short PEAD top vs bottom decile: Sharpe ~0.8–1.5 net of costs in academic studies; degraded post-2010 but not dead.
- **Cost sensitivity:** Moderate (~50–200 trades/yr depending on universe size). 2 bps is fine; data subscription cost is the real budget item.
- **Diversity:** Event-driven, single-name (not ETF), cross-sectional ranking. VERY different from current pool. HIGH novelty BUT high implementation cost due to data plumbing.

### A6. Gap Fade (open-gap reversal)
- **Thesis:** Stocks gapping up >2% at open (vs prior close) on no news tend to fade back toward the previous close in the first 30–60 min. Sell the gap-up open, cover at mid-morning.
- **Features:** Overnight gap = (today_open − yesterday_close) / yesterday_close. News filter (skip if earnings tonight/this morning). Volume filter.
- **Data:** 1-min or 5-min bars (intraday). Same intraday prereq as A2.
- **Lit Sharpe:** ~0.5–1.0 on liquid small/mid-caps; near 0 on mega-caps where gaps usually contain real information. Verify.
- **Cost sensitivity:** HIGH (intraday, ~100–200 trades/yr at small-cap spreads ~5–15 bps if Alpaca IEX doesn't have great fills on those names). Cost realism is a big risk here.
- **Diversity:** Intraday + counter-trend. Different cycle from our daily trend pool. MODERATE-HIGH novelty.

### A7. Gap-and-Go (continuation, NOT fade)
- **Thesis:** Stocks gapping >4% on news + heavy volume continue in the gap direction through the session. Buy the gap-up, ride to close.
- **Features:** Same gap calc as A6, but trigger on LARGER gaps + volume confirmation. News flag preferred (skip no-news gaps — those fade).
- **Data:** Same as A6 + news API ideally.
- **Lit Sharpe:** ~0.6–1.2 on news-confirmed gaps; degrades fast without news filter.
- **Cost sensitivity:** Same as A6.
- **Diversity:** Same intraday cycle as A6/A2; conditional on news. Complementary to A6 (opposite signal on different volume/news cohorts).

### A8. Pairs / Statistical Arbitrage (cointegration)
- **Thesis:** Two cointegrated stocks (e.g. KO/PEP, GLD/IAU, XLF/KBE) revert to long-run spread. Long the cheap one, short the rich one when spread z-score > 2; close at z=0.
- **Features:** Rolling cointegration (Engle-Granger or Johansen), z-score of residuals, half-life of mean reversion (Ornstein-Uhlenbeck fit).
- **Data:** Daily bars on multiple symbols. Standard.
- **Lit Sharpe:** Gatev, Goettler, Goyal, Rouwenhorst 2006 ("Pairs Trading: Performance of a Relative-Value Arbitrage Rule") report Sharpe ~0.5–0.8 net of costs on top US pairs; degraded since 2002 due to algorithmic competition. Literature memory; verify.
- **Cost sensitivity:** MODERATE (~50–150 round-trips/yr per pair). Real blocker is that pairs trading **REQUIRES SHORTING** for the spread leg. Our current runner is long-only. Workaround: long the cheap leg only when relative-strength reverses; or use inverse ETF for the short leg (e.g. SH against SPY); both lose half the edge.
- **Diversity:** Market-neutral (in classical form). VERY different from our pool. **Implementation blocker:** shorting capability. HIGH novelty if blocker resolves.

### A9. Volatility Risk Premium (short VIX / sell-vol when calm)
- **Thesis:** VIX implied vol systematically exceeds realized vol by ~3-4 vol points; selling vol earns the premium. Proxy: short VXX or long SVXY when VIX < 20 and VIX term structure in contango.
- **Features:** VIX level, VIX9D/VIX ratio (term structure), realized vol(20).
- **Data:** Daily bars on VIX, VXX, SVXY. All accessible via Alpaca.
- **Lit Sharpe:** Historically ~1.0–2.0 pre-2018; brutal tail risk (Feb 2018 "Volmageddon" liquidated XIV in a day). Risk-adjusted is misleading because the distribution is fat-tailed-left. Sharpe lies here.
- **Cost sensitivity:** Low at daily frequency. But ETF decay (VXX) and gap risk are not "costs" in the traditional sense — they ARE the strategy risk.
- **Diversity:** Pure vol/microstructure trade. Uncorrelated with our trend pool in calm regimes; HORRIBLY correlated to "everything goes down" in vol spikes. MODERATE novelty, but tail risk argues for STRONG safety_max_loss_pct rail.

### A10. Sector Rotation (cross-sectional momentum on sector ETFs)
- **Thesis:** Sector ETF that led the past 3/6/12 months tends to continue leading the next 1–3 months. Hold top-N of {XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC} ranked by trailing return; rebalance monthly.
- **Features:** Trailing 3/6/12-month returns per sector; rank; hold top-1 or top-3; optional cash-vs-equity regime filter using SPY 200-DMA.
- **Data:** Daily bars on 11 sector ETFs (all in `bars_cache` already or easy to add).
- **Lit Sharpe:** Antonacci "Dual Momentum" (2014): ~0.7–1.0 net Sharpe on dual-momentum sector portfolios. Long literature backing.
- **Cost sensitivity:** VERY LOW. 12 rebalances/yr × 2 trades each = 24 round-trips at 2 bps = 5 bps/yr. Free.
- **Diversity:** Cross-sectional (not time-series). Different signal generation. Already-known canonical strategy. HIGH novelty for our pool.

### A11. Low-Volatility / Defensive Tilt (long XLP/XLU/SPLV in risk-off regimes)
- **Thesis:** Low-vol stocks deliver higher Sharpe than high-vol stocks (Frazzini & Pedersen 2014, "Betting Against Beta"). Express as long SPLV or XLP/XLU when SPY's 20d realized vol > 75th percentile; long SPY when vol low.
- **Features:** SPY 20d realized vol percentile, optional VIX, sector ETF returns.
- **Data:** Daily bars on SPY, SPLV, XLP, XLU.
- **Lit Sharpe:** Frazzini-Pedersen long-short BAB factor Sharpe ~0.7–0.8 academic; long-only defensive tilt ~0.4–0.6. Verify.
- **Cost sensitivity:** LOW. Regime-driven rebalances ~4–8/yr.
- **Diversity:** Defensive overlay. Complements (rather than diversifies away from) trend pool — would correlate negatively in drawdowns. MODERATE novelty.

### A12. Volume / OBV Confirmation Filter (overlay, not standalone)
- **Thesis:** Breakouts on >2× average volume sustain; breakouts on <1× volume fade. Use OBV slope or relative-volume as a CONFIRMATION on top of a trend strategy.
- **Features:** OBV(close, vol), 20d avg volume, today's volume ratio.
- **Data:** Daily bars WITH VOLUME. **HANDOFF NOTE:** "slot #15 reserved for volume-confirmation, still blocked on bars not carrying `v`." Volume support is a prereq.
- **Lit Sharpe:** As an overlay, typically adds 0.1–0.3 to base strategy Sharpe; standalone OBV is weak (~0.2–0.4).
- **Cost sensitivity:** Reduces trade count → improves cost efficiency. Negative cost sensitivity (good).
- **Diversity:** Overlay, not a new family. Should be deferred until `bars_cache` carries volume. LOW standalone novelty; HIGH leverage as overlay.

### A13. Keltner Channel Breakout (vol-normalized breakout)
- **Thesis:** Same as Bollinger breakout but uses ATR (true range) instead of std-dev. Less sensitive to volatility clustering. Buy when close > EMA(20) + 2·ATR(20).
- **Features:** EMA(20), ATR(20), Keltner upper/lower channels.
- **Data:** Daily bars (with high/low for ATR — need to verify cache carries OHLC not just close).
- **Lit Sharpe:** ~0.4–0.7 on trend-heavy ETFs (QQQ, XLK). Similar to existing breakout but more robust to vol spikes.
- **Cost sensitivity:** LOW (daily, ~10–20 trades/yr).
- **Diversity:** Very similar to our existing breakout family — LOW novelty. Listed for completeness but probably should NOT make the top 5.

### A14. Day-of-Week Seasonality (Monday effect / Tuesday turnaround)
- **Thesis:** Mondays show systematically weaker returns (negative on average historically); Tuesday-through-Thursday positive bias. Trade SPY long Mon-close to Wed-open; flat or short Wed-close to Fri-open. Effect has decayed but isn't dead.
- **Features:** Day of week, day of month interaction (Monday before TOM is strongest).
- **Data:** Daily bars + calendar. Free.
- **Lit Sharpe:** Standalone ~0.2–0.4 since 2000; ~0.5–0.7 pre-2000 (classic "Monday effect"). Probably too weak alone, useful as filter/overlay.
- **Cost sensitivity:** Modest (~100 trades/yr at 2 bps = 20 bps drag) — might eat the edge.
- **Diversity:** Calendar trigger. Orthogonal to trend pool. MODERATE novelty but weak edge.

### A15. FOMC Drift (3-day pre-FOMC window)
- **Thesis:** SPY has earned ~80% of its excess return in the 3 days before scheduled FOMC announcements (Lucca & Moench, NY Fed 2015, "The Pre-FOMC Announcement Drift"). Buy SPY MOC two days before FOMC, sell MOC on announcement day.
- **Features:** FOMC calendar (8 meetings/yr, scheduled in advance).
- **Data:** Daily bars + FOMC calendar (hardcoded from federalreserve.gov).
- **Lit Sharpe:** Lucca & Moench reports the pre-FOMC drift accounting for the bulk of equity risk premium; standalone strategy Sharpe ~0.7–1.0 with very few trades. Verify.
- **Cost sensitivity:** VERY LOW. 8 round-trips/yr × 2 bps = ~2 bps drag.
- **Diversity:** Calendar/macro trigger. Completely orthogonal. HIGH novelty.

### A16. Inverse Volatility Position Sizing (overlay)
- **Thesis:** Size positions inversely to recent realized vol (target constant risk). Doesn't generate signals — improves any existing strategy's Sharpe by smoothing returns.
- **Features:** Rolling realized vol per symbol.
- **Data:** Daily bars.
- **Lit Sharpe:** Adds ~0.1–0.3 to base strategy Sharpe. Not a standalone strategy.
- **Cost sensitivity:** None (no extra trades).
- **Diversity:** Pure overlay. Should be in `_lib/`, not a strategy. LOW novelty as a parent; HIGH leverage as a tool.

### A17. Lunch-Lull Mean Reversion (intraday)
- **Thesis:** Volume drops dramatically 11:30–13:30 ET; price tends to revert toward VWAP during this window before institutional flow returns. Fade extreme morning moves into the lull, exit before 14:00.
- **Features:** VWAP(today), morning range, time-of-day.
- **Data:** 1-min bars (intraday prereq again).
- **Lit Sharpe:** ~0.5–0.8 on liquid ETFs; degraded by HFT in recent years. Verify.
- **Cost sensitivity:** HIGH — intraday + small per-trade edge.
- **Diversity:** Intraday + mean-rev. Same cycle family as A2/A6, but specifically mid-day. MODERATE novelty.

### A18. Trend + Regime-Conditional Position Sizing (proper regime filter, not just on/off)
- **Thesis:** Our current regime filter is binary (`regime_uptrend`). Upgrade: scale position size LINEARLY with trend strength (e.g. % above 200-DMA, or 50/200 ratio). In raging bull markets, hold 100%; in weak uptrends, hold 50%; in downtrends, hold 0%.
- **Features:** SPY 200-DMA distance percentile, ADX(14).
- **Data:** Daily bars on SPY. Already injected.
- **Lit Sharpe:** Adds ~0.2–0.5 to a base trend strategy. Faber 2007 ("A Quantitative Approach to Tactical Asset Allocation") shows monotonic improvement from coarser regime gating.
- **Cost sensitivity:** Slight increase in rebalancing trades; net cost-positive due to drawdown reduction.
- **Diversity:** Refinement of existing approach. LOW novelty as a parent, but probably the SINGLE HIGHEST-EV item per HANDOFF's "regime filter is the cheapest edge" lesson. Already largely covered by current `regime_uptrend` — implementing a *gradient* version is a small step.

---

## Section 2 — Pareto Ranking

Three axes (1 = best, 5 = worst):

| # | Archetype | EV at $100/IEX | Impl. Complexity | Data Availability | Notes |
|---|-----------|----------------|------------------|-------------------|-------|
| A1 | Bollinger Z-Score MR | 3 | 1 | 1 | Same family as failed CRSI2 — careful |
| A2 | Opening Range Breakout | 2 | 4 | 3 | Needs intraday harness; cited Sharpe high |
| A3 | Overnight Drift | 2 | 2 | 2 | MOC/MOO execution risk on Alpaca paper |
| A4 | Turn-of-the-Month | 1 | 1 | 1 | Free, cheap, well-documented |
| A5 | PEAD | 2 | 4 | 4 | Needs earnings + consensus data; high novelty |
| A6 | Gap Fade | 4 | 4 | 3 | Intraday + cost-risky |
| A7 | Gap-and-Go | 3 | 4 | 4 | Needs news API for filter to work |
| A8 | Pairs / StatArb | 2 | 3 | 1 | BLOCKED: needs shorts |
| A9 | Volatility Risk Premium | 3 | 2 | 2 | Tail risk — mandatory safety rail |
| A10 | Sector Rotation | 1 | 2 | 1 | Canonical, cheap, diversifying |
| A11 | Low-Vol Defensive | 2 | 2 | 1 | Modest edge, good drawdown reducer |
| A12 | Volume/OBV (overlay) | n/a | 2 | 3 | BLOCKED: needs volume in bars_cache |
| A13 | Keltner Breakout | 4 | 1 | 1 | Too close to existing breakout |
| A14 | Day-of-Week | 4 | 1 | 1 | Decayed edge, cost-fragile |
| A15 | FOMC Drift | 2 | 1 | 1 | Free hardcoded calendar, strong cited edge |
| A16 | Inverse-Vol Sizing | n/a | 1 | 1 | OVERLAY: belongs in `_lib/`, not a parent |
| A17 | Lunch-Lull MR | 3 | 4 | 3 | Intraday + decayed edge |
| A18 | Gradient Regime Sizing | 2 | 1 | 1 | OVERLAY: refines existing regime filter |

**Pareto-frontier (best on at least one axis without being dominated):**
- A4 (Turn-of-the-Month) — Pareto-best on all 3 axes
- A10 (Sector Rotation) — tied with A4 on EV+data, slightly more complex
- A15 (FOMC Drift) — same Pareto position as A10 but FEWER trades, smaller statistical N
- A2 (ORB) — best EV but complexity 4; on the frontier
- A5 (PEAD) — high novelty + EV but complexity 4 + data 4; on the frontier
- A8 (Pairs) — high novelty + good data but BLOCKED on shorting; on the frontier conditional on unblock

---

## Section 3 — TOP 5 FOR WEEKEND SPRINT

Selection criteria: implementable by a single subagent in a few hours, doesn't require infra work outside the sprint, maximizes DIVERSITY of return streams vs our existing pool, plays to the cheapest-edge lessons (regime filter, calendar/event triggers, low trade count).

### 🥇 #1 — Turn-of-the-Month (A4)
- **Why first:** Cheapest possible implementation (pure calendar trigger, no indicator math). Negligible cost drag. Decades of academic backing. Returns stream is essentially orthogonal to our trend pool — it'll be flat 80% of the year. Excellent acid test for Bar A.
- **Implementer notes:** Single Python file. Use `runner/market_hours.py` for trading-day arithmetic. Holding window: last trading day of month → 3rd trading day of next month, on SPY. Variant to also test: same on QQQ. Variant to test: only enter if SPY > 200-DMA (regime-gated TOM).
- **Risk:** Effect may have weakened post-2010; the 8-window walk-forward will surface this.

### 🥈 #2 — Sector Rotation / Dual Momentum (A10)
- **Why second:** Cross-sectional signal is a fundamentally NEW family for us. Cheap (12 rebalances/yr). Well-documented canon. Uses ETFs already common in our universe.
- **Implementer notes:** Universe = {XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC}. Each month, hold the top-1 by trailing 6-month return, BUT only if its return > 0 (Antonacci "absolute momentum" filter — falls back to cash/SHY in bear regimes). Single position at a time so it fits $100 cap. Variant: top-3 equal-weight if multi-position is unlocked.
- **Risk:** Sector rotation can have long flat periods inside the right sector; expect lumpy returns.

### 🥉 #3 — FOMC Drift (A15)
- **Why third:** Strong cited edge (~80% of equity risk premium concentrated in 3-day pre-FOMC window per NY Fed). Trivially cheap (8 trades/yr × 2 bps). Pure macro/calendar trigger — most orthogonal possible to our price-based pool.
- **Implementer notes:** Hardcode 2024–2028 FOMC dates (8/yr, publicly scheduled). Strategy: buy SPY at MOC two trading days before FOMC announcement; sell at MOC on announcement day. Variant: also test holding through announcement (sell next-day open). Variant: regime-gate (only when SPY > 200-DMA).
- **Risk:** N=8/yr is statistically thin — walk-forward needs ≥4 years to clear `trade count ≥ 30` from Bar A. Decision: skip this one if backtester can't extend back to 2018 reliably, OR pair it with TOM (combined 8+12 = 20/yr).
- **Mitigation if N too small:** combine with other calendar events (Treasury refunding, options expiration "OpEx week") to boost trade count.

### 🏅 #4 — Overnight Drift (A3)
- **Why fourth:** Microstructure-level trigger (close-to-open). Cited 68% of SPY's total return historically (alphaticaio, 22-yr study). Daily-frequency execution (no intraday infra needed). HIGH diversity vs price-pattern parents.
- **Implementer notes:** Buy MOC, sell MOO. Test on SPY, QQQ, IWM separately. CRITICAL: verify Alpaca paper actually executes MOC/MOO orders and what the fill model looks like in `backtest.py` (today's `close` and next bar's `open` are the simulated fills — confirm this is what the live runner can actually achieve). Variant: only enter when VIX < 20 (per Elm Wealth). Variant: skip Mondays (weakest day historically).
- **Risk:** Recent decay claims (AlphaTica "drift is dead" 2024) — held-out final window per Bar A item 2 will catch this if true.

### 🏅 #5 — Bollinger Z-Score Mean Reversion (A1)
- **Why fifth (despite CRSI2 failure):** We genuinely DO need a mean-reverter in the pool. CRSI2 failed on specific RSI-based triggers; pure z-score on raw price with a regime filter is a meaningfully different parameterization. AND — the CRSI2 failure was partly methodological (SMA(200) warmup window) per HANDOFF; revisit with a longer warmup. This is the only top-5 entry in the "high risk of redundancy" zone, but we need to know if the failure was z-score-the-concept or CRSI2-the-implementation.
- **Implementer notes:** SPY/QQQ/IWM, daily bars. Buy when z = (close - SMA(20)) / std(20) < -2.0; sell when z > 0. ADX(14) < 25 filter to skip trending regimes (CRITICAL — this is where CRSI2 lost). Required harness extension: warmup ≥ 200 bars before window start.
- **Risk:** Could repeat the CRSI2 result. Acceptable risk because (a) different parameterization, (b) we'll learn whether mean-reversion-as-a-family is dead on US ETFs vs whether CRSI2 specifically was the wrong instance.

---

## Section 4 — Honorable Mentions (sprint reserves)

If any of the top-5 fails fast (Bar A reject within an hour), pick from these in order:

6. **A8 Pairs Trading** — only if shorting capability is added to `runner/`. KO/PEP, GLD/IAU, XLE/XOM are natural cointegrated US pairs.
7. **A11 Low-Vol Defensive Tilt** — long XLP+XLU when SPY 20d realized vol > 75%ile. Simple, complementary to trend pool.
8. **A9 Volatility Risk Premium** — long SVXY when VIX < 18 AND term structure in contango. MANDATORY `safety_max_loss_pct: -25.0` rail (per HANDOFF safety_backstop infra).

---

## Section 5 — Explicitly Deferred / Rejected

- **A2 ORB, A6 Gap Fade, A7 Gap-and-Go, A17 Lunch-Lull** — ALL require intraday bars. Per HANDOFF Saturday task list item (a), the harness audit for intraday support is a PREREQUISITE. Don't fan out subagents to these until the audit is done.
- **A12 Volume/OBV** — blocked on `bars_cache` not carrying `v`. Same HANDOFF note ("slot #15 reserved, blocked on volume").
- **A5 PEAD** — defer until earnings+consensus data source is chosen and wired. Worth a separate scoping doc, not a single subagent.
- **A13 Keltner Breakout** — too similar to existing breakout family. Would burn an attempt without diversifying the pool.
- **A14 Day-of-Week** — edge probably eaten by costs at our notional.
- **A16 Inverse-Vol Sizing, A18 Gradient Regime Sizing** — these are OVERLAYS, not parents. They belong in `strategies/_lib/` as helper utilities that future parents can opt into. Not a tournament archetype.

---

## Section 6 — Cross-Cutting Implementer Reminders

1. **Bar A is law.** Every archetype must pass walk-forward on all 8 named regime windows (median return positive per regime, post-cost), held-out final window unseen during tuning, cost-aware Sharpe ≥ 0.5, ≥30 trades, max DD ≤ 30%, AST review + smoke test. Pre-commit to this before running. (`GATE.md`.)
2. **Regime filter is the cheapest edge.** Every archetype should test both naked and `regime_uptrend(spy_closes, 50)`-gated variants. The latter consistently reduces drawdowns by ~80% with no median-return loss per HANDOFF.
3. **Cost realism.** Use `CostModel` honestly. Pre-cost numbers are vanity. Intraday strategies must show edge AFTER 2 bps × trade-count is subtracted.
4. **Use `safety_max_loss_pct` rails** on anything with fat-tailed-left distribution (A9 mandatory; A2/A6/A7 recommended).
5. **`strategies_candidates/` only.** NEVER write directly to `strategies/`. Manual `mv` + smoke is the human gate.
6. **Statistical hygiene.** Per Bar A item 2, the final regime window is HELD OUT. If you tune on it, you've burned it for that archetype — slide the holdout earlier.

---

## Section 7 — Sources Cited

Direct URLs confirmed during research (2026-05-29):
- QuantConnect ORB research (Sharpe 2.4 on 1000 stocks): https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- VolatilityBox ORB (55-62% win rate ES/NQ): https://volatilitybox.com/research/opening-range-volatility-breakout/
- AlphaTica "Overnight Drift Is Dead" thread (68% of SPY return overnight): https://x.com/alphaticaio/status/2042401233067995201
- Elm Wealth "Still Working the Night Shift": https://elmwealth.com/night-shift/
- Trading Time Machine SPY overnight study: https://www.tradingtimemachine.com/studies.html
- QuantBuffet overnight SPY strategy: https://quantbuffet.com/en/2025/01/18/overnight-anomaly/
- Advisor Perspectives "Working Night Shift Still": https://www.advisorperspectives.com/articles/2025/03/11/working-night-shift-still
- McConnell & Xu Turn-of-the-Month (Purdue PDF): https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf
- Quantpedia Turn-of-the-Month: https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes
- Quantpedia PEAD: https://quantpedia.com/strategies/post-earnings-announcement-effect
- DayTrading.com PEAD overview: https://www.daytrading.com/post-earnings-announcement-drift-pead-strategy

Canonical academic references (cited from literature memory; subagent implementers should verify before encoding any threshold):
- Lakonishok & Smidt 1988 — original turn-of-month documentation, DJIA 1897–1986
- Ball & Brown 1968 — original PEAD documentation
- Gatev, Goettler, Goyal, Rouwenhorst 2006 — pairs trading performance
- Frazzini & Pedersen 2014 — "Betting Against Beta" (low-vol anomaly)
- Antonacci 2014 — "Dual Momentum Investing" (sector rotation framework)
- Lucca & Moench 2015 (NY Fed) — pre-FOMC announcement drift
- Connors & Alvarez 2009 — *Short Term Trading Strategies That Work* (CRSI2 family)
- Faber 2007 — "A Quantitative Approach to Tactical Asset Allocation" (regime filter)

---

**End of scoping doc.**

Next action (NOT in this subagent's scope): main / Tessera selects the top 5 (or top N) to fan out as parallel backtest subagents Saturday post-leaderboard, each with isolated scratch dir + bounded mandate referencing this doc and `GATE.md` Bar A.
