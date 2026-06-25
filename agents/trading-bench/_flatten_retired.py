#!/usr/bin/env python3
"""One-shot flatten of a RETIRED strategy's attributed position.

Reuses the LIVE runner's own primitives verbatim — no reimplementation of
attribution or sizing:
  - runner.runner.build_position_state(client, symbol, strat)  (attributed qty)
  - client.submit_market_order(symbol, "sell", qty=held_qty)   (clamped close)
  - db.log_trade(...) + db.clear_strategy_state(...)            (bookkeeping)

This is the exact CLOSE branch the runner runs when a strategy decides to go
flat; we invoke it deliberately because the strategy was removed from cron and
will not tick again to manage/close its dangling position.

Hard rails honored: killswitch (STOP_TRADING) aborts; paper-account guard in
broker_alpaca.AlpacaClient still applies (it refuses non-paper URLs by
construction). Pass --execute to actually trade; default is DRY-RUN.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from runner import db
from runner.broker_alpaca import AlpacaClient
from runner.runner import build_position_state

WORKSPACE = Path(__file__).resolve().parent
KILLSWITCH = WORKSPACE / "STOP_TRADING"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--execute", action="store_true",
                    help="actually submit the close; default is dry-run")
    args = ap.parse_args()

    if KILLSWITCH.exists():
        print("ABORT: STOP_TRADING killswitch present — no-op.", file=sys.stderr)
        return 2

    db.init_db()
    client = AlpacaClient()  # refuses non-paper URLs by construction (hard rail)

    pos = build_position_state(client, args.symbol, args.strategy)
    held = float(pos.get(args.symbol, {}).get("qty", 0.0) or 0.0)
    avg = float(pos.get(args.symbol, {}).get("avg_entry_price", 0.0) or 0.0)
    print(f"[{args.strategy}] attributed {args.symbol} qty={held:.8f} "
          f"avg_entry=${avg:.4f}")

    if held <= 1e-9:
        print(f"[{args.strategy}] already FLAT in {args.symbol} — nothing to do.")
        return 0

    if not args.execute:
        print(f"DRY-RUN: would SELL qty={held:.8f} {args.symbol} "
              f"(clamped to attributed qty) and clear strategy state.")
        return 0

    t0 = time.monotonic()
    order = client.submit_market_order(args.symbol, "sell", qty=held)
    order_id = order.get("id")
    fill_price = order.get("filled_avg_price")
    status = order.get("status", "submitted")
    notional = held * (float(fill_price) if fill_price else avg)
    trade_id = db.log_trade(
        args.strategy, args.symbol, "sell", held,
        notional_usd=notional,
        price=float(fill_price) if fill_price else None,
        alpaca_order_id=order_id,
        status=status,
        reason="RETIRED-from-cron de-dup flatten (interstrategy-corr action 2026-06-24)",
        raw=json.dumps(order)[:4000],
    )
    db.clear_strategy_state(args.strategy, args.symbol)
    px = f"${float(fill_price):.4f}" if fill_price else "mkt"
    print(f"[{args.strategy}] SELL {held:.8f} {args.symbol} @ {px} "
          f"order={order_id} status={status} trade_id={trade_id} "
          f"({int((time.monotonic()-t0)*1000)}ms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
