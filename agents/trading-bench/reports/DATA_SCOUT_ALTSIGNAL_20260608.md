# DATA SCOUT — Free Orthogonal / Alt-Data Sources for a Beat-SPX Equity Strategy
**Scout #1 · 2026-06-08 · RESEARCH ONLY (no code/orders changed)**

Mission: find FREE, programmatically-accessible datasets — **orthogonal to raw OHLCV** — that could
drive or *gate* a return-maximizing US-equity strategy (SPY/QQQ-class, small paper/retail account).
Decisive ranking filter = **history depth reaching 2008** (≥2 bear regimes: 2008 + 2020/2022) +
**licensing that actually permits personal/programmatic research** + **plausible orthogonality** to
the 11 price/vol lanes already capped at ~0.5 Sharpe.

**Live-tested this session (HTTP 200 + real data snippet captured):**
FINRA short-volume daily · Treasury.gov daily yield-curve CSV · NY Fed SOMA (Fed balance sheet) JSON ·
SEC EDGAR XBRL frames · Wikimedia pageviews API · AAII sentiment (GitHub mirror).
Endpoints I could NOT confirm from this datacenter IP are flagged honestly (bot-walls / flaky), not faked.

---

## (a) RANKED SHORTLIST — ingest in this order

| # | Source | Signal | →2008? | Tested live | Verdict |
|---|--------|--------|--------|-------------|---------|
| 1 | **FINRA daily short-volume** (RegSHO) | Daily short-vol / total-vol per ticker → crowding & squeeze pressure | **2009-08** (≈2008-adjacent; misses the very bottom) | ✅ pulled SPY/AAL rows | **HIGH** — daily, per-symbol, genuinely orthogonal, trivial flat-file |
| 2 | **AAII Investor Sentiment** (GitHub mirror) | Weekly retail bull/neutral/bear % → contrarian extreme gate | **1987-07** ✅ (1987,2000,2008,2020,2022) | ✅ CSV starts 7-24-87 | **HIGH** — deepest retail-sentiment history that's free; classic fade-the-crowd gate |
| 3 | **NY Fed SOMA holdings** (Fed balance sheet) | Weekly Fed System Open Market Account total/MBS/notes → QE/QT liquidity tide | **2003-07** ✅ | ✅ JSON from 2003 | **HIGH** — clean JSON API, no key, liquidity is a known equity tailwind/headwind |
| 4 | **Treasury.gov daily yield curve** | Full par-yield curve daily → curve shape / inversion / bear-steepening regime | **1990** ✅ | ✅ 2020 CSV clean | **HIGH** — authoritative, daily, no key; complements FRED T10Y2Y with full tenor set |
| 5 | **CBOE / FRED equity put-call ratio** | Daily total & equity-only P/C → options-crowd fear gauge | FRED P/C series **2006-ish**; CBOE site current-only | ⚠️ via FRED (fredgraph.csv) | **HIGH** — pull through FRED to dodge CBOE's HTML/CSV friction; orthogonal to price |
| 6 | **FINRA / FRED margin debt** | Monthly customer margin debit balances → leverage cycle / risk appetite | FRED quarterly to 1997; FINRA monthly to ~1997 | ⚠️ doc-confirmed | **MEDIUM-HIGH** — monthly is coarse but a real leverage-regime gate; pull via FRED |
| 7 | **NYSE/Nasdaq breadth (adv-decline)** via FRED/StockCharts | Daily advancers−decliners, new highs/lows → internal participation | FRED breadth series patchy; index-level to ~2000s | ⚠️ not live-confirmed here | **MEDIUM** — strong concept, but clean free *daily* history is the friction; verify source first |

> Build the top 4 first — all live-verified, all key-less, all reach ≥2008 (SOMA/Treasury/AAII comfortably; FINRA short-vol to 2009 covers the GFC *aftershock* + Euro-crisis + 2020 + 2022). Then layer P/C and margin via FRED.

---

## (b) FULL EVALUATION TABLE

