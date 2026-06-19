# Tournament Round 20260608T052006Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-08T05:20:41.779661Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and port it to a differen... | `breakout_xlk__mut_eae738` | 🟢 PROMOTE | medRet=+1.86% pos=75% medSharpe=1.02 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_eae738` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and port it to a different symbol in the same asset class. For tech (XLK/QQQ), try SOXX, SMH, or VGT. For small-caps (IWM), try IJR or VB. Keep the strategy logic identical; only change the symbol and any symbol-specific params.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_eae738`
- WF: median return +1.86%, 75% positive, 62% beat BH-SPY, median Sharpe 1.02, worst -10.74%, best +32.00%, 106 total trades.

