# Backtest Report — Cross-Sectional Momentum (Jegadeesh-Titman 12-1) on CROSS-ASSET Universe

**Pre-registered hypothesis (verbatim per main, before seeing results):**

> "Cross-asset universe because the wave-3 sector-equity universe (11 SPDR sectors) lacked dispersion — all sectors share 0.7-0.9 SPY beta. This test isolates whether the prior #1 REJECT was strategy-class (momentum doesn't work) or universe-class (sector-equity is too correlated). If cross-asset version ALSO rejects, we've ruled out both at once and the next move is clearer."

**Candidate:** `xsec_momentum_xa_38d2b2`
**Archetype:** #1 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` — cross-sectional momentum (Jegadeesh-Titman 12-1), wave-4 **cross-asset** variant.
**Sister candidate:** `xsec_momentum_236b86` (wave-3 sector-equity, REJECTED).
**Author:** trading-bench (wave-4 subagent, 2026-05-30 18:06 UTC).

**Verdict (TL;DR):** **REJECT-WITH-CAVEATS.** Cross-asset universe **substantially improved every headline number** vs sector-equity (medRet -0.36% → +0.34%, medSharpe -0.50 → +0.49, full-period Sharpe 0.30 → 1.13, return +2.04% → +6.98%) — strategy now sits *right at* the fitness gate (Sharpe 0.49 vs 0.50 cutoff, fails by 1 bp). Honest answer to the pre-registered question: **the wave-3 REJECT was substantially universe-class, not strategy-class.** The 12-1 ranking does real work when given an actually-diverse basket; what kills the candidate is the *structural* 25% bars-in-position floor that monthly K=2 of 6 cannot clear (19% deployed by design). Same floor problem documented in Pattern #2. **SPY-regime gate strictly hurts cross-asset too** (Pattern #1 generalization datum: contrary to PATTERNS.md prediction, the no-go pattern extends beyond sector-equity).

---

## 1. Strategy spec (as implemented)

| Field | Value |
|---|---|
| Universe | **6 ETFs across 4 asset classes:** `SPY` (US equity broad) · `EFA` (developed-intl equity) · `TLT` (long bonds) · `VNQ` (US REITs) · `DBC` (broad commodities) · `GLD` (gold) |
| Signal | 12-month total return SKIPPING most recent month (252-bar lookback, 21-bar skip) — Jegadeesh-Titman canonical "12-1" |
| Allocation | Long-only top-K, equal-weight per leg. **Primary K=2** (rule-of-thumb K ~ N/3 for cross-asset; N=6 ⇒ K=2). K=1 and K=3 reported as sensitivity. |
| Per-leg notional | MAX_POSITION / K. K=2 ⇒ $50/leg. K=1 ⇒ $100/leg. K=3 ⇒ $33.33/leg. |
| Rebalance | Calendar-month boundary (first tick whose YYYY-MM ≠ stored month) |
| Cost model | `alpaca_stocks` (2 bps spread, 0 fee) — all 6 symbols trade on US equity venues |
| Optional regime gate | `regime_uptrend(spy_closes, 50)` gates NEW buys only |
| Persistent state | `last_rebalance_month` (cross-flat YYYY-MM) |
| Warmup | 400 calendar days per window for the 12-1 lookback signal |

**Universe rationale.** Task spec mandated this 6-symbol basket (no deviation justified). The 6 names span US equity, intl equity, US bonds (long duration), US REITs, broad commodities, and gold — 4 distinct asset-class exposures. Binding history constraint: DBC (inception 2006-02-03) — every NAMED_WINDOWS window (earliest 2022) has full bar history for all 6 symbols. **Verified empirically:** at the earliest window's warmup-extended start (2021-02-26) all 6 had 339 bars. No window-skipping required.

**K choice.** K=2 is the primary because it preserves meaningful cross-asset rotation (you actually pick winners) while keeping per-leg notional respectable ($50, comparable to other bench positions). K=1 is degenerate "rotate-into-strongest-asset" with no diversification. K=3 (half the universe) starts looking like equal-weight buy-and-hold. Reporting all 3 lets us see whether the result is a K-knob artifact.

