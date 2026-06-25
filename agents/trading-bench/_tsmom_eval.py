"""Full honest evaluation of the multi-asset TSMOM sleeve.

Replicates the bench's honest bar:
  - benchmark vs BUY-HOLD SPY on the SAME PATH (raw return is the mission bar)
  - full-period continuous-span Sharpe (one concatenated daily series, sqrt(252))
  - OOS split: pre-2018 = IS, 2018+ = OOS (reported separately)
  - maxDD, CAGR, corr-to-SPY daily (orthogonality target < 0.3)
  - 2022 + 2020 crisis-window behavior (crisis-alpha claim)
  - robustness: lookback 6/9/12, universe size (knife-edge vs plateau)
  - inv-vol variant for contrast (PRIMARY = equal-weight in-trend)

All assets in a run must have >=12m history at the run's start_date so the
sleeve is fully formed from its first live day (no silent 3-of-4 early period).
"""
import json
import datetime as dt
from typing import List, Dict

import _tsmom_engine as E

OOS_START = "2018-01-01"

# Universes (all legs exist with full 12m history by ~2008-04 except where noted)
UNIV_CORE4 = ["DBC", "GLD", "TLT", "UUP"]                       # commodities/gold/bonds/dollar
UNIV_6 = ["DBC", "GLD", "TLT", "UUP", "IEF", "VNQ"]             # + intermediate bonds + REITs
UNIV_8 = ["DBC", "GLD", "TLT", "UUP", "IEF", "SLV", "USO", "VNQ"]
UNIV_10 = ["DBC", "GLD", "TLT", "UUP", "IEF", "SLV", "USO", "VNQ", "EFA", "EEM"]
# A truly diversified macro basket incl. equities + Nasdaq for the trend engine
UNIV_FULL = ["DBC", "GLD", "TLT", "UUP", "IEF", "SLV", "USO", "VNQ", "EFA", "EEM", "SPY", "QQQ"]

# Common start: UUP inception 2007-03 + 12m warmup => first clean rebalance ~2008-03.
START = "2008-04-01"


def split_idx(dates: List[str], oos_start: str) -> int:
    for i, d in enumerate(dates):
        if d >= oos_start:
            return i
    return len(dates)


def eval_run(symbols, lookback_m=12, weighting="ew", start=START, label=""):
    res = E.run_tsmom(symbols, lookback_m=lookback_m, skip_m=1,
                      weighting=weighting, start_date=start)
    dates = res["dates"]
    net = res["net"]
    spy = E.spy_buyhold_on_path(dates)

    si = split_idx(dates, OOS_START)
    out = {
        "label": label or f"{weighting}_{lookback_m}m_n{len(symbols)}",
        "symbols": symbols,
        "lookback_m": lookback_m,
        "weighting": weighting,
        "n_days": len(net),
        "span": (dates[0], dates[-1]) if dates else (None, None),
        "n_rebal": len(res["weights_hist"]),
        "mean_in_trend": round(sum(res["n_intrend_hist"]) / max(1, len(res["n_intrend_hist"])), 2),
        "mean_turnover": round(sum(res["turnover_events"]) / max(1, len(res["turnover_events"])), 4),
        # FULL PERIOD
        "fp_sharpe": round(E.sharpe_from_returns(net, E.BPY), 4),
        "fp_cagr": round(E.lane_honesty.cagr(net, E.TRADING_DAYS), 3),
        "fp_total_ret": round(E.total_return(net), 4),
        "fp_maxdd": round(E.max_drawdown(net), 4),
        "fp_corr_spy": round(E.corr(net, spy), 4),
        # SPY on same path (full)
        "spy_fp_sharpe": round(E.sharpe_from_returns(spy, E.BPY), 4),
        "spy_fp_cagr": round(E.lane_honesty.cagr(spy, E.TRADING_DAYS), 3),
        "spy_fp_total_ret": round(E.total_return(spy), 4),
        "spy_fp_maxdd": round(E.max_drawdown(spy), 4),
    }
    # IS vs OOS
    is_net, oos_net = net[:si], net[si:]
    is_spy, oos_spy = spy[:si], spy[si:]
    out["is_sharpe"] = round(E.sharpe_from_returns(is_net, E.BPY), 4)
    out["is_cagr"] = round(E.lane_honesty.cagr(is_net, E.TRADING_DAYS), 3)
    out["is_total_ret"] = round(E.total_return(is_net), 4)
    out["oos_sharpe"] = round(E.sharpe_from_returns(oos_net, E.BPY), 4)
    out["oos_cagr"] = round(E.lane_honesty.cagr(oos_net, E.TRADING_DAYS), 3)
    out["oos_total_ret"] = round(E.total_return(oos_net), 4)
    out["oos_maxdd"] = round(E.max_drawdown(oos_net), 4)
    out["oos_corr_spy"] = round(E.corr(oos_net, oos_spy), 4)
    out["spy_oos_sharpe"] = round(E.sharpe_from_returns(oos_spy, E.BPY), 4)
    out["spy_oos_total_ret"] = round(E.total_return(oos_spy), 4)
    out["oos_split_date"] = dates[si] if si < len(dates) else None
    # crisis windows: 2020 COVID (Feb-Apr 2020), 2022 bear (full year)
    def window_ret(rets, ds, lo, hi):
        sub = [rets[k] for k in range(len(ds)) if lo <= ds[k] <= hi]
        return round(E.total_return(sub), 4), len(sub)
    out["c2020_sleeve"] = window_ret(net, dates, "2020-02-19", "2020-04-30")
    out["c2020_spy"] = window_ret(spy, dates, "2020-02-19", "2020-04-30")
    out["c2022_sleeve"] = window_ret(net, dates, "2022-01-01", "2022-12-31")
    out["c2022_spy"] = window_ret(spy, dates, "2022-01-01", "2022-12-31")
    # 2008 GFC (Sep 2008 - Mar 2009) if in span
    out["c2008_sleeve"] = window_ret(net, dates, "2008-09-01", "2009-03-31")
    out["c2008_spy"] = window_ret(spy, dates, "2008-09-01", "2009-03-31")
    return out


