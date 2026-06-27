# AQR / Man / Jane-Street Reading Sprint #2 — NEW Hypothesis Shortlist

**Date:** 2026-06-26
**Author:** Tessera (trading-bench), opus subagent
**Type:** Hypothesis-generation reading sprint (research-only; NO code, NO config, NO trades)
**Mandate (main):** Run a focused reading sprint on published AQR / Man / Jane-Street research and produce a *new* hypothesis shortlist — explicitly NOT re-pitching the five ideas from the 2026-06-24 sprint (delisting-PIT universe, standalone TSMOM sleeve, implied−realized corr/dispersion, macro-momentum xsec rank, COR3M throttle).

---

## TL;DR — the new shortlist (ranked)

| # | New hypothesis | Source mechanism | Orthogonal to our book? | Data we have FREE? | Verdict |
|---|---|---|---|---|---|
| **1** | **Cross-asset CARRY sleeve** (bond + commodity + FX + equity-index carry, long high-carry / flat-or-short low-carry) | AQR/JFE "Carry" (Koijen-Moskowitz-Pedersen-Vrugt) | **Yes** — carry ≠ trend; only co-crashes in global recessions | **Mostly yes** (TLT/IEF/SHY/TIP, DBC, 7 FX, GLD; equity-index carry needs a proxy) | **BUILD-NOW candidate #1** |
| **2** | **"Hold-the-Dip" audit → flip `rsi_oversold_spy` to trend-aligned / kill the anti-momentum leg** | AQR "Hold the Dip" (Dec 2025) | Improves an EXISTING parent (not new return stream) | ✅ 100% (SPY OHLCV already cached) | **BUILD-NOW candidate #2 (cheap, falsifiable)** |
| **3** | **Value+Momentum *combination at the sleeve level*** — pair our trend/momentum book with a negatively-correlated value-tilt timing signal (book-level, not constituent ranking) | AQR/JoF "Value and Momentum Everywhere" | Yes (V and M are *negatively* correlated by construction) | ⚠️ Partial — value signal on indices is doable; single-name value is universe-gated | **PROTOTYPE-GATE** |
| 4 | **Carry-as-a-regime-throttle** (use bond/FX carry compression as a risk-off overlay on the equity book, instead of as its own sleeve) | "Carry" + "Defensive Equity" downside-timing | Partially (overlay, shares some beta) | ✅ (same data as #1) | maybe — probe vs SMA-200 first |
| 5 | **Performance-chasing penalty / anti-rearview allocator rule** (don't down-weight a sleeve just because it lagged in the last bull leg) | AQR "Diversifying Alternatives and the Rearview Mirror" | Allocator-hygiene, not a return stream | ✅ | **NOTE/ADOPT as a rule, not a strategy** |

**Genuinely buildable-now on free data: #1 (cross-asset carry sleeve) and #2 (hold-the-dip audit of `rsi_oversold_spy`).** Everything else is either a prototype-gate (#3), a probe-first overlay (#4), or an allocator hygiene rule (#5).

---

## Papers actually read this sprint (web_fetch, primary source = aqr.com, HTTP-200)

All AQR pieces below were pulled live and read in full-abstract form. **Man Group / Man Institute is region- AND CAPTCHA-walled from this datacenter IP** (every `man.com/maninstitute/...` path returns a 404 region-gate or a CAPTCHA subscribe wall) and **SSRN is Cloudflare-403 ("Just a moment...")**, so Man and the SSRN working-paper PDFs could NOT be freshly fetched — those I reference from prior domain knowledge and flag explicitly as *not-freshly-verified-this-sprint*. **Jane Street**'s public site is a JS-rendered cookie shell with no fetchable prose; its public output is engineering/probability talks, not tradeable-signal research (honest assessment below). This is itself a useful finding: of the three houses, **only AQR is directly readable from our IP.**

1. **"Carry"** — *Journal of Financial Economics* (Koijen, Moskowitz, Pedersen, Vrugt). Read live.
   - **Claim:** An asset's "carry" = its expected return *assuming price and market conditions stay the same* — measurable in advance, with NO asset-pricing model. Expected return = carry + expected price appreciation.
   - **Claim:** Carry predicts returns in **both cross-section and time series** across global equities, global bonds, currencies, commodities, US Treasuries, credit, and equity-index options. A long-high-carry / short-low-carry portfolio earns robust returns across *all* these classes, not just FX (where the carry trade is famous).
   - **Honest caveat the paper itself states:** despite low *unconditional* cross-class correlation, **all carry strategies do poorly at the same time, and those episodes coincide with global recessions** — i.e. carry has a hidden common crash factor (it's a "picking up nickels" premium that pays for tail risk). This matters for sizing and for the orthogonality claim.

2. **"Value and Momentum Everywhere"** — *Journal of Finance* (Asness, Moskowitz, Pedersen). Read live.
   - **Claim:** Consistent value AND momentum premia across **eight markets/asset classes**, with a strong *common factor structure*. Critically: **value and momentum are *negatively* correlated with each other**, both within and across asset classes. A combined global V+M portfolio has a far higher Sharpe than either alone.
   - **Mechanism for us:** the *negative correlation* is the usable structural fact — a value-tilt sleeve is a natural diversifier to a momentum/trend book *precisely when momentum stumbles* (momentum crashes are often value rebounds).

3. **"Hold the Dip"** — AQR Alternative Thinking (Dec 1, 2025). Read live.
   - **Claim (with their data):** "Buy the Dip" **does NOT beat buy-and-hold** over the long run. The reason given is structural: **buy-the-dip is usually positioned *opposite* momentum** (you buy after a fall, which is short-trend), so it fights a known premium. If you want to time entries/exits, **align with momentum (follow the trend), don't buy the dip.**
   - **Direct relevance:** our live parent **`rsi_oversold_spy` is a textbook buy-the-dip** (enter on RSI oversold = after a drop). AQR is effectively saying that signal class carries a momentum *headwind*. This is a falsifiable claim we can test on our own SPY data in an afternoon.

4. **"A Century of Evidence on Trend-Following Investing"** — AQR / *JPM* (Hurst, Ooi, Pedersen). Read live.
   - **Claim:** Time-series momentum (long recent-winners / short recent-losers) was **consistently profitable 1880→1990 and beyond** across equity-index/bond/commodity/FX futures — trend is not a recent fluke. Reconfirms the TSMOM sleeve thesis (already our 06-24 idea #2; NOT re-pitched here, only cited as the backdrop for carry-vs-trend orthogonality).
   - **Useful caveat they flag:** post-credit-crisis, **cross-market correlations rose** and AUM grew — trend's diversification has thinned. Relevant to why we want a *non-trend* cross-asset premium (carry) rather than a second trend sleeve.

5. **"Understanding Defensive Equity"** — AQR White Paper. Read live.
   - **Claim:** The "low-risk anomaly" — high-beta stocks have historically earned **~the same average return as low-beta** stocks, so a defensive (low-beta/low-vol) portfolio delivers benchmark-like long-run return at materially lower vol and smaller drawdowns.
   - **Reality check for us:** this is a *cross-sectional constituent* anomaly → it falls squarely under our **CROSS-SEC FACTOR GATE**, and we already **closed BAB (Betting-Against-Beta) twice** as a survivorship-beta mirage on our fixed universe (2026-06-23). So defensive-equity-as-a-stock-picker is **DEAD-on-arrival for us** unless expressed as a beta-of-the-index timing tool (which overlaps SMA-200 / vol-target we already run). Logged as "read and rejected," not a new lane.

6. **"Diversifying Alternatives and the Rearview Mirror"** — AQR White Paper (Nov 2025, "Understanding Return Expectations" Pt.10). Read live.
   - **Claim:** Diversifying L/S alternatives *feel* like a drag in bull markets even when they improve long-term wealth, because stock markets rise most of the time. The same investor biases (extrapolation, performance-chasing) that *create* L/S opportunities also make investors abandon those sleeves at the wrong time.
   - **Relevance:** not a return signal — an **allocator-discipline rule** for our blend: do not performance-chase / do not cut a diversifying sleeve (e.g. a carry or trend sleeve) just because it lagged the last bull leg. Worth encoding as a guardrail in the allocator's weighting cadence.

*(Also surfaced in the live AQR index but not core to this sprint: "Total Portfolio Approach," "2026 Capital Market Assumptions" [global 60/40 real expected return 3.4%, risk premia compressed], "Exploring Capital Efficiency," "Rebuffed: buffer funds," "Bond Market Focus: Treasury yields via survey data." None opens a new free-data return lane for a $100 paper book; noted for completeness.)*

---

## Gate / data-reality check, idea by idea

### #1 — Cross-asset CARRY sleeve  ← TOP NEW BUILD CANDIDATE
**Mechanism (from "Carry"):** carry = the return you earn if prices don't move; it predicts returns in TS and XS across asset classes. Build a long-high-carry basket across asset classes (and optionally short/flat the low-carry ones), sized to vol.

**What carry *is*, per asset class, and whether we can compute it FREE:**
- **Bonds / rates → YES.** Term-structure carry ≈ yield + roll-down. We have **TLT, IEF, SHY, TIP** cached (Yahoo adjclose) and **FRED keyed API** for the actual yield curve (`DGS2/DGS10/...`) — bond carry is directly computable (slope of the curve + roll). This is the cleanest leg.
- **Commodities → PARTIAL/YES.** Commodity carry = front-minus-deferred futures slope (backwardation = positive carry). We have **DBC** (broad basket) and **EIA WTI / PET bulk** cached. A clean per-commodity term-structure carry needs futures curves we don't fully have free, BUT a **broad-commodity carry proxy** (e.g. roll-yield sign of DBC vs a spot/near proxy, or USO-vs-DBC) is approximable. Honest: this leg is the roughest.
- **FX → YES.** FX carry = interest-rate differential. We have **7 G10 pairs** (EUR/GBP/AUD/NZD/CAD/CHF/JPY vs USD) cached + **FRED** for policy rates → classic carry trade is fully buildable.
- **Equity-index → PROXY NEEDED.** Equity carry ≈ dividend yield − financing rate (roughly the index's expected-dividend carry). We have SPY/QQQ/sector ETFs; dividend yield is derivable from price-vs-total-return or from the adjclose/close gap. Approximable, not pristine.

**Orthogonality to our book (why it might be genuinely new):**
- Our book is **trend / momentum / breakout** on single-name equity+ETF, plus a TQQQ vol-target sleeve and a sector-rotation (3-month-momentum) allocator. **Carry is a structurally different premium from trend** — "Value and Momentum Everywhere" and the trend papers establish that carry, trend, and value are distinct factors. AQR's own framing: carry's correlation to trend is low *unconditionally*. So a carry sleeve should diversify a trend-heavy book.
- **BUT** the paper's own honest caveat is the catch: **carry co-crashes across all classes in global recessions** — exactly when our equity book also bleeds. So carry is NOT crisis-alpha (trend is the crisis-alpha sleeve; carry is the opposite — it harvests calm and pays in tails). That's fine as a *diversifier in normal regimes* but it must be (a) vol-sized and (b) ideally gated off in deep risk-off, and we must NOT assume it hedges drawdowns. This is the key honest distinction vs the 06-24 TSMOM idea.

**First-test plan (one line):** Build bond+FX carry only (the two clean legs), long-high-carry / flat-low-carry, monthly rebalance, vol-targeted; measure full-period continuous-Sharpe and correlation to our allocator blend AND to SPY drawdowns — promote only if corr-to-blend < ~0.3 AND it survives the global-recession co-crash inspection (2008/2020/2022) without wrecking the book.

**Verdict: BUILD-NOW candidate.** Distinct premium, mostly-free data, clear orthogonality thesis, with an honest tail-risk caveat baked into the test.

---

### #2 — "Hold-the-Dip" audit of `rsi_oversold_spy`  ← CHEAPEST NEW WIN
**Mechanism (from "Hold the Dip"):** dip-buying underperforms because it's anti-momentum. Our `rsi_oversold_spy` enters *after* a drop (RSI oversold) → it is structurally the dip-buy AQR just published evidence against.

**Data:** 100% free — SPY OHLCV already cached. Zero new data.

**Why it might improve the book (not a new stream, an *upgrade*):** if AQR is right, the oversold-entry leg is fighting a headwind. Two falsifiable variants to A/B vs the live parent:
1. **Trend-gate the dip-buy:** only take the RSI-oversold entry when SPY is *above* its 200-day SMA (buy the dip only in an uptrend = align with the longer trend while catching the pullback). AQR's nuance is "don't buy the dip *against* the trend"; a trend-filtered dip-buy may survive.
2. **Flip to trend-aligned entry:** replace oversold-entry with breakout/momentum-entry on SPY and compare — does the same instrument do better trend-following than dip-buying, as AQR claims?

**First-test plan (one line):** Backtest `rsi_oversold_spy` as-is vs (a) +SMA-200 trend gate and (b) momentum-entry variant on the SAME SPY path with our CostModel; if the trend-gated/flip variant beats the dip-buy OOS net of cost, propose the swap; if the raw dip-buy holds up, we've *empirically rebutted* AQR on our instrument (also a publishable internal finding).

**Verdict: BUILD-NOW candidate.** Free, fast, directly tests a live parent against fresh published evidence, falsifiable either way. **NOTE:** this is an *improvement to an existing child*, not a new return engine — but it's the highest-confidence, lowest-cost item on the list and it directly stress-tests something we already trade.

---

### #3 — Value+Momentum combination at the SLEEVE level  ← PROTOTYPE-GATE
**Mechanism (from "Value and Momentum Everywhere"):** V and M are *negatively correlated*; combined Sharpe ≫ either alone. Our book is momentum/trend-heavy with **no value exposure at all.** A value-tilt sleeve would be the natural negative-correlation diversifier.

**The gate problem (be honest):** single-name *value* (cheap-vs-expensive cross-section) on our **fixed modern-survivor universe is exactly what the CROSS-SEC FACTOR GATE kills** — we already closed fundamentals-PIT value as a survivorship-beta mirage (2026-06-23), and the L/S spread was negative. So *constituent-level* value is **NOT** newly buildable. What *is* potentially new and gate-legal:
- **Asset-class / index-level value timing** (e.g. value of the bond market via real yield, value of equities via earnings yield / CAPE-like signals from FRED + index data, value of commodities via spot-vs-5yr-average) — these are TS value signals on *indices*, not constituent ranking, so they sidestep the survivorship gate. This is the AQR "value everywhere" idea applied at the asset-class level, paired with our existing momentum book to harvest the negative correlation.

**Data:** index earnings/real-yield via FRED + Yahoo index adjclose — mostly free; the cleanliness of an index-value signal is the open question.

**First-test plan (one line):** Construct one asset-class TS-value signal (equity earnings-yield z-score vs history) and measure its correlation to our momentum/trend book — if it's reliably negative (as the paper predicts) and the combined sleeve lifts continuous-Sharpe vs momentum-alone, promote to a build; if the index-value signal is just inverse-momentum noise, shelf.

**Verdict: PROTOTYPE-GATE.** Strong theoretical orthogonality (the negative V/M correlation is the most robust finding in the AQR corpus), but constituent-value is gate-dead and index-value cleanliness is unproven — probe before committing.

---

### #4 — Carry-compression as a risk-off throttle  ← PROBE-FIRST OVERLAY
**Mechanism:** instead of (or in addition to) a carry *return sleeve*, use **carry compression** (bond/FX carry collapsing) as a macro risk-off signal to de-risk the equity book — leaning on the paper's finding that carry crashes cluster with global recessions, so *carry stress can be an early macro-distress gauge.*

**Honest concern:** we have already closed a long list of equity-timing overlays (yield-curve, NFCI, VIX-term, credit HYG/LQD) where the OOS win dies on a +1-day lag or doesn't fire earlier than SMA-200. A carry-stress overlay risks the same fate. Data is free (same as #1).

**First-test plan (one line):** Build a bond+FX carry-stress index, lag it +1 day, and check whether it flags 2008/2020/2022 risk-off *earlier and more cleanly than SMA-200* — if not, it's redundant (same verdict as the closed overlays); only pursue if it adds incremental early-warning.

**Verdict: MAYBE — probe vs SMA-200 first.** Lower priority than #1 because the overlay graveyard is deep.

---

### #5 — Anti-performance-chasing allocator rule  ← ADOPT AS HYGIENE, not a strategy
**Mechanism (from "Rearview Mirror"):** diversifying sleeves feel like a drag in bull markets; cutting them on recent underperformance is the classic mistake. Our allocator re-weights on a rolling lookback — if that lookback over-reacts to a sleeve's recent lag, we're performance-chasing.

**First-test plan (one line):** Audit the allocator-blend weighting cadence — does a diversifying sleeve (carry/trend/haven) get cut after a single bad bull-leg? If so, add a guardrail (min weight floor / longer smoothing) so we don't abandon diversifiers at the wrong time.

**Verdict: ADOPT as an allocator guardrail.** Not a return stream — a documented hygiene rule. Cheap to encode; aligns with our existing allocator work.

---

## Reconciliation with prior closed lanes (skepticism / no-duplication check)
- **NOT re-pitching** any 06-24 idea: this sprint's #1 (carry) is a *different premium* from the 06-24 TSMOM sleeve (trend); #3 (V+M) is value, never tried at sleeve level; #2 (hold-the-dip) is a parent audit, not a new stream.
- **Carry vs our closed "bond+commodity carry" note (06-23):** MEMORY records "further inv-vol trend / carry-leg constructions … tested to exhaustion 2026-06-23" — but that was carry as an *inverse-vol overlay leg inside the trend sleeve*, which the inv-vol weighting gutted (same failure as the trend overlay). It was **never run as a standalone cross-asset carry *return* sleeve, return-weighted, across bonds+FX+commodities+equity-index per the JFE "Carry" construction.** That distinction is exactly why #1 is new — same lesson as how the standalone TSMOM sleeve (06-24 #2) was new despite trend having been an overlay. **Pre-flight before building #1:** re-read the 06-23 carry-leg report to confirm the standalone return-weighted construction was genuinely never tested (if it was, downgrade #1).
- **Defensive equity / low-beta:** explicitly **rejected this sprint** as constituent-level (CROSS-SEC GATE + BAB already closed twice). Logged so it isn't re-pitched.
- **Jane Street:** honest finding — their public corpus is engineering/probability/market-microstructure talks (adverse selection, OCaml, puzzles), **not retail-reproducible alpha signals**; nothing actionable for a daily-bar $100 paper book. Not a failure of effort — a correct read of what they publish.

---

## Recommended sequencing
1. **#2 (hold-the-dip audit of `rsi_oversold_spy`)** FIRST — cheapest, free data, directly tests a live parent against fresh evidence, falsifiable in an afternoon. Either improves a child or rebuts AQR on our data; both are wins.
2. **#1 (cross-asset carry sleeve, bond+FX legs first)** — the genuinely-new *return* lane; mostly-free data; clear orthogonality thesis with an honest tail caveat. Pre-flight the 06-23 carry-leg report first to confirm novelty.
3. **#3 (index-level value paired with momentum)** — prototype-gate on the negative-correlation probe before a full build.
4. **#4 (carry-stress overlay)** — only if it beats SMA-200 as an early-warning; the overlay graveyard is deep.
5. **#5 (anti-rearview allocator guardrail)** — adopt as an allocator hygiene rule whenever the blend-weighting cadence is next touched; not a strategy, but cheap insurance against cutting diversifiers at the wrong time.

---

## Data-access findings (useful meta-result of this sprint)
- **AQR (aqr.com)** = the only one of the three houses **directly readable** from our datacenter IP (HTTP-200, clean abstracts). Exact slugs matter (many 404; the live `/Insights/Research` index is the reliable way to discover current valid slugs).
- **Man Group / Man Institute** = **region- + CAPTCHA-walled** from this IP (every `man.com/maninstitute/...` path → 404 region-gate or subscribe-CAPTCHA). Could not freshly fetch; Man trend/crisis-alpha pieces referenced from prior knowledge are flagged as such.
- **SSRN** = **Cloudflare-403** ("Just a moment..."). Working-paper PDFs not fetchable headless from this IP.
- **Jane Street** = JS-rendered cookie shell; public output is engineering/probability talks, not tradeable-signal research.
- Implication for future reading sprints: **lead with AQR's live research index**; for Man, either use a residential path / cookies or rely on the (well-known) published abstracts; don't burn cycles re-trying SSRN headless.

---
*No protected file touched. No config changed. Nothing scheduled. No code written. All AQR abstracts read live via web_fetch on 2026-06-26; Man/Jane-Street walled from this IP and flagged accordingly. This is hypothesis-generation only — every "BUILD-NOW" item still owes a real backtest with our CostModel, continuous-Sharpe measurement, and (for #1/#3) the CROSS-SEC/orthogonality gates before any promotion.*