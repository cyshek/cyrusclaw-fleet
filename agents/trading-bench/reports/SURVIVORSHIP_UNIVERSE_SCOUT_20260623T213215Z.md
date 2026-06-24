# Survivorship-Clean US Equity Universe — Scout Report

**UTC stamp:** 20260623T213215Z · **Box:** Linux datacenter VM (bot-walled IP) · **Mode:** read-only recon, no signups, no spend
**Confidence:** High on EODHD/Norgate/Wikipedia/EDGAR (live-verified). Medium on Sharadar pricing (API verified live; $ figure is JS-walled, taken from known recent pricing).

---

## 1. TOP RECOMMENDATION (one line)

**Buy EODHD "All-In-One" ($99.99/mo, or $59.99/mo "All World Extended" if EOD+delisted+fundamentals is enough) — it's the only candidate that delivers delisting history + delisting-adjusted prices + 30+yr depth AND is API-native + verified reachable from this Linux datacenter box.** Norgate is cheaper (~$52/mo) and arguably cleaner on *index-constituent* history, but it's **Windows-desktop-only with no API → infeasible on this box** without standing up a Windows VM.

**If you want to spend $0 first:** a **partial** bootstrap (Wikipedia S&P 500 change-log for PIT membership 1994→now + EDGAR for the dead-ticker filer list) is viable for *membership*, but **the delisted-names' PRICES are the hard $0 dealbreaker** — no free source serves them. A momentum PoC at $0 is **not** honestly doable.

---

## 2. COMPARISON TABLE

| Source | Delisting history? | PIT constituent history? | Delisting-adj prices? | Depth (2008/2020/2022?) | Cost | License (our use) | Feasible from THIS box? | Ingest effort |
|---|---|---|---|---|---|---|---|---|
| **EODHD** | ✅ delisted tickers + `delisted=1` symbol list | ⚠️ no native index-membership history (build from prices+mktcap, or Wiki) | ✅ "Delisted Data" + adjusted_close, 30+yr | ✅ US "from the beginning" (Ford 1972; AAPL 1980 verified) | **$19.99 / $29.99 / $59.99 / $99.99 /mo** (annual ~5/6 of that) | **Personal use** OK; commercial = quote | ✅ **VERIFIED** — DEMO key returned full AAPL hist from this IP | Low–Med (REST+CSV, our `*_cache.py` pattern) |
| **Norgate** | ✅ delisted (suffix `-YYYYMM`), Plat/Diamond | ✅✅ **best** — US Historical Index Constituents (S&P, Russell) | ✅ adjusted, hist back 10–37yr by tier | ✅ deep | **Plat $346.50/6mo or $630/yr (~$52.50/mo)**; Diamond $433.50/6mo, $787.50/yr | Prosumer, non-cancellable, 6/12mo only | ❌ **BLOCKER** — Windows-only proprietary DB, **"No generic API"**, NQ/Amibroker/Python-on-Windows only | High (needs a Windows VM + scheduled export bridge to Linux) |
| **Sharadar** (Nasdaq Data Link SEP/SF1/TICKERS/ACTIONS) | ✅ TICKERS incl. delisted + ACTIONS | ⚠️ partial (SP500 membership table exists; not full Russell PIT) | ✅ SEP dividend/split-adj; survivorship-bias-free by design | ✅ SEP to ~1998, SF1 to ~1998 | ~**$50/mo SEP + ~$50/mo SF1** (≈$100/mo for both; was annual-ish) — *JS-walled, verify on signup* | Personal/research tier | ✅ **VERIFIED** — datatables API returns JSON schema+rows from this IP | Low (clean datatables, pandas-native) |
| **Tiingo** | ⚠️ retains some delisted, inconsistent | ❌ | ⚠️ adj prices yes, delisted coverage thin | partial | ~$10–30/mo paid | Personal | ✅ (free ~50 sym/hr known) | Med, but coverage gap on dead names |
| **FMP** | ✅ `delisted-companies` endpoint exists | ❌ | ⚠️ prices exist; delisting-return quality unproven | claims long hist | ~$19–29/mo+ | Personal/commercial tiers | ✅ reachable (401 w/o key) | Med; quality risk |
| **CRSP** | ✅✅ gold standard (delisting *returns*) | ✅✅ | ✅✅ | ✅ 1925+ | **WRDS subscription, institution-gated; ~$$$ thousands/yr, academic/enterprise only** | Academic/enterprise; **no individual tier** | ❌ no individual access | N/A |
| **Wikipedia S&P500 changes** | ⚠️ membership removals only (proxy) | ✅ **S&P 500 only**, reconstructable 1994→now | ❌ no prices | membership only | **$0** | CC-BY-SA | ✅ **VERIFIED** (374 dated change-rows, parseable) | Low (one-time scrape→PIT table) |
| **EDGAR** (have it) | ⚠️ filing-cessation = weak delisting proxy | ❌ no clean membership | ❌ no prices | filings ~2009+ (XBRL) | $0 | Public domain | ✅ verified | already cached |

---

## 3. WIRING SKETCH — top 1–2 candidates

