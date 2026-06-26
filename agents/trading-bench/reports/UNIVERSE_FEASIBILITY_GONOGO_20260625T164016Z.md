# Survivorship-Clean Universe — Feasibility GO/NO-GO Probe

**Date:** 2026-06-25
**Author:** Tessera (trading-bench)
**Mandate:** main greenlit a *fast GO/NO-GO* — can a **free, delisting-inclusive (survivorship-clean) historical equity universe** be built from THIS VM? It is the 🧱 binding constraint behind the entire single-stock cross-sectional class (4 lanes died 2026-06-23 to the EW-same-universe control, all on the fixed modern-survivor universe).
**Probe:** `_universe_feasibility_probe.py` (free sources only, no writes outside /tmp).

---

## VERDICT: 🔴 **NO-GO on free data.** Pivot to mutation-cron parent-diversity.

A survivorship-clean single-stock universe needs THREE things to all be free+reachable. Two are red, and the red one (delisted **price** history) is the irreplaceable join:

| Piece | Source tested | Result |
|---|---|---|
| **(B) Membership / fundamentals, PIT, delisting-inclusive** | SEC EDGAR submissions | ✅ **GREEN** — delisted registrants' full filing streams survive; the stream simply STOPS at delisting (natural PIT signal) |
| **(A) PRICE history for delisted tickers** | Yahoo v8 chart | 🔴 **RED** — **2/12 hit, and both hits are false positives** (reused tickers of post-bankruptcy successors). Genuinely-dead tickers return `no_data`/404. Yahoo silently drops delisted names. |
| **(C) Historical ticker → CIK join key (for delisted names)** | `company_tickers.json` + EDGAR FTS | 🔴 **RED** — current map is active-registrant-only (11/12 delisted absent); only recovery is unindexed full-text search, not a backtest-scale reverse index |

**Why (A) is decisive:** the whole point of a survivorship-clean universe is that a name which later delisted contributes its returns *up to* delisting (including the −90% death spiral). If price history for dead tickers isn't retrievable, every backtest silently re-introduces the exact survivorship bias we set out to remove — we'd just be re-skinning the modern-survivor set with extra steps. EDGAR fundamentals being clean (B) doesn't help: you can't trade a fundamental without a price path.

---

## Evidence (probe output, 2026-06-25)

### (A) Delisted price history — Yahoo hit rate **2/12**, both false positives
```
LEH    no_data     WCOM   no_data     ENRNQ  no_data     BSC    no_data
WAMUQ  no_data     SHLDQ  HTTP 404    SIVBQ  HTTP 404     BBBYQ  HTTP 404
MNKKQ  HTTP 404     SUNEQ  no_data
GM     OK 3922 bars 2010-11-18..now   <- NEW GM (2010 IPO), NOT old GM/Motors Liquidation
FRCB   OK 3908 bars 2010-12-09..now   <- ticker reuse, NOT the 2023 First Republic failure
```
Both "successes" start ~2010 = the *successor* entity's listing, never the failed predecessor's death spiral. Confirms Yahoo is survivorship-biased on price.

### (B) EDGAR membership/fundamentals — delisting-inclusive, PIT-clean ✅
```
ENRON CORP/OR/        10-Ks 1996-10 .. last 10-K 2001-04-02, then stops   formerNames:[ENRON OREGON CORP]
MCI INC (was WORLDCOM) filings 1994-11 .. 2006-09  last 10-K 2005-03-16   formerNames:[WORLDCOM INC, ...]
LEHMAN ... PLAN TRUST  filings 2008-02 .. 2025-08 (post-bankruptcy trust)  formerNames:[LEHMAN BROTHERS HOLDINGS INC]
```
The filing stream's *termination* is itself a clean, point-in-time delisting timestamp. `formerNames` preserves historical identity. This half is genuinely free and survivorship-free — reusable if a price source ever appears.

### (C) Ticker→CIK for delisted names — current-map-only 🔴
```
company_tickers.json: 10,433 registrants, ACTIVE only.
  delisted-in-current-map: LEH F, WCOM F, ENRNQ F, BSC F, WAMUQ F, SHLDQ F, SIVBQ F, BBBYQ F, MNKKQ F  (GM/FRCB T = successor reuse)
EDGAR full-text search: reachable but UNINDEXED for this purpose (manual lookup, not a join table).
```

---

## What a YES would require (the paid/hard path — NOT free)
1. **Delisted price history** — CRSP (academic gold standard, survivorship-free; institutional $$$), Norgate Data (~$$/mo, has delisted), Sharadar/Nasdaq Data Link SEP (~$/mo, delisting-inclusive US equities + the ticker↔permaticker↔CIK map), or Polygon (delisted tickers on paid tiers). All are **spend decisions** — by the standing rule I can recommend + state cost, but a paid DB is explicitly NOT pre-approved (MEMORY: "no paid DB"), so this needs a fresh Cyrus thesis+approval.
2. **Sharadar SEP/SF1 specifically** is the cheapest credible one-stop: delisting-inclusive prices + PIT fundamentals + a stable security master (handles ticker changes/CIK). ~$ low-tens/mo. That single subscription would flip ALL of (A)/(B)/(C) to green and unblock the entire single-stock anomaly class.

> **⛔ PAID-DB DOOR IS CLOSED (2026-06-25, via main).** Cyrus declined paid market-data twice the same night (Sharadar ~$40/mo, EODHD ~$20/mo). Do NOT re-surface a paid-DB proposal unless Cyrus explicitly reopens it. This section is recorded only as the technical answer to 'what WOULD unlock it', not as a live recommendation.

## Disposition
- **NO-GO on free data, today.** Do NOT attempt to bodge a free clean universe — Yahoo-on-delisted is a survivorship trap dressed as a fix.
- **Pivot (per main's directive): mutation-cron parent-diversity** is the next gate-free lever.
- **Shelf-with-trigger:** if Cyrus ever approves a low-cost delisting-inclusive DB (Sharadar SEP the front-runner), this unblocks single-stock xsec, clean value/quality L/S, BAB, PEAD wide-universe — i.e. it's the master key to the whole class that died 06-23. (Paid-DB door CLOSED 2026-06-25 — Cyrus declined twice; do not re-pitch unless he reopens it.)
- **Reusable now:** EDGAR delisting-inclusive fundamentals/membership infra (B) is real and free — keep for any fundamentals-only PIT work that doesn't need a tradeable price for the dead names.

**Probe artifact:** `_universe_feasibility_probe.py` (re-runnable).
