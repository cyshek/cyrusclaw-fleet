# DISPERSION / IMPLIED-CORRELATION REGIME — Lane 4 Research Report

**UTC:** 2026-06-04T06:09:46Z
**Agent:** research subagent (lane-dispersion) for Tessera (trading-bench)
**Scratch:** `strategies_candidates/dispersion_regime/`
**Driver:** `reports/_dispersion_driver.py` (throwaway; composes PUBLIC `backtest_xsec` + `runner.fp_sharpe.fp_continuous_sharpe`)
**Verdict:** **REJECT** (honest negative — best FP-cont Sharpe **+0.568**, gate bar is ≥1.0)

---

## 1. Protected-file integrity (verified at finish)

```
runner.py        4be185e4bdcb6f432d99b71b21a4859c  ✓
backtest.py      9444ee5be64d9fd2639fd8cb0a28e002  ✓
backtest_xsec.py 2278a4c8d8a66703da5cd6f2a0880061  ✓
risk.py          e4c227e019c99e7e52224eb2f91389b8  ✓
```
No edits to any protected/evaluator file. Eval = existing `fp_continuous_sharpe` over the canonical 8-window `NAMED_WINDOWS` panel, $1000 notional, active `CostModel.alpaca_stocks()`.

## 2. Signal definition

Cross-section = the 9 sector ETFs that constitute SPY: **XLK XLF XLE XLV XLI XLP XLY XLU XLB** (all ~1373 daily bars, fully present across the window — no survivorship). The instrument actually **traded** is SPY (single-name fractional deployment via the xsec idle-cash mechanism; the bench is BH-SPY).

Two dual second-moment, cross-sectional gauges, both strictly trailing (sector closes sliced to date ≤ current SPY bar — no lookahead):

- **`corr` — average pairwise realized correlation** `rho_bar(d)`: mean off-diagonal entry of the 9×9 Pearson correlation matrix of the sectors' trailing `corr_lookback`-day log-return series.
- **`dispersion` — cross-sectional stdev** of the sectors' trailing `disp_lookback`-day cumulative returns (the spread of component performance around the basket). Negated internally so "high gauge = more co-movement," consistent orientation with `corr`.

