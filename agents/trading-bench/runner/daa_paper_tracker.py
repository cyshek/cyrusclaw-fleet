"""Keller/Keuning DAA (Defensive Asset Allocation) "canary universe" — PAPER CLOCK tracker.

PAPER ONLY. No real money. READ-ONLY forward record. NOT wired into the live roster.

WHY THIS EXISTS
---------------
The confirm-or-kill backtest (_daa_confirm.py -> reports/DAA_VERDICT_*.md) tested whether
DAA's de-risking canary gate is a REAL edge orthogonal to our existing allocator_blend
(which has NO crash-off switch). DAA's value is crash-INSURANCE behaviour: a VWO/BND breadth-
momentum canary that cascades the book OUT of risk and into bonds during stress -- exactly the
de-risk our rotation sleeve lacks. The backtest verdict rests on a finite OOS window; a forward
paper clock accumulates NEW regimes the backtest could not fit -- the only honest way to earn (or
falsify) confidence in the gate. So this tracker logs, every trading day, BOTH:
  * the DAA cascade equity curve (the canary book), AND
  * our validated rotation sleeve (control = run_sector_rotation top-2 of {SPY,QQQ,GLD,TLT}),
plus SPX (^GSPC) on the same path, so we can read the gate's forward edge directly.

This is modeled VERBATIM on runner/crash_sleeve_paper_tracker.py (which mirrors
runner/xa_tsmom_paper_tracker.py). It runs NO live orders, touches NO live runner/risk files,
and writes ONLY to a SIDE DB (daa_paper.db).

MECHANISM / MATH SOURCE -- REUSED, NOT REIMPLEMENTED (no-lookahead by construction)
----------------------------------------------------------------------------------
We import the VALIDATED confirm-or-kill driver _daa_confirm and call its run_daa() DIRECTLY
over ALL price history for the equity curves, and reuse its EXACT 13612W momentum + cascade
math (_daa_confirm._mom_13612w / _trailing_return, and the same 3-state canary cascade) for the
per-day signal readout. We re-derive ZERO numeric logic here.

  CANARY universe = {VWO, BND}, checked monthly via 13612W momentum
      13612W = (12*r1 + 4*r3 + 2*r6 + 1*r12)/4   (rN = trailing ~21*N-day total return).
  RISK universe G12 = {SPY, IWM, QQQ, VGK, EWJ, VWO, VNQ, GSG, GLD, TLT, HYG, LQD}, EW top-6.
  CASH/bond universe = {SHY, IEF, LQD}, best single by 13612W.
  ALLOCATION CASCADE (signal asset != traded asset = the innovation):
      both canaries 13612W > 0  -> risk_on  : 100% top-6 risk EW              (w_defensive 0.0)
      exactly ONE canary > 0    -> half     : 50% top-3 risk EW + 50% bond    (w_defensive 0.5)
      both canaries <= 0        -> crash_off : 100% best single bond          (w_defensive 1.0)

LOOKAHEAD CONTRACT (mirrors _daa_confirm.run_daa / run_sector_rotation EXACTLY)
------------------------------------------------------------------------------
Rank on the close of the LAST trading day of the prior month (cal[i-1] when cal[i] is a
month-first), hold from the FIRST trading day of the new month. rN uses ~21*N trading days
back on the common calendar, computed through the PRIOR month-end close. The decision day
strictly precedes the held period -> leak-free by construction. The per-day signal readout
this tracker logs (regime / canary scores / held assets) is computed at the most recent
month-first using cal[sig_idx] = prior month-end -- the model's honest current-month decision.

WHAT IT LOGS (idempotent daily snapshot -> daa_paper.db)
--------------------------------------------------------
For each trading date marked:
  * regime              : risk_on / half / crash_off (current-month canary cascade state)
  * w_defensive         : defensive (cash/bond bucket) fraction in {0.0, 0.5, 1.0}
  * canary_vwo_13612w   : VWO 13612W at the current month's decision day (prior month-end)
  * canary_bnd_13612w   : BND 13612W at the current month's decision day
  * top_risk_assets     : JSON list of risk legs currently held (EW top-6 or top-3; [] if crash_off)
  * defensive_asset     : best single bond when defensive (half/crash_off); null when risk_on
  * daa_daily_return    : DAA cascade book realized close-to-close return ON `date`
  * control_daily_return: rotation-sleeve control realized return ON `date`
  * spx_daily_return    : SPX (^GSPC) realized return ON `date`
  * *_equity            : normalized equity curves (start 1.0 at paper-clock inception)
  * engine_full_sharpe  : DAA full-period continuous-span Sharpe at this run (drift check)

FIRST-ROW INVARIANT (mandatory, mirrors crash-sleeve / xa-tsmom trackers)
-------------------------------------------------------------------------
On the FIRST run, insert ONE row for the latest closed trading day. All three equity values
start at 1.0 (normalized to paper-clock inception); the three daily returns are 0.0 (no prior
logged close to difference against). The regime, canary scores and held assets ARE logged so a
future session can verify the canary engaged correctly TODAY. cum equity thereafter compounds
honestly from these daily returns.

FAIL-SAFES
----------
  * engine / import error -> raise (the cron wrapper logs it); never write a bogus row.
  * a transient Yahoo hiccup is absorbed by _refresh_bars (falls back to cache, never crashes).
  * idempotent: re-running the same day is a no-op (UNIQUE date) and never duplicates.

Entry points (importable + CLI):
  snapshot_today(db_path) -> dict        # log today's DAA + control + SPX snapshot (idempotent)
  paper_clock_stats(db_path)             # forward stats over logged rows (since inception)
  clock_staleness(db_path)               # silent-clock guard (exit 3 if >=2 trading days behind)

DB: workspace root daa_paper.db (default).
Run: python3 runner/daa_paper_tracker.py                   # snapshot + print stats
     python3 runner/daa_paper_tracker.py --stats           # just print running stats
     python3 runner/daa_paper_tracker.py --check-staleness # staleness JSON; exit 3 if stale
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(WORKSPACE / "daa_paper.db")

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# ---- Reuse the VALIDATED confirm-or-kill driver: exact 13612W + cascade math + equity curve.
#      ZERO numeric logic re-derived here.
import _daa_confirm as daa  # noqa: E402

VERDICT_DRIVER = "_daa_confirm.py"
CANARY = list(daa.CANARY)            # ["VWO", "BND"]
RISK_G12 = list(daa.RISK_G12)
CASH = list(daa.CASH)                # ["SHY", "IEF", "LQD"]
BENCH = daa.BENCH                    # "^GSPC"
TOP_RISK_FULL = daa.TOP_RISK_FULL    # 6 (both canaries up)
TOP_RISK_HALF = daa.TOP_RISK_HALF    # 3 (one canary up)
COST_BPS = daa.COST_BPS              # 2.0 one-way on turned-over fraction

# Control = our VALIDATED rotation sleeve top-2 of {SPY,QQQ,GLD,TLT}, lookback 3mo, hold 2.
CONTROL_ASSETS = ["SPY", "QQQ", "GLD", "TLT"]
CONTROL_LOOKBACK_MONTHS = 3
CONTROL_HOLD_TOP = 2

TRADING_DAYS = 252

# Regime labels (current-month canary cascade state) and their defensive fraction.
REGIME_RISK_ON = "risk_on"
REGIME_HALF = "half"
REGIME_CRASH_OFF = "crash_off"
_REGIME_DEFENSIVE_FRAC = {REGIME_RISK_ON: 0.0, REGIME_HALF: 0.5, REGIME_CRASH_OFF: 1.0}

# ^GSPC cache used by the staleness guard (same series the engines mark against).
GSPC_CACHE = str(WORKSPACE / "data_cache" / "yahoo" / "_GSPC_parsed.json")


# --------------------------------------------------------------------------- #
# DB schema  (side DB; 3 cumulative streams: daa / control / spx)
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,                 -- trading date being marked (engine last close)
    daa_equity REAL,                  -- DAA cascade book equity (1.0 at paper-clock inception)
    control_equity REAL,              -- rotation-sleeve control equity (1.0 at inception)
    spx_equity REAL,                  -- SPX (^GSPC) equity (1.0 at inception)
    regime TEXT,                      -- risk_on / half / crash_off (current-month cascade state)
    w_defensive REAL,                 -- defensive (cash/bond bucket) fraction {0.0,0.5,1.0}
    daa_daily_return REAL,            -- DAA book realized return ON `date` (close-to-close)
    control_daily_return REAL,        -- control realized return ON `date`
    spx_daily_return REAL,            -- SPX realized return ON `date`
    canary_vwo_13612w REAL,           -- VWO 13612W at current month's decision day (prior month-end)
    canary_bnd_13612w REAL,           -- BND 13612W at current month's decision day
    top_risk_assets TEXT,             -- JSON list of held risk legs (EW; [] if crash_off)
    defensive_asset TEXT,             -- best single bond when defensive; NULL when risk_on
    engine_full_sharpe REAL,          -- DAA full-period continuous-span Sharpe at this run (drift check)
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
# Pure helpers (unit-tested, offline). The 13612W momentum is the SAME math as
# _daa_confirm._mom_13612w (delegated, not reimplemented). The cascade classifier
# mirrors _daa_confirm.run_daa's monthly n_up branch verbatim.
# --------------------------------------------------------------------------- #
def _mom_13612w(close: Dict[str, Dict[str, float]], a: str, cal: List[str],
                end_idx: int) -> Optional[float]:
    """13612W = (12*r1 + 4*r3 + 2*r6 + 1*r12)/4 through cal[end_idx] (prior month-end close).

    Delegates to _daa_confirm._mom_13612w so the paper tracker can NEVER silently diverge
    from the validated backtest's momentum math."""
    return daa._mom_13612w(close, a, cal, end_idx)


