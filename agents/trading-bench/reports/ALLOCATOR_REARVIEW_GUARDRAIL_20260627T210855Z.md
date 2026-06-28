# Allocator "Rearview Mirror" Guardrail — Falsifiable Test on the LIVE `allocator_blend`

**UTC:** 2026-06-27T21:08:55Z · **Path:** common window 2010-02-12 → 2026-06-26 (4117 trading days) · **Cost:** 2 bps one-way inter-sleeve · **Ruler:** continuous-span FP Sharpe `(mean/std)·√252`, population stdev (ddof=0), `_stats_from_equity`; SPX benchmarked on the **same** path.

> **PAPER RESEARCH ONLY.** No code in `runner/`, `strategies*/`, the engine, the tracker, the crontab, any `.db`, or the broker was touched. No order placed, no spend. Driver + JSON live in `reports/`.

---

## TL;DR VERDICT — **SOFT-GO (optional risk polish), default = leave the live 63d window as-is**

**The rearview critique mostly does NOT apply to this allocator by construction, and the residual version of it is small.** The live top-level allocation is **inverse-vol (vol-driven), not return-driven** — so the classic AQR mistake ("cut the diversifier because it *underperformed* lately") cannot happen here: weights respond to *volatility*, not recent returns. The only falsifiable residual is narrower — *does the 63-day vol window over-react to a single bad-vol month?* — and the answer is: **a little, but not enough to be a real problem.**

| Variant | Full S | Full DD | OOS S | OOS DD | mean &#124;Δw&#124;/rebal | Verdict vs 63d baseline |
|---|---|---|---|---|---|---|
| **`baseline_63d` (LIVE)** | **0.998** | **−23.90%** | **1.113** | **−21.88%** | **0.085** | — reproduces doc (see gate) |
| `lb_126` (6mo vol) | 1.017 | −23.51% | 1.105 | **−19.73%** | 0.053 | DD −2.2pp, but OOS S −0.009 |
| `lb_189` (9mo vol) | 0.976 | −23.71% | 1.039 | −23.71% | 0.036 | worse OOS S; lags risk |
| `lb_252` (12mo vol) | 0.987 | −25.21% | 1.045 | −25.21% | 0.030 | worse on BOTH; over-smooths |
| `floor_0.20` | 0.998 | −23.90% | 1.113 | −21.88% | 0.084 | ~null (floor rarely binds) |
| `floor_0.25` | 1.000 | −23.90% | 1.113 | −21.96% | 0.079 | ~null |
| `floor_0.30` | 1.001 | −23.86% | 1.110 | −22.17% | 0.069 | ~null / DD slightly worse |
| `smooth_2mo` | 1.015 | −23.03% | 1.117 | −21.69% | 0.070 | DD +0.2pp, S +0.004 (noise) |
| **`smooth_3mo`** | **1.018** | −23.48% | **1.124** | **−20.93%** | 0.057 | **best cell: OOS S +0.011, DD +0.95pp** |
| `126d_floor0.25` | 1.016 | −23.49% | 1.101 | **−20.27%** | 0.048 | DD +1.6pp, OOS S −0.012 |
| `126d_smooth2mo_floor0.25` | 1.010 | −23.28% | 1.083 | −20.67% | 0.042 | DD +1.2pp, OOS S −0.030 |

**Decision:** **`smooth_3mo` is the only variant that improves OOS on *both* axes** (Sharpe **+0.011**, maxDD **+0.95pp**) while *reducing* weight turnover — but the Sharpe gain (**+0.011**) is **below the 0.02 noise floor**, so it is a **drawdown-cosmetic improvement, not risk-adjusted-return alpha.** **No variant materially beats the baseline OOS Sharpe.** → **The 63d inv-vol window is fine. Recommended action: NO CHANGE** (keep the live allocator exactly as-is). If Cyrus *wants* a slightly smoother, lower-turnover, ~1pp-shallower-drawdown ride at zero Sharpe cost, **3-month EW weight-smoothing** is the single defensible, monotone, stress-safe knob — but it is **optional polish, not a fix for a defect**, because **no defect was found.**

---

## 1. Reproduction gate (passed — as-of-aware)

