# Allocator Cadence Sweep — does re-targeting the live `invvol_63d` blend more/less often than MONTHLY beat it on RAW return?

**Date:** 2026-06-25
**Engine:** `_cadence_sweep.py` (+ diagnostics `_cadence_confound_diag.py`, `_cadence_robustness.py`, `_cadence_phase_detail.py`) → `reports/_cadence_sweep_result.json`, `reports/_cadence_confound_diag.json`, `reports/_cadence_robustness.json`, `reports/_cadence_phase_detail.json`
**Lane:** Rebalance-cadence optimization of the LIVE `allocator_blend` (inv-vol 63d risk-parity of TQQQ vol-target sleeve + sector-rotation top-2 sleeve). The live config rebalances **monthly** (`strategies/allocator_blend/params.json: monthly_cadence: true`). That cadence was a CHOICE in the original validation, never swept. **Question (binary, raw-return mandate):** does any cadence beat the monthly config on RAW cumulative return, net of realistic turnover, without wrecking Sharpe/maxDD?
**Benchmark to beat:** the CURRENTLY-LIVE **monthly** config — full Sharpe ≈1.003 / OOS 1.123 / maxDD −23.9% / **raw total return 984.7%** on this window (2010-02-12 → 2026-06-25, 4116 days). *(SPX raw = 582% floor; monthly already clears it — the bar here is **beat monthly's raw return**.)*

---

## ⭐ VERDICT — 🟢 **GREEN (measured).** Rebalancing the blend **QUARTERLY instead of monthly** robustly beats the live config on raw return — **+83pts (984.7% → 1068.0%)**, OOS **268% → 283%**, Sharpe **1.003 → 1.018** — at the same average exposure (avg w_tqqq 0.349 → 0.351, i.e. **not** a leverage-up confound) and costs only **~1pt of maxDD** (−23.9% → −24.9%). The edge is a **plateau, not a knife-edge**: every 2-monthly and 3-monthly phase beats monthly on BOTH full and OOS, anchor-independent.

**Recommended config change (for Cyrus to review + apply — I did NOT edit params.json):**
> In `strategies/allocator_blend/params.json`, change the cadence from monthly to **quarterly** (re-target at quarter-open only; keep the 5% churn guard and intramonth HOLD). Mechanically: replace the `monthly_cadence: true` gate with a quarter-change gate (re-target on a quarter boundary instead of a month boundary). **Net effect on this backtest: +83pts raw return, +0.015 Sharpe, +15pts OOS return, −1pt maxDD, and ~⅓ the rebalances (65 vs 196 → less operational churn).**

- **Beats monthly on RAW return, OOS-stable?** ✅ YES — full +83pts, IS +10pts (194→204%), OOS +15pts (268→283%). Beats in **both** eras.
- **Without wrecking Sharpe/maxDD?** ✅ Sharpe IMPROVES (1.003→1.018); maxDD ~1pt worse (−23.9→−24.9), which a faithful read calls "essentially flat," not "wrecked." (Quarter-anchor m=3 even gives −22.3% AND 1092% — strictly better on both.)
- **Plateau or knife-edge?** ✅ **Plateau.** 2-monthly (2/2 phases) and 3-monthly (3/3 phases) beat monthly full+OOS; only at 4-monthly+ does it turn phase-fragile. The recommended quarterly sits in the **middle of the robust band**.
- **Mechanism legitimate (not a hidden leverage-up)?** ✅ Quarterly runs the SAME avg TQQQ exposure as monthly (0.351 vs 0.349). The gain is a **negative rebalancing premium**: monthly snap-back repeatedly sells the sleeve that just outperformed (an implicit mean-reversion bet) which COSTS return on a trending sample; letting it ride a quarter captures within-quarter sleeve momentum while still re-anchoring risk often enough.
- **Faster cadences (weekly/biweekly/daily-churn)?** ❌ All LOSE raw return (971–980% vs 984.7%) — more turnover, marginally smoother. Faster is strictly the wrong direction here.

---

## Harness faithfulness (the sanity control — proves the rig reproduces the live config)

The "monthly baseline" is reproduced **two independent ways** and they agree to machine precision, AND reproduce the validated numbers:

| Path | Raw total ret | Full Sharpe | maxDD | avg w_tqqq |
|---|---|---|---|---|
| `ab.blend_portfolio()` (validated month-open engine, called directly) | 984.70% | 1.0029 | −23.90% | 0.3485 |
| `blend_with_cadence()` (my generalized loop, month-open trigger) | 984.70% | 1.0029 | −23.90% | — |
| **Match?** | ✅ (Δ<1e-6) | ✅ (Δ<1e-9) | ✅ | ✅ ≈0.349 (report says ~0.349) |

The validated report quoted Sharpe 1.014 / maxDD −23.9% on the 2026-06-18 window (4112 days); on today's 4116-day window the same engine gives **1.003 / −23.9% / 985%** (the regime report's 2026-06-25 reproduction matches this exactly). My generalized cadence loop is therefore a **faithful superset** of the validated engine: identical drift mechanics, identical 2bps one-way inter-sleeve cost, identical `_stats_from_equity` ruler — the ONLY thing that changes across cadences is the WHEN-to-rebalance.

