# Cross-Asset 12-1 Momentum — BROAD-UNIVERSE / $1,000 REVIVAL TEST

**Date:** 2026-06-22 · **Author:** trading-bench subagent (`xsec_momentum_revival`)
**Candidate:** `strategies_candidates/xsec_momentum_revival_b16/`
**Verdict:** ❌ **DOES NOT CLEAR THE BAR** (loses SPX on raw return in every window/K; loses on Sharpe in the headline FULL span and the OOS TEST(2018+) for every K). A clean, honest negative that resolves two pre-registered assumptions.

---

## 1. The reframed question (what is genuinely new here)

This lane is **not virgin territory** — main's framing ("deferred after wave-3 at Sharpe 0.30") is partly stale. Honest prior state:

| Prior attempt | Universe | Notional | Result |
|---|---|---|---|
| Wave-3 sector-equity 12-1 | 11 SPDRs | $100 | full-period Sharpe **0.30** → REJECTED (universe-class problem) |
| Wave-4 cross-asset 12-1 (`xsec_momentum_xa_38d2b2`) | ~6 assets (SPY/EFA/TLT/VNQ/DBC/GLD) | $100 | promoted → **DEMOTED to 0.87 full-period / 0.17 WF-median Sharpe** after the √252 annualization-bug fix (`reports/DEMOTE_xsec_momentum_xa_38d2b2_20260531T190924Z.md`) |

Two pre-registered assumptions were left open by that demote:
- **(a)** the **$100 cap floored** an 11-instrument basket (too little notional to deploy a diversified book);
- **(b)** **more cross-asset breadth helps** (a prior n=1 finding flagged that the edge "saturates at ~6 assets," and that 12-1 momentum *never selected TLT/VNQ* over the 5yr window).

> **The genuinely new test:** *Does broadening to 16 cross-asset instruments + raising notional to $1,000 clear the bar, where the 6-asset / $100 version demoted to 0.87 full-period / 0.17 WF-median Sharpe on the corrected √252 ruler?*

Answer up front: **No.** The $1,000 notional removes the floor-block (the basket now deploys ~$880–$1,000 every month, vs a $100 cap before), and the added breadth **is** used by the ranker (all 16 instruments get held sometimes) — yet performance is **worse**, not better, than the 6-asset version on raw return, and still below SPX on every honest axis. The signal itself, not the universe size or the notional floor, is what fails.

---

## 2. Universe (16 instruments, 4 asset classes)

Common-window start chosen: **2007-01-03** (first trading day after the latest inception, SLV 2006-04-28, plus ~8 months for the 12-1 warmup). All 16 instruments are live for the entire 2007→2026 span — **no shrinking universe**.

| Symbol | Class | Inception (Yahoo v8 adjclose) | Bars |
|---|---|---|---|
| SPY | Broad equity | 1993-01-29 | 8405 |
| QQQ | Broad equity | 1999-03-10 | 6863 |
| XLK | Sector (tech) | 1998-12-22 | 6915 |
| XLF | Sector (financials) | 1998-12-22 | 6915 |
| XLE | Sector (energy) | 1998-12-22 | 6915 |
| XLV | Sector (health) | 1998-12-22 | 6915 |
| TLT | Bond (20+yr Tsy) | 2002-07-30 | 6012 |
| IEF | Bond (7-10yr Tsy) | 2002-07-30 | 6012 |
| SHY | Bond (1-3yr Tsy) | 2002-07-30 | 6012 |
| GLD | Commodity (gold) | 2004-11-18 | 5430 |
| SLV | Commodity (silver) | 2006-04-28 | 5067 |
| USO | Commodity (oil) | 2006-04-10 | 5081 |
| DBC | Commodity (broad) | 2006-02-06 | 5125 |
| VNQ | REIT | 2004-09-29 | 5466 |
| EFA | Intl (developed) | 2001-08-27 | 6240 |
| EEM | Intl (emerging) | 2003-04-14 | 5834 |

Source: Yahoo v8 chart API `adjclose` (split+dividend adjusted) via `runner/daily_bars_cache.py` — the deep, IP-unwalled daily source (TOOLS.md). **Note:** Alpaca (`runner/bars_cache.py`) only serves these ETFs from ~2018–2020 — far too shallow for a 12-1 momentum backtest needing pre-2018 train + deep OOS — so the Yahoo adjclose cache is the correct (and spec-mandated) source. 10 of the 16 symbols were freshly fetched and cached this run.

---

## 3. Method