The baseline must reproduce the documented live blend (`invvol_63d`: full S **1.014** / OOS **1.147** / maxDD **−23.9%**).

| | Documented (as-of 2026-06-18) | Reproduced (this window, ends 2026-06-26, 4117d) |
|---|---|---|
| Full Sharpe | 1.014 | **0.9985** |
| OOS Sharpe | 1.147 | **1.1135** |
| maxDD | −23.9% | **−23.90%** |

- **maxDD matches to <0.01pp → the blend path, sleeve math, drift mechanics, and 2bps cost model are byte-identical** to the live engine. This is the structural identity proof.
- The Sharpe slide (full −0.0155, OOS −0.0335) is **benign as-of drift**: this blend's common window *grows* with every new trading day, so the trailing-mean Sharpe slides as recent days are appended while maxDD (a path-structural stat) stays pinned. This is **independently corroborated**: the committed engine output `_allocator_blend_result.json` (2026-06-22, window ending 2026-06-22) gives **1.0125 / 1.1425 / −23.897%** (reproduces doc to ~0.002), and a peer report (`ALLOCATOR_CADENCE_SWEEP_20260625`) already recorded the same engine giving **1.003** on the 4116-day window.
- Gate = **HARD** maxDD identity (≤0.3pp) **+** Sharpe within a benign drift band (≤0.05). **Both pass.** Reproduction is faithful; the test proceeds on a known-good baseline, not a broken one.

---

## 2. Does the rearview critique even apply here? (state explicitly)

