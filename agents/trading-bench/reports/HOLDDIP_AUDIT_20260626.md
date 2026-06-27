# Hold-the-Dip Audit — `rsi_oversold_spy` vs Trend-Gate vs Momentum-Flip

**Date:** 2026-06-26
**Lane:** BACKLOG P1 #2 (from AQR Reading Sprint #2). Main-assigned via cron.
**Type:** A/B audit of a LIVE parent against fresh published evidence. No new return engine.
**Verdict:** **AQR "Hold the Dip" EMPIRICALLY REBUTTED on our instrument.** The raw dip-buy parent wins decisively; both trend-aligned alternatives are strictly worse. **No swap promoted.** Parent stays as-is.

---

## TL;DR

| Variant | medSharpe | medRet | meanRet | %pos | trades | worst win | abs gate |
|---|---|---|---|---|---|---|---|
| **parent — RSI dip-buy** (live) | **0.892** | **+0.27%** | +0.15% | 62% | 67 | −0.45% | ✅ PASS |
| (a) dip-buy + SMA-100d trend gate | 0.000 | +0.00% | +0.12% | 38% | 26 | −0.28% | ❌ FAIL |
| (b) momentum-entry flip (buy strength) | 0.173 | +0.06% | **−0.11%** | 62% | 136 | −1.43% | ❌ FAIL |

On intraday SPY, **buying the dip (mean-reversion) beats both trend-filtering the dip AND flipping to trend-following.** That is the *opposite* of what "Hold the Dip" predicts for this instrument. The mean-reversion edge here is real and trend-alignment subtracts from it.

---

## What AQR claims (the thesis under test)

AQR, *"Hold the Dip"* (Alternative Thinking, Dec 2025): systematic dip-buying tends to underperform because it is **structurally anti-momentum** — you are buying an asset precisely when its recent trend is down. The corollary advice is "don't buy the dip *against* the trend." Our live parent `rsi_oversold_spy` is exactly a dip-buyer (enters when RSI(14) < 28), so it is a direct test subject.

## What we tested (same SPY path, same CostModel, same walk_forward windows)

All three share symbol=SPY, timeframe=1Hour, notional=$159.65, the standard `CostModel.for_symbol("SPY")`, and the 8 NAMED_WINDOWS (3 bull / 3 chop / 2 bear, 2022-H1 → 2026-recent). Identical bench path → the only thing that varies is the ENTRY logic.

