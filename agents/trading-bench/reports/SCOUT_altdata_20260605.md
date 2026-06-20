# SCOUT — Alt-data: sentiment / news / attention / physical (FREE routes only)
**Class:** Non-price signals — news sentiment, social sentiment, search/attention, physical-world proxies
**Scout date:** 2026-06-05 · **Context:** trading-bench (Tessera), paper/backtest, ZERO spend
**Mission:** find FREE, ORTHOGONAL (corr <~0.3 to OHLCV) signal to break the ~0.5 Sharpe ceiling.
All claims below verified via live web_fetch / live API probe on 2026-06-05 (web_search was down → direct fetch/probe used).

---

## TL;DR — Top picks
1. **GDELT 2.0 (GKG + Events)** — the standout. Free firehose + BigQuery, 15-min cadence, genuinely orthogonal global news tone/themes, real regime depth (Events→1979, GKG→Feb 2015). Ingestion is the only real cost. **#1 EV in this class.**
2. **Wikipedia Pageviews API** — clean JSON, no auth, daily, trivial ingest (1/5), CC0. Attention proxy. **Dealbreaker: starts 2015-07-01** (misses 2008; covers 2020/2022). Best "easy win" if you accept the start date.
3. **FRED freight/shipping macro series** (Cass, truck tonnage, transport PPI) — public-domain gov, clean API, deep history (most →1990s/2000s), physical-economy proxy. Low-freq (monthly) but genuinely non-price. Safe orthogonal add.

**Hard dealbreakers found:** Pushshift/Reddit = licensing-dead (mod-only, no-commercial, no-redistribution). StockTwits free API = no usable history (rolling recent window only). BDI = proprietary, no clean free deep history feed. Google Trends = fragile unofficial API + non-reproducible normalization.

---

## Full catalog

