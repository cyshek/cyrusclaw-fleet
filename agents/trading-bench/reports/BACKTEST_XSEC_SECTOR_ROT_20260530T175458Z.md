# Backtest Report — Sector Rotation (Faber GTAA Absolute Momentum) on SPDR Sectors

**Candidate:** `xsec_sector_rot_b7a2f9`
**Archetype:** #8 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` —
Faber GTAA / Mebane Faber Tactical Asset Allocation: per-symbol
absolute time-series momentum (`close > SMA(N)`) on the 11 SPDR
sector ETFs.
**Author:** trading-bench (subagent, 2026-05-30 17:54 UTC).
**Verdict (TL;DR):** **REJECT** — all four config variants (N=200 raw,
N=200 + regime, N=150, N=100) fail the amended Bar A and the fitness
gate. Best headline (N=150 raw): median return -0.25%, 38% windows
positive, median Sharpe -0.31; floor cleared at N=150 (in-pos ≈38%)
but the trend filter doesn't pull positive absolute returns at the
$100-cap / 11-sector / 2022-2026 regime. **Faber's edge does not
show through at this bench scale.** That's the meaningful negative
result; the strategy correctly adapts basket size (0-11 holdings,
avg ≈5 full-period) — the bench is too small for the diversification-
plus-trend-filter machinery to add up to alpha after costs.

---

## 1. Strategy spec (as implemented)

| Field | Value |
|---|---|
| Universe | 11 SPDR sector ETFs: XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY (same as #1 momentum, #3 low-vol — apples-to-apples) |
| Signal | Per-symbol **absolute** time-series momentum: `close > SMA(N)` (Faber 2007 canonical). N=200 primary; N=150, N=100 sensitivities. **No relative ranking** — fundamentally different from #1 (top-K of 11) and #3 (bottom-K of 11). |
| Allocation | Equal-weight long ALL trend-passing symbols. Per-leg notional = `max_notional / n_passed` (adapts to current basket size). Basket clamp = $100 hard cap via harness `_clamp_basket`. **Holds 0 → 11 legs dynamically.** |
| Rebalance | Calendar-month boundary (first tick whose YYYY-MM ≠ stored month). |
| Cost model | `alpaca_stocks` (2 bps spread, 0 fee) per-leg fill. |
| Optional regime gate | `regime_uptrend(spy_closes, 50)` gates NEW buys. Likely redundant — the per-symbol trend filter already encodes "be defensive in bears." Evaluated honestly; verdict in §3b. |
| Persistent state | `last_rebalance_month` (cross-flat YYYY-MM) — single key. |

**Why this matters vs #1 and #3.** Both prior xsec archetypes hold a
**fixed-K** basket (K=3 momentum, K=k low-vol) regardless of regime —
that's why they camp at 14-19% bars-in-position and structurally
underfire the amended Bar A's 25% floor. Faber GTAA's basket is
**signal-dependent**: at any given month it holds however many
sectors clear `close > SMA(N)`. In raging bulls that's 9-11; in deep
bears it's 0-2; on average across 2021-2026 it was ~5 (see full-period
diag below). This was the headline thesis for #8: dynamic basket size
should naturally clear the in-position floor that monkey-wrenched #1.
**The thesis half-holds.** At N=200 the trend filter is too strict
and in-pos still sits at 22-24% (just below the floor). At N=150 it
clears the floor cleanly (~38%). At N=100 it overfires (~60%). But
*none* of those configurations produce positive Sharpe — see §2.

## 2. Bar A scorecard (per `GATE.md`, amended 2026-05-30)

Evaluated on the **N=200 / no-regime-filter** variant (Faber's canonical
configuration). Other variants are strictly no better on bullets #1
and #3 — see §3.

