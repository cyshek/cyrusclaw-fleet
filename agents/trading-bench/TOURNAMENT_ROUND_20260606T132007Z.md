# Tournament Round 20260606T132007Z

_Mode: LIVE LLM generation_
_Generated: 2026-06-06T13:20:47.499078Z_
_Candidates: 1_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a volatility filt... | `sma_crossover_qqq__mut_3e03e4` | 🟢 PROMOTE | medRet=+3.13% pos=62% medSharpe=2.68 |

## Verdict counts

- **PROMOTE**: 1

## Candidates flagged for manual promotion review

These passed code review AND the walk-forward fitness gate. **They are quarantined in `strategies_candidates/` and NOT yet scheduled.** Tessera must read the code + the walk-forward detail below and move the directory by hand to `strategies/` before any live paper trading.

### `sma_crossover_qqq__mut_3e03e4` (parent: `sma_crossover_qqq`)
- Directive: Take the parent strategy and add a volatility filter that gates new entries when 20-bar realized volatility (stdev of pct returns) exceeds a threshold. CRITICAL: pick the threshold so that on the parent's historical bars the filter would skip at least 15% of entries — a filter that never fires is dead code. Pick a value in the range 0.005–0.025 per-bar stdev. Document the chosen threshold in the docstring with one sentence explaining why. Already-open positions can still close normally. The filter must NEVER trap an existing position long.
- Quarantine path: `/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/sma_crossover_qqq__mut_3e03e4`
- WF: median return +3.13%, 62% positive, 88% beat BH-SPY, median Sharpe 2.68, worst -14.14%, best +19.63%, 142 total trades.

