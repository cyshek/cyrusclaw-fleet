# EDGAR Delisted-Universe Probe — Survivorship-Clean Equity Universe FOR FREE?

**UTC:** 2026-06-24T171848Z
**Type:** BUILD + PROVE-OR-KILL feasibility gate (decides the #1 lane: delisting-inclusive fundamentals L/S)
**Verdict (one line):** **RED** — free delisted *price* history is unobtainable from this VM; ticker resolution for gone filers is ~0% free. Lane stays parked.

---

## TL;DR coverage numbers

| Metric | Result |
|---|---|
| EDGAR retains delisted **fundamentals** | ✅ YES (verified: SunEdison 1001 filings 2006→2018, Sears 1000, Lehman, Bear Stearns) |
| Submissions `tickers[]` exposes **historical** ticker for delisters | ❌ **0%** — empty for every confirmed delister; field is CURRENT-state |
| Free ticker resolution of "gone" CIKs (n=60 sample) | ❌ **0/60 (0%)** expose any ticker |
| Yahoo v8 delisted **price** coverage (genuine series) | ❌ **0/9 companies** — all apparent hits are ticker-RECYCLE false positives |
| Stooq delisted price coverage | ❌ bot-walled (HTML/CAPTCHA, not headless-automatable) — re-confirmed |
| AlphaVantage / Tiingo key on disk | ❌ none (`.env` has only Alpaca + FRED) |
| Survivorship hole (CY2014Q4 filers gone from current list) | **60.4%** (4,527 of 7,494) |
| **Free survivorship-clean universe achievable?** | **NO (RED)** |

---

## Task 1 — CIK → historical ticker for delisted names

**Question:** does `https://data.sec.gov/submissions/CIK##########.json` expose a `tickers` field even for delisted names?

**Answer: NO. The `tickers[]` field is current-state, not point-in-time. Delisted filers show `tickers=[]`.**

Confirmed delisters (all absent from current `company_tickers.json`, all `tickers=[]`):

| CIK | EDGAR name | tickers[] | formerNames | filings span |
|---|---|---|---|---|
| 945436 | SUNEDISON, INC. | `[]` | MEMC ELECTRONIC MATERIALS | 2006→2018 (1001) |
| 1310067 | SEARS HOLDINGS CORP | `[]` | — | 2006→2022 (1000) |
| 806085 | LEHMAN BROTHERS HOLDINGS … PLAN TRUST | `[]` | LEHMAN BROTHERS HOLDINGS | 2008→2025 (1000) |
| 777001 | BEAR STEARNS COMPANIES INC | `[]` | — | 2005→2012 (1001) |

Two failure modes discovered:

1. **Ticker stripped on delist.** EDGAR keeps the filings/fundamentals but removes the ticker. `formerNames` holds former *company names*, never former tickers — useless for price lookup.
2. **CIK reuse / reassignment trap.** Several CIKs I tested as "delister X" now resolve to a *different live entity*: CIK 914208 (was Circuit City) → **Invesco (IVZ)**; CIK 96021 (was RadioShack/Tandy) → **Sysco (SYY)**; CIK 29915 (was Kodak) → **Dow Chemical**; CIK 1075531 → **Booking Holdings (BKNG)**. So even a CIK that *does* expose a ticker can hand back the wrong company.

**Free-resolvability at scale (Task 3b):** of 60 sampled "gone" CIKs (filed CY2014, now absent from survivor list), **0/60 (0%)** exposed any ticker — 100% empty. EDGAR is not a free historical-ticker resolver.

---

## Task 2 — Delisted price history (the make-or-break)

Tested free daily-price sources for known-delisted tickers. **Controls (AAPL, MSFT) returned full history → we were NOT throttled → the negatives are real signal** (first burst run hit Yahoo 429 across the board incl. controls; re-ran query2-first with 2.5s spacing, controls 2/2 OK).

### Yahoo v8 — apparent 5/9, actually 0/9
The "covered" delisted tickers are **ticker-RECYCLE false positives**: Yahoo returns the symbol's *current* occupant, whose series runs to ~today, not the dead company ending at delisting. Yahoo's own `meta.longName` exposes each one:

| Ticker | Claimed (dead) co. | Series end | Yahoo `longName` (actual entity) | Verdict |
|---|---|---|---|---|
| SUNE | SunEdison (BK 2016) | 2026-06 | **SUNation Energy Inc.** | recycle |
| SHLD | Sears (BK 2018) | 2026-06 | **Global X Defense Tech ETF** | recycle (an ETF!) |
| CC | Circuit City (BK 2008) | 2026-06 | **The Chemours Company** | recycle |
| RSH | RadioShack (2015) | 2026-06 | `1664541` / MUTUALFUND | recycle (junk) |
| WM | Washington Mutual (2008) | 2026-06 | **Waste Management, Inc.** | recycle |

Genuinely-dead, non-recycled tickers (LEH, BSC, EK, BBI + all Q-suffix BK variants SUNEQ/SHLDQ/LEHMQ/CCTYQ/RSHCQ/WAMUQ/BBIQ) → `0-timestamps` or HTTP 404. **Real delisted-series coverage = 0/9 companies.** Using any apparent hit would inject the wrong company's prices into the backtest — worse than excluding it.

### Stooq — bot-walled (re-confirmed)
`https://stooq.com/q/d/l/?s=<t>.us&i=d` returned an HTML CAPTCHA page (`<!DOCTYPE html>…`) for every ticker incl. live controls. Matches the standing TOOLS.md note ("Stooq is now CAPTCHA/apikey-gated → not headless-automatable"). Dead from this datacenter IP.

### AlphaVantage / Tiingo — no key
`.env` contains only `APCA_*` (Alpaca) + `FRED_API_KEY`. No equity-history key with delisted coverage. (AlphaVantage free = 25 req/day anyway; would not reach universe scale, and its free `TIME_SERIES_DAILY` does not guarantee delisted names.)

**Net: 0 free sources deliver genuine delisted daily price history from this VM.**

---

## Task 3 — Universe-scale survivorship feasibility

Point-in-time filer set vs current survivor list:

- `xbrl/frames/us-gaap/Assets/USD/CY2014Q4I.json` → **7,494 unique CIKs** (who actually reported as of 2014Q4)
- current `company_tickers.json` → **8,021 CIKs** (survivors)
- Intersection (still listed): **2,967 (39.6%)**
- **GONE from current list: 4,527 (60.4%)** — delisted / merged / went private

**Survivorship-bias magnitude ≈ 60% at the filer level** for a 2014→today window. A survivor-only universe silently drops the majority of names that existed — exactly the bias this lane was meant to remove.

**Residual bias if we build anyway:** we can price the ~40% survivors (Yahoo works for listed names) and ~0% of the 60% gone set (no free ticker resolution + no free delisted prices). So a "free" universe would be **~survivor-only** — i.e. it removes **~0 percentage points** of the 60.4% survivorship bias. No improvement over the universe we already have.

---

## VERDICT: 🔴 RED

**A free survivorship-clean (or even survivorship-much-reduced) equity universe is NOT achievable from this VM.**

Driving coverage number: **delisted price coverage = 0% genuine** (0/9 companies; all apparent hits are ticker-recycle false positives), and **free ticker resolution of gone filers = 0%** (0/60). The 60.4% survivorship hole is real and large, but **un-fillable for free** — we can quantify the bias but not remove it.

**Why this is a valuable kill:** the #1 lane (delisting-inclusive fundamentals L/S) is **not buildable on free data** and should stay parked. EDGAR gives us survivorship-clean *fundamentals* (genuinely useful — point-in-time, delisters retained), but a fundamentals L/S strategy needs *prices* to form/score positions and compute returns, and the delisted price leg is the unobtainable piece.

### What WOULD unblock it (all require a spend decision, not a free fix)
1. **Paid survivorship-bias-free price + delisting DB:** CRSP (gold standard, academic/commercial), Sharadar/Norgate (retail-priced, explicit delisted coverage + delisting returns), Polygon/Tiingo paid tiers, EODHD (has a delisted-tickers endpoint). A CIK↔historical-ticker↔price map with delisting dates is precisely the paid product.
2. **A free historical CIK→ticker map** would still only be half the bridge — even with tickers, the *prices* of dead names aren't free here.

### Salvage (free, lane-adjacent — does NOT need delisted prices)
- **PEAD / earnings-surprise drift** on the *current* survivor universe (EDGAR fundamentals × Yahoo prices for listed names) — already flagged free in TOOLS.md; sidesteps the delisted-price wall because it trades live names around earnings.
- **Fundamentals factors on survivors only**, explicitly labeled survivorship-biased, used for *research signal-discovery* (not capital allocation) until a paid price source lands.

---

## Files written
- `_probe_task1_cik_ticker.py`, `_probe_task1b_resolve.py` — CIK→ticker resolution tests
- `_probe_task2_prices.py` (burst, throttled), `_probe_task2b_yahoo.py` (careful), `_probe_task2c_recycle.py` (recycle proof)
- `_probe_task3_universe.py`, `_probe_task3b_resolve.py` — universe-scale + gone-set resolvability
- JSON results: `_task1_resolved.json`, `_task2b_yahoo.json`, `_task2c_recycle.json`, `_task3_universe.json`, `_task3b_resolve.json`
- All scratch under workspace root. No protected files touched, no crontab edits, no trades.
