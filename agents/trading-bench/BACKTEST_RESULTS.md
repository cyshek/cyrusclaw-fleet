# Backtest Results — Crypto vs Stocks (Last 60 Days)

**Run date:** 2026-05-25 (PT)
**Lookback window:** 2026-03-26 → 2026-05-25 UTC (60 days)
**Harness:** `runner/backtest.py` (walk-forward, fill-at-close, $1000 starting cash)
**Caps mirrored from live:** `MAX_NOTIONAL=$100`, `MAX_POSITION=$100`, `MAX_TRADES_PER_DAY=4`
**Cost models:**
  - `CostModel.alpaca_crypto()` → `spread_bps=200, fee_bps=0` (~4% round-trip — Alpaca paper crypto tier-0 retail estimate, mid-2026)
  - `CostModel.alpaca_stocks()` → `spread_bps=2, fee_bps=0` (~4 bps round-trip — Alpaca paper commission-free on liquid US ETFs)
  - `--all` now auto-picks per strategy from symbol form (`/` => crypto).
**Tests:** `python3 -m unittest tests.test_backtest` — 8/8 passing (added `test_stocks_vs_crypto_cost_models_differ`, `test_for_symbol_dispatch`).

---

## 1. Crypto strategies (Alpaca crypto costs, ~4% round-trip)

| Strategy | Symbol | TF | Bars | Trades | Return % (no-cost) | Return % (costed) | Sharpe | MaxDD % | Win % | Avg $/Trade | Beats B&H BTC? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| buy_and_hold_btc | BTC/USD | 1Hour | 1441 | 1 | +1.16 | **+0.94** | 1.87 | -1.12 | — | — | (baseline) |
| sma_crossover_btc | BTC/USD | 1Hour | 1441 | 57 | -0.14 | **-11.31** | -15.64 | -11.31 | 0.0 | -3.96 | No |
| rsi_mean_revert_eth | ETH/USD | 1Hour | 1441 | 22 | +0.84 | **-3.51** | -8.27 | -3.55 | 0.0 | -3.19 | No |
| breakout_ltc | LTC/USD | 1Hour | 1441 | 54 | -1.25 | **-11.79** | -14.63 | -11.79 | 0.0 | -4.37 | No |
| momentum_sol | SOL/USD | 4Hour | 361 | 20 | -0.11 | **-4.02** | -6.05 | -4.14 | 10.0 | -4.02 | No |
| trend_follow_doge | DOGE/USD | 1Day | 61 | 4 | +1.25 | **+0.42** | 0.70 | -1.05 | 50.0 | +2.09 | No (under 0.94) |

**Crypto verdict:** unchanged from last cost-aware run, now confirmed on a 60-day (2× longer) window. Only `buy_and_hold_btc` and `trend_follow_doge` are net-positive after costs, and neither beats the trivial baseline by enough to call it edge. All five active-signal strategies (SMA, RSI, breakout, momentum) are *worse* than no trading. The ~4% round-trip cost floor is doing exactly what it's been doing — eating any signal that targets <5% moves.

## 2. Stocks strategies (Alpaca stocks costs, ~4 bp round-trip)

| Strategy | Symbol | TF | Bars | Trades | Return % (no-cost) | Return % (costed) | Sharpe | MaxDD % | Win % | Avg $/Trade | Beats B&H SPY? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| buy_and_hold_spy | SPY | 1Hour | 354 | 1 | +1.62 | **+1.62** | 13.27 | -0.25 | — | — | (baseline) |
| sma_crossover_qqq | QQQ | 1Hour | 359 | 9 | +1.82 | **+1.80** | 12.86 | -0.31 | 75.0 | +4.29 | Yes (+0.18 pp) |
| rsi_mean_revert_iwm | IWM | 1Hour | 341 | 8 | +0.77 | **+0.76** | 11.03 | -0.16 | 100.0 | +1.89 | No (-0.86 pp) |
| breakout_xlk | XLK | 1Hour | 294 | 3 | +3.30 | **+3.29** | 16.44 | -0.49 | 100.0 | +31.10 | **Yes (+1.67 pp)** |
| momentum_arkk | ARKK | 1Hour | 282 | 9 | +0.79 | **+0.77** | 4.03 | -0.58 | 50.0 | +1.99 | No (-0.85 pp) |
| trend_follow_gld | GLD | 1Day | 40 | 2 | -0.10 | **-0.11** | -2.80 | -0.17 | 0.0 | -1.08 | No (negative) |

