# Anti-Rearview Allocator Guardrail — Audit & Verdict

**Date:** 2026-06-27 (UTC stamp `20260627T211356Z`)
**Scope:** BACKLOG P3 hygiene / AQR "Rearview Mirror" #5 — does the live `invvol_63d`
allocator weighting over-react and abandon a diversifying sleeve at the wrong time, and
does a cheap guardrail (min-weight FLOOR and/or longer SMOOTHING) fix it without
degrading the validated operating point?
**Driver:** `reports/_antirearview_guardrail_driver.py` → `reports/_antirearview_guardrail_result.json`
**Engine (read-only, imported):** `_allocator_blend_tests.py` (`build_sleeves()` + `blend_portfolio()`), same as `runner/allocator_paper_tracker.py` uses. No sleeve logic reimplemented; `runner/`, `strategies*/`, crontab, `*.db` untouched.

---

## ⭐ VERDICT — **ADOPT 3-month weight SMOOTHING. No floor needed.**

The live inv-vol allocator **is mildly rearview-prone — but the pathology is on the *aggressive* sleeve, not the diversifier.** It systematically yanks the **TQQQ vol-target sleeve** down at its volatility-trough (a selloff spikes TQQQ's trailing vol → inverse-vol slashes its weight) right before TQQQ rebounds, so the book under-participates in the recovery. The **rotation (defensive) sleeve shows no such pathology** — cutting it is, if anything, mildly *correct*.

**The fix is not a floor.** A min-weight floor caps the *level* of a weight but not the *velocity* of the cut — and the inv-vol weights almost never get low enough for a 0.10–0.20 floor to bind (baseline min target ≈ 0.18). Floors do essentially nothing to the rearview metric or drawdown. **Smoothing addresses the velocity** (averaging successive monthly weight vectors prevents a single-month vol spike from slamming the weight down), and a **3-month simple average of the raw inv-vol weight vector** is the clean winner:

| | full Sharpe | full maxDD | CAGR | OOS Sharpe | OOS maxDD | rearview Δ (TQQQ, >5% cut) | max single monthly cut | turnover/rebal |
|---|---|---|---|---|---|---|---|---|
| **baseline `invvol_63d`** | 0.9984 | −23.90% | 15.64% | 1.1132 | −21.88% | **+1.23%** (rearview-prone) | **30.9%** | 0.093 |
| **`smooth_avg_3mo` (ADOPT)** | **1.0179** | **−23.48%** | **16.15%** | **1.1238** | **−20.93%** | **+0.17%** (cured) | **14.3%** | 0.066 |

**This is the rare guardrail that is pure upside:** it improves full Sharpe (+0.020), OOS Sharpe (+0.011), full maxDD (+0.4pt), OOS maxDD (+1.0pt), AND CAGR (+0.5pt), AND in-sample Sharpe (0.892→0.920, so it is **not** an OOS-only fluke — it improves IS and OOS together → no overfit), AND it lowers turnover (cheaper to run). It does all this *while* collapsing the rearview metric and halving the worst single-month weight yank. Cheap insurance that also happens to pay a small premium back.

> **Honesty note on the headline baseline.** The 2026-06-21 report quoted full Sharpe 1.014 / OOS 1.147 / maxDD −23.9% as of **2026-06-18** (4,112 days). This audit reproduces those numbers **exactly** when the path is truncated to 2026-06-18 (full **1.0144**, OOS **1.1466**, maxDD **−23.90%** — see below). On today's full cache (4,117 days, +5 sessions of fresh data) the recomputed baseline is **0.9984 / 1.1132 / −23.90%**; the Sharpe/CAGR drift is entirely the 5 added days (the TQQQ solo Sharpe drifted 0.864→0.854 identically). **Every variant in this audit is benchmarked on this same 4,117-day path** against the recomputed baseline — apples-to-apples. maxDD (−23.90%) and the latest month-open weights (w_tqqq 0.442 / w_rot 0.558) match the report to the digit.

**Baseline reproduction check (truncated to report as-of 2026-06-18):** full Sharpe **1.0144** ✅ (report 1.014), CAGR **15.92%** ✅ (15.9%), maxDD **−23.90%** ✅ (−23.9%), OOS Sharpe **1.1466** ✅ (1.147). Engine is faithful.

---

## Part 1 — Is it actually rearview-prone? (empirical characterization)

**Method.** At each of 197 monthly rebalances we read the raw inv-vol target weight vector (lookahead-safe: each weight uses sleeve returns *strictly before* that month-open). For each sleeve we measure its month-over-month weight change, isolate the **cuts** (drops beyond a threshold), and measure that sleeve's **standalone forward return** over the next 1/2/3 months vs its unconditional forward return. **Rearview pathology = forward return AFTER a cut is systematically HIGHER than unconditional** (you cut the sleeve right before it would have helped). Inv-vol keys off *volatility* not *return*, so the effect could be muted — we report it honestly either way.

**Finding — the pathology is real, ASYMMETRIC, and concentrated in the TQQQ sleeve.**

**TQQQ vol-target sleeve (the volatile leg) — rearview-prone at every threshold:**

| cut threshold | n cuts | fwd-1m mean | Δ vs uncond | fwd-2m Δ | fwd-3m mean | fwd-3m Δ |
|---|---|---|---|---|---|---|
| > 2% | 55 | +3.26% | **+1.37%** | +2.69% | +7.58% | +2.06% |
| > 5% | 28 | +3.11% | **+1.23%** | +1.80% | +6.46% | +0.95% |
| > 8% | 13 | +5.41% | **+3.52%** | +3.45% | +8.93% | +3.41% |
| > 10% | 11 | +4.15% | **+2.26%** | +3.71% | +10.40% | **+4.88%** |
| *(unconditional)* | 196 | +1.89% | — | — | +5.52% | — |

Every cell is positive: the deeper the cut, the more the sleeve out-performs its own average afterward. This is the textbook shape — **TQQQ's trailing vol spikes during/after a selloff, inverse-vol slashes its weight at the volatility-trough, and the sleeve then rebounds while the book is under-weight it.** Concrete episodes (single biggest monthly cuts → that sleeve's realized forward return):

