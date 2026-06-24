# H1 Cross-Asset Carry — Commodity Leg via TRUE WTI Futures Calendar-Spread

*UTC stamp `20260623T221400Z` · engine `_h1_carry_commodity_futures_tests.py` (exit 0) · machine-readable `reports/_h1_carry_commodity_futures_result.json`*

**Reopen of** `reports/H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md` (the ETF-proxy commodity carry that CLOSED 2026-06-23 as a dirty-proxy / single-regime mirage). That report's *Revisit-triggers* named exactly this path: *a non-ETF curve-shape instrument — a true front-vs-deferred WTI futures calendar-spread — to isolate the roll-yield premium without expense drag / tracking error / fund mechanics; it MUST show a positive in-sample Sharpe AND beat a dumb static-long-WTI control net OOS.* This is that test, run honestly.

---

## 0. TL;DR verdict

**k1 FAIL / k2 FAIL / k3 PASS / k4 PASS / k5 FAIL → **OVERALL CLOSE.**

- **Combined bond+commodity sleeve FULL Sharpe = 0.4643** (span-matched bond-alone = **0.5596**; unrestricted bond-alone 0.578). Adding the commodity leg **lowers** the honest full-period Sharpe — k5 fails.
- **Disposition: CLOSE the commodity leg; NO-GO on the combined H1 carry sleeve.** But this is a materially *more honest* near-miss than the ETF version: the clean futures instrument **fixed the regime artifact** (IS Sharpe is now **positive** — k4 PASS, where the ETF proxy was negative on every split). It still dies on the make-or-break control (k2): the curve-timing signal cannot beat dumb static-long-WTI net OOS at any threshold, because going-to-cash in contango gives up more upside than the contango blowups it dodges. It is a **defensive overlay, not alpha** — the same structural outcome as the ETF version, but now for an honest reason (gives up upside) rather than a dirty one (expense/regime artifact).

---

## 1. Data provenance — the clean curve, no ETF confound

- **Futures term structure:** EIA bulk `PET.RCLC1.D … PET.RCLC4.D` — NYMEX WTI (Cushing) contracts 1–4 daily settlement, **keyless**, grepped out of `data_cache/eia_PET_bulk.txt` (365 MB) into `data_cache/eia_wti/rclc{1,2,3,4}.jsonl` (only the 4 matching lines — no 365 MB load).
- **Span:** CL1 `1983-04-04` → `2024-04-05`; common 4-contract calendar `1985-01-02` → `2024-04-05` (**9,875 days**, 472 month-end rebalances). These are **real front-through-4th-month settle prices** — a clean term structure with **zero** ETF expense / tracking confound. This is the deep history (back to 1985 for the spread) the ETF proxy could not reach.
- **Data staleness caveat (load-bearing):** the EIA bulk dump is `2024-04-10 (bulk dump); CL data ends 2024-04-05`, so the futures calendar **ends 2024-04-05**. The OOS window is therefore 2019-01 → 2024-04 (~5.3y, 1,340 days) and the combined sleeve is bounded at 2024-04-05. **All k5 comparisons below are span-matched** to remove this as a confound.
- **Execution vehicles:** (A, primary) **roll-adjusted continuous front-month WTI futures return**; (B) **USO adjclose** (carries the real-world roll cost an actual trader pays). **The SIGNAL is always clean-futures-derived** even when execution uses USO — that is legitimate and the explicit difference from the dead version, where the *signal itself* was ETF-derived.
- **Cash anchor:** SHY adjclose (the long-or-cash sleeve sits in SHY when contango).
- **Negative-print handling:** 2020-04-20 CL1=-37.63 treated as roll seam (deferred CL2 return used); never taken as a held front return. Only **2 seam-fallback days** in the entire 9,874-day series, both in the April-2020 negative-oil week; the catastrophic −$37.63 front print is correctly **not** taken as a held return (a disciplined front-month roll is already in the June/CL2 contract by 2020-04-20).

## 2. Signal definition + roll convention

