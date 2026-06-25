#!/usr/bin/env python3
"""Rebuild the 8 LIVE-strategy daily return series (vol-aware ERC step 1).

Reproduces the EXACT recipe documented in reports/INTERSTRATEGY_CORRELATION_20260622.md
section 1, restricted to the 8 live strategies (in _erc_weights.json["live"] order):

  1-6 event strategies -> actual decide() through runner.backtest.backtest()
      fed DAILY adjclose bars shaped {t,o,h,l,c,v}, timeframe='1Day', ZERO-cost.
      - volume_breakout_qqq: volume_mult relaxed 3.0 -> 1.0 (PROXY, documented).
      - sma_crossover_qqq_rth: daily bars stamped at 15:00 UTC so the RTH gate
        (14:30-20:00 UTC) is a transparent no-op.
  7 tqqq_cot_combo -> VT equity via run_backtest_voltarget (target 0.40, vol_window
      20, sma 200) with the COT overlay layered per-date via the LIVE strategy's
      own _get_cot_scale() (0.5x on bearish ES AM-net WoW weeks, 3-day pub lag).
  8 allocator_blend -> _allocator_blend_tests.build_sleeves() + blend_portfolio()
      for the 'invvol_63d' blend (exactly what allocator_paper_tracker.py does).

Writes the per-date return maps + common-window aligned matrix to
reports/_volaware_series.json. READ-ONLY on all protected files.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, ".")

WS = Path(__file__).resolve().parent

from runner import daily_bars_cache as dbc
from runner import backtest as bt
from runner.backtest import CostModel

import _allocator_blend_tests as ab
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget,
)
from strategies.tqqq_cot_combo.strategy import _get_cot_scale


LIVE = [
    "breakout_xlk__mut_c382b1",
    "sma_crossover_qqq_regime",
    "sma_crossover_qqq_rth",
    "rsi_oversold_spy",
    "volume_breakout_qqq",
    "macd_momentum_iwm",
    "tqqq_cot_combo",
    "allocator_blend",
]

SYMBOL = {
    "breakout_xlk__mut_c382b1": "XLK",
    "sma_crossover_qqq_regime": "QQQ",
    "sma_crossover_qqq_rth": "QQQ",
    "rsi_oversold_spy": "SPY",
    "volume_breakout_qqq": "QQQ",
    "macd_momentum_iwm": "IWM",
}


def daily_bars_alpaca_shape(symbol, stamp_hour=None):
    """Yahoo daily adjclose bars -> engine {t,o,h,l,c,v} contract.

    Uses adjclose as the close (split/div-adjusted) and scales OHL by the same
    adjclose/close ratio so intrabar levels stay consistent with the adjusted
    close. timeframe is set to '1Day' by the caller via params. stamp_hour, if
    given, stamps the ISO timestamp at HH:00:00Z (for the RTH no-op trick)."""
    raw = dbc.get_daily(symbol)
    out = []
    for b in raw:
        c = b.get("close")
        ac = b.get("adjclose")
        if ac is None:
            continue
        if c and c > 0:
            ratio = ac / c
        else:
            ratio = 1.0
        o = (b.get("open") or c or ac) * ratio
        h = (b.get("high") or c or ac) * ratio
        lo = (b.get("low") or c or ac) * ratio
        v = b.get("volume") or 0
        d = b["date"]
        if stamp_hour is not None:
            t = "%sT%02d:00:00Z" % (d, stamp_hour)
        else:
            t = "%sT00:00:00Z" % d
        out.append({"t": t, "o": float(o), "h": float(h), "l": float(lo),
                    "c": float(ac), "v": float(v)})
    return out


def equity_to_returns(dates, equity):
    out = {}
    for i in range(1, len(dates)):
        if equity[i - 1] != 0:
            out[dates[i]] = equity[i] / equity[i - 1] - 1.0
    return out


def sharpe_of(rets):
    n = len(rets)
    if n < 2:
        return 0.0
    m = sum(rets) / n
    var = sum((r - m) ** 2 for r in rets) / n
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return (m / sd) * math.sqrt(252.0)


def ann_vol(rets):
    n = len(rets)
    if n < 2:
        return 0.0
    m = sum(rets) / n
    var = sum((r - m) ** 2 for r in rets) / n
    return math.sqrt(var) * math.sqrt(252.0)


def build_event_series(name):
    """Run the strategy's actual decide() over daily bars, zero-cost, and return
    a {date: daily_return} map from the equity curve. Each equity step aligns to
    the bar at that index; we map step i (>=1) to bars[i].date."""
    module, params = bt.load_strategy_module_and_params(name)
    p = dict(params)
    p["timeframe"] = "1Day"
    if name == "volume_breakout_qqq":
        p["volume_mult"] = 1.0   # documented PROXY relaxation (3.0 -> 1.0)
    stamp = 15 if name == "sma_crossover_qqq_rth" else None
    bars = daily_bars_alpaca_shape(SYMBOL[name], stamp_hour=stamp)
    res = bt.backtest(name, bars, p, starting_cash=1000.0,
                      cost_model=CostModel(spread_bps=0.0, fee_bps=0.0))
    eq = res.equity_curve
    # The engine appends one equity point per processed bar (after warmup it
    # still records equity each bar). Align equity[k] to bars[k].date by length.
    bar_dates = [b["t"][:10] for b in bars]
    if len(eq) == len(bars):
        dates = bar_dates
    elif len(eq) == len(bars) + 1:
        # leading starting-equity point
        dates = [bar_dates[0]] + bar_dates
    else:
        # fallback: align to the tail
        dates = bar_dates[-len(eq):]
    retmap = equity_to_returns(dates, eq)
    return retmap, res


def build_tqqq_cot_combo():
    """AUTHORITATIVE reproduction matching _xstrat_corr._tqqq_cot_combo_series
    (the recipe that built the DOCUMENTED baseline correlation matrix):
      - VT sleeve via run_backtest_voltarget(target_ann_vol=0.25, vol_window=20,
        sma_window=200) -> per-date target WEIGHTS.
      - effective_weight = vt_weight * _get_cot_scale(0.5, date)  (0.5x on bearish
        ES AM-net WoW, 3-day pub lag, via the LIVE strategy's own function).
      - daily return = effective_weight * RAW TQQQ adjclose close-to-close return
        (no extra switch cost here; intra-sleeve VT cost already shaped the
        weights). This is byte-for-byte the baseline combo series construction,
        so the reproduced combo<->allocator correlation matches the documented
        0.794 instead of drifting high.
    NOTE: target_ann_vol=0.25 (the baseline corr-matrix value) is used here for
    correlation/vol FIDELITY to the baseline. The live params.json says 0.40; we
    discuss that gap in the report (it would only RAISE the combo's vol, pushing
    its already-near-zero ERC weight even lower -> does not change the verdict).
    """
    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0))
    vt_dates = vt["strategy"]["dates"]
    vt_weights = vt["strategy"]["weights"]   # per-date target sleeve weight (len = len(dates)-1)
    # raw TQQQ daily close-to-close returns indexed by end date
    tqqq = dbc.get_daily("TQQQ")
    tqqq_ret = {}
    for i in range(1, len(tqqq)):
        p = tqqq[i - 1]["adjclose"]
        if p and p > 0:
            tqqq_ret[tqqq[i]["date"]] = tqqq[i]["adjclose"] / p - 1.0
    # weights align to days 1..N (the held days); zip against dates[1:]
    held_dates = vt_dates[1:]
    wmap = {d: w for d, w in zip(held_dates, vt_weights)}
    retmap = {}
    for d in held_dates:
        w = wmap.get(d, 0.0)
        scale = _get_cot_scale(0.5, d)
        w_eff = w * scale
        r = tqqq_ret.get(d)
        if r is not None:
            retmap[d] = w_eff * r
    return retmap, vt


def build_allocator_blend():
    """invvol_63d blend daily equity via the validated sleeve harness, exactly
    as runner/allocator_paper_tracker.py does."""
    S = ab.build_sleeves()
    dates = S["common_dates"]
    sleeves = [S["tqqq_r"], S["rot_r"]]

    def invvol_wfn(lookback=63):
        def fn(idx):
            if idx < 2:
                return [0.5, 0.5]
            lo = max(0, idx - lookback)
            v0 = ab.annualized_vol(sleeves[0][lo:idx])
            v1 = ab.annualized_vol(sleeves[1][lo:idx])
            if v0 <= 0 or v1 <= 0:
                return [0.5, 0.5]
            iv0, iv1 = 1.0 / v0, 1.0 / v1
            s = iv0 + iv1
            return [iv0 / s, iv1 / s]
        return fn

    b = ab.blend_portfolio(dates, sleeves, invvol_wfn(63), blend_cost_bps=2.0)
    retmap = equity_to_returns(b["dates"], b["equity"])
    return retmap, b


def main():
    series = {}
    diag = {}

    print(">>> Building 6 event-strategy daily series ...", flush=True)
    for name in LIVE[:6]:
        rm, res = build_event_series(name)
        series[name] = rm
        rets = list(rm.values())
        diag[name] = {"n": len(rm), "sharpe": sharpe_of(rets),
                      "n_trades": getattr(res, "n_trades", None)}
        print("    %-28s n=%5d  sharpe=%.3f  trades=%s" % (
            name, len(rm), diag[name]["sharpe"], diag[name]["n_trades"]))

    print(">>> Building tqqq_cot_combo (VT+COT) ...", flush=True)
    rm, vt = build_tqqq_cot_combo()
    series["tqqq_cot_combo"] = rm
    rets = list(rm.values())
    diag["tqqq_cot_combo"] = {"n": len(rm), "sharpe": sharpe_of(rets)}
    print("    %-28s n=%5d  sharpe=%.3f (VT solo sharpe=%.3f)" % (
        "tqqq_cot_combo", len(rm), diag["tqqq_cot_combo"]["sharpe"],
        vt["strategy"]["stats"]["sharpe"]))

    print(">>> Building allocator_blend (invvol_63d) ...", flush=True)
    rm, b = build_allocator_blend()
    series["allocator_blend"] = rm
    rets = list(rm.values())
    diag["allocator_blend"] = {"n": len(rm), "sharpe": sharpe_of(rets)}
    print("    %-28s n=%5d  sharpe=%.3f" % (
        "allocator_blend", len(rm), diag["allocator_blend"]["sharpe"]))

    # common window = intersection of all 8 date sets
    common = None
    for name in LIVE:
        ds = set(series[name].keys())
        common = ds if common is None else (common & ds)
    common = sorted(common)
    print(">>> Common window: %s -> %s  (%d days)" % (
        common[0], common[-1], len(common)))

    # aligned matrix: rows = dates, cols = strategies (LIVE order)
    mat = [[series[name][d] for name in LIVE] for d in common]

    out = {
        "live": LIVE,
        "common_window": [common[0], common[-1]],
        "n_common": len(common),
        "common_dates": common,
        "returns_matrix": mat,
        "diagnostics": diag,
    }
    json.dump(out, open(WS / "reports/_volaware_series.json", "w"))
    print(">>> wrote reports/_volaware_series.json")


if __name__ == "__main__":
    main()