- **2023-03-01**: w_tqqq 0.75 → 0.47 (−28%) → **+10.3% fwd-1m, +26.2% fwd-3m** (cut right at the SVB-scare trough, into the 2023 AI rip).
- **2025-08-01**: 0.48 → 0.37 (−11%) → +5.1% fwd-1m, **+23.8% fwd-3m**.
- **2020-07-01**: 0.55 → 0.36 (−19%) → +7.2% fwd-1m, **+13.3% fwd-3m** (post-COVID-crash vol still elevated → under-weight the recovery).
- **2018-07-02**: 0.38 → 0.26 (−12%) → +3.9% fwd-1m, **+13.2% fwd-3m**.
- *Counterexample (honesty):* **2010-05-03**: 0.42 → 0.31 (−11%) → −14.4% fwd-1m, −20.3% fwd-3m — the cut was *correct* there. So it is not universal, but the conditional *mean* is unambiguously rearview-positive.

**Rotation sleeve (the calm defensive leg) — NO pathology (mildly the opposite):**

| cut threshold | n cuts | fwd-1m Δ vs uncond | fwd-3m Δ |
|---|---|---|---|
| > 2% | 64 | −0.44% | −0.58% |
| > 5% | 26 | −0.47% | −0.85% |
| > 8% | 14 | −0.98% | −0.96% |
| > 10% | 7 | **−2.46%** | **−3.25%** |

Cutting the rotation sleeve is, if anything, mildly *correct* — its forward return after a cut is *below* its own average. **So the allocator is not abandoning the diversifier at the wrong time; it is abandoning the aggressive growth engine at its vol-trough.** This nuance matters: the AQR "Rearview Mirror" framing (cutting a *diversifier* on recent weakness) is the *milder* of the two risks here — the live scheme actually handles the diversifier fine. The real cost is missed TQQQ upside, which (a) inv-vol partially intends (downweighting the wild sleeve is the whole point) but (b) over-does in the single month a vol spike lands.

---

## Part 2 — Guardrail variants (same engine, same 4,117-day path, net of cost)

`rv_worst` = worst (most positive = most rearview-prone) of the two sleeves' (cond − uncond) mean 1-month forward return after a >5% cut, computed on that variant's **effective** (transformed) weight function. `maxCut` = largest single month-over-month weight drop the variant can produce.