### (A) EODHD — recommended, Linux/API-native
- **Endpoints (all REST, CSV/JSON, work from this box):**
  - `exchange-symbol-list/US?delisted=1` → full delisted-ticker roster (the delisting-history spine).
  - `eod/{TICKER}.US?from=...&fmt=csv` → split+div **adjusted_close** incl. dead names (the delisting-adj price piece). DEMO proved AAPL→1980 live.
  - `eod-bulk-last-day/US?date=D` → one call backfills an entire trading day across all tickers (efficient historical pull; avoids per-symbol loops/429s).
  - `div`/`splits` endpoints for corporate actions.
- **Build the PIT universe table:** for each month-end D, take all symbols (live+delisted) trading on D, compute mktcap/ADV proxy from price×shares (or EODHD fundamentals shares), keep top-N by liquidity → that's the survivorship-clean investable set on D (dead names included, scored -100% when they go to zero). Index-membership history isn't native → either (i) approximate "liquid 500/1000" by mktcap, or (ii) overlay the free Wikipedia S&P 500 change-log for exact S&P membership.
- **Eng effort:** ~1–2 days. New `runner/eodhd_cache.py` mirroring existing `cboe_cache.py`/`fred_cache.py` (keyed REST→on-disk parquet/csv in `data_cache/eodhd/`), plus a `build_pit_universe.py` that emits `universe_membership(date, ticker, in_universe, mktcap_rank, delist_date, delist_return)`.

### (B) Sharadar (Nasdaq Data Link) — cleanest data shape, API-native, slightly pricier
- **Endpoints (datatables, verified reachable):** `SHARADAR/TICKERS` (incl. delisted + `firstpricedate`/`lastpricedate`), `SHARADAR/SEP` (adj OHLCV), `SHARADAR/ACTIONS` (delistings, M&A), `SHARADAR/SF1` (PIT fundamentals). Python pkg `nasdaq-data-link` (`get_table`) on Linux — confirmed JSON returns from this IP.
- **PIT universe:** TICKERS gives `lastpricedate` → delisting spine; SEP gives the price incl. final value; the SP500 membership table (Sharadar publishes one) gives exact index PIT. Survivorship-bias-free is the explicit product design.
- **Eng effort:** ~1 day (datatables are pandas-native; less parsing than EODHD CSV).
- **Catch:** need SEP **and** SF1 for prices+fundamentals (≈$100/mo combined); pricing is behind a JS wall so confirm exact figure at signup.

---

## 4. FREE-ANGLE VERDICT ($0 bootstrap)

- **Membership: YES, partial.** Wikipedia S&P 500 change-log is live-parseable from this box (374 dated add/remove rows back to **Sep 1994**) → reconstruct exact S&P 500 PIT membership 1994→today. EDGAR gives the historical filer universe + filing-cessation as a weak delisting proxy. Both $0, both verified.
- **Prices of dead names: NO — hard dealbreaker.** Yahoo v8 **purges** delisted tickers (already known). No free source serves delisting-adjusted prices for the dead names. Without those, a stock that went to zero silently vanishes = the exact survivorship bias we're trying to kill.
- **Momentum PoC at $0?** **No.** You'd have correct membership but missing returns for everything that later died — which *reintroduces* survivorship bias into the PoC. A $0 PoC would be self-deceiving. The cheapest *honest* PoC needs one paid price feed (EODHD $19.99/mo gets you delisted EOD).

---

## 5. COST–BENEFIT (decision for Cyrus — paid-data signup = his call)

- **What it unlocks:** a survivorship-clean universe is the single binding constraint that killed **all 4 lanes today** (PIT-value, BAB, xsec-momentum, PEAD). One paid feed resurrects all four at once — this is the highest-leverage ~$20–100/mo we could spend on this project.
- **Cheapest credible honest option:** **EODHD $19.99/mo** (delisted EOD + adj prices + 30yr) is enough to re-test momentum/BAB/PEAD with dead names included. Step up to **$59.99–99.99/mo** if you also want EODHD fundamentals for the value/PEAD lanes in one vendor.
- **Norgate ($52/mo)** is data-superior on index-constituent history but **infeasible here without a Windows VM** — only worth it if we accept standing up + maintaining a Windows export bridge. Not recommended as first move.
- **CRSP** is the gold standard but **institution-gated, no individual access** → off the table unless via a university affiliation.
- **My recommendation:** start with **EODHD $19.99/mo** (one month, cancel anytime) → wire `eodhd_cache.py` → rebuild the universe → re-run the momentum lane as the honest PoC. If the lanes show real (non-survivorship) edge, step up the EODHD tier for fundamentals. Total downside risk: $20 and ~2 eng-days.

---

### Feasibility footnotes (tested, not assumed)
- EODHD DEMO key → full AAPL EOD from 1980 **returned 200 from this IP** ✅ (no-key list endpoints 403, expected).
- Sharadar `datatables/SHARADAR/{SEP,TICKERS}` → **JSON schema + rows from this IP** ✅ (only the marketing/pricing page is JS-rendered).
- FMP `delisted-companies` → reachable (401 invalid-key) ✅.
- Norgate → confirmed Windows-only, proprietary local DB, **"No generic API"** (their FAQ), 6/12-mo non-cancellable subs ❌ for Linux.
- Wikipedia S&P 500 changes → 374 dated change-rows parseable ✅. EDGAR `company_tickers.json` → 200, 798 KB ✅.
