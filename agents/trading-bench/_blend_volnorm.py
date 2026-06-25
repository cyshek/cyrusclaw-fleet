"""
Vol-normalized blend variant + diagnostics.
Problem found: _xstrat_corr daily series mix scales -- 6 event sleeves are
equity-curve returns on a 100k account with tiny position sizing (~0.01% ann vol),
while tqqq_cot_combo/allocator_blend are full-notional vol-target harness returns
(16-19% ann vol). Applying ERC *risk_weights* (built for unit-vol bets) to these
raw mixed-scale series does NOT equalize risk and inflates Sharpe via the near-zero-
vol sleeves. Fix: scale each sleeve to a common target ann vol, THEN ERC-weight.
This yields an honest unit-risk book to compare against core4.
"""
import json
import math
import _tsmom_engine as E
import _xstrat_corr as X

LIVE8 = [
    "breakout_xlk__mut_c382b1", "sma_crossover_qqq_regime", "sma_crossover_qqq_rth",
    "rsi_oversold_spy", "volume_breakout_qqq", "macd_momentum_iwm",
    "tqqq_cot_combo", "allocator_blend",
]
CRISES = {
    "2008": ("2008-09-01", "2009-03-31"),
    "2020": ("2020-02-19", "2020-04-30"),
    "2022": ("2022-01-01", "2022-12-31"),
}
TARGET_VOL = 0.10  # 10% annualized per-sleeve before ERC weighting


def comp(rets):
    g = 1.0
    for r in rets:
        g *= (1.0 + r)
    return g - 1.0


def ann_vol(rets):
    n = len(rets)
    m = sum(rets) / n
    v = sum((x - m) ** 2 for x in rets) / (n - 1)
    return math.sqrt(v) * math.sqrt(252)


def window_rets(date_to_ret, lo, hi):
    ds = sorted(d for d in date_to_ret if lo <= d <= hi)
    return [date_to_ret[d] for d in ds], ds


def stats(date_to_ret, label, spy_map):
    ds = sorted(date_to_ret.keys())
    rets = [date_to_ret[d] for d in ds]
    shp = E.sharpe_from_returns(rets, E.BPY)
    cg = E.lane_honesty.cagr(rets, E.TRADING_DAYS)
    mdd = E.max_drawdown(rets)
    tr = E.total_return(rets)
    common = [d for d in ds if d in spy_map]
    a = [date_to_ret[d] for d in common]
    b = [spy_map[d] for d in common]
    cc = E.corr(a, b)
    return {"label": label, "n": len(rets), "start": ds[0] if ds else None,
            "end": ds[-1] if ds else None, "sharpe": shp, "cagr_pct": cg,
            "maxdd": mdd, "total_return": tr, "corr_spy": cc,
            "ann_vol": ann_vol(rets) if len(rets) > 2 else None}


