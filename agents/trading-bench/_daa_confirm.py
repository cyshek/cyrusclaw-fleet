"""CONFIRM-OR-KILL: Keller/Keuning DAA "canary universe" breadth-momentum crash switch.

Honest test of whether DAA's de-risking-to-cash canary gate is a REAL edge
orthogonal to our existing allocator_blend (which has NO crash-off switch).

MECHANISM (Keller/Keuning "Defensive Asset Allocation", 2018):
  CANARY universe = {VWO, BND}, checked monthly via 13612W momentum.
      13612W = (12*r1 + 4*r3 + 2*r6 + 1*r12)/4  (rN = trailing N-month total return).
  RISK universe G12 = {SPY, IWM, QQQ, VGK, EWJ, VWO, VNQ, GSG, GLD, TLT, HYG, LQD},
      equal-weight top T=6 by 13612W.
  CASH/bond universe = {SHY, IEF, LQD}, pick best single by 13612W.
  ALLOCATION CASCADE (signal asset != traded asset = the innovation):
      (a) BOTH canaries 13612W > 0  -> 100% into top-6 risk EW.
      (b) exactly ONE canary > 0    -> 50% top-3 risk EW + 50% best single bond.
      (c) BOTH canaries <= 0        -> 100% best single bond.

LOOKAHEAD CONTRACT (mirrors _sigimprove_tests.run_sector_rotation exactly):
  Rank on the close of the LAST trading day of the prior month (cal[i-1] when
  cal[i] is a month-first), hold from the FIRST trading day of the new month.
  rN uses ~21*N trading days back on the common calendar, computed from data
  through the PRIOR month-end close. Decision day strictly precedes the held
  period -> leak-free by construction.

COST: cost_bps one-way on the fraction of book turned over each monthly rebalance
  (same convention as run_sector_rotation: cost = (cost_bps/10000)*turn).

DATA: free Yahoo daily adjclose via runner.daily_bars_cache.get_daily(), monthly
  resample. Live-ETF era only; common calendar = intersection of all universe
  tickers (HYG/BND bound the start ~2007-04). No synthesized pre-inception data.

DELIVERABLES: DAA equity curve + same-path SPX (^GSPC) + same-path control
  (run_sector_rotation top-2 of {SPY,QQQ,GLD,TLT}); full-period continuous-span
  Sharpe via runner.fp_sharpe; IS/OOS split (train<=2019, OOS 2020+); maxDD;
  total/annualized return vs SPX same-path; SPY-correlation of daily returns;
  avg defensive (cash/bond) fraction; MANDATORY +1-bar lag canary.

Run: python3 _daa_confirm.py    Writes reports/DAA_VERDICT_<UTCSTAMP>.md + json.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from runner.fp_sharpe import sharpe_from_returns
from runner.backtest import bars_per_year
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity, TRADING_DAYS,
)

# Reuse the canonical lookahead-safe monthly-rotation template as the control.
from _sigimprove_tests import run_sector_rotation

# --------------------------------------------------------------------------- #
# Universes
# --------------------------------------------------------------------------- #
CANARY = ["VWO", "BND"]
RISK_G12 = ["SPY", "IWM", "QQQ", "VGK", "EWJ", "VWO", "VNQ", "GSG", "GLD", "TLT", "HYG", "LQD"]
CASH = ["SHY", "IEF", "LQD"]
BENCH = "^GSPC"
ALL_TICKERS = sorted(set(CANARY + RISK_G12 + CASH))

TOP_RISK_FULL = 6   # both canaries up
TOP_RISK_HALF = 3   # exactly one canary up
COST_BPS = 2.0
OOS_SPLIT = "2019-12-31"   # train <= 2019, OOS 2020+


# --------------------------------------------------------------------------- #
# 13612W momentum (lookahead-safe via end_idx on the common calendar)
# --------------------------------------------------------------------------- #
def _trailing_return(close: Dict[str, Dict[str, float]], a: str, cal: List[str],
                     end_idx: int, lb_days: int) -> Optional[float]:
    """Total return of asset `a` over [end_idx - lb_days, end_idx] on `cal`."""
    if end_idx - lb_days < 0:
        return None
    d_end = cal[end_idx]
    d_start = cal[end_idx - lb_days]
    c_end = close[a].get(d_end)
    c_start = close[a].get(d_start)
    if c_end is None or c_start is None or c_start <= 0:
        return None
    return c_end / c_start - 1.0


def _mom_13612w(close: Dict[str, Dict[str, float]], a: str, cal: List[str],
                end_idx: int) -> Optional[float]:
    """13612W = (12*r1 + 4*r3 + 2*r6 + 1*r12)/4, rN over ~21*N trading days,
    measured through cal[end_idx] (the prior month-end close)."""
    r1 = _trailing_return(close, a, cal, end_idx, 21 * 1)
    r3 = _trailing_return(close, a, cal, end_idx, 21 * 3)
    r6 = _trailing_return(close, a, cal, end_idx, 21 * 6)
    r12 = _trailing_return(close, a, cal, end_idx, 21 * 12)
    if r1 is None or r3 is None or r6 is None or r12 is None:
        return None
    return (12.0 * r1 + 4.0 * r3 + 2.0 * r6 + 1.0 * r12) / 4.0


# --------------------------------------------------------------------------- #
# DAA backtest
# --------------------------------------------------------------------------- #
def run_daa(start: str = "2005-01-01", end: Optional[str] = None,
            cost_bps: float = COST_BPS, signal_lag_extra: int = 0) -> Dict:
    """Keller/Keuning DAA on the common calendar.

    signal_lag_extra: extra trading-day lag applied to the SIGNAL decision day
      (the +1-bar canary). 0 = canonical (rank on prior month-end close). 1 =
      rank one extra trading day earlier; if edge survives only at 0 and
      degrades/flips at 1, the "edge" is timing noise.
    """
    bars = {a: dbc.get_daily(a) for a in ALL_TICKERS}
    bench_bars = dbc.get_daily(BENCH)

    if end is None:
        end = min(b[-1]["date"] for b in bars.values())
    date_sets = [set(b["date"] for b in bars[a]) for a in ALL_TICKERS]
    common = sorted(set.intersection(*date_sets))
    cal = [d for d in common if start <= d <= end]

    close = {a: {b["date"]: b["adjclose"] for b in bars[a]} for a in ALL_TICKERS}
    bench_close = {b["date"]: b["adjclose"] for b in bench_bars}

    # month boundaries: first trading day of each calendar month in `cal`
    month_first: List[int] = []
    seen = set()
    for idx, d in enumerate(cal):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_first.append(idx)
    month_first_set = set(month_first)

    def best_bond(end_idx: int) -> Optional[str]:
        scored = [(c, _mom_13612w(close, c, cal, end_idx)) for c in CASH]
        scored = [(c, m) for (c, m) in scored if m is not None]
        if not scored:
            return None
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[0][0]

    def top_risk(end_idx: int, k: int) -> List[str]:
        scored = [(a, _mom_13612w(close, a, cal, end_idx)) for a in RISK_G12]
        scored = [(a, m) for (a, m) in scored if m is not None]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [a for (a, m) in scored[:k]]

    equity = [1.0]
    eq_dates = [cal[0]]
    cur_weights: Dict[str, float] = {a: 0.0 for a in ALL_TICKERS}
    n_rebalances = 0
    turnover_total = 0.0
    holdings_log: List[Dict] = []
    # per-rebalance defensive (cash/bond-bucket) fraction, captured at each month-first
    defensive_fracs: List[float] = []
    regime_counts = {"risk_on": 0, "half": 0, "crash_off": 0}

    for i in range(1, len(cal)):
        d = cal[i]
        cost = 0.0
        if i in month_first_set:
            sig_idx = i - 1 - signal_lag_extra  # rank day (prior month-end, optionally extra-lagged)
            if sig_idx < 0:
                # not enough history yet: stay flat (all cash, 0 weight) this month
                new_t = {a: 0.0 for a in ALL_TICKERS}
                defensive_fracs.append(1.0)
            else:
                cmom = {c: _mom_13612w(close, c, cal, sig_idx) for c in CANARY}
                # require both canary signals defined; else treat undefined as <=0 (defensive)
                n_up = sum(1 for c in CANARY if (cmom[c] is not None and cmom[c] > 0.0))
                new_t = {a: 0.0 for a in ALL_TICKERS}
                if n_up == 2:
                    top = top_risk(sig_idx, TOP_RISK_FULL)
                    if top:
                        w = 1.0 / len(top)
                        for a in top:
                            new_t[a] += w
                    regime_counts["risk_on"] += 1
                    defensive_fracs.append(0.0)
                elif n_up == 1:
                    top = top_risk(sig_idx, TOP_RISK_HALF)
                    if top:
                        w = 0.5 / len(top)
                        for a in top:
                            new_t[a] += w
                    bb = best_bond(sig_idx)
                    if bb is not None:
                        new_t[bb] += 0.5
                    regime_counts["half"] += 1
                    defensive_fracs.append(0.5)
                else:
                    bb = best_bond(sig_idx)
                    if bb is not None:
                        new_t[bb] += 1.0
                    regime_counts["crash_off"] += 1
                    defensive_fracs.append(1.0)

            turn = sum(abs(new_t[a] - cur_weights[a]) for a in ALL_TICKERS)
            if turn > 1e-9:
                n_rebalances += 1
                turnover_total += turn
            cost = (cost_bps / 10000.0) * turn
            cur_weights = dict(new_t)
            holdings_log.append({
                "date": d,
                "holds": {a: round(cur_weights[a], 4) for a in ALL_TICKERS if cur_weights[a] > 0},
            })

        # daily blended return using cur_weights, held over day d
        day_ret = 0.0
        for a in ALL_TICKERS:
            cn = close[a].get(d)
            cp = close[a].get(cal[i - 1])
            r = (cn / cp - 1.0) if (cn is not None and cp is not None and cp > 0) else 0.0
            day_ret += cur_weights[a] * r
        new_eq = equity[-1] * (1.0 + day_ret) * (1.0 - cost)
        equity.append(new_eq)
        eq_dates.append(d)

    strat_stats = _stats_from_equity(eq_dates, equity, [True] * (len(eq_dates) - 1), n_rebalances)

    # SPX benchmark on the SAME dates
    spx_eq = [1.0]
    for j in range(1, len(eq_dates)):
        dn = eq_dates[j]
        dp = eq_dates[j - 1]
        cn = bench_close.get(dn)
        cp = bench_close.get(dp)
        r = (cn / cp - 1.0) if (cn is not None and cp is not None and cp > 0) else 0.0
        spx_eq.append(spx_eq[-1] * (1.0 + r))
    spx_stats = _stats_from_equity(eq_dates, spx_eq)

    avg_def = sum(defensive_fracs) / len(defensive_fracs) if defensive_fracs else 0.0

    return {
        "window": {"start": eq_dates[0], "end": eq_dates[-1], "n_days": len(eq_dates)},
        "strategy": {"stats": dict(strat_stats.__dict__), "dates": eq_dates, "equity": equity},
        "spx": {"stats": dict(spx_stats.__dict__), "equity": spx_eq},
        "n_rebalances": n_rebalances,
        "avg_turnover_per_rebal": (turnover_total / n_rebalances) if n_rebalances else 0.0,
        "avg_defensive_frac": avg_def,
        "regime_counts": regime_counts,
        "pos_log": holdings_log,
        "signal_lag_extra": signal_lag_extra,
    }


# --------------------------------------------------------------------------- #
# Metrics helpers
# --------------------------------------------------------------------------- #
def _daily_rets(equity: List[float]) -> List[float]:
    out = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev > 0:
            out.append(equity[i] / prev - 1.0)
    return out


def _fp_sharpe(equity: List[float]) -> Tuple[float, int]:
    rets = _daily_rets(equity)
    bpy = bars_per_year("1Day", False)
    return sharpe_from_returns(rets, bpy), len(rets)


def _corr(xs: List[float], ys: List[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    xs = xs[:n]
    ys = ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def _split_stats(dates: List[str], equity: List[float], split: str) -> Dict:
    """Rebased IS/OOS sub-curve stats. IS = dates <= split, OOS = dates > split."""
    is_idx = [k for k, d in enumerate(dates) if d <= split]
    oos_idx = [k for k, d in enumerate(dates) if d > split]
    out: Dict = {}
    if len(is_idx) >= 2:
        ds = [dates[k] for k in is_idx]
        eq = [equity[k] for k in is_idx]
        eq = [v / eq[0] for v in eq]
        st = _stats_from_equity(ds, eq)
        fps, n = _fp_sharpe(eq)
        out["is"] = {"stats": dict(st.__dict__), "fp_sharpe": fps, "n": n,
                     "start": ds[0], "end": ds[-1]}
    if len(oos_idx) >= 2:
        ds = [dates[k] for k in oos_idx]
        eq = [equity[k] for k in oos_idx]
        eq = [v / eq[0] for v in eq]
        st = _stats_from_equity(ds, eq)
        fps, n = _fp_sharpe(eq)
        out["oos"] = {"stats": dict(st.__dict__), "fp_sharpe": fps, "n": n,
                      "start": ds[0], "end": ds[-1]}
    return out


def main():
    utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    res: Dict = {"utc": utc}

    # ---- DAA canonical (lag 0) and +1-bar lag canary ----
    daa0 = run_daa(signal_lag_extra=0)
    daa1 = run_daa(signal_lag_extra=1)

    # ---- Control: run_sector_rotation top-2 of {SPY,QQQ,GLD,TLT} ----
    # match DAA's window so SPX path + comparison are apples-to-apples
    w_start = daa0["window"]["start"]
    w_end = daa0["window"]["end"]
    ctrl = run_sector_rotation(["SPY", "QQQ", "GLD", "TLT"], bench=BENCH,
                               lookback_months=3, hold_top=2, cost_bps=COST_BPS,
                               start=w_start, end=w_end)

    # ---- full-period continuous-span Sharpe for each ----
    daa0_fps, daa0_n = _fp_sharpe(daa0["strategy"]["equity"])
    daa1_fps, daa1_n = _fp_sharpe(daa1["strategy"]["equity"])
    spx_fps, spx_n = _fp_sharpe(daa0["spx"]["equity"])
    ctrl_fps, ctrl_n = _fp_sharpe(ctrl["strategy"]["equity"])

    # ---- SPY-correlation of daily returns (DAA vs SPX same path) ----
    daa0_rets = _daily_rets(daa0["strategy"]["equity"])
    spx_rets = _daily_rets(daa0["spx"]["equity"])
    ctrl_rets = _daily_rets(ctrl["strategy"]["equity"])
    daa_spx_corr = _corr(daa0_rets, spx_rets)
    ctrl_spx_corr = _corr(ctrl_rets, spx_rets)

    # ---- IS/OOS splits ----
    daa0_split = _split_stats(daa0["strategy"]["dates"], daa0["strategy"]["equity"], OOS_SPLIT)
    daa1_split = _split_stats(daa1["strategy"]["dates"], daa1["strategy"]["equity"], OOS_SPLIT)
    ctrl_split = _split_stats(ctrl["strategy"]["dates"], ctrl["strategy"]["equity"], OOS_SPLIT)
    spx_split = _split_stats(daa0["strategy"]["dates"], daa0["spx"]["equity"], OOS_SPLIT)

    res["daa0"] = {
        "window": daa0["window"],
        "stats": daa0["strategy"]["stats"],
        "fp_sharpe": daa0_fps, "fp_n": daa0_n,
        "spy_corr": daa_spx_corr,
        "avg_defensive_frac": daa0["avg_defensive_frac"],
        "regime_counts": daa0["regime_counts"],
        "n_rebalances": daa0["n_rebalances"],
        "avg_turnover_per_rebal": daa0["avg_turnover_per_rebal"],
        "split": daa0_split,
    }
    res["daa1_lag"] = {
        "stats": daa1["strategy"]["stats"],
        "fp_sharpe": daa1_fps, "fp_n": daa1_n,
        "avg_defensive_frac": daa1["avg_defensive_frac"],
        "regime_counts": daa1["regime_counts"],
        "split": daa1_split,
    }
    res["spx"] = {
        "stats": daa0["spx"]["stats"],
        "fp_sharpe": spx_fps, "fp_n": spx_n,
        "split": spx_split,
    }
    res["control_rotation_top2"] = {
        "window": ctrl["window"],
        "stats": ctrl["strategy"]["stats"],
        "fp_sharpe": ctrl_fps, "fp_n": ctrl_n,
        "spy_corr": ctrl_spx_corr,
        "n_rebalances": ctrl["n_rebalances"],
        "split": ctrl_split,
    }

    with open(f"reports/_daa_confirm_{utc}.json", "w") as fh:
        json.dump(res, fh, indent=2, default=str)

    _print_summary(res)
    _write_report(res, utc)
    return res


def _g(d, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _print_summary(res: Dict):
    d0 = res["daa0"]
    d1 = res["daa1_lag"]
    spx = res["spx"]
    ctrl = res["control_rotation_top2"]
    print("=" * 76)
    print("DAA CONFIRM-OR-KILL  |  window", d0["window"]["start"], "->", d0["window"]["end"],
          "(", d0["window"]["n_days"], "days )")
    print("=" * 76)
    def line(tag, stats, fps, corr=None):
        s = stats
        extra = ("  SPYcorr %.3f" % corr) if corr is not None else ""
        print("%-26s FPsharpe %6.3f  CAGR %6.2f%%  maxDD %7.2f%%  totRet %8.1f%%%s" % (
            tag, fps, s["cagr_pct"], s["max_drawdown_pct"], s["total_return_pct"], extra))
    line("DAA (lag0)", d0["stats"], d0["fp_sharpe"], d0["spy_corr"])
    line("DAA (+1-bar lag)", d1["stats"], d1["fp_sharpe"])
    line("CONTROL rot top2", ctrl["stats"], ctrl["fp_sharpe"], ctrl["spy_corr"])
    line("SPX (same path)", spx["stats"], spx["fp_sharpe"])
    print("-" * 76)
    print("DAA avg defensive frac: %.3f   regimes: %s" % (
        d0["avg_defensive_frac"], d0["regime_counts"]))
    print("DAA rebalances: %d   avg turnover/rebal: %.3f" % (
        d0["n_rebalances"], d0["avg_turnover_per_rebal"]))
    print("-" * 76)
    print("OOS (>%s) FP-Sharpe:  DAA %.3f | CONTROL %.3f | SPX %.3f" % (
        OOS_SPLIT,
        _g(d0, "split", "oos", "fp_sharpe", default=float("nan")),
        _g(ctrl, "split", "oos", "fp_sharpe", default=float("nan")),
        _g(spx, "split", "oos", "fp_sharpe", default=float("nan")),
    ))
    print("LAG CANARY: DAA lag0 FP %.3f -> +1bar FP %.3f  (delta %+.3f)" % (
        d0["fp_sharpe"], d1["fp_sharpe"], d1["fp_sharpe"] - d0["fp_sharpe"]))


def _fmt_split(sp: Dict, key: str) -> str:
    blk = sp.get(key) if isinstance(sp, dict) else None
    if not blk:
        return "n/a"
    s = blk["stats"]
    return "FP %.3f | CAGR %.2f%% | maxDD %.2f%% | %s..%s" % (
        blk["fp_sharpe"], s["cagr_pct"], s["max_drawdown_pct"], blk["start"], blk["end"])


def _write_report(res: Dict, utc: str):
    d0 = res["daa0"]
    d1 = res["daa1_lag"]
    spx = res["spx"]
    ctrl = res["control_rotation_top2"]

    # ---- verdict logic ----
    daa_fp = d0["fp_sharpe"]
    ctrl_fp = ctrl["fp_sharpe"]
    spx_fp = spx["fp_sharpe"]
    daa_oos = _g(d0, "split", "oos", "fp_sharpe", default=float("nan"))
    ctrl_oos = _g(ctrl, "split", "oos", "fp_sharpe", default=float("nan"))
    lag_delta = d1["fp_sharpe"] - d0["fp_sharpe"]
    daa_dd = d0["stats"]["max_drawdown_pct"]
    ctrl_dd = ctrl["stats"]["max_drawdown_pct"]
    spx_dd = spx["stats"]["max_drawdown_pct"]

    reasons = []
    # crash-protection check: DAA maxDD should be materially shallower than SPX
    dd_protect = daa_dd - spx_dd  # both negative; positive => DAA shallower (better)
    # edge vs control (orthogonal de-risk switch should AT LEAST not lose to a
    # plain momentum rotation on risk-adjusted terms, and should cut tail risk)
    beats_ctrl_fp = daa_fp >= ctrl_fp - 0.05
    beats_ctrl_oos = (daa_oos >= ctrl_oos - 0.05) if (daa_oos == daa_oos and ctrl_oos == ctrl_oos) else False
    lag_robust = lag_delta <= 0.10  # +1bar should NOT improve materially

    if not lag_robust:
        verdict = "KILL"
        reasons.append("+1-bar lag IMPROVES FP-Sharpe by %+.3f -> timing noise, not a real signal." % lag_delta)
    elif (daa_fp >= spx_fp) and (dd_protect > 5.0) and beats_ctrl_fp and (daa_oos == daa_oos and daa_oos > 0):
        verdict = "GO-as-paper-tracker-candidate"
        reasons.append("FP-Sharpe %.3f >= SPX %.3f; maxDD %.1f%% vs SPX %.1f%% (cuts %.1fpp tail);"
                       " competitive vs control %.3f; OOS FP %.3f>0; lag-robust (delta %+.3f)."
                       % (daa_fp, spx_fp, daa_dd, spx_dd, dd_protect, ctrl_fp, daa_oos, lag_delta))
    elif (dd_protect > 8.0) and (daa_fp >= spx_fp - 0.05):
        verdict = "GO-with-caveat"
        reasons.append("Strong tail protection (maxDD %.1f%% vs SPX %.1f%%, cuts %.1fpp) at ~flat"
                       " FP-Sharpe (%.3f vs SPX %.3f); but does NOT clearly beat the plain"
                       " momentum-rotation control (FP %.3f). Value is crash-insurance, not alpha."
                       % (daa_dd, spx_dd, dd_protect, daa_fp, spx_fp, ctrl_fp))
    else:
        verdict = "KILL"
        reasons.append("No orthogonal edge: FP-Sharpe %.3f vs SPX %.3f / control %.3f;"
                       " maxDD %.1f%% vs SPX %.1f%% (%.1fpp); OOS FP %.3f. Canary cascade does not"
                       " add risk-adjusted value beyond a plain rotation." % (
                           daa_fp, spx_fp, ctrl_fp, daa_dd, spx_dd, dd_protect, daa_oos))

    lines: List[str] = []
    A = lines.append
    A("# DAA Canary Crash-Switch — CONFIRM-OR-KILL Verdict")
    A("")
    A("**UTC:** %s  " % utc)
    A("**Mechanism:** Keller/Keuning Defensive Asset Allocation (2018) — VWO/BND canary "
      "13612W gate; G12 risk EW top-6; SHY/IEF/LQD cash bucket; 3-state cascade "
      "(both-up=100% risk top6 / one-up=50% risk top3 + 50% bond / both-down=100% bond).")
    A("**Data:** free Yahoo daily adjclose (runner.daily_bars_cache), monthly rebalance, "
      + ("%.0f" % COST_BPS) + "bps one-way cost on turned-over fraction. Lookahead-safe: "
      "rank on prior month-end close, hold from month-first (mirrors run_sector_rotation).")
    A("**Window (honest, live-ETF intersection):** %s -> %s (%d trading days). "
      "Start bounded by latest-inception ticker (HYG/BND ~2007-04). No synthesized pre-inception data."
      % (d0["window"]["start"], d0["window"]["end"], d0["window"]["n_days"]))
    A("")
    A("## VERDICT: %s" % verdict)
    A("")
    for r in reasons:
        A("- " + r)
    A("")
    A("## Full-period (continuous-span) headline numbers")
    A("")
    A("| Strategy | FP-Sharpe | CAGR | maxDD | TotRet | SPY-corr |")
    A("|---|---|---|---|---|---|")
    def row(tag, stats, fps, corr):
        cs = ("%.3f" % corr) if corr is not None else "—"
        return "| %s | %.3f | %.2f%% | %.2f%% | %.1f%% | %s |" % (
            tag, fps, stats["cagr_pct"], stats["max_drawdown_pct"], stats["total_return_pct"], cs)
    A(row("**DAA (lag0)**", d0["stats"], d0["fp_sharpe"], d0["spy_corr"]))
    A(row("DAA (+1-bar lag)", d1["stats"], d1["fp_sharpe"], None))
    A(row("CONTROL rot top2 {SPY,QQQ,GLD,TLT}", ctrl["stats"], ctrl["fp_sharpe"], ctrl["spy_corr"]))
    A(row("SPX buy&hold (same path)", spx["stats"], spx["fp_sharpe"], None))
    A("")
    A("## IS / OOS split (train <= %s, OOS after)" % OOS_SPLIT)
    A("")
    A("| Strategy | IS | OOS |")
    A("|---|---|---|")
    A("| DAA (lag0) | %s | %s |" % (_fmt_split(d0["split"], "is"), _fmt_split(d0["split"], "oos")))
    A("| CONTROL rot top2 | %s | %s |" % (_fmt_split(ctrl["split"], "is"), _fmt_split(ctrl["split"], "oos")))
    A("| SPX same-path | %s | %s |" % (_fmt_split(spx["split"], "is"), _fmt_split(spx["split"], "oos")))
    A("")
    A("## +1-bar lag canary (timing-noise test)")
    A("")
    A("- DAA lag0 FP-Sharpe **%.3f** -> +1-bar lag FP-Sharpe **%.3f** (delta **%+.3f**)."
      % (d0["fp_sharpe"], d1["fp_sharpe"], lag_delta))
    A("- DAA lag0 maxDD %.2f%% -> +1-bar lag maxDD %.2f%%."
      % (d0["stats"]["max_drawdown_pct"], d1["stats"]["max_drawdown_pct"]))
    A("- Rule: if extra lag IMPROVES the edge (or losing configs improve), it is timing "
      "noise -> KILL. Here delta=%+.3f -> %s." % (
          lag_delta, "FAILS (improves) -> timing noise" if lag_delta > 0.10 else "robust (does not improve)"))
    A("")
    A("## Regime / defensive behaviour (DAA lag0)")
    A("")
    A("- Avg defensive (cash/bond-bucket) fraction over rebalances: **%.1f%%**." % (d0["avg_defensive_frac"] * 100.0))
    A("- Regime counts (monthly): risk_on=%d, half=%d, crash_off=%d."
      % (d0["regime_counts"]["risk_on"], d0["regime_counts"]["half"], d0["regime_counts"]["crash_off"]))
    A("- Rebalances: %d; avg turnover/rebal: %.3f." % (d0["n_rebalances"], d0["avg_turnover_per_rebal"]))
    A("")
    A("## Orthogonality read")
    A("")
    A("- DAA daily-return SPY-correlation: **%.3f** (control rotation: %.3f). "
      "Lower corr + shallower tail = the canary spends time in bonds during stress, "
      "which is exactly the de-risk behaviour our allocator_blend lacks." % (
          d0["spy_corr"], ctrl["spy_corr"]))
    A("- Crash-protection delta vs SPX maxDD: DAA cuts %.1fpp of max drawdown (%.1f%% vs %.1f%%)."
      % (dd_protect, daa_dd, spx_dd))
    A("")
    A("---")
    A("*Reproduce: `python3 _daa_confirm.py` (free Yahoo data only). Raw json: "
      "`reports/_daa_confirm_%s.json`.*" % utc)

    path = "reports/DAA_VERDICT_%s.md" % utc
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\nWROTE %s" % path)
    print("VERDICT: %s" % verdict)


if __name__ == "__main__":
    main()
