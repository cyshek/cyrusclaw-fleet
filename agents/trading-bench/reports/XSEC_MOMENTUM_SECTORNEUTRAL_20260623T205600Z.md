# SECTOR-NEUTRAL XSEC MOMENTUM (Jegadeesh-Titman) — KILL-TEST MEMO

**Run:** 2026-06-23 20:56 UTC · `_xsec_momentum_sectorneutral_tests.py` · universe = 104 S&P100-ish survivors · START 2006-01-01 · cost 2bps one-way · OOS = 2020-01-01+

---

## ⛔ VERDICT: **CLOSE** — sector-neutralization did NOT rescue momentum; it made the L/S spread WORSE.

- **Sector-neutral 12-1 L/S OOS Sharpe = −0.111** (spread **−14.7%** OOS) — *negative*. Does NOT clear the 0.50 promote bar.
- **Plain (global) 12-1 L/S OOS Sharpe was +0.384** → sector-neutralization delta = **−0.495 (WORSE)**.
- 6-1: sector-neutral OOS Sharpe +0.114 vs plain +0.286 → delta **−0.172 (WORSE)**.
- Long-only sleeve **LOSES to the no-signal EW-104 control OOS** (142.7% vs 165.4%, Δ −22.7pp) → survivorship FAIL.
- All four L/S variants are **dead on cost** (breakeven bps NEGATIVE — the gross spread loses money before the 2bps charge).
- **Momentum is hereby parked** until we have a delisting-inclusive universe. The short leg cannot be cleaned on a today's-survivors panel — not globally, and not within-sector.

This is a clean, decisive negative. It was not manufactured into a win, and the thesis (within-sector ranking removes the contaminating cross-sector bet → cleaner spread) was **falsified**: removing the cross-sector tilt removed the one thing giving plain 12-1 its modest positive OOS, and the within-sector short leg remains survivor-poisoned with too little intra-sector momentum dispersion among mega-cap survivors.

---

## HEADLINE TABLE (the money question: plain vs sector-neutral)

Columns: FULL total-return / FULL Sharpe / OOS(2020+) total-return / OOS Sharpe. Sector-neutral = quintile-per-sector (primary cut).

| Sleeve | FULL tot | FULL Sharpe | OOS tot | **OOS Sharpe** |
|---|---:|---:|---:|---:|
| **12-1 SECTOR-NEUTRAL L/S** (this run) | −9.2% | 0.022 | −14.7% | **−0.111** |
| 12-1 PLAIN global L/S (prior run) | +28.8% | 0.161 | +48.1% | **+0.384** |
| → **Δ (SN − plain), 12-1** | | | | **−0.495 ⛔ WORSE** |
| **6-1 SECTOR-NEUTRAL L/S** (this run) | −19.0% | −0.029 | +4.2% | **+0.114** |
| 6-1 PLAIN global L/S (prior run) | −23.1% | 0.022 | +27.9% | **+0.286** |
| → **Δ (SN − plain), 6-1** | | | | **−0.172 ⛔ WORSE** |
| EW-104 control (no signal) | +2290.5% | 0.898 | +165.4% | 0.872 |
| SPY buy & hold | +743.4% | 0.638 | +150.1% | 0.801 |

**Both formations got worse under sector-neutralization.** The decisive test (the L/S spread) is negative-to-flat in every cut; the long-only sleeves are pure survivorship beta that lose to a dumb EW hold of the same 104 names.

### Both within-sector cuts (quintile + tercile), both formations — L/S spread

| L/S variant | FULL Sharpe | IS≤2019 Sharpe | OOS Sharpe | OOS tot | clears 0.50? |
|---|---:|---:|---:|---:|:--:|
| 12-1 quintile-per-sector (PRIMARY) | 0.022 | 0.096 | **−0.111** | −14.7% | ❌ |
| 12-1 tercile-per-sector | −0.039 | −0.026 | −0.063 | −9.0% | ❌ |
| 6-1 quintile-per-sector | −0.029 | −0.107 | +0.114 | +4.2% | ❌ |
| 6-1 tercile-per-sector | −0.118 | −0.209 | +0.043 | −0.9% | ❌ |

---

## 4-CRITERION PROMOTION VERDICT (on the L/S spread, OOS 2020+)

