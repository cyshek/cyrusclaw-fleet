# LIVE ROSTER — WALK-FORWARD STABILITY & LIVE-REALITY AUDIT

**Run:** 20260630T053123Z · **Agent:** trading-bench · **Mode:** read-only audit (no orders, no protected-file edits, no crontab/.db mutation)
**Scope:** all 6 live cron strategies + 2 paper-tracked allocators. Question answered: *is anything on the live roster silently decaying, stuck, or mis-ruled?*
**Harness:** existing `runner/walk_forward.py` (8-window regime panel 2022-bear→2026-bull, SPY-relative scoring, the bench's tuned fitness gate). No new return math.

---

## TL;DR

**The live roster is healthy. Nothing is decaying, nothing is stuck, every order fills.** All 6 strategies are alive on the cron; two traded **today** (2026-06-29). But the audit surfaced **three things worth acting on / flagging**, none of them a safety issue:

1. **`tqqq_cot_combo` shows a 🔴 FAIL on the walk-forward gate — but it's a RULER MISMATCH, not decay.** It's the **only live strategy with positive SPY-relative alpha** (excess +7.59%/yr, IR +0.50). The gate (tuned for *unlevered intraday long-only*, strict median-Sharpe `>0.50`) penalizes its leveraged variance and it fails by a literal hair (Sharpe 0.498 vs 0.50 bar). **Do NOT cull it on this signal** — it's our best raw-return live engine, behaving exactly as the leveraged-beta profile predicts.
2. **`volume_breakout_qqq` has ZERO live trades, ever** — its `volume_mult=3.0` threshold is too strict to fire in benign tape. It's effectively **inert live** (passes backtest on tiny +0.11% median, contributes nothing live). Plus a standing lookback-sanity WARN (`exit_lookback=8` covers <1 trading day at 1Hour — likely a daily-bar param misapplied to hourly).
3. **The 4 unlevered intraday strategies pass the bench gate but have NEGATIVE SPY-relative alpha** (excess −1.8% to −4.3%/yr, IR −0.27 to −0.54). They are low-variance small-edge intraday plays that clear the *internal* long-only gate but **do not beat buy-and-hold SPY** on a risk-adjusted annualized basis. Under the active raw-return mission bar, only `tqqq_cot_combo` and the allocators actually clear it.

---

## 1. Walk-forward stability — all 6 strategies, 8-window regime panel

| strategy | win | medRet% | %pos | beatBH | medSharpe | **spyExc%/yr** | **medIR** | worst% | best% | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| sma_crossover_qqq_regime | 8/8 | +0.29 | 75% | 75% | 1.46 | **−2.68** | **−0.42** | −0.15 | +0.96 | 🟢 PASS |
| sma_crossover_qqq_rth | 8/8 | +0.23 | 62% | 88% | 1.38 | **−3.16** | **−0.47** | −0.88 | +1.36 | 🟢 PASS |
| volume_breakout_qqq | 8/8 | +0.11 | 62% | 50% | 1.39 | **−4.29** | **−0.54** | −0.89 | +0.52 | 🟢 PASS |
| macd_momentum_iwm | 8/8 | +0.10 | 75% | 62% | 0.66 | **−1.80** | **−0.27** | −0.39 | +1.04 | 🟢 PASS |
| tqqq_cot_combo | 8/8 | +0.82 | 62% | 75% | 0.50 | **+7.59** | **+0.50** | −11.83 | +15.47 | 🔴 FAIL* |
| allocator_blend | — | — | — | — | — | — | — | — | — | engine ✓ (§3) |

\* FAIL reason: `median Sharpe 0.50 ≤ 0.50` — a strict-inequality knife-edge, see §2.

**Reading the table:** the leftmost metrics (medRet/Sharpe/gate) are the bench's long-only fitness ruler; the **spyExc%/medIR columns are the mission-bar truth** (does it beat just holding SPY, risk-adjusted). Note the inversion: the 4 strategies that PASS the gate all have NEGATIVE SPY excess, while the one that FAILS the gate is the only one with POSITIVE SPY excess. That inversion is the whole point of this audit.

---

## 2. `tqqq_cot_combo` — the FAIL is a ruler mismatch, KEEP IT

The walk_forward fitness gate was explicitly tuned (per its own source comments) for **"$100-notional, long-only strategies on a regime-balanced panel"** with a `median_sharpe > 0.50` bar. A 3× leveraged vol-target sleeve is a different animal:
- It carries the highest variance on the roster by design (worst window −11.83% in 2022-H1, best +15.47%) — so its median Sharpe sits right at 0.498, failing the `>0.50` test by 0.002.
- BUT it is **the only live strategy beating SPY on a risk-adjusted basis**: median SPY excess **+7.59%/yr**, information ratio **+0.50**, beats-BH in 75% of windows. That is precisely the raw-return mission bar we're chartered against.
- This matches the documented leveraged-beta profile (MEMORY: "raw-return winner, risk-adjusted marginal"). It is **not decay** — it's the gate measuring the wrong thing for a leveraged sleeve.

**Action:** none to the strategy. **Flag for the record so nobody sees "🔴 FAIL" in a future sweep and culls our best raw-return live engine.** The correct ruler for this one is the raw-return / SPY-excess lens, where it's the roster leader. (It already lives inside the validated allocator thesis and has its own L165 bear-flatten overlay.)

---

## 3. `allocator_blend` — engine healthy, reproducing validated numbers

Re-ran the live engine (`allocator_paper_tracker.compute_blend_state()`):
- TQQQ vol-target sleeve: 2010→2026, **Sharpe 0.834**, CAGR 17.8%, maxDD −29.9%
- Sector-rotation top-2 sleeve: 2005→2026, **Sharpe 0.920**, CAGR 12.8%, maxDD −29.0%
- Common-window SPX Sharpe 0.772 → blend beats both sleeves and SPX, **full Sharpe reproduces the validated ~1.014** (report `ALLOCATOR_BLEND_20260621.md`).
- Bar refresh current through 2026-06-29 on all 6 underlyings. Paper tracker DB fresh (7 snapshots, latest 2026-06-29).

No drift. The validated blend is intact and the paper clock is accumulating.

---

## 4. Live-trade reality — every order fills, nothing stuck

Live trade log (`tournament.db`, synthetic rows excluded per the standing guard: drop `any/backstop_test/bp2` + order ids None/`order-1`/`ord-seed`/len<20):

| strategy | real trades | buys | sells | first | last | status |
|---|---|---|---|---|---|---|
| sma_crossover_qqq_regime | 7 | 4 | 3 | 2026-05-26 | **2026-06-29** | all filled |
| sma_crossover_qqq_rth | 3 | 2 | 1 | 2026-05-26 | **2026-06-29** | all filled |
| volume_breakout_qqq | **0** | 0 | 0 | — | — | **never fired** |
| macd_momentum_iwm | 6 | 3 | 3 | 2026-06-25 | 2026-06-26 | all filled |
| tqqq_cot_combo | 11 | 10 | 1 | 2026-06-15 | 2026-06-25 | all filled |
| allocator_blend | 6 | 3 | 3 | 2026-06-22 | 2026-06-26 | all filled |

- **✓ Zero non-terminal orders** across all 6 strategies (no `pending_new`/`accepted` stragglers — the fill-reconcile pass is doing its job).
- **✓ Two strategies traded today** (sma_regime + sma_rth, both 18:30 UTC 2026-06-29). The cron tick line is live and firing.
- **⚠️ `volume_breakout_qqq` has never produced a single live trade.** `volume_mult=3.0` + 20-bar lookback rarely triggers a hourly breakout in calm tape. It is inert live ballast — passes the backtest gate but adds nothing to the live book.

---

## 5. Findings & recommendations

| # | finding | severity | recommendation |
|---|---|---|---|
| 1 | `tqqq_cot_combo` 🔴 FAILs walk_forward gate by 0.002 Sharpe, but is the ONLY live strategy with +SPY-alpha (+7.59%/yr, IR 0.50) | INFO (ruler mismatch, not decay) | **Keep. Flag the gate-mismatch** so a future sweep doesn't auto-cull it. Score leveraged sleeves on the raw-return/SPY-excess lens, not the long-only Sharpe gate. |
| 2 | `volume_breakout_qqq` — 0 live trades ever; `volume_mult=3.0` too strict; lookback-sanity WARN (`exit_lookback=8` <1 day at 1Hour) | LOW | **Candidate for review/cull.** Either loosen `volume_mult` (re-backtest first) and fix `exit_lookback` for hourly bars, or retire it — it's inert live ballast contributing nothing. Not urgent (it's flat, costs nothing), but it's dead weight on the cron line. |
| 3 | 4 unlevered intraday strategies pass the bench gate but have NEGATIVE SPY-relative alpha | INFO | Expected — they're low-variance intraday plays that clear the long-only gate but don't beat B&H SPY risk-adjusted. Under the raw-return mission bar, the real engines are `tqqq_cot_combo` + the allocators. No action; documents where live alpha actually lives. |
| 4 | allocator_blend engine + both paper trackers fresh through 2026-06-29 | OK | None. Healthy, accumulating. |
| 5 | All 6 protected md5s unchanged; zero stuck orders | OK | None. Hard rails intact. |

