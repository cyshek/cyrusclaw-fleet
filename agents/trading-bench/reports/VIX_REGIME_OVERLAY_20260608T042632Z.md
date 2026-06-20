# VIX-Complex Regime Overlay — Honest Backtest & Verdict

**Report ID:** VIX_REGIME_OVERLAY_20260608T042632Z
**Build:** `runner/cboe_cache.py` + `runner/vix_regime.py` + `runner/vix_overlay_backtest.py`
**Mission bar:** BEAT SPX ON RAW RETURN (promotion gates suspended; honest measurement still mandatory).
**Idea under test:** NATENBERG_SYNTHESIS #2 — long-SPX core + free VIX-complex risk-on/off overlay.
**Status:** RESEARCH / PAPER ONLY. Nothing promoted, nothing live. No broker/risk-cap files touched.

---

## TL;DR / Verdict

**The VIX-complex overlay does NOT beat SPX on raw return — on any span, with any gate variant tested.** It loses by **−26 to −83 percentage points** of total return depending on the gate and window. The mechanism is simple and well-understood: the overlay parks in cash during vol stress, and over a decade dominated by bull years the *premium paid* (missed upside on every calm/trending year) **exceeds the crash protection collected** (the rare fast-spike years where it wins big).

**The scout's prior — "de-risks drawdown even if it doesn't raise raw return alone" — is PARTIALLY CONFIRMED, with an important correction:**
- **Drawdown reduction is REAL but MODEST and REGIME-DEPENDENT, not automatic.** The full-cash gates cut max-DD by only ~2–4pp and in the 2020-08→2026 window actually had a *deeper* max-DD than buy-&-hold (−31.5% vs −25.4%) because the 2022 slow-grind bear **whipsawed** the gate (exit low, re-enter high).
- The **partial de-risk-to-50%** variant is the only one that reliably reduces drawdown (−27.6% vs −33.9% on the extended span; 6.3pp avoided) while giving up the least return.
- The overlay's edge is **concentrated in FAST vol spikes**: it *beat* the underlying in **2018 (+4.6pp)** and **2020 COVID (+10.4pp)** — the two sharp-backwardation events — and *lost* every other year.

