#!/usr/bin/env python3
"""GATE-TRACKER DASHBOARD — honest forward-paper track-record visibility.

Answers ONE question at a glance, per live strategy:
    "How close is strategy X to having a MEANINGFUL forward paper track record,
     and how far is it really from the milestones that would matter at a
     real-money decision?"

This is READ-ONLY analytics. It opens every DB in SQLite read-only mode
(`file:...?mode=ro`) and NEVER writes to any trading DB. It does not trade,
does not touch strategy code, and does not edit protected files.

=== HONESTY CONTRACT (the whole point) ===
We are validation-rich but track-record-poor: backtested SPX-beaters exist, but
nothing has accumulated enough LIVED forward paper time to graduate. The
bottleneck to real money is elapsed paper time + the visibility to know when a
strategy has earned it. This dashboard is that visibility, and it must never
flatter a 7-day track record as if it were significant:
  * Any realized Sharpe / return computed on < SMALL_SAMPLE_DAYS (20) snapshot
    days is printed WITH a loud "SAMPLE TOO SMALL" warning, never bare.
  * Gate bars are shown as INFORMATIONAL track-record milestones only. The real
    real-money go-live bars are SUSPENDED in explore-phase (GATE.md top banner) —
    nothing here pre-disqualifies or blocks any idea. They answer "where does
    this strategy stand against the bars that WOULD matter later, for visibility."

=== DATA SOURCES (all on disk, read-only) ===
  * tournament.db  `trades`           -> per-strategy real-fill / round-trip counts
  * allocator_paper.db `daily_snapshots`  -> allocator_blend realized path vs SPX
  * xa_tsmom_paper.db  `daily_snapshots`  -> XA TSMOM realized path vs SPY
  * tsmom_blend_paper.db `daily_snapshots`-> tsmom_blend realized path vs SPX

=== SYNTHETIC-ROW FILTER (standing rule — applied before ANY trade metric) ===
  DROP strategy IN ('any','backstop_test','bp2');
  DROP alpaca_order_id IS NULL OR IN ('order-1','ord-seed') OR LENGTH < 20;
  Only status='filled' rows count as real fills.
(Real Alpaca fills carry 36-char UUID order ids; synthetic/seed rows are 7-8
chars or NULL — verified 2026-06-29.)

Usage:
    python3 -m runner.gate_tracker          # print text dashboard to stdout
    python3 -m runner.gate_tracker --md      # also write reports/GATE_TRACKER_<UTC>.md
    python3 -m runner.gate_tracker --md-only # write the md, print only the path
"""
from __future__ import annotations

import argparse
import math
import os
import sqlite3
from datetime import date, datetime, timezone
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------
# Roster (task-canonical live set = the 6 on the main */30 tick line) + the
# 2 standalone trackers (own snapshot DBs, NOT on the main tick line).
# ---------------------------------------------------------------------------
LIVE_STRATEGIES: tuple[str, ...] = (
    "sma_crossover_qqq_regime",
    "sma_crossover_qqq_rth",
    "volume_breakout_qqq",
    "macd_momentum_iwm",
    "tqqq_cot_combo",
    "allocator_blend",
)

# strategy -> (paper-snapshot DB filename, benchmark label). Only these have a
# realized daily-equity path on disk.
PAPER_DBS: dict[str, tuple[str, str]] = {
    "allocator_blend": ("allocator_paper.db", "SPX"),
    "xa_tsmom":        ("xa_tsmom_paper.db", "SPY"),
    "tsmom_blend":     ("tsmom_blend_paper.db", "SPX"),
}

# Standalone trackers (own snapshot DB, separate cron, not on main tick line).
STANDALONE_TRACKERS: tuple[str, ...] = ("xa_tsmom", "tsmom_blend")

# Documented / backtested full-period Sharpe for the drift check (where known).
# allocator_blend full Sharpe ~1.014 (smooth_3mo variant ~1.049 now) per GATE/MEMORY.
DOC_BACKTEST_SHARPE: dict[str, float] = {
    "allocator_blend": 1.014,
}

# ---------------------------------------------------------------------------
# Synthetic-row guard (standing rule).
# ---------------------------------------------------------------------------
SYNTH_STRATEGIES: frozenset[str] = frozenset({"any", "backstop_test", "bp2"})
SYNTH_ORDER_IDS: frozenset[str] = frozenset({"order-1", "ord-seed"})
MIN_ORDER_ID_LEN = 20

