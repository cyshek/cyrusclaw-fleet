# FUNDAMENTALS-PIT QUALITY/VALUE — does a point-in-time fundamentals tilt beat buy-and-hold SPY?

**UTC build stamp:** 20260623T183915Z · **Lane:** candidate research (reversible; no live/protected files touched) · **Author:** trading-bench subagent (opus)
**Engine:** `_fundamentals_pit_tests.py` · **Raw results:** `reports/_fundamentals_pit_result.json` · **Data cache:** `data_cache/edgar_fundamentals/` (1,457 files)

---

## VERDICT (read this first)

**CLOSE.** This is a **clean negative**. The first genuinely orthogonal-to-OHLCV signal class the bench has tried as a return engine does **not** beat buy-and-hold SPY in any honest sense.

- ✅ It "beats" SPY on **full-period raw return** (1370% vs 815%, Sharpe 1.02 vs 0.90)…
- ❌ …but it **loses out-of-sample** (2019+: 208% vs SPY 230%).
- ❌ The **long/short spread is decisively negative** (−52% full, −31% OOS, Sharpe −0.43) — there is no monotonic cross-sectional signal separating winners from losers.
- ❌ **The decisive test:** an equal-weight basket of the same 104 names with **zero factor tilt** beats SPY by *more* than the factor strategy (1517% vs 1370% full; 258% vs 208% OOS). **The factor tilt subtracts value versus its own equal-weight universe.**

The apparent full-period win is **100% survivorship bias** — picking today's S&P-100 survivors and equal-weighting them (a small-cap-within-large-cap tilt) beats SPY regardless of any fundamentals signal. The quality/value composite contributes nothing; it actively destroys return relative to naive equal-weight. **Cost is a non-issue** (breakeven 9,401 bps one-way vs 2 bps charged), and **there is no lookahead** (canary clean) — the negative is real, not an artifact of cost or leakage.

**What would need to be true to revisit:** a survivorship-bias-free universe (point-in-time index constituents *including delisted names*), on which the **long/short spread** — not the long-only book — shows a positive, OOS-stable, plateau-robust edge net of cost. Until the spread is positive on a clean universe, there is no fundamentals return engine here.

---

## 1. Universe & the survivorship caveat (the whole story)

**Universe:** 104 current large-caps (≈ S&P 100 constituents) mappable to both an EDGAR CIK and a cached Yahoo price series. List + CIK map in `data_cache/edgar_fundamentals/universe.json`. (GOOG dropped — duplicate CIK with GOOGL; MMC dropped — no CIK/price cache.)

**This universe is survivorship-biased by construction**, and that bias *is* the result. These are the names that are large-cap *today, in 2026* — i.e. the winners that survived and grew across 2010–2026. Backtesting a 2010-start strategy on 2026's survivors bakes in forward-looking selection: you are guaranteed to be holding the companies that did well, and you never hold the ones that were large in 2012 and then collapsed (GE-classic, Lehman-already-gone, the energy/retail busts, etc.).

The assignment flagged this explicitly and asked me to *measure the bias magnitude rather than hand-wave it*. I did — see §6. The bias is large enough to fully explain the headline number.

---

## 2. Point-in-time construction & lookahead proof

Every fundamental is sourced from **SEC EDGAR `data.sec.gov` companyconcept JSON** (free, no key, 200 OK from this datacenter IP with a declared `User-Agent: trading-bench-research …` header). Each XBRL fact carries `filed`, `end`, `fy`, `fp`.

**PIT rule (the anti-lookahead ballgame):** for any as-of rebalance date *T*, for each `(concept)` I select the fact with the **largest `filed` ≤ T** (ties broken by latest period `end`). Restatements are *new, later-filed rows* — they are never applied before their own `filed` date. Flows (income/revenue) are summed TTM PIT-safely (latest recent annual, else last 4 distinct-end quarters, all `filed` ≤ T). Balance-sheet items are taken as the latest `filed`-≤-T point value. Market-cap denominator = (PIT shares outstanding via `dei/EntityCommonStockSharesOutstanding`, `filed` ≤ T) × (raw close at T).

