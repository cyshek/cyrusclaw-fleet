# Tournament Round 20260608T022011Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-08T02:21:00.033048Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and combine its entry sig... | `breakout_xlk__mut_b58135` | 🟢 PROMOTE | medRet=+2.61% pos=62% medSharpe=1.98 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_b58135` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and combine its entry signal with a second signal (e.g. require both an SMA crossover AND a recent breakout). Be explicit about the logical combination (AND vs OR). CRITICAL: an AND combination filters out trades — prefer OR (more entries) when the goal is more opportunities, AND only when the goal is to filter out losers. Justify the choice in the docstring: explain which kind of parent trade you're trying to eliminate (a specific failure mode), or which kind of new trade you're trying to add. Exits fire on either parent's exit signal — never make a position harder to close than to open.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_b58135`
- WF: median return +2.61%, 62% positive, 62% beat BH-SPY, median Sharpe 1.98, worst -10.65%, best +24.93%, 219 total trades.

