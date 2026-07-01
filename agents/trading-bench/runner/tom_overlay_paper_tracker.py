"""TOM (Turn-of-Month) leverage-concentration OVERLAY — PAPER-CLOCK tracker (out-of-band, NO live orders).

WHY THIS EXISTS
---------------
A production harness (reports/TOM_OVERLAY_PRODUCTION_HARNESS_20260630T050146Z.md, verdict GO for
paper at the conservative shelf config) found that concentrating EXTRA leveraged exposure into the
turn-of-month window BEATS buy-&-hold on RAW RETURN across all four indices, in both OOS cuts, with
the +1-bar canary passing on every variant, at only +0.1 to +0.7pp of extra max drawdown in the
tradeable 3x-ETF form. Cyrus (2026-06-30) explicitly loosened the leverage rail: ETF-form leverage
on paper is now the agent's call (the live book already runs TQQQ/UPRO/SOXL). So this clock tracks
the shelf config forward on a paper account.

  SHELF CONFIG (exactly what this clock marks):
    Base exposure : 1.0x the index EVERY day (keep beta -- never go flat).
    TOM window    : last pre=2 + first post=3 trading days of the month-turn
                    (PURE calendar date mask, NO price lookahead; ~23.8% of days).
    Tilt          : +0.5 EXTRA index exposure during the window (conservative start).
    Tradeable form: rotate w = tilt/(k-1) = 0.25 of the book into a 3x ETF during TOM,
                    back out after. UPRO (3x) for the S&P book, TQQQ (3x) for the Nasdaq book.
                    (The 3x form is unambiguously right: same target exposure as the 2x form at
                    a QUARTER of the turnover -> +0.1-0.7pp DD vs the 2x form's +4.6-6.0pp.)
    Cost          : 2bps one-way on every rotation into/out of the ETF (~5 round-trips/month).

WHAT IT LOGS (per trading day, for BOTH the S&P book and the Nasdaq book)
------------------------------------------------------------------------
  * the TOM-OVERLAY book (1x base + the TOM 3x-ETF tilt), AND
  * the B&H 1x control for the SAME index (the exact thing the overlay must beat on raw return),
plus SPX, so the forward clock measures DIRECTLY whether the TOM tilt adds raw return over plain
buy-&-hold on the path actually observed. The headline claim is a RAW-RETURN claim, so the
overlay-vs-B&H raw gap is the number this clock exists to accumulate.

WHY THE FORWARD CLOCK (honest caveats the harness itself flagged)
-----------------------------------------------------------------
The modern-ETF statistical significance is WEAK (Welch t ~1.1-1.5 on SPY/QQQ; only the deep
1970s/1980s ^GSPC/^NDX history is properly significant), and the edge is leverage-amplified
BETA-TIMING, not alpha with hedge value -- the ETF-form DD cost is understated by a benign
post-2009 OOS window that contains no 2000/2008 bear inside a TOM window. A forward paper clock is
the only way to earn (or falsify) confidence that the calendar tilt keeps paying its leverage cost
going forward. So we log it daily and read the raw-return gap over B&H as it accumulates.

This is out-of-band, modeled VERBATIM on runner/crash_sleeve_paper_tracker.py. It runs NO live
orders, touches NONE of the live runner/risk/engine files, and writes ONLY to a SIDE DB. It reuses
reports/_tom_overlay_harness.py verified primitives DIRECTLY (load / daily_returns / align_returns /
tom_mask / overlay_etf / stats) -- ZERO return-math reimplementation. Every number this clock marks
comes from the SAME library that produced the verdict/harness reports.

NO-LOOKAHEAD (the make-or-break -- proven by the harness's +1-bar canary)
-------------------------------------------------------------------------
The TOM window is a PURE FUNCTION of the ordered calendar date axis (tom_mask takes only the date
list; no price input). The decision for trading date D ("is D in the TOM window?") is known before D
opens -- it is literally the date -- so applying the tilt to D's realized return is leak-free. The
ETF leg uses the ETF's OWN realized adjclose return on D (align_returns keys returns to the ETF's
consecutive bars; a missing ETF bar falls back to pure 1x -- never invents an ETF return). A future
price move cannot change whether D was a TOM day. The harness's +1-bar canary (shift the mask to the
WRONG day -> Sharpe degrades) confirmed this is a calendar TIMING edge, not same-bar leakage.

CUM-SINCE-START SEMANTICS
-------------------------
cum_*_since_start columns are each the cumulative RETURN compounded over the daily returns THIS
tracker has LOGGED, i.e. from the paper clock's FIRST row forward -- NOT the full backtest equity.
On the first run that is just today's single daily return; it accumulates honestly thereafter.
(Full-backtest cum/Sharpe is in the harness report; this DB is the forward clock.)

Entry points (importable + CLI):
  snapshot_today(db_path) -> dict       # log today's overlay+B&H snapshot for both books (idempotent)
  paper_clock_stats(db_path)            # forward stats over logged rows (since inception)
  clock_staleness(db_path)              # silent-clock guard (exit 3 if >=2 trading days behind)

DB: workspace root tom_overlay_paper.db (default).
Run: python3 runner/tom_overlay_paper_tracker.py                  # snapshot + print stats
     python3 runner/tom_overlay_paper_tracker.py --stats          # just print running stats
     python3 runner/tom_overlay_paper_tracker.py --check-staleness # staleness JSON; exit 3 if stale
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(WORKSPACE / "tom_overlay_paper.db")

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# ---- The RECOMMENDED SHELF CONFIG (harness: TOM_OVERLAY_PRODUCTION_HARNESS_20260630T050146Z.md) --
HARNESS_REPORT = "reports/TOM_OVERLAY_PRODUCTION_HARNESS_20260630T050146Z.md"
PRE = 2                    # last `pre` trading days of the month in the TOM window
POST = 3                   # first `post` trading days of the month in the TOM window
SHELF_TILT = 0.5           # EXTRA index exposure during the window (conservative start)
K_MULT = 3.0               # 3x ETF (UPRO / TQQQ) -- the preferred tradeable form
ETF_WEIGHT = SHELF_TILT / (K_MULT - 1.0)   # = 0.25 of book rotated into the 3x ETF during TOM
COST_BPS = 2.0             # one-way rotation cost (already applied inside overlay_etf)
TRADING_DAYS = 252

# Two books tracked side by side; each has a 1x base index + its 3x ETF leg.
# (SPY/UPRO = conservative headline +0.1pp DD; QQQ/TQQQ = bigger raw lift, bigger DD.)
BOOKS = [
    {"key": "spx", "base": "SPY", "etf": "UPRO"},
    {"key": "ndx", "base": "QQQ", "etf": "TQQQ"},
]

# All symbols we must keep fresh before marking a new day.
_REFRESH_SYMBOLS = ["^GSPC", "SPY", "UPRO", "QQQ", "TQQQ"]


# --------------------------------------------------------------------------- #
# DB schema  (side DB; per book: overlay + B&H control, plus a shared SPX stream)
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,
    in_tom_window INTEGER,

    spx_overlay_daily_ret REAL,
    cum_spx_overlay_since_start REAL,
    spx_bh_daily_ret REAL,
    cum_spx_bh_since_start REAL,

    ndx_overlay_daily_ret REAL,
    cum_ndx_overlay_since_start REAL,
    ndx_bh_daily_ret REAL,
    cum_ndx_bh_since_start REAL,

    spx_index_daily_ret REAL,
    cum_spx_index_since_start REAL,

    spx_overlay_full_sharpe REAL,
    ndx_overlay_full_sharpe REAL,
    created_at TEXT
);
"""


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Bar refresh (VERBATIM pattern from runner/crash_sleeve_paper_tracker.py -- critical so
# the index + ETF caches aren't stale and the newest paper-clock row doesn't log a spurious
# flat return). Resilient: a per-symbol fetch failure falls back to the cache, never fatal.
# --------------------------------------------------------------------------- #
def _refresh_bars(symbols):
    from runner import daily_bars_cache as dbc
    status = {}
    for sym in symbols:
        try:
            bars = dbc.get_daily(sym, refresh=True)
            status[sym] = bars[-1]["date"] if bars else "empty"
        except Exception as exc:  # noqa: BLE001 - intentionally broad; never fatal
            try:
                bars = dbc.get_daily(sym)
                status[sym] = "%s(cached, refresh failed: %s)" % (
                    bars[-1]["date"] if bars else "empty", type(exc).__name__)
            except Exception:
                status[sym] = "unavailable: %s" % type(exc).__name__
    return status


# --------------------------------------------------------------------------- #
# Run the SHELF overlay over ALL history for one book; return latest-day marks.
# Reuses reports/_tom_overlay_harness.py primitives DIRECTLY (zero return-math reimpl).
# --------------------------------------------------------------------------- #
def _compute_book(base_sym, etf_sym):
    """Build the TOM-overlay book + its B&H 1x control over ALL shared history, and read off
    the latest day. Uses the ETF's own start as the span floor (adjclose: decay+fees+embedded
    financing baked in). Returns (mark_date, overlay_daily, bh_daily, overlay_full_sharpe,
    in_tom_flag, n_days, window)."""
    from reports._tom_overlay_harness import (
        load, daily_returns, align_returns, tom_mask, overlay_etf, stats,
    )

    base_series = load(base_sym)          # ascending [(date, adjclose)]
    etf_series = load(etf_sym)
    if not base_series or not etf_series:
        raise RuntimeError("tom_overlay_paper: empty series for %s/%s" % (base_sym, etf_sym))

    # ETF-form span floor: only dates the ETF actually trades (UPRO 2009+, TQQQ 2010+).
    etf_start = etf_series[0][0]
    sub_series = [(d, p) for d, p in base_series if d >= etf_start]
    if len(sub_series) < 3:
        raise RuntimeError("tom_overlay_paper: too few overlapping bars for %s/%s" % (base_sym, etf_sym))

    sub_dates = [d for d, _ in sub_series]
    sub_rets = daily_returns(sub_series)                     # 1x index returns, i>=1
    etf_d2r = align_returns(sub_dates, etf_series)           # {date: ETF daily ret}
    mask = tom_mask(sub_dates, PRE, POST, shift=0)           # pure-calendar TOM flags

    overlay = overlay_etf(sub_dates, sub_rets, mask, SHELF_TILT, etf_d2r, K_MULT)  # [(date, ret)]
    bh = [(d, r) for d, r in sub_rets]                       # B&H 1x control, same path

    # latest marked day
    mark_date = overlay[-1][0] if overlay else sub_dates[-1]
    overlay_daily = overlay[-1][1] if overlay else 0.0
    bh_daily = bh[-1][1] if bh else 0.0
    _, overlay_sharpe, _, _ = stats(overlay)

    # in-TOM flag for the mark date is the LAST mask entry (sub_dates[-1] == mark_date's date
    # by construction; overlay is indexed from sub_dates[1:] so its last date == sub_dates[-1]).
    in_tom = bool(mask[-1]) if mask else False

    return {
        "mark_date": mark_date.isoformat() if isinstance(mark_date, dt.date) else str(mark_date),
        "overlay_daily_ret": overlay_daily,
        "bh_daily_ret": bh_daily,
        "overlay_full_sharpe": overlay_sharpe,
        "in_tom": in_tom,
        "n_days": len(sub_dates),
        "window": [sub_dates[0].isoformat(), sub_dates[-1].isoformat()],
    }


def compute_tom_overlay_state():
    """Re-run the SHELF overlay for BOTH books + the SPX index over ALL history and return the
    latest day's decomposed state. Refreshes bars first so no book marks a stale flat day.

    Returns dict with per-book overlay/B&H daily returns + full-backtest Sharpe, the shared SPX
    index daily return, the mark date, the in-TOM flag, and diagnostics.
    """
    from reports._tom_overlay_harness import load, daily_returns

    refresh_status = _refresh_bars(_REFRESH_SYMBOLS)
    print("[tom_overlay_paper] bar refresh: %s" % json.dumps(refresh_status), flush=True)

    spx = _compute_book(BOOKS[0]["base"], BOOKS[0]["etf"])
    ndx = _compute_book(BOOKS[1]["base"], BOOKS[1]["etf"])

    # Shared SPX index daily return (^GSPC), marked on its own latest bar.
    gspc = load("^GSPC")
    gspc_rets = daily_returns(gspc)
    spx_index_daily = gspc_rets[-1][1] if gspc_rets else 0.0

    # Consistency check: both books should mark the same latest closed session; if a book's ETF
    # cache lags a day, we still log (idempotent on date) but flag the divergence for the log.
    mark_date = spx["mark_date"]
    date_note = "ok"
    if spx["mark_date"] != ndx["mark_date"]:
        # mark against the EARLIER of the two so we never claim a day a book hasn't closed.
        mark_date = min(spx["mark_date"], ndx["mark_date"])
        date_note = "book mark dates diverge (spx=%s ndx=%s) -> marking %s" % (
            spx["mark_date"], ndx["mark_date"], mark_date)

    return {
        "mark_date": mark_date,
        "date_note": date_note,
        "in_tom_window": 1 if (spx["in_tom"] or ndx["in_tom"]) else 0,

        "spx_overlay_daily_ret": spx["overlay_daily_ret"],
        "spx_bh_daily_ret": spx["bh_daily_ret"],
        "spx_overlay_full_sharpe": spx["overlay_full_sharpe"],

        "ndx_overlay_daily_ret": ndx["overlay_daily_ret"],
        "ndx_bh_daily_ret": ndx["bh_daily_ret"],
        "ndx_overlay_full_sharpe": ndx["overlay_full_sharpe"],

        "spx_index_daily_ret": spx_index_daily,

        "n_days_spx": spx["n_days"],
        "n_days_ndx": ndx["n_days"],
        "window_spx": spx["window"],
        "window_ndx": ndx["window"],
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def snapshot_today(db_path=DEFAULT_DB):
    """Compute today's overlay+B&H state for both books and log an idempotent daily snapshot.

    Idempotent on `date` (UNIQUE): if the latest closed trading day is already logged, this is a
    no-op (returns the existing cum + inserted=0). All cum_*_since_start columns are compounded
    over ALL logged daily returns (this row inclusive), i.e. paper-clock-inception cumulative.
    """
    state = compute_tom_overlay_state()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn(db_path)
    inserted = 0
    try:
        existing = conn.execute(
            "SELECT id FROM daily_snapshots WHERE date=?", (state["mark_date"],)
        ).fetchone()

        if existing is None:
            prior = conn.execute(
                "SELECT cum_spx_overlay_since_start, cum_spx_bh_since_start, "
                "cum_ndx_overlay_since_start, cum_ndx_bh_since_start, "
                "cum_spx_index_since_start FROM daily_snapshots ORDER BY date DESC LIMIT 1"
            ).fetchone()

            def _prior(col):
                return prior[col] if prior and prior[col] is not None else 0.0

            def _grow(prior_cum, daily):
                return (1.0 + prior_cum) * (1.0 + daily) - 1.0

            cum_spx_ov = _grow(_prior("cum_spx_overlay_since_start"), state["spx_overlay_daily_ret"])
            cum_spx_bh = _grow(_prior("cum_spx_bh_since_start"), state["spx_bh_daily_ret"])
            cum_ndx_ov = _grow(_prior("cum_ndx_overlay_since_start"), state["ndx_overlay_daily_ret"])
            cum_ndx_bh = _grow(_prior("cum_ndx_bh_since_start"), state["ndx_bh_daily_ret"])
            cum_spx_ix = _grow(_prior("cum_spx_index_since_start"), state["spx_index_daily_ret"])

            conn.execute(
                """INSERT INTO daily_snapshots
                   (date, in_tom_window,
                    spx_overlay_daily_ret, cum_spx_overlay_since_start,
                    spx_bh_daily_ret, cum_spx_bh_since_start,
                    ndx_overlay_daily_ret, cum_ndx_overlay_since_start,
                    ndx_bh_daily_ret, cum_ndx_bh_since_start,
                    spx_index_daily_ret, cum_spx_index_since_start,
                    spx_overlay_full_sharpe, ndx_overlay_full_sharpe, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    state["mark_date"], state["in_tom_window"],
                    state["spx_overlay_daily_ret"], cum_spx_ov,
                    state["spx_bh_daily_ret"], cum_spx_bh,
                    state["ndx_overlay_daily_ret"], cum_ndx_ov,
                    state["ndx_bh_daily_ret"], cum_ndx_bh,
                    state["spx_index_daily_ret"], cum_spx_ix,
                    state["spx_overlay_full_sharpe"], state["ndx_overlay_full_sharpe"], ts,
                ),
            )
            conn.commit()
            inserted = 1
            state["cum_spx_overlay_since_start"] = cum_spx_ov
            state["cum_spx_bh_since_start"] = cum_spx_bh
            state["cum_ndx_overlay_since_start"] = cum_ndx_ov
            state["cum_ndx_bh_since_start"] = cum_ndx_bh
            state["cum_spx_index_since_start"] = cum_spx_ix
        else:
            row = conn.execute(
                "SELECT cum_spx_overlay_since_start, cum_spx_bh_since_start, "
                "cum_ndx_overlay_since_start, cum_ndx_bh_since_start, "
                "cum_spx_index_since_start FROM daily_snapshots WHERE date=?",
                (state["mark_date"],),
            ).fetchone()
            state["cum_spx_overlay_since_start"] = row["cum_spx_overlay_since_start"]
            state["cum_spx_bh_since_start"] = row["cum_spx_bh_since_start"]
            state["cum_ndx_overlay_since_start"] = row["cum_ndx_overlay_since_start"]
            state["cum_ndx_bh_since_start"] = row["cum_ndx_bh_since_start"]
            state["cum_spx_index_since_start"] = row["cum_spx_index_since_start"]

        n_rows = conn.execute("SELECT COUNT(*) FROM daily_snapshots").fetchone()[0]
    finally:
        conn.close()
    state["inserted"] = inserted
    state["rows_logged"] = n_rows
    return state


def paper_clock_stats(db_path=DEFAULT_DB):
    """Running stats over ALL forward rows this tracker has logged (since inception).

    These rows ARE the honest forward paper clock (one per trading day this tracker has run). For
    each book we report the forward cum of the overlay vs its B&H 1x control (the RAW-RETURN gap
    the overlay must positively accumulate) + the overlay's forward marked-at-close Sharpe. SPX
    index cum is the shared reference. tom_window_days says how often the tilt was actually engaged
    on the path observed.

    Returns: start_date, n_days, per-book {overlay_cum_pct, bh_cum_pct, overlay_vs_bh_pp,
    overlay_sharpe_since_start}, spx_index_cum_pct, tom_window_days, tom_window_pct.
    """
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT date, in_tom_window, "
            "spx_overlay_daily_ret, spx_bh_daily_ret, "
            "ndx_overlay_daily_ret, ndx_bh_daily_ret, "
            "spx_index_daily_ret FROM daily_snapshots ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"n_days": 0, "note": "no forward rows logged yet"}

    def _col(name):
        return [r[name] for r in rows if r[name] is not None]

    def _cum(vals):
        c = 1.0
        for r in vals:
            c *= (1.0 + r)
        return c - 1.0

    def _sharpe(vals):
        m = len(vals)
        if m < 2:
            return 0.0
        mean = sum(vals) / m
        var = sum((r - mean) ** 2 for r in vals) / (m - 1)
        sd = math.sqrt(var)
        return (mean / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0

    spx_ov = _col("spx_overlay_daily_ret")
    spx_bh = _col("spx_bh_daily_ret")
    ndx_ov = _col("ndx_overlay_daily_ret")
    ndx_bh = _col("ndx_bh_daily_ret")
    spx_ix = _col("spx_index_daily_ret")
    n = len(spx_ov)

    cum_spx_ov = _cum(spx_ov)
    cum_spx_bh = _cum(spx_bh)
    cum_ndx_ov = _cum(ndx_ov)
    cum_ndx_bh = _cum(ndx_bh)
    cum_spx_ix = _cum(spx_ix)

    tom_days = sum(1 for r in rows if r["in_tom_window"])
    return {
        "start_date": rows[0]["date"],
        "n_days": n,
        "spx_book": {
            "base_etf": "SPY/UPRO(3x)",
            "overlay_cum_pct": round(cum_spx_ov * 100, 4),
            "bh_cum_pct": round(cum_spx_bh * 100, 4),
            "overlay_vs_bh_pp": round((cum_spx_ov - cum_spx_bh) * 100, 4),
            "overlay_sharpe_since_start": round(_sharpe(spx_ov), 4),
        },
        "ndx_book": {
            "base_etf": "QQQ/TQQQ(3x)",
            "overlay_cum_pct": round(cum_ndx_ov * 100, 4),
            "bh_cum_pct": round(cum_ndx_bh * 100, 4),
            "overlay_vs_bh_pp": round((cum_ndx_ov - cum_ndx_bh) * 100, 4),
            "overlay_sharpe_since_start": round(_sharpe(ndx_ov), 4),
        },
        "spx_index_cum_pct": round(cum_spx_ix * 100, 4),
        "tom_window_days": tom_days,
        "tom_window_pct": round(100.0 * tom_days / len(rows), 4),
    }


# --------------------------------------------------------------------------- #
# Staleness self-check (silent-clock guard) -- VERBATIM pattern from
# crash_sleeve_paper_tracker.py / allocator_paper_tracker.py.
#
# The dangerous failure mode is NOT rc!=0 (that already alarms) -- it is the tracker running
# rc=0 yet logging NO new row for several trading days (stale cached bar, or the engine silently
# returning an old mark_date). This guard compares the latest logged DB date against the latest
# CLOSED SPX bar (the same ^GSPC cache the overlay marks the index against) and reports how many
# trading days behind the clock is. 0 = current; 1 = normal intraday transient; >=2 = alarm (exit 3).
# --------------------------------------------------------------------------- #
GSPC_CACHE = str(WORKSPACE / "data_cache" / "yahoo" / "_GSPC_parsed.json")


def _spx_trading_dates():
    """Authoritative trading-day calendar = the dates present in the cached ^GSPC daily series
    (ascending). Same series the index stream marks against, so the staleness count can never
    diverge from what the tracker would log."""
    try:
        with open(GSPC_CACHE) as fh:
            bars = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for b in bars:
        d = b.get("date") if isinstance(b, dict) else None
        if d:
            out.append(d)
    out.sort()
    return out


def clock_staleness(db_path=DEFAULT_DB):
    """How far behind the latest CLOSED SPX session the paper clock is.

    Returns dict: last_logged, latest_closed_bar, trading_days_behind, rows_logged, stale, note.
    """
    cal = _spx_trading_dates()
    latest_bar = cal[-1] if cal else None

    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT date FROM daily_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
        total = conn.execute("SELECT COUNT(*) AS n FROM daily_snapshots").fetchone()["n"]
    finally:
        conn.close()

    last_logged = row["date"] if row else None

    if last_logged is None:
        behind = None
        note = "no rows logged yet -- clock not started"
    elif latest_bar is None:
        behind = None
        note = "^GSPC cache unreadable -- cannot assess staleness"
    else:
        behind = sum(1 for d in cal if last_logged < d <= latest_bar)
        if behind == 0:
            note = "current (last logged == latest closed SPX bar %s)" % latest_bar
        elif behind == 1:
            note = ("1 trading day behind (latest closed bar %s not yet captured; "
                    "normal intraday -- self-heals next slot)" % latest_bar)
        else:
            note = ("STALE: %d trading days behind (last logged %s, latest closed bar "
                    "%s) -- paper clock has a hole" % (behind, last_logged, latest_bar))

    return {
        "last_logged": last_logged,
        "latest_closed_bar": latest_bar,
        "trading_days_behind": behind,
        "rows_logged": total,
        "stale": (behind is not None and behind >= 2),
        "note": note,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    import argparse
    p = argparse.ArgumentParser(description="TOM (turn-of-month) overlay paper-clock tracker")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--stats", action="store_true", help="only print running stats")
    p.add_argument("--check-staleness", action="store_true",
                   help="print clock staleness JSON; exit 3 if >=2 trading days behind")
    args = p.parse_args()

    if args.stats:
        st = paper_clock_stats(db_path=args.db)
        print(json.dumps(st, indent=2))
        return

    if args.check_staleness:
        st = clock_staleness(db_path=args.db)
        print(json.dumps(st, indent=2))
        sys.exit(3 if st.get("stale") else 0)

    state = snapshot_today(db_path=args.db)
    print("[tom_overlay_paper] shelf config: pre=%d/post=%d tilt=%.2f -> %dx ETF w=%.3f / cost %.1fbps (harness %s)" % (
        PRE, POST, SHELF_TILT, int(K_MULT), ETF_WEIGHT, COST_BPS, HARNESS_REPORT))
    print("[tom_overlay_paper] books: SPY/UPRO(3x) + QQQ/TQQQ(3x); base 1x every day, +tilt only in TOM window")
    if state.get("date_note") and state["date_note"] != "ok":
        print("[tom_overlay_paper] NOTE: %s" % state["date_note"])
    print("[tom_overlay_paper] mark_date=%s inserted=%d rows_logged=%d" % (
        state["mark_date"], state["inserted"], state["rows_logged"]))
    _stale = clock_staleness(db_path=args.db)
    print("[tom_overlay_paper] staleness: %s" % _stale["note"])
    print("[tom_overlay_paper] TOM window today: %s" % (
        "ENGAGED (extra 3x tilt on)" if state["in_tom_window"] else "off (1x base only)"))
    print("[tom_overlay_paper] mark_date daily return  SPX-book: overlay %.4f%% | B&H %.4f%%   NDX-book: overlay %.4f%% | B&H %.4f%%   SPX-idx %.4f%%" % (
        state["spx_overlay_daily_ret"] * 100, state["spx_bh_daily_ret"] * 100,
        state["ndx_overlay_daily_ret"] * 100, state["ndx_bh_daily_ret"] * 100,
        state["spx_index_daily_ret"] * 100))
    print("[tom_overlay_paper] cum since paper-clock start  SPX-book: overlay %.4f%% | B&H %.4f%%   NDX-book: overlay %.4f%% | B&H %.4f%%   SPX-idx %.4f%%" % (
        state["cum_spx_overlay_since_start"] * 100, state["cum_spx_bh_since_start"] * 100,
        state["cum_ndx_overlay_since_start"] * 100, state["cum_ndx_bh_since_start"] * 100,
        state["cum_spx_index_since_start"] * 100))
    print("[tom_overlay_paper] engine full backtest Sharpe (overlay, drift check)  SPX-book %.3f | NDX-book %.3f" % (
        state["spx_overlay_full_sharpe"], state["ndx_overlay_full_sharpe"]))
    print("[tom_overlay_paper] backtest windows  SPX-book %s (%d days) | NDX-book %s (%d days)" % (
        state["window_spx"], state["n_days_spx"], state["window_ndx"], state["n_days_ndx"]))
    print("")
    fwd = paper_clock_stats(db_path=args.db)
    print("[tom_overlay_paper] forward paper-clock stats (since inception):")
    print(json.dumps(fwd, indent=2))


if __name__ == "__main__":
    main()