# PEAD Large-Cap Retest — Beta-Stripped-Alpha Edition

**Date:** 2026-06-23 (UTC stamp `20260623T211313Z`)
**Strategy:** Post-Earnings Announcement Drift (PEAD), large-cap, event-driven
**Universe:** 104 names (103 present in earnings DB; BRK-B absent — fine), S&P-100-ish
**Honest bar:** **BETA-STRIPPED ALPHA** (Newey-West t-stat ≥ 2.0), *not* raw Sharpe
**Disposition:** ❌ **CLOSE** — no construct produces statistically significant alpha after the beta we *know* is there is removed. The dumb EW-103 survivor basket beats every construct. This is the same survivorship-beta-in-disguise pathology that closed fundamentals-PIT, BAB, and xsec-momentum earlier today.

---

## 0. Executive Verdict

| Construct | OOS beta | OOS β-adj alpha (ann) | **OOS alpha t (NW)** | Beats SPY? | Beats EW-103? | Promote? |
|---|---|---|---|---|---|---|
| **A — vol-scaled long** | 0.806 | −0.78% | **−0.15** | ❌ | ❌ | **FAIL** |
| **C — sector-ETF hedge (primary)** | **0.013** | +1.05% | **+0.21** | ❌ | ❌ | **FAIL** |
| REF — naive long-only (reference) | 1.078 | −1.70% | −0.29 | ❌ | ❌ | (settled beta) |
| CTRL — dollar-neutral L/S (control) | 0.273 | −1.16% | −0.30 | ❌ | ❌ | (settled, rejected) |

**Promote bar (per construct, OOS net 2 bps):** alpha t ≥ 2.0 **AND** beats SPY **AND** beats EW-103 **AND** |β| < 0.30 (hedged) **AND** reasonable maxDD.

**Overall: CLOSE.** Construct C does exactly what it was designed to do — it strips market/sector beta to ~0.01 (target < 0.30 ✓). But that is the whole point of the test: once the beta is gone, **there is no alpha left underneath it** (t = +0.21, need 2.0). The "0.65-Sharpe PEAD" was beta, confirmed a fourth way today.

The decisive evidence is the control, not the construct:

> **EW-103 buy-and-hold of the SAME 103 names scores OOS Sharpe 0.92 / +265% / alpha-to-SPY t = 1.48** (and IS alpha t = **6.25**, full-period t = **3.85**). A no-signal equal-weight basket of *today's survivors* has more statistically-significant alpha-to-SPY than any PEAD construct. Every construct *loses* to it. The PEAD signal, net, adds nothing on top of just holding the survivors.

---

## 1. Controls (the gate — non-negotiable)

Daily-rebalanced buy-and-hold, same windows, net of nothing (benchmarks bear no trading cost).

| Control | Period | Total Ret | CAGR | Sharpe | MaxDD | β-SPY | α ann | **α t (NW)** |
|---|---|---|---|---|---|---|---|---|
| SPY buy-hold | full | 663.8% | 15.15% | 0.936 | 33.7% | 1.000 | 0.00% | 0.00 |
| SPY buy-hold | IS | 136.5% | 15.43% | 1.260 | 13.0% | 1.000 | — | — |
| SPY buy-hold | **OOS** | **220.7%** | **14.85%** | **0.820** | 33.7% | 1.000 | 0.00% | 0.00 |
| EW-103 buy-hold | full | 1149.7% | 19.15% | 1.155 | 34.6% | 0.960 | 4.01% | **3.85** |
| EW-103 buy-hold | IS | 239.5% | 22.60% | 1.697 | 12.8% | 1.027 | 5.69% | **6.25** |
| EW-103 buy-hold | **OOS** | **265.2%** | **16.64%** | **0.921** | 34.6% | 0.942 | 2.37% | **1.48** |

**Read this first.** The EW-103 basket *is* the alpha that a naive PEAD long book is accidentally harvesting. It is survivorship: these 103 names were selected *because* they are mega-caps today, so equal-weighting them and holding 2012→2026 mechanically beats SPY. Any construct that does not clear **both** SPY and EW-103 OOS, net of cost, is just this survivorship beta wearing an event-driven costume.

