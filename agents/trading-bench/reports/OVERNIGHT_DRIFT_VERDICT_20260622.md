# OVERNIGHT DRIFT — "Buy-the-Close, Sell-the-Open" Anomaly — VERDICT
**Trading-bench research sprint · 2026-06-22**
Lane: overnight return puzzle (Cooper/Cliff/Gulen; Lou/Polk/Skouras decomposition).
Author: trading-bench (subagent). Status: research only — never live.

---

## VERDICT: **NO** (real but untradeable — CLOSE)

The overnight-drift anomaly is **unambiguously REAL and large in gross terms** on every
US-equity index ETF tested (SPY/QQQ/IWM/TQQQ): nearly all the risk-adjusted return
lives **overnight** (prior-close → next-open), while the **intraday** session
(open → close) earns ~zero or negative — exactly as the literature claims, replicated
cleanly on our own data. **On a risk-adjusted basis, overnight-only beats buy-and-hold
GROSS on all four ETFs** (Sharpe ON ≈ 0.95–1.02 vs B&H ≈ 0.48–0.91).

**But it does not survive its own turnover.** Overnight-only trades a full round-trip
*every day* (~252/yr). The **breakeven cost is ~0.5–1.4 bps/side** — below even the most
optimistic 2 bps/side bench convention. At a *realistic* liquid-ETF auction cost of
**5 bps/side, overnight-only is wiped out** (CAGR −11% to −15%, total return ≈ −100%),
while buy-and-hold (which pays cost once) is untouched. **Net of realistic costs,
overnight-only loses to buy-and-hold on every ETF, on both raw return and Sharpe, in-
sample AND out-of-sample (post-2018).** The premium is real; it is also smaller than the
spread you must cross to harvest it, daily.

**Recommendation: CLOSE.** The decomposition is valuable *diagnostically* (it localizes
the entire equity risk premium to the overnight window and flags intraday as a
structural drag — useful for *execution timing* of positions we already intend to hold),
but **overnight-only is not a tradeable standalone strategy at any cost level we can
realistically achieve.**

---

## Hypothesis
Decades of literature find that for US equity indices the cumulative drift has historically
accrued **overnight** while the intraday session contributes ~zero/negative. If tradeable
net of costs, a book long the ETF overnight and flat intraday could match/beat
buy-and-hold with far less exposure. We test the decomposition and whether overnight-only
clears the bar **out of sample, net of realistic costs**.

## Data & window
- Source: `runner/daily_bars_cache.py` — Yahoo v8 daily bars. Full OHLC per row + split/div-adjusted `adjclose`. Personal/research use.
- Full available history per ETF (cold-cache reproducible):
  - **SPY** 1993-02-01 → 2026-06-22 (8,404 days)
  - **QQQ** 1999-03-11 → 2026-06-22 (6,862 days)
  - **IWM** 2000-05-30 → 2026-06-18 (6,553 days)
  - **TQQQ** 2010-02-12 → 2026-06-22 (4,113 days)
- Sample size is huge (daily); the trap here is NOT *n* — it is **(a) the cost assumption and (b) time-decay**. Both are hit hard below.

---

## The adjustment-basis reconciliation audit (correctness proof)
`adjclose` is split+div-**adjusted**; `open/high/low/close` are **raw**. They cannot be
mixed. We put open[D] and close[D−1] on the same basis via a per-day factor:

```
f[D]        = adjclose[D] / close[D]          (raw close -> adjusted close)
adj_open[D] = open[D] * f[D]                  (raw open  -> adjusted open)
overnight_ret[D] = adj_open[D] / adjclose[D-1] - 1     (close[D-1] -> open[D])
intraday_ret[D]  = adjclose[D] / adj_open[D]  - 1       (open[D]    -> close[D])
```

**Reconciliation requirement:** `(1+overnight)(1+intraday)` must reproduce the adjusted
close-to-close return `adjclose[D]/adjclose[D-1]` bit-for-bit. The identity is
*algebraically exact* (the `open[D]*f[D]` term cancels), so any residual is pure float
noise. Three independent checks, all ETFs:

