# Vol-Target Sleeve on Leveraged-Trend — VERDICT

**Date:** 2026-06-13
**Author:** Tessera (trading-bench)
**Status:** ✅ Experiment complete. The drawdown problem on the leveraged-trend lead is **solved for TQQQ, net of realistic costs, out-of-sample.** Narrowly — see caveats.
**Reproduced live:** `python3 -m strategies_candidates.leveraged_long_trend.recost_voltarget` (EXIT 0, 2026-06-13). Numbers below are from the live re-run, not stale JSON.

---

## Context — why this experiment

The leveraged-trend lead (TQQQ behind an SMA-200 gate, VIX-off, T-bill cash) was the project's first and only clear "beat SPX on raw return" result (+10,121% vs +587% full-history, OOS-validated). But it was **uninvestable as-is**: −56% max drawdown, pure leverage premium, not risk-adjusted alpha. Three independent research threads (our own 19-day record, the failed bot-builders in the YouTube sprint, and Umar Ashraf's own account of where his edge lives) all converged on the same prescription: **the missing piece is not another entry signal — it's the risk/sizing layer.** This experiment builds that layer.

A first-pass vol-target sleeve already existed from 2026-06-09 but was never finished into a verdict. This report completes it, after verifying lookahead-safety and reproducing the numbers live.

## What the sleeve does

Instead of holding 100% TQQQ whenever QQQ is above its 200d SMA (the binary baseline), scale the sleeve weight **inversely to recent realized volatility** to target a fixed annualized vol:

> weight(D+1) = clamp( target_vol / realized_vol(sleeve returns through D), 0, 1.0 ), but **0 if QQQ ≤ its 200d SMA** (gate still binds).

- `realized_vol` = annualized stdev of the sleeve's trailing 20-day daily returns, **using only returns ending on/before D** (verified lookahead-safe in `backtest_daily_voltarget.py`: "a return that ends after D+1 cannot change today's weight").
- Weight capped at 1.0 (**no leverage added** beyond the ETF's own 3x — the no-leverage rail holds).
- Costs charged on **abs change in weight** (conservative; continuous sizing rebalances most days), applied identically to baseline and sleeve so the comparison is fair. Includes ETF expense ratios + bid/ask spreads, swept across cost levels.

## Result — TQQQ sleeve (the winner)

Full history 2010→2026, **net of realistic costs** (0.84% ER + ~2bps/side spread):

| Metric | Raw lead (no sleeve) | **TQQQ vol-target sleeve** | SPX |
|---|---|---|---|
| Total return | +10,121% | **+1,881%** | +587% |
| CAGR | 32.9% | **20.1%** | 12.6% |
| Max drawdown | **−56%** (uninvestable) | **−34.8%** | −33.9% |
| Sharpe | 0.846 | **0.842** | 0.773 |

- **The drawdown is now ≈ SPX's** (−34.8% vs −33.9%) — down from the raw −56%. That was the whole point, and it works.
- **Still beats SPX on raw return** (+1,881% vs +587%) **and** on Sharpe (0.842 vs 0.773).
- **Out-of-sample (frozen split 2018-01-01):** +354% vs SPX +175% net — margin **+179pp**, beats.
- **Cost-robust:** beats SPX OOS at every cost level tested — **+170pp at "realistic," +155pp even at "pessimistic"** costs. Not a thin/optimistic-only edge.

## Honest caveats (this is narrower than "leverage sizing works")

1. **The edge is TQQQ-specific, not a universal leverage-sizing law.** The same sleeve on **UPRO and SPXL (3x S&P)** beats SPX only at *optimistic* cost and **flips negative at realistic cost** (UPRO −6.8pp, SPXL −5.8pp OOS). So the sleeve rides on **QQQ's (Nasdaq-100) trend/vol character**, not on "lever any index." Do not generalize.
2. **Still a leverage premium, now risk-managed — not pure alpha.** The Sharpe edge over SPX is real but modest (0.842 vs 0.773); most of the outperformance is still levered beta, now with the tail compressed. That's a legitimate, holdable thing — but call it what it is.
3. **Single underlying, single regime-gate.** One instrument (TQQQ/QQQ), one gate (SMA-200). Robustness across sma-windows was shown earlier (7/7 beat SPX raw); robustness across *underlyings* just failed (only QQQ survives costs). A one-instrument result deserves continued paper validation before real money.
4. **SOXL excluded** — −84% to −89% drawdown even with the gate; uninvestable, correctly dropped.

## Verdict

**The experiment passed its go/no-go: vol-targeting compresses the leveraged-trend drawdown from −56% to ≈SPX (−34.8%) while still beating SPX on raw return AND Sharpe, out-of-sample, net of realistic costs — but only for TQQQ.** This is the first time the bench has a candidate that beats SPX on raw return *with an investable drawdown.*

It is a **leverage premium with a working risk-management layer**, not pure alpha — and its edge is **specific to QQQ**, which I will not overstate. But it is, by a wide margin, the strongest and most investable lead the project has produced.

## Disposition / next steps

1. **Promote the TQQQ vol-target sleeve to a paper-traded candidate** (paper clock — no real money; within standing orders). It earns a live out-of-sample paper track record while we watch it.
2. **Keep the go-live gate intact:** real money requires explicit per-request Cyrus approval; the GATE bars (12+ weeks, 15+ round-trips, realized Sharpe, drawdown ceiling) still apply. Paper first.
3. **Adopt the 2 YouTube-sprint hardening upgrades** (anti-overfit reject filter U1; churn penalty in ranking U2) — directly relevant since the sleeve trades often.
4. **Do NOT generalize to UPRO/SPXL** — they fail on cost. TQQQ only.

This is a real, honest win — the project is **not** out of leads. The wind-down question is, for now, answered: there's something here worth paper-trading and watching.
