# SCOUT — Macro / Economic Indicators (FREE routes only)

**Scout class:** Macro/econ time series as regime/risk signals — rates, yield curve, inflation, employment, financial-conditions indices, recession probabilities, credit spreads.
**Date:** 2026-06-05 · **Author:** scout-macro (subagent of trading-bench/Tessera)
**Mandate:** FREE only, zero spend, scouting only (no ingest/backtest/bulk pull). Verify access + history via web.

---

## TL;DR — Top picks

1. **FRED API (credit spreads + financial-conditions + curve, DAILY/WEEKLY subset)** — the whole macro lane in one free key. Pick the *fast-cadence, low-lag* series (T10Y2Y curve daily 1976; ICE BofA HY OAS daily 1996; NFCI weekly 1971). These are the only macro series with both deep history AND tradeable cadence, and credit spreads / financial-conditions are genuinely orthogonal to equity OHLCV (they price the *bond/funding* market). **#1 by a mile.**
2. **US Treasury Daily Par Yield Curve (XML, no key, 1990→)** — same curve signal as FRED but keyless and arguably more point-in-time-honest (it IS the source). Good redundancy / no-signup fallback.
3. **ECB Data Portal API (keyless JSON)** — euro-area rates/FX/financial-conditions for a *second* macro bloc; mild diversification vs US-only signals. Lower priority than #1/#2.

**Hard down-rank:** GDP (BEA/World Bank, quarterly+2mo lag), most BLS CPI/employment (monthly, revised) — too laggy/low-cadence to move an hourly/daily strategy, even though history is deep. Useful only as slow regime context, not as a tradeable feature.

---

## Verification notes (what I actually tested from this VM, 2026-06-04/05)

- **FRED API host `api.stlouisfed.org`** → reachable, instant. Returns proper JSON error `"api_key is not set"` (HTTP 400, 0.18s) → **fully works with the free key**; the key is the only gate.
- **FRED web CSV scrape `fred.stlouisfed.org/graph/fredgraph.csv`** → **BLOCKED** from this datacenter IP (HTTP 000 / TLS reset, Akamai bot-mitigation), even with browser UA. ⇒ *Do NOT plan to scrape fredgraph.csv; use the keyed API.* (Same datacenter-IP bot-wall pattern noted in TOOLS.md for YouTube.)
- **T10Y2Y history** → confirmed **1976-06-01 → present** via search + ALFRED series page ("revisions … from 1976-06-01 to 2026-06-03"). Daily, ~12,000 obs.
- **US Treasury XML yield curve** → reachable keyless; empirically **1990 = 250 entries, 1989 = 0** ⇒ history starts **1990**. Daily.
- **World Bank API** → keyless JSON works (US GDP returned clean). Annual cadence.
- **ECB Data Portal `data-api.ecb.europa.eu`** → keyless JSON works (EUR/USD daily FX returned).
- **web_search was intermittently down** (provider misrouting to unconfigured SearXNG/kimi). FRED *series-level* earliest dates below that I could not re-pull live are marked **[pub-knowledge, re-verify on ingest]** — they are well-established but not freshly web-confirmed this session.

---

## Catalog

### A. FRED (Federal Reserve Bank of St. Louis) — the anchor source

**Access:** REST API `https://api.stlouisfed.org/fred/series/observations?series_id=…&api_key=…&file_type=json`. **Free API key** (instant email signup, no cost). **Rate limit ~120 req/min/key.** Bulk also via API pagination. ALFRED = point-in-time/vintage variant (`alfred.stlouisfed.org`, `realtime_start`/`realtime_end` params) → critical for avoiding look-ahead on revised series.
**Licensing:** FRED redistributes thousands of series; ToS says FRED's provision does **not override the underlying series owner's** copyright. **For the series that matter to us — US Treasury, Federal Reserve Board, Chicago Fed, BEA, BLS — the underlying data is US-government public domain → fine for private/paper/commercial use.** ICE BofA OAS series are © ICE Data Indices but FRED publishes them for free public use; flag for a license re-check before any *commercial redistribution* (internal signal use is fine).
**Ingestion ease:** **1** (clean JSON, one endpoint, date-filterable, well-documented). The single best macro ingestion target.

Series shortlist, ranked by **tradeable-cadence × orthogonality × history**:

| Series ID | What it is | Cadence / lag | Earliest | Orthogonality to equity OHLCV | Notes |
|---|---|---|---|---|---|
| **T10Y2Y** | 10y–2y curve slope | **Daily**, ~1-day lag | **1976-06-01** ✅verified | **High** — bond-market term-structure, classic recession lead | Spans '08/'20/'22. Best history+cadence combo. |
| **T10Y3M** | 10y–3m curve slope (Fed's preferred recession spread) | **Daily**, ~1-day | **1982** [re-verify] | High | Stronger recession-predictor than 2y per NY Fed. |
| **BAMLH0A0HYM2** | ICE BofA US **High-Yield OAS** (credit spread) | **Daily**, ~1-day | **1996-12-31** [re-verify] | **Very high** — funding/default risk, leads equity stress | Spans '08/'20/'22. © ICE (use OK, redistribution = check). Top orthogonality. |
| **BAMLC0A0CM** | ICE BofA US **IG Corp OAS** | **Daily**, ~1-day | **1996-12** [re-verify] | High | Investment-grade credit stress. Pairs w/ HY. |
| **NFCI** | Chicago Fed **National Financial Conditions Index** | **Weekly** (Wed), ~1-week | **1971** [re-verify] | **High** — broad funding/leverage/risk composite, not price | Purpose-built financial-stress gauge. Deep history. |
| **ANFCI** | Adjusted NFCI (stripped of macro cycle) | Weekly | 1971 [re-verify] | High | Cleaner "is stress unusual given growth" signal. |
| **STLFSI4** | St. Louis Fed Financial Stress Index | Weekly | 1993 [re-verify] | High | Alt financial-stress composite; corroborates NFCI. |
| **VIXCLS** | CBOE VIX close (FRED mirror) | Daily | 1990 | **Med** — derived from SPX options, partly equity-vol | Useful but NOT fully orthogonal (it's equity-implied vol). Down-weight vs credit/curve. |
| **DGS10 / DGS2 / DGS3MO** | Treasury constant-maturity yields | Daily | 1962 / 1976 / 1981 | Med-high | Raw rate levels; build custom spreads. |
| **SAHMREALTIME** | Sahm-rule recession indicator (real-time vintage) | **Monthly**, ~1-mo lag | **1959** [re-verify] | High (regime flag) | Monthly ⇒ slow; good regime label, weak as a fast feature. |
| **WALCL** | Fed balance sheet (total assets) | **Weekly** (Wed) | 2002 | Med-high — liquidity proxy | QE/QT regime. Misses '08 start but spans '20/'22. |
| **WRESBAL / RRPONTSYD** | Bank reserves / ON-RRP (liquidity plumbing) | Weekly / Daily | 2003 / 2013 | High (liquidity) | RRP daily & orthogonal but only post-2013. |
| **T5YIE / T10YIE** | Breakeven inflation (mkt-implied) | Daily | 2003 | Med-high | Inflation expectations, daily — tradeable. |
| **CPIAUCSL** | CPI headline | **Monthly**, **~2-wk lag, revised** | 1947 | Med | Deep but laggy/low-cadence ⇒ regime context only. |
| **UNRATE / PAYEMS** | Unemployment / nonfarm payrolls | **Monthly**, ~1-wk lag, revised | 1948 / 1939 | Med | Laggy; event-driven spikes only. |

> **Vintage/revision warning:** level/macro series (CPI, payrolls, GDP, even NFCI gets small revisions) are **revised after first print** → backtesting on the *final* FRED value = look-ahead bias. For anything revised, pull via **ALFRED point-in-time** (`realtime_start=<as-of>`), not FRED's latest. Daily market series (T10Y2Y, OAS, yields, VIX) are essentially **not revised** → safe to use FRED-latest. This is the single biggest correctness trap in the macro lane.

---

### B. US Treasury — Daily Par Yield Curve (keyless)

**Access:** XML feed, **no key**: `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=<YYYY>`. Also CSV download per year. **Reachable from this VM (verified).**
**History:** **1990 → present** (verified empirically: 1990=250 daily entries, 1989=0). Daily, T+0/T+1.
**Cadence:** Daily, ~1-business-day lag.
**Licensing:** US-gov **public domain**. No restrictions.
**Orthogonality:** Same family as FRED curve (bond term structure) — **high vs equity**, but **redundant with FRED T10Y2Y/DGSx**. Value = keyless + you control the spread construction + it IS the primary source (no FRED redistribution caveat).
**Ingestion ease:** **2** (XML parse; one file/year; clean). Slightly more than FRED JSON but trivial.
**Verdict:** Best **no-signup** route to the curve; good redundancy. History starts 1990 ⇒ **misses pre-1990** but covers '08/'20/'22.

---

### C. ECB Data Portal (formerly SDW) — euro-area macro (keyless)

**Access:** REST `https://data-api.ecb.europa.eu/service/data/<FLOW>/<KEY>?format=jsondata` (also CSV/SDMX). **No key.** **Reachable from this VM (verified — EUR/USD daily returned).**
**History:** varies by series; euro-area rates/FX generally **1999 → present** (euro launch); some FX/rate series earlier. Spans '08/'20/'22.
**Cadence:** daily (FX, yields), monthly (inflation, M3), etc.
**Licensing:** ECB data **free to use with attribution**; permissive. OK for private/paper.
**Orthogonality vs US equity OHLCV:** **High** — different monetary bloc (Bund yields, euro financial conditions, EUR FX). Adds a *second* macro regime axis. But correlated to US risk-on/off in crises (global beta).
**Ingestion ease:** **2** (SDMX-JSON is slightly fiddly; series-key syntax has a learning curve).
**Verdict:** Good diversification *after* US sources are in. Not top-3 EV on its own (US-centric strategy), but cheap and orthogonal-ish.

---

### D. BEA (Bureau of Economic Analysis) — GDP & components

**Access:** REST API, **free key** required. `https://apps.bea.gov/api/data?...&UserID=…`.
**History:** GDP back to 1947 (quarterly), some annual to 1929.
**Cadence:** **Quarterly**, **first estimate ~1 month after quarter-end, then 2 revisions over 2 months.** Heavy revisions.
**Licensing:** US-gov public domain.
**Orthogonality:** High *conceptually* (real-economy output) but…
**Ingestion ease:** 2–3 (key + dataset/table-code navigation).
**Verdict:** ❌ **Down-rank for tradeable signal.** Quarterly + ~1–2mo lag + big revisions ⇒ near-useless for daily/hourly trading; the market has fully repriced before the print lands. Regime context only. FRED already mirrors the key GDP series anyway (GDPC1 etc.).

---

### E. BLS (Bureau of Labor Statistics) — CPI / employment raw

**Access:** Public Data API v2, **free registration key** (v1 keyless but capped). `https://api.bls.gov/publicAPI/v2/timeseries/data/`.
**History:** CPI 1913+, employment 1939+ (deep).
**Cadence:** **Monthly**, scheduled release ~1–2 weeks after reference month; **subject to revision** (esp. payrolls).
**Licensing:** US-gov public domain.
**Ingestion ease:** 2 (JSON; series-ID coding scheme is arcane but documented).
**Verdict:** ❌ **Down-rank.** Same problem as BEA: monthly + lag + revisions. The *surprise* vs consensus on release day is tradeable but that's an event-study feature, not a continuous signal, and consensus data isn't free here. FRED mirrors CPIAUCSL/PAYEMS/UNRATE ⇒ no reason to hit BLS directly. Use ALFRED for point-in-time.

---

### F. OECD — international macro

**Access:** SDMX REST API, **no key** (`https://sdmx.oecd.org/public/rest/data/...`). (Did not live-test this session; documented as keyless.)
**History:** varies; many series 1960s+.
**Cadence:** mostly **monthly/quarterly**, notable **lag** (OECD aggregates national stats).
**Licensing:** generally free with attribution (some datasets restricted).
**Orthogonality:** high (cross-country), but low cadence.
**Ingestion ease:** 3 (SDMX, entity/dimension mapping).
**Verdict:** ❌ Low EV for a fast US strategy — laggy, low-cadence, fiddly SDMX. Skip unless going explicitly cross-country/slow-regime.

---

### G. World Bank — development/macro indicators

**Access:** REST, **no key**: `https://api.worldbank.org/v2/country/US/indicator/<CODE>?format=json`. **Verified working from this VM.**
**History:** deep (often 1960+).
**Cadence:** **Annual** (mostly). ⇒
**Licensing:** CC-BY 4.0 (open).
**Orthogonality:** high conceptually.
**Ingestion ease:** **1** (cleanest keyless JSON I tested).
**Verdict:** ❌ **Annual cadence = useless for trading signal.** Trivial to ingest, open license — but yearly data can't drive a trading model. Mentioned only for completeness / macro backdrop.

---

## Ranking rationale (cadence × orthogonality × history × ingestion × license)

The macro lane's central tension is **history depth vs tradeable cadence**:
- Deep-history **fast** series (curve, credit OAS, financial-conditions) → ✅ the prize. Daily/weekly, ~1-day lag, span every modern bear, genuinely orthogonal to equity OHLCV (they price *bonds/funding/credit*, not stocks).
- Deep-history **slow** series (GDP, CPI, payrolls) → laggy + revised → ❌ context only, the market front-runs them.

So the EV ranking is dominated by **FRED's daily/weekly market-and-conditions subset**, with the **Treasury keyless curve** as redundant no-signup backup and **ECB** as a second-bloc diversifier.

**Orthogonality ladder (best→worst vs equity OHLCV):**
Credit OAS (HY/IG) ≳ Financial-Conditions (NFCI/ANFCI/STLFSI) ≳ Yield-curve slope (T10Y2Y/T10Y3M) ≳ Liquidity (WALCL/RRP) ≳ Breakevens > rate levels > **VIX (partly equity-implied — least orthogonal of the "macro" set)** > monthly CPI/jobs (laggy) > GDP (laggy+quarterly).

**Biggest correctness trap:** revisions/look-ahead → use **ALFRED point-in-time** for any revised series; daily market series are revision-free and safe.

**Biggest access gotcha:** this VM's datacenter IP is **bot-walled on `fred.stlouisfed.org` web/CSV** (Akamai) — but the **keyed `api.stlouisfed.org` works perfectly**. Plan ingestion on the API, not the CSV scrape.
