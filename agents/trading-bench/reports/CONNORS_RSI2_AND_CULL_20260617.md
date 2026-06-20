# Connors RSI(2) Re-Validation + Candidate Cull — 2026-06-17

**Date:** 2026-06-17  
**Author:** trading-bench subagent  
**Scope:** (1) Fresh walk-forward of Connors RSI(2) on QQQ and SPY; (2) Archive 34 confirmed-REJECT candidates.

---

## ★ BOTTOM LINE

| Task | Result |
|---|---|
| Connors RSI(2) QQQ | 🔴 **REJECT** — median Sharpe 0.00, FP Sharpe 0.21, 12 trades across 8 windows |
| Connors RSI(2) SPY | 🔴 **REJECT** — median Sharpe 0.00, FP Sharpe 0.02, 11 trades across 8 windows |
| Archive cull | ✅ **31 of 34 targeted candidates archived** (3 restored: test-suite hard dependencies) |
| Test suite | ✅ **626 passed, 1 skipped, 0 failures** |

---

## TASK 1: Connors RSI(2) Validation

### Methodology

**Warmup-extended walk-forward:** Canonical Connors RSI(2) requires SMA(200) to warm up. The standard 90-day harness window yields only ~62 trading bars — insufficient. Each window was extended by 250 calendar-day warmup prefix (`full_days = window_days + 250`). This gives the strategy a genuine chance to fire while preserving the canonical parameters unmodified.

**This is the third IC subagent pass at this task.** All three attempts reach the same bottom line (FAIL_STANDALONE). Prior results are preserved at `connors_rsi2_wf_warmup_result.json` and `CONNORS_RSI2_VALIDATION_20260527.md`.

**Strategy parameters (unchanged, canonical):**

| Param | SPY | QQQ |
|---|---|---|
| `symbol` | SPY | QQQ |
| `timeframe` | 1Day | 1Day |
| `rsi_period` | 2 | 2 |
| `buy_below` | 10 | 10 |
| `trend_period` | 200 | 200 |
| `exit_sma_period` | 5 | 5 |
| `notional_usd` | $100 | $100 |

---

### Connors RSI(2) — QQQ

| Metric | Value |
|---|---|
| **Full-period continuous Sharpe** | **0.21** |
| **Median-window Sharpe** | **0.00** |
| OOS walk-forward windows | 8/8 with data |
| Total trades (all 8 windows) | **12** |
| Median return per window | **+0.00%** |
| % Windows positive | **38%** |
| % Windows beat BH-SPY | **50%** |
| Worst window MaxDD | **-0.28%** (2023-Q3 chop) |
| Sum return across all windows | **+0.26%** |
| SPY buy-and-hold, same windows | **-1.24%** (full sum) |
| **FITNESS GATE** | 🔴 **FAIL** |

**Fitness gate failure reason:** `median return +0.00% ≤ +0.00%; only 38% of windows positive (need ≥50%); median Sharpe 0.00 ≤ 0.50`

**Per-window detail:**

| Window | Regime | Bars | Trades | Return% | Sharpe | MaxDD% | BH-SPY% | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 236 | 0 | +0.0000 | 0.00 | 0.00 | -1.74 | ✅ |
| 2022-Q3 chop | chop | 235 | 0 | +0.0000 | 0.00 | 0.00 | -0.65 | ✅ |
| 2023-H1 recovery | bull | 235 | 2 | -0.0122 | -0.05 | -0.20 | +0.74 | ❌ |
| 2023-Q3 chop | chop | 233 | 6 | +0.0946 | +0.30 | -0.28 | -0.38 | ✅ |
| 2024-Q2 bull | bull | 233 | 2 | +0.1305 | +1.18 | -0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 232 | 0 | +0.0000 | 0.00 | 0.00 | -0.80 | ✅ |
| 2025-Q3 bull | bull | 231 | 2 | +0.0456 | +0.28 | -0.11 | +0.65 | ❌ |
| 2026-recent bull | bull | 213 | 0 | +0.0000 | 0.00 | 0.00 | +1.55 | ❌ |

**Verdict: 🔴 REJECT — FAIL_STANDALONE.** Do NOT promote.

