# Credit-Stress Lane — Walk-Forward vs SPX (2026-06-09)

**PAPER / RESEARCH-ONLY. No leverage, long-only. Candidate, not promoted, not a tournament parent.**

## Verdict (honest, up front)

**No credit/macro regime gate out-RETURNS a dividend-paying S&P 500 over the full cycle. But the credit signal carries real, decoupled crisis-defense value** — directly parallel to the FX lane outcome.

- The "beats SPX raw = True" flags in the JSON are a **benchmark artifact**: they compare against `^GSPC` *price-only* (no dividends). Against the honest yardstick — **buy-and-hold SPY (total return)** — every strategy in every config **loses** over the full period, and beats SPY-BH in only **8–25% of the 12 walk-forward windows**.
- The apparent headline winner (`nfci_conditions_gate`, +2747% cash-config) is **90%+ time-in-market at 0.76–0.85 correlation to SPX** — i.e. closet-long equity. It "wins" by being in the market during the up-years, not by a distinct edge; it beats SPY-BH in **1 of 12 windows**.
- **Where the signal is real:** in stress/crisis windows the gates genuinely decouple and protect. `combined_credit_macro` (IEF risk-off): **+8.1% in the 2008 GFC while SPX fell −39.5%** (corr 0.05 that window), +5.0% in the 2011 EZ/US-downgrade vs +0.1% SPX, and cut full-period maxDD to −29% vs the market's deeper crisis drawdowns. The crisis-composite: **strat +7.4% vs SPX −12.1%**.
- **The trade-off that sinks the full-cycle beat:** de-risking on credit stress costs upside in every bull/recovery window (lagged 2003–07, 2009–11, 2017–19, 2023–24). Crisis-alpha, full-cycle drag.

**Bottom line:** the beat-SPX-raw bar is **NOT cleared.** The lane's value, if any, is as a **crisis-hedge / drawdown-control sleeve** inside a future multi-strategy allocator — not as a standalone return-generator. Keep-able as a diversifier candidate; do not promote as a return engine.

## What was built

Lookahead-safe credit/macro regime-gating lane, self-contained (protected `runner/` files untouched).

- `strategies_candidates/credit_stress/credit_data.py` — data adapter. Aligns 3 FRED series + SPX/SPY/IEF onto a common daily calendar, strict no-lookahead. **NFCI release-lag handled correctly:** weekly NFCI (dated week-ending Friday, published the following Wednesday) is forward-filled from a **conservative fixed 7-calendar-day release lag** (≥ the empirical +5d Wednesday release), so no NFCI print is ever used before it was published. Daily series (BAA10Y, T10Y2Y) use the standard `≤ D` rule. A unit test cross-checks the fill against ALFRED point-in-time vintages (no-future-leak).
- `strategies_candidates/credit_stress/backtest_credit.py` — self-contained daily engine. No-leverage invariant hard-asserted (w_spy + w_off ≤ 1.0, no shorts); 1-day signal lag (weight decided on D applied to D+1 return); monotonic cost model (0.5 / 1 / 2 / 5 bp one-way grid, 1 bp baseline for SPY/IEF ETFs).
- `strategies_candidates/credit_stress/strategies_credit.py` — 3 strategies: `credit_spread_gate` (de-risk when BAA10Y spread elevated/widening), `nfci_conditions_gate` (de-risk when NFCI tight), `combined_credit_macro` (vote of spread + curve slope + NFCI).
- `strategies_candidates/credit_stress/walk_forward_credit.py` — 12 sequential OOS regime windows (incl. 2008 GFC + 2020 COVID); median-not-max, % positive, % beat SPX, worst/best.
- `strategies_candidates/credit_stress/run_eval.py` → `credit_stress_eval.json` (full results, both configs, cost grid, per-window table, correlation-to-SPX persisted).
- `tests/test_credit_data.py` — adapter alignment, NFCI no-future-leak (ALFRED cross-check), per-strategy no-lookahead locks, cost monotonicity, no-leverage invariant. **Suite: 446 passed (was 437; +9 new).**

## Data

| Series | What | Freq | Span | Role |
|---|---|---|---|---|
| BAA10Y | Moody's Baa − 10yr Treasury credit spread | daily | 1986→2026 | primary credit-stress signal |
| NFCI | Chicago Fed Financial Conditions Index | weekly (7d release lag) | 1980→2026 | financial-conditions gate |
| T10Y2Y | 10yr−2yr Treasury curve slope | daily | 1976→2026 | recession/inversion input |
| ^GSPC / SPY / IEF | benchmark / traded long leg / risk-off leg | daily | 1993/1993/2002→2026 | sleeve + benchmark |

All free, keyed FRED + keyless Yahoo v8. Spans both 2008 and 2020. (This is the ICE-OAS-truncation self-unblock: BAA10Y/NFCI/T10Y2Y replace the deep HY/IG-OAS history FRED no longer carries free.)

