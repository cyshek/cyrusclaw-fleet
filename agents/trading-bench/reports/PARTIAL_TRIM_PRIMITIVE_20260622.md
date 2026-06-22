# PARTIAL-TRIM Runner Primitive — Build Report

**Date:** 2026-06-22 (UTC)
**Author:** trading-bench subagent
**BACKLOG item:** line 7 — *Build the PARTIAL-TRIM runner primitive (P1 infra)*
**File changed:** `runner/runner.py` (only)
**Status:** ✅ SHIPPED — primitive landed, full suite green (modulo 1 pre-existing unrelated fail), protected files md5-unchanged. **NOT wired to trade live** (wiring is a separate follow-up, per task).

---

## 1. The problem

`runner/runner.py` (the single-symbol live runner) supported exactly two position
primitives per `(strategy, symbol)`:

- **BUY notional=N** — add exposure (Kelly-sized).
- **CLOSE** — liquidate the FULL strategy-attributed qty to flat (+ clear strategy state).

There was **no partial-sell-while-staying-long**. A strategy that wants to *reduce*
exposure but stay long had to `HOLD` (documented limitation in
`strategies/leveraged_long_trend_paper/RUNNER_PLUMBING_GAP.md`). Consequences:

- The TQQQ vol-target sleeve runs **hotter than its backtest** on vol-spike days (the
  engine would trim; the runner couldn't, so it held the full position).
- A continuously-reweighted multi-asset book (the allocator blend: TQQQ + SPY/QQQ/GLD/TLT)
  **cannot be executed faithfully** without a trim primitive.

There was also a **latent hazard**: the action string `"sell"` was already accepted by
the runner's guard, but the submit path only branched `close` vs. `else`, so a `sell`
fell through the `else` → a **raw notional sell** (`notional_usd=N`). A notional sell is
**not clamped to attributed qty**, so it could oversell past flat (into a short / eating
another strategy's shares) and drift attribution via broker-side rounding. This change
closes that hazard too.

---

## 2. What changed (additive, in `runner/runner.py` only)

All changes live in the action-handling/submit region of `run()`. Four edits:

### (1) Trim normalization block (new), inserted after the `hold` early-return
Recognizes `action.action in ("trim", "sell")` and translates it into an **exact share
qty to sell**, then **clamps to attributed held qty**. Fail-safe ladder:

| Condition | Outcome |
|---|---|
| flat / no attributed qty | **HOLD** (no broker call), run detail `trim_no_pos` |
| sell qty unresolved (no usable `qty` and no `notional`+`price`) | **HOLD**, detail `trim_unresolved` |
| computed sell qty ≤ ~0 | **HOLD** |
| clamped sell qty ≥ full attributed qty | **degrade to CLOSE** (full liquidation + clear state) |
| otherwise | **partial trim** — stay long, `trim_qty` set |

Sell qty resolution: explicit `action.qty` (>0) wins; else `notional_usd / price`. Read
via `getattr(action, "qty", None)` so legacy actions without a `qty` attr are unaffected.

### (2) Action guard widened
`("buy", "sell", "close")` → `("buy", "sell", "close", "trim")`.

### (3) Risk routing for trims (risk.py UNCHANGED)
A trim is de-risking, so it is risk-checked with **CLOSE-semantics**:
`risk.check_trade(strategy, symbol, "close", 0.0, pos_usd, ...)`. That enforces the
**daily-trade-cap only** — never the position cap (a reduction can't breach it), and
bypasses the generic notional checks. **No edit to `risk.py`** — we call its existing
`close` branch. The no-oversell guarantee comes from the qty clamp, not from risk.py.

### (4) Trim submit branch (new), between the `close` and `else` branches
```
elif trim_qty is not None:
    order = client.submit_market_order(symbol, "sell", qty=trim_qty)  # QTY order
    effective_side = "sell"
    # notional recorded as cost-at-fill for the trade row/receipt
    # NB: db.clear_strategy_state is NOT called — the position persists.
```
The existing reconcile/log tail is shared and already qty-based, so the logged `sell`
row carries the exact sold qty.

---

## 3. Attribution-consistency argument — WHY the books stay synced

This is the crux. The claim: **a partial trim keeps `(strategy, symbol)` attribution
provably consistent, with zero new attribution code.**

`db.strategy_position(strategy, symbol)` (unchanged) reconstructs attributed qty by
walking trade rows in id order:

```python
WHERE strategy=? AND symbol=? AND status IN (open_statuses) ORDER BY id ASC
...
if side == "buy":   qty += q;  cost += notional
elif side == "sell":
    if qty > 0:
        sell_qty = min(q, qty)                 # <-- clamps oversell at the DB layer too
        cost   *= max(0.0, (qty - sell_qty)/qty)  # proportional cost-basis scaling
        qty    -= sell_qty
```

Three facts make the trim correct by construction:

1. **The trim emits exactly the row shape the reconstruction already understands.** A
   partial trim writes a single `sell` row with the precise clamped qty. The
   reconstruction subtracts `min(sell_qty, qty)` and scales cost basis — so after the
   trim, `strategy_position` returns `held − trim_qty` with proportionally-reduced cost
   basis. P&L stays honest. **No new attribution logic was added; the existing, tested
   reconstruction does all the work.**

2. **Per-(strategy,symbol) isolation.** Every relevant query
   (`strategy_position`, `get/save/clear_strategy_state`) is keyed by
   `WHERE strategy=? AND symbol=?`. A trim on symbol AAA touches only AAA rows; BBB is
   untouched. Multi-symbol-per-strategy attribution is therefore correct **by
   construction** — the single-symbol runner ticks one symbol per `run()` call, and the
   storage layer scopes everything to that `(strategy, symbol)` pair. (Pinned by the
   multi-symbol test below.)

3. **Defense in depth on oversell.** The runner clamps `sell_qty = min(req_qty, held_qty)`
   *before* submitting, so we never even place an oversell order. AND the reconstruction
   independently clamps `min(q, qty)`, so even a hypothetically-bad logged sell can never
   drive attributed qty negative. Two independent guards → no long→short flip is possible
   on this long-only paper account.

**Submit by QTY, never notional:** the trim places a `qty=` order (like `close`), not a
`notional_usd=` order. This guarantees the logged `sell` qty equals the qty the
attribution layer subtracts. A raw notional sell would round on the broker side and could
drift attribution — which is exactly the latent `"sell"` hazard this change removes.

---

## 4. Tests

New file: `tests/test_runner_trim.py` (12 tests). Written **before** the runner change;
verified they **FAIL against the unchanged runner** (9 fail / 3 pass — the 3 that passed
were the buy/close/hold regression pins, which already worked), then **PASS after** the
change (12/12). What each pins:

| Test | Pins |
|---|---|
| `TestPartialTrimDecrementsQty.test_trim_two_of_five` | hold 5, trim 2 → attributed=3, **stays long**, ONE qty-sell of 2, strategy state PRESERVED |
| `...test_trim_emits_sell_decision_with_qty` | trim logs a `sell` decision row with the correct qty |
| `TestTrimCannotOversell.test_trim_more_than_held_degrades_to_close` | trim 10 of 3 held → clamped to 3, goes flat, state CLEARED (no short) |
| `...test_trim_exact_full_qty_is_close` | trim == full qty → close to flat |
| `...test_trim_when_flat_holds` | trim with no position → **HOLD**, no broker call (fail-safe) |
| `TestTrimRiskAndCaps.test_trim_allowed_at_max_position` | trim allowed even at the $1000 position cap (de-risking) |
| `TestTrimByExplicitQty.test_trim_by_qty_field` | trim via explicit `action.qty=2.5` → attributed 6→3.5 |
| `TestSellAliasRoutesToTrim.test_sell_action_is_qty_clamped` | legacy `"sell"` routes to the qty-clamped path (NOT a raw notional sell) — the hazard fix |
| `TestMultiSymbolAttribution.test_two_symbols_independent_trim_and_close` | ONE strategy, TWO symbols: BUY/TRIM/CLOSE on each keep attribution independent + consistent |
| `TestRegressionBuyCloseUnchanged.test_buy_still_submits_notional` | **(d)** BUY still a notional order (unchanged) |
| `...test_close_still_liquidates_full_qty` | **(d)** CLOSE still sells full attributed qty + clears state (unchanged) |
| `...test_hold_still_no_trade` | **(d)** HOLD still writes no trade (unchanged) |

### Suite results

- **Trim file alone:** `12 passed`.
- **Existing runner + xsec:** `tests/test_runner.py tests/test_runner_xsec.py` → `19 passed` (no regression).
- **FULL suite (`python3 -m pytest -q`):** **`637 passed, 1 failed, 1 skipped`**.
  - The **+12** vs. the pre-change baseline of `625 passed` is exactly the 12 new trim tests.
  - The **1 failure is PRE-EXISTING and unrelated**:
    `tests/test_fx_bars_cache.py::test_live_eurusd_cache_span_matches_lane_claim` —
    a hardcoded EURUSD bar-count assertion (`expected 5843, got 5852`) that drifts as the
    FX data cache grows. It touches `data_cache/yahoo_fx`, not runner/risk/db. Documented
    in the baseline; **not touched by this work**.
  - (Note: `MEMORY.md`'s "586/586" is stale — the suite has since grown to 625 pre-change.)

---

## 5. MD5 verification

| File | BEFORE | AFTER | Expected | Result |
|---|---|---|---|---|
| `runner/runner.py` | `52ef6be2cc8cf72c02d30334f761bc88` | `3811c37be962ea818e9958da675b1a03` | CHANGED | ✅ |
| `runner/risk.py` | `e4c227e019c99e7e52224eb2f91389b8` | `e4c227e019c99e7e52224eb2f91389b8` | UNCHANGED | ✅ |
| `runner/backtest.py` | `ac0c579f8a20d11724879278a610fbb4` | `ac0c579f8a20d11724879278a610fbb4` | UNCHANGED | ✅ |
| `runner/backtest_xsec.py` | `2278a4c8d8a66703da5cd6f2a0880061` | `2278a4c8d8a66703da5cd6f2a0880061` | UNCHANGED | ✅ |

Backtest engines are byte-identical → no risk of the backtest/live divergence the md5
check guards against. risk.py byte-identical → the trim reuses the existing `close`
risk branch rather than introducing a new risk surface.

---

## 6. Hard rails — verified intact

- **PAPER ONLY:** `runner/broker_alpaca.py` is **untouched** (never edited). The non-paper-URL
  refusal (`PAPER_HOST_FRAGMENT` guard: "Refusing to use non-paper trade base… paper-only")
  still fires.
- **Killswitch:** `STOP_TRADING` check at the top of `run()` is unchanged.
- **MAX_NOTIONAL never exceeded:** a trim REDUCES exposure and submits by clamped qty, not
  notional — it cannot add exposure or breach MAX_NOTIONAL.
- **Never flip long→short:** `sell_qty = min(req_qty, held_qty)` (runner) + `min(q, qty)`
  (DB reconstruction) — two independent clamps to flat. Long-only invariant preserved.
- **No lookahead:** the trim uses only `position_state` (from the trade log) and the same
  `price`/`bars` already fed to `decide()`. No new data source, no future bar.
- **FAIL SAFE:** ambiguous/unresolvable trim → HOLD; full-sweep trim → CLOSE. Never a wrong
  partial that desyncs the books.

---

## 7. Honest limitations / residual risk

1. **Fractional-share / qty rounding at the broker.** The trim submits a float qty
   (e.g. 2.5 sh). Alpaca supports fractional qty for equities, and the reconcile loop
   overwrites the logged qty with the broker's `filled_qty`, so the attribution row
   reflects the ACTUAL fill — books stay synced even if the broker rounds. For a
   non-fractionable symbol the broker would reject/round; the reconcile picks up the true
   filled qty, so attribution remains correct (it logs what actually transacted). Not a
   desync risk; worst case a trim fills slightly smaller than requested.
2. **Price source for notional→qty conversion.** When a trim is expressed as a notional,
   we convert via the latest price (`market_state["last_price"]`). If price is `None`
   (rare fetch failure) and no explicit `qty` is given, we **fail safe to HOLD** rather
   than guess. A strategy that wants deterministic trims should pass `action.qty`.
3. **The xsec runner (`runner/runner_xsec.py`) still has the OLD notional-sell behavior**
   for basket `sell` legs (it was out of scope — single-symbol `runner.py` only, and
   md5 of backtest_xsec.py had to stay frozen; runner_xsec.py was not in the md5 set but
   I left it untouched to keep blast radius minimal). That path can still oversell a basket
   leg on a `sell`. **Recommendation:** port this same qty-clamp into `runner_xsec.py`'s
   "pass 2: buys/sells" loop as a fast follow-up before any xsec strategy is allowed to
   emit `sell` (today they emit buy/close only, so it's latent, not live). Logged in
   memory as a follow-up.
4. **Allocator is NOT wired to trade live.** Per the task, this lands the PRIMITIVE only.
   Wiring the continuously-rebalanced allocator to emit trims live is a separate,
   explicitly-gated follow-up.

---

## 8. Confidence

**High** that the trim primitive is attribution-correct and safe for the single-symbol
runner. The reason for the confidence is structural, not just empirical: the trim adds
**no new attribution code** — it emits the exact `sell`-row shape the existing, tested
`db.strategy_position` reconstruction already subtracts correctly, with two independent
oversell clamps (runner + DB) and a fail-safe-to-HOLD/CLOSE ladder. The md5 freeze proves
the backtest engines and risk caps are untouched. The one honest caveat worth flagging
loudly is **#3 (the xsec runner's notional-sell path is unchanged)** — it's latent today
but should be closed before any basket strategy emits `sell`.