### 1. FINRA Daily Short-Sale Volume (RegSHO Consolidated)  — **HIGH**
- **Signal / thesis:** Per-ticker daily `ShortVolume / TotalVolume`. Elevated short ratio on a name/ETF = crowding → mean-revert / squeeze fuel; falling short ratio into strength = conviction. For SPY/QQQ it's a tape-level fear proxy independent of the price path itself.
- **Access:** `https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt` — pipe-delimited, no auth, no key, no rate limit observed. One file per trading day. Also `FNYXshvol`/`FNQCshvol` (venue-specific).
- **History:** Daily files back to **~Aug 2009**. Misses the literal 2008 crash low but covers the GFC tail, 2010 flash crash, 2011 Euro crisis, 2015-16, 2018, **2020, 2022** — i.e. ≥2 full bear regimes still satisfied.
- **Orthogonality:** High. Short-flow is reported volume composition, not derivable from OHLCV.
- **Licensing:** Public regulatory disclosure, free flat files; personal/research use fine.
- **Live evidence:** `20260605|AAL|36876443.65|259554|88013517.76|B,Q,N` (real row pulled).
- **Verdict:** **HIGH** — best novel daily lane on this list; build first alongside SOMA.

### 2. AAII Investor Sentiment Survey — **HIGH**
- **Signal / thesis:** Weekly % of individual investors bullish/neutral/bearish. Bull-bear spread at extremes is a well-documented contrarian gate (excess bearishness → forward equity tailwind). Pure *retail psychology*, not price.
- **Access (the part that matters from a bot-walled IP):**
  - ❌ Official `https://www.aaii.com/files/surveys/sentiment.xls` → **403 Cloudflare challenge** from this datacenter IP (same wall as SEC/YouTube here).
  - ✅ **GitHub mirror** `https://raw.githubusercontent.com/psinopoli/AAII-Sentiment/main/AAII_SENTIMENT_CSV.csv` — clean `Date,Bullish,Neutral,Bearish`, no auth.
- **History:** **1987-07-24 →** (live-confirmed first row). Covers every modern bear incl. 2008.
- **Orthogonality:** High — survey sentiment, fully independent of OHLCV.
- **Licensing caveat:** AAII data itself is © AAII for members; the *mirror* is a third party. For a private paper-trading research use this is the pragmatic path, but treat the live tail as **possibly stale** (depends on maintainer refresh) and don't redistribute. If freshness matters, the survey value can also be cross-checked on FRED-adjacent aggregators.
- **Live evidence:** `7-24-87,0.36,0.50,0.14` … (header + 1987 rows captured).
- **Verdict:** **HIGH** — deepest free retail-sentiment history; ideal as a *gate*, not a daily signal (weekly cadence).

### 3. NY Fed SOMA — Federal Reserve Balance Sheet Holdings — **HIGH**
- **Signal / thesis:** Weekly System Open Market Account holdings (`total`, `notesbonds`, `bills`, `mbs`, `tips`). The size/direction of the Fed balance sheet = QE/QT liquidity regime, a first-order driver of multiple expansion. Δ(SOMA) as a slow risk-on/off tide.
- **Access:** `https://markets.newyorkfed.org/api/soma/summary.json` (and `/asofdates/...`, `/holdings/...`). JSON, **no key**, no rate-limit hit. Excellent docs at markets.newyorkfed.org/static/docs.
- **History:** **2003-07-09 →** (live-confirmed first record). Covers 2008 QE1 onward fully.
- **Orthogonality:** Very high — policy/liquidity, not price.
- **Licensing:** Public Fed data, free programmatic use.
- **Live evidence:** `{"asOfDate":"2003-07-09","total":"650982322000.00", ...}`.
- **Verdict:** **HIGH** — cleanest JSON on the list; pair with FRED H.4.1 (`WALCL`) for cross-check.

