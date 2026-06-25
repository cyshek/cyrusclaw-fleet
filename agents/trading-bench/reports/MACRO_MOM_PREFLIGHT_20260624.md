# MACRO MOMENTUM cross-sectional L/S — PRE-FLIGHT (GO/NO-GO)

**Date:** 2026-06-24
**Author:** Tessera (trading-bench), subagent `macro_mom_preflight2`
**Type:** Cheap pre-flight feasibility probe (research-only; no protected file touched, nothing scheduled, no trade)
**Idea:** #4 from `reports/AQR_READING_SPRINT_20260624.md` — AQR "Macro Momentum" (Brooks 2017) cross-sectional rank as a market-neutral L/S sleeve.

## VERDICT: 🔴 RED — close the free cross-sectional-momentum frontier

**One-line reason:** The honest dollar-neutral L/S **spread is weak (FP Sharpe ≤ 0.36), and broadening the basket from 6 → 11 macro assets made it WORSE, not better (0.36 → 0.20), with the tercile L/S going outright negative (−17% cum).** All the return lives in the LONG leg; the short leg has a *positive* Sharpe (bottom-half assets still rose), so shorting them is a drag — this is a diluted long-only momentum tilt, not a market-neutral alpha. Same saturation pathology as the prior price-only attempts, confirmed.

---

## The question (binary)

Does a cross-sectional momentum rank on a **macro** multi-asset basket produce a tradeable, persistent L/S **spread** — or does it saturate/fail like the prior price-only xsec attempts (`_run_tsmom_xa_wf.py`, median Sharpe 0.41, signal saturates ~6 assets)?

**Answer: it fails / saturates. Broadening the basket — the one un-probed lever that might have fixed saturation — actively HURT.**

## Method

- **Basket (broad, 11 assets, the un-probed angle):** equities SPY, EFA, EEM · rates TLT, IEF · commodities DBC, GLD, USO · credit/REIT LQD, VNQ · dollar UUP. Every symbol returns clean adjclose via `runner.daily_bars_cache.get_daily`. Spans confirmed first (`_macromom_spans.py`): latest start is **UUP 2007-03-01**, so a **2008+ window has all 11 assets clean**. Window used: **2008-02-01 → 2026-06-01, 221 monthly rebalances.**
- **Comparison basket:** the prior failed 6 — SPY, EFA, TLT, VNQ, DBC, GLD — same window.
- **Signal (free framing of "macro momentum"):** AQR blends trailing macro fundamentals + price momentum; with free adjclose-only data the defensible proxy is the **price-momentum leg** — a blended 3/6/12-month trailing total return per asset, each skipping the most recent month (21 td) to avoid 1-month reversal, z-scored across the basket each rebalance. (Brooks shows price momentum carries most of the cross-sectional rank signal.)
- **The honest test (standing cross-sec gate):** monthly rebal, **long top-half / short bottom-half, dollar-neutral, equal-weight within leg**; the metric is the **LONG-minus-SHORT spread**, full-period continuous Sharpe (annualized monthly, √12). A long-only "beats basket" does NOT count.
- **Harness note:** composed the spread directly from adjclose (the documented workaround — `walk_forward_xsec` skips <2-sym baskets / raises ZeroTradesError on warmup, and the long-top-K harness does not expose a clean dollar-neutral L/S spread series). Lookahead-safe: scores use only data ≤ rebalance date `d0`; forward returns realized `d0 → d1`.
- **Costs:** 2 bps/side applied to the symmetric-difference turnover of both legs (open+close).

## Results — the L/S SPREAD (the only number that counts)

| Config | Assets | Spread FP Sharpe | IS (pre-2019) | OOS (2019+) | Spread cum % | Net of 2bps |
|---|---|---|---|---|---|---|
| **Broad half-L/S** | 11 | **0.20** | 0.20 | 0.22 | +45.3% | 0.20 (Sharpe 0.198) |
| **Prior6 half-L/S** | 6 | **0.36** | 0.27 | 0.56 | +140.0% | 0.36 (Sharpe 0.361) |
| **Broad tercile L/S (top3/bot3)** | 11 | **0.075** | 0.02 | 0.17 | **−17.1%** | 0.071 |

