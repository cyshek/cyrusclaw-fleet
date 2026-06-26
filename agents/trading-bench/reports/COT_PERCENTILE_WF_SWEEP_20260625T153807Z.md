# COT Percentile Threshold — Walk-Forward Sweep (CLOSE / REJECT)

**Date:** 2026-06-25T15:38:07Z
**Backlog item:** `OPEN 2026-06-21 · COT percentile — needs walk-forward before wiring to core engine` (`reports/SIGNAL_IMPROVEMENTS_20260621.md` Test 1)
**Engine:** TQQQ vol-target sleeve (`strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py`), the canonical engine the live `leveraged_long_trend_paper` / `tqqq_cot_combo` adapters mirror.
**Harness:** `_cot_percentile_wf_sweep.py` → `reports/_cot_percentile_wf_sweep.json` (reuses the exact lookahead-safe machinery from `_sigimprove_tests.py`: same engine sim, same release-lagged COT percentile overlay).
**Gate:** **FP-cont (full-period continuous-span) Sharpe ≥ 1.0.** In this single-path engine the continuous full Sharpe (`_stats_from_equity.sharpe`: per-tick returns over the WHOLE concatenated equity curve × √252) *is* the FP-cont Sharpe — same convention as `runner/fp_sharpe.sharpe_from_returns` (I re-derived it with sample-stdev to match the `fp_sharpe` ddof=1 ruler exactly).

## Verdict in one line

**CLOSE / REJECT.** Across a full 5-threshold × 2-field × 2-shape grid (+ magnitude and percentile-window sub-sweeps, 29 configs), **NO configuration clears the FP-cont Sharpe ≥ 1.0 gate.** The best cell reaches **0.899** (baseline 0.856) — a real but marginal drawdown-shaper whose full-Sharpe "gain" is partly an OOS-regime artifact (IS Sharpe stays weak; rolling-Sharpe dispersion is unchanged). The COT lev_net overlay is **not promotable to the core engine.** Best-for-reference config recorded below.

---

## The gate metric & baseline

| | FP-full Sharpe (GATE) | FP-IS (≤2018) | FP-OOS (2019→) | full CAGR | full maxDD | daily win% |
|---|---|---|---|---|---|---|
| **BASELINE** (vol-target 0.25, SMA200, vix-off, 2bps) | **0.8559** | 0.689 | 1.009 | 20.8% | −34.5% | 55.5% |

> The report's Test-1 baseline quoted 0.864 (population-variance Sharpe); recomputed with the canonical `fp_sharpe` sample-stdev (ddof=1) it's 0.8559. Identical ranking, ~0.01 lower — I use the sample-stdev number throughout so the gate comparison is on the canonical ruler. Baseline is **already below 1.0 on the full continuous span** (it clears 1.0 only in the OOS sub-period and in 4–5 of 14 rolling 3-yr windows).

---

## MAIN SWEEP — 5 thresholds × 2 fields × 2 shapes (`pct_window`=52wk)