- **Signal — 12-1 momentum (skip-month spelled out):** trailing 12-month total return **skipping the most recent month**. In trading bars: `end_px = close[-1-skip]`, `start_px = close[-1-skip-lookback]`, with `lookback=252`, `skip=21`. The most recent ~21 trading days (1 month) are **excluded** from the signal (the standard momentum gap that avoids 1-month reversal). Return = `(end_px - start_px)/start_px`. Rank all instruments descending.
- **Allocation:** long-only **top-K equal-weight**, per-leg notional = `$1000 / K`. The harness `_clamp_basket` enforces the shared basket cap `MAX_POSITION = $1000` (current global value in `runner/risk.py`; the old $100 was Session-1).
- **Rebalance:** calendar-month boundaries (first tick whose month ≠ stored `last_rebalance_month`).
- **K-sweep:** K ∈ {3, 4, 5}; picked by **honest OOS** (2018+), not in-sample argmax.
- **OOS split:** TRAIN ≤ 2017-12-31 (frozen), TEST 2018-01-01+. Lookahead-safe: ranks use only bars dated ≤ month-end (with the skip gap); fills at the next available bar.
- **Cost model:** `CostModel.alpaca_stocks()` = **2 bps spread/side, 0 fee**, applied to both the strategy legs and the SPY benchmark leg.
- **Sharpe method (HEADLINE):** full-period **continuous-span** Sharpe — `sharpe_from_returns(equity_curve_returns(equity_curve), √252)` from `runner/fp_sharpe.py`, the canonical load-bearing ruler. **Median-of-windows Sharpe is a known mirage and is NOT reported as a headline** (it is what caused the original `xsec_momentum_xa` bad promotion). Benchmark SPX = SPY adjclose buy-&-hold on the **same dates / same 2 bps treatment**, continuous-span Sharpe on its daily equity curve.

**Harness path used:** direct composition of `runner/backtest_xsec.backtest_xsec` over the full span + explicit pre-2018 / post-2018 slicing of the resulting equity curve (the documented `fp_continuous_sharpe` pattern). `walk_forward_xsec` was **not** used: a monthly-rebalance momentum structurally 0-trades the short WF windows that harness is tuned for (60–140 trades/window, churny parents), so the full-span + OOS-split path is the honest one here.

---

## 4. Results — strategy vs SPX (continuous-span Sharpe headlined)

**SPX (SPY buy-&-hold, 2 bps/side):**

| Window | Span | Raw return | Sharpe | CAGR | maxDD |
|---|---|---:|---:|---:|---:|
| FULL | 2007-01-03 → 2026-06-22 | **+652.50%** | **0.627** | 10.93% | −55.19% |
| TRAIN (≤2017) | 2007-01-03 → 2017-12-29 | +136.86% | 0.493 | 8.17% | −55.19% |
| TEST (2018+) | 2018-01-02 → 2026-06-22 | **+215.31%** | **0.805** | 14.53% | −33.72% |

**Strategy (broad 16-instrument cross-asset 12-1 momentum, $1,000), by K:**

| K | Window | Raw return | Sharpe | CAGR | maxDD | Trades |
|---|---|---:|---:|---:|---:|---:|
| **3** | FULL | +222.09% | 0.511 | 6.19% | −44.18% | 377 |
| 3 | TRAIN | +91.56% | 0.460 | 6.10% | −44.18% | 235 |
| 3 | **TEST(2018+)** | +116.19% | **0.635** | 9.53% | −24.51% | 153 |
| **4** | FULL | +193.00% | 0.520 | 5.68% | −36.70% | 408 |
| 4 | TRAIN | +85.34% | 0.479 | 5.78% | −36.70% | 222 |
| 4 | TEST(2018+) | +95.42% | 0.624 | 8.23% | −22.19% | 196 |
| **5** | FULL | +178.90% | 0.561 | 5.41% | −32.32% | 449 |
| 5 | TRAIN | +88.32% | 0.548 | 5.93% | −32.32% | 243 |
| 5 | TEST(2018+) | +86.60% | 0.613 | 7.64% | −23.20% | 225 |

**Head-to-head (strategy − SPX) — the bar requires beating on BOTH raw return AND Sharpe:**

