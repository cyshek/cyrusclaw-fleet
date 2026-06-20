# LOW-TURNOVER DUAL-MOMENTUM / RELATIVE-STRENGTH ROTATION — Research Memo

**UTC:** 2026-06-04T06:38:51Z
**Lane:** 6 (re-aimed) of `reports/RESEARCH_SLATE_20260603.md` — low-turnover, longer-hold momentum/quality rotation, the night's prescribed direction (cost-ceiling escape test).
**Scratch:** `strategies_candidates/lowturn_momentum/`
**Driver:** `reports/_lowturn_momentum_driver.py` · **Raw results:** `reports/_lowturn_momentum_results.json`
**Verdict:** 🔴 **REJECT (conclusive).** Best honest FP-cont Sharpe **0.524** (a single `top_k=1` knife-edge); diversified region tops at 0.39; **0 of 36 cells ≥ 1.0**, only 1 ≥ 0.50. **Low turnover does NOT break the ~0.5 ceiling — it CONFIRMS it.**

---

## 1. Thesis (falsifiable)

A monthly-rebalanced DUAL-MOMENTUM rotation (Antonacci GEM-style) across a diversified sleeve of liquid ETFs — rank by trailing return, hold the top-K, and apply an ABSOLUTE-TREND filter (hold a winner only if its trailing return beats a safe-asset proxy, else rotate that slot to bonds) — clears the front door (FP-cont Sharpe ≥ 1.0, robust plateau, ≥ 8 %/yr-on-deployed, beats BH-SPY risk-adjusted) BECAUSE its low turnover makes per-trade cost a trivial fraction of per-trade gross.

**Result: FALSIFIED at the Sharpe gate (not the cost gate).** Turnover is genuinely low and cost is genuinely negligible — but the diversified, risk-adjusted edge simply isn't there. The signal, not the cost, is the binding constraint.

## 2. Sleeve + signal definition

- **Risk sleeve (rank candidates):** SPY, QQQ, IWM (US equity broad/tech/small), EFA, EEM (intl dev/EM), GLD, DBC (gold/commodities), VNQ (REITs) — 8 legs, 5 asset classes. Diversified by construction (the controlled contrast to the single-name SOXL lane).
- **Safe asset (absolute-filter threshold):** BIL (T-bill proxy).
- **Bond fallback (where filtered slots go):** best of {IEF, TLT} by trailing return.
- **Signal:** trailing total return over `lookback_bars` skipping `skip_bars` (classic 12-1 = 252/21, plus shorter variants swept).
- **Selection:** top-K risk legs by trailing return. Each slot passes iff its trailing return > safe-asset trailing return + `abs_margin`; PASS → hold the risk leg, FAIL → that slot's capital rotates into the bond fallback (Antonacci "out-of-market" rule, but redeployed to bonds rather than parked in cash).
- **Allocation:** equal-weight K slots at `max_notional / K`. No leverage, no shorting, exposure ≤ cash.
- **Rebalance:** monthly (calendar-month boundary). **Low turnover is the design point.**

This DIFFERS from the existing `tsmom_xa_be0d7f` (pure TSMOM, FAILED at median-Sharpe 0.41): pure TSMOM sits in CASH when nothing trends up; this dual-momentum design REDEPLOYS failing slots into bonds to keep capital working while the absolute filter still cuts equity in a real bear.

## 3. Turnover / trade-count — IS it low? (yes, decisively)

Over the full 8-window panel (~2,600 ticks, ~5 trading years of usable span):

| top_k | typical trade count (full panel) |
|---|---|
| 1 | 24–56 |
| 2 | 40–110 |
| 3 | ~93 |

**Dozens of trades over 5 years, not hundreds.** Even the highest-churn cell (126/21, K=2: 110 trades) is ~1.7 trades/month. The headline cells are 24–28 trades total (~0.4/month). This is genuinely low-turnover, monthly-or-slower behavior — thesis design constraint satisfied.

