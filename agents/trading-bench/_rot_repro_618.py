"""Confirm the deltas are pure window-extension: re-run capped at 2026-06-18 (report's end)."""
import sys
sys.path.insert(0, ".")
from _sigimprove_tests import run_sector_rotation, slice_stats, OOS_SPLIT
ASSETS = ["SPY", "QQQ", "GLD", "TLT"]
r = run_sector_rotation(ASSETS, bench="^GSPC", cost_bps=2.0, start="2005-01-01",
                        end="2026-06-18", hold_top=2, lookback_months=3)
full = r["strategy"]["stats"]; spx = r["spx"]["stats"]
oos = slice_stats(r, "2019-01-01", "2099-12-31", "strategy")
is_  = slice_stats(r, "2005-01-01", OOS_SPLIT, "strategy")
print("WINDOW:", r["window"])
print("  full  Sharpe %.4f  CAGR %.2f%%  maxDD %.2f%%  nrebal %d" % (
    full["sharpe"], full["cagr_pct"], full["max_drawdown_pct"], r["n_rebalances"]))
print("  IS    Sharpe %.4f   OOS Sharpe %.4f   SPX full %.4f" % (is_["sharpe"], oos["sharpe"], spx["sharpe"]))
print("REPORT: full 0.916 / IS 0.929 / OOS 0.898 / maxDD -29.0 / SPX 0.542")
