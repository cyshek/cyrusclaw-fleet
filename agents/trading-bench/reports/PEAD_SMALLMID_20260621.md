# PEAD on a SMALL/MID-CAP Universe — Long-Only Earnings-Surprise Drift

**Date:** 2026-06-21 (UTC) · run host openclaw-vm
**Author:** trading-bench research subagent (lane: EARNINGS-DRIFT / PEAD, small/mid re-aim)
**Harness:** `strategies_candidates/pead_smallmid/backtest_pead_smallmid.py` (+ `sweep_pead_smallmid.py`, `_alpha_check.py`)
**Data:** `strategies_candidates/pead_real/earnings.db` (90,717 EPS-surprise events, 3,198 symbols, 2012–2026, EDGAR dates + Nasdaq consensus) × `runner.daily_bars_cache` (Yahoo v8 split+div-adjusted daily bars, free, IP-unwalled).
**Citation:** Bernard & Thomas 1989 (JAR 27) / 1990 (JAE 13); Hou 2007; Hong-Lim-Stein 2000 (drift ∝ slow info diffusion in low-coverage names).

---

## Verdict (TL;DR): ❌ HONEST REJECT — small/mid is NOT materially better than mega-cap, and the apparent edge is market beta, not drift.

The pre-committed config (+5% surprise, long-only, 5/10/20d hold, 5bps one-way, realizable 30-position book) lands at **OOS Sharpe 0.33 / 0.58 / 0.50** (5/10/20d) — i.e. the best cell (0.58 @ 10d) is **statistically indistinguishable from the prior mega-cap long-only result (~0.59–0.67)**. It is **not** the 3× academic improvement the literature predicts.

The decisive diagnostic: the small/mid long book runs **beta ≈ 0.9 to SPY**, and when that beta is hedged out, **Sharpe collapses to ~0.0–0.4 and the annualized idiosyncratic alpha is statistically insignificant (t ≈ 0.3–0.8)**. The positive per-trade return (+0.55%/trade @10d) comes from the names rising *with the market* during the hold, not from genuine post-earnings drift. **One cherry-picked cell (s>15% @10d) hits OOS Sharpe 0.757**, but it (a) is a fragile corner (neighbors are 0.44–0.63), (b) is still a beta-0.88 long book (MaxDD 34%), and (c) drops to hedged-Sharpe 0.39 / ann-alpha t≈0.8 — i.e. mostly beta + noise.

**Gate:** OOS Sharpe ≥ 0.70 AND ≥ 50 OOS trades. Trade count passes hugely (1,000–2,600). Sharpe **fails at the pre-committed +5% config (0.58)**. It only clears at a single post-hoc-selected +15%/10d corner that does not survive a beta hedge. **No robust promotion. Stays in `strategies_candidates/`.**

---

## 1. Setup

| Parameter | Value |
|---|---|
| Universe | small/mid liquidity-price proxy, **point-in-time at announcement**: price ∈ [$5, $100] AND 30d avg dollar volume ∈ [$5M, $200M], computed from bars **strictly before** the earnings date (no lookahead) |
| Signal | `surprise_pct > +5%` (beat). Long-only. Skip (−5%,+5%) and all misses. |
| Quality filter | `n_estimates ≥ 4` AND `|eps_forecast| ≥ 0.05` (avoid tiny-denominator surprise blow-ups) |
| Entry | **next trading day's ADJUSTED OPEN** after the earnings date (gap already realized). adj_open = open × (adjclose/close) |
| Hold | 5, 10, 20 trading days (all tested); exit at adjusted close |
| Cost | **5 bps one-way** (10 bps round-trip) — small/mid spreads wider than mega-cap |
| Book | equal-weight, capacity-capped at **30 concurrent** positions (realizable book) |
| Full period | 2012-01-01 → 2026-06-19 |
| OOS period | **2022-01-01 → 2026-06-19** (post-2022, per task) |
| Benchmark | SPY buy-and-hold: FULL CAGR 14.99%, OOS CAGR 12.05% |

