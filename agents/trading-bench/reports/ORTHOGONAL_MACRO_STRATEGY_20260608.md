# Orthogonal Macro Strategy — `macro_regime_long` — Build + Walk-Forward Verdict
**2026-06-08 · trading-bench · PAPER/quarantine candidate · honest negative result**

## What this is
The first deliberately **orthogonal-to-price** strategy in the bench. The parent
pool feeding the mutation engine is only 2 price-derived signals (Donchian breakout
XLK + SMA-cross QQQ), and the 2026-06-08 diversity profile
(`reports/PARENT_DIVERSITY_PROFILE_20260608.md`) confirmed **no existing strategy adds
a gate-clearing orthogonal signal**. So we built one whose entry/exit comes entirely
from macro data (Fed balance sheet + Treasury curve), not from QQQ's own price, and ran
it through the **same** walk-forward fitness gate the parents pass.

- **Candidate:** `strategies_candidates/macro_regime_long/` (strategy.py + params.json + __init__.py)
- **Data layer:** `runner/macro_cache.py` (new) — WALCL (Fed total assets) + T10Y2Y (10y-2y spread) via the existing keyed FRED cache.
- **Backtester (`runner/backtest.py`) UNTOUCHED** — Option-B wiring: the strategy reads macro itself via `macro_cache` and maps each bar's date to the most-recent *lag-allowable* macro row. md5 of backtest.py unchanged (`9444ee5be64d9fd2639fd8cb0a28e002`).

## Signal (as specified)
`risk_on = (13-week slope of WALCL ≥ 0) AND (T10Y2Y > −0.5)`. Hold QQQ long when
risk-on, else flat. Close logic runs first (never trapped long).

**Anti-lookahead (verified empirically):** `macro_cache` shifts every observation's
effective-known date forward by its publication lag (WALCL +9d ≈ the H.4.1
Thu-after-ref-Wednesday gap; T10Y2Y same-day market quote), and at each bar returns only
the macro value whose effective date ≤ that bar's date. Spot-checks confirmed no leak
(e.g. WALCL effective 2020-06-12 ≤ as-of 2020-06-15). The 13-week slope's far leg is
resolved through the same lag filter.

## Walk-forward result — **FAIL the fitness gate**

| metric | value | gate threshold |
|---|---|---|
| median return % | **+0.00%** | > 0 |
| median Sharpe | **0.00** | > 0.50 |
| pct positive windows | **25%** | ≥ 50% |
| pct beat buy&hold SPY | 62.5% | ≥ 50% ✓ (only this one passes) |
| **total trades (all 8 windows)** | **7** | (min-trades floor would also fail) |

### Per-window — the smoking gun
| window | return% | Sharpe | n_trades |
|---|---|---|---|
| 2022-H1 bear | −0.02% | −4.64 | 4 |
| 2022-Q3 chop | 0.00% | 0.00 | **0** |
| 2023-H1 recovery | +0.05% | +1.17 | 2 |
| 2023-Q3 chop | 0.00% | 0.00 | **0** |
| 2024-Q2 bull | 0.00% | 0.00 | **0** |
| 2025-Q1 tariff bear | 0.00% | 0.00 | **0** |
| 2025-Q3 bull | 0.00% | 0.00 | **0** |
| 2026-recent bull | +2.34% | +12.99 | 1 |

**5 of 8 windows have ZERO trades.** This is not "the macro signal is weak" — it's two
distinct, deeper problems:

## Finding 1 — the signal sat in CASH for ~3.5 years (a real design flaw)
Sampling the gate state across each window (start/mid/end) shows the **liquidity gate was
hard-OFF for essentially all of 2022-Q3 → 2025-Q3**:

```
2022-Q3 chop      OFF  liq=-28k…-100k
2023-H1 recovery  OFF  liq=-252k   (and curve −0.7…−1.0)
2023-Q3 chop      OFF  liq=-372k…-290k
2024-Q2 bull      OFF  liq=-210k…-262k
2025-Q1 bear      OFF  liq=-194k…-133k
2025-Q3 bull      OFF  liq=-78k…-72k
2026-recent       OFF→ON (liq flips +93k mid-window)
```
The 13-week WALCL slope was **negative continuously** through that span — because that *is*
the Fed's **QT (quantitative-tightening) era**: the balance sheet shrank from mid-2022
through 2025. Using the **raw sign** of the slope as a risk-off gate therefore means
*"any QT at all ⇒ zero equities"* — which kept the strategy in cash through one of the
largest bull markets in history (2023-24). That's not conservative; it's **wrong**. The
gate is far too blunt: QT and a roaring equity market coexisted for two years.

The lone full-trade windows confirm the binary gate, not the thesis, is the problem: the
two windows it *did* trade were both directionally fine (2023-recovery +1.17 Sharpe,
2026-recent +12.99 Sharpe on 1 trade), and it **beat buy&hold SPY in 5/8 windows** — but
only by *being in cash during drawdowns*, which is risk-reduction, not edge.

## Finding 2 — slow macro regimes are structurally incompatible with the current gate
Even with a *better* threshold, a macro regime that changes state on a multi-month
timescale will rarely complete a round-trip inside a **quarter-length** walk-forward
window. The gate's `pct_positive` and (new) min-trades-40 floor are calibrated for
strategies that **churn dozens of trades per window** (the parents do 60-140). A
hold-for-months overlay produces 0-1 round-trips per quarter → it literally *cannot*
satisfy a churn-based gate, regardless of whether the underlying signal has edge. This is
a **harness limitation for slow-signal strategies**, not just a verdict on this candidate.

## Honest read
**Neither real edge nor even clean drawdown-reduction as specified.** The candidate fails
the gate, and the reason is a genuine design flaw (raw-QT-sign gate missed the QT-era
bull) compounded by a harness mismatch (slow regime vs short windows). It does *not*
become a parent.

## What this tells the project (the valuable part)
1. **Orthogonal macro is not free edge.** The cleanest, most-cited macro risk-on/off
   gates (Fed liquidity sign + curve) do **not** clear the bench's bar — consistent with
   the broader finding that the bench's ~0.5-Sharpe ceiling is a *signal* ceiling.
2. **The gate panel is mis-specified for slow strategies.** If we want macro/regime
   overlays in the tournament at all, they need **either** longer evaluation windows
   (1-2yr) **or** a slow-strategy metric track (judge on full-period Sharpe + drawdown +
   exposure, not per-quarter round-trip churn). Forcing them through the churn gate
   guarantees a 0-trade FAIL.
3. **If pursued, fix the signal, not just the harness:** replace raw-slope-sign with
   liquidity **relative to its own trend / rate-of-change of the change**, and make the
   curve gate less binary — so the gate distinguishes "QT but risk-on equities" (2023-24)
   from "QT into recession." That's a real research lane, not a one-line tweak.

## Disposition
- Candidate **stays in quarantine**; NOT added to `GATE_PASSING_PARENTS`.
- `runner/macro_cache.py` is **kept** — it's correct, lag-safe, reusable infrastructure
  for any future macro/regime work (the hard part — clean PIT macro access — is done).
- Recommended next experiment if this lane is continued: a **slow-strategy evaluation
  track** (longer windows + exposure/drawdown metric) + a **non-binary liquidity signal**.
  Lower priority than it looked pre-test: the raw macro gate having no edge is itself the
  finding.
