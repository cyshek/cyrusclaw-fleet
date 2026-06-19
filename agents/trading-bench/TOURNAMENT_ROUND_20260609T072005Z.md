# Tournament Round 20260609T072005Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-09T07:20:58.048837Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and add a TIME-STOP: trac... | `breakout_xlk__mut_9e748e` | 🟢 PROMOTE | medRet=+3.96% pos=62% medSharpe=2.91 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_9e748e` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and add a TIME-STOP: track entry bar index in position_state and force-close the position after N bars have elapsed, regardless of the parent's exit signal. Hypothesis: trades that haven't worked within their typical holding window are dead money tying up capital. Ground N in the PARENT PROFILE's holding distribution — N should be near the p75 holding-bars value (force out the slow 25% of trades). Justify the chosen N in the docstring. Time-stop is a HARD exit; it fires alongside (and after) parent's close signal in the same way a stop-loss does. Document whether time-stopped trades counted toward the parent's profitable or unprofitable bucket on average (you can infer from raw_trades holding_bars vs pnl correlation).
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_9e748e`
- WF: median return +3.96%, 62% positive, 88% beat BH-SPY, median Sharpe 2.91, worst -9.85%, best +32.91%, 96 total trades.

