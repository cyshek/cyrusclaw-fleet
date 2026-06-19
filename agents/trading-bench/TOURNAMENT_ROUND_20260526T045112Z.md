# Tournament Round 20260526T045112Z

_Mode: LIVE LLM generation_
_Generated: 2026-05-26T04:52:16.107298Z_
_Candidates: 3_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `breakout_xlk` | Take the parent strategy and add a hard stop-loss:... | `breakout_xlk__mut_9c230e` | 🟡 REJECT_GATE | gate: median return +0.40% only beats parent (+0.40%) by +0.00pp; need ≥+0.10pp · medRet=+0.40% pos=62% medSharpe=2.75 |
| 2 | `breakout_xlk` | Take the parent strategy and combine its entry sig... | `breakout_xlk__mut_90e1cb` | 🟡 REJECT_GATE | gate: median return +0.26% only beats parent (+0.40%) by -0.13pp; need ≥+0.10pp · medRet=+0.26% pos=62% medSharpe=1.53 |
| 3 | `sma_crossover_qqq_regime` | Take the parent strategy (which is trend-following... | `sma_crossover_qqq_regime__mut_87fa4b` | 🟡 REJECT_GATE | gate: median Sharpe 0.14 ≤ 0.50 · medRet=+0.01% pos=50% medSharpe=0.14 |

## Verdict counts

- **REJECT_GATE**: 3