def main():
    erc = json.load(open("reports/_erc_weights.json"))
    rw = erc["risk_weights"]
    wsum = sum(rw.values())
    rwn = {k: v / wsum for k, v in rw.items()}

    series, meta, spy_ret = X.build_all_series()
    common8 = sorted(set.intersection(*[set(series[nm].keys()) for nm in LIVE8]))

    # --- per-sleeve vol on the COMMON window, then scale to TARGET_VOL ---
    scale = {}
    print("per-sleeve ann vol on common window + scale factor to %.0f%%:" % (TARGET_VOL * 100))
    for nm in LIVE8:
        rr = [series[nm][d] for d in common8]
        v = ann_vol(rr)
        sc = TARGET_VOL / v if v > 1e-9 else 0.0
        scale[nm] = sc
        print("   %-26s vol=%6.2f%% scale=%8.2fx w_risk=%.3f"
              % (nm, v * 100, sc, rwn[nm]))

    # vol-normalized, ERC-weighted book
    book_vn = {}
    for d in common8:
        book_vn[d] = sum(rwn[nm] * scale[nm] * series[nm][d] for nm in LIVE8)

    # core4
    out = E.run_tsmom(["DBC", "GLD", "TLT", "UUP"], lookback_m=12, skip_m=1,
                      weighting="ew", start_date="2008-05-01")
    core4 = {dte: r for dte, r in zip(out["dates"], out["net"])}

    cb = sorted(set(book_vn.keys()) & set(core4.keys()))
    book_cw = {d: book_vn[d] for d in cb}
    core4_cw = {d: core4[d] for d in cb}

    # scale core4 to same TARGET_VOL too? NO -- core4 is reported as-is (its real
    # standalone). But for a fair *unit-risk* blend we ALSO show a vol-matched core4
    # blend variant. Primary: blend the vol-normed unit-risk book with as-is core4.
    ratios = [("baseline_book", 1.0), ("80/20", 0.80), ("70/30", 0.70),
              ("60/40", 0.60), ("50/50", 0.50)]
    series_all = {}
    for label, x in ratios:
        if label == "baseline_book":
            series_all[label] = book_cw
        else:
            series_all[label] = {d: x * book_cw[d] + (1.0 - x) * core4_cw[d] for d in cb}
    series_all["core4_standalone_cw"] = core4_cw

    rows = {label: stats(m, label, spy_ret) for label, m in series_all.items()}

    spy_path = E.spy_buyhold_on_path(cb)
    spy_cw = {d: r for d, r in zip(cb, spy_path)}
    spy_stats = stats(spy_cw, "SPY_buyhold_cw", spy_ret)

    crisis = {}
    cwset = set(cb)
    for cname, (lo, hi) in CRISES.items():
        crisis[cname] = {}
        for label, m in series_all.items():
            r, ds = window_rets(m, lo, hi)
            crisis[cname][label] = {"ret": comp(r) if r else None, "n": len(r)}
        rspy, dsspy = window_rets(spy_ret, lo, hi)
        dssp2 = [d for d in dsspy if d in cwset]
        rsp2 = [spy_ret[d] for d in dssp2]
        crisis[cname]["SPY"] = {"ret": comp(rsp2) if rsp2 else None, "n": len(rsp2)}

    result = {"blend_common_window": [cb[0], cb[-1], len(cb)],
              "target_vol": TARGET_VOL, "scale": scale, "rows": rows,
              "spy_buyhold_cw": spy_stats, "crisis": crisis}
    with open("reports/_tsmom_blend_volnorm_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    print("")
    print("======= VOL-NORMALIZED book (each sleeve->10% ann vol, then ERC) =======")
    print("blend window:", cb[0], "..", cb[-1], "n=", len(cb))
    hdr = ("series".ljust(22) + "Sharpe".rjust(8) + "CAGR%".rjust(9) +
           "maxDD%".rjust(9) + "annVol%".rjust(9) + "corrSPY".rjust(9) +
           "totRet%".rjust(10))
    print(hdr)
    order = ["baseline_book", "80/20", "70/30", "60/40", "50/50", "core4_standalone_cw"]
    for label in order:
        s = rows[label]
        print(label.ljust(22) + ("%.3f" % s["sharpe"]).rjust(8) +
              ("%.2f" % s["cagr_pct"]).rjust(9) + ("%.2f" % (s["maxdd"] * 100)).rjust(9) +
              ("%.2f" % s["ann_vol"]).rjust(9) + ("%.3f" % s["corr_spy"]).rjust(9) +
              ("%.1f" % (s["total_return"] * 100)).rjust(10))
    s = spy_stats
    print("SPY_buyhold_cw".ljust(22) + ("%.3f" % s["sharpe"]).rjust(8) +
          ("%.2f" % s["cagr_pct"]).rjust(9) + ("%.2f" % (s["maxdd"] * 100)).rjust(9) +
          ("%.2f" % s["ann_vol"]).rjust(9) + ("%.3f" % s["corr_spy"]).rjust(9) +
          ("%.1f" % (s["total_return"] * 100)).rjust(10))

    print("")
    print("--- crisis (compound) ---")
    for cname in ["2008", "2020", "2022"]:
        parts = []
        for label in order + ["SPY"]:
            c = crisis[cname][label]
            rv = "n/a" if c["ret"] is None else ("%+.2f%%" % (c["ret"] * 100))
            parts.append(label.split("_")[0] + "=" + rv)
        print(cname + ": " + "  ".join(parts))

    print("")
    print("DONE -> reports/_tsmom_blend_volnorm_result.json")


if __name__ == "__main__":
    main()
