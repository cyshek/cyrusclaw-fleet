# Inter-Strategy Correlation & Concentration Audit — 12 LIVE Paper Strategies
**Date:** 2026-06-22 · **Author:** quant-risk subagent (trading-bench) · **Window:** 2010-02-16 → 2026-06-18 (4,111 common trading days)

---

## TL;DR — VERDICT: the live book is severely CONCENTRATED, not diversified.

> **12 strategies ≈ 2.2 effective independent bets** (participation ratio of the correlation-matrix eigenvalues, full window). In a down-market (SPY<0 days) it only rises to **2.5** — diversification does **not** show up when you'd need it. The top eigenvalue alone is **7.86 of 12** (≈65% of all variance loads on a single "long US large-cap equity beta" factor).

**What this book actually is:** ~9 of the 12 strategies are minor variations of *the same long-equity-beta trade* (XLK ≈ QQQ ≈ TQQQ all move together). Stacking them is **phantom diversification / phantom leverage** — it looks like 12 independent edges but it's one directional bet sized up ~9×, plus two genuine diversifiers and one weak one.

**The only two real diversifiers in the entire book:**
| Strategy | Avg corr to rest (full) | Avg corr (downside) | Verdict |
|---|---|---|---|
| `rsi_oversold_spy [SPY]` | **+0.02** | **−0.06** | ✅ Genuinely orthogonal; goes *negative* in stress (mean-reversion dip-buyer). **The crown jewel of diversification.** |
| `macd_momentum_iwm [IWM]` | **+0.21** | **+0.16** | ✅ Weak but real diversifier (small-cap momentum, low beta to the QQQ/XLK cluster). |

Everything else sits at **+0.46 to +0.69** average pairwise correlation.

**Redundant near-duplicates (cull/downweight candidates):**
- The **3 XLK breakout variants** are effectively **1 strategy** (ρ = 0.93–1.00; `breakout_xlk` vs `breakout_xlk_regime` = **1.00**).
- The **3 QQQ SMA-crossover variants** are effectively **1 strategy** (ρ = 0.98–1.00; `sma_crossover_qqq` vs `sma_crossover_qqq_rth` = **exactly 1.00** — the RTH filter is a no-op at daily resolution).
- The **2 TQQQ vol-target strategies** are **1 strategy with a minor overlay** (ρ = 0.91); `allocator_blend` is 86% the same thing (ρ = 0.86 to leveraged_long_trend).

---

## 1. Method (and why it's honest)

**Why NOT trade-log correlation:** `tournament.db::trades` has only 2–5 fills per strategy over a few weeks with long flat gaps. A correlation from realized P&L on 3–5 trades is pure noise (the thin-sample mirage this bench explicitly avoids). **We do not do that.**

**What we did instead — backtested DAILY strategy-return series on a common window:**

