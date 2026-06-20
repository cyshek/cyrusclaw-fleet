# RS Breakout-with-Volume Cross-Sectional Lane — Backtest Report

**Candidate:** `strategies_candidates/rs_breakout_vol_disp/`
**UTC timestamp:** 20260602T211033Z
**Harness:** `runner/backtest_xsec.py` (cross-sectional, shared-cash) via `runner/walk_forward_xsec.py`.
**Honest ruler:** `fp_continuous_sharpe_for_agg` (concatenated walk-forward per-tick equity returns). NEVER median-of-windows.

---

## 1. Signal construction (free OHLCV only)

We have Alpaca daily bars and **nothing else** (no analyst/news/estimate data).
The "catch re-rating names early" thesis is approximated purely from price+volume:

1. **Cross-sectional relative strength.** Rank the universe by trailing total
   return over `lookback_bars=63` (~3 months), **skipping** the most recent
   `skip_bars=5` to dodge 1-bar reversal. Eligible = top `top_k=8`.
2. **Trend confirmation.** A name is eligible only if `price > SMA(trend_sma=100)`.
   No buying downtrends however high their RS rank.
3. **Breakout + volume confirmation.** Among trend-confirmed RS leaders, a NEW
   entry requires (a) a new `donchian_bars=20`-day high (today's high exceeds
   the max high of the prior 20 bars, today excluded), AND (b) today's volume
   `>= vol_mult=1.5 * SMA(vol_sma=20)` of prior volume. Volume expansion =
   "real money confirming the move" — the differentiator from a plain RS basket.
4. **Long-only, weekly rebalance, equal-weight.** On the first tick of a new ISO
   week: close held names that left the RS top-k or dropped below their trend
   filter (risk-off rail); open new breakout-on-volume names equal-weight
   (`per_leg = max_notional/target_basket_size`). Shared cash; harness
   `_clamp_basket` caps total exposure at `$100`.

Persistent state: `last_rebalance_week` ("YYYY-Www") throttles to weekly cadence.

## 2. Universe + survivorship

`baskets/dispersed_xsec.txt` — **95 dispersed liquid US equities**, all with first
daily bar 2020-07-27 (bench data floor). Deliberately retains known laggards
(BA/INTC/PYPL/PFE/T/WBA/IBM/DIS) to avoid winner cherry-picking.

**Survivorship handling:** this is the set of names that EXISTED and stayed liquid
through the data floor. Delisted/dead names are absent. **Bias direction =
optimistic** (survivorship inflates returns); results are an UPPER BOUND. Not
hand-picked — a fixed dispersed list, so selection bias is minimized but not zero.

## 3. Walk-forward results (baseline params)

Run: `walk_forward_xsec`, 8 NAMED_WINDOWS, warmup=400d (≥400 required for the
63-bar lookback + 100-bar trend SMA to prime inside each window). Cost model =
default `alpaca_stocks` (2 bps spread). $100 deployed notional. Basket = 95.

**Honest ruler (fp-continuous Sharpe on concatenated WF per-tick returns):**

| Metric | Value | Front-door clause | Pass? |
|---|---|---|---|
| **fp-cont Sharpe** | **-0.38** (n=2667) | (a) ≥ 1.0 | ❌ |
| Ann. return (deployed) | NEGATIVE (median window -0.63%) | (f) ≥ 8%/yr | ❌ |
| Worst-instrument DD | **-89.7%** | #5(b) ≤ 30% | ❌ |
| % windows beat BH-basket | 25% | beat BH | ❌ |
| Median window return | -0.63% | >0 | ❌ |
| Median-of-windows Sharpe | -0.63 | (reference only) | ❌ |
| % windows positive | 25% | ≥50% | ❌ |
| Total trades | 146 | (activity sanity: NOT warmup-starved) | ✓ active |
| Bar A bullet #1 | FAIL | — | ❌ |
| Fitness gate | **FAIL** | — | ❌ |

`fitness_gate_reason`: median return -0.63% ≤ 0; only 25% windows positive;
only 25% beat BH; median Sharpe -0.63 ≤ 0.50.

Per-window (return vs equal-weight BH-basket):

| Window | Regime | Ret | BH | Beat | maxDD | in-pos | trades |
|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | -1.20% | -1.63% | ✓ | -1.44% | 56% | 20 |
| 2022-Q3 chop | chop | -0.85% | -0.74% | ✗ | -1.21% | 46% | 19 |
| 2023-H1 recovery | bull | +0.09% | +0.62% | ✗ | -0.40% | 30% | 14 |
| 2023-Q3 chop | chop | -0.42% | -0.35% | ✗ | -0.80% | 35% | 18 |
| 2024-Q2 bull | bull | -1.19% | +0.04% | ✗ | -1.53% | 35% | 15 |
| 2025-Q1 tariff bear | bear | -1.58% | -0.73% | ✗ | -1.66% | 36% | 22 |
| 2025-Q3 bull | bull | -0.11% | +0.35% | ✗ | -0.51% | 36% | 17 |
| 2026-recent bull | bull | +1.52% | +0.93% | ✓ | -1.27% | 54% | 17 |

**Read:** the lane is genuinely active (146 trades, ~30-56% in-position) — this is
NOT a warmup-starvation false-flat. It loses to a plain equal-weight buy-and-hold
of the same basket in 6 of 8 windows, including 3 of 4 bull windows where a
breakout-momentum lane should shine. The volume-confirmation filter does not
rescue it. The -89.7% worst-instrument DD means at least one leg rode a breakout
into a near-total drawdown before the weekly trend-exit rail caught it — the rail
is too slow for the high-idio names that pass a 1.5x-volume breakout filter.