Key observations:
- RSI(2) < 10 triggers rarely on QQQ in modern tape (only 4 active windows out of 8)
- Even when it fires, outcomes are mixed: 2024-Q2 bull gives Sharpe 1.18 (genuine signal), 2023-Q3 chop gives +0.09% but would have been better in cash, 2023-H1 recovery loses
- The gate fails on all three primary criteria: median Sharpe, % positive, and median return
- FP continuous Sharpe of 0.21 is well below the ≥1.0 clause (a) hard bar
- Gate comparison: **+0.26% sum vs -1.24% SPY BH (same path)** — technically outperforms SPY over this bear-heavy panel, but on an absolute-return and Sharpe basis this is noise

---

### Connors RSI(2) — SPY

| Metric | Value |
|---|---|
| **Full-period continuous Sharpe** | **0.02** |
| **Median-window Sharpe** | **0.00** |
| OOS walk-forward windows | 8/8 with data |
| Total trades (all 8 windows) | **11** |
| Median return per window | **+0.00%** |
| % Windows positive | **25%** |
| % Windows beat BH-SPY | **50%** |
| Worst window MaxDD | **-0.29%** (2023-Q3 chop) |
| Sum return across all windows | **+0.02%** |
| SPY buy-and-hold, same windows | **-1.24%** |
| **FITNESS GATE** | 🔴 **FAIL** |

**Fitness gate failure reason:** `median return +0.00% ≤ +0.00%; only 25% of windows positive (need ≥50%); median Sharpe 0.00 ≤ 0.50`

**Per-window detail:**

| Window | Regime | Bars | Trades | Return% | Sharpe | MaxDD% | BH-SPY% | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 236 | 0 | +0.0000 | 0.00 | 0.00 | -1.74 | ✅ |
| 2022-Q3 chop | chop | 235 | 0 | +0.0000 | 0.00 | 0.00 | -0.65 | ✅ |
| 2023-H1 recovery | bull | 235 | 2 | -0.0348 | -0.24 | -0.15 | +0.74 | ❌ |
| 2023-Q3 chop | chop | 233 | 5 | -0.1135 | -0.47 | -0.29 | -0.38 | ✅ |
| 2024-Q2 bull | bull | 233 | 2 | +0.0856 | +1.02 | -0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 232 | 0 | +0.0000 | 0.00 | 0.00 | -0.80 | ✅ |
| 2025-Q3 bull | bull | 231 | 2 | +0.0829 | +0.55 | -0.07 | +0.65 | ❌ |
| 2026-recent bull | bull | 213 | 0 | +0.0000 | 0.00 | 0.00 | +1.55 | ❌ |

**Verdict: 🔴 REJECT — FAIL_STANDALONE.** Do NOT promote.

Key observations:
- SPY fires even less frequently than QQQ (RSI(2) < 10 on SPY requires a deeper sell-off)
- FP continuous Sharpe 0.02 ≈ pure noise
- 2023-Q3 chop produced a loss (-0.11%, Sharpe -0.47) — the one window where RSI(2) fires multiple times, it loses
- 2024-Q2 and 2025-Q3 are the only profitable windows (both bull regimes)
- Pattern: Connors RSI(2) can capture a quick mean-reversion bounce in specific bull regimes, but is too sparse and inconsistent to pass any gate criteria

---

### Connors RSI(2) Summary vs Mission Criteria

| Criterion | Threshold | QQQ | SPY |
|---|---|---|---|
| FP continuous Sharpe ≥ 1.0 | ≥1.0 | 0.21 ❌ | 0.02 ❌ |
| Median-window Sharpe ≥ 0.5 | ≥0.5 | 0.00 ❌ | 0.00 ❌ |
| % windows positive ≥ 50% | ≥50% | 38% ❌ | 25% ❌ |
| Median return > 0% | >0% | 0.00% ❌ | 0.00% ❌ |
| Beats SPY raw return (mission) | Beat -1.24% | +0.26% ✅ | +0.02% ✅ |
| Max DD worst window | — | -0.28% ✅ | -0.29% ✅ |

Note: Technically "beats SPY" on the sum across the 8-window span (which is bear-heavy), but this is NOT a promotion criterion — the strategy is too sparse to be meaningful. The gate fails on 4 of 4 gate criteria.

**Confirmed: FAIL_STANDALONE for both QQQ and SPY. Do NOT promote. Candidates stay in `strategies_candidates/` for the record.**

---

## TASK 2: Archive Confirmed-REJECT Candidates

### Successfully Archived (31 candidates)

