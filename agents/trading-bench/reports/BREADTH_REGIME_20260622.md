# BREADTH-REGIME OVERLAY — VERDICT: CLOSE-REDUNDANT (clean negative)

**Date:** 2026-06-22
**Lane:** Sector-breadth divergence as a regime overlay on the TQQQ vol-target sleeve
**Disposition:** **CLOSE-REDUNDANT — do NOT revive.** A clean negative, banked. No promote, no crontab.
**Bar:** beat the TQQQ 25%-vol-target SLEEVE on BOTH raw cumulative return AND continuous-span Sharpe, OOS-frozen 2018, net 2bps. (Beating SPX is not enough — the baseline already does that.)
**Code:** `strategies_candidates/leveraged_long_trend/backtest_voltarget_breadth.py`, `validate_breadth.py`
**Results JSON:** `breadth_result.json`, `validation_breadth_result.json`

---

## TL;DR

Sector breadth (% of the 11 SPDR sectors above their own 200d-SMA) does **NOT** lead the SMA-200 price gate — it fires **coincident or LATER**. As a de-risk overlay it **loses to the baseline sleeve by 126–221pp of OOS return and 0.13–0.28 of OOS Sharpe**, net of every cost level, at every threshold from 0.30→0.60. The mechanism is the **opposite** of the hypothesis: among days that survive the SMA-200 gate, *low* breadth carries *higher* forward sleeve returns (it's a buy-the-dip tell, not a topping tell). The hypothesis is **falsified**. This is the same fate as VIX-term (2026-06-22) and SKEW (2026-06-22): redundant with the price gate the sleeve already has.

Baseline reproduced **exactly** (full 2085.1% / Sharpe 0.864 / maxDD −34.52%; OOS@2bps 381.3% / 0.856), so the harness is trustworthy.

---

## The hypothesis (from the brief) and the decisive test

**Claim:** market *internals* (breadth) deteriorate **before** the cap-weighted index breaks its own 200d SMA — distribution shows up in the cross-section before the index level. If true, a breadth de-risk overlay would cut drawdowns AND preserve return by firing *earlier* than the SMA-200 gate.

**Falsifiable prediction:** breadth must (a) cross its de-risk threshold *before* QQQ breaks its 200d SMA in 2018-Q4 and 2022, AND (b) the overlay must beat the baseline sleeve OOS on return and Sharpe net of cost+lag. If breadth fires coincident → CLOSE-REDUNDANT (the VIX-term/SKEW fate).

### Result of the decisive lead-vs-coincident episode test

| Episode | Breadth first < 0.50 | SMA-200 gate first break | Lead (breadth − gate) | Verdict |
|---|---|---|---|---|
| **2018-Q4** | 2018-10-12 (b=0.30) | 2018-10-12 (b=0.30) | **0 trading days** | **COINCIDENT** |
| **2022 bear** | 2022-01-26 (b=0.455) | **2022-01-21** (b=0.818) | **−3 trading days** | **breadth LAGS** |

- In **2018-Q4** breadth and the price gate flip on the **same day**, and by then breadth is already at 0.30 — there is no early warning; breadth and price roll over together.
- In **2022** the price gate broke on **2022-01-21 while breadth was still healthy at 0.818**; breadth didn't cross 0.50 until **3 trading days later** (and 0.40 until 5 td later). Breadth was **slower** than the price gate, not faster.

**The leading-indicator premise is false.** Sector breadth is a coincident-to-lagging confirmation of the index trend, not a precursor.

---

## Headline performance (full window 2010-02-11 → 2026-06-22, GROSS)

| Variant | Total ret | CAGR | maxDD | Sharpe | avgW | rebal |
|---|---|---|---|---|---|---|
| **baseline (sleeve)** | **2085.1%** | **20.80%** | **−34.52%** | **0.864** | 0.515 | 3247 |
| hard_gate_0.50 | 1067.3% | 16.25% | −38.85% | 0.727 | 0.497 | 3080 |
| hard_gate_0.40 | 1301.0% | 17.56% | −35.51% | 0.765 | 0.505 | 3147 |
| half_gate_0.50 | 1508.5% | 18.55% | −35.32% | 0.801 | 0.506 | 3247 |
| cont_linear | 1317.8% | 17.64% | −36.02% | 0.774 | 0.502 | 3194 |
| SPX b&h | 592.9% | 12.59% | −33.92% | 0.775 | — | — |

Every breadth variant **loses to baseline on return AND Sharpe AND drawdown**. De-risking on low breadth doesn't even cut the drawdown — it makes it *worse* (−38.85% vs −34.52% for the 0.50 gate), because it sells into washouts and misses the rebound.

## Frozen OOS (2018→now), NET of 2bps — the bar that decides it

| Variant | OOS ret | OOS Sharpe | vs baseline ret | vs baseline Sharpe | Beats baseline? |
|---|---|---|---|---|---|
| **baseline** | **381.3%** | **0.856** | — | — | — |
| hard_gate_0.50 | 160.0% | 0.581 | **−221.3pp** | **−0.275** | NO / NO |
| hard_gate_0.40 | 228.0% | 0.686 | **−153.3pp** | **−0.170** | NO / NO |
| half_gate_0.50 | 255.3% | 0.727 | **−126.0pp** | **−0.129** | NO / NO |
| cont_linear | 221.4% | 0.683 | **−159.9pp** | **−0.173** | NO / NO |

**Not a single variant clears the bar on either metric, at any cost level (2/5/12 bps all concordant).**

---

## Why it fails — the redundancy decomposition (mechanism autopsy)

On in-market days (w_base>0, i.e. days that already survived the SMA-200 gate), split by breadth regime:

| Breadth thr | low-breadth days total | already gated out by SMA-200 | in-mkt LOW-breadth fwd ret (ann) | in-mkt HIGH-breadth fwd ret (ann) | spread (high−low) |
|---|---|---|---|---|---|
| 0.50 | 641 | **447 (69.7%)** | **+204.1%/yr** | +36.4%/yr | **−167.7%/yr** |
| 0.40 | 494 | **375 (75.9%)** | **+279.8%/yr** | +37.5%/yr | **−242.3%/yr** |

Two independent reasons the overlay can't add value:

1. **70–76% of low-breadth days are ALREADY flat** (the SMA-200 gate already moved the sleeve to cash). Breadth is mostly re-flagging days the price gate already handled — definitionally redundant.
2. **The residual low-breadth days that survive the gate have HIGHER forward returns** (+204%/yr vs +36%/yr). When QQQ is still above its 200d SMA but sector breadth is thin, that's a **buy-the-dip** configuration (mega-cap-led pullback that mean-reverts), not a topping signal. De-risking there throws away the sleeve's *best* forward days. This is why the COVID-2020 window shows baseline **+2.0%** but the breadth gates **−14% to −17%** (breadth hit 0.0 at the March-2020 bottom — see lookahead/sanity check — and the gates sold the low).

The sign of the edge is **backwards** from the hypothesis.

---

## Robustness / anti-overfit checks (all confirm the negative)

- **Threshold neighbors (fit IN-SAMPLE ≤2017 only, frozen OOS):** every threshold 0.30→0.60 has a **negative** OOS Sharpe margin vs baseline. The IN-SAMPLE-best threshold (0.30) frozen to OOS still loses (−70.8pp ret / −0.073 Sharpe). There is no threshold where breadth de-risking helps — it's structural, not a single bad pick.
- **1-day-lag robustness (hard_gate_0.40):** lag-0 −146pp, lag-1 −103pp, lag-2 −152pp OOS vs baseline — all deeply negative. The lag-1 wiggle is noise on a uniformly-losing signal; there is no fragile-but-real edge being missed.
- **All three cost levels (2 / 5 / 12 bps + ER) concordant** — not a cost-sensitivity artifact.

---

## Data + lookahead integrity

- **Universe:** 11 SPDR sector ETFs (XLK/XLF/XLE/XLV/XLI/XLY/XLP/XLU/XLB/XLRE/XLC), Yahoo v8 adjclose via `daily_bars_cache` (the same verified source as the sleeve). Survivorship-clean by construction (ETFs don't drop out of an index).
- **Ramp handled honestly:** XLRE (2015-10) and XLC (2018-06) are late entrants. Denominator = sectors with ≥200 prior closes as of D (eligible 9 → 10 → 11 over the window). No phantom backfill; `breadth_missing=0` (≥9 always eligible from 2010-02).
- **Lookahead guard PROVEN:** monkeypatched all of XLK's *future* bars to $0.01 (a synthetic future crash) → breadth on an earlier probe date was **bit-identical** (0.4444 = 0.4444). Future prices cannot leak backward. `state_asof` uses `bisect_right` on closes dated ≤ D only; SMA = trailing mean of closes ≤ D.
- **Sanity:** breadth = 0.0 at the March-2020 COVID bottom, recovers to 1.0 by Nov-2020 — correct directional behavior.
- **Timing convention** identical to the trend gate: weight held over D+1 decided from data ≤ D. Extra `breadth_lag` knob exercised in robustness.

---

## Verdict

**CLOSE-REDUNDANT.** Sector breadth does not lead the SMA-200 price gate (coincident in 2018-Q4, *lagging* by 3–5 td in 2022); as a de-risk overlay it loses to the baseline sleeve by 126–221pp OOS return and 0.13–0.28 OOS Sharpe at every threshold and cost level; and its mechanism is backwards (surviving low-breadth days carry *higher*, not lower, forward returns). This is the third overlay in a row (after VIX-term and SKEW) to die on the same rock: **the SMA-200 trend gate + inverse-vol sizing already capture the regime information these signals carry.** The sleeve is well-specified; bolt-on regime gates are redundant.

**Banked as a disciplined negative. Do not revive at the bench bar.** If a future lane wants market-internals, the lesson is that a *coarse 11-name sector breadth* is too slow/redundant — only a finer, genuinely-leading internal (e.g. credit-spread momentum, or single-name advance/decline with real PIT constituents) could plausibly clear, and even then the prior is low given three concordant redundancy results.

### One reusable win
The breadth engine (`build_breadth_series`, survivorship-clean with an honest eligibility ramp + proven no-lookahead) is a clean, tested primitive — reusable if a finer-universe internals lane is ever sourced.
