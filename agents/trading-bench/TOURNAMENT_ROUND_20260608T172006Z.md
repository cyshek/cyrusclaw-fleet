# Tournament Round 20260608T172006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-08T17:20:39.973487Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and port it to a differen... | `breakout_xlk__mut_eae738` | 🟢 PROMOTE | medRet=+1.27% pos=75% medSharpe=0.93 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_eae738` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and port it to a different symbol in the same asset class. For tech (XLK/QQQ), try SOXX, SMH, or VGT. For small-caps (IWM), try IJR or VB. Keep the strategy logic identical; only change the symbol and any symbol-specific params.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_eae738`
- WF: median return +1.27%, 75% positive, 75% beat BH-SPY, median Sharpe 0.93, worst -1.54%, best +20.10%, 68 total trades.

