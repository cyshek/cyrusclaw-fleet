"""Reproduce the LIVE 2-sleeve allocator baseline (breadth-A) and confirm
OOS maxDD ~ -20.0% / OOS Sharpe ~ 1.15 BEFORE any hedge work (honesty rail)."""
import sys, json
sys.path.insert(0, ".")
from _allocator_blend_tests import (
    build_sleeves, blend_portfolio, report_blend, stats_from_returns,
    slice_equity_stats,
)

S = build_sleeves()
dates = S["common_dates"]
tqqq_r = S["tqqq_r"]; rot_r = S["rot_r"]; spx_r = S["spx_r"]
spx_curve = stats_from_returns(dates, spx_r)
spx_dates = spx_curve["dates"]; spx_equity = spx_curve["equity"]

sleeves = [tqqq_r, rot_r]

def invvol_wfn(lookback=63):
    from _allocator_blend_tests import annualized_vol
    def fn(idx):
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - lookback)
        v0 = annualized_vol(sleeves[0][lo:idx])
        v1 = annualized_vol(sleeves[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0/v0, 1.0/v1
        s = iv0+iv1
        return [iv0/s, iv1/s]
    return fn

b = blend_portfolio(dates, sleeves, invvol_wfn(63), blend_cost_bps=2.0)
rep = report_blend(b, "LIVE_2sleeve_invvol63", spx_dates, spx_equity)
print("=== BASELINE inv-vol 2-sleeve (breadth-A) ===")
print(json.dumps({
    "window": rep["window"],
    "full": rep["full"],
    "is_2010_2018": rep["is_2010_2018"],
    "oos_2019_today": rep["oos_2019_today"],
    "spx_full": rep["spx_full"],
    "spx_oos": rep["spx_oos"],
    "n_rebal": rep["n_rebal"],
    "avg_turnover_per_rebal": rep["avg_turnover_per_rebal"],
}, indent=2, default=str))
print("\nTARGET CHECK: full Sharpe~1.029, OOS Sharpe~1.150, OOS maxDD~-20.02%, full maxDD~-20.33%, raw~1011% vs SPX 595%")
