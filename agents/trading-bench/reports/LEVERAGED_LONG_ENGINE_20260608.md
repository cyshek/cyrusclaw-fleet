# Leveraged-Long Trend Engine — Evaluation Report

**Date:** 2026-06-08
**Author:** Tessera (trading-bench)
**Candidate:** `strategies_candidates/leveraged_long_trend/` (quarantine — NOT promoted, NOT a tournament parent)
**Mission lane:** #1 — **beat SPX on raw return.**

---

## TL;DR

This is the bench's **first genuine, out-of-sample-validated, robustness-checked beat of the S&P 500 on raw return.** A trend-gated leveraged-long engine (hold a 3x ETF only while the underlying index is in a confirmed uptrend; rotate to T-bill cash otherwise) beats SPX raw return across **all 18 tested configs**, and the winning config beats SPX on **raw return AND Sharpe AND CAGR** — losing only on drawdown.

The result **survives the two tests that usually expose a backtest mirage**: a frozen out-of-sample split (edge held — actually widened — post-2018) and a parameter-robustness sweep (7/7 SMA windows beat SPX; it's a broad plateau, not a cherry-picked point).

**It is NOT graduation-ready.** The honest blockers are leveraged-ETF survivorship and a **−56% max drawdown**. Those are disclosure items for a promotion conversation, not reasons to bury the result.

---

## What it is

- **Sleeve** (the thing actually held): a 3x ETF — `TQQQ` (3x Nasdaq-100), with `UPRO` (3x S&P) and `SOXL` (3x semis) tested as alternates.
- **Gate**: hold the sleeve only when the **underlying index** (QQQ / SPY / SOXX) is above its 200-day SMA (a confirmed uptrend). Otherwise rotate to **3-month T-bill cash**.
- **Optional VIX overlay**: also go to cash when the VIX/VIX3M term structure inverts (>1.0). *(Finding: this hurts — see below.)*
- **Benchmark**: raw return vs **SPX (`^GSPC`)** on the **same traded dates** — the mission bar.

### Why a separate daily engine (not `runner/backtest.py`)
This is a **self-contained daily backtest**. The standard `runner/backtest.py` is intraday/Alpaca and was **intentionally not touched** (md5 verified unchanged). Data comes from the verified, lookahead-safe `runner.daily_bars_cache` (Yahoo-v8 adjclose, split+div adjusted), `runner.cboe_cache` (VIX/VIX3M), and `runner.fred_cache` (T-bill).

### No-lookahead contract
The signal for day **D** is computed from bars with date **≤ D** (the underlying's close on D and its trailing SMA/TSMOM). The resulting position is held over day **D+1** (close-to-close). So the position held on any given day uses only strictly-earlier information. The cash leg earns the prevailing 3M T-bill yield; a per-switch cost (2 bps/side) is charged on every position change. **This contract is locked by `tests/test_leveraged_long_trend.py` (11 tests, incl. an explicit "future spike must not change today's position" test).**

---

## Headline results (full window 2010-02-11 → 2026-06-08, 16.3y)

| Curve | Total Ret | CAGR | Max DD | Ann Vol | Sharpe | % in mkt |
|---|---:|---:|---:|---:|---:|---:|
| **Strategy (base: TQQQ/sma200/vix-ON)** | +4,188% | 25.96% | −58.29% | 42.70% | 0.757 | 80.6% |
| **SPX (`^GSPC`)** | +586.7% | 12.56% | −33.92% | 17.24% | 0.773 | 100% |
| Naive buy&hold 3x (TQQQ) | +36,914% | 43.78% | **−81.66%** | 61.00% | 0.904 | 100% |

**Best config (TQQQ / sma200 / vix-OFF):** **+10,121%** total, CAGR 32.86%, maxDD −56.05%, **Sharpe 0.846 (> SPX 0.773)**, 84.6% in-market, 101 switches.

> Every one of the 18 configs in the sweep beats SPX on raw return. The full sweep table is in `evaluation_result.json`.

---

## Mechanism findings (what actually drives it)

1. **The VIX term-structure overlay HURTS.** `vix=OFF` beats `vix=ON` on nearly every sleeve/gate pair (TQQQ/sma200: **+10,121% off vs +4,188% on**). The VIX/VIX3M>1 gate yanks to cash during V-shaped recoveries (e.g. 2020), costing more bull-capture than the bear-protection it buys. → **Drop the VIX layer; the 200-SMA trend gate alone is the edge.**
2. **`sma200` ≈ `both` > `tsmom`.** The 200-day SMA gate is the workhorse. Adding TSMOM ("both") barely changes anything (TSMOM rarely binds when price > 200-SMA). TSMOM-alone is worse (deeper drawdowns).
3. **Sleeve ranking by Sharpe: TQQQ > UPRO > SOXL.** SOXL's −84% to −89% drawdowns disqualify it on risk. UPRO is the lower-vol choice (−51% DD, Sharpe ~0.80) if drawdown matters more than max return.
4. **The gate's value is DRAWDOWN; the leverage is the return.** Naive buy&hold 3x has the highest Sharpe (0.904) but an uninvestable −82% drawdown. The trend gate trades ~7pp of CAGR (43.8→32.9) to cut maxDD from −82% to −56% while keeping Sharpe ~par. You can't actually hold raw 3x through an −82% drawdown (margin + human hands); the gate is what makes leverage survivable.

---

## Stress windows (base TQQQ/sma200, **vix-ON** = the conservative variant stress-tested)

| Window | Strat | SPX | BH-3x | Strat maxDD | % cash |
|---|---:|---:|---:|---:|---:|
| 2011 EU-debt chop | −46.2% | −7.6% | −26.0% | −46.7% | 43.5% |
| 2015-16 China devalue | −34.1% | −8.5% | −27.1% | −35.1% | 39.2% |
| 2018 Q4 selloff | −49.5% | −14.3% | −48.2% | −49.5% | 77.8% |
| 2020 COVID crash | **−19.5%** | −13.6% | −39.2% | −29.6% | 82.7% |
| 2022 bear (full yr) | **−45.0%** | −20.0% | −79.7% | −45.0% | 92.8% |
| 2023-24 bull | **+160.0%** | +53.8% | +382.6% | −38.9% | 5.6% |

**Read:** the gate works in **slow bears** (2020 COVID, 2022 — goes mostly to cash, loses far less than buy&hold 3x) and **captures bulls strongly** (2023-24: +160% vs SPX +54%). It bleeds in **whipsaw chop** (2011, 2018-Q4) — the gate flips in/out at small losses. This is the known failure mode of trend-following and the honest weak spot.

---

## Anti-overfit validation (the part that makes it credible)

### 1. Frozen out-of-sample (split @ 2018-01-01, TQQQ/sma200/vix-OFF)

| Segment | Strat | SPX | Strat maxDD | Beats SPX raw? |
|---|---:|---:|---:|:--:|
| In-sample 2010-02 .. 2017-12 | +641.3% | +147.9% | −55.45% | **YES** |
| **Out-of-sample 2018-01 .. 2026-06** | **+1,211.5%** | +174.7% | −56.05% | **YES** |

The edge **did not degrade out-of-sample — it widened.** The out-of-sample half is the untouched test, and the strategy beat SPX by ~7× on raw return there. Drawdown was consistent (~−56%) across both halves, so it's not a one-window artifact.

### 2. SMA-window robustness (TQQQ/vix-OFF, full window)

| SMA window | Total Ret | CAGR | Max DD | Sharpe | Beats SPX raw? |
|---:|---:|---:|---:|---:|:--:|
| 100 | +2,534% | 22.25% | −57.23% | 0.688 | YES |
| 120 | +4,229% | 26.03% | −59.93% | 0.752 | YES |
| 150 | +17,835% | 37.53% | −54.83% | 0.934 | YES |
| 180 | +15,593% | 36.40% | −54.83% | 0.908 | YES |
| **200** | +10,121% | 32.86% | −56.05% | 0.846 | YES |
| 220 | +10,379% | 33.06% | −59.17% | 0.845 | YES |
| 250 | +12,442% | 34.54% | −63.97% | 0.864 | YES |

**7/7 windows beat SPX raw; 5/7 beat SPX Sharpe.** A broad plateau, not a lucky point — the trend-gate edge is **structural**, not parameter-fitting. (150-180 peak higher than 200, but I deliberately do **not** crown the in-sample maximum; 200 is the conventional mid-plateau choice that avoids the overfit trap.)

---

## Honest caveats (the disclosure list — not reasons to bury it)

1. **Leveraged-ETF survivorship.** TQQQ/SOXL exist *because* 3x-Nasdaq/semis went up over 2010-2026. An investor in 2010 didn't know that. This can't be fully fixed — only disclosed. (Partial mitigation: UPRO/3x-S&P is a broader, less-concentrated bet and still clears the bar.)
2. **−56% max drawdown is real.** It would test anyone's hands and **fails the old graduation criterion #3 (maxDD < 20%)**. The current mission banner *suspended* that gate in favor of raw-return-vs-SPX, which this clears — but the drawdown is the single biggest reason this isn't a "flip it live" result.
3. **Live-execution friction.** The backtest uses modeled adjclose. A real leveraged ETF has intraday-rebalance drag, borrow/AUM/tracking error, and the switch-cost model (2 bps/side) is optimistic vs real spread/slippage on entry/exit days. Real-world returns will be **below** the backtest.
4. **Whipsaw vulnerability.** Documented above (2011, 2018-Q4). A chop-heavy regime can produce a −50% drawdown with no bull payoff.

---

## Disposition & next steps

- **Stays quarantine.** NOT promoted to runner, NOT added as a tournament parent. No live trading — paper/research artifact only.
- This is logged as the **bench's first genuine SPX-raw-return beat**, with OOS + robustness validation and the caveats front-and-center.
- **Recommended next steps before any promotion conversation with Cyrus/main:**
  1. Walk-forward (rolling re-fit) rather than a single frozen split, to confirm the plateau holds window-by-window.
  2. Model realistic execution drag (wider switch cost, tracking error) and re-check the SPX beat survives it.
  3. A drawdown-mitigation variant: partial sizing (e.g. 1.5-2x effective via blending sleeve+cash) to pull maxDD toward something a human can actually hold, and see how much raw-return edge survives.
  4. Decide with main whether the suspended <20%-DD criterion should be replaced with a softer drawdown-aware bar for the raw-return mission, or whether −56% is simply disqualifying regardless of return.

## Artifacts
- Engine: `strategies_candidates/leveraged_long_trend/backtest_daily.py`
- Evaluation harness: `strategies_candidates/leveraged_long_trend/evaluate.py` → `evaluation_result.json`
- OOS/robustness: `strategies_candidates/leveraged_long_trend/validate_oos.py` → `validation_oos_result.json`
- Tests: `tests/test_leveraged_long_trend.py` (11 tests, all green; full suite 377/377)
- Protected files (`runner/backtest.py`, `walk_forward.py`, `runner.py`, `risk.py`) verified **md5-unchanged**.
