# SCOUT SWEEP — Cross-Class Synthesis (FREE orthogonal data) — 2026-06-05

**Context:** trading-bench (Tessera). 11 price/vol-derived strategy lanes all hit a ~0.5 Sharpe **signal** ceiling (evidence: `OVERNIGHT_SYNTHESIS_20260604.md`). More OHLCV re-feeds are useless. This sweep hunts genuinely NEW, FREE, orthogonal input classes that could break that ceiling.

**Method:** 6 parallel scouts (positioning, alt-data, fundamentals, macro, options-IV, cross-asset), each live-verifying access/history/cadence/licensing via `curl`/`web_fetch` on 2026-06-05. Scouting only — no ingest, no backtest. Per-class catalogs: `reports/SCOUT_<class>_20260605.md`.

**Selection bar (from `_SCOUT_SPEC_20260605.md`):** orthogonality (corr <~0.3 to OHLCV) × history depth (ideally spans 2008/2020/2022 bears) × ingestion ease × licensing (paper + potentially commercial). A source starting 2021 is near-worthless for regime work.

---

## The decisive filter: 2008-regime coverage

The cleanest way to rank the entire sweep is **"does the free tier reach the 2008 GFC?"** — because that's the one bear regime most free sources *don't* cover, and regime-robustness across ≥2 distinct bears is a graduation criterion (MEMORY.md). This splits the candidates into a clear tier structure:

- **Tier 1 — spans 2008 + 2020 + 2022, free, deep, clean license, trivial-to-moderate ingest.** These are the real prizes.
- **Tier 2 — spans 2020 + 2022 but NOT 2008 (free tier starts ~2015–2019).** Useful for recent-regime work; blind to GFC. Acceptable as secondary features, not as the sole regime backbone.
- **Tier 3 — dealbreakers.** Licensing-walled, history-walled, or paywalled-on-free-tier.

---

## TIER 1 — green-light candidates (free, span all 3 bears)

Ranked by EV (orthogonality × history × ingestion × licensing):

| Rank | Source | Class | Signal (use the DERIVED feature, not the raw level) | History | Cadence / lag | Ingest | License |
|---|---|---|---|---|---|---|---|
| **1** | **FRED credit/conditions/curve** (keyed API) | macro / cross-asset | **HY−IG OAS spread**, **NFCI/ANFCI**, **T10Y2Y / T10Y3M slope** | OAS 1996, NFCI 1971, curve 1976 | daily (OAS/curve) / weekly (NFCI), ~1d–1wk | 1 | public domain ✅ |
| **2** | **CFTC COT** (TFF report) | positioning | leveraged-fund / asset-mgr **net positioning & changes** in index futures | **1986** | weekly, **3-day** Tue→Fri lag | 2 | public domain ✅ |
| **3** | **CBOE vol-index CSVs** (CDN, no key) | options-IV | **term-structure slope** (VIX9D/VIX/VIX3M/VIX6M contango↔backwardation), **SKEW**, **VVIX** | VIX/SKEW 1990, VVIX 2006 | daily EOD | 1 | free reference data ✅ |
| **4** | **GDELT 2.0 Events** | alt-data | global news **tone / Goldstein** aggregates (theme-level first, avoids ticker-mapping) | Events **1979** | 15-min (daily pre-2015) | 4 | free & open ✅ |
| **5** | **SEC EDGAR** (bulk FSDS + XBRL `frames`) | fundamentals | fundamental line-items; **cross-sectional ranking** via `frames`; PIT via `filed` dates | **2009** | quarterly | 2 | public domain ✅ |
| **6** | **Yahoo chart API** (epoch params) | cross-asset | **MOVE level**, **MOVE/VIX ratio**, **Gold/Copper ratio**, **DXY** | 2007 (verified ^MOVE, FX) | daily EOD | 1 | personal-use ⚠️ (paper-OK, flag commercial) |
| **7** | **FINRA daily short-volume** | positioning | per-name **short-volume ratio** (flow proxy) | ~2019 (**no 2008**) | daily, next-day | 1 | free reg data ✅ |