| variant | full Sh | full DD | CAGR | OOS Sh | OOS DD | rv_worst | maxCut |
|---|---|---|---|---|---|---|---|
| **smooth_avg_3mo** ⭐ | **1.0179** | −23.48 | 16.15 | **1.1238** | **−20.93** | **+0.0017** | **0.142** |
| floor_0.15/0.20 + smooth_avg_3mo | 1.0179 | −23.48 | 16.15 | 1.1238 | −20.93 | +0.0017 | 0.142 |
| vol_lookback_126d | 1.0168 | −23.51 | 16.13 | 1.1046 | −19.73 | −0.0039 | 0.366 |
| smooth_avg_2mo | 1.0148 | −23.03 | 16.02 | 1.1169 | −21.69 | +0.0262 | 0.191 |
| smooth_ewma_α0.5 | 1.0097 | −23.44 | 15.95 | 1.1099 | −21.56 | +0.0233 | 0.132 |
| smooth_ewma_α0.3 | 1.0039 | −23.23 | 15.92 | 1.0911 | −22.14 | +0.0678 | 0.098 |
| floor_0.30 | 1.0008 | −23.86 | 15.84 | 1.1099 | −22.17 | +0.0189 | 0.252 |
| smooth_avg_6mo | 1.0001 | −23.41 | 15.89 | 1.0751 | −21.84 | −0.0256 | 0.088 |
| floor_0.25 | 1.0000 | −23.90 | 15.70 | 1.1123 | −21.96 | +0.0142 | 0.280 |
| **baseline_invvol_63d** | 0.9984 | −23.90 | 15.64 | 1.1132 | −21.88 | +0.0123 | 0.309 |
| floor_0.10 | 0.9984 | −23.90 | 15.64 | 1.1132 | −21.88 | +0.0123 | 0.309 |
| floor_0.15 | 0.9984 | −23.90 | 15.64 | 1.1132 | −21.88 | +0.0123 | 0.309 |
| floor_0.20 | 0.9982 | −23.90 | 15.64 | 1.1132 | −21.88 | +0.0123 | 0.302 |
| vol_lookback_189d | 0.9759 | −23.71 | 15.49 | 1.0388 | −23.71 | −0.0038 | 0.179 |
| floor_0.50 (degenerate 50/50) | 0.9698 | −25.00 | 17.15 | 1.0453 | −25.00 | n/a | 0.000 |

**Readings:**

1. **Floors alone are a NO-OP.** floor_0.10/0.15/0.20 are *identical* to baseline to 4 decimals — the inv-vol weights almost never dip below ~0.18, so a floor in that range never binds. floor_0.25/0.30 nudge Sharpe by +0.002 but leave maxCut at ~25–30% and the rearview Δ unchanged-or-worse. **A floor caps the weight *level*, not the cut *velocity*, so it does not touch the actual pathology.** floor_0.50 (forced 50/50) *hurts* Sharpe (0.970) and DD (−25.0%). → **floor = clean NO-OP.**

2. **Smoothing is the fix, and 3-month average is the sweet spot.** It attacks the *velocity* of the cut (halves maxCut 30.9%→14.3%), collapses the TQQQ rearview Δ (+1.23%→+0.17%), and — because it stops the allocator selling TQQQ low at the vol-trough — *improves* full Sharpe, OOS Sharpe, both maxDDs, AND CAGR, AND in-sample Sharpe (0.892→0.920). It also lowers turnover (0.093→0.066 → less inter-sleeve cost). 2-month under-smooths (rv_worst still +2.6%); 6-month over-smooths (OOS Sharpe drops to 1.075 — too sluggish, gives back the diversification timing). EWMA variants are dominated by the 3mo simple average. **3-month simple average is the pick.**

3. **`floor + smooth_avg_3mo` ≡ `smooth_avg_3mo` exactly** — once smoothed, the weight never reaches the floor, so the floor is redundant. **Adopt smoothing alone; do not add a floor.**

