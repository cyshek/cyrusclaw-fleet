# Data Scout — Deep Pre-2020 Daily History for Leveraged ETFs + Underlyings
**Date:** 2026-06-08 · **Goal:** $0, datacenter-IP-fetchable, split/div-adjusted daily OHLC back to ≥2008 (GFC) to honestly backtest the trend-gated leveraged-long engine (hold TQQQ/UPRO/SOXL only above 200-DMA).
**Method:** all sources LIVE-tested from this VM via `curl` (web_fetch chokes on raw CSV/JSON — note that for next time). HTTP status + earliest date reported per source.

---

## 🏆 WINNER: Yahoo Finance v8 chart API — works clean from our IP, all tickers, deep, adjusted
**The brief's assumption that "Yahoo 429s from here" did NOT hold today.** The `^VIX` 429 was likely transient / symbol-specific rate-limiting. The **v8 chart JSON endpoint responded 200 on every ticker tested, including a 10/10 back-to-back burst with zero throttling.** This is the recommended $0 path. No key, no signup.

**Endpoint pattern (full history, split+div events):**
```
https://query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>?period1=0&period2=9999999999&interval=1d&events=div%2Csplit
```
- Send a browser `User-Agent` header (`Mozilla/5.0 (X11; Linux x86_64)`) — bare curl UA can get blocked. With UA it's clean.
- `query1` and `query2` hosts both work (failover-friendly).
- Returns JSON: `timestamp[]`, `indicators.quote[0]` = open/high/low/close/volume, **`indicators.adjclose[0].adjclose[]`** = split+dividend-adjusted close, and `events.splits` = every split (numerator/denominator/date).
- Index symbols are URL-encoded carets: `^GSPC`→`%5EGSPC`, `^NDX`→`%5ENDX`, `^SOX`→`%5ESOX`.

### Live-tested coverage (all HTTP 200, all adjclose=Y, from THIS datacenter IP, 2026-06-08)
| Symbol | Earliest daily bar | Bars | Adj close | Notes |
|---|---|---|---|---|
| **^GSPC** (S&P 500) | **1970-01-02** | 14228 | Y | deep — covers every modern bear |
| **^NDX** (Nasdaq-100) | **1985-10-01** | 10249 | Y | dot-com + GFC |
| **^SOX** (PHLX semis) | **1994-05-04** | 8077 | Y | semis trend asset for SOXL |
| **SPY** | 1993-01-29 | 8395 | Y | UPRO/SPXL underlying |
| **QQQ** | 1999-03-10 | 6853 | Y | TQQQ underlying |
| **TQQQ** (3x QQQ) | 2010-02-11 (incep) | 4104 | Y | multiple 2:1 splits captured |
| **UPRO** (3x SPY) | 2009-06-25 (incep) | 4263 | Y | |
| **SOXL** (3x semis) | 2010-03-11 (incep) | 4085 | Y | |
| **SPXL** (3x SPY) | **2008-11-05 (incep)** | 4422 | Y | pre-dates most of GFC bottom |
| **TECL** (3x tech) | **2008-12-30 (incep)** | 4385 | Y | |
| **UDOW** (3x Dow) | 2010-02-11 (incep) | 4104 | Y | |
| **SSO** (2x SPY) | **2006-06-21 (incep)** | 5021 | Y | full GFC, real 2x history |
| **QLD** (2x QQQ) | **2006-06-21 (incep)** | 5021 | Y | full GFC, real 2x history |

**Adjustment proof:** TQQQ first bar close=0.2163 vs adjclose=0.2061 (they differ) and split events return correctly — so the series IS split/dividend-adjusted. **Unadjusted leveraged-ETF data would be garbage (these split constantly); adjclose is mandatory and Yahoo provides it.**

**License/use:** Yahoo Finance data is for **personal, non-commercial use**; no formal redistribution license, scraping is technically against ToS but universally used for personal/research backtests. For an internal paper-trading research backtest (our case) this is the standard pragmatic choice. Do **not** redistribute the raw pulled data or build a commercial product on it without revisiting.

**Rate limit:** no published number; empirically 10 rapid calls = 200 each, no block. Be polite (small sleeps, cache to disk once). If `^VIX`-style 429s reappear, back off + retry `query2`; do not hammer.

---

## Backups (only if Yahoo starts 429ing persistently)

**2. Stooq — ⚠️ DOWNGRADED, no longer the clean curl source it was.**
- `https://stooq.com/q/d/l/?s=<sym>&i=d` now serves a **JS proof-of-work challenge** (SHA-256, 4 leading zeros) instead of CSV. The PoW is solvable programmatically (I solved it: ~34k iterations, POST `c`+`n` to `/__verify` with a cookie jar). **BUT** after solving, the bulk-CSV endpoint then demands an **`&apikey=`** that is gated behind a **human CAPTCHA** (`?s=<sym>&get_apikey`). So end-to-end it's a human-in-the-loop wall — not datacenter-automatable for fresh pulls. If Cyrus manually solves the captcha once to mint an apikey, the `&apikey=...` URL pattern reportedly works thereafter and Stooq reaches the 1990s for `^SPX`/`^NDX`. Until then: **not usable headless.** (Historically free, personal-use.)

