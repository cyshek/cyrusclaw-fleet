"""Canary + full diagnostics on the BEST-efficiency config: trailing-DD<-10%
trigger, cash hedge, wh25 (and wh15). This is the config whose tradeoff-breaking
claim must survive the +1-bar lag to be real."""
import sys, json
sys.path.insert(0, ".")
sys.path.insert(0, "reports")
from _crash_sleeve_probe_driver import build_sleeves, stats_from_returns, run_config, slice_equity_stats
from _crash_sleeve_robustness import build_dd_flags

S = build_sleeves()
dates = S["common_dates"]; tqqq_r = S["tqqq_r"]; rot_r = S["rot_r"]; spx_r = S["spx_r"]
spx_curve = stats_from_returns(dates, spx_r)
spx_dates = spx_curve["dates"]; spx_equity = spx_curve["equity"]
hedge_cash = [0.0] * len(dates)

base, bb = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, [False]*len(dates), 0.0, "base")
print("BASELINE: full maxDD %.2f%% OOS maxDD %.2f%% raw %.0f%% OOSsh %.3f fullsh %.3f" % (
    base["full"]["maxdd_pct"], base["oos_2019_today"]["maxdd_pct"], base["full"]["total_return_pct"],
    base["oos_2019_today"]["sharpe"], base["full"]["sharpe"]))

# crash-window DD on baseline equity
for label,(s,e) in [("2018Q4",("2018-10-01","2018-12-31")),("2020covid",("2020-02-01","2020-04-30")),("2022bear",("2022-01-01","2022-12-31"))]:
    st = slice_equity_stats(bb["dates"], bb["equity"], s, e)
    print("   baseline %s maxDD %.2f%% ret %.2f%%" % (label, st.get("max_drawdown_pct",0), st.get("total_return_pct",0)))
print()

results = {}
for thr, wlist in [(-0.10,[0.15,0.25]), (-0.08,[0.25])]:
    for w_h in wlist:
        name = "DD%d_wh%d" % (int(thr*100), int(w_h*100))
        fsb = build_dd_flags(spx_r, thr, extra_lag=0)
        flg = build_dd_flags(spx_r, thr, extra_lag=1)
        sb, sbb = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, fsb, w_h, name+"_sb")
        lg, lgb = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, flg, w_h, name+"_lag1")
        results[name] = (sb, lg, sbb)
        print("=== %s ===" % name)
        print("  same-bar: full maxDD %.2f%% OOS maxDD %.2f%% raw %.0f%% OOSsh %.3f fullsh %.3f" % (
            sb["full"]["maxdd_pct"], sb["oos_2019_today"]["maxdd_pct"], sb["full"]["total_return_pct"],
            sb["oos_2019_today"]["sharpe"], sb["full"]["sharpe"]))
        print("  lag+1   : full maxDD %.2f%% OOS maxDD %.2f%% raw %.0f%% OOSsh %.3f fullsh %.3f" % (
            lg["full"]["maxdd_pct"], lg["oos_2019_today"]["maxdd_pct"], lg["full"]["total_return_pct"],
            lg["oos_2019_today"]["sharpe"], lg["full"]["sharpe"]))
        # crash windows same-bar
        for label,(s,e) in [("2018Q4",("2018-10-01","2018-12-31")),("2020covid",("2020-02-01","2020-04-30")),("2022bear",("2022-01-01","2022-12-31"))]:
            st = slice_equity_stats(sbb["dates"], sbb["equity"], s, e)
            print("     %s maxDD %.2f%% ret %.2f%%" % (label, st.get("max_drawdown_pct",0), st.get("total_return_pct",0)))
        ddcut_sb = sb["oos_2019_today"]["maxdd_pct"] - base["oos_2019_today"]["maxdd_pct"]
        ddcut_lg = lg["oos_2019_today"]["maxdd_pct"] - base["oos_2019_today"]["maxdd_pct"]
        verdict = "SURVIVES" if ddcut_lg >= ddcut_sb - 0.4 else "WEAKENS"
        print("  CANARY: DD-cut same-bar %+.2fpp -> lag+1 %+.2fpp  => %s" % (ddcut_sb, ddcut_lg, verdict))
        print()

json.dump({k:{"same_bar":{"full_maxdd":v[0]["full"]["maxdd_pct"],"oos_maxdd":v[0]["oos_2019_today"]["maxdd_pct"],"raw":v[0]["full"]["total_return_pct"],"oos_sharpe":v[0]["oos_2019_today"]["sharpe"]},
               "lag1":{"full_maxdd":v[1]["full"]["maxdd_pct"],"oos_maxdd":v[1]["oos_2019_today"]["maxdd_pct"],"raw":v[1]["full"]["total_return_pct"],"oos_sharpe":v[1]["oos_2019_today"]["sharpe"]}} for k,v in results.items()},
          open("reports/_crash_sleeve_ddtrigger_canary.json","w"), indent=2, default=str)
print("wrote reports/_crash_sleeve_ddtrigger_canary.json")
