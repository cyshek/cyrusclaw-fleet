"""Baseline reproduction: confirm _sigimprove_tests.run_sector_rotation(top2,3mo)
matches the validated TEST 3 numbers (full 0.916 / IS 0.929 / OOS 0.898 / maxDD -29.0% / CAGR 12.9%)."""
import sys, bisect
sys.path.insert(0, ".")
from _sigimprove_tests import run_sector_rotation, slice_stats, OOS_SPLIT

ASSETS = ["SPY", "QQQ", "GLD", "TLT"]
r = run_sector_rotation(ASSETS, bench="^GSPC", cost_bps=2.0, start="2005-01-01",
                        hold_top=2, lookback_months=3)
full = r["strategy"]["stats"]
spx = r["spx"]["stats"]
oos = slice_stats(r, "2019-01-01", "2099-12-31", "strategy")
is_  = slice_stats(r, "2005-01-01", OOS_SPLIT, "strategy")
print("WINDOW:", r["window"])
print("REPRO top2/3mo/monthly:")
print("  full  Sharpe %.4f  CAGR %.2f%%  maxDD %.2f%%  totRet %.1f%%  nrebal %d" % (
    full["sharpe"], full["cagr_pct"], full["max_drawdown_pct"], full["total_return_pct"], r["n_rebalances"]))
print("  IS    Sharpe %.4f  CAGR %.2f%%  maxDD %.2f%%" % (is_["sharpe"], is_["cagr_pct"], is_["max_drawdown_pct"]))
print("  OOS   Sharpe %.4f  CAGR %.2f%%  maxDD %.2f%%  totRet %.1f%%" % (
    oos["sharpe"], oos["cagr_pct"], oos["max_drawdown_pct"], oos["total_return_pct"]))
print("  SPX   full Sharpe %.4f" % spx["sharpe"])
print()
print("REPORT TEST3 top2: full 0.916 / IS 0.929 / OOS 0.898 / maxDD -29.0 / CAGR 12.9 / SPX 0.542")
