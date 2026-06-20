# Harness Intraday Audit — 1m / 5m / Tick Readiness

**Generated:** 2026-05-29 17:17:46 UTC
**Auditor:** trading-bench subagent (read-only)
**Files reviewed:** `runner/backtest.py`, `runner/walk_forward.py`, `runner/bars_cache.py`, `runner/market_hours.py`, plus targeted spot-checks of `runner/broker_alpaca.py`, `runner/runner.py`, `runner/safety_backstop.py`, `runner/risk.py`, all `strategies/*/params.json`.

---

## TL;DR Verdict: 🟡 **YELLOW** for 1m / 5m bars · 🔴 **RED** for tick data

The harness is **structurally per-bar, not per-day** — it can run 1Min and 5Min bars today with three small concrete fixes (no refactor). However:

- **Tick-level data is unsupported.** Alpaca tick/quote endpoints are not wired in `broker_alpaca.py`; `bars_cache.py` exclusively fetches OHLCV bar aggregates. Adding tick support is a real refactor (new client methods, new cache schema, new ingestion semantics in `backtest()`). Treat tick as RED — a separate workstream, not a weekend sprint.
- **News-reactive strategies** that key off bar timestamps will work on 1Min/5Min bars, but if they need event timestamps or headlines, that's an entirely separate data integration (not in scope of this harness).

The audit applies to **both** `runner/backtest.py` AND `runner/runner.py` (live). Three of the four YELLOW items hit live too.

---

## 1. Findings

### F1 — `bars_cache` already passes timeframe through; `1Min`/`5Min` are in the allowlist ✅

`runner/bars_cache.py:30-34` whitelists `1Min, 5Min, 15Min, 30Min, 1Hour, 2Hour, 4Hour, 6Hour, 12Hour, 1Day` and passes the user's `timeframe` verbatim into the Alpaca URL at `bars_cache.py:65-71`. Both crypto (`v1beta3/crypto/us/bars`) and stocks (`v2/stocks/{sym}/bars?feed=iex`) routes are timeframe-agnostic — pagination already handled (`bars_cache.py:74-79`). **No change needed here for 1m/5m.**

Same is true for live: `broker_alpaca.py:175-194` (`crypto_bars`) and `broker_alpaca.py:207-238` (`stock_bars`) both accept the timeframe string and the `tf_minutes` map at L178 / L214 includes `1Min` and `5Min`. **Live runner can request 1m/5m bars today.**

### F2 — Cache key snaps to UTC **day** boundary; intraday reruns may return stale bars 🟡

`runner/bars_cache.py:100-107`:

```python
if end_dt is None:
    now = datetime.now(timezone.utc)
    end_dt = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
start_dt = end_dt - timedelta(days=days)
start = _iso_date(start_dt)
end = _iso_date(end_dt)
path = _cache_path(symbol, timeframe, start, end)
```

The cache filename only carries `YYYY-MM-DD` resolution. For daily bars this is fine. For 1Min/5Min:
- Two backtests run 4 hours apart on the same trading day will hit the same cache file, even though 240 new 1m bars exist in between.
- Walk-forward windows that explicitly pass `end_dt` are unaffected (each window has a fixed end date).
- Live runner does NOT use this cache (`bars_cache.py:5-6` docstring) — so live is unaffected.

**Fix scope (~5 lines):** include hour-minute in the cache filename when `timeframe` is sub-hour, OR add a TTL check (`mtime < N minutes old`). Trivial.

### F3 — `BARS_PER_YEAR` map includes 1Min/5Min and is used for Sharpe annualization ✅

`runner/backtest.py:113-124`:

```python
BARS_PER_YEAR = {
    "1Min": 60 * 24 * 365,
    "5Min": 12 * 24 * 365,
    ...
}
```

Sharpe calc at `backtest.py:608-617` looks up `BARS_PER_YEAR.get(timeframe, 24 * 365)`. **Annualization for crypto 1m/5m is correct (24×365 because crypto is 24/7).** For stocks, this same map double-counts: at 1Min in NYSE hours, real bars/year ≈ 60 × 6.5 × 252 = 98,280, not 525,600. This will overstate stocks-intraday Sharpe by sqrt(5.3) ≈ 2.3×.

**Fix scope (~10 lines):** add a separate `BARS_PER_YEAR_STOCKS` map and switch on `_is_crypto(symbol)`. Or compute `bars_per_year` empirically from the bar timestamp density of the actual window (more robust). Either way, contained to `backtest.py`.

### F4 — Daily-trade cap (`MAX_TRADES_PER_DAY=4`) is the actual blocker for intraday-momentum strategies 🟡

`runner/risk.py:27` sets `MAX_TRADES_PER_DAY = 4`, and `runner/backtest.py:74-78,108-110` enforces it per UTC day (counter keyed on `_bar_utc_day(bar)` at `backtest.py:282`). Live runner enforces the same cap via `runner/risk.py::check_trade`.

For 1Min/5Min intraday-momentum strategies, **4 round-trips/day = 4 buys + 4 closes = 8 actions/day**, but the cap counts BOTH buys AND closes as trades (`backtest.py:341,392,431`). Effective ceiling: **~2 round-trips/day per strategy.** That's not "intraday momentum," that's "twice-a-day swing."

