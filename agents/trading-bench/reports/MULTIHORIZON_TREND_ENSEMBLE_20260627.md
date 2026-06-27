# Multi-Horizon Trend Ensemble — TQQQ Vol-Target Sleeve

**Date:** 2026-06-27
**Lane:** Main-assigned (scoped per research note `memory/2026-06-26.md#L336`). Within-instrument horizon blending (NOT the multi-asset TSMOM portfolio blend, which is already paper-live).
**Type:** Gate-overlay A/B on a LIVE sleeve. No new return engine; reuses the validated vol-target engine read-only.
**Verdict:** **NEGATIVE — single SMA-200 baseline WINS. No promotion.** Horizon-ensembling on this leveraged single-instrument sleeve adds whipsaw, not diversification. The AQR/Man "horizon diversification lifts Sharpe" result does NOT transfer to a 3x single-name trend gate.

---

## TL;DR

| Gate | FULL Sharpe | OOS Sharpe | FULL CAGR | FULL maxDD | OOS maxDD | vs baseline |
|---|---|---|---|---|---|---|
| **baseline — single SMA-200** (live) | **0.854** | **0.987** | 20.5% | −34.5% | **−24.4%** | — |
| ens_majority (≥2-of-3 vote) | 0.726 | 0.792 | 16.0% | −37.5% | −36.1% | ❌ Δ−0.13 FULL / −0.20 OOS |
| ens_fraction (continuous EW vote) | 0.797 | 0.919 | 17.4% | −34.9% | −30.7% | ❌ Δ−0.06 FULL / −0.07 OOS |

Both ensemble designs are **strictly dominated** by the single-window baseline on Sharpe AND drawdown, IS and OOS. The faster horizons (SMA-50/100) re-enter into chop and amplify 3x drawdowns rather than catching extra trend.

---

## What was tested

**Thesis (AQR "A Century of Evidence on Trend-Following"; Man Group):** combining short/medium/long trend horizons (e.g. 1/3/12mo) lifts Sharpe via horizon diversification — different horizons catch different trend regimes and are imperfectly correlated. Our trend sleeves are confirmed single-window (`leveraged_long_trend` = SMA-200 only). So: does a 3-horizon EW vote beat the single SMA-200 gate on the live TQQQ vol-target sleeve?

**Three gates, identical sizing + harness** (only the trend gate varies; nothing re-tuned):
- **baseline** — `trend_up = (QQQ_close > SMA-200)`, the live sleeve gate.
- **ens_majority** — `trend_up = (≥2 of {SMA-50, SMA-100, SMA-200} say up)`; binary, fed to the existing `target_weight`.
- **ens_fraction** — continuous EW vote: `weight = voltarget_weight(any_horizon_up) × (n_up / 3)`; exposure scales with cross-horizon agreement.

**EW-across-horizons is enforced** (the honesty constraint main flagged): no horizon is weighted or tuned. Horizons fixed at 50/100/200 (the research-note example), never optimized.

**Harness (identical to the live sleeve — `backtest_daily_voltarget.py`, imported read-only):**
- Inverse-realized-vol sizing: target 25% ann, 20d rvol, w_max 1.0.
- **D+1 lag** (engine convention preserved): decide on underlying closes ≤ D_prev, hold day D.
- 2bps switch cost on |Δw|; T-bill cash on the (1−w) sleeve.
- TQQQ 2010-02-11 → 2026-06-26 (4,117 trading days; QQQ history from 1999 → full SMA-200 warmup).
- FP-continuous Sharpe (daily, √252) for FULL / IS(≤2018-12-31) / OOS(>2018-12-31).
- **+1-extra-day-lag canary**: every gate re-run deciding one extra trading day stale — the cheap lethal test that killed VIX-term and SKEW.

---

## Results & interpretation

