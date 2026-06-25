# L166 — Sortino + Calmar as Ranking Dimensions

**Date:** 2026-06-24
**Author:** Tessera (trading-bench)
**Assigned by:** main oversight cron — "ranking is total return + per-strategy P&L only; add Sortino and Calmar as ranking dimensions to the leaderboard/weekly report."
**Scope:** Built **in-scope** as a root-level augmentation (`_ranking_riskmetrics.py`). NO protected file modified (`runner/ranking.py` and all of `runner/*`, `risk.py`, `GATE.md` mtime-unchanged — verified). Artifacts: `reports/RANKING_RISKMETRICS_<ts>.md` + `reports/_ranking_riskmetrics_<ts>.json`.

---

## Deliverable

Sortino + Calmar are now computable ranking dimensions for the live book, produced by `_ranking_riskmetrics.py` (re-runnable). Current leaderboard (ranked by Sortino):

| # | Strategy | Sortino | Sharpe | Calmar | CAGR% | MaxDD% |
|---|----------|--------:|-------:|-------:|------:|-------:|
| 1 | `allocator_blend` | 1.40 | 1.01 | 0.67 | 15.9 | -23.9 |
| 2 | `sma_crossover_qqq_regime` | 1.30 | 0.93 | 0.54 | 0.8 | -1.6 |
| 3 | `sma_crossover_qqq_rth` | 1.24 | 0.89 | 0.52 | 0.8 | -1.6 |
| 4 | `breakout_xlk__mut_c382b1` | 1.21 | 0.86 | 0.49 | 0.9 | -1.8 |
| 5 | `tqqq_cot_combo` | 1.18 | 0.85 | 0.61 | 16.6 | -27.3 |
| 6 | `rsi_oversold_spy` | 0.25 | 0.18 | 0.05 | 0.2 | -4.1 |
| 7 | `macd_momentum_iwm` | 0.23 | 0.17 | 0.04 | 0.1 | -3.5 |
| 8 | `volume_breakout_qqq` | 0.22 | 0.16 | 0.05 | 0.1 | -2.3 |

**Cross-validation:** `allocator_blend` lands at Sharpe 1.01 / CAGR 15.9% / maxDD −23.9% — matches the validated allocator-blend numbers in MEMORY.md to the digit, confirming the pipeline is correct.

## Two deliberate design decisions

### 1. Source = validated daily series, NOT live trades
The live book has **1-10 fills per strategy** (most < 6 round-trips). Sortino/Calmar off that sample is **pure noise** — the existing leaderboard already disclaims "noise until n_trades >> 20." So the risk-adjusted dimensions are computed from the **backtested daily-return series** (`reports/_volaware_series.json`, 4111 days 2010→2026) — the statistically-valid source. Live realized-P&L is shown side-by-side for actual tournament standing. Computing these off the daily series is what makes them meaningful *at all* right now.

### 2. Definitions (canonical, reusing repo helpers where they exist)
- **Sortino** = mean(daily) / downside-deviation × √252. Downside deviation = RMS of `min(0, r)`. Reuses the √252 convention from `runner.fp_sharpe`. Scale-invariant.
- **Calmar** = CAGR / |maxDD|, both as fractions from the same series. CAGR via `runner.lane_honesty.cagr` (note: that helper returns a percent — handled). maxDD = compounded peak-to-trough of the cumulative-return curve.
- **Sharpe** = `runner.fp_sharpe.sharpe_from_returns(rets, 252)` (the canonical fn) — included as the anchor column.

## Honest caveat (stated in the artifact)
The 6 event sleeves are zero-cost **signal-shape** series (~1% vol, per-unit-signal, NOT capital-scaled); the 2 levered sleeves embed their leverage (~16-20% vol). So **Sortino + Sharpe (scale-invariant ratios) are the valid cross-strategy dimensions**; absolute CAGR/Calmar are only comparable *within* a scaling class — don't read the event sleeves' 0.8% CAGR as an economic return (it's per-unit-signal). For the book's actual capital-weighted return, the ERC weighting work is the reference. Sortino still ranks honestly across all 8 because it's a ratio.

## What Sortino/Calmar add
The P&L-only ranking can't distinguish two strategies with the same total return but different drawdown shapes. Sortino penalizes only downside vol (rewards strategies that are choppy-up but smooth-down); Calmar is return-per-unit-of-worst-drawdown. Here they cleanly separate the book into a top tier (allocator/sma-regime/sma-rth/breakout/tqqq, Sortino 1.18-1.40) and a weak tier (rsi/macd/volume, 0.22-0.25) — consistent with Sharpe but with the DD-shape dimension made explicit.

## Recommended permanent wiring (needs the protected-file owner)
To make this a standing part of the leaderboard/weekly report rather than a side artifact, `runner/ranking.py::compute()` should grow `sortino` / `calmar` / `sharpe` / `maxdd` columns and `format_chat()` should print them. That is a **protected-file edit** (`runner/ranking.py`), out of my write scope — handing the spec up:
- Add the daily-series risk metrics to each ranking row (the math is in `_ranking_riskmetrics.py`, ready to lift verbatim — `sortino()`, `max_drawdown()`, `calmar()`).
- Keep the live-P&L columns as the actual standing; add Sortino/Calmar as the risk-adjusted view with the same scaling caveat.
- Pin with a unit test in `tests/` asserting Sortino > Sharpe for a positively-skewed series and Calmar = CAGR/|maxDD| on a known curve.
- Same authorization class as the L134 fix (both touch protected `runner/*`).

## Net
L166's intent is delivered: Sortino + Calmar are now produced as ranking dimensions with a reproducible, cross-validated artifact, built without touching protected code. The permanent merge into `runner/ranking.py` is a one-step protected edit handed up with a ready-to-lift implementation.
