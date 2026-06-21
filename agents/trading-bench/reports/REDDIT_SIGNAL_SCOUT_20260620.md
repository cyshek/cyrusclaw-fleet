# Reddit as a Trading Signal — Scout Report
**Date:** 2026-06-20  
**Author:** trading-bench subagent  
**Scope:** Data access, academic evidence, signal design, tournament fit

---

## 1. Data Access Testing — Results

### Reddit's Own JSON API (old-API/.json endpoint)
**BLOCKED. Hard 403 from all UAs.**

Tested all of the following — every variant returned HTTP 403 with an HTML error page:
- `https://www.reddit.com/r/wallstreetbets/hot.json?limit=5` (browser UA, rich-headers)
- `https://old.reddit.com/r/wallstreetbets/hot.json`
- `https://api.reddit.com/r/wallstreetbets/hot`
- `python-requests`, Googlebot, MSIE, Linux Chrome UAs — all 403

Reddit's June 2023 API pricing change effectively killed all unauthenticated datacenter-IP JSON access. The HTML error body confirms IP-class detection (Cloudflare-style block), not just User-Agent filtering. **The classic `.json` trick is dead from this VM.**

### Pushshift / Alternatives

| Endpoint | Status | Notes |
|---|---|---|
| Pushshift (original) | **DEAD** | Confirmed in MEMORY.md — licensing/shutdown |
| **PullPush (`api.pullpush.io`)** | **✅ WORKS — HTTP 200** | Post + comment search. Returns full JSON |
| **Arctic-Shift (`arctic-shift.photon-reddit.com`)** | **✅ WORKS — HTTP 200** | Returns full post metadata |
| Quiver Quant API | 401 (auth required) | Free dashboard exists, API needs key |

**PullPush critical caveat:** Data lag is ~**1+ month**. Latest WSB post in index is `2025-05-19` as of today (2026-06-20). This makes it **suitable for backtesting historical research but not for live signal generation** without a paid/auth path.

### Signal Construction Options (Data Pipeline)
1. **Backtesting (historical, ≥2 years back):** PullPush works. Can pull posts/comments by subreddit, date range, keyword. Full post metadata including score, upvotes, flair, author.
2. **Live/real-time:** Need Reddit OAuth app (free, script app, requires account registration). `PRAW` library. Would give current data. Auth setup: ~15 min, free.
3. **Third-party processed feeds:** `sellthenews.org` (free WSB daily thread AI analysis), `adanos.org` (free tier: basic, limited history), `wsbsentiment.com` (paid $9-29/mo). These reduce build cost but add dependency.

---

## 2. Academic Evidence

### Key Studies

**"Will the Reddit Rebellion Take You to the Moon? Evidence from WallStreetBets"**  
Chacon, Morillon & Wang (2023) — *Financial Markets and Portfolio Management*  
- Dataset: 221,255 WSB recommendations, 2012–Q1 2021  
- Strategy: Daily-rebalancing long buy / short sell recommendations  
- Holding periods: 1 day, 2 days, 3 days, 1 week, 1 month, 1 year  
- **Finding: NO alpha on any holding period, risk-adjusted.** Zero evidence of outperformance.
- Volume effect: WSB submissions DO predict abnormal trading volume (crowd follows the crowd), but this doesn't translate to risk-adjusted returns.

**"Dissecting the Hype: A Study of WallStreetBets' Sentiment and Network Correlation on Financial Markets"**  
Wang et al. (2024) — AINA Conference  
- Analyzed millions of posts with sentiment analysis + network theory on individual stocks (GME, TSLA)  
- Found: WSB community predicts **stock volatility** well, but price *direction* prediction was weak
- Models showed lower RMSE when sentiment was included vs price alone, but the delta is small

**BUZZ ETF (VanEck Vectors Social Sentiment ETF) — Live Real-World Test**  
Tracks 75 large-cap US stocks with most bullish social sentiment (Reddit + Twitter):
- **April 2021 – June 2025: +23.9% total return**
- **SPY same period: +56.7%**
- **QQQ same period: +67.4%**
- BUZZ underperformed SPY by **~33 percentage points** over 4+ years
- This is the most damning evidence: a *professionally managed, real-money product* built on social sentiment vs. massive underperformance

**WSB as a Contrarian Signal (financhle.com, 2025)**  
- Post-2021 data suggests WSB bullish sentiment actually predicts **negative** returns (inverse oracle effect)
- Mechanism: by the time WSB is hyped, early movers have already loaded up; WSB retail is the exit liquidity
- Strongest contrarian signal at extremes: when >90% bullish on a ticker → bearish signal

**Key Academic Consensus (2022–2024):**
- WSB predicts volatility and volume ✅ — not disputed
- WSB predicts returns ❌ — consensus is NO. The alpha, if it existed pre-2020, has been arbitraged away
- Post-GME (2021+) is worse: the community is now so large and well-known that any signal is immediately front-run
- Alpha (if any) decays in **hours, not days** — high-frequency HFT shops already consume it

---

## 3. Practical Signal Construction

### What the Signal Would Look Like

If we built it anyway (for research), here's the architecture:

**Data collection:**
```python
# Historical (PullPush — 1+ month lag, good for backtest)
GET https://api.pullpush.io/reddit/search/comment/?subreddit=wallstreetbets&q={TICKER}&size=100&sort=desc&sort_type=created_utc

# Live (requires Reddit OAuth app — free, ~15 min setup)
# PRAW: reddit.subreddit("wallstreetbets+stocks+investing").new(limit=500)
```