**Engine reuse:** sleeve daily-return streams are `_allocator_blend_tests.build_sleeves()` output verbatim (cached in `_regime_sleeves.pkl`, built today over the common TQQQ-inception calendar — same caches/stats as the validated backtest; harness falls back to a live `build_sleeves()` if the cache is stale). The inv-vol 63d target-weight function is identical to the promoted `invvol_63d` blend and to `runner.allocator_paper_tracker`. Zero sleeve-logic reimplementation.

---

## Results — full cadence grid

Window 2010-02-12 → 2026-06-25 (4116 days). **NET** = after 2bps one-way inter-sleeve turnover cost; **gross** = zero-cost (isolates turnover drag). Sharpe via `_stats_from_equity` (population stdev, √252, the validated ruler); **fp** = `runner/fp_sharpe.py` continuous-span Sharpe (sample stdev) — reported as a cross-check (they agree to ~3 decimals here because n is large). Annual turnover = total one-way L1 inter-sleeve weight-change per year.

| Cadence | RAW net | RAW gross | cost drag | CAGR | Full Sharpe (fp) | maxDD | IS net (≤2018) | OOS net (2019→) | OOS Sharpe | Ann turnover | #rebal |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **monthly (LIVE baseline)** | **984.7%** | 988.7% | 4.0% | 15.7% | **1.003** (1.003) | **−23.9%** | 194.2% | **268.1%** | **1.123** | 1.12 | 196 |
| weekly | 971.3% | 976.4% | 5.1% | 15.6% | 1.005 (1.005) | −22.5% | — | 259.1% | 1.109 | 1.45 | 853 |
| biweekly | 979.3% | 983.6% | 4.3% | 15.7% | 1.008 (1.008) | −22.7% | — | 258.5% | 1.109 | 1.20 | 427 |
| **quarterly** | **1068.0%** | 1070.9% | 2.9% | 16.2% | **1.018** (1.018) | −24.9% | **204.2%** | **283.4%** | **1.151** | 0.76 | 65 |
| daily, 5% churn-guard | 980.3% | 984.7% | 4.4% | 15.7% | 1.005 (1.005) | −22.5% | — | 258.1% | 1.104 | 1.23 | 146 |

**Reading:** The two *faster*-than-monthly cadences (weekly, biweekly) and the daily-churn-guarded variant all **lose** raw return (971–980%) — they pay more turnover for a marginal maxDD improvement and ~flat Sharpe. The *slower* direction (**quarterly**) is the only calendar cadence that **beats** the baseline raw return, and it does so while **improving** Sharpe (1.018) and OOS (283%) and **cutting** rebalances to ⅓.

---

## Drift-threshold τ grid (rebalance only when |cur_w − tgt_w| exceeds τ)

Two natural drift metrics: **L1** = Σ|cur−tgt| across legs; **max-leg** = max|cur−tgt|. τ ∈ {0.02 … 0.25}.