**Baseline reproduces the documented sleeve anchor** (FULL Sharpe 0.854, OOS 0.987, CAGR 20.5%, maxDD −34.5%) — confirms the reimplemented per-day loop is faithful to the engine (matches the ~0.84-0.85 hardening anchor). The baseline is also **perfectly lag-robust** (OOS Sharpe 0.987 → 0.987 under +1-day lag, decay 0.000) — a clean sign for the incumbent.

**ens_majority is WORSE everywhere AND deeper drawdown.** FULL Δ−0.128, OOS Δ−0.195, FULL maxDD −37.5% (vs −34.5%), OOS maxDD −36.1% (vs −24.4%). The 2-of-3 vote *raises* 3x exposure as soon as the fast SMA-50/100 flip up — before the slow trend confirms — so it buys into bounces that fail, paying 3x on the reversal. More entries, worse risk.

**ens_fraction is also dominated**, though closer (FULL Δ−0.057, OOS Δ−0.068). Scaling exposure by agreement softens the majority gate's over-eagerness, but the OOS maxDD is still markedly worse (−30.7% vs baseline −24.4%) — the partial-exposure "1/3 / 2/3" states still hold the 3x sleeve through chop the SMA-200 gate would have sat out entirely in cash.

**Canary — the telling detail:** both ensembles' OOS Sharpe *improves* under +1 extra day of staleness (majority +0.082, fraction +0.048). A real fast-horizon edge would DECAY with extra lag; instead the inferior signal gets slightly *better* when made staler — direct evidence the fast horizons contribute whipsaw/noise, not timing edge. (The baseline, by contrast, is lag-invariant.)

### Why the AQR/Man result doesn't transfer here (mechanism, not dismissal)
AQR/Man document horizon-diversification on **broad multi-asset trend portfolios** (dozens of futures across equities/rates/FX/commodities), where different horizons fire on *different markets* and the cross-horizon correlation is genuinely low. This test is a **single leveraged instrument** (TQQQ). On one 3x name, the three horizons are highly correlated (they all read the same QQQ price), so there is no diversification to harvest — and the only thing the fast horizons add is earlier re-entry into chop, which a 3x sleeve punishes disproportionately. The single slow gate (SMA-200) is doing exactly the right job: stay in cash through the whipsaw the fast horizons would trade. **The mechanism is sound where AQR applies it; our sleeve is the wrong shape for it.**

---

## Decision

- **No promotion.** The live sleeve's single SMA-200 gate is kept unchanged — it dominates both ensembles on Sharpe and drawdown, IS and OOS, and is more lag-robust.
- **Lane CLOSED** for the leveraged single-name sleeve. Within-instrument horizon-ensembling is a multi-asset-portfolio technique; it does not improve a 3x single-name trend gate.
- **Re-open trigger:** if a genuine *multi-asset* trend sleeve is ever built (several uncorrelated futures/ETFs), horizon-ensembling there is worth a fresh test — that is the setting where AQR's diversification actually exists. Not on TQQQ.
- **Incumbent reassurance (bonus):** this exercise independently re-confirmed the single-SMA-200 sleeve's full anchor (Sharpe 0.854) and showed it is perfectly +1-day-lag robust — useful evidence the live sleeve isn't timing-fragile.

## Integrity

- **Protected runner md5s UNCHANGED:** `strategy_gen.py` `1ff0239d…`, `walk_forward.py` `6fb34eea…`, `backtest.py` `717c36e6…`, `risk.py` `e303317e…`.
- Sleeve engine files **untouched** (`backtest_daily_voltarget.py` / `backtest_daily.py` mtime 06-09, imported read-only).
- Live `strategies/leveraged_long_trend_paper/` and `strategies/allocator_blend/` **untouched**.
- No orders, no spend, no config/crontab change. Driver + datapack + this report only.

## Artifacts

- Driver: `reports/_multihorizon_trend_ensemble_driver.py` (read-only reuse of the vol-target engine; 3 gates × 2 lag-modes).
- Datapack: `reports/_multihorizon_trend_ensemble_result.json`.
- Pretty-print: `reports/_multihorizon_print.py`.
