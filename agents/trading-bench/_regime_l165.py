"""L165 — Regime detection as a first-class feature.

Measures how the 8 LIVE-BOOK strategies behave across BULL / CHOP / BEAR regimes,
and tests whether a regime gate on any of them would improve the ERC-weighted book.

READ-ONLY against protected code. Writes only to root scratch + reports/.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from datetime import datetime, timezone

from runner.fp_sharpe import sharpe_from_returns
from runner import lane_honesty

SERIES_PATH = Path("reports/_volaware_series.json")
ERC_PATH = Path("reports/_erc_weights.json")
SPY_PATH = Path("_spy_daily_l165.json")

SQRT_252 = math.sqrt(252.0)


# ---- canonical risk metrics (lifted verbatim from _ranking_riskmetrics.py) ----
def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def sortino(rets, bpy_sqrt=SQRT_252, target=0.0):
    if not rets:
        return float("nan")
    mu = _mean(rets)
    downs = [min(0.0, r - target) for r in rets]
    dd = math.sqrt(_mean([d * d for d in downs]))
    if dd == 0:
        return float("nan")
    return (mu - target) / dd * bpy_sqrt


def max_drawdown(rets):
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        eq *= (1.0 + r)
        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0
        if dd < mdd:
            mdd = dd
    return mdd


def calmar(rets):
    if not rets:
        return float("nan")
    c_pct = lane_honesty.cagr(rets)
    c_frac = c_pct / 100.0
    mdd = max_drawdown(rets)
    if mdd == 0:
        return float("nan")
    return c_frac / abs(mdd)


# ---- data loading ----
def load_series():
    d = json.loads(SERIES_PATH.read_text())
    names = d["live"]
    rm = d["returns_matrix"]
    series = {}
    for j, name in enumerate(names):
        series[name] = [row[j] for row in rm]
    return names, series, d["common_dates"]


def load_weights(names):
    e = json.loads(ERC_PATH.read_text())
    cap = e["capital_usd_v2_tradeable"]
    tot = sum(cap.values())
    w = {n: cap[n] / tot for n in names}
    return w, cap, tot


def load_spy():
    d = json.loads(SPY_PATH.read_text())
    return dict(zip(d["dates"], d["adjclose"]))


# ---- regime classifier: pure function of PAST SPY only (no lookahead) ----
def build_regime_labels(common_dates, spy_map):
    """For each date in common_dates, compute a regime label using only
    same-day-or-earlier SPY data.

    Rule (stated exactly in the report):
      Build a full SPY trading-day series (all SPY dates). For each SPY day t
      compute:
        sma200(t)  = mean of adjclose over the trailing 200 SPY sessions (incl t)
        rv20(t)    = annualized stdev of the trailing 20 daily SPY log-ish simple
                     returns (incl t), * sqrt(252)
      A rolling median of rv20 is taken over the trailing 252 SPY sessions
      (expanding until 252 available) — EXPANDING/TRAILING ONLY, no lookahead.
      Label(t):
        BEAR  if close(t) < sma200(t)
        BULL  if close(t) >= sma200(t)  AND  rv20(t) <= median_rv(t)
        CHOP  if close(t) >= sma200(t)  AND  rv20(t) >  median_rv(t)
      The label for a common_date d is the label of the most recent SPY session
      with date <= d (so it uses only information available at d's close).
    """
    spy_dates = sorted(spy_map.keys())
    closes = [spy_map[dd] for dd in spy_dates]
    n = len(spy_dates)

    # trailing returns
    rets = [0.0] * n
    for i in range(1, n):
        prev = closes[i - 1]
        if prev > 0:
            rets[i] = (closes[i] - prev) / prev

    sma200 = [None] * n
    rv20 = [None] * n
    for i in range(n):
        if i >= 199:
            window = closes[i - 199:i + 1]
            sma200[i] = sum(window) / 200.0
        if i >= 19:
            rwin = rets[i - 19:i + 1]
            mu = sum(rwin) / len(rwin)
            var = sum((r - mu) ** 2 for r in rwin) / (len(rwin) - 1)
            rv20[i] = math.sqrt(var) * SQRT_252

    # expanding/trailing rolling median of rv20 over trailing 252 valid points
    med_rv = [None] * n
    rv_hist = []  # list of (index, value) trailing window of rv20 values
    for i in range(n):
        if rv20[i] is not None:
            rv_hist.append(rv20[i])
            if len(rv_hist) > 252:
                rv_hist = rv_hist[-252:]
            med_rv[i] = statistics.median(rv_hist)

    # label each SPY day
    spy_label = [None] * n
    for i in range(n):
        if sma200[i] is None or rv20[i] is None or med_rv[i] is None:
            continue
        c = closes[i]
        if c < sma200[i]:
            spy_label[i] = "BEAR"
        elif rv20[i] <= med_rv[i]:
            spy_label[i] = "BULL"
        else:
            spy_label[i] = "CHOP"

    # map common_dates -> most recent SPY session <= d
    import bisect
    labels = {}
    diag = {"unlabeled_warmup": 0}
    for d in common_dates:
        pos = bisect.bisect_right(spy_dates, d) - 1
        if pos < 0:
            labels[d] = None
            diag["unlabeled_warmup"] += 1
            continue
        lab = spy_label[pos]
        labels[d] = lab
        if lab is None:
            diag["unlabeled_warmup"] += 1
    return labels, diag, (spy_dates, spy_label, sma200, rv20, med_rv)


def regime_occupancy(common_dates, labels):
    counts = {"BULL": 0, "CHOP": 0, "BEAR": 0, None: 0}
    for d in common_dates:
        counts[labels[d]] = counts.get(labels[d], 0) + 1
    return counts


def slice_by_regime(common_dates, series_list, labels, regime):
    return [r for d, r in zip(common_dates, series_list) if labels[d] == regime]


def metrics_block(rets):
    if len(rets) < 2:
        return {"n": len(rets), "sharpe": None, "sortino": None,
                "mean_bps": None, "in_mkt_pct": None}
    shp = sharpe_from_returns(rets, 252.0)
    srt = sortino(rets)
    mean_bps = _mean(rets) * 1e4
    in_mkt = sum(1 for r in rets if abs(r) > 1e-12) / len(rets) * 100.0
    return {
        "n": len(rets),
        "sharpe": round(shp, 3),
        "sortino": None if math.isnan(srt) else round(srt, 3),
        "mean_bps": round(mean_bps, 3),
        "in_mkt_pct": round(in_mkt, 1),
    }


def book_returns(common_dates, series, names, weights):
    """ERC-weighted daily book return = weighted sum of the 8 columns."""
    out = []
    for i in range(len(common_dates)):
        s = 0.0
        for n in names:
            s += weights[n] * series[n][i]
        out.append(s)
    return out


def book_returns_gated(common_dates, series, names, weights, labels, gated_strats, flat_regime):
    """Book return where each strat in gated_strats is FLATTENED (->0) on days
    whose regime == flat_regime. Other strats and other days unchanged.
    Capital from a flattened strat goes to CASH (return 0) — NOT re-weighted to
    others (honest: you don't get free re-leverage)."""
    gated = set(gated_strats)
    out = []
    for i, d in enumerate(common_dates):
        s = 0.0
        for n in names:
            r = series[n][i]
            if n in gated and labels[d] == flat_regime:
                r = 0.0
            s += weights[n] * r
        out.append(s)
    return out


def full_metrics(rets):
    shp = sharpe_from_returns(rets, 252.0)
    srt = sortino(rets)
    cg = lane_honesty.cagr(rets)
    mdd = max_drawdown(rets)
    cmr = calmar(rets)
    return {
        "sharpe": round(shp, 4),
        "sortino": None if math.isnan(srt) else round(srt, 4),
        "cagr_pct": round(cg, 3),
        "maxdd_pct": round(mdd * 100, 3),
        "calmar": None if math.isnan(cmr) else round(cmr, 3),
    }


def main():
    names, series, dates = load_series()
    weights, cap, captot = load_weights(names)
    spy_map = load_spy()

    labels, diag, spy_internals = build_regime_labels(dates, spy_map)
    occ = regime_occupancy(dates, labels)
    n_lab = sum(v for k, v in occ.items() if k is not None)

    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "n_days": len(dates),
        "span": [dates[0], dates[-1]],
        "weights": {n: round(weights[n], 5) for n in names},
        "capital_v2": cap,
        "occupancy": {k if k else "UNLABELED": v for k, v in occ.items()},
        "occupancy_pct": {(k if k else "UNLABELED"): round(v / len(dates) * 100, 2)
                          for k, v in occ.items()},
    }

    # sanity check: regime in known windows
    def window_breakdown(lo, hi):
        c = {"BULL": 0, "CHOP": 0, "BEAR": 0, None: 0}
        for d in dates:
            if lo <= d <= hi:
                c[labels[d]] = c.get(labels[d], 0) + 1
        tot = sum(c.values())
        return {k if k else "UNLABELED": (v, round(v / tot * 100, 1) if tot else 0)
                for k, v in c.items()}, tot

    sanity = {
        "2020Q1_covid (2020-02-19..2020-04-07)": window_breakdown("2020-02-19", "2020-04-07")[0],
        "2022_bear (2022-01-01..2022-10-15)": window_breakdown("2022-01-01", "2022-10-15")[0],
        "2013_bull (2013-01-01..2013-12-31)": window_breakdown("2013-01-01", "2013-12-31")[0],
        "2017_bull (2017-01-01..2017-12-31)": window_breakdown("2017-01-01", "2017-12-31")[0],
    }
    result["sanity_windows"] = sanity

    # per-strategy x per-regime
    per = {}
    for n in names:
        sl = series[n]
        row = {"full": metrics_block(sl)}
        for reg in ("BULL", "CHOP", "BEAR"):
            row[reg] = metrics_block(slice_by_regime(dates, sl, labels, reg))
        per[n] = row
    result["per_strategy_regime"] = per

    # book-level per regime
    book = book_returns(dates, series, names, weights)
    book_per = {"full": metrics_block(book)}
    for reg in ("BULL", "CHOP", "BEAR"):
        book_per[reg] = metrics_block(slice_by_regime(dates, book, labels, reg))
    result["book_per_regime"] = book_per
    result["book_full_metrics"] = full_metrics(book)

    # ---- sensitivity classification ----
    # regime-sensitive if (bull Sharpe - bear Sharpe) gap is large in magnitude,
    # OR bear Sharpe deeply negative. Threshold stated in report.
    GAP_CUT = 0.5  # annualized Sharpe units
    sens = {}
    for n in names:
        b = per[n]["BULL"]["sharpe"]
        be = per[n]["BEAR"]["sharpe"]
        bullv = b if b is not None else 0.0
        bearv = be if be is not None else 0.0
        gap = bullv - bearv
        sens[n] = {
            "bull_sharpe": b, "chop_sharpe": per[n]["CHOP"]["sharpe"], "bear_sharpe": be,
            "bull_minus_bear_sharpe": round(gap, 3),
            "sensitive": abs(gap) > GAP_CUT or bearv < -0.5,
        }
    result["sensitivity"] = {"gap_cut": GAP_CUT, "rule": "sensitive if |bullSharpe-bearSharpe|>0.5 OR bearSharpe<-0.5", "rows": sens}

    # ---- counterfactual: gate the bear-worst sensitive long-biased strategies ----
    # candidates = strategies whose BEAR Sharpe < 0 (would benefit from flatten-in-bear)
    bear_neg = [n for n in names if (per[n]["BEAR"]["sharpe"] is not None and per[n]["BEAR"]["sharpe"] < 0)]
    result["gate_candidates_bear_neg"] = bear_neg

    # IS/OOS split: first 70% / last 30% of dates
    split = int(len(dates) * 0.70)
    result["isoos_split_index"] = split
    result["isoos_split_date"] = dates[split]

    def seg_metrics(rets, a, b):
        return full_metrics(rets[a:b])

    counterfactuals = {}
    # (A) gate ALL bear-negative strats in BEAR
    for label, gated, flatreg in [
        ("gate_bearneg_in_BEAR", bear_neg, "BEAR"),
        ("gate_ALL_in_BEAR", names, "BEAR"),
    ]:
        gbook = book_returns_gated(dates, series, names, weights, labels, gated, flatreg)
        cf = {
            "gated_strats": gated,
            "flat_regime": flatreg,
            "full_baseline": full_metrics(book),
            "full_gated": full_metrics(gbook),
            "IS_baseline": seg_metrics(book, 0, split),
            "IS_gated": seg_metrics(gbook, 0, split),
            "OOS_baseline": seg_metrics(book, split, len(dates)),
            "OOS_gated": seg_metrics(gbook, split, len(dates)),
        }
        # turnover proxy: count regime transitions into/out of flat_regime
        trans = 0
        prev = None
        for d in dates:
            cur = (labels[d] == flatreg)
            if prev is not None and cur != prev:
                trans += 1
            prev = cur
        cf["gate_toggles"] = trans
        counterfactuals[label] = cf

    # (B) per-strategy single-gate: gate ONLY that one strat in BEAR, measure book delta
    single = {}
    for n in bear_neg:
        gbook = book_returns_gated(dates, series, names, weights, labels, [n], "BEAR")
        single[n] = {
            "full_baseline_sharpe": full_metrics(book)["sharpe"],
            "full_gated_sharpe": full_metrics(gbook)["sharpe"],
            "full_baseline_sortino": full_metrics(book)["sortino"],
            "full_gated_sortino": full_metrics(gbook)["sortino"],
            "OOS_baseline_sharpe": seg_metrics(book, split, len(dates))["sharpe"],
            "OOS_gated_sharpe": seg_metrics(gbook, split, len(dates))["sharpe"],
            "full_baseline_maxdd": full_metrics(book)["maxdd_pct"],
            "full_gated_maxdd": full_metrics(gbook)["maxdd_pct"],
        }
    counterfactuals["per_strategy_single_gate_BEAR"] = single
    result["counterfactuals"] = counterfactuals

    result["diag"] = diag

    stamp = result["generated_utc"]
    out_json = Path(f"_regime_l165_{stamp}.json")
    out_json.write_text(json.dumps(result, indent=2))
    print("WROTE", out_json)
    # quick console summary
    print("OCCUPANCY:", result["occupancy_pct"])
    print("BOOK per regime sharpe:",
          {k: book_per[k]["sharpe"] for k in ("BULL", "CHOP", "BEAR", "full")})
    print("BEAR-NEG strats:", bear_neg)
    print("SANITY 2022:", sanity["2022_bear (2022-01-01..2022-10-15)"])
    print("SANITY 2017:", sanity["2017_bull (2017-01-01..2017-12-31)"])


if __name__ == "__main__":
    main()
