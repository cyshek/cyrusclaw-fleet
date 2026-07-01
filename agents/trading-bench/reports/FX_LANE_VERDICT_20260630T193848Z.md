# FX TREND + CARRY LANE — Confirm-or-Kill Verdict

**Stamp:** 20260630T193848Z (UTC) · **Lane:** FX_LANE (FOREX trend-persistence + carry)
**Mandate:** Does FX have a tradeable edge that survives realistic cost + no-leverage + walk-forward? Negative result acceptable and logged honestly.
**Status:** Research/paper only. No live capital, no live orders, no tracker, no cron. Promotion (if any) is a separate parent decision.

---

## VERDICT: **KILL**

> **One-line reasoning:** FX time-series momentum on the 7 majors has **no gross edge** — the single mildly-positive config (12-mo long/short basket) earns a gross Sharpe of **+0.049** with a **breakeven one-way spread of 0.65 bp**, i.e. its entire "edge" is *smaller than the bid-ask spread*. At a realistic ~1 bp FX cost it is net-negative (−1.4% total over 30 yrs), the +1-bar canary collapses it to noise (+0.032 → +0.005), and it can't even beat buy-and-holding the basket (+0.034). This is a textbook **efficient-market / cost-kill**. Carry was **SKIPPED honestly** (no clean free short-rate feed wired — see below), so it does not rescue the lane.

**Sub-verdict (diversifier angle):** Even as a risk-orthogonal diversifier it fails. SPY correlation is ≈ −0.07 (genuinely uncorrelated — the one real property), **but** a diversifier with ~0% raw return and a *negative* OOS Sharpe adds no value; you would pay spread to hold noise. **Not GO-AS-DIVERSIFIER.**

---

## Hypothesis

1. **FX trend / TSMOM** (core): absolute time-series momentum persists in spot FX — long if trailing return > 0, short/flat otherwise — tradeable per-major and as an equal-weight basket, unlevered, after realistic cost.
2. **FX carry** (secondary): rate-differential carry earns a premium.
3. **FX mean-reversion** (optional tiebreaker): short-horizon contrarian, tested because trend was inconclusive/dead.

## Data + Window

- **Source:** Yahoo v8 daily FX (`runner/fx_bars_cache.py`), free, deep, IP-unwalled from this VM. Spot close; FX has no splits/divs so `adjclose == close`.
- **Universe:** 6 majors + NZD — `EURUSD, GBPUSD, USDJPY, AUDUSD, USDCHF, USDCAD, NZDUSD` (all `=X`).
- **Spans (daily):** USDJPY 1996-11 → 2026-06 (7,685 bars); the rest 2003–2006 inception → 2026-06 (~5,200–5,930 bars each). Basket axis 1996-11 → 2026-06 (7,703 bars; covers GFC 2008, EUR crisis, 2014-15 USD surge, 2022 hiking cycle, 2020 COVID).
- **IS/OOS split:** IS < 2018-01-01, OOS ≥ 2018-01-01 (n_OOS = 2,205 bars ≈ 8.5 yrs per name).
- **Survivorship:** **non-issue** — FX majors do not delist. This is a genuine structural advantage of FX over the single-stock class (which is blocked on paid PIT fundamentals). It does not, however, manufacture an edge here.

## Cost / Breakeven

- **Model:** `runner.backtest.CostModel` with **1.0 bp one-way spread** (`fee_bps=0`), round-trip ≈ 2 bp. FX-appropriate — ~200× cheaper than the crypto 200 bp model and cheaper than the 2 bp equity convention. Cost is charged on per-bar **turnover** (`Σ|wᵢ,t − wᵢ,t−1| × spread`). Cost path is asserted active (zero-cost runs are explicit comparators only).
- **Breakeven one-way spread (total-return crosses zero):**

  | Config | Gross Sharpe (0 bp) | Gross total ret | **Breakeven one-way** | Net @1 bp ret |
  |---|---|---|---|---|
  | TSMOM 12mo **LS** | +0.049 | +2.6% | **0.65 bp** | **−1.4%** |
  | TSMOM 12mo **LF** | +0.029 | +0.8% | **0.39 bp** | −1.2% |
  | TSMOM 3mo LS | −0.053 | −20.3% | *no gross edge* | −27.4% |
  | TSMOM 6mo LS | −0.093 | −27.2% | *no gross edge* | −31.8% |
  | TSMOM 12-1 LS | −0.004 | −9.2% | *no gross edge* | −12.7% |

  Only two configs have *any* positive gross return, and both break even **below 1 bp** — i.e. they lose to the spread itself. Every other config is negative even at **zero cost**, so cost is not the culprit there; there is simply no signal.

