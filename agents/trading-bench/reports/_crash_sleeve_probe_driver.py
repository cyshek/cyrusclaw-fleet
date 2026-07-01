"""CRASH-SLEEVE PROBE -- regime-gated tail-hedge 3rd sleeve.

QUESTION: Can a REGIME-GATED tail hedge (FLAT in bull/calm, engaged only on a
confirmed regime break) cut the live 2-sleeve allocator's OOS maxDD WITHOUT the
bull-market raw-return bleed that sank the STATIC 10% haven (which cost 161pp raw
for only -23.9 -> -21.5 maxDD)?

ENGINE: reuses _allocator_blend_tests.build_sleeves/blend_portfolio/report_blend
VERBATIM (zero sleeve-math reimplementation) and the validated hardened-haven
builder logic. New code = ONLY the regime-gated target_weight_fn + hedge streams.

RAILS: adjclose returns, 2bps one-way inter-sleeve turnover (incl hedge on/off
transitions), monthly rebal w/ intramonth drift, PAST-ONLY trailing 63d vol +
PAST-ONLY 200d SMA regime trigger, OOS split 2019-01-01, SPX (^GSPC) on the SAME
traded path. NO LOOKAHEAD. +1-bar canary on the best config (lethal test).
"""
from __future__ import annotations
import sys, json, math
sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from _allocator_blend_tests import (
    build_sleeves, blend_portfolio, report_blend, stats_from_returns,
    slice_equity_stats, equity_to_daily_returns, annualized_vol,
)

OOS_START = "2019-01-01"
SMA_WIN = 200


def adjclose_ret_map(sym):
    bars = dbc.get_daily(sym)
    ds = [b["date"] for b in bars]
    eq = [b["adjclose"] for b in bars]
    return equity_to_daily_returns(ds, eq)


def build_hardened_haven_stream(common):
    labels = ["GLD", "TLT", "DBC", "UUP"]
    maps = {s: adjclose_ret_map(s) for s in labels}
    cov = [d for d in common if all(d in maps[s] for s in labels)]
    series = {s: [maps[s][d] for d in cov] for s in labels}
    na = len(labels)
    n = len(cov)
    month_open = set()
    seen = set()
    for i, d in enumerate(cov):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open.add(i)

    def tgt(i, lookback=63):
        lo = max(0, i - lookback)
        inv = []
        ok = True
        for s in labels:
            w = series[s][lo:i]
            if len(w) < 10:
                ok = False
                break
            v = annualized_vol(w)
            if v <= 0:
                ok = False
                break
            inv.append(1.0 / v)
        if not ok:
            return [1.0 / na] * na
        tot = sum(inv)
        return [x / tot for x in inv]

    equity = [1.0]
    w0 = tgt(0)
    bucket = [w0[k] for k in range(na)]
    for i in range(1, n):
        if i in month_open:
            tot = sum(bucket)
            cur = [b / tot for b in bucket] if tot > 0 else [0.0] * na
            t = tgt(i)
            turn = sum(abs(t[k] - cur[k]) for k in range(na))
            cost = (2.0 / 10000.0) * turn
            tot_after = tot * (1.0 - cost)
            bucket = [t[k] * tot_after for k in range(na)]
        for k in range(na):
            bucket[k] *= (1.0 + series[labels[k]][i])
        equity.append(sum(bucket))
    hav_ret_map = {}
    for i in range(1, len(equity)):
        if equity[i - 1] > 0:
            hav_ret_map[cov[i]] = equity[i] / equity[i - 1] - 1.0
    return [hav_ret_map.get(d, 0.0) for d in common], labels, (cov[0] if cov else None)


def build_tlt_stream(common):
    m = adjclose_ret_map("TLT")
    return [m.get(d, 0.0) for d in common]


def build_regime_flags(spx_r, extra_lag=0):
    n = len(spx_r)
    price = [1.0] * n
    for i in range(1, n):
        price[i] = price[i - 1] * (1.0 + spx_r[i])
    flags = [False] * n
    for idx in range(n):
        cut = idx - 1 - extra_lag
        if cut < SMA_WIN:
            flags[idx] = False
            continue
        sma = sum(price[cut - SMA_WIN + 1: cut + 1]) / SMA_WIN
        flags[idx] = price[cut] < sma
    return flags


def make_gated_wfn(tqqq_r, rot_r, regime_flags, w_h, vol_lb=63):
    def fn(idx):
        if idx < 2:
            base = [0.5, 0.5]
        else:
            lo = max(0, idx - vol_lb)
            v0 = annualized_vol(tqqq_r[lo:idx])
            v1 = annualized_vol(rot_r[lo:idx])
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


def realized_hedge_diag(blend):
    wl = blend["weight_log"]
    if not wl:
        return {}
    hedge_ws = [row["w"][2] for row in wl]
    engaged = [w > 1e-9 for w in hedge_ws]
    trans = 0.0
    prev = 0.0
    for w in hedge_ws:
        trans += abs(w - prev)
        prev = w
    return {
        "n_rebal_months": len(wl),
        "avg_hedge_w_all_months": sum(hedge_ws) / len(hedge_ws),
        "avg_hedge_w_when_engaged": (sum(w for w in hedge_ws if w > 1e-9) / max(1, sum(engaged))),
        "pct_months_engaged": 100.0 * sum(engaged) / len(engaged),
        "hedge_leg_transition_turnover_total": trans,
    }


