# AQR / Man / Multi-Strat Reading Sprint — Hypothesis Shortlist

**Date:** 2026-06-24
**Author:** Tessera (trading-bench)
**Type:** Hypothesis-generation sprint (research-only; no code shipped, no config changed)
**Mandate (main cron):** Survey the public quant-research corpus across 4 candidate classes — cross-asset/macro lead-lag, dispersion/correlation, fundamentals-PIT, analyst-revision — for structural edges NOT yet tried as return engines in our book. Filter to ideas with **breakeven ≥ 2bps/side, corr < ~0.3 to OHLCV, span 2008+**. Output a ranked ≤5-idea shortlist + top pick.

**Method:** 3 opus subagents read the corpus (web/SSRN/AQR/Man are Cloudflare/JS-walled from this datacenter IP, so they synthesized from domain knowledge of the literature + data-reality I handed them); **I independently data-probed the two most testable claims myself** and that measurement *corrected the ranking* in two places (noted below). Closed-lane memory was loaded first so nothing dead gets re-pitched.

---

## TL;DR — the shortlist (ranked)

| # | Idea | Class | Orthogonal? | Turnover / breakeven | 2008+ | Data | Verdict |
|---|---|---|---|---|---|---|---|
| **1** | **Delisting-inclusive PIT universe (iterated EDGAR frames) → L/S value+quality** | Fundamentals-PIT | **Yes (L/S, survivorship-clean)** | monthly, low / ≫2bps | ⚠️ 2010+ (XBRL floor) | EDGAR ✅ (verified) + delisted-price resolver (build) | **BUILD NEXT** |
| **2** | **Standalone multi-asset TSMOM sleeve** (DBC/GLD/TLT/UUP, 12-1, return-weighted) | Cross-asset/macro | Yes (~0.21–0.28 to blend) | monthly long/flat, low / ≫10bps | ✅ 2010+ | Yahoo ETFs ✅ | **BUILD (1 clean run)** |
| **3** | **Implied−realized correlation spread** (COR1M − realized pairwise corr) as crash/complacency gauge | Dispersion | Partially (spread strips most beta) | low-moderate / clears 2bps | ✅ 2006+ | CBOE COR ✅ + ETF adjclose | **PROTOTYPE (probe first)** |
| 4 | Macro-momentum cross-sectional rank (L/S multi-asset) | Cross-asset/macro | Yes (mkt-neutral) | monthly, moderate | ✅ | Yahoo ETFs | maybe — risks xsec saturation |
| 5 | COR3M percentile as equity risk-on/off throttle | Dispersion | **No — falsified** | very low | ✅ | CBOE COR | **SKIP (my probe killed it)** |

**Top pick for the next build sprint: #1 — the delisting-inclusive EDGAR-frames universe.** It is the only idea that *removes the binding constraint* the whole cross-sectional program has been stuck on (survivorship), and I verified the core mechanism is real and free.

---

## 1. Top pick — Delisting-inclusive PIT universe via iterated EDGAR frames (Fundamentals-PIT)

**Why this is #1:** Last week four cross-sectional lanes (fundamentals-PIT quality/value, BAB, xsec-momentum, PEAD) all closed on the *identical* pathology — an equal-weight of the same fixed modern-survivor universe beat the factor → the "edge" was survivorship-beta, not alpha. The standing conclusion was *"the binding constraint is the UNIVERSE, not the signal."* This idea attacks the universe directly.

**The mechanism (VERIFIED by me, not just asserted):**
- `xbrl/frames/us-gaap/Assets/USD/CY2014Q4I.json` returns **7,494 unique CIKs** — *whoever filed that quarter*, not today's survivors.
- EDGAR **does not purge delisted filers.** Confirmed live from this VM:
  - **SunEdison** (CIK 945436, BK 2016): 260 datapoints, filings **2009-08-05 → 2015-11-09** (terminates at its last pre-BK filing). **Absent** from current `company_tickers.json`.
  - **Sears Holdings** (CIK 1310067, BK 2018): 340 datapoints, **2010-08-20 → 2018-12-13**.
- So **iterating frames quarter-by-quarter reconstructs an approximately point-in-time filer universe that includes eventual-delisters** — this is option (a) of the Cross-Sec Gate ("delisting-inclusive PIT universe"), achieved for **$0**, no CRSP/Compustat.

