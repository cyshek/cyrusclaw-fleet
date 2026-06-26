# Leveraged-Trend — Realistic Execution-Drag Re-Test (live-fill calibrated)

**Date:** 2026-06-25
**Status:** PAPER / RESEARCH ONLY · candidate quarantined · never live · no real orders placed by this study
**Mandate:** last honest execution gate before the leveraged-trend family (TQQQ / UPRO / SPXL vol-target) could be considered for a paper clock.
**Engine:** `backtest_daily_voltarget.run_backtest_voltarget` — **UNTOUCHED**. This study (a) measures real per-trade friction from the live Alpaca book, (b) re-costs the engine's weight path under that empirically-grounded cost model, (c) re-stats. All 7 protected runner/strategy md5s verified unchanged; full suite 831 passed / 2 skipped.
**Artifacts:** `reports/_leveraged_trend_empirical_slip.json` (live slip measurement) · `strategies_candidates/leveraged_long_trend/recost_voltarget.py` (+`empirical` cost level) · `recost_voltarget_result.json` (regenerated) · tests `tests/test_leveraged_long_recost.py` (12, green).

---

## TL;DR — VERDICT: **NO-GO (broad-cap) / CONDITIONAL-but-not-promotable (TQQQ)**

**The broad-cap (UPRO/SPXL) out-of-sample SPX beat does NOT survive realistic costs — and this re-test, calibrated to 16 *real* live fills, makes the conclusion stronger, not weaker: the beat dies on the funds' expense ratio alone, with execution friction now empirically *exonerated* as a side-show.**

- **Live-measured execution cost is CHEAP and BENIGN.** 16 real TQQQ market-order fills (2026-06-15..25, ~$100 notional) vs the Alpaca NBBO mid at fill time: **mean half-spread crossed = 1.82 bps, mean adverse slip beyond mid = 0.34 bps** (several fills filled *better* than mid; max single adverse slip 2.66 bps). That is *below* the 5 bps "realistic" turnover figure the prior 2026-06-09 study assumed — so if anything the earlier study was conservative on turnover.
- **Yet the broad-cap OOS beat still dies**, because turnover was never the binding cost. At the **empirical** cost level: **UPRO t0.25 OOS −1.7 pp**, **SPXL t0.25 OOS −0.5 pp** vs SPX. Both flip from a thin optimistic beat (+11.8 / +13.0 pp) to a loss the instant the **0.95%/yr 3x expense ratio** is charged. Empirical turnover ≈ `er_only`, confirming the ER is the whole story.
- **Sharpe does NOT hold above 0.8 for the broad-cap** at any honest cost level: UPRO/SPXL t0.25 Sharpe = **0.724** (empirical), below even SPX's own 0.805. The drawdown is compressed (~−31% vs the binary's −51%), but a DD-compressed book that nets ≤ SPX OOS at sub-SPX Sharpe is not a promotion case — you can buy SPX's return at SPX's risk by holding SPX, without 3x fee/turnover/borrow exposure.
- **TQQQ t0.25 survives** all cost levels (empirical OOS **+178.1 pp**, Sharpe **0.837** > SPX 0.805) — **but it is the survivorship winner** the cross-check already flagged: the single 3x-Nasdaq sleeve whose existence is conditioned on having won 2010–2026. Its survival is not evidence of a generalizable edge, so it does **not** clear an honest go-live gate on its own.

**Bottom line:** this is a **leverage-harvest, not alpha.** With execution now measured rather than assumed, the family's failure is pinned squarely on the holding cost of leverage. **NO-GO** for promoting the broad-cap family to a paper clock. TQQQ-only is **CONDITIONAL** at best and should not be promoted on outcome-conditioned evidence.

---

## Part 1 — Real per-trade friction from the live book (the new ingredient)

Prior cost models *assumed* a 1.5 / 3.0 / 6.0 bps half-spread. This study **measures** it. For each of the 16 real (uuid-order-id) TQQQ fills in `tournament.db`, I pulled the Alpaca v2 NBBO quote (feed=iex) at-or-before `filled_at`, took `mid = (bid+ask)/2`, and computed the signed slip (`buy: (fill−mid)/mid`; `sell: (mid−fill)/mid`; positive = adverse) and the structural half-spread crossed (`(ask−bid)/2/mid`).

