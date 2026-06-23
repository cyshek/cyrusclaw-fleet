# CBOE SKEW-Index Overlay on the TQQQ Vol-Target Sleeve — VERDICT

**Date:** 2026-06-22
**Author:** trading-bench (subagent)
**Status:** RESEARCH / PAPER ONLY — quarantine candidate, never live
**Files:**
`strategies_candidates/leveraged_long_trend/backtest_voltarget_skew.py`,
`validate_skew.py`, `skew_result.json`, `validation_skew_result.json`

---

## ONE-LINE VERDICT

**DOES NOT BEAT the existing TQQQ vol-target sleeve. CLOSE the lane (clean negative).**
No SKEW-percentile variant — in either economic direction — beats the baseline on **BOTH** total return and continuous-span Sharpe (the required bar). The fear→derisk direction loses on both. The contrarian buy-the-fear direction is "Sharpe-only" (≈half the baseline's return), is the bull-beta artifact the prior flagged, and its Sharpe edge **collapses under a 1-day lag** (the tell of an overfit/timing-fragile signal). SKEW is also largely **redundant** with the sleeve's existing SMA-200 gate + inverse-vol sizing.

This is the same landing as the directly-analogous VIX-term-structure overlay (closed clean-negative 2026-06-22), confirmed now with CBOE SKEW back to 1990 (multiple bear regimes) on the proper vol-target engine. It also confirms the 2026-06-04 data-limited Alpaca-skew prior with far better data.

---

## 1. Reproduced-baseline control (MUST match before trusting anything)

| metric | target (on disk) | reproduced | match |
|---|---|---|---|
| full-window total return | +2078.6% | **+2085.1%** | ✅ (Δ from one extra ^GSPC-alignment day, identical to vixterm run) |
| full-period continuous-span Sharpe | 0.863 | **0.864** | ✅ |
| maxDD | −34.52% | −34.52% | ✅ |
| window | 2010-02-11 → 2026-06-22 (~4114d) | same | ✅ |

Baseline = TQQQ, SMA-200 trend gate, target_ann_vol 0.25, vol_window 20, w_max 1.0, T-bill cash, 2bps/side. `n_sig_missing = 0` (SKEW starts 1990, fully covers the 2010+ window). **Control passes → comparisons are trustworthy.**

---

## 2. Per-variant full-period return + continuous-span Sharpe (NET 2bps) vs baseline

**THE BAR: beat baseline on BOTH `full_ret` (2085.1%) AND `full_Sharpe` (0.864).**

| variant (NET 2bps) | full ret% | full Sharpe | OOS ret% | OOS Sharpe | DUAL-BAR |
|---|---:|---:|---:|---:|:--|
| **baseline** | **2085.1** | **0.864** | **381.3** | **0.856** | — |
| derisk_hard_0.80 | 442.2 | 0.592 | 85.2 | 0.455 | ❌ FAIL |
| derisk_hard_0.90 | 388.3 | 0.535 | 52.7 | 0.334 | ❌ FAIL |
| derisk_p50_0.80 | 1036.9 | 0.774 | 205.7 | 0.709 | ❌ FAIL |
| derisk_p50_0.90 | 960.7 | 0.726 | 174.8 | 0.625 | ❌ FAIL |
| derisk_p25_0.80 | 693.5 | 0.694 | 139.3 | 0.594 | ❌ FAIL |
| derisk_linear | 336.8 | 0.582 | 64.5 | 0.418 | ❌ FAIL |
| buy_fear_0.80 | 881.1 | 0.873 | 264.3 | 0.936 | ⚠️ Sh-only |
| buy_fear_0.90 | 959.0 | 0.979 | 304.9 | 1.113 | ⚠️ Sh-only |
| buy_fear_linear | 1016.5 | 0.875 | 290.3 | 0.940 | ⚠️ Sh-only |
| SPX b&h (ref) | 592.9 | 0.774 | 177.2 | 0.722 | — |

- **DIRECTION A — fear→derisk: every variant FAILS on BOTH axes.** Cutting exposure when SKEW is high bleeds 50–84% of the return AND lowers Sharpe (best derisk Sharpe 0.774 < 0.864). The natural hedge thesis is dead.
- **DIRECTION B — contrarian buy-the-fear: "Sh-only" — beats Sharpe, FAILS return.** Best (buy_fear_0.90) has Sharpe 0.979 but full return only **959% < half** of baseline's 2085%. The bar requires BOTH → it does not clear it. The higher Sharpe is bought by **shedding the leverage/return that the sleeve is paid to carry** (avg weight drops to ~0.31), i.e. it is a lower-octane sleeve, not a better one.

**No variant passes the dual bar. The best-return overlay is the baseline itself.**

---

## 3. Frozen OOS (train ≤2017-12-31, test 2018-01-01+)

Baseline OOS (NET 2bps): ret **+381.3%**, Sharpe **0.856**.

- Every **derisk** variant is far below baseline OOS on both return (52–206% vs 381%) and Sharpe (0.33–0.71 vs 0.856).
- Every **contrarian** variant beats baseline OOS Sharpe (0.94–1.11) but trails OOS return (264–305% vs 381%) → same "Sh-only" failure OOS as full-window.

**Threshold-neighbor honesty (derisk_p50 cut swept on IN-SAMPLE only, NET realistic):**

| cut | IS ret% | OOS ret% | OOS Sh | OOS vs base (pp) |
|---:|---:|---:|---:|---:|
| 0.70 | 250.6 | 158.6 | 0.642 | −198.9 |
| 0.75 | 251.0 | 157.0 | 0.626 | −200.5 |
| 0.80 | 226.7 | 189.6 | 0.680 | −167.9 |
| 0.85 | 194.3 | 182.2 | 0.654 | −175.3 |
| 0.90 | 240.0 | 159.1 | 0.595 | −198.4 |
| 0.95 | 259.1 | 220.0 | 0.685 | −137.5 |

The IS-best cut (0.95) frozen into OOS still trails baseline by **−137.5pp**. This is not a knife-edge argmax — it's a **uniformly losing field**: every derisk cut, in- and out-of-sample, is worse than doing nothing.

---

## 4. ⭐ 1-DAY-LAG ROBUSTNESS (the decisive test for the best variant)

Re-run with the SKEW signal lagged one extra whole trading day. **A real signal survives a 1-day shift; an overfit/timing-fragile one collapses.** NET 2bps.

**Best contrarian (buy_fear_0.90) — the only variant that beat ANY bar:**

| sig_lag | full Sharpe vs base | OOS Sharpe vs base |
|---:|---:|---:|
| 0 | **+0.115** | **+0.257** |
| 1 | +0.027 | +0.103 |
| 2 | −0.002 | +0.008 |

**The Sharpe edge decays to zero under lag.** By a 2-day shift the full-period Sharpe advantage is *negative* and the OOS advantage is +0.008 (noise). A structural signal would hold roughly flat across a 1-day shift; this one evaporates. **→ the contrarian Sharpe "edge" is timing-fragile = fake**, exactly the failure mode the task pre-registered. (And its return trails baseline at every lag — it never had the return half of the bar anyway.)

**Best derisk (derisk_p50_0.80):** negative Sharpe-vs-base at every lag (−0.09 → −0.035 → −0.038) and return −800 to −1048pp vs base at every lag. Dead regardless of timing.

---

## 5. Redundancy decomposition (is SKEW even adding anything?)

SKEW pctile cut 0.80, lookback 252d, on the baseline weight path:

- **corr(SKEW-percentile, vol-target weight) = +0.40.** SKEW-fear is materially correlated with the sleeve's *own* inverse-vol sizing — it is partly **relabeling the vol sizing already in the engine.**
- Of the 1141 "fear" days (pctile > 0.80): **46.4% the sleeve is ALREADY defensive** — 39 already gated to cash by SMA-200, 490 already scaled down by the vol target. Only 612 are at "full" exposure where SKEW could add something new.
- **Decomposition spread (calm − fear) forward sleeve return = −9.47%/yr.** Fear days had *higher* forward returns (52.3% ann) than calm days (42.8% ann). This is the engine of both failures: derisking on fear cuts the *better* days (→ bleeds return); buying the fear catches the V-recovery bounce (→ flatters Sharpe in a regime where every 2010-2021 dip recovered).

**Conclusion: the overlay is largely redundant** — it adds churn and re-expresses the vol sizing the sleeve already does, with no orthogonal predictive content that survives honest testing.

---

## 6. Stress windows (sleeve vs overlay)

| window | SPX | baseline | derisk_p50_0.80 | buy_fear_0.80 |
|---|---|---|---|---|
| **2018-Q4** (short, sharp) | −14.3% / dd −19.6% | −26.9% / −26.9% | −26.9% / −26.9% | −14.3% / −14.3% |
| **2020 COVID** (fast) | −4.6% / dd −33.9% | +2.0% / −20.8% | +2.0% / −14.9% | +1.3% / −17.0% |
| **2022 bear** (slow grind) | −20.0% / dd −25.4% | −17.8% / −17.8% | −17.8% / −17.8% | −9.3% / −9.3% |

- In the **fast COVID crash**, derisk modestly cuts drawdown (−14.9% vs −20.8%) at ~equal return — the *one* place a tail-fear signal could plausibly earn its keep (reacting faster than the 200-SMA), mirroring VIX-term. But like VIX-term this is a **tail-hedge that COSTS return over the full period**, not a return improver — and it does not move the full-period verdict.
- The contrarian variant's "wins" in 2018-Q4 and 2022 are exactly the bull-beta tell: it happened to be scaled down going in. It is not reacting to information; it is carrying less leverage.

---

## Pre-registered theses — confirmed/overturned

- **(A) fear→derisk (natural hedge): CONFIRMED LOSER.** Overturns nothing; matches the 2026-06-04 prior and the VIX-term verdict.
- **(B) contrarian buy-the-fear: CONFIRMED BULL-BETA ARTIFACT.** "Wins" Sharpe only by de-leveraging into calm and catching V-recoveries; fails the return bar, fails the 1-day-lag test, unstable across lookbacks (Sharpe 0.979/0.902/0.861 for 252/504/expanding). Exactly the warning in the task brief.

## Hard-rails compliance

Research-only. Wrote ONLY under `strategies_candidates/leveraged_long_trend/` (new files) + this report. No promotion, no crontab/cron_tick edits, no protected-engine edits (runner/* imported read-only), no live-strategy edits. Every SKEW read went through `cboe_cache.history_asof` / `level_asof` (asserts `date < asof` → no lookahead). Real OOS, 2bps/side, baseline-on-the-same-path, baseline control reproduced (0.864 ≈ 0.863) before any comparison.

---

## FINAL VERDICT

> **DOES NOT BEAT the existing TQQQ vol-target sleeve. CLOSE the lane.**
> The CBOE SKEW index — as a percentile-rank exposure modulator, in either direction, swept over cuts/off-weights/lookbacks — adds no return-and-Sharpe-positive, lag-robust, non-redundant edge on top of the SMA-200 + inverse-vol sleeve. The only "win" (contrarian Sharpe) is a bull-beta artifact that dies under a 1-day lag and never had the return. Clean negative, consistent with the VIX-term-structure result and the 2026-06-04 skew prior. Do not promote.