This is a **policy decision**, not a bug — Cyrus deliberately capped fire-rate to limit blow-up surface. But for the intraday sprint you need an explicit decision:

- Option A: raise `MAX_TRADES_PER_DAY` to e.g. 20 globally → blast radius increases for all existing strategies.
- Option B: make it per-strategy via `params.json` (`max_trades_per_day: 20`) with a higher hard ceiling in `risk.py` → recommended; strategies opt in.
- Option C: switch cap from "trades/day" to "open positions/day" → semantic change, more invasive.

**This same gate fires in live runner.** Not just backtest.

### F5 — `position_state` initialization key is now hoisted (post-2026-05-26 fix); per-bar loop is clean ✅

`runner/backtest.py:264-273` hoists `position_state` and `persistent_state` out of the per-bar loop. The loop at `backtest.py:281-454` iterates **per bar**, not per day. No daily-boundary semantics other than the UTC-day trade-counter (F4). **Strategy interface is per-bar from inception** — `market_state["bars"]` is the full visible slice at each step (`backtest.py:344-352`), and `decide()` is invoked every bar (`backtest.py:380`). No refactor needed for finer timeframes.

Live runner mirror: `runner/runner.py:151-180` builds `market_state` once per tick (cron-driven), passes the same shape. Decide-loop is per-tick. ✅

### F6 — SPY regime slicing assumes **daily** SPY bars; intraday strategies still get daily-resolution regime 🟡

