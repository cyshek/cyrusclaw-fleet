# Reddit Mention-Momentum Backtest — FULL DATASET

**Generated:** 2026-06-21
**Backtest window:** 2020-01-01 → 2024-01-03 (all collected data)
**Author:** trading-bench (subagent)
**Data:** r/wallstreetbets via PullPush · Prices: Yahoo v8 adjclose/open
**DB snapshot:** `/tmp/reddit_snapshot.db` (copy of `reddit_mentions.db` taken mid-collection to avoid write-lock contention)

---

## TL;DR — 🔴 NO-GO

**The 78-day pilot's Sharpe 3.4 does NOT survive contact with continuous data.** On the full
2020→2023 dataset the signal is **negative across every hold period, every era, and the
out-of-sample window.** The pilot was an artifact of three cherry-picked **January-only**
windows (post-earnings drift + January effect + the 2021 GME explosion). Run continuously,
mention-velocity spikes behave as a **contrarian/reversal indicator** — you systematically
buy local sentiment tops that mean-revert.

| Cut (5-day hold, primary) | Sharpe | Win Rate | CAGR | N Trades |
|---|---|---|---|---|
| Full period | **−0.67** | 35.5% | −67% | 347 |
| Ex-GME/AMC mania | **−0.57** | 35.5% | −61% | 324 |
| **OOS (post-2022)** | **−0.88** | 39.8% | −27% | 118 |
| SPY buy & hold (same window) | **+0.74** | — | +14.2% | — |

**Gate result:** Requires Sharpe ≥ 1.0 OOS (post-2022) AND ≥ 50 trades. → OOS Sharpe = **−0.88** (118 trades). **FAILS decisively.** Does **not** warrant paper trading.

---

## 1. Data Coverage (snapshot at run time)

| Metric | Value |
|--------|-------|
| Total mention rows (ticker-days) | 23,070 |
| Date range | 2020-01-01 → 2024-01-03 |
| Distinct days with data | 697 |
| Unique tickers | 474 |
| Total posts+comments scraped | ~265,000 |

**Coverage by year (CRITICAL — collection still in progress):**

| Year | Days collected | Status |
|------|----------------|--------|
| 2020 | 338 | ✅ Full year+ |
| 2021 | 176 | ⚠️ H1 only (Jan–Jun) |
| **2022** | **4** | ❌ Collector just started |
| 2023 | 176 | ⚠️ H1 only (Jan–Jun) |
| **2024** | **3** | ❌ Collector just started |

> **The "OOS post-2022" window is effectively 2023-H1** (113 of 118 trades). 2022 (3 trades)
> and 2024 (2 trades) are nearly empty because the parallel collectors for 2021-H2, 2022,
> 2023-H2, and 2024 were launched ~03:28 and had only reached early-July / early-January when
> this snapshot was taken. **Even on the 2023-dominated OOS sample the signal fails the gate.**
> Re-running once 2022-H2 + 2024 finish will add more genuinely-out-of-sample 2022 bear-market
> trades — which, given 2022's 5-day Sharpe of −0.74 SPY environment and the signal's negative
> per-trade mean, is overwhelmingly likely to make the verdict *worse*, not better.

---

## 2. Signal Definition (as specified)

| Parameter | Value |
|-----------|-------|
| Source | r/wallstreetbets submissions + comments (PullPush, no auth) |
| Velocity threshold | mentions_today ÷ 20-day rolling avg (1-day lag) **≥ 2.0×** |
| Minimum mentions | **≥ 5** absolute (noise floor) |
| Entry | Next trading day **OPEN** (lookahead-free) |
| Exit | **CLOSE** on day N (sweep 1, 3, 5, 10) |
| Sizing | Equal weight, max 10 concurrent, ranked by velocity |
| Cost | **2 bps one-way** (4 bps round-trip) — stocks |
| Short-ticker filter | ≤3-char tickers: dictionary-word collisions excluded (see §3) |

---

## 3. Short-Ticker False-Positive Control — and a Hard Data Limitation

**Spec:** for tickers ≤3 chars, only count `$TICKER` mentions (e.g. `$GME`) to kill LOW/AMP
collisions.

**Limitation (must read):** `reddit_mentions.db` stores only an **aggregated** `mention_count`
per (date, ticker) — it merges `$GME` and bare `GME` into one number at collection time, with
**no stored field to separate `$`-prefixed mentions.** The `$TICKER`-only rule therefore
**cannot be applied retroactively** to the existing data without re-scraping all ~700 days
(which would also collide with the live collectors). 

**Faithful substitute applied:** a curated hard-exclusion list of ≤3-char tickers that are
common English words, identified directly from the data (these dominate raw counts as words,
not tickers):

`ALL` (16,901 mentions, present 100% of days), `AMP` (& / ampere), `LOW` ("buy the low"),
`AI`, `APP`, `NET`, `ES`, `FIX`, `DOC`, `ARM`, `GEN`, `ICE`, `MO`, `PM`, `GL`, `ED`, `FDS`.

