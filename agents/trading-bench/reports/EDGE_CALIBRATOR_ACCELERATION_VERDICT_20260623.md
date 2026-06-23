# edge_calibrator — Acceleration Feasibility & Trip-Count Integrity Verdict

**Date:** 2026-06-23 (~5:45 PM PT)
**Author:** Tessera
**Trigger:** Main's management check — "is there a low-cost way to synthetically accelerate the calibrator from 19/30 trips to 30 without corrupting the calibration?"
**Verdict:** ❌ **NO — do not synthetically accelerate. Let it accrue from live fills.** A real, separate integrity bug surfaced (counter pollution) — documented below for a parent-owned fix (it touches a production runner module, outside candidate-only scope).

---

## TL;DR

1. **Synthetic acceleration is fraud, not a shortcut.** The 30-trip gate measures *realized P&L of actual paper fills*. The training label is literally `y = 1 if trip_pnl > 0 else 0`. Manufacturing trips = inventing fake P&L outcomes = training the model on labels that never happened. There is no "feed historical bars into the counter" path that isn't exactly this.
2. **Even if we hit 30 today, the model would be degenerate.** Of the 19 counted round-trips, only **11 are from the live-12 book — and all 11 are WINS (zero losses).** A logistic regression on a perfectly-separable, one-class target diverges / memorizes; it would be worse than the current honest pass-through. The gate is doing its job.
3. **The genuinely actionable finding:** the trip counter (and the eventual training set) is **polluted by 8 non-book trips** — `backstop_test` (synthetic −$120 harness), `any`/`bp2` (test scaffolding), and dead crypto legs (`sma_crossover_btc`). When the gate opens, the model will train partly on garbage labels. **Recommend a universe filter** (train only on the live tournament roster). This is the real improvement, and it makes the *honest* path to 30 even further out — which is correct.

---

## What the calibrator actually is (so "accelerate" can be evaluated honestly)

`runner/edge_calibrator.py`:
- Collects **completed round-trips** by FIFO-matching buy/sell fills in `tournament.db` (`_fifo_match_global`).
- Trains a logistic regression: `P(win | features)`, where **features** = `[n_trips, win_rate, avg_hold_bars(placeholder 1.0), kelly_raw, recent_vs_all_winrate]` and **label** = `1 if trip_pnl > 0 else 0` (`extract_training_rows`).
- Calibration multiplier applied to Kelly sizing = `clip(2*P(win) − 1, 0, 1)`.
- **Gate:** `MIN_ROUND_TRIPS_TOTAL = 30` across ALL strategies before it trains; secondary guard `n_samples < 10 → pass-through`. Until then it's a pass-through (multiplier = 1.0, i.e. no effect). Auto-activates at 30 — no manual flip.

The counter is therefore **a count of real money-outcomes**, not a count of bars or signals. That framing is the whole answer to the acceleration question.

---

## Sub-question 1: "Feed historical bars manually into the counter?"

**No — three reasons, in increasing severity:**

### (a) It would be fabricating P&L labels
A trip only exists when a real buy fill is FIFO-matched to a real sell fill, and its `pnl` is the realized difference. "Feeding historical bars" to manufacture trips means writing synthetic fills into `tournament.db` with made-up prices → made-up `pnl` → made-up win/loss labels. The model would then calibrate live position sizing on outcomes that never occurred. This is the single most direct way to poison a calibration layer. **Hard no** (violates the SOUL "honest measurement" rail).

