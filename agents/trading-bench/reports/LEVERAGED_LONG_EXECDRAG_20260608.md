# Leveraged-Long Vol-Target — REALISTIC EXECUTION-DRAG TEST (the decisive net-of-cost gate)

**Date:** 2026-06-08
**Engine:** `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget_realcost.py` (new; extends the untouched `backtest_daily_voltarget.py`)
**Results dump:** `strategies_candidates/leveraged_long_trend/execution_drag_result.json`
**Builds on / corrects:** `reports/LEVERAGED_LONG_SURVIVORSHIP_20260608.md` (which flagged the off-TQQQ OOS margin as "thin enough that turnover costs could erase it" and named this test the priority gate).
**Status:** PAPER / RESEARCH ONLY. Quarantine candidate. Never live. No real orders, ever.

---

## ⭐ VERDICT (lead with it)

The prior engine charged an **optimistic** cost model: a flat 2 bps on abs(Δw) and **zero** leveraged-ETF expense ratio. Adding the two real first-order costs — the **ETF expense ratio** (the big omission, a holding cost paid every day you hold the sleeve) and a **realistic per-side bid/ask+slippage** on the ~2,900–3,240 rebalances/yr — splits the leveraged-long family cleanly:

| Sleeve | OOS (2018+) net strat vs SPX | Net OOS margin | **SURVIVES realistic cost?** |
|---|---|---|---|
| **TQQQ** | +353.8% vs +174.7% | **+179.1 pp** | ✅ **YES — survives easily** (still +119 pp even at a pessimistic 30 bps/side) |
| **UPRO** | +170.0% vs +174.7% | **−4.7 pp** | ❌ **NO — WASH** (edge erased; already negative at the central 4 bps) |
| **SPXL** | +170.3% vs +174.7% | **−4.4 pp** | ❌ **NO — WASH** (edge erased; same) |

**Plain-English headline:** *Broad-cap leveraged-long (UPRO/SPXL) is a **WASH** net of realistic cost — the post-2018 out-of-sample beat over SPX disappears. Only **TQQQ** survives, and TQQQ carries the heaviest survivorship caveat (3x Nasdaq specifically went up). The thin ~11–12 pp broad-cap margin the survivorship cross-check found had **essentially zero cost headroom**: it is consumed almost entirely by the expense ratio alone.*

**Breakeven (where the broad-cap OOS edge dies):** at the real ER, the UPRO/SPXL OOS margin crosses zero at just **~1.0–1.5 bps per side** — *below* the realistic half-spread for these tickers (~3–4 bps). For TQQQ the breakeven is far out (>30 bps/side; OOS margin is still +119 pp at 30 bps). So the cost headroom is: **TQQQ huge, UPRO/SPXL essentially none.**

**The single biggest driver is the expense ratio, not turnover.** The ER alone (with the spread held at the OLD 2 bps) drops the UPRO OOS margin from +11.0 pp to **−1.4 pp** (ER bite −12.4 pp) and SPXL from +12.2 pp to **−1.1 pp** (ER bite −13.3 pp). The unmodeled ETF expense ratio is what kills the broad-cap edge; the realistic spread is secondary and only deepens an already-negative result.

---

## What the new engine models (three grounded cost components)

The new module re-implements the **exact** lookahead-safe daily loop of `run_backtest_voltarget` (importing every signal/vol/stats helper UNCHANGED — `trend_is_up`, `realized_ann_vol`, `target_weight`, `_stats_from_equity`, the `bd` data caches), and injects two new cost terms plus one disclosed caveat:

