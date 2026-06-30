# TOM LEVERAGE-CONCENTRATION OVERLAY — VERDICT

**Run:** 20260630T042440Z · **Agent:** trading-bench (research subagent) · **Mode:** paper-research only (no live wiring, no orders, no protected-file edits)
**Mission bar:** RAW RETURN vs buy-&-hold the index (Sharpe gate suspended but reported).

---

## VERDICT: **PROMOTE** (as an allocator OVERLAY, not a standalone strategy)

The Turn-of-Month (TOM) leverage-concentration **overlay** is a **real, replicable, statistically-supported calendar timing edge** — and it survives an honest, tradeable implementation. It beats buy-&-hold on raw return on **all four indices tested**, in **27 of 28** window-parameter cells, net of realistic financing, with the edge **degrading under the +1-bar canary on every variant** (proving it's timing, not just leverage). The genuinely tradeable form — rotate a slice of the book into a leveraged ETF (UPRO/SSO for S&P, TQQQ/QLD for Nasdaq) during the ~5-day TOM window — **preserves the edge** because the ETF's real, decay-and-fee-laden return is what we backtested.

The honest cost: leverage amplifies max drawdown (S&P FULL maxDD 55%→65%, Nasdaq 83%→89%). The edge is a **raw-return / total-return engine**, not a Sharpe improver in the leveraged form. Promote it as an **overlay an allocator applies on top of a long book**, sized to the drawdown the account can stomach — NOT as a standalone strategy and NOT at max tilt.

---

## 1. The construct (what's live vs what's dead)

- **DEAD (not pursued, confirmed by parent's `_tom_deephistory_probe.py`):** *flat-elsewhere* TOM — long only inside the TOM window, flat the rest of the month. Loses to B&H on raw return over 33yr because sitting out ~76% of days forfeits the equity premium (beta). Do not pursue.
- **LIVE (this verdict):** an **OVERLAY**. Base exposure = **1.0× the index every day** (never give up beta); during the TOM window add **extra exposure `tilt`**.
  - `exposure(day) = 1.0 + (tilt if in_TOM(day) else 0)`
  - TOM window = **last `pre` + first `post` trading days** of the month-turn. Pure function of the calendar date axis — **no price lookahead**. (`pre=2, post=3` is the base case; 5 trading days straddling the turn ≈ 23.8% of all days.)
  - Cost: **2 bps one-way** on every exposure change. Financing charged on the borrowed (>1.0) portion.

---

## 2. The mechanism is REAL (not a leverage artifact)

In-window days are **23.8% of all trading days** but deliver a hugely disproportionate share of cumulative return, and carry 2–4× the mean daily return of out-window days:

| Index | span | in-win mean/day | out-win mean/day | Welch t | in-win share of cum return |
|---|---|---|---|---|---|
| SPY | 33.4yr (1993+) | +0.0805% | +0.0373% | 1.47 | **40.3%** of cum (23.8% of days) |
| QQQ | 27.3yr (1999+) | +0.0969% | +0.0425% | 1.12 | **41.6%** |
| ^GSPC | **56.5yr (1970+)** | +0.0862% | +0.0212% | **3.11 (sig)** | **55.9%** |
| ^NDX | **40.7yr (1985+)** | +0.1371% | +0.0460% | **2.38 (sig)** | **48.2%** |

**On the two longest, deepest samples the mean-difference t-stat is statistically significant (3.11, 2.38).** Longer history → stronger signal, which is the correct direction for a genuine effect (the shorter ETF-era SPY/QQQ samples are noisier at t≈1.1–1.5 but point the same way). This resolves the 2026-06-04 seasonality REJECT's explicit data-depth caveat — that test had ~5.8yr; this has up to 56yr.

**The skeptic's distinction — timing edge vs "more leverage = more return":**
- **Canary (the direct test): PASS on every single variant.** Shifting the TOM mask +1 trading day (tilt on the WRONG days) **degrades** Sharpe everywhere — S&P margin@5% OOS 0.837→0.784, ^GSPC 0.746→0.683, Nasdaq 0.933→0.886, and all ETF variants (e.g. UPRO 0.787→0.728, TQQQ 0.962→0.913). A pure-leverage artifact would be **indifferent** to a 1-day shift. The degradation proves the advantage is attached to the *specific calendar days*, not to leverage per se.
- **Tilt-Sharpe profile:** on ^GSPC, Sharpe **rises then holds** as tilt goes 0→1.0→1.5 (0.538→0.572→0.570) instead of monotonically falling. Adding exposure on TOM days improves risk-adjusted return because those days have a better return/vol profile than the average day. Pure leverage on average-quality days would only dilute Sharpe.

---

## 3. Does it replicate across indices? — YES

The TOM-overlay raw-return edge is **not SPY-specific**. FULL-sample explicit-margin overlay (tilt=1.0, financing 5%/yr) vs B&H:

| Index | B&H FULL cum | Overlay FULL cum @5% fin | B&H maxDD | Overlay maxDD |
|---|---|---|---|---|
| SPY (33.4yr) | +2,973% | **+5,824%** | 55.2% | 65.4% |
| QQQ (27.3yr) | +1,583% | **+2,442%** | 83.0% | 88.7% |
| ^GSPC (56.5yr) | +7,900% | **+32,464%** | 56.8% | 67.9% |
| ^NDX (40.7yr) | +26,451% | **+139,856%** | 82.9% | 89.0% |

Beats B&H on raw return on **all four**. Window-param robustness: across cells (1,1),(2,2),(2,3),(3,3),(1,4),(4,1),(3,5) the overlay BEATs B&H in **27 of 28** (sole loss: QQQ at an over-wide 38%-of-days window). Not a cherry-picked cell.

---

## 4. Break-even financing — the edge is hard to kill with margin cost

The financing APY at which the FULL overlay's cumulative return falls back to B&H:

| Index | break-even financing |
|---|---|
| SPY | **13.3%/yr** |
| QQQ | **11.4%/yr** |
| ^GSPC | **15.5%/yr** |
| ^NDX | **22.2%/yr** |

Realistic financing on the borrowed slice is **~3–7%/yr** (broker margin / box-spread / embedded-ETF borrow). The edge does not die until **11–22%/yr** — a 2–4× margin of safety over any plausible rate. At the realistic 5%/yr the OOS (≥2013) overlay still beats B&H on raw return on every index (SPY +733% vs +555%, QQQ +1,718% vs +1,143%, ^GSPC +544% vs +422%, ^NDX +1,518% vs +1,019%), and the second cut (OOS ≥2018) confirms it (SPY +308% vs +216%, etc.). **Robust to the split date.**

---

## 5. The TRADEABLE form: leveraged-ETF tilt (no explicit margin) — edge PRESERVED

Instead of borrowing on margin, hold the 1× index normally and during the TOM window **rotate a slice `w` of the book from the 1× index into a k× ETF**: net TOM exposure = `1 + w·(k−1)`. To target +1.0× extra: `w=1.0` into a 2× ETF, or `w=0.5` into a 3× ETF. **We backtested the ETF's REAL adjclose return — its volatility decay, ~0.9% expense ratio, and embedded financing are already in the numbers.** No idealized leverage.

| Index | ETF | span | B&H 1× (sub) | ETF-tilt overlay | OOS≥2013 B&H | OOS≥2013 ETF | canary |
|---|---|---|---|---|---|---|---|
| SPY | **UPRO (3×), w=0.5** | 17.0yr (2009+) | +708%* | **+1,167%** | +422%* | **+631%** | PASS (0.787→0.728) |
| SPY | SSO (2×), w=1.0 | 20.0yr (2006+) | +756% | +1,008% | +555% | +792% | PASS (0.611→0.551) |
| QQQ | **TQQQ (3×), w=0.5** | 16.4yr (2010+) | +1,812% | **+3,592%** | +1,143% | **+1,901%** | PASS (0.962→0.913) |
| QQQ | QLD (2×), w=1.0 | 20.0yr (2006+) | +2,089% | +3,330% | +1,143% | +1,837% | PASS (0.761→0.714) |

*\*UPRO sub-window B&H is on the ^GSPC index leg; SPY-row UPRO numbers come from the ^GSPC harness block (UPRO tracks the S&P).*

**The ETF implementation actually does slightly BETTER than the explicit-margin@5% version** on every index (e.g. QQQ TQQQ +3,592% vs margin@5% +3,184% on the same window) — because a 3× ETF's embedded financing on a short 5-day hold is cheaper than 5%/yr retail margin, and the volatility decay over such a brief window is minimal. **This is the actually-tradeable construct on the paper account, and it preserves (indeed marginally improves on) the edge.** Canary passes on all four ETF variants.

**Decay caveat (honest):** leveraged-ETF decay scales with holding period and realized vol. A 5-day TOM hold is short enough that decay is negligible *in backtest*; if the window were widened or vol regimes shifted, decay would bite more. The 3×-at-w=0.5 form is preferable to 2×-at-w=1.0: same target exposure, less ETF notional turning over, and the data shows it edges ahead.

---

## 6. The honest cost: DRAWDOWN

Leverage amplifies max drawdown. This is the real price of the raw-return gain:

- **S&P:** B&H maxDD ~55% → overlay ~65–68% (FULL). OOS-only maxDD barely moves (33.7%→34.0%) — the DD amplification is concentrated in the brutal IS bears (2000–02, 2008).
- **Nasdaq:** B&H maxDD ~83% → overlay ~89% (FULL). At tilt=2.0 the Nasdaq overlay hits **94% maxDD** — unholdable. **Do not run high tilt on Nasdaq.**
- The leveraged-ETF form has the *same* DD profile as margin (the ETF IS leverage), so this cost is intrinsic to the construct, not the implementation.

**Implication:** this is a **raw-return / total-return engine**, not a Sharpe improver in leveraged form (FULL Sharpe is roughly flat-to-slightly-down vs B&H because DD scales with return). It belongs in a **sleeve sized to a drawdown budget**, not as a max-leverage standalone.

---

## 7. Recommendation (concrete, tradeable)

**PROMOTE as an allocator OVERLAY**, not a standalone strategy:

1. **Form:** hold the long book (SPY/QQQ or the existing 1× engine) normally. During the **TOM window (pre=2, post=3 trading days)**, rotate a slice of the book into a **leveraged ETF** to add extra exposure, then rotate back out.
2. **Instrument:** **UPRO (3×) for S&P, TQQQ (3×) for Nasdaq**, at **w ≈ 0.5 × tilt** (3×-at-w=0.5 beats 2×-at-w=1.0 in the data and turns over less notional). Start conservative: **tilt = 0.5** (w≈0.25 into the 3× ETF) to cap the DD amplification while still capturing most of the edge — the tilt sweep shows the bulk of the Sharpe-friendly return arrives by tilt≈1.0 and DD climbs steeply past it.
3. **Window:** pre=2/post=3 is the robust default; (3,3) and (2,2) also work. Avoid windows wider than ~30% of days.
4. **Sizing to drawdown budget:** at tilt=1.0 expect FULL maxDD ~65% (S&P) / ~89% (Nasdaq). Size tilt down to fit the account's DD tolerance. **Nasdaq tilt should stay ≤1.0.**
5. **Standalone vs overlay:** **OVERLAY.** It needs the 1× base to keep beta; on its own (flat-elsewhere) it's the dead version. Parent should wire it as a tilt the allocator applies on top of an existing long sleeve.

A candidate scaffold is dropped at `strategies_candidates/tom_overlay/` (strategy.py + params.json + NOTES.md) — **NOT wired live; parent reviews/merges.**

### What would make me downgrade this
- If real fills on the TOM-day rotation cost materially more than 2 bps (open-auction slippage on the ETF) — but 5 rotations/month into liquid UPRO/TQQQ is cheap.
- If the effect is decaying out-of-sample post-2018: the OOS≥2018 cut still beats B&H on all indices, so no evidence of decay yet — but worth a live-paper watch.
- It is a **leverage-amplified beta-timing** edge, not an alpha that's market-neutral. In a secular bear it will lose money faster than B&H on the down-leg even while still beating B&H cumulatively across a full cycle.

---

## 8. Reproducibility & integrity

**Harness:** `reports/_tom_overlay_harness.py` (library) + `reports/_tom_overlay_run.py` (driver) + `reports/_tom_mechanism.py` (in/out-window mechanism + window/tilt sweeps). All compile clean; raw outputs saved to `reports/_tom_overlay_raw_output.txt` and `reports/_tom_mechanism_output.txt`. Data via `runner/daily_bars_cache.py` (Yahoo v8 adjclose, READ-only).

**Protected-file md5s — UNCHANGED (verified start and end of run):**
```
0f763975f2d8ba535352f6a8306afb8b  runner/runner.py
e303317e0d2ac796a1fa43e372f0a113  runner/risk.py
717c36e68941b9258f86bc99950de788  runner/backtest.py
d8927364605e9253d54284bd4068c874  runner/backtest_xsec.py
8c3df32c2bc64ddbe079464d30c7e217  runner/walk_forward_xsec.py
bccefabab4403b4226ff5caa4c8db3b8  runner/safety_backstop.py
```
No crontab, no .db, no orders touched. Writes confined to `reports/` and `strategies_candidates/`.

---

### Bottom line for the parent
The TOM overlay is **the real thing among the leads**: a calendar timing edge with a mechanistic explanation (in-window days = 24% of days but ~40–56% of return), statistically significant on deep history (t=3.1 / 2.4 on ^GSPC / ^NDX), replicating across 4 indices, surviving honest financing (break-even 11–22%/yr vs ~5% real), surviving the canary on every variant, and **tradeable today** via UPRO/TQQQ rotation that preserves the edge. The catch is drawdown amplification — so it ships as a **drawdown-budgeted overlay sleeve**, not a max-leverage standalone. **PROMOTE.**
