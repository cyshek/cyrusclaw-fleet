# sma_crossover_btc — RETIRED

**Retirement date:** 2026-05-30
**Decision:** Tessera (with explicit main approval)

## Reason

Retired by Tessera 2026-05-30 with main's explicit approval (see MEMORY.md + this date's daily log).

Structural reason: Alpaca crypto round-trip spread is ~4% (per north-star MEMORY.md sobriety reminder). No realistic trading edge survives that drag at our $100 notional cap. The strategy cannot pass Bar E (paper → real) at this venue/cost structure regardless of signal quality. Continuing to tick consumes cron cycles + leaderboard visual space for zero promotion path.

This is NOT a wipe. Code + DB rows are preserved here for audit. If/when we change broker venues or substantially lift notional, these strategies could be re-evaluated — re-deploy by moving the dir back to `strategies/` and re-adding the cron line.


## Final state at retirement

- **n_trades (filled, from rankings):** 9
- **realized P&L:** $-2.0359
- **unrealized P&L:** $+0.0000
- **total P&L:** $-2.0359
- **turnover (sum of |notional|):** $890.22
- **decision rows logged:** 124 (action dist: {'hold': 113, 'buy': 5, 'skip_killswitch': 1, 'sell': 4, 'skip_risk': 1})
- **first trade ts:** 2026-05-25T16:46:14+00:00
- **last trade ts:** 2026-05-30T07:05:02+00:00

## Full trade history

| ts_utc | side | symbol | qty | price | notional_usd | reason |
|---|---|---|---|---|---|---|
| 2026-05-25T16:46:14+00:00 | buy | BTC/USD | 0.001262494 | 77657.013 | 100.0000 | SMA10=77431.17 > SMA30=77013.44 |
| 2026-05-26T02:05:07+00:00 | sell | BTC/USD | 0.001262494 | 76616.838 | 96.7487 | SMA10=77120.68 < SMA30=77169.67 |
| 2026-05-29T02:05:03+00:00 | buy | BTC/USD | 0.001333801 | 73520.4 | 100.0000 | SMA10=73497.83 > SMA30=73496.44 |
| 2026-05-29T03:05:03+00:00 | sell | BTC/USD | 0.001333801 | 73144.07 | 97.6226 | SMA10=73437.29 < SMA30=73445.19 |
| 2026-05-29T05:05:03+00:00 | buy | BTC/USD | 0.001333984 | 73502.241 | 100.0000 | SMA10=73435.15 > SMA30=73385.64 |
| 2026-05-29T20:05:03+00:00 | sell | BTC/USD | 0.001333984 | 73422.2 | 98.0394 | SMA10=73416.53 < SMA30=73429.40 |
| 2026-05-30T00:05:02+00:00 | buy | BTC/USD | 0.001335729 | 73377.5 | 100.0000 | SMA10=73522.66 > SMA30=73445.82 |
| 2026-05-30T05:05:03+00:00 | sell | BTC/USD | 0.001335729 | 73292.2 | 97.8072 | SMA10=73434.11 < SMA30=73441.55 |
| 2026-05-30T07:05:02+00:00 | buy | BTC/USD | 0.001334199 | 73479.695 | 100.0000 | SMA10=73455.87 > SMA30=73442.95 |

## Code preserved

Original strategy code at `strategies_retired/sma_crossover_btc/strategy.py` (moved from `strategies/sma_crossover_btc/`). Params at `params.json`. To resurrect: move the dir back to `strategies/` and add the cron line in `crontab -l` (see git history of crontab if needed).

## What we learned

This was one of 5-6 textbook crypto strategies deployed 2026-05-25 as part of the initial paper-tournament slate. They were not chosen for expected edge — they were chosen to prove out the runner pipeline and to occupy bench slots with diverse signal types (buy-and-hold, SMA crossover, RSI mean-revert, breakout, momentum, daily trend-follow). They served that purpose. They never had a realistic path to Bar E at this broker.

The lesson worth keeping: **cost realism is the first gate** (per MEMORY.md north star, baked into Session 3 architecture). Any future crypto consideration starts with: what's the round-trip spread, and what edge magnitude do we need to overcome it? If the answer is "more than 4%," look elsewhere.