## 2. Bar A scorecard (per `GATE.md`, amended 2026-05-30)

Evaluated on the **K=2 without-regime-filter** variant (primary; the variant most likely to pass).

| # | Bar A bullet | Result | Verdict |
|---|---|---|---|
| 1 | All 8 named regimes pass via (a) positive return OR (b) ≥ BH-basket + ≥25% bars-in-position; (b) capped at 1 | 5/8 windows pass (a); 0 windows eligible for (b) because in-position % is 14–19% (below 25% floor) in EVERY window. 3 windows fail (2022-H1 bear, 2022-Q3 chop, 2023-Q3 chop). | **FAIL** |
| 2 | Held-out final regime (2026-recent bull) | +0.40% return, positive | **PASS** (positive, untuned) |
| 3 | Cost-aware Sharpe ≥ 0.5 on full backtest period | Full-period (1237 bars, ~5y) Sharpe **1.13** | **PASS** |
| 4 | Trade count ≥ 30 across backtest | 22 full-period (K=2); aggregate across 8 windows: 28 trades. **Below 30 floor.** | **FAIL** |
| 5 | Max drawdown ≤ 30% post-cost | Full-period **-2.00%**; worst-window -1.03% | **PASS** |
| 6 | Code review pass via AST gate | Static-import only; no eval/exec/network/file I/O | **PASS** |
| 7 | Smoke test via `./tick.sh --candidate xsec_momentum_xa_38d2b2` | `rc=0`, action=`{GLD=buy, DBC=buy}`, 1800 bars total, 2.2s | **PASS** |

**Bar A overall: FAIL** — bullet #1 fails (3 of 8 windows fail (a) AND fail (b)-floor), bullet #4 also fails (28 trades < 30). Bullet #3 *passes* — Sharpe **1.13** full-period is the highest of any candidate this wave, well above the 0.5 cutoff. The diagnosis is now structural (rebalance cadence × basket size × in-position floor + trade count under-fire), not signal-quality.

**Comparison to sector-equity wave-3 sister:**

