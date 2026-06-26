# Haven eff-N / Sharpe REFRESH — is wiring a 3rd haven sleeve worth it NOW, on the NEW QUARTERLY 2-sleeve book?

**Date:** 2026-06-25
**Assignment:** main — REFRESH the haven give-up math against the book that changed TODAY to **quarterly** rebalance. ~90% answered already on disk; this re-runs the one genuinely-new part: the prior haven frontier was computed vs the OLD **monthly** 2-sleeve baseline; the live book is now **quarterly** (raw 1068% / Sharpe 1.018), so the give-up must be re-measured vs the new, better baseline — and the haven's own intra-sleeve cadence re-tested under today's "cadence is signal-type-specific" lesson.
**Engine:** `_haven_effn_refresh.py` → `reports/_haven_effn_refresh_result.json`. Reuses the validated `_allocator_blend_tests.build_sleeves()` + `blend_portfolio()` drift/cost/stats verbatim; rebuilds the haven sleeve cleanly from the documented spec (the scratch `_haven_*_tests.py` are gone from disk). Haven assets GLD/TLT/DBC/UUP refetched/cached via `runner.daily_bars_cache.get_daily` (keyless Yahoo-v8 adjclose). **No protected/live files / `params.json` / `strategy.py` / crontab / paper clock / `.db` touched — RESEARCH ONLY; applying any finding is the parent's job.**

---

## ⭐ TL;DR — VERDICT: **DON'T-WIRE under the raw-return mandate / SHELF-WITH-TRIGGER.** The quarterly baseline does **NOT** change the prior calculus — it makes the raw give-up *slightly worse* (≈172pp vs the old ≈161pp), the sweep is still **monotonic with no interior Sharpe optimum**, and 10% is still the principled shelf if/when the mandate shifts.

Refreshing the frontier against the new quarterly book (which I **reproduced to the exact target: raw 1068.3% / Sharpe 1.0180 / maxDD −24.91%** before adding anything) confirms the prior conclusion holds and is, if anything, marginally *stronger* against wiring:

- **Haven-10 raw give-up vs the NEW quarterly baseline: −171.9pp** (aligned, identical-date-set) / **−177.7pp** vs the full-core quarterly baseline — *worse* than the prior −161pp vs monthly, because the quarterly baseline is a higher bar to give up from. Haven-10 raw = **890.7%**, still **+318.7pp over SPX** (572%).
- **For that ~172pp of raw return you buy:** OOS Sharpe 1.149 → **1.178** (+0.029), full Sharpe 1.017 → **1.037**, maxDD −24.7% → **−22.4%** (~2.3pp shallower), **2022-DD −16.2% → −14.5%** (~1.7pp shallower), and eff-N **1.494 → 2.323** (+0.83 independent bets, +55%).
- **The sweep is MONOTONIC** — every +5pp haven costs ~**80pp raw** for ~**+0.011 Sharpe**, with **NO interior Sharpe optimum** (Sharpe rises strictly to the 20% edge; raw falls strictly). Same shape as the prior study; 10% is a *pre-registered shelf*, not an optimizer's pick. I do **not** fabricate an optimum.
- **The haven sleeve itself PREFERS QUARTERLY** (the signal-type lesson transfers): as a risk-parity/low-vol defensive leg it does marginally better rebalanced quarterly than monthly — standalone Sharpe 0.793 vs 0.772, OOS 1.263 vs 1.218; in-book at 10% raw 893.8% vs 890.7%, Sharpe 1.0373 vs 1.0366. So the *recommended haven config is quarterly-internal* (matching the now-quarterly top-level book), not monthly.
- **Canary CLEAN; harness FAITHFUL** — monthly 2-sleeve reproduced two independent ways to machine precision, quarterly reproduced to target.

**Bottom line for the raw-return mandate:** the haven is a strictly-dominated raw-return trade (gives up ~172pp to buy de-concentration + ~2pp shallower DD + ~0.03 OOS Sharpe). **The quarterly switch did not move the decision.** Recommendation: **DON'T-WIRE now; keep it SHELF-READY with a clear trigger** (see below). If/when wired, the pinned config is **GLD/TLT/DBC/UUP inv-vol parity, 10% fixed, QUARTERLY internal rebalance, 2bps**.

---

## 1. Sanity control — the harness reproduces the new quarterly baseline EXACTLY (proves it's faithful)

Before touching the haven, I reproduced the live 2-sleeve book at both cadences on the full core common window (2010-02-12 → 2026-06-25, 4116 days):

