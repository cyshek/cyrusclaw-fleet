"""Hold-the-Dip audit of the LIVE `rsi_oversold_spy` parent — PRODUCTION-ENGINE
version (uses runner.backtest.backtest so cost/fill/position accounting and the
Sharpe ruler are IDENTICAL to every other backtest in the book).

AQR "Hold the Dip" (Dec 2025): dip-buying underperforms because it is anti-
momentum. Our live child `rsi_oversold_spy` IS a dip-buy (RSI(14)<28 enter on
SPY 1Hour, exit RSI>70 or 20-bar time-stop). Three arms on the SAME SPY 1Hour
path, SAME CostModel.alpaca_stocks() (2 bps/side), SAME engine + Sharpe ruler:

  BASELINE  : the live strategy's own decide() unchanged.
  (a) GATED : same decide(), but VETO the buy unless SPY > its DAILY 200d SMA
              (lookahead-safe: most recent daily adjclose STRICTLY before the
              bar's calendar day vs its 200d SMA). AQR's proposed fix.
  (b) FLIP  : momentum-entry flip — buy STRENGTH (RSI>70), exit on weakness
              (RSI<30) or 20-bar stop. Tests AQR's momentum>dip claim head-on.

+ a 1-DAY-LAG robustness canary on the gated arm (daily SMA read lagged one
extra trading day). Promote a swap only if it beats the live dip-buy OOS net of
cost (and, for the gate, survives the canary). If the raw dip-buy holds, we've
empirically rebutted AQR on SPY 1Hour. PAPER/RESEARCH ONLY. No orders.
"""
from __future__ import annotations

import bisect
import json
import sys
from typing import Callable, Dict, List, Optional

sys.path.insert(0, ".")
sys.path.insert(0, "strategies")

from runner.backtest import (CostModel, backtest, bars_per_year,
                             load_strategy_module_and_params)
from runner import bars_cache
from runner import daily_bars_cache as dbc


def load_live():
    # Use the production loader: it registers strategies.<name>.strategy in
    # sys.modules so the strategy's @dataclass resolves correctly.
    return load_strategy_module_and_params("rsi_oversold_spy")


OOS_START = "2024-01-01"   # 1Hour floor 2020-07-27; deepest honest split


def load_1h(symbol: str) -> List[dict]:
    bars = bars_cache.get_bars(symbol, "1Hour", days=6000)
    return [b for b in bars if b.get("c")]


def slice_by_day(bars: List[dict], start: Optional[str], end: Optional[str]):
    out = []
    for b in bars:
        d = str(b.get("t", ""))[:10]
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(b)
    return out


# --- daily SMA-200 trend gate (lookahead-safe, strictly-prior daily close) ----
def build_daily_sma_gate(symbol: str, window: int = 200):
    d = dbc.get_daily(symbol)
    dates = [b["date"] for b in d]
    closes = [b["adjclose"] for b in d]
    sma_at: List[Optional[float]] = [None] * len(closes)
    run = 0.0
    for i in range(len(closes)):
        run += closes[i]
        if i >= window:
            run -= closes[i - window]
        if i >= window - 1:
            sma_at[i] = run / window

    def is_up(bar_day: str, lag_days: int = 0) -> bool:
        idx = bisect.bisect_left(dates, bar_day) - 1   # strictly before bar_day
        idx -= lag_days
        if idx < 0 or idx >= len(closes) or sma_at[idx] is None:
            return False
        return closes[idx] > sma_at[idx]

    return is_up


# --- decide wrappers -------------------------------------------------------- #
def make_gated(base_decide, gate: Callable[[str, int], bool], lag: int = 0):
    def decide(market_state, position_state, params):
        act = base_decide(market_state, position_state, params)
        if getattr(act, "action", "hold") == "buy":
            bars = market_state.get("bars") or []
            day = str(bars[-1]["t"])[:10] if bars else ""
            if not gate(day, lag):
                act.action = "hold"
                act.notional_usd = 0.0
                act.reason = "HOLD-DIP gate veto: SPY <= 200d SMA @ " + day
        return act
    return decide


def make_flip(params_ref):
    """Momentum flip: buy when RSI>MOM_ENTRY, exit when RSI<MOM_EXIT or time-stop.
    Independent of the live decide() (opposite signal). Uses the same RSI/period,
    notional, and time-stop as the live params for an apples-to-apples flip.
    """
    from strategies._lib.indicators import closes as _closes, rsi as _rsi

    MOM_ENTRY = 70.0
    MOM_EXIT = 30.0

    def decide(market_state, position_state, params):
        from dataclasses import dataclass

        @dataclass
        class A:
            action: str
            symbol: str
            notional_usd: float = 0.0
            qty: Optional[float] = None
            reason: str = ""

        symbol = params.get("symbol", "SPY")
        rsi_p = int(params.get("rsi_period", 14))
        time_stop = int(params.get("time_stop_bars", 20))
        notional = float(params.get("notional_usd", 100.0))
        bars = market_state.get("bars") or []
        cs = _closes(bars)
        r = _rsi(cs, rsi_p)
        n = len(cs)
        pos = position_state.get(symbol)
        holding = float(pos.get("qty", 0)) if pos else 0.0
        if r is None:
            return A("hold", symbol, reason="warmup")
        if holding == 0:
            if r > MOM_ENTRY:
                position_state.setdefault(symbol, {})["_flip_entry_bar"] = n
                return A("buy", symbol, notional_usd=notional,
                         reason=f"FLIP momentum entry RSI={r:.1f}>{MOM_ENTRY}")
            return A("hold", symbol, reason=f"RSI={r:.1f} flat")
        entry_bar = (pos or {}).get("_flip_entry_bar", n)
        held = n - entry_bar
        if r < MOM_EXIT:
            if pos is not None:
                pos.pop("_flip_entry_bar", None)
            return A("close", symbol, reason=f"FLIP exit RSI={r:.1f}<{MOM_EXIT}")
        if held >= time_stop:
            if pos is not None:
                pos.pop("_flip_entry_bar", None)
            return A("close", symbol, reason=f"FLIP time-stop {held}>={time_stop}")
        return A("hold", symbol, reason=f"RSI={r:.1f} held={held}")
    return decide


