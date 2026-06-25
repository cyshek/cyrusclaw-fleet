# L134 — `position_state` Persistence Verification (live runner)

**Date:** 2026-06-24
**Author:** Tessera (trading-bench)
**Scope:** READ-ONLY verification. No protected file modified (runner/*, strategies/*, risk.py, GATE.md, params.json all mtime-unchanged). Scratch: `_l134_state_probe.py`, `_l134_state_probe2.py`, `_l134_fills.py`, `_l134_dryrun.py` at workspace root.
**Assigned by:** main oversight cron — "the fix shipped 2026-05-26 but no live trade has hit a stateful exit branch yet to confirm it's exercised in production; verify it, and if no real trade has hit it, write a dry-run that exercises the path directly so we know it works before it matters."

---

## TL;DR

The 2026-05-26 persistence infra is **half-confirmed-working and half-exposes a real latent bug**:

- ✅ **Cross-flat path (`strategy_persistent_state` table) is CONFIRMED exercised live and working.** `allocator_blend` persists `{"last_rebalance_month":"2026-06"}` across flat every tick (1 row, updated 2026-06-24T19:30Z). This is the harder path and it round-trips correctly in production.
- ✅ **In-position path (`strategy_state` table) round-trip works FOR STRATEGIES THAT FOLLOW THE CONTRACT** — proven by dry-run: a custom key in the per-symbol sub-dict (`position_state[symbol]["_entry_bar"]`) saves and reloads, broker-truth keys stripped.
- 🔴 **But two live strategies VIOLATE the contract and are silently broken in live** — they write bookkeeping keys at **top-level** `position_state["_key"]` instead of inside `position_state[symbol]`. The runner only persists `position_state[action.symbol]` (the per-symbol sub-dict), so those top-level keys are **never saved, never reloaded** → the state resets every tick in live. Backtest masks it because `backtest.py` reuses ONE `position_state` dict across bars (top-level key survives in-memory within a run). **Classic "works in backtest, silently broken live" asymmetry — same bug class as the 2026-05-26 incident.**

The `strategy_state` table being **empty (0 rows)** despite `rsi_oversold_spy` being mid-position right now is the live symptom of this.

---

## Evidence

### 1. Live DB state (`tournament.db`)
- `strategy_state` (in-position, cleared-on-close): **0 rows.**
- `strategy_persistent_state` (cross-flat): **1 row** — `allocator_blend | _xsec_ | {"last_rebalance_month":"2026-06"} | 2026-06-24T19:30:17Z`. ✅ working.

### 2. Which live strategies use `position_state` bookkeeping
Grep of `strategies/*/strategy.py`: `allocator_blend`, `leveraged_long_trend_paper`, `macd_momentum_iwm`, `rsi_oversold_spy`, `tqqq_cot_combo`.
- `allocator_blend` uses the **cross-flat** API (`market_state["strategy_state"]`) — correct, confirmed working.
- `leveraged_long_trend_paper`, `tqqq_cot_combo` only **read** `position_state[symbol]` broker-truth (qty) — no custom persisted key, nothing to break.
- `macd_momentum_iwm`, `rsi_oversold_spy` write **top-level** custom keys → the bug.

### 3. Live fills for the two affected strategies
- `rsi_oversold_spy`: **1 fill** — id 67, BUY SPY 2026-06-23T13:30Z, "RSI=28.0 < oversold 28.0". **No close row → currently mid-position.** Its `_rsi_spy_entry_bar` marker should be persisted but the table is empty.
- `macd_momentum_iwm`: **0 fills** — never traded live → bug is latent/unexercised (but would bite the moment it trades).

### 4. The mechanism (code-level)
**`runner/runner.py` save path (lines ~290-293):**
```python
if action.symbol and action.symbol in position_state:
    db.save_strategy_state(strategy_name, action.symbol, position_state[action.symbol])
```
→ persists `position_state["SPY"]` (the **per-symbol sub-dict**).

**`strategies/rsi_oversold_spy/strategy.py` line 55:**
```python
position_state["_rsi_spy_entry_bar"] = n_bars   # TOP-LEVEL, not position_state[symbol]
```
→ written to `position_state["_rsi_spy_entry_bar"]`, which is **not inside** `position_state["SPY"]`, so the runner never saves it.

**`runner/backtest.py` (lines 369 + loop):** `position_state: dict = {}` is hoisted **once** above the bar loop and only `.pop(symbol)`'d on flat. A top-level key therefore **survives across bars within a backtest run** — so the time-stop works in backtest. The code comment even flags it: *"This mirrors how the live runner SHOULD behave; runner/runner.py needs the same fix (separate change)."*

### 5. Dry-run proof (`_l134_dryrun.py`, against a temp DB, real `runner.db` functions)
- **PART A** (supported shape, per-symbol sub-dict): `_entry_bar=42` saved → reloaded `{'_entry_bar': 42}`. ✅ round-trip works.
- **PART B** (actual `rsi_oversold_spy` shape, top-level key): tick-1 entry writes top-level `_rsi_spy_entry_bar=100` → runner saves the SPY sub-dict → reloaded `{}` (**key absent**). Tick-2 (still holding): strategy reads `_rsi_spy_entry_bar` → **MISSING → defaults to n_bars → `bars_held=0`**. **The time-stop exit can never fire in live.**

---

## Impact assessment

- **`rsi_oversold_spy` (LIVE, mid-position now):** Its **time-stop exit is dead in live** (`bars_held` stuck at 0). Its **RSI-cross exit still works** (reads live RSI, not persisted state), so the position is NOT unprotected — it will still exit when RSI > exit_rsi. But it can over-hold past the intended `time_stop_bars` if RSI lingers below the exit threshold. Severity: **moderate** — a real but partially-mitigated exit-logic defect on a live $-trading strategy.
- **`macd_momentum_iwm` (LIVE roster, 0 fills):** Its **entry** depends on `_macd_prev_macd`/`_macd_prev_signal` to detect the cross. In live those reset every tick → `prev` is always the just-written current value → **the cross is never detected → it would never enter in live.** Severity: **high if it ever trades** — but currently latent (no fills). This is the bigger landmine: it explains a strategy that may be silently no-op-ing.

## Why I did not fix it
The fix requires editing **protected files** — either `runner/runner.py` (persist top-level custom keys too) or the two `strategies/*/strategy.py` files (move the keys into `position_state[symbol]`). All four are read-only in my scope (cron explicitly: "Don't touch protected runner/backtest/GATE files"). **This is verify-and-report; the fix is a parent/Cyrus-owned change.**

## Recommended fix (for whoever owns the protected edit)
The **cleaner, lower-blast-radius** fix is in the **two strategies** (not the runner): change `position_state["_rsi_spy_entry_bar"]` → `position_state[symbol]["_rsi_spy_entry_bar"]` (and the macd pair likewise), so they write into the per-symbol sub-dict the runner already persists. This:
- requires no runner change (zero risk to the 8-strategy book),
- makes live match backtest exactly,
- is pinned by re-running `_l134_dryrun.py` PART-A-style (the per-symbol shape already passes).

Alternative (broader): make `runner/runner.py` persist top-level non-broker-truth keys too — but that changes the contract for all strategies and is higher risk. **Recommend the per-strategy fix.**

A regression guard belongs in `tests/` once the fix lands (out of my write scope): assert that after a live-style fresh-`position_state` rebuild + `get_strategy_state` layering, `bars_held` advances. `_l134_dryrun.py` is the ready-made template.

## Net
- The 2026-05-26 persistence infra itself is **sound and confirmed live** (cross-flat path working; in-position round-trip works for contract-following strategies).
- **L134's worry was justified:** verifying it surfaced **two contract-violating live strategies** whose persisted state silently dies in live (rsi time-stop dead; macd entry would never fire). Caught **before** macd traded — exactly "before it matters."
- No protected file touched. Fix recommendation handed up.
