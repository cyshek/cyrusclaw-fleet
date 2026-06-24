# Allocator Haven Frontier — Does the GLD/TLT/DBC/UUP Haven Add to the LIVE inv-vol allocator_blend?

**Date:** 2026-06-23 (UTC stamp 20260623T222956Z)
**Assignment:** wire the validated GLD/TLT/DBC/UUP all-weather haven sleeve into the LIVE allocator mechanism (inverse-vol 63d blend, `runner/allocator_paper_tracker.py` `invvol_63d`) as a 3rd INVERSE-VOL leg, and produce an apples-to-apples frontier-lift go/no-go vs the live 2-sleeve blend.
**Engine:** `_allocator_haven_frontier_tests.py` — reuses `_allocator_blend_tests.build_sleeves/blend_portfolio/report_blend` and `_haven_rateshock_tests.build_hardened_haven` VERBATIM (zero blend-math reimplementation). Result JSON: `reports/_allocator_haven_frontier_result.json`. No protected/live files / crontab / paper clock / .db touched.
**Rails:** adjusted-close returns · 2bps one-way inter-sleeve turnover · monthly rebal w/ intramonth drift · PAST-ONLY trailing 63d vol · OOS split 2018-12-31 · SPX (^GSPC) on the SAME traded path · no lookahead (canary: past-only confirmed = True).

---

## TL;DR — VERDICT: **GO-WITH-CAP**

The **live inverse-vol mechanism massively over-allocates to the haven** — pure 3-way inv-vol hands the haven **60%** of the book (because at ~5.5% ann vol it is by far the lowest-vol leg, and inv-vol mechanically piles into the calmest sleeve). At that weight the book becomes a bond/haven-dominated portfolio: raw return **craters to 329%** (vs the 2-sleeve's 1011% and SPX's 595%), failing the raw mandate. So **pure inv-vol is the WRONG wiring**. The right wiring is a **capped/fixed haven weight**: the recommended operating point is **fixed_haven_10 (haven 10%)**, which keeps raw return well above SPX while buying the risk-adjusted improvement.

**Recommended operating point — fixed_haven_10:** haven **10%** · full Sharpe **1.035** · OOS Sharpe **1.177** · raw **850%** (giveup **161pp** vs 2-sleeve, still **+255pp** over SPX) · maxDD **-21.5%** · 2022 maxDD **-17.7%** (ret -12.3%).

---

## Aligned window & haven sleeve

- **Common (traded) window:** 2010-02-12 → 2026-06-22 (4113 days) — the INTERSECTION of the allocator calendar and the haven calendar; identical for every config below.
- **Allocator native window:** 2010-02-12 → 2026-06-23 (4114 days). Dropped **1** trailing day(s) the haven can't yet cover (DBC/UUP adjclose posts a day late): 2026-06-23 — a non-issue (stale-by-one-day tail, not a coverage gap).
- **Haven native window (GLD/TLT/DBC/UUP, UUP-binding):** 2007-03-02 → 2026-06-22 (4857 days). Since 2007-03-02 ≤ 2010-02-12, the haven **fully spans** the entire traded window with **0 missing dates / 0 NaN** on the common calendar — confirmed aligned by intersection.
- **Haven spec:** GLD/TLT/DBC/UUP, inverse-vol parity 4-way, 63d past-only vol, monthly rebal w/ intramonth drift, 2bps — the EXACT validated sleeve (`build_hardened_haven`).
- **Leg full-window ann vol:** TQQQ **25.8%** · ROT **14.2%** · HAVEN **5.5%**. The haven is by far the lowest-vol leg — this is *why* pure inv-vol over-weights it.
- **Haven standalone (allocator window):** Sharpe 0.782 · CAGR 4.26% · maxDD -14.4% · raw 98% · ann-vol 5.5% · OOS Sharpe 1.225. Negative raw vs SPX by design (insurance, not an engine).
- **eff-N:** 2-leg **1.495** → 3-leg **2.324** (adding the haven raises effective independence).

---

## The frontier (identical common window, SPX raw = 595%)

| Config | full Sharpe | OOS Sharpe | CAGR | raw ret | maxDD | 2022 maxDD | 2022 ret | ann vol | avg haven wt |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **LIVE 2-sleeve inv-vol** *(baseline)* | 1.014 | 1.145 | 15.9% | 1011% | -23.9% | -19.6% | -13.7% | 15.8% | 0% |
| 3-sleeve **PURE inv-vol** *(live mechanism extended)* | 1.227 | 1.459 | 9.3% | 329% | -12.4% | -10.9% | -4.9% | 7.5% | 60% |
| fixed haven 5% (rest inv-vol) | 1.024 | 1.160 | 15.4% | 928% | -22.6% | -18.6% | -13.0% | 15.1% | 5% |
| fixed haven 10% (rest inv-vol) | 1.035 | 1.177 | 14.8% | 850% | -21.5% | -17.7% | -12.3% | 14.3% | 10% |
| fixed haven 15% (rest inv-vol) | 1.048 | 1.195 | 14.2% | 777% | -20.3% | -16.7% | -11.5% | 13.6% | 15% |
| fixed haven 20% (rest inv-vol) | 1.060 | 1.215 | 13.7% | 709% | -19.2% | -15.6% | -10.8% | 12.9% | 20% |
| **SPX raw** *(benchmark)* | 0.776 | 0.845 | — | 595% | -33.9% | -25.4% | -19.4% | — | — |

