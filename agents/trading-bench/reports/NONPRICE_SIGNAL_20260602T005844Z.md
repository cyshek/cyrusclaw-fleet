# NON-PRICE SIGNAL CLASS — Family A (Cross-asset / credit-spread risk-regime timing)

**UTC:** 2026-06-02T00:58:44Z
**Author:** trading-bench subagent (non-price signal-class sweep, Step 3)
**Harness:** FIRST REAL USE of `runner/sweep.py` + `runner/fp_sharpe.py` (single-symbol path)
**Verdict:** ❌ **HONEST REJECT — uniform failing basin, no edge, strictly worse than BH-SPY.**

---

## 1. Which family chosen + why

Picked **Family A — cross-asset / risk-regime timing**, the lead pick: it is the
least-arbitraged-by-retail of the three feedable families, and PATTERNS #6
explicitly demands a **different signal INPUT** (not price-cross-sectional) after
closing the price-xsec lane on 4 honest rejects.

Within A, chose the **credit-spread risk-on/off** sub-idea (option A.1): the
**HYG/LQD ratio** — high-yield vs investment-grade corporate credit — as an
INTERMARKET regime gauge timing SPY exposure. Rationale: credit markets are
widely held to lead equities at turning points ("credit smells stress first"),
and the HY/IG ratio is a genuinely different input than SPY's own price. Traded
instrument is SPY (long/flat); the **novelty is the signal source**, exactly the
shape the task specifies.

## 2. Signal construction (no lookahead, no survivorship)

All from CLOSES only (no intra-bar peek):

```
ratio_t   = HYG_close_t / LQD_close_t                 # credit risk gauge
sma_t     = SMA(ratio, signal_lookback)               # trend reference
risk_on   = ratio_t > sma_t * (1 + band_pct)          # HY leading IG  -> hold SPY
risk_off  = ratio_t < sma_t * (1 - band_pct)          # HY lagging IG  -> de-risk to cash
```
Decision: flat+risk_on → BUY SPY; long+risk_off → CLOSE to cash; else HOLD.
`band_pct` is a hysteresis dead-band to damp whipsaw around the SMA.

- **No-lookahead (verified on disk):** the HYG/LQD ratio series is fetched once
  over full history (1469 daily bars, 2020-07-27→2026-06-01), then at each SPY
  bar we slice to ratios whose date ≤ the current SPY bar date. Spot-checked: at
  as-of 2023-01-03 the visible window's max date == 2023-01-03 and the next
  ratio date is 2023-01-04 (strictly future, excluded). Signal at `t` uses only
  data ≤ `t`; fill is at the current SPY bar close (backtester contract).
- **Survivorship:** HYG, LQD, SPY are all single liquid ETFs present across the
  whole window — no basket, no survivorship bias.
- **Data floor:** consistent across instruments (all three ETFs share the
  2020-07-27 IEX first bar; the ~5.5yr overlap is complete).

## 3. Sweep grid (24 cells, single-symbol path)

```
signal_lookback : [20, 40, 60, 90, 120, 200]   (trading days)
band_pct        : [0.0, 0.003, 0.006, 0.01]
```
Cartesian product = 24 cells. Cost model **ACTIVE** (asserted): Alpaca stocks,
spread 2.0 bps / fee 0.0 bps (= 4 bps round-trip, the corrected ruler). Run
through the EXISTING `walk_forward` evaluator over all 8 named regime windows;
ranked by canonical **FP-continuous-span Sharpe** (clause a); robustness
auto-classified.

## 4. Benchmark: buy-and-hold SPY across the SAME concatenated span

| metric | BH-SPY |
|---|---|
| FP-cont Sharpe (full concatenated span) | **−0.042** |
| sum-of-window return (scaled) | −1.29% |

Per-window BH-SPY: 2022-H1 −17.4%, 2022-Q3 −6.5%, 2023-H1 +7.5%, 2023-Q3 −3.8%,
2024-Q2 +4.8%, 2025-Q1 tariff −8.0%, 2025-Q3 +6.5%, 2026-recent +15.6%. The named
panel is deliberately bear-heavy, so BH-SPY's *concatenated-span* Sharpe is near
zero — **but a timing overlay must still beat that −0.04 to be worth anything,
and ideally beat it materially.**

