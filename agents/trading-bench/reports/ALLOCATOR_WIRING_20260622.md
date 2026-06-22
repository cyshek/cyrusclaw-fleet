# Allocator Wiring — Partial-Trim Basket Runner + Live Allocator Strategy

**Date:** 2026-06-22
**Author:** trading-bench (subagent)
**Status:** ✅ Both steps landed, full suite green, protected engines md5-verified unchanged.
**Scope:** PAPER ONLY. Nothing wired to the live schedule yet (strategy file landed; scheduling is a separate reviewed step).

---

## TL;DR

Two sequential deliverables to let the validated **allocator blend** trade *faithfully* on a paper clock:

1. **STEP 1 — Partial-trim leg in the BASKET runner** (`runner/runner_xsec.py`, the only engine file changed). Mirrors the single-symbol primitive already landed in `runner.py`. Adds `action="trim"` (and makes the legacy `"sell"` SAFE): resolve an exact share qty, **clamp to the leg's attributed held qty** (never oversell → never flip a leg short), submit a **QTY** order, log a `sell` row so `db.strategy_position` subtracts exactly that qty, and **do not clear leg state** (the leg stays long). A full sweep degrades to the existing CLOSE path.
2. **STEP 2 — Live allocator strategy** (`strategies/allocator_blend/strategy.py`). Exports `decide_xsec()` that **reuses the validated tracker's weight decomposition** (`runner.allocator_paper_tracker.compute_blend_state()`) and maps per-underlying target weights → per-leg buy/trim/hold/close with a 5% churn guard and full fail-safe ladder. Zero sleeve/vol/rotation math re-implemented.

**Full suite: 663 passed / 1 pre-existing unrelated FX-cache failure / 1 skipped.** (Baseline 637 + 14 new trim tests + 12 new allocator tests = 663.)

---

## STEP 1 — Partial-trim leg in `runner_xsec.py`

### The problem it fixes

Before this change the basket runner could only:
- **pass 1:** CLOSE a leg to flat (full attributed `held_qty`), or
- **pass 2:** BUY notional / **SELL notional** per leg.

The `sell`-by-notional path was a **latent oversell bug**: nothing clamped the requested notional to the leg's attributed qty, so a `sell` larger than the held leg would oversell it (and could flip the strategy's attributed position short relative to `db.strategy_position`). It was latent only because no live basket strategy emits `sell` today (they emit buy/close). A continuously-reweighted allocator book *must* be able to **reduce a leg while staying long** — which neither path supported.

### What landed (the design, mirrored from `runner.py`)

A new helper `_resolve_trim_sell_qty(action, held_qty, price)` and a dedicated trim branch in pass-2:

```
held_qty (attributed, from db.strategy_position via _build_leg_position)
      │
_resolve_trim_sell_qty:
  held_qty <= eps ............................ ("hold", None)   → fail-safe HOLD, no broker call
  qty from action.qty, else notional/price
  req_qty unresolved / <= eps ................ ("hold", None)   → fail-safe HOLD
  sell_qty = min(req_qty, held_qty)                              ← HARD no-oversell clamp
  sell_qty >= held_qty - eps ................. ("close", None)  → degrade to full CLOSE
  else ....................................... ("trim", sell_qty) → strict partial, stay long
```

In the runner pass-2:
- `act in ("trim", "sell")` → routed to the **same** qty-clamped path (so a bare legacy `sell` can never reach the notional-submit branch again — the latent bug is structurally fixed).
- **HOLD** result → log a `hold` decision row, no broker call.
- **CLOSE** result → submit `sell` by full `held_qty`, `_record_fill(... "sell" ...)`, `db.clear_strategy_state`, print a CLOSE receipt.
- **TRIM** result → submit `sell` by **clamped `sell_qty`**, `_record_fill(... "sell", qty_hint=sell_qty ...)` so the logged `sell` row carries the exact qty, **do not clear state**, print a TRIM receipt.
- Risk is consulted with **close-semantics** for trims/sells (`risk.check_trade(..., "close", 0.0, pos_usd, ...)`) — a de-risking reduction is governed by the daily-trade cap only and can never be blocked by (or breach) the position cap. `risk.py` is untouched.
- The **BUY** branch is byte-for-byte the prior behavior (basket-clamped notional submit).

### Attribution-consistency argument (why this is STRUCTURALLY safe, not just empirically passing)

The failure mode this guards against is desyncing per-leg attribution so the tournament P&L lies. Three **independent** structural guards make a trim correct by construction:

1. **No new attribution code.** A trim logs the exact same `sell`-row shape that `db.strategy_position` already consumes to reconstruct per-(strategy,symbol) qty. The attribution layer is the *tested, unchanged* `db.strategy_position` reconstruction — the same one used by every existing buy/close. We added zero parallel bookkeeping.
2. **Two independent clamp-to-held guards.** (a) `_resolve_trim_sell_qty` clamps `sell_qty = min(req_qty, held_qty)` before submission; (b) `db.strategy_position`'s own reconstruction applies `min(sell_qty, running)` when it folds the `sell` row back in. Either alone prevents a leg going negative; both together make a long→short flip impossible even if one were wrong.
3. **`_clamp_basket` is md5-frozen AND ignores trims.** It scales only `act in ("buy","sell")` notionals against `MAX_POSITION` headroom. Trims use `action="trim"`, which `_clamp_basket` does not count — so a de-risking reduction is **never shrunk** by the basket buy-clamp, and trims never consume cap headroom. (The legacy `sell` alias *is* still seen by `_clamp_basket` for headroom accounting, which is conservative — it can only clamp *other* buys *more*, never less; and the alias itself is routed to the safe qty-clamped trim path for execution. The clean contract is: strategies emit `trim` for reductions.)

Net: a trim can only ever **reduce** a leg by an exact, held-bounded share count, recorded in the one row shape the attribution layer already subtracts. Full-sweep degrades to the existing, already-trusted CLOSE mechanics.

### Pinning tests (written FIRST, red→green)

`tests/test_runner_xsec_trim.py` — **14 tests, 7 classes**. Confirmed **RED** against the unchanged runner (10 failed / 4 passed — the 4 passing are exactly the regression pins that already held), then **GREEN** after the change:

- `TestPartialTrimDecrementsLeg` — partial trim decrements that leg's attributed qty, stays long, persistent state preserved (req **a**).
- `TestTrimCannotOversellLeg` — exact-full-qty → close; more-than-held → degrades to close; flat leg → holds (req **b**).
- `TestSellAliasIsClamped` — legacy `sell` is routed through the qty-clamped path; oversize `sell` clamps to flat (latent-bug fix).
- `TestTrimByExplicitQty` — `action.qty` resolves the trim exactly.
- `TestTrimAtMaxNotional` — trim allowed even on a max-sized leg (de-risk, never cap-blocked).
- `TestMultiLegAttribution` — **BUY two legs, TRIM one, CLOSE the other → per-leg attribution independent & correct** (the core basket test, req **c**).
- `TestRegressionBuyCloseHoldUnchanged` — existing basket BUY / full-CLOSE / HOLD / empty-actions behavior **UNCHANGED** (req **d**).

---

## STEP 2 — Live allocator strategy (`strategies/allocator_blend/`)

### How it maps weights → orders

`decide_xsec(market_state, position_state, params)`:

1. **Cadence gate** (`monthly_cadence=True` default): the validated blend rebalances at month-open. On an already-rebalanced month → return `{}` (hold all, no churn). The cadence marker (`last_rebalance_month`) is persisted by the runner via `strategy_state`.
2. **Resolve target weights** by calling `runner.allocator_paper_tracker.compute_blend_state()` and reading `state["target_weights"]` — e.g. live 2026-06-18: `{TQQQ: 0.1319, SPY: 0.279, QQQ: 0.279}`, cash 0.31. **No sleeve/vol/rotation math is re-implemented here** — the tracker calls the validated `build_sleeves()` / `blend_portfolio()` / engines, which are lookahead-safe by construction (gate/vol on data ≤ D, rotation ranked on prior month-end, only ever reads the last fully-closed bar).
3. **Per leg** (over `basket ∪ held ∪ targets`):
   ```
   target_notional = target_w * MAX_NOTIONAL
   target_qty      = floor(target_notional / last_price)
   delta           = target_qty - cur_attributed_qty
   threshold       = max(1, floor(churn_frac * max(target_qty, 1)))   # 5%
   delta >  threshold              → BUY  delta sh
   delta < -threshold, target>0    → TRIM -delta sh (explicit qty; stays long)
   delta < -threshold, target<=0   → CLOSE (full exit)
   |delta| <= threshold            → HOLD
   ```
   TRIM carries an explicit `qty`, so the runner's resolver trims **exactly** that many shares (qty wins over notional) and the basket buy-clamp can't shrink the reduction.

### Churn guard

Mirrors `tqqq_cot_combo`: `threshold = max(1, floor(0.05 * target_qty))`. Intramonth weight drift inside the band → HOLD, so the book doesn't thrash on noise. Configurable via `churn_frac`.

### Fail-safes (never panic-flatten, never a wrong partial)

