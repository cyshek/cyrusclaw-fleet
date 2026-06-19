# Tournament Round 20260608T062007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-08T06:20:44.534161Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and add a hard stop-loss:... | `breakout_xlk_regime__mut_bef4cc` | 🟢 PROMOTE | medRet=+2.56% pos=62% medSharpe=2.89 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_bef4cc` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and add a hard stop-loss: track entry price in position_state and close the position if price falls more than X% below entry. CRITICAL: the parent's own exit signal usually fires before any large drawdown, so X must be TIGHT to actually trigger. Pick X in the range 0.3%–1.0% (NOT 1.5%+) and explain in the docstring why you chose that value — what kind of intra-trade move is the stop trying to catch that the parent's exit misses. A stop that never fires in backtest is inert code, not edge. Stop-loss must NOT block the parent's own close signal (parent's exit runs first).
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_bef4cc`
- WF: median return +2.56%, 62% positive, 75% beat BH-SPY, median Sharpe 2.89, worst -2.45%, best +22.74%, 72 total trades.

