# Macro-Gate v2 — `sma_crossover_qqq_macrogate` (orthogonal macro ENTRY GATE)

**Date:** 2026-06-08
**Author:** trading-bench subagent (`build-macrogate-v2`)
**Status:** CANDIDATE (paper/quarantine). NOT promoted, NOT on `strategies/` live, `GATE_PASSING_PARENTS` untouched.
**Candidate path:** `strategies_candidates/sma_crossover_qqq_macrogate/{strategy.py, params.json, __init__.py}`
**Test:** `tests/test_macrogate_v2.py` (9 tests, all green; no network — macro_cache monkeypatched)

## TL;DR — VERDICT: NEGATIVE. Do NOT promote.

The orthogonal macro acceleration gate **fails the fitness gate** and is a clear **risk-adjusted DEGRADATION** of its un-gated parent. It does exactly the thing the brief warned against: it lowers volatility by sitting in cash, but it does so by **chopping off the profitable 2023–2024 bull entries**, not just the 2022 bear bleed. Lower vol bought with lost return is not edge.

| metric | baseline `sma_crossover_qqq` | `…_macrogate` (v2) | delta |
|---|---|---|---|
| fitness gate | **PASS** | **FAIL** | — |
| median return % | **+0.313** | −0.013 | **−0.33pp** |
| median Sharpe | **+2.599** | −0.638 | **−3.24** |
| total trades (8 windows) | 142 | 48 | −94 |
| % windows positive | 62% | 25% | −37pp |
| % beat BH-SPY | 88% | 62% | −26pp |
| stdev of window returns | 1.016 | **0.739** | −0.28 (lower vol) |
| worst window % | −1.432 | **−0.355** | +1.08 (smaller DD) |
| best window % | +1.963 | +1.963 | 0 |

The **only** columns the gate improved are stdev and worst-window — i.e. it cut downside variance. But median return collapsed to ~0 and median Sharpe went **negative**. That is the textbook "de-risk into cash and call it alpha" anti-pattern; it is not a parent candidate.

---

## Design

**Base behavior** = identical to `strategies/sma_crossover_qqq` — 10/30 SMA cross on QQQ 1h bars (`fast=SMA(closes,10)`, `slow=SMA(closes,30)`; `fast<slow & holding → close`; `fast>slow & flat → candidate buy`). The close/exit branch is **byte-for-byte the parent's and always runs first**, so a bearish cross is honored before the macro gate is ever consulted — the gate can never trap us long.

**The only addition** = an orthogonal macro ENTRY gate (mirrors how `sma_crossover_qqq_regime` gates entries with the SPY-trend regime, except the gate source is macro, not SPY price):

> A new long opens only when the bullish SMA cross fires **AND** macro is risk-ON. If macro is risk-OFF, the bullish cross returns `hold` (entry blocked). A `close` is **never** blocked.