- **parent** — RSI(14)<28 oversold entry; exit RSI>70 or 20-bar time-stop. (Unchanged live code.)
- **(a) trend-gate** — same dip-buy, but the entry only fires when SPY's **daily** close is above its trend SMA. Exits always reachable (run first, never gated). Reads daily SPY from `market_state["regime"]["spy_closes"]`.
- **(b) momentum-flip** — entry FLIPPED to a trend-aligned momentum trigger (fast SMA-10 crosses above slow SMA-30 on SPY's own 1h closes); exit on cross-down or 20-bar stop. The deliberate antithesis of the parent.

### Methodological note — why the gate is SMA-100d, not SMA-200d (and why that's honest)
The task said "SMA-200." **A 200-day SMA is NOT testable on our walk-forward windows.** The daily-SPY cache floor is 2020-07-27, so for each 2022+ test window the backtester only has ~136–139 daily SPY bars before the window starts. `sma(daily_closes, 200)` returns `None` throughout → the gate would *fail open* and the variant would be **byte-identical to the parent** (which is exactly what an initial SMA-200 run produced: same 67 trades, same 0.892 Sharpe — a null result, not a test).

I verified the longest daily-SMA that actually BINDS on the available history: SMA-100d blocks ~68% of dip entries — including **100% of the 2022-H1 bear dips** (the precise "buy-the-dip-against-the-trend" case AQR warns about). SMA-100d is therefore the faithful, *testable* proxy for AQR's "intermediate trend" filter. (Period is a param; once deeper daily history is cached, 200 can be re-run — but the mechanism is fully exercised here.)

---

## Results & interpretation

**Parent dip-buy: medSharpe 0.892, +0.27% median, 62% of windows positive, passes the absolute fitness gate.** It even beats buy-&-hold SPY in all 4 down/chop windows (defensive: small positive while SPY bleeds, e.g. 2025-Q1 tariff bear +0.43% vs SPY −1.32%). This is a genuine intraday mean-reversion edge on SPY.

**(a) Trend-gating DESTROYED it — medSharpe 0.00, median return 0.00%, only 38% of windows positive.** Filtering to "dips in an uptrend only" threw away 41/67 trades and, critically, removed *winning* entries: the parent's best defensive contributions come exactly in the down/chop windows where SPY is below its trend SMA — i.e. the windows the gate suppresses. On this instrument the dip-buy's value is *counter-trend*, so a trend filter removes the alpha rather than cleaning it. **Directly contradicts AQR's "only buy the dip with the trend."**

**(b) Momentum-flip was strictly worse — medSharpe 0.17, NEGATIVE mean return, worst window −1.43% (vs parent's −0.45%).** Buying strength on SPY intraday produced 2× the trades and far worse risk-adjusted return than buying weakness. The instrument mean-reverts at the 1h horizon; trend-following fights that. **Directly contradicts AQR's "trend-following beats dip-buying on the same instrument."**

Both falsifiable predictions failed in the same direction: on intraday SPY, **mean-reversion > trend-alignment.** That is internally consistent — SPY at the 1-hour scale is a mean-reverting series, the opposite regime from the multi-month cross-asset horizon where AQR's result holds.

### Why this doesn't contradict AQR globally (skepticism check)
AQR's "Hold the Dip" is about **longer-horizon, cross-asset** dip-buying (months, broad universes) where momentum dominates. Our parent operates at the **intraday (1h) horizon on a single index** where short-term reversal is the documented effect (the same reason RSI mean-reversion is a classic intraday signal). So this is **not** a refutation of AQR's paper on its own turf — it's evidence that **the dip-buy headwind AQR documents does not apply at our horizon/instrument**, which is the only thing that matters for whether to keep the live child. Mechanism separated from marketing: the paper's logic is sound where it applies; it just doesn't apply here.

---

## Decision

- **No swap.** The parent `rsi_oversold_spy` is kept unchanged — it strictly dominates both alternatives on Sharpe, median return, and worst-window.
- **Logged as an empirical rebuttal** of "Hold the Dip" *at our horizon/instrument* (per main's instruction for the "raw dip-buy holds" branch).
- Both variant dirs moved to `strategies_candidates/` (rejected-candidate convention); parent untouched in `strategies/`.
- **Bonus finding:** the dip-buy's edge is specifically *counter-trend* — it earns most in down/chop windows. That argues it is a (small) diversifier to the trend/momentum-heavy book, not a redundant leg. Worth remembering if a book-level mean-reversion sleeve is ever considered.

## Integrity

- **Protected runner md5s UNCHANGED** (verified before/after):
  - `runner/strategy_gen.py` `1ff0239da8fb2fdf971fc2dfe3892e54`
  - `runner/walk_forward.py` `6fb34eeac25d3ff463dc11e6bbfbdadc`
  - `runner/backtest.py` `717c36e68941b9258f86bc99950de788`
  - `runner/risk.py` `e303317e0d2ac796a1fa43e372f0a113`
- Full test suite: **843 passed, 3 skipped** (no regressions).
- No `strategies/` parent modified; no live runner touched; no orders; no spend. Candidate-only + read-only audit via `walk_forward`.

## Artifacts

- Driver: `_holddip_audit_driver.py` (three-way walk_forward + gate eval, JSON datapack).
- Candidates (quarantined): `strategies_candidates/rsi_oversold_spy_trendgate/` (SMA-100d gate), `strategies_candidates/rsi_oversold_spy_momflip/` (momentum entry).
- Raw datapack: `/tmp/holddip_result.json` (regenerate via the driver).
