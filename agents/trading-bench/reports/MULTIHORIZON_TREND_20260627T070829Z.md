# Multi-Horizon Trend-Ensemble Gate vs Single-SMA-200 Gate — TQQQ Vol-Target Sleeve

**Date:** 2026-06-27 (UTC stamp `20260627T070829Z`)
**Author:** Tessera (trading-bench, subagent)
**Status:** Paper research only. No live orders, no spend. No `runner/`, `strategies/`, `crontab`, or `*.db` modified (all read-only).
**Driver:** `reports/_multihorizon_trend_driver.py` · **Result JSON:** `reports/_multihorizon_trend_result.json`
**Engine reused (verbatim mechanics):** `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py`
**Baseline reference:** `reports/TQQQ_VOLTARGET_GATE_WRITEUP_20260621.md` (the live `leveraged_long_trend_paper` sleeve)

---

## VERDICT: **CLOSE** — clean negative. The 3-horizon ensemble does NOT beat the single SMA-200 gate.

Every ensemble variant **loses** to the single-SMA-200 baseline out-of-sample, net of cost, in **both** representations (SMA-vote and TSMOM-vote agree on the negative). The loss is **not** a leak (it has no edge for the canary to kill) and **not** a turnover tax (it loses even at 0 bps). The vol-target layer already does the risk-cushioning the ensemble is trying to add, so the participation ramp mostly **dilutes upside in the clean-trend years where a 3× sleeve earns its return**. Lane closed.

---

## 1. The thesis (and the precise experiment)

Our live trend sleeves are **single-window**: `leveraged_long_trend_paper` gates the TQQQ vol-target sleeve on **QQQ SMA-200 only**. AQR ("A Century of Evidence on Trend-Following") and Man Group document that **combining short/medium/long trend horizons** (e.g. SMA-50/100/200, or 1/3/12-month TSMOM) lifts Sharpe via **horizon diversification** — different horizons catch different trend regimes and are imperfectly correlated. The post-credit-crisis rise in cross-market correlation thins single-horizon trend's diversification, which *argues for* ensembling.

**Question:** does a 3-horizon equal-weight ensemble gate beat the single SMA-200 gate on TQQQ, out-of-sample, net of cost, surviving the +1-day canary?

**Isolation discipline — the whole experiment.** I reused the validated engine's mechanics **exactly** (vol-target 0.25, vol_window 20, w_max 1.0, 2 bps cost on absolute change in weight, T-bill cash, D→D+1 lag, frozen OOS split 2018-01-01). **The only thing that changes is the gate.** The gate emits a *participation fraction* `g(D) ∈ {0, ⅓, ⅔, 1}` that multiplies the vol-target weight:

> `w_final(D+1) = clamp( g(D) · clamp(0.25 / realized_vol₂₀(TQQQ through D), 0, 1), 0, 1 )`

So ⅔-on = hold ⅔ of the vol-targeted position. This is the **honest equal-weight-across-horizons** construction — **no per-horizon weight optimization** (more knobs = more overfit surface; explicitly avoided). The gate is on the **underlying (QQQ)**, like the live sleeve; SMA windows and TSMOM lookbacks are computed on QQQ adjclose, lookahead-safe (closes through D).

**Gates tested:**
- **BASELINE** — `g = 1.0` if QQQ > SMA-200 else `0.0` (reproduces the live sleeve gate).
- **SMA-ensemble (continuous)** — `g = mean[ price>SMA50, price>SMA100, price>SMA200 ]`.
- **Discrete majority** — `g = 1.0` iff ≥2 of the 3 SMA votes agree, else `0.0` (binary).
- **TSMOM-ensemble (robustness)** — `g = mean[ ret₆₃>0, ret₁₂₆>0, ret₂₅₂>0 ]` (~3/6/12-month).

