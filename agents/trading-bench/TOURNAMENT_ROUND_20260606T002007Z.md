# Tournament Round 20260606T002007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T00:20:49.924724Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and port it to a differen... | `breakout_xlk_regime__mut_eae738` | 🟢 PROMOTE | medRet=+0.48% pos=50% medSharpe=0.50 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_eae738` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and port it to a different symbol in the same asset class. For tech (XLK/QQQ), try SOXX, SMH, or VGT. For small-caps (IWM), try IJR or VB. Keep the strategy logic identical; only change the symbol and any symbol-specific params.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_eae738`
- WF: median return +0.48%, 50% positive, 62% beat BH-SPY, median Sharpe 0.50, worst -3.60%, best +14.26%, 137 total trades.

