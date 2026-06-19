# Tournament Round 20260605T232007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-05T23:20:45.925827Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime` | Take the parent strategy and add a volatility filt... | `breakout_xlk_regime__mut_3e03e4` | 🟢 PROMOTE | medRet=+3.33% pos=75% medSharpe=3.33 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `breakout_xlk_regime__mut_3e03e4` (parent: `breakout_xlk_regime`)
- Directive: Take the parent strategy and add a volatility filter that gates new entries when 20-bar realized volatility (stdev of pct returns) exceeds a threshold. CRITICAL: pick the threshold so that on the parent's historical bars the filter would skip at least 15% of entries — a filter that never fires is dead code. Pick a value in the range 0.005–0.025 per-bar stdev. Document the chosen threshold in the docstring with one sentence explaining why. Already-open positions can still close normally. The filter must NEVER trap an existing position long.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/breakout_xlk_regime__mut_3e03e4`
- WF: median return +3.33%, 75% positive, 75% beat BH-SPY, median Sharpe 3.33, worst -1.83%, best +24.02%, 62 total trades.