**Sharpe convention:** headline = `runner.fp_sharpe.sharpe_from_returns` (ddof=1, √252) on the concatenated daily equity-return series over each span. (Cross-checked against the engine's ddof=0 Sharpe — identical to 3 dp at n≈4,117, so the convention choice is immaterial here.)

---

## 2. Baseline reproduction — confirmed faithful to the live sleeve

Span 2010-02-12 → 2026-06-26 (4,117 daily returns), OOS split 2018-01-01.

| Baseline (single SMA-200) | full | in-sample (→2017) | **OOS (2018→)** |
|---|---|---|---|
| Total return | **+2,002%** | +332% | **+387%** |
| CAGR | 20.5% | 20.4% | 20.6% |
| Sharpe (fp) | **0.854** | 0.849 | **0.858** |
| Ann vol | 25.8% | 25.8% | 25.7% |
| Max drawdown | **−34.5%** | −33.2% | −34.5% |
| Avg weight | 0.515 | 0.594 | 0.442 |

**Sanity check vs `TQQQ_VOLTARGET_GATE_WRITEUP_20260621`:** the doc's cost ladder puts the full-period at +1,863% (er_only) to **+2,026% (optimistic, 2 bps, no ER)** — my engine charges 2 bps with no expense ratio, so it lands at the optimistic rung (**+2,002%** ✓). Full Sharpe 0.854 sits inside the doc's 0.840–0.859 band ✓; full maxDD −34.5% matches −34.5/−35.1% ✓. OOS total **+387%** vs the doc's frozen-engine **+368%** (the doc cut off at 2026-06-08; mine extends 18 sessions further) ✓. **SPX OOS +175.1% matches the doc's +174.7% to a tenth.** The baseline is reproduced correctly — the comparison below is apples-to-apples.

Context benchmarks (same path): SPX full +582% / Sharpe 0.768 / −33.9%; TQQQ buy-and-hold full +34,760% / Sharpe 0.895 / **−81.7%** (uninvestable).

---

## 3. Head-to-head — every ensemble loses OOS

| Gate | full Sfp | full tot% | IS Sfp | OOS Sfp | OOS tot% | OOS maxDD | OOS avgW | OOS ann turnover |
|---|---|---|---|---|---|---|---|---|
| **baseline (SMA-200)** | **0.854** | **+2,002** | 0.849 | **0.858** | **+387** | −34.5% | 0.442 | **6.01** |
| sma_frac (½⅓⅔ ensemble) | 0.797 | +1,281 | 0.758 | 0.833 | +319 | −30.7% | 0.417 | 7.95 |
| sma_majority (≥2/3, binary) | 0.726 | +1,028 | 0.755 | 0.699 | +232 | −37.5% | 0.418 | 8.57 |
| tsmom_frac (3/6/12mo) | 0.876 | +1,971 | 0.945 | 0.812 | +321 | −26.5% | 0.430 | 6.37 |

**OOS deltas vs baseline (ensemble − baseline):**

| Gate | Δ Sharpe (OOS) | Δ total (OOS) | Δ maxDD (OOS) |
|---|---|---|---|
| sma_frac | **−0.025** | **−67.8 pp** | +3.8 pp (better DD) |
| sma_majority | **−0.159** | **−154.3 pp** | −3.0 pp (worse DD) |
| tsmom_frac | **−0.047** | **−65.2 pp** | +8.0 pp (better DD) |

Both honest EW representations (sma_frac, tsmom_frac) point the **same direction: negative**. The discrete majority is the worst of all (it throws away the vol-target's fine sizing for a coarse binary and still under-participates). **No variant beats the single window OOS.**

> **Honesty-rail nuance on `tsmom_frac`.** Its *full-period* Sharpe (0.876) edges the baseline (0.854) and its full maxDD is much softer (−26.5% vs −34.5%) — but that is **in-sample-concentrated** (IS Sharpe 0.945) and **does not carry out-of-sample** (0.812 < 0.858). This is exactly the full-period-number-flattered-by-the-pre-2018-in-sample mirage the bench's rails warn about. **OOS binds, and OOS it loses.**

---

## 4. The canary (+1 extra day) — confirms it's not even a leak

Shift the gate signal one **extra** day (total 2-day lag) and re-run. A real edge survives; a leak/luck collapses (the test that killed VIX-term + SKEW). Here there's no edge to kill — the ensemble is already behind at 1-day lag and **stays behind** at +1 day:

| Gate | OOS Sfp (1-day) | OOS Sfp (+1 day) | Δ |
|---|---|---|---|
| baseline | 0.858 | 0.872 | +0.013 |
| sma_frac | 0.833 | 0.842 | +0.009 |
| sma_majority | 0.699 | 0.736 | +0.037 |
| tsmom_frac | 0.812 | 0.806 | −0.006 |

**Ensemble − baseline AT +1 day** (does it ever overtake?): sma_frac **−0.030**, sma_majority **−0.135**, tsmom_frac **−0.066**. No. The baseline is genuinely better, by mechanism, not by a one-day lookahead artifact. (Mild +Δ under extra lag on these slow gates just means the gates are not finely timing-sensitive — not a hidden edge.)

---

## 5. Cost sensitivity — it loses even at 0 bps (so it's the gate, not the turnover)

The ensemble **trades more** — the participation multiplier ramps through ⅓ and ⅔ levels, lifting OOS annualized turnover to 7.95–8.57 vs the binary baseline's 6.01. The worry is that extra turnover eats any edge. It doesn't need to: there's no edge to eat. ΔSharpe (ensemble − baseline), OOS, at each one-way cost:

| One-way cost | sma_frac Δ | tsmom_frac Δ |
|---|---|---|
| 0 bps | −0.023 | −0.046 |
| 2 bps | −0.025 | −0.047 |
| 5 bps | −0.028 | −0.047 |

It is **already negative at zero cost.** Higher cost only widens the gap slightly. The deficit is intrinsic to the gate construction, not a transaction-cost tax.

---

## 6. Per-regime attribution — the economic story (baseline vs SMA-ensemble, by year)

| Year | base ret% | ens ret% | Δ ret% | base W | ens W | base DD% | ens DD% | note |
|---|---|---|---|---|---|---|---|---|
| 2010 | +12.8 | +17.2 | **+4.4** | 0.45 | 0.42 | −27.9 | −24.7 | choppy → helps |
| 2011 | −11.0 | −7.7 | **+3.2** | 0.41 | 0.36 | −26.2 | −21.7 | choppy → helps |
| 2012 | +24.3 | +23.9 | −0.4 | 0.56 | 0.47 | −19.8 | −18.2 | ~flat |
| 2013 | +70.1 | +58.9 | **−11.2** | 0.73 | 0.72 | −13.2 | −12.5 | clean bull → hurts |
| 2014 | +26.6 | +10.4 | **−16.2** | 0.72 | 0.67 | −14.7 | −15.9 | clean bull → hurts |
| 2015 | −6.0 | −11.2 | −5.3 | 0.52 | 0.48 | −19.3 | −18.3 | choppy → hurts |
| 2016 | −10.8 | −13.8 | −3.0 | 0.51 | 0.48 | −20.8 | −20.8 | choppy → hurts |
| 2017 | +91.5 | +83.2 | −8.3 | 0.85 | 0.83 | −9.1 | −9.4 | clean bull → hurts |
| 2018 | −3.9 | +2.3 | **+6.1** | 0.49 | 0.45 | −28.7 | −21.4 | **Q4 selloff → big help, DD −7pp** |
| 2019 | +24.8 | +15.7 | −9.2 | 0.57 | 0.55 | −22.7 | **−30.7** | hurts AND worse DD |
| 2020 | +48.7 | +44.1 | −4.6 | 0.38 | 0.37 | −20.8 | −18.8 | COVID: mild help on DD, costs return |
| 2021 | +35.8 | +20.1 | **−15.6** | 0.58 | 0.55 | −16.5 | −16.1 | clean bull → hurts |
| 2022 | −16.9 | −15.5 | +1.5 | 0.03 | 0.05 | −17.8 | −16.4 | both mostly flat (gate off) |
| 2023 | +50.8 | +50.5 | −0.2 | 0.47 | 0.43 | −18.2 | −16.2 | ~flat |
| 2024 | +29.0 | +20.7 | −8.3 | 0.54 | 0.51 | −19.7 | −19.2 | bull → hurts |
| 2025 | +14.9 | +19.5 | **+4.5** | 0.48 | 0.46 | −16.6 | −11.3 | choppy → helps, DD −5pp |
| 2026 | +8.3 | +11.5 | **+3.3** | 0.45 | 0.36 | −14.3 | −11.2 | choppy → helps |

**The pattern is exactly what horizon diversification predicts — it just doesn't pay here.** The ensemble's partial-participation ramp **cushions the whipsaw/selloff years** (2018 Q4 +6.1pp with DD −28.7%→−21.4%; 2010/2011/2025/2026 each +3–4.5pp, and lower maxDD in many years). But it **gives up large upside in the clean-bull years** (2013 −11pp, 2014 −16pp, 2021 −16pp, 2017 −8pp) — precisely the years a 3× Nasdaq sleeve makes its money. The clean-trend give-ups (−8 to −16pp) dwarf the choppy-year cushions (+3 to +6pp), netting ≈ −68pp OOS.

**Why:** the **vol-target layer is already the risk-cushion.** It shrinks the position when TQQQ vol spikes (which is when 3× ETFs bleed) and parks the sleeve in cash whenever QQQ's primary trend breaks. Layering an additional partial-participation ramp on top is largely **redundant on the downside** (the vol-target already de-risked) while **costly on the upside** (it under-participates when all three horizons aren't yet aligned, i.e. early/mid bull). The single SMA-200 gate, paired with vol-targeting, captures the trend cleanly; ensembling the gate just adds drag.

---

## 7. Deliverable summary

1. **Baseline (single SMA-200):** full Sharpe **0.854** / +2,002%; OOS Sharpe **0.858** / **+387%** / maxDD −34.5%. **Confirmed faithful** to the live sleeve (write-up's optimistic rung +2,026%, OOS +368%; SPX OOS +175% matches +174.7%).
2. **SMA-3-horizon ensemble (continuous):** OOS Sharpe **0.833** → **ΔSharpe −0.025**, **Δtotal −67.8pp** vs baseline. **Loses.**
3. **Discrete majority (≥2/3):** **ΔSharpe −0.159**, Δtotal −154.3pp. Worst variant.
4. **TSMOM 3/6/12-month ensemble:** **ΔSharpe −0.047**, Δtotal −65.2pp. **Agrees** (negative in both representations). Its better *full-period* Sharpe is an in-sample mirage that does not carry OOS.
5. **Canary (+1 extra day):** no edge to survive — ensemble−baseline stays **−0.030 / −0.135 / −0.066** OOS at +1 day (baseline +1d Sharpe 0.872 vs ensembles 0.842/0.736/0.806). Not a leak; baseline genuinely better.
6. **Turnover & cost:** ensemble OOS ann turnover **7.95–8.57** vs baseline **6.01** (it trades more), yet **loses even at 0 bps** (ΔSharpe −0.023 sma / −0.046 tsmom). Not a turnover tax — the gate itself is worse.
7. **Per-regime:** **helps** choppy/selloff years (2018 +6.1pp & DD −7pp, 2010/2011/2025/2026 +3–4.5pp, softer maxDD several years); **hurts** clean-bull years (2013/2014/2021 −11 to −16pp). The give-ups dwarf the cushions because the vol-target layer already handles the downside.
8. **VERDICT: CLOSE.** Honest negative. The single-window SMA-200 gate + vol-targeting beats the 3-horizon ensemble OOS, in both representations, at every cost rung, and is confirmed not-a-leak by the canary. No promotion. Do not torture the construction to manufacture a win — horizon-ensembling the gate adds drag because the risk job is already done by the vol-target.

**Report file:** `reports/MULTIHORIZON_TREND_20260627T070829Z.md`
**Confirmed:** no files in `runner/`, `strategies/`, no `crontab`, no `*.db` modified (all read-only); no orders placed; no spend.
