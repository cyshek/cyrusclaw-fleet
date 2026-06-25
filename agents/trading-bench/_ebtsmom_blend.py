"""EQUITY-BOOK x core4-TSMOM BLEND TEST.

Ingredient A: ERC-weighted live equity book daily returns, built by
capital-weighting reports/_volaware_series.json["returns_matrix"] with the
shipped live weights reports/_erc_weights.json["capital_usd_v2_tradeable"].

Ingredient B: core4 EW 12-1 TSMOM daily net returns, regenerated from the
validated _tsmom_engine (DBC GLD TLT UUP).

Blend: X in equity book, (1-X) in core4, monthly-rebalanced back to target mix,
2bps one-way on the two-sleeve weight turnover at each monthly rebalance.

Writes _ebtsmom_blend_results.json for the report builder.
"""
import json
import math
import datetime as dt
from typing import List, Dict, Tuple

import _tsmom_engine as E
from runner.fp_sharpe import sharpe_from_returns
from runner.backtest import bars_per_year
from runner import lane_honesty

BPY = bars_per_year("1Day", is_crypto=False)  # sqrt-of-252 convention internally
TRADING_DAYS = 252
SLEEVE_REBAL_ONE_WAY_BPS = 2.0  # 2bps one-way on |delta| of two-sleeve weights


# ----------------------------- stats helpers -----------------------------

def fp_sharpe(rets: List[float]) -> float:
    return sharpe_from_returns(rets, BPY)


def cagr_pct(rets: List[float]) -> float:
    return lane_honesty.cagr(rets, TRADING_DAYS)


def max_drawdown(rets: List[float]) -> float:
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


def total_return(rets: List[float]) -> float:
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    return eq - 1.0


def ann_vol(rets: List[float]) -> float:
    n = len(rets)
    if n < 2:
        return 0.0
    m = sum(rets) / n
    v = sum((r - m) ** 2 for r in rets) / (n - 1)
    return math.sqrt(v) * math.sqrt(TRADING_DAYS)


