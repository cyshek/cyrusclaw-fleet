# SCOUT — Positioning / Flow / Smart-Money (FREE routes) — 2026-06-05

**Scout class:** Positioning / flow / crowding signal, free routes only.
**Mission:** Find FREE, orthogonal (corr <~0.3 to OHLCV) positioning data that can break trading-bench's ~0.5 Sharpe signal ceiling. Scouting only — no ingest/backtest.
**Verification:** All access/history/cadence claims below were checked live via `web_fetch`/`curl` this session (2026-06-05). Where a source throttled or walled my probe, I say so explicitly and mark the claim as **partially verified**. Fetched page bytes treated as untrusted data (no embedded instructions followed).

---

## TL;DR ranked picks

1. **CFTC Commitments of Traders (COT)** — the crown jewel. Free gov bulk, history to **1986**, weekly, public domain, clean. Truly orthogonal (futures positioning of commercials vs. large specs vs. small traders).
2. **FINRA daily short-volume files** — free CDN CSV, no auth, daily. History **only ~2019→present** (covers 2020+2022, NOT 2008). High orthogonality, trivial ingest.
3. **AAII weekly sentiment survey** — free, weekly, history to 1987, but it's a survey (noisy, retail-opinion) and full history export is partly gated. Orthogonal-ish; secondary.

**Dealbreakers to flag up front:**
- **NAAIM Exposure Index** — explicitly **commercial use requires NAAIM permission** (verified on their page). Free to *view* only. ❌ for our potentially-commercial context.
- **SEC 13F** — **45-day lag + longs-only + no short positions** = stale, half-blind positioning. Weak signal despite being free. Down-ranked.
- **FINRA short-interest (bi-monthly)** — only ~2 snapshots/month + ~9-day settlement-to-publish lag; the *signal* is fine but cadence is coarse.
- **SEC EDGAR throttles aggressive automated access** (Fair Access). Verified: `data.sec.gov` JSON worked, then repeated hits → "Request Rate Threshold Exceeded". Must set a real `User-Agent` and pace requests. Not a dealbreaker, an ingestion constraint.

---

## Full catalog