**Notes on the Tier-1 set:**
- **#1 (FRED spreads) is the consensus #1 across TWO independent scouts** (macro AND cross-asset both crowned it). NFCI alone fuses credit + rate-vol + funding + equity-vol into one regime number, daily-to-weekly, back to 1971, public domain. Highest signal density per series in the whole sweep. **This is where I'd start.**
- **#2 (COT) is the best pure positioning signal** — 1986 history, public domain, genuinely orthogonal (futures positioning ≠ price), maps to our SPY/QQQ universe via index futures (TFF report). The 3-day lag is small and *honest* (signal as-of Tue, tradeable Fri+).
- **#3 (CBOE indices) rescues the options class** — no free *full surface* reaches 2008, but the processed indices do, and the orthogonal alpha is in SKEW/VVIX/term-slope anyway, not the raw VIX level.
- **#6 (Yahoo) is the only "easy" route to ^MOVE** (Treasury rate-vol, the rates analog to VIX) — but personal-use license = paper-only-safe, flag before any commercial step.
- **#7 (FINRA short-vol) is Tier-1 on every axis EXCEPT it starts ~2019** → demoted within-tier; great for 2020/2022, blind to GFC.

---

## TIER 2 — useful but 2008-blind (free tier starts ~2015–2019)

| Source | Class | Why secondary | Start |
|---|---|---|---|
| **DoltHub `post-no-preference/options`** | options-IV | real per-strike IV surface + full Greeks, free SQL — but **2019+** (the free OptionMetrics analogue, GFC-blind) | 2019-02 |
| **Wikipedia Pageviews** | alt-data | trivial ingest (1/5), CC0, clean attention proxy — but **2015-07 floor** | 2015-07 |
| **GDELT 2.0 GKG** (rich tone/GCAM/themes) | alt-data | richer than Events but **2015+**; use Events for 2008 depth | 2015-02 |
| **SEC Form 4** (insider txns) | positioning | near-real-time insider buy/sell, 2003+ (so *does* span 2008) but ingest=3 (CIK/XML/throttle) — borderline T1/T2 | 2003 |
| **FRED freight/transport** (Cass, truck tonnage) | alt-data | physical-economy proxy, deep history, public domain — but **monthly** = slow regime context, not a trigger | 1990s |

---

## TIER 3 — dealbreakers (do not pursue at $0)

**Licensing-walled:**
- **NAAIM Exposure Index** — "express permission required for commercial purposes" (verified on page). Free to *view* only. ❌
- **Pushshift / Reddit** — ToU now mod-only, explicit no-commercial / no-redistribution / no-derivatives (verified). Reddit historical sentiment is **closed** for trading research. ❌

