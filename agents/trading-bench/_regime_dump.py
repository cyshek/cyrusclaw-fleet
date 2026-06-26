import json

r = json.load(open("reports/_regime_allocator_result.json"))
m = r["meta"]
print("META KEYS:", list(m.keys()))
print("WINDOW", m["common_window"], "ndays", m["n_days"], "month_opens", m["n_month_opens"])
for k in ("nfci_signal_active_month_opens", "nfci_first_signalled_rebal", "nfci_pit_coverage", "nfci_first_signalled"):
    if k in m:
        print(" ", k, "=", m[k])
print("TQQQ solo", {k: round(v, 3) for k, v in m["tqqq_solo_stats"].items()})
print("ROT  solo", {k: round(v, 3) for k, v in m["rot_solo_stats"].items()})
print("SPX  solo", {k: round(v, 3) for k, v in m["spx_solo_stats"].items()})
st = r["static_invvol_63d"]
print("STATIC full", {k: round(v, 3) for k, v in st["full"].items()}, "avg_w_tqqq", round(st["avg_w_tqqq"], 3))
print("STATIC IS", st["is_2010_2018"])
print("STATIC OOS", st["oos_2019_today"])
print("SPX floor full", {k: round(v, 3) for k, v in r["spx_floor"]["full"].items()})
print("SPX floor OOS", r["spx_floor"]["oos_2019_today"])
print("VERDICT_SCAN", r["verdict_scan"])
print("CANARY clean", r["canary"]["all_used_releases_leq_rebal"],
      "cov", r["canary"].get("n_month_opens_with_release_date"), "/",
      r["canary"].get("n_month_opens_with_signal"))
# full grid dump rounded
print("\n== GRID (nfci single) ==")
for nm, v in r["regime_grid"].items():
    f = v["full"]; o = v["oos_2019_today"]; i = v["is_2010_2018"]
    print("%-20s full tot %.0f cagr %.1f sh %.3f dd %.1f | IS tot %.0f sh %.3f | OOS tot %.0f sh %.3f | beat full=%s oos=%s" % (
        nm, f["total_return_pct"], f["cagr_pct"], f["sharpe"], f["maxdd_pct"],
        i["total_return_pct"], i["sharpe"], o["total_return_pct"], o["sharpe"],
        v["beats_static_full_totret"], v["beats_static_oos_totret"]))
print("== GRID (nfci_baa) ==")
for nm, v in r["regime_grid_nfci_baa"].items():
    f = v["full"]; o = v["oos_2019_today"]; i = v["is_2010_2018"]
    print("%-20s full tot %.0f cagr %.1f sh %.3f dd %.1f | IS tot %.0f sh %.3f | OOS tot %.0f sh %.3f | beat full=%s oos=%s" % (
        nm, f["total_return_pct"], f["cagr_pct"], f["sharpe"], f["maxdd_pct"],
        i["total_return_pct"], i["sharpe"], o["total_return_pct"], o["sharpe"],
        v["beats_static_full_totret"], v["beats_static_oos_totret"]))
