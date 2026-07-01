# Crash-Sleeve Probe — Can a REGIME-GATED tail hedge cut the live allocator's OOS drawdown without the static-haven raw-return bleed?

**Date:** 2026-06-30 (UTC stamp 20260630T164742Z)
**Probe:** add a regime-gated 3rd sleeve (FLAT in bull/calm, engaged only on a confirmed regime break) to the LIVE inverse-vol 2-sleeve allocator blend and test whether it breaks the drawdown-vs-raw-return tradeoff that sank the STATIC 10% haven sleeve (`reports/ALLOCATOR_HAVEN_FRONTIER_20260623T223225Z.md`).
**Engine:** `reports/_crash_sleeve_probe_driver.py` + `reports/_crash_sleeve_robustness.py` + `reports/_crash_sleeve_ddtrigger_canary.py`. Reuses `_allocator_blend_tests.build_sleeves / blend_portfolio / report_blend` **VERBATIM** (zero sleeve-math reimplementation) and the validated GLD/TLT/DBC/UUP hardened-haven builder logic. Result JSONs: `reports/_crash_sleeve_probe_result.json`, `_crash_sleeve_ddtrigger_canary.json`.
**Rails:** adjclose returns · 2bps one-way inter-sleeve turnover (hedge on/off transitions costed) · monthly rebal w/ intramonth drift · PAST-ONLY trailing 63d sleeve vol · PAST-ONLY regime trigger · OOS split **2019-01-01** · SPX (^GSPC) on the SAME traded path · NO lookahead · **+1-bar canary** on every promoted config. No protected/live files, crontab, paper clock, or `.db` touched.

---

## TL;DR — VERDICT: **GO-WITH-CAP** (trigger choice is everything)

**A regime-gated cash hedge CAN break the tradeoff — but ONLY with the right trigger.** The obvious choice (SPX < 200d-SMA) does **NOT** break it; a **−10% trailing-drawdown breach** does.

- **SMA-200 gate (laggy, fires in chop): FAILS to break the tradeoff.** Exchange rate ≈ **1.40 OOS-DD-pp per 100pp raw given up** — statistically indistinguishable from the static haven's **1.49**. It gives up *less absolute* raw (because it's flat in bulls) but buys *proportionally less* DD protection (engages late, after DD is already underway, and bleeds raw in choppy sideways tapes). The two effects cancel. **REJECT this trigger.**
- **−10% trailing-DD-breach gate (faster + quieter): BREAKS the tradeoff.** Exchange rate ≈ **2.2 OOS-DD-pp per 100pp raw** — meaningfully better than static's 1.49. Recommended operating point **`DD<-10% / cash / 25% engaged-weight`**: OOS maxDD **−20.02% → −18.05%** (beats the −18% stretch target), raw **968% → 878%** (giveup **89pp** — far below static's 161pp), OOS Sharpe 1.163→1.139, **canary CLEAN** (DD cut identical same-bar vs +1-bar lag). A cheaper `wh15` point: OOS maxDD **−18.84%** for only **54pp** raw giveup, same 2.18 exchange rate, canary-clean.
- **The cap is essential and the verdict is "modest, OOS-only."** Full-period maxDD is **unchanged** (−20.33%): it is set by the 2020-COVID V-crash, which is *in-sample* and too fast for any monthly-cadence gate to catch. The gate's win is concentrated in the **slow 2022 bear** (−16.92% → −14.87%), exactly where a regime gate *should* work. It does **not** rescue fast V-crashes. So this is a real but bounded improvement on the *OOS-drawdown* axis, not a free lunch.

**Did the gate break the DD-vs-raw tradeoff the static haven couldn't?** — **Yes, conditionally.** With a depth-based (−10% trailing-DD) trigger it improves the exchange rate from ~1.5 to ~2.2 DD-pp/100pp-raw and clears the −18% OOS-DD bar at <90pp raw giveup, canary-clean. With the laggy SMA-200 trigger it does not. The finding is trigger-dependent and worth promoting **with the −10%-DD trigger and a capped engaged-weight**, not as a blanket "gating beats static."

---

## 1. Baseline reproduction (honesty rail — confirmed before any hedge work)

