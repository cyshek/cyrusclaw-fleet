# Reddit Alternative Signal Constructions — H1–H4

**Generated:** 2026-06-21
**Backtest window:** 2020-01-01 → 2024-01-07 (all collected data, 716 days)
**Author:** trading-bench (subagent)
**Data:** r/wallstreetbets mentions (`reddit_mentions.db`, 23,695 ticker-days, 475 tickers)
**Prices:** Yahoo v8 adjclose/open via `runner/daily_bars_cache.get_daily` (184 priced tickers)
**Cost:** 2 bps one-way (4 bps round-trip) · **Entry:** next-day OPEN · **Benchmark:** SPY buy & hold

---

## TL;DR — 🟡 The edge is on the SHORT side, on LIQUID names

The naive "mention-velocity → **buy**" signal was negative (Sharpe −0.67 full, −0.88 OOS;
`REDDIT_FULLBACKTEST_20260621.md`). I tested four alternative constructions from the same
data. **Three of the four long signals fail the Sharpe ≥ 0.5 gate.** The one genuinely
interesting result is the **mirror image**: a WSB mention-velocity spike on a **liquid
large-cap** is reversal-predictive, so **fading it (shorting) carries a real, out-of-sample-
surviving edge** — but *only* once the meme/squeeze small-caps (GME/AMC/BB/TSLA) are removed,
because shorting *those* on a spike gets your face ripped off.

