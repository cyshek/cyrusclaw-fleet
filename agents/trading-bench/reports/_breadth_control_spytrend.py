"""Control: SPY-OWN-TREND overlay (no breadth, no cross-section) vs breadth.

The decisive relabel test. Reuses the SAME fractional-deployment {SPY} sleeve
and the SAME z-score/threshold/hysteresis machinery, but the SIGNAL is SPY's
OWN price relative to its own 200-day SMA — a pure single-name trend filter
that contains ZERO cross-sectional/breadth information. If this control matches
or beats the best breadth cell, breadth adds nothing over SPY's own trend ->
the breadth result is a RELABEL of the (already-dead) SPY-momentum/trend lane.

Signal: z-score of (SPY_close / SPY_SMA200 - 1) over a trailing z_lookback,
same enter/exit thresholds + binary hysteresis as the breadth best cell.
import-only; composes PUBLIC backtest_xsec + fp_continuous_sharpe. No edits.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest_xsec import backtest_xsec  # noqa: E402
from runner.backtest import CostModel  # noqa: E402
from runner.walk_forward import NAMED_WINDOWS  # noqa: E402
from runner.fp_sharpe import fp_continuous_sharpe  # noqa: E402
from runner import bars_cache  # noqa: E402

NOTIONAL = 1000.0
WARMUP = 320


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _spy_trend_z(closes, sma_len, z_lb):
    """z-score of (close/SMA200 - 1) over trailing z_lb, causal, from visible
    bars only. closes = list of SPY closes with t <= clock_t."""
    if len(closes) < sma_len + z_lb + 1:
        return None
    # build the (close/SMA - 1) series over the available history
    ratios = []
    run = sum(closes[:sma_len])
    for i in range(sma_len - 1, len(closes)):
        if i >= sma_len:
            run += closes[i] - closes[i - sma_len]
        sma = run / sma_len
        ratios.append(closes[i] / sma - 1.0 if sma > 0 else 0.0)
    if len(ratios) < z_lb + 1:
        return None
    window = ratios[-z_lb:]
    cur = ratios[-1]
    m = sum(window) / len(window)
    var = sum((x - m) ** 2 for x in window) / (len(window) - 1)
    if var <= 0:
        return None
    return (cur - m) / math.sqrt(var)


def make_decide(sma_len, z_lb, enter_z, exit_z):
    def decide(ms, ps, p):
        sv = (ms.get("symbols") or {}).get("SPY") or {}
        bars = sv.get("bars") or []
        if not bars:
            return {}
        closes = [float(b["c"]) for b in bars]
        z = _spy_trend_z(closes, sma_len, z_lb)
        pos = ps.get("SPY")
        holding = float(pos.get("qty", 0.0)) if pos else 0.0
        if z is None:
            target = 1.0
        elif z >= enter_z:
            target = 1.0
        elif z <= exit_z:
            target = 0.0
        else:
            target = 1.0 if holding > 0 else 0.0
        if not sv.get("has_bar"):
            return {}
        if target < 0.05:
            if holding > 0:
                return {"SPY": Action("close", "SPY", reason="trend de-risk")}
            return {}
        if holding <= 0:
            return {"SPY": Action("buy", "SPY", notional_usd=NOTIONAL, reason="trend on")}
        return {"SPY": Action("hold", "SPY", reason="hold")}
    return decide


def run_panel(decide_fn):
    bts = []
    cm = CostModel.alpaca_stocks()
    deploy_sum = 0.0; deploy_n = 0; trades = 0
    per_win = []

    def wrapped(ms, ps, p):
        nonlocal deploy_sum, deploy_n
        spy = ps.get("SPY")
        deploy_sum += (float(spy.get("market_value", 0.0)) if spy else 0.0) / NOTIONAL
        deploy_n += 1
        return decide_fn(ms, ps, p)

    for label, end_dt, days, regime in NAMED_WINDOWS:
        bars = bars_cache.get_bars("SPY", "1Day", days=days + WARMUP, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest_xsec("trend", {"SPY": bars}, {}, decide_xsec_fn=wrapped,
                           starting_cash=NOTIONAL, default_cost_model=cm)
        bts.append(bt); trades += bt.n_trades
        per_win.append((label, regime, bt.total_return_pct))

    class _W:
        def __init__(s, bt): s.backtest = bt
    fp, _ = fp_continuous_sharpe([_W(bt) for bt in bts], timeframe="1Day", is_crypto=False)
    dep = deploy_sum / deploy_n if deploy_n else None
    return fp, dep, trades, per_win


def main():
    print("=== SPY-OWN-TREND control (no breadth) — same machinery, SPY 200SMA z ===")
    grid = [
        (200, 120, 0.25, -0.25),
        (200, 120, 0.0, -0.5),
        (200, 120, 0.0, -0.25),
        (200, 60, 0.0, -0.25),
        (200, 60, 0.25, -0.25),
        (50, 120, 0.0, -0.5),
    ]
    best = None
    out = []
    for sma_len, z_lb, ez, xz in grid:
        fp, dep, tr, pw = run_panel(make_decide(sma_len, z_lb, ez, xz))
        beats = sum(1 for w in pw if False)  # n/a here
        print(f"  FP={fp:+.3f} dep={dep:.3f} tr={tr} sma={sma_len} z_lb={z_lb} enter={ez} exit={xz}")
        out.append({"sma_len": sma_len, "z_lb": z_lb, "enter_z": ez, "exit_z": xz,
                    "fp": round(fp, 3), "dep": round(dep, 3), "trades": tr})
        if best is None or fp > best["fp"]:
            best = out[-1]
    print(f"\nBEST SPY-trend control: FP={best['fp']:+.3f}  {best}")
    (WS / "reports" / "_breadth_control_spytrend.json").write_text(json.dumps(out, indent=2))
    print("wrote reports/_breadth_control_spytrend.json")


if __name__ == "__main__":
    main()
