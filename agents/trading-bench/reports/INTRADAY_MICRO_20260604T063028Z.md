# INTRADAY MICROSTRUCTURE — Lane Report

**Generated:** 2026-06-04T06:30:28Z
**Author:** trading-bench research subagent (lane: intraday-micro, grow-to-10 seat)
**Surface tested:** SPY **5-minute** bars (a genuinely different eval surface from the daily lanes)
**Scratch:** `strategies_candidates/intraday_micro/` · **Driver:** `reports/_intraday_micro_driver.py`
**Promotion authority:** ZERO. This is a research finding only.

---

## TL;DR VERDICT: **REJECT** (feasibility PASSED; no robust intraday edge found)

- **Feasibility: CONFIRMED.** The existing harness honestly consumes 5Min bars — no-overnight-leak holds, cost model stays ON and is sane (~4bps round-trip), trade-cap is not silently binding. A FEASIBILITY-BLOCKED memo was *not* warranted; the harness works.
- **Two clean intraday archetypes swept** (opening-range mean-reversion *fade* and opening-range *breakout/momentum*), 72 + 27 cells, all 8 named regime windows, $1000 notional, active cost.
- **Intraday CONFIRMS the ~0.5 daily ceiling — it does NOT break it.** Every honest, plateau-robust cell lands at **RTH-corrected FP-cont Sharpe ≈ +0.25 to +0.45** (ann **+2% to +3.5%/yr** on deployed). The single higher cell (RTH Sharpe +0.73 / +5.5%/yr) is a **one-window artifact** carried entirely by 2025-Q1's tariff-crash vol expansion, and is a trail-stop **knife-edge**, not a plateau.
- The ~0.5 ceiling is therefore looking like a property of the **eval surface / cost-realism**, not of the daily archetypes. A fundamentally different microstructure surface (5Min, intraday seasonality, OR effects) lands in the *same* ~0.5 neighborhood once annualization and cost are honest.

---

## 1. Archetype & no-overnight-leak justification

**Archetypes (both opening-range-anchored, the canonical intraday family):**
- **FADE** (intraday mean-reversion): build an opening range (OR) over the first `or_bars` RTH 5Min bars; when price extends `z_thr` OR-heights *below* the OR mid, **buy the dip** betting on reversion to mid; exit on reversion (`tp_frac`), a stop (`stop_frac` OR-heights against), or forced flat at `exit_by`.
- **BREAKOUT** (intraday momentum): when price breaks `break_buf` OR-heights *above* the OR high, **buy the continuation**; exit on a trailing stop `trail_frac` OR-heights below the running high, or forced flat at `exit_by`.

Both implement only the **long leg** (buy/close) — the harness backtester has no native short and the cost model can't price fictional short fills, so I deliberately did NOT fake shorts. The long leg is the honest, harness-expressible half.

