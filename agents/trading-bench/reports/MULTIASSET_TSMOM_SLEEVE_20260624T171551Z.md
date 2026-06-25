# Multi-Asset TSMOM Sleeve — Standalone Honest Evaluation

**Stamp:** 2026-06-24T17:15:51Z  ·  **Author:** trading-bench subagent (opus)
**Engine:** `_tsmom_engine.py`  ·  **Eval harness:** `_tsmom_eval.py`  ·  **Raw results:** `_tsmom_eval_results.json`

## Thesis tested
The bench has only ever run multi-asset trend as an **inverse-vol overlay that gutted raw return** — never as its own return-judged sleeve. Managed-futures trend proxies (KMLM/DBMF) ran ≈ −0.37/−0.38 correlation vs our equity blend in 2022 = candidate **crisis-alpha diversifier** (AQR, *Time Series Momentum*, Moskowitz-Ooi-Pedersen 2012). Test it honestly as a **standalone Sharpe / return sleeve**, primary weighting = **equal-weight across in-trend assets** (NOT inv-vol).

## Construction (reuses runner primitives — no re-implemented rulers)
- **Data:** Yahoo v8 adjclose via `runner.daily_bars_cache.get_daily` (split+div adjusted). Works from this VM.
- **Signal:** 12-1 time-series momentum — trailing 12-month return skipping the most recent month (`price[t−21d] / price[t−252d] − 1`). **Long if > 0, FLAT if ≤ 0. Long/flat only, no shorting, no leverage.** Monthly rebalance on the last trading day of each month; weights take effect the next trading day (anti-lookahead).
- **Weighting (PRIMARY):** equal-weight across the assets currently in-trend; sleeve is fully invested across in-trend names, **100% cash (0% return) when nothing is in-trend** (no cash yield assumed — conservative). Inv-vol variant reported for contrast.
- **Cost:** `runner.backtest.CostModel.alpaca_stocks()` = **2 bps one-way**, charged on rebalance turnover (Σ|Δw| × 2bps).
- **Sharpe:** `runner.fp_sharpe.sharpe_from_returns` + `bars_per_year("1Day")` = sqrt(252). **CAGR:** `runner.lane_honesty.cagr`. Full-period = ONE concatenated daily series (not median-of-windows).
- **Span:** start **2008-05** (UUP inception 2007-03 + 12m warmup → sleeve fully formed from first live day; captures 2008 GFC, 2020 COVID, 2022 bear). End 2026-06-24. n ≈ 4,565 trading days.

## Universes
- **core4** = DBC GLD TLT UUP (commodities / gold / long-bonds / dollar) — the lean macro basket
- **macro7** = core4 + IEF SLV USO (adds intermediate bonds / silver / oil — still NO equities)
- **u6 / u8 / u10** = progressively wider (adds VNQ, then EFA/EEM)
- **full12** = u10 + SPY + QQQ (adds the equity legs into the trend engine)

---

## Headline results — PRIMARY (equal-weight in-trend, 12-1)

| Universe | n | Full Sharpe | Full CAGR | SPY CAGR (same path) | OOS Sharpe (2018+) | maxDD | **corr→SPY** | 2022 sleeve vs SPY |
|---|---|---|---|---|---|---|---|---|
| **core4** | 4 | 0.305 | **+2.68%** | +11.58% | 0.591 | −24.7% | **−0.01** | **+2.8%** vs −18.2% |
| macro7 | 7 | 0.280 | +2.90% | +11.58% | 0.490 | −32.1% | +0.11 | **+7.9%** vs −18.2% |
| u6 | 6 | 0.444 | +3.70% | +11.58% | 0.509 | −19.5% | +0.20 | −6.1% vs −18.2% |
| u8 | 8 | 0.363 | +3.84% | +11.58% | 0.497 | −32.1% | +0.24 | −0.7% vs −18.2% |
| u10 | 10 | 0.402 | +4.24% | +11.58% | 0.502 | −32.0% | +0.40 | −3.6% vs −18.2% |
| full12 | 12 | 0.576 | +6.50% | +11.58% | 0.659 | −31.2% | +0.57 | −9.8% vs −18.2% |

**SPY buy-hold on the same path:** Full Sharpe **0.653**, CAGR **+11.58%**, totRet **+628%**, maxDD **−51.5%**.

### Crisis windows (total return over the window)
| Config | 2008 GFC (Sep08–Mar09) | 2020 COVID (Feb19–Apr30) | 2022 bear (full year) |
|---|---|---|---|
| **core4** | −7.6% | **+4.7%** | **+2.8%** |
| macro7 | −15.5% | −1.1% | **+7.9%** |
| u10 | −16.5% | −7.3% | −3.6% |
| full12 | −16.5% | −6.9% | −9.8% |
| **SPY** | **−37.0%** | **−13.2%** | **−18.2%** |

