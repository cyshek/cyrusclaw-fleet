# Combo Sprint — macd_momentum_iwm × {breakout_xlk, volume_breakout_qqq} — VERDICT

_2026-06-27 · trading-bench (Tessera) · main-greenlit weak×orthogonal combo sprint_

## TL;DR

**Both combos REJECT, both fusion modes (AND + OR).** This is a deterministic
**cross-symbol** mechanical re-test of the pairing yesterday's
`EQUITY_CROSSPARENT_COMBO_VERDICT` flagged as the *one* combo shape that could
plausibly win (strong parent + weak-orthogonal `macd_momentum_iwm`). The cleaner
mechanical test confirms the rejection and explains *why* with a decisive
exposure diagnostic:

- **AND-fusion** (IWM-MACD bullish gate on the breakout entry) strangles trade
  count (QQQ 158→98, XLK 334→270) and **cuts** FP-continuous Sharpe. No mode
  beats its solo parent.
- **OR-fusion** raises raw return and trade count, and on QQQ raises full-span
  Sharpe (0.485→0.610) — but the diagnostic proves this lift is **closet beta,
  not timing edge**: exposure tripled (3.10×) while Sharpe rose only 1.26×, and
  Sharpe-*per-unit-exposure* DROPPED. The extra IWM-MACD entries buy more
  bull-drift exposure at a *worse* risk-adjusted rate.
- **Both books lose to simply buying-and-holding the underlying ETF**
  (QQQ-BH FP-Sharpe 0.897 full / 1.218 OOS beats every QQQ variant; XLK-BH
  0.530 beats every XLK variant).
- The QQQ-OR in-sample Sharpe lift (+0.098 IS) **evaporates OOS** (+0.012,
  negligible): solo OOS 1.003 vs OR OOS 1.015.

**No promotion. The verdict's lesson #1 holds and is reinforced: you cannot
manufacture risk-adjusted edge by bolting a second signal onto an
already-decent breakout — even a genuinely orthogonal cross-symbol one. OR adds
closet beta; AND over-restricts.**

## Method (honest harness)

- **Data:** 1Hour bars, deepest cached span **2020-07-27 → 2026-06-24** (~12.7k
  hourly bars). NOTE: the directive's "IS/OOS@2018" split is **infeasible** —
  Alpaca 1Hour depth floors at 2020-07-27 (the documented bars-cache floor).
  Adapted to the deepest honest split: **IS = …→2023-12-31, OOS = 2024-01-01→…**
  (~3.5yr IS / ~2.5yr OOS).
- **Cost:** `CostModel.alpaca_stocks()` = **2 bps one-way** (per directive).
- **D+1 lag, no lookahead:** the cross-symbol IWM-MACD confirmation reads the
  most recent IWM bar **strictly before** the primary bar's timestamp. A
  **+1-bar-lag robustness canary** is also run (the lethal test that killed
  VIX-term + SKEW).
- **IWM-MACD signal** recomputed bar-by-bar on the full IWM series using the
  **live `macd_momentum_iwm._macd()`** (byte-identical to the deployed
  strategy); bullish ≙ MACD>signal AND MACD>0. IWM is bullish 31.6% of bars.
- **Metric:** full-period **continuous-span** Sharpe (`fp_sharpe`, 1Hour
  annualization = (510/60)×252 = 2142 bars/yr) — the load-bearing ruler, NOT
  median-of-windows. SPY + underlying-ETF buy&hold on the same bar path.
- **Primary parent owns symbol + position; macd_momentum_iwm contributes only a
  cross-symbol confirmation/entry-trigger** (the only coherent way to fuse three
  different-symbol strategies into one book).

## Results — full span (2020-07 → 2026-06), 2 bps, FP-continuous Sharpe

| Variant | FP-Sharpe (base) | FP-Sharpe (canary +1lag) | trades | time-in-mkt |
|---|---|---|---|---|
| **volume_breakout_qqq** solo | +0.485 | — | 158 | 0.110 |
| qqq AND-fusion | +0.337 | +0.363 | 98 | — |
| qqq OR-fusion | +0.610 | +0.594 | 620 | 0.342 |
| QQQ buy&hold | **+0.897** | — | — | 0.997 |
| **breakout_xlk** solo | +0.282 | — | 334 | 0.560 |
| xlk AND-fusion | +0.070 | +0.016 | 270 | — |
| xlk OR-fusion | +0.266 | +0.292 | 422 | 0.621 |
| XLK buy&hold | **+0.530** | — | — | — |