## Full-period results (net of 1 bp baseline cost)

**ief_riskoff config (2002→2026)** — benchmark: SPY-BH (total return) = **+1156%**, ^GSPC price-only = +720%:

| Strategy | Net ret | vs SPY-BH | Sharpe | maxDD | ann vol | TiM | corr→SPX | beats SPY-BH (windows) |
|---|---|---|---|---|---|---|---|---|
| credit_spread_gate | +807% | **loses** | 0.76 | −37% | 13% | 75% | 0.55 | 25% |
| nfci_conditions_gate | +1471% | **loses** | 0.81 | −34% | 16% | 0.76 | 90% | 8% |
| combined_credit_macro | +794% | **loses** | 0.86 | −29% | 11% | 0.65 | 89% | 17% |

**cash_riskoff config (1993→2026)** — benchmark: SPY-BH = **+2958%**, ^GSPC price-only = +1588%:

| Strategy | Net ret | vs SPY-BH | Sharpe | maxDD | corr→SPX | beats SPY-BH (windows) |
|---|---|---|---|---|---|---|
| credit_spread_gate | +893% | **loses** | 0.63 | −32% | 0.65 | 25% |
| nfci_conditions_gate | +2747% | **loses** | 0.70 | −50% | 0.85 | 8% |
| combined_credit_macro | +1106% | **loses** | 0.74 | −29% | 0.78 | 25% |

Cost is nearly irrelevant (these are low-turnover regime gates): nfci_gate moves +1472%→+1463% across the 0.5–5 bp grid.

## Walk-forward, window-by-window — `combined_credit_macro` (ief), the cleanest variant

| Window | Regime | Strat | SPX-px | SPY-BH | corr | note |
|---|---|---|---|---|---|---|
| 2003–2007 bull | calm | +48.1% | +68.0% | +82.2% | 0.89 | lags (de-risked too early) |
| **2008 GFC** | **crisis** | **+8.1%** | **−39.5%** | **−36.5%** | **0.05** | **decoupled, positive — the real win** |
| 2009–2011 recovery | recovery | +22.2% | +36.2% | +42.9% | 0.88 | lags |
| 2011 EZ/US-downgrade | stress | +5.0% | +0.1% | +2.5% | 0.98 | beats |
| 2013–2015 QE bull | trend | +46.0% | +41.1% | +48.0% | 0.92 | ~matches |
| 2015–2016 risk-off | stress | +3.1% | +1.0% | +3.1% | 1.00 | beats SPX-px |
| 2017–2019 expansion | calm | +27.1% | +31.8% | +38.8% | 0.91 | lags |
| 2020 COVID | crisis | +6.6% | +15.3% | +17.2% | 0.96 | lags (V-recovery punished cash) |
| 2021 reflation | trend | +30.5% | +28.8% | +30.5% | 1.00 | ~matches |
| 2022 bear/hikes | bear | −21.9% | −20.0% | −18.6% | 0.95 | **slightly worse** (bonds fell too) |
| 2023–2024 recovery | recovery | +34.5% | +53.8% | +58.2% | 0.75 | lags |
| 2025–2026 recent | recent | +25.9% | +26.2% | +28.3% | 0.99 | ~matches |

**Pattern:** strong, decoupled crisis-defense (2008 especially: +8% vs −40% at corr 0.05); systematic lag in bull/recovery; no edge in the 2022 rate-driven bear (the credit gate doesn't help when bonds sell off *with* stocks). Median WF return 24.1% vs SPX-px 27.5%; positive in 11/12 windows but beats SPY-BH in only 2/12.

## Caveats / honesty notes

- **The headline "beats SPX raw" is price-vs-total-return.** Always read against SPY-BH (total return), where it loses. Reporting both, flagged.
- **2008-only crisis-alpha is n=1 for the deepest decoupling.** 2020 did *not* repeat the trick (the V-shaped recovery punished any cash holding). So "credit gate = crisis hedge" rests heavily on one GFC-type slow-bleed event; it does NOT protect a fast-recover crash, and does NOT help a rates-led bear (2022).
- **Regime windows are hand-labelled** (same method as the FX lane) — informative, not a substitute for a continuous rolling walk-forward. A rolling-origin re-run is the natural follow-up if this sleeve is ever taken further.
- Lookahead discipline verified by test (NFCI release-lag vs ALFRED PIT; per-strategy future-mutation locks). Protected `runner/` md5s unchanged.

## Disposition

**Candidate only.** Does not clear beat-SPX-raw. Real but narrow crisis-hedge property (GFC-type events). Only becomes useful alongside a multi-strategy capital-allocator that can size a small de-risking sleeve — same conclusion as the FX trend/XSMom diversifier. No paper-clock without a gate pass + explicit discussion.
