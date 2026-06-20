# NON-PRICE SIGNAL CLASS — Round 2: B1 vol-regime (Moreira-Muir) + B2 asymmetric credit veto

**UTC:** 2026-06-02T01:05:35Z
**Author:** trading-bench subagent (non-price signal-class sweep, round 2)
**Harness:** SECOND + THIRD real use of `runner/sweep.py` + `runner/fp_sharpe.py` (single-symbol path)
**Verdict:** ❌ **BOTH REJECT.** B1 (vol-regime, the strongest published prior) gets *closest of anything tried* — best FP-cont Sharpe **+0.87** on a real PLATEAU — but **no cell reaches the 1.0 front-door bar.** B2 (asymmetric credit veto) is a **uniform failing basin**, FP-cont Sharpe [−1.56, −0.44], worse than BH-SPY everywhere — the credit signal carries no exploitable equity-timing edge net of cost, symmetric OR asymmetric.

---

## 0. TL;DR verdict per family

| family | best FP-cont Sharpe | beats BH-SPY (−0.034)? | reaches ≥1.0? | robustness | front-door verdict |
|---|---|---|---|---|---|
| **B1 vol-regime (VIXY-level binary)** | **+0.87** (vixy_lookback=10, band=0) | ✅ yes (much) | ❌ no (0.87 < 1.0) | PLATEAU (real) | ❌ **REJECT — clause (a) miss; promising but sub-bar** |
| B1 vol-regime (realized-vol binary) | +0.24 | ✅ yes | ❌ no | PLATEAU | ❌ REJECT |
| B1 vol-regime (proportional inverse-vol) | −0.03 | ≈ tie | ❌ no | none | ❌ REJECT |
| **B2 asymmetric credit veto** | **−0.44** (best) | ❌ no (worse than BH) | ❌ no | none (uniform fail) | ❌ **REJECT — no edge, worse than BH** |

**Headline:** the vol-regime prior is the *only* non-price signal that has produced a positive-and-robust FP-cont Sharpe AND beaten BH-SPY risk-adjusted in this tournament — but it tops out at **0.87, short of the 1.0 front-door bar**, so it is an HONEST REJECT, not a promotion. It is the **first sign of a real (if sub-threshold) non-crowded edge** and is the one prior worth *any* further investment (see §9). The credit veto is dead in both decision shapes.

---

## 1. Signal construction + decision shape

### B1 — vol-regime timing (Moreira-Muir vol-managed)
`strategies_candidates/vol_regime_spy_mm/`. Scale SPY exposure INVERSELY to a vol regime. Three interchangeable vol-signal sources / exposure shapes, all strictly trailing:

- **VIXY-level binary** (`vol_source=vixy`): regime gauge = `VIXY_close_t` vs its own `SMA(vixy_lookback)`. Vol elevated → `VIXY > SMA*(1+band)` → de-risk to cash; calm → `VIXY < SMA*(1-band)` → hold/enter SPY. Dead-band `band` gives hysteresis. Binary long/flat.
- **Realized-vol binary** (`vol_source=realized`): realized vol of SPY daily log-returns over trailing `vol_lookback`, vs that RV series' own trailing mean over `vol_sma` (self-referential threshold — no hard-coded vol level that wouldn't transfer). Vol HIGH vs its own recent norm → de-risk.
- **Proportional inverse-vol sizing** (`exposure_mode=proportional`): the literal Moreira-Muir construction — notional scaled by `target_vol / realized_vol`, capped at [0, notional] (no leverage).

Default state = invested; we only de-risk on a confirmed vol-elevated read.

### B2 — asymmetric credit risk-OFF veto (round-1 flagged fix)
`strategies_candidates/credit_veto_spy_asym/`. SAME signal source as round 1 (HYG/LQD ratio), **only the decision shape changed**:

- **DEFAULT = LONG SPY.** Invested unless credit forces us out.
- **VETO (→ cash) only on CONFIRMED risk-off:** ratio below `SMA(veto_lookback)*(1-veto_band)` for `confirm_days` CONSECUTIVE days. A single noisy dip does nothing.
- **SLOW re-entry:** once in cash, re-enter only when the ratio recovers above a LONGER `SMA(reentry_lookback)` for `reentry_days` consecutive days.

The asymmetry (default-long, deliberate veto, sticky re-entry) is exactly the round-1 §10 flagged fix: removes the fast round-trip whipsaw that killed the symmetric SMA-cross.