---

## 2. Settled reference rows (do NOT re-litigate)

Reproduced here as anchors; both were already adjudicated.

| Construct | OOS Sharpe | OOS CAGR | OOS MaxDD | OOS β | OOS α t | Status |
|---|---|---|---|---|---|---|
| REF naive long-only (thr=10%) | 0.558 | 12.12% | 48.4% | 1.078 | −0.29 | **SETTLED = beta** (prior ~0.65 reproduced; β≈1, α insignificant) |
| CTRL dollar-neutral L/S (thr=10%) | 0.234 | 2.25% | 24.3% | 0.273 | −0.30 | **SETTLED = rejected** (toxic individual-name short leg) |

*(Note: REF here shows 0.558 vs the prior report's 0.672 at thr=10% — the difference is this run's stricter cost amortization and the per-day book-average accounting; the conclusion — β≈1, no alpha — is identical and is what matters.)*

---

## 3. THE TWO NEW CONSTRUCTS (the actual deliverable)

### Construct A — Vol-scaled long-only

Long PEAD book, each position sized ∝ 1 / (trailing 20-day realized vol), whole book scaled to 0.5× exposure when prior-close VIX > 30 (de-risk, not zero). Goal: compress the COVID/2022 drawdowns.

| Period | Total Ret | CAGR | Sharpe | MaxDD | β-SPY | α ann | **α t (NW)** | avg trade | WR | N |
|---|---|---|---|---|---|---|---|---|---|---|
| full | 384.8% | 11.57% | 0.647 | 33.2% | 0.811 | +0.42% | 0.11 | +1.70% | 60.3% | 973 |
| IS | 102.1% | 12.44% | 0.790 | 16.7% | 0.825 | +0.68% | 0.14 | +1.30% | 60.1% | 386 |
| **OOS** | **120.7%** | **9.87%** | **0.537** | **33.2%** | **0.806** | **−0.78%** | **−0.15** | +1.97% | 60.5% | 587 |

