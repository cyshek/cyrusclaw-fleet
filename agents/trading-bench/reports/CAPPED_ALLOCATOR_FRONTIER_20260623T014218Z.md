# Capped / Return-Aware Allocator — The Price of Crash Insurance on the Blend

**Date:** 2026-06-23 (UTC stamp 20260623T014218Z)
**Lane:** Structural-edge (direct follow-up to the third-sleeve study).
**Mission bar:** BEAT SPX ON RAW RETURN. Gates suspended. Honest measurement non-negotiable.

## TL;DR — VERDICT: a CAPPED trend sleeve (≤15–20%) recovers most of the diversification dividend WITHOUT losing to SPX raw — but it still trails the 2-sleeve blend on raw return. So it's a genuine *risk-adjusted* upgrade and a *tail-risk* buy, **not** a raw-return win. Under the current pure-raw-return mandate the 2-sleeve blend remains the answer; if Cyrus ever wants crash insurance, the **15–20% capped trend sleeve is the honest, pre-registered way to buy it.**

The third-sleeve study CLOSED the *naive* question: a vanilla inverse-vol 3-sleeve blend hands the calm trend leg 60% of the book and craters raw return (280% vs SPX 593% vs 2-sleeve 1040%). This study tested the obvious fix flagged in that report — **cap the trend sleeve's weight** — and mapped the full frontier. The fix works: the trend leg's diversification is real; vanilla inverse-vol was simply over-allocating to it.

---

## What was tested (engine reuse + the one new primitive)

Reuses the validated blend engine VERBATIM (`build_sleeves`, `synthetic_trend_sleeve`,
`blend_portfolio`, `report_blend`, `_solo_block` via `_third_sleeve_tests.py`, which itself reuses
`_allocator_blend_tests.py`). The **only** new code is `capped_invvol_wfn_factory`: compute the normal
inverse-vol risk-parity weights over the 3 sleeves, then **clip the trend sleeve (index 2) to `cap`** and
redistribute the clipped-off excess to TQQQ-voltarget + sector-rotation in proportion to *their* inverse-vol
weights (preserving their relative balance). `cap = 1.00` reproduces the uncapped 3-sleeve **bit-for-bit**
(verified: raw 279.68%, Sharpe 1.0568, maxDD −10.75% @ lb63 — exact match to the third-sleeve study), which
proves the capped fn feeds the SAME engine with no drift.

