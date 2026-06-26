# INTRADAY ANNUALIZATION BUG — FIX + IMPACT RE-RANK

**Generated:** 2026-06-25 (PT) · **Author:** Tessera (trading-bench) · **Type:** measurement-integrity fix
**Triggered by:** `reports/INTRADAY_READINESS_AUDIT_20260625T155500Z.md` (finding #1)
**Class:** same family as the √252 Sharpe bug (2026-05-31) — annualization error → inflated Sharpe → corrupted gate decisions.

---

## TL;DR

`runner/backtest.py:bars_per_year()` was **class-blind for intraday**: every sub-daily timeframe returned a crypto `24h × 365d` bar-count regardless of asset class. US equities only trade the ~8.5h session the data feed delivers (~510 min, pre-market + RTH) on ~252 days/yr, so **equity intraday Sharpe was overstated by ~2.02×** at every intraday timeframe.

**FIXED** (class-aware intraday `bars_per_year`) + **4 new pinning tests**. Full suite **760 passed / 1 skipped** (was 756), zero regressions.

**Scope of the corruption — read this carefully, it is NARROWER than "the leaderboard is wrong":**

| Surface | Affected? | Why |
|---|---|---|
| **Live tournament leaderboard** (`runner/ranking.py`) | ❌ **NO** | Ranks realized **daily P&L** of actual paper fills (FIFO on `tournament.db` trades). Never touches `bars_per_year` or backtest Sharpe. Risk metrics it attaches are √252 on a **daily-P&L** series (correct). |
| **Backtest report Sharpe at intraday TF** | ✅ **YES, ÷2.02×** | Any `1Hour`/sub-hour backtest Sharpe (reports, sweeps, walk-forward, candidate evaluation) was inflated. |
| **Promotion-gate decisions** | ✅ **YES** | A candidate that "cleared a Sharpe bar" via a 1Hour backtest was inflated ~2×. **This is the real damage.** |
| Daily-timeframe strategies | ❌ NO | `1Day` path was already correct (252 equity / 365 crypto). |
| Crypto intraday | ❌ NO | Fix is equity-only; crypto intraday bpy unchanged (== legacy table). |

---

## The bug (confirmed independently)

`runner/backtest.py` (pre-fix):

```python
def bars_per_year(timeframe, is_crypto):
    if timeframe == "1Day":
        return 365.0 if is_crypto else 252.0
    return float(BARS_PER_YEAR.get(timeframe, 24 * 365))   # is_crypto IGNORED
```

`BARS_PER_YEAR["1Hour"] = 24*365 = 8760`. For an equity 1Hour strategy the honest count is `8.5h × 252 = 2142`. The accessor never branched on class for intraday — the in-code comment even *defended* it ("an hour is an hour"). That reasoning is wrong for equities, which are not 24/7.

**Magnitude:** `sqrt(8760 / 2142) = 2.0223×` Sharpe inflation, identical across all intraday TFs (the ratio is purely `session-coverage × day-count`, bar-size-independent).

**Empirical grounding:** Alpaca IEX returns ~8.6 1Hour SPY bars/day spanning 12:00–20:00 UTC (08:00–16:00 ET = pre-market + RTH). I used **510 min/day** (8.5h) to match the bars the engine *actually sees* — the honest-measurement choice (slightly higher than the audit's theoretical pure-RTH 390 min, because the free feed includes pre-market).

---

## The fix

`runner/backtest.py` — class-aware intraday, daily path untouched, crypto unchanged:

```python
EQUITY_INTRADAY_MINUTES_PER_DAY = 510   # ~8.5h feed session (pre-mkt + RTH)
CRYPTO_MINUTES_PER_DAY = 1440           # 24/7

def bars_per_year(timeframe, is_crypto):
    if timeframe == "1Day":
        return 365.0 if is_crypto else 252.0
    tf_min = _TF_MINUTES.get(timeframe)
    if tf_min is None or tf_min >= 1440:
        return float(BARS_PER_YEAR.get(timeframe, 24 * 365))   # legacy fallback
    if is_crypto:
        return (1440 / tf_min) * 365.0
    return (510 / tf_min) * 252.0
```

Corrected equity intraday bars/year: 1Min 128,520 · 5Min 25,704 · 15Min 8,568 · 30Min 4,284 · **1Hour 2,142**. Crypto intraday and all daily values unchanged.

Single-point fix: all engines (`backtest`, `backtest_xsec`, `backtest_event`) + `fp_sharpe` + `spy_relative` + `vix_overlay` share this one function, so they're all corrected at once.

**Tests:** `tests/test_sharpe_annualization.py` — replaced the test that pinned the *buggy* `1Hour == 24*365` behavior with 4 tests pinning the corrected class-aware values + the 2.02× deflation factor + the 510-min session constant. 11/11 pass; full suite 760/1.

---

## Impact re-rank — live 1Hour strategies (raw backtest, 1500d, 2bps)

These are **raw-backtest** Sharpes (NOT the live leaderboard, which is unaffected). Shown to quantify the correction magnitude on the actual book. `was(bug)` = the inflated number a pre-fix run would have reported.

| strategy | trades | corrected Sharpe | was (bug) |
|---|---:|---:|---:|
| buy_and_hold_spy | 1 | **+0.982** | +1.986 |
| breakout_xlk | 234 | −2.977 | −6.020 |
| momentum_arkk | 244 | −3.420 | −6.916 |
| volume_breakout_qqq | 114 | −3.681 | −7.444 |
| rsi_mean_revert_iwm | 140 | −3.728 | −7.538 |
| rsi_oversold_spy | 125 | −3.938 | −7.964 |
| breakout_xlk__mut_c382b1 | 470 | −5.131 | −10.377 |
| sma_crossover_qqq_regime | 270 | −5.807 | −11.744 |
| sma_crossover_qqq | 350 | −6.321 | −12.782 |
| macd_momentum_iwm | 242 | −6.336 | −12.813 |
| sma_crossover_qqq_rth | 344 | −6.504 | −13.153 |

**Reading this honestly:** the raw-1Hour-backtest Sharpes are deeply negative because these strategies churn at hourly cadence under 2bps cost over this window — that is a *backtest artifact of the timeframe*, not a statement that the live book is bleeding (the live book trades sparsely and is ranked on realized daily P&L). The point of the table is the **right column vs left**: every intraday backtest number we have ever quoted was ~2× too generous in magnitude. For the one positive case (`buy_and_hold_spy`), the inflation turned a true +0.98 into a false +1.99 — exactly the kind of distortion that would wrongly clear a Sharpe≥1.0 promotion gate.

---

## Consequences / follow-ups

1. **Any historical report citing a 1Hour (or sub-hour) Sharpe is overstated ~2.02×.** Not mass-editing old reports, but future readers should apply the correction; the canonical ruler is now fixed.
2. **Promotion gates are now honest at intraday.** No candidate should clear a Sharpe bar on inflated intraday numbers going forward.
3. **The live leaderboard needs no recompute** — it was never a function of this constant (verified: `ranking.py` is realized-daily-P&L only).
4. **Remaining intraday-readiness gaps (from the audit, NOT fixed here, deliberately):** lookback-in-bars semantics (a daily-authored SMA30 = 30min at 1Min) and the `MAX_TRADES_PER_DAY=4` per-session cap. These are documented in the audit's punch-list and gated behind "before first real intraday strategy" — not live-correctness bugs, so not fixed in this pass.

---

*Fix is measurement-honesty only. No strategy logic, no risk caps, no live behavior changed. `runner/ranking.py` (live board) untouched and unaffected.*

---

## ADDENDUM — does any PAST promotion need re-evaluation? (main's follow-up)

Two gate paths consume walk-forward Sharpe (now corrected):

1. **`passes_mutation_gate`** (LLM-mutation gate) uses `MUTATION_SHARPE_DELTA_TOL = -0.10` — a **delta vs parent**, not an absolute level. A uniform 2.02× rescale hits parent and mutant identically, so the delta is **preserved**. → **Mutation-gate promotions are NOT retroactively invalidated** by this fix (scale-invariant). `breakout_xlk__mut_c382b1` (the one live mutant) stands.
2. **`passes_fitness_gate`** has an **ABSOLUTE** `median_sharpe > 0.5` clause — this **IS** affected. A 1Hour candidate that cleared with an inflated median Sharpe ~0.6 (true ~0.3) would now correctly **FAIL**. So the fitness gate was too lax at intraday pre-fix.

**Why no retroactive removal is warranted today:**
- The live leaderboard is realized **daily P&L** (`ranking.py`), not gate-Sharpe — live membership doesn't depend on this constant.
- The current mission has **absolute Sharpe gates SUSPENDED** (raw-return-vs-SPX mandate). The fitness gate's 0.5 clause is not the active promotion criterion right now.
- The live 1Hour book is the **legacy tournament seed**, tracked on paper P&L — not strategies living on a strong intraday-Sharpe claim (their corrected raw Sharpes are negative anyway).

**Standing consequence:** if/when an absolute Sharpe gate is reinstated, it now bites correctly at intraday. And `runner/reeval_candidates.py` → `passes_mutation_gate`/`passes_fitness_gate` now apply the honest Sharpe automatically on the next candidate re-eval — no separate backfill needed.