def run_config(dates, tqqq_r, rot_r, hedge_r, spx_dates, spx_equity, regime_flags, w_h, label):
    sleeves = [tqqq_r, rot_r, hedge_r]
    wfn = make_gated_wfn(tqqq_r, rot_r, regime_flags, w_h)
    b = blend_portfolio(dates, sleeves, wfn, blend_cost_bps=2.0)
    rep = report_blend(b, label, spx_dates, spx_equity)
    rep["hedge_diag"] = realized_hedge_diag(b)
    return rep, b


def main():
    S = build_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    spx_r = S["spx_r"]
    spx_curve = stats_from_returns(dates, spx_r)
    spx_dates = spx_curve["dates"]
    spx_equity = spx_curve["equity"]

    out = {"meta": {"common_window": [dates[0], dates[-1]], "n_days": len(dates),
                    "oos_split": OOS_START,
                    "regime": "SPX < trailing %dd SMA (past-only)" % SMA_WIN,
                    "lookahead_guard": ("every weight decision at month_open idx uses ONLY "
                                        "dates[:idx]/sleeves[:idx]; regime flag at idx uses SPX "
                                        "price/SMA through idx-1 (strictly past); hedge engages "
                                        "on forward returns only.")}}

    flags0 = build_regime_flags(spx_r, extra_lag=0)
    hedge_cash = [0.0] * len(dates)
    base_rep, _ = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, flags0, 0.0, "baseline_2sleeve")
    out["baseline"] = base_rep

    on_all = sum(1 for f in flags0 if f)
    oos_idx = [i for i, d in enumerate(dates) if d >= OOS_START]
    on_oos = sum(1 for i in oos_idx if flags0[i])
    out["regime_diag"] = {
        "pct_days_regime_on_full": 100.0 * on_all / len(flags0),
        "pct_days_regime_on_oos": 100.0 * on_oos / max(1, len(oos_idx)),
    }

    haven_r, haven_labels, haven_first = build_hardened_haven_stream(dates)
    tlt_r = build_tlt_stream(dates)
    instruments = {
        "cash": hedge_cash,
        "haven_GLD_TLT_DBC_UUP": haven_r,
        "TLT_alone": tlt_r,
    }
    out["meta"]["haven_labels"] = haven_labels
    out["meta"]["haven_first_covered_date"] = haven_first

    grid = [0.10, 0.15, 0.20, 0.25]
    out["configs"] = {}
    for inst_name, hr in instruments.items():
        for w_h in grid:
            label = "%s_wh%02d" % (inst_name, int(round(w_h * 100)))
            rep, _ = run_config(dates, tqqq_r, rot_r, hr, spx_dates, spx_equity, flags0, w_h, label)
            out["configs"][label] = rep

    base_oos_dd = out["baseline"]["oos_2019_today"]["maxdd_pct"]
    base_raw = out["baseline"]["full"]["total_return_pct"]
    scored = []
    for name, rep in out["configs"].items():
        oos_dd = rep["oos_2019_today"]["maxdd_pct"]
        raw = rep["full"]["total_return_pct"]
        dd_improve = oos_dd - base_oos_dd
        raw_giveup = base_raw - raw
        eff = dd_improve / max(1.0, raw_giveup) * 100.0
        scored.append((name, dd_improve, raw_giveup, eff, oos_dd, raw))
    cutters = [s for s in scored if s[1] > 0.2]
    out["scored"] = [{"name": s[0], "oos_dd_improve_pp": round(s[1], 3),
                      "raw_giveup_pp": round(s[2], 1), "dd_pp_per_100pp_raw": round(s[3], 3),
                      "oos_maxdd_pct": round(s[4], 3), "raw_ret_pct": round(s[5], 1)}
                     for s in sorted(scored, key=lambda x: x[1], reverse=True)]
    if cutters:
        best = max(cutters, key=lambda x: x[1])
    else:
        best = max(scored, key=lambda x: x[1])
    out["best_config"] = best[0]

    flags_lag = build_regime_flags(spx_r, extra_lag=1)
    best_name = best[0]
    inst_key = None
    for k in instruments:
        if best_name.startswith(k + "_wh"):
            inst_key = k
            break
    w_best = int(best_name.split("_wh")[-1]) / 100.0
    canary_rep, _ = run_config(dates, tqqq_r, rot_r, instruments[inst_key], spx_dates, spx_equity, flags_lag, w_best, best_name + "_CANARY_lag1")
    out["canary"] = {
        "config": best_name,
        "same_bar": {"oos_maxdd_pct": out["configs"][best_name]["oos_2019_today"]["maxdd_pct"],
                     "oos_sharpe": out["configs"][best_name]["oos_2019_today"]["sharpe"],
                     "full_sharpe": out["configs"][best_name]["full"]["sharpe"],
                     "raw_ret_pct": out["configs"][best_name]["full"]["total_return_pct"]},
        "lag1": {"oos_maxdd_pct": canary_rep["oos_2019_today"]["maxdd_pct"],
                 "oos_sharpe": canary_rep["oos_2019_today"]["sharpe"],
                 "full_sharpe": canary_rep["full"]["sharpe"],
                 "raw_ret_pct": canary_rep["full"]["total_return_pct"]},
    }
    out["canary"]["full_rep_lag1"] = canary_rep

    cash_scored = [s for s in scored if s[0].startswith("cash_wh")]
    if cash_scored:
        best_cash = max(cash_scored, key=lambda x: x[1])
        bc_w = int(best_cash[0].split("_wh")[-1]) / 100.0
        cc_rep, _ = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, flags_lag, bc_w, best_cash[0] + "_CANARY_lag1")
        out["canary_cash"] = {
            "config": best_cash[0],
            "same_bar": {"oos_maxdd_pct": out["configs"][best_cash[0]]["oos_2019_today"]["maxdd_pct"],
                         "oos_sharpe": out["configs"][best_cash[0]]["oos_2019_today"]["sharpe"],
                         "raw_ret_pct": out["configs"][best_cash[0]]["full"]["total_return_pct"]},
            "lag1": {"oos_maxdd_pct": cc_rep["oos_2019_today"]["maxdd_pct"],
                     "oos_sharpe": cc_rep["oos_2019_today"]["sharpe"],
                     "raw_ret_pct": cc_rep["full"]["total_return_pct"]},
        }

    with open("reports/_crash_sleeve_probe_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)

    print("")
    print("===== CRASH-SLEEVE PROBE =====")
    print("window %s -> %s  (%d days)  OOS split %s" % (dates[0], dates[-1], len(dates), OOS_START))
    b = out["baseline"]
    print("")
    print("BASELINE 2-sleeve: full Sharpe %.3f / OOS Sharpe %.3f / OOS maxDD %.2f%% / full maxDD %.2f%% / raw %.0f%% (SPX full CAGR %.2f%%)" % (
        b["full"]["sharpe"], b["oos_2019_today"]["sharpe"], b["oos_2019_today"]["maxdd_pct"],
        b["full"]["maxdd_pct"], b["full"]["total_return_pct"], b["spx_full"]["cagr_pct"]))
    print("regime ON: %.1f%% of days (full), %.1f%% (OOS)" % (
        out["regime_diag"]["pct_days_regime_on_full"], out["regime_diag"]["pct_days_regime_on_oos"]))
    print("")
    print("%-26s %8s %8s %8s %9s %7s %7s %7s" % ("config", "raw%", "OOSdd%", "OOSsh", "fullSh", "avgHw%", "engPct", "transTO"))
    print("%-26s %8.0f %8.2f %8.3f %9.3f %7s %7s %7s" % (
        "BASELINE", b["full"]["total_return_pct"], b["oos_2019_today"]["maxdd_pct"],
        b["oos_2019_today"]["sharpe"], b["full"]["sharpe"], "0.0", "0.0", "0.0"))
    for name, rep in out["configs"].items():
        hd = rep.get("hedge_diag", {})
        print("%-26s %8.0f %8.2f %8.3f %9.3f %7.1f %7.1f %7.2f" % (
            name, rep["full"]["total_return_pct"], rep["oos_2019_today"]["maxdd_pct"],
            rep["oos_2019_today"]["sharpe"], rep["full"]["sharpe"],
            100.0 * hd.get("avg_hedge_w_when_engaged", 0.0),
            hd.get("pct_months_engaged", 0.0),
            hd.get("hedge_leg_transition_turnover_total", 0.0)))
    print("")
    print("BEST (max OOS-DD cut): %s" % out["best_config"])
    c = out["canary"]
    print("CANARY +1-bar on %s:" % c["config"])
    print("   same-bar: OOSdd %.2f%% OOSsh %.3f fullSh %.3f raw %.0f%%" % (
        c["same_bar"]["oos_maxdd_pct"], c["same_bar"]["oos_sharpe"], c["same_bar"]["full_sharpe"], c["same_bar"]["raw_ret_pct"]))
    print("   lag+1  : OOSdd %.2f%% OOSsh %.3f fullSh %.3f raw %.0f%%" % (
        c["lag1"]["oos_maxdd_pct"], c["lag1"]["oos_sharpe"], c["lag1"]["full_sharpe"], c["lag1"]["raw_ret_pct"]))
    if "canary_cash" in out:
        cc = out["canary_cash"]
        print("CANARY +1-bar on best CASH %s:" % cc["config"])
        print("   same-bar: OOSdd %.2f%% OOSsh %.3f raw %.0f%%" % (
            cc["same_bar"]["oos_maxdd_pct"], cc["same_bar"]["oos_sharpe"], cc["same_bar"]["raw_ret_pct"]))
        print("   lag+1  : OOSdd %.2f%% OOSsh %.3f raw %.0f%%" % (
            cc["lag1"]["oos_maxdd_pct"], cc["lag1"]["oos_sharpe"], cc["lag1"]["raw_ret_pct"]))


if __name__ == "__main__":
    main()
