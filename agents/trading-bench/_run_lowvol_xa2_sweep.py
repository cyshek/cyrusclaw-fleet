"""Wave-5 low-vol cross-asset variant sweep driver.

Computes, per variant config:
  - Full-period (single contiguous) Sharpe / MaxDD($) / return via backtest_xsec
  - Per-window walk-forward detail (warmup +180d) for Bar A #5 clause (c)
  - Per-regime medians
  - Bar A #5 scorecard: (a) FP Sharpe>=1.0, (b) MaxDD<=$200, (c) every
    window passes V1 OR V2 AND no catastrophe.

Does NOT modify any runner/* or candidate files.
"""
from __future__ import annotations
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner import bars_cache
from runner.backtest import CostModel
from runner.backtest_xsec import backtest_xsec
from runner.walk_forward import NAMED_WINDOWS
from runner.walk_forward_xsec import _bh_basket_return

import importlib.util
STRAT_PATH = WS / "strategies_candidates" / "xsec_lowvol_xa2_440761" / "strategy.py"
spec = importlib.util.spec_from_file_location("lv2strat", STRAT_PATH)
lv2 = importlib.util.module_from_spec(spec)
sys.modules["lv2strat"] = lv2
spec.loader.exec_module(lv2)
decide_xsec = lv2.decide_xsec

CM = CostModel.alpaca_stocks()
END = datetime(2026, 5, 29, tzinfo=timezone.utc)
START_CASH = 1000.0
WARMUP = 180

# ---- universes ----
U_WAVE4 = ["SPY", "EFA", "TLT", "VNQ", "DBC", "GLD"]
U_EXPANDED = ["SPY", "EFA", "TLT", "IEF", "SHY", "LQD", "USMV", "VNQ", "DBC", "GLD"]
U_NOTLT = ["SPY", "EFA", "IEF", "SHY", "LQD", "USMV", "VNQ", "DBC", "GLD"]


def fp_run(basket, params):
    """Full-period contiguous backtest. Returns dict of metrics."""
    bbs = {}
    for s in basket:
        b = bars_cache.get_bars(s, "1Day", days=3000, end_dt=END)
        if b and len(b) >= 50:
            bbs[s] = b
    r = backtest_xsec("lv2", bbs, params, decide_xsec_fn=decide_xsec,
                      default_cost_model=CM, starting_cash=START_CASH)
    maxdd_usd = 0.0
    peak = -1e18
    for e in r.equity_curve:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > maxdd_usd:
            maxdd_usd = dd
    return {
        "sharpe": r.sharpe,
        "ret_pct": r.total_return_pct * 100,
        "maxdd_pct": r.max_drawdown_pct * 100,
        "maxdd_usd": maxdd_usd,
        "trades": r.n_trades,
        "result": r,
    }


def wf_run(basket, params):
    """Per-window walk-forward. Returns list of window dicts + regime medians."""
    notional = float(params.get("notional_usd", 100.0))
    rows = []
    per_regime = {"bull": [], "chop": [], "bear": []}
    for label, end_dt, days, regime in NAMED_WINDOWS:
        fetch_days = days + WARMUP
        bbs = {}
        for s in basket:
            b = bars_cache.get_bars(s, "1Day", days=fetch_days, end_dt=end_dt)
            if b and len(b) >= 10:
                bbs[s] = b
        if len(bbs) < 2:
            continue
        # fresh state per window via fresh params copy is not needed (state in market_state)
        bt = backtest_xsec("lv2", bbs, params, decide_xsec_fn=decide_xsec,
                           default_cost_model=CM, starting_cash=START_CASH)
        bh = _bh_basket_return(list(bbs.keys()), end_dt, days, "1Day",
                               notional_usd=notional, starting_cash=START_CASH,
                               cost_model=CM)
        sret = bt.total_return_pct  # fraction of start equity
        rows.append({
            "label": label, "regime": regime,
            "ret_pct": sret * 100, "bh_pct": bh * 100,
            "sharpe": bt.sharpe, "maxdd_pct": bt.max_drawdown_pct * 100,
            "trades": bt.n_trades,
        })
        per_regime[regime].append(sret * 100)
    reg_med = {k: (statistics.median(v) if v else None) for k, v in per_regime.items()}
    return rows, reg_med


def score_c(rows):
    """Bar A #5 clause (c): every window passes V1 OR V2, AND no catastrophe.
    Returns (ok, details list)."""
    details = []
    all_ok = True
    for w in rows:
        s = w["ret_pct"] / 100.0
        bh = w["bh_pct"] / 100.0
        # V1 multiplicative
        if bh <= 0:
            v1 = s >= 2 * bh  # less negative than 2x BH (e.g. s>=-1% when bh=-0.5%) -> wait sign
            # spec: strategy return >= 2 x BH when BH<=0. 2*bh is more negative, so s>=2*bh is easy.
        else:
            v1 = (s - bh) >= -1.5 * abs(bh)
        # V2 absolute gap
        v2 = s >= (bh - 0.01)  # within 1.0pp = 0.01 fraction
        passV = v1 or v2
        # catastrophe backstop
        catastrophe = (s <= -0.015) and (s < bh)
        win_ok = passV and not catastrophe
        if not win_ok:
            all_ok = False
        details.append({
            "label": w["label"], "s": s * 100, "bh": bh * 100,
            "v1": v1, "v2": v2, "catastrophe": catastrophe, "ok": win_ok,
        })
    return all_ok, details