**3. Alpha Vantage** — reachable from our IP (HTTP 200). `TIME_SERIES_DAILY_ADJUSTED` gives split/div-adjusted daily back ~20yr. **Requires a free key (≈20s signup, no payment)**; free tier = **25 requests/day** (was 500, now 25 — brutal for 12 tickers, but fine as a one-time backfill spread over days). `demo` key only works for demo symbols. URL: `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol=TQQQ&outputsize=full&apikey=KEY`. Personal + commercial use allowed on free tier per their terms.

**4. Tiingo** — reachable from our IP (clean 403 "supply a token", not an IP block). Free token (email signup, no card) → EOD `https://api.tiingo.com/tiingo/daily/<sym>/prices?startDate=2008-01-01&token=KEY`, split/div-adjusted, ~50 symbols/hr & 1000 req/day free. Good structured backup; **free tier is non-commercial / personal-research only.**

**5. FRED** — already covered by our key; supplies the **daily risk-free / T-bill cash leg** (e.g. `DGS3MO`, `DTB3`). Noted, not dwelt on. FRED does NOT carry the ETFs/indices we need here.

**Not worth it from here:** Financial Modeling Prep / Twelve Data free tiers (key + tight limits, no advantage over Yahoo); Nasdaq Data Link free equity tables are largely deprecated/retired; MarketWatch/Investing.com downloads are JS/login-walled; Wikipedia has no daily OHLC. GitHub OHLC mirrors exist but are stale (won't reach 2026) — only useful as a static 2008–~2020 seed if Yahoo ever dies.

---

## Synthesis: extending the backtest BEFORE ETF inception (the honest way)
TQQQ starts 2010, UPRO 2009, SOXL 2010 — too short to include the **2008 GFC** for the 3x QQQ/semis lines. To go back to ≥2008 (or 2000 dot-com for QQQ), **synthesize a proxy leveraged series from the underlying index's DAILY returns.** Standard, defensible method:

1. Take the underlying's **daily simple returns** `r_t = close_t/close_{t-1} − 1` (use `^NDX` for TQQQ, `^GSPC`/SPY for UPRO/SPXL/SSO, `^SOX` for SOXL — all available back to the 80s/90s above).
2. Leveraged daily return ≈ `L·r_t − dailyDrag`, where `L`=2 or 3 and `dailyDrag = (expenseRatio + financingCost)/252`. Financing ≈ `(L−1)·(short-rate + spread)`; short-rate from FRED (e.g. 3M T-bill `DTB3`), spread ~0.3–0.5%. ER ≈ 0.95%/yr for these.
3. **Compound the DAILY returns** to build the synthetic NAV: `NAV_t = NAV_{t-1}·(1 + L·r_t − dailyDrag)`. 

**CRITICAL caveat (state it loud so we model it right):** you **CANNOT** take the cumulative index return and multiply by L. Leveraged ETFs **rebalance daily**, so the path matters — **volatility decay** (beta-slippage) makes 3x of a choppy/sideways market lag 3× cumulative, and 3x of a steady trend can *exceed* it. You **must** apply L to each day's return *then* compound. Validate the synthesis by overlaying it on the REAL ETF over the live overlap window (2010+→now): fit/sanity-check `dailyDrag` so synthetic ≈ actual TQQQ during the overlap, then trust it pre-2010. Expect small tracking error vs reality (the model omits intraday rebal timing, swap costs, AUM effects) — treat synthetic pre-inception bars as *approximate*, real bars as ground truth. Report both backtest variants (real-only-from-inception vs synthetic-extended) so the 33.8%/yr claim is tested honestly across the GFC, not just the post-2010 bull.

**Bonus:** SSO/QLD (real **2x** history back to 2006-06) and SPXL/TECL (real **3x** back to 2008-11/12) give *actual* leveraged data covering the GFC bottom — use those as a reality anchor for whatever 3x synthesis you build, even though they're different multiples/sleeves.

---

## Recommended path (one line)
**Pull all 12 tickers' full split/div-adjusted daily history from Yahoo v8 (`period1=0`, browser UA, cache to disk once) → real ETF series from inception + synthetic 3x/2x extension from `^NDX`/`^GSPC`/`^SOX` daily returns (compounded, with FRED-financing + ER drag, overlap-calibrated) → backtest the 200-DMA trend-gated engine across 2008-GFC / 2018 / COVID-2020 / 2022.** Yahoo is free, no key, datacenter-clean today. Stooq is now captcha-walled; Tiingo/Alpha Vantage are the keyed fallbacks if Yahoo degrades.
