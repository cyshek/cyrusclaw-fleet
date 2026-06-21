# Reddit Mention-Momentum SHORT — Pre-Registered Clean-Test
**Date:** 2026-06-21 · **Author:** trading-bench (subagent) · **Status:** ❌ DEBUNKED

## TL;DR
The H2′ result — *"short liquid large-caps on WSB velocity spike: Sharpe 4.0 / OOS 2.8 / 74% WR"* — **does NOT survive a pre-registered mechanical filter.** Replacing the hand-picked exclusion list with a numeric universe rule defined *before* looking at returns:

- **Full period, 3-day hold (the H2′ canonical hold): Sharpe 0.04, WR 46.8%, t-stat −0.25, equity ×0.40 (loses money).**
- **OOS (2023+), 3-day hold: Sharpe −1.14, WR 43.2%, t-stat −1.72 — significantly NEGATIVE.**
- Even **gross of all costs/borrow**, the clean short is Sharpe 0.14 / 47% WR / +0.01% per trade — **no edge exists.** Costs and borrow are *not* what kills it.
- The famous **"SPY 26/26 = 100% win"** claim collapses to **13/39 = 33% WR** under the clean engine.

**The entire H2′ "edge" was in-sample name selection** — the hand-picked list excluded exactly the names that lose when shorted (TSLA is the single biggest loser: −0.90 cumulative over 47 trades). A mechanical filter that can't peek at which names blew up keeps TSLA/GME/AMC (most of their spike-days pass the numeric thresholds) and the strategy goes flat-to-negative.

**Recommendation: do NOT pursue paper-short capability for this signal.** There is no real short edge in Reddit mention-momentum once you can't cherry-pick the universe.

---

## 1. Pre-Registered Mechanical Universe Filter (defined once, applied blindly)

Evaluated on each signal day **D** using **only data through D** (no lookahead):

1. **Price on signal day ≥ $10** — filters penny stocks / low-float.
2. **30-day average daily volume ≥ $50M notional** — ADV = mean(close × volume) over the 30 trading days ending at D.
3. **Market cap ≥ $5B** — large-cap only. Computed as `shares_outstanding × price` using **SEC EDGAR point-in-time** shares (`dei/EntityCommonStockSharesOutstanding`, latest value *filed ≤ D*). Where shares are unavailable (ETFs, missing CIK), **fall back to the price+ADV proxy** per task spec (rules 1&2 stand in; the proxy never rejects beyond them — documented, non-additive).
4. **NOT short-squeeze-prone: 30-day realized vol < 100% annualized** — realized vol = std(daily log returns, 30d) × √252. This **mechanically captures the meme/squeeze names without naming any ticker** (GME, AMC, BBBY etc. run 150–250% annualized vol during their spikes).

**No hand-picked ticker list appears anywhere in the engine.** The only way a name leaves the universe is by failing a numeric threshold above. (Code: `reddit_short_cleantest.py`.)

### Signal & execution (frozen, identical to H2′)
- **Signal:** velocity = mention_count ÷ (20-day trailing mean); fire if velocity ≥ 2.0 **AND** mention_count ≥ 5.
- **Entry:** SHORT at next-day **OPEN** (short return positive when price falls).
- **Hold:** close on day+H. Sweep H ∈ {1, 3, 5, 10}.
- **Cost:** 4 bps one-way (8 bps round-trip) **+ 50 bps/yr borrow** accrued over the hold (≈0.6 bps for a 3-day hold).
- **Sizing:** equal weight, max 10 concurrent shorts; same-day overflow → take highest velocity.
- **Prices:** Yahoo v8 daily, split+dividend-adjusted (`runner.daily_bars_cache`). Entry uses the adjusted open, exit the adjusted close, so a split/dividend inside the hold window can't fabricate PnL.

---

## 2. Full Performance Table

### Full period (2020-01-07 → 2024-03-22) — **FILTERED** (pre-registered)
| Hold | Trades | Win% | Sharpe | t-stat | Avg/trade | CAGR | MaxDD | Equity |
|-----:|-------:|-----:|-------:|-------:|----------:|-----:|------:|-------:|
| 1d  | 698 | 50.6% | **0.76** | 0.57 | +0.12% | +9.7% | −58% | ×1.59 |
| 3d  | 603 | 46.8% | **0.04** | −0.25 | −0.08% | −16.7% | −83% | ×0.40 |
| 5d  | 541 | 46.4% | **−0.02** | −0.31 | −0.12% | −27.0% | −93% | ×0.21 |
| 10d | 427 | 47.8% | **0.06** | −0.24 | −0.13% | −24.2% | −94% | ×0.25 |

