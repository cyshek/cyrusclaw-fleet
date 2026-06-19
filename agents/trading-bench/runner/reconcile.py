"""One-shot reconcile helper: scan trades with non-terminal status and
update each row from Alpaca's current `/v2/orders/{id}` truth.

Why this exists: before the post-submit reconcile step was added to
`runner/runner.py`, every trade row was stamped with the POST-response
status (`pending_new` / `accepted`) and never updated, even after Alpaca
filled the order seconds later. This script backfills the historical rows
once. It's also safe to re-run any time \u2014 the update is idempotent.

Usage:
    python3 -m runner.reconcile           # backfill all non-terminal rows
    python3 -m runner.reconcile --dry-run # show what would change
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from . import db
from .broker_alpaca import AlpacaClient, AlpacaError


# Rows in any of these states need a fresh look from Alpaca.
NON_TERMINAL = ("submitted", "pending_new", "accepted", "new")


def _f(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def reconcile_row(client: AlpacaClient, row: dict, *,
                  dry_run: bool = False,
                  db_path=None) -> dict:
    """Reconcile a single trades row against Alpaca. Returns a small
    summary dict for the caller's report."""
    order_id = row["alpaca_order_id"]
    if not order_id:
        return {"id": row["id"], "skipped": "no order id"}
    try:
        order = client.get_order(order_id)
    except AlpacaError as e:
        return {"id": row["id"], "error": str(e)[:160]}

    new_status = order.get("status") or row["status"]
    new_price = _f(order.get("filled_avg_price"))
    new_qty = _f(order.get("filled_qty"))

    update_kwargs: dict = {"status": new_status,
                           "raw": json.dumps(order)[:4000]}
    if new_price is not None:
        update_kwargs["price"] = new_price
    if new_qty and new_qty > 0:
        update_kwargs["qty"] = new_qty

    summary = {
        "id": row["id"],
        "strategy": row["strategy"],
        "symbol": row["symbol"],
        "old_status": row["status"],
        "new_status": new_status,
        "old_price": row["price"],
        "new_price": new_price,
        "old_qty": row["qty"],
        "new_qty": new_qty,
    }
    if not dry_run:
        kwargs = dict(update_kwargs)
        if db_path is not None:
            kwargs["db_path"] = db_path
        db.update_trade_status(row["id"], **kwargs)
    return summary


def backfill(*, dry_run: bool = False, db_path=None) -> list[dict]:
    """Backfill every non-terminal trades row from Alpaca. Returns a
    list of per-row summaries."""
    path = db_path if db_path is not None else db.DB_PATH
    with db.connect(path) as c:
        placeholders = ",".join("?" * len(NON_TERMINAL))
        rows = c.execute(
            f"SELECT id, ts_utc, strategy, symbol, side, qty, price, "
            f"alpaca_order_id, status FROM trades "
            f"WHERE status IN ({placeholders}) ORDER BY id ASC",
            NON_TERMINAL,
        ).fetchall()
    rows = [dict(r) for r in rows]
    if not rows:
        return []
    client = AlpacaClient()
    out = []
    for r in rows:
        out.append(reconcile_row(client, r, dry_run=dry_run, db_path=path))
    return out


def _status_counts(db_path=None) -> dict:
    path = db_path if db_path is not None else db.DB_PATH
    with db.connect(path) as c:
        rows = c.execute(
            "SELECT status, COUNT(*) as n FROM trades GROUP BY status "
            "ORDER BY n DESC"
        ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would change without writing.")
    args = ap.parse_args()

    before = _status_counts()
    print("Before:", before)
    summaries = backfill(dry_run=args.dry_run)
    if not summaries:
        print("Nothing to do \u2014 no non-terminal rows.")
        return 0
    for s in summaries:
        print(s)
    after = _status_counts()
    print("After: ", after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