### 4. Treasury.gov Daily Treasury Par Yield Curve — **HIGH**
- **Signal / thesis:** Full daily par-yield curve (1M→30Y). Curve *shape* (2s10s, 3m10y, bear-steepening, twist) is a regime classifier that pure SPX price can't see. Inversion → recession-risk gate; re-steepening from inversion historically precedes equity stress.
- **Access:** `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{YYYY}/all?type=daily_treasury_yield_curve&field_tdr_date_value={YYYY}&page&_format=csv` — CSV, no auth, one full year per call.
- **History:** **1990 →** for the full curve (par yields). Easily ≥2008.
- **Orthogonality:** Moderate-high vs equity OHLCV (rates ≠ stock price, though risk-correlated in crises — which is the point for a gate).
- **Licensing:** Public, free.
- **Live evidence:** `12/31/2020,0.08,0.08,0.09,...,0.93,1.45,1.65` (clean 2020 row).
- **Verdict:** **HIGH** — authoritative full-tenor complement to FRED's single spreads.

### 5. CBOE / FRED Put-Call Ratio — **HIGH (route via FRED)**
- **Signal / thesis:** Total and equity-only put/call volume ratio = options-crowd positioning/fear. Spikes mark capitulation; complacent lows mark froth. Orthogonal to price level.
- **Access:** CBOE's own daily-stats page (`cboe.com/.../market-statistics/daily`) renders only a disclaimer to scrapers (confirmed — readable extract was just legal text; the numbers sit behind a JS table/secondary CSV). **Practical path = FRED**, which republishes CBOE series (e.g. equity & total P/C) as `https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}` — same channel you already use for HY-IG/NFCI.
- **History:** CBOE P/C history via FRED reaches roughly **2006**, covering 2008.
- **Orthogonality:** High.
- **Licensing:** FRED redistribution of CBOE is fine for research; CBOE site data carries "convenience, no warranty" terms.
- **Verdict:** **HIGH** — zero new infra (reuse FRED client); just add series IDs.

### 6. FINRA / FRED Margin Debt — **MEDIUM-HIGH**
- **Signal / thesis:** Monthly aggregate customer margin debit balances = system leverage / risk appetite. YoY contraction in margin debt has coincided with equity drawdowns (leverage unwind). A slow risk-cycle gate.
- **Access:** FINRA publishes monthly on its statistics site (HTML/xls, bot-friction-prone like AAII); **easier via FRED** (margin-related series, mostly quarterly via Z.1, some monthly). `fredgraph.csv?id=...`.
- **History:** Quarterly Z.1 to **1997+**; FINRA monthly series to ~1997. ≥2008 ✅ but coarse.
- **Orthogonality:** High concept; low frequency limits it to a regime filter, not a trade trigger.
- **Licensing:** Public.
- **Verdict:** **MEDIUM-HIGH** — useful gate, but monthly cadence caps standalone alpha.

### 7. NYSE/Nasdaq Breadth — Advance/Decline & New-Highs/Lows — **MEDIUM**
- **Signal / thesis:** Daily advancers−decliners, A/D line, new-highs minus new-lows = market *internals*. Breadth thrust (Zweig) is a documented bull-confirmation; breadth divergence (index up, A/D down) flags fragile rallies. Orthogonal-ish to the index price path.
- **Access:** No single clean free key-less daily API. Options: FRED has some breadth-adjacent series; StockCharts `$ADD`/`$NYAD` (display, not free API); Nasdaq/NYSE raw files are awkward. **Verify a concrete source before committing.**
- **History:** Index-level breadth exists for decades, but *free programmatic daily* history to 2008 is the friction.
- **Orthogonality:** High.
- **Licensing:** Varies by source — vet per provider.
- **Verdict:** **MEDIUM** — high-value concept, sourcing risk. Worth a focused follow-up scout if the top-4 don't deliver edge.

### 8. Wikipedia / Wikimedia Pageviews — **MEDIUM (regime-limited)**
- **Signal / thesis:** Daily pageviews for finance terms ("S&P 500", "Recession", "Bear market", specific tickers) = attention/anxiety proxy; spikes lead/coincide with stress.
- **Access:** `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{ARTICLE}/daily/{start}/{end}` — clean JSON, **no key**, generous limits.
- **History:** **2015-07 only** (API introduced Aug 2015, backfilled to Jul 2015). **FAILS the ≥2008 filter** — misses 2008 entirely and the pre-2015 setup.
- **Orthogonality:** High.
- **Licensing:** CC0/free, programmatic OK.
- **Live evidence:** `{"article":"S&P_500","timestamp":"2020010100","views":1083}`.
- **Verdict:** **MEDIUM** — technically pristine + free, but the 2015 floor means you can't validate it across 2008. Usable only as a *modern-era* overlay, never a primary regime gate. (Pre-2015 `stats.grok.se` exists but is unmaintained/unreliable.)