| ETF  | worst-day recon residual | log-sum decomposition residual | total-ret product residual (rel) |
|------|--------------------------|--------------------------------|----------------------------------|
| SPY  | 2.22e-16                 | 1.38e-14                       | 1.47e-14                         |
| QQQ  | 2.22e-16                 | 0.00e+00                       | 5.41e-15                         |
| IWM  | 2.22e-16                 | 1.29e-14                       | 1.92e-14                         |
| TQQQ | 2.22e-16                 | 1.10e-14                       | 1.10e-14                         |

✅ **Open and close are provably on the same basis.** overnight×intraday compounds back to
the close-to-close (buy-and-hold) path to machine precision. No Sharpe is reported on an
unreconciled series.

## Timing convention (no lookahead)
- `open[D]` is observable at D's open auction; `close[D]` is **not** known until D's close.
- **Overnight leg:** position entered at `close[D−1]` (known EOD D−1), exited at `open[D]`. The overnight return on row D is earned by that entry/exit — **no field dated later than the decision informs the entry.** Leak-free by construction.
- **Intraday leg:** enter `open[D]`, exit `close[D]`; decision known at the open. Leak-free.
- **Buy-and-hold:** `adjclose[D−1] → adjclose[D]` (= overnight × intraday compounded).

## Cost model
Overnight-only and intraday-only fully **enter and exit every active day** ⇒ **2 sides/day**
(~252 round-trips/yr). We charge `bps_per_side` on each side (`net = (1+gross)·(1−2·bps/1e4)−1`).
Buy-and-hold pays **one** round-trip over the whole window (charged once, for honesty).
Convention matches the bench `recost` family (bps on traded notional per side). The
5–20 bps/side rows are the spread-inclusive estimate — open/close auctions are **not** free
on a real book (half-spread + impact on a liquid ETF auction is a few bps/side).

## Canonical Sharpe
`runner/fp_sharpe.py::sharpe_from_returns` on each leg's realized per-day return series,
**√252 annualization, sample stdev (ddof=1), full-period continuous-span.** (Engine-
convention ddof=0 is identical to 3 dp here since n is large; cross-referenced in JSON.)

---

## RESULTS — full continuous-span (GROSS)

| ETF  | Leg            | Total Ret | CAGR    | MaxDD    | Ann Vol | **Sharpe (fp)** | Exposure |
|------|----------------|-----------|---------|----------|---------|-----------------|----------|
| **SPY**  | overnight-only | +2,312%  | 10.01%  | −32.8%   | 10.6%   | **0.954**       | overnight only |
|      | intraday-only  | +28%      | 0.74%   | −68.5%   | 15.2%   | 0.125           | day only |
|      | **buy & hold** | +2,987%  | 10.83%  | −55.2%   | 18.6%   | 0.647           | 100% |
| **QQQ**  | overnight-only | +3,432%  | 13.99%  | −33.5%   | 14.3%   | **0.989**       | overnight only |
|      | intraday-only  | −52%      | −2.63%  | −88.1%   | 23.1%   | −0.000          | day only |
|      | **buy & hold** | +1,607%  | 10.98%  | −83.0%   | 27.0%   | 0.521           | 100% |
| **IWM**  | overnight-only | +2,558%  | 13.44%  | −28.8%   | 13.3%   | **1.017**       | overnight only |
|      | intraday-only  | −66%      | −4.05%  | −75.9%   | 20.2%   | −0.104          | day only |
|      | **buy & hold** | +807%     | 8.85%   | −58.6%   | 23.9%   | 0.475           | 100% |
| **TQQQ** | overnight-only | +11,891% | 34.08%  | −67.7%   | 37.4%   | **0.976**       | overnight only |
|      | intraday-only  | +231%     | 7.61%   | −61.7%   | 48.4%   | 0.394           | day only |
|      | **buy & hold** | +39,571% | 44.28%  | −81.7%   | 61.1%   | 0.909           | 100% |

**Gross read:** the overnight leg carries essentially all of the risk-adjusted return.
Intraday is the structural loser on the broad-cap names (QQQ −2.6%/yr, IWM −4.1%/yr CAGR
over 25 yr). On **Sharpe and drawdown and vol**, overnight-only dominates buy-and-hold on
all four. On **raw total return**, overnight-only beats B&H for QQQ and IWM but *not* for
SPY/TQQQ (whose strong underlying lets B&H out-compound the lower-vol overnight book).
This is the textbook overnight-return puzzle, reproduced on our data. **Exposure note:** the
overnight book is in the market only ~17.5h/day on weekdays and ~0 on weekends — roughly
**~50% of calendar hours** — yet earns the lion's share of the premium at far lower vol
and shallower drawdowns. That is the genuinely interesting part.