| τ | L1 net | L1 Sharpe | L1 maxDD | L1 turn/yr | L1 #reb | ‖ | max-leg net | max-leg Sharpe | max-leg maxDD | max-leg turn/yr | max-leg #reb |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.02 | 967.9% | 1.006 | −22.3% | 1.63 | 674 | ‖ | 972.2% | 1.006 | −22.1% | 1.47 | 372 |
| 0.05 | 976.7% | 1.008 | −22.5% | 1.40 | 292 | ‖ | 980.3% | 1.005 | −22.5% | 1.23 | 146 |
| 0.10 | 980.3% | 1.005 | −22.5% | 1.23 | 146 | ‖ | 1010.6% | 1.006 | −21.6% | 0.92 | 58 |
| 0.15 | 1035.7% | 1.022 | −22.5% | 1.10 | 91 | ‖ | 1021.2% | 1.004 | −22.6% | 0.83 | 37 |
| 0.20 | 1010.6% | 1.006 | −21.6% | 0.92 | 58 | ‖ | 1065.0% | 0.993 | −24.0% | 0.71 | 24 |
| 0.25 | 1070.2% | 1.022 | −22.8% | 0.92 | 48 | ‖ | **1172.2%** | 1.029 | −24.1% | 0.54 | 16 |

**τ-robustness call — KNIFE-EDGE-ish / CONFOUNDED, NOT the clean expression.** The drift family *does* reach higher raw return than quarterly (max-leg τ=0.25 → 1172%), but for the wrong reasons:
1. **Monotone-with-τ** = the "win" just tracks "rebalance less often" (bigger τ → fewer rebalances → more drift). That's the same axis quarterly captures more cleanly, not an independent edge.
2. **Partial leverage-up confound.** The high-τ max-leg winners drift to a **higher avg TQQQ exposure** (avg w_tqqq 0.38 vs baseline 0.35) and let TQQQ run to **~100% of the book** (max effective w_tqqq 0.999) in some stretches — i.e. part of the extra return is just *more Nasdaq*, the same lever the blend's 70/30 dial already offers (`ALLOCATOR_BLEND_20260621.md`). See the confound diagnostic below.
3. **No τ plateau** — L1 and max-leg disagree on which τ is best, and the numbers jump around (max-leg Sharpe dips to 0.993 at τ=0.20 then back to 1.029 at τ=0.25). That non-monotone Sharpe is the signature of an unstable rule.

So the drift-threshold lane reaches the same *insight* (rebalance less) but via a **less clean, partly-confounded, knife-edge** path. **Quarterly is the simple, robust, exposure-neutral expression of the same effect** — which is why it's the recommendation, not the bigger drift number.

---

## The crux: confound check — is the slower-cadence win a genuine edge or a hidden leverage-up?

(`_cadence_confound_diag.json`.) For each cadence I tracked the **realized daily effective (drifted) w_tqqq**, and built a **fixed-weight monthly control** at each winner's avg exposure. If a "winner" just runs more TQQQ, its extra return is the existing weight-dial, not a cadence edge.

| Cadence | avg eff w_tqqq | [min..max] | net | Sharpe | maxDD | Fixed-monthly @ same avg w | → its net / Sharpe / maxDD |
|---|---|---|---|---|---|---|---|
| monthly baseline | 0.349 | 0.18–0.81 | 984.7% | 1.003 | −23.9% | — | — |
| **quarterly** | **0.351** | 0.19–0.83 | 1068.0% | 1.018 | −24.9% | w=0.351 | 1031.3% / 0.994 / −26.2% |
| drift maxleg 0.20 | 0.384 | 0.21–**0.999** | 1065.0% | 0.993 | −24.0% | w=0.384 | 1076.0% / 0.991 / −25.9% |
| drift maxleg 0.25 | 0.382 | 0.18–0.89 | 1172.2% | 1.029 | −24.1% | w=0.382 | 1073.1% / 0.992 / −25.9% |
| drift l1 0.25 | 0.357 | 0.17–**0.999** | 1070.2% | 1.022 | −22.8% | w=0.357 | 1038.6% / 0.994 / −26.1% |

