# DATA SCOUT #2 — Options Chains + Implied Vol + VIX-Complex Data Sources
**Date:** 2026-06-08 · **Scout:** data_scout_options (subagent) · **Status:** RESEARCH ONLY (no code/orders/signups)
**Mission:** Find data for two Natenberg-derived backtest ideas — (1) regime-gated defined-risk credit put-spreads on SPY/QQQ, (2) free VIX-complex regime overlay on a long-SPX core. Both blocked on: where do we get (a) historical+current SPY/QQQ option chains with IV, and (b) the VIX-complex index time series — free or via the Alpaca keys we already hold.

All endpoints below were verified live with `web_fetch`/`curl` on 2026-06-08 except where explicitly marked "not live-tested." Alpaca capability was read from docs only (per instructions — no live key calls made).

---

## (A) HEADLINE VERDICT — Can we get SPY/QQQ option chains + IV cheaply, and how far back?

**Short answer: YES for *current/live* chains with IV+greeks (free, multiple ways including our existing Alpaca keys). NO for *deep historical* option chains across regimes (2008/2020) without paying real money — the free/cheap option-data world only reaches back to ~Feb 2024 at best.**

Three hard facts:

1. **Alpaca (we already have keys) serves option chains, snapshots, greeks AND implied vol on the FREE "Basic" plan** — but via the *Indicative* feed (a free derivative of OPRA: indicative quotes, trades delayed 15 min), and **historical option data only goes back to February 2024.** Free tier = 200 API calls/min, "latest 15 minutes" restriction on real-time. So Alpaca covers our *live going-forward* chain+IV needs at $0, but cannot give us 2008/2020-era option chains.
   - Source (verified): `https://docs.alpaca.markets/us/docs/historical-option-data` → *"Currently we only offer historical option data since February 2024."* + Indicative feed = free derivative of OPRA, trades delayed 15 min.
   - Pricing (verified): `https://docs.alpaca.markets/us/docs/about-market-data-api` → Basic plan **Free**, options real-time coverage = **Indicative Pricing Feed**, 200 historical API calls/min, websocket 200 quotes. Algo Trader Plus ($99/mo) = full OPRA feed, 10,000 calls/min, no 15-min restriction. **Both plans' historical timeframe is stated "Since 2016" for the table, but the options-specific doc overrides this: option data only since Feb 2024.**

2. **Every other free/cheap source has the same wall:** Polygon free tier = 2-yr history + 5 calls/min (reaches ~2024). Tradier sandbox = live/delayed chains WITH greeks+IV (courtesy ORATS) but not deep history. Yahoo/yfinance = *current* chains only, no history at all. True historical option chains with IV back to 2008 (CBOE DataShop, ORATS history, OptionMetrics) are **all paid**, and not cheap (typically $thousands, or $hundreds/mo).

3. **Therefore the realistic plan for idea (1) is forward-only collection, NOT a deep historical backtest.** We cannot properly backtest a SPY/QQQ credit-put-spread strategy across the 2008/2020 regimes on free data. We CAN: (a) start collecting live SPY/QQQ chains+IV daily *now* from Alpaca (free, we have keys) to build our own history going forward, and/or (b) backtest the *signal/regime* logic on the VIX-complex (which IS free back to 1990 — see section B) while *modeling* option premiums from a Black-Scholes/IV proxy rather than real historical quotes. Honest recommendation in section D.

**One nuance worth flagging to the requester:** for a put-spread *vol-risk-premium* study, you don't strictly need a full historical chain — you need (i) the underlying price path, (ii) a reasonable IV at the strikes you'd sell, and (iii) realistic fills. (i) is free+deep (SPY/QQQ daily bars to 1993/1999). (ii) can be *proxied* from VIX (for SPY) and a QQQ-IV proxy back to 2008+ — VIX is literally 30-day SPX IV. So a **modeled-premium backtest of the credit-put-spread idea is feasible on free data back ~15+ years**; only a *quote-accurate* backtest needs paid chains.

---

## (B) VIX-COMPLEX DATA PLAN — exact free URLs + earliest dates (THE STRONG RESULT)

