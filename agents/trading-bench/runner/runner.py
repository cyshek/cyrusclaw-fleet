"""The ONE shared runner. Every strategy is invoked the same way:

    python -m runner.runner --strategy buy_and_hold_spy

Pipeline:
    1. Killswitch check (STOP_TRADING file in workspace root). If present: no-op.
    2. Load strategy module + params.
    3. Build market_state + position_state from Alpaca.
    4. Call strategy.decide(...).
    5. Risk-check the proposed action.
    6. If buy/sell: submit market order via broker_alpaca.
    7. Log to tournament.db (decisions always; trades when one fires).
    8. Print a one-line trade receipt to stdout (cron forwards to the channel).
       Skipped/rejected/hold actions stay silent to avoid channel spam.

Receipt format:
    [strategy] BUY/SELL <qty> <symbol> @ <price> | reason: <one-liner>
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from . import db, risk
from . import safety_backstop
from .broker_alpaca import AlpacaClient, AlpacaError
from .kelly import kelly_notional as _kelly_notional
from .edge_calibrator import get_calibrated_kelly_fraction as _get_calibrated_kelly
from .market_hours import is_us_equity_market_open

# Regime gate is imported lazily inside run() to keep import-time side
# effects minimal and allow tests to monkeypatch on a per-test basis.


@dataclass
class _SyntheticAction:
    """Duck-types the per-strategy `Action` dataclass for cases where the
    runner needs to synthesize an action without calling the strategy's
    `decide()` — currently only the safety backstop close path.
    The downstream pipeline (risk check, close submit, log_trade) reads
    only `.action`, `.symbol`, `.notional_usd`, `.reason`."""
    action: str
    symbol: str
    notional_usd: float = 0.0
    reason: str = ""

WORKSPACE = Path(__file__).resolve().parent.parent
KILLSWITCH = WORKSPACE / "STOP_TRADING"
STRATEGIES_ROOT = WORKSPACE / "strategies"


def killswitch_active() -> bool:
    return KILLSWITCH.exists()


def load_strategy(name: str):
    strat_dir = STRATEGIES_ROOT / name
    params_path = strat_dir / "params.json"
    if not strat_dir.is_dir():
        raise FileNotFoundError(f"No strategy dir: {strat_dir}")
    if not params_path.exists():
        raise FileNotFoundError(f"No params.json: {params_path}")
    # strategies/<name>/strategy.py imports clean once strategies is on sys.path.
    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))
    module = importlib.import_module(f"strategies.{name}.strategy")
    params = json.loads(params_path.read_text())
    return module, params


def build_position_state(client: AlpacaClient, symbol: str,
                         strategy_name: str) -> dict:
    """Strategy-attributed position from our trade log.

    The shared Alpaca account aggregates positions across strategies; for the
    tournament we must isolate each strategy's exposure. We reconstruct from
    the `trades` table. If the strategy has never traded, qty=0.
    """
    sp = db.strategy_position(strategy_name, symbol)
    if sp["qty"] <= 0:
        return {}
    avg = (sp["cost_basis_usd"] / sp["qty"]) if sp["qty"] > 0 else 0.0
    # market_value uses the most recent fill we know about; runner overlays live price after.
    return {
        symbol: {
            "qty": sp["qty"],
            "market_value": sp["qty"] * (sp["last_price"] or avg),
            "avg_entry_price": avg,
        }
    }


def current_position_usd(position_state: dict, symbol: str) -> float:
    p = position_state.get(symbol)
    return float(p["market_value"]) if p else 0.0


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
        # Quiet by design; do not spam channel.
        return 0

    try:
        module, params = load_strategy(strategy_name)
        client = AlpacaClient()
        symbol = params.get("symbol", "BTC/USD")
        is_crypto = AlpacaClient.is_crypto_symbol(symbol)

        # Stocks: short-circuit when market is closed. No order attempted; clean log.
        if not is_crypto and not is_us_equity_market_open():
            db.log_decision(strategy_name, "skip_market_closed", symbol=symbol,
                            reason="US equity market closed (regular session only)")
            db.log_run(strategy_name, "ok",
                       int((time.monotonic() - t0) * 1000),
                       detail="skip_market_closed")
            return 0

        # -------- Tier 2 regime gate (opt-in via params.regime_gate=true) -------
        # Best-effort consult: any failure here must NEVER crash a tick.
        # Crypto strategies bypass the gate (no SPY-based regime today, per
        # design §6.2 option (a)).
        regime_gate_on = bool(params.get("regime_gate", False))
        if regime_gate_on and not is_crypto:
            try:
                from . import regime_classifier as _rc  # noqa: WPS433
                regime_decision = _rc.get_today_regime()
            except Exception as _rg_err:  # noqa: BLE001
                # Module import / DB read failed; behave as if no decision.
                db.log_decision(strategy_name, "hold", symbol=symbol,
                                reason=f"regime_gate_consult_failed: {_rg_err}",
                                detail="non-fatal")
                regime_decision = None
            if regime_decision is None:
                # No fresh decision (cron missed, brand-new system, TTL'd out).
                # Default-safe: skip this tick. Trade resumes once cron writes
                # a fresh row OR the operator runs `python3 -m runner.regime_classifier --run`.
                db.log_decision(strategy_name, "skip_regime_unknown", symbol=symbol,
                                reason="no regime decision available (cron missed or stale)")
                db.log_run(strategy_name, "ok",
                           int((time.monotonic() - t0) * 1000),
                           detail="skip_regime_unknown")
                return 0
            allow = regime_decision.get("allow_strategies") or []
            if strategy_name not in allow:
                db.log_decision(
                    strategy_name, "skip_regime_block", symbol=symbol,
                    reason=(f"regime={regime_decision.get('regime')} "
                            f"blocks strategy; "
                            f"source={regime_decision.get('source')}"
                            + ("; stale" if regime_decision.get("is_stale") else "")),
                )
                db.log_run(strategy_name, "ok",
                           int((time.monotonic() - t0) * 1000),
                           detail="skip_regime_block")
                return 0

        position_state = build_position_state(client, symbol, strategy_name)
        # Merge persisted strategy bookkeeping state (running_max, scaled_out,
        # entry_bar_index, etc.) into position_state[symbol]. Broker-truth
        # keys (qty/market_value/avg_entry_price) are always from the trade
        # log via build_position_state; strategy state layered ON TOP. If we
        # currently hold no position, drop any stale strategy state to keep
        # the DB tidy (defensive — clear-on-close below should already do it).
        if symbol in position_state:
            persisted_state = db.get_strategy_state(strategy_name, symbol)
            for k, v in persisted_state.items():
                position_state[symbol].setdefault(k, v)
        else:
            db.clear_strategy_state(strategy_name, symbol)
        try:
            price = (client.latest_crypto_price(symbol) if is_crypto
                     else client.latest_stock_price(symbol))
        except AlpacaError:
            price = None
        # Overlay live price onto attributed position market_value if we hold.
        if price and symbol in position_state:
            position_state[symbol]["market_value"] = position_state[symbol]["qty"] * price
        timeframe = str(params.get("timeframe", "1Hour"))
        bar_limit = int(params.get("bar_limit", 200))
        try:
            bars = (client.crypto_bars(symbol, timeframe=timeframe, limit=bar_limit)
                    if is_crypto
                    else client.stock_bars(symbol, timeframe=timeframe, limit=bar_limit))
        except AlpacaError:
            bars = []
        # Regime injection: stocks get SPY 1Day(100) so strategies can gate
        # on broad-market trend. Crypto gets None (no equivalent reference).
        # Fetch is best-effort — if it fails, regime is None and any
        # regime-aware strategy falls back to its default behavior.
        regime = None
        if not is_crypto:
            try:
                spy_bars = client.stock_bars("SPY", timeframe="1Day", limit=100)
                spy_closes = [float(b["c"]) for b in (spy_bars or [])]
                if spy_closes:
                    regime = {"spy_closes": spy_closes,
                              "spy_last": spy_closes[-1]}
            except AlpacaError:
                regime = None
        # Underlying injection: a sleeve strategy (e.g. TQQQ) may gate on a
        # DIFFERENT underlying (e.g. QQQ) than the symbol it trades. If params
        # declares `underlying` and it differs from the traded symbol, fetch its
        # daily closes so the strategy can evaluate that gate WITHOUT a proxy.
        # Best-effort + completed daily bars only (same no-lookahead convention
        # as every other series here); None/absent on failure -> the strategy
        # fails safe. Mirrors the SPY-regime fetch above.
        underlying_block = None
        if not is_crypto:
            underlying_sym = str(params.get("underlying", "")).upper()
            if underlying_sym and underlying_sym != symbol.upper():
                try:
                    u_limit = max(int(params.get("sma_window", 200)) + 30, 260)
                    u_bars = client.stock_bars(underlying_sym, timeframe="1Day", limit=u_limit)
                    u_closes = [float(b["c"]) for b in (u_bars or [])]
                    if u_closes:
                        underlying_block = {"symbol": underlying_sym, "closes": u_closes}
                except AlpacaError:
                    underlying_block = None
        # Load cross-flat persistent state (survives close). Lifecycle is
        # explicit: the strategy owns this dict, mutates it freely, and
        # we persist whatever it leaves behind. NEVER auto-cleared on
        # flat — that's the whole point of this state class.
        persistent_state = db.get_persistent_state(strategy_name, symbol)
        market_state = {"symbol": symbol, "last_price": price,
                        "bars": bars, "timeframe": timeframe,
                        "regime": regime,
                        "underlying": underlying_block,
                        "strategy_state": persistent_state}

        # Safety backstop: BEFORE we ask the strategy what to do, check
        # whether the existing position has tripped a hard rail (e.g.
        # unrealized loss past safety_max_loss_pct in params.json). If so,
        # synthesize a close action and skip decide() entirely — the
        # strategy doesn't get to argue with the safety rail.
        backstop_pos = position_state.get(symbol)
        # bars_since_entry powers safety_max_holding_bars. None means
        # "can't compute" (flat, or never traded) and the trigger silently
        # skips. We look up entry_ts from the trade log only if we currently
        # hold a position — avoids a query when flat.
        bars_in_pos = None
        if backstop_pos:
            entry_ts = db.position_entry_ts(strategy_name, symbol)
            if entry_ts:
                bars_in_pos = safety_backstop.bars_since_entry(bars, entry_ts)
        bs_action = safety_backstop.check(backstop_pos, price, params,
                                          bars_since_entry=bars_in_pos)
        if bs_action.fire:
            action = _SyntheticAction(
                action="close",
                symbol=symbol,
                reason=f"safety_backstop:{bs_action.trigger}: {bs_action.reason}",
            )
            # Don't call decide(); fall through to the close-handling
            # pipeline below with the synthesized action.
        else:
            action = module.decide(market_state, position_state, params)

        # Persist the cross-flat state the strategy left behind. If the
        # strategy assigned {} the save helper does a DELETE so we don't
        # accumulate empty rows. Best-effort — a persistent-state save
        # failure must NEVER block a trade decision.
        try:
            db.save_persistent_state(strategy_name, symbol,
                                     market_state["strategy_state"])
        except Exception as _pstate_err:  # noqa: BLE001
            db.log_decision(strategy_name, "hold", symbol=symbol,
                            reason=f"persistent_state save failed: {_pstate_err}")

        # Persist any mutations the strategy made to position_state[symbol]
        # (e.g. updated running_max, scaled_out flag). Only relevant while
        # holding a position; flat positions are cleared explicitly on
        # close-fill below. Broker-truth keys are stripped by save_strategy_state.
        if action.symbol and action.symbol in position_state:
            try:
                db.save_strategy_state(strategy_name, action.symbol,
                                       position_state[action.symbol])
            except Exception as _state_err:  # noqa: BLE001
                # State save is best-effort; never let it block a trade decision.
                db.log_decision(strategy_name, "hold", symbol=action.symbol,
                                reason=f"strategy_state save failed: {_state_err}",
                                detail="non-fatal")

        if action.action == "hold":
            db.log_decision(strategy_name, "hold", symbol=action.symbol,
                            reason=action.reason)
            db.log_run(strategy_name, "ok",
                       int((time.monotonic() - t0) * 1000), detail="hold")
            return 0

        if action.action not in ("buy", "sell", "close"):
            db.log_decision(strategy_name, "error", symbol=action.symbol,
                            reason=f"unknown action {action.action!r}")
            db.log_run(strategy_name, "error",
                       int((time.monotonic() - t0) * 1000))
            return 1

        # Kelly sizing: replace flat notional with Kelly-optimal size for buys
        # when sufficient closed-trade history exists.
        # Returns 0.0 when Kelly fraction ≤ 0 (negative edge) → skip the trade.
        # Returns params["notional_usd"] (flat fallback) when history < 20 round-trips.
        notional = float(action.notional_usd or 0.0)
        if action.action == "buy" and notional <= risk.MAX_NOTIONAL:
            kelly_n = _kelly_notional(strategy_name, params)
            if kelly_n == 0.0:
                db.log_decision(
                    strategy_name, "skip_kelly_negative_edge",
                    symbol=action.symbol,
                    reason="Kelly fraction ≤ 0 — negative edge, skipping trade",
                )
                db.log_run(
                    strategy_name, "ok",
                    int((time.monotonic() - t0) * 1000),
                    detail="skip_kelly_negative_edge",
                )
                return 0
            # Edge-calibration: scale Kelly notional down when OOS reliability is uncertain.
            # get_calibrated_kelly_fraction: pass-through when insufficient data;
            # returns raw_fraction * multiplier (0.0-1.0) when model is trained.
            # Max notional for fraction conversion: use MAX_NOTIONAL.
            raw_kelly_fraction = kelly_n / risk.MAX_NOTIONAL
            calibrated_fraction = _get_calibrated_kelly(strategy_name, raw_kelly_fraction)
            calibrated_notional = calibrated_fraction * risk.MAX_NOTIONAL
            if calibrated_notional < kelly_n:
                db.log_decision(
                    strategy_name, "hold",
                    symbol=action.symbol,
                    reason=(f"edge_calibrator: kelly_n={kelly_n:.2f} → "
                            f"calibrated={calibrated_notional:.2f} "
                            f"(fraction {raw_kelly_fraction:.4f}→{calibrated_fraction:.4f})"),
                    detail="non-fatal",
                )
                kelly_n = max(calibrated_notional, 0.0)
            notional = kelly_n

        # Risk check
        pos_usd = current_position_usd(position_state, action.symbol)
        rc = risk.check_trade(strategy_name, action.symbol, action.action,
                              notional, pos_usd,
                              max_trades_per_day=risk.resolve_trades_per_day(params))
        if not rc.ok:
            db.log_decision(strategy_name, "skip_risk", symbol=action.symbol,
                            notional_usd=notional,
                            reason=rc.reason)
            db.log_run(strategy_name, "ok",
                       int((time.monotonic() - t0) * 1000),
                       detail=f"risk_reject: {rc.reason}")
            return 0

        # Submit
        if action.action == "close":
            if pos_usd <= 0:
                db.log_decision(strategy_name, "hold", symbol=action.symbol,
                                reason="close requested but no position")
                db.log_run(strategy_name, "ok",
                           int((time.monotonic() - t0) * 1000), detail="no-pos")
                return 0
            # Sell strategy-attributed qty only (don't blow away other strategies' BTC).
            held_qty = position_state[action.symbol]["qty"]
            order = client.submit_market_order(action.symbol, "sell", qty=held_qty)
            effective_side = "sell"
            # For attribution: record notional as cost-at-fill if we can.
            if not notional:
                notional = held_qty * (price or position_state[action.symbol]["avg_entry_price"])
            # Position is now flat — drop any strategy bookkeeping state so a
            # stale running_max can't leak into the next trade.
            db.clear_strategy_state(strategy_name, action.symbol)
        else:
            order = client.submit_market_order(action.symbol, action.action,
                                               notional_usd=notional)
            effective_side = action.action
        order_id = order.get("id")
        fill_price = order.get("filled_avg_price") or price
        raw_qty = order.get("qty")
        try:
            qty_val = float(raw_qty) if raw_qty not in (None, "") else 0.0
        except (TypeError, ValueError):
            qty_val = 0.0
        status = order.get("status", "submitted")

        # Notional buys return empty qty until fill; estimate from price.
        if qty_val <= 0 and fill_price and notional > 0:
            try:
                qty_val = round(notional / float(fill_price), 8)
            except Exception:
                pass
        trade_id = db.log_trade(strategy_name, action.symbol, effective_side, qty_val,
                     notional_usd=notional,
                     price=float(fill_price) if fill_price else None,
                     alpaca_order_id=order_id,
                     status=status,
                     reason=action.reason,
                     raw=json.dumps(order)[:4000])

        # Reconcile: the POST /v2/orders response usually returns the
        # transient state ('pending_new' / 'accepted'), not the settled
        # outcome. Poll up to 3x (500ms apart) to capture the true
        # status / filled_avg_price / filled_qty before moving on. Keep
        # the budget tight (<=2s wall clock) so the runner tick stays
        # snappy. Any failure here is logged-and-swallowed — a stale
        # status row is recoverable; a crashed tick is not.
        if order_id:
            try:
                final = order
                final_status = status
                for attempt in range(3):
                    if final_status in db.TERMINAL_ORDER_STATUSES:
                        break
                    if attempt > 0:
                        time.sleep(0.5)
                    try:
                        final = client.get_order(order_id)
                    except AlpacaError:
                        break
                    final_status = final.get("status", final_status)
                # Extract reconciled fill data (Alpaca returns strings).
                def _f(v):
                    try:
                        return float(v) if v not in (None, "") else None
                    except (TypeError, ValueError):
                        return None
                fav = _f(final.get("filled_avg_price"))
                fqty = _f(final.get("filled_qty"))
                update_kwargs = {"status": final_status,
                                 "raw": json.dumps(final)[:4000]}
                if fav is not None:
                    update_kwargs["price"] = fav
                if fqty and fqty > 0:
                    update_kwargs["qty"] = fqty
                db.update_trade_status(trade_id, **update_kwargs)
                status = final_status  # surface latest in the run detail line
                if fav is not None:
                    fill_price = fav
                if fqty and fqty > 0:
                    qty_val = fqty
            except Exception as _rec_err:  # noqa: BLE001
                # Reconcile is best-effort; never let it crash a tick.
                db.log_decision(strategy_name, "hold", symbol=action.symbol,
                                reason=f"reconcile failed: {_rec_err}",
                                detail="non-fatal")

        db.log_decision(strategy_name, effective_side, symbol=action.symbol,
                        qty=qty_val, notional_usd=notional,
                        reason=action.reason)
        db.log_run(strategy_name, "ok",
                   int((time.monotonic() - t0) * 1000),
                   detail=f"order {order_id} {status}")

        price_str = f"${float(fill_price):.2f}" if fill_price else "mkt"
        # Receipt to stdout — cron's announce delivery forwards this to channel.
        print(f"[{strategy_name}] {effective_side.upper()} {qty_val} "
              f"{action.symbol} @ {price_str} | reason: {action.reason}")
        return 0

    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        db.log_decision(strategy_name, "error", reason=str(e), detail=tb[:4000])
        db.log_run(strategy_name, "error",
                   int((time.monotonic() - t0) * 1000),
                   detail=str(e))
        print(f"[{strategy_name}] ERROR: {e}", file=sys.stderr)
        return 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True,
                    help="strategy directory name under strategies/")
    args = ap.parse_args()
    sys.exit(run(args.strategy))


if __name__ == "__main__":
    main()