**Thesis (classic dispersion trade):** LOW correlation / HIGH dispersion → names idiosyncratic, index vol suppressed, trend persists → be LONG the index. HIGH correlation / LOW dispersion → everything co-moving = stress/crowding → de-risk. The `regime_side` knob A/Bs the sign (`long_when_low_corr` = thesis vs `long_when_high_corr` = null/anti-thesis). Exposure shapes: `binary` (full/flat at a trailing-percentile threshold) and `proportional` (linear in the gauge's own trailing percentile band).

## 3. Dispersion-NOT-vol-level diagnostic (the lane's core honesty test)

Correlation of each gauge series with **SPY's own 20d trailing realized vol** over a 255-point dense grid spanning the full sample:

| Gauge | corr with SPY realized vol | interpretation |
|---|---|---|
| `corr` (avg pairwise, lb40) | **+0.653** | **substantially a vol-level proxy** |
| `dispersion` (lb20) | **−0.065** | **genuinely orthogonal to vol level** |

This is the decisive structural result. The **average-pairwise-correlation gauge is materially contaminated by vol level (r=0.65)** — when SPY vol rises, sectors co-move, so `rho_bar` partly *re-labels* the already-REJECTED vol-level lane (best there +0.54). The **dispersion gauge is clean (r=−0.065)** — it measures cross-sectional spread independent of the index's own vol. Only the dispersion branch is admissible as a genuinely orthogonal signal.

## 4. Sweep grid + honest FP-cont Sharpe per cell

**Bench: BH-SPY FP-cont = +0.225** (8 windows, 8 trades).

Headline by family (full grid in `reports/_dispersion_results.json`):

### dispersion (orthogonal — the admissible branch), thesis side
| disp_lb | thr_pct | FP-cont | avg deploy | ann-on-deployed | trades | beats-BH wins |
|---|---|---|---|---|---|---|
| 20 | 0.6 | **+0.568** | 0.62 | +7.25% | 220 | 5/8 |
| 10 | 0.5 | +0.533 | 0.53 | +6.24% | 312 | 4/8 |
| 20 | 0.7 | +0.477 | 0.72 | +7.00% | 232 | 5/8 |
| 10 | 0.4 | +0.448 | 0.44 | +4.97% | 298 | 4/8 |
| 20 | 0.4 | +0.338 | 0.44 | +3.75% | 247 | 4/8 |
| 10 | 0.7 | +0.311 | 0.72 | +4.08% | 305 | 4/8 |
| 40 | 0.4 | +0.279 | 0.40 | +2.86% | 125 | 3/8 |
| 10 | 0.6 | +0.190 | 0.62 | +2.97% | 297 | 3/8 |

### corr (vol-contaminated — see §3), thesis side
Best +0.301 (lb60, thr0.4); most cells +0.0 to +0.3.

### corr INVERTED (anti-thesis null check)
Best **+0.505** (lb40, thr0.6) — **HIGHER than the thesis-side corr cells.** The corr branch's sign is wrong-way / unstable; this alone disqualifies the corr branch on top of its vol contamination.

### proportional
Strictly worse than binary (best +0.321), high churn (300+ trades).

## 5. Plateau vs knife-edge

- **dispersion (clean branch):** a soft, coherent plateau — every cell across disp_lb ∈ {10,20,40} × thr ∈ {0.4…0.7} is **positive**, ranging ~+0.19 to +0.57, peaking at lb20/thr0.6. No sign flips, no single isolated spike. This is a **real but weak plateau**, not a knife-edge. The best cell modestly beats BH (5/8 windows) with ~7.25%/yr on deployed capital.
- **corr branch:** rejected independently — (a) vol-contaminated (r=0.65), (b) the INVERTED null beats the thesis (sign instability).

## 6. SPX-relative comparison

Best admissible cell (dispersion lb20/thr0.6): **FP-cont +0.568 vs BH-SPY +0.225** — a genuine risk-adjusted improvement (~+0.34 Sharpe), achieved by sitting in cash during low-dispersion/co-moving regimes and avoiding part of the 2022 drawdowns. BUT it deploys only ~62% of capital on average and earns ~7.25%/yr on deployed — **below the gate's 8%/yr-on-deployed floor (clause f)** and far below the Sharpe ≥1.0 bar.

## 7. Verdict — **REJECT** (honest negative = success)

1. **Best FP-cont Sharpe +0.568 < 1.0 gate bar.** Does not clear the front door. (Also < clause-(f) 8%/yr-on-deployed floor at ~7.25%.)
2. **Only the dispersion gauge is structurally clean** (orthogonal to vol level, r=−0.065). The correlation gauge collapses into the already-rejected vol-level lane (r=+0.65) and additionally fails the sign check (inverted null +0.505 > thesis +0.301). The corr branch is the dead-lane trap the brief warned about, caught explicitly.
3. The clean dispersion branch is a **real but weak orthogonal signal** — coherent positive plateau, modest BH outperformance — but its edge (~+0.34 Sharpe over BH, ~0.57 absolute) is roughly the same magnitude as the best previously-rejected lanes (+0.54). It is NOT strong enough to promote.

**No promotion. Zero promotion authority exercised.** This is a clean, falsifiable negative: dispersion-as-orthogonal-signal is confirmed orthogonal but confirmed too weak; correlation-regime-as-signal is confirmed to be relabeled vol-level timing. Both fail the same way the vol lane did, for honest structural reasons.

---
*Artifacts: `strategies_candidates/dispersion_regime/{strategy.py,params.json}`, `reports/_dispersion_driver.py`, `reports/_dispersion_results.json`.*