**History-walled (free tier = no usable backtest history):**
- **StockTwits free API** — works live but ~30 most-recent msgs only, no archive. ❌ for regime backtest.
- **Yahoo / yfinance OPTIONS chains** — live snapshot only, **zero history**. ❌ (note: Yahoo *price* chart API is fine — that's Tier 1 #6; only the options endpoint is historyless.)
- **Estimate-REVISION history** (the highest-EV fundamental signal: revision momentum / PEAD) — **paywalled on EVERY free tier** (Finnhub/AV/FMP/Sharadar). This is the sweep's single biggest *funded-upgrade* candidate.

**Paywalled (gold-standard, noted as upgrade paths only):**
- **OptionMetrics IvyDB** / **ORATS** — full IV surface to 1996/2007. The dream depth, but paid. DoltHub (2019+) is the closest free proxy.
- **Sharadar SF1** — best-in-class point-in-time fundamentals (1998+), but premium; free SF0 = tiny ticker sample.

**Access-walled (free but bot-blocked from this VM's datacenter IP — use the alternative):**
- **FRED `fredgraph.csv`** — Akamai bot-wall, *silently serves stale 2023 data* on retries (verified). **Use the keyed `api.stlouisfed.org` JSON API instead** (free instant key, respects date ranges). This one is important — the CSV route would have silently corrupted a backtest.
- **Stooq** (captcha/apikey-gated now), **Nasdaq Data Link** (Incapsula bot-wall) — both superseded by FRED/Yahoo.

---

## Correctness traps to bake in BEFORE any ingest (cross-class)

1. **Look-ahead via revisions (the big one).** FRED serves *final-revised* values. Backtesting macro/economic series on final values against historical dates = silent lookahead. **Mitigation:** market-priced series (OAS, curve, NFCI, FX, MOVE, VIX) are lightly/never revised → safe; for revised economic series (CPI, payrolls, GDP) use **ALFRED point-in-time vintages** (free, same host) or lag-shift by publication delay. Daily market series are revision-free.
2. **Positioning data is inherently lagged.** COT 3-day, short-interest ~9-day, 13F 45-day. Align signal to its *tradeable* timestamp, not its as-of timestamp. The two that survive this best: COT (3d) and FINRA daily short-vol (next-day).
3. **SEC EDGAR tag fragmentation.** A clean fundamental series requires mapping a *set* of XBRL concept tags per company across time (e.g. Apple's revenue tag changed post-ASC-606). The ingestion cost is tag/entity resolution, NOT download. Also: pin to the **post-Dec-2024 reprocessed FSDS vintage** (the dataset definition changed — mixing vintages = methodology break).
4. **Orthogonality lives in the DERIVED feature, not the raw level.** Cross-asset raw prices ≈ prices (low solo orthogonality). The regime edge is in **spreads/ratios** (HY−IG, 10y−2y, MOVE/VIX, gold/copper). Same for options: VIX *level* co-moves inversely with SPX (partly price-in-disguise); the orthogonal alpha is SKEW / VVIX / term-slope. **Build features from spreads/ratios/slopes, not levels.**
5. **EDGAR / SEC fair-access throttle.** Requires a descriptive `User-Agent: name contact@email`; keep ≤10 req/s. Bulk ZIPs avoid per-request limits → prefer for backfill.

---

## Recommendation — proposed build order (NOT yet executed; awaiting go-ahead)

If we pursue this (turning an orthogonal feature into a strategy that clears the 1.0 FP-continuous-Sharpe bar — GATE unchanged):

1. **FRED credit/conditions/curve first.** Highest signal density, public domain, ingest=1, spans everything, two scouts independently crowned it. Wire the keyed API (NOT fredgraph.csv). Build NFCI regime-gate + HY−IG / 10y−2y features.
2. **COT second.** Best pure positioning signal, 1986 depth, clean license. Budget for contract→symbol mapping + 3-day lag alignment.
3. **CBOE vol-index family third.** 15-min integration; adds SKEW/VVIX/term-slope fear signal across all bears.
4. Then evaluate **GDELT Events** (theme-level tone, sidestep ticker-mapping) and **EDGAR `frames`** (cross-sectional fundamental ranking) as the higher-ingestion-cost second wave.

**The one thing money would buy:** sell-side **consensus estimate-revision history** (PEAD / revision momentum) — paywalled everywhere free, genuinely high-EV, the single strongest *funded* candidate if we ever revisit a budget. (Consistent with the prior IV-surface spend note: both are "paid data that buys real orthogonal alpha," neither approved.)

**Honest caveat (SOUL.md):** finding orthogonal *data* is not finding *edge*. These sources clear the "new input class" bar, but whether any produces a strategy that beats 0.5→1.0 Sharpe net of costs is an empirical question only a backtest answers. This map says *where to dig*, not *that there's gold*. The 11-lane ceiling was a SIGNAL ceiling, not a cost ceiling — so new signal is the right thing to hunt, but the bar stays 1.0 and we widen data rather than lower it.

---

*Sweep complete. 6/6 catalogs verified on disk. Zero spend, zero ingest, zero backtest, no edits to `strategies/`, `runner/*.py`, or cron. All access/history claims live-verified 2026-06-05.*