### Full period — **UNFILTERED** (every velocity spike, incl. squeeze names)
| Hold | Trades | Win% | Sharpe | t-stat | Avg/trade | CAGR | MaxDD | Equity |
|-----:|-------:|-----:|-------:|-------:|----------:|-----:|------:|-------:|
| 1d  | 949 | 51.8% | 1.72 | 2.61 | +0.89% | +95% | −68% | ×28.2 |
| 3d  | 801 | 49.9% | 0.70 | 1.77 | +0.87% | +29% | −90% | ×3.55 |
| 5d  | 700 | 48.0% | 0.53 | 1.64 | +0.85% | +13% | −93% | ×1.85 |
| 10d | 518 | 48.6% | 0.15 | 0.23 | +0.17% | −51% | −99.8% | ×0.03 |

> **The unfiltered short scores *higher* than the filtered one.** Shorting the squeeze names on their spike day (enter next open, hold 1–3d) was net positive *in this sample* — but that's the uncapped-loss tail (a single GME-style rip the other way wipes you out; MaxDD −68→−99.8%), it isn't a stable edge (t-stat fades to 0.23 by 10d), and it's exactly the exposure a "liquid large-cap only" thesis claims to avoid. The clean filter strips out precisely the names that produced the (illusory) H2′ numbers.

### OOS 2023+ (2023-01-01 → 2024-03-22) — **FILTERED** ← the cleanest cut
| Hold | Trades | Win% | Sharpe | t-stat | Avg/trade | CAGR | MaxDD | Equity |
|-----:|-------:|-----:|-------:|-------:|----------:|-----:|------:|-------:|
| 1d  | 290 | 47.9% | **−0.58** | −0.61 | −0.17% | −20% | −45% | ×0.64 |
| 3d  | 250 | 43.2% | **−1.14** | −1.72 | −0.72% | −48% | −70% | ×0.27 |
| 5d  | 221 | 43.4% | **−1.06** | −1.48 | −0.78% | −59% | −85% | ×0.17 |
| 10d | 167 | 44.3% | **−0.06** | −0.59 | −0.48% | −31% | −70% | ×0.48 |

### OOS 2023+ — **UNFILTERED**
| Hold | Trades | Win% | Sharpe | t-stat | Avg/trade | Equity |
|-----:|-------:|-----:|-------:|-------:|----------:|-------:|
| 1d  | 358 | 49.7% | 0.60 | 0.55 | +0.17% | ×1.11 |
| 3d  | 302 | 45.4% | 0.15 | 0.14 | +0.07% | ×0.72 |
| 5d  | 259 | 44.8% | 0.08 | 0.50 | +0.34% | ×0.64 |
| 10d | 181 | 49.2% | 0.40 | 0.51 | +0.60% | ×1.51 |

### Year-by-year (hold = 3d, filtered)
| Year | Trades | Win% | Sharpe | t-stat | Avg/trade | Equity |
|-----:|-------:|-----:|-------:|-------:|----------:|-------:|
| 2020 | 193 | 46.1% | −0.80 | −1.21 | −0.70% | ×0.26 |
| 2021 | 101 | 49.5% | +1.47 | 1.80 | +1.28% | ×1.82 |
| 2022 |  42 | 61.9% | +3.64 | 1.24 | +2.01% | ×2.40 |
| 2023 | 188 | 44.7% | −1.40 | −1.42 | −0.69% | ×0.31 |
| 2024 |  58 | 34.5% | −0.90 | −1.25 | −1.11% | ×0.79 |

> Only **2021–2022 are positive**, and **2022 (Sharpe 3.6) is a 42-trade thin-data fluke** with t-stat just 1.24 (not significant) — that's also the year the mention DB is sparsest (62 distinct days). The high-sample years that matter — **2020 (193 trades), 2023 (188 trades), 2024 — are all clearly negative.** This is the signature of a non-edge: it "works" only in the thin, noisy windows and loses where you have enough data to measure it.

---

## 3. Cost / Borrow / Gross Sensitivity (hold = 3d, full, filtered)
| Variant | Sharpe | Win% | Avg/trade | Equity |
|---|---:|---:|---:|---:|
| With 8bps round-trip + 50bps/yr borrow (headline) | 0.04 | 46.8% | −0.08% | ×0.40 |
| Zero borrow (costs only) | 0.04 | — | — | ×0.41 |
| **Gross (zero cost, zero borrow)** | **0.14** | **47.5%** | **+0.01%** | — |

**Borrow over a 3-day hold ≈ 0.6 bps/trade — negligible.** Even fully gross, the clean short is Sharpe 0.14 with a coin-flip win rate. **Transaction costs and borrow are not what break it — there is simply no underlying edge** once the universe is mechanical.

---

## 4. How much did the filter change the results vs the hand-pick?

