"""Per-window decomposition of the best breadth cell vs BH-SPY, + a leave-one-
window-out (LOWO) FP recompute, to test whether the headline +0.848 is broad
or driven by one lucky regime window. import-only, no edits."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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

CDIR = WS / "strategies_candidates" / "breadth_internals"
spec = importlib.util.spec_from_file_location("cb", str(CDIR / "strategy.py"))
B = importlib.util.module_from_spec(spec); sys.modules["cb"] = B
spec.loader.exec_module(B)

BEST = {
    "symbol": "SPY", "basket": ["SPY"], "timeframe": "1Day",
    "notional_usd": 1000.0, "max_notional_usd": 1000.0,
    "breadth_mode": "pct_above_200sma", "sma_len": 200,
    "z_lookback": 120, "exposure_mode": "binary",
    "enter_z": 0.25, "exit_z": -0.25, "resize_band": 0.15, "min_fraction": 0.05,
}


class _BH:
    def __init__(s, a, sym, n=0.0):
        s.action = a; s.symbol = sym; s.notional_usd = n; s.qty = None; s.reason = "bh"


def bh_decide(ms, ps, p):
    sv = (ms.get("symbols") or {}).get("SPY") or {}
    if not sv.get("has_bar"):
        return {}
    if ps.get("SPY"):
        return {}
    return {"SPY": _BH("buy", "SPY", NOTIONAL)}


def run_one(decide_fn, params, only_labels=None):
    bts = []
    cm = CostModel.alpaca_stocks()
    rows = []
    for label, end_dt, days, regime in NAMED_WINDOWS:
        if only_labels is not None and label not in only_labels:
            continue
        bars = bars_cache.get_bars("SPY", "1Day", days=days + WARMUP, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest_xsec("x", {"SPY": bars}, params, decide_xsec_fn=decide_fn,
                           starting_cash=NOTIONAL, default_cost_model=cm)
        bts.append(bt)
        rows.append((label, regime, bt.total_return_pct, bt.n_trades))

    class _W:
        def __init__(s, bt): s.backtest = bt
    fp, _ = fp_continuous_sharpe([_W(bt) for bt in bts], timeframe="1Day", is_crypto=False)
    return fp, rows


def main():
    labels = [w[0] for w in NAMED_WINDOWS]
    print("=== Per-window: best breadth cell vs BH-SPY ===")
    _, brd_rows = run_one(B.decide_xsec, BEST)
    _, bh_rows = run_one(bh_decide, {"timeframe": "1Day", "notional_usd": NOTIONAL, "basket": ["SPY"]})
    bh_map = {r[0]: r[2] for r in bh_rows}
    print(f"  {'window':20s} {'regime':6s} {'breadth%':>9s} {'BH%':>9s} {'edge':>8s} trades")
    wins = 0
    for r in brd_rows:
        edge = r[2] - bh_map.get(r[0], 0.0)
        wins += 1 if edge > 0 else 0
        print(f"  {r[0]:20s} {r[1]:6s} {r[2]*100:+8.2f}% {bh_map.get(r[0],0)*100:+8.2f}% "
              f"{edge*100:+7.2f}% {r[3]}")
    print(f"  breadth beats BH on {wins}/{len(brd_rows)} windows")

    print("\n=== Leave-one-window-out (LOWO) FP of best breadth cell ===")
    full_fp, _ = run_one(B.decide_xsec, BEST)
    print(f"  full-panel FP = {full_fp:+.3f}")
    lowo = []
    for drop in labels:
        keep = [l for l in labels if l != drop]
        fp, _ = run_one(B.decide_xsec, BEST, only_labels=keep)
        lowo.append((drop, fp))
        print(f"  drop {drop:20s} -> FP={fp:+.3f}  (delta {fp-full_fp:+.3f})")
    worst = min(lowo, key=lambda x: x[1])
    best = max(lowo, key=lambda x: x[1])
    print(f"\n  FP range across LOWO: {worst[1]:+.3f} (dropping {worst[0]}) .. "
          f"{best[1]:+.3f} (dropping {best[0]})")
    print(f"  => dropping '{best[0]}' RAISES FP most: that window HURTS the cell.")
    print(f"  => dropping '{worst[0]}' LOWERS FP most: that window CARRIES the cell.")

    out = {"per_window": [{"window": r[0], "regime": r[1], "breadth_pct": r[2],
                           "bh_pct": bh_map.get(r[0]), "edge": r[2]-bh_map.get(r[0],0.0),
                           "trades": r[3]} for r in brd_rows],
           "beats_bh": f"{wins}/{len(brd_rows)}",
           "full_fp": round(full_fp, 3),
           "lowo": [{"dropped": d, "fp": round(f, 3)} for d, f in lowo]}
    (WS / "reports" / "_breadth_lowo.json").write_text(json.dumps(out, indent=2))
    print("\nwrote reports/_breadth_lowo.json")


if __name__ == "__main__":
    main()
