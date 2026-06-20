# Sentiment / News Archetype — Feasibility Memo

**Date:** 2026-05-31 05:48 UTC
**Author:** trading-bench (subagent "sentiment_feasibility")
**Status:** FEASIBILITY MEMO ONLY. Zero strategy code written. Zero promotions. Nothing under `runner/` or `strategies/` touched.
**Scope:** Can a sentiment- or news-driven archetype be honestly backtested at our constraints (once-daily cadence, $100 caps, Alpaca paper, GATE.md graduation), and is it worth building? 

> **Citation hygiene:** Sources fetched live this session are marked **[web]**. Claims from my training memory (not verified against a live source this session) are marked **[mem — spot-check]**. The team's own prior PEAD work is marked **[internal]**.

---

## TL;DR (read this first)

- **Best backtestable archetype: PEAD (post-earnings drift)** — and the team already built it, tested it, and correctly rejected it (`BACKTEST_PEAD_20260530T171825Z.md`). The honest academic literature says the drift **died in non-microcap stocks ~2006** and survives mainly in microcaps (≈3% of market value), which our $100/$1000 liquid-mega-cap universe structurally cannot harvest. **[web]**
- **Biggest leak risk: point-in-time sentiment data is effectively unavailable for free.** Pushshift (the Reddit historical archive) is dead to the public; current social-sentiment APIs serve *today's* scores, not as-of scores. Any Reddit/Twitter backtest you can cheaply build will leak lookahead and produce a fake edge.
- **Verdict: do NOT build a new sentiment/news backtest at current constraints.** PEAD is the only honest candidate and it already failed for structural reasons that $100→$1000 does not fix. Recommended next step is a one-paragraph "parked" note, not code.

---

## 1. Data Feeds Survey

The single question that decides everything: **is point-in-time / as-of timestamped history available?** Without it you cannot backtest sentiment without lookahead leakage (see §2). I've split by archetype need.

### (a) Structured earnings / news (for PEAD / earnings-drift)

| Source | Cost | API | Hist. depth | Point-in-time? | Notes |
|---|---|---|---|---|---|
| **SEC EDGAR** (8-K Item 2.02) | Free | Public REST, 10 req/s, UA header | ~10+ yr/issuer | ✅ **Yes** — filing timestamp is immutable, taxpayer-funded | Already wired by the team in `strategies_candidates/pead_lib/earnings_edgar.py`. **[internal]** Gives announcement *dates*, not surprise magnitude. |
| **Alpaca** corporate-actions / news | Free (paper) | REST | News API ~2015→, limited | News: partial. Corp-actions: yes | Alpaca has a news endpoint (Benzinga-sourced) but historical depth and as-of fidelity are weak for backtest. **[mem — spot-check]** |
| **Financial Modeling Prep** earnings-surprise / calendar | Free tier (rate-capped) → ~$20–30/mo | REST JSON | Multi-year | ⚠️ Calendar is forward-revised; surprise values are point-in-time-ish but **estimates get restated** | FMP's own education page concedes PEAD "still exists… though its magnitude has declined." **[web]** Good for *actual vs estimate* SUE that EDGAR can't give for free. |
| **Analyst-consensus SUE** (IBES/FactSet/Refinitiv) | $thousands/mo | Paid | Deep | ✅ but paid | The "real" PEAD surprise measure. Out of budget. GATE/honesty: the price-reaction proxy diverges from true SUE in ~10–20% of events. **[internal]** |

**Bottom line (a):** EDGAR (free, point-in-time, already integrated) covers *dates*; the *surprise magnitude* either uses a free price-reaction proxy (coarse, the team already tried it) or paid SUE. This is the **one** sentiment-adjacent data category where free point-in-time data genuinely exists.

### (b) General financial news with timestamps

| Source | Cost | API | Hist. depth | Point-in-time? | Notes |
|---|---|---|---|---|---|
| **GDELT** (Global news, GKG) | Free | REST / BigQuery | 2015→ (GKG 2.0) | ✅ **Yes** — each record carries a capture timestamp | Massive, noisy, entity-tagged (incl. some tickers via org names). Mapping orgs→tickers cleanly is the hard part and a leak vector (§2). **[mem — spot-check]** |
| **Tiingo News** | ~$10/mo | REST | ~2014→ | ✅ tagged by publish time + ticker | Cleaner ticker tagging than GDELT; cheap. Reasonable if you ever do news. **[mem — spot-check]** |
| **Alpaca News (Benzinga)** | Free paper | REST/WS | shallow (~recent) | Partial | Fine for live, weak for multi-year backtest. **[mem — spot-check]** |
| **NewsAPI.org / Finnhub news** | Free tier tiny → paid | REST | shallow on free | Publish-time yes; **free tier history is days-to-weeks, useless for backtest** | Don't bother for backtest. **[mem — spot-check]** |