## 4. Cost-as-fraction-of-gross — does low turnover escape the ceiling?

**Cost is negligible — and that is precisely why this lane is so informative.** Worst-instrument drawdowns are −0.07 % to −0.23 % (deployed basis), total realized costs on the sister low-turnover basket (`tsmom_xa`) were **$0.13 on $100 notional over 1,374 ticks** — i.e. ~0.13 % of notional across the *entire* span. Per-trade cost (alpaca_stocks, 2 bps spread, 0 fee) on a monthly rebalance is a rounding error against per-trade gross.

**So low turnover DID escape the COST ceiling. It did NOT escape the SHARPE ceiling.** The intraday lane proved cost pins high-turnover strategies near zero; this lane removes cost from the equation entirely — and the strategy still tops out at 0.524. **Conclusion: for this signal class, cost was never the binding constraint. The diversified-momentum signal itself is sub-1.0.** Removing cost reveals the naked signal, and the naked signal is ~0.5. This is the cleanest possible confirmation that the ~0.5 plateau is a SIGNAL ceiling, not a COST ceiling.

## 5. 2022-drawdown behavior (the source of any edge)

The absolute-trend filter DID behave as designed in the one real bear:

| Cell | 2022-H1 bear ret | 2022-Q3 chop ret | vs BH-SPY 2022-H1 (+0.19%) |
|---|---|---|---|
| 189/63, K=1 (best) | **+2.64 %** | −0.88 % | strongly beats (rotated to gold/commodities/bonds) |
| 252/21, K=2 | +0.45 % | −1.30 % | beats |
| 189/21, K=2 | −0.22 % | −0.55 % | roughly flat |

In 2022-H1 the filter pulled capital OUT of equities into the legs that were actually trending (GLD/DBC/bonds), turning a flat/negative BH window into a positive one for the concentrated cell. **The edge mechanism is real** — the filter reduces equity drawdown in the bear. The problem is it isn't large or consistent enough across the full panel to lift risk-adjusted return to the gate.

## 6. BH-relabel check (PASS — it is NOT a relabeled BH-SPY)

- **PnL correlation to BH-SPY: r ≈ 0.32** across all headline cells (per-tick equity returns). Low — the diversified sleeve + bond fallback genuinely decorrelate from buy-and-hold SPY.
- BH-SPY itself scores **FP-cont 0.460** on the same panel; the best dual-momentum cell (0.524) beats it only marginally and on just **3/8 windows** risk-adjusted.
- **Not a relabel** — but also **not a meaningful improvement.** It's a genuinely different, genuinely diversified strategy that lands at essentially the same sub-1.0 plateau as buy-and-hold. The decorrelation buys you nothing at the gate because the absolute edge is too thin.

## 7. Sweep grid + honest FP-cont Sharpe per cell

Pre-committed grid (36 cells): `lookback_bars ∈ {126,189,252} × skip_bars ∈ {21,63} × top_k ∈ {1,2,3} × abs_margin ∈ {0.0,0.02}`. FP-cont Sharpe over the concatenated 8-window panel, active cost, $100 notional.

- **fp range: −0.096 … +0.524 · median 0.264**
- **cells ≥ 0.50: 1 / 36 · cells ≥ 1.0: 0 / 36**

Top cells:

| FP | lookback | skip | K | abs_margin | trades | beats-BH win | 2022-H1 | corr-BH |
|---|---|---|---|---|---|---|---|---|
| **0.524** | 189 | 63 | **1** | 0.0 | 28 | 3/8 | +2.64% | 0.32 |
| 0.488 | 189 | 63 | 1 | 0.02 | 24 | 2/8 | +2.64% | — |
| 0.393 | 189 | 21 | 2 | 0.0 | 68 | 2/8 | −0.22% | 0.36 |
| 0.380 | 126 | 21 | 1 | 0.0 | 56 | 3/8 | −0.01% | — |
| 0.377 | 189 | 63 | 2 | 0.0 | 62 | 1/8 | +0.13% | — |
| 0.289 | 252 | 21 | 2 | 0.0 | 48 | 2/8 | +0.45% | 0.32 |