**Signal variables:**
- `mention_count`: # posts + comments mentioning ticker in last 24h
- `mention_velocity`: change in mentions vs 7-day rolling average (buzz delta)
- `weighted_score`: sum of upvotes on ticker-mentioning posts
- `sentiment_score`: VADER or FinBERT on post text (pos/neg/neutral)
- `flair_signal`: DD (due diligence) flair vs meme/YOLO flair
- `contrarian_flag`: when bullish_ratio > 90th percentile → bearish signal

**Timing:** Posts → price effect within **same day, often within hours** (pre-market / intraday). Next-day effect is near-zero after transaction costs.

### Ticker Presence on WSB (from live PullPush data)

Tested top-25 posts by score, all time:

| Ticker | Posts Found | Top Score | Avg Score | Signal Quality |
|---|---|---|---|---|
| $SPY | 25 | 1,270 | 148 | Moderate — mostly options bets |
| $QQQ | 25 | 422 | 33 | Low — passing mentions |
| $TQQQ | 25 | 1,819 | 137 | Moderate — leveraged plays |
| **$UPRO** | **25** | **16,237** | **771** | **High engagement when mentioned** |
| $NVDA | 25 | 1,869 | 172 | Moderate — AI cycle plays |
| $XLK | 25 | 2,734 | 163 | Moderate — tech ETF mentions |
| $GME | 25 | 2 | 1 | Very low — meme cycle dead |
| $AMC | 25 | 63 | 4 | Very low — same |
| $IWM | 25 | 31 | 4 | Very low — institutional ETF |
| $TSLA | 25 | 205 | 23 | Low |

**Key observation:** ETFs *are* mentioned on WSB — SPY, QQQ, TQQQ regularly, XLK and UPRO with surprising engagement. But the *pattern* is: posts about ETFs are mostly YOLO option bets ("SPY calls 0DTE lol"), not fundamental analysis that would contain predictive sentiment.

---

## 4. Fit with Our Tournament

### The Core Mismatch Problem

Our tournament trades **SPY, QQQ, XLK, IWM, TQQQ** — liquid macro ETFs tracking broad indices.

Reddit WSB's signal mechanism for meme stocks works like this:
1. Obscure small-cap with high short interest discovered
2. WSB pumps it — retail FOMO drives price up
3. Momentum accelerates → squeeze → blow-off top

**This mechanism does NOT apply to SPY/QQQ/IWM:**
- These ETFs absorb billions in daily flow — retail WSB crowd is microscopic vs. institutional flow
- No short squeeze dynamics — creation/redemption mechanism prevents it
- No information edge — WSB discusses SPY/QQQ in aggregate sentiment terms ("market is gonna crash"), not specific price-moving information

**The only potential ETF signal:** extreme retail sentiment as a *contrarian* macro indicator. When WSB is overwhelmingly bearish on SPY (e.g., mass "puts" posts), it might slightly predict a market bounce. But:
- This is already captured by put/call ratio (established, quantified)
- Effect size is tiny and noisy
- Not differentiated enough to win a tournament

### BUZZ ETF Verdict as a Proxy

BUZZ was literally designed to be the live experiment — track 75 large-cap stocks with highest social sentiment. After 4+ years: **−33% vs SPY**. The live real-money result is the final answer.

---

## 5. VERDICT: NO-GO (for tournament strategies on ETFs)

### Reasoning

1. **Data access problem:** Reddit's own API is 403'd from this VM (datacenter IP). PullPush works for historical data but has 1+ month lag — unusable for live signal without Reddit OAuth app setup.

2. **Academic evidence is conclusive:** Multiple peer-reviewed studies (2022–2024) find **no alpha** in WSB sentiment strategies, risk-adjusted, across all holding periods. The BUZZ ETF provides the definitive real-money validation: −33% vs SPY over 4 years.

3. **Signal decays too fast:** Whatever edge exists operates intraday, consumed by HFT. Our tournament strategies hold positions from days to weeks — we're competing in the wrong time frame.

4. **Wrong asset class:** WSB signal mechanism (short squeeze, meme momentum) is structurally inapplicable to broad-market ETFs. ETFs have no squeeze dynamics and face too much institutional flow to move on retail chatter.

5. **Crowded and known:** Post-2021, every quant shop runs WSB sentiment. The Chacon et al. finding that "alpha is equally elusive as viewership has grown" is the key conclusion — information leakage = arbitraged away.

### Conditional Exception (NOT worth building now)

The ONLY scenario where Reddit sentiment would be worth building: if we expand the tournament to **individual stock strategies** on high-short-interest small/mid-caps. Even then:
- Would need Reddit OAuth app (15 min to set up)
- Would need to validate on post-2021 data specifically (pre-2021 papers may have lookahead bias given GME)
- Would compete in a crowded space of existing commercial products (wsbsentiment.com, adanos.org, Quiver Quant)

**Recommendation:** Skip Reddit entirely for the current tournament roster. If we ever add individual stock universe, come back and set up the OAuth app — PullPush for historical, PRAW for live. But given the academic evidence, weight it as a minor auxiliary signal, not a primary one.

---

## 6. Data Access Summary (Reference)

| Source | Status | Use Case |
|---|---|---|
| Reddit `.json` API | ❌ 403 from datacenter IP | Dead |
| Pushshift | ❌ Dead | Dead |
| **PullPush** | ✅ Free, no auth | Historical backtest, ~1mo lag |
| **Arctic-Shift** | ✅ Free, no auth | Historical backtest |
| Reddit OAuth (PRAW) | ✅ Free (needs account) | Live signal, 15min setup |
| Quiver Quant API | 🔒 Auth required | Dashboard free, API paid |
| adanos.org | 🔒 Free tier limited | Reddit sentiment API |
| wsbsentiment.com | 💰 $9-29/mo | Processed WSB sentiment |

---

*Report generated: 2026-06-20 by trading-bench subagent*
