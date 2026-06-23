# FINRA Daily Short-Volume Signal — Lane Verdict

**File:** `reports/FINRA_SHORTVOL_LANE_20260623T012237Z.md`
**Author:** trading-bench subagent (`finra-shortvol-lane`)
**Date (UTC):** 2026-06-23
**Disposition:** ❌ **CLOSE — clean, robust negative. The signal carries no exploitable timing edge on SPY/QQQ; it is genuinely orthogonal to price/vol but adds zero return.**

---

## 1. Thesis (PRE-REGISTERED, written before seeing results)

Pre-registration committed to disk before any backtest: `reports/_FINRA_SHORTVOL_PREREG.md`.

**The data:** FINRA daily RegSHO `CNMSshvol` files report, per symbol per day, **short-SALE volume**
as a fraction of total reported volume. The core feature is

> **SVR_t = ShortVolume_t / TotalVolume_t**  (short-volume ratio)

Honest framing: this is a daily short-sale **flow / pressure proxy**, **NOT short interest** (the
bi-monthly stock of open shorts). For liquid ETFs, SVR sits high (SPY mean **0.547**, std 0.097)
because much "short" volume is bona-fide market-maker hedging — so the *level* is uninformative and
we test a **trailing z-score / percentile** of SVR for "extreme."

**Two hypotheses, BOTH tested (no sign cherry-picking):**
- **H1 (contrarian/capitulation):** extreme-HIGH SVR = short-sale over-pressure → next-days bounce.
  → go LONG when SVR z ≥ threshold, else cash.
- **H2 (informed-flow):** elevated SVR predicts weakness → go FLAT when SVR high, long otherwise.

Run as a **LONG/FLAT timing overlay** on SPY and (separately) QQQ. Harness can't short → "avoid" = cash.

## 2. Data span + caveats

| | |
|---|---|
| FINRA SVR span | **2019-01-02 → 2026-06-22**, 1,877 trading days/symbol (14 symbols cached) |
| Price | Yahoo v8 adjclose (split+div adjusted), same dates, repo `daily_bars_cache` |
| Aligned days | 1,877 (SPY & QQQ both) |
| **Depth caveat** | **NO 2008 GFC** (FINRA archive starts 2019). Covers 2020 COVID crash + 2022 bear only. |
| Cache | `data_cache/finra_shortvol/<SYM>.json`; fetch module `runner/finra_shortvol_cache.py` |

Fetcher gotcha logged: FINRA returns **HTTP 403 for non-trading days** (weekends/holidays), not just
off-archive — a naive "stop on 403" aborts the pull on the first holiday. Fixed with a
consecutive-no-file circuit breaker (treat 403/404 as "no file," only stop after 40 in a row).

## 3. Exact timing / anti-lookahead assumption

FINRA publishes day-T's file **after the close on day T** (next-morning availability is the safe
assumption). A signal from SVR through close of day T can only be acted on at **T+1 open or later**.

**Implementation:** strict 1-bar lag — the position decided at the close of day T earns the
**day-(T+1)** return: `pos_effective[t+1] = signal_from_data_through[t]`. We never let day-T's SVR
capture the T-1→T move. Trailing z/percentile windows are strictly causal (end at t, inclusive).
Returns are adjclose-to-adjclose. (Engine: `runner/finra_shortvol_backtest.py`, audited.)

## 4. Cost model + benchmark

- **Costs:** repo convention `CostModel.alpaca_stocks()` = **2 bps one-way (~4 bps round-trip)**,
  charged on every change in position `|pos_t − pos_{t-1}|`. Benchmark pays one entry cost then holds.
- **Benchmark:** SPY (resp. QQQ) buy-and-hold over the **same window, on the path actually traded**,
  net of the same cost model. Strat and benchmark sit on identical footing.
- **Metrics:** raw total return, CAGR, Sharpe (annualized √252 on daily net returns), maxDD, round-trips.

## 5. Results — strat vs benchmark (FULL + OOS)

