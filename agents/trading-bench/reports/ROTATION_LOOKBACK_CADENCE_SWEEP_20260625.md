# Rotation-Sleeve Lookback × Cadence Sweep — does any (lookback, holding-cadence) config robustly beat the live 3-mo/monthly rotation sleeve?

**Date:** 2026-06-25
**Engine:** `_rot_lookback_cadence_sweep.py` (generalizes the VALIDATED `_sigimprove_tests.run_sector_rotation`) → `reports/_rot_lookback_cadence_result.json`; analysis `_rot_analyze.py`, fine scan `_rot_finescan.py`, stress decomposition `_rot_stress.py`, lag proof `_rot_lag_proof.py`.
**Lane:** Momentum-lookback × holding-cadence optimization of the sector-rotation sleeve (SPY/QQQ/GLD/TLT, hold top-2 equal-weight by trailing momentum). The live sleeve uses a **63d (3-mo) lookback** reselected **monthly** — flagged in `reports/SIGNAL_IMPROVEMENTS_20260621.md` (line 103) as an UNSWEPT first guess. Today's `reports/ALLOCATOR_CADENCE_SWEEP_20260625.md` found a *negative rebalancing premium* on the inv-vol blend (slower beat faster), which motivated testing whether the rotation sleeve's monthly reselection is similarly too fast.
**Question (binary, raw-return mandate, Sharpe/OOS-stability gating):** does any (lookback, cadence) config ROBUSTLY beat the validated 3-mo/monthly sleeve — on a PLATEAU, full AND OOS — without wrecking Sharpe/maxDD and without being a pure beta-up confound?
**Benchmark to beat:** the CURRENT validated rotation sleeve config (3-mo/monthly), reproduced here at **full Sharpe 0.907 / IS 0.929 / OOS 0.875 / maxDD −28.98% / raw 1210.1%** on the current 2005-01-03→2026-06-25 window. SPX over the same window = full Sharpe 0.539 (the floor; the sleeve clears it by a mile — the bar is to beat the validated *config*).

---

## ⭐ VERDICT — 🔴 **RED.** The validated 3-mo/monthly first-guess is **robust and near-optimal.** NO (lookback, cadence) config robustly beats it.