### (b) A backfill from backtests is a different distribution than live fills
Even a "principled" backfill (replay each strategy's backtest, log its historical round-trips) trains the model on **backtest** execution (idealized fills, no live slippage, no partial-fill/timing reality) and then applies the learned sizing to **live paper** execution. The calibrator's entire value proposition is "learn which of *my live strategies'* trips tend to win" — backtest trips are a covariate-shifted population. You'd ship a confident-but-miscalibrated multiplier. Marginally less fraudulent than (a), still wrong.

### (c) The real-book labels are currently one-class → degenerate fit
This is the empirical kicker. Live-12 completed trips as of 2026-06-23:

| Strategy | Trips | Wins | Losses | PnL |
|---|--:|--:|--:|--:|
| breakout_xlk__mut_c382b1 | 2 | 2 | 0 | +44.04 |
| breakout_xlk_regime | 2 | 2 | 0 | +4.67 |
| breakout_xlk | 2 | 2 | 0 | +4.56 |
| sma_crossover_qqq | 2 | 2 | 0 | +3.86 |
| sma_crossover_qqq_regime | 2 | 2 | 0 | +3.81 |
| sma_crossover_qqq_rth | 1 | 1 | 0 | +0.67 |
| **Live-12 total** | **11** | **11** | **0** | **+61.61** |

**Every completed live-book trip is a win.** `P(win|features)` on a one-class target is not estimable — the fit either diverges (separable data, `C=10` barely regularizes) or collapses to "always 1.0", i.e. multiplier pinned at `clip(2·1−1,0,1)=1.0` (no calibration) or worse, overconfident on noise. Hitting "30 trips" by any means while the real book is all-wins produces a model that has learned nothing real. **The honest fix is time + at least some losing trips, not volume.**

---

## Sub-question implied: "If not, document why and move on." — Done. But one real bug found.

### 🐛 The trip counter is polluted by non-book trips

`train_calibrator` and `_fifo_match_global` count **every strategy present in `tournament.db`** — no roster filter. Of the 19 counted trips, **8 are not the live equity book:**

| Non-book strategy | Trips | What it is |
|---|--:|---|
| sma_crossover_btc | 4 | dead crypto lane (closed) |
| backstop_test | 2 | **synthetic test harness** (deliberate −$120, exercises the risk backstop) |
| any | 2 | test scaffolding |

Consequences:
- **The 19/30 is overstated as a measure of book-calibration readiness** — only 11 are real. (Saturday leaderboard already says "30 lands ~Jul 4–11"; this makes it *later*, because the real-book trip rate is what should drive the gate.)
- **When the gate opens at 30, the model trains on garbage labels:** `backstop_test`'s synthetic −$120 losses and crypto noise become training rows. A −$120 synthetic loss with `n_trips/win_rate` features will yank the logistic weights. The calibrator meant to size *live equity* strategies would be partly fit on a test harness.

### Recommendation (parent-owned — touches a production module, outside my candidate-only scope)
Add a **strategy-universe filter** to the calibrator so it counts/trains on the live tournament roster only (exclude `backstop_test`, `any`, `bp2`, and closed crypto lanes). Two clean options:
- **(preferred)** pass the live roster (same 12 the crontab feeds `cron_tick.sh`) into `train_calibrator(..., universe=set(...))` and filter in both `_fifo_match_global`-for-count and `extract_training_rows`.
- **(simpler)** a module-level `EXCLUDE_STRATEGIES = {"backstop_test","any","bp2"}` + an `is_crypto`/closed-lane skip.
Either way: **gate on live-book trips, train on live-book trips.** I did **not** implement this — `edge_calibrator.py` is production runner code; flagging to main per scope rules.

---

## Disposition

- **Synthetic acceleration:** rejected (fraud / degenerate fit). The calibrator is correctly parked in pass-through. **No action — let live fills accrue.**
- **Honest ETA to a *meaningful* calibration:** further out than the raw "30 trips" suggests. We need (a) ≥30 *live-book* trips and (b) a non-trivial number of losing trips so the label isn't one-class. At the current real-book rate (~5 trips/wk, all from the crossover/breakout strats — the big sleeves are long-only accumulators with 0 closed trips), that's weeks away, and a one-class target could push it further. **This is fine.** A calibrator that refuses to train on insufficient/degenerate data is behaving exactly as designed.
- **Counter-pollution bug:** documented for main. Real, low-risk fix, but it's a production-module change → parent's call.

**Bottom line for main:** there is no honest shortcut to 30, and we wouldn't want one — the real book is currently all-wins, so a forced fit would be meaningless. The useful output of this dig is the counter-pollution finding (19 counted, only 11 real-book, and the eventual training set includes `backstop_test`'s synthetic losses). Recommend a universe filter when you want to spend a production-module change on it.
