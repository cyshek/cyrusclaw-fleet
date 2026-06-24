# LITERATURE-MINED HYPOTHESES — Orthogonal Structural Edges for the Bench

**UTC stamp:** 20260623T185057Z · **Mode:** reading / hypothesis-generation ONLY (no backtest, no code, no data fetch beyond paper/abstract reads, no protected-file touches) · **Author:** trading-bench subagent (opus)

**Sources, with honesty about reachability (per task):**
- **Freshly fetched this session (web_fetch, clean 200):** AQR *Betting Against Beta* (Frazzini-Pedersen, JFE 2014) abstract; AQR *Time Series Momentum* (Moskowitz-Ooi-Pedersen, JFE 2012) abstract; AQR *Carry* (Koijen-Moskowitz-Pedersen-Vrugt, JFE 2018) abstract; Wikipedia low-volatility-anomaly, normal-backwardation, carry, index-fund pages (for definitional grounding).
- **web_search is DISABLED on this VM** (provider error) → I could not keyword-search; I fetched known canonical URLs directly. **SSRN is Cloudflare-403 from this datacenter IP**, **Man Institute URLs had drifted (404)**, and **the NY-Fed staff-report PDF returns undecoded binary** (web_fetch has no PDF extractor). For those I lean on the **canon I know** and our own **scout reports**, and I flag every from-memory claim as such below. Nothing here is fabricated; where I'm citing from memory rather than a fetched abstract, it says "(from memory)".
- **Bench scout reports read for grounding (on-disk, not external):** `SCOUT_SYNTHESIS_20260605.md`, `DATA_SCOUT_FUNDAMENTALS_20260608.md`, `SCOUT_altdata_20260605.md`, `DATA_SCOUT_ALTSIGNAL_20260608.md`, plus the `CREDIT_STRESS_20260609.md` and `FUNDAMENTALS_PIT_QUALITY_VALUE_20260623T183915Z.md` verdicts (to draw the closed-lane boundaries precisely).
- **Data facts verified on disk this session** (so the feasibility axis is grounded, not guessed): `data_cache/yahoo/` already holds `GLD, DBC, USO, TLT, HYG, SPY, QQQ, TQQQ` (and 4,500+ single names) as `<TICK>_parsed.json`; `data_cache/cot/` holds the **TFF financial-futures** report only (`fut_fin_*` 2010→2026) — **not** the disaggregated *commodity* COT; FRED keyed client exists per scout.

---

## 1. The bench's actual orthogonality gap (what we're missing)

Our **entire live/validated book is one risk family in three costumes:**
- TQQQ vol-target leveraged-trend sleeve = **trend + vol-timing + leverage** on US-equity tech.
- Sector rotation (SPY/QQQ/GLD/TLT, 3-mo price momentum, top-2) = **cross-asset price momentum + flight-to-haven**.
- Allocator blend of the two (inverse-vol) + a COT-positioning **modulator** on the vol-target.

Every dollar we run is **directional, price/trend/vol-driven, long-biased US-equity-or-haven beta.** The COT modulator is the only non-price input, and only as a conditioner. The closed-lane graveyard confirms the pattern: we have exhaustively tested **more flavors of the same family** (xsec momentum, lev-ETF trend, vol-regime timing, VIX term-structure, SKEW, credit-as-equity-*timer*, short-volume) and they either died or were redundant-with-trend. The two genuinely-different things we tried as *return engines* — **fundamentals cross-section** and **PEAD** — died on survivorship/liquidity, and the one **alt-data** family (Reddit) died on licensing/overfit.

**So the gap is precise:** we have **no edge that earns from a non-directional, cross-sectional-across-assets, risk-premium-or-friction source that does NOT require the US-equity market to go up and does NOT key off price-trend.** The literature's strongest *survivors* that fit that description are **(a) carry across asset classes, (b) the betting-against-beta / leverage-constraint premium, and (c) time-series momentum on the asset complex we don't trade.** The structural/frictional framing (AQR's leverage-constraint story, Jane Street's "get paid to bear risk constrained players can't / provide what forced flows demand") points hardest at **(a)** and **(b)**, because their mechanism is a *constraint on other players*, not a statistical regularity that arbitrage erases.