- **Primary signal `roll12` = log(CL1/CL2)** — front-vs-second per-step roll yield. Backwardation (>0) ⇒ positive carry ⇒ long; contango (<0) ⇒ flat/cash. The genuine curve-shape premium the ETF proxy could not isolate.
- **Robustness signal `roll14` = log(CL1/CL4)/3** — multi-point slope, per-contract-step.
- **Roll convention (documented):** hold CL1; within-contract CL1 settle-to-settle return; on roll/negative seam (|daily|>40% or non-positive price) splice on deferred CL2 daily return -- textbook continuous front-month.
- **Position variants:** `long_only_timing` (long vehicle when backwardated, else SHY cash) — the primary; and `continuous` (weight = clip(signal/scale, −1, +1), can short deep contango — the genuinely market-neutral expression).
- **Hygiene:** prior-day signal (data ≤ month-end), positions effective **T+1** (1-day lag), held constant, marked on next-day returns. Sharpe = (mean/std)·√252, ddof=1, **continuous concatenated series** (never median-of-windows) — mirrors `runner/fp_sharpe.py` and the bond leg exactly.
## 3. The 5-gate table (each PASS/FAIL with the number)

| Gate | Test | Value | Bar | Result |
|---|---|---|---|---|
| **k1** | commodity-futures-carry OOS Sharpe ≳ 0.4 | **0.3715** | ≥ 0.40 | ❌ FAIL |
| **k2** | BEATS static-long-WTI net OOS (make-or-break) | ΔSh **-0.0815**, Δtot **-20.0%** | > 0 | ❌ FAIL |
| **k3** | corr to bond leg ≲ 0.3 | **-0.0115** (monthly), 0.0026 (daily) | ≤ 0.30 | ✅ PASS |
| **k4** | POSITIVE in-sample Sharpe (not a single-regime artifact) | **0.1679** | > 0 | ✅ PASS |
| **k5** | combined FULL Sharpe > bond-alone | **0.4643** vs **0.5596** (span-matched) | > bond | ❌ FAIL |

**PASS requires k1+k2+k3+k4 all hold AND k5 combined full > bond-alone. Result: k1=F k2=F k3=P k4=P k5=F → OVERALL CLOSE.**

### The two decisive failures, stated plainly
- **k2 (make-or-break) FAILS by −20.0pp OOS total return.** The signal earns OOS Sharpe 0.3715 / total +41.5%; dumb **static-long-WTI** earns Sharpe 0.453 / total +61.5%. The curve-timing-to-cash **gives up more upside than the contango blowups it dodges** — exactly the defensive-overlay signature the ETF version showed, but here it is honest (no expense/regime artifact propping the Sharpe).
- **k5 FAILS span-matched.** Combined sleeve full Sharpe 0.4643 < span-matched bond-alone 0.5596. The commodity leg's low standalone full Sharpe (0.1988) drags the equal-risk blend **down** on the full period, even though it lifts the OOS window (0.8179). Trading the bond leg alone is strictly better.

