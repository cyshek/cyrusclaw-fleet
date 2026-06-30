import json

STRATS = ["sma_crossover_qqq_regime","sma_crossover_qqq_rth","volume_breakout_qqq",
          "macd_momentum_iwm","tqqq_cot_combo"]
TS = "20260630T053123Z"

rows = []
for s in STRATS:
    d = json.load(open(f"reports/_wf_audit_{s}_{TS}.json"))
    e = d[0] if isinstance(d, list) else d
    rows.append({
        "strategy": e["strategy"],
        "windows": e["n_windows_with_data"],
        "medRet": e["median_return_pct"],
        "pctPos": e["pct_positive"]*100,
        "beatBH": e["pct_beat_bh_spy"]*100,
        "medSharpe": e["median_sharpe"],
        "spyExcessAnn": e["median_spy_excess_ann_return"]*100,
        "medIR": e["median_spy_information_ratio"],
        "worst": e["worst"].get("pct") if isinstance(e["worst"],dict) else e["worst"],
        "best": e["best"].get("pct") if isinstance(e["best"],dict) else e["best"],
        "worstLabel": e["worst"].get("label") if isinstance(e["worst"],dict) else "",
        "fitness": e["fitness_gate"],
    })

print(f"{'strategy':30s} {'win':>4s} {'medRet%':>8s} {'%pos':>5s} {'beatBH':>6s} {'medShrp':>7s} {'spyExc%':>8s} {'medIR':>6s} {'worst%':>7s} {'best%':>7s}  fitness")
for r in rows:
    fit = r["fitness"]
    if isinstance(fit, list):
        fitstr = ("PASS" if fit[0] else "FAIL") + (f" ({fit[1]})" if len(fit) > 1 and not fit[0] else "")
    else:
        fitstr = fit if isinstance(fit,str) else ("PASS" if fit else "FAIL")
    print(f"{r['strategy']:30s} {r['windows']:>4d} {r['medRet']:>8.2f} {r['pctPos']:>4.0f}% {r['beatBH']:>5.0f}% {r['medSharpe']:>7.2f} {r['spyExcessAnn']:>8.2f} {r['medIR']:>6.2f} {r['worst']:>7.2f} {r['best']:>7.2f}  {fitstr}")