**Reference (long-only / basket, NOT the test):** broad long-top-half FP Sharpe 0.64 (cum +226%); prior6 long-top-half 0.83 (cum +502%); equal-weight basket BH 0.52 / 0.59. The long-only momentum tilt "beats basket" — but that is exactly the long-only-isn't-enough trap the cross-sec gate exists to catch.

**Rolling 24-month spread-Sharpe sign stability (zero cost):**
- Broad-11 spread positive in only **54.0%** of 198 rolling windows (range −1.08 … +1.78) — essentially a coin flip.
- Prior6 spread positive in **65.7%** of windows (range −0.78 … +2.08).

## Why it fails (the mechanism)

1. **All signal is in the long leg.** Long-only Sharpe 0.64–0.83 vs spread 0.20–0.36. The short leg's *own* Sharpe is **positive** (+0.20 to +0.27) — the bottom-half "losers" still went up on average over 2008–2026 (everything rose). Shorting things that rise is a **drag**, so the spread is just "long winners minus the cost of shorting things that also rose." That is a diluted long-only momentum exposure, not market-neutral alpha.
2. **Broadening HURT, did not help.** The hypothesis was that more independent macro exposures (EEM, IEF, USO, LQD, UUP added to the 6) would break the ~6-asset saturation. The opposite happened: spread Sharpe fell **0.36 → 0.20**. The added assets are not independent enough to sharpen the cross-section; they dilute it. The prior report's worry ("#4 likely repeats the saturated result") is **confirmed and then some** — broadening is worse than the saturated baseline.
3. **Concentrating to extremes is catastrophic.** Top-3/bottom-3 of the broad basket collapses to Sharpe **0.075** with a **negative −17% cumulative spread** — the strongest-momentum assets do not reliably out-return the weakest-momentum assets net of the short drag.

## Gate decision

| Gate criterion | Result |
|---|---|
| L/S spread positive full-period? | Broad: marginally (+0.20). Tercile: **NO (−17% cum).** |
| OOS-stable (pre/post-2019)? | Broad IS 0.20 / OOS 0.22 — stable but **trivially small**. |
| Broadening lifts vs prior 6-asset 0.41? | **NO — broadening DROPPED it (0.36 → 0.20).** |
| Survives 2bps? | Cost is immaterial (low turnover) — but there's almost nothing to survive. |

