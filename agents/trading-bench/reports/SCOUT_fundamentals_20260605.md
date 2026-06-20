# SCOUT — Fundamentals / Earnings / Estimate-Revisions (FREE routes only)
**Class:** Company fundamentals, earnings dates/surprises, analyst estimate revisions, guidance.
**Date:** 2026-06-05 · **Scout:** trading-bench subagent `scout-fundamentals`
**Mission:** orthogonal (corr <~0.3 to OHLCV) FREE signal to break the ~0.5 Sharpe ceiling. Scouting only — no ingest/backtest.

> **Verification note:** `web_search` was unavailable this run (SearXNG not configured). All claims below verified via live `curl`/`web_fetch` against vendor docs + live API pings, or flagged ⚠️ where the vendor page is a JS-only SPA that returned an empty shell to non-browser fetches and I fell back to strong prior knowledge. SEC pages throttled automated fetches (HTTP 429 "Request Rate Threshold Exceeded") until I used a compliant `User-Agent` with contact info — that UA requirement is itself an ingestion note.

---

## TL;DR — Top picks
1. **SEC EDGAR — Financial Statement Data Sets (bulk) + XBRL `companyfacts`/`companyconcept`/`frames` REST API** — the only *free, deep-history, point-in-time, licence-clean* fundamentals source. **VERIFIED Jan 2009 → Mar 2026**, quarterly bulk ZIPs + no-key JSON API. Spans 2009/2020/2022 regimes. This is the anchor.
2. **SimFin (free account, bulk-CSV + Python API)** — pre-cleaned, normalized financial statements, ~5,000 (mostly US) companies, **20+yr** claimed history, free without credit card. The "EDGAR-but-already-parsed" convenience layer. Ingestion-ease win; needs licence + PIT scrutiny.
3. **Alpha Vantage `EARNINGS` (free key)** — **VERIFIED free** reported-EPS + quarterly earnings-surprise history via demo key, multi-year. **BUT 25 requests/day** free cap = spot-check only, not universe-scale.

**Highest-value signal in this class = earnings-surprise + estimate-REVISION history.** Verdict: *surprise* history is partially free (Finnhub last-4-quarters, AV via 25/day). *Estimate-revision* history (the real alpha) is **paywalled everywhere** on free tiers — the class's single biggest gap.

---

## Full catalog