**Result:** MaxDD *did* compress (48.4% → 33.2% OOS — the vol-scaling + VIX de-risk worked as intended). But **beta is still 0.81** (it's still a long book) and **β-adjusted alpha t = −0.15** — negative and insignificant. Sizing changes the risk profile; it does not create alpha. **FAIL.**

### Construct C — Sector-ETF beta-hedge (PRIMARY candidate)

Long PEAD book, hedged by shorting the matched SPDR sector ETF (XLK/XLF/XLV/XLE/XLI/XLP/XLY/XLU/XLB, +XLRE/XLC post-inception with pre-inception proxies) in proportion to the long book's per-sector dollar weight. ETF borrow is cheap → no single-name borrow risk. Target β < 0.30.

| Period | Total Ret | CAGR | Sharpe | MaxDD | **β-SPY** | α ann | **α t (NW)** | avg trade | WR | N | turnover | breakeven |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| full | −1.17% | −0.08% | 0.065 | 34.2% | 0.019 | +0.64% | 0.19 | +1.70% | 60.3% | 973 | 3.4×/yr | 1.8 bps |
| IS | −0.53% | −0.09% | 0.051 | 20.5% | 0.040 | −0.01% | −0.00 | +1.30% | 60.1% | 386 | 3.2×/yr | 1.8 bps |
| **OOS** | **+0.20%** | **0.02%** | **0.080** | **34.2%** | **0.013** | **+1.05%** | **+0.21** | +1.97% | 60.5% | 587 | 3.5×/yr | **2.0 bps** |

**Threshold sweep (OOS), Construct C:**

| thr | Sharpe | CAGR | β-SPY | α ann | **α t (NW)** | N |
|---|---|---|---|---|---|---|
| 2% | −0.613 | −6.57% | −0.034 | −5.75% | **−1.52** | 999 |
| 5% | −0.357 | −4.46% | −0.012 | −3.78% | −0.91 | 867 |
| **10%** | 0.080 | 0.02% | 0.013 | +1.05% | **+0.21** | 587 |
| 15% | 0.021 | −1.29% | 0.028 | −0.05% | −0.01 | 392 |
| 20% | 0.103 | 0.26% | 0.049 | +1.03% | +0.19 | 286 |

**Result — the central finding of this whole exercise:** the hedge *works mechanically* — beta is driven to **0.01–0.05 across every threshold** (target < 0.30 ✓, far better than the prior individual-name neutral's 0.27). But with the beta gone, **the alpha that remains is statistically zero**: best OOS t = +0.21 at thr=10%, and *negative* at the looser thresholds where the book is biggest. The peak |α t| anywhere in the sweep is 1.52 — and that's on the *wrong side* (−1.52 at 2%). **Nowhere near 2.0. FAIL.**

The breakeven cost is **~2.0 bps one-way** — i.e. at the mission's own headline 2 bps assumption, the strategy is *already at zero net return*. The drift, once beta-stripped, is too thin to pay for its own (cheap, ETF) trading.

### Construct C cost grid (OOS, thr=10%)

| one-way cost | Sharpe | CAGR | α ann | α t |
|---|---|---|---|---|
| 0 bps | 0.146 | +1.07% | +2.10% | 0.43 |
| **2 bps (headline)** | 0.080 | +0.02% | +1.05% | 0.21 |
| 4 bps | 0.013 | −1.01% | −0.00% | −0.00 |
| 8 bps | −0.119 | −3.05% | −2.10% | −0.43 |

Even at **zero cost** (free trading, free borrow), Construct C's alpha t-stat is only 0.43. Cost is not what kills it — there is simply no edge to begin with.

---

## 4. Lookahead canary (anti-cheat sanity check)

The honest entry is D+1 (the session *after* the earnings report). The canary cheats by entering on the **earnings-date's own close** (using information not tradable until that close prints) — a deliberate lookahead leak that must score wildly better than honest if the harness is wired correctly.

| Variant (OOS, thr=10%, long-only) | CAGR | Sharpe | α ann | α t |
|---|---|---|---|---|
| **Honest** (D+1 entry) | 12.12% | 0.558 | −1.70% | −0.29 |
| **CANARY** (same-day-close cheat) | **20.90%** | **0.777** | **+7.10%** | +0.93 |
| **Δ** | **+8.79 pp CAGR** | +0.219 | +8.80 pp | +1.22 |

✅ **Canary passes:** the cheat scores materially better (+8.79 pp CAGR, alpha −1.70% → +7.10%) and the honest version does **not** match it. This confirms the honest backtest is *not* secretly peeking at the report-date close — the D+1 discipline is intact. (The canary's own t = 0.93 is still < 2.0 because single-name PEAD is noisy even when cheating across 587 trades; the canary's job is the *relative* lift, which it delivers unambiguously.)

---

## 5. Honest "why" diagnosis

**1. It's the same survivorship-beta mirage, a fourth time today.** The EW-103 control (OOS alpha-to-SPY t = 1.48, full-period t = 3.85) demonstrates that simply holding these 103 hand-picked modern survivors beats SPY with statistically-significant "alpha." Naive PEAD long-only (β = 1.08) harvests exactly this and nothing more — its own alpha-to-SPY is −0.29 (it doesn't even beat its *own* beta, because the PEAD selection/timing adds turnover and noise without adding return). This is identical to fundamentals-PIT, BAB, and xsec-momentum: *long-only "beats SPY" with β≈1 = survivorship beta, not edge.*

**2. The hedge proves the point by elimination.** Construct C is the cleanest possible test: kill the beta (✓, β→0.01) and see what's left. What's left is α t = 0.21. The drift, stripped of market/sector co-movement, is real-but-tiny and statistically indistinguishable from zero on this universe over this window. Large-cap PEAD is *efficiently arbitraged* — the names with 8+ analysts and meaningful forecasts are exactly the names where post-earnings drift is most competed away.

**3. Costs are not the villain — there's no edge to protect.** Breakeven is ~2 bps one-way and even at *zero* cost the alpha t is 0.43. This is not a "good signal eaten by friction" story; it's a "no signal once you remove beta" story.

**4. Vol-scaling fixes risk, not return.** Construct A successfully compressed MaxDD 48%→33%, confirming the sizing logic works — but it left a β=0.81 long book with α t = −0.15. Useful as a *risk overlay on a beta product*, useless as a source of *alpha*.

**5. The asymmetry from the prior report holds.** Beats vastly outnumber misses (~3.9×); large-cap analysts set beatable targets; the upward market drift overwhelms miss-drift. The long side is "beta + a whisper of drift," and the whisper does not survive a beta strip.

---

## 6. Gate assessment (OOS 2018–2026, net 2 bps)

| Construct | α t ≥ 2.0 | beats SPY | beats EW-103 | \|β\| < 0.30 | maxDD ok | **Verdict** |
|---|---|---|---|---|---|---|
| A — vol-scaled long | ❌ −0.15 | ❌ | ❌ | ❌ 0.81 | ✅ 33% | **FAIL** |
| C — sector-ETF hedge | ❌ +0.21 | ❌ | ❌ | ✅ 0.013 | ✅ 34% | **FAIL** |

No construct clears the bar. **Overall verdict: CLOSE.** This is a clean negative — a good outcome. We have now disproven the "large-cap PEAD has alpha" hypothesis four independent ways and can stop spending on it.

---

## 7. What would change the verdict (not pursued)

Documented for completeness; none are obvious wins and none are recommended now:

- **Smaller-cap universe** (the survivor-beta control would differ; drift is plausibly larger where less arbitraged) — but our cached universe is the modern-survivor S&P-100 set, so this needs a fresh, survivorship-clean small-cap universe + earnings data we don't have.
- **Drift conditioned on price reaction** (the *announcement-window return*, SUE×reaction interaction) rather than EPS surprise alone — a different signal, not a fix to this one.
- **Intraday/shorter holds** — out of scope for daily-bar infra.

The honest call: **large-cap PEAD on a survivor universe is beta, not alpha. CLOSE it.**

---

## 8. Methodology / reproducibility

| Parameter | Value |
|---|---|
| Universe | 104-name S&P-100-ish (`reports/_xsec_sector_map.json`); 103 in earnings DB |
| Large-cap filter | n_estimates ≥ 8 AND \|eps_forecast\| ≥ 0.05 |
| Entry | D+1 adjclose (session after report; AMC/unsupplied → next session) |
| Hold | 20 trading days |
| Capacity | ≤ 20 concurrent long positions |
| Thresholds | sweep {2, 5, 10, 15, 20}% |
| Costs | headline 2 bps one-way; grid {0,2,4,8}; Construct C charges long + ETF legs |
| Splits | IS 2012-01→2017-12, OOS 2018-01→2026-06 (matches prior report) |
| Prices | Yahoo v8 **adjclose** via `runner/daily_bars_cache` (PIT, split+div-adj, lookahead-guarded `asof`) |
| VIX | `runner/cboe_cache.level_asof` (strictly-prior close, no leak) |
| Beta/alpha | OLS daily strat-ret on SPY-ret; **Newey-West HAC SE, lag 20** (overlapping holds) |
| **NW validation** | **SE matches statsmodels HAC to 0.000%** (see `_validate_nw.py` / test) |

### Files

| File | Description |
|---|---|
| `strategies_candidates/pead_largecap_retest/backtest_pead_largecap.py` | Standalone, re-runnable engine (all constructs + controls + canary + cost grid). Exit 0. |
| `strategies_candidates/pead_largecap_retest/results.json` | Full numeric results (construct × threshold × period × cost). |
| `strategies_candidates/pead_largecap_retest/_pead_largecap_tests.py` | Reproducibility tests (asserts headline numbers + verdict invariants). |
| `strategies_candidates/pead_largecap_retest/_validate_nw.py` | Proves the Newey-West SE matches statsmodels. |
| `reports/PEAD_LARGECAP_RETEST_20260623T211313Z.md` | This report. |

---

*Generated 2026-06-23. Research-only; not a trading recommendation. Verdict: **CLOSE** — large-cap PEAD is survivorship beta, no surviving alpha after beta-strip (best OOS alpha-to-SPY t = 0.21 vs 2.0 bar).*