**The real blocker (honest):** delisted **CIK→ticker→price**. Current `company_tickers.json` (8,021 CIKs) excludes delisters, and Yahoo adjclose won't reliably have delisted-ticker returns. Free fix = harvest historical symbols from each delisted CIK's own filing headers / EDGAR `submissions` JSON, then source delisted prices from an archive (stooq/EDGAR). **This is data plumbing, not a paid feed** — but it's the build's hard ~30% and the part most likely to dead-end. The first sprint task is exactly: build the frames-iterator + delisted-price resolver and prove/kill price coverage *before* touching the signal.

- **Survivorship-addressing:** ✅ (the entire bar — passes by design, mechanism verified).
- **Turnover/breakeven:** monthly fundamentals, low turnover, breakeven ≫ 2bps (never the constraint here — measured 9,401bps on the prior PIT lane).
- **Orthogonality:** an L/S spread on a survivorship-clean universe is structurally decorrelated from a long-only equity-beta book.
- **Caveat:** 2010+ only (XBRL mandate floor) — covers the 2011, 2015-16, 2018-Q4, 2020, 2022 stress episodes but **not 2008 itself**. Acceptable but worth stating.

## 2. Standalone multi-asset TSMOM sleeve (Cross-asset/macro)

**Source:** AQR "Time Series Momentum" (Moskowitz-Ooi-Pedersen 2012) + "A Century of Evidence on Trend-Following." 12-1 time-series momentum, long/flat, over the **DBC / GLD / TLT / UUP** basket we already cache.

**Why it's genuinely new:** the bench has run multi-asset trend **only as an inverse-vol *overlay*** that gutted raw return (the inv-vol weighting was the killer, not the signal) — it has **never been judged as its own return sleeve on its own merits.** Managed-futures trend proxies (KMLM/DBMF) measured **−0.37/−0.38** vs our blend in 2022 and SYN_TREND full corr **0.21–0.28** → genuinely diversifying, and it's the kind of crisis-alpha sleeve that pays exactly when the equity book bleeds.

- **Orthogonality:** ✅ a trend sleeve on bonds+commodities+FX ≈ 0.2–0.3 to US-equity OHLCV.
- **Turnover/breakeven:** monthly long/flat, low; breakeven ≫ 10bps.
- **Data:** 100% from our Yahoo ETFs, 2010+. Spans 2008 if extended to the underlying futures-proxy history.
- **Verdict:** worth **one clean standalone run**, return-weighted (NOT inv-vol). Low build cost — could be a fast second sprint.

## 3. Implied−realized correlation spread (Dispersion) — prototype, probe-gated

**The dispersion data is now reachable** — a genuinely new finding this sprint: the CBOE CDN serves, keyless + HTTP-200 from our datacenter IP (the index path is open even though CBOE P/C-ratio CSVs are 403):
- **COR1M / COR3M / COR30D** (CBOE Implied Correlation): daily OHLC **2006-01-03 → 2026** (~5,150 rows, **spans 2008**). Cached.
- DSPX (2014→, no 2008), RVOL (2001→Feb-2025).