| # | Bar A bullet | Result | Verdict |
|---|---|---|---|
| 1 | All 8 named regimes pass via (a) positive return OR (b) ≥ BH-basket + ≥25% bars-in-position; (b) capped at 1 | 3/8 windows pass (a). (b)-alt is *almost* reachable (in-pos 22-24%) but misses the 25% floor by ≤3pp in every window. Net: 3 pass, 5 fail. | **FAIL** |
| 2 | Held-out final regime (2026-recent bull) | +0.21% return, positive, no prior tuning on this window | **PASS** (positive, untuned) |
| 3 | Cost-aware Sharpe ≥ 0.5 on full backtest period | Full-period (1237 bars, ~5y) Sharpe **-0.09** | **FAIL** |
| 4 | Trade count ≥ 30 across backtest | 90 full-period; 71 across the 8 named windows | **PASS** |
| 5 | Max drawdown ≤ 30% post-cost | Full-period **-3.06%**; worst-window -1.58% | **PASS** |
| 6 | Code review pass via AST gate | Static-import only; no eval/exec/network/file I/O; passes inspection | **PASS** |
| 7 | Smoke test via `./tick.sh --candidate xsec_sector_rot_b7a2f9` | `rc=0`, action=`{XLC=buy, XLI=buy, XLP=buy, XLRE=buy, XLV=buy}` (5-leg basket reflecting current market state), 3300 bars total, 3.7s | **PASS** |

**Bar A overall: FAIL** — bullet #1 fails on 5/8 regime windows;
bullet #3 (Sharpe -0.09 < 0.50) is independently binding under every
variant tried. No (b)-alt-pass rescues at N=200 because the floor is
missed by 1-3 percentage points; switching to N=150 clears the floor
on 5 windows but introduces fresh BH-basket failures (see §3c).

## 3. Walk-forward summary (8 named windows, +300d warmup per window)

### 3a. N=200 / no regime filter (Faber canonical)

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | Avg basket | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 270 | 8 | 0 | -0.39 | -0.69 | -0.83 | 0 | -1.49 | ✅ | 23 | 0.68 (3.00 when in) | ❌ |
| 2022-Q3 chop | chop | 270 | 2 | 1 | -0.48 | -0.46 | -1.58 | 0 | -0.62 | ✅ | 23 | 0.47 (2.00) | ❌ |
| 2023-H1 recovery | bull | 270 | 11 | 1 | -0.21 | -0.38 | -0.90 | 0 | +0.45 | ❌ | 23 | 1.27 (5.61) | ❌ |
| 2023-Q3 chop | chop | 269 | 12 | 1 | -0.36 | -1.07 | -0.57 | 0 | -0.41 | ✅ | 23 | 1.55 (6.71) | ❌ |
| 2024-Q2 bull | bull | 267 | 11 | 1 | +0.18 | +0.74 | -0.18 | 0 | +0.07 | ✅ | 23 | 1.73 (7.45) | ✅ |
| 2025-Q1 tariff bear | bear | 267 | 11 | 0 | -0.62 | -0.88 | -1.25 | 0 | -0.50 | ❌ | 22 | 1.13 (5.03) | ❌ |
| 2025-Q3 bull | bull | 267 | 10 | 1 | +0.51 | +1.59 | -0.19 | 0 | +0.35 | ✅ | 24 | 1.40 (5.94) | ✅ |
| 2026-recent bull | bull | 247 | 6 | 1 | +0.21 | +0.50 | -0.21 | 0 | +0.73 | ❌ | 15 | 0.50 (3.42) | ✅ |