**No-lookahead (verified on disk, §8). Survivorship: single liquid ETFs (SPY/VIXY/HYG/LQD), all present across the full window. Data floor 2020-07-27, shared by all four (1469 daily bars each).**

---

## 2. Benchmark: buy-and-hold SPY on the SAME concatenated WF span

Computed in-driver via `walk_forward` with a buy-once-hold decide, then the canonical `fp_continuous_sharpe` over the concatenated per-tick equity returns — identical span/treatment to the swept cells.

| metric | BH-SPY |
|---|---|
| **FP-cont Sharpe (full concatenated span)** | **−0.0341** |
| sum-of-window return (bench-scaled) | −0.13% |
| n ticks in concatenated span | 468 |

Per-window BH-SPY return / DD: 2022-H1 −1.74%/−1.99%, 2022-Q3 −0.65%/−1.87%, 2023-H1 +0.74%/−0.82%, 2023-Q3 −0.38%/−0.72%, 2024-Q2 +0.48%/−0.47%, 2025-Q1 tariff −0.80%/−1.93%, 2025-Q3 +0.65%/−0.24%, 2026-recent +1.56%/−0.22%. (Bench-scaled: $100 notional / $1000 equity = 0.1× amplifier per the harness's `_benchmark_spy_return`.) Panel is bear-heavy, so BH's concatenated-span Sharpe is near zero — **but a timing overlay must still beat −0.034 materially AND clear 1.0 to pass the front door.**

---

## 3. Sweep grids

| sweep | family/mode | grid | cells |
|---|---|---|---|
| B1-vixy | VIXY-level binary | `vixy_lookback∈{10,20,40,60,100}` × `band∈{0.0,0.05,0.10,0.20}` | 20 |
| B1-realized | realized-vol binary | `vol_lookback∈{10,20,40}` × `vol_sma∈{40,60,120}` × `band∈{0.0,0.10}` | 18 |
| B1-prop | inverse-vol proportional | `vol_lookback∈{10,20,40}` × `target_vol∈{0.10,0.15,0.20}` | 9 |
| B2 | asymmetric credit veto | `veto_lookback∈{40,60,90}` × `confirm_days∈{2,3,5}` × `reentry_lookback∈{90,120}` × `reentry_days∈{3,5}` | 36 |
| B2-band | asym veto + band | `veto_band∈{0.0,0.005,0.01}` × `confirm_days∈{2,3,5}` × `reentry_days∈{3,5,10}` | 27 |

**110 cells total.** Cost model ACTIVE (asserted): Alpaca stocks, spread 2.0bps / fee 0.0bps (= 4bps round-trip, corrected ruler). All run through the EXISTING `walk_forward` evaluator over all 8 named regime windows; ranked by canonical **FP-continuous-span Sharpe** (clause a); robustness auto-classified.

---

## 4. Ranked sweep tables (FP-cont Sharpe primary)

### B1-vixy (20 cells) — TOP of the whole round
| rank | params | FP-cont Sharpe (a) | med-win Sharpe | worst DD% | ann/deployed% | RT | harness verdict | robustness |
|---|---|---|---|---|---|---|---|---|
| 1 | vixy_lookback=10 band=0.0 | **+0.87** | +1.28 | −1.12 | **+7.45** | 78 | PASS* | PLATEAU |
| 2 | vixy_lookback=10 band=0.05 | +0.54 | +0.72 | −1.74 | +4.22 | 28 | PASS* | PLATEAU |
| 3 | vixy_lookback=20 band=0.0 | +0.17 | +1.19 | −1.65 | +1.53 | 56 | PASS* | PLATEAU |
| 4 | vixy_lookback=100 band=0.0 | +0.09 | +0.87 | −2.00 | +0.84 | 21 | PASS* | PLATEAU |
| 5 | vixy_lookback=20 band=0.05 | +0.04 | +0.73 | −1.83 | +0.35 | 23 | PASS* | PLATEAU |
| 14 | vixy_lookback=100 band=0.05 | −0.19 | +0.87 | −2.03 | −1.72 | 10 | PASS* | PLATEAU |
| 16 | vixy_lookback=100 band=0.1 | −0.30 | +0.87 | −1.87 | −2.55 | 9 | PASS* | PLATEAU |
| 20 | vixy_lookback=20 band=0.1 | −0.89 | −0.44 | −1.69 | −6.78 | 13 | REJECT(a,fitness) | − |

`*` **HARNESS-VERDICT CAVEAT (important — see §10 friction note):** the harness `front_door_pass` = fitness gate + Bar A #1 + #5(b)-DD, and **does NOT include clause (a) FP-cont Sharpe ≥ 1.0.** A cell renders as "PASS" while its FP-cont Sharpe is well under 1.0 (the `reject_clauses` still carry `a`, rendered as `PASS(a)`). Under the TASK's front-door definition (FP-cont Sharpe ≥1.0 AND clears #5(b) AND beats BH risk-adjusted), **every B1 cell REJECTS on clause (a).** Top cell 0.87 < 1.0.

### B1-realized (18 cells)
Best: `vol_lookback=10 vol_sma=40 band=0.0` → FP-cont **+0.24**, ann +2.81%, 19 RT, PLATEAU. 2nd: same lookback band=0.10 → +0.05, PLATEAU. The other 16 cells collapse to a flat −0.03 / ann −0.47% / 8 RT (the self-referential RV threshold rarely fires at longer lookbacks → near-always-invested → ≈ BH). No cell ≥1.0.

### B1-proportional (9 cells)
Every cell FP-cont **−0.03**, ann −0.47%, 8 RT, no pass. The inverse-vol sizing as implemented rarely trims (single-symbol backtester has no clean partial-trim primitive; it degenerates to near-always-full-notional) → effectively ≈ BH minus a little churn. **Honest implementation limit, NOT a fair test of the literal Moreira-Muir construction — see §9.**

### B2 asymmetric credit veto (36 cells) — uniform failing basin
| rank | params | FP-cont Sharpe (a) | verdict |
|---|---|---|---|
| best | veto_lookback=40 confirm_days=3 reentry_lookback=120 reentry_days=5 | **−0.44** | REJECT(a,fitness) |
| … | (all 36 in [−1.06, −0.44]) | … | REJECT |
| worst | veto_lookback=40 confirm_days=2 reentry_lookback=90 reentry_days=5 | −1.06 | REJECT |

### B2-band (27 cells) — also uniform fail
FP-cont Sharpe span **[−1.56, −0.76]**, ann −7% to −16%/yr, every cell REJECT. Adding a dead-band made it WORSE (delays the veto deeper into the loss).

**Aggregate: 110 cells. Clause-(a) passes (FP-cont ≥1.0): 0. Front-door (task def) passes: 0. Errored: 0.**

---

## 5. Plateau / knife-edge classification

- **B1-vixy:** harness flagged **7 PLATEAUs**. The high-Sharpe corner (vixy_lookback=10, band∈{0,0.05}) is a GENUINE plateau, not a knife-edge — short-lookback VIXY-cross is robustly the best region, and Sharpe degrades *smoothly* as lookback lengthens or band widens. **The signal's best region is real and stable, it's just below the bar.** No knife-edges anywhere.
- **B1-realized:** 2 PLATEAUs (short-lookback corner), rest a flat basin.
- **B1-prop / B2 / B2-band:** **no passing cells → no plateau, no knife-edge.** Uniform failing basins (the *clean* kind of reject — nothing to overfit to).

---

## 6. Per-config vs BH-SPY (return AND Sharpe) — honesty / cash-mirage check

The crux for timing overlays. BH-SPY: FP-cont Sharpe −0.034, sum-ret −0.13%.

**B1 best cell (vixy_lookback=10, band=0):**
- FP-cont Sharpe **+0.87 vs BH −0.034** → improves risk-adjusted return by ~0.9 Sharpe. Real.
- ann return on deployed **+7.45%/yr** → it MAKES money, not just shrinks vol. **78 round-trips** = actively in/out, NOT parked in cash.
- worst-window DD −1.12% (tighter than BH's −1.99% 2022-H1).
- **Cash-mirage test: PASSES the smell test.** Not a denominator trick: earns +7.45%/yr with median-window Sharpe +1.28 while trading 78×. Sharpe comes from *timing* (dodging vol-spike drawdowns and re-entering), not from sitting in near-cash. The OPPOSITE of the Pattern #5 barbell.
- **BUT FP-cont Sharpe 0.87 < 1.0** (clause a) AND ann 7.45% < 8.0% (clause f). **Near-miss on TWO load-bearing bars — not a pass.**

**B1 realized / proportional:** ≈ BH or slightly worse. No mirage, no edge.

**B2 credit veto (all cells):** EVERY cell's FP-cont Sharpe is MORE negative than BH's −0.034, ann −4% to −16%/yr. The confirmed-veto fires LATE (by construction — waits `confirm_days`), so it sells AFTER the credit-stress drawdown has mostly happened, then the slow re-entry keeps it in cash through the recovery → books the loss and misses the bounce. The whipsaw is gone, replaced by **lag-cost**: same net bleed, different mechanism. Not a mirage, just bad.

---

## 7. FRONT-DOOR VERDICT (each family)

### B1 vol-regime — ❌ REJECT (clause a), but the strongest result on the board
- **Clause (a):** best FP-cont Sharpe **+0.87 < 1.0** in ALL 47 B1 cells. FAIL.
- **Clause (f):** best ann return **+7.45%/yr < 8.0%** floor. FAIL (by 0.55pp).
- **#5(b) DD:** passes (worst instr DD −1.12% to −2.3%, well under 30%).
- **Beats BH risk-adjusted:** ✅ YES, materially (+0.87 vs −0.034) — but beating a near-zero bench is necessary, not sufficient. The absolute bar is 1.0.
- **Plateau:** ✅ real (not a knife-edge). The 0.87 is trustworthy as a *measurement*.
- **Net:** an **honest, robust, sub-threshold result.** The first non-price signal in the tournament that is simultaneously positive-Sharpe + beats-BH + makes-real-money (+7.45%/yr) + robust-plateau + not-a-mirage. It just doesn't clear 1.0 / 8%. **REJECT, flagged LOUDLY as the most promising prior — see §9.**

### B2 asymmetric credit veto — ❌ REJECT (no edge, worse than BH)
- **Clause (a):** best FP-cont Sharpe **−0.44**, an order of magnitude under 1.0. FAIL in all 63 B2 cells.
- **Beats BH:** ❌ NO — every cell worse than BH's −0.034 on Sharpe AND return.
- **Plateau:** none (uniform failing basin).
- **Net:** the asymmetric decision shape did NOT rescue the credit signal. Round 1's symmetric cross failed via whipsaw [−1.51,−0.32]; the asymmetric veto fails via lag-cost [−1.56,−0.44]. **The credit (HYG/LQD) signal has no exploitable SPY-exposure-timing edge net of 4bps, in EITHER decision shape.** That closes the round-1 flagged fix. Honest, clean reject.

---

## 8. No-lookahead / survivorship / data notes

- **No lookahead (verified on disk):** for BOTH families the cross-asset/vol series (VIXY; HYG/LQD ratio) is fetched once over full history, then sliced to values dated ≤ the current SPY bar date. **Spot-check at as-of 2023-01-03:** VIXY visible-window max date == 2023-01-03 and next series date == 2023-01-04 (strictly future, excluded); HYG/LQD ratio identical (615 visible, last 2023-01-03, next 2023-01-04 excluded). Realized vol (B1) computed from `bars[:i+1]` only — the backtester's trailing slice. Fill at current SPY bar close (backtester contract). Signal at `t` uses only data ≤ `t`. ✅
- **Survivorship:** SPY/VIXY/HYG/LQD are single liquid ETFs present across the whole window — no basket, no survivorship bias.
- **Consistent start floor:** all four share the 2020-07-27 IEX first bar; 1469 daily bars each; complete overlap. Span 2020-07-27 → 2026-06-01. (Honors Pattern #4: every number here is over real-data span ≥ 2020-07-27.)
- **Cost ACTIVE:** 2bps one-way / 4bps round-trip (Alpaca stocks), asserted by the harness; no zero-cost path.

---

## 9. Should the vol-regime prior get more investment? — YES, the only one that earns it

**Recommendation: the vol-regime prior is the single non-price signal worth further investment, and the only one that has shown a real (sub-threshold) edge. Non-price exposure-timing on SPY is NOT exhausted — but the bar is the bar.**

1. **B1-vixy is the first thing in the whole non-price program that beat BH-SPY risk-adjusted on a ROBUST PLATEAU while making real money (+7.45%/yr, 78 round-trips, not a cash-mirage).** Every prior non-price result (credit round 1, all of B2, realized/proportional vol) was negative or a mirage. A +0.87 plateau Sharpe missing 1.0 by 0.13 is *categorically different* from a −0.4 uniform-fail basin. Signal, not noise.
2. **Two concrete next shapes that could push 0.87 → ≥1.0** (distinct strategies, OUT OF SCOPE here):
   - **(a) Cleaner implied-vol input.** VIXY has roll/decay drag that pollutes the level signal. A VIX *term-structure* proxy (contango-adjusted) would likely sharpen the regime read. The realized-vol variant underperformed VIXY here, so the implied-vol channel is the right one — just a noisy proxy.
   - **(b) Properly-implemented proportional sizing.** The proportional sweep degenerated to ≈BH because the single-symbol backtester has no clean partial-trim primitive — the implementation couldn't express continuous inverse-vol sizing (collapsed to near-always-full-notional). The LITERAL Moreira-Muir construction is the proportional one, and it was NOT fairly tested. A backtester with fractional sizing (or a 2-sleeve SPY/cash split via two symbols) is needed. **Highest-value next step** — the binary gate is a crude approximation of the real vol-managed construction that the paper showed works OOS.
3. **The credit signal (Family A) is now DONE.** Symmetric (round 1) + asymmetric (round 2) both reject. Two decision shapes, two failure mechanisms. Recommend a PATTERNS entry: HYG/LQD-as-daily-SPY-timer carries no tradeable edge net of cost on this span (credit-leads-equities is real macro, not daily-bar tradeable).
4. **Honest framing:** "vol-managed improves Sharpe OOS" is real in the literature, and we reproduced a directionally-correct, robust, positive version — but at 0.87, not the >1.0 the bench requires. Whether the gap is closable with a cleaner vol input + true proportional sizing is the open question. It's the best shot left. **One more round on B1 (cleaner vol input + fractional sizing) is justified; anything on credit is not.**

---

## 10. Harness 2nd/3rd real use — friction notes

110 cells across 5 grids, **zero crashes, no edits** — second and third real (non-test) uses both succeeded first-try on the single-symbol path.

- **FINDING (real ergonomic gap, NOT a code bug → no edit warranted):** the rendered **"PASS" verdict column does NOT incorporate clause (a) FP-cont Sharpe ≥ 1.0.** `_verdict()` sets `front_door_pass = fitness ∧ bar_a1 ∧ dd5b` and records `a` only as a *reject_clause* (rendered `PASS(a)`). So a cell with FP-cont Sharpe 0.17 renders "PASS" in bold while clause (a) — the load-bearing bar per the gate — is failing. This is easy to misread as a promotion. **This is BY DESIGN** (the harness separates the always-binding fitness/DD gate from clause (a), which the reader applies), and matches round 1's note (b), but with passing-looking cells present this round it's a sharper trap than round 1's all-REJECT basin. **Recommendation for a future harness pass (with a test): either rename the column to `gate-pass (ex-a)` or fold clause (a) into `front_door_pass` so the bold label can never overstate a sub-1.0 cell.** Not done here (out of scope; cosmetic, not a correctness bug — the FP-cont Sharpe number is printed correctly in its own column, and this memo applies clause (a) by hand).
- Single-symbol `walk_forward` path: clean. `SweepSpec(family="single", decide_fn=..., base_params=..., grid=...)` worked first-try for all 5 grids. `run_sweep` ranking by FP-cont Sharpe + `classify_robustness` (plateau/knife-edge) behaved exactly as in `test_sweep.py`.
- Implementation-limit (not harness): the single-symbol backtester has no fractional-trim primitive, so the proportional Moreira-Muir sizing couldn't be expressed faithfully (§9.2b). A future harness/backtester capability, not a bug.

---

## 11. Deliverables / confirmations

- **Memo:** `reports/NONPRICE_SIGNAL_R2_20260602T010535Z.md` (this file).
- **Candidate dirs (candidates ONLY — zero promotions):**
  - `strategies_candidates/vol_regime_spy_mm/` (strategy.py + params.json) — B1.
  - `strategies_candidates/credit_veto_spy_asym/` (strategy.py + params.json) — B2.
- **Driver (throwaway):** `reports/_nonprice_r2_driver.py`.
- **Tests:** full `pytest` → **262 passed** (baseline held; zero regressions).
- **Protected four (runner.py / risk.py / runner_xsec.py / backtest.py) UNTOUCHED.** Evaluators (walk_forward.py / walk_forward_xsec.py) import-only, UNTOUCHED. `git status` confirms no changes under any protected/evaluator file. **No edits to sweep.py / fp_sharpe.py** (no genuine bug found; the §10 verdict-label item is by-design cosmetic).
- **No promotion authority exercised. No live trading. Paper/backtest only.**

**FINAL VERDICT — BOTH REJECT.** B1 vol-regime: best FP-cont Sharpe +0.87 on a real plateau, beats BH-SPY, makes +7.45%/yr, not a cash-mirage — but misses the 1.0 bar (and the 8%/yr floor). The strongest, most promising non-price result so far; worth ONE more round (cleaner implied-vol input + true fractional sizing). B2 asymmetric credit veto: uniform failing basin [−1.56, −0.44], worse than BH everywhere — the credit-as-SPY-timer idea is now closed across both decision shapes.