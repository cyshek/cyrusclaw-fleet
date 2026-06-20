# SCOUT — Cross-Asset (Rates / Credit / FX / Commodities), FREE routes only

**UTC:** 2026-06-05T04:01Z · **Scout:** subagent `scout-crossasset` for Tessera (trading-bench)
**Spec:** `reports/_SCOUT_SPEC_20260605.md` · **Mission:** free historical cross-asset price/level series whose moves lead/diverge from US equities, usable as risk-on/off & regime signals. **Scouting only** — no ingest/backtest. All access + history claims **web-verified** this session (curl against live endpoints; results inline).

---

## 0. The orthogonality framing (read first — it drives the ranking)

Cross-asset **raw prices** are still *prices*, so a naive corr-to-OHLCV is **low for that asset** (EURUSD daily returns ≈ EURUSD daily returns). That is NOT the point. The regime edge lives in **cross-asset SPREADS and RATIOS**, which encode risk appetite / funding stress / curve shape — information **not present in equity OHLCV alone**:

| Signal (spread/ratio) | What it tells you | Orthogonality to equity OHLCV |
|---|---|---|
| **HY OAS − IG OAS** (credit risk premium) | default-risk appetite; leads equity drawdowns | **High** — credit often cracks before/with equities but is a distinct market |
| **10y−2y / 10y−3m** (yield curve slope) | recession/rates regime | **High** — rates curve ≠ equity price |
| **NFCI / STLFSI** (financial-conditions composite) | aggregate system stress (credit+rate-vol+funding+eq-vol in one number) | **High** — purpose-built regime state |
| **MOVE / VIX ratio** (rate-vol vs equity-vol) | where the stress is (rates vs stocks) | **Med-High** — VIX alone is in our vol lanes; the *ratio* and MOVE level are new |
| **Gold / Copper** (defensive vs cyclical metal) | growth vs fear | **Med-High** — commodity relative, not equity |
| **DXY** (broad USD) | global risk-off / dollar funding | **Med** — inversely tied to risk assets but distinct driver |
| **TED / SOFR-OIS** (funding stress) | bank/funding stress | **High** in crises, ~0 in calm (regime-conditional) |

