"""Crash-insurance REGIME-GATED 3rd-sleeve PAPER-CLOCK tracker (out-of-band, NO live orders).

WHY THIS EXISTS
---------------
A probe (reports/CRASH_SLEEVE_PROBE_20260630T164742Z.md, verdict GO-WITH-CAP) found that
adding a REGIME-GATED cash hedge as a 3rd sleeve to the LIVE inverse-vol 2-sleeve allocator
blend (the same blend tracked by runner/allocator_paper_tracker.py) cuts OOS maxDD WITHOUT
the static-haven raw-return bleed -- but ONLY with a DEPTH-based trigger:

  CONSERVATIVE "VALUE PICK" CONFIG (what this clock tracks as PRIMARY):
    trailing-drawdown breach <= -10%  ->  engage a CASH hedge at 15% weight (wh15),
    taken PROPORTIONALLY from the 2 risk sleeves so they keep their inv-vol ratio.
    OOS maxDD -20.02% -> -18.84%, raw 968% -> 914% (-54pp giveup), +1-bar canary CLEAN.

  The maximized wh25 point (OOS maxDD -18.05%, -89pp raw) exists, but the report explicitly
  says size the LIVE engaged-weight CONSERVATIVELY at 15% -- the -10% threshold is fitted on
  n=1 OOS crash regime (2022). So this tracker uses wh15 (15%), NOT wh25.

  Hedge = CASH (0 return when engaged -- the cleanest de-risk; NOT the haven basket, NOT TLT
  which was REJECTED for deepening DD in rate-shock bears). Trigger is PAST-ONLY: SPX trailing
  drawdown from running peak, evaluated through idx-1 (strictly before the rebalance). Engages
  ~22% of OOS days.

THE POINT OF THE FORWARD CLOCK
------------------------------
The backtest win is OOS-DD-only and rests on a SINGLE crash regime (2022). A forward paper
clock accumulates NEW crash regimes the backtest could not fit -- the only way to earn real
confidence in the gate (or to falsify it). So this tracker logs, every trading day, BOTH:
  * the GATED 3-sleeve blend (2 risk sleeves + the regime-gated cash hedge), AND
  * the UNGATED live 2-sleeve baseline (identical to allocator_paper_tracker.py),
so we can measure FORWARD, directly, whether the gate actually helps on the path observed.

This is out-of-band PATH-A, modeled VERBATIM on runner/allocator_paper_tracker.py. It runs NO
live orders, touches NO live runner/risk files, and writes ONLY to a SIDE DB. It reuses
_allocator_blend_tests.build_sleeves() + blend_portfolio() DIRECTLY -- ZERO sleeve-math
reimplementation. The 2 risk sleeves use the SAME inv-vol(63d) + smooth_3mo base weighting as
the live tracker; the gate adds a 3rd cash sleeve (all-0.0 return stream) whose engaged weight
is decided by the past-only regime flag.

NO-LOOKAHEAD (the make-or-break -- verified by the +1-bar canary in the probe)
------------------------------------------------------------------------------
Every weight decision at a month-open index idx uses ONLY dates[:idx] / sleeves[k][:idx]
(blend_portfolio's hard past-only guard). The REGIME FLAG at idx is computed from an SPX price
index reconstructed by compounding spx_r, with the running-peak drawdown evaluated through
idx-1 (STRICTLY before the rebalance). The cash sleeve return is identically 0.0. The hedge
weight chosen at idx is applied only to FORWARD returns. A future SPX move cannot change the
current month's flag or weights. The probe's +1-bar canary proved the -10%-DD gate survives
lagged information -- this file implements the SAME past-only gate, with no same-bar peeking.

CUM-SINCE-START SEMANTICS
-------------------------
cum_gated_since_start / cum_baseline_since_start / cum_spx_since_start are each the
cumulative RETURN compounded over the daily returns this tracker has LOGGED, i.e. from the
paper clock's FIRST row forward -- NOT the full backtest equity. On the first run that is just
today's single daily return; it accumulates honestly thereafter. (Full-backtest equity / Sharpe
is in the report; this DB is the forward clock.)

Entry points (importable + CLI):
  snapshot_today(db_path) -> dict       # log today's gated+baseline snapshot (idempotent)
  paper_clock_stats(db_path)            # forward stats over logged rows (since inception)
  clock_staleness(db_path)              # silent-clock guard (exit 3 if >=2 trading days behind)

DB: workspace root crash_sleeve_paper.db (default).
Run: python3 runner/crash_sleeve_paper_tracker.py                  # snapshot + print stats
     python3 runner/crash_sleeve_paper_tracker.py --stats          # just print running stats
     python3 runner/crash_sleeve_paper_tracker.py --check-staleness # staleness JSON; exit 3 if stale
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
DEFAULT_DB = str(WORKSPACE / "crash_sleeve_paper.db")

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# ---- The promoted CONSERVATIVE wh15 config (probe: CRASH_SLEEVE_PROBE_20260630T164742Z.md) --
# Regime-gated CASH hedge, 15% engaged weight, engaged when SPX trailing drawdown breaches -10%.
PROBE_REPORT = "reports/CRASH_SLEEVE_PROBE_20260630T164742Z.md"
HEDGE_WEIGHT = 0.15               # ENGAGED hedge weight (the conservative "value pick" wh15)
DD_TRIGGER_PCT = -0.10            # trailing-drawdown breach that engages the hedge (depth gate)
HEDGE_INSTRUMENT = "CASH"         # 0 return when engaged -- cleanest de-risk (NOT haven, NOT TLT)

# ---- The 2 RISK sleeves: identical base weighting to runner/allocator_paper_tracker.py ----
BLEND_NAME = "invvol_63d_crashgated"
BLEND_COST_BPS = 2.0              # inter-sleeve monthly rebalance cost (one-way); hedge on/off transitions pay turnover
VOL_LOOKBACK_DAYS = 63           # inverse-vol trailing window (the 2 risk sleeves)
WEIGHT_SMOOTH_MONTHS = 3         # trailing month-opens to EW-average the inv-vol target over (smooth_3mo guardrail)
ROT_ASSETS = ["SPY", "QQQ", "GLD", "TLT"]
TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# DB schema  (side DB; 3 cumulative streams: gated / baseline / spx)
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,
    regime_on INTEGER,
    trailing_dd_pct REAL,
    w_tqqq REAL,
    w_rot REAL,
    w_hedge REAL,
    gated_daily_ret REAL,
    cum_gated_since_start REAL,
    baseline_daily_ret REAL,
    cum_baseline_since_start REAL,
    spx_daily_ret REAL,
    cum_spx_since_start REAL,
    engine_full_sharpe REAL,
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
# Pure helpers (unit-tested, offline): inv-vol, the PAST-ONLY regime gate, and
# the gated target-weight function. Mirror the probe's verbatim logic
# (reports/_crash_sleeve_probe_driver.make_gated_wfn +
#  reports/_crash_sleeve_robustness.build_dd_flags) with zero same-bar peeking.
# --------------------------------------------------------------------------- #
def _annualized_vol(returns):
    """Population-stdev annualized -- matches _allocator_blend_tests.annualized_vol."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def _build_regime_flags(spx_r, dd_thresh=DD_TRIGGER_PCT, extra_lag=0):
    """regime_on[idx] = SPX trailing drawdown (from running peak) worse than dd_thresh,
    computed PAST-ONLY through idx-1-extra_lag (STRICTLY before the month-open rebalance).

    VERBATIM mirror of reports/_crash_sleeve_robustness.build_dd_flags (the depth gate the
    probe promoted). The SPX price index is reconstructed by compounding spx_r; at index idx
    we look only at price[:cut+1] (cut = idx-1-extra_lag), take the running peak over that
    strictly-past slice, and engage if the drawdown breaches the threshold. A future SPX move
    cannot affect the flag at idx -- the lookahead guard, confirmed by the +1-bar canary.
    """
    n = len(spx_r)
    price = [1.0] * n
    for i in range(1, n):
        price[i] = price[i - 1] * (1.0 + spx_r[i])
    flags = [False] * n
    for idx in range(n):
        cut = idx - 1 - extra_lag
        if cut < 1:
            flags[idx] = False
            continue
        peak = max(price[: cut + 1])
        dd = price[cut] / peak - 1.0
        flags[idx] = dd <= dd_thresh
    return flags


