# Leveraged-Long Vol-Target — Realistic Execution-Drag Re-Costing

**Date:** 2026-06-09
**Status:** PAPER / RESEARCH ONLY · quarantine candidate · never live · no real orders
**Engine:** `backtest_daily_voltarget.run_backtest_voltarget` — **UNTOUCHED**. This study post-processes its weight path (recovers cost-free gross daily factors, rebuilds equity under a harsher cost model, re-stats with the engine's own `_stats_from_equity`). Protected runner md5s verified unchanged.
**Artifacts:** `strategies_candidates/leveraged_long_trend/recost_voltarget.py` · `recost_voltarget_result.json` · tests `tests/test_leveraged_long_recost.py` (12, green) · full suite 413/413.

---

## TL;DR — VERDICT

**The off-TQQQ (broad-cap) out-of-sample SPX beat does NOT survive realistic costs. It dies the moment you charge the 3x funds' expense ratio — turnover cost is almost a side-show because the margin was already razor-thin.**

- **UPRO target-0.25 frozen-OOS (the headline thin-margin cell):** SPX-beat margin goes **+11.1pp** (optimistic 2bps, no ER) → **−1.9pp** (add only the 0.95%/yr expense ratio) → **−6.8pp** (realistic) → **−18.0pp** (pessimistic). It flips from *beat* to *loss* at the very first honest cost component.
- **SPXL target-0.25 frozen-OOS:** identical shape — **+12.2pp → −0.8pp → −5.8pp → −16.9pp**. Same conclusion.
- **The broad-cap family is a WASH under honest costs.** The ~11–12pp optimistic OOS edge is entirely inside the cost-of-doing-business of holding and rebalancing a 3x ETF ~2,900×/yr.
- **TQQQ target-0.25 survives all cost levels** (OOS margin +193.5 → +154.9pp) — but that is exactly the survivorship-bias winner the cross-check already flagged: a single 3x-Nasdaq sleeve that won 2010-2026. Its survival is **not** evidence of a generalizable edge; it's the sleeve whose existence is conditioned on the outcome.

**Bottom line for the family:** this is a **leverage-harvest, not alpha**, and once you cost the leverage honestly on the sleeves that *aren't* the hand-picked Nasdaq winner, the harvest nets to ≤ SPX out-of-sample. The candidate should **not** be promoted on the strength of the broad-cap OOS beat — that beat is a costing artifact.

---

## The cost model (each component named, with assumption + rationale)

Two parts: a **per-rebalance** cost charged on the traded size `|Δw|`, and a **holding drag** charged every day on the sleeve-invested weight `w`. Net daily growth for held day *i*:

```
eq[i+1] = eq[i] · g_i · (1 − per_rebal_bps/1e4 · |Δw_i|) · (1 − ER_ann · (1/252) · w_i)
```
where `g_i` is the engine's recovered **cost-free** blended close-to-close growth factor (verified to round-trip the engine equity to ~1e-15).

### Per-rebalance components (charged on `|Δw_i|`)

| Component | Assumption | Rationale / source |
|---|---|---|
| `half_spread_bps` | 1.5 / **3.0** / 6.0 bps (opt/real/pess) | Half the bid/ask you cross moving size. Liquid 3x ETFs (TQQQ/UPRO/SPXL) are **wider than SPY**: SPY ~0.1–0.3bps spread, but these quote ~1–3bps full spread in normal markets (penny-wide on a $50–90 px) and blow out to 10–30bps+ in stress. Realistic 3bps half = 6bps round-trip — a deliberately conservative *normal-market* figure. |
| `slippage_bps` | 0.5 / **2.0** / 6.0 bps | Market impact / queue position when you actually push size through. You rebalance a real book ~daily; you are not always the passive fill. |
| `commission_bps` | **0.0** at all levels | Modern zero-commission. Stated explicitly so it's visibly an assumption, not a hidden free lunch — it really is ~0 today. |
| **`per_rebal_bps` (sum)** | **2.0 / 5.0 / 12.0** bps | Charged as `(per_rebal_bps/1e4)·|Δw|`. |

### Holding drag (charged daily on the invested portion `w` only)

| Component | Assumption | Rationale / source |
|---|---|---|
| `expense_ratio_ann` | **0.95%/yr** (real/pess), 0.0 (opt) | The 3x ETF's management fee + embedded financing/borrow cost of the daily-reset leverage. ProShares **UPRO ~0.91%/yr**, Direxion **SPXL/SOXL ~0.95–0.97%/yr**, ProShares **TQQQ ~0.84–0.88%/yr**. 0.95% is a round, slightly-conservative blended figure. Applied as `ER_ann·(1/252)·w_i` — **cash-parked capital `(1−w)` pays NO fund fee** (correct; you only hold the fund for the `w` portion). |

**Volatility decay is NOT double-counted.** The daily-reset compounding drag of leveraged ETFs is *already inside* the `adjclose` price series the engine consumes. We add **only** the explicit expense-ratio/borrow line, never a separate "decay" charge.

### The cost-sensitivity grid

| Level | per_rebal (bps on \|Δw\|) | expense ratio | meaning |
|---|---|---|---|
| **optimistic** | 2.0 | 0.00%/yr | == engine's flat 2bps. **Audit anchor.** |
| **er_only** (diagnostic) | 2.0 | 0.95%/yr | isolates the ER's damage from turnover's |
| **realistic** | 5.0 | 0.95%/yr | the honest mid case |
| **pessimistic** | 12.0 | 0.95%/yr | stress: wide spreads + impact |

---

## Audit anchor (verify-before-claim)

The **optimistic** level (2bps, ER 0) reproduces the existing `survivorship_crosscheck_result.json` net figures to within rounding — proving the cost application is correct before any conclusion is drawn:

| Cell | survivorship JSON | recost optimistic | Δ |
|---|---|---|---|
| UPRO t0.25 OOS net | +185.8% | +185.8% | 0.05pp |
| UPRO t0.25 full | 1241.5% | 1241.5% | 0.00pp |
| SPXL t0.25 OOS net | +186.9% | +186.9% | 0.03pp |
| SPXL t0.25 full | 1337.6% | 1337.6% | 0.00pp |
| UPRO/SPXL t0.20 (full & OOS) | match | match | ≤0.01pp |

---

## Results — net return / Sharpe / maxDD vs SPX at each cost level

SPX is a cost-free buy-and-hold index reference (does not move across cost levels). All figures are net of the stated cost model. OOS = frozen split @ 2018-01-01.

### UPRO target-0.25 — broad-cap PRIMARY test *(SPX: full 704.7%, OOS +174.7%, Sharpe 0.802, maxDD −33.92%)*

| Cost level | Full net ret | Sharpe | maxDD | **OOS net** | **OOS vs SPX** | OOS beats? |
|---|---|---|---|---|---|---|
| optimistic | 1241.5% | 0.746 | −31.27% | +185.8% | **+11.1pp** | ✅ |
| er_only | 1112.7% | 0.722 | −31.43% | +172.8% | **−1.9pp** | ❌ |
| **realistic** | **1071.2%** | **0.714** | **−31.68%** | **+167.9%** | **−6.8pp** | ❌ |
| pessimistic | 979.8% | 0.694 | −32.25% | +156.7% | −18.0pp | ❌ |

### SPXL target-0.25 — broad-cap alt-issuer *(SPX: full 677.3%, OOS +174.7%, Sharpe 0.719, maxDD −33.92%)*

| Cost level | Full net ret | Sharpe | maxDD | **OOS net** | **OOS vs SPX** | OOS beats? |
|---|---|---|---|---|---|---|
| optimistic | 1337.6% | 0.746 | −31.42% | +186.9% | **+12.2pp** | ✅ |
| er_only | 1199.0% | 0.723 | −31.58% | +173.9% | **−0.8pp** | ❌ |
| **realistic** | **1154.2%** | **0.715** | **−31.83%** | **+168.9%** | **−5.8pp** | ❌ |
| pessimistic | 1055.6% | 0.695 | −32.40% | +157.8% | −16.9pp | ❌ |

### TQQQ target-0.25 — the survivorship winner (for contrast) *(SPX: full 586.7%, OOS +174.7%, Sharpe 0.773, maxDD −33.92%)*

| Cost level | Full net ret | Sharpe | maxDD | **OOS net** | **OOS vs SPX** | OOS beats? |
|---|---|---|---|---|---|---|
| optimistic | 2025.5% | 0.859 | −34.52% | +368.2% | +193.5pp | ✅ |
| er_only | 1862.6% | 0.840 | −34.82% | +351.9% | +177.2pp | ✅ |
| **realistic** | **1794.3%** | **0.832** | **−35.06%** | **+345.1%** | **+170.4pp** | ✅ |
| pessimistic | 1644.2% | 0.812 | −35.60% | +329.6% | +154.9pp | ✅ |

### target-0.20 (both broad-cap) — for completeness

t0.20 was **already** an OOS fail even at the optimistic 2bps (UPRO −43.6pp, SPXL −42.8pp), consistent with the survivorship cross-check. It only sinks further with cost (UPRO realistic −56.1pp; SPXL realistic −55.4pp). So **t0.25 was the *only* broad-cap OOS beat there ever was — and it's the one that dies.**

---

## At what cost level does the broad-cap OOS beat survive? — plain answer

**Only at the optimistic 2bps-and-zero-expense-ratio level — i.e. the unrealistic one.** The break happens at the *very first* honest component: adding nothing but the **0.95%/yr expense ratio** (turnover still at the optimistic 2bps) already flips UPRO to −1.9pp and SPXL to −0.8pp. There is **no realistic cost level at which the broad-cap OOS beat survives.** The "realistic" mid case (5bps + 0.95% ER) leaves UPRO at −6.8pp and SPXL at −5.8pp; the pessimistic case at −18.0 / −16.9pp.

Mechanistically: the vol-targeted book rebalances ~2,865–3,329×/yr, so turnover cost is real but small *per trade* (each `|Δw|` nudge is tiny). The dominant drag is the **expense ratio applied every day to a ~50–63% average sleeve weight** — roughly `0.95% × 0.60 ≈ 0.57%/yr` of perpetual bleed, which over ~8 OOS years compounds to more than the entire ~11–12pp margin.

---

## Honest asterisks (kept, not massaged)

- **Leverage-harvest, not alpha.** Even where it "beats" (TQQQ), the mechanism is harvesting the upward drift of a leveraged sleeve in a bull-dominated sample, not generating risk-adjusted edge — note Sharpe ≤ SPX on UPRO at every cost level (0.71–0.75 vs 0.802), and only marginally above on SPXL.
- **Survivorship reduced, not eliminated.** UPRO/SPXL/SOXL are themselves survivors; TQQQ most of all. The fact that *only* the hand-picked Nasdaq winner clears realistic costs is the survivorship story made quantitative.
- **Thin OOS margins were the whole risk, and they materialized.** The cross-check called the off-TQQQ OOS margins "thin" (UPRO +11pp). This study confirms thin → negative under honest costs.
- **maxDD compression is real and cost-robust** (UPRO/SPXL hold ~−31–32% vs the binary's −51%, barely moving across cost levels) — but a drawdown-compressed book that nets ≤ SPX out-of-sample is not a promotion case; you can get SPX's return at SPX's drawdown by just holding SPX, with none of the 3x-ETF fee/turnover/borrow exposure.
- **Costs modeled are normal-market.** Real stress-window spreads on 3x ETFs blow out far past the pessimistic 6bps half-spread; the true tail cost is worse than even the pessimistic column, which makes the verdict more robust, not less.

---

## Recommendation

Do **not** promote the leveraged-long vol-target family on the basis of the broad-cap OOS SPX beat — **that beat is a costing artifact that disappears under the funds' own expense ratio.** The only sleeve that survives honest costs (TQQQ) is the one whose selection is conditioned on the outcome, so it carries no out-of-sample promise. Keep the family quarantined / shelved as a documented **leverage-harvest with no honest edge off the survivorship winner**, not a tradeable signal.
