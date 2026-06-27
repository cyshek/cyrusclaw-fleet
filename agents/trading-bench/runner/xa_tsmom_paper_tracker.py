"""Cross-asset 12-1 absolute (time-series) momentum — STANDALONE PAPER TRACKER.

PAPER ONLY. No real money. This is the forward clock for the validated
cross-asset 12-1 TSMOM book {SPY, TLT, GLD, DBC, UUP}. It is the slow-monthly
analog of runner/allocator_paper_tracker.py: a side-DB forward record that
marks the model's CURRENT target weights every trading day and accumulates the
book's realized daily P&L vs SPY since paper-clock inception.

WHY A STANDALONE TRACKER (and not a mutation parent)
----------------------------------------------------
The validated gate verdict (reports/XA_TSMOM_12_1_GATE_20260626T164538Z.md):
  FULL +222.7% / Sharpe 0.75 / maxDD -24.9%   (SPY +641% / 0.78 / -46.3%)
  OOS  +112.7% / Sharpe 1.14 / maxDD -10.6%   (SPY +213% / 0.90 / -23.9%)
  Robust plateau across 6-1/9-1/12-1/12-0 (all OOS Sharpe > SPY 0.90).
  2022 rate-shock: -1.06% vs SPY -18.18%. D+1-lag audited, 2bps/side, never fully cash.
It LOSES to SPY on raw return but wins OOS Sharpe with half the drawdown -> a
risk-orthogonal diversifier. A slow monthly cross-asset allocator cannot be a
single-name mutation parent (the parent profiler scores on 60-90d windows; a
12-month lookback profiles as zero trades, and the parent pool rejects
decide_xsec books). The CORRECT venue for it is exactly this: a standalone paper
tracker, same as allocator_blend. (The single-name cross-asset DNA went into the
gene pool separately via trend_follow_uup.)

WEIGHT / RETURN SOURCE -- REUSED, NOT REIMPLEMENTED (no-lookahead by construction)
---------------------------------------------------------------------------------
We import the VALIDATED driver reports/_xa_tsmom_driver.py and call its
run_backtest(L, K) DIRECTLY over ALL price history. We re-implement ZERO
momentum / weighting / cost math here. The driver is lookahead-safe by
construction: the signal at month-end M (price[t-1]/price[t-13]-1) sets weights
HELD during M+1; it only ever reads fully-closed month-end bars. So the weights
this tracker records as "hold today" are exactly the model's honest readout
(records[-1]["weights"] = the most recent month-end decision's EW-of-positive
book). The forward daily P&L is computed close-to-close from the adjusted-close
cache on those held weights, so the paper clock and the backtest can never
silently diverge.

WHAT IT LOGS (idempotent daily snapshot -> xa_tsmom_paper.db)
------------------------------------------------------------
For each trading date logged:
  * weights JSON       : current month-end target weights (per leg) + cash
  * held               : JSON list of legs currently held (positive 12-1 mom)
  * daily_ret          : book's realized close-to-close return ON `date`, using
                         the held weights (cash leg earns 0)
  * cum_ret_since_start: book cumulative return over logged rows (paper inception)
  * spx_daily_ret      : SPY realized close-to-close return ON `date`
  * cum_spx_since_start: SPY cumulative return over logged rows
  * engine_full_sharpe : validated full-period backtest Sharpe at this run (drift check)
A daily mark (not monthly) is intentional: weights are monthly-rebalanced but we
want a daily forward equity curve vs SPY for an honest paper-clock Sharpe. The
weights only change when the calendar month rolls (the engine picks up the new
month-end decision automatically on the next run).

FAIL-SAFES
----------
  * engine / import error -> raise (the cron wrapper logs it); we never write a
    bogus row. A transient Yahoo hiccup is absorbed by _refresh_bars (falls back
    to cache, never crashes).
  * a leg with no visible price on `date` -> that leg contributes 0 to the day's
    return (HOLD; never invents a mark).
  * idempotent: re-running the same day UPDATES that date's row, never duplicates.

NOT YET SCHEDULED until main/cron wires it (mirrors allocator_blend's launch).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.daily_bars_cache import get_daily  # noqa: E402

UNIVERSE = ["SPY", "TLT", "GLD", "DBC", "UUP"]
BENCH = "SPY"
TRADING_DAYS = 252
LOOKBACK_MONTHS = 12
SKIP_MONTHS = 1
DEFAULT_DB = str(WORKSPACE / "xa_tsmom_paper.db")
DRIVER_PATH = WORKSPACE / "reports" / "_xa_tsmom_driver.py"


# --------------------------------------------------------------------------- #
# DB schema
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,                 -- trading date being marked (engine last close)
    decision_month TEXT,              -- month-end whose weights are currently held (YYYY-MM)
    weights TEXT,                     -- JSON {sym: weight} current target book
    cash_w REAL,                      -- residual cash weight
    held TEXT,                        -- JSON list of legs currently held (positive 12-1 mom)
    daily_ret REAL,                   -- book realized return ON `date` (close-to-close)
    cum_ret_since_start REAL,         -- book cumulative return over logged rows (paper inception)
    spx_daily_ret REAL,               -- SPY realized return ON `date` (close-to-close)
    cum_spx_since_start REAL,         -- SPY cumulative return over logged rows
    engine_full_sharpe REAL,          -- validated full-period backtest Sharpe at this run (drift check)
    created_at TEXT                   -- when this row was written (UTC ISO8601)
);
"""


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Load the validated driver (reused verbatim; zero math reimplemented here)
# --------------------------------------------------------------------------- #
def _load_driver():
    spec = importlib.util.spec_from_file_location("_xa_tsmom_driver", str(DRIVER_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError("xa_tsmom_paper: cannot load validated driver at %s" % DRIVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _refresh_bars(symbols: List[str]) -> Dict[str, str]:
    """Force a re-fetch of each leg's daily bars so the latest close is present
    before we compute today's snapshot. Resilient: a per-symbol fetch failure
    falls back to whatever is cached (never crash the daily tracker over a
    transient Yahoo hiccup)."""
    from runner import daily_bars_cache as dbc
    status: Dict[str, str] = {}
    for sym in symbols:
        ok = False
        try:
            bars = dbc.get_daily(sym, refresh=True)
            status[sym] = bars[-1]["date"] if bars else "empty"
            ok = True
        except Exception as exc:  # noqa: BLE001 - intentionally broad; never fatal
            status[sym] = "refresh_failed:%s" % type(exc).__name__
        if not ok:
            try:
                bars = dbc.get_daily(sym)
                status[sym] = "%s(cached)" % (bars[-1]["date"] if bars else "empty")
            except Exception:  # noqa: BLE001
                status[sym] = "unavailable"
    return status


def _daily_adjclose_map(symbol: str) -> Dict[str, float]:
    """date(YYYY-MM-DD) -> adjclose for one symbol (adjclose if present else close)."""
    out: Dict[str, float] = {}
    for b in get_daily(symbol):
        d = b.get("date")
        px = b.get("adjclose")
        if px is None:
            px = b.get("close")
        if isinstance(d, str) and px is not None:
            try:
                pxf = float(px)
            except (TypeError, ValueError):
                continue
            if pxf > 0:
                out[d] = pxf
    return out


def _common_sorted_dates(maps: Dict[str, Dict[str, float]]) -> List[str]:
    """Sorted trading dates common to every leg in `maps` (so a day's book return
    is computed only when every held-eligible leg has a mark)."""
    if not maps:
        return []
    sets = [set(m.keys()) for m in maps.values()]
    common = set.intersection(*sets) if sets else set()
    return sorted(common)


# --------------------------------------------------------------------------- #
# Compute current state from the validated engine + the realized daily marks.
# --------------------------------------------------------------------------- #
def compute_state() -> Dict:
    """Re-run the validated driver over ALL history; return the latest held
    weights plus the realized close-to-close daily return for the most recent
    common trading date.

    Returns dict with: mark_date, decision_month, weights, cash_w, held,
    daily_return, spx_daily_return, engine_full_sharpe.
    """
    refresh_status = _refresh_bars(UNIVERSE)
    print("[xa_tsmom_paper] bar refresh: %s" % json.dumps(refresh_status), flush=True)

    drv = _load_driver()
    res = drv.run_backtest(LOOKBACK_MONTHS, SKIP_MONTHS)
    records = res.get("records") or []
    if not records:
        raise RuntimeError("xa_tsmom_paper: validated engine produced no records")
    last = records[-1]
    weights: Dict[str, float] = {s: float(last["weights"].get(s, 0.0)) for s in UNIVERSE}
    cash_w = float(last.get("w_cash", 0.0))
    held = list(last.get("held") or [])
    decision_month = str(last.get("decision_month") or "")

    # Full-period continuous Sharpe of the validated monthly book (drift check).
    eng_sharpe = _engine_full_sharpe(drv, res)

    # Realized close-to-close daily return for the latest common trading date,
    # using the CURRENT held weights (cash leg earns 0). SPY benchmark on the
    # same date. We need the two most recent COMMON dates across the held legs
    # (and SPY) to difference.
    legs_for_ret = [s for s in UNIVERSE if weights.get(s, 0.0) > 0.0]
    px_maps = {s: _daily_adjclose_map(s) for s in set(legs_for_ret) | {BENCH}}
    common = _common_sorted_dates(px_maps) if px_maps else []
    mark_date: Optional[str] = None
    daily_return = 0.0
    spx_daily_return = 0.0
    if len(common) >= 2:
        d_prev, d_now = common[-2], common[-1]
        mark_date = d_now
        # book return = sum_leg w_leg * (px_now/px_prev - 1); cash earns 0
        book = 0.0
        for s in legs_for_ret:
            m = px_maps[s]
            p0, p1 = m.get(d_prev), m.get(d_now)
            if p0 and p1 and p0 > 0:
                book += weights[s] * (p1 / p0 - 1.0)
        daily_return = book
        bm = px_maps[BENCH]
        bp0, bp1 = bm.get(d_prev), bm.get(d_now)
        if bp0 and bp1 and bp0 > 0:
            spx_daily_return = bp1 / bp0 - 1.0
    elif len(common) == 1:
        mark_date = common[-1]  # first ever mark: no prior day to difference -> 0/0

    return {
        "mark_date": mark_date,
        "decision_month": decision_month,
        "weights": weights,
        "cash_w": cash_w,
        "held": held,
        "daily_return": daily_return,
        "spx_daily_return": spx_daily_return,
        "engine_full_sharpe": eng_sharpe,
    }


def _engine_full_sharpe(drv, res) -> float:
    """Full-period continuous Sharpe of the validated monthly net-return series
    (monthly mean/std * sqrt(12)). Reuses the driver's own _sharpe if present,
    else computes it the same way."""
    monthly_rets = [r["net_ret"] for r in res.get("records") or []]
    fn = getattr(drv, "_sharpe", None)
    if callable(fn):
        try:
            return float(fn(monthly_rets))
        except Exception:  # noqa: BLE001
            pass
    n = len(monthly_rets)
    if n < 2:
        return 0.0
    mean = sum(monthly_rets) / n
    var = sum((r - mean) ** 2 for r in monthly_rets) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(12.0)


# --------------------------------------------------------------------------- #
# Snapshot (idempotent per date)
# --------------------------------------------------------------------------- #
def snapshot_today(db_path: str = DEFAULT_DB) -> Dict:
    """Compute current state and write/refresh today's row. Idempotent on `date`.
    cum_*_since_start are recomputed over all logged rows so the paper-clock
    inception is the first logged row."""
    st = compute_state()
    mark_date = st["mark_date"]
    if not mark_date:
        raise RuntimeError("xa_tsmom_paper: no common trading date to mark yet")

    conn = _get_conn(db_path)
    try:
        cur = conn.cursor()
        # Prior cumulative (over rows strictly BEFORE this date) so cum compounds.
        cur.execute(
            "SELECT cum_ret_since_start, cum_spx_since_start FROM daily_snapshots "
            "WHERE date < ? ORDER BY date DESC LIMIT 1", (mark_date,))
        prev = cur.fetchone()
        prev_cum = float(prev["cum_ret_since_start"]) if prev else 0.0
        prev_cum_spx = float(prev["cum_spx_since_start"]) if prev else 0.0

        # Is this row the paper-clock INCEPTION (no earlier-dated row exists)?
        # Must be based on whether any row with date < mark_date exists, NOT on
        # COUNT(*): an idempotent re-run of the inception day would otherwise see
        # count>=1 and overwrite its mandatory 0-return with a real day return.
        # The inception row has no prior logged close to difference against -> 0.
        is_first = (prev is None)
        day_ret = 0.0 if is_first else float(st["daily_return"])
        day_spx = 0.0 if is_first else float(st["spx_daily_return"])

        cum = (1.0 + prev_cum) * (1.0 + day_ret) - 1.0
        cum_spx = (1.0 + prev_cum_spx) * (1.0 + day_spx) - 1.0

        cur.execute(
            """INSERT INTO daily_snapshots
               (date, decision_month, weights, cash_w, held, daily_ret,
                cum_ret_since_start, spx_daily_ret, cum_spx_since_start,
                engine_full_sharpe, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 decision_month=excluded.decision_month,
                 weights=excluded.weights,
                 cash_w=excluded.cash_w,
                 held=excluded.held,
                 daily_ret=excluded.daily_ret,
                 cum_ret_since_start=excluded.cum_ret_since_start,
                 spx_daily_ret=excluded.spx_daily_ret,
                 cum_spx_since_start=excluded.cum_spx_since_start,
                 engine_full_sharpe=excluded.engine_full_sharpe,
                 created_at=excluded.created_at""",
            (mark_date, st["decision_month"], json.dumps(st["weights"]),
             st["cash_w"], json.dumps(st["held"]), day_ret, cum, day_spx,
             cum_spx, st["engine_full_sharpe"],
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "mark_date": mark_date,
        "decision_month": st["decision_month"],
        "weights": st["weights"],
        "cash_w": st["cash_w"],
        "held": st["held"],
        "daily_ret": day_ret,
        "cum_ret_since_start": cum,
        "spx_daily_ret": day_spx,
        "cum_spx_since_start": cum_spx,
        "engine_full_sharpe": st["engine_full_sharpe"],
        "is_first_row": is_first,
    }


# --------------------------------------------------------------------------- #
# Read-side: forward paper-clock stats
# --------------------------------------------------------------------------- #
def paper_clock_stats(db_path: str = DEFAULT_DB) -> Dict:
    """Forward paper-clock summary from logged rows: span, cumulative book vs
    SPY, and a daily-return Sharpe (annualized sqrt(252)) over the logged
    forward period. This is the FORWARD honest record, distinct from the
    full-backtest Sharpe."""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT date, daily_ret, cum_ret_since_start, spx_daily_ret, "
            "cum_spx_since_start FROM daily_snapshots ORDER BY date ASC").fetchall()
    finally:
        conn.close()
    if not rows:
        return {"rows_logged": 0, "note": "no snapshots yet"}

    book_rets = [float(r["daily_ret"]) for r in rows[1:]]  # skip inception 0-row
    spx_rets = [float(r["spx_daily_ret"]) for r in rows[1:]]

    def _sharpe(xs: List[float]) -> float:
        n = len(xs)
        if n < 2:
            return 0.0
        mean = sum(xs) / n
        var = sum((x - mean) ** 2 for x in xs) / (n - 1)
        if var <= 0:
            return 0.0
        return (mean / math.sqrt(var)) * math.sqrt(TRADING_DAYS)

    last = rows[-1]
    return {
        "rows_logged": len(rows),
        "first_date": rows[0]["date"],
        "last_date": last["date"],
        "cum_book_ret": float(last["cum_ret_since_start"]),
        "cum_spx_ret": float(last["cum_spx_since_start"]),
        "fwd_book_sharpe": _sharpe(book_rets),
        "fwd_spx_sharpe": _sharpe(spx_rets),
        "n_return_days": len(book_rets),
    }


def current_target_weights(db_path: str = DEFAULT_DB) -> Dict:
    """The most recently logged target book (weights + cash + held + decision month)."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT date, decision_month, weights, cash_w, held FROM daily_snapshots "
            "ORDER BY date DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    if not row:
        return {"note": "no snapshots yet"}
    return {
        "as_of": row["date"],
        "decision_month": row["decision_month"],
        "weights": json.loads(row["weights"]),
        "cash_w": float(row["cash_w"]),
        "held": json.loads(row["held"]),
    }


def _spx_trading_dates() -> List[str]:
    return [b["date"] for b in get_daily(BENCH)]


def clock_staleness(db_path: str = DEFAULT_DB) -> Dict:
    """Compare the latest logged DB date against the latest SPY trading date so a
    wedged cron is visible. behind_days = SPY dates strictly after the last
    logged row."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT date FROM daily_snapshots ORDER BY date DESC LIMIT 1").fetchone()
        rows_logged = conn.execute(
            "SELECT COUNT(*) AS c FROM daily_snapshots").fetchone()["c"]
    finally:
        conn.close()
    spx_dates = _spx_trading_dates()
    latest_spx = spx_dates[-1] if spx_dates else None
    if not row:
        return {"rows_logged": 0, "latest_logged": None,
                "latest_spx": latest_spx, "behind_days": None}
    latest_logged = row["date"]
    behind = sum(1 for d in spx_dates if d > latest_logged)
    return {
        "rows_logged": rows_logged,
        "latest_logged": latest_logged,
        "latest_spx": latest_spx,
        "behind_days": behind,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description="Cross-asset 12-1 TSMOM paper tracker")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--stats", action="store_true", help="print forward paper-clock stats and exit")
    p.add_argument("--staleness", action="store_true", help="print clock staleness and exit")
    p.add_argument("--check-staleness", action="store_true",
                   help="exit 3 if the clock has not written a row in >4 trading days (silent-clock guard)")
    p.add_argument("--weights", action="store_true", help="print current target weights and exit")
    args = p.parse_args()

    if args.stats:
        print(json.dumps(paper_clock_stats(db_path=args.db), indent=2))
        return
    if args.staleness:
        print(json.dumps(clock_staleness(db_path=args.db), indent=2))
        return
    if getattr(args, "check_staleness", False):
        st = clock_staleness(db_path=args.db)
        print(json.dumps(st))
        behind = st.get("behind_days")
        # rc=3 => stale clock (cron likely stopped). >4 trading days behind, or
        # no rows logged at all. Mirrors tsmom_blend / allocator staleness guard.
        if st.get("rows_logged", 0) == 0 or (isinstance(behind, int) and behind > 4):
            sys.exit(3)
        return
    if args.weights:
        print(json.dumps(current_target_weights(db_path=args.db), indent=2))
        return

    snap = snapshot_today(db_path=args.db)
    print(json.dumps(snap, indent=2))
    stale = clock_staleness(db_path=args.db)
    print("[xa_tsmom_paper] staleness: %s" % json.dumps(stale), flush=True)
    fwd = paper_clock_stats(db_path=args.db)
    print("[xa_tsmom_paper] forward: %s" % json.dumps(fwd), flush=True)


if __name__ == "__main__":
    main()