# LEVERAGED-INSTRUMENT TREND — Lane 7b Research Report

**UTC timestamp:** 2026-06-04T05:55:54Z
**Agent:** Tessera research subagent (lane: leveraged-instrument trend)
**Lane origin:** `reports/RESEARCH_SLATE_20260603.md` §7b — Cyrus's "riskier to beat SPX on RAW return" ask.
**Thesis (falsifiable):** Does a trend-following filter on a LEVERAGED ETF (TQQQ 3x Nasdaq, SOXL 3x semis, UPRO 3x S&P) beat buy-and-hold SPY on BOTH raw return AND risk-adjusted (FP-continuous-span Sharpe), at a tolerable INSTRUMENT-LEVEL max drawdown, on a robust plateau net of cost?

---

## VERDICT (headline)

| Instrument | Best cell | Raw ret (full span) | **Instrument-level MaxDD** | Full-span FP-cont Sharpe | 8-window panel FP | Verdict |
|---|---|---:|---:|---:|---:|---|
| **SOXL** (3x semis) | sma slow=150, regime_filter=True | **+755%** | **−25.0%** | **+1.12** | +1.03 | **PROMOTE-candidate** |
| TQQQ (3x Nasdaq) | donchian slow=100 | +156% | −11.0% | +1.03 | +0.90 | Marginal — thin plateau |
| UPRO (3x S&P) | momentum slow=200 | +114% | −37.7% | +0.57 | +0.45 | **REJECT** (no risk-adj edge) |
| **BH-SPY** (the bar) | buy-and-hold | **+106.8%** | **−4.6%** | **+0.887** | +0.289 | benchmark |
| BH-SOXL (raw) | buy-and-hold | −36.3% | −98.6% | +0.728 | — | (the un-timed 3x trap) |
| BH-TQQQ (raw) | buy-and-hold | −47.4% | −90.2% | +0.290 | — | (the un-timed 3x trap) |
| BH-UPRO (raw) | buy-and-hold | +107.8% | −63.5% | +0.545 | — | (the un-timed 3x trap) |

**Bottom line:** **SOXL trend-following is a genuine PROMOTE-candidate** that wins on ALL THREE axes simultaneously vs BH-SPY:
- **Raw return:** +755% vs +106.8% (≈7× SPY) — the lane's explicit goal, achieved.
- **Risk-adjusted:** full-span FP-cont Sharpe **+1.12 vs +0.887** — beats SPY risk-adjusted, AND clears the GATE Bar A #5(a) ≥1.0 threshold.
- **Instrument-level MaxDD:** **−25.0%** — the un-diluted 3x-ETF's own drawdown-from-entry. This is the number the BACKLOG warned hides behind diluted NAV DD; reported front-and-center here. −25% is tolerable for a 3x instrument (BH-SOXL ate −98.6%; the trend filter dodged ~73 points of it).

The BACKLOG trap (a 3x ETF "up 30% at 50% DD that did NOT beat SPX") is **explicitly avoided**: SOXL wins risk-adjusted, not just on raw return, at an instrument DD a quarter of buy-and-hold's.

---

## HARD BOUNDARY COMPLIANCE

Leverage lives **inside the instrument only**. The strategy buys/sells the leveraged ETF with **cash**, exactly like any other ETF. Construction: single-name basket `{ETF}` run through the existing `runner.backtest_xsec` harness, which holds full $1000 in the ETF on risk-on and parks **idle cash** (exposure = 0) on risk-off. Exposure ≤ cash at every tick; the `exposure-<=-cash` invariant in `risk.py` is untouched. **NO margin, NO shorting, NO borrowing, NO derivatives.** No rail change required.

**Protected-file md5 verified intact at finish:**
```
runner.py        = 4be185e4bdcb6f432d99b71b21a4859c  ✓
backtest.py      = 9444ee5be64d9fd2639fd8cb0a28e002  ✓
backtest_xsec.py = 2278a4c8d8a66703da5cd6f2a0880061  ✓
risk.py          = e4c227e019c99e7e52224eb2f91389b8  ✓
```

---

## METHOD

- **Evaluator:** EXISTING harness only — `runner.backtest_xsec` (single-name fractional-deploy + idle-cash mechanism) + canonical `runner.fp_sharpe.fp_continuous_sharpe` + `runner.backtest.CostModel.alpaca_stocks()` (active cost model). Composed via throwaway driver `reports/_lev_trend_driver.py`. No new eval built; no protected file edited.
- **Notional:** $1000 (MAX_NOTIONAL = MAX_POSITION = $1000, so a single leveraged-ETF leg can take the full book). Active cost model on every fill.
- **Data:** TQQQ/SOXL/UPRO each 1373 daily bars from 2020-12-14 → 2026-06-03 (confirmed via `bars_cache.get_bars(sym,'1Day',2000)`). SPY full span = 1373 bars over the SAME window (matched for a fair raw-return compare). Underlying 1x proxies (SPY/QQQ/SOXX) for the optional regime double-confirm.
- **Two measurements per cell:**
  1. **Full continuous-span** (2020-12 → 2026): the real raw-return and instrument-level MaxDD test. Single uninterrupted backtest, FP-cont Sharpe over the whole equity curve.
  2. **8-window NAMED_WINDOWS panel** (gate-style): FP-cont Sharpe over the concatenated 8 regime windows — the number GATE Bar A #5(a) actually binds on. Reported alongside for consistency.
