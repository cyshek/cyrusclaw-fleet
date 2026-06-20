# CROSS-ASSET CARRY / TERM-STRUCTURE — VIX roll-yield harvest

**UTC:** 2026-06-04T05:15:49Z
**Author:** trading-bench subagent (lane 2 of `reports/RESEARCH_SLATE_20260603.md` — cross-asset carry / term-structure)
**Scratch:** `strategies_candidates/carry_termstructure/` (strategy.py + params.json)
**Driver:** `reports/_carry_termstructure_driver.py` (throwaway; import-only, composes PUBLIC `runner.backtest_xsec` + canonical `runner.fp_sharpe.fp_continuous_sharpe` over the 8 `NAMED_WINDOWS`, active Alpaca cost model — same composition pattern as `reports/_vol_r3_driver.py`). NO protected/evaluator file edited.
**Verdict:** ❌ **REJECT — conclusive.** Best FP-continuous-span Sharpe across the entire 90-cell grid is **+0.031**, median **−0.181**, only **4/90** cells positive, **ZERO** cells clear 0.5 let alone the **1.0** front door. The carry signal adds essentially nothing over passively holding the short-vol leg (BH-SVXY FP-cont **+0.032**). No plateau — a sea of negative cells with a couple of 6-trade near-zero knife-edges. **Honest REJECT = success.**

---

## 0. Protected-file integrity (verified at finish)

```
runner.py        4be185e4bdcb6f432d99b71b21a4859c   ✓ unchanged
backtest.py      9444ee5be64d9fd2639fd8cb0a28e002   ✓ unchanged
backtest_xsec.py 2278a4c8d8a66703da5cd6f2a0880061   ✓ unchanged
risk.py          e4c227e019c99e7e52224eb2f91389b8   ✓ unchanged
```
(Re-verify with `md5sum runner/{runner,backtest,backtest_xsec,risk}.py` — values above match the task contract.)

---

## 1. Data-availability note

Confirmed fetchable via the existing `runner.bars_cache.get_bars` path (Alpaca IEX), end_dt 2026-05-25, daily bars:

| symbol | bars | span | role |
|---|---|---|---|
| VIXY | 1464 | 2020-07-27 → 2026-05-22 | signal: front/short-term vol ETF |
| VIXM | 1412 | 2020-07-27 → 2026-05-22 | signal: mid-term vol ETF |
| SVXY | 1464 | 2020-07-27 → 2026-05-22 | **traded leg** (short-vol, structurally long the roll carry) |
| VXX  | 1464 | 2020-07-27 → 2026-05-22 | (alt long-roll leg, not traded here) |
| SPY  | 1464 | 2020-07-27 → 2026-05-22 | bench reference |

All share the same 2020-07-27 IEX floor (~5.8 yrs). **No data blocker** — the primary candidate instruments are all available. (This matches the VIXM/VIXY availability already noted in `VOL_REGIME_R3_20260602T011741Z.md`.)

---

## 2. Signal definition — and why this is CARRY, not vol-level TIMING

**Carry gauge:** `R = VIXY / VIXM` (front short-term vol ETF ÷ mid-term vol ETF).
- `R` low / curve upward = **contango** (front cheaper than mid). The VIX futures curve sits in contango the large majority of the time; a long-vol roll holder **pays** that contango as structural decay, so the **short-vol** side (SVXY) is **paid** the roll yield just for holding through the curve.
- `R` high (≳1) = **backwardation** (curve inverted, acute stress). Now the roll **pays** the long and **charges** the short-vol holder → step aside.

**Strategy (`decide_xsec`):** purely term-structure SHAPE driven.
- Maintain trailing SMA of `R` over `ratio_lookback`.
- **HOLD SVXY** (harvest roll) while in contango: `R ≤ enter_mult·SMA(R)·(1−band)` AND `R < exit_level`.
- **FLAT** while backwardated: `R ≥ exit_level` (or `R` drifts above its own norm by the band) → close.
- Sweep grid: `ratio_lookback ∈ {20,40,60,90,120}` × `enter_mult ∈ {0.95,1.00,1.05}` × `exit_level ∈ {0.95,1.00,1.05}` × `band ∈ {0,0.05}` = **90 cells**.

**Explicit carry-not-timing argument (and how it is enforced):**
1. The P&L driver is the **roll/decay** collected by holding SVXY through contango — a structural payment for bearing the term-structure shape — NOT a forecast of where vol or SPX will move.
2. We **never go long vol** on spikes and we **never size by vol LEVEL**. The two failure modes that define the *rejected* vol-regime/R3 lane (de-risk SPY when vol is high; proportional inverse-vol SPY sizing) are absent. We only HOLD the roll-harvest leg while the curve PAYS us and stand FLAT while it would CHARGE us.
3. The decision variable is `R` vs **its own trailing norm** (shape), not an absolute vol level or a price-direction signal.

**Important honesty caveat surfaced by the data (see §3):** even though the *design* is structurally carry, on this instrument the realized return is dominated by SVXY's own brutal drawdowns (−40%+ single-window swings). When the carry edge is invisible against that noise, the construction provides no robust harvest. So the lane does NOT collapse into the dead vol-timing lane — it is a *genuinely different* (carry) construction — it simply **fails on its own terms**: the roll yield, net of the spike risk you must hold through, is not a tradeable risk-adjusted edge here.

---

## 3. Results — full 90-cell sweep (FP-continuous-span Sharpe, active cost)

