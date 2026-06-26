"""No-lookahead proof rows: show (rebalance_date, lookback_window_end, holds, scores)
for the baseline 63d/monthly. lookback_window_end must be the PRIOR period-end
close (strictly before rebalance_date), proving the rank decision uses only
trailing data."""
import sys
sys.path.insert(0, ".")
from _rot_lookback_cadence_sweep import run_rotation, ASSETS
r = run_rotation(ASSETS, lb_days=63, cadence_months=1, start="2005-01-01")
print("63d/monthly first 6 rebalances (proof rank uses prior period-end close):")
print("%-12s %-18s %-14s  scores(trailing 63d ret)" % ("rebal_date","lookback_win_end","holds"))
for h in r["pos_log"][:6]:
    sc = {k:(round(v,4) if v is not None else None) for k,v in h["scores"].items()}
    print("%-12s %-18s %-14s  %s" % (h["date"], h["lookback_window_end"], ",".join(h["holds"]), sc))
print()
print("INVARIANT: lookback_window_end < rebal_date for every row (strict lag). Verify:")
ok = all(h["lookback_window_end"] < h["date"] for h in r["pos_log"])
print("  all(lookback_window_end < rebal_date) =", ok, " (n=%d rebalances)" % len(r["pos_log"]))