# ---------------------------------------------------------------------------
# Honesty / milestone constants.
# ---------------------------------------------------------------------------
SMALL_SAMPLE_DAYS = 20          # < this many snapshot days => Sharpe/return meaningless
TRADING_DAYS_PER_YEAR = 252

# Forward-track milestones (INFORMATIONAL, non-blocking — gates suspended).
SOFT_FLOOR_DAYS = 7             # revised Bar E soft floor (1 week), 2026-05-29
SOFT_FLOOR_TRIPS = 20          # revised Bar E soft floor (20 round-trips)
LEGACY_REF_DAYS = 28            # legacy 4wk reference (relaxed 2026-05-29)
LEGACY_REF_TRIPS = 100         # legacy 100-trip reference (relaxed 2026-05-29)
SHARPE_MILESTONE = 1.0          # informational realized-Sharpe milestone

# "Today" — anchored to the call's UTC date so days-live is reproducible.
TODAY_UTC = datetime.now(timezone.utc).date()


def is_synthetic(strategy: str, order_id: Optional[str]) -> bool:
    """Standing synthetic-row guard. True => exclude before ANY trade metric."""
    if strategy in SYNTH_STRATEGIES:
        return True
    if order_id is None:
        return True
    if order_id in SYNTH_ORDER_IDS:
        return True
    if len(str(order_id)) < MIN_ORDER_ID_LEN:
        return True
    return False


def _connect_ro(path: str) -> Optional[sqlite3.Connection]:
    """Open a SQLite DB strictly read-only. Returns None if the file is absent."""
    if not os.path.exists(path):
        return None
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _parse_iso_date(ts: str) -> Optional[date]:
    """Parse an ISO8601 UTC timestamp (or plain YYYY-MM-DD) to a date."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        try:
            return datetime.strptime(ts[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _annualized_sharpe(daily_rets: list[float]) -> Optional[float]:
    """Annualized daily Sharpe = mean/std * sqrt(252). None if undefined."""
    n = len(daily_rets)
    if n < 2:
        return None
    mean = sum(daily_rets) / n
    var = sum((r - mean) ** 2 for r in daily_rets) / (n - 1)  # sample std
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return (mean / sd) * math.sqrt(TRADING_DAYS_PER_YEAR)


def _max_drawdown(daily_rets: list[float]) -> Optional[float]:
    """Max drawdown (fraction, negative) of the equity path built from daily rets."""
    if not daily_rets:
        return None
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in daily_rets:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        dd = equity / peak - 1.0
        if dd < mdd:
            mdd = dd
    return mdd


def _annualize_cum(cum_ret: float, n_days: int) -> Optional[float]:
    """Annualize a cumulative return over n trading days (CAGR-style)."""
    if n_days <= 0 or cum_ret <= -1.0:
        return None
    return (1.0 + cum_ret) ** (TRADING_DAYS_PER_YEAR / n_days) - 1.0


# ---------------------------------------------------------------------------
# Per-strategy TRADE metrics (from tournament.db, synthetic-filtered).
# ---------------------------------------------------------------------------
def compute_trade_metrics(conn: sqlite3.Connection, strategy: str) -> dict:
    """Real-fill counts + round-trip proxy for one strategy.

    Round-trip proxy DEFINITION: per (symbol), min(buy_fills, sell_fills); summed
    across symbols. A round-trip ~= a buy later closed by a sell, so the number of
    completed pairs on a symbol is bounded by min(buys, sells). This is a cheap,
    honest lower bound on completed round-trips (not exact pairing).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT symbol, side, alpaca_order_id FROM trades "
        "WHERE strategy = ? AND status = 'filled'",
        (strategy,),
    )
    rows = cur.fetchall()

    buys = 0
    sells = 0
    per_symbol: dict[str, list[int]] = {}  # symbol -> [buys, sells]
    first_fill: Optional[date] = None
    last_fill: Optional[date] = None

    # Pull ts separately (kept the first query lean); re-query with ts for dates.
    cur.execute(
        "SELECT symbol, side, alpaca_order_id, ts_utc FROM trades "
        "WHERE strategy = ? AND status = 'filled' ORDER BY ts_utc",
        (strategy,),
    )
    for symbol, side, order_id, ts_utc in cur.fetchall():
        if is_synthetic(strategy, order_id):
            continue
        d = _parse_iso_date(ts_utc)
        if d is not None:
            if first_fill is None or d < first_fill:
                first_fill = d
            if last_fill is None or d > last_fill:
                last_fill = d
        slot = per_symbol.setdefault(symbol, [0, 0])
        if side == "buy":
            buys += 1
            slot[0] += 1
        elif side == "sell":
            sells += 1
            slot[1] += 1

    round_trips = sum(min(b, s) for b, s in per_symbol.values())
    days_live = (TODAY_UTC - first_fill).days if first_fill else 0

    return {
        "fills": buys + sells,
        "buys": buys,
        "sells": sells,
        "round_trips": round_trips,
        "symbols": sorted(per_symbol.keys()),
        "first_fill": first_fill,
        "last_fill": last_fill,
        "days_live": days_live,
    }


