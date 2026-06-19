"""Walk-forward + full-period driver for xsec_sector_rot_b7a2f9.

Mirrors _run_xsec_momentum_wf.py. Candidate lives under
strategies_candidates/, so we load via importlib by path and pass
decide_xsec_fn directly into walk_forward_xsec.

The N=200 SMA trend filter needs 200+ trading bars of history before
it can fire. NAMED_WINDOWS are 60-90 calendar days; we extend with
WARMUP_DAYS=300 calendar days so the strategy has ~210 trading bars +
the labeled window. (Task spec: warmup_days=300.)

Sensitivity sweep: regime_filter ∈ {False, True} × sma_period ∈ {200, 150, 100}.

ADDITIONAL DIAGNOSTIC (vs xsec_momentum driver): per-window avg basket
size (n_holdings) — the defining behavioral signal of an absolute-
momentum trend filter (dynamic basket size: 0 in bears, 11 in bulls).
We compute it by re-running each window via backtest_xsec with a
counting wrapper. Read-only — does not edit walk_forward_xsec.
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
from runner.walk_forward import NAMED_WINDOWS  # noqa: E402

WARMUP_DAYS = 300
CANDIDATE = "xsec_sector_rot_b7a2f9"


def load(name):
    d = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(f"cand_{name}", d / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((d / "params.json").read_text())
    return mod, params


def _avg_basket_size_per_window(decide_fn, basket, params, cost_model,
                                  windows, min_bars_per_symbol=10):
    """Re-run each window with a wrapper that records len(position_state)
    on each decide call. Returns {label: {avg_basket, avg_basket_nonempty}}.

    avg_basket = mean across ALL decide calls.
    avg_basket_nonempty = mean across calls where position_state was
    non-empty (conditional on being in the market at all).
    """
    timeframe = str(params.get("timeframe", "1Day"))
    out = {}
    for label, end_dt, days, regime in windows:
        fetch_days = days + max(0, WARMUP_DAYS)
        bars_by_sym = {}
        for sym in basket:
            b = bars_cache.get_bars(sym, timeframe, days=fetch_days, end_dt=end_dt)
            if b and len(b) >= min_bars_per_symbol:
                bars_by_sym[sym] = b
        if len(bars_by_sym) < 2:
            continue

        counter = {"total_ticks": 0, "total_held": 0, "nonempty_ticks": 0,
                   "nonempty_held": 0}

        def wrapped(market_state, position_state, params, _c=counter,
                    _real=decide_fn):
            n = len(position_state)
            _c["total_ticks"] += 1
            _c["total_held"] += n
            if n > 0:
                _c["nonempty_ticks"] += 1
                _c["nonempty_held"] += n
            return _real(market_state, position_state, params)

        backtest_xsec(
            CANDIDATE, bars_by_sym, params,
            decide_xsec_fn=wrapped, default_cost_model=cost_model)

        t = counter["total_ticks"] or 1
        nt = counter["nonempty_ticks"] or 1
        out[label] = {
            "avg_basket": counter["total_held"] / t,
            "avg_basket_when_in": counter["nonempty_held"] / nt,
            "ticks": counter["total_ticks"],
        }
    return out


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

    # Also capture per-tick basket-size diagnostic for the full period.
    counter = {"total_ticks": 0, "total_held": 0,
               "nonempty_ticks": 0, "nonempty_held": 0,
               "max_held": 0}

    def wrapped(market_state, position_state, params, _c=counter, _real=decide_fn):
        n = len(position_state)
        _c["total_ticks"] += 1
        _c["total_held"] += n
        if n > _c["max_held"]:
            _c["max_held"] = n
        if n > 0:
            _c["nonempty_ticks"] += 1
            _c["nonempty_held"] += n
        return _real(market_state, position_state, params)

    bt = backtest_xsec(name, bars_by_sym, params,
                       decide_xsec_fn=wrapped,
                       default_cost_model=cost_model)
    t = counter["total_ticks"] or 1
    nt = counter["nonempty_ticks"] or 1
    diag = {
        "avg_basket": counter["total_held"] / t,
        "avg_basket_when_in": counter["nonempty_held"] / nt,
        "max_held": counter["max_held"],
    }
    return bt, bars_by_sym, diag


def run_config(label_suffix, mod, params, use_regime, sma_period):
    p = dict(params)
    p["use_regime_filter"] = use_regime
    p["sma_period"] = sma_period
    name_tagged = f"{CANDIDATE}{label_suffix}"
    print(f"\n== {name_tagged} (regime_filter={use_regime}, "
          f"sma_period={sma_period}, warmup +{WARMUP_DAYS}d) ==",
          file=sys.stderr)
    basket = list(p.get("basket") or [])
    cost_model = CostModel.alpaca_stocks()

    agg = walk_forward_xsec(
        name_tagged, basket, params=p, decide_xsec_fn=mod.decide_xsec,
        warmup_days=WARMUP_DAYS, cost_model=cost_model)
    fit_passed, fit_reason = passes_fitness_gate_xsec(agg)

    # Per-window basket-size diagnostic (re-run; lightweight).
    basket_diag = _avg_basket_size_per_window(
        mod.decide_xsec, basket, p, cost_model, NAMED_WINDOWS)

    # Full-period.
    fp_bt, fp_bars, fp_diag = full_period_xsec_backtest(
        name_tagged, basket, p, mod.decide_xsec, days=1800,
        cost_model=cost_model)
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

    return {
        "name": name_tagged,
        "use_regime": use_regime,
        "sma_period": sma_period,
        "agg": agg,
        "fitness_pass": fit_passed,
        "fitness_reason": fit_reason,
        "basket_diag": basket_diag,
        "full_period": {
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
            "diag": fp_diag,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="/tmp/xsec_sectrot_wf.json")
    ap.add_argument("--md", default="/tmp/xsec_sectrot_wf.md")
    ap.add_argument("--sensitivity", action="store_true",
                    help="Also run sma_period=150 and 100 sensitivities.")
    args = ap.parse_args()
    mod, params = load(CANDIDATE)

    configs = [
        ("__noreg_n200", False, 200),
        ("__regime_n200", True, 200),
    ]
    if args.sensitivity:
        configs += [
            ("__noreg_n150", False, 150),
            ("__noreg_n100", False, 100),
        ]

    results = []
    for tag, use_reg, n in configs:
        results.append(run_config(tag, mod, params, use_reg, n))

    out = []
    for r in results:
        agg = r["agg"]
        out.append({
            "name": r["name"],
            "use_regime": r["use_regime"],
            "sma_period": r["sma_period"],
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
            "basket_diag": r["basket_diag"],
            "full_period": r["full_period"],
        })
    Path(args.json).write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.json}", file=sys.stderr)

    chunks = [f"# Walk-Forward: {CANDIDATE}", ""]
    for r in results:
        chunks.append(f"## {r['name']} "
                      f"(use_regime={r['use_regime']}, sma={r['sma_period']})")
        chunks.append("")
        chunks.append(format_xsec_md(r["agg"]))
        # Basket size table
        chunks.append("**Avg basket size per window (dynamic — Faber signature):**")
        chunks.append("")
        chunks.append("| Window | avg_basket | avg_when_in |")
        chunks.append("|---|---|---|")
        for w in r["agg"].windows:
            d = r["basket_diag"].get(w.label, {})
            chunks.append(f"| {w.label} | {d.get('avg_basket', 0):.2f} | "
                          f"{d.get('avg_basket_when_in', 0):.2f} |")
        chunks.append("")
        fp = r["full_period"]
        diag = fp["diag"]
        chunks.append(f"**Full-period:** {fp['first_bar_t']} → {fp['last_bar_t']} · "
                      f"ticks={fp['n_ticks']} · trades={fp['n_trades']} "
                      f"(buys {fp['n_buys']} / closes {fp['n_closes']}) · "
                      f"clamps={fp['n_basket_clamps']} · "
                      f"return {fp['total_return_pct']:+.2f}% · "
                      f"Sharpe {fp['sharpe']:.2f} · "
                      f"maxDD {fp['max_dd_pct']:.2f}% · "
                      f"costs ${fp['total_costs_usd']:.2f} · "
                      f"avg_basket={diag['avg_basket']:.2f} · "
                      f"max_held={diag['max_held']}")
        chunks.append("")
    Path(args.md).write_text("\n\n".join(chunks))
    print(f"wrote {args.md}", file=sys.stderr)

    for r in results:
        agg = r["agg"]
        print(f"  {r['name']} regime={r['use_regime']} sma={r['sma_period']}: "
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
