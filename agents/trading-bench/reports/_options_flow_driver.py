#!/usr/bin/env python3
import requests, numpy as np, json
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
COST_BPS = 5

def fetch_vix():
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = {}
    for line in r.text.strip().splitlines()[1:]:
        parts = line.strip().split(",")
        if len(parts) < 5: continue
        try:
            dt = datetime.strptime(parts[0].strip(), "%m/%d/%Y")
            data[dt.strftime("%Y-%m-%d")] = float(parts[4])
        except: pass
    print("VIX loaded:", len(data), "rows,", min(data.keys()), "to", max(data.keys()))
    return data

def fetch_spy():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=946684800&period2=9999999999&interval=1d&events=div,split"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    data = {}
    for ts, ac in zip(result["timestamp"], result["indicators"]["adjclose"][0]["adjclose"]):
        if ac is not None:
            data[datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")] = float(ac)
    print("SPY loaded:", len(data), "rows,", min(data.keys()), "to", max(data.keys()))
    return data

def align_data(vix_dict, spy_dict, start_date, end_date):
    dates = sorted(d for d in set(vix_dict) & set(spy_dict) if start_date <= d <= end_date)
    return dates, np.array([spy_dict[d] for d in dates]), np.array([vix_dict[d] for d in dates])

def spy_returns(spy):
    ret = np.full(len(spy), np.nan)
    ret[1:] = np.log(spy[1:] / spy[:-1])
    return ret

def run_signal(spy, sig):
    n = len(spy)
    ret = spy_returns(spy)
    pos = np.zeros(n)
    for i in range(1, n-1):
        pos[i+1] = sig[i]
    transitions = np.abs(np.diff(np.concatenate([[0], pos])))
    strat_ret = pos * ret - transitions * COST_BPS/10000
    strat_ret = np.where(np.isnan(strat_ret), 0, strat_ret)
    return np.exp(np.cumsum(strat_ret)), strat_ret

def calc_stats(eq, ret, dates, label):
    total_return = (eq[-1]/eq[0] - 1) * 100
    clean = ret[~np.isnan(ret)]
    sharpe = (np.mean(clean)/np.std(clean, ddof=1))*np.sqrt(252) if len(clean)>0 and np.std(clean)>0 else 0.0
    max_dd = float(np.min((eq - np.maximum.accumulate(eq))/np.maximum.accumulate(eq))) * 100
    pct_mkt = np.sum(ret!=0)/len(ret)*100
    return {"label": label, "total_return_pct": round(float(total_return),2),
            "annualized_sharpe": round(float(sharpe),3), "max_drawdown_pct": round(float(max_dd),2),
            "pct_in_market": round(float(pct_mkt),2), "start_date": dates[0], "end_date": dates[-1]}

def bah_stats_fn(spy, dates):
    ret = spy_returns(spy)
    eq = np.exp(np.nancumsum(np.where(np.isnan(ret), 0, ret)))
    return calc_stats(eq, ret, dates, "Buy-and-Hold SPY")

def build_zscore_sig(vix, window=21, entry_z=1.0, exit_z=0.0):
    n = len(vix)
    z = np.full(n, np.nan)
    for i in range(window, n):
        w = vix[i-window:i]
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0: z[i] = (vix[i]-mu)/sigma
    sig = np.zeros(n)
    in_pos = False
    for i in range(n):
        if not np.isnan(z[i]) and z[i] > entry_z:
            in_pos = True
        elif not np.isnan(z[i]) and z[i] < exit_z and in_pos:
            in_pos = False
        sig[i] = 1 if in_pos else 0
    return sig

def build_threshold_sig(vix, entry=25.0, exit_low=20.0):
    n = len(vix)
    sig = np.zeros(n)
    in_pos = False
    for i in range(n):
        if vix[i] > entry:
            in_pos = True
        elif vix[i] < exit_low and in_pos:
            in_pos = False
        sig[i] = 1 if in_pos else 0
    return sig

def build_ema_zscore_sig(vix, ema_p=5, window=21, entry_z=1.0):
    alpha = 2/(ema_p+1)
    ema = np.full(len(vix), vix[0])
    for i in range(1, len(vix)):
        ema[i] = alpha*vix[i] + (1-alpha)*ema[i-1]
    return build_zscore_sig(ema, window, entry_z)

def run_period(vix_dict, spy_dict, start, end, lbl):
    dates, spy, vix = align_data(vix_dict, spy_dict, start, end)
    bah = bah_stats_fn(spy, dates)
    signals = [build_zscore_sig(vix), build_threshold_sig(vix),
               build_ema_zscore_sig(vix), (vix>12).astype(float)]
    labels = ["VIX 21d-ZScore contrarian", "VIX Threshold >25 contrarian",
              "VIX 5d-EMA ZScore contrarian", "VIX Complacency Filter (>12 long)"]
    results = []
    for sig, label in zip(signals, labels):
        eq, ret = run_signal(spy, sig)
        results.append(calc_stats(eq, ret, dates, label))
    vix_stats = {"min": float(np.min(vix)), "max": float(np.max(vix)),
                 "mean": float(np.mean(vix)), "median": float(np.median(vix)),
                 "pct_above_25": float(np.mean(vix>25)*100),
                 "pct_above_30": float(np.mean(vix>30)*100),
                 "pct_below_12": float(np.mean(vix<12)*100)}
    print()
    print("[" + lbl + "]")
    for s in [bah] + results:
        print("  {:42s} ret={:>8.2f}%  sharpe={:>6.3f}  maxdd={:>7.2f}%  mkt={:>5.1f}%".format(
              s["label"], s["total_return_pct"], s["annualized_sharpe"],
              s["max_drawdown_pct"], s["pct_in_market"]))
    return {"bah": bah, "all": results, "vix_stats": vix_stats, "dates": dates}

def main():
    print("="*65)
    print("OPTIONS FLOW SIGNAL RESEARCH - VIX PROXY BACKTEST")
    print("="*65)
    print("NOTE: CBOE PC CSV paths returned HTTP 403. Using VIX proxy.")
    vix_dict = fetch_vix()
    spy_dict = fetch_spy()
    full = run_period(vix_dict, spy_dict, "2000-01-01", "2024-12-31", "FULL 2000-2024")
    train = run_period(vix_dict, spy_dict, "2000-01-01", "2015-12-31", "TRAIN 2000-2015")
    oos = run_period(vix_dict, spy_dict, "2016-01-01", "2024-12-31", "OOS 2016-2024")
    p22 = run_period(vix_dict, spy_dict, "2022-01-01", "2024-12-31", "POST-2022 0DTE era")
    best_full = max(full["all"], key=lambda x: x["annualized_sharpe"])
    best_oos = max(oos["all"], key=lambda x: x["annualized_sharpe"])
    oos_bah = oos["bah"]
    ratio = best_oos["annualized_sharpe"] / oos_bah["annualized_sharpe"] if oos_bah["annualized_sharpe"]>0 else 0
    verdict = "PROMISING" if ratio>1.1 else ("MARGINAL" if ratio>0.85 else "DEAD")
    print()
    print("VERDICT:", verdict, "| OOS ratio:", round(ratio,3))
    output = {
        "status": "ok", "verdict": verdict,
        "data_source": "VIX proxy (CBOE P/C CSV 403; VIX fallback per spec)",
        "full_period_sharpe": best_full["annualized_sharpe"],
        "full_period_return_pct": best_full["total_return_pct"],
        "oos_sharpe": best_oos["annualized_sharpe"],
        "oos_return_pct": best_oos["total_return_pct"],
        "bah_return_pct": full["bah"]["total_return_pct"],
        "bah_sharpe": full["bah"]["annualized_sharpe"],
        "bah_oos_return_pct": oos_bah["total_return_pct"],
        "bah_oos_sharpe": oos_bah["annualized_sharpe"],
        "beats_bah": best_full["total_return_pct"] > full["bah"]["total_return_pct"],
        "beats_bah_oos_sharpe": best_oos["annualized_sharpe"] > oos_bah["annualized_sharpe"],
        "data_start_date": full["dates"][0],
        "key_finding": "VIX-proxy contrarian OOS Sharpe {:.3f} vs BaH {:.3f}; post-2022 {:.3f} vs {:.3f}".format(
            best_oos["annualized_sharpe"], oos_bah["annualized_sharpe"],
            p22["all"][0]["annualized_sharpe"], p22["bah"]["annualized_sharpe"]),
        "report": "reports/OPTIONS_FLOW_RESEARCH_20260614.md",
        "all_results": {
            "full_2000_2024": {s["label"]: {"return_pct": s["total_return_pct"], "sharpe": s["annualized_sharpe"],
                               "max_dd_pct": s["max_drawdown_pct"], "pct_in_market": s["pct_in_market"]}
                               for s in [full["bah"]]+full["all"]},
            "train_2000_2015": {s["label"]: {"return_pct": s["total_return_pct"], "sharpe": s["annualized_sharpe"]}
                                for s in [train["bah"]]+train["all"]},
            "oos_2016_2024": {s["label"]: {"return_pct": s["total_return_pct"], "sharpe": s["annualized_sharpe"],
                               "max_dd_pct": s["max_drawdown_pct"], "pct_in_market": s["pct_in_market"]}
                               for s in [oos["bah"]]+oos["all"]},
            "post_2022": {s["label"]: {"return_pct": s["total_return_pct"], "sharpe": s["annualized_sharpe"],
                          "max_dd_pct": s["max_drawdown_pct"]}
                          for s in [p22["bah"]]+p22["all"]},
        },
        "vix_stats_full": full["vix_stats"],
        "vix_stats_post22": p22["vix_stats"],
    }
    with open("/tmp/options_flow_result.json", "w") as f: json.dump(output, f, indent=2)
    with open("/tmp/options_flow_results_full.json", "w") as f: json.dump(output, f, indent=2)
    print("Results written to /tmp/options_flow_result.json")
    return output

if __name__ == "__main__":
    result = main()