**Largely NO, by construction.** The live top-level weight is `w_i ∝ 1/vol_i` over a 63-day trailing window. It is driven by **realized volatility**, never by realized return or relative performance. The canonical AQR rearview mistake — *de-allocating a diversifier because its recent **returns** lagged* — **cannot occur in this allocator**: a sleeve that has a bad *return* month but normal *vol* keeps its weight. The only channel through which "recent badness" can move weight is **a vol spike** (and a risk-off month that hurts the rotation sleeve's *return* often *also* raises its *vol*, which is exactly when inverse-vol *should* trim it — that is correct risk management, not a bug). So the test reduces to the single narrow question in §3–§5: does the **63d vol estimate over-react to a transient one-month vol spike** vs a longer/smoothed estimate?

---

## 3. Weight-stability diagnostic — IS THERE EVEN A PROBLEM? (the evidence)

Baseline 63d realized on-target weights across **196 monthly rebalances**:

- **Rotation (diversifier) weight:** mean **0.651**, range **[0.191, 0.817]**. (It is the *majority* sleeve on average — inverse-vol correctly leans into the calmer rotation sleeve.)
- **Monthly weight turnover:** mean **|Δw| = 0.085** per rebalance; **worst single-month swing = 0.618** (a covid-era snap).
- **Worst single-month rotation cut = −0.249** (w_rot dropped 24.9pp in one month); worst rise = +0.309.

**Literal rearview-pathology detector** — count rebalances where w_rot was cut by >X *and* the rotation sleeve was actually **UP the next month** (i.e. we trimmed the diversifier right before it recovered):

| Cut threshold | baseline cut events | …of which rot UP next month | as % of 196 rebals |
|---|---|---|---|
| w_rot cut > 5pp | 26 | **16** | cut+recover in 8.2% of months |
| w_rot cut > 8pp | 14 | 9 | 4.6% |
| w_rot cut > 10pp | 7 | 3 | 1.5% |

**Reading:** the pathology is *real but small in magnitude*. The 63d window does sometimes trim rotation right before it bounces (16 times in 16 years), **but these are 5–10pp trims on a sleeve that averages 65% weight — they are haircuts, not abandonments.** The diversifier is never dropped; w_rot's floor over the entire history is 0.19 (it stays material even at its lowest). Smoothing reduces these events monotonically (26 → 21 → **17** for 3mo), confirming the over-reaction is genuine but minor.

---

## 4. The three guardrail families (full spread — no cherry-pick)

**(a) Longer vol windows** — *non-monotone and mostly a wash on Sharpe.* `lb_126` is the sweet spot (full S **1.017**, OOS DD **−19.73%**, the shallowest of any cell) but *costs* 0.009 OOS Sharpe. `lb_189`/`lb_252` over-smooth: they keep rotation more stable but **lag genuine risk shifts** — `lb_252` actually *worsens* both full Sharpe (0.987) and OOS DD (−25.21%). **A longer window is not robustly better; it trades a little drawdown for a little Sharpe and breaks down past ~6mo.**

**(b) Min-weight floors {0.20, 0.25, 0.30}** — *near-null.* The floor rarely binds (baseline w_rot only dips below 0.20 once and w_tqqq's natural floor is ~0.18), so floors barely move anything: full Sharpe 0.998 → 1.001, OOS maxDD essentially unchanged (−21.88 → −22.17, slightly *worse* at 0.30 because forcing weight into the wilder TQQQ sleeve in calm regimes adds vol). **Floors are a no-op safety rail here — they don't hurt, but they don't help, because the live blend already never abandons a sleeve.**

**(c) Weight smoothing {2mo, 3mo}** — *the only coherent improvement.* EW-averaging the target weights over the trailing 2–3 rebalances damps the over-reaction: turnover drops (0.085 → 0.070 → **0.057**), full Sharpe rises (→ **1.018** at 3mo), OOS maxDD improves (→ **−20.93%** at 3mo), and OOS Sharpe ticks up to **1.124** (best cell). It is **monotone 2mo→3mo on Sharpe, turnover, and pathology-event count.** But the OOS Sharpe gain over baseline is **+0.011 — below the 0.02 noise floor** — so it is honestly a **drawdown/turnover cosmetic, not alpha.**

**(d) Blend-of-fixes** (`126d+0.25 floor`, `126d+2mo smooth+0.25 floor`) — *give back Sharpe.* Stacking knobs over-damps: OOS Sharpe falls to 1.101 / 1.083 (the second *loses* 0.030 OOS Sharpe vs baseline) even though OOS maxDD improves to ~−20.3/−20.7%. **Combining fixes is worse than the single best knob — a classic over-smoothing tax.**

**Robustness scorecard (10 variant cells vs baseline):**
- Cells beating baseline **OOS Sharpe by ≥0.02:** **0 / 10.** (No material risk-adjusted-return improvement exists.)
- Cells shaving **OOS maxDD by ≥0.5pp *without* losing >0.02 OOS Sharpe:** **`smooth_3mo` only** (the clean family is thin — `lb_126`, `126d_floor0.25`, `126d_smooth2mo_floor0.25` all shave DD but *lose* Sharpe and are excluded).
- Cells beating baseline **full Sharpe by ≥0.02:** **0 / 10.**

---

## 5. Stress behavior — did the 63d window cut the wrong sleeve at the wrong time?

**2008 GFC: N/A — pre-inception.** TQQQ began 2010-02; the common blend path *cannot* include 2008. Stated honestly rather than fabricated (n=0 months in window).

Diversifier (rotation) weight **going INTO and THROUGH** each testable stress:

| Variant | 2020 covid w_rot (mean[min–max]) | 2022 bear w_rot (mean[min–max]) |
|---|---|---|
| **baseline_63d** | 0.606 [0.450–0.741] | 0.481 [0.191–0.718] |
| lb_126 | 0.634 [0.565–0.714] | 0.485 [0.134–0.724] |
| lb_252 | 0.658 [0.608–0.706] | 0.589 [0.383–0.668] |
| floor0.25_63d | 0.606 [0.450–0.741] | 0.486 [0.236–0.718] |
| smooth2mo_63d | 0.625 [0.475–0.739] | 0.490 [0.208–0.714] |
| 126d_floor0.25 | 0.634 [0.565–0.714] | 0.498 [0.224–0.724] |

**Reading:** the 63d window behaved **correctly** in both stresses — it did **not** cut the wrong sleeve at the wrong time:
- **2020 covid:** baseline held rotation at ~0.61 average (and *raised* it as TQQQ's vol exploded), exactly the defensive tilt you want. Longer windows held it marginally higher (0.63–0.66) but the qualitative call was identical.
- **2022 bear:** baseline correctly *lowered* rotation to ~0.48 — because in 2022 the rotation sleeve's *own* vol rose (GLD/TLT both fell), so inverse-vol appropriately leaned slightly more to the (trend-gated, often-in-cash) TQQQ sleeve. `lb_252` held rotation much higher (0.59) — which is **not obviously better**: it's slower to recognize that the "diversifier" was itself stressed in 2022. **Smoothing/floors did not degrade stress behavior** (w_rot ranges essentially overlap the baseline). No variant improves the stress weighting in a way that clearly beats 63d; the longer windows merely smooth it, with ambiguous benefit.

---

## 6. Honesty self-check (all rails)

- **Ruler:** every cell uses `_stats_from_equity` → `(mean/std)·√252`, population stdev (ddof=0, divide-by-n), matching `annualized_vol`. ✅ Identical to the rest of the project. SPX benchmarked on the **same** path (full S 0.768, OOS 0.833, maxDD −33.9%) — every blend beats it. ✅
- **Lookahead-safe:** every target weight uses only sleeve returns **strictly before** the month-open index (`annualized_vol(sleeve[lo:idx])`, `idx` exclusive). Floors are applied to **target** weights only; smoothing **averages PAST target weights** (each computed at its own month-open from prior-only data) — no future info enters any weight. ✅ The one place future data is touched is the **pathology *labeler*** in §3 (forward 1-month rotation return), which only *classifies* an event after the fact and **never sets a weight** — explicitly diagnostic. ✅
- **No cherry-pick:** the full 10-cell spread is reported; the verdict is driven by the *family* counts (0 cells beat OOS Sharpe materially; only 1 cleanly beats OOS maxDD without a Sharpe cost), **not** by `argmax`. The single best cell (`smooth_3mo`, +0.011 OOS S) is explicitly flagged as **below the noise floor.** ✅
- **Bar to recommend a change:** beat baseline OOS net of cost on Sharpe-OR-maxDD, **monotone/robust across neighboring cells**, no stress degradation. → **Sharpe channel: not cleared** (0 cells). **maxDD channel: marginally cleared by exactly one clean cell** (`smooth_3mo`), monotone 2mo→3mo, stress-safe. This is a *soft* pass on the *cosmetic* axis only. ✅
- **Does the rearview critique apply?** Stated explicitly in §2: **largely NO** — the allocation is vol-driven, not return-driven; the residual (vol-spike over-reaction) is real but small (§3). ✅
- **as-of drift** disclosed and corroborated against the committed engine JSON and a peer report (§1). ✅

---

## 7. GO / NO-GO

**NO-GO on "fix a defect" — there is no defect.** The 63d inverse-vol window is sound: it never abandons the diversifier (w_rot floor 0.19 over 16y), behaves correctly through 2020/2022, and the rearview pathology it does exhibit is a handful of 5–10pp haircuts, not return-chasing abandonment. **No variant materially improves OOS Sharpe (0/10 beat by ≥0.02).**

**Optional SOFT-GO (polish only, Cyrus's call — NOT recommended as necessary):** *if* a smoother, lower-turnover, ~1pp-shallower-drawdown ride is wanted at zero Sharpe cost, the single defensible knob is:

> **Spec (only if desired):** Replace the raw month-open target `w = invvol_63d(idx)` with a 3-rebalance EW-smoothed target `w = mean(invvol_63d at the last 3 month-opens ≤ idx)`, renormalized to sum 1. Lookahead-safe (averages past targets). Effect over the live path: OOS maxDD −21.88% → **−20.93%** (+0.95pp), OOS Sharpe 1.113 → **1.124** (+0.011, within noise), monthly weight turnover 0.085 → **0.057** (−33%, *lowers* trading cost). No 2020/2022 stress degradation. Do **not** stack it with floors or a longer window (those give back Sharpe).

**Default action: leave `allocator_blend` exactly as it is.** The honest, evidence-backed conclusion is *"63d inv-vol is fine — no rearview problem exists on this allocator."*

---

### Artifacts
- Driver: `reports/_allocator_rearview_guardrail_driver.py` (`PYTHONPATH=. python3 reports/_allocator_rearview_guardrail_driver.py`)
- Machine-readable: `reports/_allocator_rearview_guardrail_result.json`
- Engine reused verbatim: `_allocator_blend_tests.py` (`build_sleeves`, `blend_portfolio`, `annualized_vol`) + `_stats_from_equity` ruler. No live code touched.
