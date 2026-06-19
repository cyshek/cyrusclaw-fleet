# Tournament Round 20260606T182007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T18:20:44.030214Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq_regime` | Take the parent strategy and add a PARTIAL EXIT (s... | `sma_crossover_qqq_regime__mut_232050` | 🟢 PROMOTE | medRet=+4.10% pos=75% medSharpe=3.08 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq_regime__mut_232050` (parent: `sma_crossover_qqq_regime`)
- Directive: Take the parent strategy and add a PARTIAL EXIT (scale-out): when an open position has risen X% above entry, close HALF the position and keep the other half running on the parent's normal exit logic. Hypothesis: parent winners give back gains by holding to exit; locking in half de-risks while preserving upside. Ground X in the PARENT PROFILE — X should sit near the median runup so it fires on ~50% of winners. CRITICAL: position_state must track 'scaled_out' boolean per symbol so partial-exit only fires ONCE per trade. Implementation: emit a `sell` Action with `notional_usd=notional/2` or `qty=holding/2`. Parent's close signal still fires the remainder. Justify X in the docstring using the parent's runup percentiles.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq_regime__mut_232050`
- WF: median return +4.10%, 75% positive, 75% beat BH-SPY, median Sharpe 3.08, worst -2.13%, best +13.74%, 88 total trades.

