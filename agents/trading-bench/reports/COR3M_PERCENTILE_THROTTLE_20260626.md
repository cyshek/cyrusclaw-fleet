# COR3M PERCENTILE THROTTLE — PROBE VERDICT: 🔴 RED (CLOSE)

**Date:** 2026-06-26
**Analyst:** Tessera (trading-bench)
**Assignment:** main cron — probe backlog "BUILD NEXT" item: COR3M 3M-implied-correlation rolling 2–3yr level-percentile as a slow equity risk-on/off throttle.
**Scratch:** `reports/_cor3m_pct_throttle_probe.py`, `reports/_cor3m_pct_throttle_results.json`
**Protected files touched:** NONE (probe-only; no runner/strategy/risk/GATE/crontab/config modified).

---

## TL;DR

**RED. Close the lane.** The COR3M rolling-percentile equity throttle fails on every honest axis, and — critically — it is **wrong-signed**, exactly as my own 2026-06-24 raw-level probe (`_disp_ortho_probe.py`) found. Re-normalizing the level into a trailing 2–3yr percentile does **not** rescue the signal; it reproduces the same backwards forward-return sort and adds whipsaw turnover.

The backlog hypothesis was: *LOW percentile = risk-on (hold), HIGH percentile = de-risk (cash), ~0.05–0.1 turns/yr, orthogonal to 12-1 trend.* Every one of those four claims is falsified by the data:

| Backlog claim | Result | Verdict |
|---|---|---|
| LOW corr = risk-on (de-risk on HIGH) | Forward returns are **highest** at HIGH corr (buy-the-fear) | ❌ wrong-signed |
| Improves the equity book | **No config beats SPY on both OOS Sharpe AND OOS CAGR** | ❌ |
| ~0.05–0.1 turns/yr (slow) | Actual **6–20 one-way turns/yr** (percentile whipsaws) | ❌ |
| Orthogonal to 12-1 trend (corr < 0.3) | Best configs **corr 0.74–0.98 to SPY** (closet beta) | ❌ |

---

## Method (honesty rails)