- **9 single-symbol event strategies** → each strategy's *actual* `decide()` logic (unchanged) run through the existing `runner.backtest.backtest()` engine, fed **daily adjclose bars** (Yahoo v8, keyless, split/div-adjusted) shaped into the engine's `{t,o,h,l,c,v}` contract, `timeframe='1Day'` for correct annualization. Zero-cost model so the correlation reflects the **signal shape**, not friction noise. Running a strategy at daily resolution is the only way to get a long common window (intraday 1Hour bars don't reach 2010).
- **2 TQQQ continuous-weight vol-target strategies** (`leveraged_long_trend_paper`, `tqqq_cot_combo`) are **not** honestly reproducible through the event engine (it has no partial-trim-while-long primitive — `runner/backtest.py`'s own docstring says running them through it "would produce a meaningless number"). So we used their **validated daily-voltarget harness** (`run_backtest_voltarget`) equity → daily returns. For `tqqq_cot_combo` we layered the COT ES AM-net 0.5× bearish overlay on the VT weights by calling the **live strategy's own `_get_cot_scale()`** per date (faithful, same 3-day publication lag).
- **`allocator_blend`** → the **validated `invvol_63d` blend** daily equity via `_allocator_blend_tests.build_sleeves()` + `blend_portfolio()` — the exact decomposition the live paper tracker (`runner/allocator_paper_tracker.py`) reuses → daily returns.

**Engines imported READ-ONLY. No protected file modified** (verified by mtime: `runner/*.py`, all `strategies/*`, `GATE.md` retain pre-session timestamps).

### Sanity check (series are real, not garbage)
| Strategy | Our backtested series | Existing report | Match? |
|---|---|---|---|
| `leveraged_long_trend_paper` (VT sleeve) | Sharpe **0.863**, CAGR **20.8%**, maxDD **−34.5%** | VT Sharpe ~0.896, maxDD ~−35–42% (`LEVERAGED_*`) | ✅ |
| `allocator_blend` (invvol_63d) | Sharpe **1.006**, CAGR **16.1%**, maxDD **−28.0%** | Sharpe **1.014** full, maxDD **−23.9%** (`ALLOCATOR_BLEND_20260621.md`) | ✅ (within cost/window tol) |
| `tqqq_cot_combo` | COT overlay **active** (real ES AM-net signal, 0.5× on bearish weeks) | combo Sharpe ~0.96 vs VT ~0.90 (`TQQQ_COT_COMBO_20260614.md`) | ✅ overlay confirmed live |

### Per-strategy series diagnostics (full available history)
| # | Strategy | Symbol | Series n | Standalone Sharpe (daily-bar) | Notes |
|---|---|---|---|---|---|
| 1 | breakout_xlk | XLK | 6,914 | 0.479 | |
| 2 | breakout_xlk_regime | XLK | 6,914 | 0.469 | ρ=1.00 vs #1 |
| 3 | breakout_xlk__mut_c382b1 | XLK | 6,914 | 0.510 | regime-conditional stop |
| 4 | sma_crossover_qqq | QQQ | 6,862 | 0.514 | |
| 5 | sma_crossover_qqq_regime | QQQ | 6,862 | 0.532 | |
| 6 | sma_crossover_qqq_rth | QQQ | 6,862 | 0.514 | ρ=1.00 vs #4 (RTH gate = no-op on daily) |
| 7 | volume_breakout_qqq | QQQ | 6,862 | 0.164 | **\*PROXY** (see caveat) |
| 8 | leveraged_long_trend_paper | TQQQ | 4,113 | 0.863 | VT harness |
| 9 | tqqq_cot_combo | TQQQ | 4,113 | — | VT + COT overlay |
| 10 | rsi_oversold_spy | SPY | 8,404 | 0.271 | **diversifier** |
| 11 | macd_momentum_iwm | IWM | 6,553 | 0.027 | weak diversifier |
| 12 | allocator_blend | BLEND | 4,112 | 1.006 | blend harness |

Common window is bounded by **TQQQ inception (2010-02)** as predicted.

---

## 2. Full-window Pearson correlation matrix (4,111 days)

```
            1      2      3      4      5      6      7      8      9     10     11     12
 1 bre    1.00   1.00   0.95   0.84   0.84   0.84   0.57   0.69   0.68   0.01   0.22   0.66
 2 bre    1.00   1.00   0.95   0.84   0.85   0.84   0.58   0.70   0.68   0.01   0.22   0.66
 3 bre    0.95   0.95   1.00   0.82   0.83   0.82   0.60   0.68   0.66   0.01   0.22   0.63
 4 sma    0.84   0.84   0.82   1.00   0.99   1.00   0.58   0.76   0.74   0.02   0.23   0.70
 5 sma    0.84   0.85   0.83   0.99   1.00   0.99   0.59   0.76   0.75   0.02   0.24   0.70
 6 sma    0.84   0.84   0.82   1.00   0.99   1.00   0.58   0.76   0.74   0.02   0.23   0.70
 7 vol    0.57   0.58   0.60   0.58   0.59   0.58   1.00   0.51   0.50  -0.00   0.24   0.46
 8 lev    0.69   0.70   0.68   0.76   0.76   0.76   0.51   1.00   0.91   0.07   0.24   0.86
 9 tqq    0.68   0.68   0.66   0.74   0.75   0.74   0.50   0.91   1.00   0.04   0.23   0.79
10 rsi    0.01   0.01   0.01   0.02   0.02   0.02  -0.00   0.07   0.04   1.00  -0.00   0.06
11 mac    0.22   0.22   0.22   0.23   0.24   0.23   0.24   0.24   0.23  -0.00   1.00   0.23
12 all    0.66   0.66   0.63   0.70   0.70   0.70   0.46   0.86   0.79   0.06   0.23   1.00
```
Legend: 1–3 = breakout_xlk{,_regime,_mut}; 4–6 = sma_crossover_qqq{,_regime,_rth}; 7 = volume_breakout_qqq; 8 = leveraged_long_trend_paper; 9 = tqqq_cot_combo; 10 = rsi_oversold_spy; 11 = macd_momentum_iwm; 12 = allocator_blend.

## 3. Downside-day correlation matrix (1,821 days, SPY return < 0 = 44.3% of days)

```
            1      2      3      4      5      6      7      8      9     10     11     12
 1 bre    1.00   1.00   0.93   0.79   0.80   0.79   0.55   0.62   0.58  -0.09   0.18   0.56
 2 bre    1.00   1.00   0.93   0.79   0.81   0.79   0.56   0.62   0.59  -0.09   0.18   0.56
 3 bre    0.93   0.93   1.00   0.75   0.76   0.75   0.59   0.59   0.55  -0.08   0.20   0.54
 4 sma    0.79   0.79   0.75   1.00   0.98   1.00   0.54   0.67   0.64  -0.06   0.17   0.60
 5 sma    0.80   0.81   0.76   0.98   1.00   0.98   0.55   0.68   0.65  -0.06   0.18   0.61
 6 sma    0.79   0.79   0.75   1.00   0.98   1.00   0.54   0.67   0.64  -0.06   0.17   0.60
 7 vol    0.55   0.56   0.59   0.54   0.55   0.54   1.00   0.46   0.40  -0.06   0.24   0.39
 8 lev    0.62   0.62   0.59   0.67   0.68   0.67   0.46   1.00   0.85  -0.00   0.18   0.80
 9 tqq    0.58   0.59   0.55   0.64   0.65   0.64   0.40   0.85   1.00  -0.06   0.14   0.70
10 rsi   -0.09  -0.09  -0.08  -0.06  -0.06  -0.06  -0.06  -0.00  -0.06   1.00  -0.04  -0.05
11 mac    0.18   0.18   0.20   0.17   0.18   0.17   0.24   0.18   0.14  -0.04   1.00   0.17
12 all    0.56   0.56   0.54   0.60   0.61   0.60   0.39   0.80   0.70  -0.05   0.17   1.00
```

**Stress read:** within the big equity cluster, downside correlations stay **0.75–1.00**. They soften only modestly vs the full window, and the cross-cluster (XLK↔TQQQ) pairs *drop a bit* (0.69→0.62) but remain high. **Diversification does not appear in the drawdown** — this is a directional long-beta book that will draw down together. The one bright spot: `rsi_oversold_spy` flips slightly **negative** to the whole book in down-tape (−0.05 to −0.09), confirming it's a real hedge-flavored sleeve.

---

## 4. Hierarchical clustering (correlation distance, average linkage)

Merge order (higher corr = tighter / merged earlier):

```
corr +1.000   sma_crossover_qqq  +  sma_crossover_qqq_rth          ── QQQ-trend
corr +0.995   breakout_xlk       +  breakout_xlk_regime            ── XLK-breakout
corr +0.989   sma_crossover_qqq_regime  +  {qqq-trend pair}        ── QQQ-trend (3)
corr +0.948   breakout_xlk__mut_c382b1  +  {xlk pair}              ── XLK-breakout (3)
corr +0.909   leveraged_long_trend_paper + tqqq_cot_combo          ── TQQQ-voltarget
corr +0.835   {XLK cluster}  +  {QQQ cluster}                      ── equity-beta core
corr +0.830   allocator_blend  +  {TQQQ cluster}                   ── joins TQQQ
corr +0.703   {XLK+QQQ}  +  {TQQQ+allocator}                       ── ONE equity macro-cluster (9 strats)
corr +0.552   volume_breakout_qqq  joins the macro-cluster
corr +0.231   macd_momentum_iwm    joins (weak)
corr +0.023   rsi_oversold_spy     joins LAST (the outlier / true diversifier)
```

### The clusters, plainly:
- **Cluster A — XLK breakout (3):** `breakout_xlk`, `breakout_xlk_regime`, `breakout_xlk__mut_c382b1` → **1 effective strategy.**
- **Cluster B — QQQ trend (3):** `sma_crossover_qqq`, `sma_crossover_qqq_regime`, `sma_crossover_qqq_rth` → **1 effective strategy.**
- **Cluster C — TQQQ vol-target + allocator (3):** `leveraged_long_trend_paper`, `tqqq_cot_combo`, `allocator_blend` → **~1.2 effective strategies** (allocator adds a little via its GLD/TLT/SPY rotation sleeve, but it's 86% TQQQ-driven).
- **A+B+C are one macro-cluster** (they all merge by ρ=0.70) = **the long-equity-beta bet.**
- **Loosely attached:** `volume_breakout_qqq` (ρ≈0.55 — same QQQ direction, choppier signal).
- **Genuine diversifiers (join last):** `macd_momentum_iwm` (ρ≈0.23) and `rsi_oversold_spy` (ρ≈0.02, the true outlier).

---

## 5. Effective number of independent bets

Participation ratio `PR = (Σλ)² / Σλ²` over the correlation-matrix eigenvalues:

| Measure | Value (of 12) |
|---|---|
| **Effective N bets — full window** | **2.22** |
| **Effective N bets — downside days** | **2.53** |
| Largest eigenvalue (full) | **7.86** (≈65% of total variance on one factor) |
| Top-6 eigenvalues (full) | 7.86, 1.03, 0.94, 0.81, 0.57, 0.42 |

**Interpretation:** one dominant factor (long equity beta) + essentially two satellites (`rsi_oversold_spy`, `macd_momentum_iwm`). **12 named strategies deliver the diversification of ~2.2 independent bets.** The book has roughly **5–6× phantom redundancy** in its risk budget.

---

## 6. Recommendation — what a risk officer would do

**The problem:** if every sleeve gets equal capital, ~75% of the book's capital is funding 3 copies of QQQ-trend + 3 copies of XLK-breakout + 3 copies of TQQQ-long. That's not 9 edges; it's **one leveraged long-equity position wearing 9 nametags.** When the equity factor draws down (2018-Q4, 2020-Q1, 2022), all of them lose together (downside ρ 0.75–1.00).

**Concrete actions:**

1. **Collapse the XLK cluster to 1.** Keep **`breakout_xlk__mut_c382b1`** (best standalone Sharpe 0.510, has the regime-conditional stop = best drawdown behavior). **Downweight or retire** `breakout_xlk` and `breakout_xlk_regime` (ρ=1.00 with each other and 0.95 with the mutant — they add zero diversification).

2. **Collapse the QQQ-trend cluster to 1.** Keep **`sma_crossover_qqq_regime`** (marginally best Sharpe 0.532). **Retire `sma_crossover_qqq_rth`** outright — it is *byte-for-byte identical in behavior* to `sma_crossover_qqq` at daily resolution (ρ = exactly 1.00; the RTH gate only matters intraday). Downweight `sma_crossover_qqq`. *(Caveat: on the live 1Hour clock the RTH variant does differ slightly — but it's still ~0.99 corr; it does not earn a full independent capital slot.)*

3. **Treat the TQQQ cluster as ONE sleeve.** `leveraged_long_trend_paper` and `tqqq_cot_combo` are ρ=0.91 — keep **`tqqq_cot_combo`** (the COT overlay genuinely reduces 2022 drawdown per its report; it's the better of the two) and run the plain VT sleeve only as the allocator's internal component, not as a separate top-level book entry. **`allocator_blend` already contains a TQQQ vol-target sleeve** (ρ=0.86 to it) — running allocator_blend *and* the two standalone TQQQ strategies triple-counts the same TQQQ exposure. Pick the allocator (it at least adds GLD/TLT/SPY rotation) **or** the standalones, not both at full weight.

4. **Protect and *overweight* the two real diversifiers.** `rsi_oversold_spy` (ρ≈0.02, negative in stress) and `macd_momentum_iwm` (ρ≈0.21) are the *only* things making this book less than a pure beta bet. In a risk-parity / equal-risk-contribution framing they deserve **more** capital than any single member of the equity cluster, not equal-or-less. `rsi_oversold_spy` in particular is the closest thing to a hedge in the book.

5. **For the Saturday leaderboard:** keep all 12 visible for the *tournament/competition* (they're distinct code & distinct live fills — fine to score individually). But the **capital-allocation / "is the book diversified" view must be cluster-aware**: report the book as **~2.2 effective bets** and weight by *cluster*, not by *strategy count*. A naive "12 strategies, equal weight" allocation is ~9× long-equity-beta with a thin diversifier tail.

**Suggested cluster weights (illustrative ERC-style):** Equity-trend macro-cluster ≤ ~50% total (split across 1 XLK + 1 QQQ + 1 TQQQ/allocator representative), `rsi_oversold_spy` ~20–25%, `macd_momentum_iwm` ~15–20%, `volume_breakout_qqq` small. That would lift effective bets from 2.2 toward ~3.5–4 without adding a single new strategy — just by not paying 9× for one factor.

---

## 7. Honest caveats

- **Backtested-return correlation ≠ live correlation.** These are daily-resolution backtests over 2010–2026; the live strategies trade a 1Hour clock with $100 notional and only a few fills so far. The *structure* (which strategies are near-duplicates) is robust and will hold live; the *exact* coefficients will differ.
- **Regime variants share a parent**, so high correlation between `X` and `X_regime` is *expected by construction* — that's the point: it confirms the regime filter rarely changes the position enough to add a meaningfully independent return stream (ρ stays 0.99–1.00). It is not a bug; it's evidence they don't deserve separate capital.
- **`sma_crossover_qqq_rth` ρ=1.00** is a *daily-resolution artifact* — its only difference from the parent is an intraday time-of-day entry gate that cannot bind on daily bars. On the live 1Hour clock it does diverge marginally, but nowhere near enough to be an independent bet. (We stamped daily bars at 15:00 UTC so the gate is a transparent no-op; documented.)
- **`volume_breakout_qqq` is a PROXY (\*).** Its native 3×-volume entry gate fires **0 times** on daily QQQ bars (it's calibrated for spikier 1Hour volume), producing a flat, uncorrelatable series. To extract a representative *signal shape* we relaxed the volume multiple to 1.0× ("price breakout confirmed by ≥-average volume"). Its real daily-native behavior is "rarely trades"; its proxy correlation (~0.55 to the QQQ cluster) is an upper bound on how QQQ-like it is. Treat its row as indicative, not exact.
- **The two TQQQ strategies and the allocator use their validated daily harnesses**, not the event engine, by necessity (the event engine cannot represent continuous-weight rebalancing). Their return series are the *validated* ones already vetted in prior reports, so they're the most trustworthy series in the set.
- **COT overlay** for `tqqq_cot_combo` was applied via the live strategy's own `_get_cot_scale()` (real ES AM-net WoW signal with 3-day publication lag) — faithful, not a re-implementation.

---
*Artifacts: full numeric matrices + eigenvalues + merge log in `reports/_interstrategy_corr_matrix.json`. Scratch generator: `_xstrat_corr.py` (workspace root). No protected file modified (mtime-verified).*