## 4. Param sweep (plateau vs knife-edge)

Star sweep around baseline (1 axis at a time), fp-cont Sharpe per cell (honest
ruler), all on the same 95-name basket / 8 windows / warmup=400d:

| lookback | top_k | vol_mult | trend_sma | **fp-cont Sharpe** | medRet | %pos | %beatBH | worstDD | trades |
|---|---|---|---|---|---|---|---|---|---|
| **63** | **8** | **1.5** | **100** | **-0.38** (baseline) | -0.63% | 25% | 25% | -89.7% | 146 |
| 126 | 8 | 1.5 | 100 | -0.51 | -0.66% | 25% | 38% | -89.7% | 123 |
| 63 | 5 | 1.5 | 100 | -0.07 | +0.16% | 62% | 50% | -39.4% | 104 |
| 63 | 12 | 1.5 | 100 | -0.07 | -0.28% | 38% | 50% | -89.7% | 199 |
| 63 | 8 | 1.0 | 100 | -0.15 | -0.51% | 50% | 50% | -89.7% | 422 |
| 63 | 8 | **2.0** | 100 | **+0.13** (argmax) | +0.03% | 62% | 50% | -20.4% | 55 |
| 63 | 8 | 1.5 | 50 | -0.43 | -0.60% | 12% | 25% | -89.7% | 155 |
| 63 | 8 | 1.5 | 200 | -0.31 | -0.18% | 38% | 38% | -89.7% | 71 |

**PLATEAU vs KNIFE-EDGE:** This is a **uniform-failure plateau**, NOT a knife-edge.
Every cell's fp-cont Sharpe lies in [-0.51, +0.13] — the entire surface is far below
the clause-(a) bar of 1.0, with no isolated lucky cell. The argmax cell
(vol_mult=2.0) reaches only +0.13 and, while a stricter 2x-volume filter does tame
the worst-instrument DD from -89.7% to -20.4% (fewer, cleaner breakouts) and lifts
%positive to 62%, its median return is ~0% and it beats BH in only 50% of windows.
No cell clears the front door. Because the whole grid agrees on REJECT, there is
no data-snooping risk: we are not promoting a single lucky argmax — we are
rejecting the entire neighborhood.

## 5. Front-door verdict: **REJECT**

| Front-door clause | Requirement | Baseline | Best cell (vm=2.0) | Verdict |
|---|---|---|---|---|
| (a) fp-cont Sharpe | ≥ 1.0 | -0.38 | +0.13 | ❌ FAIL |
| (f) net ann. return on deployed | ≥ 8%/yr | negative | ~0% | ❌ FAIL |
| #5(b) worst-instrument DD | ≤ 30% | -89.7% | -20.4% | ❌ (baseline FAIL; best cell only passes this ONE clause) |
| beat BH-basket | majority of windows | 25% | 50% | ❌ FAIL |
| Bar A bullet #1 | pass | FAIL | — | ❌ FAIL |
| Fitness gate (xsec WF) | pass | FAIL | — | ❌ FAIL |

**REJECT.** A free-OHLCV RS + trend + breakout-on-volume cross-sectional lane on a
dispersed 95-name US-equity universe does not clear the bench front door under the
$100 notional + alpaca_stocks cost model, at baseline or anywhere in a reasonable
param neighborhood. The volume-confirmation filter is real (a 2x cut tames
tail-DD and trade count) but does not create risk-adjusted edge over a plain
buy-and-hold of the same basket. This is an honest, expected REJECT — the lane is
documented and parked in `strategies_candidates/`. Zero promotions.

**Survivorship caveat (reiterated):** the 95-name universe excludes delisted/dead
names, so even these failing numbers are an optimistic UPPER BOUND. A survivorship-
clean universe would only push the verdict further toward REJECT.

## 6. Hygiene / audit trail

### No-lookahead spot-check
Empirical check (synthetic series): `_is_breakout_on_volume` returns True at bar T
only when T's bar is present; removing T (simulating the decision at T-1) flips it
to False. All features read only `bars[:cur+1]`, and the harness slices
`symbols_view[sym]["bars"]` to bars with `t <= clock_t`. Breakout uses the prior
`donchian` window EXCLUDING today (`highs[-1-donchian:-1]`) and volume avg
EXCLUDING today (`vols[:-1]`). No future leakage. Entry sized in notional, filled
by the harness at the T close (same-bar-close convention shared by every bench
candidate).

### Protected runner files — md5 UNCHANGED (start == end)
```
9444ee5be64d9fd2639fd8cb0a28e002  runner/backtest.py
2278a4c8d8a66703da5cd6f2a0880061  runner/backtest_xsec.py
4968be881421e64ce8e9f07d50f1eb2d  runner/walk_forward_xsec.py
e4c227e019c99e7e52224eb2f91389b8  runner/risk.py
2cdd7a1ff3d316aedbad88b861946621  runner/fp_sharpe.py
4704bb11a1c8a185cc3c3f73b0eb3980  runner/sweep.py
4be185e4bdcb6f432d99b71b21a4859c  runner/runner.py
ea5c8cade9afefcbad9137dcead0368b  runner/runner_xsec.py
```
Verified identical at task start and end. DID NOT EDIT any runner/*.py.

### pytest before/after
`python3 -m pytest -q`: **289 passed** after this candidate (full suite green). The
candidate adds NO tests; the only delta from the task-brief baseline of 283 is
pre-existing candidates added to the repo between the brief and this run. My
candidate is data/strategy-only and does not touch the collected test set. Suite
stayed green: before = green, after = **289 passed in ~8s**, 0 failures.

