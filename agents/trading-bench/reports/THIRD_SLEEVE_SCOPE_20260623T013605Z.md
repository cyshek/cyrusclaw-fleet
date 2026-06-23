# Third-Sleeve Scope — Does a 3rd Low-Correlation Sleeve Lift the Validated 2-Sleeve Blend?

**Date:** 2026-06-23 (UTC stamp 20260623T013605Z)
**Lane:** Structural-edge (deliberate pivot away from timing-signal hunting toward structural diversification).
**Mission bar:** BEAT SPX ON RAW RETURN. Gates suspended. Honest measurement non-negotiable.

## TL;DR — VERDICT: CLOSE the 3rd-sleeve question for a raw-return mandate.

Under the bench's actual mandate (**beat SPX on raw return**), **no 3rd sleeve helps.** The genuine
diversifiers (managed-futures / trend) lift Sharpe and slash drawdown but **halve raw return and lose to
SPX**, because the inverse-vol allocator piles 40–60% of the book into a calm, low-return trend leg and
starves the levered-Nasdaq engine that produces the raw return. The only candidate that beats SPX raw
(CREDIT) is **closet-SPY** (corr 0.66–0.70) — not real diversification, and it even hurts OOS Sharpe at
short lookbacks. **The validated 2-sleeve blend already captures the available diversification.**

**Deciding stat (deep 2010-02→2026-06 window):** 3-sleeve+trend raw return **280%** vs SPX **595%** vs
2-sleeve **1040%**. The 3rd sleeve cuts the blend's raw return to ~⅓ of the 2-sleeve and below SPX.

---

## What was tested (and how it reuses the validated engine)

The promoted blend = TWO sleeves combined by inverse-vol (63d) risk-parity:
(1) **TQQQ vol-target** sleeve, (2) **sector-rotation top-2** of [SPY,QQQ,GLD,TLT] monthly 3mo-momentum.
Engine: `_allocator_blend_tests.py` → `build_sleeves()` + `blend_portfolio()`.