**Macro risk-ON (v2 = ACCELERATION — the fix for v1's flaw):**

```
risk_on = (liq_accel > liq_accel_min) AND (curve > curve_min)
  liq_accel = liq_slope_asof(as_of, 13w) − liq_slope_asof(as_of − 91d, 13w)
  curve     = curve_spread_asof(as_of)              # T10Y2Y, 10y−2y
```

`liq_accel` asks **"is the 13-week WALCL slope HIGHER than it was ~13 weeks ago — i.e. is the liquidity drag EASING / re-accelerating?"** Missing macro warmup (any leg `None`) ⇒ risk-OFF (fail-safe; block entries, still allow closes). Params: `liquidity_slope_weeks=13`, `accel_lookback_days=91`, `liq_accel_min=0.0`, `curve_min=−0.5`, plus the two FRED release-lag params.

### Why v2 (the acceleration rationale, and why it's the fix for v1)

v1 (`macro_regime_long`) failed for two diagnosed reasons (`reports/ORTHOGONAL_MACRO_STRATEGY_20260608.md`):
1. It gated on the **raw sign** of the 13-week WALCL slope (`liq_slope ≥ 0`). Through the 2022–2024 QT era that slope was **negative continuously**, so v1 sat in cash through the entire 2023–24 bull → no edge, just absence.
2. As a standalone hold-for-months overlay it produced only ~7 trades across 8 windows → couldn't satisfy a churn-calibrated gate.

v2 fixes both **mechanically**:
- **Trade frequency** comes from the churning base SMA cross; macro only filters entries. Trade-count problem solved (48 trades, not 7).
- **Acceleration, not level.** Instead of "any QT = cash", v2 says "QT that is *getting worse* = block; QT that is *easing* / liquidity re-expanding = let the cross trade." Empirically verified from this VM's FRED cache (weekly samples across each walk-forward window):

| window | regime | acceleration-gate risk-ON share |
|---|---|---|
| 2022-H1 | bear | 0/13 |
| 2022-Q3 | chop | 0/13 |
| 2023-H1 | bull | 1/13 |
| 2023-Q3 | chop | 0/13 |
| 2024-Q2 | bull | **4/13** |
| 2025-Q1 | bear | 10/13 |
| 2025-Q3 | bull | **13/13** |
| 2026-recent | bull | **8/9** |

So the gate **does** flip risk-ON across most of 2024–2025 (the bull v1 missed), and stays OFF through the 2022 / mid-2023 QT-acceleration phase — exactly as the brief described. The problem (see verdict) is that *the timing of that flip does not line up with where the base strategy actually makes money.*

### Anti-lookahead

Unchanged and inherited from `runner/macro_cache.py` (NOT modified by this candidate; `runner/backtest.py` md5 `9444ee5be64d9fd2639fd8cb0a28e002`, untouched). Each macro observation's effective-known date is shifted forward by its publication lag (WALCL +9d ≈ the H.4.1 Thu-after-ref-Wednesday gap; T10Y2Y same-day market quote) and, at each bar, only the value whose effective-known date ≤ the bar's date is returned. The acceleration's **far leg** (`as_of − 91d`) is resolved through the **same** lag filter, so even the lookback anchor is lag-correct. The as-of date is the current (latest visible) bar's date (`market_state["bars"][-1]["t"][:10]`). `market_state` carries bars+regime but NOT macro; the strategy wires macro itself (Option B), so the protected backtester is untouched. `macro_cache.selftest()` re-confirmed: 2020-COVID slope strongly positive (+2.92M), 2022-QT negative (−241k), lag shifts forward, effective-date ≤ as-of (no leak).

---

## A/B — both strategies through the SAME walk-forward gate

```
baseline   PASS | medRet=+0.313% medSharpe=+2.599 trades=142 pctPos=62% beatBH=88% stdev=1.016 worst=-1.432% best=+1.963%
macrogate  FAIL | medRet=-0.013% medSharpe=-0.638 trades=48  pctPos=25% beatBH=62% stdev=0.739 worst=-0.355% best=+1.963%
           FAIL reason: median return -0.01% ≤ +0.00%; only 25% of windows positive (need ≥50%); median Sharpe -0.64 ≤ 0.50
```

### Per-window — candidate (`sma_crossover_qqq_macrogate`)

| window | regime | bars | trades | return % | Sharpe | maxDD % | BH-SPY % | beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 526 | **0** | +0.000 | +0.000 | +0.000 | −1.711 | Y |
| 2022-Q3 chop | chop | 554 | **0** | +0.000 | +0.000 | +0.000 | −0.429 | Y |
| 2023-H1 recovery | bull | 549 | 4 | −0.025 | −1.276 | −0.067 | +0.653 | n |
| 2023-Q3 chop | chop | 561 | 1 | −0.069 | −2.765 | −0.141 | −0.359 | Y |
| 2024-Q2 bull | bull | 552 | 6 | −0.191 | −2.806 | −0.321 | +0.511 | n |
| 2025-Q1 tariff bear | bear | 504 | 11 | −0.355 | −1.728 | −1.129 | −0.827 | Y |
| 2025-Q3 bull | bull | 548 | 17 | +0.422 | +3.649 | −0.411 | +0.709 | n |
| 2026-recent bull | bull | 368 | 9 | +1.963 | +13.638 | −0.305 | +1.453 | Y |

### Per-window — baseline (`sma_crossover_qqq`), same windows

| window | regime | bars | trades | return % | Sharpe | maxDD % |
|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 526 | 24 | −1.432 | −5.887 | −1.683 |
| 2022-Q3 chop | chop | 554 | 20 | −0.119 | −0.525 | −1.010 |
| 2023-H1 recovery | bull | 549 | 21 | **+1.063** | +4.800 | −0.799 |
| 2023-Q3 chop | chop | 561 | 17 | **+0.203** | +1.549 | −0.442 |
| 2024-Q2 bull | bull | 552 | 15 | **+0.742** | +5.729 | −0.361 |
| 2025-Q1 tariff bear | bear | 504 | 19 | −0.395 | −1.844 | −1.130 |
| 2025-Q3 bull | bull | 548 | 17 | +0.422 | +3.649 | −0.411 |
| 2026-recent bull | bull | 368 | 9 | +1.963 | +13.638 | −0.305 |

### Fitness gate
- **baseline:** PASS (`passed`)
- **macrogate:** FAIL (`median return −0.01% ≤ +0.00%; only 25% of windows positive (need ≥50%); median Sharpe −0.64 ≤ 0.50`)

---

## Honest read — does the orthogonal macro filter add value? **No.**

Walk the windows side-by-side; the mechanism is unambiguous:

1. **Where the gate HELPED (2 windows):** 2022-H1 bear and 2022-Q3 chop. The acceleration signal was risk-OFF (0/13 both), so it blocked all entries → 0 trades, 0% return, instead of baseline's −1.43% and −0.12%. This is the gate working as designed: it avoided the deepest bear bleed. That is the source of the lower stdev (1.016→0.739) and smaller worst-window (−1.43%→−0.36%).

2. **Where the gate HURT (3 windows — and this is what sinks it):** 2023-H1 (+1.06%→−0.03%), 2023-Q3 (+0.20%→−0.07%), 2024-Q2 (+0.74%→−0.19%). These are precisely the **bull/recovery windows where baseline made its money.** The acceleration gate was still mostly risk-OFF here (1/13, 0/13, 4/13) because the WALCL slope, while improving, had not yet *accelerated above its own quarter-ago value* — so the gate **blocked the profitable bullish-cross entries** and let through only a handful of late, losing ones. The gate didn't just trim the bears; it amputated the bull alpha.

3. **Where the gate was TRANSPARENT (2 windows):** 2025-Q3 (+0.42%) and 2026-recent (+1.96%) — gate fully risk-ON (13/13, 8/9), traded identically to baseline. No harm, no help.

4. **Where the gate was USELESS (1 window):** 2025-Q1 tariff bear. The gate was risk-ON (10/13, because liquidity was easing into that selloff), so it traded straight through the bear and lost −0.36% (≈ baseline −0.40%). The macro signal gave **no protection** in this second bear — the one bear where help would have mattered, the gate was looking the wrong way.

**Net:** the gate's avoided losses (2022) are smaller in aggregate than the bull profits it forfeits (2023–24). The result is a strategy whose median return is ~0 and whose median Sharpe is **negative** — strictly worse than the parent on every return/edge axis, "better" only on the variance axes you get for free by holding cash. This is the canonical *"sitting in cash to lower vol is NOT edge"* outcome, and the fitness gate correctly rejects it.

### Why this is still a useful negative result
- It confirms v2's acceleration signal is **directionally real** (correctly off in 2022, on in 2025–26) and that the wiring/anti-lookahead is sound — the failure is **economic, not a bug**.
- The core lesson: an orthogonal macro *entry* filter only adds value if its risk-OFF periods correlate with the base strategy's *losing* entries. Here they don't — the gate is risk-OFF during 2023–24, which is when this particular base strategy was *winning*. The macro cycle and the SMA-cross edge are out of phase, so gating destroys more than it saves.
- Possible future directions (NOT pursued here; documented so we don't re-derive): (a) loosen the acceleration to a less-strict "slope improving OR above a floor" so 2023–24 bulls aren't blocked; (b) apply the gate as a **position-SIZE scaler** rather than a hard on/off, so risk-OFF de-risks partially instead of forgoing the trade entirely; (c) test the gate on a base strategy whose losses *do* cluster in QT-acceleration regimes (this one's don't). All are new experiments, not tweaks to promote this candidate.

**Bottom line: `sma_crossover_qqq_macrogate` is NOT a parent candidate.** It only trades return for vol, and the fitness gate's FAIL is correct. Recorded as a clean negative.

---

## Reproduce
```bash
cd /home/azureuser/.openclaw/agents/trading-bench/workspace
python3 /tmp/run_ab.py            # A/B driver (also dumps /tmp/macrogate_ab.json)
python3 -m pytest tests/test_macrogate_v2.py -q   # 9 green
python3 -m pytest tests/ -q                       # 351 green
md5sum runner/backtest.py        # 9444ee5be64d9fd2639fd8cb0a28e002 (untouched)
```
