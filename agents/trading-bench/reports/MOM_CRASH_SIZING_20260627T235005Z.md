# Momentum-Crash-Aware Sizing Overlay - leveraged_long_trend TQQQ vol-target

**UTC:** 20260627T235005Z | **RESEARCH-ONLY (paper bench).** No live engine/tracker/db/crontab touched. The 6 protected hard-rail files are byte-identical (md5 verified).

## Thesis
The live sleeve sizes TQQQ by INVERSE of trailing-20d **price** realized vol (`w = clamp(0.25 / realized_ann_vol, 0, 1)`, SMA-200 risk-on gate, 2bps/side on abs(dw)). That is a **lagging, symmetric** vol response: it cuts AFTER vol spikes, so it still eats ~-34.5% maxDD in 2018-Q4 / 2022 fast reversals -- going INTO the crash, price-vol is still low and only spikes after the damage. Barroso & Santa-Clara (2015, *Momentum has its moments*) showed scaling momentum exposure by a **forward-looking / faster** estimate of the strategy's own return-vol materially cuts the left tail at little CAGR cost. **Question:** does a momentum-crash-aware sizing layer cut the deep drawdown WITHOUT surrendering the raw-return SPX beat, OOS, net of cost?

## Method
- Baseline = the shipped engine `run_backtest_voltarget` (target=0.25, vol_window=20, vix_off) -- authoritative reproduction.
- Variants = a **faithful clone** of that engine's sim loop, identical EXCEPT the vol estimator feeding `clamp(target/vol, 0, w_max)`. Same TQQQ path, same 2bps/side abs(dw) cost, same SMA-200 gate, same T-bill cash, same D/D+1 lag, same ^GSPC benchmark on the identical calendar. The clone is verified to reproduce the engine on the baseline estimator.
- **Headline Sharpe** = `fp_continuous_sharpe` on the single continuous equity curve (asserted equal to the engine's `_stats_from_equity` Sharpe).
- **OOS split @ 2018-01-01**; IS and OOS reported separately. Verdict hinges on OOS.
- **+1-bar canary:** every variant re-run with the sizing signal lagged ONE EXTRA bar. If the DD edge collapses under +1-bar lag it is a timing artifact = NO-GO.

### Variants tested
- **A_fast_ewma_hl10** - EWMA vol, half-life ~10d (faster reaction than 20d std).
- **B_barroso_126_21** - 6-month (126d) realized-vol forecast MAX-blended with a fast 21d spike (the literal published constant-vol-target construction).
- **C_asym_10_40** - asymmetric down-only fast cut: MAX(10d fast, 40d slow) vol -> quick to de-risk, slow to re-risk.
- **D_ewma_crashflag** - A + a hard exposure cap (0.30) for 10 days after a detected sharp sleeve drawdown (<= -15% over a trailing 60d window).

## Baseline reproduction check

| | total ret % | maxDD % | stats Sharpe | fp Sharpe |
|---|---|---|---|---|
| engine FULL | 2026.4 | -34.52 | 0.857 | 0.857 |
| known (validation json) | 2025.5 | -34.52 | 0.859 | - |
| clone FULL | 2026.4 | -34.52 | 0.857 | 0.857 |

- engine OOS: strat **368.4%** vs SPX 172.9%, maxDD -34.52% (known 368.2% / 174.7% / -34.52%).
- engine IS: strat 332.0% vs SPX 147.9% (known 332.0% / 147.9%).
- **reproduction all_ok = True** (checks: {"engine_vs_known_full_maxdd": true, "engine_vs_known_full_sharpe": true, "engine_vs_known_full_totret": true, "engine_vs_known_oos_ret": true, "engine_vs_known_oos_maxdd": true, "engine_vs_known_is_ret": true, "clone_vs_engine_full_maxdd": true, "clone_vs_engine_full_totret": true, "clone_vs_engine_full_sharpe": true, "fp_equals_stats_sharpe_engine": true, "fp_equals_stats_sharpe_clone": true})

## Variants vs baseline (clone) -- net 2bps/side

Baseline (clone): FULL maxDD -34.52%, fpSharpe 0.857, totRet 2026.4%. OOS strat 368.4% vs SPX 172.9%, maxDD -34.52%.

| variant | FULL maxDD% | FULL fpSh | FULL totRet% | OOS strat% | OOS SPX% | OOS maxDD% | OOS dd vs base (pp shallower) | canary OOS maxDD% | canary vs-variant dd (pp, >0=falsifies) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| A_fast_ewma_hl10 | -32.22 | 0.816 | 1487.4 | 293.9 | 172.9 | -31.86 | +2.67 | -27.88 | +3.98 | **NO-GO** |
| B_barroso_126_21 | -30.03 | 0.783 | 928.3 | 181.9 | 172.9 | -30.03 | +4.49 | -26.79 | +3.25 | **NO-GO** |
| C_asym_10_40 | -31.49 | 0.821 | 1280.4 | 274.3 | 172.9 | -30.71 | +3.82 | -26.92 | +3.79 | **NO-GO** |
| D_ewma_crashflag | -31.91 | 0.797 | 1179.7 | 251.2 | 172.9 | -31.24 | +3.28 | -25.95 | +5.29 | **NO-GO** |

### Per-variant verdict reasons
- **A_fast_ewma_hl10 -> NO-GO**: guts the mission-beat: keeps only 62% of baseline SPX-beat margin and 80% of baseline OOS return (>SPX by only 121.0pp vs baseline +195.4pp) -- cutting DD by surrendering the raw-return edge is a NO-GO; +1-bar canary FALSIFIES timing: extra lag makes DD 3.98pp SHALLOWER (better), so the DD-cut is lower-exposure/noise, not crash-timing skill
- **B_barroso_126_21 -> NO-GO**: guts the mission-beat: keeps only 5% of baseline SPX-beat margin and 49% of baseline OOS return (>SPX by only 9.0pp vs baseline +195.4pp) -- cutting DD by surrendering the raw-return edge is a NO-GO; +1-bar canary FALSIFIES timing: extra lag makes DD 3.25pp SHALLOWER (better), so the DD-cut is lower-exposure/noise, not crash-timing skill
- **C_asym_10_40 -> NO-GO**: guts the mission-beat: keeps only 52% of baseline SPX-beat margin and 74% of baseline OOS return (>SPX by only 101.4pp vs baseline +195.4pp) -- cutting DD by surrendering the raw-return edge is a NO-GO; +1-bar canary FALSIFIES timing: extra lag makes DD 3.79pp SHALLOWER (better), so the DD-cut is lower-exposure/noise, not crash-timing skill
- **D_ewma_crashflag -> NO-GO**: guts the mission-beat: keeps only 40% of baseline SPX-beat margin and 68% of baseline OOS return (>SPX by only 78.3pp vs baseline +195.4pp) -- cutting DD by surrendering the raw-return edge is a NO-GO; +1-bar canary FALSIFIES timing: extra lag makes DD 5.29pp SHALLOWER (better), so the DD-cut is lower-exposure/noise, not crash-timing skill

## Why the DD reduction is NOT crash-timing skill (the real headline)

Two independent diagnostics show every variant's shallower drawdown is a **structural lower-exposure / noise-reversion artifact**, not momentum-crash skill:

**1. Return give-up is grossly disproportionate to the DD cut, and it guts the mission-beat.** The baseline OOS beats SPX by **+195.4pp** (368.4% vs 172.9%). The variants shave a few pp of DD but surrender most of that edge:

| variant | avgW (FULL) | OOS ret% | OOS ret kept vs base | SPX-beat margin kept | OOS maxDD% cut (pp) |
|---|---|---|---|---|---|
| baseline | 0.515 | 368.4 | 100% | 100% | -- |
| A_fast_ewma_hl10 | 0.490 | 293.9 | 80% | 62% | +2.67 |
| B_barroso_126_21 | 0.408 | 181.9 | 49% | 5% | +4.49 |
| C_asym_10_40 | 0.453 | 274.3 | 74% | 52% | +3.82 |
| D_ewma_crashflag | 0.459 | 251.2 | 68% | 40% | +3.28 |

The variants simply hold a **smaller average position** (avgW drops from ~0.52 to 0.41-0.49 FULL). Lower leverage mechanically cuts both DD and return -- B_barroso keeps only ~5% of the mission-beat margin (a SPX tracker), and even the best (A_fast_ewma) keeps ~62%. This is exactly the *cutting DD by giving up the mission-beat* that honesty rail #7 defines as a NO-GO.

**2. The +1-bar canary makes drawdown SHALLOWER, not deeper -- the lethal tell.** For a genuine crash-*timing* edge, lagging the sizing signal one extra bar should make DD *worse* (you react to the crash later). Instead, every variant's DD gets **shallower** under +1-bar lag (canary-vs-variant: A_fast_ewma_hl10 +3.98pp, B_barroso_126_21 +3.25pp, C_asym_10_40 +3.79pp, D_ewma_crashflag +5.29pp). DD improving under MORE lag proves the fast/forecast vol reaction is firing on noise during sharp V-bottoms (cutting right before TQQQ compounds hardest), not catching crashes. The timing has negative information value.

## VERDICT

**CLEAN NEGATIVE: no crash-aware variant cleared the OOS bar. The DD reductions came from structurally LOWER EXPOSURE (lower avgW), not crash-timing skill -- they got SHALLOWER under +1-bar lag (falsifying timing) AND surrendered most of the mission-beat (giving up huge raw OOS return to barely clear SPX). Cutting DD that way is a NO-GO per honesty rail #7.**

No crash-aware sizing variant earned a GO. To EARN a GO (honesty rail #7) a variant had to, OOS and net of cost: beat the live vol-target sleeve on maxDD by >=2pp (shallower) AND keep the raw-return mission-beat largely intact (>=75% of the baseline SPX-beat margin and >=85% of baseline OOS return) AND survive the +1-bar canary (DD edge must be timing-driven, not improved by extra lag). Every variant failed on the mission-beat AND on the canary: they cut DD only by de-leveraging, surrendering most of the raw-return edge, and their DD-cut got *better* under +1-bar lag (falsifying any timing claim). This is a clean negative -- no winner was manufactured.

## Honesty rails honored
- Baseline reproduced FIRST via the engine itself (all_ok=True) before any variant ran.
- Headline Sharpe = fp_continuous_sharpe (continuous span), never median-of-windows.
- SAME path, SAME 2bps/side cost, SAME ^GSPC benchmark on the identical calendar for baseline AND every variant.
- D+1 lag on all signals; +1-bar canary applied to every variant.
- OOS @ 2018-01-01 reported separately; verdict hinges on OOS.