**Lookahead canary:** every snapshot records the max `filed` date of any fact it touches and asserts `filed ≤ asof`; a violation is appended to a global list. **Result: 0 violations** across the full backtest (and across 60 quarter-end unit-test snapshots). Verified example: as of 2015-06-30, AAPL equity = $129.0B from a fact **filed 2015-04-28** (Q1 end 2015-03-28) — correctly the most-recent *filed* fact, not a future period. Reporting lag (10-Q/10-K filed 30–90 days after period end) is handled automatically by filed-date masking.

**XBRL floor:** data is rich from ~mid-2009 (XBRL mandate). Backtest starts **2010-06-01** to give every name a clean year of filed history before first use.

---

## 3. The composite (sub-factor definitions)

At each rebalance, every name's PIT sub-factors are computed, **cross-sectionally robust-z-scored** (median/MAD, winsorized ±3), and averaged into a VALUE tilt, a QUALITY tilt, and a combined composite. Higher = more attractive (cheap + high-quality). Sub-factors with sign conventions:

| Tilt | Sub-factor | Definition | Sign |
|---|---|---|---|
| **Value** | Earnings yield (E/P) | NI_ttm / mktcap | + (cheaper) |
| **Value** | Book-to-market (B/P) | Equity / mktcap | + |
| **Quality** | ROE | NI_ttm / Equity | + |
| **Quality** | ROA | NI_ttm / Assets | + |
| **Quality** | Gross-profitability | GrossProfit_ttm / Assets (or (Rev−COGS)/Assets) | + |
| **Quality** | Low-leverage | Equity / Assets | + (less levered) |
| **Quality** | Low-accruals (Sloan) | −ΔNOA / Assets, NOA = (Assets−Cash) − (Liab−LTD) | + (lower NOA growth) |

