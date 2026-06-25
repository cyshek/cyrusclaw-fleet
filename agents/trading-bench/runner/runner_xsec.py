"""Cross-sectional (basket) live runner. Sister of `runner/runner.py`.

Single-symbol strategies that export `decide()` use `runner/runner.py`.
Cross-sectional strategies that export `decide_xsec()` use this module.
The two runners never share execution paths — keep behavior of the
single-symbol runner byte-for-byte identical when editing this file.

Pipeline (per tick):
    1. Killswitch check (STOP_TRADING file in workspace root).
    2. Load xsec strategy via `runner.backtest_xsec.load_xsec_strategy`.
    3. Skip when US equity market closed (xsec basket is stocks/ETFs).
    4. Optional Tier-2 regime gate consult (mirror runner.run shape).
    5. Per leg: rebuild position_state from db.strategy_position.
    6. Per leg: fetch live bars + latest price via AlpacaClient.
    7. Build market_state {timeframe, clock_t, symbols, regime,
       strategy_state}, where clock_t = max last-bar timestamp.
    8. Call decide_xsec(market_state, position_state, params) -> dict.
    9. Apply `_clamp_basket(...)` against current live position USD.
   10. Per leg: risk-check via risk.check_trade with basket-aware
       trades-per-day cap; submit orders; log decision/trade rows.
   11. Persist cross-flat strategy_state via db.save_persistent_state.

Idempotency: monthly-rebalance strategies will return `{}` on most
ticks — runner happily logs the empty result as "no_actions" and
returns 0. Two ticks in a row on the same day produce two run rows,
zero trades.

CLI:
    python3 -m runner.runner_xsec --strategy xsec_momentum_xa_38d2b2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import db, risk
from . import bear_flatten_gate


class _XsecAction:
    """Lightweight synthetic action for the L165 bear-flatten override.

    The xsec runner reads actions via getattr(a, "action"/"symbol"/"reason"),
    so a plain attribute holder is sufficient; it never needs the full
    strategy Action dataclass. notional_usd/qty default to a close (ignored
    on the close pass, which sells the whole held qty)."""

    __slots__ = ("action", "symbol", "notional_usd", "qty", "reason")

    def __init__(self, action: str, symbol: str, *, reason: str = "",
                 notional_usd: float = 0.0, qty: Optional[float] = None):
        self.action = action
        self.symbol = symbol
        self.reason = reason
        self.notional_usd = notional_usd
        self.qty = qty
from .backtest_xsec import _clamp_basket, _PosBook, load_xsec_strategy
from .broker_alpaca import AlpacaClient, AlpacaError
from .market_hours import is_us_equity_market_open


WORKSPACE = Path(__file__).resolve().parent.parent
KILLSWITCH = WORKSPACE / "STOP_TRADING"


def killswitch_active() -> bool:
    return KILLSWITCH.exists()


def _build_leg_position(strategy_name: str, symbol: str) -> dict:
    """Return {} if flat, else {'qty', 'market_value', 'avg_entry_price'}.

    market_value uses last fill price; runner overlays live price after.
    """
    sp = db.strategy_position(strategy_name, symbol)
    if sp["qty"] <= 0:
        return {}
    avg = (sp["cost_basis_usd"] / sp["qty"]) if sp["qty"] > 0 else 0.0
    return {
        "qty": sp["qty"],
        "market_value": sp["qty"] * (sp["last_price"] or avg),
        "avg_entry_price": avg,
    }


def _fetch_leg_bars(client: AlpacaClient, symbol: str,
                    timeframe: str, limit: int) -> List[dict]:
    try:
        return client.stock_bars(symbol, timeframe=timeframe, limit=limit) or []
    except AlpacaError:
        return []


def _fetch_leg_price(client: AlpacaClient, symbol: str) -> Optional[float]:
    try:
        return client.latest_stock_price(symbol)
    except AlpacaError:
        return None


def _fetch_regime(client: AlpacaClient) -> Optional[dict]:
    """Best-effort SPY 1Day injection for regime-aware strategies.

    limit raised 100->260 so the L165 bear-flatten gate can compute SPY
    SMA-200/201 (needs >=201 closes). Strategies reading spy_closes for a
    shorter lookback slice the tail and are unaffected."""
    try:
        spy_bars = client.stock_bars("SPY", timeframe="1Day", limit=260)
        spy_closes = [float(b["c"]) for b in (spy_bars or [])]
        if spy_closes:
            return {"spy_closes": spy_closes, "spy_last": spy_closes[-1]}
    except AlpacaError:
        pass
    return None


def _build_position_state_view(books: Dict[str, dict],
                               live_price_by_sym: Dict[str, Optional[float]]
                               ) -> Dict[str, dict]:
    """position_state visible to decide_xsec: only held symbols.

    Mirrors `backtest_xsec` shape — overlays live price into
    market_value when available, otherwise falls back to avg entry.
    """
    out: Dict[str, dict] = {}
    for sym, book in books.items():
        if not book or float(book.get("qty", 0.0)) <= 0:
            continue
        px = live_price_by_sym.get(sym) or book.get("avg_entry_price", 0.0)
        out[sym] = {
            "qty": float(book["qty"]),
            "market_value": float(book["qty"]) * float(px or 0.0),
            "avg_entry_price": float(book.get("avg_entry_price", 0.0)),
        }
    return out


def _books_for_clamp(books: Dict[str, dict]) -> Dict[str, _PosBook]:
    """Convert leg-position dicts into _PosBook structs that
    `_clamp_basket` understands (it reads `.qty` and `.avg_entry_price`)."""
    out: Dict[str, _PosBook] = {}
    for sym, b in books.items():
        if not b:
            out[sym] = _PosBook()
        else:
            out[sym] = _PosBook(
                qty=float(b.get("qty", 0.0)),
                avg_entry_price=float(b.get("avg_entry_price", 0.0)),
            )
    return out


_QTY_EPS = 1e-9


def _resolve_trim_sell_qty(action, held_qty: float,
                           price: Optional[float]) -> tuple:
    """Resolve a partial-trim (or legacy `sell`) leg into an exact, held-
    clamped share qty. Mirrors the single-symbol runner.py trim normalizer
    so the two runners stay behaviorally identical.

    Inputs:
      action   : the strategy Action for this leg (reads .qty / .notional_usd).
      held_qty : the leg's CURRENT strategy-attributed qty (from
                 db.strategy_position via _build_leg_position) -- the hard
                 clamp ceiling. NEVER oversell past this.
      price    : last visible price for this leg, used to derive qty from a
                 notional request when no explicit .qty is given.

    Returns one of:
      ("hold",  None)      : nothing attributed, or qty unresolvable, or <=0
                             -> fail safe to HOLD (no broker call).
      ("close", None)      : the requested sell sweeps >= the whole leg
                             -> degrade to a full CLOSE (go cleanly flat +
                             clear leg state) rather than leave dust.
      ("trim",  sell_qty)  : a strict partial reduction; stay long. sell_qty
                             is clamped to (held_qty - eps).

    IMPORTANT: qty is resolved from the action's ORIGINAL notional, NOT the
    basket-clamped notional. A trim/sell is de-risking; the basket clamp
    (which only scales fresh buys up to MAX_POSITION) must not shrink a
    reduction. The clamp-to-held below is the hard no-oversell rail; it is
    independent of, and in addition to, db.strategy_position's own
    min(sell_qty, running) clamp during reconstruction (two guards).
    """
    if held_qty <= _QTY_EPS:
        return ("hold", None)
    req_qty = None
    a_qty = getattr(action, "qty", None)
    if a_qty is not None:
        try:
            a_qty = float(a_qty)
            if a_qty > 0:
                req_qty = a_qty
        except (TypeError, ValueError):
            req_qty = None
    if req_qty is None:
        try:
            req_notional = float(getattr(action, "notional_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            req_notional = 0.0
        if req_notional > 0 and price and float(price) > 0:
            req_qty = req_notional / float(price)
    if req_qty is None or req_qty <= _QTY_EPS:
        return ("hold", None)
    sell_qty = min(req_qty, held_qty)
    if sell_qty >= held_qty - _QTY_EPS:
        # Sweeps the whole leg -> treat as a CLOSE (clean flat + clear state).
        return ("close", None)
    return ("trim", sell_qty)


def run(strategy_name: str) -> int:
    """Returns process exit code (0 = ok, 1 = error)."""
    db.init_db()
    t0 = time.monotonic()

    # 1. Killswitch
    if killswitch_active():
        db.log_decision(strategy_name, "skip_killswitch",
                        reason="STOP_TRADING present")
        db.log_run(strategy_name, "killswitch",
                   int((time.monotonic() - t0) * 1000),
                   detail="no-op")
        return 0

    try:
        decide_xsec_fn, params = load_xsec_strategy(strategy_name)
        client = AlpacaClient()
        basket: List[str] = list(params.get("basket") or [])
        if not basket:
            db.log_decision(strategy_name, "error",
                            reason="params.basket missing or empty")
            db.log_run(strategy_name, "error",
                       int((time.monotonic() - t0) * 1000),
                       detail="no basket")
            return 1

        # xsec basket is all equities/ETFs — no crypto path.
        if not is_us_equity_market_open():
            db.log_decision(strategy_name, "skip_market_closed",
                            reason="US equity market closed (regular session only)")
            db.log_run(strategy_name, "ok",
                       int((time.monotonic() - t0) * 1000),
                       detail="skip_market_closed")
            return 0

        # ---- Tier-2 regime gate (opt-in) — same shape as runner.run() ----
        regime_gate_on = bool(params.get("regime_gate", False))
        if regime_gate_on:
            try:
                from . import regime_classifier as _rc  # noqa: WPS433
                regime_decision = _rc.get_today_regime()
            except Exception as _rg_err:  # noqa: BLE001
                db.log_decision(strategy_name, "hold",
                                reason=f"regime_gate_consult_failed: {_rg_err}",
                                detail="non-fatal")
                regime_decision = None
            if regime_decision is None:
                db.log_decision(strategy_name, "skip_regime_unknown",
                                reason="no regime decision available (cron missed or stale)")
                db.log_run(strategy_name, "ok",
                           int((time.monotonic() - t0) * 1000),
                           detail="skip_regime_unknown")
                return 0
            allow = regime_decision.get("allow_strategies") or []
            if strategy_name not in allow:
                db.log_decision(
                    strategy_name, "skip_regime_block",
                    reason=(f"regime={regime_decision.get('regime')} "
                            f"blocks strategy; "
                            f"source={regime_decision.get('source')}"
                            + ("; stale" if regime_decision.get("is_stale") else "")),
                )
                db.log_run(strategy_name, "ok",
                           int((time.monotonic() - t0) * 1000),
                           detail="skip_regime_block")
                return 0

        timeframe = str(params.get("timeframe", "1Day"))
        bar_limit = int(params.get("bar_limit", 300))

        # ---- Per-leg market + position state ----
        books: Dict[str, dict] = {}
        bars_by_sym: Dict[str, List[dict]] = {}
        live_price_by_sym: Dict[str, Optional[float]] = {}
        last_bar_t_by_sym: Dict[str, Optional[str]] = {}
        for sym in basket:
            books[sym] = _build_leg_position(strategy_name, sym)
            bars = _fetch_leg_bars(client, sym, timeframe, bar_limit)
            bars_by_sym[sym] = bars
            live_price_by_sym[sym] = _fetch_leg_price(client, sym)
            last_bar_t_by_sym[sym] = (str(bars[-1].get("t"))
                                      if bars and bars[-1].get("t") else None)

        # clock_t = max last-bar timestamp (the most recent shared moment).
        valid_ts = [t for t in last_bar_t_by_sym.values() if t]
        clock_t = max(valid_ts) if valid_ts else ""

        # symbols view shaped exactly as backtest_xsec emits it.
        symbols_view: Dict[str, dict] = {}
        for sym in basket:
            bars = bars_by_sym[sym]
            last_t = last_bar_t_by_sym[sym]
            cur_close = float(bars[-1]["c"]) if bars else None
            symbols_view[sym] = {
                "bars": bars,
                # last_price: live overlay if we have it, else bar close.
                "last_price": (live_price_by_sym[sym]
                               if live_price_by_sym[sym] is not None
                               else cur_close),
                # has_bar: True iff this symbol printed AT clock_t (the
                # most recent moment). In live mode all legs that returned
                # any bars typically share the same most-recent timestamp
                # for a 1Day basket; legs that didn't print today get False.
                "has_bar": bool(last_t and last_t == clock_t),
            }

        regime = _fetch_regime(client)
        persistent_state = db.get_persistent_state(strategy_name, "_xsec_")
        market_state = {
            "timeframe": timeframe,
            "clock_t": clock_t,
            "symbols": symbols_view,
            "regime": regime,
            "strategy_state": persistent_state,
        }
        position_state = _build_position_state_view(books, live_price_by_sym)

        # -------- L165 bear-flatten regime gate (opt-in; SPY-200d + hysteresis) --
        # When params["bear_flatten_gate"] is true (allocator_blend secondary),
        # consult the deterministic SPY-SMA-200 overlay BEFORE decide_xsec. If
        # latched bear (SPY < SMA200, held until SPY >= SMA201), OVERRIDE the
        # basket to close every currently-held leg and skip decide_xsec
        # entirely this tick. The hysteresis latch lives in
        # strategy_state[_bear_flatten] (cross-flat persistent state, persisted
        # right below). Fail-open: any error / short SPY history defers to the
        # strategy's own logic.
        bear_gate_fired = False
        if bool(params.get("bear_flatten_gate", False)):
            try:
                _spy_cl = bear_flatten_gate.spy_closes_from_regime(regime)
                _ss = market_state.get("strategy_state")
                _prev_bf = (_ss.get(bear_flatten_gate.STATE_KEY)
                            if isinstance(_ss, dict) else None)
                _gres = bear_flatten_gate.evaluate(_spy_cl, _prev_bf)
                if isinstance(_ss, dict):
                    _ss[bear_flatten_gate.STATE_KEY] = _gres.new_state
                if _gres.flatten:
                    bear_gate_fired = True
                    _bf_actions: Dict[str, Any] = {}
                    for _sym in basket:
                        _bk = books.get(_sym) or {}
                        try:
                            _hq = float(_bk.get("qty", 0.0) or 0.0)
                        except (TypeError, ValueError):
                            _hq = 0.0
                        if _hq > 0:
                            _bf_actions[_sym] = _XsecAction(
                                action="close", symbol=_sym,
                                reason=f"L165 {_gres.note} -> flatten leg to cash")
                    actions = _bf_actions
                    db.log_decision(strategy_name, "bear_flatten_close",
                                    reason=_gres.note,
                                    detail=f"L165 SPY bear gate; closing {len(_bf_actions)} held leg(s)")
            except Exception as _bf_err:  # noqa: BLE001  fail-open
                db.log_decision(strategy_name, "hold",
                                reason=f"bear_flatten_gate error (deferred): {_bf_err}",
                                detail="non-fatal")
                bear_gate_fired = False

        if not bear_gate_fired:
            actions = decide_xsec_fn(market_state, position_state, params) or {}
        if not isinstance(actions, dict):
            raise TypeError(
                f"decide_xsec must return dict[symbol -> Action], got "
                f"{type(actions).__name__}")

        # Persist any cross-flat state the strategy left behind.
        try:
            db.save_persistent_state(strategy_name, "_xsec_",
                                     market_state.get("strategy_state") or {})
        except Exception as _pstate_err:  # noqa: BLE001
            db.log_decision(strategy_name, "hold",
                            reason=f"persistent_state save failed: {_pstate_err}",
                            detail="non-fatal")

        if not actions:
            db.log_run(strategy_name, "ok",
                       int((time.monotonic() - t0) * 1000),
                       detail="no_actions")
            return 0

        # Filter actions to known symbols only.
        clean_actions = {sym: a for sym, a in actions.items() if sym in basket}
        for bad_sym in set(actions.keys()) - set(basket):
            db.log_decision(strategy_name, "skip_unknown_symbol",
                            symbol=bad_sym,
                            reason="symbol not in params.basket")

        # Basket clamp: pass current books + last prices.
        clamp_books = _books_for_clamp(books)
        clamp_prices: Dict[str, Optional[float]] = {
            sym: live_price_by_sym.get(sym) for sym in basket
        }
        clamped_buys, was_clamped = _clamp_basket(clean_actions, clamp_books,
                                                  clamp_prices)
        if was_clamped:
            db.log_decision(strategy_name, "basket_clamp",
                            reason="basket request exceeded MAX_POSITION; "
                                   "scaled buy notionals to fit")

        max_trades_per_day = risk.resolve_trades_per_day(params)

        # Execute in deterministic order: closes first (free cap headroom),
        # then buys/sells in sorted symbol order. Mirrors backtest_xsec.
        ordered_syms = sorted(clean_actions.keys())
        n_trades_executed = 0
        n_legs_rejected = 0

        # --- pass 1: closes ---
        for sym in ordered_syms:
            a = clean_actions[sym]
            act = getattr(a, "action", "hold")
            if act != "close":
                continue
            book = books.get(sym) or {}
            held_qty = float(book.get("qty", 0.0))
            if held_qty <= 0:
                db.log_decision(strategy_name, "hold", symbol=sym,
                                reason="close requested but no position")
                continue
            pos_usd = held_qty * float(
                live_price_by_sym.get(sym)
                or book.get("avg_entry_price", 0.0) or 0.0)
            rc = risk.check_trade(strategy_name, sym, "close", 0.0, pos_usd,
                                  max_trades_per_day=max_trades_per_day)
            if not rc.ok:
                n_legs_rejected += 1
                db.log_decision(strategy_name, "skip_risk", symbol=sym,
                                reason=rc.reason)
                continue
            try:
                order = client.submit_market_order(sym, "sell", qty=held_qty)
            except AlpacaError as oe:
                n_legs_rejected += 1
                db.log_decision(strategy_name, "error", symbol=sym,
                                reason=f"submit close failed: {oe}")
                continue
            _record_fill(strategy_name, sym, "sell", order, held_qty,
                         notional_hint=pos_usd,
                         price_hint=live_price_by_sym.get(sym),
                         reason=getattr(a, "reason", ""))
            db.clear_strategy_state(strategy_name, sym)
            n_trades_executed += 1

        # --- pass 2: buys / trims / sells ---
        # `buy`  -> add notional (basket-clamped); existing behavior, unchanged.
        # `trim` -> partial-reduce-while-long: resolve an exact share qty,
        #           CLAMP to the leg's attributed held qty (never oversell past
        #           flat), submit a QTY order, log a `sell` row so
        #           db.strategy_position subtracts exactly that qty, and do NOT
        #           clear leg state (the leg stays long). A full sweep degrades
        #           to the CLOSE path below.
        # `sell` -> legacy alias; routed to the SAME qty-clamped trim path so a
        #           bare `sell` can never go through the notional-submit branch
        #           and oversell a leg (the latent-bug fix).
        for sym in ordered_syms:
            a = clean_actions[sym]
            act = getattr(a, "action", "hold")
            if act not in ("buy", "sell", "trim"):
                # hold or close (already handled) — record hold rows for
                # explicit hold actions so the decision log shows what the
                # strategy thought, mirroring runner.py.
                if act == "hold":
                    db.log_decision(strategy_name, "hold", symbol=sym,
                                    reason=getattr(a, "reason", ""))
                elif act != "close":
                    n_legs_rejected += 1
                    db.log_decision(strategy_name, "error", symbol=sym,
                                    reason=f"unknown action {act!r}")
                continue

            book = books.get(sym) or {}
            held_qty = float(book.get("qty", 0.0) or 0.0)
            leg_price = live_price_by_sym.get(sym)
            pos_usd = held_qty * float(
                leg_price or book.get("avg_entry_price", 0.0) or 0.0)

            # ---- TRIM / legacy SELL: qty-clamped partial reduction ----
            if act in ("trim", "sell"):
                kind, sell_qty = _resolve_trim_sell_qty(a, held_qty, leg_price)
                if kind == "hold":
                    # Nothing attributed, or qty unresolvable -> fail safe HOLD
                    # (no broker call). Mirrors runner.py trim_no_pos /
                    # trim_unresolved.
                    db.log_decision(
                        strategy_name, "hold", symbol=sym,
                        reason=("trim requested but no attributed position / "
                                f"qty unresolved ({getattr(a, 'reason', '')})"))
                    continue
                # A trim/close is DE-RISKING: consult risk with close-semantics
                # (daily-trade-cap only; never blocked by the position cap;
                # notional passed as 0). The no-oversell guarantee is the qty
                # clamp above; risk.py stays unchanged.
                rc = risk.check_trade(strategy_name, sym, "close", 0.0, pos_usd,
                                      max_trades_per_day=max_trades_per_day)
                if not rc.ok:
                    n_legs_rejected += 1
                    db.log_decision(strategy_name, "skip_risk", symbol=sym,
                                    reason=rc.reason)
                    continue
                if kind == "close":
                    # Full sweep -> liquidate the whole attributed qty and clear
                    # leg state, via the same close mechanics as pass 1.
                    try:
                        order = client.submit_market_order(sym, "sell",
                                                           qty=held_qty)
                    except AlpacaError as oe:
                        n_legs_rejected += 1
                        db.log_decision(strategy_name, "error", symbol=sym,
                                        reason=f"submit trim->close failed: {oe}")
                        continue
                    _record_fill(strategy_name, sym, "sell", order, held_qty,
                                 notional_hint=pos_usd,
                                 price_hint=leg_price,
                                 reason=f"trim>=full->close: "
                                        f"{getattr(a, 'reason', '')}")
                    db.clear_strategy_state(strategy_name, sym)
                    n_trades_executed += 1
                    fill_price = order.get("filled_avg_price") or leg_price
                    price_str = (f"${float(fill_price):.2f}"
                                 if fill_price else "mkt")
                    print(f"[{strategy_name}] CLOSE {held_qty} {sym} "
                          f"@ {price_str} | reason: "
                          f"trim>=full->close: {getattr(a, 'reason', '')}")
                    continue
                # Strict partial: submit by clamped QTY and STAY LONG.
                trim_notional = sell_qty * float(
                    leg_price or book.get("avg_entry_price", 0.0) or 0.0)
                try:
                    order = client.submit_market_order(sym, "sell",
                                                       qty=sell_qty)
                except AlpacaError as oe:
                    n_legs_rejected += 1
                    db.log_decision(strategy_name, "error", symbol=sym,
                                    reason=f"submit trim failed: {oe}")
                    continue
                # qty_hint=sell_qty so the recorded `sell` row carries the EXACT
                # qty the attribution layer subtracts. Do NOT clear leg state.
                _record_fill(strategy_name, sym, "sell", order, sell_qty,
                             notional_hint=trim_notional,
                             price_hint=leg_price,
                             reason=getattr(a, "reason", ""))
                n_trades_executed += 1
                fill_price = order.get("filled_avg_price") or leg_price
                price_str = f"${float(fill_price):.2f}" if fill_price else "mkt"
                print(f"[{strategy_name}] TRIM {sell_qty} {sym} "
                      f"@ {price_str} | reason: {getattr(a, 'reason', '')}")
                continue

            # ---- BUY: add notional (basket-clamped). Unchanged behavior. ----
            requested = float(getattr(a, "notional_usd", 0.0) or 0.0)
            notional = float(clamped_buys.get(sym, requested) or 0.0)
            if notional <= 0:
                n_legs_rejected += 1
                db.log_decision(strategy_name, "skip_risk", symbol=sym,
                                notional_usd=requested,
                                reason=("basket clamp -> 0 "
                                        f"(requested {requested:.2f})"))
                continue
            rc = risk.check_trade(strategy_name, sym, act, notional, pos_usd,
                                  max_trades_per_day=max_trades_per_day)
            if not rc.ok:
                n_legs_rejected += 1
                db.log_decision(strategy_name, "skip_risk", symbol=sym,
                                notional_usd=notional,
                                reason=rc.reason)
                continue
            try:
                order = client.submit_market_order(sym, act,
                                                   notional_usd=notional)
            except AlpacaError as oe:
                n_legs_rejected += 1
                db.log_decision(strategy_name, "error", symbol=sym,
                                reason=f"submit {act} failed: {oe}")
                continue
            _record_fill(strategy_name, sym, act, order, qty_hint=None,
                         notional_hint=notional,
                         price_hint=live_price_by_sym.get(sym),
                         reason=getattr(a, "reason", ""))
            n_trades_executed += 1
            # Print a per-leg receipt; cron forwards to channel.
            fill_price = order.get("filled_avg_price") or live_price_by_sym.get(sym)
            price_str = f"${float(fill_price):.2f}" if fill_price else "mkt"
            print(f"[{strategy_name}] {act.upper()} ~${notional:.2f} {sym} "
                  f"@ {price_str} | reason: {getattr(a, 'reason', '')}")

        db.log_run(strategy_name, "ok",
                   int((time.monotonic() - t0) * 1000),
                   detail=(f"xsec_trades={n_trades_executed} "
                           f"rejected={n_legs_rejected} "
                           f"clamped={int(was_clamped)}"))
        return 0

    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        db.log_decision(strategy_name, "error", reason=str(e),
                        detail=tb[:4000])
        db.log_run(strategy_name, "error",
                   int((time.monotonic() - t0) * 1000),
                   detail=str(e))
        print(f"[{strategy_name}] ERROR: {e}", file=sys.stderr)
        return 1


def _record_fill(strategy_name: str, symbol: str, side: str, order: dict,
                 qty_hint: Optional[float], notional_hint: float,
                 price_hint: Optional[float], reason: str) -> None:
    """Log trade + decision rows for a submitted leg.

    Mirrors the single-symbol runner.py recording (without the
    poll/reconcile loop — xsec ticks are once-a-month rebalances, so
    a stale status row gets cleaned up on the next reconcile pass run
    out-of-band rather than blocking the tick)."""
    order_id = order.get("id")
    raw_qty = order.get("qty")
    fill_price = order.get("filled_avg_price") or price_hint
    try:
        qty_val = float(raw_qty) if raw_qty not in (None, "") else 0.0
    except (TypeError, ValueError):
        qty_val = 0.0
    if qty_val <= 0 and qty_hint:
        qty_val = float(qty_hint)
    # Notional buys return empty qty until fill; estimate from price.
    if qty_val <= 0 and fill_price and notional_hint > 0:
        try:
            qty_val = round(notional_hint / float(fill_price), 8)
        except Exception:
            pass
    status = order.get("status", "submitted")
    db.log_trade(strategy_name, symbol, side, qty_val,
                 notional_usd=notional_hint,
                 price=float(fill_price) if fill_price else None,
                 alpaca_order_id=order_id, status=status,
                 reason=reason,
                 raw=json.dumps(order)[:4000])
    db.log_decision(strategy_name, side, symbol=symbol, qty=qty_val,
                    notional_usd=notional_hint, reason=reason)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True,
                    help="strategy directory name under strategies/")
    args = ap.parse_args()
    sys.exit(run(args.strategy))


if __name__ == "__main__":
    main()