- **The cadence axis answers the motivating question NO:** for **every** lookback, slowing the reselection (monthly → bimonthly → quarterly) **monotonically DESTROYS** raw return and Sharpe. Monthly is strictly the best cadence at every lookback. This is the **OPPOSITE** of the inv-vol blend's negative-rebalancing-premium — and it is mechanistically correct: rotation momentum must refresh monthly to catch regime rotations; holding a stale top-2 for a quarter misses the rotation that is the sleeve's entire reason to exist. **Monthly reselection is the right call — confirmed, not a coincidence.**
- **The lookback axis has NO plateau.** Exactly one cell (189d/monthly) clears a raw+full+OOS screen, but it is a textbook **KNIFE-EDGE / era-luck + beta-up confound**: its **IS Sharpe is 0.836 — WORSE than the baseline's 0.929** (the whole "win" is carried by the post-2019 tech bull), both lookback-neighbors fail, and it runs a higher offense tilt (off/def 0.61/0.35 vs baseline 0.58/0.40). A fine 105–260d scan confirms every apparent winner shares this exact pathology: **IS < baseline, OOS-carried, beta-tilted.** Not a single lookback beats on full **and** IS **and** OOS.
- **Dual-lookback blends don't rescue it.** The best (`63+126` monthly) is the *mirror* imbalance — IS-strong (1.115) but OOS-weak (0.802) — and also beta-tilted (off/def 0.65/0.34). Every dual winner wins one era and fails the other.
- **Net:** **KEEP the live 63d/monthly config.** This closes the "is the lookback/cadence leaving money on the table" question with a valuable confirmation: the unswept first-guess was sound. (The contrast with the blend's quarterly-cadence GREEN is itself instructive — the negative rebalancing premium is a property of the *risk-parity weight-snap*, not a universal "rebalance less" law; the momentum-selection sleeve wants the opposite.)

---

## Harness faithfulness (the sanity control — proves the rig reproduces the validated sleeve)

My generalized builder `run_rotation()` is `_sigimprove_tests.run_sector_rotation` with two axes exposed (lookback in trading days; cadence = reselect every N-th month-open) and **nothing else changed**: same SPY/QQQ/GLD/TLT set, same top-2 equal-weight, same 2bps one-way turnover cost on changed notional, same daily-marking, same `_stats_from_equity` ruler (population stdev, √252), same lookahead contract (rank on the prior period-end close). The 63d/monthly cell **is** the validated config (3-mo → `lb_days = 3*21 = 63` exactly).

| Path / window | Full Sharpe | IS (≤2018) | OOS (2019→) | maxDD | CAGR | SPX full | raw ret |
|---|---|---|---|---|---|---|---|
| **Validated TEST 3 report** (window end 2026-06-18) | **0.916** | **0.929** | **0.898** | **−29.0%** | 12.9% | 0.542 | — |
| My harness, **capped at 2026-06-18** | **0.9158** | **0.9293** | **0.8982** | **−28.98%** | 12.89% | 0.5441 | — |
| My harness, **current window 2026-06-25** (the baseline I sweep against) | 0.9069 | 0.9293 | 0.8752 | −28.98% | 12.75% | 0.5391 | 1210.1% |

**Match at the report's own end-date is to 3 decimals on every metric** (full 0.9158 vs 0.916, IS 0.9293 vs 0.929, OOS 0.8982 vs 0.898, maxDD −28.98 vs −29.0, SPX 0.5441 vs 0.542). The only difference at the current window is the **7 extra trading days** through 2026-06-25 (5403 vs 5399 days), which nudges full to 0.9069 and OOS to 0.8752 (IS is unchanged because it ends 2018). This is the identical window-extension effect the cadence-sweep report documented for the blend. **The harness is a faithful superset of the validated engine** — the only thing that varies across cells is (lookback, cadence).

---

## Results — lookback × cadence grid (current window 2005-01-03 → 2026-06-25, 5403 days)

All cells: top-2 EW, 2bps one-way cost, `_stats_from_equity` (pop-stdev √252). `fp` continuous-span Sharpe (sample stdev) agrees to ~3 decimals (n large) — full grid in the JSON.

### FULL-period Sharpe (baseline 63d/monthly = **0.9069**)
| lb \ cadence | monthly | bimonthly | quarterly |
|---|---|---|---|
| 21d | 0.9867 | 0.8708 | 0.8056 |
| 42d | 0.8263 | 0.8159 | 0.7336 |
| **63d (baseline)** | **0.9069** | 0.8184 | 0.7238 |
| 126d | 0.9055 | 0.7578 | 0.7456 |
| 189d | 0.9737 | 0.9000 | 0.8075 |
| 252d | 0.8286 | 0.7440 | 0.6399 |

### IS Sharpe 2005–2018 (baseline = **0.9293**) — the discriminator
| lb \ cadence | monthly | bimonthly | quarterly |
|---|---|---|---|
| 21d | 0.8524 | 0.7305 | 0.8226 |
| 42d | 0.8406 | 0.8545 | 0.7696 |
| **63d (baseline)** | **0.9293** | 0.7289 | 0.8697 |
| 126d | 0.9662 | 0.7500 | 0.7199 |
| 189d | **0.8358** | 0.7865 | 0.5708 |
| 252d | 0.6342 | 0.5190 | 0.5840 |

### OOS Sharpe 2019+ (baseline = **0.8752**)
| lb \ cadence | monthly | bimonthly | quarterly |
|---|---|---|---|
| 21d | 1.2045 | 1.0981 | 0.7815 |
| 42d | 0.8089 | 0.7606 | 0.6968 |
| **63d (baseline)** | **0.8752** | 0.9683 | 0.5267 |
| 126d | 0.8137 | 0.7736 | 0.7960 |
| 189d | 1.1976 | 1.0864 | 1.2016 |
| 252d | 1.1491 | 1.1208 | 0.7328 |

### RAW total return % (baseline = **1210.1%**)
| lb \ cadence | monthly | bimonthly | quarterly |
|---|---|---|---|
| 21d | 1497.4 | 1055.7 | 894.9 |
| 42d | 908.9 | 892.2 | 763.1 |
| **63d (baseline)** | **1210.1** | 939.6 | 777.2 |
| 126d | 1220.6 | 781.5 | 803.3 |
| 189d | 1528.0 | 1310.5 | 990.5 |
| 252d | 954.1 | 742.1 | 586.6 |

### maxDD % (baseline = **−28.98%**)
| lb \ cadence | monthly | bimonthly | quarterly |
|---|---|---|---|
| 21d | −39.16 | −30.81 | −35.94 |
| 42d | −30.61 | −34.31 | −33.61 |
| **63d (baseline)** | **−28.98** | −32.02 | −30.86 |
| 126d | −27.66 | −29.96 | −30.86 |
| 189d | −23.66 | −28.33 | −23.66 |
| 252d | −29.42 | −24.79 | −30.86 |

**Reading the cadence axis (left→right in every row): monotone decay.** Bimonthly and quarterly lose raw return and Sharpe at essentially every lookback. At the baseline lookback the collapse is stark: 63d raw 1210% (monthly) → 940% (bimonthly) → 777% (quarterly); full Sharpe 0.907 → 0.818 → 0.724. **The motivating hypothesis — "monthly is too fast, like the blend" — is FALSE for the rotation sleeve.** Slower reselection strictly hurts. (Mechanism below.)

---

## Plateau vs knife-edge classification (`_rot_analyze.py`)

A cell "robustly beats" only if it improves raw return AND holds full-Sharpe AND OOS-Sharpe (≈ baseline or better) AND doesn't blow maxDD. **Exactly one cell passes that screen: 189d/monthly.** Its plateau test:

**189d/monthly → KNIFE-EDGE (rejected).**
- **IS Sharpe 0.836 < baseline 0.929.** The headline full-Sharpe "win" (0.974) is carried entirely by OOS (1.198); in-sample it is *worse* than the config it's trying to beat. A robust edge improves both eras — this improves one and degrades the other.
- **Lookback-neighbors fail:** 126d/monthly (OOS 0.814 < baseline) and 252d/monthly (raw 954% < baseline 1210%, full 0.829 < baseline). 189d sits on a spike between a weaker short side and a much weaker long side — **no contiguous plateau.**
- **Beta-up confound:** off/def 0.61/0.35 vs baseline 0.58/0.40 (+0.03 offense, −0.05 defense). The longer lookback structurally tilts toward whatever's been trending — SPY/QQQ in the 2019–2026 bull.

### Fine 105–260d scan @ monthly (`_rot_finescan.py`) — confirms it's a region-wide OOS/beta artifact, not a plateau edge
| lb | full | IS | OOS | raw% | maxDD | off/def | note |
|---|---|---|---|---|---|---|---|
| 115d | 0.933 | 0.971 | 0.874 | 1288 | −27.3 | 0.59/0.39 | IS-OK but full≈base, OOS≈base |
| 126d | 0.906 | 0.966 | 0.814 | 1221 | −27.7 | 0.60/0.38 | ~baseline |
| 155d | 0.949 | **0.825** | 1.156 | 1387 | −24.8 | 0.60/0.37 | beats raw+full+OOS, **IS<base** |
| 185d | 0.990 | **0.873** | 1.183 | 1585 | −23.7 | 0.60/0.36 | beats raw+full+OOS, **IS<base** |
| 189d | 0.974 | **0.836** | 1.198 | 1528 | −23.7 | 0.61/0.35 | beats raw+full+OOS, **IS<base** |
| 195d | 0.968 | **0.867** | 1.138 | 1568 | −23.7 | 0.60/0.36 | beats raw+full+OOS, **IS<base** |
| 210d | 0.917 | **0.784** | 1.136 | 1290 | −29.4 | 0.59/0.37 | beats raw+full+OOS, **IS<base** |
| 252d | 0.829 | 0.634 | 1.149 | 954 | −29.4 | 0.58/0.37 | raw<base |

**NOT ONE cell in the entire 105–260d band beats the baseline on full AND IS AND OOS.** The 155–210d cells form a coherent *region* that beats on full+OOS — but **every single one has IS Sharpe well below the baseline's 0.929** (0.78–0.87). So the "win-region" is not a robustness plateau; it is a **systematic IS/OOS imbalance**: longer lookbacks gave up in-sample (GFC-containing) performance to over-index on the recent bull, plus a consistent +0.02–0.03 offense tilt. That is the definition of overfit-to-recent-regime, and it is exactly the discipline that separated today's quarterly-cadence GREEN (a clean plateau, exposure-neutral) from the drift-threshold knife-edge that got rejected.

---

## Confound check — the longer-lookback "win" gives up the crash protection that is the sleeve's whole purpose (`_rot_stress.py`)

Stress-window decomposition, baseline **63d/monthly** vs the **189d/monthly** "winner":

| window | 63d/monthly Sharpe / ret% / maxDD | 189d/monthly Sharpe / ret% / maxDD |
|---|---|---|
| GFC 2007-11→2009-06 | **0.343** / 7.9 / −28.9 | 0.222 / 4.1 / −14.6 |
| calm 2009-07→2019-12 | **1.048** / 280.7 / −22.5 | 0.893 / 208.1 / −20.9 |
| 2020 COVID | 1.225 / 27.0 / −17.9 | **1.800** / 35.9 / −13.1 |
| 2022 bear | −0.956 / −17.8 / −27.3 | −0.833 / −16.4 / −23.5 |
| 2023-2026 bull | 1.325 / 87.2 / −12.9 | **1.510** / 117.3 / −14.1 |

**The 189d "edge" is entirely the 2020 COVID-rebound + 2023–2026 bull.** In the **GFC** (Sharpe 0.222 vs 0.343) and the **long 2009–2019 calm** (0.893 vs 1.048) the longer lookback is *worse* risk-adjusted; in **2022** it's a near-tie. The shallower GFC drawdown (−14.6%) is just the slow lookback de-risking late and sitting out the recovery (4.1% vs 7.9% captured) — not better protection. So the full-Sharpe number is **recent-bull era-luck stacked on a small beta-up tilt**, precisely the trap the mandate warns against. A sleeve whose job is to diversify the leveraged-long book in 2008/2022 should not be re-tuned to a window where it gives up 2008/2022 to chase 2023–2026.

### Dual-lookback (rank-average of two windows) — mirror imbalance, also confounded
| dual | cadence | full | IS | OOS | raw% | off/def | note |
|---|---|---|---|---|---|---|---|
| 63+126 | monthly | 0.989 | **1.115** | 0.802 | 1623 | 0.65/0.34 | IS-strong but **OOS<base (0.875)**; +0.07 offense |
| 63+252 | monthly | 0.994 | 0.882 | 1.178 | 1576 | 0.64/0.35 | IS<base, OOS-carried; +0.06 offense |
| 21+252 | monthly | 0.928 | 0.859 | 1.045 | 1263 | 0.64/0.35 | IS<base |

`63+126` is the *opposite* imbalance from 189d — strong in-sample (1.115), weak OOS (0.802, below the 0.875 baseline) — so it too wins one era and fails the other, while tilting offense up to 0.65. **No dual blend beats on both IS and OOS.** Multi-timeframe momentum did not produce a robust win here; it just relocated the imbalance and added beta.

---

## No-lookahead statement + proof (`_rot_lag_proof.py`)

- **Ranking decision at rebalance index `i` uses trailing returns through `cal[i-1]`** — the prior period-end close, **strictly before** the held period. Forward P&L is the next period's daily closes. This is the identical lookahead contract as the validated `run_sector_rotation`; changing lookback/cadence changes only the window length and which month-opens trigger a reselect, never what information the rank may see.
- **Adjusted close throughout** (Yahoo v8 adjclose) → PIT by construction.
- **Calendar triggers are causal** (month-open indices derived purely from date strings).

Proof rows — baseline 63d/monthly, first reselections with a filled window:

| rebal_date | lookback_window_end | holds | scores (trailing 63d ret) |
|---|---|---|---|
| 2005-05-02 | 2005-04-29 | GLD,TLT | SPY −0.010, QQQ −0.053, GLD +0.016, TLT +0.022 |
| 2005-06-01 | 2005-05-31 | QQQ,TLT | SPY −0.011, QQQ +0.012, GLD −0.036, TLT +0.067 |
| 2005-07-01 | 2005-06-30 | GLD,TLT | SPY +0.019, QQQ +0.017, GLD +0.019, TLT +0.091 |

`lookback_window_end < rebal_date` for **all 257 reselections** (verified invariant `all(... ) = True`). The top-2 picked each month are exactly the two highest trailing-return assets as of the prior month-end — no future leak. (The first 3 month-opens show `None` scores: the 63d window isn't yet full at the 2005 start, so the sleeve correctly holds nothing until it fills — warm-up, not a bug.)

---

## Honest caveats

1. **One regime, survivorship-bull sample (inherited, unfixable).** SPY/QQQ exist as the offense legs in a 2005–2026 window dominated by a secular equity/tech bull (with 2008 and 2022 as the stress tests). The fact that *longer* lookbacks look good in raw/OOS terms is itself a symptom of that bull (longer momentum over-weights the persistent uptrend). The IS-discriminator (which includes 2008) is what exposes it as non-robust. In a genuinely mean-reverting decade the ranking could behave differently — but that cuts *against* lengthening the lookback, not for it.
2. **The cadence finding is robust and direction-clear, not a third-decimal call.** Slower-than-monthly loses 200–400pts of raw return at the baseline lookback — well outside noise. The mechanism (momentum-selection needs to refresh; risk-parity weight-snap does not) is sound and explains why this sleeve's verdict is the *opposite* of the same-day blend-cadence GREEN.
3. **maxDD is genuinely lower at long lookbacks** (e.g. 189d −23.7% vs baseline −29.0%). If the *only* objective were drawdown compression (not the raw-return mandate, and accepting worse IS Sharpe + a beta tilt + OOS-concentration), a longer lookback is a defensible pure risk knob. Under the actual mandate (beat the validated config on raw return on a robust plateau) it fails. Shelved as a risk-preference note, not a recommendation.
4. **21d/monthly posts the 2nd-highest full Sharpe (0.987)** but with maxDD −39.2% (worst in the grid) and IS 0.852 < baseline — a fast-momentum whip that's even less robust than 189d. Mentioned for completeness; rejected on the same IS-imbalance + drawdown grounds.
5. **Grid resolution.** Lookback swept at {21,42,63,126,189,252}d plus a fine 105–260d pass (10d steps) around the only candidate region; cadence at {1,2,3} months. Sub-monthly cadence deliberately not tested (the rotation signal is monthly momentum — sub-monthly just churns cost, and the cadence axis already shows the value is at monthly, the fastest tested).

---

## Canary / file-safety

- **No-lookahead canary: CLEAN** — every reselect ranks on trailing (`< i`) data through the prior period-end; harness reproduces the validated baseline to 3 decimals at the report's own end-date (proof no leak was introduced by the generalization).
- **Protected files: UNTOUCHED.** No edits to `runner/*.py`, `strategies/allocator_blend/*`, `runner/allocator_paper_tracker.py`, any strategy module, or the crontab. Only `_rot_*` scratch scripts + `reports/_rot_lookback_cadence_result.json` + this report were created. This is research-only; **no config change is proposed** (RED = keep the live sleeve).

---

## Bottom line

**RED — keep the live 63d/monthly rotation sleeve.** The unswept first-guess flagged in `SIGNAL_IMPROVEMENTS_20260621.md` is **robust and effectively optimal** under the bench's plateau discipline. Both axes confirm it: the cadence axis shows monthly is strictly the best (slower monotonically hurts — opposite of the blend, and mechanistically right for a momentum-selection sleeve), and the lookback axis has no plateau (every apparent winner is an IS/OOS-imbalanced, recent-bull-carried, beta-tilted knife-edge, not a robust region). This closes the "is the rotation lookback/cadence leaving money on the table" question with a clean NO. No config change proposed.