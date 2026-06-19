# Tournament Round 20260605T034408Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T03:46:20.210695Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add an ENTRY-CONFIRMA... | `sma_crossover_qqq__mut_386443` | 🟢 PROMOTE | medRet=+2.11% pos=62% medSharpe=1.88 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_386443` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add an ENTRY-CONFIRMATION DELAY: require the parent's entry signal to remain TRUE for N consecutive bars before actually placing the buy. If the signal is false on any bar, reset the consecutive-bar counter to 0 immediately. Hypothesis: many false-positive entries are single-bar spikes (e.g. a one-bar breakout that reverses immediately, or an SMA crossover that flips back next bar). Forcing the signal to hold for N bars filters those out at the cost of entering N bars late on true trends. Pick `entry_confirm_bars` in the range 2–5. Justify the chosen N in the docstring relative to the parent's typical holding distribution (N should be a small fraction of median holding bars — otherwise the lag eats too much of the move).

CRITICAL — use `market_state['strategy_state']` (NOT `position_state`) to count consecutive signal bars. `position_state` is cleared on close, but `strategy_state` survives across flat periods so the counter persists naturally between trades. The runner re-reads `market_state['strategy_state']` after `decide()` returns, so mutating the dict in-place is sufficient (no reassignment needed).

This filter ONLY gates entries. Exits (parent's own close signal) must fire normally and must NEVER be blocked by the confirmation counter. Already-open positions must always be closeable.

Code skeleton (adapt to the parent's specific entry-signal shape):
```python
def decide(market_state, position_state, params):
    symbol = params['symbol']
    n_confirm = int(params.get('entry_confirm_bars', 2))
    state = market_state['strategy_state']  # survives flats

    # ... compute indicators / parent signal ...
    entry_signal = (last > hi)   # parent's own entry condition
    exit_signal  = (last < lo)   # parent's own exit condition

    holding = float((position_state.get(symbol) or {}).get('qty', 0))

    # Exits ALWAYS run first and are never gated.
    if holding > 0 and exit_signal:
        state['confirm_count'] = 0  # reset on exit too
        return Action('close', symbol, reason='...')

    # Confirmation counter (only meaningful when flat).
    if entry_signal:
        state['confirm_count'] = state.get('confirm_count', 0) + 1
    else:
        state['confirm_count'] = 0   # ANY false bar resets

    if holding == 0 and state.get('confirm_count', 0) >= n_confirm:
        state['confirm_count'] = 0   # consume the confirmation
        return Action('buy', symbol, notional_usd=notional,
                      reason=f'entry confirmed {n_confirm} bars')

    return Action('hold', symbol, reason='...')
```

Add `entry_confirm_bars` to params.json (default 2). Document in the docstring the chosen N AND what fraction of parent entries you expect this to filter out (if it filters <5% you picked N too low; if >50% you picked N too high — both are inert in different ways).
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_386443`
- WF: median return +2.11%, 62% positive, 88% beat BH-SPY, median Sharpe 1.88, worst -11.35%, best +19.52%, 134 total trades.

