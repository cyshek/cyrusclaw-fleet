# DATA SCOUT — BUILD-READY SPEC for HIGH-ranked Alt-Signal Sources
**Scout #2 · 2026-06-08 · RESEARCH ONLY (no code/cron/orders) · every claim live-tested from THIS datacenter IP unless flagged**

Turns scout #1's shortlist (`reports/DATA_SCOUT_ALTSIGNAL_20260608.md`) into ingest-ready specs.
Each block = endpoint + schema + earliest date + cadence/LAG + live IP-reachability test + derived-signal + anti-lookahead note.
**Key disk fact confirmed:** `FRED_API_KEY` (32-char) IS present in `.env`, and the **keyed** `api.stlouisfed.org/fred/series/observations` endpoint works perfectly from our VM (WALCL returned 1225 weekly obs to 2026-06-03). `fredgraph.csv` remains the only broken FRED path — use the keyed JSON API.

> **⚠️ TWO scout-#1 claims are now CORRECTED by live tests (read before building):**
> 1. **FINRA short-vol does NOT reach 2009 from `cdn.finra.org`.** That CDN serves only a **rolling ~recent window**: live-confirmed **2019-01-02 = 200**, but **2018-01-02 / 2016 / 2015 / 2013 / 2010 / 2009-08-03 all = 403 AccessDenied.** So keyless reach from our IP = **2019-01 → present** (covers 2020 + 2022 bears; **misses 2008 AND the GFC tail entirely**). Deep 2009→2018 backfill needs a mirror (see block 1).
> 2. **Put/Call via FRED is DEAD.** The CBOE FRED release (rid=200) = 21 series, **all volatility indices, ZERO put/call.** `PCALL`/`CBOEPUTCALL`/`PUTCALL` all 400 "does not exist." CBOE delisted P/C from FRED. And `cdn.cboe.com` P/C CSV = **403** from our IP. P/C is now a LOW-priority, hard-to-source item — demoted (see block 5).

---

## RANKED BY BUILD PRIORITY

### ⭐ #1 — NY Fed SOMA (Fed balance-sheet / QE-QT liquidity) — CONFIRMED, build FIRST
- **Endpoint (keyless JSON):** `https://markets.newyorkfed.org/api/soma/summary.json` (full history, one pull). Companion: `/api/soma/asofdates/latest.json`, `/api/soma/asofdates/list.json`, `/api/soma/summary/asof/{YYYY-MM-DD}.json`.
- **Schema (per record in `soma.summary[]`):** `asOfDate` (YYYY-MM-DD), `total`, `notesbonds`, `bills`, `tips`, `tipsInflationCompensation`, `mbs`, `cmbs`, `agencies`, `frn` — all USD **as strings** (e.g. `"650982322000.00"`); parse to float. `frn` can be `""`.
- **Earliest date:** **2003-07-09** (live first record). Covers 2008 QE1 → present in full.
- **Cadence + LAG:** **Weekly, Wednesday level.** Live: latest `asOfDate` = **2026-06-03** (a Wed), pulled on Sun 2026-06-08 → ~publication lag of a few days after each Wed. Anti-lookahead: a given Wed's holdings are not safely "known" until ~the following Thu/Fri; **lag the series ~1 week** for point-in-time backtests (don't index Wed data to Wed close).
- **Live IP test:** ✅ 200, `{"asOfDate":"2003-07-09","total":"650982322000.00",...}`; latest asof 2026-06-03.
- **License:** Public Fed data, free programmatic use.
- **Derived signal:** WoW Δ in `total` (and `mbs` separately) = liquidity injection/drain. Sign + 4/13-wk slope of Δtotal → slow risk-on/off tide. Normalize by level (pct change) for cross-era comparability (balance sheet went $0.65T→$9T→$6.7T).
- **Why first:** cleanest JSON, no key, one-shot full history, deepest clean coverage, zero friction.