**Bottom line (b):** GDELT and Tiingo give genuinely timestamped history. But "news exists with a timestamp" ≠ "tradeable signal" — you still need an event-driven multi-symbol harness (which we lack, see §3) and a defensible org→ticker map (a leak vector).

### (c) Social sentiment (Reddit / Twitter / StockTwits)

| Source | Cost | API | Hist. depth | Point-in-time? | Notes |
|---|---|---|---|---|---|
| **Pushshift** (historical Reddit archive) | Was free | Was REST | 2005→2023 dumps | ✅ historically — **but public access is dead** | Post the 2023 Reddit API crackdown, Pushshift is restricted to Reddit-approved moderators; public API/ingest is gone. Static HuggingFace dumps (`fddemarco/pushshift-reddit`) exist but **stop ~2023 and have no go-forward feed**. **[web]** This is the crux: the *one* tool that gave as-of Reddit scores is no longer usable for a live-maintainable strategy. |
| **Reddit official API** | Free (rate-capped) / paid tiers | REST | **No deep history; pulls current state** | ❌ **No** — returns *today's* score/upvotes, not the score as-of the past date | Fatal for backtest: you'd be scoring a 2-year-old post with its 2026 upvote count. Pure lookahead. **[web/mem]** |
| **StockTwits API** | Free-ish, rate-capped | REST | shallow recent | ❌ mostly current-state | Same as-of problem; also thin, bot-heavy, ticker-stream survivorship. **[mem — spot-check]** |
| **X/Twitter API** | $100+/mo (Basic) and up | REST | gated, expensive | ❌ for cheap tiers | Cost + no cheap history + ToS. Off the table. **[mem — spot-check]** |
| **Pre-packaged sentiment vendors** (e.g. SocialSentiment, Sentifi-style) | $$$ | REST | varies | sometimes as-of, paid | Out of budget and you're trusting their point-in-time discipline. |

**Bottom line (c):** **There is no free, point-in-time, live-maintainable social-sentiment feed in 2026.** Pushshift is dead to the public; everything cheap returns current-state scores. Any social-sentiment backtest you build on free data will silently leak (§2). This single fact is enough to kill naive Reddit/Twitter archetypes.

---

## 2. Lookahead-Leak Traps (the most important section)

Sentiment/news backtests are unusually easy to cheat. Every trap below produces a *beautiful* equity curve that evaporates live. Be ruthless:

1. **Current-score-as-historical-score (the killer).** Reddit/StockTwits/Twitter APIs return a post's **upvotes/score as it is *today***, not as it was on the trade date. A post that later went viral looks "high sentiment" on day 0 — but on day 0 it had 3 upvotes. Backtesting on today's scores = trading on the future. This alone fakes most retail "WSB sentiment" alpha. Pushshift's death means you *cannot cheaply* get the as-of score, so you'll be tempted to use the leaky one.

2. **Ticker-mention dictionary built with hindsight.** If your $TICKER regex / NER dictionary is built from "tickers people talked about" (GME, AMC, NVDA…), you've selected the names that *subsequently* moved. The dictionary itself encodes the future. A point-in-time-honest system must map *every* post to tickers using only info available then.

3. **Sentiment-tracked-universe survivorship.** "We track sentiment for the 50 most-discussed tickers" — those 50 are the ones that survived/mooned. Delisted, renamed, or faded names drop out of the tracked set, so your universe is the winners' bracket. Classic survivorship, dressed up.

4. **News-timestamp revision / "first-seen" ambiguity.** A headline's displayed timestamp may be the *updated* time, the index time, or the syndication time — not when it first hit the wire. GDELT capture-time helps, but article URLs get re-crawled. If you trade on a 4:05pm headline whose "real" wire time was 4:05pm but whose dataset timestamp is the 4:30pm re-crawl, you're fine; the reverse (trading earlier than the news actually existed) is the leak. EDGAR is clean here; news feeds are not, by default.

