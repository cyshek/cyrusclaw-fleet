# Intraday Data Source Spike
**Date:** 2026-06-19  
**Author:** intraday-data-spike subagent  
**Target symbols:** SPY, QQQ, IWM, TLT, GLD  
**Goal:** Can we get free 5-minute bar data from this VM (datacenter IP) for a 2+ year backtest?

---

## Summary

**✅ YES — Alpaca free tier (SIP feed) works from this VM and is the clear path forward.**  
All 5 target ETFs have 5-minute bar history going back to at least 2016 (~10 years), with real-time (not delayed) access available without any paid subscription for historical data.

---

## Results Table

| Source | Available | History Depth | Interval | Rate Limit | Verdict |
|--------|-----------|---------------|----------|------------|---------|
| **Alpaca (SIP feed)** | ✅ YES | ~2016-01-04 (10yr) | 1Min, 5Min, 15Min, 30Min, 1H, 1D | No observed hard limit (5 rapid calls all 200, ~230ms each) | **✅ USE THIS** |
| **Alpaca (IEX feed)** | ✅ YES | 2016+ (same) | Same as SIP | Same | Backup; IEX ~15% market share, sparser |
| Yahoo Finance 5m | ✅ for recent | **60 days max** | 5m only | ~1 req/sec | ❌ Too short for backtest |
| Yahoo Finance 1m | ✅ for recent | **7 days max** | 1m | ~1 req/sec | ❌ Too short for backtest |
| Polygon.io | ❌ No key | 2yr (free tier) | 5m | 5 req/min (free) | Needs free registration |
| Alpha Vantage | ❌ No key | Limited (free) | 1m, 5m, 15m, 30m, 60m | 5 req/min, 500/day | Needs free key |
| Tiingo | ❌ No key | Limited (free) | 5m, 15m | 500 req/hr (free) | Needs free key |
| EOD Historical | ❌ 403 | Unknown | 5m | — | Needs key |
| Stooq | ❌ Skipped | — | — | CAPTCHA-gated | Skip |

---

## Alpaca Details

### Feed Behavior
- **Default feed / `feed=sip`**: Returns SIP consolidated tape (NYSE + NASDAQ + 12+ exchanges). Full volume. ✅
- **`feed=iex`**: IEX only (~15% market share), much sparser bars (low n, spotty coverage)
- **Use `feed=sip`** for backtesting — it's the default and works on the free tier for historical data.

### Important Caveat: Recent vs Historical
- **Historical SIP (any date up to ~yesterday)**: Works fine, no subscription required
- **Live/real-time SIP** (querying with `sort=desc` and no `end`): Returns recent data fine
- **Tested range**: 2016-01-04 through 2026-06-18 — all accessible

### Multi-Symbol Endpoint
Use `feed=sip` explicitly when calling the multi-symbol endpoint:
```
GET /v2/stocks/bars?symbols=SPY,QQQ,IWM,TLT,GLD&timeframe=5Min&start=...&end=...&feed=sip
```
Without `feed=sip`, only the last symbol alphabetically (GLD) was returned — bug or routing issue in the default-feed multi-sym path. Explicit `feed=sip` returns all 5 symbols correctly.

### History Availability (Verified)
| Symbol | Earliest Tested | Bars at 2016-01-04 |
|--------|----------------|---------------------|
| SPY | 2016-01-04 | ✅ 3+ bars returned |
| QQQ | 2016-01-04 | ✅ 3+ bars returned |
| IWM | 2016-01-04 | ✅ 3+ bars returned |
| TLT | 2016-01-04 | ✅ 3+ bars returned |
| GLD | 2016-01-04 | ✅ 3+ bars returned |

> Note: Pre-2016 data appears null. Exact start varies by symbol but 2016 is a safe floor. Actual exchange-tape earliest may be 2015-12-xx — 2016-01-04 is first confirmed trading date.

### Data Volume Estimate
- Regular session (9:30–16:00 ET): ~252 days × 78 bars × 2yr = **~39,312 bars/symbol**
- Extended hours included: ~252 × 150 × 2yr = **~75,600 bars/symbol**  
- Pages required at 10k limit: **4–8 pages** for 2yr per symbol → very manageable
- API call time: ~230ms/request, so a full 2-year 5-symbol pull ≈ 10–40 calls ≈ under 10 seconds