core4 is **positive in 2 of 3 crises** (2020 + 2022) and far shallower than SPY in the third (2008). This is the KMLM/DBMF crisis-alpha profile, **confirmed** — but only for the **lean, equity-free** basket. Adding SPY/QQQ/EFA/EEM into the trend engine *destroys* the crisis alpha (the equity legs get chopped right when you need protection) and pulls corr→SPY up toward 0.57.

---

## Robustness

**Lookback (6/9/12 month) — stable plateau, NOT a knife-edge argmax:**
- core4: Sharpe 0.36 / 0.39 / 0.31 — **corr→SPY = +0.01 / −0.03 / −0.01 at every lookback** (orthogonality is lookback-invariant)
- u10:  Sharpe 0.39 / 0.33 / 0.40; OOS Sharpe 0.46 / 0.75 / 0.50

No single lookback spikes above the others → not overfit to one argmax.

**OOS (pre-2018 IS / 2018+ OOS) — holds up, not an IS mirage:**
- core4 OOS Sharpe **0.591** (vs IS 0.059) — OOS is *stronger*, not a decayed in-sample fit
- full12 OOS Sharpe 0.659 (vs IS 0.496); every config has a **positive** OOS Sharpe
- (SPY OOS Sharpe over the same 2018+ window = 0.801 — the sleeve still trails SPY OOS on raw return)

**Cost fragility — none.** Breakeven one-way cost: **core4 = 68 bps, macro7 = 69 bps, full12 = 170 bps** — vs the 2 bps realistic cost. Turnover ≈ 0.30/rebalance × ~12 rebal/yr is cheap; the edge survives ~34× the modeled cost.

**Inv-vol contrast (u10, 12-1):** inv-vol gave Full Sharpe **0.496** (vs EW 0.402) and maxDD **−16.1%** (vs −32.0%) but **lower CAGR 4.02% vs 4.24%**. So on this long/flat construction inv-vol *improved risk-adjusted* return while *shaving raw* return — directionally consistent with the "inv-vol trims return" thesis, though far less catastrophic than the documented overlay (because here it allocates only across in-trend names, not as a return-suppressing overlay on everything).

---

## Verdict: 🟡 **AMBER** — genuine orthogonal crisis-alpha diversifier; does NOT beat SPX raw return

**On the mission bar (beat SPX raw return): FAILS, clearly and in every config.** Best full-period CAGR is full12 at +6.50% vs SPY's +11.58%; the lean core4 is only +2.68%. As a *standalone return engine* a long/flat multi-asset TSMOM sleeve is **not competitive** with buy-hold SPY.

**On the diversification claim: PASSES, strongly, for the lean macro basket.** core4 delivers:
- **corr→SPY ≈ −0.01** (target < 0.3 — beaten by an order of magnitude), lookback-invariant
- **positive returns in the 2020 and 2022 equity drawdowns** (+4.7%, +2.8%) and −7.6% in 2008 vs SPY's −37%
- positive, stable **OOS Sharpe 0.59**, robust across lookbacks, breakeven 68 bps (cost-insensitive)

This is exactly the crisis-alpha overlay profile the thesis predicted. **It is a real diversifier sleeve — a shelf / paper-track candidate to be combined WITH the equity book (where its zero/negative correlation lifts blended Sharpe and cuts blended drawdown), NOT a standalone Sharpe sleeve to replace equities.** The single most important construction finding: **keep equities OUT of the trend engine** — core4/macro7 (equity-free) are the diversifier; the moment SPY/QQQ enter the basket, correlation to SPY climbs to 0.4–0.6 and the crisis alpha evaporates.

### Recommended next step (if pursued)
Paper-track **core4 EW 12-1** (or macro7 for stronger 2022 alpha) as a **diversifier overlay**, and run a blended test: `X% equity book + (1−X)% core4-TSMOM` — measure whether the near-zero correlation lifts the *combined* full-period Sharpe above the equity book alone. That blend test, not the standalone number, is where this sleeve earns its keep. (Out of scope for this build per task constraints — flagged for the allocator lane.)

---

## Files
- `_tsmom_engine.py` — sleeve engine (load_panel, run_tsmom, stats, crisis windows)
- `_tsmom_eval.py` — full eval harness (universe sweep, lookback robustness, IS/OOS, inv-vol, breakeven)
- `_tsmom_eval_results.json` — raw numbers for every config
- `_tsmom_smoke.py` — initial smoke test

## Caveats / honesty notes
- Sleeve assumes **0% on idle cash** (when nothing is in-trend). A real implementation would earn ~T-bill yield on cash, which would *raise* the sleeve's standalone return materially in cash-heavy stretches (2008/2022) — so the standalone return here is a conservative floor, but it still won't close an ~9-point CAGR gap to SPY.
- ETFs only (Yahoo adjclose); no futures-roll modeling. The KMLM/DBMF/AQR managed-futures programs use a much wider futures universe (rates, FX, ags, energy curve) + short legs — a long/flat ETF proxy is a *floor* on the true trend premium, especially the short-side crisis alpha we cannot capture here.
- Pre-2008 history excluded by design (UUP inception) to keep all legs present from day one; full-history single-asset (TLT/GLD-only from 2004) was not the brief.