5. **After-hours / overnight gap leak.** Earnings and most market-moving news drop after the close. If your once-daily tick reads "today's news" and trades on "today's close," you may be capturing a price that already moved on that news. The team hit exactly this: `o_to_c` proxy missed ~80% of the reaction because the move happened in the overnight gap. **[internal]** You must trade the *next* session's open/close, not the announcement session's close.

6. **Restated fundamentals / estimate revision.** Analyst estimates (for SUE) get revised after the fact. Pulling "the consensus estimate" today gives a number that may differ from the as-of-announcement consensus. FMP and most free feeds restate. Only true point-in-time estimate databases (paid) avoid this.

7. **Look-ahead in label construction.** Defining "positive sentiment event" using thresholds tuned on the full sample (e.g. "top-decile mention spike") leaks the full-sample distribution into each day's decision. Deciles must be computed expanding-window / as-of.

8. **Signal-already-priced-in (not a leak, but the economic trap).** Even with perfect point-in-time data, a "Reddit volume spike → buy" signal is public and crowded. By the time a spike is measurable, the move is largely done. Properly cost- and timing-weighted, naive social-volume strategies have **negative** expectancy after spread/slippage. The honest literature and every careful replication I'm aware of land here. **[mem — spot-check]**

**Implication:** With free data, traps #1, #2, #3 are nearly unavoidable for social sentiment. That's why social-sentiment archetypes are not honestly backtestable here — not "hard," but **structurally leaky given the only affordable data.**

---

## 3. Backtestable Archetypes (ranked by feasibility)

Filter applied: once-daily cadence (no sub-hour reaction), $100 caps, must be able to clear GATE.md (Sharpe≥1.0, MaxDD<20% real-money / ≤30% candidate, **100+ trades** for full graduation, **≥8%/yr net-on-deployed** absolute-return floor), net of Alpaca stock costs.

### Rank 1 — PEAD (post-earnings drift), price-reaction proxy. **Backtestable, but already failed.**
- **Why it's the honest first candidate (the prior is right):** structured, timestamped, free point-in-time data (EDGAR), academically documented since Bernard-Thomas 1989, drift horizon is *days-to-weeks* so once-daily cadence is a natural fit (no HFT requirement). **[internal/web]**
- **Pressure-test of the prior — and it doesn't survive:**
  - The team **already built and rejected it** (`BACKTEST_PEAD_20260530T171825Z.md`): 18 round-trips over 2 years on 8 mega-caps, 3 of 4 regime medians ≤0, held-out window produced **0 trades**, trade count 18 ≪ 30 (and ≪100 for full graduation). **[internal]**
  - The deeper reason it can't be rescued: **PEAD died in non-microcaps.** Martineau (2022, *"Rest in Peace Post-Earnings Announcement Drift"*) shows drift vanished from non-microcap stocks 2001→2006 with decimalization + faster arbitrage; 2025 papers reviving it rely specifically on **microcaps (bottom-20th-pct, ~3% of market value)**, and a 2025 UCLA Anderson (Subrahmanyam) reconciliation confirms the debate "turns on whether microcaps are included." **[web]**
  - Our universe is **liquid mega-caps** — precisely where PEAD is deadest. Microcaps are where the edge lives, and microcaps are exactly what $100/$1000 caps + Alpaca IEX feed + spread sensitivity handle worst.
- **Does $1000 fix it?** No. $1000 raises per-trade size but **not trade count** (still ~event-limited) and **not the universe problem** (mega-caps still have no drift). It slightly improves the ability to hold more concurrent small positions, which only matters if you also (a) build a multi-symbol event harness and (b) move to small/microcaps — two big projects that change the risk profile. $1000 alone changes nothing material.

### Rank 2 — News-event drift on structured, point-in-time news (GDELT/Tiingo). **Backtestable in principle, blocked by harness + leak risk.**
- Timestamped data genuinely exists (§1b). Cadence fits (daily).
- **Blockers:** (i) needs the **multi-symbol event-driven harness we don't have** (`runner/backtest.py` is single-symbol — flagged repeatedly in PEAD docs **[internal]**); (ii) org→ticker mapping is a live leak vector (§2 trap #2); (iii) expected edge after the news is public is thin and likely doesn't clear costs at $100.
- **$1000:** same as PEAD — doesn't address the structural blockers.

### Rank 3 — Naive social-volume / Reddit-sentiment spike → buy. **NOT honestly backtestable. Reject.**
- Fails at the data layer: no free point-in-time social feed (§1c). Any cheap build leaks via traps #1–#3 (§2). Even leak-free, the signal is public/crowded with **negative post-cost expectancy** (§2 trap #8). 
- **$1000 makes it worse**, not better: bigger size into a crowded, already-moved, high-spread signal increases loss.

