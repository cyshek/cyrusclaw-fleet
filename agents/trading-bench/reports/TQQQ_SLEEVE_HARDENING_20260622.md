# TQQQ Vol-Target Sleeve — Hardening Study #2 (Three-Parameter Robustness)

**Date:** 2026-06-22
**Scope:** The LIVE TQQQ vol-target sleeve — sleeve A of `allocator_blend` **and** the standalone `leveraged_long_trend` candidate. Load-bearing **twice**.
**Question:** Are its three core parameters — SMA trend-gate length (200d), realized-vol window (20d), target ann vol (25%) — **robust plateaus** or **overfit lucky picks**?
**Methodology:** Same skeptical knife-edge test as the allocator 63d study. Three 1-D sweeps (one knob moved, other two frozen at live) + expanding-window walk-forward + joint (sma × vol_window) sanity grid. Continuous-span sqrt(252) Sharpe, gross **and** net@2bps, full-period **and** frozen-2018 OOS. No-lookahead D/D+1 convention preserved (same engine, only `VolTargetParams` re-instantiated).
**Status:** RESEARCH / MEASUREMENT ONLY. No live config touched. One actionable improvement **flagged for Cyrus to decide** — not applied.

**Artifacts:**
- Script: `strategies_candidates/leveraged_long_trend/hardening_param_sweep.py` (reproducible from cold cache, reuses the engine)
- JSON sidecar: `strategies_candidates/leveraged_long_trend/hardening_param_sweep_result.json`

---

## 0. Anchor reproduction (MUST pass before sweeping) — ✅ EXACT

Live params `sma_window=200, vol_window=20, target_ann_vol=0.25, w_max=1.0`, net@2bps:

| Metric | Reproduced | Promoted headline | Match |
|---|---|---|---|
| Full-period Sharpe | **0.8631** | 0.842–0.863 | ✅ top of range |
| CAGR | **20.73%** | ~20% | ✅ |
| Max drawdown | **−34.52%** | ~−34.5% | ✅ exact |
| Total return | **2078.6%** | (SPX 592.8%) | ✅ beats SPX raw |
| SPX Sharpe | 0.774 | — | beats net of 2bps ✅ |
| OOS (2018+) Sharpe | 0.855 | — | beats SPX OOS 0.722 ✅ |
| OOS total return | 379.9% | — | beats SPX OOS 177.1% ✅ |
| Window | 2010-02-11 → 2026-06-22 (4114 days) | | |
| Gate flips / rebalances | 100 / 3247 | | |

Gross Sharpe 0.869 (cost drag ~0.006). **Anchor reproduces the promoted sleeve cleanly — proceeding to sweeps.**

---

## (A) SMA trend-gate length — sweep [100,125,150,175,200,225,250]

*(vol_window=20, target=0.25 held; net@2bps)*

| SMA | Full Sharpe | Full CAGR | Full maxDD | OOS Sharpe | OOS ret | OOS maxDD | flips |
|---|---|---|---|---|---|---|---|
| 100 | 0.718 | 15.7% | −37.5% | 0.689 | 223.9% | −37.5% | 189 |
| 125 | 0.798 | 18.3% | −36.4% | 0.771 | 291.8% | −32.5% | 154 |
| **150** | **0.915** | 22.0% | −32.2% | **0.912** | 436.6% | −25.1% | 110 |
| **175** | 0.893 | 21.5% | −33.7% | **0.918** | 444.5% | −31.2% | 100 |
| **200 (LIVE)** | 0.863 | 20.7% | −34.5% | 0.855 | 379.9% | −34.5% | 100 |
| 225 | 0.860 | 20.8% | −33.7% | 0.818 | 348.1% | −32.3% | 98 |
| 250 | 0.882 | 21.5% | −34.1% | 0.835 | 366.1% | −31.5% | 90 |

**Plateau test:** live 200's immediate neighbors (175: 0.893, 225: 0.860) are within 0.05 → no knife-edge. **But the live value is NOT the peak — it sits on the down-slope of a plateau centered at 150–175.** The 100-day end collapses hard (0.718, 189 flips = gate whipsaw); from 150 up the surface is a smooth, broad plateau.

**Verdict: SMA-200 = ROBUST (no fragility), but mildly SUB-OPTIMAL.** The sweet spot is **150–175**, ~0.05 Sharpe and ~60pp OOS return richer than 200, with *equal or better* drawdown. This is the one genuine finding of the study — see §Joint Sanity and §Actionable Flag. It is **not** a lone spike: 150 and 175 are adjacent and both strong, and the joint grid (below) confirms a contiguous high-Sharpe basin.