| Metric (bps) | mean | median | min | max | stdev |
|---|---|---|---|---|---|
| **adverse slip beyond mid** | **+0.34** | +0.42 | −2.93 | +2.66 | 1.23 |
| **half-spread crossed** | **1.82** | 1.80 | 0.61 | 4.00 | — |

- **Implied one-way per-rebalance friction ≈ 1.82 (half-spread) + 0.34 (slip) ≈ 2.2 bps.** Round-trip ≈ 4.3 bps of half-spread floor + ~0.7 bps of adverse slip.
- Fills were near-instant (6–52 ms), confirming genuine liquid market fills.
- **The slip is tiny and frequently favourable.** TQQQ at $100 notional in calm 2026 is a benign execution environment — the market-order penalty over mid is well under 1 bp on average.

### Honest caveats on the measurement (kept, not massaged)
- **TQQQ only.** UPRO/SPXL were *never traded live* (0 real fills) — their real spreads are **wider** (less AUM/volume), so the broad-cap figure used in the re-cost (same 1.82/0.34) is, if anything, **optimistic** for UPRO/SPXL. The verdict (they fail) is therefore robust to this — a wider real spread only worsens their case.
- **Calm regime + open liquidity.** June-2026 is low-vol; 3x-ETF spreads blow out to 10–30 bps+ in stress. The `pessimistic` column (6 bps half-spread) is the stress proxy and the family fails there too.
- **$100 fractional notional → no size/impact.** A real book pushing size pays more queue/impact than these fills show.
- **n=16 is small** — order-of-magnitude calibration, not a precise constant. It is used to *bound* turnover cost, and that bound lands below the prior "realistic" assumption, which is the only claim it needs to support.

---

## Part 2 — Re-cost grid (engine weight-path post-processed; audit-anchored)