**Stocks verdict — the headline result:** the story flips on the stocks venue. With cost drag reduced ~100× (2 bp vs 200 bp one-way), four of six stock strategies are net-positive after costs, and **two beat their buy-and-hold baseline** (`breakout_xlk` clearly, `sma_crossover_qqq` marginally). The cost-aware gap between optimistic and realistic returns collapses to <0.05 pp on most strategies — friction is no longer the dominant factor.

### Fitness-gate criterion (beat buy-and-hold net of costs)

This is the bar from MEMORY.md: edge must be "net of realistic execution costs."

- 🟢 **`breakout_xlk`**: +3.29% vs SPY's +1.62% on the same 60-day window. **Clears.** 3 trades, 100% win, $31/trade average — fits the breakout archetype perfectly (rare signal, large mean payoff). Sample size is **tiny** (3 trades, 2 closed); could be coincidence on a single ~6% XLK rally that happened to trigger.
- 🟡 **`sma_crossover_qqq`**: +1.80% vs SPY +1.62%. **Beats by 18 bp — within noise on 60 days.** 75% win rate over 9 trades is encouraging; flagged for live-watch but I wouldn't call this edge yet.
- 🔴 **`rsi_mean_revert_iwm`**, **`momentum_arkk`**: positive returns but underperform SPY. These are real signals (100% and 50% win rate) but the alpha is small relative to just being long the market.
- 🔴 **`trend_follow_gld`**: only 40 daily bars, 2 trades, slightly negative. Not enough data to judge GLD specifically; probably needs a longer lookback window than the bench can fetch cheaply.

### Why the win-rates are so high on stocks (and why I'm not euphoric)

A 100% win rate on 3 trades isn't 100%; it's `wins / 3`. With one losing trade it would drop to 67%. Same for `rsi_mean_revert_iwm` at 8 trades. The 60-day window includes a clean ~+2% drift in major US equity indices (SPY +1.6%, QQQ +1.8%), which biases any long-only strategy upward. **Walk-forward across multiple regimes (bull/chop/correction) is still required before promoting to real money.** This window is too friendly to long-only strategies.

## 3. Cross-comparison: which archetypes survive on which venue?

| Archetype | Crypto venue | Stocks venue | Pattern |
|---|---|---|---|
| Buy-and-hold | +0.94% | +1.62% | Both positive (held through up-drift). Stocks win because no spread on the entry-only round trip. |
| SMA crossover | **-11.31%** | **+1.80%** | Cost-floor flip. Same trade frequency (~9-60 trades/60d), but stocks' 2bp cost vs crypto's 200bp leaves the signal intact. |
| RSI mean-revert | **-3.51%** | **+0.76%** | Signal works on both venues (positive no-cost return on both); only stocks lets it survive after friction. |
| Breakout (Donchian) | **-11.79%** | **+3.29%** | Same as SMA — the cost difference is decisive. Note: on crypto LTC the signal was *negative* even before costs; on stocks XLK it was positive. So this isn't purely a cost story; the underlying assets behave differently too. |
| Momentum (lookback return) | **-4.02%** | **+0.77%** | Stocks survive but barely; both venues have weak no-cost edges (-0.11% / +0.79%). |
| Trend-follow (SMA20 daily) | **+0.42%** | **-0.11%** | The one archetype that does *better* on crypto in this window. DOGE happened to trend cleanly; GLD chopped. Sample sizes (4 vs 2 trades) are too small to draw conclusions. |

**Net-net:** stocks venue rescues 4 of 5 active-signal archetypes that crypto kills. `breakout_xlk` and `sma_crossover_qqq` are the live-paper candidates worth watching; the others need more bars or different parameters before they're worth time.

## What this means for graduation criteria (from MEMORY.md)

Reminder of the bar: 4+ weeks, 100+ round-trips, Sharpe > 1, max DD < 20%, multiple regimes, walk-forward.

- **breakout_xlk** has Sharpe 16+ and MaxDD 0.49% on this window — both crush the criteria, but on 3 trades that's noise. Needs 60+ more trades (the strategy fires rarely; might need a smaller lookback or several symbols in parallel to get sample).
- **sma_crossover_qqq** at 9 trades, Sharpe 13 is similarly under-sampled.
- None of the stock strategies have 100+ round-trips, so none clear the formal graduation gate. But they're now *plausibly* on a path to clearing it, which the crypto versions weren't.

## Caveats (read before believing any of this)