A note on the bar this must clear (from MEMORY/scouts): the historical ceiling was a **signal** ceiling (~0.5 Sharpe), not a cost ceiling, and graduation needs **regime-robustness across ≥2 distinct bears** and a positive **out-of-sample** showing — so I weight axis (3), prior-OOS-survival, heavily, and I flag crowding honestly.

---

## 2. The three hypotheses

Each is specified with: **mechanism** (why the edge exists — risk / behavioral / structural-frictional), **signal-construction sketch** (what you'd compute, *not* built), **free data source + 2008-depth**, **failure modes / what kills it**, and **why this over the others**. Scorecards in §3.

---

### H1 — Cross-asset CARRY / curve-roll harvest (bonds + commodities, the legs we DON'T trade)

**The claim.** Hold a static, slow tilt toward the assets with the **highest carry** (expected return if prices don't move) and away from the lowest, *within and across* asset classes we currently have zero exposure to as a carry bet: the **Treasury curve** (roll-down / term premium) and **commodity futures** (roll yield / backwardation-vs-contango). This is **not** directional and **not** trend — carry can be positive while price falls, and it is famously *negatively* correlated with momentum, which is exactly what makes it orthogonal to our book.

**Mechanism (risk premium + structural/frictional — the strong combo).**
- *Bond carry / roll-down:* an upward-sloping curve pays you to hold longer duration and "roll down" the curve as bonds age toward shorter, lower-yielding points — compensation for **duration risk** and for bearing what liability-constrained / regulation-constrained players (banks, insurers) must shed. This is the maturity-transformation premium (the bank borrow-short-lend-long trade; *Carry (investment)* Wikipedia, fetched).
- *Commodity carry / roll yield:* in **backwardation** the futures curve is downward-sloping, so a long roll *earns* as the contract converges up to spot — Keynes/Hicks "normal backwardation": **hedgers (producers) pay speculators a premium to transfer price risk** (Wikipedia *normal backwardation*, fetched; "Facts and Fantasies about Commodity Futures," Gorton-Rouwenhorst 2006, *from memory*). This is a **forced-flow / risk-transfer** edge — Jane-Street-flavored: you get paid to take the side constrained hedgers won't.
- AQR's *Carry* paper (Koijen-Moskowitz-Pedersen-Vrugt, JFE 2018, **fetched**) is the unifying evidence: *"carry predicts returns both in the cross section and time series for … global equities, global bonds, currencies, commodities, U.S. Treasuries, credit and equity index options,"* with **unconditionally low correlations across asset classes** but a shared bad state (carry does poorly together **in global recessions**). That last point is the risk-premium fingerprint — you're paid because it crashes in recessions — and also the **failure mode to respect**.

**Signal-construction sketch (what you'd compute — NOT built):**
- *Bond leg:* proxy curve carry with the **slope** you already pull from FRED (e.g. `T10Y2Y`, `T10Y3M`) and/or the level/roll of a long-duration ETF. Concretely: a long-`TLT`/`IEF` tilt **scaled by realized curve steepness** (steeper ⇒ more roll-down ⇒ bigger tilt; inverted ⇒ flat/zero). Vol-target the leg so it's risk-comparable.
- *Commodity leg:* the cleanest free roll-yield proxy without a futures-data vendor is the **ratio of a front-month-tracking ETF to a deferred/optimized-roll ETF** on the same commodity complex — e.g. `USO` (front-month crude) vs a longer-dated/optimized-roll crude ETF, or a broad `DBC`/`GSG` (optimized roll) vs a naive front-roll basket. Backwardation shows up as the optimized-roll product **outperforming** the front-roll product over time; that spread *is* the carry signal. Go long the complex when the curve carry is positive (backwardated), flat/short-tilt when deeply contangoed.
- *Combine:* equal-risk-weight a small bond-carry sleeve + commodity-carry sleeve, rebalanced monthly, vol-targeted to a modest budget. This is a **diversifier sleeve**, not a SPY-beater on its own — judge it on **correlation to the live book** and **Sharpe of the standalone sleeve**, and on whether it *adds* to the allocator frontier.

**Free data + 2008 depth.** **Strong.** `TLT` (2002+) and `IEF` (2002+) and `GLD/DBC/USO` are **already cached** (`data_cache/yahoo/`), and `T10Y2Y`/`T10Y3M` are free keyed-FRED back to the 1970s — so the **bond-carry leg reaches well before 2008**. Commodity carry depth is the catch: `DBC` (2006+), `USO` (2006+), `GSG` (2006+) all just barely reach the GFC; a *clean* roll-yield needs a deferred-contract ETF whose inception you must check (some optimized-roll products are 2014+). **Honest caveat:** the *deepest, cleanest* commodity-carry signal lives in actual futures term-structure data (paid / harder), so the free-ETF version is a **proxy** — good enough for a feasibility read, not as pristine as the AQR construction.

**Failure modes / what kills it.**
1. **Recession co-crash (the headline risk, straight from the AQR abstract):** all carry legs dump together in global recessions — so this is **NOT a hedge**; it's a premium you harvest in calm and give back in crises. If the bench wanted a *diversifier that's also a crisis hedge*, carry is the wrong tool (that's trend's job — see H3).
2. **Commodity-carry proxy error:** ETF roll-cost/expense-ratio drag and tracking error can swamp the signal; if the front-vs-deferred spread is dominated by fund mechanics rather than curve shape, it's noise. Mandatory control: compare the carry sleeve to a **no-signal equal-weight hold of the same ETFs** (the lesson banked from the fundamentals-PIT close — the EW-of-same-universe control is non-negotiable).
3. **Crowding (moderate):** currency carry is heavily crowded and decayed post-2008 (and **FX carry is already CLOSED on this bench, OOS 0.39**) — but *commodity* and *bond* carry are **less arbitraged** and have a cleaner economic (hedging-pressure / duration) story. Still, post-publication 2018 means some decay is plausible; demand OOS proof.
4. **Cost:** monthly rebalance on liquid ETFs is cheap, so cost is unlikely to be the killer (unlike overnight-drift). The killer is **signal**, as always.

**Why this over the others.** It's the **most orthogonal** of the three — carry is *definitionally* uncorrelated-to-momentum and non-directional, and it lives in **asset classes (bonds-as-carry, commodities) we have literally never traded as a return source.** It directly fills the §1 gap. It's also the purest *structural/frictional* story (hedging pressure, duration constraint) the task asked me to weight. **The distinction from closed lanes:** this is **carry, not credit-as-equity-timer** (CREDIT_STRESS closed) — we're harvesting a term/roll premium *as a standalone return*, not using a spread to time SPY exposure; and it is **commodity/bond carry, not FX/crypto carry** (both closed), which have different (hedging-pressure vs interest-rate-differential) mechanisms and are far less crowded.

---

### H2 — Betting-Against-Beta (BAB) / low-beta tilt *inside* our existing equity universe (leverage-constraint friction)

**The claim.** Within the broad US single-name universe we **already have cached** (4,500+ tickers in `data_cache/yahoo/`), build a **beta-neutral long-low-beta / short-high-beta** portfolio (or, leverage-constrained, a long-only **overweight-low-beta / underweight-high-beta** tilt). Low-beta stocks have historically delivered **higher risk-adjusted returns** than high-beta stocks — the flattest-security-market-line anomaly.

**Mechanism (structural-frictional — the textbook constrained-player story).** This is **the** AQR leverage-constraint paper and the single cleanest "structural edge from constrained players" in the canon. From the **fetched** *Betting Against Beta* abstract (Frazzini-Pedersen, JFE 2014): *"many investors — individuals, pension funds, mutual funds — are constrained in the leverage they can take, and therefore overweight risky securities instead. This … suggests high-beta assets require lower risk-adjusted returns than low-beta assets. The security market line for U.S. stocks is too flat relative to the CAPM."* The premium exists because **constrained investors who want more return can't lever, so they buy high-beta stocks instead, bidding their prices up and expected returns down** — and the arbitrageurs who *could* lever the low-beta side are themselves funding-constrained (and get margin-called precisely when the trade goes against them). It's reinforced by the **low-volatility anomaly** (Wikipedia, fetched): low-vol/low-beta securities earn higher returns "in most markets studied," documented in equities *and corporate bonds*, contradicting CAPM. The mechanism is **risk-bearing-capacity / funding friction**, not a behavioral quirk that arbitrage erases — which is why it has *some* OOS legs (axis 3).

**Signal-construction sketch (what you'd compute — NOT built):**
- For each name, estimate **rolling beta to SPY** (e.g. 252-day, shrunk toward 1 à la Frazzini-Pedersen's "shrinkage beta" — *from memory of the paper's method*) using only data ≤ as-of date.
- **Rank** the universe by beta each month; form **low-beta** and **high-beta** baskets.
- *Beta-neutral version (the real BAB):* go **long the low-beta basket levered up to beta 1**, **short the high-beta basket de-levered to beta 1**, so the portfolio is ~market-neutral and earns the *alpha* of the flat SML. *Long-only/leverage-respecting version* (closer to what a small paper account does): **overweight low-beta, underweight/exclude high-beta**, vol-targeted — captures part of the premium without shorting or leverage.
- **Mandatory control (banked lesson):** compare to the **no-signal equal-weight hold of the same universe** — the BAB tilt must beat its own EW universe, not just SPY, or it's another survivorship mirage.

**Free data + 2008 depth.** **Strong-to-excellent.** It needs **only price data we already have** — betas are computed from the cached Yahoo OHLCV. SPY/single-names reach 1993+/well before 2008 for the survivors; the **honest depth problem is survivorship** (the cached universe is today's names — same trap that killed fundamentals-PIT). **This is the single biggest threat to H2's validity** and must be confronted: a defensible version restricts to names that *existed and were liquid* at each point-in-time, or at minimum reports the EW-universe control so the survivorship lift is subtracted out. No paid data needed; the cost is **point-in-time-universe discipline**, not data acquisition.

**Failure modes / what kills it.**
1. **Survivorship bias (the FUNDAMENTALS-PIT lesson, again):** ranking *today's* survivors by beta can manufacture a fake premium. The L/S **spread** on a clean universe is the only honest test; the long-only book on a survivor universe is not. If the spread isn't positive OOS, it's dead — exactly how the fundamentals composite died today.
2. **Crowding / decay (real, axis-3 concern):** BAB and "min-vol" are now **enormous** crowded factor products (USMV/SPLV ETFs hold tens of billions). Post-2014-publication, several studies argue the premium has compressed, and low-vol got expensive (a valuation headwind). It had a famous **drawdown in 2009's junk-rally and again in 2020-21 growth/meme melt-ups**, where high-beta trash ripped. So this is the **most-crowded** of the three — I flag it explicitly: the edge is *real in mechanism* but *partially arbitraged in practice*.
3. **Overlap with our live book (orthogonality risk):** a long-low-beta tilt is **still long US equity** and still partly directional — it is *more* correlated to our book than H1 or the non-equity legs of H3. The beta-*neutral* L/S version is the orthogonal one; the long-only tilt is only semi-orthogonal.
4. **Shorting/financing frictions:** the true BAB needs shorting high-beta names + leverage on low-beta — operationally heavier and exactly the friction the premium compensates; a small paper account may only capture the diluted long-only slice.

**Why this over the others.** It's the **canonical structural edge** (constrained players, flattest SML) with the **lowest data lift** (price-only, fully cached) and a **clean point-in-time test** the bench knows how to run. **The distinction from closed lanes:** we closed **price cross-sectional *momentum*** — BAB is a **different cross-sectional sort (beta/vol, not past return)** with a **different mechanism (leverage constraint, not under-reaction)** and is **negatively correlated to momentum**; and it differs from the closed **vol-regime *timing*** (Moreira-Muir) because that *times aggregate exposure* whereas BAB is a *cross-sectional sort* of which names to hold — orthogonal construction.

---

### H3 — Time-Series Momentum (trend) on the cross-asset complex we DON'T trade (bonds, commodities, FX, vol)

**The claim.** Run **classic 12-month time-series momentum** (long if own past 12-mo return > 0, short/flat if < 0, vol-scaled) on a **diversified futures-like complex** — Treasuries, commodities, FX, and possibly credit — i.e. the **managed-futures / CTA trend program** that AQR and Man AHL built their firms on. We run *equity* trend (TQQQ sleeve) and *cross-asset price momentum* (sector rotation across SPY/QQQ/GLD/TLT); we do **NOT** run a broad **multi-asset trend sleeve dominated by the non-equity legs**, and crucially we don't harvest the thing trend is famous for: **positive crisis convexity** ("trend is long volatility / a crisis hedge").

**Mechanism (behavioral under/over-reaction + risk premium, with a structural twist).** From the **fetched** *Time Series Momentum* abstract (Moskowitz-Ooi-Pedersen, JFE 2012): *"strong positive predictability from a security's own past returns for 58 diverse futures … country equity indices, currencies, commodities and sovereign bonds over 25+ years … 12-month TSMOM profits are positive … for every asset contract we examine,"* driven by **positive auto-covariance** between next-month and lagged-1-year returns. The economic story is **initial under-reaction then delayed over-reaction** to news (behavioral), plus **risk-transfer from hedgers to speculators** in futures (structural, same hedging-pressure root as commodity carry), plus a **slow diffusion of information / capital**. The structural payoff that matters for *us*: trend has **historically made money in extended equity bear markets** (sustained down-trends across assets) — the convexity our long-biased book entirely lacks. (Man AHL's "value of trend in crises" work documents this; I could **not** fetch it — Man URL 404'd — so I cite it *from memory* as the well-known CTA-crisis-alpha result, not a freshly-verified number.)

**Signal-construction sketch (what you'd compute — NOT built):**
- Universe of **liquid, deeply-historical ETFs** (free, cached or trivially fetchable): `TLT`/`IEF` (rates), `GLD` (gold), `DBC`/`USO`/`GSG` (commodities), `UUP`/`FXE` (FX), optionally `HYG`/`LQD` (credit). All except the FX/SLV-class are already in `data_cache/yahoo/`.
- For each, compute **12-month (or blended 1/3/12-mo) own-return sign**, take **long if >0, short/flat if <0** (long-only-if-no-shorting: long-or-cash), **scale each position by inverse realized vol** so each contributes equal risk, cap gross leverage.
- **Equal-risk-weight** across the complex, rebalance monthly. Critically, **down-weight or exclude the equity leg** so the sleeve is dominated by the **non-equity** trends we don't already own — that's what makes it additive to the live book rather than redundant with the TQQQ sleeve.
- Evaluate on **standalone Sharpe**, **correlation to live book** (target ≤0.3), and **crisis-window return** (2008/2020/2022) — the convexity is the whole point.

**Free data + 2008 depth.** **Strong, with the same ETF-proxy asterisk as H1.** Bond/gold/broad-commodity ETFs reach 2002–2006 (so they span 2008); FX ETFs (`UUP` 2007+) just reach it. **The honest caveat:** the *real* TSMOM is on **futures** (continuous, leverage-native, no expense drag); the **ETF version is a proxy** that (a) can't easily short some legs, (b) eats expense ratios, (c) has shorter history than the underlying futures (which go back to the 1980s–90s). So we can build a *feasible* version that spans 2008, but it is a **diluted, long-biased-ish proxy** of the canonical CTA trend — and a long-only ETF version may **lose much of the crisis convexity** (you can't get long-vol from cash; you'd need to short or hold inverse ETFs, which decay).

**Failure modes / what kills it.**
1. **Redundancy with our existing trend (the orthogonality trap):** TSMOM *is trend*, and we **already run trend** (TQQQ sleeve) and **already run cross-asset price momentum** (sector rotation hits GLD/TLT). If the non-equity legs are dominated by the same risk-on/off swings, this collapses into "more of what we have." This is the **single biggest reason H3 ranks below H1/H2 on orthogonality** — it's the *least* novel mechanism on this bench even though the *instruments* differ.
2. **Post-publication decay (real, axis-3):** managed-futures/CTA trend had a famously **weak 2011–2019 stretch** (low vol, central-bank suppression, whipsaws) after the 2008 glory run — widely discussed as "trend is crowded / dead" before it roared back in 2022. So the premium is **regime-dependent and has visibly decayed in calm-trending-up regimes**, which is most of the last 15 years. Demand evidence it adds across the *full* cycle, not just 2008/2022.
3. **ETF-proxy dilution kills the convexity:** the crisis-hedge property comes from being able to **go short** falling assets; a long-only-or-cash ETF version can't, so it may capture the carry-ish trend in up-markets but **lose the down-market convexity that is its entire reason to exist**. Inverse ETFs decay and aren't a clean fix.
4. **Cost/turnover:** trend flips positions; monthly rebalance on liquid ETFs is tolerable, but faster signals churn — keep it slow (12-mo) to stay cheap.

**Why this over the others.** It has the **strongest and longest OOS track record of the three** (TSMOM is positive on *every one of 58 contracts* over 25+ years in the paper, and CTAs have run it live for decades — axis 3 is its best axis) and it's the **only one that adds crisis convexity** to a long-biased book. **The distinction from closed/live lanes:** we closed *cross-sectional* momentum and we run *equity* trend — this is **time-series (absolute) trend on a NON-equity-dominated multi-asset complex**, a different signal (own-return sign, not relative rank) on different instruments (bonds/commodities/FX), explicitly weighted *away* from the equity leg we already own. It is adjacent to our live trend sleeve, so it earns its place *only* if the non-equity legs prove ≤0.3-correlated to the live book — which is an empirical question, not a given.

---

## 3. Scorecards (1–5; 5 = best for the bench)

Axes: **(1) Orthogonality** to the live book (higher = more uncorrelated/different-mechanism). **(2) Free-data feasibility** (higher = cleaner free data reaching 2008). **(3) Prior OOS-survival** (higher = held up post-publication / across markets; lower = known-crowded/decayed).

| Hypothesis | (1) Orthogonality | (2) Free-data feasibility | (3) Prior OOS-survival | Mechanism type | Net read |
|---|---|---|---|---|---|
| **H1 — Cross-asset carry (bonds + commodities)** | **5** — non-directional, anti-correlated to momentum, in asset classes we never trade as carry | **3.5** — bond-carry leg excellent (TLT/IEF/FRED, pre-2008); commodity-carry leg is an ETF *proxy*, barely reaches 2008, roll-yield needs care | **3.5** — commodity/bond carry less crowded than FX; AQR 2018 broad evidence; but post-pub decay + recession co-crash | risk premium **+ structural/frictional (hedging pressure, duration)** | Most orthogonal, cleanest *structural* story, moderate data asterisk |
| **H2 — BAB / low-beta intra-equity** | **3** — beta-neutral L/S is orthogonal, but it's still US-equity; long-only tilt is only semi-orthogonal | **4.5** — price-only, fully cached; cost = point-in-time-universe discipline, no paid data | **3** — real mechanism (leverage constraint) but **heavily crowded** (USMV/SPLV), compressed post-2014, junk-rally drawdowns | **structural/frictional** (leverage/funding constraint) — the textbook constrained-player edge | Lowest data lift + cleanest mechanism, but most-crowded + most-equity-correlated |
| **H3 — TSMOM on non-equity complex** | **2.5** — *trend*, the family we already run; only the instruments differ | **3.5** — same ETF-proxy asterisk as H1; long-only version loses convexity | **4** — strongest/longest live track record (CTAs, 58 contracts), but **visible 2011–2019 decay** | behavioral (under/over-reaction) + risk premium + hedging-pressure | Best OOS pedigree + only crisis-convexity adder, but least novel here |

---

## 4. Final ranking + top pick

**Ranked for *this bench, right now*:**

1. **🥇 H1 — Cross-asset carry (bonds + commodities).**
2. **🥈 H2 — BAB / low-beta intra-equity.**
3. **🥉 H3 — TSMOM on the non-equity complex.**

**Top pick: H1 (cross-asset carry), specifically the bond-curve-carry + commodity-roll-yield sleeve.**

**Rationale.** The bench's gap (§1) is *non-directional, non-trend, cross-asset risk-premium/friction* — and carry is the **only** one of the three that is *definitionally* non-directional and *negatively* correlated to the momentum/trend that dominates our live book. That makes it the **highest expected orthogonality contribution to the allocator**, which is the actual objective (a new sleeve earns its place by being uncorrelated, not by beating SPY solo). H2 is mechanistically beautiful but (a) **most crowded** of the three and (b) **still long US equity**, so its marginal orthogonality is lower; H3 is the **least novel** here because we already run trend — it's a convexity *complement* worth building eventually, but it doesn't fill the orthogonality gap the way carry does.

**The one honest knock on the top pick (stated plainly):** carry's risk is that **it co-crashes in recessions** (AQR's own finding) — so H1 is a *premium-harvesting diversifier*, **not a crisis hedge**. If what the allocator most needs is downside convexity, H3 (trend) is the better complement and H1 is the better *return-diversifier*. I'm picking H1 because the bench's stated gap is **orthogonal return source**, not **more downside protection** (we already get haven-tilt from sector rotation), and carry is the orthogonal-return king. If Cyrus/main says "actually we want crisis convexity," flip the top pick to **H3**.

**Also flagged for the go/no-go:** the **mandatory EW-of-same-universe control** (banked from today's fundamentals-PIT close) applies to **all three** — none of these is allowed to claim an edge until it beats a no-signal hold of its own instruments, OOS, net of cost. That single test is what would have saved the fundamentals lane a week, and it's the fastest way to kill any of these cheaply.

---

## 5. "What I'd build first if greenlit" — one-paragraph sketches (NOT built, just sketched)

### Top pick — H1 (cross-asset carry)
Start with the **bond-curve-carry leg alone** (it's the cleanest free-data piece): a self-contained candidate module (mirroring the `strategies_candidates/credit_stress/` pattern, protected `runner/` untouched) that takes the already-cached `TLT`/`IEF` series + free keyed-FRED `T10Y2Y`/`T10Y3M`, computes a **monthly duration tilt scaled by curve steepness** (steeper ⇒ larger long-duration tilt; inverted ⇒ flat), vol-targets the leg to a modest budget, applies a 1-day signal lag + monotonic cost grid, and is evaluated **first against its own no-signal EW hold of TLT/IEF** and **then for correlation to the live book + allocator-frontier lift** across 2008/2020/2022 walk-forward windows. *Only if* the bond leg shows a positive, OOS-stable, low-correlation contribution do you add the **commodity-roll-yield leg** (front-vs-optimized-roll ETF spread on `DBC`/`USO`/`GSG`), which carries the proxy-error asterisk and should be gated behind the bond-leg result. Decision artifact: a `CARRY_SLEEVE_*.md` verdict reporting standalone Sharpe, corr-to-book, EW-control delta, and frontier impact — go/no-go on *adds orthogonal return to the allocator*, not on *beats SPY solo*.

### Runner-up — H2 (BAB)
If the bench prefers the lowest-data-lift path, build the **point-in-time-universe BAB test** first: compute shrinkage betas (≤ as-of date, 252-day) on the cached single-name universe, form low/high-beta baskets monthly, and — critically — test the **beta-neutral long/short *spread*** (not the long-only book) **against the EW-of-same-universe control on a survivorship-aware universe**. The entire go/no-go hinges on whether the L/S spread is **positive and OOS-stable on a clean universe** (the exact test that killed fundamentals-PIT); if it's only the long-only-survivor book that "works," it's a mirage and you close it the same day. Cheapest possible kill-test, zero new data — which is its own argument for running it as a fast parallel probe even while H1 builds.

---

## 6. TL;DR for the go/no-go

- **H1 — cross-asset carry (bonds+commodities):** orthogonality **5** / feasibility **3.5** / OOS **3.5**. Non-directional risk-premium+hedging-pressure harvest in asset classes we never trade as carry. Best free source: **cached `TLT`/`IEF` + free-FRED curve slope** (bond leg, pre-2008 depth). **TOP PICK** — fills the orthogonal-*return* gap; caveat: co-crashes in recessions (diversifier, not hedge). Differs from CLOSED credit-as-timer (this is carry-as-return) and CLOSED FX/crypto carry (different mechanism, less crowded).
- **H2 — BAB / low-beta intra-equity:** orthogonality **3** / feasibility **4.5** / OOS **3**. Leverage-constraint structural edge; **price-only, fully cached** (lowest data lift). Best free source: **already-cached single-name Yahoo OHLCV**. Knock: most crowded (USMV/SPLV), still long-equity. Differs from CLOSED xsec-momentum (beta sort ≠ return sort, anti-correlated to momentum).
- **H3 — TSMOM on non-equity complex:** orthogonality **2.5** / feasibility **3.5** / OOS **4**. Classic CTA trend on bonds/commodities/FX; **only one adding crisis convexity**, strongest OOS pedigree. Best free source: **cached `TLT`/`GLD`/`DBC`/`USO` (+`UUP`)**. Knock: it's *trend*, the family we already run — least novel here; flip to this as TOP PICK only if the allocator's priority is downside convexity rather than orthogonal return.

**Single best pick: H1 (cross-asset carry), bond-curve-carry leg first.** Single best free data source for it: **the already-cached `TLT`/`IEF` Yahoo series + free keyed-FRED curve-slope (`T10Y2Y`/`T10Y3M`), which reach well before 2008.**

*Reading/framing only. No backtest, no code, no data fetch beyond paper/abstract reads, no touches to `runner/`, `strategies*`, cron, `*.db`, broker/clock/allocator. The only artifact created is this report.*