### 9. SEC EDGAR XBRL Frames / Financial-Statement Datasets — **HIGH but already "covered"**
- **Status:** On the known list, but two field notes worth recording:
  - ✅ `https://data.sec.gov/api/xbrl/frames/us-gaap/{Tag}/USD/CY{YYYY}Q{n}I.json` **works** and reaches **2009** (live-pulled CY2009Q1 Assets, 80 points).
  - ⚠️ **Hard UA requirement:** `sec.gov/cgi-bin/browse-edgar` (Form-4 current feed, full-text search) returns **403 "undeclared automated tool"** without a declared `User-Agent: Company contact@email`. data.sec.gov tolerated web_fetch's default UA, but any real client must set a descriptive UA + stay ≤10 req/s.
- **Verdict:** Keep as covered; flag the UA gotcha so the ingestor sets headers up front.

---

## (c) DEAD-LIST — do NOT re-chase

| Source | Why DEAD |
|--------|----------|
| **Reddit / Pushshift sentiment** | Pushshift restricted to mods; Reddit API now paid/locked. Licensing dead (as already known). |
| **NAAIM Exposure Index** | Members/commercial-permission gated; not freely programmatic. (Already flagged.) |
| **AAII official `sentiment.xls` direct** | **403 Cloudflare** from datacenter IP. (Data itself alive via GitHub mirror — use that, see #2.) |
| **Wikimedia pageviews for 2008 validation** | API floor = **2015-07**. Cannot cover 2008. Modern overlay only, never a regime gate. |
| **CBOE daily-stats HTML scrape for P/C numbers** | Page serves only a disclaimer to fetchers; numbers behind JS. Get P/C via **FRED** instead, don't scrape CBOE. |
| **SEC browse-edgar / EDGAR FTS without UA** | **403** "undeclared automated tool" unless a descriptive User-Agent is set. Not dead, but dead-if-you-forget-the-header. |
| **stats.grok.se (pre-2015 pageviews)** | Unmaintained / unreliable; don't depend on it for the 2008 gap. |
| **Stooq `/q/d/l/` CSV (from this VM)** | Returned empty/expired via web_fetch here (cookie/rate friction). Index prices already covered by Yahoo chart API — not worth fighting. |

---

## (d) BUILD ORDER (recommendation)

1. **NY Fed SOMA** + **Treasury daily yield curve** first — both key-less JSON/CSV, reach 2003/1990, cleanest ingestion, give you a **liquidity tide + curve-shape regime** layer to *gate* the existing price/vol lanes. Lowest effort, highest coverage.
2. **FINRA daily short-volume** — your one genuinely *novel daily* orthogonal lane. Loop the dated flat-file pattern (2009→present); aggregate SPY/QQQ short-ratio + a breadth-of-shorting cross-section.
3. **AAII sentiment (GitHub mirror)** + **P/C via FRED** — bolt on as **weekly/daily contrarian gates** (extreme bearishness / P/C spikes = risk-on tilt). Reuse the FRED client you already have for P/C; AAII is a tiny static CSV.
4. **Margin debt (FRED)** as a slow monthly leverage-cycle filter — cheap to add once FRED client exists.
5. Only then, if top-tier lanes underwhelm: spin a **focused breadth-sourcing scout** (A/D line daily to 2008) and consider Wikipedia pageviews as a **post-2015 overlay** for live trading (not backtest validation).

**Reminder for whoever ingests:** orthogonal *data* ≠ *edge*. Every one of these reaches the bar on coverage + access + licensing; the **backtest across 2008/2020/2022 decides** which actually gate or drive return. Rank candidates by regime coverage (done here), then let the engine kill the ones with no out-of-sample lift. SOMA + short-vol are my highest-conviction *new* digs; AAII is the highest-conviction *gate*.