→ **🔴 RED.** Not GREEN (spread is weak, broadening backfired, no market-neutral edge). Not even AMBER (it's not marginal-but-promising — broadening, the specific lever this pre-flight existed to test, made it strictly worse, and the concentrated version is negative). **The free cross-sectional-momentum frontier is exhausted** — price-only TSMOM xsec (prior), macro-momentum half-L/S (here), and tercile L/S (here) all land in the same place: the cross-sectional *spread* carries no robust market-neutral alpha on a free multi-asset basket; the only thing that "works" is the long-only momentum tilt, which is not what the gate asks for.

## Recommendation

**Close the lane cleanly.** Do not promote to a full build. The standing conclusion from the prior xsec attempts holds and is reinforced: on free multi-asset data the cross-sectional momentum *spread* ≈ a diluted long-only tilt once you subtract the short-leg drag, and adding assets dilutes rather than sharpens it. To genuinely revisit macro momentum would require the **actual macro-fundamental signals** Brooks uses (trailing growth/inflation/real-yield momentum on individual markets via futures) — not free adjclose price momentum — which is a paid-data / futures-universe decision, not a free build. Park here.

---
*Artifacts: `_macromom_spans.py` (history confirm), `_macromom_preflight.py` (half-L/S engine, both baskets, 0/2bps), `_macromom_sensitivity.py` (tercile L/S + rolling-24m sign stability), results in `_macromom_results.json` / `_macromom_sensitivity.json`. No protected file touched; no crontab edit; nothing scheduled; no trade. All Python written to files with real newlines, py_compile-verified before run (heeded the literal-`\n` heredoc warning).*

---

## APPENDIX — second pre-flight (real FRED macro signals, long-only): 🟡 AMBER-defensive

A parallel pre-flight (`macro_mom_preflight`, recovered) tested a DIFFERENT construction — not the price-momentum L/S above, but a **real macro-regime tilt** using FRED fundamentals — and reached a complementary AMBER. Both are preserved because they answer different questions; together they fully characterize #4. Scratch: `_macro_mom_engine.py` / `_macro_mom_driver.py` / `_macro_mom_stress.py` / `_macro_mom_subperiod.py`.

**Construction:** monthly, **long top-2 EW** (NOT L/S). Per-asset transparent +1/−1 growth/inflation regime score from 6 FRED series — INDPRO, CPIAUCSL (monthly, **PIT-lagged ≥2 calendar months** — no release leak), T10Y2Y, DGS10, BAA10Y, DTWEXBGS (daily, lagged 1 trading day). 6-asset basket SPY,EFA,TLT,VNQ,DBC,GLD, span 2007-05→2026-06 (4,818d).

**Head-to-head (identical span), VERIFIED by parent re-running `_macro_mom_subperiod.py`:**
| Variant | Sharpe | CAGR% | MaxDD% | corr→SPY |
|---|---|---|---|---|
| macro-only long-top-2 | 0.77 | 10.4 | −22.7 | 0.26 |
| price-only baseline | 0.63 | 8.9 | −37.1 | 0.38 |
| combined macro+price | 0.65 | 9.0 | −30.5 | 0.31 |
| SPY buy&hold | 0.62 | 10.7 | −55.2 | 1.00 |

**Crisis (macro / price / SPY):** 2008 **+16.2% / −9.0% / −43.9%**; 2020 +3.9% / −0.2% / −9.2%; 2022 +2.2% / −6.0% / −17.7%.

**Subperiod stress (parent-reproduced exactly):**
- 2007–2009 incl GFC: macro **0.98** / price 0.24 — the entire edge.
- 2010–2019 expansion: macro 0.58 / price **0.65** — price WINS.
- **Ex-GFC (drop 2008-01..2009-06): macro 0.79 vs price 0.77 — dead heat** (price higher CAGR 10.6% vs 10.1%).

**Robustness:** Sharpe holds 0.70–0.77 across 2m/3m/4m PIT lags (2008 alpha survives a 3-mo-stale feed); a crude growth+inflation-only score is *better* (0.88 Sharpe, −20% DD) → edge is macro CONTENT, not tuned rules. Picks TLT 36% / DBC 50% → **saturation prior does NOT repeat** for the long-only macro tilt.

**Why AMBER not GREEN:** the macro edge is **crisis-alpha + ~40%-shallower drawdown**, NOT general return content (ex-GFC it ties price; combined dilutes → macro & price don't stack).

## COMBINED #4 VERDICT (reconciled) — NO-GO as a return engine under the raw-return mandate
- **L/S market-neutral spread: 🔴 RED** — dead, broadening worsens it; the standing cross-sec gate fails. The free xsec-momentum *spread* frontier is exhausted.
- **Long-only macro-regime tilt: 🟡 AMBER-defensive** — real, leak-free crisis-alpha + drawdown protection, but **CAGR 10.4% < SPY 10.7% → does NOT beat SPX raw.** Same disqualification as the 80/20 blend and the core4 sleeve: a risk-adjusted/crisis win, not a raw-return engine.
- **Mission verdict (mandate = beat SPX RAW):** #4 does NOT advance the mission. Parked. The macro-regime tilt + its leak-free FRED PIT machinery (`_macro_mom_engine.py`) are SHELF-READY crisis-insurance, re-addable if the mandate ever reinstates a risk-adjusted/DD-wall trigger. A genuine raw-return macro-momentum revisit needs Brooks's actual macro-fundamental signals on a futures universe = paid/futures decision.
