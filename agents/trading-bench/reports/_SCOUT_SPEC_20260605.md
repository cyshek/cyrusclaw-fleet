# Free-Dataset Scout — Shared Deliverable Spec (2026-06-05)

Mission: find FREE data sources (ZERO spend) that supply ORTHOGONAL signal
(corr <~0.3 to OHLCV price/vol history) capable of breaking trading-bench's
~0.5 Sharpe SIGNAL ceiling. 11 price/vol-derived lanes all hit ~0.5, so MORE
price re-feeds are useless. Hunt genuinely NEW input classes.

SCOUTING ONLY — do NOT ingest, download bulk, or backtest. Produce a ranked map.

For EACH source in your class, capture:
(a) ACCESS — API / bulk file / scrape; endpoint or URL; auth needs (key? free signup? none?); rate limits.
(b) HISTORY DEPTH — earliest date available. MUST ideally span 2008, 2020, 2022 bear regimes to be useful. State coverage honestly; a source starting 2021 is near-worthless for regime work.
(c) CADENCE — real-time / daily / weekly / monthly / quarterly; release lag.
(d) LICENSING — does the terms-of-use permit our (private, paper-trading, potentially commercial) use? Public-domain (gov) vs restrictive. Flag any "personal use only" / "no redistribution" blockers.
(e) ORTHOGONALITY — honest estimate of correlation to OHLCV price/vol. High orthogonality = the point. If it's just price in disguise (e.g. another index's prices), say so and down-rank.
(f) INGESTION EASE — 1 (trivial: clean CSV/JSON API) to 5 (painful: PDF scrape, ID-mapping hell, entity resolution).

OUTPUT:
- Write your full catalog to your assigned report file (markdown table + notes).
- Flag your class's TOP 2-3 highest-EV sources (best orthogonality × history × ingestion-ease × licensing).
- Return to the parent a TERSE summary (≤12 lines): your top 2-3 picks with one-line why each, plus any dealbreakers. NO code, NO full catalog dump in the reply — the file is the deliverable.

HARD RULES:
- FREE sources ONLY. Zero spend. If a source is freemium, note exactly what the FREE tier gives and whether it's enough (history depth + cadence).
- Paper/backtest context only. No live trading, no orders.
- Use web_search / web_fetch to verify access + history claims — don't assert from memory; vendor pages change. Sanity-check that "free" is actually free and history actually goes back far enough.
- Be skeptical: many "free APIs" cap history to 1-5y on the free tier (kills regime coverage) or forbid commercial use. Catch these.