| Universe rule | Signals passed | Pass rate |
|---|---:|---:|
| Raw velocity-spike signals | 1,277 | 100% |
| **Pre-registered mechanical** | **880** | **68.9%** |
| Original hand-picked exclusion (H2′) | 720 | 56.4% |

The two filters are **not nested** — they remove *different* names:
- **Mechanical KEEPS** (hand-pick dropped): **GME, AMC, BB, CLOV, SPCE, TSLA** — because on most of their signal days they pass price/ADV/mcap and (outside the very peak) realized-vol < 100%. The realized-vol gate only clips the single most extreme days.
- **Mechanical DROPS** (hand-pick kept): AAL, QQQ, NOK, SMCI, SOUN, OXY, GLD, JNUG, ULTA, RKLB, FOX, KIM, BRK — mostly on ADV/mcap/price thresholds.

EDGAR point-in-time market cap resolved for **897/1,224 (73%)** of evaluated signals; the rest (ETFs like SPY/QQQ/SLV, plus names with no clean shares concept) used the price+ADV proxy.

### Filter rejection breakdown (signals failing each rule; non-exclusive)
- realized-vol ≥ 100%: 275 · market-cap < $5B: 225 · price < $10: 132 · ADV < $50M: 122 · no price data: 31

### The smoking gun — per-ticker contribution (hold=3, filtered)
**Biggest losers are the high-sample-size names you can't avoid mechanically:**
`TSLA −0.90 (47 trades, 45% WR)` · `SPCE −0.41 (13)` · `BILL −0.38 (14)` · `NVDA −0.30 (26, 42%)` · `AAPL −0.30 (27, 30%)`.

**"Winners" are tiny-N flukes:** `SOFI +0.65 (6 trades, 100% WR)` · `MRNA +0.39 (3)` · `INTC +0.37 (6)` · `DOC +0.31 (1 trade!)`.

The hand-picked H2′ list specifically removed the high-N losers (TSLA via the meme exclusion) and what remained looked like a 74% WR machine. **That is textbook in-sample selection.** Under a mechanical rule, the unavoidable large-cap shorts (TSLA, NVDA, AAPL) drag the book negative.

---

## 5. Honest Verdict

- **Does Sharpe ≥ 1.0 OOS survive the pre-registered filter?** **No.** OOS 2023+ is Sharpe **−1.14** (3d), **−1.06** (5d), **−0.58** (1d). Not a single OOS hold reaches +1.0; the best is +0.0 (10d, t = −0.59). The claimed OOS 2.8 was an artifact of the hand-picked universe.
- **Is the full-period Sharpe 4.0 real?** **No.** Clean full-period 3d Sharpe is **0.04** (t = −0.25). The "4.0" required excluding the names that lose.
- **How much did the filter change results?** It **erased the edge entirely** — from a claimed Sharpe 4.0/2.8 to ~0/negative. The hand-pick wasn't a liquidity filter; it was a (look-ahead) loser-removal filter worth ~all of the apparent alpha.
- **Is the *direction* right (fade WSB spikes)?** Weakly, and only at **1-day** hold (full Sharpe 0.76, but t = 0.57 → not significant, and OOS it's −0.58). The 1-day result is the only non-embarrassing number and it does not replicate OOS.

### Is this worth pursuing further (getting short capability on paper)?
**No — not for this signal.** Building paper-short plumbing to trade Reddit mention-momentum has no expected edge: the clean backtest is flat-to-negative gross *and* net, in-sample *and* OOS, across every hold period, with the only positive pockets being thin-data flukes (2022, n=42) that vanish in the high-sample years. Short capability may be worth building for *other* strategies, but **this signal is not the justification.** Reddit mention-momentum — long (prior report: Sharpe −0.67) or short (this report) — is a confirmed non-edge.

---

## Appendix — Reproduce
```
python3 reddit_short_cleantest_run.py        # writes _reddit_short_cleantest_result.json
```
- Engine: `reddit_short_cleantest.py` (mechanical filter + short backtest, no ticker lists)
- Driver: `reddit_short_cleantest_run.py` (all cuts, sensitivities, universe comparison)
- Raw results: `_reddit_short_cleantest_result.json`
- Prices: `runner/daily_bars_cache.py` (Yahoo v8, split+div adj) · Mcap: SEC EDGAR PIT shares (`data_cache/edgar_shares/`)

**Caveat (documented):** Yahoo's v8 `close` is itself split-adjusted, so the $10 price floor is applied on a split-adjusted basis for names that split *after* the signal date. Impact is conservative and immaterial here — squeeze exclusion is carried by the realized-vol and market-cap gates (e.g. GME on 2021-01-25 is cut by rvol 210% and mcap $1B regardless of the price field), and no marginal name's pass/fail hinges on the price rule alone.
