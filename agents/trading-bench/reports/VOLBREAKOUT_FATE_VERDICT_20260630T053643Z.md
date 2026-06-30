# volume_breakout_qqq — FATE VERDICT: RETIRE (no-edge, not a config bug)

**Run:** 20260630T053643Z · **Agent:** trading-bench · **Mode:** paper-research (read-only sweep; verdict recommends a cron-line removal, executed separately with backup)
**Trigger:** Live-roster audit (`reports/LIVE_ROSTER_WF_AUDIT_20260630T053123Z.md`) flagged `volume_breakout_qqq` as inert live (0 trades ever) + a standing lookback-sanity WARN.
**Question:** Is there a `(volume_mult, exit_lookback)` config that makes it both pass the gate AND add real edge — or is it dead weight?

---

## TL;DR — RETIRE

I swept `volume_mult ∈ {1.2,1.5,2.0,2.5,3.0}` × `exit_lookback ∈ {8,17,25}` (15 cells) through the existing walk_forward harness. **Verdict: no config rescues it. RETIRE from the live cron.**

- **ZERO of 15 cells have positive SPY-relative alpha.** Every single variant — including the 7 that PASS the bench fitness gate and fire 46–92 trades — has a **negative information ratio (−0.50 to −0.59)** and **negative annualized SPY excess (−3.85% to −5.16%/yr)**. This is not a tuning problem; it's a **no-edge** problem. Every form loses to just holding SPY, risk-adjusted.
- The "inert live" symptom (0 live trades) was a red herring: the live config actually fires **63 trades in backtest** — it just hadn't triggered in the short, calm live window yet. The real finding is deeper and worse: **even when it trades plenty, it has no edge.**
- This is the **inverse of the `tqqq_cot_combo` lesson** from the same audit: there a gate FAIL hid a real winner (mis-measured leveraged sleeve); here a gate PASS hides a real loser (the long-only gate is blind to SPY-relative underperformance).

---

## The sweep (15 cells, full 8-window regime panel)

| volMult | exitLB | win | medRet% | %pos | beatBH | medShrp | **spyExc%/yr** | **medIR** | trades | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.2 | 8 | 8 | −0.04 | 38% | 38% | −0.22 | −5.00 | −0.58 | 171 | 🔴 FAIL |
| 1.2 | 17 | 8 | +0.02 | 50% | 50% | 0.12 | −4.10 | −0.55 | 120 | 🔴 FAIL |
| 1.2 | 25 | 8 | +0.12 | 50% | 75% | 0.54 | **−3.90** | **−0.51** | 92 | 🟢 PASS |
| 1.5 | 8 | 8 | +0.01 | 50% | 38% | 0.06 | −4.78 | −0.56 | 151 | 🔴 FAIL |
| 1.5 | 17 | 8 | +0.10 | 62% | 38% | 0.48 | −3.86 | −0.52 | 112 | 🔴 FAIL |
| 1.5 | 25 | 8 | +0.11 | 50% | 50% | 0.67 | −3.85 | −0.50 | 86 | 🟢 PASS |
| 2.0 | 8 | 8 | −0.05 | 38% | 38% | −0.35 | −5.16 | −0.59 | 123 | 🔴 FAIL |
| 2.0 | 17 | 8 | +0.02 | 50% | 50% | 0.09 | −4.25 | −0.54 | 94 | 🔴 FAIL |
| 2.0 | 25 | 8 | +0.06 | 50% | 62% | 0.25 | −4.16 | −0.52 | 74 | 🔴 FAIL |
| 2.5 | 8 | 8 | +0.07 | 62% | 50% | 1.02 | −4.86 | −0.57 | 89 | 🟢 PASS |
| 2.5 | 17 | 8 | +0.15 | 62% | 38% | 1.30 | −4.08 | −0.52 | 74 | 🔴 FAIL |
| 2.5 | 25 | 8 | +0.20 | 62% | 62% | 1.44 | −4.34 | −0.53 | 60 | 🟢 PASS |
| **3.0** | **8** | 8 | +0.11 | 62% | 50% | 1.39 | −4.29 | −0.54 | 63 | 🟢 PASS ← **LIVE** |
| 3.0 | 17 | 8 | +0.19 | 62% | 50% | 1.00 | −3.97 | −0.51 | 54 | 🟢 PASS |
| 3.0 | 25 | 8 | +0.17 | 62% | 62% | 1.16 | −4.13 | −0.52 | 46 | 🟢 PASS |

**configs that PASS gate AND fire ≥8 trades: 7. configs with POSITIVE SPY-excess alpha: 0.**

The `spyExc%/yr` and `medIR` columns are uniformly negative. There is no corner of this grid where the strategy beats buy-and-hold SPY on a risk-adjusted basis. The best medIR in the entire sweep is −0.50.

---

## Why retire rather than fix

1. **No-edge is structural, not parametric.** Loosening the volume filter just trades more often at the same negative IR; tightening it trades less at the same negative IR. The signal (volume-confirmed hourly Donchian breakout on QQQ) does not contain SPY-relative alpha at this scale in this 2022→2026 panel.
2. **It contributes nothing live today** (0 trades, flat position) — retiring it is zero-cost and removes a misleading 🟢 from the roster that the long-only gate awards to a SPY-underperformer.
3. **Mission alignment:** the active bar is raw-return-beats-B&H. This strategy fails the spirit of that bar in all 15 configs. Keeping it dilutes the roster's signal.

**Keep the strategy file** (`strategies/volume_breakout_qqq/`) on disk as a documented dead-end (like the FX candidates) — just remove it from the live cron tick line.

---

## Recommended action (executed separately with backup)

Remove `volume_breakout_qqq` from the cron tick line:
```
# BEFORE
*/30 7-21 * * 1-5 .../cron_tick.sh sma_crossover_qqq_regime sma_crossover_qqq_rth volume_breakout_qqq macd_momentum_iwm tqqq_cot_combo allocator_blend
# AFTER
*/30 7-21 * * 1-5 .../cron_tick.sh sma_crossover_qqq_regime sma_crossover_qqq_rth macd_momentum_iwm tqqq_cot_combo allocator_blend
```
Position is flat (0 live trades) so no unwind needed. Back up crontab first. Live roster goes 6 → 5 strategies.

---

## Reproducibility & integrity

- Sweep driver: `reports/_volbreakout_sweep.py` (runs `runner.walk_forward.walk_forward(params=...)` per cell; READ-ONLY; never writes live params.json).
- Run: `cp reports/_volbreakout_sweep.py _t.py && python3 -m _t && rm _t.py` (needs workspace-root `runner` package on path).
- All 6 protected md5s unchanged this run. No orders, no .db writes, no params.json edits. The crontab change is a separate, backed-up action.
