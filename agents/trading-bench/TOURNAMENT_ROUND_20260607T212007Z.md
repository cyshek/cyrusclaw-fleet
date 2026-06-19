# Tournament Round 20260607T212007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-07T21:20:53.895141Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a POST-LOSS COOLD... | `sma_crossover_qqq__mut_2728d3` | 🟢 PROMOTE | medRet=+3.13% pos=62% medSharpe=2.68 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_2728d3` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a POST-LOSS COOLDOWN: after closing a trade that realized a loss (exit price < entry price), refuse to take ANY new entry for the next N bars. Decrement the remaining-cooldown counter by 1 on every bar. Exits are NEVER gated by the cooldown — already-open positions must always be closeable on the parent's normal exit signal. Hypothesis: a fresh realized loss is weak but non-zero evidence that the local regime is hostile to this strategy's edge (volatility spike, trend reversal, news shock). Sitting out N bars lets the worst-case path play through without re-entering into it. Pick `loss_cooldown_bars` in the range 3–20. Justify the chosen N in the docstring relative to the parent's typical holding distribution (roughly 0.25–1.0× median holding bars is a sane band — much smaller is inert, much larger eats too many trading opportunities).

CRITICAL — use `market_state['strategy_state']` (NOT `position_state`) to track the cooldown counter. `position_state` is cleared on close (which is exactly when you need to ARM the cooldown), but `strategy_state` survives across flat periods so the counter persists naturally between trades. The runner re-reads `market_state['strategy_state']` after `decide()` returns, so mutating the dict in-place is sufficient (no reassignment needed).

DETECTING THE LOSS — DO NOT mirror entry_price into strategy_state yourself. The runner already exposes the parent's average entry price via `position_state[symbol]['avg_entry_price']` while a position is open. On the bar where YOUR code decides to close, read that value BEFORE returning the close action and compare to `market_state['last_price']`: if last_price < avg_entry_price (ignoring fees — good-enough proxy for realized loss), set `strategy_state['cooldown_remaining'] = N` in the same call that emits the close. Reading avg_entry_price AFTER the close action is too late because position_state[symbol] is gone on the next bar. Don't try to detect the loss retroactively on a later bar.

This filter ONLY gates entries. Exits (parent's own close signal) must fire normally and must NEVER be blocked by the cooldown counter. Safety backstops (`safety_max_loss_pct`, `safety_max_holding_bars`) also continue to fire unchanged — they short-circuit decide() before your code runs, so you don't need to special-case them.

Code skeleton (adapt to the parent's specific entry-signal shape):
```python
def decide(market_state, position_state, params):
    symbol = params['symbol']
    cooldown_n = int(params.get('loss_cooldown_bars', 5))
    state = market_state['strategy_state']  # survives flats
    last = float(market_state['last_price'])

    # ... compute indicators / parent signal ...
    entry_signal = (last > hi)   # parent's own entry condition
    exit_signal  = (last < lo)   # parent's own exit condition

    pos = position_state.get(symbol) or {}
    holding = float(pos.get('qty', 0))

    # 1. Exits ALWAYS run first and are never gated by cooldown.
    if holding > 0 and exit_signal:
        # Detect realized loss BEFORE the close clears position_state.
        entry_px = float(pos.get('avg_entry_price', 0.0) or 0.0)
        if entry_px > 0 and last < entry_px:
            state['cooldown_remaining'] = cooldown_n
        return Action('close', symbol, reason='...')

    # 2. Decrement cooldown once per bar (only when flat — exits above
    #    already returned). Floor at 0; never negative.
    cd = int(state.get('cooldown_remaining', 0) or 0)
    if cd > 0:
        state['cooldown_remaining'] = cd - 1

    # 3. Block entries while cooldown is still arming (use the
    #    pre-decrement value so a fresh cooldown_remaining=N blocks
    #    the NEXT N entry opportunities, not N-1).
    if holding == 0 and entry_signal and cd == 0:
        return Action('buy', symbol, notional_usd=notional,
                      reason='entry (no cooldown active)')

    return Action('hold', symbol,
                  reason=f'cooldown {cd}' if cd > 0 else 'no signal')
```

Add `loss_cooldown_bars` to params.json (default 5). Document in the docstring the chosen N AND your rough expectation of how often it will fire given the parent's typical loss rate (if the parent loses on <10% of trades the cooldown almost never engages and the directive is inert; if it loses on >60% of trades the cooldown is active most of the time and may smother the strategy). Either extreme is a sign the directive isn't a good fit for this parent — say so honestly in the docstring rather than picking N to hide it.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_2728d3`
- WF: median return +3.13%, 62% positive, 88% beat BH-SPY, median Sharpe 2.68, worst -14.32%, best +19.63%, 140 total trades.

