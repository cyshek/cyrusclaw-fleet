#!/usr/bin/env python3
"""_xstrat_corr.py — SCRATCH (subagent: inter-strategy correlation audit).

Builds a DAILY strategy-return series for each of the 12 LIVE paper strategies
over a common window, then computes:
  - Pearson correlation matrix (full + downside-day)
  - hierarchical clustering (correlation distance)
  - effective number of independent bets (participation ratio of eigenvalues)
  - per-strategy average pairwise correlation (redundancy rank)

WRITE-SCOPE: imports engines READ-ONLY. Creates only reports/ outputs + this
scratch file. Modifies NO protected file.

Method (honest):
  * 9 single-symbol event strategies -> runner.backtest.backtest() fed DAILY
    adjclose bars (Yahoo, keyless) shaped into the engine's {t,o,h,l,c,v}
    contract. timeframe forced to '1Day' so Sharpe annualization is correct.
    Strategy logic is UNCHANGED; we just run it at daily resolution (the only
    way to get a long common window back to TQQQ inception 2010).
  * 2 TQQQ continuous-weight vol-target strategies (leveraged_long_trend_paper,
    tqqq_cot_combo) are NOT honestly reproducible through the event engine
    (the engine has no partial-trim primitive; backtest.py comment says so).
    For these we use their VALIDATED daily-voltarget harness equity curve
    (run_backtest_voltarget) -> daily returns. tqqq_cot_combo = the VT sleeve
    with a COT bearish 0.5x scale overlay; we apply that overlay to the VT
    daily weights using the SAME COT cache the live strategy reads.
  * allocator_blend -> the VALIDATED invvol_63d blend daily equity, via
    _allocator_blend_tests.build_sleeves()+blend_portfolio() (the exact
    decomposition the live paper tracker reuses) -> daily returns.

RTH caveat: sma_crossover_qqq_rth has a 14:30-20:00 UTC entry gate. On daily
bars we stamp bars at T15:00:00Z so the gate is a no-op (truthful: at daily
resolution the RTH filter cannot distinguish bars, so it collapses to its
parent sma_crossover_qqq). Documented in the report.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import daily_bars_cache as dbc
from runner import backtest as bt

# ---------------------------------------------------------------------------
# The 12 live strategies and their primary symbol.
# ---------------------------------------------------------------------------
SINGLE_SYMBOL = [
    ("breakout_xlk", "XLK"),
    ("breakout_xlk_regime", "XLK"),
    ("breakout_xlk__mut_c382b1", "XLK"),
    ("sma_crossover_qqq", "QQQ"),
    ("sma_crossover_qqq_regime", "QQQ"),
    ("sma_crossover_qqq_rth", "QQQ"),
    ("volume_breakout_qqq", "QQQ"),
    ("rsi_oversold_spy", "SPY"),
    ("macd_momentum_iwm", "IWM"),
]
# Special continuous-weight / blend strategies (handled separately).
SPECIAL = ["leveraged_long_trend_paper", "tqqq_cot_combo", "allocator_blend"]

ALL_NAMES = [n for n, _ in SINGLE_SYMBOL] + SPECIAL


# ---------------------------------------------------------------------------
# Daily bar -> engine bar-shape ({t,o,h,l,c,v}) using ADJCLOSE (split/div-adj).
# We stamp the time at 15:00:00Z so any intraday RTH gate (sma_..._rth) is a
# no-op at daily resolution.
# ---------------------------------------------------------------------------
def daily_to_engine_bars(symbol: str) -> List[dict]:
    rows = dbc.get_daily(symbol)
    out: List[dict] = []
    for r in rows:
        ac = r.get("adjclose")
        if ac is None:
            continue
        c = float(ac)
        # Scale O/H/L by the adj/raw ratio so they stay consistent with adjclose.
        raw_c = r.get("close")
        ratio = (c / float(raw_c)) if (raw_c not in (None, 0)) else 1.0
        def _adj(v):
            return float(v) * ratio if v is not None else c
        out.append({
            "t": f"{r['date']}T15:00:00Z",
            "o": _adj(r.get("open")),
            "h": _adj(r.get("high")),
            "l": _adj(r.get("low")),
            "c": c,
            "v": float(r.get("volume") or 0.0),
        })
    return out


def equity_to_returns(dates: List[str], equity: List[float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for i in range(1, len(dates)):
        p = equity[i - 1]
        if p and p > 0:
            out[dates[i]] = equity[i] / p - 1.0
    return out


# ---------------------------------------------------------------------------
# Single-symbol strategy -> {date: daily strat return} via event engine on
# daily bars. The engine's equity_curve is per-bar; bars are daily so the
# equity step from bar i-1 to i is that day's strategy return.
# ---------------------------------------------------------------------------
def single_symbol_returns(name: str, symbol: str,
                          param_overrides: Optional[dict] = None) -> Dict[str, float]:
    bars = daily_to_engine_bars(symbol)
    module, params = bt.load_strategy_module_and_params(name)
    params = dict(params)
    params["timeframe"] = "1Day"  # correct annualization + daily decisions
    if param_overrides:
        params.update(param_overrides)
    # zero-cost so the correlation reflects the SIGNAL, not friction noise
    cm = bt.CostModel(spread_bps=0.0, fee_bps=0.0)
    res = bt.backtest(name, bars, params, starting_cash=100000.0, cost_model=cm)
    eq = res.equity_curve
    # equity_curve[i] corresponds to bars[i] (same length as bars)
    dates = [b["t"][:10] for b in bars]
    if len(eq) != len(dates):
        # engine returns one equity per processed bar; align by trailing length
        dates = dates[-len(eq):]
    return equity_to_returns(dates, eq), res


# ---------------------------------------------------------------------------
# SPECIAL strategies: TQQQ continuous-weight + allocator blend.
# ---------------------------------------------------------------------------
# volume_breakout_qqq trades 0x on daily bars (its 3x-volume gate is calibrated
# for 1Hour bars). To extract a representative daily SIGNAL shape we relax the
# volume gate to 1.0x ("price breakout confirmed by >=avg volume"). Clearly a
# PROXY; flagged in the report. Its native-config daily series is flat.
VOLBREAK_PROXY = {"volume_mult": 1.0}


def _tqqq_voltarget_series():
    """leveraged_long_trend_paper daily returns = validated VT sleeve equity.
    Also returns the per-date VT target WEIGHTS + the underlying QQQ-gate dates
    so the COT overlay (tqqq_cot_combo) can be layered on the SAME weights."""
    from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
        run_backtest_voltarget, VolTargetParams,
    )
    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0))
    dates = vt["strategy"]["dates"]
    eq = vt["strategy"]["equity"]
    weights = vt["strategy"]["weights"]  # per-date target sleeve weight
    rmap = equity_to_returns(dates, eq)
    return rmap, dates, weights, vt["strategy"]["stats"]


def _tqqq_cot_combo_series(vt_dates, vt_weights):
    """tqqq_cot_combo = VT sleeve weight scaled to 0.5x on COT-bearish days.
    We reconstruct its daily return from the TQQQ daily return * effective
    weight, where effective weight = vt_weight * (0.5 if COT bearish else 1.0).
    Uses the SAME cot_cache the live strategy reads. Lookahead-safe: COT signal
    as-of each date."""
    tqqq = dbc.get_daily("TQQQ")
    tqqq_by = {b["date"]: b for b in tqqq}
    tqqq_dates_sorted = [b["date"] for b in tqqq]
    # TQQQ daily close-to-close returns indexed by end date
    tqqq_ret = {}
    for i in range(1, len(tqqq)):
        p = tqqq[i - 1]["adjclose"]
        if p and p > 0:
            tqqq_ret[tqqq[i]["date"]] = tqqq[i]["adjclose"] / p - 1.0
    # COT bearish scale per date via the LIVE strategy's own _get_cot_scale
    # (faithful: same ES AM-net WoW + 3-day publication lag the live adapter uses).
    cot_scale_fn = None
    cot_ok = False
    try:
        from strategies.tqqq_cot_combo.strategy import _get_cot_scale
        cot_scale_fn = _get_cot_scale
        # probe once to confirm the COT series is actually available
        _probe = _get_cot_scale(0.5, vt_dates[len(vt_dates) // 2])
        cot_ok = True
    except Exception:
        cot_ok = False
    # Build effective-weight daily returns on vt_dates calendar.
    wmap = {d: w for d, w in zip(vt_dates, vt_weights)}
    rmap = {}
    for d in vt_dates:
        w = wmap.get(d, 0.0)
        if cot_ok and cot_scale_fn is not None:
            try:
                w *= cot_scale_fn(0.5, d)  # cot_scale_bearish=0.5 per params.json
            except Exception:
                pass
        r = tqqq_ret.get(d)
        if r is not None:
            rmap[d] = w * r
    return rmap, cot_ok


def _allocator_blend_series():
    """allocator_blend daily returns = validated invvol_63d blend equity."""
    import _allocator_blend_tests as ab
    s = ab.build_sleeves()
    dates = s["common_dates"]
    tqqq_r = s["tqqq_r"]
    rot_r = s["rot_r"]
    sleeves = [tqqq_r, rot_r]

    # invvol_63d weight fn — identical to the promoted blend (and live tracker).
    def invvol_wfn(idx: int):
        lookback = 63
        lo = max(0, idx - lookback)
        out = []
        for k in range(len(sleeves)):
            window = sleeves[k][lo:idx]
            v = ab.annualized_vol(window) if len(window) >= 2 else 0.0
            out.append((1.0 / v) if v > 0 else 0.0)
        tot = sum(out)
        if tot <= 0:
            return [1.0 / len(sleeves)] * len(sleeves)
        return [x / tot for x in out]

    blend = ab.blend_portfolio(dates, sleeves, lambda i: invvol_wfn(i),
                               blend_cost_bps=2.0, vol_lookback_days=63)
    rmap = equity_to_returns(blend["dates"], blend["equity"])
    return rmap, blend["stats"]


# ---------------------------------------------------------------------------
# Analysis: align all 12 -> matrix; Pearson full + downside; clusters; eff-N.
# ---------------------------------------------------------------------------
LABELS = {
    "breakout_xlk": "breakout_xlk [XLK]",
    "breakout_xlk_regime": "breakout_xlk_regime [XLK]",
    "breakout_xlk__mut_c382b1": "breakout_xlk__mut_c382b1 [XLK]",
    "sma_crossover_qqq": "sma_crossover_qqq [QQQ]",
    "sma_crossover_qqq_regime": "sma_crossover_qqq_regime [QQQ]",
    "sma_crossover_qqq_rth": "sma_crossover_qqq_rth [QQQ]",
    "volume_breakout_qqq": "volume_breakout_qqq [QQQ]*",
    "leveraged_long_trend_paper": "leveraged_long_trend_paper [TQQQ]",
    "tqqq_cot_combo": "tqqq_cot_combo [TQQQ]",
    "rsi_oversold_spy": "rsi_oversold_spy [SPY]",
    "macd_momentum_iwm": "macd_momentum_iwm [IWM]",
    "allocator_blend": "allocator_blend [BLEND]",
}
ORDER = [
    "breakout_xlk", "breakout_xlk_regime", "breakout_xlk__mut_c382b1",
    "sma_crossover_qqq", "sma_crossover_qqq_regime", "sma_crossover_qqq_rth",
    "volume_breakout_qqq", "leveraged_long_trend_paper", "tqqq_cot_combo",
    "rsi_oversold_spy", "macd_momentum_iwm", "allocator_blend",
]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sxx = sum((xs[i] - mx) ** 2 for i in range(n))
    syy = sum((ys[i] - my) ** 2 for i in range(n))
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def build_all_series():
    """Return {name: {date: ret}} for all 12, plus SPY return map (downside ref)."""
    series: Dict[str, Dict[str, float]] = {}
    meta: Dict[str, dict] = {}
    # single-symbol
    for name, sym in SINGLE_SYMBOL:
        ov = VOLBREAK_PROXY if name == "volume_breakout_qqq" else None
        rmap, res = single_symbol_returns(name, sym, ov)
        series[name] = rmap
        meta[name] = {"sharpe": res.sharpe, "trades": res.n_trades,
                      "n": len(rmap)}
    # special
    vt_rmap, vt_dates, vt_w, vt_stats = _tqqq_voltarget_series()
    series["leveraged_long_trend_paper"] = vt_rmap
    meta["leveraged_long_trend_paper"] = {"sharpe": vt_stats["sharpe"],
                                           "cagr": vt_stats["cagr_pct"],
                                           "maxdd": vt_stats["max_drawdown_pct"]}
    cot_rmap, cot_ok = _tqqq_cot_combo_series(vt_dates, vt_w)
    series["tqqq_cot_combo"] = cot_rmap
    meta["tqqq_cot_combo"] = {"cot_overlay": cot_ok}
    al_rmap, al_stats = _allocator_blend_series()
    series["allocator_blend"] = al_rmap
    meta["allocator_blend"] = {"sharpe": al_stats["sharpe"],
                               "cagr": al_stats["cagr_pct"],
                               "maxdd": al_stats["max_drawdown_pct"]}
    # SPY daily return (downside reference)
    spy = dbc.get_daily("SPY")
    spy_ret = {}
    for i in range(1, len(spy)):
        p = spy[i - 1]["adjclose"]
        if p and p > 0:
            spy_ret[spy[i]["date"]] = spy[i]["adjclose"] / p - 1.0
    return series, meta, spy_ret


def common_window(series):
    sets = [set(series[n].keys()) for n in ORDER]
    common = sorted(set.intersection(*sets))
    return common


def corr_matrix(series, dates):
    cols = {n: [series[n][d] for d in dates] for n in ORDER}
    M = [[0.0] * len(ORDER) for _ in ORDER]
    for i, a in enumerate(ORDER):
        for j, b in enumerate(ORDER):
            M[i][j] = 1.0 if i == j else pearson(cols[a], cols[b])
    return M


def participation_ratio(M):
    """Effective number of independent bets = (sum eig)^2 / sum(eig^2).
    Pure-python symmetric eigenvalues via Jacobi rotation."""
    n = len(M)
    A = [row[:] for row in M]
    # Jacobi eigenvalue algorithm
    for _ in range(100):
        # find largest off-diagonal
        p, q, mx = 0, 1, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if abs(A[i][j]) > mx:
                    mx = abs(A[i][j]); p, q = i, j
        if mx < 1e-12:
            break
        app, aqq, apq = A[p][p], A[q][q], A[p][q]
        phi = 0.5 * math.atan2(2 * apq, aqq - app) if (aqq - app) != 0 else math.pi / 4
        c, s = math.cos(phi), math.sin(phi)
        for k in range(n):
            akp, akq = A[k][p], A[k][q]
            A[k][p] = c * akp - s * akq
            A[k][q] = s * akp + c * akq
        for k in range(n):
            apk, aqk = A[p][k], A[q][k]
            A[p][k] = c * apk - s * aqk
            A[q][k] = s * apk + c * aqk
    eig = [A[i][i] for i in range(n)]
    eig = [max(0.0, e) for e in eig]  # clip tiny negatives
    s1 = sum(eig)
    s2 = sum(e * e for e in eig)
    pr = (s1 * s1 / s2) if s2 > 0 else float("nan")
    return pr, sorted(eig, reverse=True)


def hierarchical_clusters(M):
    """Average-linkage agglomerative clustering on distance = 1 - corr.
    Returns merge log (as text) and a flat cluster assignment at a 0.5 corr
    (=0.5 distance) cut."""
    n = len(M)
    dist = [[1.0 - M[i][j] for j in range(n)] for i in range(n)]
    clusters = {i: [i] for i in range(n)}
    active = set(range(n))
    merges = []

    def cluster_dist(a, b):
        tot = 0.0; cnt = 0
        for i in clusters[a]:
            for j in clusters[b]:
                tot += dist[i][j]; cnt += 1
        return tot / cnt if cnt else 1.0

    next_id = n
    while len(active) > 1:
        best = None; ba = bb = -1
        al = sorted(active)
        for x in range(len(al)):
            for y in range(x + 1, len(al)):
                d = cluster_dist(al[x], al[y])
                if best is None or d < best:
                    best = d; ba, bb = al[x], al[y]
        merges.append((ba, bb, best, 1.0 - best))
        clusters[next_id] = clusters[ba] + clusters[bb]
        active.discard(ba); active.discard(bb); active.add(next_id)
        next_id += 1
    return merges, clusters


def avg_pairwise(M):
    n = len(M)
    out = []
    for i in range(n):
        vals = [M[i][j] for j in range(n) if j != i and not math.isnan(M[i][j])]
        out.append(sum(vals) / len(vals) if vals else float("nan"))
    return out


def _fmt_matrix(M, names_short):
    w = 7
    head = " " * 6 + "".join(f"{i+1:>{w}}" for i in range(len(M)))
    lines = [head]
    for i, row in enumerate(M):
        cells = "".join((f"{v:>{w}.2f}" if not math.isnan(v) else f"{'nan':>{w}}") for v in row)
        lines.append(f"{i+1:>2}|{names_short[i][:3]:<3}{cells}")
    return "\n".join(lines)


def run_full():
    print(">>> Building all 12 daily return series ...", flush=True)
    series, meta, spy_ret = build_all_series()
    common = common_window(series)
    print(f">>> COMMON WINDOW: {common[0]} .. {common[-1]}  ({len(common)} trading days)")
    for n in ORDER:
        print(f"    {LABELS[n]:38s} full_n={len(series[n]):5d}  meta={meta.get(n)}")

    # Full-window correlation
    M = corr_matrix(series, common)

    # Downside-day correlation: days where SPY return < 0
    downside = [d for d in common if spy_ret.get(d, 0.0) < 0.0]
    print(f">>> DOWNSIDE DAYS (SPY<0): {len(downside)} of {len(common)} "
          f"({100*len(downside)/len(common):.1f}%)")
    Md = corr_matrix(series, downside)

    # Effective number of bets
    pr, eig = participation_ratio(M)
    pr_d, eig_d = participation_ratio(Md)
    print(f">>> EFFECTIVE N BETS (full)     = {pr:.2f}  (of 12)")
    print(f">>> EFFECTIVE N BETS (downside) = {pr_d:.2f}  (of 12)")
    print(f"    top eigenvalues (full): {[round(e,2) for e in eig[:6]]}")

    # Clusters
    merges, clusters = hierarchical_clusters(M)

    # Avg pairwise
    ap_full = avg_pairwise(M)
    ap_down = avg_pairwise(Md)
    ranked = sorted(range(len(ORDER)), key=lambda i: ap_full[i], reverse=True)
    print(">>> AVG PAIRWISE CORR (full), most redundant first:")
    for i in ranked:
        print(f"    {LABELS[ORDER[i]]:38s} avg_full={ap_full[i]:+.3f}  avg_down={ap_down[i]:+.3f}")

    short = [ORDER[i] for i in range(len(ORDER))]
    print("\n=== FULL-WINDOW CORRELATION MATRIX ===")
    print(_fmt_matrix(M, short))
    print("\n=== DOWNSIDE-DAY CORRELATION MATRIX ===")
    print(_fmt_matrix(Md, short))

    # Save JSON
    out = {
        "common_window": [common[0], common[-1]],
        "n_days": len(common),
        "n_downside_days": len(downside),
        "order": ORDER,
        "labels": [LABELS[n] for n in ORDER],
        "meta": meta,
        "corr_full": M,
        "corr_downside": Md,
        "eff_n_bets_full": pr,
        "eff_n_bets_downside": pr_d,
        "eigenvalues_full": eig,
        "eigenvalues_downside": eig_d,
        "avg_pairwise_full": ap_full,
        "avg_pairwise_downside": ap_down,
        "clusters_merge_log": [
            {"a": a, "b": b, "merge_dist": d, "merge_corr": c} for (a, b, d, c) in merges
        ],
    }
    rp = WORKSPACE / "reports" / "_interstrategy_corr_matrix.json"
    rp.write_text(json.dumps(out, indent=2))
    print(f"\n>>> wrote {rp}")
    return out, merges


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="probe single-symbol")
    ap.add_argument("--probe-special", action="store_true", help="probe special 3")
    ap.add_argument("--full", action="store_true", help="full analysis + JSON")
    args = ap.parse_args()
    if args.probe:
        for name, sym in SINGLE_SYMBOL:
            ov = VOLBREAK_PROXY if name == "volume_breakout_qqq" else None
            rmap, res = single_symbol_returns(name, sym, ov)
            ds = sorted(rmap)
            print(f"{name:30s} sym={sym:4s} n_ret={len(ds):5d} "
                  f"{ds[0] if ds else '-'}..{ds[-1] if ds else '-'} "
                  f"trades={res.n_trades} sharpe={res.sharpe:.3f} "
                  f"ret={res.total_return_pct*100:.1f}%")
    if args.probe_special:
        vt_rmap, vt_dates, vt_w, vt_stats = _tqqq_voltarget_series()
        ds = sorted(vt_rmap)
        print(f"{'leveraged_long_trend_paper':30s} n_ret={len(ds):5d} "
              f"{ds[0]}..{ds[-1]} VTsharpe={vt_stats['sharpe']:.3f} "
              f"cagr={vt_stats['cagr_pct']:.1f}% maxdd={vt_stats['max_drawdown_pct']:.1f}%")
        cot_rmap, cot_ok = _tqqq_cot_combo_series(vt_dates, vt_w)
        ds2 = sorted(cot_rmap)
        print(f"{'tqqq_cot_combo':30s} n_ret={len(ds2):5d} "
              f"{ds2[0]}..{ds2[-1]} cot_overlay_active={cot_ok}")
        al_rmap, al_stats = _allocator_blend_series()
        ds3 = sorted(al_rmap)
        print(f"{'allocator_blend':30s} n_ret={len(ds3):5d} "
              f"{ds3[0]}..{ds3[-1]} blendSharpe={al_stats['sharpe']:.3f} "
              f"cagr={al_stats['cagr_pct']:.1f}% maxdd={al_stats['max_drawdown_pct']:.1f}%")
    if args.full:
        run_full()