| Source | Access / auth | History depth (verified) | Cadence / lag | Licensing | Orthogonality to OHLCV | Ingestion ease (1–5) | Verdict |
|---|---|---|---|---|---|---|---|
| **SEC EDGAR Financial Statement Data Sets** (bulk) | Free HTTP ZIP per quarter; no key; compliant UA required | **Jan 2009 → Mar 2026** ✅ (page header literally states range) | Quarterly; ~quarter lag (data filed after quarter-end lands next posting) | **Public domain (US gov)** — fully clean for private/paper/commercial | High (~0.1–0.3): raw statement line-items, not price | **2** (flat TSV/NUM/SUB/TAG/PRE files; well-documented PDF schema) | **TOP PICK** |
| **SEC EDGAR XBRL REST API** (`data.sec.gov/api/xbrl/companyfacts`, `companyconcept`, `frames`) | Free JSON; no key; UA required; ~10 req/s fair-access | Back to **2009** (XBRL mandate era); per-tag | Updated as filings post; ~real-time on filing | **Public domain** | High | **2** (clean JSON; ⚠️ *tag fragmentation* gotcha, see notes) | **TOP PICK** |
| **SEC EDGAR Full-Text Search** (`efts.sec.gov/LATEST/search-index`) | Free JSON; no key; UA required | **2001 → present** (FTS index coverage) | Real-time on filing | **Public domain** | High (text/event signal: 8-K timing, guidance language, risk-factor deltas) | **3** (must parse filing bodies / NLP) | Strong (event + text overlay) |
| **SimFin** (free account) | Free signup (no CC); bulk-CSV + Python API + Excel | **~20+ yr** claimed; US first (US 20yr target completed ~Q1 2023) ⚠️ verify start year per-statement | Updated continuously; statement cadence quarterly | ⚠️ SaaS ToS — FREE tier "all major features"; confirm redistribution/commercial clause before relying | High | **1** (pre-normalized clean CSV — its whole pitch; "saves steps vs EDGAR") | **TOP PICK** (convenience) |
| **Alpha Vantage** `EARNINGS` | Free key, **25 req/day** | Multi-year reported-EPS + surprises ✅ (demo key returned full history) | Quarterly | Free tier ToS ok for research; NASDAQ-licensed (realtime is premium) | High (surprise = orthogonal event) | **2** (clean JSON) but **25/day kills universe scale** | Spot-check only |
| **Alpha Vantage** `INCOME_STATEMENT`/`BALANCE_SHEET`/`CASH_FLOW`/`EARNINGS_CALENDAR` | Free key, 25/day | "20+ yr" claimed | Quarterly | as above | High | **2** | Same 25/day cap |
| **Alpha Vantage** `EARNINGS_ESTIMATES` | Free key | ⚠️ demo returned **empty** `estimates:[]` — likely premium/sparse | — | — | High (estimate revisions = top signal) | — | **Gap — not usable free** |
| **Finnhub** `/stock/earnings` (EPS surprises) | Free key (60/min) | Endpoint says "back to 2000" but **`freeTier:"Last 4 quarters"`** ✅ (from API spec) | Quarterly | Free ToS personal/eval; commercial unclear ⚠️ | High | **2** | **Crippled: 4q only free** |
| **Finnhub** estimate endpoints (`/stock/eps-estimate`, `/revenue-estimate`, EBIT, EBITDA, DPS) | Free key | **"Premium Access Required"** ✅ (spec flag) | — | — | High (revisions) | — | **Gap — paywalled** |
| **Finnhub** `/stock/financials-reported` (as-reported), `/metric` | Free key | Limited on free; premium for depth ⚠️ | Quarterly | — | High | 2 | Weak free |
| **Sharadar Core US Fundamentals (SF1)** via Nasdaq Data Link | API key required | Deep (≈1998+) **point-in-time, multi-dimension (ARQ/ART/MRQ…)** | Continuous ✅ | **`"premium":true`** ✅ (metadata endpoint) — data call w/o sub → "valid API key required" | High; **best-in-class PIT** (no restatement lookahead) | 1 (clean datatable) | **PAID — dealbreaker.** Free "SF0" = tiny ticker sample only |
| **Financial Modeling Prep (FMP)** free tier | Free key, **250 calls/day** | Free tier = **End-of-Day only**; **5yr history is the PAID Starter ($22/mo)** tier ✅; fundamentals mostly marked "L"=latest/limited on free | Daily/quarterly | Free ToS; commercial = paid | High | 2 | **Weak free: latest-only, no deep fundamentals** |
| **Tiingo** fundamentals | Free key | ⚠️ Free fundamentals historically **DOW 30 only**; full "all listings" is a paid add-on (SPA unrenderable to confirm live this run) | Daily statements/metrics | Free ToS research-ok; redistribution restricted | High | 2 | **Universe-capped free → near-useless for breadth** |
| **Tiingo** EOD + news (free) | Free key | EOD deep; news separate | Daily | as above | (EOD = price, NOT orthogonal) | 1 | Out of class (price) |

---

## Notes, gotchas & honest caps

### SEC EDGAR (the anchor — free, deep, clean)
- **Three complementary free surfaces, all no-key, all public-domain:**
  1. **Bulk FSDS** — quarterly ZIPs, **verified coverage Jan 2009 → Mar 2026**. Each ZIP = `sub` (submission), `num` (numeric facts), `tag`, `pre`, `txt`. Best for batch building a full-universe fundamentals panel.
  2. **REST `companyfacts`/`companyconcept`** — `https://data.sec.gov/api/xbrl/companyconcept/CIK{10digit}/us-gaap/{Tag}.json`. **Live-tested OK** (Apple `entityName` + facts JSON returned). Also a `companyfacts/CIK{...}.json` all-tags blob.
  3. **`frames` API** — one concept across ALL filers for one period (great for cross-sectional ranking).
  4. **Full-text search** (`efts.sec.gov`) — returns 200; indexes **2001+**; good for 8-K/guidance event timing.
- **Point-in-time caveat (important):** EDGAR gives you each fact *as filed* with its `filed` date and `form`, so you CAN reconstruct PIT (use first-filed value, ignore later restatements). BUT: the **bulk FSDS were REPROCESSED in Dec 2024** — the dataset definition CHANGED (now only primary-statement, rendered facts; a new `segments` field added to NUM; prior version archived, not updated). If you mix pre- and post-Dec-2024 vintages you get a subtle methodology break. Pin to the reprocessed series.
- **Tag-fragmentation gotcha (live-observed):** querying `us-gaap:Revenues` for Apple returned only **2016–2018** because Apple migrated to `RevenueFromContractWithCustomerExcludingAssessedTax` (post-ASC 606). Building a clean revenue series requires mapping a *set* of concept tags per company across time — this is the real ingestion pain (entity/tag resolution), not the download. Budget for a tag-crosswalk layer.
- **Fair-access:** SEC throttles aggressively without a descriptive `User-Agent: name contact@email` header (I hit HTTP 429 until I set one). Keep ≤10 req/s. Bulk ZIPs avoid per-request limits entirely → prefer them for backfill.
- **Orthogonality:** very high. These are raw accounting line-items; correlation to OHLCV is the fundamental→price linkage you actually want to model, not a price re-feed.

