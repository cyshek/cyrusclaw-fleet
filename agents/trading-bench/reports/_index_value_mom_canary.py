"""Sanity + canary checks on the index-value/mom probe.
1) Print the trailing div-yield level for SPY at a few dates (is it sane, ~1.5-3%?).
2) Show DFII10 real-yield level at a few dates.
3) CANARY: re-run the equity div-yield value leg with a SECOND day of lag
   (lag=2). A real signal degrades gracefully; a lookahead-leaking one collapses
   or flips. Compare corr-to-mom and standalone Sharpe lag1 vs lag2.
4) Also re-run mom book lag2 as paired canary.
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "reports")
import _index_value_mom_probe as P
import _index_value_mom_driver as D

dates = P.build_calendar("SPY")

# sanity: div yield + real yield levels
spy_dy = D.trailing_div_yield("SPY", dates, win_d=252)
dfii10 = P.fred_on_calendar("DFII10", dates)
check_dates = ["2010-06-30", "2013-06-28", "2016-06-30", "2020-03-31", "2022-06-30", "2024-06-28"]
idx_by_date = {d: i for i, d in enumerate(dates)}
print("=== SANITY: SPY trailing 12m div yield & DFII10 real 10y ===")
for cd in check_dates:
    # nearest <= cd
    i = max(i for d, i in idx_by_date.items() if d <= cd)
    dy = spy_dy[i]
    ry = dfii10[i]
    print(f"  {dates[i]}: SPY_divyield={dy*100:.2f}%  DFII10_real10y={ry}")

print()
print("=== CANARY: equity div-yield value leg, lag1 vs lag2 ===")
for lag in (1, 2):
    v = P.value_signal_returns(dates, "SPY", spy_dy, cheap_is_high=True,
                               z_win_d=252 * 5, vol_target=0.15, lag_days=lag,
                               start=P.SAMPLE_START, long_flat_only=False, rebal="month")
    st = P.stats(v["net"], v["dates"], f"divyield_lag{lag}")
    mom = P.tsmom_book_returns(dates, symbols=("QQQ", "SPY"), lookback_m=12,
                               skip_m=1, vol_target=0.15, lag_days=lag, start=P.SAMPLE_START)
    disc = D.discrimination(v["dates"], v["net"], mom["dates"], mom["net"], f"divyield_lag{lag}")
    print(f"  lag{lag}: standalone fpSharpe={st['fp_sharpe']} OOS={st['oos_sharpe']} "
          f"fpCAGR={st['fp_cagr']}% | corr_to_mom={disc['corr_value_to_mom']} "
          f"margin={disc['distinctness_margin_vs_shortmom']}")

print()
print("=== CANARY: bond real-yield value leg (best standalone OOS), lag1 vs lag2 ===")
for lag in (1, 2):
    v = P.value_signal_returns(dates, "IEF", dfii10, cheap_is_high=True,
                               z_win_d=252 * 5, vol_target=0.15, lag_days=lag,
                               start=P.SAMPLE_START, long_flat_only=False, rebal="month")
    st = P.stats(v["net"], v["dates"], f"bondreal_lag{lag}")
    mom = P.tsmom_book_returns(dates, symbols=("QQQ", "SPY"), lookback_m=12,
                               skip_m=1, vol_target=0.15, lag_days=lag, start=P.SAMPLE_START)
    disc = D.discrimination(v["dates"], v["net"], mom["dates"], mom["net"], f"bondreal_lag{lag}")
    print(f"  lag{lag}: standalone fpSharpe={st['fp_sharpe']} OOS={st['oos_sharpe']} "
          f"fpCAGR={st['fp_cagr']}% | corr_to_mom={disc['corr_value_to_mom']} "
          f"margin={disc['distinctness_margin_vs_shortmom']}")