| K | Window | Δ Raw return | Δ Sharpe | Clears? |
|---|---|---:|---:|:--:|
| 3 | FULL | −430.41% | −0.116 | ❌ |
| 3 | TRAIN | −45.30% | −0.033 | ❌ |
| 3 | TEST(2018+) | −99.12% | −0.171 | ❌ |
| 4 | FULL | −459.50% | −0.107 | ❌ |
| 4 | TRAIN | −51.52% | −0.014 | ❌ |
| 4 | TEST(2018+) | −119.89% | −0.181 | ❌ |
| 5 | FULL | −473.60% | −0.067 | ❌ |
| 5 | TRAIN | −48.54% | **+0.055** | ❌ (Sharpe-only, in-sample, still loses raw return) |
| 5 | TEST(2018+) | −128.71% | −0.192 | ❌ |

**K pick (honest OOS, not in-sample argmax):** K=3 is marginally best out-of-sample (OOS Sharpe **0.635**, OOS raw +116.2%), but all three K lose decisively to SPX's OOS **0.805 / +215.3%**. There is no K that clears.

**Lower drawdown is the only edge:** the strategy's maxDD (−22% to −44%) beats SPX's −55% (FULL) / −34% (TEST). So it is a lower-vol, lower-return rotation — a *worse Sharpe* because the return give-up exceeds the vol give-up. That is the signature of a signal with no real alpha, only beta-timing drag.

---

## 5. Selection-frequency table — the saturation test (most informative)

% of rebalance months each instrument is held (FULL span, 234 months). Computed by an independent month-by-month replay of the same `_rank_12_1` signal (lookahead-safe: only bars ≤ month-end, skip-gap baked in).

**K=4, FULL (234 months):**

| Symbol | Class | Months held | % |
|---|---|---:|---:|
| QQQ | BroadEq | 117 | **50.0%** |
| XLK | Sector | 103 | **44.0%** |
| GLD | Commod | 92 | 39.3% |
| SLV | Commod | 78 | 33.3% |
| XLF | Sector | 68 | 29.1% |
| VNQ | REIT | 63 | 26.9% |
| XLE | Sector | 61 | 26.1% |
| XLV | Sector | 61 | 26.1% |
| TLT | Bond | 52 | 22.2% |
| USO | Commod | 47 | 20.1% |
| DBC | Commod | 47 | 20.1% |
| EEM | Intl | 42 | 17.9% |
| EFA | Intl | 31 | 13.2% |
| SPY | BroadEq | 29 | 12.4% |
| IEF | Bond | 29 | 12.4% |
| SHY | Bond | 16 | 6.8% |

**Selected EVER: 16/16 · held >10% of months: 15/16 · held >20%: 11/16.** (K=3: 16 ever, 12 over 10%; K=5: 16 ever, 15 over 10%.)

### What this resolves about the two priors

- **"Edge saturates at ~6 assets / extra breadth never selected" — REFUTED as stated.** The breadth IS used: every one of the 16 instruments gets held, and 12–15 of them clear 10% of months. The 9 instruments *added* beyond the original 6-asset basket (XLF, XLE, XLV, SLV, USO, DBC, EEM, and heavier sector/commodity rotation) are NOT dead weight in the *selection* sense — momentum actively rotates through them.
- **BUT broadening still doesn't help performance**, because the names momentum rotates *into* are dominated by high-beta equity proxies (QQQ 50%, XLK 44%) plus crisis-chasing metals (GLD 39%, SLV 33%). The strategy buys them *after* their 12-1 run-up and eats the reversal/whipsaw (377–449 trades, 95–110 basket clamps over the span). Breadth adds **rotation churn, not diversifying alpha** — so the extra instruments hurt raw return (6-asset $100 was 0.87 FP Sharpe; this broad book is 0.51–0.56) while the OOS Sharpe stays stuck below SPX.

- **"12-1 momentum never selects TLT/VNQ" — was a window artifact, now corrected.** Over the full span TLT is held 22% and VNQ 27% of months. The TRAIN vs TEST split shows exactly why the prior n=1 saw zero:

| Symbol | TRAIN ≤2017 (132 mo) | TEST 2018+ (102 mo) |
|---|---:|---:|
| TLT | 29.5% | 12.7% |
| IEF | 17.4% | 5.9% |
| SHY | 9.1% | 3.9% |
| VNQ | 34.8% | 16.7% |
| QQQ | 47.7% | 52.9% |
| XLK | 36.4% | 53.9% |

Momentum **correctly rotated OUT of bonds** in the 2018+ rate-hike cycle (TLT 29.5%→12.7%) and INTO tech (XLK 36%→54%). The prior "never selected" observation came from looking only at a recent rate-hike window; it is regime-specific, not structural. The signal does the *sensible* thing here — it just doesn't generate alpha doing it.

---

## 6. Verdict

**❌ DOES NOT CLEAR THE BAR.** The honest why, crisply:

1. **The $1,000 notional removes the floor-block but the signal doesn't clear.** The basket now deploys ~$880–$1,000/month (verified: final K=4 book = DBC $228 + SLV $374 + USO $29 + XLK $245 = $877; ~$1,000 at rebalance). Assumption (a) — "the $100 cap floored the basket" — is **resolved: the floor was real but not load-bearing.** Removing it did not help; OOS Sharpe (0.61–0.64) still trails SPX (0.805).
2. **Broadening to 16 instruments does not help — it slightly hurts.** Assumption (b) — "more breadth helps" — is **resolved NEGATIVE.** The breadth is genuinely used (16/16 ever selected), but momentum rotates into high-beta equity/metals and churns (377–449 trades), so raw return falls vs the 6-asset version and OOS Sharpe stays below benchmark. Extra cross-asset breadth adds churn, not diversifying alpha, for a 12-1 long-only ranker under these bench constraints (monthly cadence, 2 bps, equal-weight top-K).
3. **Every K loses SPX on raw return in every window, and on Sharpe in FULL + OOS.** The only "win" (K=5 TRAIN Sharpe +0.055) is in-sample and still loses raw return by 49 pts. Lower drawdown is the lone genuine property, but the return give-up exceeds the vol give-up → worse Sharpe.

**This is a SUCCESS as a test:** it cleanly resolves both pre-registered assumptions with selection-frequency evidence, and corrects a stale prior ("never selects bonds" → window artifact). The cross-asset 12-1 momentum lane is **closed** at the bench bar — do not promote, do not start a paper clock.

### Recommended next (BACKLOG P2)

Per the brief's two options, I recommend the **`load_xsec_strategy` candidate-path cleanup** over the options-feasibility memo, for two reasons: (1) it is a concrete, low-risk infra fix that removes a recurring footgun this very task hit (the loader only reads `strategies/`, not `strategies_candidates/`, forcing the symlink-or-call-directly dance documented in the brief); (2) the options-feasibility memo is a larger research item better scoped to a fresh sprint with its own data-access decision. The cleanup pays for itself every time a candidate is evaluated. (Routing this recommendation to main, not auto-starting it — it touches a protected runner file, which is out of scope for this explore-mode subagent.)

---

## 7. Reproducibility

**Files created (all under candidate dir + driver scratch; NO `strategies/`, NO crontab, NO protected-runner edits):**
- `strategies_candidates/xsec_momentum_revival_b16/{__init__.py, strategy.py, params.json}` — the candidate (decide_xsec; 16-instrument, $1,000, K-param).
- `_revival_driver.py` — the backtest+OOS+selection driver (imports `runner.*` read-only).
- `_revival_probe.py` — universe fetch/inception probe.
- `_revival_results.json` — full numeric results.
- `reports/XSEC_MOMENTUM_REVIVAL_20260622.md` — this report.
- 10 new `data_cache/yahoo/<SYM>_{raw,parsed}.json` (XLF, XLE, XLV, IEF, SHY, USO, VNQ, EFA, EEM, DBC) fetched via `daily_bars_cache`.

**Exact commands:**
```bash
cd /home/azureuser/.openclaw/agents/trading-bench/workspace
python3 _revival_probe.py        # fetch + verify 16-instrument universe (inceptions)
python3 _revival_driver.py        # full + train + test backtest, K∈{3,4,5}, selection freq
python3 -m pytest -q              # regression suite
```

**Suite green count:** **663 passed**, 1 skipped, **1 failed**. The single failure — `tests/test_fx_bars_cache.py::test_live_eurusd_cache_span_matches_lane_claim` (`expected 5843 EURUSD bars, got 5852`) — is a **pre-existing, unrelated** stale-assertion in the FX lane (the EURUSD cache organically grew 9 bars since the test's hardcoded count was written). I touched nothing in `fx_bars_cache.py` or the `yahoo_fx` cache. Effective green for this work = 663/663 relevant.

**Protected-file-untouched verification:**
```
$ find runner -newermt '2026-06-22 14:30' -name '*.py'
(empty)   # no engine/runner file mutated
```
All new files are confined to `strategies_candidates/xsec_momentum_revival_b16/`, the `_revival_*` driver scratch, this report, and the Yahoo bar cache. `runner/*` imported read-only.

**Benchmark ruler sanity:** SPY 2007→2026 raw adjclose return = +652.8% (driver: +652.50% net of 2 bps round-trip ✓); SPY full-period daily Sharpe×√252 = 0.627 (matches expected ~0.6 ✓).