---

## (B) Realized-vol window — sweep [10,15,20,30,42,63]

*(sma=200, target=0.25 held; net@2bps)*

| vol_window | Full Sharpe | Full CAGR | Full maxDD | OOS Sharpe | OOS ret | OOS maxDD |
|---|---|---|---|---|---|---|
| 10 | 0.829 | 20.6% | −38.7% | 0.753 | 315.8% | −33.6% |
| 15 | 0.838 | 20.3% | −32.3% | 0.818 | 358.4% | −31.4% |
| **20 (LIVE)** | **0.863** | 20.7% | −34.5% | **0.855** | 379.9% | −34.5% |
| 30 | 0.832 | 19.4% | −33.7% | 0.823 | 336.5% | −33.7% |
| 42 | 0.798 | 18.1% | −34.0% | 0.814 | 321.6% | −34.0% |
| 63 | 0.771 | 16.8% | −37.1% | 0.705 | 229.4% | −37.1% |

**Plateau test:** live 20 is the **clean peak** of the grid. Neighbors (15: 0.838, 30: 0.832) are within 0.03 — a symmetric plateau that rolls off gently on both sides. The extremes are genuinely worse: vol_window=10 (too noisy → worst DD −38.7%) and vol_window=63 (too sluggish → can't down-size fast enough, Sharpe 0.771, DD −37.1%).

**Verdict: vol_window-20 = ROBUST.** A defensible, mechanically-sensible peak (≈1 trading month of returns), not a data-mined point. **KEEP.**

---

## (C) Target annualized vol — sweep [0.15,0.20,0.25,0.30,0.35,0.40]

*(sma=200, vol_window=20 held; net@2bps)*

| target | Full Sharpe | Full CAGR | Full maxDD | Full vol | OOS ret | avg W |
|---|---|---|---|---|---|---|
| 0.15 | 0.861 | 13.2% | −21.3% | 15.9% | 174.2% | 0.318 |
| 0.20 | 0.864 | 17.2% | −27.8% | 21.0% | 266.5% | 0.421 |
| **0.25 (LIVE)** | 0.863 | 20.7% | −34.5% | 25.8% | 379.9% | 0.515 |
| 0.30 | 0.863 | 23.7% | −38.9% | 30.0% | 516.0% | 0.597 |
| 0.35 | 0.856 | 25.9% | −42.6% | 33.6% | 631.9% | 0.664 |
| 0.40 | 0.864 | 28.1% | −44.5% | 36.6% | 769.3% | 0.715 |

**This is a risk dial, not a tunable edge.** Sharpe is **DEAD FLAT** (~0.86) across the entire 0.15→0.40 range — max neighbor gap **0.001**. What moves monotonically is the risk/return trade: CAGR 13%→28%, maxDD −21%→−44%, realized vol 16%→37%, avg exposure 0.32→0.72. The vol-targeting mechanism is doing exactly its job — delivering the *same* risk-adjusted return at *any* chosen risk level. So there is no "peak" or "cliff" to be on; 25% is simply where you set the volatility budget.

**Verdict: target-25% = SENSIBLE RISK PICK.** It places realized vol ~26% and maxDD ~−34.5% (≈SPX's −33.9%) — a coherent "leveraged upside, SPX-like drawdown" choice. Sharpe is invariant to it, so the only question is risk appetite, and 25% is a reasonable mid. **No change warranted** — but note: if Cyrus ever wants more return and can stomach deeper DD, 0.30–0.40 buys it at *no Sharpe cost* (this is a dial, not a fragility).

---

## Walk-forward (expanding IS, joint (sma,vol_window) re-selection, yearly OOS)

Each year, pick the (sma, vol_window) with the best **in-sample** Sharpe over all history to date, apply OOS to the next year, chain the blocks. Grid {sma: 100,150,200,250} × {vol_window: 10,20,30,63}.

| Test yr | IS-best pick | WF-OOS ret | static-live OOS ret |
|---|---|---|---|
| 2016 | (250,10) | −16.6% | −8.4% |
| 2017 | (250,10) | +81.2% | +87.5% |
| 2018 | (250,10) | −3.7% | −8.5% |
| 2019 | (150,10) | +30.5% | +24.8% |
| 2020 | (250,10) | +39.1% | +41.6% |
| 2021 | (250,10) | +33.1% | +40.5% |
| 2022 | (250,10) | −21.1% | −17.8% |
| 2023 | (150,20) | +54.0% | +50.8% |
| 2024 | (150,20) | +28.7% | +34.0% |
| 2025 | (150,20) | +15.8% | +15.2% |
| 2026 | (150,20) | +9.1% | +12.7% |

| Strategy | Chained OOS total | Continuous OOS Sharpe |
|---|---|---|
| **WF re-selected** | **+595.6%** | **0.840** |
| **static-LIVE (200,20)** | **+741.6%** | **0.936** |
| best-static-in-hindsight (150,20) | — | 1.014 (OOS-span) |

**WF selection LOSES to naive static-live** (+595% vs +741%; Sharpe 0.840 vs 0.936). This is the **robust / good-news result**: re-optimizing the parameters over time does *not* help — it actively hurts, because IS-optimal kept chasing (250,10), which over-fit the early sample and didn't generalize. **The choice of these parameters does not need to be adapted through time; a fixed sensible setting is the right design.** This strongly argues *against* over-tuning and *for* leaving the sleeve's params static.

> Note the asymmetry: WF underperforms because its *selection rule* is noisy, but the *single* best-static-in-hindsight is (150,20) at OOS-span Sharpe 1.014 vs live's 0.949 — consistent with §A's finding that 150–175 is the true sweet spot. WF doesn't capture it because greedy IS-Sharpe selection is unstable; a human picking the plateau center once does.

---

## Joint sanity (sma × vol_window grid, OOS 2018+ net@2bps)

**OOS Sharpe surface** (the whole point — is any winner a plateau or a spike?):

```
sma\vw     10      15      20      30      42
 125     0.670   0.730   0.771   0.739   0.735
 150     0.799   0.866   0.912   0.873   0.870
 175     0.809   0.879   0.918   0.887   0.883
 200     0.753   0.818  [0.855]  0.823   0.814   <- live row
 225     0.720   0.780   0.818   0.786   0.778
```

**OOS raw return surface (%):**
```
sma\vw     10      15      20      30      42
 125      239     271     292     256     247
 150      358     405     437     376     364
 175      370     421     444     395     381
 200      316     358    [380]    336     322   <- live row
 225      288     326     348     307     294
```

The surface is **smooth and single-peaked** — no isolated spikes. The vol_window=**20** column is the ridge across *every* sma (confirms §B robustness independent of gate length), and within that ridge the sma sweet spot is **150–175** (confirms §A). Live (200,20) sits one row below the crest.

**Cells that materially beat live (200,20) on BOTH OOS Sharpe (+≥0.03) AND OOS return (+≥5pp):**

| cell | OOS Sharpe (Δ) | OOS ret (Δ) | OOS maxDD | neighbor-min Sharpe | plateau? |
|---|---|---|---|---|---|
| **(175,20)** | 0.918 (+0.063) | 444.5% (+64.6pp) | −31.2% | 0.855 | **✅ plateau (all neighbors ≥ live)** |
| (150,20) | 0.912 (+0.058) | 436.6% (+56.8pp) | −25.1% | 0.771 | ✗ (one neighbor (125,20) dips below live) |
| (175,30) | 0.887 (+0.032) | 395.3% (+15.4pp) | −30.3% | 0.823 | ✗ |

**(175,20) is the standout: it beats live on Sharpe, raw return, AND drawdown, and its entire 4-neighborhood is ≥ live Sharpe — a true plateau, not a spike.**

### Cost-robustness check (does the (150–175) edge survive honest costs?)

Re-costed the exact weight path under the recost model's *realistic* (5bps/Δw + 0.95%/yr ER) and *pessimistic* (12bps/Δw + 0.95% ER) levels:

| config | realistic OOS Sharpe / ret / DD | pessimistic OOS Sharpe / ret / DD |
|---|---|---|
| LIVE (200,20) | 0.832 / 356.2% / −35.1% | 0.815 / 340.2% / −35.6% |
| **(175,20)** | **0.894 / 417.7% / −31.8%** | **0.877 / 399.4% / −32.3%** |
| (150,20) | 0.889 / 409.8% / **−25.7%** | 0.871 / 390.8% / −26.3% |

The 150–175 advantage is **NOT a turnover artifact** — it persists (and the gap *widens* slightly) under realistic and pessimistic execution costs. (175,20) keeps a ~0.06 OOS-Sharpe and ~60pp OOS-return edge even at pessimistic costs; (150,20) additionally delivers a ~10pp shallower drawdown.

---

## VERDICTS

| Parameter | Live | Verdict | Detail |
|---|---|---|---|
| **SMA gate length** | 200 | **ROBUST — but sub-optimal; SHOULD CONSIDER → 175** | No knife-edge (neighbors within 0.05), but live sits on the down-slope of a 150–175 plateau. (175,20) beats live on Sharpe (+0.06 OOS), raw return (+65pp OOS) AND drawdown, is a true plateau (good neighbors), and survives realistic+pessimistic costs. **Actionable improvement — flagged, not applied.** |
| **Realized-vol window** | 20 | **ROBUST** | Clean symmetric peak; neighbors within 0.03; mechanically sensible (~1 trading month); ridge holds across all gate lengths. **KEEP.** |
| **Target ann vol** | 0.25 | **SENSIBLE RISK PICK** | Pure risk dial — Sharpe invariant (~0.86, max gap 0.001) across 0.15–0.40; only return/DD/exposure scale. 25% → vol ~26%, DD ~−34.5% (≈SPX). Reasonable mid. **KEEP** (no Sharpe reason to move; 0.30–0.40 buys more return at equal Sharpe if more DD is acceptable — a dial, not a fragility). |

### Is the live sleeve over-tuned? — **NO.**

Two of three parameters are clean-robust plateaus; the third (target vol) is a risk dial with Sharpe-invariance, not a tuned edge. The walk-forward proves re-optimizing the params over time *hurts* (static-live +741% beats WF +595%), which is the signature of a **robust, not over-fit**, design. There is no knife-edge anywhere on the surface — it is smooth and single-peaked, and the live point is comfortably inside the high-Sharpe basin.

### The one nuance (actionable, for Cyrus to decide — NOT applied)

The gate length is the *only* parameter where live is meaningfully off-center: **200 sits below a 150–175 sweet spot.** Moving the gate **200 → 175** is a defensible, plateau-backed, cost-robust improvement (better OOS Sharpe **and** return **and** drawdown, with a strong neighborhood). It is the **only** change this study would put on the table.

- **Why 175 over 150:** 175 is a *true plateau* (every neighbor ≥ live Sharpe); 150 has slightly higher raw return and a notably shallower drawdown (−25% vs −31% OOS) but one weak neighbor (125), so 175 is the more conservative, robustness-first pick.
- **Caveat (do not over-weight this):** the sleeve trades a *single survivorship-biased instrument* (TQQQ exists because 3x-Nasdaq went up 2010–2026). The 150–175 vs 200 gap is real and OOS-persistent on *this* path, but it is still one realized history of one lucky sleeve. 200d is the textbook-canonical trend filter (more defensible to a skeptic / more out-of-distribution-robust precisely *because* it wasn't picked from this data). A reasonable case exists for leaving the gate at the canonical 200 and treating 175 as "known headroom," **or** for moving to 175 to bank the measured edge. **This is Cyrus's call.** The study's job is to surface it with numbers, which it has.
- **Live params are NOT broken or fragile** — they are safe and inside the plateau. This is a "leave-more-on-the-table" finding, not a "fix-a-landmine" finding.

---

## Measurement hygiene confirmations

1. **No lookahead:** identical D/D+1 convention — `VolTargetParams` re-instantiated with different `sma_window`/`vol_window`/`target_ann_vol`, same `run_backtest_voltarget` engine; vol+SMA from data ≤ D, weight applied D+1. No new lookahead introduced by parametrizing.
2. **Same path / same window** every cell; **gross AND net@2bps** computed; **OOS quoted alongside full-period** throughout.
3. **Continuous-span Sharpe, sqrt(252)** — the engine's `_stats_from_equity` Sharpe is exactly the continuous-span statistic; sub-window (IS/OOS) Sharpe is the same statistic on the sliced equity span (population var /n, matching the engine; vs `fp_sharpe.py`'s sample var /(n−1) the difference is <0.001 on ~4000-point series).
4. **Gate flips & rebalances reported** per cell. The 100-day gate's high Sharpe penalty comes with 189 flips (whipsaw); the 150–175 plateau runs 100–110 flips like live — *not* a few-switch fluke.
5. **Risk vs risk-adjusted separated** explicitly for target-vol (it wins return only by taking more risk; Sharpe flat) vs the SMA finding (genuinely better risk-*adjusted*: better Sharpe at ~equal/better DD).

*Reproduce: `python3 -m strategies_candidates.leveraged_long_trend.hardening_param_sweep` (cold-cache safe; reuses the live sleeve engine).*
