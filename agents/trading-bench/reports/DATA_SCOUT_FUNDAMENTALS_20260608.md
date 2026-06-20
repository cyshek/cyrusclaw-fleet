# DATA SCOUT — FREE FUNDAMENTALS / EARNINGS / ESTIMATE-REVISION HISTORY
**Date:** 2026-06-08 · **Scope:** read-only, live-tested from this VM's datacenter IP · **Tools:** curl/web_fetch only (no keys used)

## TL;DR VERDICT
- **Free, backtest-grade FUNDAMENTALS exist and are excellent: SEC EDGAR `data.sec.gov` JSON APIs.** Point-in-time by construction (`filed` date + `accn`), reach ~mid-2009, 5,000-company cross-sections, 200 OK from our IP with a declared User-Agent. This is our anti-lookahead backbone. **Buildable today.**
- **Free EARNINGS SURPRISE + CALENDAR exist: Nasdaq `api.nasdaq.com` (no key, 200 from our IP)** gives actual-vs-consensus EPS surprise history per symbol + a daily calendar. Alpha Vantage `EARNINGS`/`EARNINGS_CALENDAR` (free 25/day) corroborates reported EPS back ~quarterly.
- **Historical estimate-REVISION TIME SERIES (the #1 funded-upgrade target) stays effectively PAID.** No free source gives a *dated history* of consensus EPS as-of each past date. **BUT** Nasdaq's `earnings-forecast` endpoint exposes a free **snapshot** of "revisions up / down over the last 4 weeks" + high/low/mean + #estimates — a usable *current* revision-momentum signal, just not a deep backtestable panel. So: revision-momentum is *partially* free (live signal yes, deep history no).

---

## RANKED SOURCES (live HTTP from our datacenter IP)

### 1. SEC EDGAR — `data.sec.gov` JSON APIs ★ BACKBONE (free, no key, point-in-time)
- **companyfacts:** `GET https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit}.json` → **HTTP 200, 3.7 MB** (AAPL). 503 us-gaap concepts. Each datapoint carries `val, start, end, accn, fy, fp, form, filed, frame`.
- **frames (cross-sectional, all filers one concept/period):** `GET .../api/xbrl/frames/us-gaap/EarningsPerShareDiluted/USD-per-shares/CY2023Q1.json` → **200, 745 KB, 4,993 companies**. This is how you build a universe-wide point-in-time panel in one call per concept/period.
- **submissions / filing index:** `GET https://data.sec.gov/submissions/CIK{...}.json` → **200, 164 KB** (filing dates, forms, accession nos).
- **full-text search:** `GET https://efts.sec.gov/LATEST/search-index?q=...` → **200**.
- **POINT-IN-TIME DISCIPLINE (critical):** the `filed` field = the date the number became public. **Backtest rule: only use a fact on/after its `filed` date, NOT its period-`end` date.** Restatements appear as *new* rows (later `filed`, same `end`) → to avoid lookahead, for any as-of date T select the row with the **largest `filed` ≤ T** for each `(concept, fy, fp)`. This is exactly the lever we'd otherwise pay a vendor for; EDGAR gives it natively.
- **Earliest date:** XBRL mandate → data is rich from **~mid-2009** (CY2009Q3 frame = 184 KB; CY2008Q1 = 3.5 KB ≈ empty). Pre-2009 not available via XBRL.
- **Auth/headers:** **MUST send `User-Agent: name email`** → 200. Without UA → **403** (confirmed). No API key, no signup. Fair-Access rate ~10 req/s; bulk `*.zip` (companyfacts.zip / Financial Statement Data Sets) live on `www.sec.gov` which scraper-guards UA-less hits (we saw 403 on those static paths + a "Request Rate Threshold Exceeded" page) — fetchable with a compliant UA + polite throttle, but the JSON APIs above already cover the need without bulk downloads.
- **License:** U.S. government work, public domain. No attribution required.
- **Concepts confirmed present (AAPL):** EarningsPerShareDiluted (334 pts, filed 2009-07-22→2026-05-01), NetIncomeLoss (334), Revenues / RevenueFromContractWithCustomerExcludingAssessedTax (113), Assets (144), StockholdersEquity (258). Enough for value (P/B, P/E), quality (ROE, accruals), and earnings-surprise-vs-fundamentals signals.

### 2. Nasdaq `api.nasdaq.com` ★ EARNINGS SURPRISE + CALENDAR + revision SNAPSHOT (free, no key)
- **Per-symbol surprise history:** `GET https://api.nasdaq.com/api/company/AAPL/earnings-surprise` → **200**. Returns `{fiscalQtrEnd, dateReported, eps (actual), consensusForecast, percentageSurprise}` — but **only last ~4 quarters** per call (shallow history; not a deep backtest panel on its own).
- **Daily calendar w/ surprise:** `GET https://api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD` → **200**, 62 rows/day for a sample date: `{symbol, eps, epsForecast, surprise, noOfEsts, fiscalQuarterEnding, time, marketCap}`. Iterate dates → build a dated surprise+report-date dataset going forward (and some backfill).
- **Revision-momentum SNAPSHOT (closest free thing to the paid target):** `GET https://api.nasdaq.com/api/analyst/AAPL/earnings-forecast` → **200**. Per fiscal period: `consensusEPSForecast, highEPSForecast, lowEPSForecast, noOfEstimates, up, down` where up/down = **"Over the Last 4 Weeks Number of Revisions – Up / Down."** This is a *current-state* revision-direction signal — directly usable for a live revision-momentum tilt — but **no dated history** is returned (`asOf: null`), so you can only build a panel by snapshotting it yourself going forward.
- **Headers:** needs a browser-y `User-Agent` (+ `Accept: application/json`); no key, no signup. **Earliest:** effectively "now + shallow trailing"; treat as a *forward-collection* source, not a deep archive.
- **License:** undocumented/ToS-gray (unofficial JSON behind nasdaq.com). Fine for research; don't redistribute.

### 3. Alpha Vantage — `EARNINGS`, `EARNINGS_CALENDAR` (free key, 25 req/day)
- `function=EARNINGS&symbol=IBM&apikey=demo` → **200**, annual+quarterly **reportedEPS** history (multi-year). `EARNINGS_CALENDAR&horizon=3month` → **200**, CSV of upcoming `{symbol, reportDate, fiscalDateEnding, estimate, timeOfTheDay}`.
- Gives **reported actuals + forward estimate (single, current)**; **no revision history.** Free tier **25 calls/day** (sometimes "demo" key wider) → too thin to refresh a large universe daily; fine as a cross-check / small-universe source. Earliest: several years of quarterly reported EPS. License: free tier, attribution appreciated.

### 4. Financial Modeling Prep (free key, 250/day, US only)
- No-key call → **HTTP 401** (`earnings-surprises/AAPL`). Free tier = **250 req/day, US-market only** (per current docs). Has analyst-estimates + earnings-surprise endpoints, but **historical estimate depth is gated to paid**; free is shallow/snapshot. Usable as a small secondary; not a revision archive.

### 5. Finnhub (free key required for ALL the relevant endpoints)
- `revenue-estimate`, `eps-estimate`, `recommendation`, `earnings`, `price-target`, `upgrade-downgrade` → all **HTTP 401 `"Please use an API key"`** without a token. Free tier exists but: estimate/revision-trend endpoints are **premium-gated** and free history is capped (~1 yr); company-profile already moved to premium. **The estimate-trend / revision endpoints are NOT in the free tier** → does not solve the revision problem for free.

### 6. Others — quick verdicts
- **Tiingo fundamentals:** `/tiingo/fundamentals/...` → **HTTP 403** no-token; fundamentals are a **paid add-on** even with a free account. Not free for this.
- **polygon.io financials:** `vX/reference/financials` → **HTTP 401** no-key; free tier exists but heavily rate-limited and financials depth/estimates are gated. Restated, not point-in-time. Skip.
- **SimFin:** `backend.simfin.com/api/v3/...` → **HTTP 401**. Free tier gives *some* standardized fundamentals (delayed) but **no estimate revisions**; restated statements (lookahead risk). Marginal vs EDGAR.
- **Zacks / Estimize / IBES / Intrinio Zacks-EPS:** the actual *historical estimate-revision* products — all **paywalled** (Intrinio/Zacks licensed; Estimize quant access is commercial; IBES = Refinitiv/WRDS paid). No free dated-revision panel surfaced. (Web-search corroboration was partial — search backend degraded mid-scout — but every "estimate revisions API" hit resolved to a paid/keyed vendor.)

---

## ESTIMATE-REVISION VERDICT (the funded-upgrade question)
**A free, dated, backtestable history of analyst EPS/revenue estimate revisions does NOT exist on any tier we could reach.** It stays a **funded upgrade** (IBES/Zacks/Estimize/Intrinio class). Two free consolation paths:
1. **Forward-collect it ourselves for free:** snapshot Nasdaq `earnings-forecast` (consensus mean/high/low/#est + 4-wk up/down) on a schedule → over weeks we *build* our own revision time-series at $0. Cheap to start, but no backfill (history accrues only from when we start).
2. **Use earnings SURPRISE drift instead (PEAD), which IS free:** EDGAR (actual EPS, point-in-time `filed`) × Nasdaq/AlphaVantage (consensus at report) → surprise → drift. This captures most of the same alpha family the revision data targets, without paying.

## WHAT'S BUILDABLE NOW (free, point-in-time clean)
1. **EDGAR quality/value cross-section** — pull `frames` for EPS/NetIncome/Assets/Equity/Revenue per quarter; rank universe on ROE, earnings yield, accruals; rebalance using **`filed`-date masking** to avoid lookahead. Pure EDGAR, public-domain, ~2009→now.
2. **Earnings-surprise drift (PEAD)** — EDGAR actual EPS (with `filed`/`accn`) joined to consensus-at-report (Nasdaq surprise / AV estimate); go long large positive surprises post-report for the drift window. Free end-to-end.
3. **Live revision-momentum tilt** — overlay Nasdaq `earnings-forecast` up/down counts as a *current* signal on top of (1)/(2). Live-usable immediately; backtest only on self-collected history.

**Point-in-time discipline (non-negotiable):** key every fundamental on its EDGAR `filed` date, take the latest-filed row ≤ as-of T per (concept,fy,fp), and never use a restated value before its restatement `filed` date. Lag earnings-date joins to the *reported* date, not the fiscal period end. Do this and the free stack is genuinely backtest-grade for fundamentals + surprise (revision-history remains the only piece worth paying for later).
