# Tournament Round 20260526T033647Z

_Mode: LIVE LLM generation_
_Generated: 2026-05-26T03:37:42.665048Z_
_Candidates: 3_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and try a different lookb... | `breakout_xlk__mut_d17bb6` | 🟢 PROMOTE | medRet=+0.34% pos=62% medSharpe=1.73 |
| 2 | `breakout_xlk_regime` | Take the parent strategy and combine its entry sig... | `breakout_xlk_regime__mut_90e1cb` | 🟢 PROMOTE | medRet=+0.19% pos=75% medSharpe=2.14 |
| 3 | `sma_crossover_qqq` | Take the parent strategy and add a time-of-day fil... | `sma_crossover_qqq__mut_dd307e` | 🟢 PROMOTE | medRet=+0.33% pos=62% medSharpe=2.78 |

## Verdict counts

- **PROMOTE**: 3

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk__mut_d17bb6` (parent: `breakout_xlk`)
- Directive: Take the parent strategy and try a different lookback / period parameter (e.g. SMA fast/slow, Donchian lookback, RSI period). Pick a value in the range 10-50 that is meaningfully different from the parent's value. Keep the rest of the strategy logic identical.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk__mut_d17bb6`
- WF: median return +0.34%, 62% positive, 88% beat BH-SPY, median Sharpe 1.73, worst -1.03%, best +3.26%, 46 total trades.

### `breakout_xlk_regime__mut_90e1cb` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and combine its entry signal with a second signal (e.g. require both an SMA crossover AND a recent breakout). Be explicit about the logical combination (AND vs OR). Exits fire on either parent's exit signal — never make a position harder to close than to open.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_90e1cb`
- WF: median return +0.19%, 75% positive, 75% beat BH-SPY, median Sharpe 2.14, worst -0.18%, best +2.40%, 60 total trades.

### `sma_crossover_qqq__mut_dd307e` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a time-of-day filter that only allows new entries during 14:30-20:00 UTC (US regular session). Bars are tagged with 't' in ISO8601 UTC. Closes still fire any time. The filter must NEVER trap an existing position long.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_dd307e`
- WF: median return +0.33%, 62% positive, 88% beat BH-SPY, median Sharpe 2.78, worst -1.27%, best +1.95%, 142 total trades.

