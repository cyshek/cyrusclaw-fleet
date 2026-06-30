# TOM OVERLAY — PRODUCTION HARNESS & GO/NO-GO

**Run:** 20260630T050146Z · **Agent:** trading-bench · **Mode:** paper-research only (no live wiring, no orders, no protected-file edits, no crontab/.db touched)
**Mission bar:** RAW RETURN vs buy-&-hold the index. Sharpe reported, gate suspended.
**Purpose:** Give Cyrus a clean, reproducible go/no-go on the **recommended shelf config** (not the tilt=1.0 stress numbers in the verdict). This is the doc to sign off.

---

## TL;DR — GO (paper), at the conservative shelf config

The Turn-of-Month (TOM) leverage-concentration **overlay** at the **recommended shelf config (window pre=2/post=3, tilt=0.5, rotate into a 3× ETF)** beats buy-&-hold on **raw return across all four indices**, in both OOS cuts, with the **+1-bar canary passing on every variant** — and in the tradeable 3× form it costs **only +0.1 to +0.7pp of max drawdown**. At this conservative tilt the OOS Sharpe is **essentially at parity with B&H** (you get the raw-return lift for a near-zero risk-adjusted give-up). This is a clean, honest, tradeable edge.

**Recommendation:** GO for **paper** as a drawdown-budgeted allocator overlay. **Use the 3× ETF form (UPRO for S&P, TQQQ for Nasdaq) at w=0.25**, NOT the 2× form. Do **not** auto-wire — this is Cyrus's call because it adds leverage to the roster. **Real money remains a separate, explicit decision** gated on a paper-forward track record.

---

## The shelf config (exactly what ships if greenlit)

```
Base exposure : 1.0x the index every day (keep beta — never go flat)
TOM window    : last 2 + first 3 trading days of each month-turn
                (pure calendar date mask, NO price lookahead; ~23.8% of days)
Tilt          : +0.5 EXTRA index exposure during the window (conservative start)
Tradeable form: rotate w = tilt/(k-1) of the book into a kx ETF during TOM, back out after
                tilt=0.5 -> w=0.25 into a 3x ETF (UPRO / TQQQ)   <-- USE THIS
                        -> w=0.50 into a 2x ETF (SSO / QLD)       (worse DD, do not use)
Cost          : 2 bps one-way on every rotation (5 round-trips/month into liquid ETFs)
Rebalance     : ~5 calendar rotations per month
```

---

## 1. Cross-index results at the shelf config (tilt=0.5)

### Tradeable 3× ETF form (the actual product) — REAL ETF adjclose: decay + fees + embedded financing baked in

| Index | ETF (w) | span | B&H 1× cum | **ETF-tilt cum** | B&H maxDD | **ETF-tilt maxDD** | DD cost | canary |
|---|---|---|---|---|---|---|---|---|
| S&P | UPRO 3× (0.25) | 17.0yr (2009+) | +989% | **+1,266%** | 33.7% | **33.8%** | **+0.1pp** | PASS 0.894→0.858 |
| S&P (deep) | UPRO 3× (0.25) | 17.0yr on ^GSPC | +708% | **+926%** | 33.9% | **34.0%** | **+0.1pp** | PASS 0.804→0.770 |
| Nasdaq | TQQQ 3× (0.25) | 16.4yr (2010+) | +1,812% | **+2,609%** | 35.1% | **35.9%** | **+0.7pp** | PASS 0.982→0.954 |
| Nasdaq (deep) | TQQQ 3× (0.25) | 16.4yr on ^NDX | +1,577% | **+2,287%** | 35.6% | **36.2%** | **+0.6pp** | PASS 0.943→0.917 |

**Every index beats B&H raw, with near-zero drawdown cost, canary passes on all.** This is the central result.

### Why the 3× form, not the 2×: same target exposure, far less drawdown

For the identical +0.5 target exposure, the 3×-at-w=0.25 form turns over a quarter of the book; the 2×-at-w=0.5 turns over half. The DD cost difference is stark:

| Index | 3× form DD cost | 2× form DD cost |
|---|---|---|
| S&P (UPRO vs SSO) | **+0.1pp** | +5.4pp |
| S&P deep (UPRO vs SSO) | **+0.1pp** | +4.6pp |
| Nasdaq (TQQQ vs QLD) | **+0.7pp** | +6.0pp |
| Nasdaq deep (TQQQ vs QLD) | **+0.6pp** | +5.8pp |

The 3× form is unambiguously the right instrument. (Both still beat B&H raw and pass the canary; the 2× just pays much more DD for the same edge.)

### OOS robustness at the shelf config (3× form)

| Index | ETF | OOS≥2013 B&H cum / Sharpe | **OOS≥2013 ETF cum / Sharpe** | OOS≥2018 B&H | **OOS≥2018 ETF** |
|---|---|---|---|---|---|
| S&P | UPRO | +555% / 0.914 | **+677% / 0.899** | +216% / 0.805 | **+268% / 0.822** |
| Nasdaq | TQQQ | +1,143% / 1.002 | **+1,503% / 0.993** | +391% / 0.907 | **+503% / 0.921** |

Beats B&H raw in **both** OOS cuts on **both** indices. **Sharpe is at parity** (within ~0.01) — at tilt=0.5 the raw-return lift is nearly free in risk-adjusted terms, unlike tilt=1.0 which gave up more Sharpe. No evidence of post-2018 decay.

---

## 2. The drawdown cost is explicit (tilt ladder)

