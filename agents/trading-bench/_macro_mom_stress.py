"""Stress tests for the macro-mom pre-flight result:
 (1) PIT-lag sensitivity: re-run macro-only with 3m and 4m monthly lag (vs 2m)
     and verify the 2008 crisis alpha survives a MUCH more conservative lag
     (kills the 'it peeked at the recession' worry).
 (2) Scoring-map robustness: a CRUDE alternative macro score (growth+inflation
     only, no curve/credit/usd tuning) -- does macro STILL beat price, or did
     the fine-grained rule map curve-fit?
 (3) Show the actual macro selections entering & through 2008 (transparency).
"""
from __future__ import annotations
import math
import _macro_mom_engine as E

START = "2007-04-01"
END = "2026-06-24"
macro = E.load_macro("2004-01-01", END)


def stat_line(label, v):
    spy_v = E.spy_path(v["panel"], v["panel_dates"], v["dates"])
    shp = E.sharpe_from_returns(v["net"], E.BPY)
    cg = E.cagr(v["net"])
    mdd = E.max_drawdown(v["net"]) * 100
    c = E.corr(v["net"], spy_v)
    g08, _ = E.window_return(v["dates"], v["net"], "2008-01-01", "2009-03-31")
    g22, _ = E.window_return(v["dates"], v["net"], "2022-01-01", "2022-10-31")
    print(f"{label:22s} Sharpe={shp:5.2f} CAGR={cg:6.2f} MaxDD={mdd:7.2f} "
          f"corrSPY={c:5.2f}  2008={g08:6.1f}% 2022={g22:6.1f}%")


# ---- (1) PIT lag sensitivity (monkeypatch the monthly min_month_lag default) ----
print("=== (1) PIT-LAG SENSITIVITY (macro-only long top-2) ===")
print("Re-running macro with progressively MORE conservative monthly release lag.")

orig_score = E.macro_score
orig_mt = E.monthly_trend
orig_mtp = E.monthly_trend_prev

def make_lagged(lag):
    def mt(series, date, lookback_m, min_month_lag=lag):
        return orig_mt(series, date, lookback_m, min_month_lag=min_month_lag)
    def mtp(series, date, lookback_m, min_month_lag=lag):
        return orig_mt(series, date, lookback_m, min_month_lag=min_month_lag + 1)
    return mt, mtp

for lag in (2, 3, 4):
    mt, mtp = make_lagged(lag)
    E.monthly_trend = mt
    E.monthly_trend_prev = mtp
    v = E.run_strategy("macro", macro, START, END)
    stat_line(f"macro 2m-base lag={lag}m", v)
# restore
E.monthly_trend = orig_mt
E.monthly_trend_prev = orig_mtp

# also the price baseline for reference on this exact span
print()
vp = E.run_strategy("price", macro, START, END)
stat_line("price-only baseline", vp)


# ---- (2) CRUDE macro score: growth + inflation ONLY ----
print()
print("=== (2) SCORING-MAP ROBUSTNESS: crude growth+inflation-only score ===")

def crude_score(asset, date, macro):
    growth = E.monthly_trend(macro["INDPRO"], date, 12)
    infl = E.monthly_trend(macro["CPIAUCSL"], date, 12)
    if growth is None or infl is None:
        return None
    GROWTH_UP = growth > 0.0
    INFL_HOT = infl > 0.025
    s = 0.0
    if asset in ("SPY", "EFA", "VNQ"):
        s += 1.0 if GROWTH_UP else -1.0
        s += -1.0 if INFL_HOT else 0.0
    elif asset == "TLT":
        s += -1.0 if GROWTH_UP else 1.0
        s += -1.0 if INFL_HOT else 1.0
    elif asset == "GLD":
        s += 1.0 if INFL_HOT else -0.5
    elif asset == "DBC":
        s += 1.0 if INFL_HOT else -1.0
        s += 1.0 if GROWTH_UP else -1.0
    return s

E.macro_score = crude_score
vc = E.run_strategy("macro", macro, START, END)
stat_line("macro CRUDE (growth+infl)", vc)
vcls = E.run_strategy("macro", macro, START, END, ls=True)
stat_line("macro CRUDE L/S", vcls)
E.macro_score = orig_score


# ---- (3) transparency: macro selections entering & through 2008 ----
print()
print("=== (3) MACRO long top-2 selections 2007-09 .. 2009-03 (transparency) ===")
v = E.run_strategy("macro", macro, START, END)
for d, wd in v["weights"]:
    if "2007-09" <= d <= "2009-03":
        longs = [s for s in E.BASKET if wd[s] > 0]
        print(f"  {d}: {longs}")