def _trailing_dd_at(spx_r, idx, extra_lag=0):
    """SPX trailing drawdown (running peak -> price) evaluated PAST-ONLY through
    idx-1-extra_lag, for transparency logging of the mark date. Same cutoff as the flag."""
    n = len(spx_r)
    if n == 0:
        return 0.0
    price = [1.0] * n
    for i in range(1, n):
        price[i] = price[i - 1] * (1.0 + spx_r[i])
    cut = idx - 1 - extra_lag
    if cut < 1:
        return 0.0
    peak = max(price[: cut + 1])
    return price[cut] / peak - 1.0 if peak > 0 else 0.0


def _make_gated_wfn(tqqq_r, rot_r, regime_flags, w_h=HEDGE_WEIGHT, vol_lb=VOL_LOOKBACK_DAYS):
    """Build the gated 3-sleeve target-weight function over [tqqq, rot, cash].

    VERBATIM mirror of reports/_crash_sleeve_probe_driver.make_gated_wfn:
      base = inverse-vol(63d) on the 2 RISK sleeves (strictly-past slice tqqq_r[lo:idx]).
      regime ON  -> [base0*(1-w_h), base1*(1-w_h), w_h]  (risk sleeves keep their inv-vol RATIO)
      regime OFF -> [base0, base1, 0.0]
    Always sums to 1. The cash sleeve return is identically 0 (handled by the caller).

    This is the RAW inv-vol base (single month-open), matching the probe driver. The LIVE
    compute_crash_sleeve_state() wraps the SAME gate around the smooth_3mo EW-average base to
    match the live 2-sleeve tracker's weighting. Both are lookahead-safe by construction.
    """
    def fn(idx):
        if idx < 2:
            base = [0.5, 0.5]
        else:
            lo = max(0, idx - vol_lb)
            v0 = _annualized_vol(tqqq_r[lo:idx])
            v1 = _annualized_vol(rot_r[lo:idx])
            if v0 <= 0 or v1 <= 0:
                base = [0.5, 0.5]
            else:
                iv0, iv1 = 1.0 / v0, 1.0 / v1
                s = iv0 + iv1
                base = [iv0 / s, iv1 / s]
        on = regime_flags[idx] if idx < len(regime_flags) else False
        if on and w_h > 0:
            return [base[0] * (1.0 - w_h), base[1] * (1.0 - w_h), w_h]
        return [base[0], base[1], 0.0]
    return fn