---

## RESULTS — NET of costs (the crux) & BREAKEVEN

Overnight-only NET vs buy-and-hold NET, full period:

| ETF  | bps/side | ON total | ON CAGR | ON Sharpe | BH total | BH CAGR | BH Sharpe | ON>BH (tot / Sharpe) |
|------|----------|----------|---------|-----------|----------|---------|-----------|----------------------|
| SPY  | 0 (gross)| +2,312%  | 10.01%  | 0.954     | +2,987%  | 10.83%  | 0.647     | n / **Y**            |
| SPY  | 2        | −16%     | −0.54%  | 0.003     | +2,985%  | 10.83%  | 0.647     | n / n                |
| SPY  | 5        | −100%    | −14.50% | −1.426    | +2,984%  | 10.83%  | 0.646     | n / n                |
| QQQ  | 0 (gross)| +3,432%  | 13.99%  | 0.989     | +1,607%  | 10.98%  | 0.521     | **Y** / **Y**        |
| QQQ  | 2        | +127%    | 3.05%   | 0.282     | +1,607%  | 10.98%  | 0.521     | n / n                |
| QQQ  | 5        | −96%     | −11.42% | −0.779    | +1,606%  | 10.98%  | 0.521     | n / n                |
| IWM  | 0 (gross)| +2,558%  | 13.44%  | 1.017     | +807%    | 8.85%   | 0.475     | **Y** / **Y**        |
| IWM  | 2        | +93%     | 2.56%   | 0.257     | +807%    | 8.85%   | 0.475     | n / n                |
| IWM  | 5        | −96%     | −11.84% | −0.884    | +806%    | 8.85%   | 0.474     | n / n                |
| TQQQ | 0 (gross)| +11,891% | 34.08%  | 0.976     | +39,571% | 44.28%  | 0.909     | n / **Y**            |
| TQQQ | 2        | +2,213%  | 21.22%  | 0.706     | +39,556% | 44.28%  | 0.909     | n / n                |
| TQQQ | 5        | +96%     | 4.20%   | 0.301     | +39,532% | 44.27%  | 0.909     | n / n                |

### Breakeven cost (bps/side) at which overnight-only stops beating B&H

| ETF  | breakeven — **raw total return** | breakeven — **Sharpe** |
|------|----------------------------------|------------------------|
| SPY  | 0.0 (never beats B&H gross on total ret) | **0.65** |
| QQQ  | **0.53** | **1.32** |
| IWM  | **0.82** | **1.43** |
| TQQQ | 0.0 (never beats B&H gross on total ret) | **0.49** |

**This is the whole story.** The premium is annihilated by **~0.5–1.4 bps/side** — i.e. the
strategy needs a per-side execution cost *below* a single basis point to keep its
Sharpe edge, and below ~1 bp to keep any total-return edge on the two ETFs where it has
one. Real liquid-ETF auction execution (half-spread + impact + the open/close auction
imbalance) runs **several** bps/side. **Even the bench's optimistic 2 bps/side convention
already kills it on every ETF.** At 5 bps/side it is a capital-destruction machine
(daily 2×5 = 10 bps drag × ~252 = ~25%/yr of pure cost bleed).

---

## Time-decay (has the effect weakened?)

Overnight leg, GROSS Sharpe (fp) by sub-period, vs buy-and-hold:

| ETF  | 1990s | 2000s | 2010s | 2020s | pattern |
|------|-------|-------|-------|-------|---------|
| SPY  | **2.565** | 0.425 | 0.969 | 0.710 | huge in the 90s, decayed hard, partial 2010s revival |
| QQQ  | 5.804 (n=206, tiny) | 0.620 | 1.254 | 0.857 | strongest mid-life, softening into 2020s |
| IWM  | — | 1.061 | 1.012 | 1.032 | unusually *stable* ~1.0 across decades |
| TQQQ | — | — | 1.279 | 0.712 | clear fade 2010s → 2020s |