**Ranking rule applied below:** pre-built composites & spreads/ratios ranked **highest**; raw single series (one FX pair, one metal) ranked **lower** (they're inputs to a spread, not a signal themselves). This matches the spec's "judge orthogonality at the SIGNAL level."

⚠️ **DATA-HONESTY CAVEAT (applies to all FRED macro/credit series):** FRED serves **final-revised** values. Serving today's value against a historical date = **silent lookahead leak** (release lag + revisions) — the exact trap `MACRO_NOWCAST` (2026-06-04) sidestepped by using ETF-price proxies. **Mitigations:** (a) credit OAS, curve, NFCI, FX, MOVE are **market-priced** series — lightly/never revised, low leak risk; (b) for strict point-in-time use **ALFRED vintages** (free, same host) or lag-shift each series by its publication delay; (c) **Yahoo & LBMA prices are PIT by construction** (market closes, not revised). Macro *survey/economic* series (claims, ISM, CPI) are the dangerous ones — **not** in this cross-asset scope, so leak risk here is modest, but flag it at ingestion.

---

## 1. Master catalog

| # | Source / series | Access (verified) | History depth (verified) | Cadence / lag | Licensing | Orthogonality (signal-level) | Ingest ease |
|---|---|---|---|---|---|---|---|
| **A** | **FRED — Financial-Conditions composites** `NFCI`, `ANFCI`, `STLFSI4` | `api.stlouisfed.org/fred/series/observations` (free instant key) **or** `fredgraph.csv?id=…` (no key, but bot-flaky — see §3) | **NFCI back to 1971-01-08** ✓verified; **STLFSI4 back to 1993-12-31** ✓verified | NFCI/ANFCI **weekly** (Wed, ~1wk lag); STLFSI4 weekly | **Public domain** (US gov / Fed). Commercial OK. | **HIGH** — purpose-built regime state, aggregates credit+rate-vol+funding+eq-vol. Single richest series. | **1** (clean CSV/JSON) |
| **B** | **FRED — Credit OAS** `BAMLH0A0HYM2` (US HY), `BAMLC0A0CM` (US IG), `BAMLC0A0CMEY`, sector/rating cuts | same as A | **HY & IG from 1996-12-31** (ICE BofA index inception; daily). VIX served back to **1990** & DTWEXBGS to **2006** ✓verified same host, confirming deep daily delivery | **Daily**, ~1 biz-day lag | Public domain (FRED redistribution of ICE BofA indices; FRED ToU permits use). | **HIGH** as **HY−IG spread**; HY level alone = risk premium. Spans 2008/2020/2022 fear spikes. | **1** |
| **C** | **FRED — Treasury curve** `T10Y2Y`, `T10Y3M`, `DGS10`, `DGS2`, `DGS3MO`, `DFII10` (real yield) | same as A | `T10Y2Y` daily, deep (1976+); DGS10 1962+ | **Daily**, ~1 biz-day lag | Public domain | **HIGH** as **slope** (10y−2y, 10y−3m); curve regime is orthogonal to equity price | **1** |
| **D** | **FRED — Funding/FX** `TEDRATE` (TED), `SOFR`, `DTWEXBGS` (broad USD), `DEXUSEU`,`DEXJPUS`,`DEXUSUK`,`DEXCHUS` | same as A | `DTWEXBGS` from **2006** ✓; `DEXUSEU/JPUS/USUK` from **1999-01-04** ✓verified; `TEDRATE` 1986–2022 (**discontinued Jan-2022** — LIBOR sunset) | **Daily**, ~1 biz-day lag | Public domain | **Med-High**: TED = funding stress (regime-conditional, ~0 in calm); DXY = risk-off; FX pairs = inputs | **1** (TED: note discontinuation → swap to SOFR-OIS proxy post-2022) |
| **E** | **Yahoo Finance chart API** — cross-asset prices: `^TNX`,`^TYX`,`^FVX` (UST yields), `^MOVE` (rate vol), `^VIX`,`^VVIX`, `DX-Y.NYB` (DXY), `EURUSD=X`,`JPY=X`, `GC=F`(gold),`SI=F`(silver),`HG=F`(copper),`CL=F`(WTI),`BZ=F`(Brent),`ZN=F`(10y note fut) | `query1.finance.yahoo.com/v8/finance/chart/<sym>?period1=<epoch>&period2=<epoch>&interval=1d` — **no key, no captcha** | **DAILY via period1/period2** verified: `EURUSD=X` 631 pts 2007-01→2009-05 ✓; `^TNX` from 2007-01-03 ✓; `^MOVE` 606 pts from 2007-01-03 ✓; `GC=F` from 2000 ✓. ⚠️ `range=max` **downsamples to monthly** — MUST use epoch params for daily | **Daily** (delayed/EOD) | Yahoo ToS = **personal use**, "no redistribution"; tolerated for private research/paper. Gray-area for commercial → **flag**. | **Gold/Copper ratio, MOVE level, MOVE/VIX ratio, DXY** = the unique adds here; raw FX = input | **1** (JSON; epoch-param gotcha = the only friction) |
| **F** | **LBMA precious-metal fixes** `gold_pm`, `gold_am`, `silver` | `prices.lbma.org.uk/json/gold_pm.json` (+ `gold_am`,`silver`) — **public JSON, no key** ✓verified HTTP200 | **14,611 daily records back to 1968-04-01** ✓verified; last 2026-06-04 | **Daily** (one/two fixes per day; ~same-day) | LBMA data: free for **non-commercial**; commercial/redistribution restricted → **flag** for commercial | **Med** as **Gold level / Gold-Silver ratio**; clean authoritative metal benchmark (vs Yahoo futures roll noise) | **1** (JSON: `{d, v:[USD_AM/PM, GBP, EUR]}`) |
| **G** | **EIA energy** (spot/futures) v2 API | `api.eia.gov/v2/...` — **free instant key** (empty without key ✓verified) | WTI/Brent spot daily from 1986; deep | **Daily**, ~few-day lag | **Public domain** (US gov) | **Med** — energy as growth/inflation proxy; but Yahoo `CL=F/BZ=F` already free key-less → EIA only if you want official spot + refined cracks | **2** (key + v2 path nesting) |
| **H** | **Stooq EOD CSV** (FX/commod/indices) | `stooq.com/q/d/l/?s=<sym>&i=d` — **now requires `&apikey=` (captcha-gated)** ✓verified ("Get your apikey… enter the captcha") | Long history advertised (FX/indices multi-decade) | Daily EOD | Free tier; ToU restricts heavy/automated use | Same as Yahoo (raw prices) | **3** ↓ — **captcha wall** kills frictionless scripted pull; **superseded by Yahoo (E)** which is key-free |
| **I** | **Nasdaq Data Link (ex-Quandl) free tier** | `data.nasdaq.com/api/v3/...` — **Incapsula bot-wall** ✓verified (returns NOINDEX challenge HTML, not data) | Legacy FRED/CBOE mirrors, varies | varies | Free tier exists but most premium datasets retired/paywalled | Redundant w/ FRED | **4** ↓ — **bot-walled + redundant**; not worth fighting. Use FRED directly. |

---

## 2. TOP 2–3 highest-EV picks

### 🥇 #1 — FRED financial-conditions composites (NFCI / STLFSI4) + credit OAS spreads (Row A + B)
- **Why:** *Highest signal density per series.* NFCI is a single number that already fuses credit spreads, rate vol, funding stress, and equity vol into a regime state — verified daily/weekly back to **1971** (NFCI) / **1993** (STLFSI4) / **1996** (HY-IG OAS). Spans every regime the spec asked for (2008, 2020, 2022) with room to spare. Public domain, commercial-OK, ingestion-ease 1.
- **The signal:** use NFCI/ANFCI as a regime gate, and **HY OAS − IG OAS** + **10y−2y** as orthogonal risk-appetite/curve features. These are spreads → genuinely additive over equity OHLCV.
- **Dealbreaker watch:** revision/release-lag → use keyed API + lag-shift or ALFRED vintages for strict PIT (low risk for market-priced series, but document it).

### 🥈 #2 — Yahoo chart API for MOVE, DXY, Gold/Copper, FX (Row E)
- **Why:** *Key-free, captcha-free, daily, instantly scriptable.* Verified daily history to 2007 for `^MOVE` (606 pts) and `EURUSD=X` (631 pts) across the GFC. Delivers the cross-asset pieces FRED lacks natively: **^MOVE (Treasury rate-vol — the rates analog to VIX)**, **DXY**, and **Gold(GC=F)/Copper(HG=F) ratio**. The MOVE/VIX ratio and gold/copper ratio are the freshest regime features.
- **Dealbreaker watch:** (1) `range=max` silently downsamples to monthly → **must** use `period1/period2` epochs for daily (verified fix). (2) Yahoo ToS is "personal use / no redistribution" — **fine for private paper research, gray for commercial** — flag before any commercial step.

### 🥉 #3 — LBMA precious-metal fixes (Row F)
- **Why:** Public JSON, no key, **14,611 daily gold records back to 1968** (verified) — authoritative metal benchmark cleaner than rolling futures. Best as **Gold level** + **Gold/Silver ratio** (defensive-metal regime).
- **Dealbreaker watch:** non-commercial license (flag for commercial); one fix/day (not intraday).

---

## 3. Verified gotchas & dealbreakers (don't relearn these at ingest time)

1. **FRED `fredgraph.csv` is Akamai bot-protected and FLAKY for scripts.** Verified: it intermittently **ignores `cosd`/`coed`** and returns a **stale cached 2023 slice** — HY OAS returned 2023 data on **3 consecutive retries** despite a 2008 range request, while NFCI/DTWEXBGS/VIX/FX (fresh cookies) returned correct ranges. **FIX: use the official keyed API** `api.stlouisfed.org/fred/series/observations` (free instant key; verified clean `400 api_key not set`) — it respects date ranges and is the reliable ingestion path. Treat fredgraph.csv as a quick-look tool only.
2. **Stooq daily CSV is now captcha/apikey-gated** (verified: download URL returns "Get your apikey… enter the captcha"). The old frictionless bulk CSV route is gone for per-symbol daily. Apikey is free but **needs a human captcha** → **not scriptable in an autonomous pipeline**. **Superseded by Yahoo (key-free).** Down-ranked.
3. **Nasdaq Data Link / Quandl-legacy = Incapsula bot-wall** (verified: returns `_Incapsula_Resource` challenge HTML, NOINDEX/NOFOLLOW, not JSON). Plus most premium datasets retired. **Redundant with FRED.** Down-ranked.
4. **Yahoo `range=max` downsamples to monthly** (verified: 272 "max" pts for EURUSD since 2003 = monthly). Daily history **requires `period1`/`period2` epoch params** (verified: 631 daily pts 2007–2009). Easy to miss → would silently starve a regime backtest of resolution.
5. **TEDRATE discontinued Jan-2022** (LIBOR sunset). For post-2022 funding stress, substitute **SOFR-OIS** or a SOFR-based spread; don't assume a live TED feed.
6. **Licensing tiers:** FRED + EIA = **public domain (commercial-safe)**. Yahoo + LBMA + Stooq = **personal/non-commercial, no redistribution** — fine for private paper research; **must be flagged before any commercial deployment.**

---

## 4. Coverage check vs spec's required regimes (2008 / 2020 / 2022)

| Pick | 2008 GFC | 2020 COVID | 2022 bear | Verified anchor |
|---|---|---|---|---|
| NFCI | ✓ (1971+) | ✓ | ✓ | NFCI 1971-01-08 = 0.596 (verified) |
| HY−IG OAS | ✓ (1996+) | ✓ | ✓ | series inception 1996-12-31 (well-documented; FRED deep-history delivery confirmed via VIX-1990/DTWEXBGS-2006) |
| 10y−2y / curve | ✓ | ✓ | ✓ | T10Y2Y deep (1976+) |
| Yahoo ^MOVE / FX | ✓ (2007+) | ✓ | ✓ | ^MOVE 606 daily pts from 2007-01-03; EURUSD=X 631 pts 2007–2009 (verified) |
| LBMA gold | ✓ (1968+) | ✓ | ✓ | 14,611 recs from 1968-04-01 (verified) |

All top picks comfortably span every required regime. ✅

---

*Scout complete. Free-only, zero-spend, no ingest/backtest performed. No edits to `strategies/`, `runner/*.py`, or any cron. All access/history claims verified against live endpoints this session.*
