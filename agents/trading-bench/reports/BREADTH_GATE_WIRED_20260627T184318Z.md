# TQQQ vol-target sleeve — SMA-breadth gate WIRED (config change record)

**Date:** 2026-06-27 (record stamp 20260627T184318Z)
**Author:** Tessera (trading-bench)
**Authorized by:** main (Sat 11:30 AM check-in → explicit go after I flagged the two caveats)
**Type:** PAPER config change (gate-logic upgrade on the standalone TQQQ vol-target sleeve). No live orders, no spend.

---

## What changed

The standalone TQQQ vol-target sleeve `strategies/leveraged_long_trend_paper/` had a
**binary SMA-200 trend gate** (QQQ close > 200d SMA → risk-on, else flat). It is now
an **opt-in multi-horizon SMA-breadth participation gate**:

```
g = (# of {30, 90, 180}d SMAs the QQQ close is above) / 3   ∈ {0, 1/3, 2/3, 1}
w = clamp(g * voltarget_weight, 0, w_max)        # breadth MULTIPLIES the vol-target weight
```

- New param `breadth_windows: [30, 90, 180]` in `params.json`.
- New helper `breadth_gate_scaler()` in `strategy.py` (verbatim mirror of the validated
  tiebreak driver's `make_breadth_scaler`).
- **Non-destructive / reversible:** absent or empty `breadth_windows` falls back to the
  single-window binary SMA-200 gate, bit-identical to prior behaviour. Remove the
  `breadth_windows` key to revert.
- `vix_gate=false`, `target_vol=0.25`, `w_max=1.0`, all other params UNCHANGED.

## Why (validated edge — engine-confirmed, NOT recollection)

From the 2026-06-27 ens_sma_breadth tiebreak (`reports/_ens_breadth_tiebreak_result.json`,
full engine parity max|Δequity|=0 over 4118 days), under the **LIVE convention
(vix_gate=False, continuous-slice OOS @2018)**:

| metric | binary SMA-200 (base) | breadth {30,90,180} | delta |
|---|---|---|---|
| OOS fp-Sharpe | 0.8369 | 0.8551 | **+0.0183** |
| OOS+canary fp-Sharpe | 0.8644 | 0.9200 | **+0.0556** (canary SURVIVES → not a leak) |
| OOS maxDD | −34.52% | **−22.55%** | **+11.97pp shallower** |
| OOS total return | +363.0% | +315.2% | −47.8pp |
| IS fp-Sharpe | 0.8488 | 0.7786 | −0.0702 (gives up Sharpe in-sample) |

**Read:** the win is **drawdown compression** (−11.97pp) with a small POSITIVE and
**canary-robust** OOS Sharpe edge. It costs ~48pp of OOS total return and gives up Sharpe
in-sample — this is a risk-reducing refinement, not a return amplifier. Faster-horizon
breadth de-risks sooner on a roll-over without the binary gate's all-or-nothing cliff.

**No sign-conflict trap:** the {50,100,200} triple's apparent "pass" was a vix_gate=True
artifact (wrong baseline). {30,90,180} was validated on vix_gate=False = the live config,
and was the only one of 8 nearby triples to clear under the live convention.

## Verification done (this session)

1. **Scaler parity (`reports/_verify_breadth_wiring.py`):** the live `strategy.py`
   `breadth_gate_scaler` produces **bit-identical g values** to the validated oracle across
   all 4118 decision days — `max|g_live − g_oracle| = 0.000e+00`, 0 mismatches, for both
   {30,90,180} and the {200} binary fallback.
2. **End-to-end via validated `simulate()`:** swapping the live scaler into the proven
   harness reproduces every headline metric to **Δ = 0.00e+00** — OOS Sharpe +0.855135,
   maxDD −22.550109%; canary OOS +0.920012; base OOS +0.836853 / −34.523587%.
3. **Runtime smoke (`reports/_smoke_breadth_decide.py`):** `decide()` executes without
   exception across plumbing-gap (fail-safe flat), uptrend (g=1.0), downtrend (g=0.0), and
   mixed-breadth cases. Gate notes correctly emit `breadth{30/90/180}` with the live g.
4. **Integrity:** `runner/backtest.py`, `runner/risk.py`, `runner/runner.py` md5sums
   UNCHANGED (717c36e6… / e303317e… / 0f763975…). No `*.db` written. Killswitch absent.
   Only `strategies/leveraged_long_trend_paper/{strategy.py,params.json}` modified.

## Scope caveats (flagged to main, recorded here)

- **The standalone sleeve does not trade live.** Per `RUNNER_PLUMBING_GAP.md` it fails-safe
  to FLAT and no-ops every tick (runner supplies SPY-only regime + TQQQ-only bars; the QQQ
  gate input is missing). This config change is correct and validated, but it produces no
  live fills until the QQQ-closes plumbing lands — a **separate runner decision**, untouched
  here. There is therefore no fill-level paper-tracker DB to append to; THIS markdown is the
  config-change/validated-numbers record.
- **The live-firing `allocator_blend` sleeve A is NOT affected.** It imports the engine
  (`run_backtest_voltarget`) + `allocator_paper_tracker` directly, not this `strategy.py`.
  Porting the breadth gate into the allocator's vol-target sleeve would be a separate edit
  (engine or allocator) — a follow-on decision if main wants it.

## Files

- Modified: `strategies/leveraged_long_trend_paper/strategy.py` (+`breadth_gate_scaler`,
  breadth weight path), `strategies/leveraged_long_trend_paper/params.json`
  (+`breadth_windows: [30,90,180]` + note).
- Verification (read-only, reports/): `_verify_breadth_wiring.py`, `_smoke_breadth_decide.py`.
- Source of truth for the edge: `reports/_ens_breadth_tiebreak_driver.py` +
  `reports/_ens_breadth_tiebreak_result.json` + `ENS_BREADTH_TIEBREAK_20260627T074651Z.md`.