### The genuinely NEW result (why this is a cleaner close than the ETF version)
- **k4 PASSES — IS Sharpe is POSITIVE (+0.1679).** This is the headline difference. The ETF-proxy version had **negative IS Sharpe on every split** (−0.30 to −0.64) — a pure post-2018 regime artifact. The clean futures instrument **removes that artifact**: the curve-carry premium is weakly positive *pre-2019 too* (see §4). The premium is **real but small** — too small to beat static-long or to lift the combined sleeve.
- **k3 PASSES emphatically — corr to bond leg -0.0115 monthly / 0.0026 daily.** Genuinely orthogonal (even cleaner than the ETF version's −0.28). And unlike the ETF proxy (corr→SPX +0.45 = long beta), this clean leg's corr→SPX is **+0.0534** — barely any equity beta. The orthogonality is real; there just isn't enough standalone edge to monetize it.

## 4. IS/OOS split-robustness — the artifact detector (the ETF version's killer)

Primary commodity leg (roll-adjusted front-month, roll12, long-only), four OOS split conventions:

| OOS split | **IS Sharpe** | IS total | OOS Sharpe | OOS total |
|---|---|---|---|---|
| 2014-12-31 | **0.179** | +42.0% | 0.2728 | +40.0% |
| 2016-12-31 | **0.1749** | +43.8% | 0.3008 | +38.3% |
| 2018-12-31 | **0.1679** | +40.6% | 0.3715 | +41.5% |
| 2020-12-31 | **0.1596** | +35.5% | 0.5146 | +46.8% |

**This is the decisive contrast with the ETF version.** There, IS Sharpe was **negative on every split** and OOS rose mechanically as the split moved later — the textbook regime-artifact signature. **Here, IS Sharpe is POSITIVE and stable on all four splits (+0.16 to +0.18)**, and IS total return is positive every split. The clean futures curve genuinely carries a small backwardation premium pre-2019. The OOS Sharpe is *higher* than IS (0.27–0.51 vs ~0.17) — a mild regime tailwind from post-2018 backwardation — but it is **not** the all-or-nothing artifact the ETF proxy was. The signal is real; it is just **weak** (IS ~0.17, full 0.20).

### Year-by-year commodity-leg total return (primary)

| 1985 | 1986 | 1987 | 1988 | 1989 | 1990 | 1991 | 1992 | 1993 | 1994 | 1995 | 1996 | 1997 | 1998 | 1999 | 2000 | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -1.7% | -27.6% | -9.9% | +38.9% | +26.6% | -2.9% | -26.6% | -4.0% | +0.0% | -3.3% | +10.1% | +32.6% | -22.1% | +0.0% | +22.0% | +4.7% | +6.9% | +9.0% | +4.2% | +24.2% | -7.2% | +3.9% | +29.0% | -10.6% | +0.4% | +2.3% | +10.2% | +0.2% | -3.5% | -28.5% | +0.4% | +0.8% | +0.3% | -2.5% | +14.6% | -15.9% | +33.9% | +7.9% | -14.0% | +18.3% |

**Positive in 23 of 40 years.** Unlike the ETF version (lost money in 8 of 11 IS years), the clean leg is positive across both IS and OOS eras — consistent with k4. But the magnitude is small and the worst years (2008, 2014–15, 2020) still bite.

## 5. Secondary variants (robustness — same harness)

| Variant | FULL Sharpe | IS Sharpe | OOS Sharpe | Read |
|---|---|---|---|---|
| **Primary** roll12, front-roll | 0.1988 | 0.1679 | 0.3715 | weak-but-positive IS; fails k1/k2 |
| V2 roll14 (CL1 vs CL4), front-roll | 0.2061 | 0.1955 | 0.2642 | similar weak-positive; multi-point slope no better |
| V3 **continuous** (can short contango) | -0.3013 | -0.2627 | -0.484 | **NEGATIVE everywhere** — shorting contango loses; the market-neutral expression is worse, not better |
| V4 primary signal, **USO execution** | 0.2368 | 0.0997 | 0.6181 | higher OOS but **IS collapses to 0.0997** — USO's roll cost eats the pre-2019 edge |

**Reading:** every honest variant confirms the same story. The long-only timing (V1/V2) has a small positive IS but fails k1/k2. The **continuous/market-neutral V3 is negative everywhere** — the genuinely-untested 'short the contango' expression that the ETF report speculated might work **does not**: deep-contango shorts lose money (the curve is usually right that spot will fall, but the roll-down you'd harvest is swamped by spot vol). V4 (USO execution) shows the real-world roll cost **destroys the small pre-2019 IS edge** — the premium is too thin to survive an actual tradeable wrapper.
## 6. Lookahead canary — no leakage

- **Honest** (prior-day curve, T+1 lag): FULL Sharpe **0.1988**.
- **Cheat** (same-day curve, NO lag — decides and trades on the same close it observes): FULL Sharpe **0.1976**.
- Paths differ: **True** → honest != cheat => no leakage (cheat uses same-day curve + no lag). The honest path is actually a hair *higher* than the cheat here (0.1988 vs 0.1976), which is fine — it confirms there is no leaked forward information being exploited; the tiny gap is just the T+1 execution timing, not an edge.

## 7. Cost grid (0/2/5 bps; 2 bps primary) — cost is NOT the killer

| Cost (bps) | FULL Sharpe | OOS Sharpe | OOS total | Static-long OOS total | Beats control? |
|---|---|---|---|---|---|
| 0 | 0.2001 | 0.3732 | +41.9% | +61.5% | **no** |
| 2 | 0.1988 | 0.3715 | +41.5% | +61.5% | **no** |
| 5 | 0.1969 | 0.3689 | +40.9% | +61.5% | **no** |

Turnover is low (0.134/rebal — a long-or-cash monthly switch), so cost barely moves the needle (FULL 0.200→0.197 across 0→5 bps). **The signal loses to static-long at EVERY cost including 0 bps** — k2 is not a cost artifact, it is a structural give-up-the-upside problem.

## 8. Threshold sensitivity — k2 fails at EVERY threshold; k4 is modest

| Signal threshold | FULL Sharpe | **IS Sharpe** | OOS Sharpe | OOS total | Beats static-long OOS? |
|---|---|---|---|---|---|
| -0.005 | 0.0511 | **0.0585** | 0.0201 | -32.7% | **no** |
| -0.002 | 0.132 | **0.1105** | 0.2469 | +15.8% | **no** |
| +0.000 | 0.1988 | **0.1679** | 0.3715 | +41.5% | **no** |
| +0.002 | 0.0691 | **0.0458** | 0.1975 | +8.8% | **no** |
| +0.005 | 0.0874 | **0.129** | -0.1659 | -30.8% | **no** |
| +0.010 | -0.0292 | **-0.0028** | -0.1935 | -28.5% | **no** |

**Two honest reads:** (1) **k2 fails at every threshold** — there is no long-only cutoff that beats dumb static-long-WTI net OOS. (2) **k4 (positive IS) holds at the primary (thr=0, IS +0.168) and most thresholds**, but it degrades and even goes slightly negative at thr=+0.01 — so the positive IS is **real but modest**, not a robust high-Sharpe plateau. The premium exists pre-2019 (the genuine new finding); it is simply too small to clear the bars.

## 9. SPX on the actually-traded path + orthogonality

- **SPX (SPY) on the commodity-leg traded calendar:** FULL Sharpe 0.5487, OOS 0.8508 (the 2019–2024 OOS window was a strong equity tape — context for the OOS numbers everywhere).
- **Commodity leg corr → SPX: +0.0534** (monthly). Essentially **zero equity beta** — a clean improvement over the ETF proxy's +0.45 long-commodity-beta fingerprint. The clean futures curve-shape signal really is orthogonal to equities; it just doesn't carry enough edge.

## 10. The combined sleeve — equal-risk math on a too-weak leg (k5 FAILS)

Combined carry sleeve = **equal-risk-weight (inverse-vol, 63d, monthly, lookahead-safe)** of the **bond-leg primary path** (imported `_h1_carry_bondleg_tests.run_one`: FULL 0.578 / OOS 0.434) + the **clean commodity-futures-leg primary path**, on the overlapping span **2002-08-01 → 2024-04-05** (5,436 days).

| Combined sleeve | FULL | IS≤2018 | OOS 2019+ | corr→SPX | corr→TQQQ |
|---|---|---|---|---|---|
| inverse-vol(bond, commodity-futures) | **0.4643** | 0.3439 | **0.8179** | 0.1065 | -0.0335 |

**Combined IS/OOS split-robustness:**

| split | IS Sharpe | OOS Sharpe |
|---|---|---|
| 2014-12-31 | 0.3704 | 0.6374 |
| 2016-12-31 | 0.3659 | 0.6793 |
| 2018-12-31 | 0.3439 | 0.8179 |
| 2020-12-31 | 0.3706 | 0.9643 |

**The honest k5 read — this is where it dies:**
- The diversification *math* is genuine: corr(bond, commodity) ≈ 0 (daily 0.0026), so combining lifts the OOS window to **0.8179** (naive 50/50 OOS 0.4213; inverse-vol tilts toward the calmer bond leg). The combined **IS Sharpe is also positive (0.3439)** — a real improvement over the ETF version (whose combined IS was −0.05 to −0.16).
- **BUT the combined FULL Sharpe is 0.4643**, and **span-matched bond-alone is 0.5596** (over the identical 2002-08-01→2024-04-05 window; unrestricted bond-alone to 2026 is 0.578). **Adding the commodity leg LOWERS the full-period Sharpe** (0.5596 → 0.4643). The commodity leg's weak standalone full Sharpe (0.1988) is simply too low: equal-risk-blending a 0.20-Sharpe leg into a 0.56-Sharpe leg drags the blend down on the full period, even with zero correlation. **k5 fails on both the absolute >0.578 bar AND the span-matched bond-alone bar.**
- **The forward read:** the bond leg alone is strictly better than the combined sleeve on any honest full-period basis. The commodity leg adds OOS sparkle (and, unlike the ETF version, real positive-IS diversification) but **not enough** to clear the bar — it would need roughly the bond leg's own Sharpe (~0.5+) standalone to lift the blend, and it has 0.20.

## 11. VERDICT

**k1 FAIL (0.3715 < 0.4) / k2 FAIL (−20.0pp vs static-long) / k3 PASS (-0.0115) / k4 PASS (IS +0.1679) / k5 FAIL (0.4643 < 0.5596 span-matched) → OVERALL CLOSE.**

The make-or-break gate **k2 — beats-its-own-static-long control** — fails, just as it did for the ETF proxy. But the *reason* is now honest and the failure is cleaner:

- ✅ **The clean futures instrument did its job — it removed the dirty-proxy confounds.** k4 flips from the ETF version's negative-IS-on-every-split artifact to a **stable positive IS** (+0.16 to +0.18 across four splits); corr→SPX drops from +0.45 (long beta) to +0.05 (orthogonal); the negative-2020-print and roll seams are handled correctly. **The backwardation premium is real and exists pre-2019.** This is the genuine find the reopen was chasing.
- ❌ **…but the premium is too WEAK to monetize.** Standalone full Sharpe **0.20**, OOS **0.37** (misses k1's 0.4). It **loses to dumb static-long-WTI by ~20pp OOS at every threshold and every cost** (k2) — the long-or-cash timing gives up more upside in contango than it saves in blowups. It is a **defensive overlay, not alpha** (the same disposition BAB and the ETF commodity leg earned).
- ❌ **The combined sleeve does not clear the bar.** Combined full Sharpe **0.46** < span-matched bond-alone **0.56** (k5). The 0.20-Sharpe commodity leg drags the equal-risk blend below the bond leg standing alone, despite genuine zero correlation. The OOS 0.82 is real diversification math but the full-period number — the honest, forward-proxy basis — is **worse** than just trading the bond leg.
- ⚠️ **The market-neutral expression (V3 continuous) is negative everywhere** — the 'short the contango' idea the ETF report speculated about does not work. **USO execution (V4) destroys the small IS edge** — the premium can't survive a real tradeable wrapper's roll cost.

### Disposition (the go/no-go)
**NO-GO on the commodity futures leg and NO-GO on the combined H1 carry sleeve as a paper candidate.** This is a **PARTIAL → CLOSE** outcome. What is missing is unchanged from the ETF close, now confirmed with the clean instrument: a commodity-carry signal that (a) beats its own static-long control net (it doesn't — by ~20pp), and (b) is strong enough standalone (~0.5 Sharpe) to lift the combined sleeve above the bond leg (it isn't — 0.20). The clean futures data **removed the artifact** (k4 now passes) but **revealed the premium is genuinely too small**, not absent — a more honest negative than the ETF mirage, but a negative all the same.

**What this means for the bond leg:** unchanged — **shelf-with-trigger.** The bond carry leg remains the only real, all-weather, orthogonal carry signal on the bench (full 0.578, OOS 0.434, corr −0.20/−0.14 to the book, beats both its controls, hedged 2022). It misses 0.5 standalone, and **neither the ETF-proxy nor the now-clean WTI-futures commodity leg can be the second leg that lifts it over.** The H1 'combined carry sleeve' thesis, with the commodity leg as the second leg, **fails** — under both the dirty (ETF) and clean (futures) instruments.

### Does ANY further reopen exist?
- **A *different commodity* with a stronger curve premium** (e.g. the energy complex breadth — heating oil / gasoline / natgas calendar spreads, or a cross-sectional carry across the GSCI constituents long-backwardated / short-contango, beta-neutral). WTI alone is one market; a **cross-sectional commodity carry** (the genuinely-untested multi-commodity expression) is a separate hypothesis, not a tweak of this one — but it needs free per-commodity futures-curve data (EIA gives energy; metals/ags would need another keyless source). **Low priority** given WTI's clean premium was real-but-weak; the cross-section would have to be much stronger to clear k2.
- **No reopen of WTI long-only timing.** It has now been tested with the clean instrument across thresholds, costs, both execution vehicles, and the market-neutral expression. It fails k1/k2 robustly. **This specific lane is closed.**
- **The bond leg needs no second leg** to justify its shelf-with-trigger status as a small orthogonal eff-N contributor (see the bond-leg report §9). The combined-sleeve thesis is the part that closes here.
## 12. Honesty rails self-check

- ✅ **Clean signal source, NO ETF confound.** The signal is `log(CL1/CL2)` from real EIA NYMEX WTI settle prices (`PET.RCLC1-4.D`), keyless. This is the explicit fix for the dead version's central flaw (ETF front-vs-deferred spreads conflated roll-yield with expense drag / tracking error). Execution vehicle A is the roll-adjusted futures return; vehicle B (USO) is reported separately and shown to destroy the edge — i.e. the dirty path is disclosed, not hidden.
- ✅ **Roll convention documented + negative-print handled.** Continuous front-month = within-contract CL1 return, spliced on the deferred CL2 return at roll/negative seams; the 2020-04-20 −$37.63 print is treated as a seam (only 2 seam-fallback days total), never taken as a held return. Roll convention stated in §2 and in the JSON `meta.roll_convention`.
- ✅ **POSITIVE in-sample Sharpe required AND reported on 4 splits.** IS Sharpe +0.16 to +0.18 on all of {2014,2016,2018,2020}-12-31 — the clean-instrument result that distinguishes this from the ETF version's negative-IS artifact. Reported as the k4 gate, not buried.
- ✅ **EW/static-long control = the make-or-break k2**, on the identical traded path + cost, at every threshold (0±) and every cost (0/2/5 bps). The signal **fails** it (−20pp OOS) — reported as the headline killer, not explained away.
- ✅ **Lookahead canary** (same-day curve + no lag) → honest ≠ cheat (0.1988 vs 0.1976) → no leakage.
- ✅ **Cost grid 0/2/5 bps**, 2 bps primary, monotone; shown NOT to be the killer (loses to static-long even at 0 bps). Turnover reported (0.134/rebal).
- ✅ **Full continuous-span Sharpe** (mean/std)·√252, ddof=1, on the concatenated daily series — reuses the bond-leg `sharpe`/`metrics` which mirror `runner/fp_sharpe.py`. **Never median-of-windows.**
- ✅ **SPX on the actually-traded path** (SPY returns on the futures calendar); commodity-leg corr→SPX +0.05 reported (clean orthogonality vs the ETF proxy's +0.45 beta).
- ✅ **Combined sleeve span-matched.** Because the EIA dump ends 2024-04-05, k5 is judged against the bond leg **restricted to the identical 2002-08→2024-04 overlap** (0.5596), not the bond leg's unrestricted 2026 Sharpe (0.578) — removing the 'spans differ' objection. Combined fails k5 on BOTH bars.
- ✅ **Combined sleeve reported on full AND OOS AND four-split** basis (not just the flattering OOS 0.82); the diversification math cross-checked against naive 50/50 (OOS 0.42).
- ✅ **Did NOT manufacture a pass.** The clean instrument produced exactly the genuine positives the reopen hoped for (positive IS, zero equity beta, zero bond corr) — and they are stated plainly — but they are explicitly **subordinated** to the make-or-break k2 failure and the k5 full-period drag. The honest call is CLOSE: a real-but-too-weak premium, not an artifact and not an edge.
- ✅ **PROTECTED dirs untouched.** The engine imports only `_h1_carry_bondleg_tests` (root scratch, READ-ONLY — which itself imports only `runner/fred_cache`). No other `runner/*.py`, no `strategies*/`, no crontab, no `*.db`, no broker / paper-clock / allocator files were written. All scratch + outputs live at root or in `reports/`. Futures data read from `data_cache/eia_wti/*.jsonl` (grepped from the cached bulk dump).

---

*Files: engine `_h1_carry_commodity_futures_tests.py` (root, runs clean: `python3 _h1_carry_commodity_futures_tests.py`, exit 0, reproduces every headline number); machine-readable `reports/_h1_carry_commodity_futures_result.json`; this report. Data: EIA bulk `PET.RCLC1-4.D` → `data_cache/eia_wti/rclc{1,2,3,4}.jsonl` (keyless) + USO/SHY/SPY/TQQQ adjclose (cached Yahoo) + bond-leg path via `_h1_carry_bondleg_tests.run_one` (→ keyed-FRED T10Y2Y). Single consistent UTC stamp across all deliverables.*