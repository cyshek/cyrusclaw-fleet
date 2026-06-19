# Tournament Round 20260526T050733Z

_Mode: LIVE LLM generation_
_Generated: 2026-05-26T05:09:44.775392Z_
_Candidates: 6_

## Summary

| # | Parent | Directive | Candidate | Verdict | Notes |
|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq` | Take the parent strategy and add a hard stop-loss:... | `sma_crossover_qqq__mut_bef4cc` | 🟡 REJECT_GATE | gate: median return +0.31% only beats parent (+0.31%) by +0.00pp; need ≥+0.10pp · medRet=+0.31% pos=62% medSharpe=2.60 |
| 2 | `breakout_xlk` | Take the parent strategy and add a hard stop-loss:... | `breakout_xlk__mut_bef4cc` | 🟡 REJECT_GATE | gate: median return +0.35% only beats parent (+0.40%) by -0.05pp; need ≥+0.10pp · medRet=+0.35% pos=62% medSharpe=1.88 |
| 3 | `breakout_xlk_regime` | Take the parent strategy and port it to a differen... | `breakout_xlk_regime__mut_eae738` | 🟡 REJECT_GATE | gate: median Sharpe 0.33 ≤ 0.50 · medRet=+0.06% pos=62% medSharpe=0.33 |
| 4 | `sma_crossover_qqq` | Take the parent strategy and try a different lookb... | `sma_crossover_qqq__mut_d17bb6` | 🟡 REJECT_GATE | gate: median return +0.27% only beats parent (+0.31%) by -0.04pp; need ≥+0.10pp · medRet=+0.27% pos=62% medSharpe=2.27 |
| 5 | `breakout_xlk` | Take the parent strategy and add a REGIME-CONDITIO... | `breakout_xlk__mut_c382b1` | 🟡 REJECT_GATE | gate: median return +0.38% only beats parent (+0.40%) by -0.02pp; need ≥+0.10pp · medRet=+0.38% pos=62% medSharpe=2.70 |
| 6 | `breakout_xlk` | Take the parent strategy and replace the binary re... | `breakout_xlk__mut_a6c41b` | 🟡 REJECT_GATE | gate: median Sharpe 0.29 ≤ 0.50 · medRet=+0.04% pos=50% medSharpe=0.29 |

## Verdict counts

- **REJECT_GATE**: 6