### SimFin (best free convenience layer)
- Free account, **no credit card**, gives bulk-CSV + Python API. Pitch (and user testimonials) explicitly: "exactly what I'd do aggregating from SEC EDGAR myself — SimFin saves me the steps." So it's a pre-parsed EDGAR-equivalent with consistent schema/units → **ingestion ease 1**.
- Claims **20+ yr** history, ~5,000 companies, mostly US (EU/Asia were roadmap items for 2023–24). ⚠️ Verify per-statement start year — "20yr US" completion was targeted ~Q1 2023, so older years may be thinner for some names.
- **Licence is the open question:** SaaS ToS; "FREE account accesses all major features" but I could NOT load the Prices page (404/SPA) to read the redistribution/commercial clause. **Before depending on it for anything beyond personal paper research, read SimFin ToS for a "personal use only"/"no redistribution" blocker.** Paper-only research is almost certainly fine; treat commercial use as unconfirmed.
- **PIT:** SimFin is restated/cleaned, NOT explicitly point-in-time-versioned like Sharadar. Assume mild restatement lookahead risk — fine for coarse signal, not for strict PIT backtests. Cross-check against EDGAR `filed` dates if PIT matters.

### Earnings surprise & estimate REVISIONS (the high-value gap)
- **This is the single highest-EV fundamental signal** (estimate-revision momentum + surprise drift / PEAD are well-documented orthogonal alphas). Honest finding on FREE routes:
  - **Surprise history:** partially free. Finnhub free = **last 4 quarters only**. Alpha Vantage `EARNINGS` = multi-year free but **25 calls/day** → ~25 tickers/day backfill, painful but feasible over weeks for a fixed universe.
  - **Estimate (consensus) + REVISION history:** **paywalled on every free tier checked.** Finnhub estimates = "Premium Access Required"; AV `EARNINGS_ESTIMATES` returned empty on demo; FMP estimates = paid; Sharadar (which has the cleanest estimates/PIT) = premium.
  - **Free workaround for a *crude* revision proxy:** derive your own "implied revision/surprise" from EDGAR as-reported actuals vs. a naive model, OR scrape guidance language deltas from 8-K/10-Q via EDGAR FTS. Not true sell-side consensus, but $0 and orthogonal. Flag as a build, not a download.

### Down-ranked / out-of-scope
- **FMP free:** EOD-only, fundamentals "latest/limited," 5yr depth starts at the **paid** tier → fails regime-coverage on free. Skip for history.
- **Finnhub free:** good *latest* fundamentals + 4q surprise, but no deep history and estimates paywalled → spot-check only.
- **Tiingo free fundamentals:** DOW-30 universe cap (⚠️ unconfirmed-live but long-standing) makes it near-worthless for cross-sectional breadth. Tiingo's value is EOD price (out of this class).
- **Sharadar SF1:** technically the *best* product (deep PIT, multi-dimension) but **confirmed premium** — only its tiny SF0 sample is free. Note for a future paid-budget conversation; not actionable at $0.

---

## Recommended free stack for this class (zero spend)
1. **Backfill fundamentals from EDGAR bulk FSDS (2009→now)** — build the universe panel; pin to post-Dec-2024 reprocessed vintage; build a per-company tag-crosswalk to fight tag fragmentation.
2. **Layer EDGAR XBRL `frames` for cross-sectional ranking** + `companyconcept` for targeted series; use `filed` dates to enforce point-in-time.
3. **Use SimFin free bulk-CSV as a fast-start / cross-check** while the EDGAR parser matures (pending a 2-minute ToS read for redistribution).
4. **Earnings-surprise signal:** Alpha Vantage `EARNINGS` (25/day, fixed universe, backfill over a couple weeks) for multi-year surprises; supplement near-term with Finnhub free (last 4q).
5. **Estimate-revision alpha is NOT free** — either accept the gap, build a crude EDGAR-derived proxy, or escalate for a paid Sharadar/estimates budget.

**Bottom line:** EDGAR (bulk + XBRL API) is a genuinely excellent, regime-spanning, public-domain, point-in-time-capable free source — the real ingestion cost is tag/entity resolution, not access. SimFin removes that cost for free with a licence asterisk. The orthogonal-alpha sweet spot (consensus estimate revisions) is the one thing money would actually buy here.