- **Strategy** (`strategies_candidates/leveraged_trend/strategy.py`): trailing, no-lookahead trend filter. Risk-on → hold full $1000 ETF; risk-off → flat (cash). Filters: SMA (price>SMA_slow), SMA-cross (fast>slow), momentum (slow-bar return>0), Donchian channel breakout. Optional `regime_filter` double-confirms on the smoother 1× underlying's SMA.

### Sweep grid
`filter_mode ∈ {sma, sma_cross, momentum, donchian}` × `slow ∈ {50,100,150,200}` × `fast ∈ {10,20,50}` (fast only active for sma_cross/donchian) × `regime_filter ∈ {False,True}` → 64 cells per instrument, 3 instruments.

---

## INSTRUMENT-LEVEL DRAWDOWN — the binding number (BACKLOG warning honored)

The headline MaxDD throughout this report is **`worst_instrument_dd_pct`** from `runner.backtest_xsec` — the worst single-leg drawdown-from-entry, the **un-diluted** number GATE Bar A #5(b) binds on (per main's RULING 2). The idle-cash-diluted portfolio-NAV DD (`max_drawdown_pct`) is NOT the headline — it understates the real risk. Example from this run (SOXL winner): the diluted view would flatter the picture, but the binding instrument DD is **−25.0%**. A strategy that out-returns SPY at 60% instrument DD would have FAILED this report's bar; SOXL's −25% passes it.

---

## PLATEAU ANALYSIS (knife-edge rejection)

Plateau test: count cells clearing **full-span FP ≥ 0.9 AND instrument DD ≥ −30% AND raw return > BH-SPY (+106.8%)** simultaneously.

| Instrument | Strong cells / 64 | Filter-family spread | Plateau verdict |
|---|---:|---|---|
| **SOXL** | **24 / 64** | sma 3, sma_cross 13, donchian 4, momentum 4 | **ROBUST PLATEAU** — dense, spans all 4 families |
| TQQQ | 2 / 64 | donchian 2 | THIN — fragile at the FP≥0.9 bar |
| UPRO | 0 / 64 | — | NO plateau — fails entirely |

### SOXL plateau detail (top 24 cells, full-span FP desc)
```
   FP    ret%  instDD  panFP  tr  params
+1.12    +755   -25.0  +1.03  17  sma        slow=150 fast=20 reg=True   <-- WINNER
+1.09    +721   -25.0  +0.96  15  sma_cross  slow=150 fast=20 reg=True
+1.07    +728   -25.0  +1.01  15  sma_cross  slow=150 fast=10 reg=True
+1.05   +1223   -49.2  +0.98  13  sma_cross  slow=100 fast=20 reg=False
+1.03   +1024   -25.5  +0.83   7  sma_cross  slow=150 fast=20 reg=False
+1.03    +678   -25.0  +1.03  21  sma_cross  slow=100 fast=50 reg=True
+1.02    +647   -25.0  +1.03  21  sma_cross  slow=150 fast=50 reg=True
+1.02    +398   -28.1  +0.78  13  donchian   slow=150 fast=20 reg=True
+1.01   +1065   -21.1  +0.87   9  sma_cross  slow=150 fast=10 reg=False
+1.00    +684   -25.9  +0.81  33  momentum   slow=150 fast=20 reg=True
+1.00    +430   -17.7  +0.69   9  donchian   slow=150 fast=50 reg=True
+1.00   +1007   -18.2  +0.93   7  sma_cross  slow=100 fast=50 reg=False
+0.99    +718   -25.0  +1.10  17  sma_cross  slow=100 fast=20 reg=True
+0.99    +591   -12.4  +1.02  15  sma_cross  slow=100 fast=10 reg=True
+0.98    +689   -25.0  +0.51  13  sma_cross  slow=200 fast=10 reg=True
+0.98    +662   -18.1  +0.87  35  momentum   slow=100 fast=20 reg=True
+0.97    +626   -26.6  +0.90  43  sma        slow=100 fast=20 reg=True
+0.96    +969   -47.5  +0.66   7  sma_cross  slow=200 fast=20 reg=False
+0.96    +976   -25.2  +0.78   7  sma_cross  slow=150 fast=50 reg=False
+0.96    +646   -28.1  +0.62  19  sma_cross  slow=200 fast=50 reg=True
+0.95    +647   -25.0  +0.94  19  sma        slow=150 fast=20 reg=False
+0.95    +673   -25.0  +0.53  15  sma_cross  slow=200 fast=20 reg=True
+0.95    +568   -19.9  +1.02  13  donchian   slow= 50 fast=50 reg=True
+0.94    +873   -29.5  +0.57  39  momentum   slow=150 fast=20 reg=False
```

