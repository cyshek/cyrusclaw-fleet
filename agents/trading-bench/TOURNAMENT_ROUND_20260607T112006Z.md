# Tournament Round 20260607T112006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-07T11:21:06.799842Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a REGIME-CONDITIO... | `sma_crossover_qqq__mut_c382b1` | 🟢 PROMOTE | medRet=+2.93% pos=62% medSharpe=2.54 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_c382b1` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a REGIME-CONDITIONAL hard stop-loss. Read SPY closes from `market_state['regime']`. When SPY is BELOW its 50-day SMA (bear/chop regime), apply a TIGHT stop (e.g. 0.5%). When SPY is ABOVE its 50-day SMA (bull regime), apply a LOOSE stop or no stop at all — trends should be allowed to breathe. CRITICAL: the parent's regime filter (if any) only gates ENTRIES; this directive adds regime-conditional behavior on EXITS, which the parent doesn't have. Ground both stop thresholds in the PARENT PROFILE — the tight stop should be near the parent's p75 drawdown (close to the median); the loose stop should be near or beyond p25. Justify both numbers in the docstring. Stop must NOT block parent's own close signal.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_c382b1`
- WF: median return +2.93%, 62% positive, 88% beat BH-SPY, median Sharpe 2.54, worst -15.74%, best +18.71%, 200 total trades.

