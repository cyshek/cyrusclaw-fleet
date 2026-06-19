# Tournament Round 20260608T012007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-08T01:20:43.611191Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and try a different lookb... | `breakout_xlk__mut_d17bb6` | 🟢 PROMOTE | medRet=+2.56% pos=62% medSharpe=1.72 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_d17bb6` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and try a different lookback / period parameter (e.g. SMA fast/slow, Donchian lookback, RSI period). Pick a value in the range 10-50 that is meaningfully different from the parent's value. Keep the rest of the strategy logic identical.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_d17bb6`
- WF: median return +2.56%, 62% positive, 62% beat BH-SPY, median Sharpe 1.72, worst -13.92%, best +32.63%, 58 total trades.

