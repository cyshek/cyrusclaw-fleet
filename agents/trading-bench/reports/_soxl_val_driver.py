"""SOXL leveraged_trend VALIDATION driver (throwaway, validation subagent).

Composes PUBLIC runner.backtest_xsec + canonical fp_continuous_sharpe over:
  (1) FULL continuous span (trade count, instrument DD, full-span FP, return floor)
  (2) IN-SAMPLE window  2020-12 .. 2024-12-31  (FP-cont)
  (3) HELD-OUT window   2025-01-01 .. 2026-06-03 (FP-cont) -- out-of-sample
  (4) 8-window NAMED_WINDOWS panel (gate-style FP-cont) + held-out final window alone

No protected/evaluator file edited. Single-name basket = {SOXL}.
"""
from __future__ import annotations
import importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest_xsec import backtest_xsec
from runner.backtest import CostModel
from runner.walk_forward import NAMED_WINDOWS
from runner.fp_sharpe import fp_continuous_sharpe
from runner import bars_cache

SYM = "SOXL"
NOTIONAL = 1000.0
START_CASH = 1000.0
WARMUP_DAYS = 400  # calendar days of priming so SMA100 + regime SMA100 compute


def _load():
    cdir = WS / "strategies_candidates" / "leveraged_trend"
    spec = importlib.util.spec_from_file_location("cand_lev_trend_val", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


DECIDE, PARAMS = _load()


class _W:
    def __init__(s, bt): s.backtest = bt


def _fp(bts):
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in bts], timeframe="1Day", is_crypto=False)
    return fps, nret


def _slice_bars(bars, start_iso, end_iso):
    """Return bars with date in [start_iso, end_iso]. We need warmup BEFORE start
    for the trailing filters to be primed, so we keep a warmup head of bars before
    start but mark only the scored span. Simpler: include warmup head so SMA primes,
    then the backtest runs across all included bars. To isolate FP to the scored span,
    we pass only bars whose date <= end_iso and >= (start - warmup). The strategy is
    trailing so early-warmup bars produce flat (risk-off until primed) actions -- they
    contribute ~0 return, not lookahead. For a CLEAN OOS FP we instead pass bars from a
    warmup head and then the scored span; the FP is computed on the full equity curve of
    the passed slice. To keep IN vs HELD-OUT genuinely disjoint in *return contribution*,
    we give each its own warmup head and start the equity curve at the window boundary by
    construction of the slice (warmup bars are flat)."""
    out = [b for b in bars if start_iso <= str(b["t"])[:10] <= end_iso]
    return out


def _warmup_head(bars, start_iso, warmup_bars=140):
    """bars strictly before start_iso, last `warmup_bars` of them, for priming."""
    head = [b for b in bars if str(b["t"])[:10] < start_iso]
    return head[-warmup_bars:]


def _run(bars):
    cm = CostModel.alpaca_stocks()
    bt = backtest_xsec("lev", {SYM: bars}, PARAMS, decide_xsec_fn=DECIDE,
                       starting_cash=START_CASH, default_cost_model=cm)
    fps, nret = _fp([bt])
    return bt, fps, nret


def _span_years(bars):
    d0 = datetime.strptime(str(bars[0]["t"])[:10], "%Y-%m-%d")
    d1 = datetime.strptime(str(bars[-1]["t"])[:10], "%Y-%m-%d")
    return (d1 - d0).days / 365.25