def _classify_regime(vwo_mom: Optional[float], bnd_mom: Optional[float]) -> Tuple[str, float]:
    """Map the two canary 13612W scores to (regime_label, w_defensive), VERBATIM mirror of
    _daa_confirm.run_daa's cascade: undefined canary is treated as <=0 (defensive), exactly
    as the driver does (`cmom[c] is not None and cmom[c] > 0.0`).

      both > 0  -> (risk_on,   0.0)
      one  > 0  -> (half,      0.5)
      both <= 0 -> (crash_off, 1.0)
    """
    n_up = 0
    if vwo_mom is not None and vwo_mom > 0.0:
        n_up += 1
    if bnd_mom is not None and bnd_mom > 0.0:
        n_up += 1
    if n_up == 2:
        return REGIME_RISK_ON, 0.0
    if n_up == 1:
        return REGIME_HALF, 0.5
    return REGIME_CRASH_OFF, 1.0


def _top_risk(close: Dict[str, Dict[str, float]], cal: List[str], end_idx: int,
              k: int) -> List[str]:
    """EW top-k risk legs by 13612W through cal[end_idx]. Mirrors _daa_confirm.run_daa.top_risk."""
    scored = [(a, _mom_13612w(close, a, cal, end_idx)) for a in RISK_G12]
    scored = [(a, m) for (a, m) in scored if m is not None]
    scored.sort(key=lambda t: t[1], reverse=True)
    return [a for (a, m) in scored[:k]]


