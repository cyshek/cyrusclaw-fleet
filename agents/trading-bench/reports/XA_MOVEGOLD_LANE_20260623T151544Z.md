# XA_MOVEGOLD — Cross-Asset MOVE / Gold-Copper Regime Overlay — LANE REPORT

**UTC:** 2026-06-23T15:15:44Z
**Agent:** research subagent (lane-xa-movegold) for Tessera (trading-bench)
**Scope:** candidate/read-only — NO live strategies, crontab, paper-clock, or promote touched; NO protected/evaluator edits.
**Scratch:** `strategies_candidates/xa_movegold/{strategy.py,params.json}`
**Driver:** `reports/_xa_movegold_driver.py` (throwaway; composes PUBLIC `backtest_xsec` + `fp_continuous_sharpe` + a cost-honest deep-OOS vector backtest)
**Prereg:** `reports/_XA_MOVEGOLD_PREREG.md` (written BEFORE any backtest)
**Results JSON:** `reports/_xa_movegold_results.json`

## VERDICT: **CLOSE** (clean, honest negative)

**The one decisive number:** across the **54-cell** pre-registered sweep, on the honest total-return traded path, **0 of 54 cells beat BH-SPY on the full period (2003–2026)** and only **2 of 54 beat on the frozen OOS test (≥2019)** — and both of those win **only at ~85%/77% deployed capital** (closet-beta), while the single best one (`move_z` trend W63 t1.5) **LOSES the train split (2003–2018) by −147pp** and **loses the full period by −437.6pp** (+698% vs BH +1136%). A cell that loses in-sample-train and "wins" only in the test window is a regime-specific fluke, not a timing edge.

---

## 1. Protected-file integrity (verified before AND after — UNCHANGED)

```
                     BEFORE                            AFTER
runner.py        3811c37be962ea818e9958da675b1a03  ==  3811c37be962ea818e9958da675b1a03  ✓
risk.py          e4c227e019c99e7e52224eb2f91389b8  ==  e4c227e019c99e7e52224eb2f91389b8  ✓
backtest.py      ac0c579f8a20d11724879278a610fbb4  ==  ac0c579f8a20d11724879278a610fbb4  ✓
backtest_xsec.py fd39e011087d6e0295da83efbe858819  ==  fd39e011087d6e0295da83efbe858819  ✓
broker_alpaca.py 2d82c8106496e7c80636684d2299cc89  ==  2d82c8106496e7c80636684d2299cc89  ✓
```
Eval = the existing `fp_continuous_sharpe` over the canonical 8-window `NAMED_WINDOWS` panel, $1000 notional, active `CostModel.alpaca_stocks()` (spread 2bps one-way), single-name deployment through PUBLIC `backtest_xsec`. The deep-OOS path is a self-contained long/flat vector backtest on SPY `adjclose` total-return with the IDENTICAL 2bps-each-side cost on every flip — zero eval reimplementation, zero protected-file touch.

## 2. Why this lane was new (not a re-dig of closed lanes)

Prior REJECTS used either equity-derived inputs or growth/credit/curve ETF momentum:
- `macro_nowcast` (FP +0.501) — growth/credit/curve ETF momentum + SPY/TLT/GLD rotation.
- `dollar_leadlag` (FP +0.547) — DXY/UUP.
- VIX-overlay / VIXTERM / SKEW — **equity** vol.

**None tested BOND-MARKET VOLATILITY (`^MOVE`, the rates analog to VIX) or the Gold/Copper growth-vs-fear ratio.** That orthogonal angle is what this lane tested. Confirmed below: the signal genuinely IS orthogonal (clean relabel + clean orthogonality diagnostics) — it just doesn't time SPX well enough to beat raw BH on the honest path.

## 3. Data & point-in-time honesty (all market-priced → PIT by construction)

| Symbol | n | span | role |
|---|---|---|---|
| `^MOVE` | 5835 | 2002-11-12 → 2026-06-18 | Treasury rate vol — SIGNAL |
| `GC=F` / `HG=F` | 6476 / 6481 | 2000-08 → 2026-06 | gold / copper — SIGNAL (GC/HG ratio) |
| `^VIX` | 9186 | 1990-01 → 2026-06 | equity vol — SIGNAL (MOVE/VIX) |
| `SPY` (adjclose) | 8406 | 1993-01 → 2026-06 | traded path (deep OOS) |
| `QQQ`,`TLT`,`GLD`,`TQQQ` | deep | — | alt traded / off-asset / diag |

All inputs are market-priced daily closes → knowable EOD that day, never revised → **no release-lag/revision surface, no lookahead from the data itself.** `adjclose` used for the traded path (total-return compounding).

