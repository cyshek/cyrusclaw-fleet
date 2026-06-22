"""Allocator-blend PAPER-CLOCK tracker (out-of-band, NO live Alpaca orders).

WHY THIS EXISTS
---------------
The inv-vol allocator blend (TQQQ vol-target sleeve + sector-rotation top-2 sleeve)
cleared the bench's gate on backtest: full Sharpe 1.014 / OOS 1.147 / maxDD -23.9%,
beating BOTH sleeves standalone (report: reports/ALLOCATOR_BLEND_20260621.md). It is
the bench's first real multi-sleeve allocator and the first candidate worth a real
paper clock toward real money.

BUT it CANNOT be wired to the live runner faithfully: the blend is a continuously
multi-asset-reweighted book (TQQQ + up to 2 of SPY/QQQ/GLD/TLT, inverse-vol tilted),
and runner.py today supports only BUY-notional + CLOSE-to-flat per (strategy,symbol)
-- no partial-trim-while-long, no clean multi-symbol attribution per strategy. Fake-
wiring it into a runner that can't execute it would produce a dishonest divergence
between the logged paper record and the model (exactly the failure the TQQQ adapter
docstring warns against).

So this is PATH A (BACKLOG P1, fast): a backtest-FORWARD daily tracker, modeled on
the Polymarket paper tracker (runner/polymarket_tracker.py). Each day it:
  1. Re-runs the VALIDATED blend engine by calling _allocator_blend_tests.build_sleeves()
     + _allocator_blend_tests.blend_portfolio() DIRECTLY (no reimplementation of sleeve
     logic), which themselves reuse the validated run_backtest_voltarget +
     run_sector_rotation engines over ALL available price history through the latest close.
  2. Reads off the LATEST day's: blend daily return, SPX daily return, sleeve target
     weights, rotation holdings, and the running blend / SPX cumulative returns since
     the paper clock's first row.
  3. Logs an idempotent daily snapshot row to a SIDE DB (allocator_paper.db). The
     forward record (rows from the day this tracker starts running onward) is the
     HONEST paper clock -- the model's realized daily P&L on the path actually observed,
     marked at each day's close, with zero live orders.

NO-LOOKAHEAD
------------
Every number comes from the validated engines, which are lookahead-safe by
construction (gate/vol computed on data <= D; rotation ranked on prior month-end).
The tracker only ever reads the LAST fully-closed day's realized blend return. It
cannot peek forward: when it runs on date T, the latest engine bar is the last close
available from the cache, and we log that day's already-realized return.

CUM-SINCE-START SEMANTICS
-------------------------
`cum_ret_since_start` / `cum_spx_since_start` are the blend's / SPX's cumulative
return compounded over the daily returns this tracker has LOGGED, i.e. from the
paper clock's FIRST row forward -- NOT the full backtest equity. On the very first
run that is just today's single daily return; it accumulates honestly thereafter.
(The full-backtest equity / Sharpe is in the report; this DB is the forward clock.)

Entry points (importable + CLI):
  snapshot_today(db_path) -> dict     # log today's blend snapshot (idempotent)
  paper_clock_stats(db_path)          # running stats over forward rows (since inception)
  current_target_weights(db_path)     # latest decomposed per-underlying weights

DB: workspace root allocator_paper.db (default).
Run: python3 runner/allocator_paper_tracker.py            # snapshot + print stats
     python3 runner/allocator_paper_tracker.py --stats    # just print running stats
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(WORKSPACE / "allocator_paper.db")

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# The promoted headline blend config: inverse-vol (63d) risk-parity weighting.
# Keep in sync with the report / MEMORY (the promoted candidate).
BLEND_NAME = "invvol_63d"
BLEND_COST_BPS = 2.0               # inter-sleeve monthly rebalance cost (one-way)
VOL_LOOKBACK_DAYS = 63             # inverse-vol trailing window
ROT_ASSETS = ["SPY", "QQQ", "GLD", "TLT"]
TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# DB schema  (matches the launch spec exactly)
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,                 -- the trading date being marked (engine last close)
    w_tqqq REAL,                      -- top-level weight on the TQQQ vol-target sleeve
    w_rot REAL,                       -- top-level weight on the rotation sleeve
    rot_holds TEXT,                   -- JSON list of the rotation sleeve's current top-2 holds
    daily_ret REAL,                   -- blend's realized return ON `date` (close-to-close)
    cum_ret_since_start REAL,         -- blend cumulative return over logged rows (paper-clock inception)
    spx_daily_ret REAL,               -- SPX realized return ON `date` (close-to-close)
    cum_spx_since_start REAL,         -- SPX cumulative return over logged rows
    engine_full_sharpe REAL,          -- blend full-period backtest Sharpe at this run (drift check)
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
# Run the validated blend engine and extract the latest day's state.
# Reuses _allocator_blend_tests.build_sleeves() + blend_portfolio() DIRECTLY.
# --------------------------------------------------------------------------- #
def _annualized_vol(returns: List[float]) -> float:
    """Population-stdev annualized — matches _allocator_blend_tests.annualized_vol."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def _refresh_bars(symbols: List[str]) -> Dict[str, str]:
    """Force a re-fetch of each symbol's daily bars so the latest close is present
    before we compute today's snapshot. Critical for the SPX benchmark: the ^GSPC
    cache can lag the tradeable ETFs by a day, which would otherwise log a spurious
    flat SPX return on the newest paper-clock row. Resilient: a per-symbol fetch
    failure is logged and we fall back to whatever is already cached (never crash
    the daily tracker over a transient Yahoo hiccup).
    """
    from runner import daily_bars_cache as dbc
    status: Dict[str, str] = {}
    for sym in symbols:
        try:
            bars = dbc.get_daily(sym, refresh=True)
            status[sym] = bars[-1]["date"] if bars else "empty"
        except Exception as e:  # noqa: BLE001 - intentionally broad; never fatal
            try:
                bars = dbc.get_daily(sym)  # fall back to cache
                status[sym] = "%s(cached, refresh failed: %s)" % (
                    bars[-1]["date"] if bars else "empty", type(e).__name__)
            except Exception:
                status[sym] = "unavailable: %s" % type(e).__name__
    return status


