# Leveraged-Long Vol-Target — SURVIVORSHIP CROSS-CHECK (UPRO / SPXL / SOXL)

**Date:** 2026-06-08
**Author:** Tessera (trading-bench)
**Builds on:** `reports/LEVERAGED_LONG_VOLTARGET_20260608.md` (the TQQQ vol-target result)
**Candidate family:** `strategies_candidates/leveraged_long_trend/` (quarantine — NOT promoted, NOT a tournament parent)
**Purpose:** test whether the vol-target result is a structural property of the sizing mechanism or a **TQQQ-survivorship artifact**, by re-running the EXACT same engine on other 3x sleeves.

---

## TL;DR — verdict **B (PARTIAL)**, and it corrects my own prior report

Re-running the identical vol-target engine on three other 3x sleeves (UPRO = 3x S&P / ProShares, SPXL = 3x S&P / Direxion, SOXL = 3x semis) splits the TQQQ result cleanly into a part that **survives** and a part that **does not**:

- ✅ **The raw-return SPX beat is STRUCTURAL.** All 3 sleeves, every sweep cell, beat SPX on raw return. This is not TQQQ-specific.
- ✅ **Drawdown compression holds on broad large-cap** (UPRO & SPXL bring maxDD ≤ SPX at targets 0.20/0.25) — **but NOT on semis** (SOXL stays above SPX's drawdown even at target 0.20).
- ❌ **The risk-adjusted (Sharpe) edge was largely TQQQ-SPECIFIC.** On TQQQ, vol-target beat SPX Sharpe (0.859 vs 0.773). On UPRO it's **below** SPX (0.746 vs 0.802); on SOXL **below** (0.723 vs 0.752). Only SPXL clears SPX Sharpe — and only because SPXL's window starts in 2008-11, so the GFC crash drags SPX's *own* reference Sharpe down to 0.719 (an artifact of the longer window, not a better strategy).
- ⚠️ **OOS is target-dependent.** At **target 0.25**, all three sleeves pass the post-2018 OOS raw beat. At **target 0.20**, the broad-cap pair (UPRO & SPXL) **FAIL** OOS (post-2018 strat < SPX); SOXL passes only because its post-2018 semis run was enormous. The TQQQ report's "clean OOS at both targets" does **not** generalize — only 0.25 is robust across sleeves.

**Net correction to the prior report:** the **raw-return beat is the real, structural finding** (and it's a big one — 1.5×–3.5× SPX raw across every sleeve). The **"modest risk-adjusted edge" claim was over-stated** — it held on TQQQ but is the part most attributable to the specific winner. The honest headline going forward: *vol-targeted leveraged-trend reliably beats SPX on raw return across multiple 3x sleeves with broad-cap drawdown at/under SPX; it does NOT reliably beat SPX risk-adjusted once you leave the TQQQ winner.*

---

## Method (apples-to-apples with the TQQQ result)

- **Same engine, params only changed.** `backtest_daily_voltarget.run_backtest_voltarget(VolTargetParams(sleeve=…, underlying=…))`. The engine, cost model (abs-weight-change 2 bps), trend gate (200d SMA), vol window (20d), w_max (1.0), and lookahead-safe sizing are **identical** to the TQQQ run — only `sleeve`/`underlying` differ. No new code paths, no new lookahead introduced.
- **Sleeves:** UPRO/SPY (3x S&P, 2009-06→), SPXL/SPY (3x S&P alt issuer, 2008-11→ — reaches into the GFC), SOXL/SOXX (3x semis, 2010-03→ — a different, far more volatile sector).
- **Sweep:** target_ann_vol ∈ {binary(None), 0.20, 0.25, 0.30, 0.40}; benchmark `^GSPC` on the **same traded dates** the engine returns (no re-windowing).
- **Frozen-OOS:** split @ 2018-01-01, IS vs OOS raw beat, exactly as `validate_oos_voltarget.py`.
- **Independently reproduced:** the UPRO target-0.25 headline was re-run directly from the engine by the parent and matched the worker's JSON **to the digit** (tot +1241.5%, maxDD −31.27%, Sharpe 0.746, avgW 0.628, rebal 2865). Results are real, not fabricated.

---

## Results — headline configs (full window, same-date SPX ref)

| Sleeve | Window | Config | Total Ret | vs SPX | Max DD | vs SPX DD | Sharpe | vs SPX Sh | Raw? | Sharpe? | DD≤SPX? |
|---|---|---|---:|---:|---:|---:|---:|---:|:--:|:--:|:--:|
| **UPRO** | 2009-26 | binary | +4,113% | +705% | −51.4% | −33.9% | 0.797 | 0.802 | ✅ | ❌ | ❌ |
| UPRO | | t0.20 | +777% | +705% | −26.8% | −33.9% | 0.724 | 0.802 | ✅ | ❌ | ✅ |
| UPRO | | **t0.25** | +1,242% | +705% | −31.3% | −33.9% | 0.746 | 0.802 | ✅ | **❌** | ✅ |
| **SPXL** | 2008-26 | binary | +4,134% | +677% | −51.7% | −33.9% | 0.780 | 0.719 | ✅ | ✅ | ❌ |
| SPXL | | t0.20 | +821% | +677% | −26.9% | −33.9% | 0.723 | 0.719 | ✅ | ✅ | ✅ |
| SPXL | | **t0.25** | +1,338% | +677% | −31.4% | −33.9% | 0.746 | 0.719 | ✅ | ✅* | ✅ |
| **SOXL** | 2010-26 | binary | +4,643% | +544% | −84.2% | −33.9% | 0.695 | 0.752 | ✅ | ❌ | ❌ |
| SOXL | | t0.20 | +625% | +544% | −34.8% | −33.9% | 0.723 | 0.752 | ✅ | ❌ | ❌ |
| SOXL | | **t0.25** | +976% | +544% | −41.8% | −33.9% | 0.723 | 0.752 | ✅ | ❌ | ❌ |
| *TQQQ (ref)* | 2010-26 | *t0.25* | *+2,026%* | *+587%* | *−34.5%* | *−33.9%* | *0.859* | *0.773* | *✅* | *✅* | *✅* |

\* SPXL "beats SPX Sharpe" only because its 2008-start window lowers the SPX reference Sharpe to 0.719 (vs ~0.80 on the 2009/2010-start windows). On a like-for-like window SPXL's Sharpe (0.746) would also sit below SPX. So treat SPXL's Sharpe "pass" as a windowing artifact, not a real risk-adjusted win.

**Reading it:** every sleeve, every config beats SPX raw (the structural part). Broad-cap (UPRO/SPXL) compresses DD to ≤ SPX at 0.20/0.25; semis (SOXL) does not (semis are too volatile — even sized to 20% target the residual tail is worse than SPX). And the Sharpe column is the story: **0.746 / 0.746 / 0.723 — all at or below SPX's ~0.80** once you're off TQQQ. TQQQ's 0.859 was the outlier.

---

## Frozen-OOS (split @ 2018-01-01) — the real fragility

| Sleeve | Config | IS strat vs SPX | OOS strat vs SPX | OOS beats SPX raw? |
|---|---|---|---|:--:|
| UPRO | t0.20 | +272% vs +191% ✅ | +131% vs +175% | **❌ FAIL** |
| UPRO | t0.25 | +360% vs +191% ✅ | +186% vs +175% | ✅ (narrow) |
| SPXL | t0.20 | +289% vs +181% ✅ | +132% vs +175% | **❌ FAIL** |
| SPXL | t0.25 | +391% vs +181% ✅ | +187% vs +175% | ✅ (narrow) |
| SOXL | t0.20 | +117% vs +132% ❌ | +223% vs +175% | ✅ |
| SOXL | t0.25 | +151% vs +132% ✅ | +311% vs +175% | ✅ |

**The TQQQ report claimed clean OOS at both 0.20 and 0.25. Off-TQQQ that is FALSE for 0.20:** the broad-cap pair *fails* the OOS raw beat at target 0.20 (post-2018, sized that conservatively, they trail SPX). Only **target 0.25 survives OOS on broad-cap, and only narrowly** (+186 vs +175, +187 vs +175). SOXL passes OOS at both targets but that's its idiosyncratic post-2018 semis boom (NVDA/AI cycle), not robustness — and SOXL *fails IS* at 0.20, the mirror-image instability. The lesson: the conservative-target version is **not** uniformly OOS-robust; the edge thins out exactly where you'd size down for safety.

---

## Honest verdict & what changed

**Verdict: B (PARTIAL).** The cross-check did its job — it separated signal from artifact:

- **SURVIVES (structural):** the **raw-return SPX beat.** Trend-gated, vol-targeted 3x exposure beats SPX raw on every sleeve tested (broad-cap and semis), in-sample. This is the real finding and it generalizes. It is — honestly — a **leverage premium harvested with a drawdown-control overlay**, not alpha, but it's a robust, reproducible leverage premium.
- **SURVIVES on broad-cap only:** **drawdown ≤ SPX.** UPRO/SPXL at 0.20-0.25 bring the −51% binary drawdown down to −27/−31% (≤ SPX). Semis can't get there.
- **DOES NOT survive:** the **risk-adjusted (Sharpe) edge.** It was 0.86 on TQQQ but 0.72-0.75 (≤ SPX) on UPRO/SOXL. The "beats SPX on Sharpe too" claim in the TQQQ report was **largely TQQQ-specific** and should not be treated as a general property.
- **DOES NOT survive uniformly:** **OOS robustness at the conservative target.** 0.20 fails OOS on broad-cap; only 0.25 holds, and narrowly.

**Survivorship status: REDUCED, not eliminated.** UPRO/SPXL/SOXL are *also* survivors (3x leveraged ETFs that happened to track indices which rose). But they're a much broader, less-Nasdaq-specific set, and the raw-beat holding across all of them is real evidence the mechanism isn't a single-winner fluke. What it is NOT is evidence of risk-adjusted alpha.

**Remaining caveats (unchanged):** no full 2008 bear for TQQQ/SOXL (SPXL has partial); high turnover (~2,900-3,300 rebalances) → real execution drag will exceed the modeled 2 bps and eat into these (already-thinner) margins; close-to-close modeling only.

---

## Disposition & next steps

- **Stays quarantine.** Nothing promoted; protected `runner/` md5s verified **unchanged**; full suite **391/391**.
- **The prior TQQQ report (`LEVERAGED_LONG_VOLTARGET_20260608.md`) is amended** with a correction banner pointing here: the raw-return beat stands; the risk-adjusted-edge and clean-OOS claims are downgraded to "TQQQ-specific / not robust off-TQQQ."
- **Recommended next steps (re-prioritized by this result):**
  1. **Reframe the candidate honestly as a raw-return leverage-harvest, not a risk-adjusted-edge play.** That's what the data supports. The promotion conversation with main/Cyrus should be on those terms.
  2. **Realistic execution-drag model is now the priority gate** — the margins off-TQQQ are thin enough (OOS +186 vs +175) that turnover costs could erase them. Build the wider-cost/slippage/tracking-error model and re-check whether the broad-cap OOS beat survives it. **If it doesn't survive realistic costs, the whole family is a wash.**
  3. **Rolling walk-forward** (not single frozen split) on UPRO to see if 0.25's narrow OOS edge is stable through time or just a 2018-cut artifact.
  4. Synthetic pre-2010 3x extension for the 2008 bear (SPXL gives a partial real read already — its binary −51.7% over a window incl. 2008 is the closest we have).

## Artifacts
- Runner: `strategies_candidates/leveraged_long_trend/survivorship_crosscheck.py`
- Results: `strategies_candidates/leveraged_long_trend/survivorship_crosscheck_result.json` (per-sleeve full sweep + frozen-OOS; reproduced to the digit by parent)
- Prior report amended: `reports/LEVERAGED_LONG_VOLTARGET_20260608.md`
- Protected `runner/` md5s verified **unchanged**; full suite **391/391**.