# ---------------------------------------------------------------------------
# Realized track record (from a paper-snapshot DB).
# ---------------------------------------------------------------------------
def compute_realized_metrics(db_path: str, bench_label: str) -> Optional[dict]:
    """Realized paper-path stats from a daily_snapshots DB. None if absent/empty."""
    conn = _connect_ro(db_path)
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT date, daily_ret, cum_ret_since_start, spx_daily_ret, "
            "cum_spx_since_start, engine_full_sharpe "
            "FROM daily_snapshots ORDER BY date"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    dates = [r[0] for r in rows]
    daily_rets = [float(r[1]) for r in rows if r[1] is not None]
    spx_daily = [float(r[3]) for r in rows if r[3] is not None]
    n = len(rows)

    last = rows[-1]
    cum_strat = float(last[2]) if last[2] is not None else None
    cum_spx = float(last[4]) if last[4] is not None else None
    engine_sharpe = float(last[5]) if last[5] is not None else None

    realized_sharpe = _annualized_sharpe(daily_rets)
    spx_sharpe = _annualized_sharpe(spx_daily)
    mdd = _max_drawdown(daily_rets)
    ann_strat = _annualize_cum(cum_strat, n) if cum_strat is not None else None
    ann_spx = _annualize_cum(cum_spx, n) if cum_spx is not None else None

    return {
        "db": os.path.basename(db_path),
        "bench_label": bench_label,
        "n_days": n,
        "first_date": dates[0],
        "last_date": dates[-1],
        "cum_strat": cum_strat,
        "cum_spx": cum_spx,
        "ann_strat": ann_strat,
        "ann_spx": ann_spx,
        "realized_sharpe": realized_sharpe,
        "spx_sharpe": spx_sharpe,
        "max_drawdown": mdd,
        "engine_full_sharpe": engine_sharpe,
        "small_sample": n < SMALL_SAMPLE_DAYS,
    }


# ---------------------------------------------------------------------------
# Formatting helpers.
# ---------------------------------------------------------------------------
def _pct(x: Optional[float], digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:+.{digits}f}%"