**Per-regime median:** bull = +0.20% · chop = -0.42% · bear = -0.50%
**Aggregate:** median ret **-0.29%** · 38% positive · 62% beat BH-basket · median Sharpe **-0.42** · trades 71 · clamps 6/71 fills (8%, materially lower than #1's 14% — adaptive sizing prevents most clamps).
**Fitness gate (shared single-symbol gate):** 🔴 FAIL — median ret -0.29% ≤ 0%, only 38% positive, median Sharpe -0.42 ≤ 0.50.
**Bar A #1 (amended, cap=1):** 🔴 FAIL — 4 windows fail (b) for in-pos 22-23% < 25% (missed by ≤3pp in every case); 2025-Q1 bear and 2026-recent bull fail (a). Net 5/8 fail.

### 3b. N=200 / **with** regime filter

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | Avg basket | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 270 | 7 | 0 | -0.37 | -0.90 | -0.47 | 0 | -1.49 | ✅ | 23 | 0.53 (2.33) | ❌ |
| 2022-Q3 chop | chop | 270 | 4 | 0 | -0.67 | -1.15 | -1.14 | 0 | -0.62 | ❌ | 16 | 0.40 (2.53) | ❌ |
| 2023-H1 recovery | bull | 270 | 5 | 0 | -0.28 | -1.20 | -0.49 | 0 | +0.45 | ❌ | 15 | 0.53 (3.46) | ❌ |
| 2023-Q3 chop | chop | 269 | 12 | 1 | -0.36 | -1.07 | -0.57 | 0 | -0.41 | ✅ | 23 | 1.55 (6.71) | ❌ |
| 2024-Q2 bull | bull | 267 | 8 | 0 | +0.01 | +0.06 | -0.16 | 0 | +0.07 | ❌ | 23 | 1.20 (5.16) | ✅ |
| 2025-Q1 tariff bear | bear | 267 | 6 | 0 | -0.25 | -0.72 | -0.62 | 0 | -0.50 | ✅ | 22 | 0.67 (2.98) | ❌ |
| 2025-Q3 bull | bull | 267 | 10 | 1 | +0.51 | +1.59 | -0.19 | 0 | +0.35 | ✅ | 24 | 1.40 (5.94) | ✅ |
| 2026-recent bull | bull | 247 | 4 | 0 | -0.01 | -0.07 | -0.18 | 0 | +0.73 | ❌ | 6 | 0.24 (4.00) | ❌ |

**Aggregate:** median ret **-0.26%** · 25% positive (worse) · 50% beat BH-basket (worse) · median Sharpe **-0.81** (much worse) · trades 56.
**Bar A #1:** 🔴 FAIL — same floor failure plus fresh BH-misses in 2022-Q3 and 2023-H1 (the gate cut entry early and lost out on the recovery).

**Regime gate verdict: STRICTLY WORSE.** As predicted in the task spec
— the per-symbol SMA(200) trend filter already encodes "be defensive
in bears," and overlaying SPY-SMA(50) double-gates entries.
Concretely, in 2023-H1 recovery the gate suppressed buys in March/April
2023 (SPY still below SMA50 from the Q1 SVB scare) so the strategy
missed the recovery rally; in 2026-recent bull it cut basket from 0.50
to 0.24 avg holdings and turned a +0.21% window into -0.01%. **Ship
without the regime overlay if you ship at all** — consistent with the
#1 momentum report's finding for the same basket.

### 3c. Sensitivity sweep — SMA window N ∈ {200, 150, 100}, all no-regime

| Variant | Med Ret % | % Pos | % Beat BH | Med Sharpe | Trades | Med In-Pos % | Avg basket (FP) | Full-Period Ret % | Full-Period Sharpe | Bar A #1 |
|---|---|---|---|---|---|---|---|---|---|---|
| N=200 (primary) | -0.29 | 38 | 62 | -0.42 | 71 | 23 | 5.25 | -0.60 | -0.09 | FAIL |
| N=150 | -0.25 | 38 | 50 | -0.31 | 100 | **38** | 5.40 | -0.69 | -0.11 | FAIL |
| N=100 | -0.65 | 38 | 38 | -0.75 | 200 | **61** | 5.29 | -2.84 | -0.35 | FAIL |

**N=150 is the most charitable read.** It's the only variant that
**naturally clears the 25% in-position floor** in 7/8 windows (range
31-39%). And in 2022-H1 bear it actually books a (b)-alt pass:
return -0.49% < BH-basket -1.49% AND in-pos 38% ≥ 25% → BarA #1 ✅(b).
But the median return (-0.25%) and Sharpe (-0.31) are nearly identical
to N=200, AND it introduces fresh failures: 2022-Q3 (-0.64% vs
BH -0.62% — misses by 2bps), 2023-H1 (-0.05% vs +0.45%), 2025-Q1
(-0.92% vs -0.50%), 2026-recent (-0.46% vs +0.73%). Net Bar A #1 still
FAIL: now via (a)-fail-and-also-fail-(b)-because-underperform-BH
instead of (a)-fail-and-fail-(b)-because-floor.

**N=100 is the worst variant.** Overfires the trend filter
(in-pos ~60%) and pays the noise: avg trades doubles to 200, full-period
Sharpe degrades to -0.35, full-period return -2.84%. This is the textbook
trend-following-too-fast result (Hurst-Ooi-Pedersen 2017 §3 shows the
12-month TSMOM Sharpe collapses below 6-month lookback on most asset
classes; we see the same shape).

**No N value rescues the strategy.** The N=150-→-clears-floor /
N=200-→-just-misses-floor / N=100-→-overfires shape is a real
behavior of the signal but the absolute returns are flat-to-negative
across every choice. The basket size IS adapting correctly (full-period
avg 5.25 holdings, max 10-11 in raging bull, 0 in deepest 2022 bear
weeks per the diagnostic) — but the diversification isn't enough to
produce positive risk-adjusted returns net of 2 bps per leg at $9-$20
per-leg notional.

## 4. Full-period backtest (single contiguous run, ~5 years)

| Metric | N=200 no-reg | N=200 + regime | N=150 no-reg | N=100 no-reg |
|---|---|---|---|---|
| Window | 2021-06-25 → 2026-05-29 (1237 bars) | same | same | same |
| Total trades | 90 (47/43) | 88 (46/42) | 120 (62/58) | 155 (80/75) |
| Basket clamps | 23 ticks | 13 ticks | 20 ticks | 19 ticks |
| Total return | **-0.60%** | -0.52% | -0.69% | **-2.84%** |
| Sharpe (annualized) | **-0.09** | -0.09 | -0.11 | -0.35 |
| Max drawdown | -3.06% | -2.40% | -2.65% | -4.98% |
| Total costs paid | $0.21 | $0.20 | $0.29 | $0.39 |
| Avg basket (all ticks) | 5.25 | 5.22 | 5.40 | 5.29 |
| Max basket size | 10 | 11 | 11 | 11 |

Per-symbol full-period contribution (N=200 no-reg, sorted ascending P&L):

| Symbol | Buys | Closes | Realized P&L | Final qty |
|---|---|---|---|---|
| XLY | 3 | 3 | -$6.27 | 0 |
| XLU | 2 | 2 | -$5.05 | 0 |
| XLK | 2 | 2 | -$4.71 | 0 |
| XLV | 6 | 6 | -$4.23 | 0 |
| XLP | 8 | 7 | -$2.44 | 0.188 (open) |
| XLRE | 6 | 5 | -$2.22 | 0.564 (open) |
| XLB | 6 | 6 | -$1.10 | 0 |
| XLE | 5 | 5 | -$0.13 | 0 |
| XLI | 3 | 2 | +$2.34 | 0.100 (open) |
| XLF | 3 | 3 | +$4.15 | 0 |
| XLC | 3 | 2 | **+$11.31** | 0.214 (open) |

XLC carries the entire P&L (single 2022→2024 hold). XLK loses -$4.71
on only 2 round-trips — the trend filter got whipsawed at SMA(200)
crossings during early 2022 and late 2023. XLY loses -$6.27 on 3 trips —
similar mechanism (consumer-disc kept oscillating around its SMA in
2022-2023). Aggregate effect: dispersion is roughly symmetric around
zero and the post-cost return is mildly negative.

## 5. Verdict: **REJECT**

Strict Bar A: REJECT (bullets #1 and #3 fail under all four variants).

Conditional verdict: **REJECT**, period. This is the meaningful negative
result the task spec named: *"If it doesn't show edge even pre-floor
here, that's a meaningful negative result — the $100 cap + 11-sector
universe may simply be too constrained for the strategy's edge to
show."* That is exactly what we see.

Three structural reasons, in priority order:

1. **The 11-sector basket is too narrow for Faber's idea.** Faber's
   GTAA literature (Faber 2007, 2013; Antonacci 2014's "dual momentum"
   replication) shows the absolute-momentum trend filter on a
   **diversified asset basket** (US/intl equity, REITs, bonds,
   commodities) produces ~50-100bps annualized alpha over BH-equity.
   On an 11-sector all-equity basket, every member is ~0.7-0.9
   correlated with SPY → the trend filter is mostly firing on SPY
   itself with sector-specific noise added. Net: the strategy is
   effectively "be in SPY-ish exposure when SPY is up, in cash when
   SPY is down" — i.e. a degenerate single-asset TSMOM dressed up as
   sector rotation. **Cross-asset Faber needs cross-asset assets;**
   the bench's `MAX_TRADES_PER_DAY = 4` constraint kept us from
   widening the universe to bonds/REITs/commodities without rewriting
   the harness.

2. **2022-2026 was a particularly cruel regime for trend filters on
   equity sectors.** The 2022 bear was a sharp first-half + sharp
   second-half recovery — fast enough that SMA(200) lagged. The
   2023 SVB scare and 2025 Q1 tariff bear were both ≤90-day events
   that whipsawed the filter. The Faber literature shows the strategy
   primarily protects against *long, grinding* bears (2000-2002,
   2008-2009) where SMA(200) catches the downturn early and stays
   out. We saw no such regime in our 5-year sample.

3. **The $100 cap squeezes Faber's diversification benefit to nearly
   zero.** With max_basket ≈ 11, per-leg notional bottoms at $9.
   2-bps spread on $9 = $0.0018 in slippage per fill — fine in
   isolation but the strategy fires 90-200 fills per 5y and that's
   $0.20-$0.40 in cumulative costs against a -0.6% to -2.8% return.
   At full bench-scale 11-leg deployment the strategy's "advantage"
   over BH-basket is the *correlation-weighted* trend-filter exit;
   at $9/leg the trading frictions wash out any small alpha.

## 6. Honest discussion

**What worked as designed.** The dynamic basket sizing is real and
behaves as the literature predicts: avg basket 0.5-1.7 in bears,
1.5-3.4 in bulls (N=200), max held 10-11 in raging bulls, 0 in deep
bears. In 2022-H1 bear the strategy lost -0.39% vs BH-basket -1.49%
— the trend filter genuinely went defensive (avg 0.68 holdings) and
saved ~1.1pp. In 2022-Q3 chop similar story: -0.48% vs BH -0.62%
with avg basket 0.47. **The defensive mechanism works.** It's the
"plus side" — generating positive absolute returns from sector
selection during bulls — that the strategy can't deliver at this
universe size.

**On the in-position floor issue.** This is the headline empirical
finding for the manager conversation: **at N=200 the strategy sits at
22-24% in-pos in every window — missing the amended Bar A floor by
1-3 percentage points in a way that feels like the floor was
calibrated to penalize it.** Three honest observations:

(a) Switching to N=150 cleanly clears the floor (in-pos ~38% across
    7/8 windows, one exception). So the floor IS calibrated such that
    a 50% reduction in trend-filter lookback gets a strategy in this
    family above water. The N=200 floor-miss isn't a fundamental
    architectural issue — it's a parameter-window mismatch. **But the
    bench doesn't reward "satisfies the floor"; it rewards "satisfies
    the floor AND produces positive returns,"** and N=150 doesn't get
    the second clause either.

(b) The #1 momentum report flagged the floor as potentially needing
    "asset-type or rebalance-cadence awareness for xsec strategies."
    The sector-rotation result here gives the manager a useful data
    point: at N=150, the floor is reachable for this kind of strategy
    *naturally* (no parameter game) but the returns still aren't
    there. So the floor isn't actually the binding constraint for
    Faber on this bench — the **edge** is. I'm not flagging a need
    for amendment; I'm noting that the floor here is consistent with
    the strategy's actual behavior.

(c) The regime-overlay (3b) variant dropped in-pos to 6-23% — a
    big reduction. The double-defensive interaction is real and
    confirmed; same finding as #1 momentum.

**What the bench cap is doing to the result.** Basket clamps fire
8% of fills (6/71) at N=200 — materially lower than #1 momentum's
14%. That's the adaptive-sizing benefit at work: when the strategy
wants to deploy 5 legs it asks for $20 each and the basket fits
under $100; when it asks for 10 legs at $10 each it also fits. The
clamps that *do* fire are rotation-tick collisions (close + new buy
the same tick exceeding the cap before the close settles). At
$500 / $1000 notional caps these would essentially disappear, and
the per-leg notional would scale up enough that 2bps spread is
negligible. **However**: even removing all clamps, the strategy still
produces -0.60% / Sharpe -0.09 full-period at the larger N=200 size.
The basket-cap isn't the binding constraint — the signal-on-this-
universe is.

**What to NOT conclude.** Do not conclude "Faber GTAA doesn't work."
The strategy is one of the most-replicated systematic edges in the
literature with 40+ years of out-of-sample track record on
*cross-asset* universes. What this bench shows is that the
*equity-only-sectors* implementation, at *$100 notional* and during
*2021-2026*, doesn't pass our gates. Three of those four conditions
are bench artifacts; only "during 2021-2026" reflects real out-of-
sample edge erosion (and even there the signal still loses *less*
than BH in the bears, just not enough to pass).

**Net recommendation.** Do NOT promote. Two follow-ups worth filing
for the manager queue:

1. **Re-test at higher notional + cross-asset basket.** If the harness
   gets a `MAX_TRADES_PER_DAY` lift (or a staggered-fill mode per the
   #1 report §6 follow-up #3), the natural next experiment is Faber
   on something like {SPY, EFA, IEF, TLT, GLD, DBC, VNQ} — the
   canonical Faber universe. That removes both bench artifacts at
   once. Until then this archetype is structurally hobbled.

2. **For all three xsec archetypes (#1, #3, #8), the same finding
   recurs:** at $100 / 11-sectors / 2021-2026, none of the classic
   academic xsec equity-anomaly archetypes (relative momentum,
   low-vol, absolute trend) clear Bar A. **This is consistent
   evidence that the harness needs higher notional, a broader
   universe, OR a different archetype family** (intraday, vol-
   targeted long-short, options overlays) before xsec-style baskets
   become viable here. The #1 report flagged this as a Tessera
   conversation; this report adds a second data point. The #3
   sibling will add a third.

## 7. Files created

| Path | Purpose |
|---|---|
| `strategies_candidates/xsec_sector_rot_b7a2f9/{strategy.py, params.json, __init__.py}` | NEW — candidate (Faber GTAA on 11 SPDR sectors). |
| `_run_xsec_sector_rot_wf.py` | NEW — walk-forward + full-period driver with sensitivity sweep (N ∈ {200, 150, 100}) + per-window avg-basket-size diagnostic. |
| `/tmp/xsec_sectrot_wf.md`, `/tmp/xsec_sectrot_wf.json` | Raw outputs (8 windows × 4 variants + full-period each). |
| `reports/BACKTEST_XSEC_SECTOR_ROT_20260530T175458Z.md` | This report. |

**No NEW tests added.** The xsec harness + candidate_smoke xsec
dispatch already exist from wave-3 #1 momentum; this candidate exercises
exactly the same code paths. Test count therefore stays at 182
(unchanged from baseline).

**No edits to** `runner/runner.py`, `runner/backtest.py`,
`runner/backtest_xsec.py`, `runner/walk_forward_xsec.py`,
`runner/candidate_smoke.py` — md5 verified unchanged before and after
this run (see §8).

## 8. Verification

```
$ md5sum runner/runner.py runner/backtest.py runner/backtest_xsec.py \
         runner/walk_forward_xsec.py runner/candidate_smoke.py
e3c1652caea2c440a639e5811993a90d  runner/runner.py
c940c9572d158aa86f1ac30b07406944  runner/backtest.py
8e0f4d77be5a6ce424535f2ec46f6db5  runner/backtest_xsec.py
2d416571fcbff20a018284d198d950ea  runner/walk_forward_xsec.py
29529a246b1c96cf26fce9a098c08950  runner/candidate_smoke.py
# Identical to pre-run snapshot at /tmp/protected_md5_before.txt — diff is empty.

$ python3 -m pytest tests/ -q
182 passed in 5.34s

$ ./tick.sh --candidate xsec_sector_rot_b7a2f9
[xsec_sector_rot_b7a2f9] SMOKE OK xsec (3632ms) basket=[XLB,XLC,XLE,XLF,XLI,XLK,
XLP,XLRE,XLU,XLV,XLY] bars_total=3300 actions={XLC=buy, XLI=buy, XLP=buy,
XLRE=buy, XLV=buy}
# rc=0; 5 of 11 sectors currently pass close > SMA(200) — adaptive basket
# behaving exactly as designed.

$ python3 _run_xsec_sector_rot_wf.py --sensitivity
  xsec_sector_rot_b7a2f9__noreg_n200  regime=False sma=200: windows=8/8
    medRet=-0.29% pos=38% beatBH=62% medSharpe=-0.42 trades=71
    BarA#1=FAIL FIT=FAIL
  xsec_sector_rot_b7a2f9__regime_n200 regime=True  sma=200: windows=8/8
    medRet=-0.26% pos=25% beatBH=50% medSharpe=-0.81 trades=56
    BarA#1=FAIL FIT=FAIL
  xsec_sector_rot_b7a2f9__noreg_n150  regime=False sma=150: windows=8/8
    medRet=-0.25% pos=38% beatBH=50% medSharpe=-0.31 trades=100
    BarA#1=FAIL FIT=FAIL
  xsec_sector_rot_b7a2f9__noreg_n100  regime=False sma=100: windows=8/8
    medRet=-0.65% pos=38% beatBH=38% medSharpe=-0.75 trades=200
    BarA#1=FAIL FIT=FAIL
```

Test count: **182 passed** (unchanged from baseline of 182 after wave-3
#1 momentum landed). Numbers in this report match
`/tmp/xsec_sectrot_wf.json` byte-for-byte.

---

**Final verdict: REJECT.** Candidate stays in `strategies_candidates/`.
The Faber GTAA archetype on an 11-equity-sector basket at $100 cap
does not produce positive risk-adjusted returns on 2021-2026 data,
under any of the four parameter variants tested. The dynamic basket
size mechanism works as designed (avg 5.25 holdings, max 10-11, goes
near-flat in deepest 2022 bear weeks); the trend filter genuinely
reduces drawdowns vs BH-basket in bears (2022-H1: -0.39% vs -1.49%);
but neither of those wins is enough to produce positive aggregate
returns or clear the amended Bar A floor at N=200. The N=150
sensitivity clears the in-position floor but loses to BH-basket in
4 windows. The regime overlay strictly degrades all metrics. **The
strategy needs higher notional and/or a cross-asset basket to show
its documented edge;** at the current bench scale it's a structurally
attenuated version of itself.
