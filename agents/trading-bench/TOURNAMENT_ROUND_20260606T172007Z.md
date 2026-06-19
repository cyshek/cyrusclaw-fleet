# Tournament Round 20260606T172007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T17:20:46.587045Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and port it to a differen... | `breakout_xlk__mut_eae738` | 🟢 PROMOTE | medRet=+0.59% pos=50% medSharpe=0.52 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_eae738` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and port it to a different symbol in the same asset class. For tech (XLK/QQQ), try SOXX, SMH, or VGT. For small-caps (IWM), try IJR or VB. Keep the strategy logic identical; only change the symbol and any symbol-specific params.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_eae738`
- WF: median return +0.59%, 50% positive, 75% beat BH-SPY, median Sharpe 0.52, worst -5.89%, best +18.61%, 208 total trades.