### Bar Format
Fields: `t` (ISO8601 UTC), `o`, `h`, `l`, `c` (OHLC), `v` (volume), `vw` (VWAP), `n` (trade count)

---

## Sample: SPY 5-Minute Bars (2023-01-03, regular session open, SIP feed)

```
timestamp (UTC)           open     high      low    close     volume       vwap  n_trades
2023-01-03T14:30:00Z    384.37   385.12   383.59   384.51  1,983,324   384.3476     22363
2023-01-03T14:35:00Z    384.54   385.44   384.32   385.39    961,927   384.8422      9801
2023-01-03T14:40:00Z    385.41   386.43   385.17   385.28  1,629,742   385.9046     14564
2023-01-03T14:45:00Z    385.29   385.40   383.02   383.50  1,997,429   384.0469     14407
2023-01-03T14:50:00Z    383.49   383.96   382.50   382.80  1,800,303   383.2833     10841
2023-01-03T14:55:00Z    382.80   383.10   381.66   381.71    982,402   382.2094     10002
2023-01-03T15:00:00Z    381.77   382.58   381.68   382.12  1,600,548   382.2598     11112
2023-01-03T15:05:00Z    382.12   382.41   381.78   381.97    879,537   382.1197      7210
2023-01-03T15:10:00Z    381.96   382.03   380.93   381.17  1,236,231   381.4345      9670
2023-01-03T15:15:00Z    381.18   381.37   380.22   380.25    999,059   380.8450      9979
```
Note: Timestamps are UTC. NYSE session 9:30–16:00 ET = 14:30–21:00 UTC. Volume is SIP consolidated.

---

## Yahoo Finance Limitations

Yahoo's v8 chart API works from our datacenter IP (tested: HTTP 200) but has hard caps:
- `interval=1m`: max `range=7d` — ~7 calendar days of data
- `interval=5m`: max `range=60d` — ~60 calendar days of data
- Yahoo explicitly returns error: *"5m data not available... range must be within last 60 days"*

Yahoo is useful for **rolling live signals** (last 60d window) but **cannot support a multi-year backtest**.

---

## Recommendation

**Use Alpaca SIP feed via the existing `broker_alpaca.py` / `bars_cache.py` infrastructure.**

The workspace already has `AlpacaClient` in `runner/broker_alpaca.py` with the `.env` keys loaded. The `bars_cache.py` already has Alpaca bar-fetching logic. Key implementation notes:

1. **Fetch endpoint**: `GET /v2/stocks/{symbol}/bars` with `?timeframe=5Min&feed=sip&start=...&end=...&limit=10000`
2. **Multi-symbol**: Use `/v2/stocks/bars?symbols=SPY,QQQ,...&feed=sip` (the `feed=sip` param is required for multi-sym)
3. **Pagination**: Follow `next_page_token` — each page ≤10k bars; 2yr of regular-session 5Min data ~4 pages/symbol
4. **Extended hours filtering**: Data includes pre/after market; filter `14:30:00Z ≤ t < 21:00:00Z` for regular-session-only strategy
5. **No rate limit observed** from this IP in rapid testing — be polite but no observed hard cap for historical pulls
6. **Cache to disk** after first pull (already standard practice in this workspace via `bars_cache.py`)

### If Alpaca keys ever expire or are revoked
Fallback options that need free key registration (minutes, no cost):
- **Polygon.io** free tier: 5 req/min, 2yr history on 5m bars — register at polygon.io
- **Alpha Vantage**: 5 req/min, 500/day — register at alphavantage.co

Both require less than 60 seconds to register for a free API key.

---

## Conclusion

**Free intraday data path exists.** Alpaca SIP historical bars via our existing paper-trading API keys cover all 5 target ETFs at 1-minute and 5-minute resolution from 2016 onward — well beyond the 2-year backtest requirement. No new API key registration needed. No paid tier needed for historical research.
