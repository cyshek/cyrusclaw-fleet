"""Position-level drift check: DB filled-trade net qty per SYMBOL vs Alpaca held qty.

Complements runner/reconcile.py (which only reconciles non-terminal ORDER status).
This checks the second drift dimension: does the book the DB THINKS we hold match
what Alpaca ACTUALLY holds, per symbol?

Two pollution/realism guards (mirrors the edge_calibrator universe-filter fix):
  1. SYNTHETIC EXCLUSION: rows from test/seed strategies (`any`, `backstop_test`,
     `bp2`, ...) or with fake order ids (`order-1`, `ord-seed`, non-UUID) never hit
     Alpaca -- they are unit-test/seed fixtures and must not count toward drift.
  2. ASSET-CLASS TOLERANCE: equities reconcile to float epsilon; crypto carries a
     small fractional-fill/fee haircut (Alpaca skims spread/fee on crypto fills) so
     held qty sits a hair below summed fill qty -- a looser tolerance is correct,
     not a bug.

Exit codes: 0 = no real drift, 2 = real drift on a live-roster / real-order symbol.

Usage:
    python3 -m runner.position_drift            # human report
    python3 -m runner.position_drift --json     # machine summary
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(WORKSPACE / "tournament.db")

# Strategies that only ever produced synthetic test/seed rows (never real orders).
SYNTHETIC_STRATEGIES = {"any", "backstop_test", "bp2"}
# Order ids that are obviously not real Alpaca UUIDs.
SYNTHETIC_ORDER_IDS = {"order-1", "ord-seed"}

EQUITY_TOL = 1e-6      # equities: should match to float epsilon
CRYPTO_TOL = 1e-2      # crypto: fractional-fill/fee haircut tolerance


def _is_crypto(symbol: str) -> bool:
    return "/" in symbol  # Alpaca crypto pairs look like BTC/USD


def _is_synthetic_row(strategy: str, order_id) -> bool:
    if strategy in SYNTHETIC_STRATEGIES:
        return True
    if order_id is None:
        return True
    oid = str(order_id)
    if oid in SYNTHETIC_ORDER_IDS:
        return True
    # Real Alpaca order ids are 36-char UUIDs; anything much shorter is synthetic.
    if len(oid) < 20:
        return True
    return False


def compute_db_net(db_path: str = DEFAULT_DB) -> Dict[str, float]:
    """Net qty per symbol from REAL filled trades (buys +, sells -)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT strategy, symbol, side, qty, alpaca_order_id "
            "FROM trades WHERE status='filled'"
        ).fetchall()
    finally:
        conn.close()

    net: Dict[str, float] = defaultdict(float)
    for r in rows:
        if _is_synthetic_row(r["strategy"], r["alpaca_order_id"]):
            continue
        q = float(r["qty"] or 0.0)
        net[r["symbol"]] += q if r["side"] == "buy" else -q
    return dict(net)


def check_drift(db_path: str = DEFAULT_DB) -> Dict:
    """Compare DB net (real rows only) to Alpaca held qty per symbol."""
    sys.path.insert(0, str(WORKSPACE))
    from runner.broker_alpaca import AlpacaClient, AlpacaError

    net = compute_db_net(db_path)
    client = AlpacaClient()
    rows: List[Dict] = []
    real_drift = False

    for sym in sorted(net):
        db_net = net[sym]
        tol = CRYPTO_TOL if _is_crypto(sym) else EQUITY_TOL
        err = None
        try:
            pos = client.get_position(sym)
            alp_qty = float(pos.get("qty", 0.0)) if pos else 0.0
        except AlpacaError as e:
            alp_qty = None
            err = str(e)[:160]

        if alp_qty is None:
            status = "ALPACA_ERROR"
            diff = None
            real_drift = True
        else:
            diff = db_net - alp_qty
            if abs(diff) <= tol:
                status = "OK"
            else:
                status = "DRIFT"
                real_drift = True

        rows.append({
            "symbol": sym,
            "db_net": round(db_net, 8),
            "alpaca_qty": (round(alp_qty, 8) if alp_qty is not None else None),
            "diff": (round(diff, 10) if diff is not None else None),
            "asset": "crypto" if _is_crypto(sym) else "equity",
            "tol": tol,
            "status": status,
            "error": err,
        })

    return {"real_drift": real_drift, "rows": rows,
            "n_symbols": len(rows)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--json", action="store_true", help="machine JSON output")
    args = ap.parse_args()

    res = check_drift(db_path=args.db)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print("=== Position drift: DB net (real filled rows) vs Alpaca held ===")
        for r in res["rows"]:
            aq = ("%+.6f" % r["alpaca_qty"]) if r["alpaca_qty"] is not None else "ERR"
            df = ("%+.2e" % r["diff"]) if r["diff"] is not None else "n/a"
            mark = "" if r["status"] == "OK" else "  <<< %s" % r["status"]
            print("  %-8s [%s] DB=%+.6f Alpaca=%s diff=%s tol=%.0e%s" % (
                r["symbol"], r["asset"], r["db_net"], aq, df, r["tol"], mark))
        print()
        print("REAL_DRIFT =", res["real_drift"])
    return 2 if res["real_drift"] else 0


if __name__ == "__main__":
    sys.exit(main())