**OOS split:** train 2019-01→2022-12, test **2023-01→2026-06**. The honest OOS pick is the config that
maximizes **train** raw return, with its **test** performance reported (true out-of-sample).

### SPY
| Config | Window | Raw ret | CAGR | Sharpe | maxDD | Trips | Exposure |
|---|---|---|---|---|---|---|---|
| **SPY buy & hold** | FULL 2019–26 | **+232.5%** | 17.5% | 0.927 | −33.7% | — | 100% |
| Best config by *full* raw ret (in-sample, optimistic) | FULL | +251.7% | — | 1.086 | — | — | **86%** ⚠ |
| **SPY buy & hold** | TEST 2023–26 | **+103.5%** | — | 1.435 | — | — | 100% |
| **Honest OOS pick** (sel. train-ret) H2 w42 z0.5 h5 | TEST | **+92.5%** | — | 1.373 | — | — | 87% |
| Honest OOS pick (sel. train-Sharpe) H1 w21 z2.0 h3 | TEST | **+13.1%** | — | 0.932 | — | — | low |
| Cherry-picked ORACLE (best TEST with hindsight) | TEST | +113.5% | — | 1.558 | — | — | **93%** |

### QQQ
| Config | Window | Raw ret | CAGR | Sharpe | Exposure |
|---|---|---|---|---|---|
| **QQQ buy & hold** | FULL 2019–26 | **+398.4%** | — | 1.019 | 100% |
| Best by *full* raw ret (in-sample) | FULL | +421.0% | — | 1.054 | **98%** ⚠ |
| **QQQ buy & hold** | TEST 2023–26 | **+182.4%** | — | 1.603 | 100% |
| **Honest OOS pick** (sel. train-ret) H1 w21 z1.0 h10 | TEST | **+111.5%** | — | 1.682 | 70% |
| Honest OOS pick (sel. train-Sharpe) H1 w252 z1.5 h5 | TEST | **+27.0%** | — | 1.119 | 16% |
| Cherry-picked ORACLE (best TEST with hindsight) | TEST | +199.3% | — | 1.699 | **99%** |

**Walk-forward (expanding train, pick best-train-ret config, apply next calendar year):**
- **SPY:** strat beat bench in **2/6 years**; compounded OOS **+75.4% vs +114.2%** bench.
- **QQQ:** strat beat bench in **2/6 years**; compounded OOS **+95.8% vs +142.4%** bench.
- The only "wins" are 2022 (bear — any de-risk helped, and the picked config was still ~90% long) and
  one near-tie. **Every up-year the signal loses by going to cash.** When it picked a genuinely
  lower-exposure config (2021 SPY 33% expo → +7.7% vs +28.7%; 2023 QQQ 60% expo → +37.6% vs +54.8%) it
  got **crushed** — SVR-driven de-risking removes good up-days.

## 6. Param response surface — knife-edge vs plateau

It is **neither a knife-edge spike nor a real plateau of edge — it's a monotone ramp toward
closet-beta.** Collapsing full-Sharpe over z/hold by (direction, window) for SPY:

- **H1 (contrarian)** is mostly **WORSE** than buy-and-hold: full-Sharpe ranges −0.16 … 0.84 across
  windows, frequently below the 0.927 benchmark. The capitulation thesis is simply wrong here.
- **H2 (avoid-when-high)** climbs toward the benchmark Sharpe **only as exposure → 100%**: the
  high-Sharpe H2 configs are the low-threshold / long-most-of-the-time ones (full-Sharpe up to 1.086
  at **86% exposure**). It approaches buy-and-hold from below, it does not beat it with timing.
- Full-Sharpe range over all 160 configs: **−0.16 … 1.086** (bench 0.927). Test-Sharpe range
  **−0.11 … 1.576** (bench 1.435). The configs at the top of those ranges are all ≥90% invested.

**The decisive diagnostic — performance is pure exposure, not skill:**

