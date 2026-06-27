# INDEX-LEVEL TS-VALUE × MOMENTUM-BOOK CORRELATION PROBE

**Generated:** 2026-06-27T07:50:38Z · **Lane:** AQR Reading Sprint #2/#3 — "Index-level Value+Momentum sleeve" (last untouched lane) · **Type:** correlation probe / feasibility gate (NOT a strategy build)

---

## ⛔ VERDICT: **NO** — CLOSE the lane.

> An index-level TS-value signal does **NOT** offer a distinct, gate-legal diversifying premium to our momentum book. It dies **on economics, not on data-sourcing**: every free index-level TS-value signal I could build is either (a) genuinely negatively correlated to momentum **but has no standalone expectancy** (it's a money-losing drag, partly relabeled short-momentum), or (b) has standalone expectancy **but is positively correlated** to momentum (not a diversifier). **No leg is simultaneously negative-and-imperfect-corr AND profitable standalone** — so the AQR "negative V/M correlation lifts the frontier" mechanism cannot fire here: adding a negatively-correlated money-loser bleeds the book instead of diversifying it. Data sourcing was *not* the blocker — I sourced clean, sane, canary-clean free signals (SPY trailing div-yield, DFII10 real 10y, DBC/GLD price-vs-5yr). The premise is dead at the probe. **Did NOT build the 2-sleeve blend** (task gates that on the probe passing).

**Why this is a useful result, not a failure:** it cleanly forecloses the last AQR lane with a *specific* reason (no free standalone-positive index-TS-value signal exists on our tradeable universe), consistent with the broader finding that genuine value exposure on our universe is gate-dead — here at the asset-class/index level for an economic reason (no expectancy) rather than the survivorship-beta reason that killed constituent-level value.

---

## The gating question (restated)

Is an index-level TS-value signal reliably **negatively** correlated to our momentum book — or is it just inverse-momentum noise / a relabeled short-momentum bet? The discriminating bar: a genuine value premium is **imperfectly** negative to momentum (≈ −0.2 to −0.5) **and** has its **own** non-negative standalone return. A −1×momentum book has corr-to-mom = **−1.0 by construction** — any "value" leg approaching that is just short-momentum.

## Harness discipline (all enforced)

- **Lookahead-safe:** all z-scores / trailing means use only data ≤ D (5yr trailing windows, inclusive of D).
- **+1-day signal lag:** signal computed from prices/levels through index `i−1`, position applied from the next day.
- **2 bps/side** turnover cost on every weight×scale change.
- **FP-continuous Sharpe** √252 (`runner.fp_sharpe.sharpe_from_returns`, `bars_per_year`).
- **OOS split 2018-01-01** reported separately.
- **1-day-lag canary** run on the candidate legs (lag1 vs lag2) — stable, no collapse → lookahead-clean.
- **Read-only** on all caches; **no** modifications to `strategies/`, `runner/`, crontab, or any `*.db`. Integrity verified (md5sums unchanged, below).

## The momentum book proxy (what we correlate against)

12-1 TSMOM on (QQQ, SPY), long/flat, equal-weight in-trend, vol-targeted 15% ann (cap 1.5×), monthly rebalance, +1d lag, 2 bps/side. Reconstructs the live momentum sleeves' core risk-asset trend exposure (`xa_tsmom_12_1`, `momentum_arkk`, `macd_momentum_iwm`, TQQQ vol-target trend).

| metric | full | IS (<2018) | OOS (≥2018) |
|---|---|---|---|
| FP Sharpe | **0.793** | 0.950 | **0.649** |
| CAGR | 12.35% | — | 10.63% |
| maxDD | −33.2% | — | — |
| span | 2008-02-01 → 2026-06-26 (n=4629) | | |

Sane and healthy — a legitimate momentum-book stand-in.

## Index-level TS-value legs built (all FREE, lookahead-safe, cheap→long)

| leg | traded asset | value level (source) | "cheap" rule |
|---|---|---|---|
| equity_divyield_SPY | SPY | SPY trailing-12m dividend yield, derived from Yahoo adjclose÷close (total-return vs price-return), z-scored vs own 5yr | high div-yield = cheap |
| equity_ERPproxy_SPY | SPY | (SPY div-yield) − DFII10 real-10y, z-scored — **labeled proxy** (no free CAPE/EP series exists) | high ERP = equities cheap vs bonds |
| bond_realyield_IEF | IEF (7-10y Tsy) | DFII10 real 10y yield (FRED), z-scored vs own 5yr | high real yield = bonds cheap |
| commodity_DBC_5yr | DBC | DBC adjclose ÷ own trailing 5yr avg, z-scored | below trailing avg = cheap |
| commodity_GLD_5yr | GLD | GLD adjclose ÷ own trailing 5yr avg, z-scored | below trailing avg = cheap |

**Signal-level sanity (verified):** SPY trailing div-yield prints 1.40%–2.24% across 2010-2024 (correct historical range); DFII10 real-10y prints −0.17% (2020) to +2.08% (2024) (correct). The value levels are economically real, not artifacts.

> **On the equity-value proxy honesty:** there is **no free point-in-time CAPE / forward-E/P series** (FRED has none; forward-PE is paid). So the cleanest *price-based* free equity-value signal is the **trailing realized dividend yield** (genuine, derivable from Yahoo) — that's the primary equity-value leg. The ERP leg is explicitly a **real-yield-anchored proxy** and labeled as such. This is the honest free frontier for index equity value.

---

## THE PROBE — full-sample correlations, rolling range, and the discrimination test

`margin vs short-mom` = corr_to_mom − (−1) = corr_to_mom + 1. **Larger margin ⇒ more distinct from a pure −1×momentum bet.** A leg with margin ≈ 0 (corr ≈ −1) IS short-momentum.

| leg | corr→mom | margin vs short-mom | rolling-2y corr [min, max] | standalone fpSharpe | standalone OOS Sharpe | (A) neg-imperfect? | (B) own non-neg ret? | **GATE** |
|---|---|---|---|---|---|---|---|---|
| equity_divyield_SPY | **−0.581** | 0.419 | [−0.978, +0.516] | −0.208 | −0.421 | ✅ | ❌ | **FAIL** |
| equity_ERPproxy_SPY | +0.156 | 1.156 | [−0.970, +0.972] | +0.023 | −0.347 | ❌ | ❌ | **FAIL** |
| bond_realyield_IEF | +0.212 | 1.212 | [−0.362, +0.574] | +0.183 | **+0.352** | ❌ | ✅ | **FAIL** |
| commodity_DBC_5yr | −0.096 | 0.904 | [−0.505, +0.331] | −0.195 | +0.049 | ✅ (weak) | ❌ | **FAIL** |
| commodity_GLD_5yr | −0.054 | 0.946 | [−0.281, +0.216] | −0.422 | −0.599 | ✅ (weak) | ❌ | **FAIL** |
| **REFERENCE: −1×mom** | **−1.000** | 0.000 | — | — | — | (is short-mom) | — | — |

**Gate condition (joint, ALL required):** (A) corr→mom ∈ (−0.7, −0.05) — negative enough to diversify but not short-mom; (B) fpSharpe ≥ 0 **and** OOS Sharpe ≥ 0 — own non-negative expectancy; (C) survives 1-day-lag canary.

**Legs passing the joint gate: `[]` (none).**

### What the discrimination test reveals (the crux)

1. **The −1×momentum reference correctly pins at corr = −1.000, margin 0.000** — the discriminator works.
2. **equity_divyield_SPY** is the most AQR-faithful leg and IS imperfectly-negative at the full-sample level (−0.58, margin 0.42 → distinguishable from short-mom *on average*). **But** (i) it **loses money standalone** (fpSharpe −0.21, OOS −0.42) — it's a *drag*, not a premium; and (ii) its **rolling-2y corr swings to −0.978**, i.e. in some regimes it collapses into being essentially short-momentum. So it fails (B) outright and only partially clears (A).
3. **bond_realyield_IEF** is the *only* leg with positive standalone OOS (+0.35) — but it's **positively** correlated to momentum (+0.21), so it isn't a diversifier (fails A). (Mechanically: when real yields are high/cheap it goes long bonds, and over 2008-2026 bonds and the equity-trend book co-moved enough — flight-to-quality + the post-2020 rate regime — to keep correlation positive.)
4. **Commodity legs** (DBC/GLD) are near-zero-correlated (nice diversification) but have **no standalone expectancy** (both negative). Buying "cheap" commodities vs a 5yr average is a money-loser net of cost over this sample.

**The fatal pattern:** the negative correlation and the standalone expectancy **never co-occur**. The AQR mechanism requires a value sleeve that *makes money on its own* AND is negatively correlated to momentum; combining two positive-Sharpe negatively-correlated books lifts the frontier. Here the only negatively-correlated legs are money-losers, so blending them in would just bleed the book (you'd be paying a negative-carry hedge), and the only positive-expectancy leg adds no diversification. The frontier cannot lift.

### 1-day-lag canary (lookahead integrity) — PASS

| leg | lag1 fpSharpe / OOS / corr→mom | lag2 fpSharpe / OOS / corr→mom |
|---|---|---|
| equity_divyield_SPY | −0.208 / −0.421 / −0.581 | −0.203 / −0.403 / −0.598 |
| bond_realyield_IEF | +0.183 / +0.352 / +0.212 | +0.200 / +0.350 / +0.209 |

Both legs are **stable** under an extra day of lag — no collapse, no sign-flip. The signals are lookahead-clean; the negative verdict is **not** a leakage artifact, it's real economics.

---

## Why the lane died (data-sourcing vs being-short-momentum)

**Neither, exactly — it died on a third thing: no standalone expectancy.** To be precise about the two failure modes the task asked me to distinguish:

- **It did NOT die on data-sourcing.** I sourced clean, free, deep, sane, canary-clean index-level TS-value signals (SPY div-yield 1993→, DFII10 real-yield 2003→, DBC/GLD 5yr ratios). Sourcing worked.
- **It did NOT die purely on being-short-momentum.** The most value-like leg (equity div-yield) is *distinguishable* from short-momentum on the full sample (margin 0.42, not ≈0). It's not a pure relabel.
- **It died because no free index-level TS-value signal has its own positive expectancy on our universe** — and the one negatively-correlated value-like leg additionally degenerates into short-momentum in some regimes (rolling corr → −0.98). With no standalone edge, the negative correlation is worthless (you can't diversify a momentum book with a money-loser and come out ahead).

This is consistent with — and extends — the existing gate finding that value is dead on our universe: constituent-level value is a survivorship-beta mirage (CLOSED 2026-06-23), and now **index/asset-class-level TS-value is dead too, for the distinct reason of zero free standalone expectancy.** Both roads to AQR-style value are closed.

## Disposition

- **CLOSE** the "Index-level Value+Momentum sleeve" lane (the last untouched AQR Reading Sprint #2/#3 lane).
- **Did NOT** sketch/wire the 2-sleeve V+M inv-vol blend — correctly gated off, since the probe failed (a blend of momentum + a negatively-correlated money-loser cannot lift the frontier; it would lower it).
- **Revisit only if** a *free, standalone-positive, point-in-time* index-level value series becomes available — realistically that means a free PIT CAPE / forward-earnings-yield feed (none exists today). Absent that, this lane stays closed.

## Reusable machinery (left in `reports/`, nothing wired)

- `reports/_index_value_mom_probe.py` — engine: momentum-book reconstructor, generic index-level TS-value return builder (lookahead-safe z-score → vol-targeted position), alignment + rolling-corr + discrimination helpers, FP/OOS stats. Reusable for any future "is X a distinct diversifier to our book?" probe.
- `reports/_index_value_mom_driver.py` — builds the 5 value legs + momentum book, runs the discrimination test, writes the JSON.
- `reports/_index_value_mom_canary.py` — 1-day-lag canary + signal-level sanity prints.
- `reports/_index_value_mom_verdict.py` — joint-gate verdict table.
- `reports/_index_value_mom_probe_result.json` — full numeric results.

## Integrity (read-only proof)

| file | md5 BEFORE | md5 AFTER | status |
|---|---|---|---|
| runner/backtest.py | 717c36e68941b9258f86bc99950de788 | 717c36e68941b9258f86bc99950de788 | ✅ unchanged |
| runner/risk.py | e303317e0d2ac796a1fa43e372f0a113 | e303317e0d2ac796a1fa43e372f0a113 | ✅ unchanged |
| runner/runner.py | 0f763975f2d8ba535352f6a8306afb8b | 0f763975f2d8ba535352f6a8306afb8b | ✅ unchanged |

No writes outside `reports/`. No `STOP_TRADING` change (file does not exist; not created). No orders, no spend, no strategy/cron/db modification.