---

## 4. Execution-Cost Reality

Alpaca stocks: ~2 bps one-way spread on liquid mega-caps, no commission (the cost model already used: `alpaca_stocks`, ~$0.37 drag on the PEAD run **[internal]**). At once-daily cadence this is *gentle* — the problem is never the fee, it's whether **gross edge exists at all**.

| Archetype | Gross edge (honest) | Survives ~2–4 bps r/t at $100? | Survives at $1000? |
|---|---|---|---|
| PEAD mega-cap | ~0 (drift dead in non-microcaps) | No — there's no edge to survive **[web]** | No (no edge; size doesn't create one) |
| PEAD microcap (hypothetical) | Real but small | **Spread on microcaps is 50–300+ bps, not 2 bps** — eats the edge | Marginal at best; needs careful liquidity work |
| News-event drift (mega-cap) | Thin, mostly priced same-session | Borderline-to-negative net | Borderline |
| Social-volume spike | Negative gross after timing | No | No (worse) |

**Key cost insight:** the only place PEAD edge survives academically (microcaps) is the place where Alpaca execution cost *explodes* (wide spreads, thin books). The 2-bps assumption is only valid on mega-caps, where there's no edge. This scissors-action is why sentiment/news alpha is so hard for small retail books.

---

## 5. Verdict + Recommended Next Step

**Verdict: NONE of the sentiment/news archetypes are worth building a new backtest for at current constraints.**

- **PEAD** is the most honest candidate and the team already did the work to reject it. The rejection is *structural*, not a tuning miss: drift is dead in the liquid universe we can trade, alive only in microcaps we can't cleanly trade at $100/$1000 with Alpaca. **[internal + web]**
- **Social sentiment** is dead on arrival at the data layer — no free point-in-time feed since Pushshift's public death — and economically negative-expectancy even leak-free. This matches the well-known pattern: **most retail sentiment-alpha projects have negative expectancy.** I'm not hedging that; that's the conclusion. **[web/mem]**
- **News-event drift** is the only "maybe someday," and only *after* a multi-symbol event-driven harness exists — which is a general infrastructure project the team has already identified as the real unlock for PEAD/cross-sectional/mean-reversion alike. **[internal]**

**Recommended single next step:** **Do not write a sentiment strategy. Park it.** Add a 3-line note to `BACKLOG.md` / archetype triage: *"Sentiment/news archetypes deferred — PEAD rejected (drift dead in non-microcaps, `BACKTEST_PEAD_20260530T171825Z.md`); social sentiment infeasible (no free point-in-time feed post-Pushshift); revisit news-event drift ONLY if/when the multi-symbol event-driven harness lands, and even then expect thin post-cost edge."* 

If the team ever wants *one* honest experiment in this family, the **highest-value-per-dollar** move is **not** sentiment at all — it's finishing the multi-symbol event-driven harness, which would let PEAD be tested properly on a wide universe *and* unlocks the cross-sectional strategies already in the pipeline. Sentiment is a poor place to spend the next engineering dollar.

---

### Appendix: sources
- **[web]** UCLA Anderson Review, "Is Post-Earnings Announcement Drift a Thing? Again?" (Subrahmanyam working paper review; Martineau 2022 "Rest in Peace PEAD") — drift died in non-microcaps 2001–2006; survives in microcaps (~3% of market value). Fetched 2026-05-31.
- **[web]** Financial Modeling Prep education page — PEAD "still exists… magnitude declined." Search result, 2026-05-31.
- **[web]** Pushshift public-access status (Reddit 2023 API crackdown; HuggingFace static dumps end ~2023; no go-forward public feed). Search results, 2026-05-31.
- **[internal]** `reports/BACKTEST_PEAD_DATA_FEASIBILITY_20260530T171453Z.md`, `reports/BACKTEST_PEAD_20260530T171825Z.md` (team's own EDGAR-based PEAD build + rejection).
- **[internal]** `GATE.md` (Bars A/D thresholds, ≥8%/yr-on-deployed floor, single-symbol harness gap).
- **[mem — spot-check]** GDELT/Tiingo/Reddit-API/StockTwits/Twitter API cost & point-in-time characteristics; negative-expectancy of naive social-volume strategies.

*No code written. No `runner/` or `strategies/` changes. Memo only.*