def run(name, bars, decide_fn, params):
    cm = CostModel.alpaca_stocks()
    res = backtest("rsi_oversold_spy", bars, params,
                   starting_cash=1000.0, decide_fn=decide_fn, cost_model=cm)
    return {
        "fp_sharpe": res.sharpe, "ret_pct": res.total_return_pct * 100.0,
        "n_trades": res.n_trades, "maxdd_pct": res.max_drawdown_pct * 100.0,
        "win_rate": res.win_rate, "n_bars": res.n_bars,
    }


def spy_bh(bars, params):
    """SPY buy&hold on the same 1Hour path (one round-trip cost)."""
    cm = CostModel.alpaca_stocks()
    if len(bars) < 2:
        return {"fp_sharpe": 0.0, "ret_pct": 0.0}
    c0 = float(bars[0]["c"]); c1 = float(bars[-1]["c"])
    buy = cm.buy_fill_price(c0); sell = cm.sell_fill_price(c1)
    ret = (sell - buy) / buy * 100.0
    # fp sharpe of the bar-to-bar buy&hold equity
    eq = [1.0]
    prev = None
    for b in bars:
        c = float(b["c"])
        if prev is not None and prev > 0:
            eq.append(eq[-1] * (c / prev))
        prev = c
    import math
    rets = [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]
    if len(rets) >= 2:
        m = sum(rets) / len(rets)
        v = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
        s = (m / math.sqrt(v)) * math.sqrt(bars_per_year("1Hour", False)) if v > 0 else 0.0
    else:
        s = 0.0
    return {"fp_sharpe": s, "ret_pct": ret}


def main():
    mod, params = load_live()
    base_decide = mod.decide
    gate = build_daily_sma_gate("SPY", 200)
    spy = load_1h("SPY")
    print(f"SPY 1Hour bars: {len(spy)}  {spy[0]['t']} -> {spy[-1]['t']}")
    print(f"live params: RSI<{params['oversold_threshold']} enter, "
          f">{params['exit_rsi']} exit, {params['time_stop_bars']}-bar stop, "
          f"notional={params['notional_usd']}")

    spans = {"full": (None, None), "is": (None, "2023-12-31"), "oos": (OOS_START, None)}
    arms = {
        "baseline_dipbuy": base_decide,
        "gated_sma200": make_gated(base_decide, gate, lag=0),
        "flip_momentum": make_flip(params),
    }
    res = {}
    for aname, dfn in arms.items():
        res[aname] = {}
        for sname, (s, e) in spans.items():
            sub = slice_by_day(spy, s, e)
            res[aname][sname] = run(aname, sub, dfn, params)
        r = res[aname]
        print(f"\n=== {aname} ===")
        for sname in ("full", "is", "oos"):
            x = r[sname]
            print(f"  {sname:4s}: fpS={x['fp_sharpe']:+.3f} ret={x['ret_pct']:7.2f}% "
                  f"trades={x['n_trades']:3d} maxDD={x['maxdd_pct']:6.2f}% win={x['win_rate']*100:4.1f}%")

    # canary: gated arm with daily SMA lagged +1 day (OOS)
    sub_oos = slice_by_day(spy, OOS_START, None)
    res["gated_sma200"]["canary_oos"] = run(
        "gated_canary", sub_oos, make_gated(base_decide, gate, lag=1), params)

    # benchmark
    res["spy_buyhold"] = {"full": spy_bh(spy, params),
                          "oos": spy_bh(sub_oos, params)}

    base = res["baseline_dipbuy"]
    bh = res["spy_buyhold"]
    print("\n\n===== VERDICT (vs live baseline dip-buy) =====")
    print(f"baseline_dipbuy: FULL fpS={base['full']['fp_sharpe']:+.3f} ret={base['full']['ret_pct']:.2f}%  |  OOS fpS={base['oos']['fp_sharpe']:+.3f} ret={base['oos']['ret_pct']:.2f}%")
    print(f"SPY buy&hold   : FULL fpS={bh['full']['fp_sharpe']:+.3f} ret={bh['full']['ret_pct']:.2f}%  |  OOS fpS={bh['oos']['fp_sharpe']:+.3f} ret={bh['oos']['ret_pct']:.2f}%  (dumb bar)")
    for aname in ("gated_sma200", "flip_momentum"):
        r = res[aname]
        d_oos = r["oos"]["fp_sharpe"] - base["oos"]["fp_sharpe"]
        d_full = r["full"]["fp_sharpe"] - base["full"]["fp_sharpe"]
        verdict = "BEATS baseline OOS" if d_oos > 0 else "does NOT beat baseline OOS"
        print(f"\n{aname}: {verdict}  (Δ_OOS fpS={d_oos:+.3f}, Δ_FULL fpS={d_full:+.3f})")
        if "canary_oos" in r:
            cd = r["oos"]["fp_sharpe"] - r["canary_oos"]["fp_sharpe"]
            print(f"  canary OOS fpS={r['canary_oos']['fp_sharpe']:+.3f} (drop {cd:+.3f}; robust={abs(cd)<=0.10})")

    json.dump(res, open("_holddip_results.json", "w"), indent=2, default=str)
    print("\nwrote _holddip_results.json")


if __name__ == "__main__":
    main()
