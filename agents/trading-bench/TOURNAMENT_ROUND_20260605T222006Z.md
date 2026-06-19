# Tournament Round 20260605T222006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T22:20:45.588562Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq_regime` | Take the parent strategy and combine its entry sig... | `sma_crossover_qqq_regime__mut_b58135` | 🟢 PROMOTE | medRet=+2.13% pos=88% medSharpe=1.59 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq_regime__mut_b58135` (parent: `sma_crossover_qqq_regime`)
- Directive: Take the parent strategy and combine its entry signal with a second signal (e.g. require both an SMA crossover AND a recent breakout). Be explicit about the logical combination (AND vs OR). CRITICAL: an AND combination filters out trades — prefer OR (more entries) when the goal is more opportunities, AND only when the goal is to filter out losers. Justify the choice in the docstring: explain which kind of parent trade you're trying to eliminate (a specific failure mode), or which kind of new trade you're trying to add. Exits fire on either parent's exit signal — never make a position harder to close than to open.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq_regime__mut_b58135`
- WF: median return +2.13%, 88% positive, 62% beat BH-SPY, median Sharpe 1.59, worst -2.13%, best +13.06%, 73 total trades.

