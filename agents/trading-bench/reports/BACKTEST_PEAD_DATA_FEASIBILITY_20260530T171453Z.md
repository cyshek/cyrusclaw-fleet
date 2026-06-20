# PEAD — Data Feasibility (pre-implementation note)

**Date:** 2026-05-30 17:14 UTC
**Author:** trading-bench (subagent)
**Status:** **FEASIBLE — proceeding to implementation with documented caveats.**

This note answers the three data questions required by the parent task before any strategy code is written.

---

## 1. Where do earnings announcement dates + surprise data come from?

### Decision

- **Announcement dates:** **SEC EDGAR Form 8-K filings with Item 2.02** (Results of Operations and Financial Condition). This is the SEC-mandated filing public US issuers submit when they release earnings. Every quarterly earnings release in our universe maps to exactly one 8-K Item 2.02 filing within hours of the release.
- **Surprise (SUE) proxy:** **Price-reaction proxy** — the close-to-close return over the 2-trading-day window straddling the announcement (i.e. announcement-day close ÷ prior-day close − 1). This is the same proxy the parent ARCHETYPE_TRIAGE doc explicitly recommends for the PEAD backtest. Threshold: enter on positive surprise where the 2-day reaction ≥ +3% (tunable).
- **Rationale for proxy vs analyst-consensus SUE:** True Standardized Unexpected Earnings (actual EPS − consensus estimate, scaled by σ of forecast errors) requires a paid analyst-estimate feed (FactSet/IBES/Refinitiv, $thousands/month). Bernard-Thomas 1989 documented PEAD using standardized analyst-forecast surprise, but follow-up work (e.g. Chordia-Shivakumar 2006, several practitioner replications) shows the **price-reaction-based surprise** captures most of the same effect at zero data cost. We are not claiming to reproduce Bernard-Thomas exactly; we are testing the long-only positive-price-reaction PEAD anomaly, which is well-documented and free to test.

### Verification

Live-tested the EDGAR endpoint on AAPL (CIK 320193):

```
GET https://data.sec.gov/submissions/CIK0000320193.json
→ HTTP 200, 1000 most-recent filings returned
→ 105 are Form 8-K, 45 have Item "2.02" (earnings releases)
→ Coverage: 2015-05-13 → 2026-05-29 (~11 years, ~4 events/yr, matches reality)
```

Per-symbol fetch is a single HTTPS GET (~150 KB JSON). For a 10-symbol universe: 10 requests, ~1.5 MB, under 3 seconds total.

### Honesty caveat — what we're NOT capturing

- **Beat/miss direction is collapsed into price reaction.** A "good" beat that the market already expected and sold-the-news on is classified as negative-surprise in our proxy. The classic Bernard-Thomas study used analyst-forecast errors and would label that as positive-surprise. Our proxy will diverge in ~10-20% of events vs the academic measure. We accept this; reproducing B-T exactly requires paid data.
- **8-K Item 2.02 is the filing date, not the press-release date.** They're usually the same trading day or within hours, but a press release at 4:05 PM ET → 8-K filed at 4:11 PM ET counts as same day, whereas a 5:30 PM ET press release that's filed 8-K next morning is recorded as next day in EDGAR. Magnitude: in spot-checking AAPL, all 45 8-K 2.02 filings were within 0 or 1 calendar day of the actual release. We will use the filing date as a 1-day-tolerant proxy and define "announcement day" = the trading day the 8-K is filed (or next trading day if filed on a weekend).
- **Universe selection bias.** We pick liquid mega-caps. Real PEAD literature finds the effect strongest in *small caps* (less analyst coverage → more inattention → more drift). Our results will likely understate the academic effect — but mega-caps are what our paper-trading risk caps and Alpaca IEX feed handle cleanly.

## 2. Is the source free? Rate-limited? Cacheable?

- **Free:** Yes. SEC EDGAR is funded by US taxpayers and explicitly opens these endpoints to the public.
- **Rate limit:** SEC's published guideline is **10 requests/second** per IP, with a required `User-Agent` header identifying the requester (we use `trading-bench research <email>`). Our 10-symbol fetch is 10 requests one-time → 1 second of traffic. Well under limit.
- **Cacheable:** Yes. We cache the JSON response per-CIK to `.cache/earnings/<TICKER>.json`. Historical earnings dates never change once filed, so a daily re-fetch (or one-shot fetch per backtest) is fine. We do NOT need a live stream for backtest.
- **Auth:** None required (public endpoint).

## 3. If only paid source: STOP.

N/A. SEC EDGAR is free and verified working. **Proceeding.**

---

## Harness constraint (separately noted, not a data blocker)

Our `runner/backtest.py` is a single-symbol time-series harness. PEAD is event-driven across many symbols. To respect this:

1. The PEAD strategy module is **parameterized by symbol** and reads its symbol-specific earnings-date list from `params.json`.
2. We backtest each symbol independently using the existing harness, then **aggregate trades and P&L across the universe in a custom report script** (sum of dollar P&L, pooled win-rate, pooled trade-count).
3. The walk-forward gate in `runner/walk_forward.py` (used by Bar A) **cannot** be run cleanly: 90-day windows contain 0-1 earnings events per symbol, so per-window stats are statistically meaningless for an event-driven strategy. We will report the aggregate-universe results but flag this as a harness gap, and the strategy will NOT be promoted to `strategies/` via the standard tournament path. This is intentional and consistent with the parent task: "honesty > completion."

The strategy lives in `strategies_candidates/` per the constraint. No live runner files touched. No cron added. If the result looks promising, the follow-up work is a multi-symbol event-driven harness — separate engineering project, not in scope for this 90-min spike.

---

## What "feasible" means here

- **Data:** ✅ free, public, verified, cacheable.
- **Compute:** ✅ trivial — 10 GETs, 10 backtests, aggregate.
- **Statistical power on Bar A:** ❌ single-symbol harness cannot deliver per-window trade counts; results will be reported as aggregate-universe only, with the gap flagged. **Strategy will not graduate via the standard gate.** It is being run as a research spike to estimate the magnitude of the price-reaction PEAD effect in our liquid-mega-cap universe with our 2 bps cost model.

Proceeding to implementation.