| | corr(exposure, excess test-ret) | # configs beating bench (of 160) | their exposure | # beating bench with exposure < 70% |
|---|---|---|---|---|
| SPY | **+0.956** | 22 | min 0.90, mean 0.97 | **0** |
| QQQ | **+0.971** | 24 | min 0.91, mean 0.98 | **0** |

Configs that meaningfully go to cash (exposure < 50%, n≈60) underperform by **−90% (SPY) to −158%
(QQQ)** average excess return. **The cross-sectional spread in results is ~96-97% explained by how
much the config stays invested.** A signal with real timing edge would let *lower-exposure* configs
win; here zero do.

## 7. Orthogonality check (the prior orthogonal rejects all died as secret vol relabels)

Correlation of the SVR signal to SPY/QQQ trailing 63d return and trailing 63d realized vol:

| Symbol | SVR vs trailing-ret | SVR vs trailing-vol | SVR-z vs trailing-ret | SVR-z vs trailing-vol |
|---|---|---|---|---|
| SPY | −0.097 | +0.189 | −0.102 | +0.088 |
| QQQ | −0.026 | −0.009 | +0.013 | +0.093 |

**All |corr| ≤ 0.19.** Unlike prior rejects, this signal is **genuinely orthogonal** to price and
vol — it is NOT a vol relabel. That makes the negative *more* informative, not less: SVR is real
independent information, it just **does not predict next-day index direction** in a tradeable way.
(The faint +0.19 SVR↔vol on SPY is the only whiff of structure — short-sale share ticks up slightly
in higher-vol regimes — but far too weak to monetize, and the timing tests already prove it doesn't.)

## 8. Honest verdict

**Does it beat SPY/QQQ on raw return out-of-sample? NO — decisively, by every honest construction:**

- **SPY OOS:** best honest pick **+92.5% vs +103.5%** buy-and-hold (Sharpe 1.373 vs 1.435). Walk-forward
  **+75.4% vs +114.2%**, won 2/6 years.
- **QQQ OOS:** best honest pick **+111.5% vs +182.4%** buy-and-hold. Walk-forward **+95.8% vs +142.4%**,
  won 2/6 years.
- Even the **cherry-picked, hindsight-oracle** config only *ties* buy-and-hold — and does so by being
  ~93-99% invested, i.e. by becoming buy-and-hold.

**Killer number:** across all 160 configs, **corr(exposure, excess return) = +0.96 / +0.97**, and
**0 of the 22-24 configs that beat the benchmark have exposure below 90%.** The FINRA short-volume
ratio on SPY/QQQ has **no exploitable timing edge** — every attempt to use it to step aside removes
more good days than bad. It is independent of price/vol (clean orthogonality) but uninformative for
next-day index timing.

**Disposition: CLOSE this lane.** This is a documented, honest negative — a real result that retires a
free, never-before-tested signal class at this bench. No further depth (more history, paper clock)
is warranted: the failure is mechanistic (exposure-is-everything) and consistent across the COVID
crash, the 2022 bear, single-split OOS, and walk-forward.

**Caveat on generality (not a reason to keep it open):** this tests SVR only as a **broad-index
long/flat timing overlay**. SVR *might* still carry cross-sectional information at the single-stock
level (e.g. ranking individual names by SVR extremes), which this index-overlay test does not address.
If the bench ever wants to revisit short-volume, the only honest next angle is **cross-sectional
single-name** (and even there, the academic prior is weak for short-*sale*-volume vs short-*interest*).
For the index-timing question posed, the answer is a clean no.

---

### Artifacts
- Pre-registration: `reports/_FINRA_SHORTVOL_PREREG.md`
- Fetch/cache module: `runner/finra_shortvol_cache.py` (+ cache `data_cache/finra_shortvol/`)
- Backtest engine: `runner/finra_shortvol_backtest.py`
- Experiment driver: `_finra_shortvol_run.py` → full results `_finra_shortvol_results.json`
- Protected runner files (runner.py, backtest.py, backtest_xsec.py, risk.py): **untouched**. No
  `strategies/` change, no crontab change, nothing promoted.
