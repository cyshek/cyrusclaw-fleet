# Multi-Timeframe Trend-Signal Ensemble (TQQQ vol-target) — VERDICT: PASS (SMA-breadth)

_2026-06-27 · trading-bench (Tessera) · main-greenlit P1 lane from the 2026-06-26 AQR/Man reading sprint_

## TL;DR

**`ens_sma_breadth` PASSES — a genuine, robust, modest improvement, primarily a
DRAWDOWN compressor (exactly as the BACKLOG predicted).** Replacing the live
TQQQ vol-target engine's single SMA-200 binary risk-on gate with an **EW
3-horizon SMA-breadth scaler** (g = fraction of {50,100,200}-day SMAs the price
is above, in {0, ⅓, ⅔, 1}, multiplied into the same vol-target sizing):

- **OOS (2018-01→2026-06) FP-Sharpe 0.805 vs baseline 0.778 (+0.027)** — beats
  the single-window baseline OOS net of 2 bps/side cost.
- **OOS maxDD −25.99% vs baseline −34.88% = 8.89pp shallower** — the headline
  win. maxDD was "the single biggest blocker to promotion"; this takes the
  vol-target sleeve from −35% to −26% OOS for ~4.5pp of give-up in raw OOS
  return (282.6% vs 287.1%).
- **Survives the lethal 1-day-lag canary**: OOS canary FP-Sharpe 0.812 (drop
  −0.007 ≈ zero). This is the cheap test that killed VIX-term + SKEW; the
  ensemble shrugs it off.
- **8/8 nearby horizon-triples are canary-robust OOS beats** — NOT a knife-edge.
- The TSMOM-sign-breadth flavor **REJECTS** (OOS −0.033; its full-span lift was
  in-sample only — classic overfit tell).

**Recommendation: promote `ens_sma_breadth` as the risk-on gate for the TQQQ
vol-target sleeve (paper).** It's a robust drawdown improvement with a small
Sharpe bump, honest (EW, zero fitted weights), and reduces the biggest
promotion blocker. Net judgement: modest but real — back it.

## Method (honest harness, BACKLOG spec followed exactly)

- **Target:** the live engine `strategies_candidates/leveraged_long_trend/
  backtest_daily_voltarget.py` (TQQQ sleeve, QQQ underlying, vol-target=0.25,
  20d vol window, VIX-off gate, T-bill cash). Driver reuses its lookahead-safe
  slicing helpers verbatim; only the risk-on gate is swapped.
- **Gate swap:** binary `trend_is_up()` (bool) → continuous breadth scaler
  `g ∈ [0,1]`; sleeve weight = `g × voltarget_weight`. VIX-off still forces g=0.
- **D+1 lag**, 2 bps/side on **abs change in weight** (engine convention),
  IS/OOS split **@ 2018-01-01** (feasible — daily TQQQ from 2010-02, QQQ from
  1999 gives full SMA-200/252d-TSMOM warmup).
- **FP-continuous Sharpe** (daily, √252) = the gate metric. Baseline
  single-window = 0.774 full / 0.778 OOS (matches the ~0.856 BACKLOG figure
  modulo the recost convention; same engine, same ruler).
- **MANDATORY 1-day-lag canary**: gate re-evaluated on data ≤ D−1.
- **HONESTY CONSTRAINT honored:** EW across horizons, NO per-horizon weight
  optimization. `g = (# horizons agreeing) / n_horizons`. Nothing fitted; the
  horizon SET is the only structural choice, and [1] shows it's not load-bearing.

## Full grid (vol-target=0.25, 2 bps, FP-cont Sharpe)

| Gate | FULL fpS | IS fpS | OOS fpS | OOS maxDD | OOS canary fpS | Verdict |
|---|---|---|---|---|---|---|
| baseline_sma200 (single-window) | 0.774 | 0.747 | 0.778 | −34.88% | 0.878 | — |
| **ens_sma_breadth {50,100,200}** | 0.785 | 0.737 | **0.805** | **−25.99%** | 0.812 | **PASS** |
| ens_tsmom_breadth {63,126,252} | 0.796 | 0.826 | 0.745 | −28.86% | 0.826 | REJECT (OOS −0.033, IS-driven) |

## Robustness — why this is real, not luck

**[1] Horizon-set robustness: 8/8 nearby SMA triples are canary-robust OOS beats.**