def _num(x: Optional[float], digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


def _progress(have: float, target: float) -> str:
    """'X of Y (Z%)' progress label, capped display at 100%+ when exceeded."""
    if target <= 0:
        return f"{have:g} of {target:g}"
    pct = have / target * 100.0
    return f"{have:g} of {target:g} ({pct:.0f}%)"


# ---------------------------------------------------------------------------
# Render one strategy block (text). Returns a list of lines.
# ---------------------------------------------------------------------------
def render_strategy_block(name: str, trade: dict, realized: Optional[dict]) -> list[str]:
    L: list[str] = []
    L.append(f"── {name} " + "─" * max(2, 56 - len(name)))

    if trade["fills"] == 0:
        L.append("   ⚠️  NO REAL FILLS yet (no live forward track record to measure).")
    else:
        fr = (f"   Days-live: {trade['days_live']}d "
              f"(first real fill {trade['first_fill']}, last {trade['last_fill']})")
        L.append(fr)
        L.append(f"   Real fills: {trade['fills']}  "
                 f"(buys {trade['buys']} / sells {trade['sells']})  "
                 f"symbols: {', '.join(trade['symbols']) or '—'}")
        L.append(f"   Round-trips (proxy = Σ min(buys,sells) per symbol): "
                 f"{trade['round_trips']}")

    # Realized track record (only where a snapshot DB exists).
    if realized is not None:
        L.append("")
        L.append(f"   Realized paper path  [{realized['db']}]  "
                 f"n={realized['n_days']} snapshot days "
                 f"({realized['first_date']} → {realized['last_date']})")
        if realized["small_sample"]:
            L.append(f"   ⚠️⚠️  SAMPLE TOO SMALL — realized Sharpe/return statistically "
                     f"MEANINGLESS (n={realized['n_days']} < {SMALL_SAMPLE_DAYS}). "
                     f"Numbers shown for tracking only:")
        L.append(f"      cum return:   {_pct(realized['cum_strat'])}   "
                 f"vs {realized['bench_label']} {_pct(realized['cum_spx'])}   "
                 f"(excess {_pct((realized['cum_strat'] or 0) - (realized['cum_spx'] or 0))})")
        L.append(f"      annualized:   {_pct(realized['ann_strat'])}   "
                 f"vs {realized['bench_label']} {_pct(realized['ann_spx'])}")
        L.append(f"      realized Sharpe (ann): {_num(realized['realized_sharpe'])}   "
                 f"(vs {realized['bench_label']} {_num(realized['spx_sharpe'])})")
        L.append(f"      max drawdown (realized path): {_pct(realized['max_drawdown'])}")

        # Backtest-vs-realized drift note.
        doc = DOC_BACKTEST_SHARPE.get(name)
        eng = realized["engine_full_sharpe"]
        if doc is not None or eng is not None:
            parts = []
            if doc is not None:
                parts.append(f"documented backtest ~{doc:.3f}")
            if eng is not None:
                parts.append(f"engine_full_sharpe (this run) {eng:.3f}")
            drift_line = f"   Backtest-vs-realized drift: {', '.join(parts)}"
            rs = realized["realized_sharpe"]
            if rs is not None and eng is not None:
                drift_line += f"; realized {rs:.2f}"
                if realized["small_sample"]:
                    drift_line += "  (drift uninterpretable — sample tiny; NOT an alarm)"
                elif rs < 0.5 * eng:
                    drift_line += "  ⚠️ realized << backtest — investigate cost model / regime / bug"
            L.append(drift_line)

    # Distance-to-graduation (informational, non-blocking).
    L.append("")
    L.append("   Distance-to-graduation (INFORMATIONAL — gates SUSPENDED in explore phase, not a blocker):")
    if trade["fills"] > 0:
        L.append(f"      soak (days):   {_progress(trade['days_live'], SOFT_FLOOR_DAYS)} "
                 f"vs 1wk soft floor   |   {_progress(trade['days_live'], LEGACY_REF_DAYS)} vs legacy 4wk ref")
        L.append(f"      round-trips:   {_progress(trade['round_trips'], SOFT_FLOOR_TRIPS)} "
                 f"vs 20-trip soft floor   |   {_progress(trade['round_trips'], LEGACY_REF_TRIPS)} vs legacy 100-trip ref")
    else:
        L.append("      soak / round-trips: 0 (no real fills yet)")
    if realized is not None and realized["realized_sharpe"] is not None:
        rs = realized["realized_sharpe"]
        tag = "  ⚠️ (n<20 — meaningless)" if realized["small_sample"] else ""
        L.append(f"      realized Sharpe vs {SHARPE_MILESTONE:.1f} milestone: "
                 f"{rs:.2f} / {SHARPE_MILESTONE:.1f}{tag}")
    else:
        L.append(f"      realized Sharpe vs {SHARPE_MILESTONE:.1f} milestone: n/a (no realized snapshot path)")

    return L


def _build_report(strategies: tuple[str, ...]) -> dict:
    """Gather all per-strategy data into a structured dict (testable core)."""
    tconn = _connect_ro(os.path.join(ROOT, "tournament.db"))
    out: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                 "today": TODAY_UTC.isoformat(),
                 "live": [], "trackers": []}
    try:
        for name in strategies:
            trade = (compute_trade_metrics(tconn, name) if tconn is not None
                     else {"fills": 0, "buys": 0, "sells": 0, "round_trips": 0,
                           "symbols": [], "first_fill": None, "last_fill": None,
                           "days_live": 0})
            realized = None
            if name in PAPER_DBS:
                db_file, bench = PAPER_DBS[name]
                realized = compute_realized_metrics(os.path.join(ROOT, db_file), bench)
            out["live"].append({"name": name, "trade": trade, "realized": realized})

        for name in STANDALONE_TRACKERS:
            trade = (compute_trade_metrics(tconn, name) if tconn is not None
                     else {"fills": 0, "buys": 0, "sells": 0, "round_trips": 0,
                           "symbols": [], "first_fill": None, "last_fill": None,
                           "days_live": 0})
            realized = None
            if name in PAPER_DBS:
                db_file, bench = PAPER_DBS[name]
                realized = compute_realized_metrics(os.path.join(ROOT, db_file), bench)
            out["trackers"].append({"name": name, "trade": trade, "realized": realized})
    finally:
        if tconn is not None:
            tconn.close()
    return out