def run_variant(name, basket, **pover):
    params = {
        "basket": basket, "timeframe": "1Day",
        "max_notional_usd": 100, "notional_usd": 100,
        "vol_lookback_bars": pover.get("lb", 63),
        "bottom_k": pover.get("k", 3),
        "weight_mode": pover.get("wm", "inv_vol"),
        "use_regime_filter": pover.get("reg", False),
        "regime_sma_period": 50,
        "xsec_basket_size": pover.get("k", 3),
        "safety_max_loss_pct": -50.0,
    }
    fp = fp_run(basket, params)
    rows, reg_med = wf_run(basket, params)
    c_ok, c_det = score_c(rows)
    a = fp["sharpe"] >= 1.0
    b = fp["maxdd_usd"] <= 200.0
    p5 = a and b and c_ok
    return {
        "name": name, "params": params,
        "fp": {k: fp[k] for k in ("sharpe", "ret_pct", "maxdd_pct", "maxdd_usd", "trades")},
        "reg_med": reg_med, "rows": rows,
        "c_ok": c_ok, "c_det": c_det, "a": a, "b": b, "p5": p5,
    }


# Wave-4 universe = the ONLY one with real rotation (expanded collapses to
# SHY/IEF/LQD cash-park, negative Sharpe). So the productive levers are
# inverse-vol weighting + K/lookback tuning ON the wave-4 universe, plus a
# single +USMV swap-test that keeps dispersion.
U_W4_USMV = ["SPY", "EFA", "TLT", "VNQ", "DBC", "GLD", "USMV"]  # min-vol equity added
U_W4_SHYTLT = ["SPY", "EFA", "SHY", "VNQ", "DBC", "GLD"]  # swap TLT->SHY (de-risk bleed)

VARIANTS = [
    # baseline reproduction (wave-4 universe, equal weight)
    ("V0 wave4 eq K3 N60", U_WAVE4, dict(k=3, lb=60, wm="equal")),
    ("V0b wave4 eq K2 N60", U_WAVE4, dict(k=3, lb=60, wm="equal")),
    # lever (b): inverse-vol weighting on wave-4 universe
    ("V1 wave4 invvol K3 N60", U_WAVE4, dict(k=3, lb=60, wm="inv_vol")),
    ("V2 wave4 invvol K2 N60", U_WAVE4, dict(k=2, lb=60, wm="inv_vol")),
    ("V3 wave4 invvol K4 N60", U_WAVE4, dict(k=4, lb=60, wm="inv_vol")),
    # vol-lookback sensitivity (wave-4 univ, inv-vol K3)
    ("V4 wave4 invvol K3 N21", U_WAVE4, dict(k=3, lb=21, wm="inv_vol")),
    ("V5 wave4 invvol K3 N126", U_WAVE4, dict(k=3, lb=126, wm="inv_vol")),
    ("V6 wave4 eq K3 N21", U_WAVE4, dict(k=3, lb=21, wm="equal")),
    ("V7 wave4 eq K3 N126", U_WAVE4, dict(k=3, lb=126, wm="equal")),
    # regime gate (wave-4 invvol K3)
    ("V8 wave4 invvol K3 N60 +reg", U_WAVE4, dict(k=3, lb=60, wm="inv_vol", reg=True)),
    # +USMV min-vol equity swap-test
    ("V9 w4+USMV invvol K3 N60", U_W4_USMV, dict(k=3, lb=60, wm="inv_vol")),
    ("V10 w4+USMV eq K3 N60", U_W4_USMV, dict(k=3, lb=60, wm="equal")),
    # swap TLT->SHY only (de-risk the bleed but keep dispersion via 5 risk assets)
    ("V11 w4 SHY-for-TLT eq K3 N60", U_W4_SHYTLT, dict(k=3, lb=60, wm="equal")),
    ("V12 w4 SHY-for-TLT invvol K3 N60", U_W4_SHYTLT, dict(k=3, lb=60, wm="inv_vol")),
]


def main():
    out = []
    for name, basket, pov in VARIANTS:
        try:
            r = run_variant(name, basket, **pov)
            out.append(r)
            print(f"{name:34s} FPSharpe={r['fp']['sharpe']:.2f} ret={r['fp']['ret_pct']:+.2f}% "
                  f"DD=${r['fp']['maxdd_usd']:.2f} tr={r['fp']['trades']} "
                  f"(c)={'OK' if r['c_ok'] else 'FAIL'} #5={'PASS' if r['p5'] else 'no'}")
        except Exception as e:
            print(f"{name}: ERROR {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
    Path("/tmp/lv2_sweep.json").write_text(json.dumps(out, indent=2, default=str))
    print("wrote /tmp/lv2_sweep.json")


if __name__ == "__main__":
    main()
