# Regime-Conditional Allocator — TQQQ Vol-Target × Sector Rotation (NFCI switch)

**Date:** 2026-06-25
**Engine:** `_regime_allocator.py` → `reports/_regime_allocator_result.json` (sleeves cached in `_regime_sleeves.pkl` via `_regime_build_sleeves.py`; diagnostics `_regime_diag.py`, `_regime_charity.py`)
**Lane:** Does making the inter-sleeve weight between the two validated SPX-beaters **regime-conditional** (tilt toward TQQQ in risk-ON, toward rotation in risk-OFF, switched by a PIT NFCI composite) beat the promoted **static inverse-vol blend** on **raw cumulative return** without wrecking Sharpe/maxDD?
**Benchmark to beat:** static `invvol_63d` blend (full Sharpe 1.003 / OOS 1.123 / maxDD −23.9% / **raw total return 985%** on this window). **Floor:** SPX raw (total return 582%). *(Mandate = beat SPX raw; the static blend already does, so the bar here is **beat the static blend's raw return**.)*

---

## ⭐ VERDICT — 🔴 **RED. Close the lane.** Making the inter-sleeve weight NFCI-regime-conditional does NOT produce a robust, OOS-stable raw-return beat over the static inv-vol blend. Every variant that "beats" raw return is a **confound** (a near-constant TQQQ overweight, not a regime switch) that *degrades* Sharpe and maxDD; the one genuinely-switching variant (median threshold) **loses** raw return outright and its tilt is **overfit** (helps in-sample, reverses out-of-sample).

**The three ways to slice it, all negative:**

| Framing | Raw-return vs static? | Sharpe/maxDD vs static? | Verdict |
|---|---|---|---|
| `thr=0` (absolute) tilts | ✅ beats (up to 1499%) | ❌ Sharpe 1.003→0.948, maxDD −23.9%→−29.3% | **Confound** — see below |
| `thr=expanding-median` (real switch) | ❌ **loses** (985%→909%) | ❌ Sharpe →0.94, OOS collapses | Regime timing has *negative* value |
| `NFCI+BAA10Y` z-blend | ✅ full only (1080%) | ❌ **fails OOS**, Sharpe →0.88, maxDD −31% | IS-only / overfit |

- **Promotable to a paper clock?** ❌ **NO.**
- **Robust plateau or knife-edge?** Neither helps — it's a **monotone confound** (`thr=0`) plus an **overfit reversal** (`exmed`). Not a lucky single cell, but not an edge either.
- **No-lookahead canary:** ✅ **CLEAN** (181/181 signalled month-opens use an NFCI value whose release date ≤ the rebalance date).

---

## Why the `thr=0` "beats" are a confound, not an edge (the crux)

The NFCI level has been **below zero essentially the entire 2011→2026 sample** (NFCI@month-opens: min −0.99, median **−0.65**, p75 −0.53, **max +0.05**). NFCI > 0 ("tighter-than-average financial conditions") is the risk-OFF trigger for `thr=0` — and it **fires on just 1 of 181 signalled month-opens (0.6%).**

So `nfci_zero_tilt0.35` is in **risk-ON 99.4% of the time** → it simply **adds +0.35 to `w_tqqq` almost every month.** Realized avg `w_tqqq` jumps **0.349 → 0.665**. That is not a regime switch — it is a **static ~67%-TQQQ blend in disguise**, i.e. exactly the report's existing 60/40–70/30 "more Nasdaq punch" lane (`reports/ALLOCATOR_BLEND_20260621.md`: 70/30 → CAGR 18.9%, maxDD −28.2%). The apparent raw-return win is **pure leverage-up**, and it pays the usual price: full Sharpe **1.003 → 0.948** and maxDD **−23.9% → −29.3%**. That violates the "not wrecking Sharpe/maxDD" clause and adds nothing the static blend's weight dial didn't already offer.

When you instead use a threshold that *actually splits the sample into two regimes* — `thr=expanding-median` fires risk-OFF **59% of the time** (a real ~50/50 switch) — the strategy **loses**: raw total return **985% → 909%** and Sharpe **1.003 → 0.938**. Tilting toward TQQQ in below-median-NFCI months and toward rotation in above-median months **destroys value** on this sample.

---

## Results — full grid (monthly rebalance, 2bps one-way inter-sleeve cost; window 2010-02-12 → 2026-06-25, 4116 days, 197 month-opens; NFCI signal active on 181 of them, first 2011-06-01)

`tilt0.00` = the static baseline reproduced exactly through each weight function (sanity control — identical 985% / Sharpe 1.003 every time). **Bold** = beats static raw return.

### Single-composite NFCI (the headline test)

| Variant | Raw total ret | CAGR | Full Sharpe | maxDD | IS tot (≤2018) | IS Sharpe | OOS tot (2019→) | OOS Sharpe | Beats static raw (full / OOS) |
|---|---|---|---|---|---|---|---|---|---|
| **static invvol_63d** | **985%** | 15.7% | **1.003** | **−23.9%** | 194% | 0.892 | 268% | 1.123 | — |
| nfci **zero** tilt0.15 | **1197%** | 17.0% | 0.989 | −26.4% | 216% | 0.865 | 310% | 1.125 | ✅ / ✅ *(confound)* |
| nfci **zero** tilt0.25 | **1348%** | 17.8% | 0.970 | −28.0% | 230% | 0.841 | 338% | 1.113 | ✅ / ✅ *(confound)* |
| nfci **zero** tilt0.35 | **1499%** | 18.5% | 0.948 | −29.3% | 245% | 0.819 | 363% | 1.092 | ✅ / ✅ *(confound)* |
| nfci **exmed** tilt0.15 | 943% | 15.4% | 0.974 | −24.0% | 229% | 0.917 | 216% | 1.039 | ❌ / ❌ |
| nfci **exmed** tilt0.25 | 909% | 15.2% | 0.938 | −24.2% | 254% | 0.920 | 185% | 0.960 | ❌ / ❌ |
| nfci **exmed** tilt0.35 | 888% | 15.1% | 0.897 | −25.1% | 280% | 0.916 | 159% | 0.874 | ❌ / ❌ |

### Robustness composite: NFCI + BAA10Y credit z-blend (risk-OFF iff ½·z(NFCI)+½·z(BAA10Y) > 0, expanding PIT windows)

| Variant | Raw total ret | CAGR | Full Sharpe | maxDD | OOS tot | OOS Sharpe | Beats static raw (full / OOS) |
|---|---|---|---|---|---|---|---|
| nfci_baa tilt0.15 | **1029%** | 16.0% | 0.955 | −25.9% | 253% | 1.024 | ✅ / ❌ |
| nfci_baa tilt0.25 | **1049%** | 16.1% | 0.915 | −28.5% | 242% | 0.955 | ✅ / ❌ |
| nfci_baa tilt0.35 | **1080%** | 16.3% | 0.877 | −31.0% | 233% | 0.892 | ✅ / ❌ |

> The z-blend "beats" full raw return but **fails OOS on every cell** (OOS 233–253% all < static's 268%) and **monotonically degrades Sharpe (→0.88) and maxDD (→−31%)** as tilt rises. IS-only improvement that reverses OOS = overfit, not edge.

### The overfit smoking gun (honest `exmed` switch, IS vs OOS)

For the genuine ~50/50 regime switch, raising the tilt **improves in-sample raw return but destroys out-of-sample** — the textbook overfit reversal:

| exmed tilt | IS tot (≤2018) | OOS tot (2019→) |
|---|---|---|
| 0.15 | 229% | 216% |
| 0.25 | 254% | 185% |
| 0.35 | 280% | **159%** |
| *(static)* | *194%* | *268%* |

More tilt → better IS, worse OOS, monotonically. The regime timing is fitting noise in the training half.

### Charity check — defensive-only (de-risk in risk-OFF, hold exact static otherwise)

The most charitable "flee to the GLD/TLT rotation sleeve only in stress" framing, under both the median and tightest-quartile thresholds:

| Variant | Raw total ret | Full Sharpe | maxDD | OOS tot | maxDD better? | Sharpe better? |
|---|---|---|---|---|---|---|
| static | 985% | 1.003 | −23.9% | 268% | — | — |
| defonly exmed t0.15 | 869% | 0.989 | −23.1% | 223% | +0.8pt | ❌ |
| defonly p75 t0.15 | 913% | 0.983 | −23.5% | 234% | +0.4pt | ❌ |
| defonly exmed t0.25 | 797% | 0.969 | −23.9% | 195% | ❌ | ❌ |

> Even the kindest defensive-only variant shaves maxDD by a trivial **0.4–0.8pt** while giving up **70–116pts of raw return**, lowering full Sharpe (0.98 < 1.003), and lowering OOS (223–234% < 268%). Strictly dominated — there is **no AMBER drawdown-improvement angle** to salvage.

---

## No-lookahead canary (the make-or-break discipline) — ✅ CLEAN

**PIT source:** the cached **first-release** NFCI dict (`.cache/fred/NFCI_pit_firstrelease.json`: `obs_date → [release_date, first_print_value]`) — the purest point-in-time feed (first print, zero revision leak). At each month-open `D` the regime uses the **latest observation whose `release_date ≤ D`** — the freshest NFCI a trader could legitimately have acted on at `D`.

**Why first-release, not ALFRED as-of:** NFCI's ALFRED real-time archive **begins 2011-05-25** (its first published vintage); `realtime_start=realtime_end=D` for `D < 2011-05` returns HTTP 400 *"series does not exist in ALFRED"* (verified). So **pre-2011-05 month-opens get NO NFCI signal and fall back to the exact static inv-vol weight** — the honest treatment (you could not have traded an NFCI regime in 2010). Signal is active on **181 / 197** month-opens.

**Canary rows** (sampled ~every 2 years) — every used value was released **before** the rebalance date, with the real ~1-week publication lag visible:

| Rebal date | NFCI value used | Observation week | Release date | release ≤ rebal? |
|---|---|---|---|---|
| 2012-02-01 | −0.430 | 2012-01-27 | 2012-02-01 | ✅ |
| 2014-02-03 | −0.940 | 2014-01-24 | 2014-01-29 | ✅ |
| 2016-02-01 | −0.560 | 2016-01-22 | 2016-01-27 | ✅ |
| 2018-02-01 | −0.940 | 2018-01-26 | 2018-01-31 | ✅ |
| 2020-02-03 | −0.820 | 2020-01-24 | 2020-01-29 | ✅ |
| 2022-02-01 | −0.587 | 2022-01-21 | 2022-01-26 | ✅ |
| 2024-02-01 | −0.564 | 2024-01-26 | 2024-01-31 | ✅ |
| 2026-02-02 | −0.600 | 2026-01-23 | 2026-01-28 | ✅ |

**Global check:** all 181 signalled month-opens use a release dated ≤ their rebalance date (`all_used_releases_leq_rebal = True`). The NFCI value used on `D` always lags `D` by its real publication delay. **No lookahead.** *(The result is RED regardless — but it's RED on a clean signal, not because of a leak.)*

---

## Rigor / method notes

- **Engine reuse (zero sleeve-logic reimplementation):** sleeve daily-return streams come from `_allocator_blend_tests.build_sleeves()` and the blend mechanic is `_allocator_blend_tests.blend_portfolio()` called **directly** (monthly rebalance, intramonth weight drift, 2bps one-way inter-sleeve turnover cost = `BLEND_COST_BPS`). The static baseline reproduces the promoted `invvol_63d` `w_tqqq = iv0/(iv0+iv1)` from trailing-63d sleeve vols at each month-open — mirroring `runner/allocator_paper_tracker.py::compute_blend_state()`. Sanity: the `tilt0.00` control reproduces the static blend exactly (985% / Sharpe 1.003 / maxDD −23.9%, avg `w_tqqq` 0.349) in every weight-function path.
- **Static baseline avg `w_tqqq` = 0.349** on the latest data (≈ the report's stated ~35/65, not the task brief's 0.442 — the lower figure is correct; logged).
- **≤2 free params, by design:** the regime mapping is `w_tqqq = clamp(w_static ± tilt, 0, 1)` with two knobs only — **tilt magnitude** {0.15, 0.25, 0.35} and **threshold definition** {`zero`, `exmed`, plus the `nfci_baa` composite}. No per-cell tuning; the grid is reported in full so the reader sees the whole surface, not an argmax.
- **Sharpe convention:** `_stats_from_equity` population-stdev √252 (matches the blend report's table); cross-checked against the canonical FP-continuous Sharpe (`runner/fp_sharpe.py`, ddof=1) — identical to 3 dp for the static blend (1.003 / 1.003).
- **IS/OOS split** = blend report's split (IS ≤ 2018-12-31, OOS 2019+).
- **Adjusted close throughout** (inherited from the validated sleeves).

---

## Honest caveats

1. **Sample regime is one-sided.** NFCI spent 2011→2026 almost entirely "loose" (below zero), so an *absolute* NFCI threshold barely switches and a *relative* (median) threshold splits the sample arbitrarily. This window simply does not contain enough sustained "tight financial conditions" for an NFCI risk-on/off allocator to add value — and where it does switch (2018-Q4, 2020-Q1, 2022), the rotation sleeve's own internal momentum already handles the de-risking, so the top-level NFCI tilt is redundant at best and mistimed at worst.
2. **Both sleeves are already gated/defensive internally** (TQQQ vol-target goes to cash below SMA-200; rotation flees to GLD/TLT on momentum). The inter-sleeve weight is a *second-order* control; the first-order regime response is baked into the sleeves. Layering an NFCI switch on top double-counts the regime call and adds timing noise.
3. **Survivorship (inherited).** The window is a TQQQ-inception-bounded secular bull; an NFCI risk-off overlay would plausibly matter more in a genuine extended-tight-conditions regime (e.g. 2008, or a future stagflation) that this sample doesn't contain. That's a reason to *shelve the idea conceptually*, not to promote this implementation — which, on all available data, loses.
4. **What WOULD change the verdict (re-open trigger):** a materially longer / tighter-conditions sample (or a sleeve set whose defense is *not* already regime-aware) in which a median-threshold NFCI switch beats static raw return **OOS** with non-degraded Sharpe/maxDD. None of that is present today.

---

## Recommendation

**Close the lane (RED).** The promoted **static `invvol_63d` blend remains the best inter-sleeve rule** — regime-conditioning the weight on NFCI does not improve raw return without a confound, fails the genuine out-of-sample test, and degrades risk-adjusted metrics. Keep paper-clocking the static blend (`runner/allocator_paper_tracker.py`) unchanged. If a future edge-discovery sprint wants a regime overlay, the lesson here is: **it must switch on a signal that actually changes state in-sample, beat the static blend OOS, and not just lever-up the higher-CAGR sleeve.** Do not re-run this exact NFCI×two-sleeve test absent a tighter-conditions sample.