def render_dashboard(report: Optional[dict] = None) -> str:
    """Full text dashboard as a single string."""
    if report is None:
        report = _build_report(LIVE_STRATEGIES)

    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("  GATE-TRACKER DASHBOARD — forward paper track record & distance to graduation")
    lines.append("=" * 78)
    lines.append(f"  Generated: {report['generated_utc']}   (today = {report['today']} UTC)")
    lines.append("")
    lines.append("  HONESTY NOTE: We are validation-rich but track-record-POOR. Nothing here has")
    lines.append("  accumulated enough LIVED forward paper time to be statistically meaningful.")
    lines.append("  A 7-day track record is 7 days. Realized Sharpe/return on < %d snapshot days is"
                 % SMALL_SAMPLE_DAYS)
    lines.append("  flagged MEANINGLESS. Gate bars below are INFORMATIONAL milestones only — the")
    lines.append("  real real-money go-live bars are SUSPENDED in explore phase (GATE.md banner);")
    lines.append("  NOTHING here blocks or pre-disqualifies any idea.")
    lines.append("")
    lines.append("  Round-trip proxy = Σ min(buy_fills, sell_fills) per symbol (a cheap, honest")
    lines.append("  lower bound on completed round-trips — not exact trade pairing).")
    lines.append("")

    lines.append("#" * 78)
    lines.append("  LIVE STRATEGIES (main */30 7-21 tick line)")
    lines.append("#" * 78)
    for item in report["live"]:
        lines.append("")
        lines.extend(render_strategy_block(item["name"], item["trade"], item["realized"]))

    lines.append("")
    lines.append("#" * 78)
    lines.append("  STANDALONE TRACKERS (own snapshot DB, separate cron — NOT on the main tick line)")
    lines.append("#" * 78)
    for item in report["trackers"]:
        lines.append("")
        lines.extend(render_strategy_block(item["name"], item["trade"], item["realized"]))

    lines.append("")
    lines.append("=" * 78)
    lines.append("  END — remember: elapsed forward paper time is the binding constraint, and")
    lines.append("  none of these samples is large enough yet to call statistically significant.")
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown rendering (same numbers, md-friendly).
# ---------------------------------------------------------------------------
def render_markdown(report: Optional[dict] = None) -> str:
    if report is None:
        report = _build_report(LIVE_STRATEGIES)

    M: list[str] = []
    M.append("# GATE-TRACKER DASHBOARD — forward paper track record & distance to graduation")
    M.append("")
    M.append(f"_Generated: {report['generated_utc']} (today = {report['today']} UTC). READ-ONLY analytics._")
    M.append("")
    M.append("> **HONESTY NOTE.** We are validation-rich but track-record-**poor**. Nothing here has "
             "accumulated enough LIVED forward paper time to be statistically meaningful. "
             f"Realized Sharpe/return on **< {SMALL_SAMPLE_DAYS} snapshot days is flagged MEANINGLESS**. "
             "Gate bars are **INFORMATIONAL milestones only** — the real real-money go-live bars are "
             "**SUSPENDED in explore phase** (GATE.md banner); nothing here blocks or pre-disqualifies any idea.")
    M.append("")
    M.append("> **Round-trip proxy** = Σ min(buy_fills, sell_fills) per symbol — a cheap, honest "
             "lower bound on completed round-trips (not exact trade pairing).")
    M.append("")

    def _block_md(item: dict) -> list[str]:
        name = item["name"]
        trade = item["trade"]
        realized = item["realized"]
        B: list[str] = []
        B.append(f"### {name}")
        B.append("")
        if trade["fills"] == 0:
            B.append("- ⚠️ **NO REAL FILLS yet** (no live forward track record to measure).")
        else:
            B.append(f"- **Days-live:** {trade['days_live']}d "
                     f"(first real fill {trade['first_fill']}, last {trade['last_fill']})")
            B.append(f"- **Real fills:** {trade['fills']} "
                     f"(buys {trade['buys']} / sells {trade['sells']}); "
                     f"symbols: {', '.join(trade['symbols']) or '—'}")
            B.append(f"- **Round-trips (proxy):** {trade['round_trips']}")
        if realized is not None:
            B.append(f"- **Realized paper path** (`{realized['db']}`): "
                     f"n={realized['n_days']} snapshot days "
                     f"({realized['first_date']} → {realized['last_date']})")
            if realized["small_sample"]:
                B.append(f"  - ⚠️⚠️ **SAMPLE TOO SMALL — realized Sharpe/return statistically "
                         f"MEANINGLESS (n={realized['n_days']} < {SMALL_SAMPLE_DAYS}).** "
                         f"Numbers shown for tracking only:")
            B.append(f"  - cum return **{_pct(realized['cum_strat'])}** vs "
                     f"{realized['bench_label']} {_pct(realized['cum_spx'])} "
                     f"(excess {_pct((realized['cum_strat'] or 0) - (realized['cum_spx'] or 0))})")
            B.append(f"  - annualized {_pct(realized['ann_strat'])} vs "
                     f"{realized['bench_label']} {_pct(realized['ann_spx'])}")
            B.append(f"  - realized Sharpe (ann) **{_num(realized['realized_sharpe'])}** "
                     f"(vs {realized['bench_label']} {_num(realized['spx_sharpe'])})")
            B.append(f"  - max drawdown (realized path) {_pct(realized['max_drawdown'])}")
            doc = DOC_BACKTEST_SHARPE.get(name)
            eng = realized["engine_full_sharpe"]
            if doc is not None or eng is not None:
                parts = []
                if doc is not None:
                    parts.append(f"documented backtest ~{doc:.3f}")
                if eng is not None:
                    parts.append(f"engine_full_sharpe (this run) {eng:.3f}")
                dl = f"  - drift: {', '.join(parts)}"
                rs = realized["realized_sharpe"]
                if rs is not None and eng is not None:
                    dl += f"; realized {rs:.2f}"
                    if realized["small_sample"]:
                        dl += " (drift uninterpretable — sample tiny; NOT an alarm)"
                    elif rs < 0.5 * eng:
                        dl += " ⚠️ realized << backtest — investigate cost model / regime / bug"
                B.append(dl)
        B.append("- **Distance-to-graduation** (informational, non-blocking — gates suspended):")
        if trade["fills"] > 0:
            B.append(f"  - soak: {_progress(trade['days_live'], SOFT_FLOOR_DAYS)} vs 1wk soft floor; "
                     f"{_progress(trade['days_live'], LEGACY_REF_DAYS)} vs legacy 4wk ref")
            B.append(f"  - round-trips: {_progress(trade['round_trips'], SOFT_FLOOR_TRIPS)} vs 20-trip soft floor; "
                     f"{_progress(trade['round_trips'], LEGACY_REF_TRIPS)} vs legacy 100-trip ref")
        else:
            B.append("  - soak / round-trips: 0 (no real fills yet)")
        if realized is not None and realized["realized_sharpe"] is not None:
            rs = realized["realized_sharpe"]
            tag = " ⚠️ (n<20 — meaningless)" if realized["small_sample"] else ""
            B.append(f"  - realized Sharpe vs {SHARPE_MILESTONE:.1f} milestone: {rs:.2f} / {SHARPE_MILESTONE:.1f}{tag}")
        else:
            B.append(f"  - realized Sharpe vs {SHARPE_MILESTONE:.1f} milestone: n/a (no realized snapshot path)")
        B.append("")
        return B

    M.append("## Live strategies (main */30 tick line)")
    M.append("")
    for item in report["live"]:
        M.extend(_block_md(item))
    M.append("## Standalone trackers (own snapshot DB, separate cron — not on the main tick line)")
    M.append("")
    for item in report["trackers"]:
        M.extend(_block_md(item))
    M.append("---")
    M.append("_Reminder: elapsed forward paper time is the binding constraint; none of these "
             "samples is large enough yet to call statistically significant._")
    M.append("")
    return "\n".join(M)


def write_markdown_report(report: Optional[dict] = None) -> str:
    """Write the markdown dashboard to reports/GATE_TRACKER_<UTC>.md. Returns path."""
    if report is None:
        report = _build_report(LIVE_STRATEGIES)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    reports_dir = os.path.join(ROOT, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    out_path = os.path.join(reports_dir, f"GATE_TRACKER_{ts}.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="GATE-tracker forward-paper dashboard (read-only).")
    ap.add_argument("--md", action="store_true",
                    help="also write a markdown report to reports/GATE_TRACKER_<UTC>.md")
    ap.add_argument("--md-only", action="store_true",
                    help="write the markdown report and print ONLY its path (no text dashboard)")
    args = ap.parse_args(argv)

    report = _build_report(LIVE_STRATEGIES)

    if args.md_only:
        path = write_markdown_report(report)
        print(path)
        return 0

    print(render_dashboard(report))

    if args.md:
        path = write_markdown_report(report)
        print("")
        print(f"[markdown report written] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