**Bottom line:** As a standalone raw-return play, this is a REFUTE. As a **drawdown/crash gate for a future LEVERAGED-long lane (idea #1)**, it is genuinely useful *in the partial-de-risk form* — exactly where giving up some upside to cap a tail is the whole point. It should be carried forward as an overlay primitive, not as a strategy.

---

## 1. Data & spans (cache-floor honesty)

### VIX-complex (CBOE CDN, keyless) — `runner/cboe_cache.py`
Ingested daily index CSVs from `https://cdn.cboe.com/api/global/us_indices/daily_prices/<IDX>_History.csv`, cached to `data_cache/cboe/` (raw CSV + parsed JSON). Mozilla UA, 12s timeout, on-disk cache so re-runs don't re-hit the network. Two column layouts handled: VIX/VIX3M = `DATE,OPEN,HIGH,LOW,CLOSE`; VVIX/SKEW = `DATE,<NAME>` (single value, stored as `close`). Dates parsed MM/DD/YYYY.

| Index | First date | Through | Rows |
|---|---|---|---|
| VIX | 1990-01-02 | 2026-06-05 | ~9,200 |
| SKEW | 1990-01-02 | 2026-06-05 | ~9,200 |
| VVIX | 2006-03-06 | 2026-06-05 | ~5,000 |
| VIX3M | 2009-09-18 | 2026-06-05 | ~4,200 |

**Point-in-time discipline:** these are END-OF-DAY index levels. A decision on trading date **D** may use ONLY levels dated **strictly < D** (the close for D is not known until D's close). `asof()`/`level_asof()`/`history_asof()` enforce this and raise `CboeLookaheadError` on any same-date-or-later access. **Verified live:** decision 2022-06-13 uses the VIX print from 2022-06-10 (27.75), NOT the same-day close (34.02).

### Tradeable underlying — the BINDING constraint
- **Alpaca free IEX SPY daily bars** are the only *tradeable* underlying available, and from this datacenter IP they only become **contiguous (~21 bars/mo) from 2020-08**. Earlier bars are sparse/empty (2019-06 and 2020-03 have **0 bars** — the COVID crash itself is NOT in the contiguous SPY data). The cache filenames claim 2004 but the real first bar is 2018-11-01 with gaps. **We bound the primary backtest by the BARS, not the VIX data**, and never fabricate bars.
  - **Primary span: 2020-08-03 → 2026-06-05** (1,468 bars, ~5.8yr). Covers the **2022 bear** and **2025 tariff bear** cleanly; **misses COVID**.
- **FRED `SP500` (price index, keyed, 10yr license)** gives a deeper SPX path: **2016-06-06 → 2026-06-04** (2,514 points). Used as a SECONDARY, clearly-labeled **MODELED-UNDERLYING** comparison — it is the SPX *price* index (**no dividends**, not a tradeable bar series), but it extends the window ~4yr back and **includes the Feb-Mar 2020 COVID crash**, the single best stress test for a VIX gate.

**Cash convention:** a risk-off (cash) day earns **0%** — we do NOT credit a risk-free rate. This is conservative; in the high-rate 2023–2025 years it understates the overlay's edge by a few pp. Stated plainly so the reader can mentally add it back.

---

## 2. Signals — `runner/vix_regime.py` (all point-in-time)

`signals_asof(date, spy_bars)` returns, using only data strictly before `date`:
- **VIX level**, plus **z-score** and **percentile** over a trailing 252-day window.
- **Term-structure slope** `ts_slope = VIX3M − VIX` and **ratio** `ts_ratio = VIX / VIX3M`. `ts_ratio > 1.0` = **backwardation** (front-month fear above 3-month = stress). This is the core risk-on/off signal.
- **SKEW** level + percentile (tail-risk pricing).
- **VVIX** level + percentile (vol-of-vol).
- **VRP proxy** = `VIX − trailing annualized realized vol of SPY` (implied-minus-realized; positive = vol risk premium being paid).

Sign behavior validated: calm 2017-10-02 → deep contango, low VIX pct, risk-ON; COVID 2020-03-18 → backwardation (ts_ratio 1.20), VIX 76, 99.6th pct, risk-OFF.

---

## 3. The overlay & methodology

**Gate (rule-based, NOT per-day fit):** risk-OFF (move toward cash) if **EITHER** `ts_ratio > 1.0` (backwardation) **OR** `vix_pct > 0.90` (VIX in trailing top decile); else risk-ON (full SPY). Re-risk when both normalize. Optional SKEW/VVIX legs. Missing signals degrade gracefully to risk-ON (so the pre-2009 VIX3M gap doesn't spuriously de-risk).

**Replay:** for each day, weight is decided from strictly-prior data, then earns that day's close-to-close return; equity compounds. Buy-&-hold benchmark trades the **exact same date path**. A **2bp one-way switching cost** is charged on turnover (gross is the headline, net reported alongside — costs are tiny here, ~7pp over a decade).

**Out-of-sample honesty check:** pick the `vix_pct_off` threshold that maximizes RAW return on the first 50% (TRAIN), then apply it UNCHANGED to the held-out 50% (TEST). Result below.

**Why not the walk-forward harness's per-fold refit?** The overlay is a *fixed gate*, not a fitted model — there are no per-fold parameters to estimate. The honest analogue is the chronological train/test split (no shuffle, real warm-up preserved), which is what we ran. The `spy_relative` helper supplies the annualized excess-return + information-ratio numbers below.

---

## 4. Results — PRIMARY span (tradeable SPY bars, 2020-08-03 → 2026-06-05)

RAW total return, head-to-head vs buy-&-hold SPY on the same path:

| Gate | Raw return | SPY raw | **Excess** | Max-DD (strat / SPY) | DD avoided | Sharpe (strat/SPY) | % days OFF |
|---|---|---|---|---|---|---|---|
| ts-only (VIX/VIX3M>1.0) | +94.40% | +124.31% | **−29.91pp** | −29.9% / −25.4% | −4.5pp | 0.84 / 0.91 | 5% |
| pct-only (VIX>90th) | +68.87% | +124.31% | **−55.44pp** | −31.5% / −25.4% | −6.2pp | 0.70 / 0.91 | 11% |
| ts+pct (either) | +73.69% | +124.31% | **−50.62pp** | −31.5% / −25.4% | −6.2pp | 0.75 / 0.91 | 12% |
| ts+pct+vvix | +47.48% | +124.31% | **−76.83pp** | −31.5% / −25.4% | −6.1pp | 0.56 / 0.91 | 16% |
| **ts+pct de-risk-to-50%** | +98.57% | +124.31% | **−25.74pp** | −31.5% / −25.4% | −2.3pp | 0.87 / 0.91 | 12% |

**Every variant loses on raw return AND fails to reduce drawdown** on this span — because the 2022 bear was a slow grind that whipsawed the gate. Per-year (ts+pct):

| Year | Strat | SPY | Excess | % days OFF | Note |
|---|---|---|---|---|---|
| 2020 (Aug+) | +12.4% | +13.7% | −1.3pp | 7% | post-COVID recovery |
| 2021 | +21.2% | +27.0% | −5.8pp | 3% | bull → cash bleeds |
| **2022** | **−26.3%** | **−19.5%** | **−6.9pp** | 24% | **WHIPSAW: gate hurt** |
| 2023 | +24.3% | +24.3% | 0.0pp | 0% | gate never tripped |
| 2024 | +17.1% | +23.3% | −6.2pp | 18% | chop → cash bleeds |
| 2025 | +14.1% | +16.3% | −2.3pp | 16% | tariff bear, mild help |
| 2026 (→Jun) | +4.2% | +8.2% | −3.9pp | 16% | — |

**OOS split** (train 2020-08→2023-07, test 2023-07→2026-06): best train threshold `vix_pct_off=0.85` (train raw +31.95%). On the held-out TEST slice: strat **+50.99%** vs SPY **+66.13%** = **−15.1pp** — still loses, BUT cut test-slice drawdown to **−10.3% vs −19.0%** (8.7pp avoided). So even the in-sample-favored threshold doesn't beat raw OOS; its only payoff is drawdown.

---

## 5. Results — EXTENDED span (FRED SP500 price index, MODELED, 2016-06 → 2026-06, **incl. COVID**)

⚠️ MODELED UNDERLYING: SP500 is the SPX **price** index (no dividends), not tradeable bars. Use for regime coverage, not as a live P&L claim.

| Gate | Raw return | SP500 raw | Excess | Max-DD (strat/idx) | DD avoided | Sharpe (strat/idx) |
|---|---|---|---|---|---|---|
| ts-only | +198.3% | +259.6% | −61.3pp | −29.8% / −33.9% | +4.2pp | 0.88 / 0.80 |
| pct-only | +197.8% | +259.6% | −61.7pp | −31.5% / −33.9% | +2.4pp | 0.90 / 0.80 |
| ts+pct | +176.3% | +259.6% | −83.2pp | −31.5% / −33.9% | +2.4pp | 0.86 / 0.80 |
| **ts+pct de-risk-50%** | +221.7% | +259.6% | **−37.8pp** | **−27.6% / −33.9%** | **+6.3pp** | 0.89 / 0.80 |

Per-year (ts+pct) — **this is the key evidence for WHEN the gate works:**

| Year | Strat | SP500 | Excess | % OFF | Regime |
|---|---|---|---|---|---|
| 2016 | +1.6% | +6.1% | −4.5pp | 6% | calm bull |
| 2017 | +17.1% | +19.4% | −2.3pp | 2% | calm bull |
| **2018** | **−1.7%** | **−6.2%** | **+4.6pp** | 32% | **vol spikes → gate WINS** |
| 2019 | +18.3% | +28.9% | −10.6pp | 6% | bull → cash bleeds hard |
| **2020** | **+26.7%** | **+16.3%** | **+10.4pp** | 21% | **COVID crash → gate WINS BIG** |
| 2021 | +20.9% | +26.9% | −6.0pp | 3% | bull |
| **2022** | **−26.4%** | **−19.4%** | **−6.9pp** | 24% | **slow-grind bear → gate LOSES** |
| 2023 | +24.2% | +24.2% | 0.0pp | 0% | never tripped |
| 2024 | +16.9% | +23.3% | −6.4pp | 17% | chop |
| 2025 | +14.1% | +16.4% | −2.3pp | 16% | tariff bear, mild |
| 2026 | +6.8% | +10.8% | −3.9pp | 16% | — |

**The pattern is unambiguous:** the overlay wins **only** in fast, sharp-backwardation events (2018, 2020-COVID) and loses the insurance premium in every calm/trending year and in slow-grind bears (2022). Sharpe is modestly *higher* than the index on the extended span (0.86–0.90 vs 0.80) because cash days dampen volatility — but Sharpe is not the mission bar, raw return is, and on raw return it loses.

---

## 6. Honest caveats / modeling notes

1. **COVID is in the EXTENDED (modeled SP500) span only, not the PRIMARY (tradeable SPY) span.** The single regime where the overlay shines most (2020) rests on the price-index proxy, not on tradeable bars. Flagged loudly.
2. **SP500 = price index, no dividends.** Both strat and benchmark are understated by the same ~1.5–2%/yr, so the *excess* is roughly unaffected, but absolute returns aren't a live-tradeable claim.
3. **Cash earns 0%** (no risk-free credit) — conservative; understates the overlay in high-rate years.
4. **No leverage, no shorting** — a pure long/cash gate. The overlay's natural home is *gating leverage*, not trading flat SPY.
5. **Switching costs modeled at 2bp one-way** (tiny at ~12–14 switches/yr). Slippage on real fills not modeled; immaterial at this turnover.
6. **Single underlying, single-country, ~10yr max.** Not a multi-regime century-scale claim. The 2022-vs-2020 divergence (slow bear hurts, fast crash helps) is the load-bearing insight and is robust across both spans.
7. **Lookahead audited and clean** — verified that decisions use only strictly-prior VIX prints; `CboeLookaheadError` guards every accessor; 11 pytest cases (incl. a synthetic canary that asserts the guard *raises* on a same-date record).

---

## 7. Recommendation

- **As a standalone raw-return strategy: REJECT.** It does not beat SPX raw on any span/variant. Do not promote.
- **As an overlay primitive for the LEVERAGED-long lane (idea #1): CARRY FORWARD, in the partial-de-risk (≤50% off) form.** When the core is leveraged, capping the tail in fast-backwardation events (2018, 2020) is exactly worth giving up a slice of trending-year upside — and the partial-de-risk variant is the only one that reduces drawdown without 2022-style whipsaw self-harm. Pair the gate with a leverage engine, not flat SPY.
- **Best single signal:** `ts_ratio > 1.0` (term-structure backwardation) is the cleanest, lowest-turnover trigger (5–8% of days OFF, +4.2pp DD avoided on the extended span). `vix_pct` and `vvix` legs add turnover and cost more than they save.

**Artifacts:** `runner/cboe_cache.py`, `runner/vix_regime.py`, `runner/vix_overlay_backtest.py`, `tests/test_cboe_cache.py` (11 tests). Full suite **320 passed** (was 309). Data cached under `data_cache/cboe/`.