### ⭐ #2 — Treasury.gov Daily Par Yield Curve (full 1M→30Y) — CONFIRMED, build SECOND
- **Endpoint (keyless CSV, one year/call):** `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{YYYY}/all?type=daily_treasury_yield_curve&field_tdr_date_value={YYYY}&page&_format=csv`
- **Schema:** header `Date,"1 Mo","2 Mo","3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"`. `Date` = **MM/DD/YYYY**, rows **descending** (newest first) within the year. Values = par yield in **percent** (e.g. `0.93` = 0.93%). Note: tenor set varies by era — `2 Mo` only exists from 2018-10, `4 Mo` added 2022-10, `30 Yr` had a 2002–2006 gap; **handle missing columns per year**.
- **Earliest date:** full par-yield curve from **1990** (≥2008 trivially).
- **Cadence + LAG:** **Daily (business days)**, posted **same day ~by 18:00 ET** (Treasury publishes that afternoon). Minimal lag → safe to index to same-day close. Weekends/holidays simply absent.
- **Live IP test:** ✅ 200, `12/31/2020,0.08,0.08,0.09,...,0.93,1.45,1.65` (clean full 2020 file).
- **License:** Public, free.
- **Derived signal:** curve shape — 2s10s (`10 Yr`−`2 Yr`), 3m10y (`10 Yr`−`3 Mo`), inversion flag, bear-steepening/twist (Δslope). Inversion → recession-risk gate; un-inversion from inverted historically precedes equity stress. Complements FRED single spreads with the *full tenor set in one pull*.
- **Anti-lookahead:** same-day OK; just confirm the day's file exists before using (no T+1 needed).