## 5. Ranked sweep table (FP-cont Sharpe primary) — TOP + BOTTOM

| rank | params | FP-cont Sharpe (a) | med-win Sharpe | worst DD% | ann/deployed% | round-trips | verdict | robustness |
|---|---|---|---|---|---|---|---|---|
| 1 | lookback=20 band=0.003 | **−0.32** | −0.36 | −1.56 | −3.05 | 26 | REJECT(a,fitness) | — |
| 2 | lookback=40 band=0.0 | −0.37 | −0.38 | −1.69 | −3.36 | 43 | REJECT(a,fitness) | — |
| 3 | lookback=40 band=0.003 | −0.43 | −0.18 | −1.75 | −3.78 | 20 | REJECT(a,fitness) | — |
| 4 | lookback=20 band=0.0 | −0.51 | −0.53 | −1.67 | −5.07 | 65 | REJECT(a,fitness) | — |
| … | … | … | … | … | … | … | … | … |
| 23 | lookback=60 band=0.006 | −1.47 | −1.12 | −1.86 | −14.29 | 15 | REJECT(a,fitness) | — |
| 24 | lookback=90 band=0.01 | **−1.51** | −1.71 | −1.96 | −15.93 | 13 | REJECT(a,fitness) | — |

**Summary:** 24 cells · front-door pass **0** · PLATEAU **0** · KNIFE-EDGE **0** ·
errored **0**. FP-cont Sharpe spans **[−1.51, −0.32]** — every cell deeply
negative, an order of magnitude under the 1.0 bar.

## 6. Plateau / knife-edge classification

**No passing cell → no plateau, no knife-edge.** This is the *good* kind of
reject: a **uniform failing basin**, not an isolated knife-edge ridge. The whole
(lookback × band) neighborhood agrees the signal has no edge — there is no
parameter corner to be tempted by, and nothing to overfit to.

## 7. Per-config vs BH-SPY (return AND Sharpe) — the honesty check

| comparison | FP-cont Sharpe | sum-window return% |
|---|---|---|
| **BH-SPY** | **−0.042** | **−1.29%** |
| best timer cell (lookback=20 band=0.003) | −0.32 | −0.81% |
| worst timer cell (lookback=90 band=0.01) | −1.51 | −3.78% |

- **Sharpe:** EVERY timer cell is MORE negative than BH-SPY's −0.04. The overlay
  *degrades* risk-adjusted return in every configuration.
- **Return:** every cell loses money on deployed capital (−3% to −16%/yr);
  several cells beat BH's *return* slightly (e.g. −0.81% vs −1.29%) **only by
  sitting in cash and dodging a couple of the bear windows** — but they do so
  with WORSE Sharpe, i.e. the classic **cash-sitting Sharpe mirage in reverse**:
  the timer cuts a little drawdown but its whipsaw losses overwhelm the benefit.
  This is NOT edge — it is a lower-exposure proxy that also pays churn cost.
- The signal *does* fire correctly in one spot (2025-Q1 tariff bear: timer
  +0.67% vs BH −0.80%), but bleeds from whipsaw in chop/recovery windows
  (2022-Q3, 2023-H1, 2023-Q3 all negative while it churns 1–8 trades per window).

## 8. FRONT-DOOR VERDICT

❌ **REJECT.** Fails clause (a) FP-cont Sharpe ≥ 1.0 in ALL 24 cells (best −0.32),
fails the fitness gate in all cells, and **does not beat BH-SPY risk-adjusted in
any cell** (every cell's Sharpe < BH's −0.04). No #5 fast-track relevance
(clause (a) and (f) both fail hard). Honest reject — as the task notes, a clean
result either way.

