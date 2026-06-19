# RESEARCH_QUEUE.md — Weekly research ideas

Each entry: the question, why it might matter, rough source.
The Friday research cron picks 1-2 of these per week, researches them, posts a short verdict to channel, and moves them to DONE or promotes to a backtest spec in BACKLOG.

Add ideas freely. No commitment to research them — just a place to park "worth looking at."

---

## Queue (unresearched)

- **COT positioning extremes (absolute percentile vs week-over-week delta)** — we use AM-net WoW direction; literature suggests absolute positioning extremes (top/bottom decile of net long) may be stronger signals. Source: CFTC academic literature. Testable: swap the WoW signal for a rolling percentile rank, re-run the TQQQ+COT combo sweep.

- **Overnight drift in leveraged ETFs** — TQQQ/UPRO show persistent overnight return bias in some academic work (close→open). If real post-2020, could slot cleanly into the vol-target engine as a second signal. Source: Lou, Polk, Skouras (2019) "A tug of war: overnight vs intraday expected returns." Testable: pull Alpaca open/close, compute overnight return distribution, check persistence.

- **VIX term structure (front/back contango ratio) as regime signal** — steeper contango = low fear = risk-on. Cleaner than raw VIX level. CBOE VIX3M/VIX ratio is free from this IP. We partially explored this with vol-regime (Moreira-Muir) but used VIXY level not term structure. Testable: replace VIX level gate with VIX3M/VIX ratio, sweep on TQQQ. Source: Simon & Campasano (2014).

- **Jane Street / AQR / Man Institute publications** — systematic reviews of factor investing, market microstructure, and execution. Good for finding structural edges we haven't thought about. Source: aqr.com/insights, man.com/maninstitute, janestreet.com/quantitative-research. Not directly testable, but good for generating new hypotheses.

- **Put/call skew as directional signal** — different from the aggregate P/C ratio we already rejected. OTM put skew (25-delta) signals tail hedging demand. CBOE SKEW index is a free daily proxy. Testable: SKEW percentile rank as a filter on TQQQ entries.

- **Earnings drift on small/mid-cap post-earnings** — PEAD sprint found mega-cap doesn't drift enough. Literature says the effect is 3x stronger in small/mid caps. Free source: SEC EDGAR 8-K Item 2.02 for dates, Yahoo v8 for OHLCV. Testable: replicate the sprint on a 200-500 name small/mid universe, same YoY EPS proxy.

- **Systematic options selling (cash-secured puts on TQQQ)** — not leverage, just premium capture. If TQQQ implied vol > realized vol persistently, selling OTM puts during low-VIX periods = positive carry. Source: CBOE premium capture literature. Testable in theory but requires options data (not free).

---

## Done

_(moved here after research sprint with verdict)_