All moved to `strategies_candidates/_archive/`:

| Candidate | Verdict source |
|---|---|
| `breadth_internals` | REJECT report exists |
| `carry_termstructure` | REJECT conclusive |
| `dispersion_regime` | REJECT best Sharpe 0.568 |
| `dollar_leadlag_spy_6df4f1` | STILL-REJECT |
| `intraday_micro` | REJECT |
| `leveraged_trend` | REJECT no risk-adj edge |
| `lowturn_momentum` | REJECT conclusive |
| `macro_nowcast` | REJECT |
| `options_skew` | REJECT signal |
| `pead_lib` | Library helper, not a strategy |
| `seasonality_calendar` | REJECT conclusive |
| `sma_crossover_qqq_regime__mut_0b11ed` | REJECT_GATE |
| `tsmom_spy_2951d463` | Failed Sharpe |
| `vol_regime_spy_mm` | Prior REJECT |
| `vol_regime_spy_prop` | STILL-REJECT |
| `xsec_lowvol_c3783c` | REJECT-WITH-CAVEATS |
| `xsec_lowvol_xa2_440761` | Defensive-sleeve-only, never alpha |
| `xsec_lowvol_xa_38a206` | REJECT |
| `xsec_meanrev_xa_8e5a3f` | REJECT |
| `xsec_momentum_236b86` | REJECT |
| `xsec_momentum_wide_7c4a1f` | Near-miss REJECT |
| `xsec_sector_rot_b7a2f9` | REJECT |
| `xsec_sector_rot_xa_257225` | REJECT-WITH-CAVEATS |
| `xsec_ss_lowvol_lc20` | REJECT |
| `xsec_ss_meanrev_lc20` | REJECT near-miss |
| `xsec_ss_meanrev_lc20_lowturn` | STILL-REJECT |
| `xsec_ss_momentum_dispersed95` | REJECT (`XSEC_DISPERSED_UNIVERSE_20260602T003839Z.md`) |
| `xsec_ss_momentum_lc20` | REJECT |
| `xsec_ss_momentum_lc20_v2` | REJECT (`SS_MOMENTUM_MONTHLY_20260602T002021Z.md`) |
| `xsec_universe` | REJECT confirms 0.5 ceiling |
| `tqqq_cot_combo` | Duplicate (live copy in `strategies/`) |

### Restored to Candidates (3 — test-suite hard dependencies)

These were moved to `_archive/` but then restored because live tests import them directly:

| Candidate | Reason restored | Test file |
|---|---|---|
| `fx_lane` | `tests/test_fx_strategies.py` imports `strategies_candidates.fx_lane` | Cannot archive without updating tests |
| `macro_regime_long` | `tests/test_macro_regime_long.py` loads `macro_regime_long/strategy.py` | Cannot archive without updating tests |
| `sma_crossover_qqq_macrogate` | `tests/test_macrogate_v2.py` loads `sma_crossover_qqq_macrogate/strategy.py` | Cannot archive without updating tests |

**These 3 are logically archived (REJECTs) but physically retained to avoid breaking the test suite.** Main should decide: (a) update the tests to skip/stub these imports and then re-archive, or (b) leave them in place as test fixtures with a clear `_ARCHIVED_TEST_FIXTURE` marker.

### Candidates Left in Place (not on task list)

These remain in `strategies_candidates/` — either still viable, uncertain verdict, or not on the archive list:

| Candidate | Status / Notes |
|---|---|
| `connors_rsi2_qqq` | Just validated — REJECT but kept for record |
| `connors_rsi2_spy` | Just validated — REJECT but kept for record |
| `cot_positioning` | REJECT (best FP-Sharpe 0.930 < 1.0) — not on task list; main should decide |
| `credit_regime_spy_hyglqd` | REJECT (NONPRICE_SIGNAL_20260602) — not on task list |
| `credit_stress` | "Candidate only" — crisis-hedge/DD-control sleeve; BACKLOG says keep |
| `credit_veto_spy_asym` | REJECT (NONPRICE_SIGNAL_R2_20260602) — not on task list |
| `leveraged_long_trend` | Explicitly retained (task says "keep leveraged_long_trend") |
| `leveraged_long_trend_paper` | Explicitly retained (task says keep) + live in `strategies/` |
| `levered_rotate_3x` | REJECT (LEVERED_ETF_TREND_20260531) — not on task list |
| `levered_trend_tqqq` | REJECT (LEVERED_ETF_TREND_20260531) — not on task list |
| `meanrev3d_qqq_cd3fbd` | REJECT (BACKTEST_MEANREV3D_QQQ) — not on task list |
| `overnight_basket_d6cde5` | REJECT (BACKTEST_OVERNIGHT_BASKET_20260602) — not on task list |
| `overnight_spy_31408d4a` | REJECT (BACKTEST_OVERNIGHT_SPY_20260530) — not on task list |
| `overnight_spy_unfiltered_31408d4a` | REJECT (ablation) — not on task list |
| `pead_event_smallcap` | REJECT (EVENT_HARNESS_20260602T053933Z) — not on task list |
| `pead_midlarge` | REJECT near-miss (PEAD_MIDLARGE_20260604) — not on task list; PEAD lane still open |
| `pead_universe_ab40b473` | REJECT (BACKTEST_PEAD_20260530) — not on task list |
| `regime_gated_xsec_momentum_xa_c87bbf` | Phase 1 FAIL; parent DEMOTED — not on task list |
| `rs_breakout_vol_disp` | REJECT (RS_BREAKOUT_VOL_20260602) — not on task list |
| `rsi_mean_revert_spy` | FAIL walk-forward (per memory/2026-06-16.md) — not on task list |
| `tsmom_xa_be0d7f` | REJECT (BACKTEST_TSMOM_XA) — not on task list |
| `xsec_momentum_xa_38d2b2` | DEMOTED (not deleted), kept as audit trail — was live once |

---

## Candidates Worth a Closer Look

The following candidates remain in `strategies_candidates/` and may deserve promotion consideration or next-round evaluation:

1. **`pead_midlarge`** — FP-cont Sharpe **0.926**, n=90 trades, positive ann-on-deployed (+18%), shallow drawdown. Best PEAD result to date. Near-miss on clause (a); the binding failure is "can't beat SPX raw return" (not Sharpe weakness). Worth noting if the gate is ever reviewed for event-driven strategies. Report: `PEAD_MIDLARGE_20260604T055521Z.md`.

2. **`credit_stress`** — Not a return engine, but demonstrated genuine GFC-type crisis decoupling (+8.1% in 2008 while SPX -39.5%). Useful once a multi-strategy allocator exists. BACKLOG entry 2026-06-09 explicitly says "keep as candidate."

3. **`cot_positioning`** — REJECT (best Sharpe 0.93 < 1.0), but described as "legitimate, expected reject" with some information content. If a multi-signal allocator is built, COT could contribute as a filter/gate rather than standalone alpha.

---

## Test Suite

```
626 passed, 1 skipped, 0 failures
```

All tests green. Three candidates were restored from `_archive/` specifically to preserve test-suite integrity (`fx_lane`, `macro_regime_long`, `sma_crossover_qqq_macrogate`).

---

## Appendix: Connors RSI(2) — Why It Rarely Fires

The root cause of near-zero trades is structural, not a data or harness bug:

- RSI(2) < 10 on daily bars requires a multi-day consecutive downturn in an already-uptrending instrument (SMA(200) filter). This combination is rare in modern tape: ~2-5% of trading days historically for SPY, slightly more for QQQ.
- In any 90-day window (≈62 trading bars), expect 1-3 qualifying entry bars at most.
- The 8-window span covers multiple regimes where the asset was either trending up hard (no pullbacks deep enough to trigger RSI < 10) or in a bear (SMA(200) filter blocks entry).
- This is not a "broken" strategy — Connors RSI(2) was published for full-year backtests (2000-2008 literature) where it would see 15-40 entries/year. Our 90-day windows are too short.

**If the mission ever includes a full-period (2020-2026) single backtest rather than walk-forward windows, Connors RSI(2) would accumulate more trades and may show non-trivial results. The walk-forward result is an honest assessment of regime-robustness, not a claim about the strategy's absolute P&L over a long bull period.**

---

RESULT: Connors RSI(2) REJECT on both QQQ and SPY (FP Sharpe 0.21/0.02, median Sharpe 0.00, insufficient trades across walk-forward windows); 31 of 34 targeted REJECT candidates archived to `strategies_candidates/_archive/` (3 retained as live test-suite dependencies: fx_lane, macro_regime_long, sma_crossover_qqq_macrogate); 626 tests green.