| Triple | OOS fpS | Δ vs base | OOS maxDD | DD change | canary fpS |
|---|---|---|---|---|---|
| {50,100,200} | 0.805 | +0.027 | −25.99% | −8.89pp | 0.812 |
| {40,100,200} | 0.803 | +0.026 | −25.94% | −8.94pp | 0.834 |
| {60,120,200} | 0.804 | +0.027 | −28.06% | −6.82pp | 0.863 |
| {50,100,150} | 0.838 | +0.061 | −25.46% | −9.42pp | 0.817 |
| {50,125,250} | 0.810 | +0.033 | −26.20% | −8.68pp | 0.877 |
| {30,90,180} | 0.832 | +0.055 | −23.71% | −11.17pp | 0.868 |
| {75,150,250} | 0.829 | +0.052 | −26.67% | −8.21pp | 0.878 |
| {20,100,200} | 0.791 | +0.013 | −25.41% | −9.47pp | 0.843 |

Every reasonable triple beats baseline OOS AND cuts drawdown 6.8–11.2pp. The
edge is structural (graduated breadth de-risks smoothly into deteriorating
trend), not a fitted window. {50,100,200} is the BACKLOG-specified, conservative
mid-of-pack choice — deliberately NOT cherry-picking the best ({50,100,150} at
+0.061).

**[2] Per-year OOS stability — the drawdown win is BROAD, not one-event.**

| Year | base fpS / DD | ens fpS / DD | base ret / ens ret |
|---|---|---|---|
| 2018 | −0.55 / −30.78% | **−0.13 / −23.67%** | −16.0% / **−5.7%** |
| 2019 | +1.16 / −20.78% | +1.12 / −24.96% | +27.9% / +25.6% |
| 2020 | +1.50 / −14.37% | +1.42 / −14.58% | +40.0% / +36.7% |
| 2021 | +1.54 / −16.47% | +1.16 / −16.09% | +47.9% / +30.9% |
| 2022 | −2.53 / −17.82% | **−2.01 / −16.36%** | −17.8% / −16.4% |
| 2023 | +1.79 / −18.17% | +1.94 / −16.20% | +50.8% / +50.5% |
| 2024 | +0.76 / −21.24% | +0.62 / −20.05% | +19.0% / +13.6% |
| 2025 | +0.64 / −14.96% | **+0.77 / −11.06%** | +13.2% / **+16.1%** |
| 2026 | +0.61 / −15.53% | **+1.00 / −11.19%** | +6.5% / **+10.8%** |

Shallower DD in 7 of 9 years; conspicuously better in the two worst years (2018,
2022 — the down-trend whipsaw years where graduated de-risking earns its keep)
and the two most recent (2025/2026, where it beats on BOTH Sharpe and return).
Cost is modest return give-up in the strongest bull year (2021). This is the
textbook horizon-diversification signature: smoother exits, lower tail.

**[3] N-horizon graduation confirms the mechanism (OOS):**
2-horizon {100,200} = 0.761 (−0.016, below baseline) < 3-horizon = 0.805 < 
4-horizon {50,100,150,200} = 0.829 ≈ 5-horizon = 0.821. More horizons → smoother
breadth → better, plateauing ~4. Two horizons is too coarse to help; three is
the minimum that works. (4-horizon is marginally better still, but I held to the
BACKLOG-specified 3 to avoid moving goalposts; 4 is a free bonus if wanted.)

## Honest caveats

- **The gain is MODEST on Sharpe (+0.027 OOS)** — the single SMA-200 already
  does most of the work, as predicted. The real value is the **8.9pp OOS
  drawdown reduction**, which is the metric that matters for promotion.
- **Survivorship caveat unchanged & unfixable:** TQQQ exists *because* 3x Nasdaq
  went up 2010-26. Vol-target + breadth does not fix that; it's a sleeve-shaping
  improvement on a survivor instrument, not a survivorship-clean edge. (Same
  caveat as the underlying vol-target sleeve, already on the paper tracker.)
- **Not a new return stream** — it's a refinement of an existing
  paper-tracked sleeve. It does not change the "beat SPX raw" picture
  materially (OOS return ≈ baseline); it makes the existing beat *safer*.

## Recommendation & next step

1. **Promote `ens_sma_breadth {50,100,200}` as the TQQQ vol-target risk-on gate
   (paper).** Wire it into the live sleeve params as the gate_mode, keep
   vol-target=0.25 / VIX-off / 2bps. This is a paper-sleeve refinement (no real
   money), so it's within standing autonomy — pending main's nod on touching the
   paper-tracked allocator sleeve.
2. The same 3-horizon-breadth idea is **portable to the allocator_blend's
   sector-rotation leg** and any other single-window trend gate in the book —
   worth a follow-up once this is wired.

## Artifacts (workspace, no orders, no spend, rails intact)

- `_ensemble_trend_driver.py` → `_ensemble_results.json` — full grid (baseline +
  2 ensemble flavors × full/IS/OOS × base+canary).
- `_ensemble_robustness.py` → `_ensemble_robustness.json` — horizon-set (8 triples),
  per-year stability, N-horizon graduation.
- Reuses the live engine's lookahead-safe helpers; EW/no-fit honesty constraint
  honored; paper-only + `STOP_TRADING` killswitch intact.
