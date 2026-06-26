# INTRADAY LOOKBACK CONVENTION + RISK-CAP — implementation report

**Generated:** 2026-06-25T17:00Z · **Scope:** audit MUST-FIX punch-list items #2 (lookback/warmup time-convention helper + guard) and #3 (intraday-aware per-day trade cap). · **Source audit:** `reports/INTRADAY_READINESS_AUDIT_20260625T155500Z.md` §(d) items 2 & 3.

> **Item #1 (bars_per_year intraday fix) was ALREADY DONE before this task and was NOT touched.** `runner/backtest.py:bars_per_year` and `tests/test_sharpe_annualization.py` are byte-for-byte unchanged. Everything below is **additive** and **behavior-preserving for the existing all-daily / all-1Hour live book**.

---

## 0. Files changed

| File | Change |
|------|--------|
| `runner/backtest.py` | **+** `timeframe_to_daily_bars()`, **+** `assert_lookback_sane()`, **+** `_LOOKBACK_TOKENS`, **+** `_warn_lookback_if_intraday()`; wired a non-fatal intraday-only lint into `load_strategy_module_and_params`. |
| `runner/backtest_xsec.py` | imported `assert_lookback_sane` from `.backtest`; wired the same non-fatal intraday-only lint into `load_xsec_strategy`. |
| `runner/risk.py` | extended `resolve_trades_per_day(params, timeframe=None)` with a documented 4-tier precedence; **+** constants `MAX_TRADES_PER_DAY_CEILING=50`, `INTRADAY_TRADES_PER_DAY_DEFAULT=20`, `_INTRADAY_TIMEFRAMES`; **+** helpers `_is_intraday_tf`, `_explicit_trades_override`, `_xsec_basket_bump`; updated module docstring. |
| `tests/test_timeframe_lookback.py` | **NEW** — 32 focused unit tests covering both items. |

`runner/runner.py` was **deliberately NOT modified** — see §1c.

---

## 1. ITEM 2 — lookback/warmup time-convention helper + guard

### (a) Helper API — `runner/backtest.py`

```python
def timeframe_to_daily_bars(timeframe: str, is_crypto: bool = False) -> float
```
Returns how many bars of `timeframe` equal **one trading day**:
- `1Day` → `1.0` (both classes)
- equity intraday → `EQUITY_INTRADAY_MINUTES_PER_DAY / _TF_MINUTES[tf]` → **8.5** at 1Hour, **510** at 1Min
- crypto intraday → `CRYPTO_MINUTES_PER_DAY / _TF_MINUTES[tf]` → **24** at 1Hour, **1440** at 1Min
- unknown timeframe → **`ValueError`** (explicit; never silently guesses)

It **reuses the existing constants** already in `backtest.py` (`EQUITY_INTRADAY_MINUTES_PER_DAY=510`, `CRYPTO_MINUTES_PER_DAY=1440`, `_TF_MINUTES`) — same session model as the (already-fixed) `bars_per_year`. No new module, no new imports, no cycle.

### (b) Guard API — `runner/backtest.py`

```python
def assert_lookback_sane(params: dict, timeframe: str, is_crypto: bool = False,
                         *, lookback_keys=None) -> list[str]
```
A **non-fatal lint**. It inspects lookback-ish numeric params and returns a list of human-readable WARNING strings; it **never raises on warnings** and **never mutates `params`**.

- **Which keys** — case-insensitive substring match against `_LOOKBACK_TOKENS = (slow, fast, window, period, lookback, span, sma, rsi, bars, exit_lookback, time_stop_bars)`, exactly the audit §2 list. An explicit `lookback_keys=[...]` override bypasses the token scan and inspects only the named keys. Bool and non-numeric values are skipped.
- **When it warns** — a lookback param warns iff its bar count is **less than one trading day's worth of bars** at that timeframe: `value < timeframe_to_daily_bars(timeframe, is_crypto)`. That means the window no longer spans a single session — a strong tell that the count was authored in **daily** units and is being misapplied at a finer timeframe.
- **Guaranteed quiet cases (verified by tests):**
  - `timeframe == "1Day"` → always `[]` (one bar == one day; counts are in their authored unit).
  - normal daily-authored counts at **1Hour** (e.g. `slow=30` → 30/8.5 = 3.5 trading days) → `[]`.