# --------------------------------------------------------------------------- #
# Bar refresh (VERBATIM from runner/allocator_paper_tracker.py -- critical so ^GSPC
# isn't stale and the newest paper-clock row doesn't log a spurious flat SPX return).
# --------------------------------------------------------------------------- #
def _refresh_bars(symbols):
    """Force a re-fetch of each symbol's daily bars so the latest close is present before
    we compute today's snapshot. Resilient: a per-symbol fetch failure falls back to the
    cache and never crashes the daily tracker over a transient Yahoo hiccup."""
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
# Run the validated sleeves + GATED blend over ALL history; extract latest day.
# Reuses _allocator_blend_tests.build_sleeves() + blend_portfolio() DIRECTLY.
# --------------------------------------------------------------------------- #
def compute_crash_sleeve_state():
    """Re-run the validated 2 risk sleeves, build the GATED 3-sleeve blend AND the UNGATED
    2-sleeve baseline over ALL history, and return the latest day's decomposed state.

    Calls _allocator_blend_tests.build_sleeves() + blend_portfolio() directly so the paper
    tracker can NEVER silently diverge from the validated backtest. We only (a) form the SAME
    smooth_3mo inv-vol base weighting as the live 2-sleeve tracker, (b) overlay the PAST-ONLY
    -10% trailing-DD regime gate as a 3rd cash sleeve, and (c) read off the latest day for both
    the gated and ungated books.

    Returns dict: mark_date, regime_on, trailing_dd_pct, w_tqqq, w_rot, w_hedge,
    gated_daily_ret, baseline_daily_ret, spx_daily_ret, engine_full_sharpe, n_days, window.
    """
    import _allocator_blend_tests as ab

    refresh_status = _refresh_bars(["^GSPC", "TQQQ", "QQQ", "SPY", "GLD", "TLT"])
    print("[crash_sleeve_paper] bar refresh: %s" % json.dumps(refresh_status), flush=True)

    S = ab.build_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    spx_r = S["spx_r"]
    if not dates:
        raise RuntimeError("crash_sleeve_paper: empty common calendar between sleeves")

    n = len(dates)
    risk_sleeves = [tqqq_r, rot_r]
    cash_r = [0.0] * n

    month_open = []
    seen = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open.append(i)

    def _raw_invvol_w(idx):
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - VOL_LOOKBACK_DAYS)
        v0 = _annualized_vol(risk_sleeves[0][lo:idx])
        v1 = _annualized_vol(risk_sleeves[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0 / v0, 1.0 / v1
        s = iv0 + iv1
        return [iv0 / s, iv1 / s]

    def _smoothed_base_w(idx):
        prev = [m for m in month_open if m <= idx]
        sel = prev[-WEIGHT_SMOOTH_MONTHS:] if prev else [idx]
        if not sel:
            sel = [idx]
        acc0 = acc1 = 0.0
        for m in sel:
            w = _raw_invvol_w(m)
            acc0 += w[0]
            acc1 += w[1]
        cnt = len(sel)
        w = [acc0 / cnt, acc1 / cnt]
        s = w[0] + w[1]
        if s <= 0:
            return [0.5, 0.5]
        return [w[0] / s, w[1] / s]

    regime_flags = _build_regime_flags(spx_r, DD_TRIGGER_PCT, extra_lag=0)

    def baseline_wfn(idx):
        return _smoothed_base_w(idx)

    def gated_wfn(idx):
        b = _smoothed_base_w(idx)
        on = regime_flags[idx] if idx < len(regime_flags) else False
        if on and HEDGE_WEIGHT > 0:
            return [b[0] * (1.0 - HEDGE_WEIGHT), b[1] * (1.0 - HEDGE_WEIGHT), HEDGE_WEIGHT]
        return [b[0], b[1], 0.0]

    gated = ab.blend_portfolio(dates, [tqqq_r, rot_r, cash_r], gated_wfn,
                               blend_cost_bps=BLEND_COST_BPS,
                               vol_lookback_days=VOL_LOOKBACK_DAYS)
    gated_eq = gated["equity"]
    gated_full_sharpe = gated["stats"]["sharpe"]

    baseline = ab.blend_portfolio(dates, [tqqq_r, rot_r], baseline_wfn,
                                  blend_cost_bps=BLEND_COST_BPS,
                                  vol_lookback_days=VOL_LOOKBACK_DAYS)
    baseline_eq = baseline["equity"]

    mark_date = dates[-1]
    last_idx = n - 1

    gated_daily = (gated_eq[-1] / gated_eq[-2] - 1.0) if len(gated_eq) >= 2 else 0.0
    baseline_daily = (baseline_eq[-1] / baseline_eq[-2] - 1.0) if len(baseline_eq) >= 2 else 0.0
    spx_daily = spx_r[-1] if spx_r else 0.0

    latest_mo = month_open[-1] if month_open else last_idx
    gated_w = gated_wfn(latest_mo)
    w_tqqq, w_rot, w_hedge = gated_w[0], gated_w[1], gated_w[2]

    regime_on = 1 if (last_idx < len(regime_flags) and regime_flags[last_idx]) else 0
    trailing_dd = _trailing_dd_at(spx_r, last_idx, extra_lag=0)

    return {
        "mark_date": mark_date,
        "regime_on": regime_on,
        "trailing_dd_pct": round(trailing_dd, 6),
        "w_tqqq": round(w_tqqq, 4),
        "w_rot": round(w_rot, 4),
        "w_hedge": round(w_hedge, 4),
        "gated_daily_ret": gated_daily,
        "baseline_daily_ret": baseline_daily,
        "spx_daily_ret": spx_daily,
        "engine_full_sharpe": gated_full_sharpe,
        "n_days": n,
        "window": [dates[0], dates[-1]],
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def snapshot_today(db_path=DEFAULT_DB):
    """Compute today's gated+baseline state and log an idempotent daily snapshot.

    Idempotent on `date` (UNIQUE): if the latest closed trading day is already logged,
    this is a no-op (returns the existing state + inserted=0). cum_*_since_start are
    compounded over ALL logged daily returns (this row's date inclusive), i.e. the
    paper-clock-inception cumulative, across all 3 streams (gated/baseline/spx).
    """
    state = compute_crash_sleeve_state()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn(db_path)
    inserted = 0
    try:
        existing = conn.execute(
            "SELECT id FROM daily_snapshots WHERE date=?", (state["mark_date"],)
        ).fetchone()

        if existing is None:
            prior = conn.execute(
                "SELECT cum_gated_since_start, cum_baseline_since_start, cum_spx_since_start "
                "FROM daily_snapshots ORDER BY date DESC LIMIT 1"
            ).fetchone()
            prior_gated = prior["cum_gated_since_start"] if prior and prior["cum_gated_since_start"] is not None else 0.0
            prior_base = prior["cum_baseline_since_start"] if prior and prior["cum_baseline_since_start"] is not None else 0.0
            prior_spx = prior["cum_spx_since_start"] if prior and prior["cum_spx_since_start"] is not None else 0.0
            # cum stored as cumulative RETURN; growth factor = 1 + cum.
            cum_gated = (1.0 + prior_gated) * (1.0 + state["gated_daily_ret"]) - 1.0
            cum_base = (1.0 + prior_base) * (1.0 + state["baseline_daily_ret"]) - 1.0
            cum_spx = (1.0 + prior_spx) * (1.0 + state["spx_daily_ret"]) - 1.0

            conn.execute(
                """INSERT INTO daily_snapshots
                   (date, regime_on, trailing_dd_pct, w_tqqq, w_rot, w_hedge,
                    gated_daily_ret, cum_gated_since_start, baseline_daily_ret,
                    cum_baseline_since_start, spx_daily_ret, cum_spx_since_start,
                    engine_full_sharpe, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    state["mark_date"], state["regime_on"], state["trailing_dd_pct"],
                    state["w_tqqq"], state["w_rot"], state["w_hedge"],
                    state["gated_daily_ret"], cum_gated, state["baseline_daily_ret"],
                    cum_base, state["spx_daily_ret"], cum_spx,
                    state["engine_full_sharpe"], ts,
                ),
            )
            conn.commit()
            inserted = 1
            state["cum_gated_since_start"] = cum_gated
            state["cum_baseline_since_start"] = cum_base
            state["cum_spx_since_start"] = cum_spx
        else:
            row = conn.execute(
                "SELECT cum_gated_since_start, cum_baseline_since_start, cum_spx_since_start "
                "FROM daily_snapshots WHERE date=?",
                (state["mark_date"],),
            ).fetchone()
            state["cum_gated_since_start"] = row["cum_gated_since_start"]
            state["cum_baseline_since_start"] = row["cum_baseline_since_start"]
            state["cum_spx_since_start"] = row["cum_spx_since_start"]

        n_rows = conn.execute("SELECT COUNT(*) FROM daily_snapshots").fetchone()[0]
    finally:
        conn.close()
    state["inserted"] = inserted
    state["rows_logged"] = n_rows
    return state


def paper_clock_stats(db_path=DEFAULT_DB):
    """Running stats over ALL forward rows this tracker has logged (since inception).

    These rows ARE the honest forward paper clock (one per trading day this tracker has
    run). `sharpe_since_start` is the forward, out-of-sample, marked-at-close Sharpe from
    the logged GATED daily returns -- distinct from the backtest Sharpe in the report. The
    cum for all 3 streams (gated/baseline/spx) lets us read the gate's forward edge directly,
    and regime_engaged_* says how often the -10% hedge actually fired on the path observed.

    Returns: start_date, n_days, cum_gated_pct, cum_baseline_pct, cum_spx_pct,
             gate_vs_baseline_pp, sharpe_since_start, regime_engaged_days,
             regime_engaged_pct, current_w_tqqq, current_w_rot, current_w_hedge,
             current_regime_on.
    """
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT date, regime_on, w_tqqq, w_rot, w_hedge, gated_daily_ret, "
            "baseline_daily_ret, spx_daily_ret FROM daily_snapshots ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"n_days": 0, "note": "no forward rows logged yet"}

    gated_rets = [r["gated_daily_ret"] for r in rows if r["gated_daily_ret"] is not None]
    base_rets = [r["baseline_daily_ret"] for r in rows if r["baseline_daily_ret"] is not None]
    spx_rets = [r["spx_daily_ret"] for r in rows if r["spx_daily_ret"] is not None]
    n = len(gated_rets)

    def _cum(vals):
        c = 1.0
        for r in vals:
            c *= (1.0 + r)
        return c - 1.0

    cum_gated = _cum(gated_rets)
    cum_base = _cum(base_rets)
    cum_spx = _cum(spx_rets)

    if n >= 2:
        mean = sum(gated_rets) / n
        var = sum((r - mean) ** 2 for r in gated_rets) / (n - 1)
        sd = math.sqrt(var)
        sharpe = (mean / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    else:
        sharpe = 0.0

    engaged = sum(1 for r in rows if r["regime_on"])
    last = rows[-1]
    return {
        "start_date": rows[0]["date"],
        "n_days": n,
        "cum_gated_pct": round(cum_gated * 100, 4),
        "cum_baseline_pct": round(cum_base * 100, 4),
        "cum_spx_pct": round(cum_spx * 100, 4),
        "gate_vs_baseline_pp": round((cum_gated - cum_base) * 100, 4),
        "sharpe_since_start": round(sharpe, 4),
        "regime_engaged_days": engaged,
        "regime_engaged_pct": round(100.0 * engaged / len(rows), 4),
        "current_w_tqqq": last["w_tqqq"],
        "current_w_rot": last["w_rot"],
        "current_w_hedge": last["w_hedge"],
        "current_regime_on": last["regime_on"],
    }


# --------------------------------------------------------------------------- #
# Staleness self-check (silent-clock guard) -- VERBATIM from allocator_paper_tracker.py.
#
# The dangerous failure mode is NOT rc!=0 (that already alarms) -- it is the tracker
# running rc=0 yet logging NO new row for several trading days (stale cached SPX bar, or
# the engine silently returning an old mark_date). That leaves a hole in the forward track
# record discovered only when someone reads the DB. This guard compares the latest logged
# DB date against the latest CLOSED SPX bar (the same ^GSPC cache the engine marks against)
# and reports how many trading days behind the clock is. 0 = current; 1 = normal intraday
# transient (self-heals next slot); >=2 = genuine lag -> alarm (exit 3).
# --------------------------------------------------------------------------- #
GSPC_CACHE = str(WORKSPACE / "data_cache" / "yahoo" / "_GSPC_parsed.json")


def _spx_trading_dates():
    """Authoritative trading-day calendar = the dates present in the cached ^GSPC daily
    series (ascending). Same series the engine marks against, so the staleness count can
    never diverge from what the tracker would log."""
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

    Returns dict: last_logged, latest_closed_bar, trading_days_behind, rows_logged,
    stale (True when behind >= 2), note.
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
    p = argparse.ArgumentParser(description="Crash-sleeve (regime-gated) paper-clock tracker")
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
    print("[crash_sleeve_paper] config: %s hedge wh%d / DD-trigger %.0f%% / %s (probe %s)" % (
        HEDGE_INSTRUMENT, int(round(HEDGE_WEIGHT * 100)), DD_TRIGGER_PCT * 100,
        BLEND_NAME, PROBE_REPORT))
    print("[crash_sleeve_paper] mark_date=%s inserted=%d rows_logged=%d" % (
        state["mark_date"], state["inserted"], state["rows_logged"]))
    _stale = clock_staleness(db_path=args.db)
    print("[crash_sleeve_paper] staleness: %s" % _stale["note"])
    print("[crash_sleeve_paper] REGIME: %s | SPX trailing DD %.2f%% (trigger %.0f%%)" % (
        "ON (hedge engaged)" if state["regime_on"] else "OFF (no hedge)",
        state["trailing_dd_pct"] * 100, DD_TRIGGER_PCT * 100))
    print("[crash_sleeve_paper] gated sleeve weights: TQQQ-voltarget %.1f%% / rotation %.1f%% / cash-hedge %.1f%%" % (
        state["w_tqqq"] * 100, state["w_rot"] * 100, state["w_hedge"] * 100))
    print("[crash_sleeve_paper] mark_date daily return: gated %.4f%% | baseline %.4f%% | SPX %.4f%%" % (
        state["gated_daily_ret"] * 100, state["baseline_daily_ret"] * 100, state["spx_daily_ret"] * 100))
    print("[crash_sleeve_paper] cum since paper-clock start: gated %.4f%% | baseline %.4f%% | SPX %.4f%%" % (
        state["cum_gated_since_start"] * 100, state["cum_baseline_since_start"] * 100,
        state["cum_spx_since_start"] * 100))
    print("[crash_sleeve_paper] engine full backtest Sharpe (gated, drift check) = %.3f" % state["engine_full_sharpe"])
    print("[crash_sleeve_paper] backtest window %s (%d days)" % (state["window"], state["n_days"]))
    print("")
    fwd = paper_clock_stats(db_path=args.db)
    print("[crash_sleeve_paper] forward paper-clock stats (since inception):")
    print(json.dumps(fwd, indent=2))


if __name__ == "__main__":
    main()