| Criterion | 12-1q | 12-1t | 6-1q | 6-1t |
|---|:--:|:--:|:--:|:--:|
| c1 — L/S OOS Sharpe ≥ 0.50 | ❌ −0.111 | ❌ −0.063 | ❌ +0.114 | ❌ +0.043 |
| c2 — L/S beats SPY OOS | ❌ | ❌ | ❌ | ❌ |
| c3 — L/S beats EW-104 OOS | ❌ | ❌ | ❌ | ❌ |
| c4 — L/S spread positive OOS | ❌ | ❌ | ✅ | ❌ |
| **DECISION** | **SHELF/CLOSE** | **SHELF/CLOSE** | **SHELF/CLOSE** | **SHELF/CLOSE** |

No variant passes a single criterion fully except c4 (mere positivity) for 6-1q, which is +4.2% over five years — economically nil and dead on cost.

---

## LANE-HONESTY GUARDS (`runner/lane_honesty.py`, verbatim)

```
=== LANE HONESTY: FAIL ===
  [SURVIVORSHIP FAIL] signal OOS tot +1.4270 vs EW +1.6543 (Δ -0.2273) | L/S spread OOS tot -0.1474 Sharpe -0.111 — LOSES to no-signal EW hold of same universe by -22.7pp OOS — survivorship beta, not alpha
  [OOS-MIRAGE PASS] full +0.021 / IS +0.096 / OOS -0.111 — full/IS Sharpe support the OOS result (not an OOS-only mirage)
  FAILURES: SURVIVORSHIP: LOSES to no-signal EW hold of same universe by -22.7pp OOS — survivorship beta, not alpha
```

- **Survivorship: FAIL.** The long-only top-fraction-per-sector sleeve loses to the no-signal EW-104 control by 22.7pp OOS, and the L/S spread is negative OOS. Classic survivorship-beta-in-disguise — the long-only "beats SPY" is just owning today's winners, and once you neutralize that (the L/S spread), there is no edge left.
- **OOS-mirage: PASS** (not a mirage — full/IS/OOS Sharpe are *consistently* ~0/negative; this lane is uniformly bad, not a one-regime fluke).

**Survivorship-neutrality note (reported FIRST, per rails):** the sector-neutral L/S spread is survivorship-neutral AND sector-neutral *by construction* (both legs drawn from the same 104 names, now also balanced within each sector). That construction is exactly why it is the decisive test — and it comes back **negative**. The MANDATORY no-signal EW-104 control was run and the long-only sleeve fails to beat it OOS.

---

## LOOKAHEAD CANARY (no-leak proof)

```
honest 12-1 sector-neutral L/S full Sharpe = 0.022
cheat  (forward-peek, includes traded month) = 3.541
paths_differ = True   honest < cheat = True   ✅
```

A forward-peeking variant scores a fantastical 3.54 Sharpe vs the honest 0.02 — a gigantic, correct gap. The honest path is strictly past-only (12-1 skip-1 ranked at prior-month-end, traded the following month); no leakage. (The 3.54 cheat number is itself a vivid reminder of how much "edge" a single month of lookahead fabricates — and how worthless this signal is without it.)

---

## SECTOR MAP (SEC SIC → coarse SIC-division bucket)

Source: SEC submissions API `sic`/`sicDescription` (cached to `data_cache/edgar_submissions/*.json`; full table at `reports/_xsec_sector_map.json`). 16 buckets, all 104 names mapped. Used **as-is** (no hand-overrides) — mega-caps cluster by SIC, which is sensible for momentum and fully auditable.

| Sector | n | Members |
|---|--:|---|
| Industrials | 22 | ACN BA BKNG CAT DE DHR DIS EMR GD GE HON ITW LMT MA NSC PYPL RTX SPGI TMO UNP V WM |
| Financials | 17 | AON AXP BAC BLK BRK-B CB CI CME ELV GS ICE JPM MS PGR SCHW UNH WFC |
| Pharma | 10 | ABBV ABT AMGN BMY GILD JNJ LLY MRK REGN ZTS |
| ConsumerDiscretionary | 9 | AMZN COST HD LOW MCD NKE SBUX TJX WMT |
| TechSoftware | 8 | ADBE ADP CRM GOOGL INTU META MSFT NOW |
| Semiconductors | 6 | AMD AVGO INTC MU NVDA TXN |
| Energy | 5 | COP CVX EOG SLB XOM |
| TechHardware | 4 | AAPL CSCO IBM QCOM |
| ConsumerStaples | 4 | KO MO PEP PM |
| CommServices | 4 | CMCSA NFLX T VZ |
| MedDevices | 4 | BSX ISRG MDT SYK |
| Chemicals | 3 | APD LIN PG |
| Utilities | 3 | DUK NEE SO |
| RealEstate | 3 | AMT EQIX PLD |
| **AutoTransport** | **1** | TSLA — **dropped from L/S (singleton)** |
| **Materials** | **1** | FCX — **dropped from L/S (singleton)** |