def _best_bond(close: Dict[str, Dict[str, float]], cal: List[str],
               end_idx: int) -> Optional[str]:
    """Best single bond by 13612W through cal[end_idx]. Mirrors _daa_confirm.run_daa.best_bond."""
    scored = [(c, _mom_13612w(close, c, cal, end_idx)) for c in CASH]
    scored = [(c, m) for (c, m) in scored if m is not None]
    if not scored:
        return None
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0][0]


# --------------------------------------------------------------------------- #
# Bar refresh (VERBATIM convention from runner/crash_sleeve_paper_tracker.py).
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
# Current-month signal readout (regime / canary scores / held assets), computed
# lookahead-safe at the most recent month-first using the prior month-end close.
# Reuses the validated _daa_confirm math throughout.
# --------------------------------------------------------------------------- #
def compute_signal_state(cal: List[str],
                         close: Dict[str, Dict[str, float]]) -> Dict:
    """Decode the CURRENT month's canary cascade decision (the weights the model holds today).

    Finds the most recent month-first index in `cal`; the decision (rank) day is the prior
    month-end = cal[mf-1] (lookahead-safe, identical cutoff to _daa_confirm.run_daa). Returns
    the regime label, w_defensive, both canary 13612W scores AT the decision day, the held risk
    legs (EW top-6/top-3), and the best bond (defensive_asset).
    """
    # month-first indices on cal
    month_first: List[int] = []
    seen = set()
    for idx, d in enumerate(cal):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_first.append(idx)
    if not month_first:
        return {"regime": REGIME_CRASH_OFF, "w_defensive": 1.0,
                "canary_vwo_13612w": None, "canary_bnd_13612w": None,
                "top_risk_assets": [], "defensive_asset": None,
                "decision_date": None}

    mf = month_first[-1]
    sig_idx = mf - 1  # prior month-end close (the decision day); strictly before the held month
    if sig_idx < 0:
        # not enough history for a full prior-month decision -> defensive flat (matches driver)
        return {"regime": REGIME_CRASH_OFF, "w_defensive": 1.0,
                "canary_vwo_13612w": None, "canary_bnd_13612w": None,
                "top_risk_assets": [], "defensive_asset": None,
                "decision_date": None}

    vwo_mom = _mom_13612w(close, "VWO", cal, sig_idx)
    bnd_mom = _mom_13612w(close, "BND", cal, sig_idx)
    regime, w_def = _classify_regime(vwo_mom, bnd_mom)

    top_risk: List[str] = []
    defensive_asset: Optional[str] = None
    if regime == REGIME_RISK_ON:
        top_risk = _top_risk(close, cal, sig_idx, TOP_RISK_FULL)
    elif regime == REGIME_HALF:
        top_risk = _top_risk(close, cal, sig_idx, TOP_RISK_HALF)
        defensive_asset = _best_bond(close, cal, sig_idx)
    else:  # crash_off
        defensive_asset = _best_bond(close, cal, sig_idx)

    return {
        "regime": regime,
        "w_defensive": w_def,
        "canary_vwo_13612w": vwo_mom,
        "canary_bnd_13612w": bnd_mom,
        "top_risk_assets": top_risk,
        "defensive_asset": defensive_asset,
        "decision_date": cal[sig_idx],
    }