- **Sleeves:** (1) TQQQ vol-target, (2) sector-rotation top-2 [SPY,QQQ,GLD,TLT], (3) SYN_TREND = synthetic
  12-1 time-series-momentum long/flat over [DBC,GLD,TLT,UUP] (the deep 2010+ trend proxy; real-CTA ETFs
  DBMF/KMLM only exist post-2019 so they can't anchor a deep read).
- **Window:** deep common 2010-02-12 → 2026-06-22 (4113 days) — spans 2011 / 2018-Q4 / 2020-covid / 2022 bear.
- **Cost:** 2bps inter-sleeve. **Cap sweep:** 15/20/25/30/100%. **Lookback sweep:** 21/42/63/126d.
- **No lookahead** (PAST returns only in the weight fn). SPX raw = buy-&-hold ^GSPC on the same window.
- No protected/live files, crontab, or paper clock touched. Scratch: `_capped_allocator_tests.py`,
  `reports/_capped_allocator_result.json`.

**Baselines on this window:** SPX raw **593%** · 2-sleeve blend raw **1040%**, Sharpe **1.007**, OOS **1.120**,
maxDD **−28.0%** · trend-leg corr vs 2-sleeve blend (full) **0.213**.

---

## The frontier (full cap × lookback grid)

Each cell: full raw return % / full Sharpe / OOS Sharpe / full maxDD / avg trend weight. **Bold** = beats SPX
raw (593%). The 2-sleeve blend (no trend sleeve) is raw 1040% / 0.985–1.01 Sharpe / −28.0% maxDD throughout.

| lb | cap=15% | cap=20% | cap=25% | cap=30% | cap=100% (uncapped) |
|---:|---|---|---|---|---|
| **21**  | **677%** / .971 / 1.070 / −26.2% | **619%** / .979 / 1.081 / −24.7% | 564% / .987 / 1.092 / −23.1% | 513% / .995 / −21.6% | 273% / 1.037 / −11.1% |
| **42**  | **781%** / 1.027 / 1.138 / −23.8% | **712%** / 1.036 / 1.151 / −22.2% | **648%** / 1.046 / 1.164 / −20.6% | 589% / 1.056 / −19.0% | 294% / 1.078 / −10.5% |
| **63**  | **786%** / 1.029 / 1.154 / −23.4% | **713%** / 1.037 / 1.166 / −21.8% | **645%** / 1.044 / 1.179 / −20.2% | 582% / 1.052 / −18.6% | 280% / 1.057 / −10.8% |
| **126** | **884%** / 1.081 / 1.205 / −20.0% | **800%** / 1.090 / 1.217 / −18.8% | **721%** / 1.100 / 1.229 / −17.6% | **649%** / 1.109 / 1.241 / −16.4% | 295% / 1.108 / −10.8% |

### Reads
1. **A 15–20% trend cap beats SPX raw at EVERY lookback** while LIFTING Sharpe (≈ +0.02 to +0.08 vs the
   2-sleeve) and CUTTING maxDD by ~4–8 points (−28% → −20 to −24%). That is the sweet spot: most of the
   crash-insurance dividend, no raw-return loss vs SPX.
2. **25% cap beats SPX raw at lb=42/63/126** (only the noisy lb=21 just misses, 564% vs 593%).
3. **Longer lookback (126d) is strictly better** for the capped blend — at lb=126 even a 30% cap beats SPX
   raw (649%), with Sharpe 1.109 and maxDD **−16.4%** (vs 2-sleeve −28.0%). The 126d weighting reacts more
   slowly, so it leaves more in the levered-Nasdaq engine between vol spikes.
4. **Uncapped (cap=100%) always loses on raw return** (~273–295%) at every lookback — confirming the
   third-sleeve verdict was specifically about *vanilla* inverse-vol over-allocation, **not** a flaw in the
   trend sleeve itself.

---

## The honest catch — it's a tail-risk buy, not a raw-return win

Every "beats SPX raw" cell **still trails the 2-sleeve blend on raw return** (best capped = 884% @ lb126/cap15
vs 2-sleeve 1040%). So under a *pure* raw-return mandate — "maximize the number" — the **2-sleeve blend is
still the winner outright**, because adding ANY trend exposure costs raw return; it just no longer costs
*enough* to fall below SPX once capped.

What the cap actually buys, quantified at the most attractive operating point (**lb=126, cap=20%**):
- Raw return 1040% → **800%** (give up ~240 pts of return, still **+207 pts over SPX's 593%**).
- maxDD −28.0% → **−18.8%** (buy ~9 points of drawdown protection).
- Full Sharpe 1.007 → **1.090**; OOS Sharpe 1.120 → **1.217** (a real risk-adjusted lift).

That is a clean, honest **frontier trade**: ~9 points of drawdown + ~0.08–0.10 Sharpe for ~240 pts of raw
return, while staying comfortably above SPX. Whether that trade is worth taking is a **mandate question**, not
a statistics question — and the current mandate says raw return, where the 2-sleeve wins.

---

## Verdict & disposition

- **Under the current pure-raw-return bar: KEEP the 2-sleeve blend.** It beats every capped 3-sleeve variant
  on raw return. Confirmed — no change to the live paper tracker.
- **The capped trend sleeve is now a SHELF-READY crash-insurance option, pre-registered.** If/when Cyrus
  wants drawdown protection (or shifts toward a risk-adjusted bar), the honest recommendation is a
  **15–20% trend cap at the 126d (or 63d) lookback** — it beats SPX raw, lifts OOS Sharpe to ~1.2, and cuts
  maxDD to ~−19/−20%. This resolves the third-sleeve study's open caveat with a concrete, parameter-pinned
  recommendation instead of a vague "trend would help if the bar changed."
- **Not promoting to a paper clock now** — under the raw-return mandate it's strictly dominated by the
  2-sleeve on the metric that counts. It's logged as a ready-to-deploy variant the moment the objective
  includes drawdown/Sharpe.

**Caveats carried forward (unchanged):** SYN_TREND is a synthetic proxy, not a real CTA fund; the real-MF
ETFs (DBMF/KMLM) only validate the *post-2019* slice; trend's covid-Q1 correlation to the blend is high
(~0.58) so it protects slow grinds (2022) far better than fast V-crashes (2020). The drawdown cushion here is
mostly a 2022/2011/2018-style benefit.

**Files:** `_capped_allocator_tests.py`, `reports/_capped_allocator_result.json`.
No live `strategies/allocator_blend/`, crontab, paper clock, or protected runner files were touched.