**Within-sector cut:** PRIMARY = **quintile-per-sector** (within-sector fraction 0.20, matching the plain run's 0.2 for apples-to-apples); ROBUSTNESS = **tercile-per-sector** (0.3333). Per-sector pick `k = max(1, round(n_sector × frac))`, capped at `⌊n_sector/2⌋` so the long and short legs are disjoint within every sector. A sector needs ≥2 names to contribute both legs.

- **Names dropped:** only the **2 singletons (TSLA, FCX)** — they have no within-sector counterpart, so they sit out the L/S every month (frac_dropped = 1.00). All 14 multi-name sectors contribute both legs every month (frac_dropped = 0.00).
- **Resulting book (12-1q):** ~21.6 longs / ~21.6 shorts pooled across 14 sectors per rebalance — equal long/short exposure within each sector ⇒ genuinely sector-neutral by construction.
- Per-sector k/leg (12-1q): Industrials 4, Financials 3, Pharma/ConsDisc 2, TechSoftware ~1.6, all others 1.

**Auditable SIC quirks (used as-is, not overridden):** V/MA/PYPL/ACN file as SIC 7389 "Business Services" and SPGI as 7320 "Consumer Credit Reporting" → all land in *Industrials* (the SIC reality for payment networks / data / consulting). UNH/CI/ELV file as 6324 "Hospital & Medical Service Plans" → *Financials* (managed-care insurers). DIS files as 7990 "Amusement & Recreation" → *Industrials* (services residual). NKE = 3021 rubber footwear → *ConsumerDiscretionary*. None of these change the conclusion; documented for transparency.

---

## COST / TURNOVER / BREAKEVEN

| L/S variant | turnover/rebal | breakeven (bps, 1-way) | alive on 2bps cost? |
|---|--:|--:|:--:|
| 12-1 quintile-per-sector | 25.7% | **−12.8** | ❌ dead |
| 12-1 tercile-per-sector | 21.1% | **−31.8** | ❌ dead |
| 6-1 quintile-per-sector | 35.5% | **−20.2** | ❌ dead |
| 6-1 tercile-per-sector | 30.3% | **−36.3** | ❌ dead |

All breakevens are **negative**, meaning the GROSS L/S spread already loses money — there is no cost level at which this is alive. (For reference the plain global 12-1 L/S had a *positive* breakeven of +50.4 bps; sector-neutralization destroyed even that, because it stripped out the profitable cross-sector tilt.) Turnover is comparable to / slightly **lower** than the plain global cut (plain 12-1 ≈ 24.5%/rebal vs sector-neutral 25.7%) — so the failure is **not** a turnover-cost story; the raw spread is simply unprofitable.

---

## KILLER-WINDOW REGIME TABLE (12-1 quintile-per-sector L/S vs long-only / EW-104 / SPY)

| Window | n | **L/S tot** | L/S Sharpe | long-only | EW-104 | SPY |
|---|--:|--:|--:|--:|--:|--:|
| 2008-09 GFC crash | 146 | −26.12% | −2.13 | −34.48% | −28.21% | −36.95% |
| 2009 junk-rally | 128 | **−32.87%** | −3.63 | +28.84% | +51.07% | +40.37% |
| 2011 debt-ceiling | 64 | −3.77% | −1.11 | −16.14% | −13.06% | −13.82% |
| 2018-Q4 selloff | 63 | +1.15% | +0.39 | −11.23% | −11.11% | −13.53% |
| 2020-Q1 covid crash | 41 | −0.91% | −0.45 | −16.57% | −17.91% | −19.42% |
| 2020-21 high-beta melt | 252 | **−13.70%** | −0.63 | +44.74% | +62.87% | +56.23% |
| 2022 bear (full yr) | 251 | −7.64% | −0.48 | −11.51% | −8.01% | −18.18% |
| 2022-H1 bear | 124 | −2.10% | −0.26 | −18.79% | −15.72% | −19.98% |
| 2023-H1 recovery | 124 | −9.22% | −1.67 | +6.11% | +11.40% | +16.79% |
| 2025-Q1 tariff bear | 61 | −2.05% | −0.64 | −7.01% | −4.11% | −7.58% |

**The L/S spread lost in 9 of 10 stress windows** (only the 2018-Q4 selloff was a tiny +1.15%). The two worst beatings are the canonical momentum-crash quarters — the **2009 junk-rally (−32.87%)** and the **2020-21 high-beta melt-up (−13.70%)** — exactly when beaten-down low-momentum survivors snap back hardest and run over the short leg. Sector-neutralizing did nothing to soften these; the short-leg survivorship problem is intra-sector too.

---

## ROBUSTNESS SWEEP (sector-neutral L/S, lookback × within-sector bucket × cadence)

| lookback | within-sec bucket | cadence | full Sharpe | IS Sharpe | OOS Sharpe | OOS tot |
|--:|--:|:--:|--:|--:|--:|--:|
| 6 | 0.20 | M | −0.029 | −0.107 | 0.114 | +4.2% |
| 6 | 0.20 | Q | −0.007 | −0.192 | **0.337** | +24.7% |
| 6 | 0.333 | M | −0.118 | −0.209 | 0.043 | −0.9% |
| 6 | 0.333 | Q | −0.101 | −0.255 | 0.190 | +9.5% |
| 9 | 0.20 | M | −0.004 | −0.025 | 0.032 | −3.3% |
| 9 | 0.20 | Q | 0.022 | −0.022 | 0.100 | +3.0% |
| 9 | 0.333 | M | −0.064 | −0.086 | −0.027 | −6.2% |
| 9 | 0.333 | Q | −0.056 | −0.131 | 0.075 | +1.4% |
| 12 | 0.20 | M | 0.022 | 0.096 | −0.111 | −14.7% |
| 12 | 0.20 | Q | 0.038 | −0.015 | 0.136 | +6.1% |
| 12 | 0.333 | M | −0.039 | −0.026 | −0.063 | −9.0% |
| 12 | 0.333 | Q | −0.056 | −0.103 | 0.031 | −1.7% |

**Every one of the 12 configs has full-period Sharpe ≤ +0.038.** The single best OOS number anywhere (6-1 quarterly, +0.337) sits on **negative full Sharpe AND negative IS Sharpe** — a textbook single-regime OOS fragment, not a forward edge (and still below 0.50). No corner of the parameter space produces a real spread. This is a uniformly dead lane, not an unlucky parameter choice.

---

## HONEST INTERPRETATION — why sector-neutralization didn't help

The thesis was that ranking momentum WITHIN sector removes the cross-sector bet "contaminating" the plain L/S short leg, yielding a cleaner, stronger spread. **The data falsifies it on both counts:**

1. **The cross-sector tilt wasn't contamination — it was the only source of plain-momentum's modest positive.** Plain 12-1 L/S earned +0.384 OOS largely by being long whole high-momentum sectors (tech/semis) and short whole low-momentum ones (energy/staples) over the 2020+ tech run. Neutralizing sectors deletes exactly that bet, and what remains — *intra-sector* winner-minus-loser among mega-caps — has no edge (−0.111 OOS). We removed the baby with the bathwater.

2. **The short-leg survivorship poison persists within sector.** Our 104 names are today's survivors, so every name (in every sector) is a stock that *didn't* go to zero. Within a sector, "lowest-momentum survivor" is disproportionately a beaten-down name about to mean-revert (it survived, after all) — so shorting it loses, hard, in junk rallies (−32.87% in 2009, −13.70% in 2020-21). Sector-bucketing changes *which* survivors you short, not the fact that you're shorting future-survivors. The L/S spread lost in 9/10 stress windows.

3. **Mega-cap intra-sector momentum dispersion is too low to overcome cost.** With ~1–4 names per leg per sector among highly-correlated large caps, the within-sector winner/loser gap is thin and noisy. Gross breakeven is **negative** — the spread doesn't even cover zero, let alone 2bps. Tighter (tercile) cuts made it *worse*, not better (more middling names diluting an already-absent signal).

**Bottom line:** momentum on a today's-survivors mega-cap panel is not salvageable by sector-neutralization. The honest defect is the universe (survivorship in the short leg), not the ranking geometry. **CLOSE this lane and park cross-sectional momentum until we have a delisting-inclusive (point-in-time constituent) universe** — only a panel that includes the names that actually went to zero can give the momentum short leg an honest chance. No paper-tracking is warranted; nothing here cleared the bar.

---

## ARTIFACTS & REPRODUCIBILITY
- Backtest script: `_xsec_momentum_sectorneutral_tests.py` (runs clean, exit 0; copy of the plain harness with ONLY the ranking step changed to within-sector pooled selection).
- Result JSON: `reports/_xsec_momentum_sectorneutral_result.json`
- Sector map: `reports/_xsec_sector_map.json` (+ raw cache `data_cache/edgar_submissions/*.json`, 104 files)
- Sector-map builder: `_build_sector_map.py`
- Plain-momentum comparison source: `reports/_xsec_momentum_result.json`
- Scope: RESEARCH/candidate only — no live wiring, no cron, no promotion, no protected files modified.
