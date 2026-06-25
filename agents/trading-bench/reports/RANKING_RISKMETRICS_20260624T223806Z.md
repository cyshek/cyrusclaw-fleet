# Tournament Leaderboard — risk-adjusted dimensions (Sortino + Calmar)

Generated 20260624T223806Z · source: validated daily series (4111 days, 2010-02-16→2026-06-18)

Ranked by **Sortino** (annualized, downside-deviation denominator). Sharpe, Calmar, CAGR, maxDD from the same series. Live realized-P&L shown for actual standing (tiny samples — noise until n>>20).

| # | Strategy | Sortino | Sharpe | Calmar | CAGR% | MaxDD% | Live $ | Live n |
|---|----------|--------:|-------:|-------:|------:|-------:|-------:|-------:|
| 1 | `allocator_blend` | 1.40 | 1.01 | 0.67 | 15.9 | -23.9 | -2.23 | 3 |
| 2 | `sma_crossover_qqq_regime` | 1.30 | 0.93 | 0.54 | 0.8 | -1.6 | +0.02 | 6 |
| 3 | `sma_crossover_qqq_rth` | 1.24 | 0.89 | 0.52 | 0.8 | -1.6 | +0.67 | 2 |
| 4 | `breakout_xlk__mut_c382b1` | 1.21 | 0.86 | 0.49 | 0.9 | -1.8 | +44.05 | 4 |
| 5 | `tqqq_cot_combo` | 1.18 | 0.85 | 0.61 | 16.6 | -27.3 | -43.05 | 10 |
| 6 | `rsi_oversold_spy` | 0.25 | 0.18 | 0.05 | 0.2 | -4.1 | +0.00 | 1 |
| 7 | `macd_momentum_iwm` | 0.23 | 0.17 | 0.04 | 0.1 | -3.5 | — | — |
| 8 | `volume_breakout_qqq` | 0.22 | 0.16 | 0.05 | 0.1 | -2.3 | — | — |

**Sortino** = mean/downside-deviation × √252 (penalizes only downside vol). 
**Calmar** = CAGR / |maxDD| (return per unit of worst drawdown). 
Both add the drawdown-shape dimension the P&L-only ranking lacks — two strategies with the same total return but different DD profiles now separate.

> ⚠️ **Scaling caveat:** the 6 event sleeves are zero-cost SIGNAL-SHAPE daily series (~1% vol, per-unit-signal, NOT capital-scaled); the 2 levered sleeves (`tqqq_cot_combo` ~20% vol, `allocator_blend` ~16% vol) embed their leverage. So **Sortino + Sharpe (scale-INVARIANT ratios) are the valid cross-strategy dimensions**; absolute CAGR / Calmar are only comparable WITHIN the same scaling class (don't read the event sleeves' CAGR as an economic return). For the live book's actual capital-weighted return, see the ERC weighting work.