- **Data.** COR3M close from `data_cache/cboe/COR3M_History.csv` (CBOE CDN, 2006-01-03 → 2026-06-23, 5,135 rows, **spans 2008**). SPY adjusted close from Yahoo v8 chart API (split+div adjusted). Common grid: **5,134 days, 2006-01-03 → 2026-06-23**.
- **Signal.** Rolling percentile rank of COR3M close within the trailing window ending at day *t* (strictly backward-looking). Tested **3yr (756d)** and **2yr (504d)** windows.
- **D+1 lag.** Signal computed from `close[t]` decides exposure applied to `return[t+1]` (trade next bar). No same-bar lookahead. (Confirmed: percentile uses only `series[i-win+1 .. i]`.)
- **Sharpe.** Continuous-span, daily log returns, ×√252. Same convention as `runner/fp_sharpe`.
- **IS/OOS split.** Pre-committed calendar split at **2018-01-01** (IS 3,009d / OOS 2,125d).
- **Benchmark.** SPY buy&hold on the **identical** day grid (same-path).
- **Cost.** 2 bps one-way (`CostModel.alpaca_stocks`) charged on every change in exposure weight.
- **Cash leg.** Earns **0%** (conservative floor; a real T-bill leg would only *help* the throttle, and still doesn't clear the bar).

---

## Result 1 — The forward-return sort is BACKWARDS (the killer)

Forward-21d SPY return (annualized) bucketed by COR3M percentile quintile, D+1 honest entry:

**3yr (756d) window:**

- Q0 (lowest implied corr): **+8.9%**
- Q1: +4.1%
- Q2: +7.6%
- Q3: +17.9%
- Q4 (highest implied corr): **+37.5%**

**2yr (504d) window:**

- Q0 (lowest): **+7.6%** → Q1 +3.7% → Q2 +3.8% → Q3 +13.4% → Q4 (highest): **+26.6%**

The relationship is **monotone increasing** in implied correlation. High implied correlation clusters near panic bottoms (2009, 2011, 2020-03, 2022) where forward equity returns are *strongest* — the classic "buy the fear" pattern. The backlog's premise (high corr → de-risk) is precisely inverted. This is the same result my raw-level quintile sort produced on 2026-06-24 (Q5 high-corr = +26.7% fwd vs Q1 +10.6%); the percentile transform does not change the sign.

---

## Result 2 — No throttle beats SPY on the real bar

**SPY buy&hold (common grid):** full Sharpe 0.546 / CAGR 11.0%; **OOS Sharpe 0.703 / CAGR 14.5% / total +213% / maxDD −33.7%**.

Across **16 throttle configs** (2 windows × {binary thr 0.5/0.8/0.9, banded-3} × {lowON, highON}):

> **ZERO configs beat SPY on BOTH OOS Sharpe AND OOS CAGR.**

The only two cells that edge SPY's OOS Sharpe at all:

| Config | OOS Sharpe | OOS CAGR | corr→SPY | turns/yr |
|---|---|---|---|---|
| SPY buy&hold | 0.703 | **14.5%** | 1.00 | 0 |
| binary 3yr lowON thr0.9 | 0.736 | 12.4% | 0.80 | 6.0 |
| binary 2yr lowON thr0.9 | 0.763 | 11.4% | 0.74 | 10.7 |

Both "win" Sharpe only by sitting in cash ~90% of the time (thr0.9 = long only in the bottom-decile percentile), sacrificing **2–3 points of CAGR** to cash-drag. A +0.03–0.06 OOS Sharpe bump on ~2,100 days is **inside the noise band**, bought with materially lower compounding — not an edge, and not a reason to add complexity over plain SPY (or over the existing TQQQ-vol-target / sector-rotation sleeves that already beat SPX raw).

The `highON` (inverse / buy-the-fear) direction produces higher raw return (because it's long SPY most of the time) but **fails orthogonality outright** (corr 0.87–0.98) and still doesn't beat SPY OOS Sharpe — it's just leveraged closet beta with extra cost.

---

## Result 3 — Orthogonality claim fails

A binary risk-on/off **equity** gate is, by construction, SPY-when-on and flat-when-off. The best configs show **corr 0.74–0.98 to SPY daily returns**. The backlog predicted "orthogonal to 12-1 trend (corr < 0.3)" — but an instrument that is long SPY 74–98% of the time is **closet beta to any long-equity sleeve** (12-1 trend, vol-target TQQQ, sector rotation all load on equity beta in risk-on regimes). It cannot serve as a <0.3 orthogonal diversifier. The genuinely orthogonal dispersion expression is the **implied−realized correlation SPREAD**, which I already probed and closed RED on 2026-06-25 (`CORR_RISK_PREMIUM_PROBE_20260625.md`: passes orthogonality, zero forward-return content).

---

## Result 4 — Turnover prediction was wrong

Predicted ~0.05–0.1 round-trips/yr. **Actual: 6–20 one-way turns/yr** (≈3–10 round-trips/yr). The percentile crosses its threshold far more often than the raw level crosses its median, because de-trending amplifies sensitivity near the boundary. Cost is *not* the binding constraint here (the signal is dead regardless), but the "slow, low-turnover" framing is also false.

---

## Why this was worth running anyway

My 2026-06-24 falsification was on the **raw level**; the assignment correctly flagged that **percentile re-normalization is a different transform** (it strips COR3M's slow secular drift). It was a legitimate distinct test, not a re-run — the percentile could in principle have separated forward returns where the level didn't. It doesn't: the sort is backwards in *both* representations, which is stronger evidence that the mechanism itself (low implied corr → future equity strength) does not exist. Buy-the-fear dominates.

---

## Disposition

- **Verdict: 🔴 RED — CLOSE.** Do not pitch the COR3M (or COR1M/COR30D) implied-correlation **level/percentile** as an equity risk-on/off throttle again. Both representations (level, percentile) and the orthogonal expression (implied−realized spread) are now closed.
- **Dispersion-class equity-throttle is fully exhausted** on free data: level (2026-06-24), percentile (this report), spread (2026-06-25 `CORR_RISK_PREMIUM_PROBE`).
- **Binding constraint reaffirmed:** the defect is the *mechanism/sign*, not data quality — COR3M is survivorship-immune (single index time-series), 2006+, 2008-spanning, clean.
- **Reusable artifact:** `reports/_cor3m_pct_throttle_probe.py` is a generic D+1-honest, IS/OOS, cost-aware single-instrument **on/off-throttle backtester** — reusable for any future "level/percentile gate on the equity book" idea (drop-in a different CSV).
- **Revisit trigger (low priority):** only if a *cross-sectional* dispersion use (single-name dispersion as a stock-selection signal, not an index throttle) is ever stood up on a survivorship-clean universe — that is a different construct from anything closed here.

---

*No trades placed. No protected file modified. Probe + report only.*
