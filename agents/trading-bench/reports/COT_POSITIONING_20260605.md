# COT-POSITIONING LANE — VERDICT REPORT

**Date:** 2026-06-05
**Lane:** Orthogonal-signal hunt, Tier-1 source #2 (CFTC COT / TFF)
**Verdict:** ❌ **REJECT** — best honest cell FP-cont-Sharpe **+0.930** < **1.0** gate (unchanged).
**Run log:** `reports/_cot_run_log_*.txt` · **Raw results:** `reports/_cot_positioning_results.json`
**Driver:** `reports/_cot_positioning_driver.py` (throwaway; composes PUBLIC `backtest_xsec` + `fp_sharpe` only)
**Cache module:** `runner/cot_cache.py` (keyed-public ingest, PIT release-gated) · **Tests:** `tests/test_cot_cache.py` (5/5 pass)

---

## What was tested

The hypothesis: **exogenous weekly speculator positioning extremes mean-revert.** Read CFTC
Commitments-of-Traders (TFF = Traders in Financial Futures) point-in-time, release-gated
(a Tuesday snapshot cannot inform a trade before its Friday public release, +3 days), forward-filled
onto the daily bar clock. Crowding measured as a z-score of net-OI by trader category:
- `lev_net_oi` — leveraged funds (hedge-fund/CTA proxy)
- `am_net_oi` — asset managers (real-money)
- `deal_net_oi` — dealer/intermediary

Markets: ES (→SPY), NQ (→QQQ), ZN (→rates). Deployment modes: single-name SPY timing
(binary + proportional ramp) and cross-asset rotation {SPY, IEF/GLD safe-asset}.
Both **contrarian** (fade extremes) and **momentum** (follow specs) directions swept.
Scored on the canonical 8-window `NAMED_WINDOWS` panel with the live Alpaca stock cost model.
**GATE unchanged at 1.0 FP-cont-Sharpe.** No protected/evaluator file touched (md5 verified).

## Result — REJECT

| Sweep family | Best FP | dep | beat-BH | trades | params |
|---|---|---|---|---|---|
| **spy_momentum_lev** | **+0.930** | 0.47 | **3/8** | 158 | lev_net_oi, momentum, z104, thr0 |
| spy_contrarian_deal | +0.869 | 0.62 | 1/8 | 65 | deal_net_oi, contrarian, z156, thr0 |
| xa_gld_contrarian_lev | +0.492 | 1.02 | 0/8 | 402 | GLD safe, lev contrarian, z156 |
| spy_contrarian_lev | +0.450 | 0.70 | 0/8 | 207 | lev_net_oi, contrarian, z156, thr0 |
| spy_contrarian_lev_prop | +0.423 | 0.61 | 0/8 | 695 | proportional ramp, band 1.0 |
| xa_ief_contrarian_lev | +0.307 | 1.01 | 0/8 | 396 | IEF safe |
| spy_contrarian_am | +0.260 | 0.36 | 0/8 | 138 | am_net_oi |

**Benchmark:** BH-SPY FP-cont = **+0.660** (8 trades; a ferocious bull-skewed panel — 2023-H1 +27%,
2024-Q2 +48%, 2025-Q3 +50%, 2026-recent +87%).

Nothing clears 1.0. The single best cell (+0.930) is **close but under**, and it beats buy-and-hold SPY in
only **3 of 8 windows**. Everything else is ≤ +0.87 and mostly **0/8 beat-BH**. This is a clean negative.

## Three honest reads (why this is a real finding, not a tuning failure)

1. **The signal partially re-encodes the volatility lane — it is NOT cleanly orthogonal.**
   Relabel diagnostic (the whole reason we left price/vol): leveraged-fund crowding-z vs SPY trailing
   realized vol is **corr = +0.45 (z156) / +0.53 (z104)**. That is *not* the <~0.3 orthogonality the hunt
   requires — leveraged-fund positioning leans on a vol-regime proxy in disguise. The cleaner categories
   (asset-manager corr +0.11, dealer +0.24 vs return) ARE more orthogonal, but their best cells are weaker
   (+0.26 am, +0.87 deal on only 65 trades). **Orthogonal-where-it's-clean is also weak-where-it's-clean.**

2. **The only thing near the gate is MOMENTUM on positioning, not the contrarian mean-reversion we hypothesized.**
   The top cell follows leveraged funds (trend), it doesn't fade them. The mean-reversion thesis the lane was
   built to test is *not* what produced the best number — and even the momentum read can't clear 1.0. The a-priori
   story is unconfirmed; we'd be reverse-fitting to keep it alive.

3. **Sampling + history are structurally thin for this signal.** Weekly prints forward-filled to a daily clock
   give ~55 independent observations per window in the relabel diagnostic. And the cached **TFF combined history
   starts 2010 — it does NOT cover the 2008 GFC** (the scout's "TFF→1986" applies to a different/legacy file
   family; the public `fut_fin` combined files reach 2010). So this lane sees 2020 + 2022 but is **2008-blind**,
   failing the decisive regime-robustness filter that ranked the orthogonal sources in the first place.

## What's kept vs. thrown away

- **KEEP (reusable infra, correctness-verified):**
  - `runner/cot_cache.py` — keyed PUBLIC CFTC ingest, disk-cached 2010→now, **PIT release-gated**
    (`released_asof` / `release_date_for`, +3d Tue→Fri lag), `CotLookaheadError` canary, built-in selftests.
  - `data_cache/cot/` — full TFF history cached (raw zips + `parsed_YYYY.json`, 2010-2026). No re-fetch needed
    if COT is ever revisited (e.g. a different contract, or a funded pre-2010 history source).
  - `tests/test_cot_cache.py` — 5/5 pass; locks the no-lookahead contract (snapshot 2024-06-11 → release
    2024-06-14, release ≤ as-of) and the documented 2008-gap honesty.
- **THROW AWAY:** the `cot_positioning` candidate as a promotable strategy. It is **quarantined in
  `strategies_candidates/` and stays there** — it does not go near live `strategies/`.

## Decision & next step

- **COT positioning: REJECTED at the 1.0 gate.** Logged as a clean negative. The relabel diagnostic earned its
  keep — it caught that "leveraged-fund crowding" is a vol proxy before we shipped it.
- This is the orthogonal-data-≠-edge caveat (MEMORY.md) landing in practice: the *data* was genuinely new and
  free; the *edge* wasn't there at our bar. **Gate stays at 1.0. We widen the data, we don't lower the bar.**
- **Next Tier-1 source per the synthesis build order: CBOE vol-index CSVs** (SKEW / VVIX / term-structure slope,
  1990/2006 — and unlike COT, no key needed and it *does* span 2008). FRED credit-spreads remains the #1 pick
  but is **still hard-blocked on a FRED API key** (`runner/fred_cache.py` foundation ready; fires the instant a
  key lands — fredgraph.csv fallback forbidden, it's bot-walled + serves stale data from this VM).