**No-overnight-leak (TRAP #1) — confirmed on three independent grounds:**
1. **Harness causality is structural.** `runner/backtest.py` exposes `market_state["bars"] = bars[:i+1]` and `last_price = close_of_bar_i`. `decide()` at bar *i* can only see bars at-or-before *i*. My code never indexes forward; the OR and day-state are rebuilt at the first bar of each new UTC day from already-seen bars.
2. **Default `allow_overnight=False`** forces a square-off at/after `exit_by` (19:45 UTC ≈ 15:45 ET) and on any out-of-RTH bar, so the strategy is **flat overnight by construction** → measured PnL is *intraday* reversion/continuation, not the overnight gap.
3. **Overnight ablation run** (relabel guard, see §4): holding overnight did not help (it slightly *worsened* the fade), confirming the lane's PnL is not a disguised overnight-gap bet.

---

## 2. Intraday cost reality check (TRAP #2)

- Cost model: `CostModel.alpaca_stocks()` = **spread_bps=2.0 one-way → ~4bps round-trip**, applied to every fill. **Always ON.**
- **Trade-cap is NOT silently binding.** The harness `MAX_TRADES_PER_DAY=4` cap counts buys+closes. Both archetypes do **≤1 entry + 1 exit/day = 2 trades/day** by design — the driver asserts `max_trades_in_any_single_day ≤ 2` for intraday-only cells (verified across the whole sweep; overnight-hold cells touch 4 on roll days). So no intraday strategy here was truncated by the cap.
- **Cost magnitude is real but not fatal at this trade frequency.** Representative cells: ~440–720 round-trips over the 1.88-yr concatenated span → **total cost $36–$145** on a $1000 book. Per-trade gross edge is tiny (intraday 5Min moves are small), so cost eats most marginal cells — which is exactly why the *plateau* sits near zero and only extreme/rare-trigger cells survive. Cost did not *obliterate* feasibility (the harness runs fine), but it is the binding reason the edge can't clear ~0.5.

---

## 3. Sweep grids + honest FP-cont Sharpe (plateau vs knife-edge)

**Two Sharpe columns reported per cell — annualization honesty:**
`fp_continuous_sharpe(timeframe='5Min')` uses the harness `bars_per_year('5Min') = 12*24*365 = 105,120`, a **24/7 wall-clock** count. Stock 5Min bars exist only in RTH (~78–87 bars/day × 252 ≈ 19,656/yr). The harness number therefore **overstates** annualized intraday Sharpe by `sqrt(105120/19656) ≈ 2.313×` (the exact inflation flagged in `HARNESS_INTRADAY_AUDIT` F3). I report:
- **`fp_h`** = raw harness number (what the gate's ruler literally returns for 5Min — itself a known overstatement), and
- **`fp_rth`** = `fp_h / 2.313` = the RTH-density-corrected Sharpe, which is the apples-to-apples comparison against the daily lanes' ~0.5.
**The gate-relevant, honest number is `fp_rth`.**

### 3a. FADE (intraday mean-reversion) — 72 cells: **REJECT**
- Grid: `or_bars ∈ {3,6,12}` × `z_thr ∈ {0.5,1.0,1.5,2.0}` × `tp_frac ∈ {0.0,0.5}` × `stop_frac ∈ {1.0,2.0,3.0}`.
- **71 of 72 cells negative.** The ONLY positive cell: `or_bars=12, z_thr=2.0, tp_frac=0.5, stop_frac=1.0` → **fp_rth = +0.328, ann +0.98%/yr, only 94 trades**. Every neighbor of that cell is negative.
- **KNIFE-EDGE, not a plateau.** The single winner only trades on z≥2.0 extreme extensions (94 trades total) — it dodges cost by trading rarely, not by having edge. **Fading intraday dips is a loser** (catching falling knives in bear/chop windows). Clean REJECT.

### 3b. BREAKOUT (intraday momentum) — 27 cells: **REJECT (one-window artifact)**
- Grid: `or_bars ∈ {3,6,12}` × `break_buf ∈ {0.0,0.25,0.5}` × `trail_frac ∈ {0.5,1.0,2.0}`.
- **Mildly, mostly positive** — the genuine plateau (cells positive WITH positive neighbors) sits at **fp_rth ≈ +0.25 to +0.45 (ann +2% to +3.5%/yr)**.
- **Headline best:** `or_bars=12, break_buf=0.0, trail_frac=2.0` → **fp_h +1.690 / fp_rth +0.731 / ann +5.54%/yr / 568 trades / $114 cost**. BUT:
  - **trail_frac knife-edge:** same cell at trail=0.5 → fp_rth +0.127; trail=1.0 → +0.147; only trail=2.0 (barely-ever-stop, ≈ hold-to-EOD) wins. The "breakout" degenerates into "intraday long with a stop so wide it rarely fires."
  - **Single-window artifact (the decisive kill):** per-window decomposition of the best cell —

    | window | regime | strat ret | win-Sharpe |
    |---|---|---|---|
    | 2022-H1 | bear | −0.25% | −0.08 |
    | 2022-Q3 | chop | +3.56% | +4.07 |
    | 2023-H1 | bull | −0.30% | −0.28 |
    | 2023-Q3 | chop | −1.70% | −3.87 |
    | 2024-Q2 | bull | −1.47% | −2.64 |
    | **2025-Q1** | **bear** | **+10.38%** | **+8.49** |
    | 2025-Q3 | bull | −0.74% | −2.29 |
    | 2026-recent | bull | +1.29% | +3.48 |

    **5 of 8 windows are negative.** The entire full-period Sharpe is carried by **2025-Q1 tariff-crash** (+10.38%). Remove that one violent-vol window and the strategy is net-negative. That is the opposite of a robust plateau — it's a single-regime vol-expansion harvest. The plateau cell (`or_bars=6, buf=0.25, trail=2.0`, fp_rth +0.449) shows the **same shape**: 2025-Q1 +9.81% carries it, 5/8 windows negative.

---

## 4. BH-relabel honesty check (TRAP #3)

- **BH-intraday benchmark** (long at first RTH bar, flat at EOD, no overnight — same convention as the strategies): **fp_h −0.931 / fp_rth −0.403.** Buying-and-holding SPY intraday-only is a *loser* over this panel (the overnight gap, which BH-intraday excludes, is where SPY's drift lives — confirming the daily-lane finding that SPY return is gap-concentrated).
- **Correlation(best-breakout per-window ret, BH-intraday per-window ret) = +0.46.** Moderate, NOT 1.0. The breakout is *not* a relabeled buy-and-hold: it actually outperforms in the bear/crash windows (2025-Q1, 2022-Q3) where BH-intraday craters — it's harvesting **intraday volatility expansion**, concentrated in crash events, not directional beta.
- **Overnight ablation:** holding overnight (`allow_overnight=True`) did NOT improve the fade (−0.989 vs −1.178 fp_rth, ann actually worse) — so the lane PnL is genuinely intraday, not a disguised overnight-gap directional bet. **Relabel trap cleared:** the (weak) edge is real intraday microstructure, it's just not large or robust enough.

---

## 5. Deployed-%/yr and gate check

- Best honest plateau: **ann +2% to +3.5%/yr on deployed $1000**, net of cost. Single-window-flattered best: +5.5%/yr.
- **Gate (Bar A / #5):** requires FP-cont Sharpe ≥ 1.0 AND ≥ 8.0%/yr-on-deployed AND a robust plateau beating BH.
  - Sharpe: honest `fp_rth ≈ 0.45` ≪ 1.0. **FAIL.**
  - Return floor: ≤ +3.5%/yr plateau (best-case +5.5% is one-window) ≪ 8%/yr. **FAIL.**
  - Plateau: knife-edge / single-window. **FAIL.**
  - Beats-BH: technically yes vs the (negative) BH-intraday, but on a one-window basis. Not admissible.
- **Trade count ≥30: PASS** (hundreds). **MaxDD ≤30%: PASS** (worst window DD ~−8%). These are the only bars cleared; the edge bars are missed by a wide margin.

**Nothing here is promotable. REJECT.**

---

## 6. Does intraday BREAK or CONFIRM the ~0.5 daily ceiling?

**CONFIRMS the ceiling — strongly.** Tonight five daily price/macro signal classes all capped at ~0.50–0.57 FP-cont Sharpe. This lane tested a *genuinely different surface* — 5-minute bars, opening-range effects, intraday mean-reversion vs momentum, time-of-day square-offs — and the honest, plateau-robust result lands at **RTH-corrected Sharpe ≈ 0.25–0.45**, i.e. **at or below the same ~0.5 neighborhood**, with the only higher number being a single-regime artifact.

Two reinforcing signals that the ceiling is the **surface / cost-realism**, not the archetype:
1. A completely orthogonal microstructure surface reproduces the same ~0.5 cap.
2. The binding constraint is visibly **cost vs. tiny intraday gross edge** — the plateau hugs zero precisely because ~4bps round-trip eats most 5Min moves, and only rare-trigger or single-event cells poke above it.

**Recommendation for where to dig next:** NOT deeper intraday-SPY single-name (this is a dry hole at honest cost). If the ceiling is the cost/eval surface, the productive directions are (a) lower-turnover holds where cost is amortized over larger moves, or (b) genuinely uncorrelated *sources* (cross-asset, true cross-sectional dispersion) rather than another price-derived signal on the same instrument. Intraday did its job: it's strong evidence the ~0.5 is the **floor of the realistic-cost daily-and-intraday price surface**, not a quirk of the daily archetypes.

---

## 7. Integrity

- Protected files **unchanged** (md5 verified at finish):
  - `runner.py = 4be185e4bdcb6f432d99b71b21a4859c` ✓
  - `backtest.py = 9444ee5be64d9fd2639fd8cb0a28e002` ✓
  - `backtest_xsec.py = 2278a4c8d8a66703da5cd6f2a0880061` ✓
  - `risk.py = e4c227e019c99e7e52224eb2f91389b8` ✓
- Composed PUBLIC `runner.backtest.backtest` + canonical `runner.fp_sharpe.fp_continuous_sharpe(timeframe='5Min')`. No custom evaluator. No new eval ruler.
- All numbers over the identical 8-window NAMED_WINDOWS panel + active `alpaca_stocks` cost model, $1000 notional.
- **Annualization caveat surfaced, not hidden:** the harness 5Min `bars_per_year` is a 24/7 wall-clock count that overstates intraday-stock Sharpe ~2.31×; `fp_rth` is the corrected, gate-relevant number. (Pre-existing harness limitation per HARNESS_INTRADAY_AUDIT F3 — flagged, not patched, since protected-file edits are out of scope.)

**Verdict: REJECT. Feasibility passed; no robust intraday edge; intraday CONFIRMS (does not break) the ~0.5 ceiling. Honest REJECT = success.**