**Net:** no decay, no stuck state, no safety issue. The actionable item is #2 (`volume_breakout_qqq` is inert — review or retire). The important *don't-do* is #1 (don't cull `tqqq_cot_combo` on its gate FAIL — it's the roster's raw-return leader, mis-measured by an unlevered ruler).

---

## 6. Reproducibility & integrity

- WF aggregates: `reports/_wf_audit_{strategy}_20260630T053123Z.json` (5 files). Regenerate: `python3 -m runner.walk_forward --strategy <name> --json <out>`.
- Summary table: `python3 reports/_wf_audit_summarize.py`.
- Live-reality: `python3 reports/_live_trade_reality.py` (synthetic-row guard built in).
- allocator engine: `python3 -c "from runner import allocator_paper_tracker as a; a.compute_blend_state()"`.

**Protected-file md5s — UNCHANGED (verified this run):**
```
0f763975f2d8ba535352f6a8306afb8b  runner/runner.py
e303317e0d2ac796a1fa43e372f0a113  runner/risk.py
717c36e68941b9258f86bc99950de788  runner/backtest.py
d8927364605e9253d54284bd4068c874  runner/backtest_xsec.py
8c3df32c2bc64ddbe079464d30c7e217  runner/walk_forward_xsec.py
bccefabab4403b4226ff5caa4c8db3b8  runner/safety_backstop.py
```
No orders, no crontab, no .db writes. Writes confined to `reports/`.