(Canary-robust = the OR Sharpe survives the extra 1-bar lag; that robustness is
real but irrelevant because the *base* signal is already sub-benchmark beta.)

## The decisive exposure diagnostic (QQQ-OR, the only variant that "looked" good)

```
exposure ratio OR/solo = 3.10x   ;   Sharpe ratio OR/solo = 1.26x
solo mean-tick-ret / exposure = 1.11e-05
OR   mean-tick-ret / exposure = 7.90e-06   <-- LOWER per-unit-exposure
```

If OR-fusion's added IWM-MACD entries were accretive, Sharpe-per-unit-exposure
would hold or rise. It **falls** — OR buys 3× the market exposure at a *worse*
risk-adjusted rate, and the higher gross exposure to a bull-drifting QQQ is what
lifts the raw Sharpe. That is the textbook closet-beta signature. The honest
benchmark settles it: **QQQ buy&hold (0.897 full / 1.218 OOS) beats every QQQ
combo variant** — the entire book is a worse risk-adjusted bet than holding the
index it trades.

## IS vs OOS (the lift is in-sample)

| | solo IS | OR IS | solo OOS | OR OOS | ETF-BH OOS |
|---|---|---|---|---|---|
| QQQ | +0.288 | +0.386 | +1.003 | +1.015 | **+1.218** |
| XLK | +1.007 | +0.869 | −0.122 | −0.077 | **+0.265** |

QQQ-OR's IS edge (+0.098) collapses to +0.012 OOS. XLK is OOS-broken outright
(solo and OR both negative; buy&hold positive) — `breakout_xlk`'s standalone
1Hour edge does not survive 2024-26 OOS, and fusion does not rescue it.

## Secondary finding — the "+0.10pp median-return" gate is unreachable here (gate-mismatch, not signal failure)

At the bench's $100-fixed-notional / $1000-book sizing, a single round-trip moves
equity by a fraction of a percent, so **per-window median returns sit in basis
points** (solo QQQ median-window = +0.006%, solo XLK = +0.009%). The
`MUTATION_MIN_DELTA_PCT = +0.10pp` delta gate is ~10–20× the entire signal
magnitude — **no 1Hour ETF strategy can clear it at this sizing.** This is the
**identical gate-mismatch** that closed the UUP lane (per MEMORY.md: "per-window
returns max out … round to 0.00% against the equity-calibrated median-return
gate"). For 1Hour ETF combos the honest gate is **FP-continuous Sharpe vs the
underlying-ETF buy&hold**, which is what this verdict binds on. Flagging so the
"+0.10pp median" gate isn't reflexively applied to intraday ETF lanes again.

## What this confirms / adds to the combo doctrine

1. **Cross-symbol fusion does not escape the dilution trap.** Yesterday's verdict
   showed same-symbol LLM-prose fusion dilutes; this shows deterministic
   *cross-symbol* fusion of a strong breakout + a genuinely orthogonal
   (different-ETF) momentum signal **also** dilutes — AND by over-restriction,
   OR by closet beta. The "strong + weak-orthogonal" escape hatch the prior
   verdict speculated about **does not pan out at the signal level.**
2. **The only place this pairing could help is the BOOK level** (allocator /
   sleeve weighting across the three as separate sleeves), not inside one
   `decide()`. That matches the standing doctrine (combine at book level where
   diversification helps; signal-level fusion dilutes).
3. **`breakout_xlk` is OOS-fragile on 1Hour** (negative 2024-26). Worth a
   separate note for the live roster — its strong reported WF Sharpe is
   IS/median-of-windows flattery; FP-continuous OOS is negative.

## Artifacts (all in workspace, no orders placed, hard rails untouched)

- `_combo_fusion_lib.py` — cross-symbol fusion harness (AND/OR, D+1 + canary lag,
  no-lookahead aligned IWM-MACD lookup, reuses live `_macd()`).
- `_combo_fusion_driver.py` → `_combo_fusion_results.json` — full grid (solo +
  AND + OR × base + canary × 2 primaries, IS/OOS, median-windows, FP-Sharpe).
- `_combo_qqq_or_diag.py` → `_combo_qqq_or_diag.json` — exposure/closet-beta
  diagnostic that settles the QQQ-OR lift.
- `_combo_xlk_check.py` — XLK exposure/OOS check.
- Paper-only + `STOP_TRADING` killswitch intact; no spend.