**Realized inv-vol haven weight (the headline finding):** pure 3-way inv-vol hands the haven **60.1%** of the book on average — because at 5.5% ann vol it is the calmest leg and inv-vol mechanically concentrates in the calmest sleeve. That is **far above** the ~25% sensible-weight flag — the live mechanism would need a haven cap.

---

## Decision gates (g1–g4)

Evaluated on the **3-sleeve PURE inv-vol** config (the natural live-mechanism extension), vs the reproduced live 2-sleeve baseline.

| Gate | Test | Result | Detail |
|---|---|:--:|---|
| **g1** | 3-sleeve pure inv-vol still beats SPX raw | ❌ FAIL | 3sl pure raw 329% vs SPX raw 595% |
| **g2** | 3-sleeve OOS Sharpe ≥ live 2-sleeve OOS Sharpe | ✅ PASS | 3sl pure OOS Sharpe 1.459 vs 2sl OOS Sharpe 1.145 |
| **g3** | 3-sleeve maxDD AND 2022-DD shallower than 2-sleeve | ✅ PASS | 3sl maxDD -12.4% vs 2sl -23.9% | 3sl 2022DD -10.9% vs 2sl -19.6% |
| **g4** | inv-vol hands haven a SENSIBLE weight (≤~25%) | ❌ FAIL | pure inv-vol hands haven 60.1% (> ~25% cap-flag) |

---

## VERDICT — **GO-WITH-CAP**

**Does adding the haven improve the LIVE allocator_blend operating point? — YES, but ONLY with a haven cap; pure inv-vol is the wrong wiring.**

- **The live inv-vol mechanism over-allocates to the haven (g4 FAIL).** Because the haven is the lowest-vol leg (5.5% vs TQQQ 25.8%/ROT 14.2%), pure 3-way inv-vol hands it **60.1%** of the book. That turns the levered-growth allocator into a haven-dominated portfolio.
- **Raw return craters under pure inv-vol:** 329% vs the 2-sleeve's 1011% and SPX's 595% — FAILS the raw mandate (g1 FAIL).
- **The fix is a capped/fixed haven weight.** The recommended operating point is **fixed_haven_10 (haven 10%)**: it keeps raw return at **850%** (still **+255pp** over SPX, only **161pp** below the 2-sleeve) while improving the drawdown/risk-adjusted profile.
- **Why 10% and not the highest-Sharpe sweep point?** The fixed-haven sweep is **monotonic** in haven weight — every +5pp of haven raises Sharpe and shallows the drawdown but costs ~75-80pp of raw return, with **no interior optimum** from Sharpe alone (a 'max-Sharpe' selector just runs to the highest grid weight). Under the **raw-return mandate** the principled cap is the **validated, pre-registered 10% shelf**: it captures the meaningful DD/Sharpe improvement (2022-DD -19.6%→-17.7%, maxDD -23.9%→-21.5%, OOS Sharpe 1.145→1.177) while preserving the **largest raw cushion** over SPX. **15-20% is available** if more insurance is wanted (15% → raw +182pp/SPX, OOS Sh 1.195, 2022-DD -16.7%; 20% → raw +114pp/SPX, OOS Sh 1.215, 2022-DD -15.6%) — but each step trades ~75pp of raw return for ~+0.02 Sharpe, a sacrifice the current mandate argues against.
- **Recommended-cap rationale:** validated pre-registered shelf point; principled under the raw mandate (sweep is monotonic so 'max Sharpe' would just pick the highest grid weight -- 10% keeps the largest raw cushion while still improving DD/Sharpe). 15-20% available for more insurance.

### The honest raw-giveup tradeoff

The mandate is **BEAT SPX RAW** (gates suspended). A haven **reduces** raw return — it is insurance, not an engine. So the only question that matters is whether the risk-adjusted improvement (Sharpe / maxDD / 2022-DD / eff-N) is worth the raw giveup, AND whether the wired config still clears SPX raw. Concretely on this window:

- **2-sleeve baseline:** raw **1011%**, full Sharpe 1.014, OOS Sharpe 1.145, maxDD -23.9%, 2022 maxDD -19.6%.
- **fixed-10% haven:** raw **850%** (giveup 161pp), full Sharpe 1.035, OOS Sharpe 1.177, maxDD -21.5%, 2022 maxDD -17.7% — the validated shelf point.
- **pure inv-vol (haven 60%):** raw **329%** (giveup 683pp) — the giveup is large precisely because inv-vol over-weights the haven; the risk-adjusted metrics improve but not enough to justify abandoning the raw mandate.

---

*Numbers cross-checked console vs JSON on a clean re-run. Engine reuses `_allocator_blend_tests` (build_sleeves / blend_portfolio / report_blend) and `_haven_rateshock_tests.build_hardened_haven` verbatim. Lookahead canary (inv-vol past-only) = True. Candidate research only — no protected/live files, crontab, paper clock, or .db touched. Full numeric dump: `reports/_allocator_haven_frontier_result.json`.*