- **Unknown timeframe** → propagates `ValueError` (a bad tf is a real config error, not something to lint past).

Example warning string (real `volume_breakout_qqq` case at 1Hour):
> `lookback param 'exit_lookback'=8 at timeframe '1Hour' covers only 0.94 trading day(s) (8.5 bars/day); if this count was authored for DAILY bars it is being misapplied at this finer timeframe (it no longer spans a full session).`

### (c) Wiring — non-fatal, intraday-only, daily book untouched

- `runner/backtest.py: load_strategy_module_and_params` → calls `_warn_lookback_if_intraday(name, params)`, which **returns immediately when `timeframe == "1Day"`** (zero new output for the daily book) and otherwise prints `"[<name>] WARN lookback-sanity: ..."` to **stderr**. Wrapped in `try/except` so a lint bug can never block a load.
- `runner/backtest_xsec.py: load_xsec_strategy` → same intraday-only, `try/except`-guarded stderr warning after params load.
- **`runner/runner.py` (live decide path) was SKIPPED on purpose.** The audit said to skip it "if it risks noise on every daily tick." The live book is **1Hour**, `runner.py:load_strategy` runs **once per tick**, and one live strategy — **`volume_breakout_qqq`** (`exit_lookback=8` < 8.5 bars/day) — **would emit a warning every single hour** even though that 8 is intentional. Wiring runner.py would spam a real live strategy's log hourly for no benefit, so the helper is exposed and wired only into the on-demand backtest loaders. (At 1Day, runner.py would be silent anyway — but it is not all-daily, it is 1Hour, so the noise risk is live and real.)

Behavior at `1Day` is unchanged: no warnings, no extra compute on the hot path (the lint is at load time, not per-bar, and short-circuits on `1Day`).

### (d) Strategy lookback inventory (no params changed — inventory + documentation only)

Grep of `strategies/*/params.json` for numeric lookback-ish params, with the **same key-matching logic the guard uses**. Right-most columns: would the guard warn at the **live 1Hour** cadence, and at **1Min**?

| Strategy | timeframe | Lookback-ish params | warns @1Hour? | warns @1Min? |
|---|---|---|---|---|
| allocator_blend | 1Day | *(none numeric/lookbacky)* | — | n/a (daily) |
| breakout_xlk | 1Hour | `lookback=20` | no | **yes** |
| breakout_xlk__mut_c382b1 | 1Hour | `lookback=20, regime_period=50` | no | **yes** |
| breakout_xlk_regime | 1Hour | `lookback=20, regime_period=50` | no | **yes** |
| buy_and_hold_spy | 1Hour | *(none)* | — | — |
| leveraged_long_trend_paper | 1Day | `vol_window=20, sma_window=200` | — | n/a (daily) |
| macd_momentum_iwm | 1Hour | `fast=12, slow=26` | no | **yes** |
| momentum_arkk | 1Hour | `lookback=24` | no | **yes** |
| rsi_mean_revert_iwm | 1Hour | `rsi_period=14` | no | **yes** |
| rsi_oversold_spy | 1Hour | `rsi_period=14, exit_rsi=70, time_stop_bars=20` | no | **yes** |
| sma_crossover_qqq | 1Hour | `fast=10, slow=30` | no | **yes** |
| sma_crossover_qqq_regime | 1Hour | `fast=10, slow=30, regime_period=50` | no | **yes** |
| sma_crossover_qqq_rth | 1Hour | `fast=10, slow=30` | no | **yes** |
| tqqq_cot_combo | 1Day | `vol_window=20, sma_gate_window=200` | — | n/a (daily) |
| trend_follow_gld | 1Day | `period=20` | — | n/a (daily) |
| **volume_breakout_qqq** | 1Hour | `lookback=20, exit_lookback=8` | **YES (exit_lookback=8)** | **yes** |

