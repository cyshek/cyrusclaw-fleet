# Post-Market Bug Review — 2 bugs (2026-06-25)

**Triage source:** main's post-market review (cron-routed). Both bugs fixed/diagnosed; paper-only, no real money touched, killswitch untouched.

---

## BUG 1 — runner.py dust-qty guard (FIXED, tests green)

**Symptom:** `breakout_xlk__mut_c382b1` fired 4× HTTP 422 (`qty must be > 1e-9`) daily before the dust-correction job cleared the residual.

**Root cause:** `runner.py` had a `_QTY_EPS (1e-9)` dust guard on the **close** path (full-liquidation) but **not** on the **trim/partial-sell** path. A residual ~1e-9 attributed qty routed through the trim submit (`submit_market_order(sell, qty=trim_qty)`) and Alpaca rejected it with 422. The `sell` action alias also routes through this same trim path, so a dust `sell` hit the broker.

**Fix (additive, low blast radius):** added a final dust guard at the top of the `elif trim_qty is not None:` branch (runner.py ~L483), mirroring the proven close-path dust handling:

```python
if trim_qty is None or trim_qty <= _QTY_EPS:
    db.log_decision(strategy_name, "hold", symbol=action.symbol,
                    reason=f"trim dust qty {float(trim_qty or 0.0):.2e} <= eps; skip submit")
    db.log_run(strategy_name, "ok",
               int((time.monotonic() - t0) * 1000), detail="dust-trim")
    return 0
```

Any sub-threshold trim qty → no-op HOLD (logged `detail="dust-trim"`), never a broker submit. The dust-correction job still zeroes the residual.

**Note on reachability:** the front-door qty resolver provably cannot emit `trim_qty <= 1e-9` (`min(req_qty, held_qty)` with both `> 1e-9` is `> 1e-9`; sub-eps `req_qty` already returns HOLD upstream), so this guard is **defense-in-depth** against a float-edge / attribution-race residual (the live `breakout_xlk` case) and any future code path. Belt-and-suspenders, exactly as requested.

**Pinning tests (2 new, `tests/test_runner_trim.py::TestDustQtyGuard`):**
- `test_legit_tiny_trim_above_eps_still_submits` — a 2e-9 qty (above threshold) **still submits** → guard does not over-fire on legit small trims.
- `test_dust_sell_qty_never_reaches_broker` — a 1e-9 (==eps) sell qty **never reaches the broker** (fake client raises a 422-equivalent if it does); attribution + strategy state preserved.

**Verification:** `tests/test_runner_trim.py` → **14 passed** (12 original + 2 new). Full suite → **723 passed, 1 skipped** (was 721; nothing regressed).

---

## BUG 2 — tqqq_cot_combo exit logic (DIAGNOSED: working as designed — KEEP)

**Symptom:** 10 buys since 2026-06-15 (incl. 4 today), **0 sells**, unrealized −$43.05.

**Verdict: (b) WORKING AS DESIGNED.** Full audit: `reports/TQQQ_COT_COMBO_EXIT_AUDIT_20260625.md` (opus, READ-ONLY — no files/trades/params/cron touched).

`tqqq_cot_combo` is a **vol-target + SMA-200-gated accumulator** (targets a weight, lets the runner rebalance), **not** a discrete buy/sell-signal trader. The 10-buys/0-sells streak is **one position ramping from $0 to full target weight**, chopped into small fills by the 4-trades/day risk cap. Logs show it has now **converged** (`hold |delta|<=1`).

**Exit logic is present, correctly wired, and PROVEN REACHABLE** (3 paths, all verified by direct `decide()` simulation):
- **A — SMA-200 gate OFF:** `if not gate_up and current_qty>0: return Action("close")` when QQQ closes below its 200-day SMA → runner submits a real full-qty sell.
- **B — vol-target downside trim:** `if delta < -threshold: return Action("sell", -delta sh)` when realized vol rises or COT halves the weight.
- **C — target collapses to 0:** full close.

Runner fetches **real QQQ closes** from Alpaca (not the TQQQ proxy); strategy's logged SMA200=630.86 matches independent calc 630.84.

**Why no sells:** the SMA-200 risk-gate has been **ON the entire window** — QQQ is **+12.65% above** its 200-day SMA (710.62 vs 630.84). It needs a **−11.2% QQQ drop** to flip the gate OFF and liquidate to cash. That's the *only* reason there have been no sells; the regime is firmly risk-ON. The −$43 is ordinary **mark-to-market** drawdown on a fully-deployed 3× ETF — **not a stuck exit**, and not degenerate (`w_max=1.0` caps deployment; the SMA-gate is the stop).

**Independent DB confirmation (tournament.db, this session, not just the subagent):**
- 10 buys / 0 sells; net **12.7072 TQQQ @ $78.69 avg**, cost ≈ $999.90, realized $0.00.

**Live actionable note (not a bug):** notional was cut **$1000 → $160** at 2026-06-24T16:05 (ERC capital reweighting). At $160 notional target_qty is now **~2 shares vs 12.7 held**, so the **next unthrottled tick will emit a ~10-share SELL** to rebalance down — an exit is **imminent by design**, not theoretical. No manual close needed; the strategy will self-correct to the new target on the next tick.

**Action taken:** none required (KEEP). Did **not** disable the strategy, did **not** manually close the position — the exit machinery is healthy and a rebalance-down sell is already queued by the notional change.

---

## Net

- BUG 1: code fix + 2 pinning tests, full suite green.
- BUG 2: clean bill of health on the exit logic; the −$43 is MTM noise, and the strategy is already set up to trim back to the new $160 target on its next tick.