def main():
    full = bars_cache.get_bars(SYM, "1Day", days=2000)
    out = {}

    # (1) FULL span
    bt, fp, nret = _run(full)
    yrs = _span_years(full)
    ann = ((1.0 + bt.total_return_pct) ** (1.0 / yrs) - 1.0) * 100.0
    out["full"] = {
        "span": f"{str(full[0]['t'])[:10]}..{str(full[-1]['t'])[:10]}",
        "years": round(yrs, 2),
        "ret_pct": round(bt.total_return_pct * 100, 1),
        "ann_ret_pct_on_deployed": round(ann, 2),
        "inst_dd_pct": round(bt.worst_instrument_dd_pct * 100, 2),
        "nav_dd_pct": round(bt.max_drawdown_pct * 100, 2),
        "n_trades": bt.n_trades,
        "n_buys": getattr(bt, "n_buys", None),
        "n_closes": getattr(bt, "n_closes", None),
        "fp_cont_sharpe": round(fp, 3),
        "n_ticks": bt.n_ticks,
    }
    print("FULL:", json.dumps(out["full"], indent=2))

    # (2) IN-SAMPLE 2020-12..2024-12-31  (with its own warmup head = bars before start)
    IS_START, IS_END = "2020-12-14", "2024-12-31"
    is_bars = _slice_bars(full, IS_START, IS_END)
    bt_is, fp_is, _ = _run(is_bars)
    out["in_sample"] = {
        "span": f"{str(is_bars[0]['t'])[:10]}..{str(is_bars[-1]['t'])[:10]}",
        "n_bars": len(is_bars),
        "ret_pct": round(bt_is.total_return_pct * 100, 1),
        "inst_dd_pct": round(bt_is.worst_instrument_dd_pct * 100, 2),
        "n_trades": bt_is.n_trades,
        "fp_cont_sharpe": round(fp_is, 3),
    }
    print("IN_SAMPLE:", json.dumps(out["in_sample"], indent=2))

    # (3) HELD-OUT 2025-01-01..end, warmup head before it (140 bars) to prime filters
    HO_START, HO_END = "2025-01-01", "2026-12-31"
    head = _warmup_head(full, HO_START, 140)
    ho_scored = _slice_bars(full, HO_START, HO_END)
    ho_bars = head + ho_scored
    bt_ho, fp_ho, _ = _run(ho_bars)
    # also: scored-only return (the held-out window return contribution)
    yrs_ho = _span_years(ho_scored)
    ann_ho = ((1.0 + bt_ho.total_return_pct) ** (1.0 / max(yrs_ho, 0.01)) - 1.0) * 100.0 if bt_ho.total_return_pct > -1 else float("nan")
    out["held_out"] = {
        "scored_span": f"{str(ho_scored[0]['t'])[:10]}..{str(ho_scored[-1]['t'])[:10]}",
        "warmup_head_bars": len(head),
        "n_scored_bars": len(ho_scored),
        "ret_pct_incl_warmup": round(bt_ho.total_return_pct * 100, 1),
        "ann_ret_pct": round(ann_ho, 2),
        "inst_dd_pct": round(bt_ho.worst_instrument_dd_pct * 100, 2),
        "n_trades": bt_ho.n_trades,
        "fp_cont_sharpe": round(fp_ho, 3),
    }
    print("HELD_OUT:", json.dumps(out["held_out"], indent=2))

    # (4) 8-window panel + held-out final window (2026-recent bull) standalone
    cm = CostModel.alpaca_stocks()
    bts = []
    per_win = []
    final_label = NAMED_WINDOWS[-1][0]
    final_fp = None
    for label, end_dt, days, regime in NAMED_WINDOWS:
        bars = bars_cache.get_bars(SYM, "1Day", days=days + WARMUP_DAYS, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt_w = backtest_xsec("lev", {SYM: bars}, PARAMS, decide_xsec_fn=DECIDE,
                             starting_cash=START_CASH, default_cost_model=cm)
        bts.append(bt_w)
        fpw, _ = _fp([bt_w])
        per_win.append({"label": label, "regime": regime,
                        "ret_pct": round(bt_w.total_return_pct * 100, 2),
                        "inst_dd_pct": round(bt_w.worst_instrument_dd_pct * 100, 2),
                        "trades": bt_w.n_trades, "fp_alone": round(fpw, 3)})
        if label == final_label:
            final_fp = round(fpw, 3)
    panel_fp, _ = _fp(bts)
    out["panel"] = {
        "panel_fp_cont_sharpe": round(panel_fp, 3),
        "total_trades": sum(w["trades"] for w in per_win),
        "final_holdout_window": final_label,
        "final_holdout_fp_alone": final_fp,
        "per_window": per_win,
    }
    print("PANEL:", json.dumps(out["panel"], indent=2))

    (WS / "reports" / "_soxl_val_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_soxl_val_results.json")


if __name__ == "__main__":
    main()