**Concept-coverage gaps (documented, not fudged):** a probe of EDGAR coverage found `NetIncomeLoss / StockholdersEquity / Assets` are **universal**, but `GrossProfit`, `AssetsCurrent`, `LiabilitiesCurrent` **404 for financials/some energy** (banks don't report them). Where a sub-factor's inputs are missing for a name, that sub-factor is **omitted for that name** and the tilt averages over whatever sub-factors *are* available (≥1 required). This is why the robust core (E/P, B/P, ROE, ROA, leverage) carries the composite; gross-profitability and accruals are sparse contributors. The gap is disclosed, not silently zero-filled.

---

## 4. Headline results (strategy vs SPY buy-and-hold, same traded path, net 2 bps)

**Primary config:** monthly rebalance, **long top-quintile (20%)**, equal-weight, combined composite. ~20 names held, 193 rebalances, **avg turnover 7.6%/rebal**.

| Span | Strat Sharpe | Strat ret | Strat maxDD | SPY Sharpe | SPY ret | SPY maxDD | Beats SPY raw? |
|---|---|---|---|---|---|---|---|
| **FULL** (2010-06→2026) | 1.02 | **+1370%** | −36.3% | 0.90 | +815% | −33.7% | ✅ yes |
| **IS** (pre-2019) | 1.23 | +376% | −18.2% | 0.88 | +177% | −19.4% | ✅ yes (+199pp) |
| **OOS** (2019+) | 0.84 | +208% | −36.3% | 0.92 | +230% | −33.7% | ❌ **no (−21pp)** |

**The win is entirely IS-loaded.** Out-of-sample, the strategy underperforms SPY on raw return *and* Sharpe, with a *worse* drawdown. An edge that lives only before the OOS split is the textbook overfit / artifact signature.

---

## 5. Long/short spread — the smoking gun

**Long top-quintile minus short bottom-quintile**, monthly, net 2 bps:

| Span | Sharpe | Total return | maxDD |
|---|---|---|---|
| FULL | **−0.43** | **−52.3%** | −52.8% |
| OOS (2019+) | −0.41 | −31.1% | −34.3% |

If the composite were a genuine cross-sectional signal, shorting the *worst*-ranked names would **add** return. It does the opposite — the spread bleeds consistently. **There is no monotonic relationship between the composite and forward returns.** The long-only "outperformance" is not factor alpha; it's just being long a basket that happened to go up (survivorship beta).

---

## 6. The decisive survivorship control (EW-104, no factor tilt)

The single most important table in this report. **Equal-weight all 104 universe names, no factor signal whatsoever**, monthly rebalance, net 2 bps:

| Span | EW-104 (NO factor) | Factor composite | SPY | EW-104 beats SPY? | Factor beats EW-104? |
|---|---|---|---|---|---|
| **FULL** ret | **+1517%** (Sh 1.11) | +1370% (Sh 1.02) | +815% (Sh 0.90) | ✅ +702pp | ❌ no (−147pp) |
| **IS** ret | +351% | +376% | +177% | ✅ | ~tie |
| **OOS** ret | **+258%** (Sh 1.01) | +208% (Sh 0.84) | +230% (Sh 0.92) | ✅ +28pp | ❌ **no (−50pp)** |

**Conclusion:** the survivorship-biased *universe alone* — with zero fundamentals input — beats SPY by 702pp full-period and is the *only* version that also beats SPY out-of-sample. **The fundamentals composite underperforms its own equal-weight universe both full and OOS.** The factor tilt is not just non-additive; it's *value-destroying* relative to naive EW. Every "win" attributed to quality/value in §4 is actually the universe, and the factor selection makes it worse.

This is the magnitude of the survivorship bias, quantified as requested: **the entire headline edge (+555pp of the factor strat's excess over SPY) is survivorship; the factor's own contribution is negative.**

---

## 7. Killer battery (named stress windows, total return strat vs SPY)

| Window | Strat | SPY | Better? |
|---|---|---|---|
| 2020-Q1 covid crash | −20.8% | −19.4% | ✗ |
| 2022 bear (full yr) | −17.4% | −18.2% | ✓ slight |
| 2022-H1 bear | −21.5% | −20.0% | ✗ |
| 2025-Q1 tariff bear | **0.0%** | −7.6% | ✓ notable |
| 2011 debt-ceiling | −10.8% | −13.8% | ✓ |
| 2018-Q4 selloff | −11.9% | −13.5% | ✓ |
| 2023-H1 recovery | +19.5% | +16.8% | ✓ |
| 2024-Q2 bull | +1.5% | +4.4% | ✗ |

Mixed (beats in 5/8). A mild quality/low-vol defensive flavor shows up in some bears (2025-tariff flat vs SPY −7.6%; 2011; 2018Q4), but it gives it back in the sharp ones (covid, 2022-H1) and lags clean bulls. **Not a haven, and not differentiable from "lower-beta large-cap basket."** GFC is below the XBRL floor (data starts 2010) so it's intentionally absent.

---

## 8. Robustness sweep — a plateau, but a *survivorship* plateau

12 configs (cadence M/Q × bucket 20%/33% × signal composite/value/quality), all net 2 bps:

| cad | bucket | signal | full Sh | full ret | full DD | OOS Sh | OOS ret | beats SPY full | turnover |
|---|---|---|---|---|---|---|---|---|---|
| M | 0.20 | composite | 1.02 | 1370% | −36.3 | 0.84 | 208% | ✓ | 0.076 |
| M | 0.20 | value | 1.07 | 1775% | −36.8 | 0.97 | 288% | ✓ | 0.061 |
| M | 0.20 | quality | 1.03 | 1216% | −34.0 | 0.82 | 185% | ✓ | 0.081 |
| M | 0.33 | composite | 1.08 | 1465% | −34.7 | 0.98 | 262% | ✓ | 0.062 |
| M | 0.33 | value | 1.07 | 1491% | −36.2 | 0.98 | 265% | ✓ | 0.050 |
| M | 0.33 | quality | 1.07 | 1266% | −33.3 | 0.95 | 229% | ✓ | 0.074 |
| Q | 0.20 | composite | 1.06 | 1587% | −39.1 | 0.90 | 242% | ✓ | 0.162 |
| Q | 0.20 | value | 1.07 | 1852% | −38.2 | 0.99 | 311% | ✓ | 0.125 |
| Q | 0.20 | quality | 1.06 | 1314% | −34.2 | 0.87 | 204% | ✓ | 0.187 |
| Q | 0.33 | composite | 1.09 | 1534% | −35.9 | 0.99 | 272% | ✓ | 0.135 |
| Q | 0.33 | value | 1.06 | 1515% | −38.6 | 1.00 | 280% | ✓ | 0.108 |
| Q | 0.33 | quality | 1.04 | 1169% | −34.4 | 0.88 | 202% | ✓ | 0.173 |

The full-period result is a **broad plateau** (no knife-edge argmax — that part is reassuring methodologically). **But §6 proves the plateau is the survivorship artifact**: it persists even with *zero* factor signal (EW-104 sits right in the middle of this table at 1517%). A plateau that is reproduced by the no-signal control is not evidence of edge. *Of note:* `value_z` is the only sub-tilt whose OOS raw return clears SPY (288–311% vs 230%) — but it still trails the EW-104 control OOS (258%)… wait, value_z OOS (288%) does exceed EW-104 OOS (258%). That is the one thread worth a footnote (see §9), though on a survivorship-biased universe it is not promotable.

---

## 9. Honesty rails check & the one loose thread

- **No lookahead:** canary 0 violations; PIT-select on `filed`; verified example + 60-snapshot unit test. ✅
- **Ranks from past-only data:** every fact `filed` ≤ rebalance date. ✅
- **SPY on the same traded path:** SPY return computed on the identical rebalance calendar. ✅
- **Full continuous-span Sharpe** (not median-of-windows), matching `runner/fp_sharpe` convention (mean/std·√252, ddof=1). ✅
- **2 bps one-way cost + breakeven:** breakeven **9,401 bps** ≫ 2 bps charged → cost is irrelevant at monthly/quarterly cadence (the low-turnover thesis held; turnover 5–19%/rebal). ✅
- **Survivorship disclosed + quantified:** §1, §6. The bias fully explains the headline. ✅
- **Concept gaps documented, not fudged:** §3. ✅

**The one loose thread (footnoted honestly, not promoted):** the `value_z` sub-tilt's OOS raw return (≈288–311%) edges out *both* SPY (230%) and the EW-104 control (258%) — i.e. cheap-names-within-survivors did add a little OOS. But (a) it's on a survivorship-biased universe, (b) the value *spread* (long-cheap/short-expensive) is part of the same composite whose overall L/S is −52%, and (c) a ~30–80pp OOS edge from a single sub-factor on a biased 104-name universe is exactly the kind of thin, fragile signal that vanishes on a clean universe. **Not promotable as-is.** It is the *only* reason this isn't a 100%-flat negative, and it points at where a clean-universe re-test should look (value spread specifically), not at a live strategy.

---

## 10. Disposition & what would change the call

**CLOSE** this as a return engine. Net of survivorship bias, the quality/value composite does not beat buy-and-hold SPY — it underperforms its own equal-weight universe, loses OOS, and has a negative long/short spread. The exercise was worth it: it's the first orthogonal-to-OHLCV class tested, the PIT/EDGAR infrastructure now exists and is validated (reusable), and the negative is *clean* (no cost-kill, no leakage — the signal genuinely isn't there).

**Shelf-with-trigger (not promote) conditions for a future revisit — all required:**
1. **Survivorship-free universe:** point-in-time index membership *including delisted names* (the missing piece; EDGAR has the delisted companies' fundamentals, but mapping historical S&P constituency + delisted price series is the real work). Without this, every number here is contaminated.
2. **Edge must show in the long/short spread**, not the long-only book — the spread is what isolates factor alpha from beta. Currently negative.
3. **OOS-stable + plateau-robust** against a *no-signal EW control on the same clean universe* (the control this report introduced). The factor must beat its own EW universe, not just SPY.
4. Candidate sub-factor to probe first: **value (E/P, B/P)** spread, the only thread with a faint OOS pulse here.

Absent (1)–(3), there is no fundamentals return engine to promote. Logged; infrastructure cached for reuse.

---

*Files: engine `_fundamentals_pit_tests.py`; JSON `reports/_fundamentals_pit_result.json` (includes `survivorship_control_ew104` + `VERDICT`); EDGAR cache `data_cache/edgar_fundamentals/` (104 names × 14 concepts, fetched once). Scratch builders `_bld1/2/3.py`, `_ew_control.py` retained for reproducibility. No `runner/*.py`, `strategies/*`, crontab, `*.db`, broker, paper-clock, or allocator files were touched.*