**This is fully solved, free, deep, and current.** CBOE publishes the entire VIX complex as daily-updating CSVs on its CDN, no auth, no key, no rate limit of note. All five URLs below were fetched live 2026-06-08 and are **current through 2026-06-05** (i.e. actively maintained, ~1 trading day lag, not stale archives).

| Index | What it is | Exact free URL (CBOE CDN, verified live) | Earliest date (verified) | Latest (verified) | Format |
|---|---|---|---|---|---|
| **VIX** | 30-day SPX implied vol | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | **1990-01-02** | 2026-06-05 | DATE,OPEN,HIGH,LOW,CLOSE |
| **VIX3M** (was VXV) | 3-month SPX implied vol → term-structure slope | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv` | **2009-09-18** | 2026-06-05 | DATE,OPEN,HIGH,LOW,CLOSE |
| **VVIX** | vol-of-VIX | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv` | **2006-03-06** | 2026-06-05 | DATE,VVIX (close only) |
| **SKEW** | CBOE SKEW (tail-risk / put skew) | `https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv` | **1990-01-02** | 2026-06-05 | DATE,SKEW (close only) |
| **VIX9D** | 9-day SPX implied vol (short end of term structure) | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX9D_History.csv` | **2011-01-04** | 2026-06-05 | DATE,OPEN,HIGH,LOW,CLOSE |

**Key term-structure note:** VIX/VIX3M slope (the core "risk-on/off" backwardation signal Natenberg-style overlays use) is computable **back to 2009-09-18** — the binding constraint is VIX3M's start. VIX itself + SKEW go to 1990. VVIX to 2006. So a full VIX-level + SKEW + VVIX overlay works back to **2006**; adding the term-structure slope narrows the common window to **Sept 2009 → present** (which still covers the 2010 flash crash, 2011 euro crisis, 2015/2018 vol spikes, 2020 COVID crash, 2022 bear — plenty of regimes).

**Evidence snippets (verified live 2026-06-08):**
- VIX first/last rows: `01/02/1990,17.24,17.24,17.24,17.24` … `06/05/2026,15.87,21.57,15.56,21.51`
- SKEW: `01/02/1990,126.09` … `06/05/2026,152.25`
- VVIX: `03/06/2006,71.73` … `06/05/2026,102.04`
- VIX3M first row: `09/18/2009,25.91,26.66,25.91,26.54`
- VIX9D first row: `01/04/2011,16.06,...`

**Access mechanics:** plain HTTPS GET, returns `text/csv`, no API key, no auth header, no documented rate limit (these are static CDN objects refreshed daily). Date format is `MM/DD/YYYY`. Just `curl`/`requests.get()` and parse. This is the cleanest data in the whole report.

**Backups (redundancy, not needed but documented):**
- **FRED** `VIXCLS` (CBOE VIX daily close, to 1990) — `https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS`. FRED also carries `VXVCLS` (VIX3M), `VXNCLS` (Nasdaq-100 VXN), `VXDCLS` (Dow), `OVXCLS` (oil), `GVZCLS` (gold). *Note: my datacenter-IP `curl` to FRED's fredgraph.csv returned empty/timed out on 2026-06-08 — likely a transient or a redirect/UA quirk from this VM, NOT a sign the series is gone; FRED VIXCLS is a long-standing, documented series. The CBOE CDN is the better primary anyway, so this is pure backup.* If FRED is needed later, the documented-stable path is the FRED API (`api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key=...&file_type=json`) with a free FRED API key.
- **Yahoo** `^VIX`, `^VIX3M`, `^VVIX`, `^SKEW` via the chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/%5EVIX`). *Tested 2026-06-08 from this VM → HTTP 429 (rate-limited / bot-walled on datacenter IP), same Google-style IP wall we already hit with YouTube.* yfinance works fine from residential IPs but is unreliable from this box. **Skip Yahoo for the VIX complex — CBOE CDN is strictly better and not IP-walled.**

---

## (C) FULL COMPARISON TABLE — every candidate source

### Option chains + IV/greeks (idea 1)