The whole point of the conservative tilt is to cap drawdown amplification. Explicit-margin@5% reference ladder (clean apples-to-apples; the ETF form's actual DD is the table in §1):

| Index | B&H (tilt 0) maxDD | tilt=0.25 | **tilt=0.50 (SHELF)** | tilt=1.00 (verdict stress) |
|---|---|---|---|---|
| S&P | 55.2% | 57.8% | **60.4%** | 65.4% |
| Nasdaq | 83.0% | 84.4% | **85.8%** | 88.7% |
| S&P deep (^GSPC) | 56.8% | 59.7% | **62.5%** | 67.9% |
| Nasdaq deep (^NDX) | 82.9% | 84.4% | **85.9%** | 89.0% |

Two notes:
- The explicit-margin reference looks worse on DD than the ETF form because it amplifies the full IS-bear path (2000–02, 2008); the **tradeable ETF form's actual DD cost is the +0.1–0.7pp in §1**, because the leveraged slice is only on 5 days/month and the OOS bears (post-2009) are shallower. Both are reported for honesty.
- **Nasdaq B&H is already an 83% peak-to-trough instrument.** Even +1.5pp is on top of an already-brutal number. Size accordingly; tilt stays ≤1.0 on Nasdaq, and 0.5 is the right start.

---

## 3. Mechanism — real, not a leverage artifact (from the verdict, re-confirmed)

In-window days are 23.8% of all days but carry 2–4× the mean daily return and deliver 40–56% of cumulative return:

| Index | span | in-win mean/day | out-win mean/day | Welch t | in-win share of cum |
|---|---|---|---|---|---|
| SPY | 33.4yr | +0.0805% | +0.0373% | 1.47 (weak) | 40.3% |
| QQQ | 27.3yr | +0.0969% | +0.0425% | 1.12 (weak) | 41.6% |
| ^GSPC | **56.5yr** | +0.0862% | +0.0212% | **3.11 (sig)** | 55.9% |
| ^NDX | **40.7yr** | +0.1371% | +0.0460% | **2.38 (sig)** | 48.2% |

**Canary is the decisive test and it PASSES everywhere** — shifting the TOM mask +1 day (tilt on the WRONG days) degrades Sharpe on every single variant at the shelf tilt (S&P UPRO 0.894→0.858, Nasdaq TQQQ 0.982→0.954, and all others). A pure-leverage artifact would be indifferent to a 1-day shift. The degradation proves the edge is attached to the specific calendar days.

---

## 4. Honest caveats (read before signing)

1. **Modern-era statistical strength is thin.** The in/out-window mean gap is only weakly significant on the modern liquid ETFs (SPY t=1.47, QQQ t=1.12). It clears significance only on the 40–56yr index series (^GSPC 3.11, ^NDX 2.38). The effect is real and points the same direction on all samples, but the modern ETF-era edge leans partly on leverage, not a robustly-significant modern in-window premium. **This is why we start at tilt=0.5 and watch it in paper, not tilt=1.0.**
2. **It is leverage-amplified beta-timing, not market-neutral alpha.** In a secular bear it loses money faster than B&H on the down-leg, even while beating B&H cumulatively across a full cycle. It does not hedge; it concentrates exposure.
3. **Drawdown is the intrinsic cost.** The ETF form's +0.1–0.7pp is small *because the OOS sample (post-2009) had no 2000/2008-class bear*. A future deep bear during a TOM window would amplify DD more than the OOS numbers suggest. The tilt ladder (§2) is the honest worst-case framing.
4. **Live-fill risk.** Numbers assume 2 bps per rotation. Real open-auction slippage on the TOM-day rotation could be higher; 5 rotations/month into liquid UPRO/TQQQ should be cheap, but this is the first thing to verify in paper.

### What would flip this to NO-GO / downgrade
- Real paper fills cost materially more than 2 bps per rotation.
- Post-2018 OOS starts decaying in live paper (no evidence yet — both cuts still beat B&H).
- The Sharpe gate gets reinstated as a hard bar: in leveraged form this is a raw-return engine, ~parity Sharpe at tilt=0.5 and below-B&H at tilt=1.0. It would need a DD cap to clear a strict risk-adjusted bar.

---

## 5. Decision

- **GO for paper** as a drawdown-budgeted allocator overlay. Recommended: **3× ETF form (UPRO/TQQQ) at w=0.25, window pre=2/post=3, tilt=0.5.** This captures the raw-return edge at near-zero DD cost and ~parity Sharpe.
- **Do NOT auto-wire.** Adding leverage to the live roster is Cyrus's call. Candidate scaffold is staged at `strategies_candidates/tom_overlay/` (NOT live).
- **Real money is a separate, explicit decision**, gated on a paper-forward track record (live-fill confirmation + no OOS decay).
- **If Nasdaq is included:** keep tilt ≤1.0; start at 0.5. It sits on top of an already-83% instrument.

---

## 6. Reproducibility & integrity

**Harness (all compile clean; numbers regenerate exactly):**
- `reports/_tom_overlay_harness.py` — verified library (load, TOM mask, stats/maxDD, overlay_margin, overlay_etf, canary). Same primitives the verdict used.
- `reports/_tom_production_harness.py` — **this report's driver** (shelf config tilt=0.5, tilt ladder, ETF forms, OOS×2, canary). Run: `python3 -m reports._tom_production_harness`.
- `reports/_tom_overlay_run.py` — full verdict driver (tilt=1.0 stress + financing sweep + break-even).
- `reports/_tom_mechanism.py` — in/out-window mechanism, window-param + tilt sweeps, Welch t.
- Raw output: `reports/_tom_production_raw_output.txt`.
- Data: `runner/daily_bars_cache.py` (Yahoo v8 adjclose, READ-only).

**Protected-file md5s — UNCHANGED (verified this run):**
```
0f763975f2d8ba535352f6a8306afb8b  runner/runner.py
e303317e0d2ac796a1fa43e372f0a113  runner/risk.py
717c36e68941b9258f86bc99950de788  runner/backtest.py
d8927364605e9253d54284bd4068c874  runner/backtest_xsec.py
8c3df32c2bc64ddbe079464d30c7e217  runner/walk_forward_xsec.py
bccefabab4403b4226ff5caa4c8db3b8  runner/safety_backstop.py
```
No orders, no crontab, no .db. Writes confined to `reports/`.

---

### Bottom line for Cyrus
TOM overlay at the conservative shelf config is a **GO for paper**: beats buy-&-hold on raw return across all 4 indices and both OOS cuts, passes the canary everywhere, and in the tradeable 3× ETF form (UPRO/TQQQ at w=0.25) costs only **+0.1–0.7pp of max drawdown** for the gain — with Sharpe essentially at parity. The catch is it's leverage-amplified beta-timing (thin modern-era significance, no hedge value, DD cost understated by a benign OOS sample), so it ships at tilt=0.5 with a paper-forward watch, **not** auto-wired and **not** with real money until the paper track record confirms the fills. **Your sign-off needed to wire it to paper.**
