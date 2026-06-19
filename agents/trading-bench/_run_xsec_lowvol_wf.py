"""Walk-forward + full-period driver for xsec_lowvol_c3783c candidate.

The candidate lives under strategies_candidates/, so load_xsec_strategy
can't reach it; we import via importlib by path and pass
decide_xsec_fn directly into walk_forward_xsec.

The realized-vol signal needs lookback_bars (60 by default) of history
before it can fire. NAMED_WINDOWS are 60-90 calendar days; we extend
with WARMUP_DAYS = 180 calendar days so the strategy has roughly
~120 trading bars warm-up + the labeled window. Mirrors the spec from
the task brief.

Two configs evaluated: regime_filter=False (raw low-vol) and
regime_filter=True (regime overlay on SPY 50d SMA).

Additionally runs a K sensitivity sweep (K=2/3/5) and a lookback
sensitivity (N=21 vs N=60) for the noreg variant only — needed for
the report's sensitivity sections.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner import bars_cache  # noqa: E402
from runner.backtest import CostModel  # noqa: E402
from runner.backtest_xsec import backtest_xsec  # noqa: E402
from runner.walk_forward_xsec import (  # noqa: E402
    walk_forward_xsec,
    passes_fitness_gate_xsec,
    format_xsec_md,
)

WARMUP_DAYS = 180
CANDIDATE = "xsec_lowvol_c3783c"


def load(name):
    d = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(f"cand_{name}", d / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((d / "params.json").read_text())
    return mod, params


def full_period_xsec_backtest(name, basket, params, decide_fn, days=1800,
                               end_dt=None, cost_model=None):
    if end_dt is None:
        now = datetime.now(timezone.utc)
        end_dt = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    if cost_model is None:
        cost_model = CostModel.alpaca_stocks()
    timeframe = str(params.get("timeframe", "1Day"))
    bars_by_sym = {}
    for sym in basket:
        b = bars_cache.get_bars(sym, timeframe, days=days, end_dt=end_dt)
        if b and len(b) >= 10:
            bars_by_sym[sym] = b
    bt = backtest_xsec(name, bars_by_sym, params,
                       decide_xsec_fn=decide_fn,
                       default_cost_model=cost_model)
    return bt, bars_by_sym


def run_config(label_suffix, mod, params, *, use_regime, bottom_k=None,
               vol_lookback_bars=None, do_full_period=True):
    p = dict(params)
    p["use_regime_filter"] = use_regime
    if bottom_k is not None:
        p["bottom_k"] = bottom_k
    if vol_lookback_bars is not None:
        p["vol_lookback_bars"] = vol_lookback_bars
    name_tagged = f"{CANDIDATE}{label_suffix}"
    print(f"\n== {name_tagged} (regime={use_regime}, "
          f"K={p['bottom_k']}, N={p['vol_lookback_bars']}, "
          f"warmup +{WARMUP_DAYS}d) ==", file=sys.stderr)
    basket = list(p.get("basket") or [])
    agg = walk_forward_xsec(
        name_tagged, basket, params=p, decide_xsec_fn=mod.decide_xsec,
        warmup_days=WARMUP_DAYS)
    fit_passed, fit_reason = passes_fitness_gate_xsec(agg)

    fp_payload = None
    if do_full_period:
        fp_bt, fp_bars = full_period_xsec_backtest(
            name_tagged, basket, p, mod.decide_xsec, days=1800)
        first_ts = ""
        last_ts = ""
        if fp_bars:
            all_t = []
            for s in fp_bars.values():
                if s:
                    all_t.append(s[0].get("t", ""))
                    all_t.append(s[-1].get("t", ""))
            if all_t:
                first_ts = min(x for x in all_t if x)
                last_ts = max(x for x in all_t if x)
        fp_per_sym = {sym: {"buys": ps.n_buys, "closes": ps.n_closes,
                             "pnl": ps.realized_pnl_usd, "final_qty": ps.final_qty}
                       for sym, ps in fp_bt.per_symbol.items()}
        fp_payload = {
            "n_ticks": fp_bt.n_ticks,
            "n_trades": fp_bt.n_trades,
            "n_buys": fp_bt.n_buys,
            "n_closes": fp_bt.n_closes,
            "n_basket_clamps": fp_bt.n_basket_clamps,
            "total_return_pct": fp_bt.total_return_pct * 100,
            "sharpe": fp_bt.sharpe,
            "max_dd_pct": fp_bt.max_drawdown_pct * 100,
            "total_costs_usd": fp_bt.total_costs_usd,
            "starting_equity": fp_bt.starting_equity,
            "final_equity": fp_bt.final_equity,
            "first_bar_t": first_ts,
            "last_bar_t": last_ts,
            "per_symbol": fp_per_sym,
        }

    return {
        "name": name_tagged,
        "use_regime": use_regime,
        "bottom_k": p["bottom_k"],
        "vol_lookback_bars": p["vol_lookback_bars"],
        "agg": agg,
        "fitness_pass": fit_passed,
        "fitness_reason": fit_reason,
        "full_period": fp_payload,
    }


def floor_sensitivity(agg, floors=(20.0, 15.0, 10.0)):
    """Re-score Bar A bullet #1 under hypothetical alternative
    bars-in-position floors. Cap on (b) usage stays at 1 (matches
    the current rule).
    """
    out = {}
    for floor in floors:
        b_used = 0
        passes = 0
        per_window = []
        for w in agg.windows:
            bt = w.backtest
            ret = bt.total_return_pct
            if ret > 0:
                passes += 1
                per_window.append((w.label, "a"))
                continue
            b_eligible = (ret >= w.bh_basket_return_pct - 1e-12
                          and w.bars_in_position_pct >= floor)
            if b_eligible and b_used < 1:
                passes += 1
                b_used += 1
                per_window.append((w.label, "b"))
            else:
                per_window.append((w.label, "FAIL"))
        out[floor] = {
            "passes": passes,
            "n_windows": len(agg.windows),
            "all_pass": passes == len(agg.windows),
            "b_used": b_used,
            "per_window": per_window,
        }
    return out


def _agg_summary(r):
    agg = r["agg"]
    return {
        "name": r["name"],
        "use_regime": r["use_regime"],
        "bottom_k": r["bottom_k"],
        "vol_lookback_bars": r["vol_lookback_bars"],
        "fitness_pass": r["fitness_pass"],
        "fitness_reason": r["fitness_reason"],
        "n_windows_with_data": agg.n_windows_with_data,
        "median_return_pct": agg.median_return_pct,
        "pct_positive": agg.pct_positive,
        "pct_beat_bh_basket": agg.pct_beat_bh_basket,
        "median_sharpe": agg.median_sharpe,
        "median_return_bull": agg.median_return_bull,
        "median_return_chop": agg.median_return_chop,
        "median_return_bear": agg.median_return_bear,
        "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
        "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
        "total_trades": agg.total_trades,
        "bar_a_bullet1_pass": agg.bar_a_bullet1_pass,
        "bar_a_bullet1_reason": agg.bar_a_bullet1_reason,
        "bar_a_b_used_count": agg.bar_a_b_used_count,
        "windows": [w.to_row() for w in agg.windows],
        "floor_sensitivity": floor_sensitivity(agg),
        "full_period": r.get("full_period"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="/tmp/xsec_lowvol_wf.json")
    ap.add_argument("--md", default="/tmp/xsec_lowvol_wf.md")
    args = ap.parse_args()
    mod, params = load(CANDIDATE)

    results = []
    # Primary configs: K=3, N=60, both regime variants — full period.
    results.append(run_config("__noreg",   mod, params, use_regime=False))
    results.append(run_config("__regime",  mod, params, use_regime=True))

    # Sensitivity: K=2 and K=5 (N=60, noreg) — walk-forward only, no full period.
    results.append(run_config("__noreg_k2", mod, params, use_regime=False,
                              bottom_k=2, do_full_period=False))
    results.append(run_config("__noreg_k5", mod, params, use_regime=False,
                              bottom_k=5, do_full_period=False))
    # Sensitivity: N=21 (K=3, noreg) — walk-forward only.
    results.append(run_config("__noreg_n21", mod, params, use_regime=False,
                              vol_lookback_bars=21, do_full_period=False))

    out = [_agg_summary(r) for r in results]
    Path(args.json).write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.json}", file=sys.stderr)

    chunks = [f"# Walk-Forward: {CANDIDATE}", ""]
    for r in results:
        chunks.append(f"## {r['name']} (regime={r['use_regime']}, "
                      f"K={r['bottom_k']}, N={r['vol_lookback_bars']})")
        chunks.append("")
        chunks.append(format_xsec_md(r["agg"]))
        fp = r.get("full_period")
        if fp:
            chunks.append(f"**Full-period:** {fp['first_bar_t']} → {fp['last_bar_t']} · "
                          f"ticks={fp['n_ticks']} · trades={fp['n_trades']} "
                          f"(buys {fp['n_buys']} / closes {fp['n_closes']}) · "
                          f"clamps={fp['n_basket_clamps']} · "
                          f"return {fp['total_return_pct']:+.2f}% · "
                          f"Sharpe {fp['sharpe']:.2f} · "
                          f"maxDD {fp['max_dd_pct']:.2f}% · "
                          f"costs ${fp['total_costs_usd']:.2f}")
        chunks.append("")
    Path(args.md).write_text("\n\n".join(chunks))
    print(f"wrote {args.md}", file=sys.stderr)

    for r in results:
        agg = r["agg"]
        print(f"  {r['name']}: K={r['bottom_k']} N={r['vol_lookback_bars']} "
              f"regime={r['use_regime']}: "
              f"windows={agg.n_windows_with_data}/{agg.n_windows} "
              f"medRet={agg.median_return_pct:+.2f}% "
              f"pos={agg.pct_positive*100:.0f}% "
              f"beatBH={agg.pct_beat_bh_basket*100:.0f}% "
              f"medSharpe={agg.median_sharpe:.2f} "
              f"trades={agg.total_trades} "
              f"BarA#1={'PASS' if agg.bar_a_bullet1_pass else 'FAIL'} "
              f"FIT={'PASS' if r['fitness_pass'] else 'FAIL'}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
