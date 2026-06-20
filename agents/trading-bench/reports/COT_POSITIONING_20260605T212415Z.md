# COT Positioning — Orthogonal-Signal Lane Verdict (Tier-1 free-data source #2)

**Date:** 2026-06-05 (UTC 20260605T212415Z)
**Lane:** CFTC Commitments of Traders (COT), Traders in Financial Futures (TFF)
**Status:** ⛔ **REJECT** — best cell FP-cont-Sharpe **+0.930 < 1.0 gate**
**Author:** Tessera (built inline after two subagents were killed mid-run by gateway restarts)

---

## TL;DR

The classic contrarian-positioning thesis (speculators crowded long → forward
underperformance) **did not clear the bar**, and in fact the *contrarian*
direction was the weak one (best contrarian-lev FP ≈ +0.45). The only cells with
real signal were the **opposite** read — leveraged-fund positioning *momentum*
(chase the crowd) at **FP +0.930**, and dealer-net contrarian at **FP +0.869** —
both still **under the 1.0 gate**. COT positioning is **partially orthogonal**
to price (low correlation to trailing *return*, but a meaningful link to
realized *vol*). Net: a legitimate, expected REJECT. There is *some* information
here, but it tops out in the same ~0.5–0.9 band every price/vol lane hits — it
does not break the ceiling on its own.

This is a real answer, not a failure: it rules COT-positioning-alone out as a
graduation candidate, and quantifies *why* (signal ceiling, not a cost or
plumbing artifact).

---

## Data provenance

- **Source:** public-domain CFTC COT TFF "combined" annual history files
  (`fut_fin_txt_<YEAR>.zip` → `FinFutYY.txt`), ingested + disk-cached under
  `data_cache/cot/` by `runner/cot_cache.py`. No API key, no spend.
- **History span:** **2010 → 2026** (all years cached).
- **Contracts matched** (exact `Market_and_Exchange_Names`, auditable via
  `cot_cache.matched_contract_names`):
  - **ES → SPY:** `E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE`,
    `E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE`
  - **NQ → QQQ:** `NASDAQ MINI - …`, `NASDAQ-100 STOCK INDEX (MINI) - …`
  - **ZN → 10y:** `10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE`,
    `UST 10Y NOTE - CHICAGO BOARD OF TRADE`
- **⚠️ 2008-GFC GAP (must-flag):** TFF financial-futures reporting begins **2010**.
  This lane is **blind to the 2008 crisis**. The graduation regime-robustness
  criterion wants ≥2 distinct bears; here we only have **2020 (COVID)** and
  **2022 (rate shock)**. Even had this passed, it could not graduate on regime
  coverage without splicing the older legacy/disaggregated format (different
  trader categories — deferred).

## Point-in-time / lookahead convention (the make-or-break)

- COT snapshots **Tuesday**, publishes the following **Friday** (~3 calendar-day
  lag; `RELEASE_LAG_DAYS = 3`, forced to the Friday of the snapshot week).
- The **only** trading accessor is `cot_cache.released_asof(market, date)`:
  returns the most recent report whose **RELEASE date ≤ query date**. A
  `CotLookaheadError` canary fires on any violation. The trailing z-score window
  is built from `released_history`, which contains only already-released reports.
  The weekly value is forward-filled onto the daily bar clock between releases.
- **Worked example (verified):** snapshot **Tue 2025-12-30** →
  `release_date_for` → **Fri 2026-01-02**. A query for 2025-03-15 returns the
  2025-03-11 snapshot released 2025-03-14 (Fri ≤ query). Proven in
  `tests/test_cot_cache.py` (a snapshot is NOT visible on its own snapshot date,
  becomes visible exactly on its release date).

## Signal construction

Raw per-market features (point-in-time, weekly, forward-filled):
- `lev_net_oi` = (Lev_Money long − short) / OpenInterest — **leveraged funds**
  (hedge-fund speculators); the primary driver.
- `am_net_oi` = Asset_Mgr net / OI — slow institutional side.
- `deal_net_oi` = Dealer net / OI — swap/intermediary ("smart-money hedge") side.
- **Crowding z-score:** standardize the current released value against its own
  trailing `z_weeks` (104 or 156 ≈ 2–3yr) released history.
