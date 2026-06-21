# Two-Sleeve Allocator Blend — TQQQ Vol-Target × Sector Rotation

**Date:** 2026-06-21
**Engine:** `_allocator_blend_tests.py` → `reports/_allocator_blend_result.json`
**Sleeves (reproduced EXACTLY from validated engines, same caches/stats):**
1. **TQQQ vol-target** — `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py` (TQQQ + QQQ SMA-200 gate + inverse-vol size to 25% ann vol, 20d window, 2bps abs-weight cost, VIX off). The live `leveraged_long_trend_paper` adapter mirrors this.
2. **Sector rotation top-2** — `_sigimprove_tests.run_sector_rotation` (SPY/QQQ/GLD/TLT, monthly, trailing 3-mo momentum, hold top-2 equal-weight, 2bps one-way on monthly turnover).

**Common backtest window:** 2010-02-12 → 2026-06-18 (4,112 trading days) — bounded by TQQQ's 2010 inception. All standalone numbers below are **re-computed on this identical common window** so the blend comparison is apples-to-apples.

---

## ⭐ VERDICT — YES. The blend is the bench's first real multi-sleeve allocator worth paper-trading.

**Every blend tested beats BOTH standalone Sharpes**, and the best blend cuts max drawdown by ~10 points vs the TQQQ sleeve while keeping a 16% CAGR (still beating SPX's 12.5%). The "uncorrelated-in-stress" hypothesis **largely holds** (full corr 0.58, but drops to −0.08 / 0.25–0.29 in the worst equity stress of 2011 / 2022 / 2020-Q1). This is the genuine diversification dividend the bench has been chasing — risk-adjusted return that exceeds either bet alone, from combining a levered-Nasdaq engine with a defensive GLD/TLT rotation.

- **Promotable as a paper candidate:** ✅ **YES** — recommend the **inverse-vol (risk-parity)** blend as the headline, with **50/50** as the simple, robust alternative.
- **Does a blend beat both standalone Sharpes?** ✅ YES, all six.
- **Does maxDD drop materially below −29%?** ✅ YES — inv-vol −23.9%, 50/50 −25.0% (vs ROT −29.0%, TQQQ −34.5%).

---

## Standalone sleeves (common window 2010-02 → 2026-06)

| Sleeve | Full Sharpe | CAGR | maxDD | OOS Sharpe (2019→) |
|---|---|---|---|---|
| TQQQ vol-target | 0.864 | 20.8% | −34.5% | 1.011 |
| Sector rotation top-2 | 0.929 | 13.0% | −29.0% | 0.898 |
| **SPX raw (ref)** | 0.772 | 12.5% | −33.9% | 0.841 |

Full-window ann vol: **TQQQ 25.8%**, **rotation 14.2%** — the rotation sleeve is ~1.8× calmer, which is why inverse-vol tilts ~65% into it.

---

## The blends (monthly rebalance, 2bps one-way inter-sleeve turnover cost)

| Blend (TQQQ/ROT) | Full Sharpe | CAGR | maxDD | Ann vol | IS Sharpe (≤2018) | OOS Sharpe (2019→) | OOS maxDD |
|---|---|---|---|---|---|---|---|
| 70 / 30 | 0.938 | 18.9% | −28.2% | 20.8% | 0.834 | 1.061 | −23.5% |
| 60 / 40 | 0.962 | 18.2% | −26.5% | 19.3% | 0.868 | 1.072 | −24.2% |
| **50 / 50** | **0.984** | 17.4% | −25.0% | 18.0% | 0.903 | 1.076 | −25.0% |
| 40 / 60 | 1.000 | 16.6% | −25.8% | 16.8% | 0.937 | 1.070 | −25.8% |
| 30 / 70 | 1.007 | 15.8% | −26.6% | 15.8% | 0.967 | 1.052 | −26.6% |
| **inv-vol 63d (risk parity)** | **1.014** | 15.9% | **−23.9%** | 15.8% | 0.892 | **1.147** | **−21.9%** |

> All six blends beat **both** standalone Sharpes (TQQQ 0.864, ROT 0.929). The Sharpe rises monotonically as you shift toward the rotation sleeve (because it's the higher-Sharpe, lower-vol leg), but CAGR falls — so the choice is a **return-vs-smoothness** dial, not a free lunch on raw return.

**Headline picks:**
- **Inverse-vol (risk parity) — best risk-adjusted:** Sharpe **1.014** full / **1.147** OOS, maxDD **−23.9%** (−21.9% OOS), CAGR 15.9%. Realized avg weight ≈ **35% TQQQ / 65% rotation** (it correctly downweights the wilder sleeve). This is the cleanest "allocator" — it lets vol set the mix and produces the best Sharpe AND the shallowest drawdown simultaneously.
- **50/50 — simplest robust default:** Sharpe 0.984 full / 1.076 OOS, maxDD −25.0%, CAGR **17.4%** (the highest CAGR among the high-Sharpe blends). No vol-estimation machinery, dead simple to run, and still beats both sleeves. If you want more Nasdaq punch with a clean rule, this is it.

IS/OOS stability is good across all blends (no blend collapses OOS; the inv-vol blend actually *improves* OOS to 1.147). No sign of an overfit curve.

---

## Correlation — the crux (does "uncorrelated in stress" hold?)

**Full-period daily-return correlation: 0.581** — positive and moderate. These are NOT uncorrelated in the average tape (both are long-biased equity-ish books — TQQQ is levered Nasdaq, rotation is usually holding SPY/QQQ when equities trend). So the naive "negatively correlated" framing is **too strong for the full sample**.

**BUT the correlation collapses in the equity-stress windows that matter** — exactly when TQQQ's gate flips to cash and rotation flees into GLD/TLT:

| Drawdown window | corr(TQQQ, ROT) | n days |
|---|---|---|
| 2011 summer (debt-ceiling/EU) | **−0.081** | 170 |
| 2015–2016 selloff | 0.531 | 167 |
| 2018-Q4 | 0.660 | 63 |
| 2020-Q1 COVID crash | **0.293** | 62 |
| 2022 bear | **0.248** | 251 |

**Reading:** In the two cleanest "equities-down, flight-to-safety" regimes — **2011 (−0.08)** and **2022 (0.25)** — correlation drops hard, and that's where the blend earns its keep: the TQQQ gate goes to T-bills while rotation sits in GLD/TLT, so the two legs stop moving together. 2020-Q1 (0.29) is similar but messier (the March everything-crash briefly correlated everything, then GLD/TLT decoupled). The exceptions are **2018-Q4 (0.66)** and **2015–16 (0.53)** — fast, shallow equity drops where rotation hadn't fully rotated defensive before the bounce, so both legs fell together. Net: the diversification is **regime-dependent and shows up in the slow, deep drawdowns** (2011, 2022) more than in the fast V-shapes (2018-Q4, 2020 spike).

---

## Lookahead / rigor notes

- **No lookahead in either sleeve** (inherited): TQQQ gate uses QQQ closes ≤ D and realized vol from sleeve returns ending ≤ D; rotation ranks on **prior month-end close** and holds the new month's forward returns. Verified by reading both engines.
- **No lookahead in the blend layer:** monthly target weights are set at month-open. Fixed blends use constants; the **inverse-vol weights use each sleeve's realized vol from returns STRICTLY THROUGH the prior month-end** (`returns[lo:idx]`, idx = month-open index) — a future sleeve return cannot change this month's weight.
- **Cost honesty / no double-counting:** each sleeve's *own* trading costs (TQQQ ~2bps daily abs-weight rebal; rotation 2bps monthly turnover) are **already baked into its standalone return stream**. The blend adds **only** the top-level cost of moving capital *between* the two sleeves at the monthly allocator rebalance (2bps one-way on inter-sleeve turnover). For fixed blends this is small (just the monthly drift snap-back); for inv-vol it's slightly higher (weights move with vol). No cost is charged twice.
- **Drift modeled honestly:** between monthly rebalances the sleeve weights **drift** with realized returns (the book isn't magically held at fixed weights); we snap back to target each month-open.
- **Adjusted close** used for SPY/QQQ/GLD/TLT and TQQQ/QQQ throughout (Yahoo v8 `adjclose`, split+div adjusted) — confirmed via the shared `daily_bars_cache`.
- **Independent cross-check:** a naive 50/50 daily-average (no drift, no cost) gives Sharpe **0.987** vs the engine's **0.984** — the tiny gap is exactly the drift+cost drag, confirming the blend machinery isn't inflating the result.

---

## Honest caveats

1. **Both legs are still long-biased equity-ish.** Full-period corr 0.58 means this is NOT a market-neutral or truly-uncorrelated pair. It's "two equity-flavored books whose *tails* decouple," not "stocks + a genuine hedge." A simultaneous crash in *both* equities AND bonds/gold (see #2) would hit both legs.
2. **GLD/TLT 2022 behavior is the live risk.** The rotation sleeve's defense rests on GLD/TLT being a haven when equities fall. **2022 was the regime where that partly broke** — TLT fell *with* stocks as rates ripped. The blend still helped in 2022 (corr only 0.25, and rotation could rotate into GLD/cash via momentum), but a repeat rate-shock where bonds AND stocks both bleed is the scenario that most erodes the diversification. The momentum rank does give it an escape hatch (it can drop TLT if TLT's 3-mo momentum turns negative), which is why 2022 wasn't a disaster — but don't assume bonds always save you.
3. **Survivorship (inherited, unfixable here):** TQQQ exists *because* 3× Nasdaq went up 2010–2026. The whole common window is a survivor's bull-tilted sample. Vol-targeting and blending reshape the risk; they don't undo survivorship. The rotation sleeve has 2008 coverage in its native 2005-start window (Sharpe held there), but the *blend* can only be tested from 2010 (TQQQ inception) — so **the blend has never seen a 2008-magnitude event.**
4. **Window-bounded:** 4,112 days / ~16.3 years is a decent sample but spans essentially one secular bull with corrections. One genuine regime change (prolonged stagflation, a lost decade for both Nasdaq and bonds) is outside this test.
5. **Drawdown-window correlations are short samples** (62–251 days each) — directionally informative, not precise. The 2011/2022 decoupling is the robust signal; the exact coefficients aren't.

---

## Recommended next steps

1. **Promote the inverse-vol blend (and 50/50 as the simple sibling) to the paper roster** as the bench's first multi-sleeve allocator. Paper-trade both; the inv-vol one is the thesis (vol-weighted risk parity), the 50/50 is the can't-overfit control.
2. **Stress the GLD/TLT-fails scenario explicitly** — re-run the blend forcing the rotation sleeve's bond/gold legs to behave like 2022 (or substitute a cash-only defensive leg) to bound the downside when the haven breaks.
3. **Walk-forward the inv-vol lookback** (63d is a first guess; test 21/42/126d) for stability before trusting the 1.014 to the third decimal.
4. **Consider a 3rd uncorrelated sleeve** later (e.g. a managed-futures/trend leg with real negative-equity-beta) to push the full-period correlation down — that's the path from "good blend" to "genuinely diversified allocator."
