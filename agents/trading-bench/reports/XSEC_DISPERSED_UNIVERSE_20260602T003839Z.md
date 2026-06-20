# Dispersed-Universe Cross-Sectional MOMENTUM — Confirm-or-Kill the xsec Lane on Its FAIR Universe

**UTC timestamp:** 20260602T003839Z
**Author:** dispersed-universe xsec momentum subagent (depth 1), trading-bench
**Ruler:** CORRECTED (√252 Sharpe annualization + GATE #5(b) binds on `worst_instrument_dd_pct` deployed-capital DD, per HARNESS_INTEGRITY_AUDIT + RULING 2).
**Strategy reused UNCHANGED:** `strategies_candidates/xsec_ss_momentum_lc20_v2` (the $1000-rail-correct Jegadeesh-Titman momentum). Only the **universe** was swapped (20-name blue-chip → 95-name dispersed) + K swept for the bigger N. Universe dispersion is the single variable under test.
**Candidate written:** `strategies_candidates/xsec_ss_momentum_dispersed95/` (`strategy.py` verbatim-copied from v2 + `params.json` pointing at the 95-name basket).
**Basket file:** `baskets/dispersed_xsec.txt` (95 audited names).
**Suite at finish:** `237 passed in 6.99s` (unchanged vs 237 baseline). ZERO edits to any protected runner file (mtimes all ≤ 2026-05-31 19:11Z, predate this session).
**Promotions to `strategies/`:** ZERO (subagent has no promotion authority).

---

## TL;DR — THE HEADLINE FINDING

**The dispersed universe did NOT rescue cross-sectional momentum. It made it slightly WORSE on Sharpe and dramatically WORSE on tail risk.**

| | 20-name blue-chip (prior memo) | **95-name dispersed (this memo)** |
|---|---|---|
| Best FP-cont Sharpe (any variant) | **+0.21** (6-1 mo K5) | **+0.16** (12-1 mo K10 decile) |
| Canonical 12-1 monthly | −0.11 | **+0.16** (decile) / +0.04 (quintile) |
| Worst instrument DD across variants | −29% | **−90%** |
| Front-door passes | 0/6 | **0/4** |

Widening from 20 correlated mega-caps to 95 genuinely dispersed names (semis, biotech, growth, defensives, laggards) moved the load-bearing FP-cont Sharpe by **essentially nothing** — it stayed pinned in a flat basin near zero (−0.11 to +0.33 across the entire sweep + jitter). **The diagnosed "too-undispersed universe" root cause was real but NOT the binding constraint:** even with abundant cross-sectional dispersion, single-stock price-momentum has no risk-adjusted edge net of 4bps over 2020-07→2026.

Worse, the dispersion *introduced a new failure*: the high-idio-vol names momentum chases into the top-decile (single biotech/semi/growth blow-ups) produced **−86% to −90% single-leg drawdowns** — catastrophic deployed-capital wipeouts the 20-name universe never generated (it capped at −29%). The wider universe doesn't just fail to add edge; it adds uncompensated tail risk that fails GATE #5(b) outright.

**Decisive conclusion: price-based single-stock cross-sectional momentum is EXHAUSTED. Drop the lane.** This is the load-bearing call the task asked for — and it points firmly to "did NOT rescue," with confidence, because we tested it on the universe the anomaly was actually written for and it still failed.

---

## Universe construction + selection rule (the core of the task)

**Selection rule (auditable, NOT hindsight-picked):**
1. **Survivorship floor:** every name must fetch full daily history from the **2020-07-27 data floor** (first bar == `2020-07-27`, ≥ 1400 bars to 2026-06-01). Verified per-name. Any name failing this was **DROPPED and logged**, never silently kept.
2. **Already listed + liquid in mid-2020** — no 2020+ IPOs, no hindsight 2026-winner cherry-picking. All 95 names traded liquidly years before the floor.
3. **Deliberate cross-sectional DISPERSION** — the spread IS the point. Buckets span: mega-cap tech/growth, semis (highest idio-vol cyclical-tech), biotech/pharma (low-SPY-beta idiosyncratic), consumer discretionary/cyclical, financials, industrials, energy (own factor), staples, utilities, healthcare, telecom/value-laggards, materials.
4. **Deliberately INCLUDE known laggards/losers** so the universe is NOT a winners-only cut: BA, INTC, PYPL, PFE, T, IBM, DIS, CVS, WBA(attempted), MRNA, FCX, NEM all retained.

**Audit script:** `reports/_dispersed_universe_audit.py` (read-only; fetches bars, prints per-name first-bar/bar-count, writes the survivor basket).

**Survivorship audit result: 95 survivors, 1 dropped.**

| Metric | Value |
|---|---|
| Candidates screened | 96 (across 12 dispersion buckets, deduped) |
| **Survivors (full history from 2020-07-27)** | **95** |
| Dropped | 1 |
| Bar count range (survivors) | 1466–1469 bars (full span) |
| First bar (all survivors) | 2020-07-27 ✅ |

**DROPPED name (logged, survivorship-honest):**
- **WBA (Walgreens):** only 1279 bars, last bar 2025-08-27 → **delisted/taken private Aug-2025.** This is a *real* survivorship signal: WBA was a deliberate laggard pick, and its mid-window disappearance means the surviving 95-name set has a **mild residual survivorship bias** (a name that blew up and delisted is absent from the back half of the panel). Flagged loudly: this biases results *slightly favorable* to momentum (a delisted loser can't drag the loser-avoidance book), which makes the REJECT even more robust — the edge is absent *despite* a small survivorship tailwind.

**Survivors (N=95):**
```
AAPL MSFT GOOGL AMZN META NFLX ADBE CRM ORCL NOW INTU PYPL SHOP        (tech/growth, 13)
NVDA AMD AVGO QCOM MU INTC TXN AMAT LRCX                                (semis, 9)
GILD BIIB AMGN REGN VRTX MRNA PFE BMY LLY ABBV                          (biotech/pharma, 10)
TSLA HD NKE SBUX MCD LOW TGT DIS BKNG MAR                               (discretionary, 10)
JPM BAC GS MS C WFC AXP SCHW BLK                                        (financials, 9)
CAT DE BA GE HON UPS LMT RTX MMM                                        (industrials, 9)
XOM CVX COP SLB EOG PSX                                                 (energy, 6)
PG KO PEP WMT COST CL MDLZ KMB                                          (staples, 8)
NEE DUK SO D AEP                                                        (utilities, 5)
JNJ UNH MRK ABT TMO DHR CVS                                            (healthcare, 7)
VZ T CSCO IBM                                                          (telecom/value-laggard, 4)
LIN APD FCX NEM DOW                                                     (materials, 5)
```
This is a genuine high-beta/low-beta SPREAD: SPY-betas range from ~0.3 (utilities, staples) to ~1.8+ (semis, TSLA, growth) — the idiosyncratic dispersion the 20-name blue-chip set structurally lacked.

---

## Cost model — ACTIVE, asserted

`CostModel.alpaca_stocks()` → **spread_bps=2.0 (one-way) → 4bps round-trip, fee_bps=0.0.** The driver **asserts `spread_bps==2.0 and fee_bps==0.0` before every WF run** (no `--no-costs` sneak). Verified: RT cost on $1000 = $0.40 = 4bps. Continuous-span Sharpe = concatenated per-tick equity returns across all 8 windows, √252, **2776 ticks** in the series (matching the prior memo's methodology exactly — directly comparable).

---

## Variants + params (focused sweep, dispersion is the variable)

K swept for N=95: **top-decile K=10** and **top-quintile K=19**. Cadence: canonical **12-1 monthly** + faster **6-1 monthly**. Warmup 420d (primes the 252-bar lookback; no `ZeroTradesError`). Driver: `reports/_dispersed_universe_driver.py`.

| Variant | lookback | skip | reb_months | top_k |
|---|---|---|---|---|
| 12-1 monthly K10 (decile, **canonical/primary**) | 252 | 21 | 1 | 10 |
| 12-1 monthly K19 (quintile) | 252 | 21 | 1 | 19 |
| 6-1 monthly K10 (decile) | 126 | 21 | 1 | 10 |
| 6-1 monthly K19 (quintile) | 126 | 21 | 1 | 19 |

---

## Results — full 8-window walk-forward (corrected ruler, $1000 deployed)

`instrDD` = worst single-leg deployed-capital DD-from-entry (the #5(b)-binding number). `A#1` = amended Bar A bullet #1 per-window pass.

### 1. 12-1 monthly K10 (decile, canonical, PRIMARY) — REJECT
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 40 | −8.23 | −0.35 | −33.25 | −16.25 | ✅ | ❌ |
| 2022-Q3 chop | chop | 38 | −8.26 | −0.42 | −28.68 | −7.36 | ❌ | ❌ |
| 2023-H1 recovery | bull | 34 | −6.75 | −0.51 | −19.03 | +6.23 | ❌ | ❌ |
| 2023-Q3 chop | chop | 28 | −2.56 | −0.17 | −25.02 | −3.52 | ✅ | ❌ |
| 2024-Q2 bull | bull | 21 | −1.26 | 0.00 | **−86.37** | +0.38 | ❌ | ❌ |
| 2025-Q1 tariff bear | bear | 34 | −3.96 | −0.11 | −45.92 | −7.32 | ✅ | ❌ |
| 2025-Q3 bull | bull | 24 | +8.44 | 0.79 | −16.92 | +3.49 | ✅ | ✅ |
| 2026-recent bull | bull | 14 | +45.30 | 1.62 | −22.96 | +9.33 | ✅ | ✅ |

**Agg:** FP-cont Sharpe **+0.16** · medWin Sharpe −0.14 · medRet −3.26% · 25% pos · 62% beat BH · **233 trades** · worstInstrDD **−86.37%** · **ann +7.77%/yr**.

### 2. 12-1 monthly K19 (quintile) — REJECT
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 16 | −3.05 | −0.46 | −24.97 | −16.25 | ✅ | ❌ |
| 2022-Q3 chop | chop | 16 | −2.38 | −0.79 | −29.72 | −7.36 | ✅ | ❌ |
| 2023-H1 recovery | bull | 16 | −3.36 | −1.16 | −22.10 | +6.23 | ❌ | ❌ |
| 2023-Q3 chop | chop | 16 | −2.96 | −0.77 | −18.46 | −3.52 | ✅ | ❌ |
| 2024-Q2 bull | bull | 16 | −0.82 | −0.14 | −29.84 | +0.38 | ❌ | ❌ |
| 2025-Q1 tariff bear | bear | 16 | −2.50 | −0.51 | −30.25 | −7.32 | ✅ | ❌ |
| 2025-Q3 bull | bull | 16 | +2.10 | 1.01 | −12.10 | +3.49 | ❌ | ✅ |
| 2026-recent bull | bull | 12 | +15.32 | 1.62 | −11.49 | +9.33 | ✅ | ✅ |

**Agg:** FP-cont Sharpe **+0.04** · medWin Sharpe −0.49 · medRet −2.44% · 25% pos · 62% beat BH · **124 trades** · worstInstrDD −30.25% · **ann +0.85%/yr**.

### 3. 6-1 monthly K10 (decile) — REJECT (highest medRet, worst tail)
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 78 | −26.18 | −0.80 | −51.45 | −16.25 | ❌ | ❌ |
| 2022-Q3 chop | chop | 76 | −25.82 | −0.76 | −51.08 | −7.36 | ❌ | ❌ |
| 2023-H1 recovery | bull | 88 | +4.84 | 0.30 | −22.89 | +6.23 | ❌ | ✅ |
| 2023-Q3 chop | chop | 80 | +15.12 | 0.73 | −26.23 | −3.52 | ✅ | ✅ |
| 2024-Q2 bull | bull | 83 | +12.72 | 0.61 | **−85.77** | +0.38 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 84 | −27.33 | −0.64 | **−90.03** | −7.32 | ❌ | ❌ |
| 2025-Q3 bull | bull | 94 | +10.46 | 0.46 | −45.05 | +3.49 | ✅ | ✅ |
| 2026-recent bull | bull | 44 | +53.36 | 1.55 | −29.89 | +9.33 | ✅ | ✅ |

**Agg:** FP-cont Sharpe **+0.07** · medWin Sharpe +0.38 · medRet +7.65% · 62% pos · 50% beat BH · **627 trades** · worstInstrDD **−90.03%** · **ann +5.96%/yr**.

### 4. 6-1 monthly K19 (quintile) — REJECT
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 40 | −7.51 | −0.83 | −31.60 | −16.25 | ✅ | ✅ |
| 2022-Q3 chop | chop | 40 | −9.25 | −1.11 | −31.43 | −7.36 | ❌ | ❌ |
| 2023-H1 recovery | bull | 40 | −2.63 | −0.42 | −22.10 | +6.23 | ❌ | ❌ |
| 2023-Q3 chop | chop | 40 | −0.59 | −0.03 | −23.15 | −3.52 | ✅ | ❌ |
| 2024-Q2 bull | bull | 40 | +6.82 | 0.84 | −33.15 | +0.38 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 41 | −6.78 | −0.90 | −90.03 | −7.32 | ✅ | ❌ |
| 2025-Q3 bull | bull | 40 | −0.16 | −0.01 | −26.10 | +3.49 | ❌ | ❌ |
| 2026-recent bull | bull | 36 | +22.71 | 1.51 | −25.57 | +9.33 | ✅ | ✅ |

**Agg:** FP-cont Sharpe **+0.02** · medWin Sharpe −0.22 · medRet −1.61% · 25% pos · 62% beat BH · **317 trades** · worstInstrDD −90.03% · **ann +0.95%/yr**.

---

## Continuous-span vs median-window Sharpe (side by side)

Clause (a) binds on the LEFT column.

| Variant | **FP-cont Sharpe (clause a)** | median-window Sharpe (generous) | ann/deployed (f) | trades | worst instrDD (5b) |
|---|---|---|---|---|---|
| 12-1 monthly K10 decile (canonical) | **+0.16** | −0.14 | +7.77% | 233 | −86.37 |
| 12-1 monthly K19 quintile | **+0.04** | −0.49 | +0.85% | 124 | −30.25 |
| 6-1 monthly K10 decile | **+0.07** | +0.38 | +5.96% | 627 | −90.03 |
| 6-1 monthly K19 quintile | **+0.02** | −0.22 | +0.95% | 317 | −90.03 |

**Not one variant reaches FP-cont Sharpe ≥ 1.0; the best is +0.16, a full 0.84 short.** No median mirage to debunk — even the generous median-window figure peaks at +0.38. The signal is simply weak, and the dispersed universe did not change that.

---

## Front-door verdict per variant

A variant passes ONLY if it clears (a) FP-cont Sharpe ≥ 1.0 **AND** #5(b) deployed-capital DD ≤ 30% **AND** (f) ann-on-deployed ≥ 8%/yr — ALL honestly. No soft-pass on median-of-windows or return-floor side door.

| Variant | FP-Sharpe (a) | ann/deployed (f) | instrDD (5b) | Fitness | BarA#1 | **VERDICT** |
|---|---|---|---|---|---|---|
| 12-1 monthly K10 decile | +0.16 ❌ | +7.77% ❌ | −86.37 ❌ | ❌ | ❌ | **REJECT** (a, f, 5b, #1) |
| 12-1 monthly K19 quintile | +0.04 ❌ | +0.85% ❌ | −30.25 🟢 | ❌ | ❌ | **REJECT** (a, f, #1) |
| 6-1 monthly K10 decile | +0.07 ❌ | +5.96% ❌ | −90.03 ❌ | ❌ | ❌ | **REJECT** (a, f, 5b, #1) |
| 6-1 monthly K19 quintile | +0.02 ❌ | +0.95% ❌ | −90.03 ❌ | ❌ | ❌ | **REJECT** (a, f, 5b, #1) |

**No PROMOTE-eligible candidate.** Every variant fails clause (a) decisively. Notably, the two decile variants ALSO fail #5(b) with −86% to −90% single-leg DDs — a **new** failure mode the dispersed universe introduced (the 20-name universe maxed at −29%). The quintile variants survive #5(b) (more diversification per basket) but earn ~0%/yr. There is no corner of this grid that clears the front door.

---

## Param-jitter robustness — flat basin, not a knife-edge

Stressed the strongest cell (12-1 monthly K10 decile, +0.16 FP-Sharpe) by jittering ONE knob at a time. Driver: `reports/_dispersed_universe_jitter.py`.

| Jitter (1 knob from 12-1 mo K10) | FP-cont Sharpe | medWin Sharpe | ann%/yr | trades | instrDD% | ≥1.0? |
|---|---|---|---|---|---|---|
| center (12-1 mo K10) | +0.16 | −0.14 | +7.8 | 233 | −86.37 | ❌ |
| lookback 210 (~10-1) | **+0.33** | +0.36 | +22.0 | 305 | −77.98 | ❌ |
| lookback 294 (~14-1) | −0.11 | −0.24 | −4.4 | 149 | −86.82 | ❌ |
| K=7 (tighter decile) | +0.20 | −0.17 | +12.5 | 173 | −86.37 | ❌ |
| K=14 (looser) | +0.15 | −0.47 | +4.1 | 124 | −31.20 | ❌ |
| skip 10 | +0.18 | −0.11 | +9.9 | 258 | −85.16 | ❌ |
| skip 42 | +0.11 | −0.28 | +6.2 | 192 | −86.55 | ❌ |
| quarterly (reb_m=3) | +0.01 | −0.21 | +1.0 | 173 | −86.37 | ❌ |

**Every cell lands FP-cont Sharpe −0.11 to +0.33** — a flat basin near zero, NOT a tunable ridge toward 1.0. The single best cell (lookback-210, +0.33) is still 0.67 short AND carries a −78% instrument DD that fails #5(b) — it's not a pass under any reading. This is robust evidence the reject is structural, not a tuning miss or overfit argmax.

### Universe-subset stress (the survivorship / dispersion-tail test)
Dropping the high-idio-vol tail (semis + biotech + TSLA/MRNA, 16 names → N=79):

| Universe subset | FP-cont Sharpe | medWin | ann%/yr | trades | instrDD% |
|---|---|---|---|---|---|
| 12-1 mo K10, **no-idio-tail (N=79)** | **0.00** | +0.03 | −1.9 | 236 | −33.25 |

**This is the cleanest diagnostic in the memo.** When the high-idio-vol tail is removed, FP-cont Sharpe collapses to **exactly 0.00** and the catastrophic DD drops from −86% to −33%. The small positive Sharpe readings on the full universe are driven ENTIRELY by the volatile dispersion tail — the same names producing the −86%/−90% wipeouts. There is no stable, broad-based cross-sectional edge; there's a high-variance tail that occasionally pays (2026-recent +45%) and occasionally craters (−90% in 2025-Q1 tariff). A "pass" built on that tail would be a hindsight-fragile artifact, not edge. **This also kills the obvious "fix": you cannot tame the tail-risk by trimming the volatile names without trimming away the only thing producing positive Sharpe — the tail IS the (non-)edge.**

---

## The dispersion comparison — did wider/more-dispersed universe move the Sharpe? (THE HEADLINE)

**No. By essentially nothing on Sharpe — and it made tail risk dramatically worse.**

| Dimension | 20-name blue-chip (prior) | 95-name dispersed (this) | Δ |
|---|---|---|---|
| Best FP-cont Sharpe (any variant) | +0.21 | +0.16 | **−0.05 (worse)** |
| Canonical 12-1 monthly FP-Sharpe | −0.11 (K5) | +0.16 (K10 decile) | +0.27 (still ≈0) |
| Best jitter-cell FP-Sharpe | +0.28 | +0.33 | +0.05 (still 0.67 short of 1.0) |
| Whole-neighborhood Sharpe basin | 0.15–0.28 | −0.11–0.33 | same flat basin near 0 |
| Worst single-leg instrument DD | −29% | **−90%** | **+61pp WORSE** |
| Front-door passes | 0/6 | 0/4 | unchanged: zero |

**Interpretation — this IS the load-bearing finding:** The root-cause diagnosis (the 20-name blue-chip universe was too undispersed for cross-sectional ranking to feed on) was **mechanically correct but not the binding constraint.** Adding 75 more names with genuine high-beta/low-beta and idiosyncratic dispersion — the Jegadeesh-Titman setting — moved the load-bearing FP-cont Sharpe from +0.21 to +0.16. That is within noise; it is NOT the jump from ≈0 to ≥1.0 that a real universe-driven edge would produce. The momentum signal does not have a hidden edge that the narrow universe was suppressing. **Cross-sectional dispersion was not the missing ingredient.**

What the wider universe DID change is the *risk profile, for the worse*: momentum mechanically concentrates the top-decile into whatever has run hardest, which in a dispersed universe means the highest-idio-vol names (MRNA, single semis/growth) right before they mean-revert violently — producing −86% to −90% single-leg crashes (e.g. the 2024-Q2 and 2025-Q1 tariff windows). The 20-name blue-chip universe never did this because blue-chips don't crash 90%. So the dispersed universe is strictly worse: same (non-)Sharpe, far more tail risk.

---

## Survivorship / lookahead / sparse-signal / integrity notes

- **Survivorship:** universe selected by a documented rule (listed+liquid pre-mid-2020, full history from the 2020-07-27 floor), NOT by 2026 hindsight winners. Deliberate laggards retained (BA/INTC/PYPL/PFE/T/IBM/DIS/CVS). **1 name dropped for incomplete history: WBA (delisted Aug-2025, 1279 bars).** Residual bias flagged: WBA's absence is a mild *favorable-to-momentum* survivorship tilt (a delisted loser can't drag the book), so the REJECT holds *despite* a small tailwind. The universe-subset jitter (drop high-idio tail → Sharpe 0.00) independently confirms the result is not a hindsight artifact — it's robust to removing the exact names a cherry-picker would have leaned on.
- **Lookahead:** uses the audited-clean `walk_forward_xsec`/`backtest_xsec` path UNCHANGED (strategy sees `bars[:cur+1]`, fills only `if has_bar_at_t` at that bar's close, regime SPY slice gated on `st[:10] <= tick_date`). Momentum signal reads only trailing closes (`bars[-1-skip]` back to `bars[-1-skip-lookback]`); no same-bar leak. Same strategy code as the prior memo's v2 — only the basket changed.
- **Warmup-starvation:** ran with 420d warmup so the 252-bar lookback primes inside each window. No `ZeroTradesError` fired; every variant traded in all 8 windows (min 124 total trades). The guard that forced the original `xsec_momentum_xa` correction was respected, not bypassed.
- **Sparse-signal:** all variants ≥ 124 round-trips (well over GATE #4's 30-trade floor); no degenerate near-flat run.
- **Cost model:** alpaca_stocks 4bps round-trip, asserted `spread_bps==2.0/fee_bps==0.0` before every WF run. No `--no-costs` path.
- **FP-Sharpe methodology:** clause (a) = continuous concatenated-equity √252 Sharpe across all 8 windows (2776 per-tick returns), matching the prior reversal/momentum subagents' `_lowturn_fpsharpe`/`fp_continuous_sharpe`. NOT median-of-windows. This is the decisive, load-bearing number.

---

## Artifacts & integrity

- **Basket file:** `baskets/dispersed_xsec.txt` (95 audited names + selection-rule header comments).
- **Candidate written:** `strategies_candidates/xsec_ss_momentum_dispersed95/` (`strategy.py` verbatim-copied from `xsec_ss_momentum_lc20_v2`; `params.json` points at the 95-name basket, K=10 decile default, full $1000 rail). STAYS in `strategies_candidates/` — ZERO promotion.
- **Driver scripts (research-only, in `reports/`, no `test_` prefix so pytest ignores them):**
  - `_dispersed_universe_audit.py` — survivorship audit (per-name first-bar/bar-count, drop log, writes basket).
  - `_dispersed_universe_driver.py` — 4-variant 8-window WF, asserts cost model active, computes FP-continuous Sharpe + median-window Sharpe + ann-on-deployed + worst_instrument_dd + BarA#1 + front-door verdict.
  - `_dispersed_universe_jitter.py` — one-knob param jitter around the best cell + universe-subset (drop high-idio-tail) stress.
- **Tests:** `237 passed in 6.99s` after the candidate was added — no regression vs the 237 baseline.
- **Smoke test:** `./tick.sh --candidate xsec_ss_momentum_dispersed95` → `SMOKE OK xsec`, rc=0, decile basket `{INTC,GOOGL,AVGO,C,NEM,AMD,MU,CAT,AMAT,LRCX}` (10 momentum winners), no DB errors.
- **Cost model verified ACTIVE:** `CostModel.alpaca_stocks()` spread_bps=2.0, fee_bps=0.0 → RT cost on $1000 = $0.40 = 4bps. Asserted before every WF run.
- **Protected files UNTOUCHED — verified by mtime:** `runner/runner.py` (2026-05-31T01:40Z), `runner/risk.py` (05-31T06:05Z), `runner/runner_xsec.py` (05-31T01:52Z), `runner/backtest.py` (05-31T19:05Z), `runner/backtest_xsec.py` (05-31T19:10Z), `runner/walk_forward.py` (05-26T04:49Z), `runner/walk_forward_xsec.py` (05-31T19:11Z), `runner/safety_backstop.py` (05-26T23:35Z) — all predate this session (2026-06-02 ~00:38Z). Only the new basket file, candidate dir, and three `reports/_dispersed_universe_*.py` driver scripts are dated today. Evaluation used the `decide_xsec_fn`+`params` override path into `walk_forward_xsec` — the same no-protected-edit pattern the three prior rejection reports used.

---

## Recommendation

**Do not promote. DROP the price-based single-stock cross-sectional lane — confirmed exhausted on its FAIR universe.**

The task framed this as the decisive confirm-or-kill: test momentum on the wide, dispersed universe the anomaly was actually written for, and let the result decide whether to drop price-based xsec entirely. The answer is unambiguous:

1. **The dispersed universe did NOT rescue the edge.** Best FP-cont Sharpe +0.16 (vs +0.21 on the 20-name set) — a flat basin near zero across the entire lookback × cadence × K sweep AND the one-knob jitter (−0.11 to +0.33). No corner reaches the 1.0 clause-(a) bar; the closest cell (+0.33) is still 0.67 short and fails #5(b) on a −78% leg.
2. **The dispersion the diagnosis hoped would help instead hurt:** it introduced −86% to −90% single-leg deployed-capital drawdowns (the 20-name set capped at −29%), failing GATE #5(b) on both decile variants. Momentum chasing the highest-idio-vol names into the top-decile is a tail-risk machine, not an alpha machine.
3. **The positive Sharpe is entirely a high-idio-vol-tail artifact:** removing semis+biotech+TSLA/MRNA collapses FP-Sharpe to exactly 0.00. There is no broad, stable cross-sectional edge — and the tail that produces the occasional +45% window is the same tail that produces the −90% crash. You cannot harvest one without the other.

**Lane-level conclusion (now spanning four rejects — 20-name sweep, low-turn reversal, monthly momentum, and this dispersed-universe momentum):** single-stock price-based cross-sectional signals do not clear the corrected front door at 4bps over 2020-2026, on EITHER a narrow blue-chip universe OR a wide dispersed one. The universe was not the binding constraint; the signal class is. **Drop price-based xsec.** If the cross-sectional lane is revisited, it should be with a *different signal input entirely* (fundamentals, earnings-revision, cross-asset/macro, or a non-price feature) — not more universe engineering or parameter tuning of price-momentum. The tournament still has ZERO legitimate single-stock promotions; this is a clean, honest, decisive reject that closes the price-based xsec investigation.