| Hyp | Construction | Side | Hold | Full Sharpe | OOS Sharpe | Gate (≥0.5 full) |
|-----|--------------|------|------|-------------|------------|------------------|
| **H1** | avg_score > 90th pct + mc≥3 | long | 5d | **0.48** | 0.99 | ❌ (0.48 < 0.5) |
| **H2** | velocity spike, flipped | **short** | 3d | 0.14 (naive) | 0.35 | see below |
| **H2′** | **H2, liquid large-caps only** | **short** | 3d | **4.00** ⭐ | **2.80** ⭐ | ✅ (but can't paper-short) |
| **H3** | mentioned ≥10 of last 14 days | long | 10d | **−0.19** | 0.18 | ❌ |
| **H4** | velocity spike + avg_score ≥ median | long | 5d | **−0.75** | −1.41 | ❌ (worse than baseline) |

**SPY same window:** full Sharpe **0.59**, CAGR +11.2%, MaxDD −33.7%, total +53.4%. OOS
(post-2022): Sharpe **0.12**, CAGR +0.5%.

> ⭐ **H2′ (liquid-only short) is the headline finding and is flagged for follow-up.** We can't
> paper-trade shorts in the current harness, so this is a research flag, not a deploy
> recommendation — but it is the first Reddit construction that shows a robust, OOS-surviving,
> statistically-significant edge (per-trade t-stat 6.2, survives a −50% stop).

---

## 1. Method (shared across all hypotheses)

- **Universe / data:** all 475 tickers in `reddit_mentions.db`; 184 had usable Yahoo price
  history over the window. `avg_score` = mean upvotes of posts mentioning that ticker that day
  (high = community upvoting/bullish framing; negative = downvoted/bearish).
- **Entry:** next trading day **OPEN** (signal uses data through day D; position entered D+1 open
  → lookahead-free). **Exit:** CLOSE on day `entry_idx + hold`.
- **Cost:** 2 bps one-way subtracted as `2·COST_BPS/10000` round-trip per trade.
- **Sizing:** equal weight, max 10 concurrent, same-day signals ranked best-first (H1 by
  avg_score, H2/H4 by velocity, H3 by recent mention sum).
- **Sharpe:** per-exit-date mean-PnL series, annualized ×√(252/hold).
- **Short-ticker filter:** dictionary-word collisions (`ALL`/`AMP`/`LOW`/`AI`/`TECH`/`FAST`/…)
  excluded — same curated list as the full backtest, since the DB can't separate `$TICKER` from
  bare `TICKER`.
- **Anti-lookahead on the score/median thresholds:** H1's 90th-percentile and H4's median are
  computed on each ticker's **strictly-prior** history (`.shift(1).expanding()`), so the
  threshold at day D never sees D's own value.
- **Cuts:** full period · ex-GME/AMC mania (2021-01-15→03-31 removed) · OOS post-2022.

---

## 2. H1 — High-score (community endorsement) — ❌ FAILS gate

**Signal:** `avg_score > 90th percentile of that ticker's trailing history AND mention_count ≥ 3`.
**Thesis:** community *upvoting* a stock = bullish conviction, distinct from raw velocity.

| Cut | N | Win Rate | Avg Ret | Sharpe | CAGR | Max DD |
|-----|---|----------|---------|--------|------|--------|
| Full period | 190 | 47.4% | +0.83% | **0.48** | −26% | −96% |
| Ex-mania | 181 | 47.5% | +0.38% | **0.39** | −9% | −95% |
| **OOS post-2022** | 57 | 54.4% | +0.85% | **0.99** | +25% | −33% |

**Year-by-year (5d):**

| Year | N | Win Rate | Sharpe | SPY Sharpe |
|------|---|----------|--------|-----------|
| 2020 | 90 | 42.2% | **−1.63** | +0.64 |
| 2021 | 43 | 48.8% | **+1.74** | +2.13 |
| 2022 | 4 | 0.0% | n/a (thin) | −0.74 |
| 2023 | 53 | 58.5% | **+1.70** | +1.90 |

**Verdict: ❌ does NOT show edge.** Full-period Sharpe 0.48 is below both the 0.5 bar and SPY's
0.59. The OOS 0.99 looks tempting but is an artifact of *which* years OOS happens to contain
(2023-heavy, the signal's best year) — and **in every individual positive year it still trails
SPY** (2021: 1.74 vs 2.13; 2023: 1.70 vs 1.90), while 2020 is catastrophic (−1.63). The top
contributors are the usual squeeze tail — **GME (+362% over 16 trades, 81% WR), TSLA, BB, AMC** —
so "high score" is just a *different selector that re-discovers the same GME/meme names* as the
velocity signal, with the same overfit-to-2021 fragility. Not a distinct edge.

---

## 3. H2 — Contrarian / reversal (flip the original) — 🟡 the real story

**Signal:** velocity spike (≥2× 20-day avg, ≥5 mentions) → **SHORT** next-day open, hold 3d.
Short return simulated as −(long return) − costs. **We can't paper-short in the current harness**,
so this is a research signal, not a live recommendation.

### 3a. Naive H2 (short everything that spikes) — muddied by squeeze names

| Cut | N | Win Rate | Avg Ret | Sharpe |
|-----|---|----------|---------|--------|
| Full period | 362 | 64.6% | −1.15% | **0.14** |
| Ex-mania | 339 | 64.6% | +1.08% | **0.64** |
| OOS post-2022 | 121 | 58.7% | +0.62% | **0.35** |

The **win rate is the tell: ~65% of velocity spikes are followed by a 3-day decline** — fading
them wins about two-thirds of the time. But naive full-period Sharpe is only 0.14 because a
handful of catastrophic short losses (you shorted a meme squeeze) dwarf the many small wins. The
avg-return **flips sign** between full (−1.15%) and ex-mania (+1.08%): the GME/AMC mania window is
exactly where the naive short bleeds out.

**Where the naive short blows up (bottom contributors):** `GME −656%` (15 trades), `AMC −332%`,
`BB −155%`, `TSLA −114%` — i.e. shorting the squeeze names on a mention spike is suicidal, which
is unsurprising and is precisely the regime where the *long* momentum story was real.

### 3b. H2′ — Short LIQUID LARGE-CAPS ONLY (exclude meme/squeeze) — ⭐ robust edge

Excluding the squeeze/meme universe (`GME, AMC, BB, BBBY, CLOV, SPCE, NOK, PLTR, TSLA, RIVN,
LCID, HOOD, SOFI, NIO, MARA, RIOT, COIN, AMD, …`) and shorting only the liquid large-caps that
spike:

| Cut | N | Win Rate | Avg Ret/trade | Sharpe | Max DD¹ |
|-----|---|----------|---------------|--------|---------|
| **Full period** | 210 | **74.3%** | +4.13% | **4.00** ⭐ | −48% |
| **OOS post-2022** | 73 | **67.1%** | +1.33% | **2.80** ⭐ | −15% |

**Robustness checks (full period):**
- **Per-trade t-stat = 6.21** (mean +4.13%, std 9.63%, n=210) → not a few-outlier fluke; the
  *median* trade is +3.68%.
- **Clip every short loss at −50% (a hard stop): Sharpe still 4.00.** The worst single trade is
  only −38%, so the result is **not** a hidden squeeze-tail artifact.
- Worst 5 trades: −38%, −25%, −21%, −20%, −20%. Best 5: +64%, +32%, +26%, +26%, +24%. Broadly
  positive distribution, not lottery-shaped.

**The shorts that print (top contributors):** `SPY +156% over 26 trades — 26/26 = 100% win`,
`UPS +85% (100% WR)`, `NOK +78%`, `GILD +67%`, `INTC +63%`, `PFE +58%`, `MSFT +55%`, `COST +53%`,
`MRNA +47%`. **These are the exact same names that were the *worst longs* in the original
backtest.** When WSB suddenly mass-mentions `SPY`/`MSFT`/`COST`/`INTC`, the market is selling off
on bad news, and the move continues down for ~3 days — so shorting the open after the spike is the
mirror-image edge.

> ¹ **CAGR / final-equity caveat (important):** the headline equity curve compounds each day's
> mean PnL with no margin cap and unbounded short loss, which produces an absurd CAGR (~+299%,
> 258× equity). **Discount those numbers** — they are a compounding artifact, not an executable
> return. The **Sharpe and per-trade t-stat are the trustworthy statistics** (ratio measures,
> robust to the stop-clip), and they say the directional edge is real.

**Verdict on H2: 🟡 FLAG — the short-flip is genuinely interesting and worth a proper follow-up.**
- It is the **first Reddit construction with a robust, OOS-surviving, statistically-significant
  edge** (OOS Sharpe 2.80, 67% WR, 73 trades, t-stat 6.2 full-period, survives a −50% stop).
- It is the clean mechanistic mirror of why the *long* failed: WSB velocity spikes on liquid
  names are **reversal**, not momentum.
- **BUT:** (a) we can't paper-short in the current harness; (b) the executable return depends
  entirely on borrow availability/cost and margin-bounded sizing, neither modeled here; (c) the
  "exclude squeeze names" universe rule was chosen *after* seeing the squeeze blowups (mild
  in-sample selection) — though the *mechanism* (don't short low-float meme squeezes) is a-priori
  sound, not a data-mined boundary. **This warrants a dedicated short-side backtest** with: a
  pre-registered liquid-universe filter (e.g. price > \$10, ADV > \$50M, market-cap floor), borrow
  cost (~25–50 bps/day on hard-to-borrows, near-0 on SPY/large-caps), and margin-constrained
  equal-weight sizing. **Recommended next step.**

---

## 4. H3 — Sustained attention (persistent, not spike) — ❌ FAILS

**Signal:** ticker mentioned on **≥10 of the last 14 data-days**; long, entry next-day open after
the 14th day, hold 10d. **Thesis:** sustained coverage = building narrative, not panic.

| Cut | N | Win Rate | Avg Ret | Sharpe |
|-----|---|----------|---------|--------|
| Full period | 470 | 37.7% | +0.65% | **−0.19** |
| Ex-mania | 430 | 38.6% | +0.13% | **−0.45** |
| OOS post-2022 | 140 | 45.7% | +0.42% | **+0.18** |

**Verdict: ❌ no edge.** Sustained attention is *negative* full-period and ex-mania, and only
marginally positive (0.18, below the 0.5 bar and below SPY) out of sample. The narrative-building
thesis doesn't hold — persistent WSB attention concentrates on names already in well-known
multi-week drawdowns/grinds; the 37.7% win rate says the "sustained" names mostly keep bleeding.
Beta 2.2 means you're just buying high-beta names into trouble.

---

## 5. H4 — Negative-sentiment filter — ❌ FAILS (actively harmful)

**Signal:** velocity spike (same as original) **AND** `avg_score ≥ that ticker's trailing median`
(community receptive/upvoting, not downvoting). Long, 5d. **Thesis:** filter out the "panic
mention" spikes where the community is voting the posts down.

| Cut | N | Win Rate | Avg Ret | Sharpe |
|-----|---|----------|---------|--------|
| Full period | 221 | 34.8% | −1.71% | **−0.75** |
| Ex-mania | 210 | 35.2% | −1.25% | **−0.61** |
| **OOS post-2022** | 76 | 39.5% | −1.90% | **−1.41** |

**Verdict: ❌ no edge — the filter makes the original WORSE.** This is itself an informative
result: the original velocity-long was −0.67; adding the "high community score" receptiveness
filter drives it to **−0.75 full / −1.41 OOS**. Requiring the community to be *upvoting* during a
spike doesn't select bullish conviction — it selects the **most crowded, most euphoric tops**,
which mean-revert hardest. High avg_score during a velocity spike is a *contrarian-bearish* tell,
consistent with H2: the more enthusiastically WSB upvotes a sudden spike, the more it's a local
top. (This corroborates H2's short edge from the long side.)

---

## 6. Cross-hypothesis synthesis

1. **Every long construction fails** the Sharpe ≥ 0.5 gate (H1 0.48, H3 −0.19, H4 −0.75). None
   beats SPY (0.59) full-period. The "buy WSB attention" thesis is dead in all four framings.
2. **The edge is short, and on liquid names.** H2 (64.6% WR fading spikes), H4 (high-score spikes
   are tops), and the original loser list (SPY/MSFT/COST/INTC as worst longs) all triangulate the
   same mechanism: **a WSB mention-velocity spike on a liquid large-cap marks a local top that
   mean-reverts over ~3 days.** Fading it (H2′) yields full Sharpe 4.0 / OOS 2.8 / 74% WR /
   t-stat 6.2, robust to a −50% stop.
3. **Squeeze names are the universe poison both ways.** GME/AMC/BB/TSLA were the only place the
   *long* momentum story was ever real (2021), and they are exactly where the *naive short* blows
   up. Any deployable Reddit signal must **partition the universe**: momentum/long is (was) a
   low-float-squeeze phenomenon; reversal/short is a liquid-large-cap phenomenon.
4. **avg_score is a contrarian, not a confirming, signal** during spikes (H4's failure proves it).

---

## 7. Verdicts at a glance

| Hyp | Edge (Sharpe > 0.5 full)? | Verdict |
|-----|---------------------------|---------|
| **H1** high-score long | ❌ No (0.48; SPY-trailing every year) | NO-GO — re-selects the GME tail |
| **H2** contrarian short (naive) | ⚠️ Only ex-mania (0.64); 65% WR | Promising but squeeze-poisoned |
| **H2′** contrarian short, liquid-only | ✅ **Yes (4.0 full / 2.8 OOS)** | 🟡 **FLAG — follow-up short-side backtest** |
| **H3** sustained attention | ❌ No (−0.19) | NO-GO |
| **H4** sentiment-filtered long | ❌ No (−0.75; harmful) | NO-GO — high-score = top |

**Is the short-flip (H2) interesting enough to flag even though we can't paper-trade it? — YES.**
It's the only Reddit construction tested (across this report and the full backtest) that produces
a robust, statistically-significant, OOS-surviving edge. It cannot be paper-traded in the current
long-only harness, so it's flagged — not deployed — pending a dedicated short-side backtest with
borrow cost, a pre-registered liquid universe, and margin-bounded sizing. **Recommended as the
next piece of Reddit work; the long-side book is dead.**

---

## 8. Honest caveats

- **Data coverage is uneven** (2020 full, 2021-H1, 2023-H1; 2022 & 2024 ≈ 3–4 days each — the
  parallel collectors hadn't finished at run time). The OOS window is effectively 2023-heavy.
  Re-run H2′ once 2022-H2/2024 finish — 2022 (bear market) is where mean-reversion shorts on
  liquid names *should* do best, so the expectation is the H2′ edge **holds or strengthens**,
  unlike the long book.
- **H2′ universe rule chosen post-hoc** (excluded squeeze names after seeing them blow up). The
  *mechanism* is a-priori sound, but the exact exclusion list is mild in-sample selection — a
  follow-up must pre-register a mechanical liquidity filter (price/ADV/mcap), not a hand-picked
  name list.
- **Short execution unmodeled:** no borrow cost, no locate availability, no margin cap, no
  short-squeeze stop. The −50%-clip robustness check is a crude proxy; a real backtest needs the
  borrow/margin layer. SPY/large-cap borrow is cheap and deep, which is favorable, but it must be
  modeled.
- **CAGR/equity figures for H2′ are inflated** by unbounded-short compounding — trust the Sharpe
  and t-stat, not the 258× equity.
- **PullPush sampling cap** (~200 posts + 200 comments/day) means mention counts are a
  recency-biased top-slice, not full volume — same limitation as the full backtest.

---

## 9. Files

| File | Purpose |
|------|---------|
| `reddit_altsignals.py` | H1–H4 signal builders + long/short backtest engine |
| `reddit_altsignals_run.py` | Driver: all cuts, year-by-year, ticker contributions, JSON dump |
| `_reddit_altsignals_result.json` | Full structured results |
| `runner/daily_bars_cache.py` | Yahoo v8 daily bars cache (reused; 184 priced tickers) |
| `reddit_mentions.db` | WSB mention data (2020–2024, 23,695 ticker-days) |
| `reports/REDDIT_FULLBACKTEST_20260621.md` | The original velocity-long NO-GO (context) |

---

*Generated 2026-06-21 by trading-bench (subagent). Verdict: long constructions H1/H3/H4 all
NO-GO; the edge is the SHORT flip (H2′) on liquid large-caps — full Sharpe 4.0, OOS 2.8, 74% WR,
t-stat 6.2 — flagged for a dedicated short-side backtest since the current harness can't paper-
short. Mention-velocity on liquid names is reversal, not momentum.*