**STRICT anti-lookahead (pre-committed & enforced):** at a traded bar dated `d`, the signal reads ONLY signal closes dated **`< d`** (STRICT), via `daily_bars_cache.asof_strict` semantics replicated in the strategy's `_strict_prior_slice`. We chose `< d` (not `<= d`) — the more conservative option — so no same-day close can inform a same-day fill. Verified by smoke test: e.g. 2020-03-20 MOVE z=+3.13 (extreme bond stress → risk-OFF), 2025-04-10 Gold/Copper z=+4.34 (growth-fear spike) — economically correct, computed strict-prior.

### Stated harness constraint (not a leak)
`backtest_xsec` fetches **traded** symbols via `bars_cache.get_bars` (Alpaca IEX), which only reaches ~2018-11 (SPY) / ~2020-07 (QQQ/TLT/GLD) — identical to what `macro_nowcast` faced. So the 8-window panel is in-sample 2022–2026. To get a genuine frozen OOS split (train≤2018 / test>2018), the deep path uses `daily_bars_cache` adjclose (deep to 2003) for BOTH signal and traded path, cost-honest. The SIGNAL is never starved (deep to 2002); only the Alpaca panel is bounded.

## 4. Sweep grid (pre-registered: 3 signals × 2 signs × 3 windows × 3 thresholds = 54 cells)

Signals: `move_z` (MOVE level z), `movevix_z` (MOVE/VIX z), `goldcopper_z` (GC/HG z). Both signs (trend = high z → risk-OFF; contrarian = inverse). W∈{63,126,252}, thr∈{0.5,1.0,1.5} z-units. Timing {SPY} long/flat. (Rotate {SPY,TLT,GLD} also wired; reported below.)

### 4a. PANEL (8-window NAMED_WINDOWS, in-sample 2022–2026) — proven-honest pattern
**Bench: BH-SPY FP-cont = +0.5478** (8 windows).

| rank | FP-cont | avg deploy | ann-on-deployed | beats-BH wins | params |
|---|---|---|---|---|---|
| 1 | **+1.2577** | 0.553 | +9.13% | 4/8 | movevix_z trend W252 t0.5 |
| 2 | +1.0730 | 0.340 | +7.49% | 3/8 | goldcopper_z **contrarian** W126 t1.0 |
| 3 | +0.8784 | 0.415 | +6.87% | 3/8 | goldcopper_z contrarian W63 t0.5 |
| 7 | +0.7549 | 0.850 | +6.72% | 4/8 | move_z trend W252 t1.5 |

On the in-sample panel several cells clear the BH-SPY FP bench — but the panel is 2022–2026 in-sample only (Alpaca-bounded) and **cannot be trusted as OOS**. The OOS test below is what counts, and it kills the lane.

### 4b. DEEP OOS (SPY adjclose total-return 2003–2026, cost-honest, frozen train≤2018 / test≥2019)

Sorted by TEST raw return (top cells):

| TEST ret | vs BH (+228.0%) | beat? | test exp | FULL ret | vs BH (+1136%) | params |
|---|---|---|---|---|---|---|
| +247.3% | **+19.3pp** | ✅ | 0.847 | +698% | **−438pp** | move_z trend W63 t1.5 |
| +229.7% | +1.7pp | ✅ | 0.766 | +530% | −606pp | move_z trend W63 t1.0 |
| +214.6% | −13.4pp | ❌ | 0.678 | +765% | −371pp | move_z trend W63 t0.5 |
| +210.3% | −17.8pp | ❌ | 0.832 | +638% | −498pp | move_z trend W252 t1.5 |
| +203.7% | −24.4pp | ❌ | 0.860 | +942% | −194pp | movevix_z trend W126 t1.5 |

**Tally: 54 cells | TEST-beat-BH: 2 | FULL-beat-BH: 0 | BOTH: 0.**

## 5. THE FOUR KILLER DIAGNOSTICS (numbers, honest)

### (a) RELABEL CHECK — **PASSES (genuinely NOT a relabel)**
corr(signal z, SPY 60d trailing return) and corr(signal z, SPY 20d realized vol), dense grid n=1885 over 2004–2026:

| signal | corr vs SPY return | corr vs SPY vol |
|---|---|---|
| move_z W126 | −0.313 | +0.331 |
| movevix_z W126 | +0.373 | −0.280 |
| goldcopper_z W252 | −0.377 | **+0.462** (max) |