## 8. Plateau vs knife-edge (FAIL — no plateau)

- The single 0.524 cell is `top_k=1` (a CONCENTRATED single-asset bet, the antithesis of the "diversified sleeve" thesis) and is **isolated**: its `top_k=2/3` neighbors at the same lookback collapse to 0.38 and 0.32. The lone above-0.5 cell is a **knife-edge**, not a plateau.
- The genuinely diversified region (`top_k=2`, the design intent) tops out at **0.39** and most cells cluster 0.27–0.39.
- Shortening to 126-bar lookback with 21-skip degrades hard (0.05–0.17) — the signal is lookback-sensitive, another knife-edge symptom.
- **No robust plateau anywhere near 1.0.** Pre-committed: the best single cell is not the result; the plateau is — and there is no plateau.

## 9. Deployed-%/yr and deployment

- Avg deployment fraction: 0.26–0.61 of the $100 cap (cash drag from the monthly cadence + frequent bond-fallback parking).
- Annualized-on-deployed: best cell ~**+5.2 %/yr**, diversified K=2 cells ~+2–3.5 %/yr — **below the 8 %/yr-on-deployed bar.**
- BH-SPY on the same panel: ~+6.0 %/yr. The strategy does not out-earn passive SPY even on deployed capital.

## 10. Honest sample caveat

Data starts 2020-07-27. A 12-month (252-bar) lookback + 21-skip burns ~390 calendar days of warmup, so usable signal begins ~2021-09. The panel captures essentially **ONE real bear (2022) + the 2025 tariff dip** across ~5 years ≈ ~60 monthly rebalances. **This is thin for a monthly, regime-sensitive strategy** — momentum's edge is concentrated in regime transitions, and we have only one-and-a-half of them. Even the 0.524 cell rests on a handful of decisive rebalances; it should be read as fragile, not as a near-miss worth chasing.

---

## VERDICT: 🔴 REJECT (conclusive) — confirms the ~0.5 ceiling

Low-turnover dual momentum is a **clean, honest REJECT**, and an *informative* one:

1. **It does NOT break the ~0.5 FP-cont Sharpe ceiling — it CONFIRMS it.** Best honest cell 0.524 (a `top_k=1` knife-edge); diversified region ≤ 0.39; 0/36 cells ≥ 1.0.
2. **Cost was never the binding constraint for this signal class.** Turnover is genuinely low (dozens of trades / 5 yr), cost is a rounding error (~0.13 % of notional total), and the naked, cost-free signal still lands at ~0.5. The intraday lane's "cost pins the plateau near zero" is a high-turnover phenomenon; remove turnover and the SAME ~0.5 plateau reappears — meaning the plateau is a **signal ceiling**, the deeper constraint.
3. **It is genuinely diversified and NOT a BH-SPY relabel** (corr ≈ 0.32, positive 2022 behavior) — the absolute-trend filter works as designed — but the decorrelation and the bear-protection are too thin to clear the gate.
4. **No plateau, fails the deployed-yield bar, thin sample.** Nothing here warrants promotion.

This closes the low-turnover momentum/quality lane with the same conclusion as the price-xsec, vol-regime, credit, dollar, and dispersion lanes: **real-but-sub-1.0, and now we know the ~0.5 plateau survives even when cost is removed.** The honest REJECT is the success here — it rules out "cost is the only thing pinning us at 0.5" for the low-turnover case.

**Zero promotion authority — Tessera validates.** Protected files unchanged (md5 verified at finish: runner.py=4be185e4bdcb6f432d99b71b21a4859c, backtest.py=9444ee5be64d9fd2639fd8cb0a28e002, backtest_xsec.py=2278a4c8d8a66703da5cd6f2a0880061, risk.py=e4c227e019c99e7e52224eb2f91389b8).