def breakeven_bps(symbols, lookback_m=12, weighting="ew", start=START):
    """Breakeven one-way bps: the cost level at which full-period total return
    goes to ~0. Solve by scanning cost up until total return crosses zero."""
    lo, hi = 0.0, 500.0
    # total return is monotone decreasing in cost; bisect
    def tr_at(bps):
        r = E.run_tsmom(symbols, lookback_m=lookback_m, skip_m=1,
                        weighting=weighting, start_date=start, one_way_bps=bps)
        return E.total_return(r["net"])
    if tr_at(lo) <= 0:
        return 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if tr_at(mid) > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 1)


def main():
    results = {}

    # PRIMARY: equal-weight, 12-1, across universe sizes
    print("=== PRIMARY (equal-weight in-trend, 12-1) across universe sizes ===")
    for name, u in [("core4", UNIV_CORE4), ("u6", UNIV_6), ("u8", UNIV_8),
                    ("u10", UNIV_10), ("full12", UNIV_FULL)]:
        r = eval_run(u, 12, "ew", label=f"ew_12m_{name}")
        results[f"ew_12m_{name}"] = r
        print(f"  {name:7s} n={len(u):2d} | fpSharpe={r['fp_sharpe']:.3f} "
              f"fpCAGR={r['fp_cagr']:.2f}% spyCAGR={r['spy_fp_cagr']:.2f}% | "
              f"OOS Sh={r['oos_sharpe']:.3f} | maxDD={r['fp_maxdd']*100:.1f}% "
              f"corrSPY={r['fp_corr_spy']:.3f} | 2022 sleeve={r['c2022_sleeve'][0]*100:+.1f}% "
              f"spy={r['c2022_spy'][0]*100:+.1f}%")

    # LOOKBACK robustness on the u10 universe
    print("\n=== LOOKBACK robustness (u10, equal-weight) ===")
    for lb in [6, 9, 12]:
        r = eval_run(UNIV_10, lb, "ew", label=f"ew_{lb}m_u10")
        results[f"ew_{lb}m_u10"] = r
        print(f"  {lb:2d}m | fpSharpe={r['fp_sharpe']:.3f} fpCAGR={r['fp_cagr']:.2f}% "
              f"OOS Sh={r['oos_sharpe']:.3f} maxDD={r['fp_maxdd']*100:.1f}% "
              f"corrSPY={r['fp_corr_spy']:.3f}")

    # INV-VOL contrast on u10, 12-1
    print("\n=== INV-VOL variant contrast (u10, 12-1) ===")
    r = eval_run(UNIV_10, 12, "invvol", label="invvol_12m_u10")
    results["invvol_12m_u10"] = r
    print(f"  invvol u10 | fpSharpe={r['fp_sharpe']:.3f} fpCAGR={r['fp_cagr']:.2f}% "
          f"OOS Sh={r['oos_sharpe']:.3f} maxDD={r['fp_maxdd']*100:.1f}% "
          f"corrSPY={r['fp_corr_spy']:.3f}")
    rew = results["ew_12m_u10"]
    print(f"  (vs EW u10  | fpSharpe={rew['fp_sharpe']:.3f} fpCAGR={rew['fp_cagr']:.2f}%)")

    # BREAKEVEN bps for the headline config (u10 EW 12-1)
    be = breakeven_bps(UNIV_10, 12, "ew")
    results["ew_12m_u10"]["breakeven_oneway_bps"] = be
    print(f"\n=== BREAKEVEN one-way bps (u10 EW 12-1): {be} bps ===")

    with open("_tsmom_eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nwrote _tsmom_eval_results.json")
    return results


if __name__ == "__main__":
    main()