**Coverage:** 27,643 candidate beats over 2,205 distinct symbols → after the point-in-time liquidity/price filter, **15,512 small/mid trades built across 1,607 symbols** (12,130 events priced-out as mega-cap-liquid or sub-$5/illiquid; 0 no-bars; 1 no-exit). This is a genuinely small/mid cross-section, not a handful of names.

---

## 2. Results at the PRE-COMMITTED config (+5% surprise)

### FULL period (2012–2026)

| Hold | Sharpe | CAGR | WR | Avg/trade | MaxDD | Beta | N |
|---|---|---|---|---|---|---|---|
| 5d  | 0.346 | 5.50% | 51.0% | +0.172% | 71.1% | 0.94 | 8,698 |
| 10d | 0.546 | 10.36% | 52.8% | +0.443% | 53.9% | 0.99 | 5,753 |
| **20d** | **0.607** | **11.68%** | 55.0% | +0.976% | 56.9% | 1.05 | 3,785 |

### OOS (post-2022)

| Hold | Sharpe | CAGR | WR | Avg/trade | MaxDD | Beta | N |
|---|---|---|---|---|---|---|---|
| 5d  | 0.332 | 5.10% | 50.8% | +0.259% | 30.9% | 0.87 | 2,631 |
| **10d** | **0.583** | **12.10%** | 52.1% | +0.553% | 28.6% | 0.92 | 1,716 |
| 20d | 0.496 | 9.14% | 51.6% | +1.031% | 27.5% | 0.94 | 1,105 |

**The drift exists per-trade** (positive avg trade, WR > 51%, monotonically rising avg-return with hold length — classic Bernard-Thomas signature) **but the portfolio Sharpe is capped ~0.58 because the book is essentially long-equity beta** (β 0.9–1.05). It does not beat SPY on a risk-adjusted basis and underperforms SPY on CAGR.

---

## 3. Surprise-magnitude × hold sweep (does a tighter signal clear the gate?)

OOS, long-only, 30-position book:

| Config | Sharpe | CAGR | WR | Avg/trade | Beta | MaxDD | N |
|---|---|---|---|---|---|---|---|
| s>5%  H10 | 0.583 | 12.10% | 52.1% | +0.553% | 0.93 | 28.6% | 1,716 |
| s>10% H10 | 0.633 | 13.46% | 51.6% | +0.461% | 0.93 | 34.0% | 1,569 |
| **s>15% H10** | **0.757** | **17.34%** | 51.8% | +0.609% | 0.88 | 33.7% | 1,358 |
| s>5%  H20 | 0.496 | 9.14% | 51.6% | +1.031% | 0.94 | 27.5% | 1,105 |
| s>10% H20 | 0.615 | 12.28% | 50.5% | +0.802% | 0.94 | 26.2% | 989 |
| s>15% H20 | 0.440 | 7.91% | 50.1% | +0.508% | 0.98 | 26.6% | 896 |

Only **s>15% / H10 clears 0.70 (0.757)**. But it is a **fragile, post-hoc-selected corner**: its immediate neighbours (s>15% H20 = 0.44, s>10% H10 = 0.63) are far below the gate, and at +15% it is no longer a "small/mid PEAD" so much as a momentum-on-extreme-beats long book riding β 0.88. Not a robust plateau → not a credible single config to promote.

---

## 4. THE DECISIVE TEST — beta hedge (is any of this idiosyncratic drift?)

Subtract `β × SPY_return` from the daily book (β estimated in-window) and re-measure. Also regress daily book return on SPY to extract the annualized **alpha** intercept and its t-stat:

| OOS config | Raw Sharpe | **Hedged Sharpe** | β | **Ann. alpha** | **t(alpha)** |
|---|---|---|---|---|---|
| s>5%  H10 | 0.583 | **0.14** | 0.93 | +2.71% | **0.3** |
| s>10% H10 | 0.633 | **0.24** | 0.93 | +5.03% | **0.5** |
| s>15% H10 | 0.757 | **0.39** | 0.88 | +8.92% | **0.8** |

**Across the board, hedging the market beta collapses the strategy to ~0.0–0.4 Sharpe, and the idiosyncratic alpha is statistically insignificant (every t < 1.0, vs the ~2.0 needed for significance).** Over 4.5 OOS years the small/mid long-PEAD book has **no reliably-positive return that is independent of simply being long equities.** The full-period hedge is even worse (Sharpe −0.05 to −0.24). This is the core finding: **the small/mid "PEAD edge" in a liquid, fillable universe is market beta dressed up as drift.**