1. **Leveraged-ETF expense ratio (HOLDING cost — the big omission).**
   `er_cost_today = (annual_ER / 252) * w_today`, charged on the **sleeve-exposed fraction only** (you pay the ETF's ER on the dollars in the ETF; the `(1−w)` cash sleeve does **not** pay it). Paid **every day you hold**, independent of turnover — distinct from and additive to the trading cost.
   ER values used (published, ProShares/Direxion, 2026-06): **TQQQ 0.84%**, **UPRO 0.91%**, **SPXL 0.97%**, SOXL 0.90% (SOXL skipped — already DD-disqualified).
   ⚠️ **ER ASSUMPTION FLAGGED:** per-source/date the live numbers vary a few bps (TQQQ seen 0.82–0.88, UPRO 0.89–0.91, SPXL 0.84–0.97). These are the conservative task-specified defaults. The ER is the dominant input, so we also ran an **ER sensitivity** (below) to bracket it; the WASH verdict is robust across the plausible ER range (even at ER 0.70% the broad-cap OOS margin is only ~+5–6 pp at zero spread, and any realistic spread still erases it).

2. **Bid/ask spread + slippage on turnover (TRADING cost — replaces the flat 2 bps).**
   `trade_cost_today = (spread_bps_per_side / 10000) * abs(w_today − w_prev)`. Per-side, charged on abs change in weight (a full 0→1 entry pays the full per-side; a 0.62→0.60 nudge pays proportionally). Central realistic defaults: **TQQQ 2 bps** (extremely liquid), **UPRO/SPXL 4 bps** (liquid but wider). Swept to **{2, 5, 10, 15, 20, 30} bps** for the breakeven. The continuous-daily-rebalance book is the cost-vulnerable part — modeled honestly/pessimistically.

3. **Daily-reset tracking-error (DISCLOSED, not modeled).** We do **not** model intraday daily-reset path dependence. The adjclose series already bakes in the sleeve's *realized* daily-reset tracking, which makes an adjclose-based sim **optimistic vs a live book** that rebalances at intraday prices into choppy daily-reset drag. Disclosed as a caveat (see Caveats) rather than over-engineered.

**Cost application** (mirrors the existing engine, multiplicative, same day):
`new_eq = eq * (1 + blended) * (1 − trade_cost) * (1 − er_cost)`.

---

## (a) Full-window, NET of realistic cost — and the drag's bite

Config (all sleeves): `target_ann_vol=0.25, vol_window=20, w_max=1.0, gate=sma200, vix_gate=off`, each sleeve's full available history vs SPX on the same dates.

| Sleeve | Window | OLD optimistic tot | **NET tot (real cost)** | Drag | Net CAGR | Net maxDD | Net Sharpe | avgW | rebal | vs SPX (net) |
|---|---|---|---|---|---|---|---|---|---|---|
| TQQQ | 2010-02→2026-06 | +2,025.5% | **+1,880.8%** | −144.7 pp | 20.12% | −34.79% | 0.842 | 0.516 | 3,238 | SPX +586.7% → **+1,294 pp** |
| UPRO | 2009-06→2026-06 | +1,241.5% | **+1,089.9%** | −151.5 pp | 15.6% | −31.59% | 0.73 | 0.628 | 2,865 | SPX +704.7% → +385 pp |
| SPXL | 2008-11→2026-06 | +1,337.6% | **+1,166.2%** | −171.3 pp | 15.6% | −31.75% | 0.74 | ~0.63 | 2,917 | SPX +677.3% → +489 pp |

The drag (OLD optimistic → NET) is **−145 to −171 pp of total return** over ~16–18 years. On the FULL window every sleeve still beats SPX on raw return by a wide margin — but the full-window beat is dominated by the **in-sample** 2009–2017 leveraged-bull run; the honest test is the frozen-OOS below.

**Cost decomposition (cumulative drag fraction over the full window):** the **ER is roughly 2× the trading cost.**

| Sleeve | cum ER drag | cum trade drag | ER : trade |
|---|---|---|---|
| TQQQ | 7.05% | 2.36% | ~3.0× |
| UPRO | 9.66% | 4.64% | ~2.1× |
| SPXL | 10.35% | 4.68% | ~2.2× |

This is the crux: the previously-**entirely-unmodeled** expense ratio is the larger of the two real costs.

---

## (b) Frozen-OOS (split @ 2018-01-01), NET of cost — THE KEY NUMBERS

Does the post-2018 raw beat over SPX **still hold after realistic cost**? (Compared to the pre-cost survivorship-report margins: UPRO +186 vs +175 ≈ +11 pp, SPXL +187 vs +175 ≈ +12 pp.)

| Sleeve | OOS net strat ret | OOS SPX ret | **Net OOS margin** | Pre-cost margin (survivorship rpt) | Verdict |
|---|---|---|---|---|---|
| **TQQQ** | +353.8% | +174.7% | **+179.1 pp** | (fat, ~+193 pp pre-cost) | ✅ **SURVIVES** |
| **UPRO** | +170.0% | +174.7% | **−4.7 pp** | +11.0 pp | ❌ **WASH** |
| **SPXL** | +170.3% | +174.7% | **−4.4 pp** | +12.2 pp | ❌ **WASH** |

**TQQQ's OOS beat is fat and survives** every realistic cost level. **UPRO and SPXL flip from a thin positive pre-cost margin to NEGATIVE net of cost** — the post-2018 out-of-sample period, the part you'd actually have traded forward, **trails SPX once you pay the real ER + spread.** The broad-cap "edge" was an artifact of the optimistic cost model.

---

## (c) Breakeven sensitivity — how much cost headroom the thin edge has

At the fixed real ER, sweep per-side `spread_bps` and read the OOS margin vs SPX:

**OOS margin (pp) by per-side spread bps:**

| per-side bps | TQQQ | UPRO | SPXL |
|---|---|---|---|
| 2 | +179.1 ✅ | −1.4 ❌ | −1.1 ❌ |
| 5 | +172.2 ✅ | −6.3 ❌ | −6.0 ❌ |
| 10 | +161.0 ✅ | −14.3 ❌ | −14.1 ❌ |
| 15 | +150.1 ✅ | −22.1 ❌ | −21.9 ❌ |
| 20 | +139.5 ✅ | −29.7 ❌ | −29.4 ❌ |
| 30 | +119.0 ✅ | −44.1 ❌ | −43.9 ❌ |

**Fine grid near the UPRO/SPXL crossing (real ER applied):**

| per-side bps | UPRO OOS margin | SPXL OOS margin |
|---|---|---|
| 0.0 | +1.9 ✅ | +2.3 ✅ |
| 0.5 | +1.1 ✅ | +1.4 ✅ |
| 1.0 | +0.3 ✅ | +0.6 ✅ |
| 1.5 | −0.6 ❌ | −0.3 ❌ |
| 2.0 | −1.4 ❌ | −1.1 ❌ |

**Breakeven per-side spread (where OOS margin → 0):**
- **TQQQ:** > 30 bps/side (still +119 pp at 30 bps) — enormous headroom.
- **UPRO:** **≈ 1.0–1.5 bps/side.**
- **SPXL:** **≈ 1.0–1.5 bps/side.**

Both broad-cap sleeves die at **~1–1.5 bps per side, which is below their realistic half-spread (~3–4 bps).** The edge has essentially **zero** cost headroom.

**ER sensitivity (spread = 0, isolating the ER):** even with NO trading cost at all, the ER alone leaves only a razor-thin OOS margin that any realistic spread erases:

| ER (spread=0) | UPRO OOS margin | SPXL OOS margin |
|---|---|---|
| 0.00% | +14.5 ✅ | +15.7 ✅ |
| 0.30% | +10.3 ✅ | +11.5 ✅ |
| 0.50% | +7.5 ✅ | +8.7 ✅ |
| 0.70% | +4.8 ✅ | +5.9 ✅ |
| real (0.91/0.97%) | +1.9 ✅ | +2.3 ✅ |

The ER consumes ~12.6 of the ~14.5–15.7 pp gross OOS margin. The WASH verdict is **robust across the plausible ER range** — even a generous ER of 0.70% leaves only ~+5 pp, which the realistic ~3–4 bps/side spread then wipes out.

---

## Honesty & method notes

- **Negative result is the most valuable outcome here, and it is the true one.** We did **not** massage costs down to keep the broad-cap result alive: the ER (the single most-impactful term) is taken from published issuer numbers, and the spread is set at *realistic* (not punitive) central levels, with the breakeven shown so anyone can read the headroom. The broad-cap WASH stands.
- **No lookahead (re-locked).** Costs depend only on today's/yesterday's weights, both decided from data with date ≤ the decision day. `test_realcost_no_lookahead_future_vol_spike` confirms a future sleeve-price spike changes no prior held-day weight **and** no prior cost — with ER+spread active.
- **Numbers reproduce.** The realcost engine at **ER=0, spread=2 bps reduces EXACTLY** (max |Δequity| = 0.00e+00, total-return diff = 0.00e+00) to the prior voltarget engine with `switch_cost_bps=2` — reproducing the survivorship report's numbers to the digit (TQQQ +2025.5%, UPRO +1241.5%, SPXL +1337.6%). So the only difference between this engine and the prior one is the two added cost terms, exactly as intended. Verified across TQQQ/UPRO/SPXL and the binary baseline.

## Caveats (disclosed)

1. **Survivorship (unchanged, and now MORE decisive).** UPRO/SPXL/SOXL exist because their indices rose; the broad-cap version was the *lower-survivorship* hedge against TQQQ-specificity. With the broad-cap version now a **WASH net of cost**, the only surviving member is **TQQQ — the most survivorship-suspect sleeve** (3x Nasdaq specifically). This materially **weakens** the promotion case for the whole family: the part that survives realistic cost is exactly the part most attributable to a single historical winner.
2. **adjclose-optimism vs intraday drag.** The sim rebalances at close-to-close on split/div-adjusted closes. A live book rebalancing ~3,000×/yr at intraday prices into leveraged-ETF daily-reset tracking drag would do **worse**, not better. So the NET numbers here are still an **upper bound** on a live result — which makes the broad-cap WASH verdict, if anything, conservative (the true live margin would be more negative).
3. **ER assumption.** Published ERs vary a few bps by source/date (flagged above). The ER sensitivity shows the WASH verdict holds across the plausible range.
4. **Single frozen split.** OOS is a single 2018-01-01 cut (matching the prior reports for apples-to-apples). A rolling walk-forward would further stress-test TQQQ's surviving edge; that remains the recommended next step on TQQQ only.

---

## Bottom line for promotion

- **Broad-cap leveraged-long (UPRO/SPXL): do NOT promote.** Net of realistic cost it is a **wash** — the out-of-sample beat over SPX is **negative** (−4.7 / −4.4 pp), and the breakeven spread (~1–1.5 bps/side) is below the real half-spread. The lower-survivorship version of the family has no demonstrable edge once you pay real costs.
- **TQQQ: the only survivor**, with a fat +179 pp net OOS margin and >30 bps/side of cost headroom — **but** it is the single most survivorship-exposed sleeve, so any promotion must carry that caveat prominently and (recommended) a rolling walk-forward before any further step. Even then: **paper/research only.**

*Files: engine `backtest_daily_voltarget_realcost.py`, results `execution_drag_result.json`, tests `tests/test_leveraged_long_trend_realcost.py` (10 new, all green; suite 391→401). Protected runner md5s unchanged.*
