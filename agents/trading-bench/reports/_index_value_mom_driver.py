"""DRIVER: index-level TS-value vs momentum-book correlation probe.

Builds:
  MOM book   = 12-1 TSMOM on (QQQ,SPY), vol-target 15%, monthly, +1d lag, 2bps.
  VALUE legs (index-level TS, lookahead-safe z-scores, cheap->long):
    1) EQUITY div-yield value: SPY trailing 12m dividend yield (derived from
       Yahoo adjclose-vs-close), z-scored vs own 5yr history. High yield=cheap.
       Traded asset = SPY. [genuine price-based equity value, free]
    2) EQUITY ERP proxy: (SPY trailing div yield) - real 10y yield (DFII10),
       z-scored. High ERP=equities cheap vs bonds. Traded = SPY. [proxy, labeled]
    3) BOND real-yield value: DFII10 real 10y yield z-score. High real yield=
       bonds cheap. Traded = IEF (7-10y Tsy). [genuine bond value, free]
    4) COMMODITY value: DBC price / its own 5yr trailing avg, z-scored (low
       ratio=cheap). Traded = DBC. [genuine commodity value, free]

DISCRIMINATION TEST: for each value leg, corr(value_ret, mom_ret) vs
corr(-mom_ret, mom_ret)=-1.0. A value leg that is NOT inverse-momentum must
have corr-to-mom materially > -1 (imperfect) and its own non-negative
standalone return.
"""
from __future__ import annotations
import json
import math
import datetime as dt
from typing import List, Optional, Dict

import sys
sys.path.insert(0, ".")
sys.path.insert(0, "reports")

import _index_value_mom_probe as P
from runner import daily_bars_cache as dbc

OUT_JSON = "reports/_index_value_mom_probe_result.json"


def trailing_div_yield(symbol: str, dates: List[str], win_d: int = 252) -> List[Optional[float]]:
    """Derive trailing 12m dividend yield from Yahoo close vs adjclose.

    adjclose is total-return (price+divs reinvested); close is price-only.
    The ratio R_t = adjclose_t/close_t grows with cumulative reinvested divs.
    Trailing 12m dividend return approx = (R_t / R_{t-252}) - 1 (the extra
    total-return over price-return contributed by dividends in the window).
    This is a clean, lookahead-safe trailing realized dividend yield."""
    bars = dbc.get_daily(symbol)
    by_date = {b["date"]: b for b in bars}
    # build ratio series on the master calendar (ffill <= D)
    ratio: List[Optional[float]] = []
    last = None
    bd_sorted = [b["date"] for b in bars]
    j = 0
    n = len(bars)
    for d in dates:
        while j < n and bars[j]["date"] <= d:
            c = bars[j]["close"]; ac = bars[j]["adjclose"]
            if c and ac and c > 0:
                last = ac / c
            j += 1
        ratio.append(last)
    out: List[Optional[float]] = []
    for i in range(len(dates)):
        if i - win_d < 0 or ratio[i] is None or ratio[i - win_d] is None or ratio[i - win_d] <= 0:
            out.append(None)
        else:
            out.append(ratio[i] / ratio[i - win_d] - 1.0)
    return out


def price_over_trailing_avg(symbol: str, dates: List[str], win_d: int = 252 * 5) -> List[Optional[float]]:
    """asset adjclose / its own trailing `win_d`-day average. <1 = cheap.
    Lookahead-safe (mean uses only <= D)."""
    px = P.adjclose_on(symbol, dates)
    out: List[Optional[float]] = []
    for i in range(len(dates)):
        lo = i - win_d + 1
        if lo < 0 or px[i] is None:
            out.append(None); continue
        vals = [px[k] for k in range(lo, i + 1) if px[k] is not None]
        if len(vals) < win_d // 2:
            out.append(None); continue
        avg = sum(vals) / len(vals)
        out.append(px[i] / avg if avg > 0 else None)
    return out


def subtract_series(a: List[Optional[float]], b: List[Optional[float]]) -> List[Optional[float]]:
    out = []
    for x, y in zip(a, b):
        out.append((x - y) if (x is not None and y is not None) else None)
    return out


def discrimination(value_ret_dates, value_ret, mom_dates, mom_ret, label) -> Dict:
    """The crux test. Align value & mom; compute corr(value,mom),
    corr(-mom,mom)=-1 reference, and corr(value,-mom). Also rolling corr range."""
    va, mo, dd = P.align(value_ret_dates, value_ret, mom_dates, mom_ret)
    neg_mo = [-x for x in mo]
    c_vm = P.corr(va, mo)
    c_v_negm = P.corr(va, neg_mo)
    c_negm_m = P.corr(neg_mo, mo)  # == -1.0 sanity
    roll = P.rolling_corr(va, mo, dd, win_d=504)
    # how far is value from being exactly -mom? distance in corr space.
    # if value were k*(-mom)+noise, corr(value,mom) -> -1. The "distinctness"
    # margin = c_vm - (-1) = c_vm + 1. Larger margin = more distinct.
    return {
        "label": label,
        "n_overlap": len(dd),
        "span": [dd[0], dd[-1]] if dd else [None, None],
        "corr_value_to_mom": round(c_vm, 4),
        "corr_value_to_negmom": round(c_v_negm, 4),
        "corr_negmom_to_mom_sanity": round(c_negm_m, 4),
        "distinctness_margin_vs_shortmom": round(c_vm + 1.0, 4),
        "rolling_corr_min": round(min(roll), 4) if roll else None,
        "rolling_corr_max": round(max(roll), 4) if roll else None,
        "rolling_corr_mean": round(sum(roll) / len(roll), 4) if roll else None,
        "n_rolling_windows": len(roll),
    }