**What this tells the tournament:** the credit-spread (HYG/LQD) intermarket
timer, as a long/flat SPY overlay on daily bars over this 5.5yr window, carries
**no exploitable edge net of 4 bps**. The de-risk signal is real but too noisy
and too lagged to overcome whipsaw cost; it does not improve Sharpe or
materially cut drawdown vs simply holding SPY. This is one data point on whether
the *cross-asset* signal class is worth more investment (see §10).

## 9. Harness's-first-real-use notes (API friction)

The sweep harness worked **first-try with zero friction** on the single-symbol
path — this was its first real (non-test) use and it required **no edits and no
bug fixes**. Specifically:
- `SweepSpec(family="single", decide_fn=..., base_params=..., grid=...)` +
  `run_sweep(spec, verbose=True)` ran all 24 cells through the existing
  `walk_forward` evaluator cleanly.
- The cost-active assert fired as designed (I never tried zero-cost).
- `classify_robustness` correctly reported 0 plateaus / 0 knife-edges on a
  uniformly-failing basin.
- `report.to_markdown()` rendered the ranked table + "ROBUST PLATEAUS: none"
  banner correctly.
- **Minor ergonomics (not bugs, not fixed):** (a) the single-symbol path's
  `ann_return_on_deployed_pct` uses `total_return_usd` summed across windows /
  deployed — correct, but for a long/flat SPY overlay the per-config *sum-window
  return vs BH* comparison I most wanted is not a built-in column, so I computed
  it in the driver. A future "vs-BH-same-span" column would help overlay
  strategies. (b) `bar_a1_pass` is hard-coded True for single-symbol (Bar A #1 is
  xsec-specific) — correct by design, just worth remembering when reading the
  verdict column. Neither warranted a harness edit.

No protected files touched; `sweep.py`/`fp_sharpe.py` left unchanged (no genuine
bug surfaced, so no edit + no new test needed).

## 10. Should the cross-asset signal class get more investment?

Mixed signal, leaning **measured**. The HYG/LQD *direction* was correct in the
one window where credit genuinely led (2025 tariff bear), which is weak evidence
the intermarket relationship carries *some* information. But as a standalone
daily long/flat timer it is dominated by whipsaw. If the lane is revisited, the
higher-probability shapes are: (a) using credit as a **risk-OFF-only veto**
(only de-risk on a *strong, persistent* credit-deterioration signal, never
whipsaw-toggle) rather than a symmetric on/off gate; or (b) a **slower
confirmation** (multi-week persistence requirement) to kill the churn. Those are
distinct strategies, not parameter tweaks of this one — out of scope here. The
*symmetric SMA-cross* construction tested is dead.

## 11. Data / lookahead / survivorship notes

- **No lookahead** (verified on disk, §2): signal at `t` uses only cross-asset
  closes dated ≤ `t`; fill at current SPY bar close.
- **No survivorship bias:** three single liquid ETFs (HYG/LQD/SPY), all present
  across the full window.
- **Consistent start floor:** all three share the 2020-07-27 IEX first bar; 1469
  daily bars each; complete overlap.
- **Cost ACTIVE:** 2 bps one-way / 4 bps round-trip (Alpaca stocks), asserted by
  the harness; no zero-cost path.

## 12. Bookkeeping

- **Test count:** full suite **262 passed** (baseline preserved; no regressions).
- **Candidate dir written:** `strategies_candidates/credit_regime_spy_hyglqd/`
  (`strategy.py`, `params.json`, `__init__.py`) — candidate ONLY, **ZERO
  promotions** to `strategies/`.
- **Sweep driver:** `reports/_credit_regime_sweep_driver.py` (throwaway analysis
  script, harness public-API only).
- **Protected files UNTOUCHED:** `runner/runner.py`, `runner/risk.py`,
  `runner/runner_xsec.py`, `runner/backtest.py` unchanged; evaluators
  `walk_forward.py` / `walk_forward_xsec.py` import-only; `sweep.py` /
  `fp_sharpe.py` unchanged (no bug found). Confirmed.

**Family run: A (cross-asset / credit-spread, HYG/LQD timer). Verdict: HONEST
REJECT, uniform failing basin, strictly worse than BH-SPY on Sharpe AND no
material drawdown benefit.**
