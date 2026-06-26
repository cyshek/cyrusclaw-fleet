"""80/20 equity-book × core4-TSMOM BLEND PAPER-CLOCK tracker.

PAPER ONLY. Out-of-band. NO live Alpaca orders, ever.

WHY THIS EXISTS
---------------
The multi-asset TSMOM blend (80% ERC-weighted live equity book + 20% core4-TSMOM
sleeve) cleared the bench's *risk-adjusted* bar in-sample: combined full-period
Sharpe 0.992 vs the book-only 0.923 (ΔSharpe +0.069, +7.5% rel), maxDD −6.98%,
with corr(book, core4) = +0.046 and crisis-positive core4 offsets in 2020 (+4.7%)
and 2022 (+2.8%). Verdict was AMBER — a real, robust, but modest, vol-trim-driven,
*in-sample* lift whose entire crisis-offset value rode on two windows (and reversed
in 2018-Q4). Reports:
  reports/EQUITYBOOK_TSMOM_BLEND_20260624T220759Z.md  (the X-sweep + verdict)
  reports/TSMOM_BLEND_TEST_20260624.md                (independent reproduction)

The AMBER report's explicit recommendation: *"paper-track the X=0.80 blend (20%
core4) as a candidate diversifier overlay and watch whether the 2020/2022-style
crisis offset recurs out-of-sample"* — and do NOT wire it live on the strength of
an in-sample +0.07 Sharpe. The 80/20 mandate (main, 2026-06-25) is Sharpe-focused
and confirms: START THE PAPER CLOCK, don't move real money.

This is PATH A (the same shape as runner/allocator_paper_tracker.py): a
backtest-FORWARD daily tracker. Each run it:
  1. Re-runs the VALIDATED ingredients by calling them DIRECTLY (no reimplementation):
       - Ingredient A (book): _xstrat_corr.build_all_series() rebuilds all 8 live
         strategy daily-return series live from the engines (run_backtest +
         vol-target/COT/allocator harnesses) over ALL price history through the
         latest cached close; each sleeve is vol-normalized to TARGET_VOL ann vol
         on the common window, THEN ERC-risk-weighted by reports/_erc_weights.json
         ["risk_weights"] -> the honest UNIT-RISK book return (this is the
         validated _blend_volnorm.py construction; see CONSTRUCTION HONESTY).
       - Ingredient B (core4): _tsmom_engine.run_tsmom(["DBC","GLD","TLT","UUP"],
         lookback_m=12, skip_m=1, weighting="ew") -> the validated 12-1 long/flat
         EW-in-trend daily net series.
  2. Forms the 80/20 daily blend return on the latest fully-closed day, plus the
     SPX daily return on the same day, and the running cum-since-inception for both.
  3. Logs an idempotent daily snapshot row to a SIDE DB (tsmom_blend_paper.db).

The forward record (rows from the day this tracker starts running onward) is the
HONEST paper clock: the model's realized daily return on the path actually observed,
marked at each day's close, with zero live orders.

CONSTRUCTION HONESTY (carried verbatim from the report + _blend_volnorm.py)
---------------------------------------------------------------------------
The 8 per-strategy series are NOT all the same leverage/notional convention: the
live _xstrat_corr rebuild emits the 6 event sleeves as equity-curve returns on a
~$87/$100k position (~0.01% ann vol, near-flat), while tqqq_cot_combo /
allocator_blend embed their real leverage at ~16-20% ann vol. Applying ERC
risk-weights (built for UNIT-vol bets) to those RAW mixed-scale series does NOT
equalize risk and inflates the book Sharpe via the near-zero-vol sleeves (the raw
capital-weighted book reads a misleading ~1.54). The validated fix (Patel et al.
style, and exactly what _blend_volnorm.py does): scale EACH sleeve to a common
TARGET_VOL (10% ann) FIRST, THEN ERC-risk-weight -> an honest unit-risk book that
reproduces the report's baseline Sharpe ~0.96 / 80/20 ~1.04 on current live data.
core4 is blended AS-IS (its real standalone) and earns 0% on idle cash (a
conservative floor; real managed futures would earn collateral T-bill yield).

NO-LOOKAHEAD
------------
Every number comes from the validated engines, lookahead-safe by construction (each
backtest computes signals on data <= D; core4 ranks on prior month-end). The tracker
only ever reads the LAST fully-closed common day's already-realized blend return; it
cannot peek forward.

CUM-SINCE-START SEMANTICS
-------------------------
`cum_ret_since_start` / `cum_spx_since_start` compound the daily returns this tracker
has LOGGED (from its FIRST row forward), NOT the full backtest equity. On the very
first run that is just today's single daily return; it accumulates honestly after.

Entry points (importable + CLI):
  snapshot_today(db_path) -> dict        # log today's blend snapshot (idempotent)
  paper_clock_stats(db_path) -> dict     # running stats over forward rows
  check_staleness(db_path) -> int        # 3 if clock >=2 trading days behind latest SPX

DB: workspace root tsmom_blend_paper.db (default).
Run: python3 runner/tsmom_blend_paper_tracker.py                 # snapshot + stats
     python3 runner/tsmom_blend_paper_tracker.py --stats         # just running stats
     python3 runner/tsmom_blend_paper_tracker.py --check-staleness
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(WORKSPACE / "tsmom_blend_paper.db")

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# ----- validated blend config (keep in sync with the report / MEMORY) -------
BLEND_X = 0.80                     # fraction in the equity book (1-X in core4)
CORE4_ASSETS = ["DBC", "GLD", "TLT", "UUP"]
CORE4_LOOKBACK_M = 12
CORE4_SKIP_M = 1
CORE4_WEIGHTING = "ew"
CORE4_START = "2008-05-01"
SLEEVE_REBAL_BPS = 2.0             # inter-sleeve rebalance cost (one-way); modeled in report
TRADING_DAYS = 252
# The 8 live strategies, fixed order = the ERC risk-weight keys.
LIVE8 = [
    "breakout_xlk__mut_c382b1", "sma_crossover_qqq_regime", "sma_crossover_qqq_rth",
    "rsi_oversold_spy", "volume_breakout_qqq", "macd_momentum_iwm",
    "tqqq_cot_combo", "allocator_blend",
]
ERC_WEIGHTS_PATH = WORKSPACE / "reports" / "_erc_weights.json"
ERC_RISK_KEY = "risk_weights"     # ERC risk-weights (unit-vol bets) -> normalized
TARGET_VOL = 0.10                 # per-sleeve ann vol BEFORE ERC weighting
# WHY VOL-NORMALIZE FIRST (the validated construction, see _blend_volnorm.py):
# the live _xstrat_corr rebuild emits the 6 event sleeves as equity-curve returns
# on a ~$87/$100k position (~0.01% ann vol, near-flat) while tqqq_cot_combo /
# allocator_blend are full-notional vol-target harness returns (16-19% ann vol).
# Applying ERC risk-weights (designed for UNIT-vol bets) to those raw mixed-scale
# series does NOT equalize risk and inflates book Sharpe via the ~0-vol sleeves
# (the raw capital-weighted book reads a misleading ~1.54). The honest book scales
# EACH sleeve to TARGET_VOL first, THEN ERC-weights -> a true unit-risk book that
# reproduces the validated baseline Sharpe ~0.96 / 80/20 ~1.04 on current live data.

# Every symbol whose daily-bars cache gates the blend's markable frontier (book
# single-symbol legs + the TQQQ special + core4 + the SPY benchmark). The daily
# bars cache (runner.daily_bars_cache.get_daily) serves a parsed cache AS-IS once
# written and never auto-refetches, so without an explicit refresh the freshest
# print never lands and the common-day frontier (mark = common[-1]) freezes at
# whichever symbol is stalest. This is exactly the allocator tracker's _refresh_bars
# discipline (it force-refreshes ^GSPC/TQQQ/QQQ/SPY/GLD/TLT for the same reason);
# the tsmom tracker originally shipped WITHOUT it, which is why its paper clock
# stuck at inception while the allocator clock advanced daily.
_REFRESH_SYMBOLS: List[str] = [
    "XLK", "QQQ", "SPY", "IWM", "TQQQ",   # book single-symbol legs + VT/COT underlier
    "DBC", "GLD", "TLT", "UUP",           # core4 TSMOM sleeve
]


def _refresh_bars(symbols: List[str]) -> Dict[str, str]:
    """Force a re-fetch of each symbol's daily bars so the latest close is present
    before we compute today's snapshot. Mirrors allocator_paper_tracker._refresh_bars.
    Resilient: a per-symbol fetch failure is logged and we fall back to whatever is
    already cached (never crash the daily tracker over a transient Yahoo hiccup).
    """
    from runner import daily_bars_cache as dbc
    status: Dict[str, str] = {}
    for sym in symbols:
        try:
            bars = dbc.get_daily(sym, refresh=True)
            status[sym] = bars[-1]["date"] if bars else "empty"
        except Exception as exc:  # noqa: BLE001 - intentionally broad; never fatal
            try:
                bars = dbc.get_daily(sym)  # fall back to whatever is cached
                status[sym] = "%s(cached, refresh failed: %s)" % (
                    bars[-1]["date"] if bars else "empty", type(exc).__name__)
            except Exception:
                status[sym] = "unavailable: %s" % type(exc).__name__
    return status


# --------------------------------------------------------------------------- #
# DB schema (mirrors allocator_paper_tracker's daily_snapshots shape)
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,                 -- trading date marked (latest common close)
    x_book REAL,                      -- blend weight on the equity book (BLEND_X)
    core4_holds TEXT,                 -- JSON list of core4 names currently in-trend
    book_daily_ret REAL,              -- equity book realized return ON `date`
    core4_daily_ret REAL,             -- core4 realized return ON `date`
    daily_ret REAL,                   -- 80/20 blend realized return ON `date`
    cum_ret_since_start REAL,         -- blend cumulative return over logged rows
    spx_daily_ret REAL,               -- SPX realized return ON `date`
    cum_spx_since_start REAL,         -- SPX cumulative return over logged rows
    engine_full_sharpe REAL,          -- blend full-period backtest Sharpe at this run (drift check)
    engine_book_sharpe REAL,          -- book-only full-period Sharpe at this run
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
# math helpers (population-stdev annualized — matches the engines)
# --------------------------------------------------------------------------- #
def _sharpe(returns: List[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    m = sum(returns) / n
    var = sum((r - m) ** 2 for r in returns) / (n - 1)
    sd = math.sqrt(var)
    if sd <= 1e-12:
        return 0.0
    return (m / sd) * math.sqrt(TRADING_DAYS)


def _compound(returns: List[float]) -> float:
    g = 1.0
    for r in returns:
        g *= (1.0 + r)
    return g - 1.0


# --------------------------------------------------------------------------- #
# Build the two ingredient daily-return maps live to the latest close.
# --------------------------------------------------------------------------- #
def _ann_vol(returns: List[float]) -> float:
    """Annualized sample-stdev volatility (matches _blend_volnorm.ann_vol)."""
    n = len(returns)
    if n < 3:
        return 0.0
    m = sum(returns) / n
    v = sum((x - m) ** 2 for x in returns) / (n - 1)
    return math.sqrt(v) * math.sqrt(TRADING_DAYS)


def _load_risk_weights() -> Dict[str, float]:
    """ERC risk-weights normalized to sum 1 over the LIVE8 (the unit-vol bet
    weights the shipped book uses)."""
    erc = json.loads(ERC_WEIGHTS_PATH.read_text())
    rw = erc[ERC_RISK_KEY]
    sub = {k: float(rw[k]) for k in LIVE8 if k in rw}
    s = sum(sub.values())
    if s <= 0:
        raise ValueError("ERC risk weights sum to 0")
    return {k: v / s for k, v in sub.items()}


def build_ingredients() -> Tuple[Dict[str, float], Dict[str, float],
                                 Dict[str, float], Dict[str, List[str]], Dict[str, float]]:
    """Return (book_ret_by_date, core4_ret_by_date, spy_ret_by_date,
    core4_holds_by_date, risk_weights).

    VALIDATED CONSTRUCTION (mirrors _blend_volnorm.py exactly):
      1. Rebuild all 8 live strategy daily series via _xstrat_corr (live engines).
      2. On the 8-series common window, scale EACH sleeve to TARGET_VOL ann vol
         (scale_i = TARGET_VOL / ann_vol_i).  This removes the ~$87/$100k
         position-size artifact so ERC risk-weights apply to true unit-vol bets.
      3. book_ret[t] = Σ_i rwn_i · scale_i · series_i[t]  (vol-normed, ERC book).
      core4_ret[t] = validated run_tsmom net return on t (blended AS-IS, not scaled).
      spy_ret[t]   = SPY close-to-close return on t (same cache).
      core4_holds  = which of DBC/GLD/TLT/UUP were in-trend (held) entering t.

    The per-sleeve scale recalibrates each run as the common window grows (the
    same recompute-to-latest-close discipline as allocator_paper_tracker's
    weights) -- so the forward book stays on a true unit-risk footing.
    """
    import _xstrat_corr as X           # noqa: WPS433  (workspace-root research module)
    import _tsmom_engine as E          # noqa: WPS433

    rwn = _load_risk_weights()
    # Refresh the daily-bars cache to the latest close BEFORE rebuilding the live
    # series, so the book/core4/SPY frontier marks to today's print instead of
    # freezing at whatever symbol's cache is stalest (the inception-freeze bug).
    refresh_status = _refresh_bars(_REFRESH_SYMBOLS)
    print("[tsmom_blend] bar refresh: %s" % json.dumps(refresh_status), flush=True)
    series, _meta, spy_ret = X.build_all_series()

    # 8-series common window.
    date_sets = [set(series[nm].keys()) for nm in LIVE8 if nm in series]
    if len(date_sets) != len(LIVE8):
        missing = [nm for nm in LIVE8 if nm not in series]
        raise RuntimeError(f"book series missing strategies: {missing}")
    book_dates = sorted(set.intersection(*date_sets))

    # per-sleeve scale to TARGET_VOL on the common window.
    scale: Dict[str, float] = {}
    for nm in LIVE8:
        v = _ann_vol([series[nm][d] for d in book_dates])
        scale[nm] = (TARGET_VOL / v) if v > 1e-9 else 0.0

    # vol-normalized, ERC-weighted book.
    book_ret = {d: sum(rwn[nm] * scale[nm] * series[nm][d] for nm in LIVE8)
                for d in book_dates}

    # core4 validated engine to the latest close (blended AS-IS).
    out = E.run_tsmom(CORE4_ASSETS, lookback_m=CORE4_LOOKBACK_M,
                      skip_m=CORE4_SKIP_M, weighting=CORE4_WEIGHTING,
                      start_date=CORE4_START)
    core4_ret = {d: r for d, r in zip(out["dates"], out["net"])}
    # weights_hist is a list of (rebal_date, {sym: w}) at MONTHLY rebalances
    # only. The holdings in force ON a given mark date = the most recent
    # rebalance's in-trend names as-of that date. We record the LATEST
    # rebalance snapshot's holds (sufficient for the snapshot's mark day,
    # which is always >= the last rebalance).
    core4_holds: Dict[str, List[str]] = {}
    wh = out.get("weights_hist") or []
    for rebal_date, wmap in wh:
        if isinstance(wmap, dict):
            core4_holds[rebal_date] = [a for a, wt in wmap.items() if wt and wt > 0]

    return book_ret, core4_ret, spy_ret, core4_holds, rwn


def _full_period_sharpes(book_ret: Dict[str, float],
                         core4_ret: Dict[str, float]) -> Tuple[float, float, str, str, int]:
    """Full-period blend + book Sharpe on the common window (drift monitor)."""
    common = sorted(set(book_ret) & set(core4_ret))
    if not common:
        return 0.0, 0.0, "", "", 0
    blend = [BLEND_X * book_ret[d] + (1.0 - BLEND_X) * core4_ret[d] for d in common]
    book = [book_ret[d] for d in common]
    return (_sharpe(blend), _sharpe(book), common[0], common[-1], len(common))


# --------------------------------------------------------------------------- #
# snapshot
# --------------------------------------------------------------------------- #
def snapshot_today(db_path: str = DEFAULT_DB) -> dict:
    """Compute + log today's (latest-closed-common-day) blend snapshot. Idempotent
    on `date` (UNIQUE). Returns the row dict (or the existing row if already logged)."""
    book_ret, core4_ret, spy_ret, core4_holds, _w = build_ingredients()
    common = sorted(set(book_ret) & set(core4_ret) & set(spy_ret))
    if not common:
        raise RuntimeError("no common date across book/core4/SPY series")
    mark = common[-1]                          # latest fully-closed common day
    b = book_ret[mark]
    c = core4_ret[mark]
    blend = BLEND_X * b + (1.0 - BLEND_X) * c
    spx = spy_ret[mark]
    # core4 holds in force on `mark` = most recent rebalance snapshot <= mark.
    holds = []
    rebal_dates = sorted(d for d in core4_holds if d <= mark)
    if rebal_dates:
        holds = core4_holds[rebal_dates[-1]]

    blend_sh, book_sh, _s0, _s1, _n = _full_period_sharpes(book_ret, core4_ret)

    conn = _get_conn(db_path)
    try:
        existing = conn.execute(
            "SELECT * FROM daily_snapshots WHERE date = ?", (mark,)).fetchone()
        if existing is not None:
            row = dict(existing)
            row["_already_logged"] = True
            return row

        # cum-since-start = prior cum compounded with today's return.
        prev = conn.execute(
            "SELECT cum_ret_since_start, cum_spx_since_start FROM daily_snapshots "
            "ORDER BY date DESC LIMIT 1").fetchone()
        if prev is None:
            cum_ret = blend
            cum_spx = spx
        else:
            cum_ret = (1.0 + (prev["cum_ret_since_start"] or 0.0)) * (1.0 + blend) - 1.0
            cum_spx = (1.0 + (prev["cum_spx_since_start"] or 0.0)) * (1.0 + spx) - 1.0

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO daily_snapshots (date, x_book, core4_holds, book_daily_ret, "
            "core4_daily_ret, daily_ret, cum_ret_since_start, spx_daily_ret, "
            "cum_spx_since_start, engine_full_sharpe, engine_book_sharpe, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (mark, BLEND_X, json.dumps(holds), b, c, blend, cum_ret, spx, cum_spx,
             blend_sh, book_sh, now))
        conn.commit()
        return {
            "date": mark, "x_book": BLEND_X, "core4_holds": holds,
            "book_daily_ret": b, "core4_daily_ret": c, "daily_ret": blend,
            "cum_ret_since_start": cum_ret, "spx_daily_ret": spx,
            "cum_spx_since_start": cum_spx, "engine_full_sharpe": blend_sh,
            "engine_book_sharpe": book_sh, "created_at": now,
            "_already_logged": False,
        }
    finally:
        conn.close()


def paper_clock_stats(db_path: str = DEFAULT_DB) -> dict:
    """Running stats over the FORWARD rows (paper-clock inception -> latest)."""
    conn = _get_conn(db_path)
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM daily_snapshots ORDER BY date ASC").fetchall()]
    finally:
        conn.close()
    if not rows:
        return {"n_rows": 0}
    blend = [r["daily_ret"] for r in rows]
    spx = [r["spx_daily_ret"] for r in rows]
    return {
        "n_rows": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "blend_cum_ret": rows[-1]["cum_ret_since_start"],
        "spx_cum_ret": rows[-1]["cum_spx_since_start"],
        "blend_sharpe_since_start": _sharpe(blend),
        "spx_sharpe_since_start": _sharpe(spx),
        "blend_minus_spx_cum": (rows[-1]["cum_ret_since_start"]
                                - rows[-1]["cum_spx_since_start"]),
        "latest_engine_full_sharpe": rows[-1]["engine_full_sharpe"],
        "latest_engine_book_sharpe": rows[-1]["engine_book_sharpe"],
    }


def check_staleness(db_path: str = DEFAULT_DB, max_trading_days: int = 3,
                    max_age_days: int = 4) -> int:
    """Return 3 if the paper clock looks STALLED, else 0.

    Catches BOTH failure modes:
      (a) FROZEN FRONTIER (the inception-freeze bug): the cron runs every day but
          the newest snapshot DATE stops advancing because a book ingredient's
          bars cache went stale, so mark = common[-1] sticks. A created_at-only
          guard is BLIND to this (created_at refreshes every run while the clock
          is actually frozen) -- which is exactly how it slipped for a week.
      (b) CRON STOPPED: no new run at all -> the newest row's created_at ages out.

    (a) is detected by counting TRADING DAYS (not calendar days, so weekends do
    not inflate the gap) between the newest snapshot DATE and the latest SPY daily
    bar. With the bars-cache refresh now wired into build_ingredients the residual
    book lag is <=1 trading day, so a tolerance of `max_trading_days` (default 3,
    covering a weekend + a post-close-before-print day of slack) flags a genuine
    freeze without false-positiving on the structural ~1-day lag. (b) is the
    original created_at age check, kept as a secondary backstop.
    """
    conn = _get_conn(db_path)
    try:
        last = conn.execute(
            "SELECT date, created_at FROM daily_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if last is None:
        return 0  # no rows yet = clock not started, not stale

    # (a) FROZEN-FRONTIER guard: snapshot date vs latest SPY bar, in TRADING days.
    snap_date = last["date"]
    if snap_date:
        try:
            from runner import daily_bars_cache as dbc
            spy_dates = [b["date"] for b in dbc.get_daily("SPY")]
            if spy_dates:
                latest_spy = spy_dates[-1]
                # trading-day gap = number of SPY bars strictly after the snapshot date.
                gap_td = sum(1 for d in spy_dates if d > snap_date)
                if gap_td > max_trading_days:
                    print(
                        "[tsmom_blend] STALE-FRONTIER: newest snapshot %s is %d "
                        "trading day(s) behind latest SPY bar %s (tol=%d)"
                        % (snap_date, gap_td, latest_spy, max_trading_days),
                        flush=True)
                    return 3
        except Exception:
            pass  # SPY fetch is best-effort; fall through to the created_at backstop

    # (b) CRON-STOPPED backstop: newest row's created_at age in wall-clock days.
    if not last["created_at"]:
        return 0
    try:
        written = datetime.fromisoformat(last["created_at"])
    except ValueError:
        return 0
    if written.tzinfo is None:
        written = written.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - written).total_seconds() / 86400.0
    return 3 if age_days > max_age_days else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_stats(st: dict) -> None:
    if st.get("n_rows", 0) == 0:
        print("tsmom_blend paper clock: no rows yet.")
        return
    print(f"tsmom_blend paper clock  [{st['first_date']} -> {st['last_date']}]  "
          f"n={st['n_rows']}")
    print(f"  blend cum {st['blend_cum_ret']*100:+.2f}%  vs SPX cum "
          f"{st['spx_cum_ret']*100:+.2f}%  (Δ {st['blend_minus_spx_cum']*100:+.2f} pts)")
    print(f"  blend Sharpe-since-start {st['blend_sharpe_since_start']:.3f}  "
          f"vs SPX {st['spx_sharpe_since_start']:.3f}")
    print(f"  engine full-period Sharpe (drift monitor): blend "
          f"{st['latest_engine_full_sharpe']:.3f} / book "
          f"{st['latest_engine_book_sharpe']:.3f}")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    db_path = DEFAULT_DB
    if "--db" in argv:
        i = argv.index("--db")
        db_path = argv[i + 1]
        del argv[i:i + 2]

    if "--check-staleness" in argv:
        rc = check_staleness(db_path)
        if rc == 3:
            print("STALE: tsmom_blend paper clock has not written a new row in "
                  ">4 days -- the daily cron may have stopped.")
        else:
            print("tsmom_blend paper clock fresh (newest row written within 4 days).")
        return rc

    if "--stats" in argv:
        _print_stats(paper_clock_stats(db_path))
        return 0

    # default: snapshot today + print stats.
    row = snapshot_today(db_path)
    tag = "already-logged" if row.get("_already_logged") else "logged"
    print(f"[{tag}] {row['date']}  blend {row['daily_ret']*100:+.3f}%  "
          f"(book {row['book_daily_ret']*100:+.3f}% x{BLEND_X:.2f} + core4 "
          f"{row['core4_daily_ret']*100:+.3f}% x{1-BLEND_X:.2f})  "
          f"SPX {row['spx_daily_ret']*100:+.3f}%")
    _print_stats(paper_clock_stats(db_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