**Benchmarks (single-name `backtest_xsec`, same panel, buy-once):**
- **BH-SPY FP-cont = +0.250** (canonical, per `VOL_REGIME_R3` same NAMED_WINDOWS path; SPY not inside this lane's fetched basket so the in-driver SPY bench reads empty — the +0.250 reference is the binding SPX-relative number).
- **BH-SVXY FP-cont = +0.032**, 8 trades — passively holding short-vol earns ~nothing risk-adjusted: the roll yield is eaten by the spike drawdowns.
- **BH-VIXY FP-cont = +0.452**, 8 trades — (the *long* vol-roll leg; bench only, not a strategy — its positive number here is the 2020-26 vol-spike path, not a carry edge.)

**Grid distribution:**

| metric | value |
|---|---|
| cells | 90 |
| FP-cont **max** | **+0.031** |
| FP-cont median | −0.181 |
| FP-cont min | −0.561 |
| cells FP > 0 | 4 / 90 |
| cells FP ≥ 0.5 | **0** |
| cells FP ≥ 1.0 (front door) | **0** |

**Top cells (all are noise, not a plateau):**

| FP-cont | trades | avg deploy | worst-inst DD | params |
|---|---|---|---|---|
| +0.031 | 6 | 0.27 | −0.5% | lb90, em1.05, ex0.95, band0.05 |
| +0.031 | 6 | 0.27 | −0.5% | lb90, em1.05, ex1.00, band0.05 |
| +0.031 | 6 | 0.27 | −0.5% | lb90, em1.05, ex1.05, band0.05 |
| +0.024 | 88 | 0.22 | −0.1% | lb40, em0.95, ex1.05, band0.0 |

The three +0.031 cells fire only **6 trades** over 5.8 years and their FP is dominated by two offsetting windows (2023-H1 **+27.96%** / 2024-Q2 **−42.72%**) — a coin-flip, not an edge. The one higher-activity positive cell (+0.024, 88 trades) is statistically indistinguishable from zero. Per-window SVXY swings of +28% / −43% / −20% confirm the realized P&L is governed by short-vol's own volatility, not by a harvested roll premium.

---

## 4. Plateau vs knife-edge classification

❌ **No plateau anywhere.** The grid is overwhelmingly negative (median −0.181; 86/90 cells ≤ 0). The only positive cells are isolated:
- The +0.031 trio shares `em1.05, band0.05` and survives only at `lb90` — neighbors (`lb60`, `lb120`, `band0`) collapse to negative (e.g. `lb120, em1.05` → **−0.174**). That is a textbook **knife-edge**, and even the knife-edge peak is +0.031 ≈ zero.
- The +0.024 cell (`lb40, em0.95, ex1.05`) flips negative at adjacent `ex1.0` (−0.018) — also isolated.

There is no contiguous region of robust positive Sharpe to stand on. By the sweep's own plateau-vs-knife rule, this lane produces **knife-edges at the noise floor**, which is a fail.

---

## 5. SPX-relative comparison

| construction | FP-cont Sharpe | vs BH-SPY (+0.250) |
|---|---|---|
| BH-SPY (canonical) | +0.250 | — |
| **Best carry cell** | **+0.031** | **−0.219 WORSE** |
| BH-SVXY (passive short-vol) | +0.032 | −0.218 worse |
| Grid median | −0.181 | −0.431 worse |

The best carry configuration is **worse, risk-adjusted, than simply buying and holding SPY**, and is no better than passively holding SVXY with no signal at all (+0.031 vs +0.032). **The term-structure carry signal contributes zero alpha** over the passive short-vol hold, and the passive short-vol hold itself is sub-SPX. On a raw-return basis the construction is also un-investable: single-window drawdowns of −30% to −43% on the deployed leg.

---

## 6. Verdict

❌ **REJECT — conclusive and honest.**

- Front door (FP-cont Sharpe ≥ 1.0 on a robust plateau, net of cost): **FAIL** by a wide margin — best cell +0.031, nothing ≥ 0.5, no plateau.
- SPX-relative: **FAIL** — best cell (+0.031) is below BH-SPY (+0.250) and adds nothing over passive BH-SVXY (+0.032).
- Knife-edge vs plateau: **knife-edges only, at the noise floor.**
- Carry-not-timing discipline: **maintained** — the construction did NOT drift into the rejected vol-level/inverse-vol-SPY-sizing lane. It is a genuinely distinct carry design that **fails on its own merits**: the VIX-term-structure roll yield, net of the spike drawdowns you must hold through (and net of cost), is not a tradeable risk-adjusted edge on the instruments available to us (VIXY/VIXM/SVXY).

**Secondary carry proxies (bond/commodity roll):** NOT pursued — the primary VIX-term-structure result is decisive enough (max +0.031 across 90 cells, zero plateau) that the lane's headline thesis is refuted; spending budget on a second roll proxy is unlikely to clear a 1.0 front door given how far short the strongest, most-studied carry instrument fell. Flagged as available-if-revisited, not silently failed.

**Promotion authority:** NONE. Candidate stays in `strategies_candidates/carry_termstructure/`. No file promoted; nothing posted to any channel.

---

### Pattern note for the slate
Carry/term-structure now joins price-xsec, vol-regime-timing, credit-regime, PEAD, and dollar-lead-lag as a REJECTED lane. The VIX-roll carry premium is real in theory but, on retail-accessible ETF wrappers (VIXY/VIXM/SVXY) over 2020-2026, it is swamped by the wrapper's own crash risk and does not survive net of cost on any robust plateau. Consistent with the slate's standing read: edge, if it exists, is in **non-price / harder-to-access / structurally-uncrowded** signals — not in another price- or vol-derived wrapper.