**Reading — quarterly passes the confound test cleanly:**
- **Quarterly runs avg w_tqqq 0.351 ≈ baseline 0.349** → its +83pts is **NOT** leverage-up. And it beats even its OWN fixed-weight control (1068% vs 1031% at the same 0.351 avg), with **better** Sharpe (1.018 vs 0.994) and **better** maxDD (−24.9% vs −26.2%). So quarterly sits **above** the static return-vs-DD dial at equal exposure — a real (if modest) cadence dividend.
- **The high-τ drift winners are partly confounded:** they push avg w_tqqq to ~0.38 (more Nasdaq) and let TQQQ drift to ~100% — so part of their headline 1065–1172% is just the existing leverage lever. (maxleg 0.25 still beats its 0.382 fixed control, so it's not *purely* leverage — but it's a muddier read than quarterly's clean exposure-neutral win.)

---

## Cadence-period response — plateau, not a lucky point (`_cadence_robustness.json`, `_cadence_phase_detail.json`)

Phase-averaged "every-Nth-month" family (averaging over all N phase offsets removes anchor luck):

| Cadence | avg full net | avg Sharpe | avg maxDD | avg OOS net | phases beating monthly (full / OOS) |
|---|---|---|---|---|---|
| every 1mo (= monthly) | 984.7% | 1.003 | −23.9% | 268.1% | — |
| every 2mo | 1050.6% | 1.018 | −23.2% | 273.9% | **2/2 / 2/2** |
| **every 3mo (quarterly)** | 1071.1% | 1.018 | −23.8% | 278.2% | **3/3 / 3/3** |
| every 4mo | 1080.5% | 1.017 | −23.8% | 272.9% | 3/4 / **1/4** |
| every 6mo | 1017.2% | 0.992 | −23.9% | 252.9% | (degrading) |

- **The robust band is 2–3 months wide and centered on quarterly.** At N=2 and N=3, **every single phase** beats monthly on BOTH full and OOS (Sharpe 1.012–1.025, maxDD −23.1% to −24.9%). At N=4 it turns phase-fragile (only 1/4 phases beat OOS); by N=6 the Sharpe degrades below monthly. So the lesson is "rebalance ~quarterly," **not** "rebalance as rarely as possible" — the curve humps and rolls over.
- **Anchor robustness:** all three standard quarter anchors beat monthly (Jan/Feb/Mar-anchored → 1068% / 1076% / 1092%, Sharpe 1.018–1.029, maxDD −24.9% / −23.8% / −22.3%). The win does not depend on which months anchor the quarters.

**Per-year decomposition (quarterly − monthly net):** quarterly beat monthly in **10/17 years**. The edge is broad-ish and asymmetric — many small wins plus a few bigger ones in stress/chop years (**2022 +3.8pts**, 2012 +3.4, 2018 +2.3, 2025 +1.6, 2011 +1.2), with capped small losses (worst −3.3 in 2016, −1.1 in 2021). It is **not** one lucky year carrying the result; the biggest single contributor (2022, the bear) is exactly where "don't snap the just-outperformed defensive mix back down" pays — a sensible, not lucky, source.

---

## No-lookahead statement

- **Rebalance DECISION at date d uses only data ≤ d.** The inv-vol 63d target weight at any rebalance index `i` is computed from `sleeves[k][i-63 : i]` — sleeve returns **strictly before** `i` (the trailing realized vol). This is the *same* lookahead-safe target function as the validated `invvol_63d` blend and the live `allocator_paper_tracker`; changing the cadence changes only WHICH indices `i` trigger a rebalance, never what information the target at `i` may see.
- **Forward P&L is d→d+1.** Each day the buckets earn `sleeves[k][i]` (the return ending on `dates[i]`) AFTER any rebalance at `i`; no day's return feeds its own rebalance decision. No overlap leak.
- **Calendar triggers are causal:** month/quarter/week-open indices are determined purely from the date string, independent of returns.
- **Sleeve returns are PIT by construction** (inherited): TQQQ gate uses QQQ closes ≤ d and trailing realized vol; rotation ranks on prior month-end close. Adjusted close throughout (Yahoo v8 adjclose).
- **Harness-faithfulness proof** (monthly path reproduces the validated 984.7% / 1.003 / −23.9% to machine precision) confirms no inadvertent leak was introduced by the generalization.

---

## Honest caveats

1. **maxDD is ~1pt worse than monthly** (−24.9% vs −23.9%) at the standard Jan-anchor. This is within "essentially flat," Sharpe still improves, and quarter-anchor m=3 actually gives **better** maxDD (−22.3%) with **better** return (1092%) — but the headline standard-quarter config does pay ~1pt of drawdown for its ~83pt return gain. Not a wreck; disclosed.
2. **The absolute raw-return gain is meaningful but not dramatic.** +83pts on a 985% base ≈ +8.4% of final wealth over 16y (CAGR 15.7%→16.2%, +0.5pt/yr). It's a real, robust, free-ish improvement to a LIVE config — not a new strategy. Right-size expectations.
3. **The drift-threshold family can post bigger numbers (up to 1172%) but is the wrong tool** — partly a leverage-up confound (avg w_tqqq drifts to 0.38, TQQQ to ~100%) and knife-edge in τ. I deliberately do NOT recommend it; quarterly is the clean expression.
4. **Same survivorship-bull sample** (inherited, unfixable): TQQQ exists because 3× Nasdaq went up 2010–2026. The negative-rebalancing-premium that quarterly harvests is strongest in a trending/secular-bull tape; in a genuinely mean-reverting or choppy-sideways decade, *more*-frequent rebalancing could instead help. The 2–3mo plateau and the 2022-bear win give some comfort, but this is one regime.
5. **Don't over-extend the lesson.** "Rebalance less" is good only out to ~quarterly here; 4-monthly is phase-fragile and 6-monthly degrades Sharpe. The recommendation is specifically **quarterly**, the middle of the robust plateau — not "rebalance as rarely as possible."
6. **Live churn guard interaction:** the live tracker also applies a 5% per-leg churn guard at order time; this backtest models the inter-sleeve reweight directly. The quarterly recommendation keeps the churn guard (it only further suppresses tiny trades — strictly reduces turnover, can't hurt the thesis). The daily-churn-guarded cadence I tested (which IS essentially "churn guard every day") underperforms monthly, confirming the guard alone is not the lever — the calendar slowdown is.

---

## Canary / file-safety

- **No-lookahead canary: CLEAN** — every rebalance target uses only trailing (`< i`) sleeve returns; harness reproduces the validated baseline to machine precision (proof no leak was introduced).
- **Protected files: UNTOUCHED.** `params.json`, `allocator_paper_tracker.py`, `runner/*.py`, crontab — all mtimes predate this session; only `_cadence_*` scratch + `reports/_cadence_*` JSON were created. The recommended config change is **proposed here only**; I did NOT edit `params.json`.

---

## Recommended next steps

1. **Apply the quarterly cadence to the live `allocator_blend`** (Cyrus to review + edit `params.json`): re-target at quarter-open only, keep the 5% churn guard + intramonth HOLD. Expected: +83pts raw / +0.015 Sharpe / +15pts OOS / −1pt maxDD / ⅓ the rebalances. Low-risk: it's the same validated sleeves and inv-vol targets, just snapped 4×/yr instead of 12×/yr.
2. *(Optional)* Consider the **Mar-anchored** quarter (3/6/9/12) — on this sample it strictly dominated the standard Jan-anchor (1092% return AND −22.3% maxDD AND Sharpe 1.029). But that's a per-sample optimization; the plain calendar quarter (Jan-anchor) is the honest, no-tuning default and already wins. Don't anchor-mine.
3. *(Optional)* Re-confirm the quarterly edge on a **walk-forward of the inv-vol lookback** (the blend report flagged 63d as a first guess); cadence × lookback is a small 2-D grid and would harden the recommendation further.