`active(b/c)` = decision-days the overlay boosted / cautioned (proof it isn't a no-op). caution-only = `long_mult` 1.0 (capped, so only the high-extreme 0.5× fires); boost = `long_mult` 1.25 at the low extreme.

### lev_net (leveraged-fund speculator)

| entry/exit | shape | **FP-full** | FP-OOS | full maxDD | active b/c | gate |
|---|---|---|---|---|---|---|
| 10/90 | caution 1.0/0.5 | 0.8030 | 0.971 | −33.8% | 0/504 | ❌ |
| 15/85 | caution 1.0/0.5 | 0.7962 | 0.940 | −32.2% | 0/600 | ❌ |
| 20/80 | caution 1.0/0.5 | 0.8302 | 1.009 | −32.6% | 0/767 | ❌ |
| 25/75 | caution 1.0/0.5 | 0.8204 | 1.006 | −34.6% | 0/900 | ❌ |
| 30/70 | caution 1.0/0.5 | 0.7987 | 0.957 | −34.6% | 0/1067 | ❌ |
| 10/90 | boost 1.25/0.5 | 0.8166 | 0.951 | −33.9% | 544/504 | ❌ |
| 15/85 | boost 1.25/0.5 | 0.8256 | 0.924 | −31.5% | 736/600 | ❌ |
| **20/80** | **boost 1.25/0.5** | **0.8657** | 0.993 | **−31.7%** | 991/767 | ❌ |
| 25/75 | boost 1.25/0.5 | 0.8437 | 0.960 | −33.4% | 1159/900 | ❌ |
| 30/70 | boost 1.25/0.5 | 0.8017 | 0.895 | −33.4% | 1417/1067 | ❌ |

### deal_net (dealer / "commercial" analog)

| entry/exit | shape | **FP-full** | FP-OOS | full maxDD | gate |
|---|---|---|---|---|---|
| 10/90 | caution 1.0/0.5 | 0.7665 | 0.921 | −34.9% | ❌ |
| 15/85 | caution 1.0/0.5 | 0.7381 | 0.851 | −35.3% | ❌ |
| 20/80 | caution 1.0/0.5 | 0.6705 | 0.803 | −35.8% | ❌ |
| 25/75 | caution 1.0/0.5 | 0.7163 | 0.879 | −35.8% | ❌ |
| 30/70 | caution 1.0/0.5 | 0.6835 | 0.825 | −36.9% | ❌ |
| 10/90 | boost 1.25/0.5 | 0.7825 | 0.954 | −36.4% | ❌ |
| 15/85 | boost 1.25/0.5 | 0.7409 | 0.828 | −38.8% | ❌ |
| 20/80 | boost 1.25/0.5 | 0.6776 | 0.806 | −40.6% | ❌ |
| 25/75 | boost 1.25/0.5 | 0.7164 | 0.860 | −40.9% | ❌ |
| 30/70 | boost 1.25/0.5 | 0.6541 | 0.766 | −42.6% | ❌ |

**Reading:**
- **`lev_net` ≫ `deal_net` at EVERY threshold and shape** — the report's "specs work, commercials are backwards" sign-finding **replicates robustly across the entire grid.** deal_net not only underperforms (best 0.78) but *blows out* maxDD to −42% on the boost variants (the dealer book is structurally net-short as a hedge → its percentile extremes carry no contrarian information, and boosting on them adds risk in the wrong regimes).
- **`lev_net`'s best threshold is 20/80** (the original first guess) on the boost shape — 0.866. The neighbors 15/85 and 25/75 are lower, and 10/90 / 30/70 lower still → 20/80 is a genuine local plateau peak, **not** an artifact of a lucky knife-edge, but the whole family sits 0.80–0.87.

---

## MAGNITUDE sub-sweep — `lev_net`, 20/80, boost × caution strength

| boost / caution | **FP-full** | FP-OOS | full maxDD |
|---|---|---|---|
| 1.00 / 0.50 | 0.8302 | **1.009** | −32.6% |
| 1.00 / 0.75 | 0.8490 | 1.008 | −33.1% |
| 1.25 / 0.50 | 0.8657 | 0.993 | −31.7% |
| 1.25 / 0.75 | 0.8839 | 0.995 | −32.4% |
| 1.50 / 0.50 | 0.8804 | 0.971 | −32.8% |
| **1.50 / 0.75** | **0.8986** | 0.976 | −33.7% |

**The overfit tell:** as boost magnitude rises, **full Sharpe climbs (0.83→0.90) but OOS Sharpe FALLS (1.009→0.976).** The in-sample full-Sharpe gain is bought partly by OOS decay — the more aggressively you lever the signal, the more you're fitting the pre-2019 window. The most *honest* cell is the gentle **caution-only 1.0/0.75** (full 0.849, OOS 1.008, smallest IS/OOS divergence) — but it's still sub-gate on the full span.

---

## PERCENTILE-WINDOW robustness — `lev_net`, 20/80, boost 1.25/0.5

| pct_window | **FP-full** | FP-OOS | full maxDD |
|---|---|---|---|
| 26 wk | 0.8305 | 0.918 | −32.0% |
| **52 wk** | **0.8657** | 0.993 | −31.7% |
| 78 wk | 0.8201 | 0.901 | −33.3% |

52-week is the peak; 26 and 78 both lower → the original 52-week trailing-percentile window was well-chosen and **not** knife-edge, but no window lifts the family past ~0.87.

---

## Walk-forward stability (rolling 3-yr Sharpe, stepped 1 yr — 14 windows)

| | windows ≥ 1.0 | rolling min | rolling max | rolling stdev | IS/OOS gap |
|---|---|---|---|---|---|
| BASELINE | 5 / 14 | 0.500 | 1.148 | 0.212 | −0.32 (IS 0.69 / OOS 1.01) |
| best (lev 20/80 boost1.5/caut0.75) | 5 / 14 | 0.430 | 1.217 | **0.212** | −0.21 |

- The overlay does **not** add new strength — the same calendar windows that are strong for the baseline are strong for the overlay; it just nudges them. **Rolling-Sharpe dispersion is identical (0.212)** → the overlay is not a stabilizer, it doesn't shrink the volatility-of-Sharpe.
- Both baseline and overlay clear 1.0 in only **5 of 14** rolling windows; the full-span Sharpe is dragged below 1.0 by the weak 2014–2017 and 2020–2023 windows (which the overlay can't fix — COT positioning extremes simply weren't predictive there).
- The overlay's apparent full-Sharpe edge is **OOS-period-loaded**: IS (≤2018) Sharpe stays weak (0.69–0.76) while the OOS sub-period (2019→) happened to reward it. That's a regime-dependence flag, not a structural edge.

---

## Best-for-reference config

If this overlay is ever revisited (e.g. for a **drawdown-compression** mandate rather than a Sharpe mandate), the defensible knobs are:
- **Field:** `lev_net` (leveraged-fund speculator net). **Never `deal_net`** — it degrades both Sharpe and maxDD.
- **Direction:** DIRECT (boost when specs washed-out-low, cut when specs crowded-high). The legacy "commercials contrarian" framing is empirically backwards for the NQ-TFF contract.
- **Thresholds:** **20/80** (local plateau peak; robust to ±5 pts).
- **Percentile window:** **52 weeks** (peak; robust to ±26 wk).
- **Best DD-shaper cell:** `lev_net 20/80 boost1.25/caut0.5` → maxDD **−31.7%** (−2.8 pts vs baseline −34.5%) at full Sharpe 0.866 — the cleanest drawdown win without the OOS decay of the 1.5× boost.
- **Best raw-Sharpe cell:** `lev_net 20/80 boost1.50/caut0.75` → full 0.899, but OOS drifts to 0.976 (don't use — overfit lean).

**But for the Sharpe-mandate gate (≥1.0): REJECTED.** Nothing clears it.

---

## Honesty notes / caveats

- **COT-TFF data starts 2010** → this sweep has **no 2008 stress coverage** (same limitation as the original Test 1). The overlay's behavior in a GFC-scale event is untested.
- The overlay genuinely fires (e.g. lev_net 20/80 boost: 991 boost-days + 767 caution-days over ~4,100 trading days) — these are not no-op results.
- Lookahead discipline preserved end-to-end (inherited from `_sigimprove_tests`): COT via release-lagged `released_history` (Tuesday snapshot invisible until Friday release); overlay multiplier for held day D+1 computed from decision day D only.
- Sharpe convention: sample-stdev (ddof=1) × √252, matching `runner/fp_sharpe`. The engine's own `_stats_from_equity` uses population variance (÷n); at n≈4,100 the difference is ~0.01 and does not change any gate outcome.
- `tqqq_cot_combo` (live) already embeds the COT lev_net signal via its own `cot_scale` mechanism (the 0.50 scale chosen 2026-06-14, a *separate* WoW-direction lever, not this percentile overlay). This sweep concerns the **percentile-extreme** overlay specifically and does not change the live strategy's existing behavior.

---

## Disposition

**CLOSE / REJECT.** The COT lev_net percentile overlay is a marginal, regime-dependent drawdown-shaper that never lifts the full-period continuous-span Sharpe to the 1.0 gate (best 0.899 vs baseline 0.856). Do **not** wire to the core engine. Best-for-reference config recorded above for a possible future *drawdown-mandate* revisit. BACKLOG item closed.