| Source | Chains? | IV? | Greeks? | Endpoint / access | Auth / cost | History depth | Rate limit | Research license | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Alpaca (Basic/free)** | ✅ | ✅ | ✅ | `data.alpaca.markets/v1beta1/options/...` (snapshots, chain, bars, trades, quotes); docs `historical-option-data`, `real-time-option-data` | We hold keys; **free**. Indicative feed (derived OPRA), trades delayed 15 min | **Only since Feb 2024**; "latest 15 min" restriction on real-time | 200 calls/min | OK for personal/paper algo use under Alpaca ToS | **HIGH** (for live/forward chains+IV at $0; we already have keys) |
| **Alpaca (Algo Trader Plus)** | ✅ | ✅ | ✅ | same endpoints, full OPRA | $99/mo | Still only since Feb 2024 for options | 10,000 calls/min | same | **SKIP for now** (no signup; doesn't fix history) |
| **Polygon.io / "Massive" (free)** | ✅ | ✅ (via indicators) | ✅ | `api.polygon.io/v3/snapshot/options/...`, aggregates | Free API key | **2 years** only (reaches ~2024) | **5 calls/min** | research-ok | **MEDIUM** (backup live source; 5/min is painful; no deep history) |
| **Tradier sandbox** | ✅ | ✅ (ORATS) | ✅ (ORATS) | `sandbox.tradier.com/v1/markets/options/chains` — *"Greek and IV data included courtesy of ORATS"* | Free sandbox token | Live/delayed, **shallow history** | modest | research-ok in sandbox | **MEDIUM** (clean greeks+IV for live collection; good redundancy to Alpaca) |
| **Yahoo / yfinance** | ✅ (current only) | partial (mid-IV) | ✖ | `query1.finance.yahoo.com/v7/finance/options/SPY` / `yfinance.Ticker("SPY").option_chain()` | none | **none** (snapshot only) | bot-walled on datacenter IP (429 from this VM) | gray-area ToS | **SKIP** (no history; IP-walled here) |
| **CBOE DataShop** | ✅ | ✅ | ✅ | datashop.cboe.com (order historical option quote files) | **Paid** (per-dataset, can be $$$) | deep (to ~2004+) | n/a (file delivery) | per-purchase license | **SKIP** (paywalled; deepest but expensive — revisit only if a quote-accurate historical backtest becomes essential) |
| **ORATS (history API)** | ✅ | ✅ | ✅ | `api.orats.io` (hist/cores, hist/strikes) | **Paid** subscription | deep historical IV+greeks (their specialty) | per-plan | research/commercial tiers | **SKIP** (best historical IV vendor, but paid — note it's the engine behind Tradier's live greeks) |
| **OptionMetrics IvyDB** | ✅ | ✅ | ✅ | academic/institutional | **Paid** (institutional, expensive) | to 1996 | n/a | academic license | **SKIP** (gold standard for academia, out of scope for retail/paper) |

### VIX-complex indices (idea 2)

| Source | VIX | VIX3M | VVIX | SKEW | VIX9D | Endpoint | Auth/cost | Earliest | Rate limit | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **CBOE CDN CSVs** | ✅1990 | ✅2009 | ✅2006 | ✅1990 | ✅2011 | `cdn.cboe.com/api/global/us_indices/daily_prices/<IDX>_History.csv` | **none / free** | see col | none of note | current to 2026-06-05 | **HIGH — primary** |
| **FRED** | ✅(VIXCLS) | ✅(VXVCLS) | ✖ | ✖ | ✖ | `fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS` or FRED API | free (API key for API) | 1990 | generous | (empty from this VM via fredgraph today — use FRED API w/ key if needed) | **MEDIUM — backup for VIX/VIX3M** |
| **Yahoo ^VIX etc.** | ✅ | ✅ | ✅ | ✅ | ✖ | `query1.finance.yahoo.com/v8/finance/chart/%5EVIX` | none | ~1990 | **429 / IP-walled here** | **SKIP from this VM** |

---

## (D) RECOMMENDED BUILD PATH — for BOTH Natenberg ideas, given data reality

### Idea (2) — VIX-complex regime overlay on long-SPX core → **BUILD NOW, fully backtestable, $0**
This is unblocked and should be the **first thing built**, because the data is free, clean, and deep:
1. Pull the 5 CBOE CDN CSVs (VIX, VIX3M, VVIX, SKEW, VIX9D) — one `requests.get` each, parse `MM/DD/YYYY`. Refresh daily (they update ~T+0/T+1).
2. Build the regime gate: VIX level (percentile/threshold), **VIX/VIX3M slope** (contango vs backwardation → risk-on/off; available 2009-09→present), SKEW (tail-risk tilt), VVIX (vol-of-vol stress). 
3. Backtest as a risk-on/off overlay on a long-SPX (SPY or ^GSPC/SPX) core: full position when risk-on, de-risked (cash/reduced) when the gate trips. Underlying SPX/SPY price history is free and deep (data scout #1's territory).
4. **Common backtest window 2009-09 → present** if you require the term-structure slope (covers 2010, 2011, 2015, 2018, 2020, 2022 stress regimes). If you only use VIX-level + SKEW + VVIX, you extend back to **2006**; VIX-level + SKEW alone → **1990**.
5. Benchmark vs buy-&-hold SPX on raw return + drawdown. No paid data, no option chains needed.

### Idea (1) — regime-gated defined-risk credit put-spreads on SPY/QQQ → **TWO-TRACK**
Because deep historical chains are paywalled, split into a feasible-now modeled study + a forward live-collection track:

**Track 1 (now, free): modeled-premium backtest, ~2006/2009 → present.**
- Underlying: SPY/QQQ daily bars (free, deep).
- IV input: use **VIX as the SPY ~30-day ATM IV** directly (VIX *is* 30-day SPX IV; SPY≈SPX/10). For QQQ, use **VXN** (Nasdaq-100 vol) — free via FRED `VXNCLS` and CBOE CDN (`VXN_History.csv` — same CDN pattern, not yet live-tested but almost certainly present; verify before relying). 
- Price the put spread you'd sell each cycle with Black-Scholes using that IV plus a **skew adjustment** (sell ~16–30 delta OTM puts; bump IV at those strikes using the SKEW index or a fixed empirical skew slope). This gives a *realistic modeled credit* without real historical quotes.
- Apply the *same* VIX-complex regime gate from idea (2) to decide when to put on spreads (e.g. only sell premium when term structure is in contango / VIX below its Xth percentile — exactly the vol-risk-premium harvesting condition).
- Haircut fills (bid/ask, slippage) conservatively since modeled, not quoted.
- **This is the honest, buildable version of idea (1) on free data and it directly tests the Natenberg thesis (harvest index put-skew + VRP, regime-gated).** Caveat clearly that premiums are modeled, not historical-quote-accurate.

**Track 2 (start now, pays off later): live chain collection for quote-accurate validation.**
- Use our **existing Alpaca keys (free Basic/Indicative)** to snapshot SPY+QQQ option chains (strikes, bid/ask, IV, greeks) daily and store them. Tradier sandbox as a free second source / cross-check (its greeks+IV come from ORATS).
- After a few months we have our *own* real chain history to validate the Track-1 modeled backtest going forward, and to run the strategy in paper for real.
- Do **not** pay for CBOE DataShop / ORATS history unless Track-1 modeled results look strong enough to justify a quote-accurate confirmation — defer that spend until the edge is demonstrated.

**Net:** ship the VIX-complex overlay (idea 2) immediately — it's free and deep. Build idea (1) as a modeled-premium + regime-gated backtest now (free, ~15yr depth via VIX/VXN as IV proxies), and start free Alpaca/Tradier live chain collection in parallel so a quote-accurate version and paper-trading become possible within months — all without spending a dollar.

---
*Endpoints marked "verified live" were fetched 2026-06-08. Alpaca capabilities read from official docs only (no live key calls, per instructions). VXN_History.csv pattern is inferred from the confirmed CBOE CDN pattern and should be verified before use. Yahoo + FRED-fredgraph were unreliable from this datacenter IP (429/empty) — CBOE CDN is the recommended primary and is not IP-walled.*
