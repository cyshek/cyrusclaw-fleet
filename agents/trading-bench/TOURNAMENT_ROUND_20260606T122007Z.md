# Tournament Round 20260606T122007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T12:20:55.655720Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and add a TRAILING STOP. ... | `breakout_xlk_regime__mut_f111eb` | 🟢 PROMOTE | medRet=+2.30% pos=88% medSharpe=2.10 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_f111eb` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and add a TRAILING STOP. Track the highest price seen since entry (running max) in position_state and close the position when price falls X% from that running max (NOT from entry price). Hypothesis: this lets winners run during sustained trends while still cutting them when a real reversal starts, capturing more of the parent's upside than a fixed-from-entry stop. Ground X in the PARENT PROFILE — the runup distribution shows how far typical winners run; X should be smaller than the median runup so the trailing stop fires on the give-back phase rather than the run-up phase. Justify the chosen X in the docstring. Trailing stop must NOT block parent's own close signal. position_state must reset running_max to entry_price on every new entry.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_f111eb`
- WF: median return +2.30%, 88% positive, 75% beat BH-SPY, median Sharpe 2.10, worst -0.37%, best +14.89%, 80 total trades.

