"""Tournament ranking.

For each strategy we compute:
    - n_trades:    filled/submitted trades to date
    - realized_pnl_usd:    P&L from closed legs (FIFO)
    - unrealized_pnl_usd:  current open exposure marked to latest fill price (cheap proxy)
    - total_pnl_usd
    - win_rate:    closed trades only, > 0 considered a win
    - avg_trade_pnl: realized only
    - turnover_usd

Output: prints a Markdown table to stdout, and stores a snapshot row in `rankings`.
Used by the weekly tournament report; safe to call ad-hoc.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from . import db
from . import correlation
from . import risk_metrics
from .edge_calibrator import LIVE_ROSTER, EXCLUDE_STRATEGIES


SCHEMA = """
CREATE TABLE IF NOT EXISTS rankings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    strategy        TEXT    NOT NULL,
    n_trades        INTEGER NOT NULL,
    realized_usd    REAL    NOT NULL,
    unrealized_usd  REAL    NOT NULL,
    total_usd       REAL    NOT NULL,
    win_rate        REAL,
    turnover_usd    REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rankings_ts ON rankings(ts_utc);
"""


def _ensure_schema():
    with db.connect() as c:
        c.executescript(SCHEMA)


def compute(include_all: bool = False) -> List[dict]:
    """Per-strategy realized/unrealized P&L + risk metrics.

    By default the leaderboard is restricted to the LIVE book (edge_calibrator.LIVE_ROSTER)
    and ALWAYS strips EXCLUDE_STRATEGIES (synthetic harnesses + dead crypto legs) -- the same
    canonical guard used by position_drift / edge_calibrator, so the board reflects the real
    8-strategy book instead of tournament.db's synthetic-row pollution. Pass include_all=True
    to show every strategy in the DB (forensics only).
    """
    _ensure_schema()
    with db.connect() as c:
        trades = c.execute(
            "SELECT strategy, symbol, side, qty, price, notional_usd, ts_utc "
            "FROM trades WHERE status IN "
            "('submitted','filled','partially_filled','accepted','new','pending_new') "
            "ORDER BY id ASC"
        ).fetchall()

    # group per (strategy, symbol), filtering non-book rows unless include_all.
    by_key: Dict[tuple, list] = defaultdict(list)
    for t in trades:
        strat = t["strategy"]
        if not include_all and (strat in EXCLUDE_STRATEGIES or strat not in LIVE_ROSTER):
            continue
        by_key[(strat, t["symbol"])].append(dict(t))

    # latest fill price per symbol for unrealized mark
    latest_price: Dict[str, float] = {}
    for t in trades:
        if t["price"]:
            latest_price[t["symbol"]] = float(t["price"])

    summary: Dict[str, dict] = defaultdict(lambda: {
        "strategy": "", "n_trades": 0, "realized_usd": 0.0,
        "unrealized_usd": 0.0, "wins": 0, "losses": 0, "turnover_usd": 0.0,
    })

    for (strat, sym), legs in by_key.items():
        lots = deque()  # FIFO of {qty, price}
        realized = 0.0
        wins = 0
        losses = 0
        for leg in legs:
            qty = float(leg["qty"] or 0)
            price = float(leg["price"] or 0)
            notional = float(leg["notional_usd"] or qty * price)
            summary[strat]["turnover_usd"] += notional
            summary[strat]["n_trades"] += 1
            if leg["side"] == "buy":
                lots.append({"qty": qty, "price": price})
            else:  # sell
                remaining = qty
                while remaining > 1e-12 and lots:
                    lot = lots[0]
                    take = min(lot["qty"], remaining)
                    pnl = (price - lot["price"]) * take
                    realized += pnl
                    if pnl >= 0:
                        wins += 1
                    else:
                        losses += 1
                    lot["qty"] -= take
                    remaining -= take
                    if lot["qty"] <= 1e-12:
                        lots.popleft()
        # unrealized = open lots marked to latest_price
        mark = latest_price.get(sym, 0.0)
        unrealized = sum((mark - lot["price"]) * lot["qty"] for lot in lots) if mark else 0.0
        s = summary[strat]
        s["strategy"] = strat
        s["realized_usd"] += realized
        s["unrealized_usd"] += unrealized
        s["wins"] += wins
        s["losses"] += losses

    rows = []
    for strat, s in summary.items():
        closed = s["wins"] + s["losses"]
        win_rate = (s["wins"] / closed) if closed else None
        total = s["realized_usd"] + s["unrealized_usd"]
        rows.append({
            "strategy": strat,
            "n_trades": s["n_trades"],
            "realized_usd": round(s["realized_usd"], 4),
            "unrealized_usd": round(s["unrealized_usd"], 4),
            "total_usd": round(total, 4),
            "win_rate": round(win_rate, 3) if win_rate is not None else None,
            "turnover_usd": round(s["turnover_usd"], 2),
        })
    rows.sort(key=lambda r: r["total_usd"], reverse=True)
    _attach_risk_metrics(rows)
    return rows


def _attach_risk_metrics(rows: List[dict]) -> None:
    """Add Sortino/Calmar (and supporting day counts) to each row, from the realized
    daily-P&L series. Additive + best-effort: any failure leaves the row's raw P&L intact
    and simply omits the risk fields (set to None). Never raises.
    """
    for r in rows:
        try:
            series = correlation.daily_pnl_series(r["strategy"])
            m = risk_metrics.compute_for_series(series)
        except Exception:
            m = {"n_closed_days": None, "n_down_days": None,
                 "sortino": None, "calmar": None, "max_drawdown_usd": None}
        r["sortino"] = (round(m["sortino"], 3) if m["sortino"] is not None else None)
        r["calmar"] = (round(m["calmar"], 3) if m["calmar"] is not None else None)
        r["max_drawdown_usd"] = m["max_drawdown_usd"]
        r["n_closed_days"] = m["n_closed_days"]


def snapshot(rows: List[dict]) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.connect() as c:
        for r in rows:
            c.execute(
                "INSERT INTO rankings (ts_utc, strategy, n_trades, realized_usd, "
                "unrealized_usd, total_usd, win_rate, turnover_usd) VALUES "
                "(?,?,?,?,?,?,?,?)",
                (ts, r["strategy"], r["n_trades"], r["realized_usd"],
                 r["unrealized_usd"], r["total_usd"], r["win_rate"],
                 r["turnover_usd"]),
            )


def format_chat(rows: List[dict]) -> str:
    if not rows:
        return "📊 No trades yet. Tournament leaderboard empty."
    lines = ["📊 **Tournament leaderboard** (so far)"]
    for i, r in enumerate(rows, 1):
        wr = f"{r['win_rate']*100:.0f}%" if r["win_rate"] is not None else "n/a"
        sortino = r.get("sortino")
        calmar = r.get("calmar")
        srt = f"{sortino:+.2f}" if sortino is not None else "n/a"
        clm = f"{calmar:+.2f}" if calmar is not None else "n/a"
        ndays = r.get("n_closed_days")
        nd = ndays if ndays is not None else "?"
        lines.append(
            f"{i}. `{r['strategy']}` — total ${r['total_usd']:+.2f} "
            f"(realized ${r['realized_usd']:+.2f}, unrealized ${r['unrealized_usd']:+.2f}) "
            f"| trades={r['n_trades']}, win%={wr}, turnover=${r['turnover_usd']:.0f} "
            f"| Sortino={srt}, Calmar={clm} (closed-days={nd})"
        )
    lines.append(
        "_Sample sizes are tiny; rankings are noise until n_trades >> 20. "
        "Sortino/Calmar show n/a until a strategy has ≥2 closed-P&L days with a losing day "
        "(no downside → ratio undefined, not infinite)._"
    )
    return "\n".join(lines)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Tournament ranking")
    parser.add_argument("--correlation", action="store_true",
                        help="Append per-strategy daily-P&L correlation matrix")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="Skip writing rankings snapshot row")
    parser.add_argument("--risk-sort", action="store_true",
                        help="Sort leaderboard by Sortino (desc) instead of total P&L; "
                             "undefined-Sortino strategies sink to the bottom")
    parser.add_argument("--all", action="store_true",
                        help="Include ALL strategies in tournament.db (synthetic test rows "
                             "+ retired/dead lanes); default shows only the live book")
    args = parser.parse_args()

    rows = compute(include_all=args.all)
    if args.risk_sort:
        rows.sort(
            key=lambda r: (r.get("sortino") is not None, r.get("sortino") or 0.0),
            reverse=True,
        )
    if not args.no_snapshot:
        snapshot(rows)
    print(format_chat(rows))

    if args.correlation:
        strategies = [r["strategy"] for r in rows]
        print()
        print(correlation.format_correlation_section(strategies))


if __name__ == "__main__":
    main()
