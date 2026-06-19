"""Lookahead-leak audit for the leveraged-long engine.

Build a synthetic world where the underlying CRASHES on a known day, and verify
the strategy does NOT magically dodge the crash-day's loss using same-day info.
If there is NO leak, the strategy (deciding on day D's close, holding over D+1)
should still EAT the move that happens on the day it was already positioned for,
and only avoid moves on days AFTER the signal flips.
"""
import sys
sys.path.insert(0, ".")
from strategies_candidates.leveraged_long_trend import backtest_daily as bt

# Monkeypatch dbc.get_daily to return synthetic series (no network).
import runner.daily_bars_cache as dbc


def mkbars(closes, start="2020-01-01"):
    import datetime
    d = datetime.date.fromisoformat(start)
    out = []
    i = 0
    while len(out) < len(closes):
        if d.weekday() < 5:  # weekday
            c = closes[len(out)]
            out.append({"date": d.isoformat(), "open": c, "high": c, "low": c,
                        "close": c, "adjclose": c, "volume": 1000})
        d += datetime.timedelta(days=1)
        i += 1
    return out


# Underlying: flat uptrend (well above any SMA) for 260 days, then a cliff.
# Build 260 days rising slowly so SMA200 is satisfied, then a sharp drop.
under = [100.0 + 0.1 * i for i in range(260)]   # 100 -> ~126, steadily up
# sleeve = 3x daily of underlying returns, start at 10.0
sleeve = [10.0]
for i in range(1, len(under)):
    r = under[i] / under[i - 1] - 1.0
    sleeve.append(sleeve[-1] * (1.0 + 3.0 * r))

# Now append a crash: underlying -10% on day 260 (index 260), sleeve -30%.
under.append(under[-1] * 0.90)
sleeve.append(sleeve[-1] * 0.70)
# then keep going flat-down a few days
for _ in range(5):
    under.append(under[-1] * 0.99)
    sleeve.append(sleeve[-1] * (1.0 + 3.0 * (-0.01)))

ubars = mkbars(under)
sbars = mkbars(sleeve)
# benchmark = underlying itself (doesn't matter for the leak test)
bbars = ubars

orig = dbc.get_daily


def fake_get_daily(symbol, **kw):
    if symbol == "TQQQ":
        return sbars
    return ubars  # QQQ / ^GSPC


dbc.get_daily = fake_get_daily
bt.dbc.get_daily = fake_get_daily

# Disable VIX + tbill to isolate the trend logic.
p = bt.LevLongParams(sleeve="TQQQ", underlying="QQQ", benchmark="QQQ",
                     gate_mode="sma200", sma_window=200, vix_gate=False,
                     use_tbill_cash=False, switch_cost_bps=0.0)
res = bt.run_backtest(p)

# Inspect the position log around the crash day.
crash_date = ubars[260]["date"]
print("crash day =", crash_date, "underlying drops -10%, sleeve -30%")
print("")
print("position log around the crash (date, pos, inst_ret):")
for pl in res["pos_log"]:
    if ubars[255]["date"] <= pl["date"] <= ubars[266]["date"]:
        print("  %s  %-6s  inst_ret=%+.4f" % (pl["date"], pl["pos"], pl["inst_ret"]))

# THE LEAK TEST:
# On the crash day, the underlying was still in a clean uptrend AT THE PRIOR
# CLOSE (it had been rising for 260 days). So the position decided on day 259's
# close = SLEEVE (in market). That position is HELD over day 260 (the crash).
# => a NON-LEAKING strategy MUST take the -30% hit on the crash day.
# A LEAKING strategy would have seen the crash coming and been in cash => inst_ret 0.
crash_pl = [pl for pl in res["pos_log"] if pl["date"] == crash_date]
assert crash_pl, "crash day not in pos_log"
cp = crash_pl[0]
print("")
print("=== LEAK VERDICT ===")
if cp["pos"] == "sleeve" and cp["inst_ret"] < -0.20:
    print("PASS (no leak): strategy was IN sleeve on the crash day and ATE %.1f%% — "
          "it could not see the same-day crash. Correct." % (cp["inst_ret"] * 100))
elif cp["pos"] == "cash":
    print("FAIL (LEAK!): strategy was in CASH on the crash day despite a clean "
          "uptrend at the prior close — it must have peeked at same-day data.")
else:
    print("INCONCLUSIVE: pos=%s inst_ret=%.4f" % (cp["pos"], cp["inst_ret"]))

# Second check: AFTER the crash, the underlying may still be above SMA200 (one
# -10% day off a +26-day uptrend won't break a 200d SMA), so the strategy likely
# STAYS in. That's fine — it just confirms the gate is slow (a known property),
# not a leak.
dbc.get_daily = orig