def main():
    print("Building master calendar (SPY)...")
    dates = P.build_calendar("SPY")
    print(f"  calendar: {dates[0]}..{dates[-1]} n={len(dates)}")

    # ---- MOMENTUM BOOK ----
    print("Building momentum book (12-1 TSMOM QQQ+SPY, vt15%, monthly, +1d, 2bps)...")
    mom = P.tsmom_book_returns(dates, symbols=("QQQ", "SPY"), lookback_m=12,
                               skip_m=1, vol_target=0.15, lag_days=1,
                               start=P.SAMPLE_START)
    mom_stats = P.stats(mom["net"], mom["dates"], "MOM_BOOK_12_1_QQQ_SPY_vt15")
    print(f"  MOM: fpSharpe={mom_stats['fp_sharpe']} fpCAGR={mom_stats['fp_cagr']}% "
          f"OOS Sh={mom_stats['oos_sharpe']} span={mom_stats['span']}")

    results = {"momentum_book": mom_stats, "value_legs": {}, "discrimination": {},
               "canary": {}, "meta": {
                   "one_way_bps": P.ONE_WAY_BPS, "vol_target": 0.15,
                   "oos_start": P.OOS_START, "sample_start": P.SAMPLE_START,
                   "bpy": P.BPY,
                   "generated_utc": dt.datetime.utcnow().isoformat() + "Z"}}

    # ---- VALUE LEVELS ----
    print("Building value levels...")
    spy_dy = trailing_div_yield("SPY", dates, win_d=252)
    dfii10 = P.fred_on_calendar("DFII10", dates)            # real 10y yield (%)
    erp_proxy = subtract_series([(x * 100 if x is not None else None) for x in spy_dy], dfii10)
    dbc_ratio = price_over_trailing_avg("DBC", dates, win_d=252 * 5)
    gld_ratio = price_over_trailing_avg("GLD", dates, win_d=252 * 5)

    # value leg specs: (key, asset, value_level, cheap_is_high, z_win_d, long_flat_only)
    legs = [
        ("equity_divyield_SPY", "SPY", spy_dy, True, 252 * 5, False),
        ("equity_ERPproxy_SPY", "SPY", erp_proxy, True, 252 * 5, False),
        ("bond_realyield_IEF",  "IEF", dfii10, True, 252 * 5, False),
        ("commodity_DBC_5yr",   "DBC", dbc_ratio, False, 252 * 5, False),  # low ratio=cheap
        ("commodity_GLD_5yr",   "GLD", gld_ratio, False, 252 * 5, False),
    ]

    for key, asset, lvl, cheap_hi, zwin, lfo in legs:
        print(f"  value leg: {key} (asset={asset}, cheap_is_high={cheap_hi}, zwin={zwin}d)")
        v = P.value_signal_returns(dates, asset, lvl, cheap_is_high=cheap_hi,
                                   z_win_d=zwin, vol_target=0.15, lag_days=1,
                                   start=P.SAMPLE_START, long_flat_only=lfo,
                                   rebal="month")
        st = P.stats(v["net"], v["dates"], key)
        results["value_legs"][key] = st
        disc = discrimination(v["dates"], v["net"], mom["dates"], mom["net"], key)
        results["discrimination"][key] = disc
        print(f"      standalone: fpSharpe={st['fp_sharpe']} fpCAGR={st['fp_cagr']}% "
              f"OOS Sh={st['oos_sharpe']} | corr_to_mom={disc['corr_value_to_mom']} "
              f"(margin vs shortmom={disc['distinctness_margin_vs_shortmom']}) "
              f"rollcorr[{disc['rolling_corr_min']},{disc['rolling_corr_max']}]")
        # stash returns for blend sketch (only the most promising)
        v["_stats"] = st
        results["value_legs"][key]["_dates_first_last"] = [v["dates"][0], v["dates"][-1]] if v["dates"] else [None, None]
        # keep raw on object for later
        legs_dict = results.setdefault("_raw_returns", {})
        # don't dump full arrays to JSON (huge) -- keep in-memory only via closure below

    # ---- DISCRIMINATION CANARY: -1x mom mirror should look like short-mom ----
    neg_mom = {"dates": mom["dates"], "net": [-x for x in mom["net"]]}
    disc_neg = discrimination(neg_mom["dates"], neg_mom["net"], mom["dates"], mom["net"],
                              "NEGATIVE_MOM_MIRROR(reference)")
    results["discrimination"]["_NEGATIVE_MOM_REFERENCE"] = disc_neg
    print(f"  REFERENCE (-1x mom): corr_to_mom={disc_neg['corr_value_to_mom']} "
          f"(should be ~ -1.0)  margin={disc_neg['distinctness_margin_vs_shortmom']}")

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print("wrote " + OUT_JSON)
    return results


if __name__ == "__main__":
    main()