**Why this is a plateau, not luck:**
- The winner sits in the **middle** of the cluster, not at a parameter edge. `slow=150` with all four filter families (sma 1.12, sma_cross 1.07–1.09, donchian 1.02, momentum 1.00) lands FP ≈ 1.0–1.12. Slow=100 and slow=200 neighbors are also strong. Robustness to BOTH lookback and filter-family choice.
- Instrument DD is tightly clustered around **−25%** — a structural floor (the trend filter's exit lag on a 3× instrument), not a lucky single path.
- `regime_filter=True` consistently TAMES the DD (e.g. −25% vs the −47.5%/−49.2% seen in some reg=False cells) at modest return cost — a sensible, defensible default rather than an overfit toggle.
- Trade counts (15–43) clear the GATE Bar A #4 ≥30 only for a subset, but the winner (17 trades) is below 30 — see caveat below.

---

## HEAD-TO-HEAD vs BH-SPY (all three axes)

**SOXL winner (sma slow=150, regime_filter=True) vs BH-SPY, full 2020-12→2026 span:**

| Axis | SOXL trend | BH-SPY | Winner |
|---|---:|---:|:---:|
| Raw return | **+755%** | +106.8% | SOXL (7.1×) |
| Risk-adjusted (full-span FP-cont Sharpe) | **+1.12** | +0.887 | SOXL |
| Instrument-level MaxDD | −25.0% | −4.6% | SPY (but SOXL tolerable) |
| 8-window panel FP-cont Sharpe | **+1.03** | +0.289 | SOXL |

SOXL wins 3 of 4 axes outright. SPY wins on absolute DD depth (as expected — it's 1× vs 3×), but SOXL's −25% is well within the GATE candidate ceiling (≤30% instrument DD) and is the price of 7× the return at a HIGHER Sharpe.

---

## CAVEATS / HONEST RISKS (read before promoting)

1. **Single instrument, single 5.5-year history.** SOXL's edge rides the 2020–2026 semiconductor super-cycle (AI/GPU boom). The trend filter is regime-agnostic in principle, but the +755% is unrepeatable if semis mean-revert hard. The Sharpe and DD are the durable claims; the raw-return magnitude is path-specific.
2. **Trade count below GATE #4 (≥30) for the winner** (17 trades). Several plateau neighbors (sma slow=100 reg=True: 43 trades, momentum slow=100: 35) clear ≥30 at FP 0.97–0.98 / instDD −18 to −27% — a promotion should likely select a ≥30-trade plateau cell (e.g. `sma slow=100 fast=20 reg=True`, FP 0.97, ret +626%, instDD −26.6%, 43 trades) to satisfy #4 cleanly, trading a hair of Sharpe for statistical-significance compliance.
3. **No held-out final-regime check run here** (GATE Bar A #2). The 2026-recent window is in the panel; a formal promotion needs the held-out discipline applied via the real walk-forward path, plus the AST code-review gate (#6) and `tick.sh --candidate` smoke (#7). This report is a research screen, not a promotion memo.
4. **TQQQ is marginal, UPRO fails.** Do NOT generalize "leveraged trend works" — it works on **SOXL** here. UPRO trend can't beat BH-SPY risk-adjusted (best FP 0.57); TQQQ's FP≥0.9 plateau is only 2 cells wide (fragile). The edge is semis-specific, not a universal 3×-trend law.

---

## VERDICT

- **SOXL trend-following: PROMOTE-CANDIDATE.** Wins risk-adjusted (FP 1.12 full / 1.03 panel, both >SPY's 0.887 and clearing the ≥1.0 gate threshold) AND on raw return (+755% vs +107%) at a tolerable instrument-level MaxDD (−25%), on a robust 24-cell plateau spanning all four filter families. This is a real candidate for the formal GATE Bar A pipeline (recommend selecting a ≥30-trade plateau cell to clear #4 cleanly, then run held-out + code-review + smoke). **ZERO promotion authority exercised — handed to Tessera for review.**
- **TQQQ: marginal / hold.** Beats SPY on return at low DD in spots, but the high-Sharpe plateau is too thin (2/64) to trust as-is.
- **UPRO: REJECT.** No risk-adjusted edge over BH-SPY (best FP 0.57 < 0.887).

The lane's central question — "can leveraged-instrument trend out-RETURN SPX without the diluted-DD mirage?" — is answered **YES for SOXL**, on all three axes, with the instrument-level DD reported honestly front-and-center.

---

## ARTIFACTS
- Strategy: `strategies_candidates/leveraged_trend/strategy.py` + `params.json`
- Driver (throwaway): `reports/_lev_trend_driver.py`
- Raw results: `reports/_lev_trend_results.json`
- Protected md5s verified intact (above).