| Bar A bullet | Sector-equity (#236b86) | Cross-asset (#xa_38d2b2 K=2) |
|---|---|---|
| #1 walk-forward | FAIL (5/8 fail) | FAIL (3/8 fail) |
| #2 held-out 2026 bull | PASS (+0.48%) | PASS (+0.40%) |
| #3 full-period Sharpe ≥ 0.5 | **FAIL (0.30)** | **PASS (1.13)** |
| #4 trade count ≥ 30 | PASS (63) | **FAIL (22)** |
| #5 maxDD ≤ 30% | PASS (-3.09%) | PASS (-2.00%) |

Cross-asset trades the "Sharpe-too-low" failure mode for the "trades-too-sparse" failure mode (K=2 over 6 names rebalanced monthly = 12-24 trades / 5y). At K=3 trade count rises (38 across windows) and full-period count is similar but a different failure mode — see §5.

## 3. Walk-forward summary — primary K=2 (8 windows, +400d warmup per window)

### 3a. K=2 without regime filter (PRIMARY)

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | 4 | 1 | -0.40 | -0.41 | -1.03 | 0 | -1.18 | ✅ | 19 | ❌ |
| 2022-Q3 chop | chop | 338 | 4 | 0 | -0.38 | -0.44 | -1.01 | 100 | -0.85 | ✅ | 19 | ❌ |
| 2023-H1 recovery | bull | 337 | 2 | 0 | +0.28 | +0.44 | -0.63 | 0 | +0.44 | ❌ | 19 | ✅ |
| 2023-Q3 chop | chop | 336 | 4 | 1 | -0.51 | -0.94 | -0.81 | 100 | -0.44 | ❌ | 18 | ❌ |
| 2024-Q2 bull | bull | 337 | 2 | 0 | +0.42 | +0.76 | -0.34 | 0 | +0.09 | ✅ | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 335 | 2 | 0 | +0.47 | +0.53 | -0.88 | 0 | +0.15 | ✅ | 18 | ✅ |
| 2025-Q3 bull | bull | 336 | 6 | 1 | +1.13 | +2.84 | -0.20 | 100 | +0.53 | ✅ | 18 | ✅ |
| 2026-recent bull | bull | 317 | 4 | 1 | +0.40 | +0.54 | -0.57 | 100 | +0.74 | ❌ | 14 | ✅ |

**Per-regime median:** bull = +0.41% · chop = -0.45% · bear = +0.04%

**Aggregate:** median ret +0.34% · 62% positive · 62% beat BH-basket · median Sharpe 0.49 · trades 28 · clamps 4/28 fills (14%).
**Fitness gate (shared):** 🔴 FAIL — by 1 bp (median Sharpe 0.49 ≤ 0.50). Median return *passes* (+0.34% > 0). Pct-positive *passes* (62% ≥ 50%).
**Bar A #1 (amended, cap=1):** 🔴 FAIL — 3/8 windows fail. 2022-H1 bear, 2022-Q3 chop, 2023-Q3 chop all hit the 19% < 25% in-position floor (structural — K=2 of 6 monthly never clears 25%).

### 3b. K=2 with regime filter

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | 3 | 0 | -0.30 | -0.32 | -1.03 | 0 | -1.18 | ✅ | 19 | ❌ |
| 2022-Q3 chop | chop | 338 | 2 | 0 | -0.64 | -1.02 | -1.04 | 0 | -0.85 | ✅ | 13 | ❌ |
| 2023-H1 recovery | bull | 337 | 2 | 0 | -0.10 | -0.19 | -0.52 | 0 | +0.44 | ❌ | 12 | ❌ |
| 2023-Q3 chop | chop | 336 | 4 | 1 | -0.51 | -0.94 | -0.81 | 100 | -0.44 | ❌ | 18 | ❌ |
| 2024-Q2 bull | bull | 337 | 2 | 0 | +0.42 | +0.76 | -0.34 | 0 | +0.09 | ✅ | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 335 | 2 | 0 | +0.47 | +0.53 | -0.88 | 0 | +0.15 | ✅ | 18 | ✅ |
| 2025-Q3 bull | bull | 336 | 6 | 1 | +1.13 | +2.84 | -0.20 | 100 | +0.53 | ✅ | 18 | ✅ |
| 2026-recent bull | bull | 317 | 2 | 0 | -0.16 | -0.68 | -0.41 | 0 | +0.74 | ❌ | 5 | ❌ |

**Per-regime median:** bull = +0.16% · chop = -0.57% · bear = +0.09%

**Aggregate:** median ret -0.13% · 38% positive · 62% beat BH-basket · median Sharpe -0.25 · trades 23.
**Fitness gate:** 🔴 FAIL on all three sub-criteria (medRet, pct-positive, Sharpe).
**Bar A #1:** 🔴 FAIL — 4/8 fail.

**Regime gate verdict (K=2): STRICTLY WORSE.** This is a **Pattern #1 generalization datum**. Median return drops from +0.34% to -0.13%, median Sharpe from 0.49 to -0.25, pct-positive from 62% to 38%. The mechanism that PATTERNS.md predicted would *help* cross-asset (low-beta legs like TLT/GLD/DBC benefit from a SPY filter) doesn't materialize because **the strategy almost never picks TLT in these windows** (TLT lost ~50% from 2020-2023 in the rate-hike cycle — it never made top-K). So the basket the gate actually filters is mostly SPY/EFA/VNQ/GLD/DBC, of which the equity-correlated names dominate when the strategy is loaded up. The regime gate then becomes the same "cut winning-window exposure without saving the bears" pattern as sector-equity:
- 2023-H1 recovery: in-pos 19% → 12%, return +0.28% → -0.10%.
- 2026-recent bull: in-pos 14% → 5%, return +0.40% → -0.16%.
- 2022-Q3 chop: in-pos 19% → 13%, return -0.38% → -0.64%.

**Pattern #1 should be amended.** It's not "no-go for sector-equity" — it's **"no-go for any basket where the strategy's selected winners are correlated to SPY at decision time."** When momentum hands you GLD+DBC (low SPY beta), the gate is irrelevant; when it hands you SPY+EFA (high SPY beta), the gate becomes double-defensive. That's the same mechanism as sector-equity. **Counter-evidence to PATTERNS.md prediction.** Recommend the implication be reframed; sibling subagents on this wave (#3, #8) should confirm/refute on their cross-asset variants too.

### 3c. K-sensitivity comparison (without regime filter)

| K | medRet % | medSharpe | pos% | beatBH% | trades | full-period Sharpe | full-period Ret % | maxDD % |
|---|---|---|---|---|---|---|---|---|
| **K=1** | +0.25 | +0.23 | 62 | 62 | 12 | 0.85 | +7.90 | -3.30 |
| **K=2** (primary) | +0.34 | +0.49 | 62 | 62 | 28 | 1.13 | +6.98 | -2.00 |
| **K=3** | +0.21 | +0.33 | 62 | 75 | 38 | 1.23 | +7.20 | -1.86 |

K=2 is the per-window-Sharpe winner; K=3 is the full-period-Sharpe winner (more diversification, lower vol). K=1 has the best single-window ret (+1.74% in 2025-Q1 tariff bear, all-in on GLD) but the worst chop performance (-1.03% in 2022-Q3, also all-in on GLD when GLD whipsawed). **None of K∈{1,2,3} passes Bar A.** The failure mode is consistent: the in-position floor binds (14-19%) at every K because K ≤ basket-size × monthly-cadence math caps it — even K=3 only holds 3 of 6 names for ~22 trading days at a time.

## 4. Full-period backtest (single contiguous run, 2021-06-25 → 2026-05-29, ~5 years)

| Metric | K=1 noreg | K=2 noreg | K=3 noreg | K=2 regime |
|---|---|---|---|---|
| Window | 2021-06-25 → 2026-05-29 (1237 bars) | same | same | same |
| Starting equity | $1000 | $1000 | $1000 | $1000 |
| Notional per leg | $100 | $50 | $33.33 | $50 |
| Total trades | 23 (12 / 11) | 22 (12 / 10) | 21 (12 / 9) | 22 (12 / 10) |
| Basket clamps | 0 | 7 (32%) | 15 (71%) | 7 |
| Total return | **+7.90%** | +6.98% | +7.20% | +6.98% |
| Sharpe (annualized) | 0.85 | **1.13** | **1.23** | 1.13 |
| Max drawdown | -3.30% | -2.00% | -1.86% | -2.00% |
| Total costs paid | $0.46 | $0.18 | $0.10 | $0.18 |

### Per-symbol full-period contribution (K=2 noreg, primary)

| Symbol | Asset class | Buys | Closes | Realized P&L | Final qty | Final MV |
|---|---|---|---|---|---|---|
| **SPY** | US equity | 3 | 3 | **+$17.85** | 0 | $0.00 |
| **GLD** | Gold | 3 | 2 | **+$6.03** | 0.2154 | $89.88 |
| **EFA** | Intl equity | 4 | 4 | +$4.78 | 0 | $0.00 |
| **DBC** | Commodities | 2 | 1 | **-$3.56** | 0.2858 | $8.43 |
| TLT | Long bonds | 0 | 0 | $0.00 | 0 | $0.00 |
| VNQ | REITs | 0 | 0 | $0.00 | 0 | $0.00 |

**Asset attribution observations:**

1. **TLT and VNQ were NEVER selected.** Over the entire 5-year run, the 12-1 momentum signal never ranked either in the top 2. TLT spent 2021-2023 in a brutal duration drawdown (rate-hike cycle); VNQ tracked equities-with-extra-rate-risk. The signal correctly avoided them. This vindicates the momentum-as-defensive-selector intuition.
2. **SPY carried the strategy** (+$17.85 on 3 round trips). This is concerning: the apparent "cross-asset" rotation reduced to mostly SPY-with-occasional-rotation-to-GLD-or-EFA. The cross-asset diversification benefit was *real* (it kept us out of TLT/VNQ disasters) but *narrower* than the universe label suggests.
3. **GLD was the second-largest contributor** and remains held at end-of-run ($89.88 MV) — gold's late-2023 → 2026 run was a 12-1 signal favorite.
4. **DBC was the only loser** (-$3.56), the classic momentum-crash pattern: 2022's commodity spike → 12-1 selected DBC into late-2022 → commodity prices fell. Same failure mode as XLY in the sector-equity sister.
5. **The basket was effectively 4-of-6.** If we re-ran the strategy on a SPY/EFA/GLD/DBC universe alone (dropping TLT and VNQ which were never selected), the full-period Sharpe would likely be similar — the cross-asset benefit comes from the *option* to rotate into bonds/REITs when they look strong, not from actually holding them. Worth flagging for a wave-5 mutation if Tessera wants one.

## 5. Bars-in-position % per window (the structural blocker)

| Window | K=1 | K=2 | K=3 |
|---|---|---|---|
| 2022-H1 bear | 19 | 19 | 19 |
| 2022-Q3 chop | 19 | 19 | 19 |
| 2023-H1 recovery | 19 | 19 | 19 |
| 2023-Q3 chop | 18 | 18 | 18 |
| 2024-Q2 bull | 19 | 19 | 19 |
| 2025-Q1 tariff bear | 18 | 18 | 18 |
| 2025-Q3 bull | 18 | 18 | 18 |
| 2026-recent bull | 14 | 14 | 14 |
| **MEDIAN** | **18.5** | **18.5** | **18.5** |

**In-position is K-invariant.** At every K, the strategy is in-position the same fraction of the time — because what determines occupancy is *how often the strategy holds any leg at all*, which is governed by the monthly rebalance cadence + window length, not K. With ~21 trading bars per month and 60-90 calendar day (~45-65 trading bar) windows, the strategy enters on the first day of each month and is "in position" continuously for ~21 bars × 2-3 month-blocks = 18-19% of the window when you also count the pre-warmup-completion bars where occupancy is 0. **This is the structural property Pattern #2 (single-data-point class generalization trap) identified for fixed-K rotators**: low-vol scored 67% in-position (held continuously), sector-rotation 5.25 avg holdings cleared the floor, but xsec_momentum with **fixed K and monthly rebalance** sits at 18-19% by construction. The cross-asset universe didn't change this; the universe never could.

The floor failure is a property of (a) the monthly rebalance cadence, (b) fixed-K allocation, (c) the warmup-bars-zero-occupancy contribution to the denominator. To clear the 25% floor structurally, you'd need either (a) bi-weekly or weekly rebalance (alters signal character), (b) variable-K dynamic basket (turns this into archetype #8 sector-rotation), or (c) excluding warmup ticks from the denominator (a harness-level decision, not a strategy decision). **NOT proposing the amendment unilaterally** — flagging consistent with Pattern #2 process.

## 6. Apples-to-apples comparison vs wave-3 sector-equity #1 momentum

The clean experimental contrast — same strategy, same harness, same windows, only the universe changes:

| Metric | Sector-equity (#236b86, K=3 of 11) | Cross-asset (#xa_38d2b2, K=2 of 6) | Δ |
|---|---|---|---|
| Median return | -0.36% | **+0.34%** | **+0.70pp** |
| Median Sharpe | -0.50 | **+0.49** | **+0.99** |
| % windows positive | 38% | **62%** | **+24pp** |
| % beat BH-basket | 62% | 62% | 0pp |
| Full-period return | +2.04% | **+6.98%** | **+4.94pp** |
| Full-period Sharpe | 0.30 | **1.13** | **+0.83** |
| Full-period MaxDD | -3.09% | -2.00% | +1.09pp (better) |
| Total trades (8 windows) | 50 | 28 | -22 (fewer, K-driven) |
| Basket clamps (full-period) | 23 (37%) | 7 (32%) | -16 (lower K = less clamping) |
| In-position % (median) | 18.5% | 18.5% | 0pp (structural — see §5) |
| Bar A verdict | REJECT (#1 + #3 fail) | REJECT-WITH-CAVEATS (#1 + #4 fail; **#3 PASS**) | Verdict-class change |

**Every signal-quality metric improved materially.** The strategy's edge appeared when the universe gave it actual dispersion to rotate across. The two failure modes that remain are *structural* (in-position floor inherent to monthly-fixed-K) and *trade-count-floor* (K=2 over 6 ⇒ fewer trades) — neither is an indictment of the strategy class.

## 7. Honest discussion

### 7a. Pre-registered hypothesis: answered

**The wave-3 sector-equity REJECT was substantially universe-class.** Switching to cross-asset on identical infrastructure took:
- Median return from -0.36% to +0.34% (sign flip)
- Median Sharpe from -0.50 to +0.49 (sign flip)
- Full-period Sharpe from 0.30 to 1.13 (above 0.5 cutoff that sector-equity missed)

That's a ~$70 improvement on a $1000 5-year run, post-cost. The improvement is *not subtle* — it's the difference between "this strategy class is broken" and "this strategy class has real edge but the bench shape (K-cadence-cap interaction) doesn't let it pass Bar A." That is a much more interesting and informative answer than wave-3 alone gave us.

**What the candidate STILL fails on is universe-independent:**
- **In-position floor (Bar A #1).** Structural; identical 18.5% median at every K and on both universes. Floor is a fixed-K-rotator property (Pattern #2 datum #4 — this is the second within-class confirmation that monthly-fixed-K cross-sec strategies systematically under-fire the floor).
- **Trade count floor (Bar A #4).** K=2 over 6 ⇒ ~12-24 round-trips on the 5y run. Universe size, not universe shape, drives this. Raising K helps (K=3 has 38 trades over windows) but compresses the cross-sectional bet.

### 7b. Pattern #1 generalization datum: SPY-regime-gate hurts cross-asset too

**PATTERNS.md #1 predicted the gate might HELP on cross-asset baskets** ("when the universe has 0.3-0.5 SPY beta (bonds, gold, REITs), the SPY gate adds real information. Don't blanket-ban it; ban it specifically for sector-equity"). This run **refutes that prediction**:

| K | medRet noreg | medRet regime | Δ |
|---|---|---|---|
| K=1 | +0.25% | +0.01% | -0.24pp |
| K=2 | +0.34% | -0.13% | -0.47pp |
| K=3 | +0.21% | -0.07% | -0.28pp |

Strictly worse at every K. The mechanism explains the prediction failure: the **strategy itself acts as a regime selector** by ranking 12-1 returns — when SPY is in a SPY-bull regime, momentum overwhelmingly picks SPY + EFA (the high-beta legs), which are exactly the legs the SPY gate would *let through*. When SPY is in a SPY-bear regime, momentum picks GLD + DBC + occasionally TLT — but the SPY gate then blocks those buys too (the gate doesn't know whether the current top-K is high-beta or low-beta — it just gates ALL buys). So the gate consistently cuts winning-window exposure (in-pos drops from 19% → 5% in 2026-recent bull) without adding bear-window value (the strategy was already going to pick defensive legs there).

**Recommended PATTERNS.md amendment** (defer to Tessera/main on whether to commit):
- Reframe Pattern #1 from "no-go for sector-equity baskets" to **"no-go for any basket where the strategy's own ranking signal already encodes which legs benefit from a SPY-up regime."** Specifically: any momentum/trend strategy where the selected basket changes character based on market regime. The gate is redundant *across universes* because the per-symbol signal already does the work.
- Counter-cases to test before *that* framing generalizes: does the gate help on a *signal-free* basket like equal-weight-rebalance? It might — but that's a degenerate "BH with SPY filter" strategy, which would land in the same "200d SMA on SPY = textbook regime filter, not strategy-specific edge" rejection per GATE.md Bar A history.

This is the **second within-class data point** in the original Pattern #1 evidence set (sector-equity counted as 3 confirmations; cross-asset is the predicted counter-case the pattern said should NOT apply). Per Pattern #2 rules, **two within-class data points is enough to bring the reframe as a proposal**; I'm flagging it here for Tessera's call rather than editing PATTERNS.md from a subagent.

### 7c. What didn't work, and what to be honest about

**(a) TLT was a non-event.** Bonds were in their worst multi-year drawdown in 40 years across most of the test window. The "cross-asset diversification" hypothesis at its strongest assumes bonds work as the alpha-uncorrelated leg; for this test window they were correlated *negatively* in the bad way (both equities and bonds fell in 2022). Momentum correctly avoided them — but the strategy never demonstrated it could *use* bonds productively, because there was no productive bond regime to use. **A re-test over a 2008-2020 window (when bonds were the alpha leg) would likely look quite different and could be the next move.** Cannot fetch — Alpaca data starts in 2020 for SPY only; equity ETFs go back further but DBC binds at 2006. Worth attempting if Tessera wants to extend the historical window beyond NAMED_WINDOWS.

**(b) The K-knob doesn't fix it.** I tried K∈{1,2,3} hoping one would land. None did. The in-position floor is K-invariant (§5) and the trade-count floor relaxes with higher K but Sharpe drops (K=3: medSharpe 0.33 < 0.5).

**(c) The strategy was effectively SPY + GLD with occasional EFA/DBC tourism.** Per the attribution table in §4. The "cross-asset" label oversells the diversification that actually occurred. Honest description: this is a momentum strategy that uses cross-asset *as a defensive overlay* — when equities go bad, momentum sometimes rotates to gold, which sometimes works (2025-Q1: +1.74% at K=1). The diversification is opportunistic, not structural.

**(d) Won't pass Bar A as-is no matter what dial we turn.** Even a manager bench amendment that relaxed the in-position floor for fixed-K rotators wouldn't get the regime variant past Sharpe 0.5. The non-regime variant clears Sharpe by exactly 0 (0.49 vs 0.50) — within numerical noise. This isn't a hidden gem; it's a real-but-marginal edge that the bench correctly classifies as "promising but not ready."

### 7d. What this implies for the wave-4 sibling tests

The wave-4 cross-asset experiments are intentionally a 3-strategy fan-out to disentangle universe-class vs strategy-class for the three rejected cross-sec archetypes. My data point says **for #1 momentum, the answer is "substantially universe-class — the cross-asset rescue is real."** Sibling subagents on #3 low-vol and #8 sector-rotation will report their own conclusions; together the 3 results should let main decide whether to (a) propose a "fixed-K cross-sec needs cadence-aware floor" bench amendment, (b) explore variable-K extensions of these archetypes, or (c) move on to other archetypes from the triage.

### 7e. Recommendation

**Do NOT promote.** Stays in `strategies_candidates/`. Highest-value next moves (priority order):

1. **Wave-4 cross-class consensus.** Wait for sibling #3 low-vol and #8 sector-rotation cross-asset results before drawing any class-level conclusions (per Pattern #2 rule: ≥2 within-class data points before framing earns durability).
2. **Pattern #1 amendment proposal to Tessera/main.** The "cross-asset is the exception" prediction is refuted by this run. Propose reframe.
3. **Variable-K mutation of this strategy.** If main wants to push on this archetype, the most promising mutation is volatility-scaled K (Barroso-Santa Clara 2015): K shrinks in high-momentum-vol regimes (a la 2022 momentum crash), expands in low-vol. Would also help with the in-position floor (K can spike to 4-5 in calm bull markets). Material added complexity; not free.
4. **Trim universe.** Drop TLT and VNQ which were never selected. Re-test on SPY/EFA/GLD/DBC (4 names, K=2 unchanged). Hypothesis: similar Sharpe, fewer "what's the point of including this" questions. Cheap experiment.

## 8. Files created / modified

| Path | Status | Purpose |
|---|---|---|
| `strategies_candidates/xsec_momentum_xa_38d2b2/{strategy.py, params.json, __init__.py}` | NEW | Candidate. Mirrors `xsec_momentum_236b86` pattern; cross-asset basket; default K=2. |
| `_run_xsec_momentum_xa_wf.py` | NEW | Driver. 6 configs (K∈{1,2,3} × regime∈{F,T}), full-period + walk-forward. |
| `reports/BACKTEST_XSEC_MOMENTUM_XA_20260530T180628Z.md` | NEW | This report. |
| `/tmp/xsec_mom_xa_wf.md`, `/tmp/xsec_mom_xa_wf.json` | Raw walk-forward outputs. |
| `runner/runner.py`, `runner/backtest.py`, `runner/backtest_xsec.py`, `runner/walk_forward_xsec.py`, `runner/candidate_smoke.py` | **UNCHANGED** | md5 verified pre/post. Consumer-only per task constraints. |

## 9. Verification

```
$ python3 -m pytest tests/ -q
182 passed in 7.44s

$ ./tick.sh --candidate xsec_momentum_xa_38d2b2
[xsec_momentum_xa_38d2b2] SMOKE OK xsec (2199ms) basket=['SPY','EFA','TLT','VNQ','DBC','GLD']
  bars_total=1800 actions={GLD=buy, DBC=buy}
rc=0

$ python3 _run_xsec_momentum_xa_wf.py
  xsec_momentum_xa_38d2b2__K2_noreg  K=2 regime=False:
    windows=8/8 medRet=+0.34% pos=62% beatBH=62% medSharpe=0.49
    trades=28 BarA#1=FAIL FIT=FAIL
  xsec_momentum_xa_38d2b2__K2_regime K=2 regime=True:
    windows=8/8 medRet=-0.13% pos=38% beatBH=62% medSharpe=-0.25
    trades=23 BarA#1=FAIL FIT=FAIL
  xsec_momentum_xa_38d2b2__K1_noreg  K=1 regime=False:
    windows=8/8 medRet=+0.25% pos=62% beatBH=62% medSharpe=0.23
    trades=12 BarA#1=FAIL FIT=FAIL
  xsec_momentum_xa_38d2b2__K1_regime K=1 regime=True:
    windows=8/8 medRet=+0.01% pos=50% beatBH=75% medSharpe=-0.12
    trades=12 BarA#1=FAIL FIT=FAIL
  xsec_momentum_xa_38d2b2__K3_noreg  K=3 regime=False:
    windows=8/8 medRet=+0.21% pos=62% beatBH=75% medSharpe=0.33
    trades=38 BarA#1=FAIL FIT=FAIL
  xsec_momentum_xa_38d2b2__K3_regime K=3 regime=True:
    windows=8/8 medRet=-0.07% pos=38% beatBH=75% medSharpe=-0.21
    trades=28 BarA#1=FAIL FIT=FAIL
```

**md5 verification (before/after this run):**
```
runner/runner.py            847a9229d773cb59a5be88f67f007c2f  UNCHANGED
runner/backtest.py          62fb434650c4ae0213a828b3cabed6b2  UNCHANGED
runner/backtest_xsec.py     8e0f4d77be5a6ce424535f2ec46f6db5  UNCHANGED
runner/walk_forward_xsec.py 2d416571fcbff20a018284d198d950ea  UNCHANGED
runner/candidate_smoke.py   29529a246b1c96cf26fce9a098c08950  UNCHANGED
```

Test count: **182 passed** (identical to pre-run baseline). No new test infra added per task constraints.

---

**Final verdict: REJECT-WITH-CAVEATS.** Cross-asset materially rescued the signal-quality metrics (medSharpe sign-flipped from -0.50 to +0.49; full-period Sharpe 0.30 → 1.13); the remaining failure modes (in-position floor, trade-count floor) are structural properties of fixed-K monthly rotators that are universe-independent. The pre-registered hypothesis is answered: **the wave-3 REJECT was substantially universe-class, not strategy-class.** Pattern #1 prediction (regime-gate may help cross-asset) is **refuted** — the gate is strictly worse here too, for a mechanistic reason (the strategy's own ranking encodes the same regime info the gate would add). Both findings are durable enough to be wave-4 inputs.
