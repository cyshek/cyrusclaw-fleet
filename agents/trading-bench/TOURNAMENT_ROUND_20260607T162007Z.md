# Tournament Round 20260607T162007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-07T16:20:46.210662Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a PARTIAL EXIT (s... | `sma_crossover_qqq__mut_232050` | 🟢 PROMOTE | medRet=+3.08% pos=62% medSharpe=2.65 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_232050` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a PARTIAL EXIT (scale-out): when an open position has risen X% above entry, close HALF the position and keep the other half running on the parent's normal exit logic. Hypothesis: parent winners give back gains by holding to exit; locking in half de-risks while preserving upside. Ground X in the PARENT PROFILE — X should sit near the median runup so it fires on ~50% of winners. CRITICAL: position_state must track 'scaled_out' boolean per symbol so partial-exit only fires ONCE per trade. Implementation: emit a `sell` Action with `notional_usd=notional/2` or `qty=holding/2`. Parent's close signal still fires the remainder. Justify X in the docstring using the parent's runup percentiles.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_232050`
- WF: median return +3.08%, 62% positive, 88% beat BH-SPY, median Sharpe 2.65, worst -14.32%, best +19.63%, 142 total trades.

