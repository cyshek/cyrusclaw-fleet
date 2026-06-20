# buy_and_hold_btc — RETIRED

**Retirement date:** 2026-05-30
**Decision:** Tessera (with explicit main approval)

## Reason

Retired by Tessera 2026-05-30 with main's explicit approval (see MEMORY.md + this date's daily log).

Structural reason: Alpaca crypto round-trip spread is ~4% (per north-star MEMORY.md sobriety reminder). No realistic trading edge survives that drag at our $100 notional cap. The strategy cannot pass Bar E (paper → real) at this venue/cost structure regardless of signal quality. Continuing to tick consumes cron cycles + leaderboard visual space for zero promotion path.

This is NOT a wipe. Code + DB rows are preserved here for audit. If/when we change broker venues or substantially lift notional, these strategies could be re-evaluated — re-deploy by moving the dir back to `strategies/` and re-adding the cron line.


## Final state at retirement

- **n_trades (filled, from rankings):** 1
- **realized P&L:** $+0.0000
- **unrealized P&L:** $-5.1882
- **total P&L:** $-5.1882
- **turnover (sum of |notional|):** $100.00
- **decision rows logged:** 125 (action dist: {'skip_killswitch': 1, 'buy': 1, 'hold': 123})
- **first trade ts:** 2026-05-25T16:40:51+00:00
- **last trade ts:** 2026-05-25T16:40:51+00:00

## Full trade history

| ts_utc | side | symbol | qty | price | notional_usd | reason |
|---|---|---|---|---|---|---|
| 2026-05-25T16:40:51+00:00 | buy | BTC/USD | 0.001263257 | 77586.7 | 100.0000 | no position; opening $100.00 buy-and-hold |

## Code preserved

Original strategy code at `strategies_retired/buy_and_hold_btc/strategy.py` (moved from `strategies/buy_and_hold_btc/`). Params at `params.json`. To resurrect: move the dir back to `strategies/` and add the cron line in `crontab -l` (see git history of crontab if needed).

## What we learned

This was one of 5-6 textbook crypto strategies deployed 2026-05-25 as part of the initial paper-tournament slate. They were not chosen for expected edge — they were chosen to prove out the runner pipeline and to occupy bench slots with diverse signal types (buy-and-hold, SMA crossover, RSI mean-revert, breakout, momentum, daily trend-follow). They served that purpose. They never had a realistic path to Bar E at this broker.

The lesson worth keeping: **cost realism is the first gate** (per MEMORY.md north star, baked into Session 3 architecture). Any future crypto consideration starts with: what's the round-trip spread, and what edge magnitude do we need to overcome it? If the answer is "more than 4%," look elsewhere.