| # | Source | Access | History depth | Cadence / lag | Licensing | Orthogonality (est.) | Ingest ease (1-5) | Verdict |
|---|--------|--------|---------------|---------------|-----------|----------------------|-------------------|---------|
| 1 | **CFTC COT** (legacy + disaggregated + TFF) | Bulk ZIP per year, no auth, no key. `cftc.gov/files/dea/history/...` | **1986→present** (legacy); disaggregated 2006/2009→ | **Weekly.** Tue-close snapshot, published **Fri 3:30pm ET → 3-day lag** | **Public domain (US gov).** No restriction. | **HIGH (~0.1-0.25).** Futures positioning, not price. | **2** (clean TXT/XLS, fixed schema; need symbol→contract map) | ⭐ TOP PICK |
| 2 | **FINRA daily short-sale volume** | `cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt`, no auth | **~2019-01→present** (2018 & earlier = 403). **No 2008.** | **Daily**, ~next-day | **Public reg data**, free download. No redistribution-blocker found. | **HIGH (~0.2).** Short flow per symbol/day. | **1** (pipe-delimited CSV, one file/day) | ⭐ TOP PICK |
| 3 | **FINRA short-interest (Reg 4560)** | FINRA downloadable bi-monthly short-interest file (exact bulk URL to confirm at ingest; main site is Cloudflare-walled to bots) | Long (years); bi-monthly settlement dates | **Bi-monthly** (2×/mo), **~8-9 day** settle→publish lag | Public reg data, free | **HIGH (~0.15).** Aggregate short positioning per name. | **2** | ⭐ strong (coarse cadence) |
| 4 | **SEC Form 4 (insider txns)** | EDGAR: `data.sec.gov/submissions/CIK*.json` (verified 200) + full-index/daily-index feeds | **1994/2003→present** (Form 4 e-filing mandatory 2003) | **Near-real-time** (insiders must file ≤2 business days) | **Public domain.** UA + pacing required (throttle verified). | **HIGH (~0.1-0.2).** Insider buy/sell. | **3** (entity/CIK mapping, XML parse, throttle pacing) | ✅ good, timelier than 13F |
| 5 | **AAII Sentiment Survey** | `aaii.com/sentimentsurvey/sent_results` (HTML table, verified 200); full history Excel partly member-gated | **1987→present** (full export gated) | **Weekly** (Thu release) | "tracking only"-style; survey data. Personal/research OK; redistribution unclear. | **MED (~0.25-0.4).** Retail opinion, mean-reverting vs price. | **2** (scrape weekly table) / **3** for full backfill | ✅ secondary |
| 6 | **SEC 13F institutional holdings** | EDGAR 13F structured data sets + filings; free | **2013→** (structured sets); filings older | **Quarterly**, **45-day lag** | Public domain | **MED-LOW.** Stale + **longs-only, no shorts**. | **4** (entity resolution, 13F security mapping) | ⚠️ weak (lag+longs-only) |
| 7 | **NAAIM Exposure Index** | `naaim.org/...exposure-index` (verified 200); CSV/embed | 2006→present | **Weekly** (Wed poll) | ❌ **"Express permission must be sought from NAAIM for commercial purposes"** (verified on page) | MED (~0.3). Active-manager equity exposure. | 2 | ❌ licensing blocker |
| 8 | **Exchange short volume (NYSE/Nasdaq TRF)** | Subsumed by FINRA consolidated short-volume (#2). Direct exchange feeds often paid. | n/a | Daily | Mixed; exchange terms vary | Same as #2 (overlaps) | 2-3 | ↪ use #2 instead |

---

## Detailed notes (verified evidence)

### 1. CFTC COT — ⭐ CROWN JEWEL (verified)
- **Verified live:** fetched `https://www.cftc.gov/files/dea/history/deacot1986.zip` → **HTTP 200, `application/zip`, contains `Annual.TXT`**. History to **1986** confirmed for the legacy report.
- Disaggregated futures-only & combined + Traders-in-Financial-Futures (TFF) reports confirmed by year on the Historical Compressed index (2006/2009→present, plus a 2006-2016 bundle).
- **Cadence (from CFTC FAQ, verified):** report = **Tuesday close**, published **Friday 3:30pm ET**. → **fixed 3-day reporting lag.** This is the signal-staleness fact to bake into any backtest: position as-of Tue is only actionable from Fri.
- **Reports to use for equities/our universe:** *Traders in Financial Futures (TFF)* covers E-mini S&P 500, Nasdaq-100, etc. — directly maps to our SPY/QQQ-centric universe via index futures positioning (dealer/asset-manager/leveraged-funds/other-reportables breakdown).
- **Orthogonality:** futures *positioning levels & changes* (net non-commercial / leveraged-fund net) are a classic contrarian/crowding signal, not a price re-feed. Realistic |corr| to OHLCV ~0.1-0.25. This is exactly the "new input class" the mission wants.
- **Licensing:** US government work → public domain. No use restriction. ✅ commercial OK.
- **Ingest:** annual ZIP → fixed-width/CSV TXT, stable column layout. Main work is contract-code→symbol mapping and aligning Tue snapshot to a tradeable Fri+ timestamp. Ease **2**.
- **History coverage vs required regimes:** 2008 ✅ (1986 start), 2020 ✅, 2022 ✅. **Best regime coverage in this entire class.**

### 2. FINRA daily short-sale volume — ⭐ TOP PICK (verified)
- **Verified live:** `https://cdn.finra.org/equity/regsho/daily/CNMSshvol20260603.txt` → **HTTP 200**, clean pipe-delimited: `Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market`. Per-symbol daily short vs total volume on the consolidated tape.
- **History probe (verified via curl HTTP codes):** 2026-06 ✅, 2025-06 ✅, 2020-06 ✅, **2019-01-02 ✅ but 2018-01-02 ✗(403), 2017 ✗, 2016 ✗.** → **archive starts ~2019.** Covers **2020 + 2022** bear regimes; **does NOT cover 2008.** Honest limitation: ~7yr history, fine for recent-regime work, blind to GFC.
- **Cadence:** daily, next-business-day availability. No auth, no key, no rate-limit hit observed.
- **Orthogonality:** short-volume ratio (ShortVolume/TotalVolume) per name is a flow/positioning proxy weakly correlated with price; daily granularity makes it more actionable than bi-monthly short interest. |corr| ~0.2.
- **Licensing:** FINRA publishes this as regulatory transparency data, free bulk. No personal-use-only blocker found on the file route.
- **Ingest:** **1** — one CSV per trading day, trivial parse, symbol already plain ticker.
- **Caveat:** short *volume* ≠ short *interest* (it's executions flagged short intraday, includes market-maker hedging churn). Useful but noisy; normalize per-name.

### 3. FINRA short-interest (Rule 4560) — strong, coarse cadence (partially verified)
- FINRA collects member short-interest **twice monthly** (settlement mid-month & month-end) and publishes ~8-9 calendar days later. Long history.
- **Access caveat:** FINRA's main `finra.org` pages are Cloudflare bot-walled (verified: 403 "Just a moment..."). The bulk short-interest file is downloadable but the exact CDN path/format I could not confirm by probe this session (my guessed `/equity/consolidated/shrt/` path 403'd — **not** the real URL). **Mark URL as TO-CONFIRM at ingest;** the dataset itself is well-established and free.
- **Orthogonality:** HIGH (aggregate short positioning per name = genuine crowding). **Cadence weakness:** only 2 obs/month + ~9-day lag → slow-moving signal, better as a regime/overlay feature than a fast trade trigger.

### 4. SEC Form 4 insider transactions — timelier than 13F (verified API works)
- **Verified live:** `https://data.sec.gov/submissions/CIK0000320193.json` (Apple) → **HTTP 200 JSON**, `insiderTransactionForIssuerExists: 1`, full filing index with accession numbers. This is the correct free EDGAR route.
- **Cadence:** insiders must file Form 4 within **2 business days** of a transaction → near-real-time, far timelier than 13F.
- **History:** Form 4 electronic filing mandatory since **2003**; covers 2008/2020/2022. ✅
- **Throttle (verified):** after a few rapid hits, `www.sec.gov` returned **"Request Rate Threshold Exceeded"**. EDGAR enforces Fair Access — **must send a descriptive `User-Agent` and pace (<10 req/s, ideally far less).** Operational, not a blocker.
- **Orthogonality:** insider net buy/sell is a known orthogonal signal (insiders trade on private info, weakly price-correlated). |corr| ~0.1-0.2.
- **Ingest:** **3** — XML form parsing, CIK→ticker mapping, dedup of derivative vs non-derivative tables, throttle-aware crawling. More plumbing than COT.

### 5. AAII Sentiment Survey — secondary (verified table)
- **Verified live:** `aaii.com/sentimentsurvey/sent_results` → **HTTP 200**, weekly Bullish/Neutral/Bearish % table (e.g., Jun 3: 36.3/26.7/37.0). Weekly, Thursday release.
- **History:** survey runs since **1987** (covers all regimes) but the **full downloadable Excel history is commonly behind AAII membership**; the public page shows a rolling recent window. Backfill of full 1987→ may require member access or piecing together. Mark backfill as **partly gated**.
- **Orthogonality:** retail sentiment, contrarian/mean-reverting vs price; |corr| ~0.25-0.4 (higher than COT — it co-moves more with recent returns). Useful as overlay, weaker standalone.
- **Licensing:** intended for tracking/research; redistribution rights unclear → fine for private paper use, verify before any commercial redistribution.

### 6. SEC 13F — ⚠️ weak (free but structurally limited)
- Free via EDGAR (DERA structured 13F data sets, 2013→; raw filings older). Public domain.
- **Two killer limitations:** (a) **45-day reporting lag** after quarter-end → positioning is up to ~4.5 months stale by the time you'd trade it; (b) **longs-only** — 13F reports long equity/options positions, **no short positions, no cash** → you see half the book. For a *positioning/crowding* signal these are severe. Down-ranked despite zero cost.
- Ingest **4** (13F security-list mapping, manager entity resolution, amendment handling).

### 7. NAAIM Exposure Index — ❌ LICENSING BLOCKER (verified)
- **Verified live:** page states *"NAAIM publishes this data for use in tracking only and reserves the right to the use and trademarks... **Express permission must be sought from NAAIM for use of this data for commercial purposes.**"*
- Weekly (Wed poll), -200%/+200% active-manager equity exposure, 2006→. Good signal, but the commercial-use restriction makes it unsafe for our potentially-commercial context. Free to *view*, not free to *use commercially*. ❌

### 8. Exchange short volume (NYSE/Nasdaq) — redundant
- Exchange-direct short-volume feeds are largely paid or terms-restricted; the **consolidated FINRA file (#2) already aggregates TRF + exchange short volume** for free. Use #2; no separate ingest warranted.

---

## Recommendation to parent

**Build order if pursuing this class:**
1. **COT (TFF report)** first — best history (1986), public domain, weekly, directly maps to SPY/QQQ via index-futures positioning. Highest EV. Treat the **3-day Tue→Fri lag** correctly (signal as-of Tue, tradeable Fri+).
2. **FINRA daily short-volume** second — trivial daily CSV, orthogonal flow, but accept **~2019-start history** (no 2008; OK for 2020/2022 regime work).
3. **Form 4** if a third, timelier name-level signal is wanted — but budget for EDGAR throttle pacing + XML parsing.

**Avoid / down-rank:** 13F (lag+longs-only), NAAIM (commercial-use blocker). AAII only as a cheap weekly overlay.

**Universal lag caveat for the whole class:** positioning data is *inherently lagged* (COT 3d, short-interest ~9d, 13F 45d). Stale positioning = weak/decayed signal. The two that survive this best are **COT** (only 3d, deep history) and **daily short-volume** (next-day). Those are the only two I'd green-light for serious backtesting from this class.