4. **A longer vol lookback (126d)** is a respectable *alternative* (Sharpe 1.017, best OOS DD −19.73%, kills the rearview Δ), but it leaves maxCut high (36.6% — it doesn't damp single-month velocity, it just uses a slower vol estimate) and its OOS Sharpe (1.105) is below smooth_avg_3mo's (1.124). Smoothing dominates on the metric the guardrail exists for. 189d over-smooths and degrades OOS.

---

## Lookahead / rigor

- **Baseline reproduces the promoted report exactly** at its as-of date (full 1.0144 / OOS 1.1466 / maxDD −23.90% @ 2026-06-18). The audit path is the live full cache; all variants share it.
- **Smoothing is lookahead-safe — explicitly verified.** The smoothed weight at month-open *m* is the average of the raw inv-vol weight vectors at month-opens ≤ *m*, each of which uses sleeve returns strictly before its own index. A truncation test (zero every sleeve return strictly after *m*, recompute) leaves the weight **bit-identical** at every month-open → no future information enters the weight. Floors and longer-lookback variants are trivially lookahead-safe (pointwise transforms / slower past-vol windows).
- **Same cost model** throughout: 2bps one-way on inter-sleeve monthly turnover via `blend_portfolio`; intra-sleeve costs already baked into each sleeve stream. Smoothing *reduces* turnover, so it is not buying its Sharpe with hidden extra trading.
- **Headline Sharpe = full continuous-span, sample stdev (ddof=1), √252** (fp_sharpe convention), applied identically to baseline and every variant. The engine's own `_stats_from_equity` uses population stdev; on ~4,100 points the two agree to the 4th decimal (baseline 0.9984 ddof=1 vs 0.9985 pop).
- **Not an overfit:** the winner improves IS (0.892→0.920) and OOS (1.113→1.124) *together*; it is not a parameter tuned to the OOS span. 3 months is also a coarse, hard-to-overfit setting (we tested 2/3/6 and two EWMA decays, not a fine grid).

---

## Honest caveats

1. **The realized Sharpe gain is small (~+0.02 full, +0.011 OOS).** The honest framing matches the BACKLOG expectation: this is **cheap insurance** (it halves the worst single-month weight yank and removes the rearview tilt) that happens to *also* pay a small risk-adjusted premium and a ~0.5pt CAGR/1pt OOS-DD improvement — rather than the usual guardrail that costs a little Sharpe for DD safety. Do not oversell the Sharpe bump; sell the **robustness** (no more selling TQQQ low at the vol-trough) and the *absence* of a cost.
2. **Same survivorship-bull-tilted 2010→ window** as the parent blend (TQQQ inception). The rearview episodes are all inside one secular bull with corrections; the guardrail has never seen a 2008-magnitude event either. Smoothing's logic (don't yank a sleeve on one month's vol spike) is regime-robust in principle, but the *magnitude* of the benefit is window-bounded.
3. **Drawdown-window / cut-conditional samples are small** (7–64 cuts per threshold). The *direction* (TQQQ rearview-positive, rotation rearview-negative) is consistent across all four thresholds and 1/2/3-month horizons, so it is a robust sign; the exact basis points are not precise.
4. **This is a weighting-layer change, not a sleeve change.** It does not touch the validated sleeves or the live tracker. Adopting it means: when the allocator weighting is next touched (the BACKLOG trigger), replace the raw month-open inv-vol weight with the trailing **3-month average** of the last three monthly inv-vol weight vectors before applying it. (Floor optional and inert — recommend omitting for simplicity.)

---

## Recommendation (crisp)

**ADOPT `smooth_avg_3mo`** — replace the live `invvol_63d` raw month-open weight with a **3-month simple average of the last three monthly inv-vol weight vectors** (renormalized to sum 1). **Do NOT add a min-weight floor** (it is a clean NO-OP here — the inv-vol weights never get low enough for it to bind, and it does not damp the single-month cut velocity that is the actual pathology).

- **vs baseline (same 4,117-day path):** full Sharpe **0.9984 → 1.0179**, OOS Sharpe **1.1132 → 1.1238**, full maxDD **−23.90% → −23.48%**, OOS maxDD **−21.88% → −20.93%**, CAGR **15.64% → 16.15%**, worst single-month weight cut **30.9% → 14.3%**, TQQQ rearview Δ **+1.23% → +0.17%**, turnover **0.093 → 0.066**.
- **Pure upside, lookahead-safe, lower turnover, not overfit (IS and OOS both improve).** Adopt at the next allocator-weighting touch per the BACKLOG trigger.

**FLOOR verdict: NO-OP — do not adopt.** **SMOOTHING verdict: ADOPT 3-month average.**

---

*Artifacts (all under `reports/`): `_antirearview_guardrail_driver.py`, `_antirearview_guardrail_result.json`, this file. Read-only on `runner/`, `strategies*/`, `*.db`; no orders/spend/config/cron changes.*