## Strategies Tested — Full-period + IS/OOS Sharpe, Raw Return, MaxDD (net @1 bp)

**Basket (equal-weight, unlevered, gross exposure ≤ 1.0 enforced):**

| Strategy | Sharpe full | Sharpe IS | Sharpe OOS | Total ret | CAGR | MaxDD | Turnover |
|---|---|---|---|---|---|---|---|
| TSMOM 12mo **LS** *(best)* | **+0.032** | +0.049 | **−0.029** | −1.4% | −0.05% | −29.7% | 0.052 |
| TSMOM 12mo LF | +0.015 | +0.017 | +0.011 | −1.2% | −0.04% | −23.0% | 0.026 |
| TSMOM 3mo LS | −0.091 | −0.066 | −0.206 | −27.4% | −1.04% | −43.7% | 0.121 |
| TSMOM 3mo LF | −0.070 | −0.055 | −0.154 | −13.2% | −0.46% | −27.0% | 0.060 |
| TSMOM 6mo LS | −0.120 | −0.049 | −0.423 | −31.8% | −1.24% | −35.4% | 0.084 |
| TSMOM 6mo LF | −0.075 | −0.022 | −0.371 | −14.3% | −0.50% | −29.6% | 0.042 |
| TSMOM 12-1 LS | −0.021 | −0.007 | −0.073 | −12.7% | −0.44% | −34.9% | 0.052 |
| **BASKET buy&hold** (long-only EW) | +0.034 | +0.030 | +0.068 | −0.1% | ~0.00% | −32.1% | 0.001 |
| MR 5d contrarian | −0.084 | −0.142 | +0.146 | −25.5% | −0.96% | −44.1% | 0.398 |

**Per-symbol TSMOM 12mo LS:**

| Symbol | Sharpe full | Sharpe IS | Sharpe OOS | Total ret | CAGR | MaxDD |
|---|---|---|---|---|---|---|
| USDJPY=X | +0.148 | +0.151 | +0.145 | +36.7% | +1.03% | −38.2% |
| AUDUSD=X | +0.103 | +0.147 | +0.026 | +11.3% | +0.52% | −37.8% |
| GBPUSD=X | −0.073 | −0.133 | +0.034 | −21.9% | −1.06% | −47.0% |
| NZDUSD=X | −0.089 | −0.132 | −0.001 | −33.6% | −1.75% | −53.8% |
| USDCAD=X | −0.134 | −0.026 | −0.392 | −29.0% | −1.45% | −43.1% |
| EURUSD=X | −0.331 | −0.525 | +0.190 | −62.0% | −4.08% | −69.6% |
| USDCHF=X | −0.352 | −0.409 | −0.228 | −61.4% | −3.97% | −68.6% |

**Read:** Only **2 of 7** names are even mildly positive (USDJPY +0.148, AUDUSD +0.103); 5 lose money. No config clears a Sharpe worth deploying (all |Sharpe| < 0.16, basket ≈ 0). The "best" basket's OOS Sharpe is **negative**. The best raw return belongs to **buy-and-hold (−0.1%)**, which the trend overlay fails to beat — i.e. the signal destroys value relative to doing nothing.

## +1-Bar Canary (lag the signal one extra day)

| Config | Base Sharpe | +1-bar lag | Read |
|---|---|---|---|
| basket 12mo LS | +0.032 | **+0.005** | edge evaporates → timing noise |
| basket 3mo LS | −0.091 | +0.001 | *improves* under lag → pure noise |
| basket 12-1 LS | −0.021 | −0.000 | *improves* under lag → pure noise |
| MR 5d | −0.084 | −0.144 | degrades under lag (signal is real but **losing**) — and 0.398 turnover would be obliterated by cost |