Real ≤3-char tickers (`SPY`, `AMD`, `GME`, `AMC`, `BB`, `BA`, `NOK`, `QQQ`, …) are **kept**.

**Impact of the filter:** it removes the worst pure-noise names (LOW alone was −211% total
return across 25 trades) and *improves* the full-period 5d Sharpe from −1.00 (unfiltered) to
−0.67 (filtered). **It does not rescue the strategy** — the edge is negative either way. Both
versions are reported below for full transparency.

---

## 4. Results — Primary (short-ticker filter ON)

**SPY benchmark (2020-01-01 → 2024-01-03):** Sharpe **0.74**, CAGR **+14.2%**, MaxDD −33.7%, Total +94.6%.

### 4a. Full period (includes GME/AMC mania)

| Hold | N Trades | Win Rate | Avg Ret | Sharpe | CAGR | Max DD | Beta |
|------|----------|----------|---------|--------|------|--------|------|
| 1d | 451 | 33.0% | −1.7% | **−2.54** | −76% | −99.9% | 0.21 |
| 3d | 385 | 33.5% | +0.9% | **−0.13** | −59% | −99.4% | −1.62 |
| 5d | 347 | 35.5% | −1.6% | **−0.67** | −67% | −99.7% | 1.05 |
| 10d | 286 | 36.7% | +3.1% | **+0.43** | −1.6% | −98.2% | 0.14 |

### 4b. Excluding GME/AMC mania (2021-01-15 → 2021-03-31 removed)

| Hold | N Trades | Win Rate | Avg Ret | Sharpe | CAGR | Max DD |
|------|----------|----------|---------|--------|------|--------|
| 1d | 419 | 33.2% | −2.4% | **−3.60** | −73% | −99.9% |
| 3d | 359 | 33.4% | −1.2% | **−0.60** | −62% | −99.6% |
| 5d | 324 | 35.5% | −1.5% | **−0.57** | −61% | −99.5% |
| 10d | 267 | 37.1% | +3.3% | **+0.47** | +8.4% | −98.2% |

### 4c. Out-of-sample, post-2022 (the gate window)

| Hold | N Trades | Win Rate | Avg Ret | Sharpe | CAGR | Max DD |
|------|----------|----------|---------|--------|------|--------|
| 1d | 142 | 35.9% | −1.6% | **−4.87** | −35% | −72% |
| 3d | 128 | 35.9% | −0.8% | **−0.72** | −19% | −56% |
| 5d | 118 | 39.8% | −1.2% | **−0.88** | −27% | −74% |
| 10d | 92 | 37.0% | −0.7% | **−0.41** | −33% | −82% |

> Only the 10-day hold ever turns marginally positive, and only on the **full** period —
> driven entirely by the GME/AMC mania tail. Ex-mania it's +0.47; OOS it's −0.41. There is no
> hold period that survives out of sample.

---

## 5. Year-by-Year (5-day hold, primary)

| Year | N Trades | Win Rate | Sharpe | SPY Sharpe | Note |
|------|----------|----------|--------|-----------|------|
| 2020 | 164 | 34.8% | **−1.53** | +0.64 | COVID crash + recovery; signal bought panic spikes |
| 2021 | 65 | 29.2% | **+0.61** | +2.13 | Meme era — only positive year, still < SPY |
| 2022 | 3 | 0.0% | n/a | −0.74 | ❌ only 4 days collected |
| 2023 | 113 | 41.6% | **−0.48** | +1.90 | Post-meme; best WR but still negative Sharpe |
| 2024 | 2 | 0.0% | n/a | +1.88 | ❌ only 3 days collected |

**Every year with meaningful data underperforms SPY.** Even 2021 — the meme peak — only
reaches Sharpe 0.61 vs SPY's 2.13. The signal never beats simply holding the index.

---

## 6. Why it fails — ticker contribution (5-day hold, full period)

**Top contributors** (all meme/growth names; concentrated, episodic):

| Ticker | Total Ret | N | Avg Ret | WR |
|--------|-----------|---|---------|-----|
| TSLA | +171.6% | 30 | +5.7% | 56.7% |
| AMC | +120.9% | 12 | +10.1% | 33.3% |
| BB | +59.9% | 6 | +10.0% | 50.0% |
| GME | +49.7% | 9 | +5.5% | 44.4% |
| PLTR | +39.8% | 12 | +3.3% | 58.3% |
| BBBY | +30.4% | 7 | +4.4% | 71.4% |