- **Position rule:** `direction=contrarian` (deploy when washed-out, flat when
  crowded) or `momentum` (chase); `exposure_mode` binary or proportional;
  `mode` spy_timing (SPY long/flat) or cross_asset (rotate SPY↔IEF/GLD).

## Result vs the 1.0 gate

Scored with PUBLIC `fp_continuous_sharpe` over the canonical 8-window
`NAMED_WINDOWS` regime panel, Alpaca stock cost model. Buy-hold SPY bench on the
same panel = **FP +0.660**.

| Sweep family | Best FP | Trades | Beats BH | Notes |
|---|---|---|---|---|
| spy **momentum** lev (z104, thr0) | **+0.930** | 158 | 3/8 | **best overall**, still < 1.0 |
| spy contrarian **deal** (z156, thr0) | +0.869 | 65 | 1/8 | low trade count |
| spy momentum lev (z156, thr0) | +0.508 | 189 | 0/8 | |
| xa **GLD** contrarian lev (z156) | +0.492 | 402 | 0/8 | |
| spy contrarian lev (z156, thr0) | +0.450 | 207 | 0/8 | the *classic* thesis — weak |
| spy contrarian am (z104, thr0) | +0.260 | 138 | 0/8 | |
| xa IEF contrarian lev (z156) | +0.307 | 396 | 0/8 | |

**Best cell:** `mode=spy_timing, market=ES, feature=lev_net_oi,
direction=momentum, exposure_mode=binary, z_weeks=104, thr_z=0.0` →
**FP +0.930**, 158 trades, avg deploy 0.47, worst-instrument DD −16.3%.
**Verdict: REJECT (0.930 < 1.0).**

## Relabel diagnostic — is it actually orthogonal?

Correlation of the COT crowding-z series vs SPY trailing return / realized vol
(n ≈ 55 dense-grid points):

| Feature | corr vs SPY **return** | corr vs SPY **vol** |
|---|---|---|
| lev_net_oi z156 | −0.205 | **+0.451** |
| lev_net_oi z104 | −0.354 | **+0.528** |
| am_net_oi z156 | +0.113 | −0.114 |
| deal_net_oi z156 | +0.236 | **−0.438** |
| NQ lev_net_oi z156 | +0.221 | −0.207 |

**Read:** genuinely low correlation to trailing **return** (it is *not* a price
relabel — the orthogonality hypothesis holds on that axis). But a **meaningful
link to realized volatility** (lev +0.53, dealer −0.44): when vol is high,
leveraged funds are net-longer / dealers net-shorter. So COT positioning carries
a real **vol-regime** component — partially new information, not fully orthogonal.

## Honest caveats

- **Small samples:** relabel n≈55; the best cell has 158 trades across 8 windows.
  Nowhere near the 100+ *per-regime* robustness we'd want.
- **No 2008.** Only 2 bears in-sample.
- The `am`/`deal`/momentum split means the "edge" is not a stable, theory-backed
  direction — the contrarian thesis we set out to test underperformed, and the
  cells that scored are the ones most exposed to overfitting the 2010–2026 path.

## Disposition

- **REJECT** for standalone graduation. Do **not** promote to live `strategies/`.
- The candidate stays quarantined in `strategies_candidates/cot_positioning/`.
- **Worth keeping as a FEATURE, not a strategy:** the vol-regime correlation
  suggests COT positioning could be a useful *conditioning input* combined with
  an orthogonal signal (e.g. the FRED credit-spread lane, once the key lands) —
  a multi-factor combine is a separate, later question. Logged to BACKLOG.
- Infra (`cot_cache.py` + driver + cached 2010–2026 history) is reusable for that
  combine and for any future COT feature — sunk cost is recovered.

## Artifacts

- `runner/cot_cache.py` — ingest + PIT `released_asof` + lookahead canary + selftests + CLI
- `reports/_cot_positioning_driver.py` — backtest/relabel driver (adapted from `_macro_nowcast_driver.py`)
- `reports/_cot_positioning_results.json` — full sweep results
- `reports/_cot_run.log` — run log (this report's source numbers)
- `tests/test_cot_cache.py` — lookahead-guard unit tests
- `data_cache/cot/` — cached TFF history 2010–2026
- `strategies_candidates/cot_positioning/{strategy.py,params.json}` — quarantined candidate