1. **One window, friendly to longs.** May-2026 was a +1.6% SPY drift. Any long-only strategy looks good. We need at least one bear/chop window before saying anything is real.
2. **Stocks cost estimate (2 bp) is conservative-rough.** Liquid ETFs (SPY/QQQ) trade with sub-bp spreads at retail size; less-liquid ETFs (ARKK, XLK in size) are wider. Bench-wide 2 bp is fine for $100 trades on majors; tune per-symbol later.
3. **No partial-fill / slippage on stocks either.** $100 market orders on SPY are absorbed by an MM book without moving price; this assumption breaks at $10k+.
4. **`feed=iex` (free tier) is incomplete.** IEX is ~2.5% of US equity volume. Bar OHLCV is roughly correct for liquid names but trade counts and volumes will look small vs the SIP truth. Bar timestamps/prices match SIP closely enough for indicator math.
5. **No holiday calendar in `market_hours.py`.** Stock strategies will skip-clean on holidays because there are no new bars; runner won't error.
6. **Bar counts vary by symbol.** GLD has 40 daily bars (calendar limited); SPY has 354 hourly (extended-hours stripped). Bar-count differences are normal and not a bug.
7. **Fill-at-close optimism still applies.** Both venues — live order arrives some seconds later at a different price.
8. **No funding / borrow.** Spot longs only.
9. **Sample sizes.** 3 trades is not a strategy verdict. Treat the stocks table as "this isn't dead on arrival," not "ship it."
10. **Determinism / cache.** Bars cached under `.cache/bars/{symbol}_{tf}_{start}_{end}.json` — reruns are free.

## What I would do now

1. **Don't schedule live paper crons for the 6 new stock strategies yet.** Surface this report to Tessera and let her decide which (if any) deserve live paper time. The two candidates worth considering: `breakout_xlk`, `sma_crossover_qqq`. `rsi_mean_revert_iwm` and `momentum_arkk` are profitable but don't beat buy-and-hold; live-watching them won't add signal vs the backtest unless we hit a different regime.
2. **Consider deprecating the cost-floored crypto strategies.** `sma_crossover_btc`, `breakout_ltc`, `momentum_sol` are now confirmed structural losers on the crypto venue across two windows (30d + 60d). Letting them keep trading is throwing paper money at friction. `rsi_mean_revert_eth` is borderline. Decision belongs with Tessera.
3. **Pull a second 60-day window** (Feb-Mar 2026 if data exists) to walk-forward the stock strategies before any live-promotion. The current window is too long-friendly.
4. **Per-symbol cost tuning** when more data lands. ARKK/XLK probably deserve ~5 bp; SPY/QQQ ~1 bp. Doesn't change verdicts but tightens the table.

## Reproduce

```bash
# Auto-pick cost model per symbol (crypto -> 200bp, stocks -> 2bp):
python3 -m runner.backtest --all --days 60

# Optimistic (no costs anywhere):
python3 -m runner.backtest --all --days 60 --no-costs

# Force a uniform cost across all strategies:
python3 -m runner.backtest --all --days 60 --spread-bps 50 --fee-bps 5

# One strategy:
python3 -m runner.backtest --strategy breakout_xlk --days 60

# Emit a Markdown table:
python3 -m runner.backtest --all --days 60 --md /tmp/table.md

# Tests:
python3 -m unittest tests.test_backtest
```

## Files

- `runner/backtest.py` — harness + `CostModel.alpaca_crypto()` / `alpaca_stocks()` / `for_symbol()` + auto-pick in `--all`
- `runner/broker_alpaca.py` — added `latest_stock_price`, `stock_bars` (feed=iex), `is_crypto_symbol`, `default_tif`; `submit_market_order` resolves TIF per symbol
- `runner/market_hours.py` — `is_us_equity_market_open(now_utc)` Mon-Fri 9:30-16:00 ET (TODO: holiday calendar)
- `runner/runner.py` — symbol-aware bar/price fetch; stock strategies skip-clean when market closed
- `runner/bars_cache.py` — `_fetch_range` routes crypto vs stocks endpoint
- `strategies/{buy_and_hold_spy, sma_crossover_qqq, rsi_mean_revert_iwm, breakout_xlk, momentum_arkk, trend_follow_gld}/` — 6 new stock strategies
- `tests/test_backtest.py` — added `test_stocks_vs_crypto_cost_models_differ`, `test_for_symbol_dispatch`
- `.cache/bars/*.json` — cached OHLCV pulls (now mixes crypto + stocks files)
