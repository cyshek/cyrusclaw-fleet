# Backtest — Dollar-Trend Cross-Asset Lead-Lag Overlay (UUP → SPY)

**UTC:** 20260602T072340Z
**Author:** trading-bench (subagent: cross-asset macro lead-lag timing)
**Status:** COMPLETE. **Verdict: honest REJECT** (a sound null — the goal was a sound test, not a manufactured pass).

## Variant chosen + rationale

**Variant (c): FX / dollar lead-lag — UUP (DXY proxy) 63-day trend → SPY long/flat timing, monthly rebalance.**

One-line rationale: the dollar is the cleanest *economic* lead-lag and is *negatively* correlated to equities, so a dollar-trend timing signal is genuinely orthogonal to "just hold SPY" — unlike copper/oil momentum (co-moves with equities, risks merely tracking SPY at lower return) or TLT/yield-curve trend (collapses toward a textbook SPY 200-SMA regime filter the GATE distrusts).

Why not the others:
- **(a) yield-curve/TLT trend:** ≈ bond-momentum regime filter, collinear with SPY trend; low novelty, GATE-suspicious (200-SMA-equivalent).
- **(b) Dr. Copper/DBC momentum:** price-momentum on a high-beta cyclical asset that co-moves *contemporaneously* with equities → high risk of tracking SPY at lower return (the explicit anti-pattern).
- **(d) credit variant:** HYG/LQD is DEAD; a duration-matched HYG/IEF variant is not meaningfully different in signal economics. Skipped.

## Fixed construction params (locked BEFORE results)

| param | value |
|---|---|
| Timed instrument | SPY (long/flat) |
| Signal instrument | UUP (Invesco DB US Dollar Bullish, DXY proxy) |
| Dollar trend | UUP close vs UUP SMA-63 (~3 months) |
| Risk-on (hold SPY) | UUP close < UUP SMA-63 (dollar weakening) |
| Risk-off (flat) | UUP close ≥ UUP SMA-63 (dollar strengthening) |
| Rebalance | monthly (first trading bar of month only) → low turnover |
| Notional | $100, long/flat only, no shorting/leverage |
| Cost model | CostModel.alpaca_stocks() — 2 bps one-way, honest (not weakened) |
| Window | full real Alpaca daily span (~2020-07 → 2026-05) |
| No-lookahead | at SPY bar dated d, signal uses only UUP closes dated ≤ d |

## Results (net of honest 2bps cost; source of truth = `last_run.json`)

**Window:** 2020-07-27 → 2026-05-29, 1468 daily bars, 5.84 yr.

**Turnover (the key survivable property — and it IS survivable here):**
- n_trades = **16** (8 buys / 8 closes), **2.74 trades/yr** — well under the "<<100" target.
- In-position 470/1468 bars → **deployed only 32%** of the time (sat out most of the bull run).
- Total cost over the whole backtest: **$0.33**. Turnover is not the problem; the signal is.

| metric | NET | GROSS |
|---|---|---|
| fp-continuous Sharpe | **0.547** | 0.553 |
| total return (on $1000 book) | +2.82% | +2.85% |
| ROI on deployed ($100) | +28.2% | +28.5% |
| **annualized return on deployed** | **+4.35%/yr** | +4.39%/yr |
| win rate | 87.5% (14/16) | — |
| portfolio max-DD | −1.9% | — |
| worst-instrument DD | −19.4% | — |
| total costs | $0.33 | $0.00 |
| **same-path BH-SPY** | **+133.9%** (15.7%/yr) | — |
| **beats BH-SPY?** | **No** | — |

The strategy earns a positive but tiny return because it is *flat 68% of the time* — including through most of 2020-2021 and 2023-2024 equity rallies. High win rate (87.5%) is a mirage of small, infrequent, well-timed-on-the-margin trades; it does not translate into meaningful return because capital is rarely deployed. Cost-survivability (the property the failed high-churn lanes lacked) is fully achieved — but a cost-survivable signal with no edge is still no edge.

## Robustness (read-only sensitivity, locked variant = SMA-63)

To confirm the REJECT is not a single-parameter fluke, the dollar-trend lookback was swept (the candidate stays locked at 63):

| SMA | n_trades | fp-Sharpe | ann-on-deployed |
|---|---|---|---|
| 21 | 35 | 0.191 | ~1.9%/yr |
| 42 | 21 | 0.593 | ~5.6%/yr |
| **63 (locked)** | **16** | **0.547** | **4.35%/yr** |
| 84 | 14 | 0.631 | ~6.0%/yr |
| 126 | 15 | 0.664 | ~6.3%/yr |

**No parameter clears either front-door gate.** fp-Sharpe peaks at ~0.66 (vs 1.0 bar); ann-on-deployed peaks at ~6.3% (vs 8% bar). The locked 63 is mid-pack — not cherry-picked. The null is structural, not a tuning artifact.

## No-lookahead confirmation

At each SPY bar dated `d`, the signal reads ONLY UUP closes dated ≤ `d` (strict filter in `strategy._visible_uup_closes`). The injected UUP series is a fixed pre-fetch; the date-filter enforces walk-forward visibility. No UUP bar dated after the current SPY bar is ever consulted. Monthly-rebalance gate keys off the previous bar's month, also backward-only.

## GATE Bar A front-door verdict

| clause | bar | actual | pass? |
|---|---|---|---|
| (a) fp-continuous Sharpe ≥ 1.0 | 1.0 | **0.547** | ❌ FAIL |
| (f) ann. net return on deployed ≥ 8%/yr | 8.0% | **4.35%/yr** | ❌ FAIL |
| beats same-path BH-SPY risk-adjusted | — | +2.8% vs +134% | ❌ No |

**VERDICT: REJECT.** Both primary front-door guards fail by a wide margin, the result is robust across the parameter sweep, and the overlay is crushed by buy-and-hold SPY. The dollar-trend lead-lag — at least via the UUP-SMA-trend formulation at retail cost — does not carry tradeable equity-timing edge. This is a clean null on a sound, no-lookahead, cost-honest, low-turnover test: **a SUCCESS as a test**, not a failure to engineer a pass.

Economic read: the dollar↔equity lead-lag is real but (i) too slow/noisy at the 3-month-trend horizon to beat the equity risk premium, and (ii) keeps the overlay flat through major rallies (32% deployed), so it forfeits far more upside than it dodges downside. The negative-correlation orthogonality that made it the best-justified candidate is exactly what makes it sit out the bull market.

## Protected files / suite integrity

Full suite re-run: **289 passed, 0 regressions**. Protected-file md5 (pre == post, verified):
```
4be185e4bdcb6f432d99b71b21a4859c  runner/runner.py
e4c227e019c99e7e52224eb2f91389b8  runner/risk.py
9444ee5be64d9fd2639fd8cb0a28e002  runner/backtest.py
2278a4c8d8a66703da5cd6f2a0880061  runner/backtest_xsec.py
5d56241fe65392c0c50bdbefd25e93b3  runner/backtest_event.py
```
risk.py untouched (exposure-≤-cash invariant intact). Composed PUBLIC `backtest()` API only via `decide_fn` + `CostModel`; no new harness capability needed. Paper/backtest only; ZERO promotions; no cron; no STOP_TRADING changes.