### ⭐ #3 — FINRA Daily Short-Volume (RegSHO consolidated) — CONFIRMED (2019+), build THIRD
- **Endpoint (keyless flat file, one trading day/file):** `https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt` (consolidated NMS). Venue variants exist: `FNYXshvol` (NYSE TRF), `FNQCshvol`, `FNSQshvol` (Nasdaq TRFs) — use **CNMS** (consolidated) for a market-wide signal.
- **Schema (pipe-delimited, header present):** `Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market`. `Date`=YYYYMMDD; `Symbol`=ticker; volumes are shares (can be fractional, e.g. `448127.310887`); `Market`=venue codes (`B,Q,N`). **NOTE the real column order**: ShortExemptVolume is col 4, TotalVolume col 5 (scout #1's sample row had cols transposed — trust this header). Last line of each file is a trailer/footer row — drop non-numeric `Date`.
- **Earliest date REACHABLE from our IP:** **2019-01-02** (live 200). The CDN is a **rolling window** — 2018-01-02 and all earlier dates = **403 AccessDenied**. *Full* dataset (every ticker daily) exists **2009-08-01→present** but only via backfill mirror, NOT this CDN from our IP.
  - **Backfill path for 2009→2018:** GitHub `arthurwu1227/FINRA-shortsale-data` (every ticker daily 2009-08-01→2023, ~1.7GB — heavy, only pull if pre-2019 history proves necessary). Otherwise accept the **2019-01 floor** (still covers 2020 + 2022 bear regimes).
- **Cadence + LAG:** **Daily, T+1.** File for trading day D posts the **next business day** (~by 18:00 ET D+1). Weekends/holidays = **no file (404/403)** — ingest must skip-and-continue, never assume contiguous dates. Anti-lookahead: short-vol for day D is not knowable until D+1, so **lag 1 trading day** (use D's short-ratio as a signal for D+1 onward, never same-day).
- **Live IP test:** ✅ 200 for 2026-06-05, 2025-01-02, 2024-01-02, 2023-01-03, 2020-01-02, 2019-01-02. ❌ 403 for 2018-01-02, 2016, 2015, 2013, 2010, 2009-08-03.
- **License:** Public regulatory disclosure, free flat files; personal/research fine. Caveat (per FINRA/TrendSpider): this is **off-exchange (TRF) reported volume only**, NOT total consolidated tape — do **not** compute `ShortVolume/exchange-total` as a true short-interest %; treat the ratio as a *relative tape-composition* gauge.
- **Derived market-level short-pressure signal:** for each day, take the universe (or a liquid subset: SPY/QQQ/IWM + S&P 500 names), compute per-ticker `r_i = ShortVolume/TotalVolume`, then aggregate to a market signal three ways: (a) **volume-weighted mean ratio** `Σ ShortVol / Σ TotalVol` (one robust market short-pressure number), (b) **breadth-of-shorting** = % of names with `r_i` above its own trailing median (cross-sectional crowding), (c) SPY/QQQ ETF own ratio as a clean index-level proxy. Elevated/ rising aggregate ratio = defensive/fear tape; extreme spikes = potential squeeze/mean-revert fuel. This is the **one genuinely novel DAILY orthogonal lane** on the list.

### #4 — AAII Investor Sentiment (contrarian gate) — REACHABLE but STALE-mirror problem, build FOURTH (gate only)
- **The honest situation:** the official `aaii.com` survey is **Cloudflare-403** from our IP ("Just a moment…"), so we depend on GitHub mirrors — and **every free mirror I found is FROZEN/abandoned:**
  - `psinopoli/AAII-Sentiment/main/AAII_SENTIMENT_CSV.csv` — **now header-only (`Date,Bullish,Neutral,Bearish`, 0 data rows)**: effectively EMPTIED. scout #1's recommended mirror is **dead**. Do not use.
  - `hackingthemarkets/sentiment-fear-and-greed/master/datasets/aaii-sentiment.csv` — ✅ 200, **richer schema** (`Date,Bullish,Neutral,Bearish,Total,Bullish 8-Week Mov Avg,Bull-Bear Spread,Bullish Average,Bullish Average ± St.Dev,S&P 500 Weekly High/Low/Close`), `Date`=YYYY-MM-DD, ratios as decimals (0.32 = 32%). BUT newest row = **2020-09-17** → ~5.7 yr stale.
  - `Akashjalil22/Investor-Sentiments/main/AAII-AAII_SENTIMENT.csv` — ✅ 200, same rich schema, newest row = **2021-04-01** → ~5 yr stale.
- **Earliest date:** 1987-07 (the survey's full history is in the live mirrors — covers 1987/2000/2008/2020). History depth is fine; **freshness is the blocker.**
- **Cadence + LAG (when fresh):** weekly, survey runs Thu→Wed, **published Thursdays**; treat the weekly value as known end-of-that-Thursday. As a contrarian *gate* the weekly cadence is fine.
- **License:** AAII data © AAII (members); mirrors are 3rd-party. For private paper-research OK; **don't redistribute.**
- **Recommendation:** **Backtest-only, as a gate.** For *historical* 2008→2021 backtests the stale mirror (Akashjalil22, to 2021-04) is usable. For **live** trading the only fresh source is the Cloudflare-walled aaii.com — would need a residential proxy or a manual weekly paste; do NOT promise live AAII from this IP. Derived signal: bull-bear spread z-score; extreme bearishness (spread < −1σ) → forward risk-on tilt gate.
- **Live IP test:** psinopoli ✅200-but-empty; hackingthemarkets ✅200 (tail 2020-09); Akashjalil22 ✅200 (tail 2021-04); aaii.com ❌403 Cloudflare.

### #5 — Put/Call ratio + Margin debt — DEMOTED (both blocked from our IP; do NOT build now)
- **Put/Call — scout #1's "route via FRED" is WRONG (live-disproven):**
  - FRED CBOE release (rid=200) = **21 series, ALL volatility indices, ZERO put/call** (live-enumerated). `PCALL/CBOEPUTCALL/PUTCALL` = 400 "does not exist." **CBOE permanently delisted P/C from FRED.**
  - `cdn.cboe.com/api/global/us_indices/daily_prices/total_put_call.csv` = **403 AccessDenied** from our IP (CBOE S3 bot-wall).
  - **Verdict:** no clean keyless P/C path from this IP. Park it. (If pursued later: CBOE DataShop is paid; a maintained P/C GitHub mirror would need a focused search once the search backend is healthy — search was down this session.)
- **Margin debt — also NOT in FRED + FINRA site bot-walled:**
  - FRED "margin debt" search = only Bankrate-poll junk; **no FINRA margin-debit series in FRED.**
  - `finra.org/.../margin-statistics` = **Cloudflare-403** from our IP (note: `cdn.finra.org` flat files work, but margin debt is NOT published as a cdn flat file — it's HTML/xls behind the walled `finra.org`).
  - **Verdict:** monthly, coarse, AND blocked → lowest priority. Defer; revisit with a mirror search later.
- **Net:** **do not spend build effort on #5 now.** The orthogonal-sentiment role is better filled by AAII (gate) + the new EPU find below.

---

## NEW orthogonal sources found this session (not in scout #1) — all via the working keyed FRED API
| Series ID | What | Start | Freq | Note |
|-----------|------|-------|------|------|
| **WALCL** | Fed total assets (H.4.1), Wed level | **2002-12-18** | Weekly | ✅live, latest 2026-06-03 = $6.71T. **Cleaner Fed-liquidity series than SOMA** (keyed FRED, full asset base). Build alongside/instead-of SOMA; cross-check the two. Lag ~1wk (Thu release). |
| **USEPUINDXD** | Economic Policy Uncertainty Index (US), **DAILY** | **1985-01-01** | Daily | ✅live, 15,130 obs. Deep daily orthogonal-to-price stress proxy; spikes lead/coincide with risk-off. Strong new gate candidate. |
| **NFCI** | Chicago Fed National Financial Conditions | 1971-01-08 | Weekly | ✅live (likely already used per scout #1). Broad financial-conditions tide. |
| (VIX family) | VIXCLS/VXNCLS/RVXCLS… on FRED rid=200 | 1990+ | Daily | Available but **price-vol correlated** — likely already in the 11 capped lanes; not "orthogonal." |

> EPU (`USEPUINDXD`) is the standout new find: **daily, to 1985, keyed-FRED-reachable, orthogonal to price.** Worth slotting in as a daily gate next to short-vol. WALCL is the recommended Fed-liquidity workhorse (beats SOMA on access cleanliness, though SOMA breaks out MBS).

---

## RECOMMENDED INGEST ORDER (build in this sequence)
1. **NY Fed SOMA** (`summary.json`) — keyless, one-shot full history to 2003, cleanest. ✅
2. **WALCL via keyed FRED** — Fed balance sheet to 2002, trivial once a FRED client exists; cross-checks SOMA. ✅ (build the reusable keyed-FRED client HERE — it unlocks EPU/NFCI too.)
3. **Treasury daily yield curve** — keyless CSV, year-at-a-time loop to 1990; gives curve-shape regime layer. ✅
4. **FINRA daily short-volume** (CNMS) — the novel daily lane; loop `CNMSshvol{YYYYMMDD}.txt` **2019→present** (skip 404/403 non-trading days; lag T+1). Accept 2019 floor unless a backtest demands pre-2019 (then pull the arthurwu1227 mirror). ✅
5. **USEPUINDXD (EPU) via FRED** — free daily orthogonal gate, near-zero marginal effort once FRED client built. ✅
6. **AAII** — backfill the static historical CSV (Akashjalil22 mirror, to 2021-04) for **backtest-only** contrarian gating; flag the live-freshness gap honestly. ⚠️
7. **(defer) Put/Call + Margin debt** — both blocked from our IP; revisit only with a dedicated mirror-search once the web_search backend is healthy. ⛔

**Build the keyed-FRED client at step 2** — it's the highest-leverage piece (unlocks WALCL + EPU + NFCI + any future FRED series in one module). SOMA + Treasury are standalone keyless fetchers. Short-vol is the only multi-file looped ingest.

---
*Reachability summary (this IP, this session): SOMA ✅ · Treasury ✅ · FINRA short-vol ✅(2019+ only) · keyed-FRED/WALCL/EPU/NFCI ✅ · AAII ✅-but-stale-mirrors · P/C ❌(FRED-delisted + CBOE-403) · margin debt ❌(not-in-FRED + finra.org Cloudflare-403). web_search backend went down mid-session (SearXNG misconfig) — all specs above were confirmed via direct web_fetch/keyed-API tests, not search.*