- **Engine / tracker / import error** → `_compute_target_weights` returns `None` → `decide_xsec` returns `{}` = **whole-basket HOLD**, and does **not** advance the cadence marker (retries next tick). A transient Yahoo hiccup never liquidates the book.
- **A leg with no visible price** → **HOLD that one leg** (we never size — or blindly close — a leg we can't mark).
- **Target rounds to flat** on a held leg → CLOSE; on an unheld leg → emit nothing.
- All emitted `qty` are strictly positive; trim qty ≤ held qty (strategy-side, on top of the runner's clamp).

### Smoke / unit test

`tests/test_allocator_blend_strategy.py` — **12 tests, 7 classes**, all green:
- Deterministic (compute_blend_state monkeypatched, **no network**): cold-start buys at correct floor-qty; overweight leg → TRIM with exact qty; zero-target held leg → CLOSE; within-band → HOLD; engine-failure → whole-basket HOLD; missing-price → hold that leg; no negative/short qty ever; monthly cadence (same-month 2nd call → `{}`; cadence-off → acts every tick).
- **LIVE integration smoke** against the real validated tracker (gated to `pytest.skip` if engine/network unavailable) — verified it yields a sane, well-formed action dict (≥1 buy) from a flat book at the real current target weights.

---

## md5 verification (protected files)

| File | Status | md5 |
|---|---|---|
| `runner/runner_xsec.py` | **CHANGED** (expected) | `76251ca9ea48c0971d5ef52ac13fa08d` |
| `runner/runner.py` | UNCHANGED | `3811c37be962ea818e9958da675b1a03` |
| `runner/risk.py` | UNCHANGED | `e4c227e019c99e7e52224eb2f91389b8` |
| `runner/backtest.py` | UNCHANGED | `ac0c579f8a20d11724879278a610fbb4` |
| `runner/backtest_xsec.py` | UNCHANGED | `2278a4c8d8a66703da5cd6f2a0880061` |
| `runner/broker_alpaca.py` | UNCHANGED | `2d82c8106496e7c80636684d2299cc89` |

Verified via `md5sum -c` AND byte-diff against saved originals. **Only `runner_xsec.py` changed.** Paper-vs-real guard / non-paper-URL refusal / `STOP_TRADING` killswitch all untouched.

---

## Limitations (honest)

- **Fractional shares.** `target_qty = floor(notional / price)` uses whole shares (matches `tqqq_cot_combo`; fractional policy is broker-side). A small target weight on a high-priced leg can floor to 0 → that leg sits flat. (At the configured $100 notional, TQQQ's 0.13 weight = $13 → 0 shares at an $80 price; this is *correct* behavior at small notional and resolves as MAX_NOTIONAL scales up. The paper account should run a notional large enough that the smallest target leg floors to ≥1 share if exact tracking matters.)
- **Weekend/holiday.** `runner_xsec` already skips when the US equity market is closed, so `decide_xsec` is never called on a closed day. `compute_blend_state` refreshes bars first so a lagging `^GSPC` cache won't desync the marks.
- **Tracking adapter, not a re-derivation.** It trades the model's *current* target weights; the forward honest P&L is whatever the orders it emits realize. The full-backtest Sharpe lives in `reports/ALLOCATOR_BLEND_20260621.md`.
- **NOT YET SCHEDULED.** Intentionally not added to `crontab` / `cron_tick.sh`. Wiring into the schedule (and choosing the live paper notional) is a separate step pending parent review.
- **Legacy `sell` + `_clamp_basket` headroom.** A legacy `sell` alias is still counted by the frozen `_clamp_basket` for headroom accounting (conservative — only clamps other buys more). Strategies should emit `trim` (not `sell`) for reductions; the allocator does.

---

## Confidence

- **STEP 1 (partial-trim basket runner): HIGH.** Safety is structural (reuse of the tested `db.strategy_position` reconstruction, two independent clamp-to-held guards, md5-frozen `_clamp_basket` that ignores trims), not merely empirical. Mirrors a design already landed and tested in `runner.py`. 14 pinning tests red→green; protected engines byte-identical; full suite green.
- **STEP 2 (allocator strategy): HIGH on correctness of the mapping + fail-safes; MEDIUM on live fidelity until it actually runs a paper clock.** The weight source is the validated, lookahead-safe tracker (zero re-implementation). The weights→orders mapping, churn guard, and fail-safes are unit-proven and live-smoked. The remaining unknown is purely operational: real forward fills/slippage on the paper account once scheduled — which is exactly what the (separate, reviewed) scheduling step will start measuring.