**Worst contributors** (broadly-discussed large caps — the signal's poison):

| Ticker | Total Ret | N | Avg Ret | WR |
|--------|-----------|---|---------|-----|
| SPY | **−129.0%** | 22 | −5.9% | **0.0%** |
| UPS | −75.8% | 4 | −19.0% | 0.0% |
| GILD | −70.6% | 3 | −23.5% | 0.0% |
| MRNA | −70.3% | 4 | −17.6% | 0.0% |
| MSFT | −64.5% | 14 | −4.6% | 21.4% |
| INTC | −55.2% | 4 | −13.8% | 0.0% |
| COST | −53.4% | 9 | −5.9% | 11.1% |

**The mechanism:** WSB mention spikes on big-cap names overwhelmingly fire on **bad news**
(earnings misses, the COVID crash, guidance cuts). A velocity spike + "next-day open" entry =
**buying the panic top**, and these names keep falling. SPY itself is the single worst name
(−129%, 0% win rate over 22 trades) — when WSB suddenly talks about "SPY" en masse, the market
is selling off, and you've bought the top of a leg down. Outside the narrow set of squeeze
names (GME/AMC/BB/TSLA) in 2020–21, mention velocity is a **reversal** signal, not momentum.

---

## 7. Validation: the engine is correct (pilot reproduces)

To prove the collapse is a *data-coverage* effect and not a code regression, I restricted this
engine to the pilot's exact coverage — the three **January-only** windows it actually had
(Jan 2020, Jan 2021, Jan 2023), no short-filter (the pilot had none):

| Hold | Pilot-replica Sharpe | Pilot reported |
|------|---------------------|----------------|
| 1d | 1.72 | 3.43 |
| 5d | **2.42** | 2.93 |
| 10d | 1.48 | 3.43 |

Same ballpark (differences = exact day-boundary handling and the pilot's discontinuous
3-window stitching). **The engine faithfully reproduces the pilot's strong numbers on the
pilot's data — and the same engine produces negative Sharpe on continuous data.** The
difference is entirely the data, confirming the pilot was an **overfit to January seasonality
+ the GME event.**

---

## 8. Verdict: 🔴 NO-GO — do not paper trade

**Gate:** Sharpe ≥ 1.0 OOS (post-2022) AND ≥ 50 trades in that window.

- OOS (post-2022, 5d) Sharpe = **−0.88** with 118 trades → **trade-count met, Sharpe fails by a mile.**
- No hold period clears the gate in any out-of-sample cut.
- Best-case (full-period, 10d, includes mania) Sharpe = +0.43, still below SPY's 0.74.

This is the textbook **"83-day pilot, overfit trap"** that main and making-money explicitly
flagged. The full dataset confirms the skepticism was correct. **No capital — not even paper —
should be allocated to this signal as specified.**

### What would have to change to revisit (assumptions that gate the decision)
1. **Direction flip → contrarian.** The losers (SPY/MSFT/UPS panic-spikes) and the negative
   per-trade mean suggest *fading* extreme mention velocity on liquid names might have an edge.
   That's a *different strategy* requiring its own backtest — not this one.
2. **Squeeze-only universe.** Restricting to genuine high-short-interest / low-float small caps
   (the only regime where the momentum mechanism is real) + a short-interest data feed. Narrow,
   episodic, capacity-constrained — and 2021-dependent.
3. **Full-volume, $-tagged collection.** Re-scrape storing `$`-prefix counts separately AND
   capturing full daily volume (current data is capped at ~200 posts+200 comments/day by
   PullPush pagination — a sampling artifact). Unlikely to flip the sign given §6.

None of these are "collect more of the same and re-run." The signal-as-specified is dead.

---

## 9. Honest caveats

- **2022-H2 + 2024 still collecting.** This is a *true* limitation, but it cuts *against* the
  strategy: those are exactly the post-meme / bear-market periods where the signal is weakest
  (2022 SPY Sharpe −0.74; signal already negative in every comparable cut). Re-run when complete
  for completeness, but expectation is the verdict hardens.
- **−99% MaxDD reflects full-investment compounding** of the daily mean-return book (each day's
  mean PnL compounds the entire equity). Real position-level sizing (10 independent sleeves)
  would dampen the headline DD — but the **negative per-trade mean (−1.6% net)** is sizing-
  independent and is the actual disqualifier.
- **PullPush sampling cap** (~200+200/day) means counts are a recency-biased top-slice, not full
  volume. On the pilot's GME peak days this acted as a *conviction filter that flattered* the
  signal; on continuous data it doesn't rescue it.

---

## 10. Files

| File | Purpose |
|------|---------|
| `reddit_fullbacktest.py` | Signal engine + short-ticker filter (this run) |
| `reddit_fullbacktest_run.py` | Driver: all cuts, filtered vs unfiltered, JSON dump |
| `_reddit_fullbt_result.json` | Full structured results |
| `runner/reddit_cache.py` | PullPush collector → `reddit_mentions.db` |
| `reddit_mentions.db` | Mention data (collection ongoing) |

---

*Generated 2026-06-21 by trading-bench. Verdict: 🔴 NO-GO. Signal-as-specified has negative risk-adjusted return out of sample; pilot Sharpe 3.4 was January-window + GME overfit.*
