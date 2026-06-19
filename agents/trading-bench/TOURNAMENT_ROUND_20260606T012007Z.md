# Tournament Round 20260606T012007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T01:21:38.910428Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and add a TIME-STOP: trac... | `breakout_xlk_regime__mut_9e748e` | 🟢 PROMOTE | medRet=+3.17% pos=88% medSharpe=3.18 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_9e748e` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and add a TIME-STOP: track entry bar index in position_state and force-close the position after N bars have elapsed, regardless of the parent's exit signal. Hypothesis: trades that haven't worked within their typical holding window are dead money tying up capital. Ground N in the PARENT PROFILE's holding distribution — N should be near the p75 holding-bars value (force out the slow 25% of trades). Justify the chosen N in the docstring. Time-stop is a HARD exit; it fires alongside (and after) parent's close signal in the same way a stop-loss does. Document whether time-stopped trades counted toward the parent's profitable or unprofitable bucket on average (you can infer from raw_trades holding_bars vs pnl correlation).
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_9e748e`
- WF: median return +3.17%, 88% positive, 75% beat BH-SPY, median Sharpe 3.18, worst -1.83%, best +18.53%, 82 total trades.