**But I falsified the naive expression myself (this is why #5 is SKIP and #3 is only "prototype"):** I probed COR3M vs SPY over 5,134 common days (`_disp_ortho_probe.py`):
- `corr(ΔCOR3M, SPY_ret) = −0.609` → the daily *change* in implied correlation is strongly inverse-SPY = a **lagging beta proxy, not orthogonal**.
- `corr(COR3M level, fwd 5d/21d SPY ret) = +0.04 / +0.09` → the **level has ~zero linear forward predictive power.**
- forward-21d SPY return by COR-level quintile is **non-monotone and backwards** — Q5 (highest implied corr) shows the *highest* forward return (+26.7% ann) vs Q1 +10.6%. High implied correlation clusters near panic bottoms where forward equity returns are strong ("buy-the-fear"), so a "high corr → de-risk" throttle would be wrong-signed.

**Conclusion:** the orthogonal content is **not** in the level/throttle (#5, dead) — it's in the **implied−realized spread** (the correlation risk premium; Driessen-Maenhout-Vilkov 2009 showed the index variance risk premium ≈ correlation risk premium). Building a realized pairwise-correlation series from our sector-ETF adjclose and trading `COR1M − realized` as a complacency/crash gauge *strips most of the inverse-SPY level* and is the defensible expression. **Prototype-gate:** before a full build, repeat my orthogonality probe on the *spread* (not the level) — if `corr(spread, SPY trend) < 0.3` and the spread sorts forward returns monotonically, promote to a build; else shelf the whole dispersion class.

- **Turnover/breakeven:** COR3M lag-1 autocorr 0.987, ~14 median-crosses/yr → very low turnover, clears 2bps by orders of magnitude. (Cost is never the dispersion constraint; orthogonality is.)

## 4. Macro-momentum cross-sectional rank — maybe

AQR "Macro Momentum" (Brooks 2017): rank the cross-section of bond/commodity/FX/equity proxies on trailing macro+price momentum, market-neutral L/S. Structurally orthogonal (mkt-neutral, non-US-equity). **But** risks repeating the prior `xsec_momentum_xa` finding (signal saturates at ~6 assets; TLT/VNQ never selected). Pre-flight that note before committing. Conditional.

## 5. COR3M percentile equity throttle — SKIP (falsified)

Documented above — my own probe killed it. Kept in the report as a recorded negative so it isn't re-pitched.

---

## What's confirmed DEAD this sprint (do not re-pitch)

- **Cross-asset/macro equity-timing overlays** (yield-curve, Dr-Copper, FX-trend, credit HYG/LQD, NFCI, VIX-term) — all closed; NFCI rescues 2022 DD but OOS dies on +1d lag and doesn't fire earlier than SMA-200.
- **Further inv-vol trend / carry-leg constructions** (3rd-sleeve, capped-allocator, bond+commodity carry, commodity roll-yield) — tested to exhaustion 2026-06-23.
- **Analyst-revision history** — PARKED, data-walled. Historical PIT consensus is paid everywhere free (Finnhub/Tiingo/SimFin gated; Zacks/IBES commercial). Only Nasdaq forward-snapshot collection is free → no 2008+ backfill → not backtestable. The realized-SUE proxy = PEAD = already closed.

## Recommended sequencing

1. **#1 (delisting-inclusive EDGAR universe)** — highest payoff (removes the universe constraint blocking the entire cross-sectional program), mechanism verified; the price-resolver is the make-or-break first task.
2. **#2 (standalone multi-asset TSMOM sleeve)** — cheap, fast, genuinely diversifying crisis-alpha; good parallel/second sprint.
3. **#3 (implied−realized corr spread)** — prototype-gate on the *spread's* orthogonality probe before a full build; the data is now in hand.

---
*Artifacts: probes `_disp_ortho_probe.py` (COR vs SPY orthogonality), `_edgar_delister_probe.py` (delisted-filer retention). New data cached: `data_cache/cboe/{COR1M,COR3M,COR30D,DSPX,RVOL}_History.csv`. No protected file touched; no config changed; nothing scheduled. Subagent raw findings logged in `memory/2026-06-24.md`.*

---

## ⚠️ UPDATE (same day, post-build-probe): #1 was KILLED — verdict RED

The #1 top pick (delisting-inclusive EDGAR-frames universe) was sent straight to a make-or-break feasibility probe and **failed the price-leg gate.** Verdict: **🔴 RED — a free survivorship-clean equity universe is NOT achievable from this VM.** Verified independently (`_verify_recycle.py`):

- **Delisted CIK→ticker: 0/60 free.** EDGAR submissions `tickers[]` is current-state, not point-in-time; all confirmed delisters show `tickers=[]` and are absent from `company_tickers.json`. EDGAR keeps the *fundamentals* but strips the *ticker*.
- **Delisted prices: 0/9 free (the make-or-break).** Every Yahoo "hit" is a ticker-recycle false positive — confirmed via `longName`: SUNE→"SUNation Energy" (runs to 2026, not SunEdison-2016), SHLD→"Global X Defense ETF" (starts 2023, after Sears-2018), CC→"Chemours", WM→"Waste Management". Stooq is CAPTCHA-walled; no keyed archive on disk.
- **Survivorship magnitude:** CY2014Q4 frame = 7,494 CIKs; **60.4% (4,527) gone** from the current survivor list — large, real, **un-fillable for free.**

**Net:** EDGAR delivers survivorship-clean *fundamentals*, but a fundamentals L/S needs *prices*, and the delisted-price leg is the unobtainable-for-free piece. **Unblocking requires a paid survivorship-bias-free DB (CRSP / Sharadar / Norgate / EODHD) — a Cyrus spend decision, not a free build.** The lane is parked there. Full probe: `reports/EDGAR_DELISTED_UNIVERSE_PROBE_20260624T171848Z.md`.

**Revised actionable shortlist:** with #1 gated behind a paid feed, the live free build candidates are **#2 (standalone multi-asset TSMOM sleeve — in progress)** and **#3 (implied−realized correlation spread — prototype-gated).**