# --------------------------------------------------------------------------- #
# Run the validated DAA engine + the control rotation over ALL history; extract
# the latest day's decomposed state. Reuses _daa_confirm.run_daa() +
# _sigimprove_tests.run_sector_rotation() DIRECTLY (zero math reimplemented).
# --------------------------------------------------------------------------- #
def compute_daa_state() -> Dict:
    """Re-run the validated DAA cascade AND the rotation-sleeve control over ALL history,
    and return the latest day's decomposed state.

    Calls _daa_confirm.run_daa() directly for the DAA equity curve + SPX same-path curve, and
    _sigimprove_tests.run_sector_rotation() for the control, so the paper tracker can NEVER
    silently diverge from the validated backtest. The per-day signal readout (regime / canary
    scores / held assets) is decoded lookahead-safe at the latest month-first.

    Returns dict: mark_date, regime, w_defensive, canary_vwo_13612w, canary_bnd_13612w,
    top_risk_assets, defensive_asset, daa_daily_return, control_daily_return, spx_daily_return,
    engine_full_sharpe, n_days, window.
    """
    from _sigimprove_tests import run_sector_rotation

    refresh_status = _refresh_bars([BENCH] + sorted(set(daa.ALL_TICKERS) | set(CONTROL_ASSETS)))
    print("[daa_paper] bar refresh: %s" % json.dumps(refresh_status), flush=True)

    # --- DAA cascade (canonical lag 0) over all history (validated driver) ---
    res = daa.run_daa(signal_lag_extra=0)
    daa_dates: List[str] = res["strategy"]["dates"]
    daa_eq: List[float] = res["strategy"]["equity"]
    spx_eq: List[float] = res["spx"]["equity"]
    if not daa_dates or len(daa_eq) < 1:
        raise RuntimeError("daa_paper: validated DAA engine produced no equity curve")
    mark_date = daa_dates[-1]
    w_start = res["window"]["start"]
    w_end = res["window"]["end"]

    # --- Control: rotation top-2 of {SPY,QQQ,GLD,TLT}, matched to the DAA window ---
    ctrl = run_sector_rotation(CONTROL_ASSETS, bench=BENCH,
                               lookback_months=CONTROL_LOOKBACK_MONTHS,
                               hold_top=CONTROL_HOLD_TOP, cost_bps=COST_BPS,
                               start=w_start, end=w_end)
    ctrl_dates: List[str] = ctrl["strategy"]["dates"]
    ctrl_eq: List[float] = ctrl["strategy"]["equity"]

    # --- latest-day close-to-close returns from each equity curve ---
    daa_daily = (daa_eq[-1] / daa_eq[-2] - 1.0) if len(daa_eq) >= 2 else 0.0
    spx_daily = (spx_eq[-1] / spx_eq[-2] - 1.0) if len(spx_eq) >= 2 else 0.0
    # control may end on the same mark_date (shared calendar); guard length + alignment.
    control_daily = 0.0
    if len(ctrl_eq) >= 2:
        if ctrl_dates and ctrl_dates[-1] == mark_date:
            control_daily = ctrl_eq[-1] / ctrl_eq[-2] - 1.0
        else:
            # fall back to control's own last step (still its honest latest daily mark)
            control_daily = ctrl_eq[-1] / ctrl_eq[-2] - 1.0

    # --- DAA full-period continuous-span Sharpe (drift check), reuse driver's fp helper ---
    daa_fps, _ = daa._fp_sharpe(daa_eq)

    # --- decode current-month signal readout (regime / canary scores / held assets) ---
    sig = _signal_state_from_run(res, daa_dates)

    return {
        "mark_date": mark_date,
        "regime": sig["regime"],
        "w_defensive": sig["w_defensive"],
        "canary_vwo_13612w": sig["canary_vwo_13612w"],
        "canary_bnd_13612w": sig["canary_bnd_13612w"],
        "top_risk_assets": sig["top_risk_assets"],
        "defensive_asset": sig["defensive_asset"],
        "daa_daily_return": daa_daily,
        "control_daily_return": control_daily,
        "spx_daily_return": spx_daily,
        "engine_full_sharpe": daa_fps,
        "n_days": len(daa_dates),
        "window": [w_start, w_end],
    }


