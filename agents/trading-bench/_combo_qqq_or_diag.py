"""Diagnose the QQQ OR-fusion Sharpe lift: real timing edge or just closet beta
(more time-in-market on a bull-drifting QQQ)?

Tests:
  1. Time-in-market fraction for solo vs OR (how much of the span is the book
     actually long?). If OR's Sharpe lift tracks exposure 1:1, it's beta.
  2. QQQ buy&hold FP-Sharpe on the same tick grid (the pure-beta benchmark).
  3. Exposure-matched: scale solo and OR equity-return SERIES to the same
     gross exposure and recompare — does OR still win per-unit-risk?
  4. IS vs OOS FP-Sharpe for solo vs OR (does the lift survive OOS?).
  5. Per-window Sharpe (not just return) for solo vs OR.
"""
from __future__ import annotations

import json
from typing import List

import _combo_fusion_lib as L
from runner.fp_sharpe import equity_curve_returns, sharpe_from_returns
from runner.backtest import bars_per_year, CostModel, backtest


def time_in_market(equity_curve: List[float]) -> float:
    """Fraction of tick-to-tick steps where equity actually MOVED (proxy for
    being in a position). Flat steps => out of market (or holding through a
    zero-return bar, rare intraday)."""
    if len(equity_curve) < 2:
        return 0.0
    moved = sum(1 for i in range(1, len(equity_curve))
                if equity_curve[i] != equity_curve[i - 1])
    return moved / (len(equity_curve) - 1)


def qqq_buyhold_curve(qqq_bars: List[dict], start=None, end=None) -> List[float]:
    bars = L.slice_by_date(qqq_bars, start, end)
    if len(bars) < 2:
        return [1000.0]
    # 1000 fully deployed into QQQ at first close, marked-to-market each bar
    c0 = float(bars[0]["c"])
    shares = 1000.0 / c0
    return [shares * float(b["c"]) for b in bars]


def fp_s(curve: List[float]) -> float:
    return sharpe_from_returns(equity_curve_returns(curve), bars_per_year("1Hour", False))


def run_variant_curve(primary, bars, decide_fn, state, start=None, end=None):
    b = L.slice_by_date(bars, start, end)
    L.reset_lookup(state)
    _, params = L.load_strategy_module_and_params(primary)
    res = backtest(primary, b, params, starting_cash=1000.0,
                   decide_fn=decide_fn, cost_model=CostModel.alpaca_stocks())
    return res


def main():
    iwm_bars = L.load_full_1h("IWM")
    iwm_states = L.build_iwm_macd_states(iwm_bars)
    qqq_bars = L.load_full_1h("QQQ")

    primary = "volume_breakout_qqq"
    solo = L.solo_decide if False else None
    mod, _ = L.load_strategy_module_and_params(primary)
    solo_fn = mod.decide

    or_lookup, or_state = L.make_aligned_lookup(iwm_states, lag_bars=0)
    or_fn, _ = L.make_or_fusion(primary, or_lookup)

    dummy_lookup, dummy_state = L.make_aligned_lookup(iwm_states, lag_bars=0)

    print("=== QQQ OR-fusion deep dive ===")
    print(f"QQQ coverage {qqq_bars[0]['t'][:10]}..{qqq_bars[-1]['t'][:10]} n={len(qqq_bars)}")

    # full span
    solo_res = run_variant_curve(primary, qqq_bars, solo_fn, dummy_state)
    or_res = run_variant_curve(primary, qqq_bars, or_fn, or_state)

    tim_solo = time_in_market(solo_res.equity_curve)
    tim_or = time_in_market(or_res.equity_curve)
    fps_solo = fp_s(solo_res.equity_curve)
    fps_or = fp_s(or_res.equity_curve)

    # QQQ buy&hold benchmark
    qqq_bh = qqq_buyhold_curve(qqq_bars)
    fps_bh = fp_s(qqq_bh)
    tim_bh = time_in_market(qqq_bh)

    print(f"\n[1+2] FULL SPAN")
    print(f"  solo : fpS={fps_solo:+.3f} time_in_mkt={tim_solo:.3f} trades={solo_res.n_trades} ret={solo_res.total_return_pct:+.3f}%")
    print(f"  OR   : fpS={fps_or:+.3f} time_in_mkt={tim_or:.3f} trades={or_res.n_trades} ret={or_res.total_return_pct:+.3f}%")
    print(f"  QQQ BH: fpS={fps_bh:+.3f} time_in_mkt={tim_bh:.3f} (pure beta benchmark, always-on)")
    print(f"  exposure ratio OR/solo = {tim_or/max(tim_solo,1e-9):.2f}x ; Sharpe ratio OR/solo = {fps_or/max(fps_solo,1e-9):.2f}x")
    print(f"  --> if Sharpe-ratio << exposure-ratio, the lift is NOT just beta")

    # [3] exposure-normalized Sharpe (Sharpe is already scale-invariant, but
    # compare Sharpe-per-unit-time-in-market to see if OR is more EFFICIENT)
    eff_solo = fps_solo  # Sharpe already risk-normalized
    print(f"\n[3] Sharpe is scale-invariant; the real q is whether OR's EXTRA trades")
    print(f"    are accretive. Mean-return/exposure:")
    rs_solo = equity_curve_returns(solo_res.equity_curve)
    rs_or = equity_curve_returns(or_res.equity_curve)
    mr_solo = sum(rs_solo)/max(len(rs_solo),1)
    mr_or = sum(rs_or)/max(len(rs_or),1)
    print(f"    solo mean-tick-ret={mr_solo:.2e} / exposure {tim_solo:.3f} = {mr_solo/max(tim_solo,1e-9):.2e}")
    print(f"    OR   mean-tick-ret={mr_or:.2e} / exposure {tim_or:.3f} = {mr_or/max(tim_or,1e-9):.2e}")

    # [4] IS vs OOS
    print(f"\n[4] IS vs OOS FP-Sharpe")
    for lbl, st, en in [("IS", None, L.IS_END), ("OOS", L.OOS_START, None)]:
        L.reset_lookup(dummy_state)
        sres = run_variant_curve(primary, qqq_bars, solo_fn, dummy_state, st, en)
        or_lookup2, or_state2 = L.make_aligned_lookup(iwm_states, lag_bars=0)
        or_fn2, _ = L.make_or_fusion(primary, or_lookup2)
        ores = run_variant_curve(primary, qqq_bars, or_fn2, or_state2, st, en)
        qbh = qqq_buyhold_curve(qqq_bars, st, en)
        print(f"  {lbl:3s}: solo fpS={fp_s(sres.equity_curve):+.3f} (tr={sres.n_trades})  "
              f"OR fpS={fp_s(ores.equity_curve):+.3f} (tr={ores.n_trades})  "
              f"QQQ-BH fpS={fp_s(qbh):+.3f}")

    out = {
        "solo_fp_sharpe": fps_solo, "or_fp_sharpe": fps_or, "qqq_bh_fp_sharpe": fps_bh,
        "tim_solo": tim_solo, "tim_or": tim_or,
        "solo_trades": solo_res.n_trades, "or_trades": or_res.n_trades,
    }
    json.dump(out, open("_combo_qqq_or_diag.json", "w"), indent=2)
    print("\nwrote _combo_qqq_or_diag.json")


if __name__ == "__main__":
    main()
