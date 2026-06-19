# Tournament Round 20260605T082006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T08:20:53.482750Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a TIME-STOP: trac... | `sma_crossover_qqq__mut_9e748e` | 🟢 PROMOTE | medRet=+3.13% pos=62% medSharpe=2.68 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_9e748e` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a TIME-STOP: track entry bar index in position_state and force-close the position after N bars have elapsed, regardless of the parent's exit signal. Hypothesis: trades that haven't worked within their typical holding window are dead money tying up capital. Ground N in the PARENT PROFILE's holding distribution — N should be near the p75 holding-bars value (force out the slow 25% of trades). Justify the chosen N in the docstring. Time-stop is a HARD exit; it fires alongside (and after) parent's close signal in the same way a stop-loss does. Document whether time-stopped trades counted toward the parent's profitable or unprofitable bucket on average (you can infer from raw_trades holding_bars vs pnl correlation).
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_9e748e`
- WF: median return +3.13%, 62% positive, 88% beat BH-SPY, median Sharpe 2.68, worst -14.32%, best +19.63%, 142 total trades.