Net daily growth for held day *i* (engine's recovered cost-free factor `g_i`):
```
eq[i+1] = eq[i] · g_i · (1 − per_rebal_bps/1e4 · |Δw_i|) · (1 − ER_ann · (1/252) · w_i)
```

| Cost level | half-spr | slip | per-rebal (on \|Δw\|) | ER/yr | meaning |
|---|---|---|---|---|---|
| optimistic | 1.5 | 0.5 | 2.0 bps | 0.00% | == engine baseline (**audit anchor**) |
| er_only | 1.5 | 0.5 | 2.0 bps | 0.95% | isolates ER damage from turnover |
| **empirical** | **1.82** | **0.34** | **2.16 bps** | **0.95%** | **live-fill measured turnover + real 3x ER** |
| realistic | 3.0 | 2.0 | 5.0 bps | 0.95% | prior honest mid case |
| pessimistic | 6.0 | 6.0 | 12.0 bps | 0.95% | stress: wide spreads + impact |

**Audit anchor preserved:** the `optimistic` level reproduces the engine baseline net figures to rounding (verified by `tests/test_leveraged_long_recost.py`, 12 green), proving the cost application is correct before any conclusion.

### Results — t0.25 (the only broad-cap config that EVER beat OOS), full Sharpe + frozen-OOS @ 2018

**UPRO t0.25** *(SPX ref: OOS +178.2%, full Sharpe 0.805, maxDD −33.92%)*

| level | Sharpe | OOS net | OOS vs SPX | beats? | maxDD |
|---|---|---|---|---|---|
| optimistic | 0.748 | +190.0% | **+11.8 pp** | ✅ | −31.27% |
| er_only | 0.724 | +176.8% | −1.4 pp | ❌ | −31.43% |
| **empirical** | **0.724** | **+176.5%** | **−1.7 pp** | **❌** | −31.44% |
| realistic | 0.716 | +171.8% | −6.4 pp | ❌ | −31.68% |
| pessimistic | 0.696 | +160.5% | −17.7 pp | ❌ | −32.25% |

**SPXL t0.25** *(SPX ref: OOS +178.2%, full Sharpe 0.721, maxDD −33.92%)*

| level | Sharpe | OOS net | OOS vs SPX | beats? | maxDD |
|---|---|---|---|---|---|
| optimistic | 0.748 | +191.2% | **+13.0 pp** | ✅ | −31.42% |
| er_only | 0.725 | +178.0% | −0.2 pp | ❌ | −31.58% |
| **empirical** | **0.724** | **+177.7%** | **−0.5 pp** | **❌** | −31.59% |
| realistic | 0.717 | +172.9% | −5.3 pp | ❌ | −31.83% |
| pessimistic | 0.697 | +161.5% | −16.7 pp | ❌ | −32.40% |

**TQQQ t0.25 — the survivorship winner (contrast)** *(SPX ref: OOS +172.7%, full Sharpe 0.768, maxDD −33.92%)*

| level | Sharpe | OOS net | OOS vs SPX | beats? | maxDD |
|---|---|---|---|---|---|
| optimistic | 0.856 | +367.5% | +194.8 pp | ✅ | −34.52% |
| er_only | 0.837 | +351.2% | +178.5 pp | ✅ | −34.82% |
| **empirical** | **0.837** | **+350.8%** | **+178.1 pp** | **✅** | −34.83% |
| realistic | 0.829 | +344.4% | +171.7 pp | ✅ | −35.06% |
| pessimistic | 0.809 | +328.8% | +156.1 pp | ✅ | −35.60% |

**t0.20 (both broad-cap):** already an OOS fail at the optimistic 2 bps (UPRO −44.3 pp, SPXL −43.4 pp) and worse at empirical (UPRO −53.4 pp, SPXL −52.6 pp). So **t0.25 was the only broad-cap OOS beat that ever existed — and it is the one that dies.**

---

## Answers to the four gate questions

1. **Realistic per-trade friction (TQQQ/UPRO/SPXL @ ~$100):** measured from live TQQQ fills = **1.82 bps half-spread + 0.34 bps adverse slip ≈ 2.2 bps one-way**. UPRO/SPXL not traded live → real spreads wider, so this is a *floor* for them.
2. **Re-ran walk-forward sweep (TQQQ & UPRO t0.25, + SPXL, + t0.20/binary) with drag baked in:** done — full + frozen-OOS @ 2018, 5 cost levels incl. the new `empirical`.
3. **Does the OOS beat-SPX-raw survive? Does Sharpe hold above 0.8?**
   - **Broad-cap (UPRO/SPXL): NO and NO.** OOS beat flips negative at the very first honest cost (ER): empirical UPRO **−1.7 pp**, SPXL **−0.5 pp**. Sharpe **0.724** < 0.80 (and < SPX 0.805) at every honest level.
   - **TQQQ: YES and YES** (empirical OOS **+178.1 pp**, Sharpe **0.837**) — but survivorship-conditioned, not a generalizable edge.
4. **Verdict report:** this file. **Clear call below.**

---

## GO / NO-GO / CONDITIONAL

- **Broad-cap leveraged-trend (UPRO / SPXL vol-target): 🔴 NO-GO.** The only OOS beat that ever existed (t0.25) is a costing artifact that disappears under the funds' own expense ratio. Live-measured execution is cheaper than previously assumed, which *removes execution as an excuse* and pins the failure on the holding cost of 3x leverage. Sub-0.8 Sharpe, negative OOS margin. Do not promote to a paper clock.
- **TQQQ-only vol-target: 🟡 CONDITIONAL — not promotable on current evidence.** It survives honest costs (the only sleeve that does), but its selection is conditioned on the outcome (it is *the* 3x-Nasdaq sleeve that won the sample). Survival here is the survivorship story made quantitative, not an out-of-sample promise. It would need either (a) a survivorship-clean construction (a rule that picks the leverage sleeve *ex-ante*, not TQQQ-because-it-won) or (b) an explicit acknowledgement that any paper clock on it is a single-name leverage-harvest bet with a −35% drawdown profile and a real-money 3x rail conversation — **not** a validated edge. Recommend keep shelved as a documented leverage-harvest.

**Family-level call: NO-GO for promotion.** The execution-drag gate is now closed with live data: the leveraged-trend family does not carry an honest, generalizable, cost-surviving edge over SPX. Keep quarantined.

---

## Honest asterisks (kept)
- **Leverage-harvest, not alpha** — even TQQQ's survival is harvesting a leveraged bull-sample drift, not risk-adjusted edge (broad-cap Sharpe ≤ SPX everywhere).
- **Survivorship reduced, not eliminated** — UPRO/SPXL/TQQQ are all survivors; that only TQQQ clears is the bias quantified.
- **maxDD compression is real and cost-robust** (broad-cap ~−31% vs binary −51%) but does not rescue a ≤-SPX-OOS, sub-0.8-Sharpe book.
- **Measured costs are normal-market** — true stress-window 3x spreads exceed even the pessimistic column, making the NO-GO more robust, not less.
- **Volatility decay not double-counted** — it is already inside the `adjclose` series the engine consumes; only the explicit ER line is added.