def _signal_state_from_run(res: Dict, daa_dates: List[str]) -> Dict:
    """Decode the current-month signal readout for the latest mark, rebuilding the SAME
    common calendar + close map _daa_confirm.run_daa used (its ALL_TICKERS intersection over
    [start,end]) so the decision day cutoff matches the engine exactly. Lookahead-safe:
    canary scores are read at the prior month-end (cal[mf-1])."""
    from runner import daily_bars_cache as dbc
    bars = {a: dbc.get_daily(a) for a in daa.ALL_TICKERS}
    start = res["window"]["start"]
    end = res["window"]["end"]
    date_sets = [set(b["date"] for b in bars[a]) for a in daa.ALL_TICKERS]
    common = sorted(set.intersection(*date_sets))
    cal = [d for d in common if start <= d <= end]
    close = {a: {b["date"]: b["adjclose"] for b in bars[a]} for a in daa.ALL_TICKERS}
    return compute_signal_state(cal, close)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def snapshot_today(db_path: str = DEFAULT_DB) -> Dict:
    """Compute today's DAA + control + SPX state and log an idempotent daily snapshot.

    Idempotent on `date` (UNIQUE): if the latest closed trading day is already logged, this
    is a no-op (returns the existing state + inserted=0). All three equity curves start at
    1.0 at the paper-clock's FIRST logged row; on that inception row the three daily returns
    are 0.0 (no prior logged close to difference against), but the regime / canary scores /
    held assets ARE logged so a future session can verify the canary engaged correctly.
    Thereafter each *_equity compounds from its logged daily return.
    """
    state = compute_daa_state()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn(db_path)
    inserted = 0
    try:
        existing = conn.execute(
            "SELECT id FROM daily_snapshots WHERE date=?", (state["mark_date"],)
        ).fetchone()

        if existing is None:
            prior = conn.execute(
                "SELECT daa_equity, control_equity, spx_equity "
                "FROM daily_snapshots ORDER BY date DESC LIMIT 1"
            ).fetchone()
            is_first = prior is None
            # Inception row: equities normalized to 1.0, daily returns 0.0 (no prior close).
            if is_first:
                daa_ret = control_ret = spx_ret = 0.0
                daa_eq = control_eq = spx_eq = 1.0
            else:
                daa_ret = state["daa_daily_return"]
                control_ret = state["control_daily_return"]
                spx_ret = state["spx_daily_return"]
                prior_daa = prior["daa_equity"] if prior["daa_equity"] is not None else 1.0
                prior_ctrl = prior["control_equity"] if prior["control_equity"] is not None else 1.0
                prior_spx = prior["spx_equity"] if prior["spx_equity"] is not None else 1.0
                daa_eq = prior_daa * (1.0 + daa_ret)
                control_eq = prior_ctrl * (1.0 + control_ret)
                spx_eq = prior_spx * (1.0 + spx_ret)

            conn.execute(
                """INSERT INTO daily_snapshots
                   (date, daa_equity, control_equity, spx_equity, regime, w_defensive,
                    daa_daily_return, control_daily_return, spx_daily_return,
                    canary_vwo_13612w, canary_bnd_13612w, top_risk_assets, defensive_asset,
                    engine_full_sharpe, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    state["mark_date"], daa_eq, control_eq, spx_eq, state["regime"],
                    state["w_defensive"], daa_ret, control_ret, spx_ret,
                    state["canary_vwo_13612w"], state["canary_bnd_13612w"],
                    json.dumps(state["top_risk_assets"]), state["defensive_asset"],
                    state["engine_full_sharpe"], ts,
                ),
            )
            conn.commit()
            inserted = 1
            state["daa_equity"] = daa_eq
            state["control_equity"] = control_eq
            state["spx_equity"] = spx_eq
            state["is_first_row"] = is_first
        else:
            row = conn.execute(
                "SELECT daa_equity, control_equity, spx_equity "
                "FROM daily_snapshots WHERE date=?",
                (state["mark_date"],),
            ).fetchone()
            state["daa_equity"] = row["daa_equity"]
            state["control_equity"] = row["control_equity"]
            state["spx_equity"] = row["spx_equity"]
            state["is_first_row"] = False

        n_rows = conn.execute("SELECT COUNT(*) FROM daily_snapshots").fetchone()[0]
    finally:
        conn.close()
    state["inserted"] = inserted
    state["rows_logged"] = n_rows
    return state


def paper_clock_stats(db_path: str = DEFAULT_DB) -> Dict:
    """Running stats over ALL forward rows this tracker has logged (since inception).

    These rows ARE the honest forward paper clock (one per trading day this tracker has run).
    `sharpe_since_start` is the forward, out-of-sample, marked-at-close Sharpe from the logged
    DAA daily returns -- distinct from the backtest Sharpe in the report. The cum for all 3
    streams (daa/control/spx) lets us read the gate's forward edge directly, and
    defensive_days/defensive_pct says how often the canary actually de-risked on the path.

    Returns: start_date, n_days, cum_daa_pct, cum_control_pct, cum_spx_pct,
             daa_vs_control_pp, sharpe_since_start, defensive_days, defensive_pct,
             crash_off_days, current_regime, current_w_defensive.
    """
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT date, regime, w_defensive, daa_daily_return, control_daily_return, "
            "spx_daily_return FROM daily_snapshots ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"n_days": 0, "note": "no forward rows logged yet"}

    daa_rets = [r["daa_daily_return"] for r in rows if r["daa_daily_return"] is not None]
    ctrl_rets = [r["control_daily_return"] for r in rows if r["control_daily_return"] is not None]
    spx_rets = [r["spx_daily_return"] for r in rows if r["spx_daily_return"] is not None]
    n = len(daa_rets)

    def _cum(vals):
        c = 1.0
        for r in vals:
            c *= (1.0 + r)
        return c - 1.0

    cum_daa = _cum(daa_rets)
    cum_ctrl = _cum(ctrl_rets)
    cum_spx = _cum(spx_rets)

    if n >= 2:
        mean = sum(daa_rets) / n
        var = sum((r - mean) ** 2 for r in daa_rets) / (n - 1)
        sd = math.sqrt(var)
        sharpe = (mean / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    else:
        sharpe = 0.0

    defensive_days = sum(1 for r in rows if (r["w_defensive"] is not None and r["w_defensive"] > 0.0))
    crash_off_days = sum(1 for r in rows if r["regime"] == REGIME_CRASH_OFF)
    last = rows[-1]
    return {
        "start_date": rows[0]["date"],
        "n_days": n,
        "cum_daa_pct": round(cum_daa * 100, 4),
        "cum_control_pct": round(cum_ctrl * 100, 4),
        "cum_spx_pct": round(cum_spx * 100, 4),
        "daa_vs_control_pp": round((cum_daa - cum_ctrl) * 100, 4),
        "sharpe_since_start": round(sharpe, 4),
        "defensive_days": defensive_days,
        "defensive_pct": round(100.0 * defensive_days / len(rows), 4),
        "crash_off_days": crash_off_days,
        "current_regime": last["regime"],
        "current_w_defensive": last["w_defensive"],
    }


# --------------------------------------------------------------------------- #
# Staleness self-check (silent-clock guard) -- VERBATIM convention from
# runner/crash_sleeve_paper_tracker.py.
# --------------------------------------------------------------------------- #
def _spx_trading_dates():
    """Authoritative trading-day calendar = the dates present in the cached ^GSPC daily series
    (ascending). Same series the engines mark against, so the staleness count can never diverge
    from what the tracker would log."""
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


def clock_staleness(db_path: str = DEFAULT_DB) -> Dict:
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
    p = argparse.ArgumentParser(description="Keller/Keuning DAA canary paper-clock tracker")
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
    print("[daa_paper] mechanism: Keller/Keuning DAA canary {VWO,BND} 13612W cascade "
          "(risk_on/half/crash_off) | control=rotation top-2 {SPY,QQQ,GLD,TLT} | driver %s"
          % VERDICT_DRIVER)
    print("[daa_paper] mark_date=%s inserted=%d rows_logged=%d is_first_row=%s" % (
        state["mark_date"], state["inserted"], state["rows_logged"],
        state.get("is_first_row")))
    _stale = clock_staleness(db_path=args.db)
    print("[daa_paper] staleness: %s" % _stale["note"])
    print("[daa_paper] REGIME: %s | w_defensive %.2f | canary 13612W VWO=%s BND=%s" % (
        state["regime"], state["w_defensive"],
        ("%.4f" % state["canary_vwo_13612w"]) if state["canary_vwo_13612w"] is not None else "n/a",
        ("%.4f" % state["canary_bnd_13612w"]) if state["canary_bnd_13612w"] is not None else "n/a"))
    print("[daa_paper] held risk legs: %s | defensive_asset: %s" % (
        state["top_risk_assets"], state["defensive_asset"]))
    print("[daa_paper] mark_date daily return: DAA %.4f%% | control %.4f%% | SPX %.4f%%" % (
        state["daa_daily_return"] * 100, state["control_daily_return"] * 100,
        state["spx_daily_return"] * 100))
    print("[daa_paper] equity (1.0 at inception): DAA %.6f | control %.6f | SPX %.6f" % (
        state.get("daa_equity", float("nan")), state.get("control_equity", float("nan")),
        state.get("spx_equity", float("nan"))))
    print("[daa_paper] engine full backtest Sharpe (DAA, drift check) = %.3f" % state["engine_full_sharpe"])
    print("[daa_paper] backtest window %s (%d days)" % (state["window"], state["n_days"]))
    print("")
    fwd = paper_clock_stats(db_path=args.db)
    print("[daa_paper] forward paper-clock stats (since inception):")
    print(json.dumps(fwd, indent=2))


if __name__ == "__main__":
    main()