**Findings:**
1. **Every 1Hour strategy is clean at the live 1Hour cadence EXCEPT `volume_breakout_qqq`**, whose `exit_lookback=8` (< 8.5 bars/day) trips the lint. The 8 is an intentional ~1-session exit window; this is the canonical "right at the boundary" case and is exactly why runner.py was not wired (§1c). It is a *warning*, not an error — no behavior change.
2. **At 1Min, every strategy carrying a lookback param would warn** — confirming the audit's foot-gun thesis: a daily/1Hour-authored `slow:30`, `rsi_period:14`, `lookback:20`, `sma_window:200`, etc. all collapse to a sub-session window at 1Min. The guard catches this for any **future** intraday reuse.
3. **No params were migrated.** We are not moving the live daily/1Hour book to intraday; the guard exists to catch future misuse, per the task.

> Note on `exit_rsi=70`: the `rsi` token also flags threshold params like `exit_rsi`. For a non-fatal lint, an occasional conservative false-positive at intraday is acceptable; callers that want tighter scope pass `lookback_keys=[...]`. (At 1Hour `exit_rsi=70` > 8.5 so it does not warn anyway; it would only warn at very fine timeframes.)

---

## 2. ITEM 3 — intraday-aware per-day trade cap (`runner/risk.py`)

### (a)+(b) New signature, precedence, and constants

```python
def resolve_trades_per_day(params: Optional[dict], timeframe: Optional[str] = None) -> int
```
`timeframe` is **optional and defaults to `None`** → **exactly** the pre-change behavior, so all existing single-arg callers are untouched.

**Precedence (highest wins), documented in the docstring:**
1. **EXPLICIT override** — `max_trades_per_day: N` in params, clamped to `[1, MAX_TRADES_PER_DAY_CEILING]`. Honored at **any** timeframe. Malformed/`<1` → ignored (falls through).
2. **INTRADAY default** — when `timeframe` is sub-daily and no explicit override: `INTRADAY_TRADES_PER_DAY_DEFAULT` (**20**), but **never below the xsec-basket bump** (`max(20, 2*K)`), all clamped to the ceiling.
3. **XSEC-basket bump** — `xsec_basket_size: K` (1≤K≤`MAX_XSEC_BASKET_SIZE`) → `max(MAX_TRADES_PER_DAY, 2*K)`. Applies at daily / no-timeframe.
4. **LEGACY default** — `MAX_TRADES_PER_DAY` (**4**).