**Crucially**, even where the *gross* overnight Sharpe stays healthy (IWM ~1.0 every
decade), the **net@2bps overnight CAGR is at or below buy-and-hold in every decade since
the 1990s** (e.g. SPY net@2bps CAGR: 2000s −5.6%, 2010s −1.8%, 2020s −1.5% vs B&H
+13–16%). The 1990s were the only era where overnight-only net cleared B&H — and that era
predates the ETF-arb crowding and penny-spread regime that defines modern markets. **The
gross effect has partially decayed; the *net, tradeable* effect has been dead since the
early 2000s.**

---

## Out-of-sample (frozen ≥ 2018, parameter-free strategy)

| ETF  | ON gross Sharpe | BH gross Sharpe | ON net@2bps (tot / Sharpe) | BH net@2bps (tot / Sharpe) | ON net@5bps (tot / Sharpe) |
|------|-----------------|-----------------|----------------------------|----------------------------|----------------------------|
| SPY  | 0.859 | 0.809 | −2.0% / 0.043 | +217.6% / 0.809 | −72.7% / −1.182 |
| QQQ  | 0.939 | 0.916 | +23.8% / 0.247 | +398.0% / 0.916 | −65.5% / −0.793 |
| IWM  | 1.103 | 0.495 | +61.4% / 0.446 | +115.3% / 0.495 | −55.0% / −0.539 |
| TQQQ | 0.813 | 0.810 | +270.6% / 0.580 | +1,383.2% / 0.810 | +3.3% / 0.230 |

OOS, the *gross* overnight Sharpe still edges B&H (the anomaly persists in raw form). But
**net of even 2 bps/side, overnight-only OOS loses to B&H on total return for every ETF,
and on Sharpe for every ETF; at 5 bps/side it is deeply negative on the three broad-cap
names.** OOS confirms the full-sample conclusion: not tradeable at our cost level.

---

## Why this is a clean negative, not a measurement failure
- ✅ Reconciliation proves open/close on the same basis (residuals ~1e-14). Three independent cross-checks (per-day product, log-sum additivity, full-period product) all pass.
- ✅ No lookahead: overnight position decided at the prior close, exited at the next open.
- ✅ Same path / same window for all three legs per ETF.
- ✅ Parameter-free strategy (no tuning to overfit); OOS reported anyway for comparability.
- ✅ The negative is driven entirely by **turnover cost** (252 round-trips/yr) overwhelming a per-trade edge of a few bps — a structural, not statistical, kill. Breakeven < 1.5 bps/side on every ETF.

**The literature is right that the premium exists. The premium is just smaller than the
cost of harvesting it daily.** This is the canonical fate of a high-turnover micro-edge.

## Diagnostic value (what to keep)
1. **Execution timing:** for any long position we *already* intend to hold, the
   decomposition says the open→close session is a structural drag on the broad-cap names —
   marginal support for **executing buys near the close and sells near the open** rather
   than the reverse, *when discretionary about intraday timing.* (Second-order; not a
   strategy.)
2. **Risk-premium localization:** ~all the equity risk premium is overnight; intraday is
   noise-to-negative. Useful context for any intraday strategy (you are fighting a
   headwind during RTH on these names).

## Deliverables
- Backtest: `strategies_candidates/overnight_drift/backtest_overnight.py` (decomposition + cost sweep + breakeven + decade split + OOS; reproducible from cold cache via `python3 -m strategies_candidates.overnight_drift.backtest_overnight`).
- Sanity checks: `strategies_candidates/overnight_drift/_sanity_check.py` (independent reconciliation cross-checks).
- Raw results JSON: `strategies_candidates/overnight_drift/overnight_drift_result.json`.
- No protected engine file or live strategy was touched.

## Bottom line
**NO — CLOSE.** Overnight drift is real and large gross (overnight Sharpe ≈ 1.0 vs B&H
≈ 0.5–0.9, intraday ≈ 0), but **breakeven is ~0.5–1.4 bps/side**, it dies at the
optimistic 2 bps bench cost, it is wiped out at a realistic 5 bps/side, the net edge has
been dead since the early 2000s, and OOS (≥2018) it loses to buy-and-hold net on every
ETF. **Real but untradeable at our cost level.** Keep the decomposition as an execution-
timing/diagnostic note; do not pursue overnight-only as a standalone book.
