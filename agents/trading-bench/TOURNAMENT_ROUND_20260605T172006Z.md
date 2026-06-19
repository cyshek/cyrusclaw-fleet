# Tournament Round 20260605T172006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T17:20:51.471664Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq_regime` | Take the parent strategy and combine its entry sig... | `sma_crossover_qqq_regime__mut_b58135` | 🟢 PROMOTE | medRet=+2.82% pos=88% medSharpe=2.01 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq_regime__mut_b58135` (parent: `sma_crossover_qqq_regime`)
- Directive: Take the parent strategy and combine its entry signal with a second signal (e.g. require both an SMA crossover AND a recent breakout). Be explicit about the logical combination (AND vs OR). CRITICAL: an AND combination filters out trades — prefer OR (more entries) when the goal is more opportunities, AND only when the goal is to filter out losers. Justify the choice in the docstring: explain which kind of parent trade you're trying to eliminate (a specific failure mode), or which kind of new trade you're trying to add. Exits fire on either parent's exit signal — never make a position harder to close than to open.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq_regime__mut_b58135`
- WF: median return +2.82%, 88% positive, 62% beat BH-SPY, median Sharpe 2.01, worst -2.49%, best +12.75%, 76 total trades.

