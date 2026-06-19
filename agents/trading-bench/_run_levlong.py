"""Run the leveraged_long_trend backtest end-to-end and dump results to JSON.

Produces:
  - full-window headline (strategy vs SPX vs buy&hold-TQQQ)
  - stress-window breakdown (2018-Q4, 2020 COVID, 2022 bear, 2023-24 bull)
  - frozen-OOS: default params, in-sample 2010-2018, OOS 2019->today
  - a UPRO/SPX second cut + gate-mode variants + no-VIX-gate isolation
Writes reports/_levlong_result.json (intermediate, consumed by the report writer).
"""
import sys
import json
import bisect
sys.path.insert(0, ".")

from strategies_candidates.leveraged_long_trend.backtest_daily import (
    LevLongParams, run_backtest, subwindow_stats, _stats_from_equity,
)


def slice_curve_stats(result, start, end):
    ds = result["strategy"]["dates"]
    lo = bisect.bisect_left(ds, start)
    hi = bisect.bisect_right(ds, end)
    s_eq = result["strategy"]["equity"][lo:hi]
    s_ds = ds[lo:hi]
    flags = [pl["pos"] != "cash" for pl in result["pos_log"] if start <= pl["date"] <= end]
    strat = _stats_from_equity(s_ds, s_eq, flags, 0)
    spx = _stats_from_equity(s_ds, result["spx"]["equity"][lo:hi])
    slv = _stats_from_equity(s_ds, result["bh_sleeve"]["equity"][lo:hi])
    return {
        "strategy": strat.__dict__,
        "spx": spx.__dict__,
        "bh_sleeve": slv.__dict__,
        "start": s_ds[0] if s_ds else start,
        "end": s_ds[-1] if s_ds else end,
        "n": hi - lo,
    }


def trim(result):
    return {
        "params": result["params"],
        "window": result["window"],
        "strategy_stats": result["strategy"]["stats"],
        "spx_stats": result["spx"]["stats"],
        "bh_sleeve_stats": result["bh_sleeve"]["stats"],
    }


out = {}

# ---- CORE: TQQQ gated by QQQ, full window ----
p = LevLongParams()
print("running core TQQQ/QQQ full window ...", flush=True)
res = run_backtest(p)
out["core"] = trim(res)

# ---- stress windows ----
stress = {
    "2018Q4": ("2018-10-01", "2018-12-31"),
    "2020_covid": ("2020-02-15", "2020-04-15"),
    "2022_bear": ("2022-01-01", "2022-12-31"),
    "2023_2024_bull": ("2023-01-01", "2024-12-31"),
}
out["stress"] = {k: subwindow_stats(res, a, b) for k, (a, b) in stress.items()}

# ---- frozen-OOS ----
print("computing frozen-OOS slices ...", flush=True)
out["oos"] = {
    "in_sample_2010_2018": slice_curve_stats(res, "2010-01-01", "2018-12-31"),
    "oos_2019_today": slice_curve_stats(res, "2019-01-01", "2099-12-31"),
}

# ---- second cut: UPRO gated by SPX ----
print("running second cut UPRO/SPY ...", flush=True)
try:
    p2 = LevLongParams(sleeve="UPRO", underlying="SPY", benchmark="^GSPC")
    res2 = run_backtest(p2)
    out["upro_cut"] = trim(res2)
except Exception as e:
    out["upro_cut"] = {"error": "%s: %s" % (type(e).__name__, e)}

# ---- gate-mode variants ----
print("running gate-mode variants ...", flush=True)
out["gate_variants"] = {}
for mode in ("tsmom", "both"):
    try:
        pv = LevLongParams(gate_mode=mode)
        rv = run_backtest(pv)
        out["gate_variants"][mode] = {"strategy_stats": rv["strategy"]["stats"]}
    except Exception as e:
        out["gate_variants"][mode] = {"error": "%s: %s" % (type(e).__name__, e)}

# ---- no-VIX-gate isolation ----
try:
    pnv = LevLongParams(vix_gate=False)
    rnv = run_backtest(pnv)
    out["no_vix_gate"] = {"strategy_stats": rnv["strategy"]["stats"]}
except Exception as e:
    out["no_vix_gate"] = {"error": "%s: %s" % (type(e).__name__, e)}

with open("reports/_levlong_result.json", "w") as f:
    json.dump(out, f, indent=2)

# ---- console summary ----
c = out["core"]
print("")
print("=== CORE TQQQ/QQQ (sma200 + VIX gate), %s -> %s ===" % (c["window"]["start"], c["window"]["end"]))


def line(tag, s):
    print("  %-12s totRet %+12.1f%%  CAGR %+7.2f%%  maxDD %7.2f%%  vol %6.2f%%  Sharpe %5.2f" % (
        tag, s["total_return_pct"], s["cagr_pct"], s["max_drawdown_pct"], s["ann_vol_pct"], s["sharpe"]))


line("STRATEGY", c["strategy_stats"])
line("SPX(bh)", c["spx_stats"])
line("TQQQ(bh)", c["bh_sleeve_stats"])
print("  in-market %.1f%%  switches %d" % (
    c["strategy_stats"]["pct_in_market"], c["strategy_stats"]["n_switches"]))
print("")
print("=== FROZEN-OOS ===")
for k in ("in_sample_2010_2018", "oos_2019_today"):
    o = out["oos"][k]
    print("  %-22s STRAT %+11.1f%%  vs SPX %+10.1f%%  (strat maxDD %.1f%%)" % (
        k, o["strategy"]["total_return_pct"], o["spx"]["total_return_pct"],
        o["strategy"]["max_drawdown_pct"]))
print("")
print("=== STRESS WINDOWS (strat vs SPX vs bh-TQQQ) ===")
for k, v in out["stress"].items():
    if "strategy_ret_pct" in v:
        print("  %-16s STRAT %+9.1f%%  SPX %+8.1f%%  bhTQQQ %+11.1f%%  (cash %.0f%%)" % (
            k, v["strategy_ret_pct"], v["spx_ret_pct"], v["bh_sleeve_ret_pct"],
            v["pct_cash_in_window"]))
print("")
print("=== context: gate variants / no-VIX (strategy totRet) ===")
for mode in ("tsmom", "both"):
    gv = out["gate_variants"].get(mode, {})
    if "strategy_stats" in gv:
        print("  gate=%-6s totRet %+12.1f%%  maxDD %7.2f%%" % (
            mode, gv["strategy_stats"]["total_return_pct"], gv["strategy_stats"]["max_drawdown_pct"]))
if "strategy_stats" in out.get("no_vix_gate", {}):
    nv = out["no_vix_gate"]["strategy_stats"]
    print("  no-VIX-gate totRet %+12.1f%%  maxDD %7.2f%%" % (
        nv["total_return_pct"], nv["max_drawdown_pct"]))
if "strategy_stats" in out.get("upro_cut", {}) or "strategy_stats" in str(out.get("upro_cut", {})):
    uc = out.get("upro_cut", {})
    if "strategy_stats" in uc:
        print("  UPRO/SPY cut totRet %+12.1f%%  maxDD %7.2f%%  vs SPX %+10.1f%%" % (
            uc["strategy_stats"]["total_return_pct"], uc["strategy_stats"]["max_drawdown_pct"],
            uc["spx_stats"]["total_return_pct"]))
print("")
print("wrote reports/_levlong_result.json")
