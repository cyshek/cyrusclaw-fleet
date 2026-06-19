# Tournament Round 20260526T051228Z

_Mode: LIVE LLM generation_
_Generated: 2026-05-26T05:15:28.186859Z_
_Candidates: 8_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq_regime` | Take the parent strategy and add a PARTIAL EXIT (s... | `sma_crossover_qqq_regime__mut_232050` | 🟡 REJECT_GATE | gate: median return +0.41% only beats parent (+0.41%) by +0.00pp; need ≥+0.10pp · medRet=+0.41% pos=75% medSharpe=2.95 |
| 2 | `sma_crossover_qqq_regime` | Take the parent strategy (which is trend-following... | `sma_crossover_qqq_regime__mut_87fa4b` | 🟡 REJECT_GATE | gate: median return -0.05% ≤ +0.00%; only 38% of windows positive (need ≥50%); median Sharpe -0.82 ≤ 0.50 · medRet=-0.05% pos=38% medSharpe=-0.82 |
| 3 | `breakout_xlk_regime` | Take the parent strategy and try a different lookb... | `breakout_xlk_regime__mut_d17bb6` | 🟡 REJECT_GATE | gate: median return +0.26% only beats parent (+0.33%) by -0.07pp; need ≥+0.10pp · medRet=+0.26% pos=75% medSharpe=1.93 |
| 4 | `sma_crossover_qqq_regime` | Take the parent strategy and add a volatility filt... | `sma_crossover_qqq_regime__mut_3e03e4` | 🟡 REJECT_GATE | gate: median return +0.41% only beats parent (+0.41%) by +0.00pp; need ≥+0.10pp · medRet=+0.41% pos=75% medSharpe=2.95 |
| 5 | `sma_crossover_qqq_regime` | Take the parent strategy and port it to a differen... | `sma_crossover_qqq_regime__mut_eae738` | 🟡 REJECT_GATE | gate: median Sharpe 0.39 ≤ 0.50 · medRet=+0.01% pos=50% medSharpe=0.39 |
| 6 | `sma_crossover_qqq` | Take the parent strategy and add a time-of-day fil... | `sma_crossover_qqq__mut_dd307e` | 🟡 REJECT_GATE | gate: median return +0.27% only beats parent (+0.31%) by -0.04pp; need ≥+0.10pp · medRet=+0.27% pos=62% medSharpe=2.36 |
| 7 | `breakout_xlk` | Take the parent strategy (which is trend-following... | `breakout_xlk__mut_87fa4b` | 🟡 REJECT_GATE | gate: median return -0.12% ≤ +0.00%; only 12% of windows positive (need ≥50%); median Sharpe -0.88 ≤ 0.50 · medRet=-0.12% pos=12% medSharpe=-0.88 |
| 8 | `sma_crossover_qqq` | Take the parent strategy and add a volatility filt... | `sma_crossover_qqq__mut_3e03e4` | 🟡 REJECT_GATE | gate: median return +0.31% only beats parent (+0.31%) by +0.00pp; need ≥+0.10pp · medRet=+0.31% pos=62% medSharpe=2.60 |

## Verdict counts

- **REJECT_GATE**: 8