**New constants:**
- `MAX_TRADES_PER_DAY_CEILING = 50` — hard safety clamp on the explicit override and the intraday default (mirrors the `MAX_XSEC_BASKET_SIZE` clamp pattern; a typo'd `max_trades_per_day: 100000` can never authorize runaway turnover).
- `INTRADAY_TRADES_PER_DAY_DEFAULT = 20` — the chosen intraday default (reasoning below).
- `_INTRADAY_TIMEFRAMES` — frozenset of sub-daily tfs used to detect intraday.

The explicit-override and basket-bump parsers (`_explicit_trades_override`, `_xsec_basket_bump`) use the **same defensive style** as the original `xsec_basket_size` handling: parse via `int(...)`, range-check, malformed → safe fallback, **never raise**. (String numerics like `"7"`/`"3"` still parse, preserving the existing `test_resolve_k_string_numeric_works` contract.)

### Chosen intraday default — **20 trades/UTC day** — and why

- The legacy cap of **4/UTC-day** encodes a *once-or-twice-a-day-decision* book. An intraday strategy that legitimately enters/exits several times per session would be **silently truncated after trade #4** (every later trade logs `skip_risk` and is dropped, biasing the backtest toward early-session fills — audit §3). The default must lift that throttle.
- I deliberately **did NOT scale the default to the raw bar count.** A proportional cap would authorize **510 trades/day at 1Min** — that invites runaway turnover, and the free **IEX-only** feed already makes minute-scale fills optimistic, so a high churn ceiling would flatter exactly the strategies we trust least. A single, defensible, bounded number is safer and clearer.
- **20 trades/UTC day ≈ 10 round trips per session** — high enough to let a real multi-entry intraday strategy breathe (5× the daily cap), low enough to remain a runaway rail. It sits well under the `MAX_TRADES_PER_DAY_CEILING=50` hard clamp, leaving explicit opt-in headroom for the rare strategy that genuinely needs more (`max_trades_per_day`, still clamped to 50).
- **Daily is provably unchanged:** `timeframe` None or `"1Day"` takes tiers 3/4 only → still **4** (or basket-bumped). Verified against the existing `test_risk.py` regression suite and new explicit-`1Day` tests.

### (c) Callers — all still work (no timeframe passed → unchanged)

`grep -rn resolve_trades_per_day runner/` (excluding the def and docstring) →
- `runner/backtest_xsec.py:381` — `risk_mod.resolve_trades_per_day(params)`
- `runner/runner_xsec.py:419` — `risk.resolve_trades_per_day(params)`
- `runner/runner.py:492` — `risk.resolve_trades_per_day(params)`

All three pass **no `timeframe`** → resolve via the legacy/daily path → **behavior identical**. No live `params.json` was changed; the resolver is merely *capable* + *documented*. (Wiring callers to pass a timeframe is a future change for when an actual intraday strategy ships — out of scope here, and would be inert for the all-daily/1Hour book unless a strategy opts in.)

---

## 3. Tests + verification

### New tests — `tests/test_timeframe_lookback.py` (32 tests)
- `timeframe_to_daily_bars`: 1Day/1Hour/1Min for equity **and** crypto, crypto>equity invariant, `ValueError` on junk/`""`/`"7Min"`.
- `assert_lookback_sane`: `[]` at 1Day; `[]` for normal 1Hour daily counts; warns at 1Min for daily-authored `slow=30`/`fast=10`; warns for the real `exit_lookback=8` @1Hour case; no-mutation; skips non-lookback keys / bool / non-numeric; explicit `lookback_keys` override; crypto 1440 threshold; `ValueError` propagation.
- `resolve_trades_per_day`: **backward-compat** (None/`{}`/xsec = 4/6/12; explicit `1Day` == omitted) **UNCHANGED**; intraday default (20, never below basket bump); explicit override (daily + intraday, beats basket+intraday, ceiling clamp, malformed fall-through, string numeric); ceiling as hard safety floor.

### Full-suite before / after
| | passed | skipped |
|---|---|---|
| **Before** (baseline) | **760** | **1** |
| **After** | **792** | **1** |

`792 = 760 + 32` new tests. **Zero regressions** — no existing test was modified or broken. (No test was edited to "match" a change; backward-compat was preserved in the code, and the pre-existing `tests/test_risk.py` cap regressions + `tests/test_sharpe_annualization.py` both pass untouched.)

### Daily-book numerics unchanged — evidence
- **Item #1 untouched:** `runner/backtest.py:bars_per_year` body and `tests/test_sharpe_annualization.py` are unmodified (verified by inspection; the 510/1440 session model is exactly as the prior fix left it).
- **Helpers are additive & off the daily compute path:** `timeframe_to_daily_bars` / `assert_lookback_sane` are new functions; the only call sites are the two backtest **loaders**, gated on `timeframe != "1Day"` → a daily load executes zero new logic and prints nothing.
- **Daily cap identical:** `resolve_trades_per_day(params)` (no timeframe) and `(params, "1Day")` both return **4** (or the unchanged basket bump) — pinned by both the legacy `test_risk.py` suite and new tests.
- **No import cycle:** `runner/risk.py` does **not** import `runner/backtest.py` (intraday detection is a local frozenset), so the `backtest → risk` import direction is preserved.

---

## 4. Summary

- **Item 2:** added a unit-bridge `timeframe_to_daily_bars` + a non-fatal `assert_lookback_sane` lint, wired intraday-only into both backtest loaders (daily book silent). Inventoried all 16 strategies; only `volume_breakout_qqq` warns at the live 1Hour cadence (`exit_lookback=8`), and that boundary case is precisely why `runner.py` was left unwired. No params migrated.
- **Item 3:** `resolve_trades_per_day` is now timeframe-aware with explicit > intraday-default(20) > xsec-bump > legacy(4) precedence, an explicit `max_trades_per_day` override path, and a `MAX_TRADES_PER_DAY_CEILING=50` runaway clamp — all fully backward-compatible (daily/single-arg = exactly 4/6/12 as before). No live params changed.
- **760 → 792 passed / 1 skipped, zero regressions. Daily book numerically untouched.**