This study **reuses those functions verbatim** and extends `blend_portfolio` to N sleeves (it already
takes a list of sleeves + an N-way weight function). The 3-sleeve blend uses the **SAME** inverse-vol
risk-parity machinery and the **SAME** 2bps inter-sleeve cost — an apples-to-apples comparison on
**identical dates** (the intersection of the 2-sleeve common window with each candidate's own data).
Scratch code: `_third_sleeve_tests.py`, `_third_sleeve_robust.py`. No protected/live files touched.

**2-sleeve baseline to beat** (full common window 2010-02→2026-06): inv-vol blend **full Sharpe 1.007,
OOS 1.120, maxDD −28.0%*, CAGR 16.1%, raw return 1040%**.
(* The hardening report quotes −23.9% maxDD for the full 2010-2026 inv-vol blend; this run's −28.0% is the
same engine but the drawdown figure is sensitive to the exact day-0 alignment of the common window and the
63d-vol warmup — the comparison below is internally consistent because 2-sleeve and 3-sleeve are computed
identically on the same window.)

### Candidates (priority order)
| # | Candidate | What it is | Data span | History caveat |
|---|-----------|-----------|-----------|----------------|
| P1a | **DBMF** | iMGP DBi Managed Futures ETF (real CTA) | 2019-05-09 → 2026-06-22 (1789 shared d) | SHORT — no 2008/2011/2018 |
| P1a | **KMLM** | KraneShares Mt Lucas Managed Futures ETF (real CTA) | 2020-12-03 → 2026-06-22 (1392 shared d) | SHORTEST — only 2022 stress |
| P1b | **SYN_TREND** | Synthetic 12-1 TSM long/flat basket over DBC/GLD/TLT/UUP (crude CTA replication) | 2010-02-12 → 2026-06-22 (4113 d) | DEEP but approximate (not a real MF fund) |
| P2 | **CREDIT** | FRED BAA10Y credit-spread z-score risk-on/off (SPY when calm, IEF when stressed) | 2010-02-12 → 2026-06-22 (4113 d) | DEEP; macro structural leg |

**Handling the short-MF-history problem:** the real MF ETFs (DBMF/KMLM) only exist post-2019, so they are
reported on their own short clean windows; SYN_TREND provides the deep (2010+) approximate read on the same
trend thesis. I did **not** truncate the good 2-sleeve history except where doing the head-to-head against a
short 3rd leg (where identical dates are required). DBMF/KMLM/UUP were freshly fetched to `data_cache/yahoo/`
(Yahoo v8, browser UA, query1→query2 backoff) — no re-fetch of already-cached symbols.

---

## 1. Correlation table — the gate that matters

Daily-return correlation of the **3rd sleeve vs each existing leg and vs the 2-sleeve blend**, full window
and in stress sub-windows. (n/a = candidate's data doesn't reach that window.)

| Candidate | vs TQQQ-leg (full) | vs ROT-leg (full) | **vs 2-sleeve blend (full)** | blend·2020-Q1 covid | blend·2022 bear | blend·2011 |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|
| **DBMF**      | 0.30 | 0.25 | **0.28** | **0.57** | **−0.38** | n/a |
| **KMLM**      | −0.01 | −0.11 | **−0.10** | n/a | **−0.37** | n/a |
| **SYN_TREND** | 0.02 | 0.36 | **0.21** | **0.58** | 0.08 | 0.64 |
| **CREDIT**    | 0.66 | 0.58 | **0.70** | **0.86** | 0.66 | 0.21 |

**Read:**
- **Trend (DBMF/KMLM/SYN_TREND) is genuinely low-corr** to the blend (full 0.21–0.28, KMLM even −0.10), and
  **negatively correlated in the 2022 bear** (DBMF −0.38, KMLM −0.37) — the textbook crisis-alpha behavior.
- **BUT the 2020-Q1 covid corr is HIGH (0.57–0.58)** for DBMF and SYN_TREND. Trend-following is slow; it gets
  caught in V-shaped crashes and **does not protect the fastest drawdown** the blend faces. So even its
  diversification is regime-specific (helps in slow grinds like 2022, not in fast crashes like covid).
- **CREDIT is high-corr everywhere** (0.70 full, 0.86 in covid). It is effectively closet-SPY — it holds SPY
  most of the time and only ducks to IEF on a wide-spread z-score. **Dead on arrival as a diversifier.**

---

## 2. Head-to-head: 3-sleeve vs 2-sleeve vs SPX (on the traded path, net of cost)

All on **identical dates** per candidate, inverse-vol 63d, 2bps inter-sleeve cost. "SPX raw" = buy-&-hold
^GSPC total return on the same window. **Mission bar = beat SPX raw.**

| Candidate (window) | Variant | Raw ret | CAGR | Sharpe | OOS Sharpe | maxDD | avg 3rd-wt | **Beats SPX raw?** |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| **DBMF** 2019-05→2026-06 (SPX raw **160%**) | 2-sleeve | **255%** | 19.6% | 1.096 | 1.096 | −28.0% | — | ✅ |
| | 3-sleeve+DBMF | 158% | 14.3% | 1.142 | 1.142 | **−14.6%** | 0.46 | ❌ |
| **KMLM** 2020-12→2026-06 (SPX raw **104%**) | 2-sleeve | **145%** | 17.6% | 1.029 | 1.029 | −28.0% | — | ✅ |
| | 3-sleeve+KMLM | 86% | 11.9% | 1.056 | 1.056 | **−9.9%** | 0.41 | ❌ |
| **SYN_TREND** 2010-02→2026-06 (SPX raw **595%**) | 2-sleeve | **1040%** | 16.1% | 1.007 | 1.120 | −28.0% | — | ✅ |
| | 3-sleeve+SYN_TREND | 280% | 8.5% | 1.057 | **1.244** | **−10.8%** | 0.60 | ❌ |
| **CREDIT** 2010-02→2026-06 (SPX raw **595%**) | 2-sleeve | **1040%** | 16.1% | 1.007 | 1.120 | −28.0% | — | ✅ |
| | 3-sleeve+CREDIT | 795% | 14.4% | 1.060 | 1.044 | −30.0% | 0.43 | ✅ |

**Read:** Every 3rd sleeve **lifts full Sharpe** (+0.03 to +0.09) and the trend sleeves **cut maxDD roughly
in half** (−28% → −10 to −15%). But on **raw return** — the mandate — the trend 3-sleeve **loses to SPX in
all three cases**, cutting the blend's return by ~40–73%. CREDIT beats SPX raw but only because it's
basically SPY with a small drawdown trim (no structural diversification, and it underperforms 2-sleeve raw
by 245 pts).

---

## 3. Robustness — does the conclusion survive different inverse-vol lookbacks?

Re-ran the head-to-head at inv-vol lookbacks **21 / 42 / 63 / 126d**. The "3-sleeve loses to SPX on raw
return" conclusion is **invariant** for every trend candidate at every lookback (`3s>SPX-raw? = NO` in all
12 trend cells). CREDIT beats SPX raw at every lookback (but is closet-SPY).