The only positive config barely survives a 1-day lag (+0.032 → +0.005), and the losing configs get *better* when delayed — both are signatures of timing noise, not a real edge. **KILL confirmed by the canary.**

## SPY Correlation (same path, daily returns)

| Strategy | Corr to SPY | n overlap |
|---|---|---|
| TSMOM 12mo LS | **−0.073** | 6,567 |
| BASKET buy&hold | +0.144 | 6,567 |

Genuinely uncorrelated (the one real property of the trend basket) — but uselessly so, because the return it diversifies *with* is ≈ 0 and its OOS Sharpe is negative.

## Carry — Honest SKIP (no fabricated rate data)

**Decision: SKIPPED, documented.** Carry was **not** tested. Justification:
- The free Yahoo `=X` spot feed carries **only OHLC + adjclose** (verified: `indicators = {quote, adjclose}` — no forward points, no swap/deposit rates). There is no cheap forward/spot basis to proxy carry from.
- No clean per-currency short-rate feed is wired in this repo. `runner/fred_cache.py` exists and *could* in principle source policy-rate differentials (Fed funds, ECB MRO, BoJ, BoE, RBA, SNB, BoC) for a proper PIT carry build — **but** standing that up correctly (7-currency rate alignment, PIT lag, rolling differentials) is a substantial separate build.
- Per the mandate's explicit instruction ("do NOT invent rate data … SKIP carry and say so honestly rather than fabricate a rate feed"), and because the **trend hypothesis is decisively dead**, bolting a half-built carry proxy onto a failed lane would be exactly the manufacture-a-winner anti-pattern. **Out of scope for this confirm-or-kill.**
- **Assumption that would flip this:** if a future dedicated lane wires FRED policy-rate differentials with proper PIT alignment, FX carry is worth a clean standalone test (carry is the *other* canonical FX premium and is mechanically distinct from trend). That is a separate task, not this one.

## Lookahead / Leakage Audit

- **Signal lag (proven by test):** `tsmom_signal` computes `positions[t]` from `closes[:t]` **only** (most-recent close used is index `t−1−skip`); the position is applied to the `t−1 → t` forward return. `tests/test_fx_strategies.py::test_tsmom_signal_is_lookahead_safe` mutates a *future* close and asserts every prior position is unchanged. `::test_tsmom_signal_position_into_t_uses_prior_close_only` checks the exact indices. **No future bar is ever read.**
- **PIT accessors:** basket alignment uses `close_series` (forward-fill ≤ D, never ahead); the cache's `asof`/`asof_strict` raise on any bound violation.
- **No leverage (proven by test):** per-leg weight = `±1/N_active`; `::test_basket_gross_exposure_never_exceeds_one` asserts gross Σ|wᵢ| ≤ 1.0 every bar. No config relies on leverage — and none "works" anyway, so the leverage-kill rule never even triggers.
- **Cost always active:** `::test_fx_cost_default_is_one_bp` pins the 1 bp default; zero-cost runs are explicit comparators only.

## Why KILL (the blunt version)

**Efficient market + cost.** Spot FX major trend-persistence, at daily frequency on the liquid majors, is arbitraged to ~zero gross edge over 30 years. The one config with positive gross return (12mo LS, Sharpe +0.049) has a breakeven spread of **0.65 bp** — its signal is worth less than the cost to trade it — and it dies under a 1-day lag. It cannot beat buy-and-hold, it cannot beat zero, and its OOS Sharpe is negative. There is no leverage-free, cost-surviving, walk-forward-robust trend edge here. **Not GO. Not GO-AS-DIVERSIFIER. KILL.**

---

## Reproduce

```bash
python3 _fx_verdict.py        # full strategy table, per-symbol, canary, SPY-corr
python3 _fx_breakeven.py      # gross vs net + breakeven one-way spread
python3 -m pytest -q tests/test_fx_strategies.py   # 18 harness/lookahead tests
```

**Reusable harness:** `runner/fx_strategies.py` (lookahead-safe TSMOM/MR signals, unlevered basket accounting, FX cost model, metrics). **Tests:** `tests/test_fx_strategies.py`.
**Protected files:** none modified (imported `CostModel`, `bars_per_year` from `runner/backtest.py` only).
