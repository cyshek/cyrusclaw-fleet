# Low-Turnover Single-Stock Mean-Reversion — Attack the Cost-Strangle

**UTC timestamp:** 20260601T210128Z
**Author:** low-turnover mean-reversion subagent (depth 1), trading-bench
**Ruler:** CORRECTED (√252 Sharpe annualization + GATE #5(b) binds on `worst_instrument_dd_pct` deployed-capital DD, per RULING 2 / HARNESS_INTEGRITY_AUDIT).
**Parent improved:** `strategies_candidates/xsec_ss_meanrev_lc20` (baseline: 946 round-trips, net −8.7%/yr-on-deployed, median-window Sharpe −0.25).
**Candidate written:** `strategies_candidates/xsec_ss_meanrev_lc20_lowturn` (+`min_drop_pct` magnitude-gate lever; cadence/K/safety-rail via existing param plumbing).
**Suite at finish:** `237 passed in 7.03s` (unchanged; ZERO edits to any protected runner file — mtimes all predate this session, verified).
**Promotions to `strategies/`:** ZERO. (Subagent has no promotion authority.)
**Front-door verdict:** **REJECT — all variants.** Honest reject, reported as-is, no soft-pass.

---

## TL;DR

The parent's reversal **signal is real** and the **turnover cut works**: slowing the rebalance from weekly→monthly, shrinking K, magnitude-gating entries, and tightening the per-leg safety rail drops round-trips from **946 → ~98** and flips net return from **−8.7%/yr → ~+10%/yr on deployed notional**. The cost-strangle is genuinely defeated.

**But no variant clears the front door honestly.** The standard door fails **BarA#1** (a contrarian buys-losers book structurally underperforms equal-weight BH in a v-shaped recovery — the 2023-H1 window). The **#5 fast-track** fails **clause (a)** once you measure Sharpe the way the gate actually defines it: **full-period continuous-span Sharpe is +0.73–0.80, NOT the +1.17 median-of-windows number** that superficially looked like a pass. The median-window Sharpe was the **exact best-window-vs-full-period mirage** that forced the `xsec_momentum_xa` promotion-record correction (2026-05-31). Caught here before it could mislead.

The lead config also sits on a **knife-edge, not a plateau**: every adjacent parameter cell (K±1, rebalance±3 bars, drop-threshold±0.5pp, lookback±1 bar) drops median Sharpe below 1.0 — and lb=4 collapses it to 0.07. That is an overfit signature, independent of the FP-Sharpe finding.

---

## Universe (identical to parent — directly comparable)

```
AAPL MSFT JNJ XOM JPM PG KO WMT CVX HD MRK PEP CSCO VZ DIS MCD NKE UNH BA CAT
```
Same survivorship-safe fixed mid-2020 large-cap set as the parent and the rejection report. Laggards (BA/DIS) retained; not hindsight-selected. All 20 fetch full history from the 2020-07-27 data floor.

**Cost model: ACTIVE, non-zero.** `CostModel.alpaca_stocks()` = 2bps one-way spread → **4bps = $0.04 round-trip on $100 notional**, 0 commission. Driver asserts `spread_bps==2.0 and fee_bps==0.0` before every run (no `--no-costs` sneak). The baseline reproduced exactly through this path: 946 trades, worst instr DD −24.37%, all 8 window returns matching the rejection report to the decimal — confirming the cost drag is applied and the harness is the audited one.

---

## Baseline reproduction (anchor)

| Window | Regime | Trades | Return % | Sharpe | instrDD % | BH % | Beats BH? | BarA#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 129 | −0.61 | −0.62 | −16.39 | −1.12 | ✅ | ✅ |
| 2022-Q3 chop | chop | 125 | −1.94 | −2.40 | −16.48 | −0.69 | ❌ | ❌ |
| 2023-H1 recovery | bull | 119 | −0.50 | −0.79 | −11.18 | +0.22 | ❌ | ❌ |
| 2023-Q3 chop | chop | 117 | +0.13 | 0.32 | −11.07 | −0.37 | ✅ | ✅ |
| 2024-Q2 bull | bull | 123 | +0.64 | 1.42 | −14.79 | −0.13 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 119 | +0.11 | 0.13 | −24.37 | −0.61 | ✅ | ✅ |
| 2025-Q3 bull | bull | 127 | +0.71 | 1.62 | −22.35 | +0.41 | ✅ | ✅ |
| 2026-recent bull | bull | 87 | −0.77 | −1.59 | −20.28 | +0.71 | ❌ | ❌ |

**Aggregate:** median-win Sharpe −0.25 · 50% positive · 62% beat BH · **946 trades** · worst instr DD −24.37% · **ann-on-deployed −8.71%/yr**. (My compounding annualizer reads −8.71% vs the report's simple −8.07%; same direction/magnitude, method held constant across all variants below.)

---

## Levers tested

| Lever | Mechanism | Code change? |
|---|---|---|
| **1. Slower rebalance** | `rebalance_bars` 5→10→15→21 (weekly→monthly) | No (parent param) |
| **2. Magnitude-gated entry** | new `min_drop_pct`: only enter names down worse than X% over lookback; take ≤K, never relax to force K | **Yes** — added to lowturn candidate |
| **3. Fewer legs** | `top_k` 5→4→3→2 | No (parent param) |
| **3b. Tighter safety rail** | `safety_max_loss_pct` −50→−25 (caps a crashing leg held all month) | No (parent param, `safety_backstop`) |
| **4. Hold-the-winners overlap** | **ALREADY in the parent** — `decide_xsec` only closes names rotating OUT of bottom-K and only buys names not held. Confirmed by reading strategy.py: turnover = churn in bottom-K membership, not sell-and-rebuy. **No protected-file change available to cut further; skipped as a no-op.** | n/a |

Lever 4 note: the single biggest turnover cut the task flagged is already baked into the parent's rotate-out/open-new logic. Cutting it further (e.g. partial-rebalance bands) would require touching the harness's rebalance mechanics — protected territory — so it was **not** pursued, per constraint.

---

## Turnover-vs-alpha-decay frontier (the knee)

Param-only sweep (no magnitude gate), full 8-window WF:

| Config | Trades | medWin Sharpe | worst instrDD % | ann-on-deployed | Fitness | #5(b) |
|---|---|---|---|---|---|---|
| **baseline** reb5/K5 | 946 | −0.25 | −24.37 | −8.71%/yr | 🔴 | 🟢 |
| reb5/K3 | 644 | −0.22 | −24.37 | −12.43%/yr | 🔴 | 🟢 |
| reb10/K5 | 512 | −0.07 | −26.82 | +0.71%/yr | 🔴 | 🟢 |
| reb10/K4 | 426 | −0.26 | −24.37 | +2.05%/yr | 🔴 | 🟢 |
| reb10/K3 | 334 | −0.07 | −24.37 | +0.68%/yr | 🔴 | 🟢 |
| reb15/K3 | 222 | +0.02 | −19.51 | +1.03%/yr | 🔴 | 🟢 |
| reb21/K5 | 218 | −0.10 | −32.80 | +5.28%/yr | 🔴 | 🔴 |
| reb21/K4 | 180 | +0.31 | −32.80 | +6.32%/yr | 🔴 | 🔴 |
| **reb21/K3** | **152** | **+0.57** | **−32.80** | **+10.33%/yr** | 🟢 | 🔴 |

**The knee is monthly (reb21).** That is where ann-on-deployed flips clearly positive — the reversal alpha survives the horizon-stretch enough to clear the cost drag once turnover is cut ~6×. Below monthly (reb10/15) the cost drag still dominates; the signal's gross edge per round-trip is just too small at 4bps to support weekly/biweekly churn.

**But monthly cadence introduces a NEW failure: deployed-capital DD.** Every reb21 variant hits worst instr DD −32.80% (2025-Q1 tariff bear) — a single loser leg craters and is held unhedged for 21 bars. That **trips GATE #5(b)** (>30%). The fix that preserves the cost savings is the **−25% safety rail** (lever 3b), which force-closes the cratering leg early:

| reb21/K3 + rail | worst instrDD % | ann-on-deployed | #5(b) |
|---|---|---|---|
| no rail (−50) | −32.80 | +10.33%/yr | 🔴 FAIL |
| **−25 rail** | **−28.80** | **+10.22%/yr** | 🟢 PASS |

So the rail buys #5(b) compliance at ~0.1pp return cost — but note the margin is thin (−28.80% vs −30% ceiling, 1.2pp) and **entirely rail-dependent**: at a −30 or −50 rail it's back to −32.7% and fails. The candidate passes #5(b) *only because* the rail is set just tight enough. Flagged as fragile.

---

## Magnitude-gate sweep (lever 2) on the reb21/K3/−25-rail base

| min_drop_pct | Trades | medWin Sharpe | beat BH | ann-on-deployed | note |
|---|---|---|---|---|---|
| None (parent) | 153 | 0.57 | 75% | +10.22%/yr | baseline gate-off |
| **−3.0** | **90** | **0.88** | **88%** | **+10.64%/yr** | sharpest edge, adequate trades |
| −4.0 | 61 | 0.81 | 75% | +6.71%/yr | thinning |
| −5.0 | 50 | 0.21 | 88% | +6.83%/yr | sparse-signal degradation |
| −6.0 | 30 | 0.44 | 75% | +7.16%/yr | at the #4 trade-count floor |
| −8.0 | 19 | 0.44 | 75% | +7.01%/yr | **below #4 trade-count=30 floor** |

**Magnitude-gate knee is −3.0%:** lifts median-win Sharpe 0.57→0.88, beat-BH to 88%, on 90 trades. Beyond −4% the **sparse-signal risk that killed meanrev3d_qqq materializes** — trade counts collapse and Sharpe degrades; ≤−8% would fail GATE #4 (trades ≥30). This confirms the gate must stay shallow.

---

## The lead candidate and why it REJECTS

The single config that superficially cleared the most gates: **reb21 / K4 / lb5 / −25 rail / drop−3.0**.

| Window | Regime | Trades | Return % | Sharpe | instrDD % | BH % | Beats BH? | BarA#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 17 | +1.06 | 1.65 | −21.39 | −1.12 | ✅ | ✅ |
| 2022-Q3 chop | chop | 20 | −0.31 | −0.45 | −12.17 | −0.69 | ✅ | ✅ |
| **2023-H1 recovery** | bull | 4 | **−0.04** | −0.26 | −7.28 | **+0.22** | ❌ | **❌** |
| 2023-Q3 chop | chop | 10 | +0.44 | 1.63 | −4.89 | −0.37 | ✅ | ✅ |
| 2024-Q2 bull | bull | 14 | +0.22 | 0.72 | −11.17 | −0.13 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 13 | −0.66 | −0.79 | −28.80 | −0.61 | ❌ | ❌ |
| 2025-Q3 bull | bull | 8 | +1.14 | 2.84 | −9.09 | +0.41 | ✅ | ✅ |
| 2026-recent bull | bull | 12 | +1.18 | 2.38 | −19.51 | +0.71 | ✅ | ✅ |

**Aggregate:** median-win Sharpe **1.17** · 62% positive · 75% beat BH · **98 trades** (vs 946 baseline, **−90%**) · worst instr DD **−28.80%** · ann-on-deployed **+10.13%/yr**.

### Gate-by-gate verdict (the honest read)

**Standard front door:**
- Fitness gate: 🟢 PASS (median-win Sharpe 1.17 > 0.5, 62% positive, 75% beat BH, median ret +0.33%).
- **BarA#1: 🔴 FAIL.** 2023-H1 recovery (−0.04% < BH +0.22%) and 2025-Q1 tariff bear both fail (a); only 1 (b)-escape is allowed and it can't rescue both. **Structural, not fixable by tuning:** a buys-losers book lags equal-weight BH in a v-shaped recovery where everything bounces. Magnitude-gating actually *worsens* this window (only 4 trades fire — it barely participates in the recovery, going flat-ish at −0.04% while BH makes +0.22%).
- → **REJECT via standard door.**

**#5 fast-track (clause (d) bypasses #1 and #3):**
- (b) deployed-capital DD ≤30%: 🟢 PASS (−28.80%) — but rail-dependent and thin (see fragility note).
- (c) per-window V1/V2 + no-catastrophe: 🟢 PASS (verified all 8 windows).
- (f) ≥8%/yr on deployed: 🟢 PASS (+10.13%/yr).
- **(a) Full-period Sharpe ≥1.0: 🔴 FAIL.**

### The clause-(a) finding (decisive)

Clause (a) binds on **full-period continuous-span Sharpe** — the single concatenated equity-return series across all 8 windows annualized with √252 — exactly as the `xsec_momentum_xa` promotion record defines it ("True FP Sharpe on real 2020+ data is 1.04 ... 1.13 was the best single-window Sharpe, not the full-period Sharpe"). Measured that honest way:

| Config | **FP continuous Sharpe** | median-window Sharpe (mirage) | trades |
|---|---|---|---|
| reb21/K4/lb5/drop3 (lead) | **+0.73** | +1.17 | 98 |
| reb21/K3/lb5/drop3 | +0.69 | +0.88 | 90 |
| reb21/K4/lb5/drop2.5 | +0.72 | +1.02 | 109 |
| reb21/K4/**lb6**/drop3 (best found) | **+0.80** | +1.69 | 99 |
| reb21/K3/lb5/dropNone | +0.56 | +0.57 | 153 |

**Not one variant reaches FP continuous Sharpe ≥1.0.** The lead's true (a) number is **0.73**, a full 0.27 short. The +1.17 median-window figure was the **best-window-vs-full-period inflation** the momentum-record correction explicitly warned about — median-of-8-windows over-weights the two calm-tape windows (2025-Q3 Sharpe 2.84, 2026 2.38) and ignores that the continuous series spends long stretches flat or bleeding. → **REJECT via #5 fast-track at clause (a).**

### Overfit / knife-edge evidence (independent second reason to reject)

Param-jitter around the lead, one knob at a time — median-window Sharpe (the *generous* metric, and it still falls apart):

| Jitter | medWin Sharpe | clears ≥1.0? |
|---|---|---|
| center (lead) | 1.17 | ✅ |
| K=3 | 0.88 | ❌ |
| K=5 | 0.95 | ❌ |
| drop −3.5 | 0.97 | ❌ |
| drop −4.0 | 0.81 | ❌ |
| **lookback 4** | **0.07** | ❌ (near-total collapse, 1-bar change) |
| lookback 6 | 1.69 | ✅ |
| lookback 7 | 1.03 | ✅ |
| rebalance 18 | 0.59 | ❌ |
| rebalance 24 | 0.36 | ❌ |

The Sharpe≥1.0 pass exists on a **narrow ridge**: K must be exactly 4, rebalance exactly 21, drop exactly −3.0±0.5, lookback 5-7. Move one knob one notch in most directions and it fails — lb=4 → 0.07 is the clearest tell that the edge isn't structurally robust to the signal-horizon. Even if FP Sharpe had cleared 1.0 (it didn't), this jitter profile is the overfit signature the task asked me to be skeptical of. **A lead config that only wins as the argmax of a multi-knob sweep, with failing neighbors, has not earned a promotion.**

---

## Front-door verdict summary

| Variant (all reb=monthly knee) | FP Sharpe (a) | ann/deployed (f) | instrDD (5b) | clause(c) | BarA#1 | **VERDICT** |
|---|---|---|---|---|---|---|
| reb21/K3/dropNone/−25 | 0.56 | +10.22% 🟢 | −28.80 🟢 | 🟢 | 🔴 | **REJECT** (a<1.0, #1) |
| reb21/K3/drop−3/−25 | 0.69 | +10.64% 🟢 | −28.80 🟢 | 🟢 | 🔴 | **REJECT** (a<1.0, #1) |
| **reb21/K4/drop−3/−25 (lead)** | **0.73** | +10.13% 🟢 | −28.80 🟢 | 🟢 | 🔴 | **REJECT** (a<1.0, #1) |
| reb21/K4/lb6/drop−3/−25 (best a) | 0.80 | +11.25% 🟢 | −24.02 🟢 | 🟢 | 🔴 | **REJECT** (a<1.0, #1) |

**No PROMOTE-eligible candidate.** Standard door blocked by BarA#1 (structural recovery-window BH underperformance). #5 fast-track blocked by clause (a) — true full-period Sharpe 0.73–0.80, short of 1.0. Both blocks are honest; no return-floor or median-Sharpe side door was used (the gate's own continuous-Sharpe definition is what closes it).

---

## The tradeoff I found (the knee, stated plainly)

- **Turnover→cost:** the parent's gross reversal edge per round-trip is **smaller than ~4bps at $100 notional**. Weekly (946 trades) and even biweekly (334–512 trades) cadences leave net return negative-to-barely-positive. **Monthly (reb21, ~150–220 trades) is the knee** where ~+10%/yr-on-deployed emerges. A real ~19pp/yr swing from cutting turnover ~6×.
- **Horizon→alpha decay:** push past monthly (reb24) and Sharpe collapses (0.36) — the 5-day reversal signal has decayed too far by the time a monthly book acts on it. The cadence is **boxed between reb18 (cost still wins) and reb24 (alpha gone)**, with reb21 the only survivor — itself a sign of a thin, fragile edge, not a broad plateau.
- **Concentration→DD:** smaller K and longer holds raise single-leg deployed DD (−32.8% at reb21), requiring the −25% safety rail to stay under #5(b)'s 30% ceiling. The rail works but leaves only 1.2pp margin.
- **Magnitude-gate→sparsity:** the −3% entry gate sharpens conviction (Sharpe ↑, beat-BH ↑) but past −4% reintroduces the meanrev3d_qqq sparse-signal failure; ≤−8% breaches GATE #4's 30-trade floor.
- **The honest verdict:** every lever helps the *gross* picture, and net return genuinely clears the cost-strangle — but the **risk-adjusted edge (full-period Sharpe) never reaches 1.0**, and the config that comes closest is an overfit ridge. The signal is real (Lehmann/Lo-MacKinlay short-horizon single-name reversal); at 4bps/$100 it is **not strong enough, risk-adjusted, to deploy** under the corrected ruler.

---

## Survivorship / lookahead / sparse-signal / integrity notes

- **Lookahead:** uses the audited-clean `walk_forward_xsec`/`backtest_xsec` path unchanged (strategy sees `bars[:cur+1]`, fills at that bar's close only `if has_bar_at_t`, regime SPY slice `t[:10] <= date`). The magnitude gate reads only trailing returns already in `ranks_preview`; no same-bar leak introduced.
- **Sparse-signal:** explicitly monitored. No window hit `ZeroTradesError`. Per-window trade counts reported for every variant; the −3% gate keeps all 8 windows non-empty (min 4 trades, 2023-H1). Thresholds ≥−5% flagged as degrading and ≥−8% as breaching GATE #4.
- **Survivorship:** identical fixed mid-2020 large-cap universe to the parent — no IPO bias, mild-and-flagged delisting bias, laggards retained, not hindsight-selected.
- **Warmup:** 40d (> the 5-bar lookback) for all runs; baseline reproduced to the decimal, confirming no warmup-starvation artifact.
- **Cost model:** alpaca_stocks 4bps round-trip, asserted active before every run. No zero-cost path.
- **FP-Sharpe methodology:** clause (a) computed as continuous concatenated-equity √252 Sharpe (matching the momentum promotion record), NOT median-of-windows — the distinction is load-bearing and is the decisive reject reason.

---

## Artifacts & integrity

- **Candidate written:** `strategies_candidates/xsec_ss_meanrev_lc20_lowturn/` (`strategy.py` + `params.json`). Adds the `min_drop_pct` magnitude-gate lever (default `null` recovers exact parent behavior); ships the monthly-knee params (reb21/K3/−25 rail) as defaults. STAYS in `strategies_candidates/` — ZERO promotion.
- **Driver scripts (research-only, in `reports/`, no `test_` prefix so pytest ignores them):** `_lowturn_driver.py` (loads candidate decide_xsec from `strategies_candidates/`, runs full WF, asserts cost model active), `_lowturn_clausec.py` (#5 clause-(c) per-window evaluator), `_lowturn_fpsharpe.py` (full-period continuous-span Sharpe — the honest clause-(a) number).
- **Tests:** `237 passed in 7.03s` after the candidate was added — no regression vs the 237 baseline.
- **Smoke test:** `./tick.sh --candidate xsec_ss_meanrev_lc20_lowturn` → `SMOKE OK xsec`, rc=0, actions `{MRK=buy, WMT=buy, PEP=buy}`, no DB errors.
- **Protected files UNTOUCHED — verified:** `runner/runner.py`, `runner/risk.py`, `runner/runner_xsec.py`, `runner/backtest.py`, `runner/backtest_xsec.py`, `runner/walk_forward.py`, `runner/walk_forward_xsec.py`, `runner/safety_backstop.py` all carry mtimes ≤ 2026-05-31_19:11, predating this session (2026-06-01 ~21:00 UTC). Only the new candidate dir is dated today. The harness override path (passing `decide_xsec_fn`+`params` into `walk_forward_xsec`) was used to evaluate a `strategies_candidates/` strategy without modifying the loader — same pattern the rejection report used.
- **Lever 4 (hold-the-winners overlap):** confirmed already present in the parent's `decide_xsec` (rotate-out + open-new-only). No further turnover cut available without touching protected rebalance mechanics → skipped per constraint, as instructed.

## Recommendation

**Do not promote.** Close the single-stock short-horizon reversal lane at $100/4bps: the signal is real and the turnover cut is the right diagnosis (net flips positive), but risk-adjusted (full-period Sharpe ≤0.80) it does not clear the front door, and the closest config is overfit. Candidate retained in `strategies_candidates/` for provenance. If the lane is revisited, the only structural lever left is a larger notional (lower bps-on-notional drag) or a different signal entirely — not more parameter tuning of this one.