| Source | Access / Auth | History depth | Cadence / lag | Licensing | Orthogonality | Ingest (1–5) | Verdict |
|---|---|---|---|---|---|---|---|
| **GDELT 2.0 GKG** | Raw CSV firehose `data.gdeltproject.org/gdeltv2/` (no auth) + Google BigQuery public dataset (free 1TB/mo) + DOC 2.0 JSON API | **GKG 2.0: Feb 2015→now.** (GDELT 1.0 GKG 2013; legacy partial to 1979 via Events) | **15-min** firehose, near-real-time | 100% free & open, explicitly public; commercial OK | **HIGH** — global news tone/emotion/themes, not price-derived | **4** (entity→ticker mapping, theme filtering, huge volume) | ★ **TOP PICK** |
| **GDELT 2.0 Events** | Same firehose + BigQuery | **1979→now** (daily 1979–2005, 15-min 2015+); spans **2008/2020/2022** ✓ | 15-min (modern) / daily (historical) | Free & open, commercial OK | HIGH — CAMEO event counts, Goldstein/tone | **4** (CAMEO codes, actor/geo mapping) | ★ **TOP PICK** (best regime depth in class) |
| **GDELT DOC 2.0 API** | `api.gdeltproject.org/api/v2/doc/doc` JSON/JSONP, no auth | **Jan 2017→now**, but query window ≤3 months at a time | 15-min | Free & open | HIGH (article-level full-text + tone by keyword) | **2** (clean JSON, but stitch 3-mo windows + entity logic) | ✔ Easy entry to GDELT; shallow history — use for prototyping, BigQuery for backfill |
| **Wikipedia Pageviews API** | `wikimedia.org/api/rest_v1/metrics/pageviews/per-article/...` no auth | **2015-07-01→now** (probed: 2015-07 OK, 2007 → 404). Misses 2008; covers 2020/2022 | **Daily**, ~1–2 day lag | CC0 / public domain; very liberal | MED–HIGH — attention proxy (ticker/company/topic page views) | **1** (clean JSON, per-article daily) | ✔ **TOP-3** — best ingest-to-value; start date is the catch |
| **FRED — freight/shipping/transport** | FRED API (free key) + bulk CSV; series e.g. Cass Freight, ATA truck tonnage, PPI rail/water transport, rail carloads | Most **1990s–2000s→now**; many span 2008/2020/2022 ✓ | **Monthly** (some weekly), 1–8 wk lag | US-gov public domain; fully free/commercial | MED — physical-economy proxy, low corr to daily OHLCV but macro-lagging | **1** (gold-standard clean API) | ✔ Safe orthogonal macro lane; low-freq |
| **Common Crawl CC-NEWS** | AWS S3 `s3://commoncrawl/crawl-data/CC-NEWS/` (anon S3, no auth) WARC | **2016→now**; misses 2008, covers 2020/2022 | Daily WARC drops | Free; CC terms permit research/commercial use of crawl | HIGH (raw global news text) **but** it's a corpus, not a signal | **5** (raw HTML WARC → parse → NLP → entity-resolve → sentiment) | △ Powerful but huge build; GDELT already does this work for you |
| **Google Trends** (via pytrends) | Unofficial pseudo-API `pytrends` (no official key); needs proxies vs rate limits | **2004→now**; spans **2008/2020/2022** ✓ | Daily/weekly (weekly for >9mo windows); ~1–3 day lag | **ToU ambiguous** for systematic/commercial scraping; pytrends "only good until Google changes backend" | MED–HIGH — search attention, orthogonal in principle | **4** (fragile, **non-reproducible normalization** — each pull rescaled 0–100, sampled; stitching long series is a science) | △ Real history but brittle + reproducibility hazard; treat as research-grade only |
| **StockTwits** (free API) | `api.stocktwits.com/api/2/streams/symbol/{TICK}.json` — **works unauthed today** (probed live, returned msgs+prices+cashtags) | **No usable history** — cursor returns only ~30 most-recent msgs; no deep backfill on free tier | Real-time | Restrictive; official API increasingly gated; ToS limits redistribution | MED — retail sentiment (but most msgs lack Bull/Bear tag → must infer) | **3** live / **5** for history (no free archive) | ✗ History dealbreaker — fine for live only, useless for regime backtest |
| **Pushshift / Reddit** | `pushshift.io` now **mod-gated** (probed ToU live) | (historically 2005→) — **irrelevant, access closed** | n/a | **DEALBREAKER** — ToU: must certify Reddit **moderator**, "express limited purpose of community moderation," explicit **no commercialization, no redistribution, no derivative products** | HIGH in theory | 5 | ✗ **DEAD** for trading research |
| **Baltic Dry Index (BDI)** | No free official feed. Baltic Exchange = proprietary/paywalled. Free routes = news scrape / TradingEconomics widget / Investing.com scrape | Index since 1985 (BFI), BDI Nov 1999; ATH 11,793 May 2008 — spans all bears ✓ | Daily, ~same-day | **Proprietary** (Baltic Exchange owns the index); free redistribution of the *time series* not licensed | HIGH — pure physical shipping demand, classic orthogonal macro signal | **4** (no clean free API; scrape = fragile + ToS risk) | △ Great signal, bad free access — only daily latest-value free, no licensed deep series |
| **AIS marine / port-call free tiers** | e.g. open AIS aggregators; free tiers tiny, rate-limited, snapshot-only | Free tiers ~recent only; deep history paywalled | Real-time snapshot | Restrictive free tiers, no bulk | HIGH (supply-chain physical) | **5** | ✗ Free tiers too thin for backtest history |
| **NOAA / NASA physical feeds** | NOAA CDO API (free key), NASA EarthData (free) | Decades, gov public domain | Daily–monthly | Public domain ✓ | LOW for cross-asset alpha (weather→commodities niche only) | **2–3** | △ Niche (energy/ag commodity strategies only); not general-equity orthogonal |

---

## Notes & gotchas (the stuff that bites)