def compute_blend_state() -> Dict:
    """Re-run the validated sleeves + blend over ALL history and return the latest
    day's decomposed state.

    Calls _allocator_blend_tests.build_sleeves() and blend_portfolio() directly so the
    paper tracker can NEVER silently diverge from the validated backtest. We do not
    re-implement any sleeve logic here — we only (a) form the same inv-vol target-weight
    function used by the validated 'invvol_63d' blend, and (b) read off the latest day.

    Returns dict with: mark_date, daily_return, spx_daily_return, w_tqqq, w_rot,
    voltarget_sleeve_w, rot_holdings, target_weights, engine_full_sharpe, window, n_days.
    """
    # Import here (not at module top) so the module imports cheaply and a heavy/stale
    # engine import can't wedge module load (mirrors the polymarket tracker pattern).
    import _allocator_blend_tests as ab

    # Refresh the key symbols FIRST so the latest close (esp. ^GSPC, which lags the
    # tradeable ETFs) is in the cache before build_sleeves() reads it. Otherwise the
    # newest paper-clock row would log a spurious flat SPX return.
    refresh_status = _refresh_bars(["^GSPC", "TQQQ", "QQQ", "SPY", "GLD", "TLT"])
    print("[allocator_paper] bar refresh: %s" % json.dumps(refresh_status), flush=True)

    # build_sleeves() reproduces BOTH validated sleeves on the common (TQQQ-inception)
    # calendar and hands back date-aligned daily-return streams for TQQQ, rotation, AND
    # SPX. We reuse it verbatim — zero sleeve-logic duplication.
    S = ab.build_sleeves()
    dates: List[str] = S["common_dates"]
    tqqq_r: List[float] = S["tqqq_r"]
    rot_r: List[float] = S["rot_r"]
    spx_r: List[float] = S["spx_r"]
    if not dates:
        raise RuntimeError("allocator_paper: empty common calendar between sleeves")

    sleeves = [tqqq_r, rot_r]  # index 0 = TQQQ vol-target sleeve, 1 = rotation sleeve

    # Inverse-vol (63d) target-weight function — IDENTICAL to the invvol_wfn used in
    # _allocator_blend_tests.main() for the promoted 'invvol_63d' blend. Lookahead-safe:
    # only uses sleeve returns STRICTLY BEFORE the month-open index `idx`.
    def invvol_wfn(idx: int) -> List[float]:
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - VOL_LOOKBACK_DAYS)
        v0 = _annualized_vol(sleeves[0][lo:idx])
        v1 = _annualized_vol(sleeves[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0 / v0, 1.0 / v1
        s = iv0 + iv1
        return [iv0 / s, iv1 / s]

    # Run the validated blend engine DIRECTLY to get the running equity + full Sharpe.
    blend = ab.blend_portfolio(dates, sleeves, lambda i: invvol_wfn(i),
                               blend_cost_bps=BLEND_COST_BPS,
                               vol_lookback_days=VOL_LOOKBACK_DAYS)
    blend_eq = blend["equity"]                 # base 1.0 at dates[0]
    blend_full_sharpe = blend["stats"]["sharpe"]

    # Latest fully-closed day = the last common date.
    mark_date = dates[-1]
    last_idx = len(dates) - 1
    daily_return = (blend_eq[-1] / blend_eq[-2] - 1.0) if len(blend_eq) >= 2 else 0.0
    spx_daily_return = spx_r[-1] if spx_r else 0.0

    # --- Top-level sleeve weights currently in effect (latest month-open inv-vol) ---
    # The blend snaps to target at each month-open and drifts intramonth; the honest
    # "model says hold this" readout is the on-target weight a rebalance today would set,
    # i.e. invvol_wfn evaluated at the latest month-open index <= last_idx.
    month_open: List[int] = []
    seen = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open.append(i)
    latest_mo = month_open[-1] if month_open else last_idx
    w_tqqq, w_rot = invvol_wfn(latest_mo)

    # --- Re-run the two underlying engines once more to read the per-day internals we
    # need for decomposition: the vol-target sleeve's OWN internal TQQQ weight on
    # mark_date, and the rotation sleeve's current top-2 holdings. build_sleeves() does
    # not return these, so we call the engines directly (same configs build_sleeves uses).
    from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
        VolTargetParams, run_backtest_voltarget,
    )
    from _sigimprove_tests import run_sector_rotation

    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0))
    vt_dates = vt["strategy"]["dates"]
    vt_weights = vt["strategy"]["weights"]     # weights[k] is the held weight OVER vt_dates[k+1]
    vt_w_map = {vt_dates[i + 1]: vt_weights[i] for i in range(len(vt_weights))}
    voltarget_sleeve_w = float(vt_w_map.get(mark_date, 0.0))

    rot = run_sector_rotation(ROT_ASSETS, bench="^GSPC", cost_bps=2.0,
                              start="2005-01-01", hold_top=2, lookback_months=3)
    # Rotation holdings log is under key "pos_log": [{"date", "holds": [...], ...}].
    rot_pos_log = rot.get("pos_log", []) or []
    cur_holds: List[str] = []
    for h in rot_pos_log:
        if h.get("date", "") <= mark_date:
            cur_holds = list(h.get("holds", []))
        else:
            break  # pos_log is chronological; stop once past mark_date

    # --- Decomposed per-underlying portfolio weights ---
    #   TQQQ leg:     w_tqqq * voltarget_sleeve_w  (remainder of that sleeve sits in cash)
    #   rotation leg: w_rot split equally across the current top-2 holds
    target_weights: Dict[str, float] = {}
    tqqq_port_w = w_tqqq * voltarget_sleeve_w
    if tqqq_port_w > 1e-9:
        target_weights["TQQQ"] = round(tqqq_port_w, 4)
    if cur_holds:
        per = w_rot / len(cur_holds)
        for a in cur_holds:
            target_weights[a] = round(target_weights.get(a, 0.0) + per, 4)
    implied_cash_w = round(1.0 - sum(target_weights.values()), 4)

    return {
        "mark_date": mark_date,
        "daily_return": daily_return,
        "spx_daily_return": spx_daily_return,
        "w_tqqq": round(w_tqqq, 4),
        "w_rot": round(w_rot, 4),
        "voltarget_sleeve_w": round(voltarget_sleeve_w, 4),
        "rot_holdings": cur_holds,
        "target_weights": target_weights,
        "implied_cash_w": implied_cash_w,
        "engine_full_sharpe": blend_full_sharpe,
        "n_days": len(dates),
        "window": [dates[0], dates[-1]],
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def snapshot_today(db_path: str = DEFAULT_DB) -> Dict:
    """Compute today's blend state and log an idempotent daily snapshot.

    Idempotent on `date` (UNIQUE): if the latest closed trading day is already logged,
    this is a no-op (returns the existing state + inserted=0). cum_*_since_start are
    compounded over ALL logged daily returns (this row's date inclusive), i.e. the
    paper-clock-inception cumulative.
    """
    state = compute_blend_state()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn(db_path)
    inserted = 0
    try:
        existing = conn.execute(
            "SELECT id FROM daily_snapshots WHERE date=?", (state["mark_date"],)
        ).fetchone()

        if existing is None:
            # Compound cum-since-start = prior cum * (1 + today's ret). Prior cum is the
            # most recent row's cum_ret_since_start (1.0-based product of (1+ret)); if no
            # prior row, this is the first day so cum = (1 + today's ret).
            prior = conn.execute(
                "SELECT cum_ret_since_start, cum_spx_since_start FROM daily_snapshots "
                "ORDER BY date DESC LIMIT 1"
            ).fetchone()
            prior_blend = prior["cum_ret_since_start"] if prior and prior["cum_ret_since_start"] is not None else 0.0
            prior_spx = prior["cum_spx_since_start"] if prior and prior["cum_spx_since_start"] is not None else 0.0
            # cum stored as cumulative RETURN (e.g. 0.05 = +5%); growth factor = 1 + cum.
            cum_blend = (1.0 + prior_blend) * (1.0 + state["daily_return"]) - 1.0
            cum_spx = (1.0 + prior_spx) * (1.0 + state["spx_daily_return"]) - 1.0

            conn.execute(
                """INSERT INTO daily_snapshots
                   (date, w_tqqq, w_rot, rot_holds, daily_ret, cum_ret_since_start,
                    spx_daily_ret, cum_spx_since_start, engine_full_sharpe, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    state["mark_date"], state["w_tqqq"], state["w_rot"],
                    json.dumps(state["rot_holdings"]), state["daily_return"], cum_blend,
                    state["spx_daily_return"], cum_spx, state["engine_full_sharpe"], ts,
                ),
            )
            conn.commit()
            inserted = 1
            state["cum_ret_since_start"] = cum_blend
            state["cum_spx_since_start"] = cum_spx
        else:
            row = conn.execute(
                "SELECT cum_ret_since_start, cum_spx_since_start FROM daily_snapshots WHERE date=?",
                (state["mark_date"],),
            ).fetchone()
            state["cum_ret_since_start"] = row["cum_ret_since_start"]
            state["cum_spx_since_start"] = row["cum_spx_since_start"]

        n_rows = conn.execute("SELECT COUNT(*) FROM daily_snapshots").fetchone()[0]
    finally:
        conn.close()
    state["inserted"] = inserted
    state["rows_logged"] = n_rows
    return state


def paper_clock_stats(db_path: str = DEFAULT_DB) -> Dict:
    """Running stats over ALL forward rows this tracker has logged (since inception).

    These rows ARE the honest forward paper clock (one per trading day this tracker has
    run). `sharpe_since_start` is the forward, out-of-sample, marked-at-close Sharpe from
    the logged daily returns — distinct from the backtest Sharpe in the report.

    Returns: start_date, n_days, cum_ret_pct, spx_cum_ret_pct, sharpe_since_start,
             current_w_tqqq, current_w_rot, current_rot_holds.
    """
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT date, w_tqqq, w_rot, rot_holds, daily_ret, spx_daily_ret "
            "FROM daily_snapshots ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"n_days": 0, "note": "no forward rows logged yet"}

    blend_rets = [r["daily_ret"] for r in rows if r["daily_ret"] is not None]
    spx_rets = [r["spx_daily_ret"] for r in rows if r["spx_daily_ret"] is not None]
    n = len(blend_rets)

    cum = 1.0
    for r in blend_rets:
        cum *= (1.0 + r)
    spx_cum = 1.0
    for r in spx_rets:
        spx_cum *= (1.0 + r)

    if n >= 2:
        mean = sum(blend_rets) / n
        var = sum((r - mean) ** 2 for r in blend_rets) / (n - 1)
        sd = math.sqrt(var)
        sharpe = (mean / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    else:
        sharpe = 0.0

    last = rows[-1]
    return {
        "start_date": rows[0]["date"],
        "n_days": n,
        "cum_ret_pct": round((cum - 1.0) * 100, 4),
        "spx_cum_ret_pct": round((spx_cum - 1.0) * 100, 4),
        "sharpe_since_start": round(sharpe, 4),
        "current_w_tqqq": last["w_tqqq"],
        "current_w_rot": last["w_rot"],
        "current_rot_holds": json.loads(last["rot_holds"]) if last["rot_holds"] else [],
    }


def current_target_weights(db_path: str = DEFAULT_DB) -> Dict:
    """Latest logged sleeve split + rotation holds (lightweight read for callers)."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"note": "no rows logged yet"}
    return {
        "date": row["date"],
        "w_tqqq": row["w_tqqq"],
        "w_rot": row["w_rot"],
        "rot_holds": json.loads(row["rot_holds"]) if row["rot_holds"] else [],
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Allocator-blend paper-clock tracker")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--stats", action="store_true", help="only print running stats")
    args = p.parse_args()

    if args.stats:
        st = paper_clock_stats(db_path=args.db)
        print(json.dumps(st, indent=2))
        return

    state = snapshot_today(db_path=args.db)
    print("[allocator_paper] mark_date=%s inserted=%d rows_logged=%d" % (
        state["mark_date"], state["inserted"], state["rows_logged"]))
    print("[allocator_paper] sleeve split: TQQQ-voltarget %.1f%% / rotation %.1f%%" % (
        state["w_tqqq"] * 100, state["w_rot"] * 100))
    print("[allocator_paper] decomposed target weights: %s (cash %.1f%%)" % (
        json.dumps(state["target_weights"]), state["implied_cash_w"] * 100))
    print("[allocator_paper] rotation holds: %s | voltarget internal TQQQ w=%.2f" % (
        state["rot_holdings"], state["voltarget_sleeve_w"]))
    print("[allocator_paper] mark_date daily return: blend %.4f%% | SPX %.4f%%" % (
        state["daily_return"] * 100, state["spx_daily_return"] * 100))
    print("[allocator_paper] cum since paper-clock start: blend %.4f%% | SPX %.4f%%" % (
        state["cum_ret_since_start"] * 100, state["cum_spx_since_start"] * 100))
    print("[allocator_paper] engine full backtest Sharpe (drift check) = %.3f" % state["engine_full_sharpe"])
    print("[allocator_paper] backtest window %s (%d days)" % (state["window"], state["n_days"]))
    print("")
    fwd = paper_clock_stats(db_path=args.db)
    print("[allocator_paper] forward paper-clock stats (since inception):")
    print(json.dumps(fwd, indent=2))


if __name__ == "__main__":
    main()