"""
TSMOM BLEND TEST -- equity book (8-strat ERC-risk-weighted) x core4 multi-asset TSMOM.
Pure research; reuses _tsmom_engine + _xstrat_corr primitives. No literal backslash-n anywhere.
"""
import json
import _tsmom_engine as E
import _xstrat_corr as X

LIVE8 = [
    "breakout_xlk__mut_c382b1",
    "sma_crossover_qqq_regime",
    "sma_crossover_qqq_rth",
    "rsi_oversold_spy",
    "volume_breakout_qqq",
    "macd_momentum_iwm",
    "tqqq_cot_combo",
    "allocator_blend",
]

CRISES = {
    "2008": ("2008-09-01", "2009-03-31"),
    "2020": ("2020-02-19", "2020-04-30"),
    "2022": ("2022-01-01", "2022-12-31"),
}


def comp(rets):
    g = 1.0
    for r in rets:
        g *= (1.0 + r)
    return g - 1.0


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
    return {
        "label": label,
        "n": len(rets),
        "start": ds[0] if ds else None,
        "end": ds[-1] if ds else None,
        "sharpe": shp,
        "cagr_pct": cg,
        "maxdd": mdd,
        "total_return": tr,
        "corr_spy": cc,
    }


def main():
    erc = json.load(open("reports/_erc_weights.json"))
    rw = erc["risk_weights"]
    assert set(rw.keys()) == set(LIVE8), "risk_weights keys != LIVE8"
    wsum = sum(rw.values())
    rwn = {k: v / wsum for k, v in rw.items()}
    cap = erc.get("capital_weights") or erc.get("capital") or None

    series, meta, spy_ret = X.build_all_series()

    date_sets = []
    for nm in LIVE8:
        assert nm in series, ("missing series: " + nm)
        date_sets.append(set(series[nm].keys()))
    common8 = sorted(set.intersection(*date_sets))
    print("[book] common8 window:", common8[0], "..", common8[-1], "n=", len(common8))

    book = {}
    for d in common8:
        book[d] = sum(rwn[nm] * series[nm][d] for nm in LIVE8)

    book_cap = None
    if cap and set(cap.keys()) >= set(LIVE8):
        csum = sum(cap[nm] for nm in LIVE8)
        capn = {nm: cap[nm] / csum for nm in LIVE8}
        book_cap = {d: sum(capn[nm] * series[nm][d] for nm in LIVE8) for d in common8}

    out = E.run_tsmom(["DBC", "GLD", "TLT", "UUP"], lookback_m=12, skip_m=1,
                      weighting="ew", start_date="2008-05-01")
    core4 = {dte: r for dte, r in zip(out["dates"], out["net"])}
    print("[core4] window:", out["dates"][0], "..", out["dates"][-1], "n=", len(out["dates"]))

    cb = sorted(set(book.keys()) & set(core4.keys()))
    print("[blend] common window:", cb[0], "..", cb[-1], "n=", len(cb))

    book_cw = {d: book[d] for d in cb}
    core4_cw = {d: core4[d] for d in cb}

    ratios = [("baseline_book", 1.0), ("80/20", 0.80), ("70/30", 0.70),
              ("60/40", 0.60), ("50/50", 0.50)]
    blends = {}
    for label, x in ratios:
        blends[label] = {d: x * book_cw[d] + (1.0 - x) * core4_cw[d] for d in cb}

    series_all = {
        "baseline_book": book_cw,
        "80/20": blends["80/20"],
        "70/30": blends["70/30"],
        "60/40": blends["60/40"],
        "50/50": blends["50/50"],
        "core4_standalone_cw": core4_cw,
    }

    rows = {}
    for label, m in series_all.items():
        rows[label] = stats(m, label, spy_ret)

    core4_full = stats(core4, "core4_full_span", spy_ret)
    book_full = stats(book, "book_full_span_common8", spy_ret)

    spy_path = E.spy_buyhold_on_path(cb)
    spy_cw = {d: r for d, r in zip(cb, spy_path)}
    spy_stats = stats(spy_cw, "SPY_buyhold_cw", spy_ret)

    crisis = {}
    cwset = set(cb)
    for cname, (lo, hi) in CRISES.items():
        crisis[cname] = {}
        for label, m in series_all.items():
            r, ds = window_rets(m, lo, hi)
            crisis[cname][label] = {
                "ret": comp(r) if r else None,
                "n": len(r),
                "span": [ds[0], ds[-1]] if ds else None,
            }
        rspy, dsspy = window_rets(spy_ret, lo, hi)
        dssp2 = [d for d in dsspy if d in cwset]
        rsp2 = [spy_ret[d] for d in dssp2]
        crisis[cname]["SPY"] = {
            "ret": comp(rsp2) if rsp2 else None,
            "n": len(rsp2),
            "span": [dssp2[0], dssp2[-1]] if dssp2 else None,
        }

    result = {
        "common8_window": [common8[0], common8[-1], len(common8)],
        "core4_full_window": [out["dates"][0], out["dates"][-1], len(out["dates"])],
        "blend_common_window": [cb[0], cb[-1], len(cb)],
        "risk_weights_normalized": rwn,
        "rows": rows,
        "core4_full": core4_full,
        "book_full": book_full,
        "spy_buyhold_cw": spy_stats,
        "crisis": crisis,
        "book_cap_available": book_cap is not None,
    }
    if book_cap is not None:
        book_cap_cw = {d: book_cap[d] for d in cb}
        result["book_cap_stats"] = stats(book_cap_cw, "book_capital_weighted_cw", spy_ret)

    with open("reports/_tsmom_blend_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    print("")
    print("================ FULL-PERIOD (blend common window) ================")
    hdr = ("series".ljust(22) + "Sharpe".rjust(8) + "CAGR%".rjust(9) +
           "maxDD%".rjust(9) + "corrSPY".rjust(9) + "totRet%".rjust(10) + "n".rjust(7))
    print(hdr)
    order = ["baseline_book", "80/20", "70/30", "60/40", "50/50", "core4_standalone_cw"]
    for label in order:
        s = rows[label]
        line = (label.ljust(22) + ("%.3f" % s["sharpe"]).rjust(8) +
                ("%.2f" % s["cagr_pct"]).rjust(9) + ("%.2f" % (s["maxdd"] * 100)).rjust(9) +
                ("%.3f" % s["corr_spy"]).rjust(9) +
                ("%.1f" % (s["total_return"] * 100)).rjust(10) + str(s["n"]).rjust(7))
        print(line)
    s = spy_stats
    line = ("SPY_buyhold_cw".ljust(22) + ("%.3f" % s["sharpe"]).rjust(8) +
            ("%.2f" % s["cagr_pct"]).rjust(9) + ("%.2f" % (s["maxdd"] * 100)).rjust(9) +
            ("%.3f" % s["corr_spy"]).rjust(9) +
            ("%.1f" % (s["total_return"] * 100)).rjust(10) + str(s["n"]).rjust(7))
    print(line)

    print("")
    print("--- context (own full spans) ---")
    for s in (book_full, core4_full):
        print(s["label"], s["start"], "..", s["end"], "n=", s["n"],
              "Sharpe=%.3f" % s["sharpe"], "CAGR=%.2f%%" % s["cagr_pct"],
              "maxDD=%.2f%%" % (s["maxdd"] * 100), "corrSPY=%.3f" % s["corr_spy"],
              "totRet=%.1f%%" % (s["total_return"] * 100))

    print("")
    print("================ CRISIS WINDOWS (compound return) ================")
    for cname in ["2008", "2020", "2022"]:
        print("")
        print("-- " + cname + " (" + CRISES[cname][0] + ".." + CRISES[cname][1] + ") --")
        for label in order + ["SPY"]:
            c = crisis[cname][label]
            rv = "n/a" if c["ret"] is None else ("%+.2f%%" % (c["ret"] * 100))
            print("  " + label.ljust(22) + rv.rjust(10) + "  n=" + str(c["n"]) +
                  "  span=" + str(c["span"]))

    if book_cap is not None:
        s = result["book_cap_stats"]
        print("")
        print("[secondary] capital-weighted book: Sharpe=%.3f CAGR=%.2f%% maxDD=%.2f%% corrSPY=%.3f"
              % (s["sharpe"], s["cagr_pct"], s["maxdd"] * 100, s["corr_spy"]))

    print("")
    print("DONE -> reports/_tsmom_blend_result.json")


if __name__ == "__main__":
    main()