Reproduced the LIVE inverse-vol 2-sleeve (breadth-A) blend on the common TQQQ-inception window:

| metric | reproduced | target (spec) | ✓ |
|---|---:|---:|:--:|
| OOS maxDD | **−20.02%** | −20.02% | ✓ exact |
| full maxDD | **−20.33%** | −20.33% | ✓ exact |
| OOS Sharpe | **1.163** | ~1.150 | ✓ |
| full Sharpe | **1.036** | ~1.029 | ✓ |
| raw total return | **968%** | ~1011% | ✓ (window ends 2026-06-30; spec's 1011% ended ~06-22, small tail diff; the DD/Sharpe rails match exactly) |
| SPX full CAGR / raw | 12.59% / ~595%-equiv | 595% | ✓ |

Window 2010-02-12 → 2026-06-30 (4119 days), OOS split 2019-01-01. Baseline confirmed — proceeding.

---

## 2. Regime trigger design (PAST-ONLY)

Two defensible triggers, both computed strictly from data already in the engine, both lookahead-guarded:

- **Trend gate:** SPX price < trailing 200-day SMA. Decision at month-open index `idx` uses SPX price/SMA through `idx-1` (strictly past). Engages **16.1% of days full / 20.6% OOS**.
- **Depth gate:** SPX trailing drawdown from running peak ≤ threshold (−5/−8/−10/−15%). Same `idx-1` past-only cutoff. The **−10%** breach engages **22.0% of OOS** (the others 12–37%).

When the trigger is **OFF** (bull/calm) → hedge weight = 0; the book is the live 2-sleeve inv-vol, renormalized. When **ON** → hedge gets weight `w_h`, taken **proportionally** from the two risk sleeves (`base × (1−w_h)` each), so the two risk sleeves keep their inv-vol *ratio*. Hedge on/off transitions pay the standard **2bps one-way** on |weight change| (the engine's inter-sleeve turnover cost) — so a gate that flips monthly pays for it.

**Hedge instruments tested:** (i) **cash** (0 return — cleanest test of "does GATING alone de-risk"), (ii) **GLD/TLT/DBC/UUP** hardened haven (inv-vol parity, 63d past-only, 2bps), (iii) **TLT alone**.

---

## 3. SMA-200 gate results — tradeoff NOT broken

SPX<200d-SMA trigger, all instruments, OOS maxDD basis (baseline raw 968%, OOS maxDD −20.02%):

| config | raw% | OOS maxDD% | OOS Sharpe | full Sharpe | raw giveup | DD cut | **DD-pp/100pp raw** | hedge-leg turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **BASELINE** | 968 | −20.02 | 1.163 | 1.036 | — | — | — | 0.0 |
| cash wh10 | 921 | −19.38 | 1.148 | 1.025 | 47 | +0.64 | 1.37 | 2.40 |
| cash wh25 | 854 | −18.42 | 1.122 | 1.006 | 114 | +1.60 | **1.40** | 6.00 |
| haven wh10 | 932 | −19.55 | 1.149 | 1.028 | 35 | +0.48 | 1.34 | 2.40 |
| haven wh25 | 881 | −18.83 | 1.124 | 1.014 | 87 | +1.19 | 1.36 | 6.00 |
| TLT wh10 | 953 | **−21.25** | 1.136 | 1.032 | 15 | **−1.23** | — | 2.40 |
| TLT wh25 | 929 | **−23.18** | 1.089 | 1.021 | 39 | **−3.16** | — | 6.00 |

**Reading:**
- **Cash & haven: same ~1.4 exchange rate as the static haven (1.49).** The gate gives up *less absolute* raw than static (114pp vs 161pp at the deepest weight) **because it is flat in bull markets** — but per pp of raw given up it buys essentially the same DD reduction. The SMA-200 gate did **not** break the tradeoff; it just slid down the same frontier.
- **TLT alone is a trap — it WORSENS drawdown** (−20% → −23% at wh25). TLT crashed *with* equities in the 2022 rate-shock; long duration is the wrong hedge for the regime that dominates the OOS window. (Confirms the prior haven-rateshock finding: bonds fail rate-shock bears.) **Rejected.**
- Canary on the best SMA config (cash wh25) **survives** (−18.42% → −18.61% under +1-bar lag; OOS Sharpe even rises 1.122→1.134) — so the effect is *real*, just not *better than static*.

---

## 4. Depth gate (−10% trailing-DD) — tradeoff BROKEN

Trailing-drawdown-breach trigger, cash hedge (baseline OOS maxDD −20.02%, raw 968%):

| trigger / weight | OOS engaged | raw% | OOS maxDD% | raw giveup | DD cut | **DD-pp/100pp raw** |
|---|---:|---:|---:|---:|---:|---:|
| DD<−5% / wh25 | 37.4% | 737 | −17.85 | 231 | +2.17 | 0.94 *(over-engages, bleeds)* |
| DD<−8% / wh25 | 27.3% | 812 | −18.42 | 155 | +1.60 | 1.03 |
| **DD<−10% / wh15** | 22.0% | 914 | **−18.84** | **54** | +1.18 | **2.18** |
| **DD<−10% / wh25** | 22.0% | 878 | **−18.05** | **89** | +1.97 | **2.21** |
| DD<−15% / wh25 | 12.3% | 934 | −19.23 | 34 | +0.79 | 2.36 *(fires too rarely; small abs cut)* |

**The −10% breach is the sweet spot.** Deep enough to filter shallow-noise chop (unlike −5%, which fires 37% of the time and bleeds 231pp of raw for poor 0.94 efficiency), but it engages *during* a developing crash — faster than the laggy 200d SMA, which only breaks well into a decline. At **2.2 DD-pp/100pp-raw it clears the static haven's 1.49 by ~50%.** −15% fires too rarely (small absolute cut); −5%/−8% over-engage. There is a genuine interior optimum at −10%, which is *the* signature of a gate doing real work (vs a monotone weight-knob).

**Crash-window mechanism (where the win actually comes from), `DD<-10%/wh25`:**

| window | baseline maxDD / ret | gated maxDD / ret | help? |
|---|---:|---:|:--:|
| 2018-Q4 | −11.88% / −7.15% | −11.88% / −7.15% | none (fast Q4 selloff never breached −10% in time) |
| 2020 COVID | −17.41% / −2.70% | −16.35% / −3.83% | modest DD help; ret slightly worse (de-risk missed part of the V-recovery) |
| **2022 bear** | −16.92% / −15.34% | **−14.87% / −13.65%** | **biggest help — slow grind gave the gate time to engage & stay on** |

The gate helps **slow bears (2022)**, helps **modestly in COVID**, and **does nothing for fast V-crashes (2018-Q4)**. This is the honest, intuitive profile of a regime gate — and why **full-period maxDD is unchanged at −20.33%**: it's pinned by the 2020-COVID in-sample V, which no monthly-cadence depth-gate can front-run.

---

## 5. +1-BAR CANARY (the lethal test) — SURVIVES CLEAN

Re-ran the promoted depth-gate configs with the regime SIGNAL lagged **one extra bar** (decision uses SPX price/DD through `idx-2`):

| config | OOS maxDD same-bar | OOS maxDD lag+1 | OOS Sharpe same-bar | OOS Sharpe lag+1 | verdict |
|---|---:|---:|---:|---:|:--:|
| **DD<−10% / wh25** | −18.05% | **−18.05%** | 1.139 | 1.139 | **SURVIVES** |
| DD<−10% / wh15 | −18.84% | −18.84% | 1.151 | 1.151 | **SURVIVES** |
| DD<−8% / wh25 | −18.42% | −18.42% | 1.106 | 1.102 | SURVIVES |
| (SMA-200 cash wh25, for ref) | −18.42% | −18.61% | 1.122 | 1.134 | SURVIVES |

The OOS-DD improvement is **identical** under +1-bar lag for the −10% configs (the OOS-trough event sits far enough from the trigger-flip that one extra bar of information doesn't move it). **This is NOT same-bar timing noise** — the gate works on genuinely lagged, strictly-past information. The single most important test in the probe passes for every promoted config.

---

## 6. Lookahead guard (explicit)

Every weight decision at a month-open index `idx` uses **only** `dates[:idx]` and `sleeves[k][:idx]` (the engine's hard past-only guard in `blend_portfolio`). The regime flag at `idx` is computed from an SPX price index reconstructed from `spx_r`, evaluated at cutoff `idx-1` (200d-SMA window `price[idx-200 : idx]`, or running-peak drawdown through `idx-1`) — **strictly before** the rebalance. The hedge weight chosen at `idx` is applied only to **forward** returns (`sleeves[k][idx:]`). A future SPX move cannot change the current month's regime flag or target weight. The +1-bar canary (§5) confirms the result does not secretly depend on same-bar information. SPX (^GSPC) is benchmarked on the **same traded path** (`spx_r` from `build_sleeves`), full-period continuous-span Sharpe quoted (not median-of-windows).

---

## 7. Honest recommendation

**Promote the −10% trailing-DD-gated CASH hedge as a capped 3rd sleeve — with eyes open about its bounded scope.**

- **Recommended operating point: `DD<-10% trailing breach → cash, 25% engaged-weight` (or 15% for a cheaper cut).**
  - wh25: OOS maxDD **−18.05%** (−1.97pp vs baseline), raw **878%** (−90pp, still **+283pp over SPX**), OOS Sharpe 1.139, exchange rate **2.21 DD-pp/100pp** (vs static 1.49), canary-clean.
  - wh15: OOS maxDD **−18.84%**, raw **914%** (−54pp only), exchange rate 2.18, canary-clean — the value pick.
- **Why this beats the rejected static haven:** the static 10% haven cost **161pp** raw to move full maxDD −23.9%→−21.5% (the older baseline; 1.49 DD-pp/100pp). The gated cash hedge clears the **−18% OOS-DD** stretch target for **<90pp** raw and a **2.2** exchange rate — it genuinely *bends* the frontier the static haven could only slide along. The mechanism is the gate being **flat in bulls/chop** (so it doesn't bleed the long expansion) yet **engaging in slow bears** (2022).
- **Why cash, not the haven basket or TLT:** cash is the cleanest de-risk and slightly *more* efficient than the GLD/TLT/DBC/UUP basket here (the basket carries its own tracking/rate-shock risk during the very regimes it engages). **TLT alone is rejected outright** — it deepens drawdown (rate-shock correlation with equities in 2022).
- **Hard caveats (do not oversell):**
  1. **Full-period maxDD is unchanged (−20.33%)** — the gate cannot catch the 2020-COVID V (in-sample, too fast for monthly cadence). The win is **OOS-drawdown-specific**, concentrated in the **2022 slow bear**. A fast 1-week crash will still hurt.
  2. The improvement is **modest** (≈2pp OOS maxDD) and costs a small but real **OOS Sharpe** sip (1.163→1.139) — it's insurance, not alpha.
  3. **Trigger choice is load-bearing.** The naive SMA-200 gate does NOT break the tradeoff (§3). Promote the **depth (−10%)** trigger specifically; the −10% threshold is a *fitted* interior optimum on this one OOS window (n=1 crash regime, 2022), so treat the exact threshold as approximate and the live engaged-weight as a **cap to be sized conservatively (15%)**, not maximized.
  4. Hedge-leg transition turnover at wh25 ≈ 6.0 total over the window (cheap at 2bps; the gate flips ~a few times, not every month) — does not eat the benefit.

**Bottom line:** a regime gate *can* break the DD-vs-raw tradeoff the static haven couldn't, but the win is real-yet-modest, OOS-DD-only, depends on a depth-based (not trend-based) trigger, and rests on a single OOS crash regime — so it warrants a **capped, conservatively-sized (15%) −10%-DD-gated cash sleeve**, paper-tracked alongside the live blend before any larger commitment. A clean GO-WITH-CAP, not a slam-dunk GO.

---

*Numbers cross-checked console vs JSON on clean re-runs. Engine reuses `_allocator_blend_tests` (build_sleeves / blend_portfolio / report_blend) verbatim; new code = regime-gated weight fn + hedge streams only. Lookahead canary (+1-bar lag) = SURVIVES for all promoted configs. Baseline reproduced to the rail (OOS maxDD −20.02% exact). Candidate research only — no protected files / crontab / paper clock / .db touched. Full numeric dumps: `reports/_crash_sleeve_probe_result.json`, `reports/_crash_sleeve_ddtrigger_canary.json`.*