`runner/backtest.py:223-256` pre-fetches `SPY 1Day` bars covering the backtest window and slices them by `bar_date = bar.get("t")[:10]` (date-only) at `backtest.py:324-336`. For a 1Min strategy, every bar within the same UTC day sees the **identical** SPY regime — which is fine semantically (you don't want intraday-noisy regime signal) but worth flagging:

- The SPY 1Day fetch hardcodes `"1Day"` timeframe at `backtest.py:248`. If you want intraday regime (e.g. SPY 5Min for an "is SPY-up-on-the-day" filter), that's a small extension.
- Slicing at `[:10]` (date prefix) silently coerces minute-level bar timestamps to date-only comparison. Works correctly but is timeframe-implicit.

Live runner: `runner/runner.py:166` hardcodes `"1Day"` for SPY too. Same situation.

**Fix scope:** opt-in `regime_timeframe` param in `params.json`. Trivial.

### F7 — `safety_backstop.bars_since_entry` is bar-count, not time-elapsed ✅ (but semantically different at 1m)

`runner/runner.py:189-199` and `runner/safety_backstop.py:145+` compute "bars since entry" as a bar count. The `safety_max_holding_bars` param therefore means very different real-time durations at 1Min (1 bar = 1 min) vs 1Day (1 bar = 1 day). Strategies that set `safety_max_holding_bars=24` get auto-closed after 24 minutes on 1Min, 24 hours on 1Hour, 24 days on 1Day. **No code bug** — but strategy params have to be tuned per timeframe. Worth documenting in the archetype scoping doc.

### F8 — `market_hours.is_us_equity_market_open()` resolution is fine ✅

`runner/market_hours.py:117-137` resolves to minute precision (NYSE 09:30-16:00 ET). Live runner check at `runner/runner.py:122` correctly gates stocks tickers on minute boundaries. No assumption of daily granularity anywhere. ✅

### F9 — Cost model assumptions: 🟡 likely too pessimistic for intraday stocks, fine for crypto

`runner/backtest.py:155-191`:
- `CostModel.alpaca_stocks()` → 2 bps one-way spread, 0 fee. This was calibrated for **SPY/QQQ at $100 notional held for hours/days**. For 1Min/5Min intraday on liquid ETFs, the effective spread is roughly the same (~1-2 bps), but you'll be paying it **far more often** — at e.g. 20 round-trips/day with 4 bps RT cost, that's 80 bps/day = 20%/year just in friction. The model is correct; the **strategy economics** are the problem, and intraday strategies need to clear that bar in their fitness numbers.
- `CostModel.alpaca_crypto()` → 200 bps one-way (4% RT). Already crushing for daily holds; at intraday frequency it makes any crypto-1m strategy DOA. Document explicitly that crypto-intraday is structurally non-viable on Alpaca paper.
- **No market-impact / slippage model beyond spread.** At $100 notional this is realistic. If you ever scale notional, revisit.
- **No partial-fill modeling.** Every fill is "full notional at the next bar close ± spread" (`backtest.py:374-378`). For minute-bar momentum at any realistic size, this is fine; for tick-scale or for $10k+ notional, it isn't.

**No code change required.** Just be aware when reading 1m/5m backtest results.

### F10 — Tick-level data: not supported 🔴

`broker_alpaca.py` exposes `latest_crypto_price` / `latest_stock_price` (single quote at moment of call) and `crypto_bars` / `stock_bars` (OHLCV aggregates). There is **no** `/v2/stocks/{sym}/trades` or `/v2/stocks/{sym}/quotes` historical-tick endpoint wired in, and `bars_cache.py` only knows the bar shape `{t,o,h,l,c,v}`.

For tick-driven strategies you would need:
1. New `AlpacaClient.stock_trades(symbol, start, end)` / `stock_quotes(...)` methods, paginated.
2. New cache layer for tick data (file sizes explode — 1 day of SPY trades ≈ several MB; full year of one symbol is multi-GB).
3. New `tick_state` shape in `backtest()` — `bars` array is the wrong primitive.
4. SIP feed access (free IEX feed gives trade-tape coverage but not consolidated NBBO quotes — strategies that need bid/ask need paid SIP).

**Scope: 2-4 days of engineering, not a weekend item.** Recommend deferring tick-level strategies until after the 1m/5m sprint validates the harness extensions.

---

## 2. Does the same audit apply to `runner/runner.py` (live)?

| Finding | Backtest | Live runner | Notes |
|---|---|---|---|
| F1 timeframe pass-through | ✅ works | ✅ works | `broker_alpaca.{crypto,stock}_bars` accept 1Min/5Min today |
| F2 cache UTC-day key | 🟡 affects | ✅ N/A | Live doesn't use bars_cache |
| F3 BARS_PER_YEAR for Sharpe | 🟡 affects | ✅ N/A | Live doesn't compute Sharpe |
| F4 MAX_TRADES_PER_DAY=4 | 🟡 affects | 🟡 **affects live too** | Same `risk.check_trade` |
| F5 per-bar loop | ✅ clean | ✅ clean | Both per-bar/per-tick |
| F6 SPY regime hardcoded 1Day | 🟡 affects | 🟡 **affects live too** | `runner.py:166` |
| F7 holding-bars semantics | ✅ no bug | ✅ no bug | Document per-tf |
| F8 market hours | ✅ minute-precision | ✅ minute-precision | OK |
| F9 cost model | 🟡 documented | ✅ N/A live | Live pays real Alpaca spreads |
| F10 tick data | 🔴 unsupported | 🔴 unsupported | Both need new client methods |

---

## 3. Minimal Todo List to Enable 1m / 5m Backtests This Weekend

Ordered by dependency / blast radius. Each is small.

1. **F4 (BLOCKING for intraday-momentum):** make `MAX_TRADES_PER_DAY` a per-strategy `params.json` field, with hard ceiling (suggest 40 = 20 round-trips) in `runner/risk.py`. Update `_bt_check_trade` in `backtest.py:64-92` to read the override. Update live `runner/risk.py::check_trade` likewise. Add a test in `tests/test_walk_forward.py` style. **~30 LOC + test.**

2. **F2 (BLOCKING for repeatable intraday backtests):** add TTL to bars_cache when `timeframe` is sub-hour. Either:
   - include `HH-MM` in cache filename when `tf_minutes < 60`, OR
   - skip-cache-if-mtime-older-than(tf_minutes) on read.
   Both are ~5 LOC at `bars_cache.py:100-115`. **~5 LOC.**

3. **F3 (CORRECTNESS for stocks Sharpe):** add stocks-aware bars/year. Cleanest: in `backtest()` at `backtest.py:608-617`, compute `bars_per_year` from observed timestamp density: `bars_per_year = len(bars) * (365*86400) / (last_t - first_t)`. Drop the lookup table. **~10 LOC, also fixes any future timeframe drift.**

4. **F6 (nice-to-have):** add `regime_timeframe` to `params.json`, default `"1Day"`; pass through at `backtest.py:248` and `runner.py:166`. **~6 LOC.**

5. **F7 (DOCS only):** add a note to `AGENTS.md` or `GATE.md` that `safety_max_holding_bars` is bar-count, so 1Min strategies should set it accordingly (e.g. `60` = "max 1 hour hold").

6. **Sanity test:** write `tests/test_intraday_backtest.py` that fetches SPY 5Min for one week and runs a trivial buy-and-hold to verify the round-trip: bars fetched, backtest completes, sharpe finite, no UTC-day cap fires. **~40 LOC.**

**Total: ~100 LOC + 1 test, ~1 hour of work.** All contained to `runner/`. No DB schema changes. No live cron disruption (live runner is unaffected unless you ship items 1, 4 — both of which are additive and backward-compatible).

---

## 4. Tick-Level Strategies — Defer

Don't add tick support this weekend. The fixes above unlock 1Min / 5Min, which is enough for "intraday momentum." Tick-driven strategies (e.g. orderbook-imbalance, microprice) are a separate ~2-4 day project: new `broker_alpaca` methods, new cache layer, new backtest primitive. Flag for a future sprint with explicit Cyrus sign-off.

## 5. News-Reactive Strategies — Out of harness scope

News-reactive strategies need an event/headline feed (Benzinga, Polygon news, RSS, etc.). The bar harness can serve them well — at minute granularity you can react to a news timestamp within the same bar — but the news ingestion is a separate data integration not present anywhere in `runner/`. Recommend separate scoping doc.

---

## Verification

```
$ ls -la /home/azureuser/.openclaw/agents/trading-bench/workspace/reports/HARNESS_INTRADAY_AUDIT_*.md
```
(Run after this report is written.)
