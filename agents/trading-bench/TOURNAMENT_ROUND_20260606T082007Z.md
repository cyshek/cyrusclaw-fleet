# Tournament Round 20260606T082007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T08:20:47.687595Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and add a take-profit ove... | `breakout_xlk_regime__mut_0b11ed` | 🟢 PROMOTE | medRet=+3.28% pos=75% medSharpe=3.60 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_0b11ed` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and add a take-profit overlay: track entry price in position_state and close the position when price has risen more than X% above entry. Pick X in the range 0.8%–3.0% based on what fraction of typical winning trades you want to lock in. The hypothesis: the parent gives back gains on winners by holding too long. Justify the chosen X in the docstring. Take-profit must NOT block the parent's own close signal (parent's exit runs first); take-profit only fires when the parent would otherwise hold.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_0b11ed`
- WF: median return +3.28%, 75% positive, 75% beat BH-SPY, median Sharpe 3.60, worst -1.83%, best +19.37%, 114 total trades.