def corr(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    a = a[:n]; b = b[:n]
    if n < 2:
        return 0.0
    ma = sum(a) / n; mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def window_total(rets: List[float], dates: List[str], lo: str, hi: str) -> Tuple[float, int]:
    sub = [rets[k] for k in range(len(dates)) if lo <= dates[k] <= hi]
    return total_return(sub), len(sub)


def month_end_indices(dates: List[str]) -> List[int]:
    out = []
    for i in range(len(dates)):
        cur = dates[i][:7]
        nxt = dates[i + 1][:7] if i + 1 < len(dates) else None
        if nxt != cur:
            out.append(i)
    return out


# ----------------------------- ingredient A: book -----------------------------

def build_book() -> Tuple[List[str], List[float], Dict]:
    series = json.load(open("reports/_volaware_series.json"))
    weights = json.load(open("reports/_erc_weights.json"))
    live = series["live"]
    dates = series["common_dates"]
    mat = series["returns_matrix"]
    cap = weights["capital_usd_v2_tradeable"]
    budget = sum(cap.values())
    w = [cap[name] / budget for name in live]
    assert abs(sum(w) - 1.0) < 1e-9, sum(w)
    book = []
    for row in mat:
        book.append(sum(w[i] * row[i] for i in range(len(live))))
    meta = {
        "live": live,
        "budget_usd": budget,
        "weights_norm": {live[i]: w[i] for i in range(len(live))},
        "n": len(book),
        "span": (dates[0], dates[-1]),
    }
    return dates, book, meta


# ----------------------------- ingredient B: core4 -----------------------------

def build_core4() -> Tuple[List[str], List[float], Dict]:
    res = E.run_tsmom(["DBC", "GLD", "TLT", "UUP"], lookback_m=12, skip_m=1,
                      weighting="ew", start_date="2008-04-01")
    dates = res["dates"]
    net = res["net"]
    spy = E.spy_buyhold_on_path(dates)
    repro = {
        "n": len(net),
        "span": (dates[0], dates[-1]),
        "fp_sharpe": round(fp_sharpe(net), 4),
        "fp_cagr": round(cagr_pct(net), 3),
        "fp_total_ret": round(total_return(net), 4),
        "fp_maxdd": round(max_drawdown(net), 4),
        "fp_corr_spy": round(corr(net, spy), 4),
        "c2020": [round(x, 4) for x in window_total(net, dates, "2020-02-19", "2020-04-30")],
        "c2022": [round(x, 4) for x in window_total(net, dates, "2022-01-01", "2022-12-31")],
    }
    return dates, net, repro


# ----------------------------- blend -----------------------------

def blend_series(book_r: List[float], core_r: List[float], dates: List[str],
                 X: float, rebal_idx: set, one_way_bps: float = SLEEVE_REBAL_ONE_WAY_BPS):
    """Monthly-rebalanced 2-sleeve blend. Target mix: X in book, (1-X) in core4.

    We track the dollar value of each sleeve. Between rebalances the sleeve
    weights drift with their own returns. On each month-end we snap back to the
    target (X, 1-X) and charge a cost = one_way_bps * sum|w_after_target - w_before_drift|
    on the combined equity that day (turnover of the two-sleeve weights).
    """
    n = len(dates)
    # start at target mix
    v_book = X
    v_core = 1.0 - X
    blend_rets: List[float] = []
    total_rebal_cost = 0.0
    n_rebal = 0
    for i in range(n):
        tot_before = v_book + v_core
        # grow each sleeve by its daily return
        v_book *= (1.0 + book_r[i])
        v_core *= (1.0 + core_r[i])
        tot_after = v_book + v_core
        day_ret = tot_after / tot_before - 1.0 if tot_before > 0 else 0.0
        # rebalance at month-end close -> snap weights back to target, charge cost
        if i in rebal_idx:
            tot = v_book + v_core
            if tot > 0:
                w_book = v_book / tot
                w_core = v_core / tot
                # turnover of two-sleeve weights = |w_book - X| + |w_core - (1-X)|
                turn = abs(w_book - X) + abs(w_core - (1.0 - X))
                cost_frac = turn * (one_way_bps / 1e4)
                # debit today's blend return and rescale sleeve dollars post-cost
                day_ret -= cost_frac
                total_rebal_cost += cost_frac
                n_rebal += 1
                tot_post = tot * (1.0 - cost_frac)
                v_book = X * tot_post
                v_core = (1.0 - X) * tot_post
        blend_rets.append(day_ret)
    return blend_rets, {"total_rebal_cost_frac": total_rebal_cost, "n_rebal": n_rebal}


def stat_pack(rets: List[float], dates: List[str]) -> Dict:
    c2020 = window_total(rets, dates, "2020-02-19", "2020-04-30")
    c2022 = window_total(rets, dates, "2022-01-01", "2022-12-31")
    c2018q4 = window_total(rets, dates, "2018-10-01", "2018-12-31")
    return {
        "sharpe": round(fp_sharpe(rets), 4),
        "cagr_pct": round(cagr_pct(rets), 4),
        "total_ret": round(total_return(rets), 4),
        "maxdd": round(max_drawdown(rets), 4),
        "ann_vol": round(ann_vol(rets), 4),
        "c2020": [round(c2020[0], 4), c2020[1]],
        "c2022": [round(c2022[0], 4), c2022[1]],
        "c2018q4": [round(c2018q4[0], 4), c2018q4[1]],
    }


def main():
    book_dates, book_full, book_meta = build_book()
    core_dates, core_full, core_repro = build_core4()

    # standalone book stats (full book series, its own dates)
    book_standalone = stat_pack(book_full, book_dates)

    # ----- align on common date intersection -----
    bmap = {d: book_full[k] for k, d in enumerate(book_dates)}
    cmap = {d: core_full[k] for k, d in enumerate(core_dates)}
    common = sorted(set(bmap) & set(cmap))
    book_r = [bmap[d] for d in common]
    core_r = [cmap[d] for d in common]
    n_common = len(common)

    corr_bc = corr(book_r, core_r)

    # book stats ON THE ALIGNED window (the X=1.00 baseline for deltas)
    book_aligned = stat_pack(book_r, common)
    core_aligned = stat_pack(core_r, common)

    rebal_idx = set(month_end_indices(common))

    Xs = [1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.60, 0.50]
    sweep = []
    for X in Xs:
        br, bx = blend_series(book_r, core_r, common, X, rebal_idx)
        sp = stat_pack(br, common)
        sp["X"] = X
        sp["frac_core"] = round(1.0 - X, 2)
        sp["n_rebal"] = bx["n_rebal"]
        sp["total_rebal_cost_frac"] = round(bx["total_rebal_cost_frac"], 6)
        sweep.append(sp)

    # baseline = X=1.00 row
    base = next(r for r in sweep if abs(r["X"] - 1.00) < 1e-9)

    # best risk-adjusted (max sharpe) and min maxdd among X<=0.90 (>=10% diversifier)
    elig = [r for r in sweep if r["X"] <= 0.90 + 1e-9]
    best_sharpe = max(sweep, key=lambda r: r["sharpe"])
    best_dd = max(sweep, key=lambda r: r["maxdd"])  # maxdd negative; max = least negative
    best_sharpe_div = max(elig, key=lambda r: r["sharpe"]) if elig else None
    best_dd_div = max(elig, key=lambda r: r["maxdd"]) if elig else None

    def deltas(r):
        return {
            "X": r["X"],
            "frac_core": r["frac_core"],
            "dSharpe": round(r["sharpe"] - base["sharpe"], 4),
            "dMaxDD_abs_pts": round((r["maxdd"] - base["maxdd"]) * 100, 2),  # +ve = shallower DD
            "dCAGR_pts": round(r["cagr_pct"] - base["cagr_pct"], 4),
            "dAnnVol_pts": round((r["ann_vol"] - base["ann_vol"]) * 100, 4),
        }

    out = {
        "book_meta": book_meta,
        "book_standalone_fullseries": book_standalone,
        "book_standalone_span": book_meta["span"],
        "core4_repro": core_repro,
        "core4_span": core_repro["span"],
        "alignment": {
            "n_common": n_common,
            "common_span": (common[0], common[-1]),
            "book_n": len(book_full),
            "core_n": len(core_full),
        },
        "book_aligned": book_aligned,
        "core_aligned": core_aligned,
        "corr_book_core4": round(corr_bc, 4),
        "sweep": sweep,
        "baseline_X1": base,
        "best_sharpe_overall": {"X": best_sharpe["X"], "sharpe": best_sharpe["sharpe"]},
        "best_dd_overall": {"X": best_dd["X"], "maxdd": best_dd["maxdd"]},
        "best_sharpe_div10": deltas(best_sharpe_div) if best_sharpe_div else None,
        "best_dd_div10": deltas(best_dd_div) if best_dd_div else None,
        "deltas_all": [deltas(r) for r in sweep],
        "sleeve_rebal_one_way_bps": SLEEVE_REBAL_ONE_WAY_BPS,
    }
    with open("_ebtsmom_blend_results.json", "w") as f:
        json.dump(out, f, indent=2)

    # ----- console summary -----
    print("=== INGREDIENT A: equity book ===")
    print(f"  budget=${book_meta['budget_usd']:.0f}  n={book_meta['n']}  span={book_meta['span']}")
    print(f"  standalone: Sharpe={book_standalone['sharpe']:.4f} CAGR={book_standalone['cagr_pct']:.3f}% "
          f"maxDD={book_standalone['maxdd']*100:.2f}% annVol={book_standalone['ann_vol']*100:.2f}% "
          f"totRet={book_standalone['total_ret']*100:.1f}%")
    print()
    print("=== INGREDIENT B: core4 reproduction check ===")
    print(f"  Sharpe={core_repro['fp_sharpe']:.4f} (exp ~0.3051)  CAGR={core_repro['fp_cagr']:.3f}% (exp ~2.682) "
          f"maxDD={core_repro['fp_maxdd']*100:.2f}% (exp ~-24.74) corrSPY={core_repro['fp_corr_spy']:.4f} (exp ~-0.0139)")
    print(f"  2020={core_repro['c2020'][0]*100:+.1f}% (exp +4.7)  2022={core_repro['c2022'][0]*100:+.1f}% (exp +2.81)")
    print()
    print(f"=== ALIGNMENT: n_common={n_common} span={common[0]}..{common[-1]} ===")
    print(f"=== CORR(book, core4) = {corr_bc:.4f} ===")
    print(f"  book aligned: Sharpe={book_aligned['sharpe']:.4f} CAGR={book_aligned['cagr_pct']:.3f}% maxDD={book_aligned['maxdd']*100:.2f}%")
    print(f"  core aligned: Sharpe={core_aligned['sharpe']:.4f} CAGR={core_aligned['cagr_pct']:.3f}% maxDD={core_aligned['maxdd']*100:.2f}%")
    print()
    print("=== X-SWEEP (X = frac in equity book) ===")
    hdr = f"{'X':>5} {'core%':>6} {'Sharpe':>7} {'CAGR%':>7} {'maxDD%':>7} {'annVol%':>7} {'2020%':>7} {'2022%':>7} {'18Q4%':>7}"
    print(hdr)
    for r in sweep:
        print(f"{r['X']:>5.2f} {r['frac_core']*100:>5.0f}% {r['sharpe']:>7.4f} {r['cagr_pct']:>7.3f} "
              f"{r['maxdd']*100:>7.2f} {r['ann_vol']*100:>7.2f} {r['c2020'][0]*100:>+7.1f} "
              f"{r['c2022'][0]*100:>+7.1f} {r['c2018q4'][0]*100:>+7.1f}")
    print()
    print(f"=== BEST overall Sharpe: X={best_sharpe['X']:.2f} Sharpe={best_sharpe['sharpe']:.4f} ===")
    print(f"=== BEST overall maxDD : X={best_dd['X']:.2f} maxDD={best_dd['maxdd']*100:.2f}% ===")
    if best_sharpe_div:
        d = deltas(best_sharpe_div)
        print(f"=== BEST Sharpe @ div>=10%: X={d['X']:.2f} (core {d['frac_core']*100:.0f}%) "
              f"dSharpe={d['dSharpe']:+.4f} dMaxDD={d['dMaxDD_abs_pts']:+.2f}pts dCAGR={d['dCAGR_pts']:+.3f}pts ===")
    if best_dd_div:
        d = deltas(best_dd_div)
        print(f"=== BEST maxDD @ div>=10% : X={d['X']:.2f} (core {d['frac_core']*100:.0f}%) "
              f"dSharpe={d['dSharpe']:+.4f} dMaxDD={d['dMaxDD_abs_pts']:+.2f}pts dCAGR={d['dCAGR_pts']:+.3f}pts ===")
    print()
    print("wrote _ebtsmom_blend_results.json")


if __name__ == "__main__":
    main()