### GDELT (the real prize)
- **Two delivery paths, pick per need:** (a) **raw 15-min CSV zips** at `data.gdeltproject.org/gdeltv2/` — truly zero-spend, no account, but you ingest/parse everything yourself; (b) **BigQuery public dataset** — SQL over the whole archive, **free 1 TB query/mo + 10 GB storage**. GKG files are ~3 MB/15 min → naive `SELECT *` full scans blow the 1 TB free budget fast; **always date-partition / column-prune** queries to stay free.
- **History honesty:** GKG **2.0 = Feb 19, 2015** onward (the rich tone/GCAM/theme version). Events DB reaches **1979** (the only thing in this whole class that natively covers 2008). If 2008 regime coverage matters, lean on **Events + Goldstein/AvgTone**, not GKG.
- **DOC 2.0 API** is the friendliest on-ramp (clean JSON, keyword→article tone) but only **Jan 2017+** and ≤3-month query windows — great for prototyping a signal, then backfill via BigQuery.
- **Entity-mapping pain (the ingestion tax):** GDELT keys on actors/orgs/themes/locations, *not tickers*. Mapping "Apple" mentions/tone → AAPL requires a name→ticker dictionary + disambiguation (Apple the fruit, Apple Records…). This is the 4/5 cost and the main reason this isn't a 1/5 plug-in. Theme-level/sector-level signals (e.g., ECON_*, fear/uncertainty tone aggregates) sidestep ticker-mapping and may be the fastest orthogonal win.

### Wikipedia Pageviews
- **Probed live:** `Apple_Inc./daily/20150701..` returns clean view counts; `20071201..` → 404. So **2015-07-01 is the hard floor.** No 2008. Fine for 2020 + 2022 bears.
- Per-article daily, all-access/all-agents selectable. Map company → canonical page title (redirects resolve server-side mostly). Spike detection on page views = decent attention/event proxy. CC0 → no licensing worry. **Lowest ingestion cost in the entire class (1/5).**

### FRED freight/transport
- Not BDI (FRED doesn't carry the proprietary BDI), but **public-domain proxies**: Cass Freight Index, ATA Truck Tonnage, rail carloads (AAR), PPI for rail/water/air freight, Harpex-adjacent? (no). Monthly cadence + release lag means it's a *slow* regime/macro feature, not a day-trading signal — but it's genuinely non-price and free with the cleanest API going.

### Reproducibility / brittleness flags
- **Google Trends:** values are **0–100 normalized to the query's geo+timeframe and re-sampled each call** — two pulls of the same term can differ; long histories require window-stitching with overlap-rescaling. pytrends is unofficial and breaks when Google changes its backend. Usable for research, dangerous as a production feature without heavy plumbing.
- **StockTwits:** unauthenticated endpoint works *today* but is undocumented/unstable; no deep history on free tier → cannot build a regime backtest. Most messages have no explicit Bull/Bear sentiment tag, so you'd run your own classifier anyway.

### Dead ends (don't waste time)
- **Pushshift/Reddit:** ToU now requires you certify you're a **Reddit moderator** using data **solely for moderation**, with explicit bans on commercialization/redistribution/derivatives. Reddit historical sentiment is **closed** for trading research. (Verified on pushshift.io ToU 2026-06-05.)
- **BDI clean feed / AIS bulk / port indices:** the *signal* is great and spans all bears, but free access is latest-value-only or tiny snapshot tiers; deep historical series are paywalled or scrape-with-ToS-risk. No zero-spend path to a backtest-grade series.

---

## Ranking by EV (orthogonality × history × ingestion-ease × licensing)

1. **GDELT Events+GKG** — only class member combining HIGH orthogonality + real bear-regime depth (Events→1979) + free/open licensing. Ingestion (entity mapping) is the price of admission; mitigate by starting with **theme/sentiment aggregates** (no ticker mapping) before per-name signals.
2. **Wikipedia Pageviews** — trivial ingest, clean license, daily attention signal; the **2015 start** caps it (no 2008) but it's the fastest thing to wire up and validate.
3. **FRED freight/transport macro** — public-domain, deepest clean history, genuinely physical/non-price; low-frequency, so a regime/context feature rather than a trade trigger.

**Honorable-but-not-now:** Common Crawl CC-NEWS (same value as GDELT but you'd rebuild GDELT to use it — skip). Google Trends (real 2004+ history, but brittleness + normalization make it research-grade only).

**Skip:** Pushshift/Reddit (licensing-dead), StockTwits history (none free), BDI/AIS deep history (no free route).
