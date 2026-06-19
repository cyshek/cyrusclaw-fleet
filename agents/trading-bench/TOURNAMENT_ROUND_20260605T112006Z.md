# Tournament Round 20260605T112006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T11:20:54.243318Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and add a time-of-day fil... | `breakout_xlk_regime__mut_dd307e` | 🟢 PROMOTE | medRet=+2.53% pos=75% medSharpe=2.41 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_dd307e` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and add a time-of-day filter that only allows new entries during 14:30-20:00 UTC (US regular session). Bars are tagged with 't' in ISO8601 UTC. Closes still fire any time. The filter must NEVER trap an existing position long.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_dd307e`
- WF: median return +2.53%, 75% positive, 75% beat BH-SPY, median Sharpe 2.41, worst -2.63%, best +21.96%, 60 total trades.

