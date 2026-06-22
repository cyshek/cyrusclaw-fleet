"""Allocator-blend (inv-vol 63d) — live-runner BASKET adapter (decide_xsec).

PAPER ONLY. No real money. This file makes the bench's first multi-sleeve
allocator trade faithfully on a PAPER Alpaca clock via runner/runner_xsec.py.

VALIDATED BLEND (report: reports/ALLOCATOR_BLEND_20260621.md)
------------------------------------------------------------
Inverse-vol (63d) risk-parity weighting of two validated sleeves:
  * TQQQ vol-target sleeve  (leveraged_long_trend voltarget, 25% ann-vol target)
  * sector-rotation top-2   (SPY/QQQ/GLD/TLT, 3-mo lookback, hold top-2)
Full-period backtest: Sharpe 1.014 / OOS 1.147 / maxDD -23.9% — beats BOTH
sleeves standalone. It is the first candidate worth a real paper clock toward
real money.

WHY A decide_xsec ADAPTER (and why it is now FAITHFUL)
-----------------------------------------------------
The blend is a continuously multi-asset-reweighted book (TQQQ + up to 2 of
SPY/QQQ/GLD/TLT, inverse-vol tilted, cash residual). It could not be wired to
the live runner faithfully until the runner gained a PARTIAL-TRIM-while-long
primitive — without it the runner could only BUY-notional or CLOSE-to-flat per
(strategy,symbol), so a reweight that *reduces* a leg would either be impossible
or oversell it. That primitive now exists in runner/runner_xsec.py (action
"trim": qty-clamped to the leg's attributed held qty, never oversells, logs a
`sell` row so db.strategy_position subtracts exactly that qty, leg stays long;
full sweep degrades to CLOSE). This adapter is the first consumer of it.

WEIGHT SOURCE — REUSED, NOT REIMPLEMENTED (no-lookahead by construction)
-----------------------------------------------------------------------
Per-underlying TARGET weights come straight from the VALIDATED tracker:
`runner.allocator_paper_tracker.compute_blend_state()`, which itself calls the
validated `_allocator_blend_tests.build_sleeves()` + `blend_portfolio()` and the
two underlying engines (run_backtest_voltarget + run_sector_rotation) over ALL
price history through the latest close. We re-implement ZERO sleeve / vol /
rotation math here. The tracker is lookahead-safe by construction (gate/vol on
data <= D; rotation ranked on prior month-end; it only ever reads the last
fully-closed bar). So the weights this adapter trades to are exactly the model's
honest "hold this today" readout — `state["target_weights"]`, e.g.
`{TQQQ: 0.13, SPY: 0.28, QQQ: 0.28}` with cash = `implied_cash_w` (here ~0.31).

WEIGHTS -> ORDERS (per leg, churn-guarded)
------------------------------------------
For each symbol in (configured basket ∪ currently-held ∪ target_weights):
    target_notional = target_w * MAX_NOTIONAL        (cash = the residual leg)
    target_qty      = floor(target_notional / last_price)
    delta           = target_qty - current_attributed_qty
    threshold       = max(1, floor(churn_frac * max(target_qty, 1)))   # ~5%
  * delta >  threshold        -> BUY  delta shares  (add)
  * delta < -threshold:
        target_qty <= 0       -> CLOSE the leg (go flat, clear leg state)
        else                  -> TRIM -delta shares (reduce, stay long)
  * |delta| <= threshold      -> HOLD (don't thrash)
TRIM carries an explicit `qty`, so the runner trims EXACTLY that many shares
(qty wins over notional in the runner's resolver) and the basket buy-clamp never
shrinks a de-risking reduction. The churn guard mirrors tqqq_cot_combo (5% of
target, min 1 share) so intramonth weight drift doesn't churn the book.

FAIL-SAFES (never panic-flatten, never wrong partial)
-----------------------------------------------------
  * engine / tracker / import error  -> return {} == WHOLE-BASKET HOLD. We never
    flatten on a compute failure; a transient Yahoo hiccup must not liquidate.
  * a leg with no visible price       -> HOLD that one leg (can't size it).
  * target weight for a symbol not in the runner's basket -> still emitted; the
    runner only acts on symbols it can price/trade, and logs the rest.
A monthly-rebalance cadence is enforced (the blend rebalances at month-open):
by default we only re-target on a month change (`monthly_cadence=True`), matching
the validated engine; intramonth ticks HOLD. Set `monthly_cadence=False` to
re-target every tick (still churn-guarded) for faster paper convergence.

LIMITATIONS (honest)
--------------------
  * Fractional shares: target_qty uses floor() of whole shares (matches
    tqqq_cot_combo + the paper account's fractional policy is broker-side). Tiny
    target weights on a high-priced leg can floor to 0 -> that leg sits flat.
  * Weekends/holidays: runner_xsec already skips when the US equity market is
    closed; on a closed day this strategy is never called. compute_blend_state
    refreshes bars first, so a stale ^GSPC cache won't desync the marks.
  * This is a TRACKING adapter: it trades the model's CURRENT target weights;
    it does not itself re-derive Sharpe. The forward honest P&L is what the
    tournament/paper clock records from the orders this emits.
  * NOT YET SCHEDULED. This file is intentionally not added to crontab /
    cron_tick.sh — wiring into the schedule is a separate, reviewed step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Action:
    action: str        # "buy" | "trim" | "hold" | "close"
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


# The blend's tradeable universe. Cash is the residual (never an order).
# TQQQ = vol-target sleeve; SPY/QQQ/GLD/TLT = the rotation sleeve's candidates
# (it holds the top-2 on any given month). Kept here so the runner basket can be
# validated/derived, but the AUTHORITATIVE per-symbol weights come from the
# tracker's decomposition at decide-time, not from this list.
ALLOCATOR_UNIVERSE: List[str] = ["TQQQ", "SPY", "QQQ", "GLD", "TLT"]


def _month_key(t_iso: str) -> str:
    """Extract 'YYYY-MM' from an ISO timestamp (empty if unparseable)."""
    return t_iso[:7] if t_iso and len(t_iso) >= 7 else ""


def _leg_price(symbols_view: dict, sym: str) -> Optional[float]:
    """Last visible price for a leg from the runner's symbols view.

    Uses `last_price` (live overlay if present, else latest bar close), as
    shaped by runner_xsec / backtest_xsec. Returns None when unpriceable ->
    caller HOLDs that leg (never sizes a leg it can't mark).
    """
    sv = symbols_view.get(sym) or {}
    px = sv.get("last_price")
    if px is None:
        bars = sv.get("bars") or []
        if bars:
            try:
                px = float(bars[-1].get("c"))
            except (TypeError, ValueError):
                px = None
    try:
        px = float(px) if px is not None else None
    except (TypeError, ValueError):
        px = None
    if px is not None and px <= 0:
        return None
    return px


def _compute_target_weights(params: dict) -> Optional[Dict[str, float]]:
    """Return the blend's CURRENT per-underlying target weights by REUSING the
    validated tracker decomposition. Returns None on ANY failure (-> whole-
    basket HOLD upstream). Re-implements no sleeve/vol/rotation math.

    `state["target_weights"]` already excludes cash (cash = implied_cash_w);
    we pass it through verbatim (e.g. {"TQQQ":0.13,"SPY":0.28,"QQQ":0.28}).
    """
    try:
        # Import lazily so a heavy/transiently-broken engine import can't wedge
        # strategy *load* (mirrors the tracker's own lazy-import discipline).
        from runner import allocator_paper_tracker as apt
        state = apt.compute_blend_state()
    except Exception:  # noqa: BLE001 - any failure -> HOLD the whole basket.
        return None
    tw = state.get("target_weights") if isinstance(state, dict) else None
    if not isinstance(tw, dict) or not tw:
        return None
    out: Dict[str, float] = {}
    for sym, w in tw.items():
        try:
            wf = float(w)
        except (TypeError, ValueError):
            continue
        if wf > 0:
            out[str(sym)] = wf
    return out or None


def decide_xsec(market_state: dict, position_state: dict, params: dict) -> dict:
    """Move the paper book toward the blend's current per-underlying target
    weights. Returns {symbol: Action}; absent symbols are implicit HOLD.

    Contract (runner_xsec): market_state has `symbols` (per-sym view with
    `last_price`/`bars`/`has_bar`), `clock_t`, `strategy_state`; position_state
    is {sym: {qty, market_value, avg_entry_price}} for HELD legs only.
    """
    actions: Dict[str, Action] = {}
    symbols_view = market_state.get("symbols") or {}

    # Persistent state for cadence tracking (runner persists this back to db).
    state = market_state.get("strategy_state")
    if not isinstance(state, dict):
        state = {}
    market_state["strategy_state"] = state

    max_notional = float(params.get("max_notional_usd", 100.0))
    churn_frac = float(params.get("churn_frac", 0.05))
    monthly_cadence = bool(params.get("monthly_cadence", True))

    # ---- Monthly cadence gate (the validated blend rebalances at month-open).
    clock_t = str(market_state.get("clock_t", ""))
    this_month = _month_key(clock_t)
    last_month = state.get("last_rebalance_month", "")
    if monthly_cadence and this_month and this_month == last_month:
        # Already rebalanced this month -> hold everything (no churn).
        return {}

    # ---- Resolve target weights (REUSED tracker decomposition). -------------
    target_w = _compute_target_weights(params)
    if target_w is None:
        # Engine/data failure -> WHOLE-BASKET HOLD. Never panic-flatten; do NOT
        # advance the cadence marker (so we retry next tick).
        return {}

    # Universe to consider = configured basket ∪ currently held ∪ targets.
    basket: List[str] = [str(s) for s in (params.get("basket") or [])]
    consider = set(basket) | set(position_state.keys()) | set(target_w.keys())

    for sym in sorted(consider):
        cur_qty = 0.0
        held = position_state.get(sym)
        if isinstance(held, dict):
            try:
                cur_qty = float(held.get("qty", 0.0) or 0.0)
            except (TypeError, ValueError):
                cur_qty = 0.0

        tgt_w = float(target_w.get(sym, 0.0) or 0.0)

        price = _leg_price(symbols_view, sym)
        if price is None:
            # Can't size this leg -> HOLD it (even if we're holding qty; we will
            # not blindly close a leg we can't price). Only log if it matters.
            if cur_qty > 0 or tgt_w > 0:
                actions[sym] = Action(
                    "hold", sym,
                    reason=f"no price -> hold leg (tgt_w={tgt_w:.4f}, "
                           f"cur_qty={cur_qty:g})")
            continue

        target_notional = tgt_w * max_notional
        target_qty = math.floor(target_notional / price) if price > 0 else 0
        threshold = max(1, math.floor(churn_frac * max(target_qty, 1)))
        delta = target_qty - cur_qty

        base_reason = (
            f"tgt_w={tgt_w:.4f} tgt_notional=${target_notional:.0f} "
            f"px=${price:.2f} tgt_qty={target_qty} cur_qty={cur_qty:g} "
            f"thresh={threshold}")

        # Target flat (or rounds to flat): close if we hold, else hold.
        if target_qty <= 0:
            if cur_qty > 0:
                actions[sym] = Action(
                    "close", sym,
                    reason=f"target_w~0 -> close to flat | {base_reason}")
            # else: not held and target flat -> nothing to emit.
            continue

        if delta > threshold:
            buy_qty = delta
            buy_notional = round(buy_qty * price, 2)
            actions[sym] = Action(
                "buy", sym, notional_usd=buy_notional, qty=float(buy_qty),
                reason=f"underweight +{buy_qty:g}sh (${buy_notional:.0f}) "
                       f"| {base_reason}")
        elif delta < -threshold:
            sell_qty = -delta
            # target_qty > 0 here (handled <=0 above) -> this is a strict TRIM,
            # not a close. Explicit qty makes the runner trim EXACTLY this many.
            trim_notional = round(sell_qty * price, 2)
            actions[sym] = Action(
                "trim", sym, notional_usd=trim_notional, qty=float(sell_qty),
                reason=f"overweight -{sell_qty:g}sh (${trim_notional:.0f}) "
                       f"| {base_reason}")
        else:
            # Within churn band -> hold (don't thrash). Only emit a hold row for
            # legs we actually hold or want (keeps the decision log meaningful).
            if cur_qty > 0 or tgt_w > 0:
                actions[sym] = Action(
                    "hold", sym,
                    reason=f"within churn band |delta|={abs(delta):g} "
                           f"<= {threshold} | {base_reason}")

    # Advance cadence marker only after a successful re-target.
    if this_month:
        state["last_rebalance_month"] = this_month
    return actions