---

## 5. Comparison vs prior mega-cap PEAD

| Result | Universe | OOS Sharpe (best) | Idiosyncratic alpha? |
|---|---|---|---|
| `PEAD_MARKETNEUTRAL_20260620` (long-only large-cap) | mega/large, n_est≥8 | 0.61–0.67 | short side negative; long = β~1.0 |
| `PEAD_MIDLARGE_20260604` (price-reaction proxy) | liquid mid/large | FP-cont 0.93, never beats BH-SPY | near-miss, beta-driven |
| **THIS — small/mid, EPS-surprise, $5–100 / $5–200M ADV** | **small/mid** | **0.58 @ pre-committed +5%; 0.76 only at cherry-picked +15%** | **insignificant (t 0.3–0.8)** |

**Answer to "is small/mid materially better?": NO.** At the honest pre-committed config it is ~the same 0.58 vs the mega-cap 0.59–0.67, and the beta-hedged alpha is indistinguishable from zero. The literature's 3× small-cap drift premium is **real but lives below our liquidity floor** — in micro-caps (price < $5, ADV < $5M) with no analyst coverage that we deliberately excluded as unfillable, and which **this desk already rejected at FP-cont Sharpe −0.34** (`reports/EVENT_HARNESS_20260602T053933Z.md`). The tradeable, liquid slice of small/mid does not carry it.

---

## 6. Gate scorecard

| Gate | Threshold | Pre-committed (+5% / best hold) | Pass? |
|---|---|---|---|
| OOS Sharpe | ≥ 0.70 | 0.583 (10d) | ❌ |
| OOS N trades | ≥ 50 | 1,716 | ✅ |
| (diagnostic) beta-hedged OOS Sharpe | > 0 meaningfully | 0.14 | ❌ |
| (diagnostic) idiosyncratic alpha t-stat | ≥ ~2 | 0.3–0.8 | ❌ |

**Only the trade-count gate passes.** The Sharpe gate fails at the pre-committed config; it is met only at a single non-robust +15%/10d corner that does not survive a beta hedge. **Disposition: REJECT for promotion. No paper candidate.**

---

## 7. Honest limitations / what would change the verdict

- **No paid point-in-time analyst-revision feed.** Surprise = (actual − consensus)/|consensus| from the Nasdaq snapshot in earnings.db; the consensus is the latest stored value, which for historical rows risks mild restatement contamination. This is a known, disclosed power-limitation (it adds noise, doesn't create a long-only beta) — it does not manufacture the beta-1 behaviour that is the actual reason for rejection.
- **Liquidity floor excludes microcaps by design.** The genuine 3× drift is a microcap phenomenon; we cannot fill it (prior −0.34 reject). If the desk ever accepts microcap-illiquid fills (it shouldn't at this capital), that lane could be revisited — but that is a different, already-rejected universe.
- **Equal-weight 30-position cap.** A surprise-weighted or vol-targeted sizing was not exhaustively tuned; given the beta-hedged alpha is insignificant (t<1), sizing tweaks cannot rescue a signal whose idiosyncratic component is ~zero.
- **Entry at next-day open is conservative-correct** (gap already public); using the *announcement-day close* instead would re-introduce part of the initial-reaction return and inflate the result with information not tradeable at our entry — deliberately avoided.

**What would flip it:** a beta-hedged (or dollar-neutral vs a small/mid index) version showing ann-alpha t ≥ 2. The data here says that does not exist in the liquid small/mid slice.

---

## Artifacts
- `strategies_candidates/pead_smallmid/backtest_pead_smallmid.py` — main backtest
- `strategies_candidates/pead_smallmid/sweep_pead_smallmid.py` — surprise×hold×hedge sweep
- `strategies_candidates/pead_smallmid/_alpha_check.py` — beta/alpha OLS diagnostic
- `strategies_candidates/pead_smallmid/backtest_results.json`, `sweep_results.json`
- Bars cached under `data_cache/yahoo/` (1,607 small/mid symbols pulled this run)