| 2-sleeve config | Raw net | Full Sharpe (pop) | fp cont Sharpe | OOS Sharpe | maxDD | 2022-DD | avg w_tqqq | Match? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| monthly (validated engine `ab.blend_portfolio`) | 985.0% | 1.0030 | — | — | −23.90% | — | — | — |
| monthly (my cadence-trigger loop) | 985.0% | 1.0030 | — | — | −23.90% | — | — | ✅ Δ<1e-6 |
| **quarterly (THE NEW LIVE BASELINE)** | **1068.3%** | **1.0180** | 1.0179 | **1.1508** | **−24.91%** | −16.08% | 0.3470 | — |
| *cadence-sweep report target* | *1068.0%* | *1.018* | — | *1.151* | *−24.9%* | — | — | ✅ |

**Read:** The monthly baseline reproduces the validated 985.0% / 1.003 / −23.90% **two independent ways to machine precision**, and the quarterly config reproduces the cadence-sweep report's **1068% / 1.018 / −24.9% / OOS 1.151** to the decimal. The harness is a faithful superset of the live engine — the ONLY thing that changes downstream is adding the haven leg. ✅

---

## 2. Refreshed 3-sleeve frontier vs the QUARTERLY baseline

3-sleeve = TQQQ vol-target + sector-rotation top-2 + **GLD/TLT/DBC/UUP haven**, haven fixed at {0,5,10,15,20}%, the rest split TQQQ/ROT by inv-vol, **top-level QUARTERLY rebalance** (matching the now-quarterly live book), 2bps. Aligned traded window **2010-02-16 → 2026-06-25 (4115 days)** — one early date drops because DBC/UUP need a trailing vol day; haven=0% on this window (raw **1062.6%**) is the apples-to-apples baseline (identical date set as the haven runs). **SPX on the same path = 572.0% raw.**

**Recommended haven cadence = QUARTERLY-internal** (see §3); table below is the **quarterly-internal-haven** frontier (the monthly-haven frontier is within ~3pp everywhere and shown beneath):

| haven wt | Raw net | full Sharpe | OOS Sharpe | maxDD | 2022-DD | eff-N (3-leg) | avg haven wt | beats SPX raw? |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| **0% (baseline)** | **1062.6%** | 1.0166 | 1.1494 | −24.69% | −16.23% | 1.494 *(2-leg)* | 0% | ✅ |
| 5% | 975.4% | 1.0266 | 1.1641 | −23.54% | −15.36% | — | 5% | ✅ |
| **10%** | **893.8%** | **1.0373** | **1.1801** | **−22.38%** | **−14.49%** | **2.323** | 10% | ✅ |
| 15% | 817.5% | 1.0488 | 1.1976 | −21.21% | −13.61% | — | 15% | ✅ |
| 20% | 746.2% | 1.0610 | 1.2166 | −20.03% | −12.72% | — | 20% | ✅ |

*Monthly-internal-haven frontier (for completeness): haven 5/10/15/20% → raw 973.7 / 890.7 / 813.2 / 740.9%, full Sharpe 1.0263 / 1.0366 / 1.0476 / 1.0594, OOS 1.1632 / 1.1783 / 1.1948 / 1.2127, maxDD −23.52 / −22.35 / −21.16 / −19.97%, 2022-DD −15.38 / −14.52 / −13.65 / −12.78%.*

**THE KEY NUMBER — haven-10 raw give-up vs the NEW quarterly baseline:**

| give-up basis | baseline raw | haven-10 raw | **give-up** |
|---|---:|---:|---:|
| vs **aligned** quarterly baseline (identical date set — the clean read) | 1062.6% | 890.7%¹ | **−171.9pp** |
| vs **full-core** quarterly baseline (headline 1068%) | 1068.3% | 890.7%¹ | **−177.7pp** |
| *(prior study, vs the OLD monthly baseline)* | *1011%* | *850%* | *−161pp* |
| cushion of haven-10 over SPX raw | — | 890.7% | **+318.7pp** |

¹ haven-10 raw = 890.7% (monthly-internal) / 893.8% (quarterly-internal); give-up quoted on the monthly-internal value to match the prior study's convention; quarterly-internal is ~3pp better (≈−169pp / −174.5pp).

**Read:** Against the higher quarterly bar, the haven-10 raw give-up is **~172pp** (aligned) — *larger* than the prior ~161pp vs monthly, simply because quarterly raised the baseline ~57pp while the haven dilutes a roughly fixed *fraction* of return. The quarterly switch therefore makes wiring the haven **marginally less attractive on raw**, not more. Every variant still clears SPX raw comfortably (+319pp at 10%).

---

## 3. Haven-sleeve cadence — the risk-parity leg PREFERS quarterly (signal-type lesson confirmed)

Today's transferable lesson is that cadence is signal-type-specific: momentum-rotation wants to ride, but a **risk-parity/low-vol defensive blend** (the inv-vol leg, and by analogy the haven) benefits from slower re-anchoring. Tested directly — rebalancing the **inter-asset reweight INSIDE the haven sleeve** monthly vs quarterly:

| haven internal cadence | standalone raw | standalone Sharpe | standalone OOS Sharpe | standalone maxDD | in-book @10% raw | in-book @10% Sharpe | in-book @10% OOS |
|---|---:|---:|---:|---:|---:|---:|---:|
| monthly (196 rebal) | 95.9% | 0.772 | 1.218 | −14.32% | 890.7% | 1.0366 | 1.1783 |
| **quarterly (65 rebal)** | **102.3%** | **0.793** | **1.263** | −15.82% | **893.8%** | **1.0373** | **1.1801** |

**Read:** **Quarterly wins** on standalone raw (+6.3pp), standalone Sharpe (+0.020), standalone OOS Sharpe (+0.045), and in-book at 10% on raw (+3.1pp), Sharpe, and OOS — at ⅓ the rebalances. (Quarterly's standalone maxDD is ~1.5pp deeper, the same small DD-for-return trade the top-level cadence sweep saw; in-book the difference washes out.) **This confirms the signal-type lesson transfers to the haven:** as a low-vol (5.5–5.6% ann) inv-vol-parity defensive leg, the haven should be rebalanced **quarterly**, matching the now-quarterly top-level book — not monthly. The recommended haven config is therefore **quarterly-internal**.

---

## 4. eff-N refresh — 2-leg → 3-leg reproduces the prior frontier on the current window

**Formula (quoted, matches the frontier report):** effective number of independent bets = **participation ratio of the daily-return correlation matrix** = **(trace)² / Σᵢⱼ Cᵢⱼ²**. For a correlation matrix trace = N, so this is **N² / Σᵢⱼ Cᵢⱼ²**. (Verified: this formula reproduces the cached frontier's 1.495 / 2.323 to 4 decimals.)

| book | eff-N (this refresh) | prior frontier |
|---|---:|---:|
| 2-leg (TQQQ vol-target + sector-rotation) | **1.4942** | 1.495 |
| 3-leg (+ haven, **monthly**-internal) | **2.3225** | 2.324 |
| 3-leg (+ haven, **quarterly**-internal) | **2.3107** | — |

3-leg daily-return correlation matrix (haven monthly):
```
              TQQQ-leg   ROT-leg   HAVEN
TQQQ-leg        1.000     0.582    -0.013
ROT-leg         0.582     1.000     0.314
HAVEN          -0.013     0.314     1.000
```

**Read:** The eff-N jump **1.494 → 2.323 (+0.83 bets, +55%)** is unchanged from the prior study and robust to the window/cadence refresh. The haven remains the genuinely-independent leg: corr to the levered-Nasdaq leg **−0.013**, to the rotation leg +0.314. (The quarterly-internal haven is a hair lower at 2.311 — quarterly re-anchoring makes the haven stream microscopically more correlated to the book, immaterial.) The de-concentration value of the 3rd sleeve is real and structural; it is what you're paying ~172pp of raw return to obtain.

---

## 5. The decision framing — under the RAW-RETURN MANDATE

**Does the quarterly baseline change the calculus? NO.** The prior logic holds intact and is marginally reinforced:

1. **The sweep is still MONOTONIC with NO interior optimum.** Raw falls strictly with haven weight (1062.6 → 975 → 894 → 818 → 746%); Sharpe rises strictly to the 20% edge (1.017 → 1.027 → 1.037 → 1.049 → 1.061). Average trade per +5pp haven: **−80.4pp raw for +0.0107 Sharpe.** There is no haven weight that maximizes Sharpe in the interior — more haven always means more Sharpe and less raw. So any chosen weight is a **mandate-driven shelf**, not an optimizer's pick. (I explicitly do not fabricate an interior optimum.)

2. **10% remains the principled shelf.** It's the pre-registered cap from the prior frontier (the inv-vol blend over-allocates the haven to ~45-60% and craters raw, so a cap is mandatory). 10% holds raw at 894% (+319pp over SPX), captures the full eff-N→2.32 de-concentration, and delivers the shallowest-meaningful 2022-DD (−14.5%) and best OOS Sharpe-per-pp-given-up.

3. **Under a PURE raw-return mandate, the 2-sleeve quarterly book strictly dominates** the headline metric (1068% vs 894% at haven-10). The haven buys de-concentration (eff-N +0.83), ~2.3pp shallower maxDD, ~1.7pp shallower 2022-DD, and +0.029 OOS Sharpe — none of which the current mandate prices. Wiring it would dilute the live book's raw return by ~172pp for benefits the mandate doesn't reward.

### Recommendation: **DON'T-WIRE-UNDER-RAW-MANDATE → SHELF-WITH-TRIGGER**

> **Do not wire the haven into the live book now.** Under the raw-return mandate it is strictly dominated (gives up ~172pp raw vs the quarterly baseline). The quarterly switch did not change this — it slightly widened the give-up.
>
> **Keep it shelf-ready with a pre-registered config and a clear trigger.** Wire it the moment ANY of these fire: (a) the mandate reinstates a risk-adjusted / drawdown bar; (b) the book's eff-N concentration (currently ~1.49, ~65% Nasdaq-tech beta) becomes a stated constraint; (c) the levered-Nasdaq sleeve's drawdown becomes the binding constraint on go-live sizing. On any trigger, the pinned operating point is:
>
> **`GLD/TLT/DBC/UUP` inverse-vol parity, fixed 10% 3rd sleeve, QUARTERLY internal rebalance (matching the quarterly top-level book), 2bps.** Expected book: raw **893.8%** (+318.7pp over SPX), full Sharpe **1.037**, OOS Sharpe **1.180**, maxDD **−22.4%**, 2022-DD **−14.5%**, eff-N **2.323**. *(Note the haven config is now QUARTERLY-internal, an update from the prior MONTHLY-internal recommendation — the signal-type lesson applies to the haven too.)*

---

## No-lookahead / canary statement — CLEAN

- **Past-only trailing vol, no lookahead.** The inv-vol target at index `i` (both the 2-leg core split and the 4-asset haven weights) is computed from returns in `[i-63, i)` — **strictly before** `i`. A future return can never change the weight applied at `i`.
- **Forward P&L is d→d+1.** Each day the buckets earn the return ending on `dates[i]` **after** any rebalance at `i`; no day's return feeds its own rebalance decision. No overlap leak.
- **Calendar triggers are causal** (month/quarter-open determined purely from the date string).
- **Adjusted-close throughout** (Yahoo v8 adjclose — correct for GLD/TLT/DBC/UUP distributions and ETF splits).
- **2bps one-way** on both inter-sleeve and intra-haven turnover (no double-counting: intra-sleeve costs are already baked into the core sleeve streams; the haven's intra-asset cost is charged inside the haven build).
- **OOS split 2018-12-31; SPX (^GSPC) on the SAME traded path** (aligned window, 572% raw).
- **Harness-faithfulness proof:** the monthly 2-sleeve reproduces the validated 985.0% / 1.0030 / −23.90% **two independent ways to machine precision**, and the quarterly config reproduces the cadence-sweep target 1068% / 1.018 / −24.9% — confirming no leak was introduced by the refresh.
- **The haven is INSURANCE** — its standalone raw (95.9% monthly / 102.3% quarterly vs SPX 572%) is **negative-relative by design, not a bug**; the book-level question is the DD/Sharpe/eff-N improvement vs the raw give-up, and every wired variant still clears SPX raw.

---

## Honest caveats

1. **The give-up GREW, not shrank.** Quarterly raised the no-haven baseline ~57pp, so haven-10's raw give-up went from ~161pp (vs monthly) to ~172pp (vs quarterly). The refresh makes the case for wiring marginally *weaker* on raw — the opposite of a free upgrade.
2. **The book-level haven benefit is INCREMENTAL** (inherited from the prior study): at a 10% sleeve, the dramatic sleeve-level all-weather transformation dilutes to ~2.3pp shallower maxDD, ~1.7pp shallower 2022-DD, +0.029 OOS Sharpe. Real, not a step-change.
3. **Aligned-window quirk:** the 3-sleeve runs start 2010-02-16 (one date later than the 2-sleeve's 2010-02-12) because DBC/UUP need a trailing vol day; this trims ~5.7pp off the no-haven baseline (1068.3% full-core → 1062.6% aligned). I report the give-up against both so neither flatters the haven.
4. **Same survivorship-bull sample** (inherited, unfixable): the haven's raw drag is largest precisely in the secular-bull tape that TQQQ exists to exploit. In a sustained inflation/rate-shock or sideways decade the haven's relative value would be higher than this sample shows — which is exactly the regime the GLD/TLT/DBC/UUP spec was built to survive (it's the only recipe flat across all 8 stress windows; see `HAVEN_RATESHOCK_PATCH`).
5. **Quarterly-internal haven is a marginal win, not a large one** (+3pp raw, +0.02 standalone Sharpe). It's the right default given the book is quarterly, but don't oversell it; monthly-internal is within ~3pp everywhere.

---

*Numbers cross-checked console↔JSON. Engine `_haven_effn_refresh.py` reuses `_allocator_blend_tests.build_sleeves/blend_portfolio` (drift/cost/stats) verbatim; haven sleeve rebuilt from the `HAVEN_RATESHOCK_PATCH` documented spec; GLD/TLT/DBC/UUP adjclose cached via `runner.daily_bars_cache`. Full numeric dump: `reports/_haven_effn_refresh_result.json`. Candidate research only — no protected/live files, `params.json`, `strategy.py`, crontab, paper clock, or `.db` touched. Applying any config change is the parent's job.*