**Max |r| = 0.462 < 0.5** across all 9 signal/window combos. The MOVE / Gold-Copper signals are **NOT disguised SPY price/vol relabels** — they are genuinely exogenous cross-asset structure. (Same honest finding as macro_nowcast: the signal is real, it just doesn't predict forward returns well enough.)

### (b) CLOSET-BETA CHECK — **FAILS (this is the kill)**
- **NO cell beats BH-SPY with deployed fraction < 70%.** The only 2 cells that beat BH on the OOS test do so at **0.847 and 0.766 deployed** — i.e. they "win" by staying ~80% invested in a bull-heavy 2019–2026, the textbook FINRA closet-beta failure mode.
- `corr(exposure, excess_ret)` is near-zero (test −0.020, full +0.022) — but that's an artifact of binary 0/1 timing exposure (when fully deployed, excess vs SPY ≈ 0; when flat, excess = −SPY). The decisive closet-beta tell the brief asked for is the **"no win below 70% exposure"** result: every beat requires near-full investment, so there is no timing alpha, only beta-when-it-paid.
- All lower-exposure (more "timing-active") cells underperform BH; the contrarian gold/copper cells run 0.34–0.46 exposure and land +92–99% test vs BH +228% — they lose by ~130pp precisely because they de-risk and miss the bull.

### (c) ORTHOGONALITY-TO-WHAT-WE-RUN — **PASSES (genuinely orthogonal, but doesn't matter given it loses)**
corr(this signal's risk-on/off state, SMA-200-gate state on QQQ) and corr to 20d-vol-target exposure on TQQQ, n=4094 over 2010–2026:

| config | corr vs SMA-200 state | corr vs vol-target exp |
|---|---|---|
| deep-best (move_z W63 t1.5) | 0.132 | 0.171 |
| move_z trend W126 t1.0 | 0.224 | 0.264 |
| goldcopper trend W126 t1.0 | 0.205 | 0.252 |

Low correlations (0.13–0.26) → the MOVE/GoldCopper state is **NOT a re-skin of SMA-200 or vol-target** (both already live in `leveraged_long_trend_paper` + `tqqq_cot_combo`). It IS additive/orthogonal in state-space — but since it fails to beat raw BH (§4b) and only "wins" via closet-beta (§b), orthogonality buys nothing here.

### (d) KNIFE-EDGE vs PLATEAU — **KNIFE (second independent kill)**
The OOS "winners" are an isolated argmax, not a ridge. Within `move_z` trend:

| W | t0.5 | t1.0 | t1.5 |
|---|---|---|---|
| 63 | −13.4pp ❌ | +1.7pp ✅ | **+19.3pp ✅** |
| 126 | (−)❌ | −48.8pp ❌ | −71.0pp ❌ |
| 252 | −75.1pp ❌ | −66.2pp ❌ | −17.8pp ❌ |

The only beats live at **W63 only**, and even there flipping thr 1.5→0.5 turns the win into a loss. W126/W252 are uniformly losses. There is **no broad, sign-stable plateau** — the single +19.3pp cell is an isolated spike at one corner of the grid. Worse: that same cell **loses the TRAIN split by −147pp** (Sharpe 0.415 vs BH 0.548), so its OOS "win" is not even train-consistent — the hallmark of overfit, not edge.

## 6. The macro_nowcast trap — checked, avoided
We compared ONLY to **total-return BH-SPY on the identical traded path** (not `^GSPC` price-only). Against price-only `^GSPC`, a low-exposure overlay can look like a beat; against total-return BH it loses. Every number above is vs total-return BH. The lane fails the honest comparison.

## 7. Verdict — **CLOSE** (honest negative = success)

Against the pre-registered rubric, the lane fails 2 of the 5 PROMOTE conditions outright and is marginal on a 3rd:
1. **Beats SPX raw OOS?** ❌ — only 2/54 on test, 0/54 full; the best is a train-losing, full-period-−438pp fluke.
2. **Survives relabel?** ✅ — max |r| 0.462 < 0.5; genuinely not a price/vol relabel.
3. **Survives closet-beta?** ❌ — NO cell beats BH below 70% deployment; both "wins" are ~80% invested.
4. **Survives orthogonality?** ✅ — corr to SMA-200/vol-target only 0.13–0.26; genuinely additive in state-space.
5. **Plateau not knife?** ❌ — single isolated W63 argmax; train-inconsistent; no sign-stable ridge.

**Decisive number restated:** `corr(exposure, excess_ret) ≈ 0` with **no BH-beat anywhere below 70% deployed capital, 0/54 cells beating BH full-period, and the lone OOS winner losing its own train split by −147pp.** Bond-market volatility (`^MOVE`) and the Gold/Copper ratio are real, orthogonal, non-relabel regime signals — they simply do not time forward SPX returns well enough to beat raw buy-and-hold on the honest, cost-net traded path. Same structural ceiling as every prior overlay.

**Cumulative finding:** this extends the slate's pattern — even a genuinely orthogonal, non-relabel EXOGENOUS cross-asset signal (rate-vol + commodity growth/fear) tops out unable to beat raw BH-SPY net of costs. The eval surface continues to cap long/flat equity-timing overlays below the raw-return bar. **No promotion. Zero promotion authority exercised.**

---
*Artifacts: `strategies_candidates/xa_movegold/{strategy.py,params.json}`, `reports/_xa_movegold_driver.py`, `reports/_xa_movegold_results.json`, `reports/_XA_MOVEGOLD_PREREG.md`, `reports/_xa_movegold_run.log`. No protected/evaluator file changed (md5 verified identical, §1).*
