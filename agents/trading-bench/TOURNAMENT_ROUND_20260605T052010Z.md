# Tournament Round 20260605T052010Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T05:20:45.049981Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and replace the binary re... | `sma_crossover_qqq__mut_a6c41b` | 🟢 PROMOTE | medRet=+2.63% pos=62% medSharpe=2.44 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_a6c41b` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and replace the binary regime gate with a regime-score gate using `regime_score(spy_closes, period=50)`. Only enter when regime_score > 0.02 (SPY at least 2% above its 50d SMA). This is a stricter version of the regime filter.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_a6c41b`
- WF: median return +2.63%, 62% positive, 62% beat BH-SPY, median Sharpe 2.44, worst -1.24%, best +11.63%, 61 total trades.