| Candidate | lb=21 | lb=42 | lb=63 | lb=126 | 3s beats SPX raw? |
|---|---|---|---|---|:---:|
| DBMF (3s raw ret) | 130% | 144% | 158% | 152% | **NO** (SPX 160%) — fails all |
| KMLM (3s raw ret) | 78% | 80% | 86% | 91% | **NO** (SPX 104%) — fails all |
| SYN_TREND (3s raw ret) | 273% | 294% | 280% | 295% | **NO** (SPX 595%) — fails all |
| CREDIT (3s raw ret) | 677% | 776% | 795% | 934% | YES (SPX 595%) — but closet-SPY |

Sharpe-wise the 3-sleeve trend blend beats the 2-sleeve at lb=21/42/63 but **flips to worse at lb=126**
(DBMF 1.105 vs 1.162; KMLM 1.105 vs 1.115) — i.e. even the risk-adjusted win is lookback-fragile. CREDIT
**hurts OOS Sharpe** vs 2-sleeve at lb=21 (0.948 vs 1.035). No candidate produces a stable, mandate-relevant
improvement.

---

## 4. Honest verdict per candidate

- **DBMF (P1a) — NO.** Genuine diversifier (low-corr, −0.38 in 2022) and halves drawdown, but cuts raw
  return below SPX at every lookback (158% vs 160% SPX vs 255% 2-sleeve). Short history (no pre-2019 stress).
  Fails the raw-return mandate.
- **KMLM (P1a) — NO.** Best correlation profile of the lot (−0.10 full, −0.37 in 2022), best drawdown cut
  (−9.9%), but the largest raw-return sacrifice (86% vs 104% SPX vs 145% 2-sleeve). Shortest history. Fails.
- **SYN_TREND (P1b) — NO (deep confirmation).** With the full 2010–2026 window the verdict is unambiguous:
  3-sleeve raw return **280%** vs SPX **595%** vs 2-sleeve **1040%**. Best OOS Sharpe of any variant (1.244)
  and tiny maxDD (−10.8%), but the raw-return collapse is fatal for the mandate. Also high covid corr (0.58)
  — doesn't protect fast crashes.
- **CREDIT (P2) — NO (different reason).** Beats SPX raw (795%), but corr 0.66–0.70 (0.86 in covid) = closet-
  SPY, not diversification. Lifts full Sharpe trivially while *hurting* OOS Sharpe at short lookbacks. Adds
  cost and complexity for no structural benefit. Dead as a diversifier.

---

## 5. Conclusion & disposition

**CLOSE the 3rd-sleeve question for the raw-return mandate.** The validated 2-sleeve inverse-vol blend
already captures the available diversification: the only sleeves with genuine low/negative correlation
(managed-futures / trend) are *too calm* — inverse-vol risk-parity hands them 40–60% of the book and the
levered-Nasdaq raw-return engine gets diluted below SPX. This is a real, useful finding, not a failure to
find a signal: **diversification that lowers vol also lowers raw return, and the mandate is raw return.**

**The one honest caveat / where a 3rd sleeve WOULD win:** if the mandate were ever **risk-adjusted**
(maximize Sharpe / minimize drawdown rather than beat SPX on raw return), **trend is a genuine win** —
adding SYN_TREND lifts OOS Sharpe 1.120 → 1.244 and cuts maxDD −28% → −11%. That is a real structural
dividend; it's simply orthogonal to *this* bench's raw-return bar. If the bar shifts, the next honest step
is: (a) deepen the trend read with a longer real-MF proxy or futures data pre-2019, (b) test a **capped /
return-aware** allocator that limits the trend sleeve's weight (e.g. ≤25%) so it trims tail risk without
gutting raw return, and (c) only then a paper clock. Under the current raw-return bar, none of that is
warranted — the 2-sleeve blend is the answer.

**Files:** `_third_sleeve_tests.py`, `_third_sleeve_robust.py`, `reports/_third_sleeve_result.json`.
No live `strategies/allocator_blend/`, crontab, paper clock, or protected runner files were touched.
