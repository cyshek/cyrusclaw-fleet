# Tournament Round 20260606T102007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T10:20:43.595065Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a time-of-day fil... | `sma_crossover_qqq__mut_dd307e` | 🟢 PROMOTE | medRet=+3.24% pos=62% medSharpe=2.83 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_dd307e` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a time-of-day filter that only allows new entries during 14:30-20:00 UTC (US regular session). Bars are tagged with 't' in ISO8601 UTC. Closes still fire any time. The filter must NEVER trap an existing position long.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_dd307e`
- WF: median return +3.24%, 62% positive, 88% beat BH-SPY, median Sharpe 2.83, worst -12.66%, best +19.53%, 142 total trades.

