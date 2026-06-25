"""Sensitivity add-on for the macro-momentum L/S pre-flight.

Two cheap robustness checks on top of _macromom_preflight.py:

(A) TERCILE L/S: long top-3 / short bottom-3 of the broad 11-asset basket
    (sharper extremes than top-half/bottom-half) — does concentrating the
    signal on the strongest/weakest assets rescue the spread?

(B) SIGN STABILITY: rolling 24-month spread Sharpe of the broad-11 and prior-6
    L/S spreads — is any positive full-period number coming from one regime,
    or is the spread persistently signed?

Reuses the engine in _macromom_preflight.py (imported), only overriding the
leg-selection to terciles for (A).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

import _macromom_preflight as mm  # noqa: E402


def run_ls_tercile(symbols, start=mm.START, cost_bps_per_side=0.0, k=3):
    """Same engine as mm.run_ls but long top-k / short bottom-k."""
    prices, dates = mm.load_series(symbols)
    cal = mm.union_calendar(dates, start)
    rebs = mm.rebalance_days(cal)

    spread_rets: List[float] = []
    long_rets: List[float] = []
    short_rets: List[float] = []
    bh_rets: List[float] = []
    reb_used: List[str] = []
    sel_long = {s: 0 for s in symbols}
    sel_short = {s: 0 for s in symbols}
    prev_long: set = set()
    prev_short: set = set()

    for j in range(len(rebs) - 1):
        d0 = rebs[j]
        d1 = rebs[j + 1]
        scores = {}
        for s in symbols:
            sc = mm.blended_score(prices[s], dates[s], d0)
            if sc is not None:
                scores[s] = sc
        if len(scores) < 2 * k:
            continue
        z = mm.zscore(scores)
        ranked = sorted(z.keys(), key=lambda s: z[s], reverse=True)
        longs = ranked[:k]
        shorts = ranked[len(ranked) - k:]

        def leg_ret(members):
            rs = []
            for s in members:
                fr = mm.fwd_return(prices[s], dates[s], d0, d1)
                if fr is not None:
                    rs.append(fr)
            return (sum(rs) / len(rs)) if rs else None

        lr = leg_ret(longs)
        sr = leg_ret(shorts)
        if lr is None or sr is None:
            continue
        all_rs = []
        for s in symbols:
            fr = mm.fwd_return(prices[s], dates[s], d0, d1)
            if fr is not None:
                all_rs.append(fr)
        bh = (sum(all_rs) / len(all_rs)) if all_rs else 0.0

        cur_long = set(longs)
        cur_short = set(shorts)
        changed = len(cur_long.symmetric_difference(prev_long)) + \
            len(cur_short.symmetric_difference(prev_short))
        denom = (len(cur_long) + len(cur_short)) * 2
        turn_frac = (changed / denom) if denom else 0.0
        cost = turn_frac * (cost_bps_per_side / 1e4) * 2.0
        prev_long = cur_long
        prev_short = cur_short

        spread_rets.append((lr - sr) - cost)
        long_rets.append(lr)
        short_rets.append(sr)
        bh_rets.append(bh)
        reb_used.append(d1)
        for s in longs:
            sel_long[s] += 1
        for s in shorts:
            sel_short[s] += 1

    return {
        "symbols": symbols,
        "n_assets": len(symbols),
        "k": k,
        "n_months": len(spread_rets),
        "dates": reb_used,
        "spread_rets": spread_rets,
        "long_rets": long_rets,
        "short_rets": short_rets,
        "bh_rets": bh_rets,
        "sel_long": sel_long,
        "sel_short": sel_short,
    }


def rolling_sharpe(dates: List[str], rets: List[float], win: int = 24
                   ) -> List[Tuple[str, float]]:
    out = []
    for i in range(win, len(rets) + 1):
        seg = rets[i - win:i]
        out.append((dates[i - 1], mm.ann_sharpe(seg)))
    return out


def frac_positive_rolling(roll: List[Tuple[str, float]]) -> float:
    if not roll:
        return 0.0
    pos = sum(1 for _, s in roll if s > 0)
    return pos / len(roll)


def main():
    out = {}

    # (A) Tercile L/S, broad 11.
    for cost in (0.0, mm.COST_BPS_PER_SIDE):
        r = run_ls_tercile(mm.BROAD, cost_bps_per_side=cost, k=3)
        sp = r["spread_rets"]
        d = r["dates"]
        is_sp, oos_sp = mm.split_is_oos(d, sp, mm.OOS_SPLIT)
        key = f"tercile_broad11_{int(cost)}bps"
        out[key] = {
            "k": 3,
            "n_assets": 11,
            "n_months": r["n_months"],
            "span": (d[0] if d else None, d[-1] if d else None),
            "spread_fp_sharpe": mm.ann_sharpe(sp),
            "spread_fp_cum_pct": mm.cum_return(sp) * 100.0,
            "is_sharpe": mm.ann_sharpe(is_sp),
            "is_n": len(is_sp),
            "oos_sharpe": mm.ann_sharpe(oos_sp),
            "oos_n": len(oos_sp),
            "long_fp_sharpe": mm.ann_sharpe(r["long_rets"]),
            "short_fp_sharpe": mm.ann_sharpe(r["short_rets"]),
            "sel_long": r["sel_long"],
            "sel_short": r["sel_short"],
        }
        print(f"\n== {key} ==")
        print(json.dumps(out[key], indent=2, default=str))

    # (B) Rolling 24m sign stability for both baskets (zero cost spreads).
    r_broad = mm.run_ls(mm.BROAD, cost_bps_per_side=0.0)
    r_p6 = mm.run_ls(mm.PRIOR6, cost_bps_per_side=0.0)
    roll_broad = rolling_sharpe(r_broad["dates"], r_broad["spread_rets"], 24)
    roll_p6 = rolling_sharpe(r_p6["dates"], r_p6["spread_rets"], 24)
    out["rolling24_broad11"] = {
        "frac_windows_positive": frac_positive_rolling(roll_broad),
        "n_windows": len(roll_broad),
        "min": min((s for _, s in roll_broad), default=0.0),
        "max": max((s for _, s in roll_broad), default=0.0),
    }
    out["rolling24_prior6"] = {
        "frac_windows_positive": frac_positive_rolling(roll_p6),
        "n_windows": len(roll_p6),
        "min": min((s for _, s in roll_p6), default=0.0),
        "max": max((s for _, s in roll_p6), default=0.0),
    }
    print("\n== rolling 24m sign stability ==")
    print(json.dumps({k: out[k] for k in ("rolling24_broad11", "rolling24_prior6")},
                     indent=2, default=str))

    Path(WS / "_macromom_sensitivity.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\n[driver] wrote _macromom_sensitivity.json")


if __name__ == "__main__":
    main()
