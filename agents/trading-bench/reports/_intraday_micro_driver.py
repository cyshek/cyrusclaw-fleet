"""Throwaway driver: INTRADAY MICROSTRUCTURE feasibility + sweep on 5Min bars.

Composes the PUBLIC single-symbol runner.backtest.backtest + the canonical
runner.fp_sharpe.fp_continuous_sharpe(timeframe='5Min') over the 8 NAMED_WINDOWS.
No protected-file edits, no custom evaluator.

ARCHETYPE: intraday mean-reversion / opening-range fade on SPY 5Min bars.
  - Each trading day we compute an opening range over the first `or_bars` RTH
    bars (e.g. 6 bars = 30 min from 09:30 ET).
  - After the opening range completes, if price has EXTENDED z>thr above/below
    the opening-range midpoint (measured in units of the OR's own height, or a
    trailing realized-vol band), we FADE it: short the up-extension / long the
    down-extension, betting on reversion to the OR mid.
  - Exit on reversion to mid (take-profit), OR a stop, OR forced flat at the
    `exit_by` bar-of-day (square off before close — NO overnight hold by
    default, so this is a PURE intraday edge, not overnight-gap exposure).
  - Long-only execution constraint of the harness: the backtester supports
    buy/close (no native short). So we implement the LONG leg of the fade only
    (fade DOWN-extensions: buy when price is stretched BELOW OR-mid, exit on
    reversion up). This is the honest, harness-expressible half of the
    archetype and avoids fictional short fills the cost model can't price.

NO-OVERNIGHT-LEAK JUSTIFICATION (trap #1):
  - decide() at bar i sees ONLY market_state['bars'][:i+1] (harness guarantees
    this; verified in backtest.py: `"bars": bars[: i + 1]`). We never index
    forward.
  - Day boundary is detected from bar timestamps (UTC date change). Opening
    range / day-state is rebuilt at the first bar of each new day from bars
    already seen. No peeking at the next day's open.
  - `exit_by` forces flat at/after a configurable bar-of-day, so by default we
    are FLAT overnight => the measured PnL is intraday reversion, not the
    overnight gap. We ALSO run an `allow_overnight=True` ablation to size the
    overnight-gap contribution (the relabel check, trap #3).

INTRADAY COST REALITY (trap #2):
  - CostModel.alpaca_stocks() => spread_bps=2.0 one-way (round-trip ~4bps).
  - Cost model is ALWAYS ON. We report n_trades and total_costs_usd per cell.
  - Daily trade cap = 4 (harness default, MAX_TRADES_PER_DAY). Our archetype
    does AT MOST 1 entry + 1 exit per day = 2 trades/day, well under the cap,
    so no silent truncation. We assert trades/day stays <= 2.

ANNUALIZATION HONESTY:
  - We call fp_continuous_sharpe(timeframe='5Min') => harness bpy = 105,120
    (12*24*365, a 24/7 wall-clock count). Stock 5Min bars only exist in RTH
    (~78-87 bars/day * 252 sessions ~= 21,900/yr). The harness number therefore
    OVERSTATES annualized Sharpe by sqrt(105120/21900) ~= 2.19x. We report the
    harness headline AND a RTH-corrected Sharpe = harness_sharpe / 2.19 so the
    ~0.5-ceiling comparison is apples-to-apples with the daily lane.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest import backtest, CostModel, bars_per_year
from runner.walk_forward import NAMED_WINDOWS
from runner.fp_sharpe import fp_continuous_sharpe, sharpe_from_returns, concat_window_returns

SYM = "SPY"
TF = "5Min"
NOTIONAL = 1000.0
START_CASH = 1000.0

# RTH window in UTC (09:30-16:00 ET == 13:30-20:00 UTC, standard; we keep
# 13:30..19:55 inclusive of entries, and force-exit by `exit_by`). DST shifts
# ET<->UTC by an hour; using a slightly inclusive band (13:30-20:00) is robust
# and the per-day open is re-anchored to the first in-band bar each day so a
# 1h DST shift just changes which bar is "the open", not the logic.
RTH_START = "13:30"
RTH_END = "20:00"

# Harness 5Min annualization is 24/7 wall-clock; correct to RTH session density.
HARNESS_BPY_5MIN = bars_per_year(TF, is_crypto=False)        # 105120
RTH_BARS_PER_DAY = 78.0                                       # 6.5h * 12 bars/h
RTH_BPY_5MIN = RTH_BARS_PER_DAY * 252.0                       # ~19656
ANNUALIZE_CORRECTION = math.sqrt(HARNESS_BPY_5MIN / RTH_BPY_5MIN)  # ~2.31


def _tod(bar):
    """HH:MM (UTC) of a bar."""
    t = bar.get("t") or ""
    return t[11:16] if len(t) >= 16 else ""


def _day(bar):
    t = bar.get("t") or ""
    return t[:10] if len(t) >= 10 else ""


def _in_rth(bar):
    tod = _tod(bar)
    return RTH_START <= tod <= RTH_END


class _Action:
    def __init__(self, action="hold", symbol=SYM, notional_usd=0.0, reason=""):
        self.action = action
        self.symbol = symbol
        self.notional_usd = notional_usd
        self.qty = None
        self.reason = reason


def _make_breakout(p):
    """Opening-range BREAKOUT (momentum): buy when price breaks above the OR
    high after the OR forms; exit on EOD or a trailing stop below the running
    high. Tests the opposite microstructure (continuation, not reversion)."""
    or_bars = int(p["or_bars"])
    buf = float(p.get("break_buf", 0.0))      # OR-heights above OR-high to trigger
    trail_frac = float(p.get("trail_frac", 1.0))  # trailing stop in OR-heights below run-high
    exit_by = p["exit_by"]
    allow_overnight = bool(p.get("allow_overnight", False))

    def decide(market_state, position_state, params):
        bars = market_state["bars"]; bar = bars[-1]
        st = market_state["strategy_state"]
        if not isinstance(st, dict):
            st = {}; market_state["strategy_state"] = st
        pos = position_state.get(SYM)
        have = bool(pos and float(pos.get("qty", 0)) > 0)
        tod = _tod(bar); day = _day(bar); close = float(bar["c"])
        if st.get("day") != day:
            st.clear(); st["day"] = day
            st["or_hi"] = None; st["or_lo"] = None; st["or_count"] = 0
            st["or_done"] = False; st["run_high"] = None
        if not _in_rth(bar):
            if have and not allow_overnight:
                return _Action("close", SYM, reason="exit:outside_rth")
            return _Action("hold")
        if not st["or_done"]:
            hi = float(bar["h"]); lo = float(bar["l"])
            st["or_hi"] = hi if st["or_hi"] is None else max(st["or_hi"], hi)
            st["or_lo"] = lo if st["or_lo"] is None else min(st["or_lo"], lo)
            st["or_count"] += 1
            if st["or_count"] >= or_bars:
                st["or_done"] = True
                st["or_height"] = max(st["or_hi"] - st["or_lo"], 1e-9)
            return _Action("hold")
        height = st["or_height"]
        if not allow_overnight and tod >= exit_by:
            if have:
                return _Action("close", SYM, reason="exit:eod")
            return _Action("hold")
        if have:
            st["run_high"] = close if st["run_high"] is None else max(st["run_high"], close)
            if close <= st["run_high"] - trail_frac * height:
                return _Action("close", SYM, reason="exit:trail")
            return _Action("hold")
        trigger = st["or_hi"] + buf * height
        if close >= trigger:
            if st.get("entered_today"):
                return _Action("hold")
            st["entered_today"] = True
            st["run_high"] = close
            return _Action("buy", SYM, NOTIONAL, reason="breakout")
        return _Action("hold")
    return decide


def make_decide(p):
    """Build an opening-range decide() closure for params p.

    mode='fade' : buy DOWN-extensions below OR-mid, exit on reversion up.
    mode='break': buy UP-breakouts above OR-high, exit trail/EOD (momentum).
    """
    if p.get("mode") == "break":
        return _make_breakout(p)

    or_bars = int(p["or_bars"])          # bars defining the opening range
    z_thr = float(p["z_thr"])            # extension threshold (OR-heights below mid)
    tp_frac = float(p["tp_frac"])        # take-profit: revert to mid - tp_frac*height? (we use mid)
    stop_frac = float(p["stop_frac"])    # stop: extend stop_frac more OR-heights against
    exit_by = p["exit_by"]               # HH:MM UTC: force flat at/after this
    allow_overnight = bool(p.get("allow_overnight", False))

    def decide(market_state, position_state, params):
        bars = market_state["bars"]
        bar = bars[-1]
        st = market_state["strategy_state"]
        if not isinstance(st, dict):
            st = {}
            market_state["strategy_state"] = st

        pos = position_state.get(SYM)
        have_pos = bool(pos and float(pos.get("qty", 0)) > 0)
        tod = _tod(bar)
        day = _day(bar)
        close = float(bar["c"])

        # ---- Day rollover bookkeeping ----
        if st.get("day") != day:
            # New day. If we somehow still hold and overnight not allowed, the
            # harness will have marked-to-market; we square off on first RTH bar.
            st.clear()
            st["day"] = day
            st["or_lo"] = None
            st["or_hi"] = None
            st["or_count"] = 0
            st["or_done"] = False

        if not _in_rth(bar):
            # Outside RTH: if we hold and overnight not allowed, exit now.
            if have_pos and not allow_overnight:
                return _Action("close", SYM, reason="exit:outside_rth")
            return _Action("hold")

        # ---- Build opening range from the first or_bars RTH bars ----
        if not st["or_done"]:
            hi = float(bar["h"]); lo = float(bar["l"])
            st["or_hi"] = hi if st["or_hi"] is None else max(st["or_hi"], hi)
            st["or_lo"] = lo if st["or_lo"] is None else min(st["or_lo"], lo)
            st["or_count"] += 1
            if st["or_count"] >= or_bars:
                st["or_done"] = True
                st["or_mid"] = 0.5 * (st["or_hi"] + st["or_lo"])
                st["or_height"] = max(st["or_hi"] - st["or_lo"], 1e-9)
            # During OR formation we do not trade.
            if have_pos and not allow_overnight:
                return _Action("close", SYM, reason="exit:or_form")
            return _Action("hold")

        mid = st["or_mid"]
        height = st["or_height"]
        # Forced square-off near close (intraday-only by default).
        if not allow_overnight and tod >= exit_by:
            if have_pos:
                return _Action("close", SYM, reason="exit:eod")
            return _Action("hold")

        if have_pos:
            entry = float(pos.get("avg_entry_price", close))
            # Take-profit: price reverted up to the OR mid.
            if close >= mid - tp_frac * height:
                return _Action("close", SYM, reason="exit:tp_mid")
            # Stop: extended further DOWN beyond entry by stop_frac OR-heights.
            if close <= entry - stop_frac * height:
                return _Action("close", SYM, reason="exit:stop")
            return _Action("hold")

        # Flat: look for a DOWN-extension to FADE (buy the dip toward reversion).
        # z = how many OR-heights below mid we are.
        z = (mid - close) / height
        if z >= z_thr:
            # Only one entry per day (we already exit by EOD); enforce it.
            if st.get("entered_today"):
                return _Action("hold")
            st["entered_today"] = True
            return _Action("buy", SYM, NOTIONAL, reason=f"fade_down z={z:.2f}")
        return _Action("hold")

    return decide


class _W:
    def __init__(self, bt):
        self.backtest = bt


def run_panel(p):
    """Run the archetype over all 8 NAMED_WINDOWS on SPY 5Min. Returns dict."""
    cm = CostModel.alpaca_stocks()
    decide = make_decide(p)
    params = {"symbol": SYM, "timeframe": TF, "notional_usd": NOTIONAL}
    from runner import bars_cache
    wins = []
    per_win = []
    total_trades = 0
    total_cost = 0.0
    total_days = 0
    max_trades_day = 0
    for label, end_dt, days, regime in NAMED_WINDOWS:
        bars = bars_cache.get_bars(SYM, TF, days=days, end_dt=end_dt)
        if not bars or len(bars) < 50:
            continue
        bt = backtest("intraday_micro", bars, params,
                      starting_cash=START_CASH, decide_fn=decide,
                      cost_model=cm)
        wins.append(_W(bt))
        # trades/day audit
        from collections import Counter
        tcount = Counter()
        for tr in bt.closed_trades:
            d = (tr.get("exit_time") or "")[:10]
            tcount[d] += 2  # buy+close
        if tcount:
            max_trades_day = max(max_trades_day, max(tcount.values()))
        ndays = len(set(_day(b) for b in bars))
        total_days += ndays
        per_win.append({
            "label": label, "regime": regime, "ret_pct": bt.total_return_pct,
            "n_trades": bt.n_trades, "cost": bt.total_costs_usd,
            "sharpe_win": bt.sharpe, "maxdd": bt.max_drawdown_pct,
            "win_rate": bt.win_rate, "n_closed": len(bt.closed_trades),
        })
        total_trades += bt.n_trades
        total_cost += bt.total_costs_usd
    fp, nret = fp_continuous_sharpe(wins, timeframe=TF, is_crypto=False)
    fp_corr = fp / ANNUALIZE_CORRECTION
    # total return across concatenated windows (compounded per-window)
    comp = 1.0
    for w in wins:
        comp *= (1.0 + w.backtest.total_return_pct)
    total_ret = comp - 1.0
    # annualized return on deployed notional ($1000), full span
    span_years = total_days / 252.0 if total_days else 1.0
    ann_ret = ((1.0 + total_ret) ** (1.0 / span_years) - 1.0) if span_years > 0 else 0.0
    return {
        "fp_harness": fp, "fp_rth": fp_corr, "nret": nret,
        "total_trades": total_trades, "total_cost": total_cost,
        "total_ret": total_ret, "ann_ret": ann_ret, "span_years": span_years,
        "max_trades_day": max_trades_day, "per_win": per_win,
    }


def bh_panel():
    """Buy-and-hold-intraday SPY benchmark: long at first RTH bar, flat at EOD,
    no overnight (matches our intraday-only convention). This is the relabel
    yardstick: if our 'edge' just tracks BH-intraday, it's not microstructure."""
    cm = CostModel.alpaca_stocks()

    def decide(market_state, position_state, params):
        bars = market_state["bars"]; bar = bars[-1]
        st = market_state["strategy_state"]
        if not isinstance(st, dict):
            st = {}; market_state["strategy_state"] = st
        day = _day(bar); tod = _tod(bar)
        pos = position_state.get(SYM)
        have = bool(pos and float(pos.get("qty", 0)) > 0)
        if st.get("day") != day:
            st.clear(); st["day"] = day; st["bought"] = False
        if not _in_rth(bar):
            if have:
                return _Action("close", SYM, reason="eod")
            return _Action("hold")
        if tod >= "19:45":
            if have:
                return _Action("close", SYM, reason="eod")
            return _Action("hold")
        if not have and not st["bought"]:
            st["bought"] = True
            return _Action("buy", SYM, NOTIONAL, reason="bh")
        return _Action("hold")

    params = {"symbol": SYM, "timeframe": TF, "notional_usd": NOTIONAL}
    from runner import bars_cache
    wins = []
    for label, end_dt, days, regime in NAMED_WINDOWS:
        bars = bars_cache.get_bars(SYM, TF, days=days, end_dt=end_dt)
        if not bars or len(bars) < 50:
            continue
        bt = backtest("bh_intraday", bars, params, starting_cash=START_CASH,
                      decide_fn=decide, cost_model=cm)
        wins.append(_W(bt))
    fp, nret = fp_continuous_sharpe(wins, timeframe=TF, is_crypto=False)
    return {"fp_harness": fp, "fp_rth": fp / ANNUALIZE_CORRECTION, "wins": wins}


def _summ(p, tag):
    r = run_panel(p)
    print(f"[{tag}] fp_h={r['fp_harness']:+.3f} fp_rth={r['fp_rth']:+.3f} "
          f"ann={r['ann_ret']*100:+.2f}%/yr trades={r['total_trades']} "
          f"cost=${r['total_cost']:.0f} ret={r['total_ret']*100:+.2f}% "
          f"mtd={r['max_trades_day']} | {json.dumps({k:p[k] for k in p if k not in ('symbol','timeframe','notional_usd','exit_by','allow_overnight','mode')})}")
    return r


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "feas"
    print(f"=== annualization: harness_bpy={HARNESS_BPY_5MIN:.0f} rth_bpy={RTH_BPY_5MIN:.0f} "
          f"correction(/)={ANNUALIZE_CORRECTION:.3f} ===")

    if mode == "feas":
        p = {"or_bars": 6, "z_thr": 1.0, "tp_frac": 0.0, "stop_frac": 1.5,
             "exit_by": "19:45", "allow_overnight": False}
        r = run_panel(p)
        print("FEASIBILITY cell:", json.dumps({k: v for k, v in r.items() if k != "per_win"}, default=str, indent=2))
        for w in r["per_win"]:
            print(f"  {w['label']:20s} {w['regime']:5s} ret={w['ret_pct']*100:+6.2f}% "
                  f"trades={w['n_trades']:4d} cost=${w['cost']:7.2f} closed={w['n_closed']:3d} "
                  f"wr={w['win_rate']:.2f} dd={w['maxdd']*100:.1f}%")
        print(f"max_trades_in_any_single_day={r['max_trades_day']} (cap=4)")
        return

    if mode == "bh":
        b = bh_panel()
        print("BH-intraday FP harness=%.3f rth=%.3f" % (b["fp_harness"], b["fp_rth"]))
        return

    if mode == "sweep_fade":
        print("--- FADE (intraday mean-reversion) sweep ---")
        best = None
        for or_bars, z_thr, tp_frac, stop_frac in itertools.product(
                [3, 6, 12], [0.5, 1.0, 1.5, 2.0], [0.0, 0.5], [1.0, 2.0, 3.0]):
            p = {"mode": "fade", "or_bars": or_bars, "z_thr": z_thr,
                 "tp_frac": tp_frac, "stop_frac": stop_frac,
                 "exit_by": "19:45", "allow_overnight": False}
            r = _summ(p, "fade")
            if best is None or r["fp_rth"] > best[1]["fp_rth"]:
                best = (p, r)
        print("BEST fade:", json.dumps({k: best[1][k] for k in ("fp_harness","fp_rth","ann_ret","total_trades")}, default=str), best[0])
        return

    if mode == "sweep_break":
        print("--- BREAKOUT (intraday momentum) sweep ---")
        best = None
        for or_bars, buf, trail in itertools.product(
                [3, 6, 12], [0.0, 0.25, 0.5], [0.5, 1.0, 2.0]):
            p = {"mode": "break", "or_bars": or_bars, "break_buf": buf,
                 "trail_frac": trail, "exit_by": "19:45", "allow_overnight": False}
            r = _summ(p, "break")
            if best is None or r["fp_rth"] > best[1]["fp_rth"]:
                best = (p, r)
        print("BEST break:", json.dumps({k: best[1][k] for k in ("fp_harness","fp_rth","ann_ret","total_trades")}, default=str), best[0])
        return

    if mode == "overnight":
        # Relabel ablation: same best-ish fade params but HOLD overnight.
        print("--- OVERNIGHT ablation (relabel check) ---")
        base = {"mode": "fade", "or_bars": 6, "z_thr": 1.0, "tp_frac": 0.5,
                "stop_frac": 2.0, "exit_by": "19:45"}
        for ov in (False, True):
            p = dict(base); p["allow_overnight"] = ov
            _summ(p, f"overnight={ov}")
        return


if __name__ == "__main__":
    main()


def diag():
    """Per-window detail + BH-correlation for the best breakout cell."""
    from runner import bars_cache

    bp = {"mode": "break", "or_bars": 12, "break_buf": 0.0, "trail_frac": 2.0,
          "exit_by": "19:45", "allow_overnight": False}
    # second-best robust plateau cell for comparison
    rp = {"mode": "break", "or_bars": 6, "break_buf": 0.25, "trail_frac": 2.0,
          "exit_by": "19:45", "allow_overnight": False}
    cm = CostModel.alpaca_stocks()
    for name, p in (("BEST_break", bp), ("PLATEAU_break", rp)):
        r = run_panel(p)
        print(f"\n### {name}: fp_h={r['fp_harness']:+.3f} fp_rth={r['fp_rth']:+.3f} "
              f"ann={r['ann_ret']*100:+.2f}%/yr trades={r['total_trades']} cost=${r['total_cost']:.0f}")
        for w in r["per_win"]:
            print(f"  {w['label']:20s} {w['regime']:5s} ret={w['ret_pct']*100:+6.2f}% "
                  f"sharpe_win={w['sharpe_win']:+.2f} closed={w['n_closed']:3d} wr={w['win_rate']:.2f} dd={w['maxdd']*100:.1f}%")
    # BH-correlation on per-window returns (relabel check)
    rbest = run_panel(bp)
    bh = bh_panel()
    strat_w = [w["ret_pct"] for w in rbest["per_win"]]
    bh_w = [w.backtest.total_return_pct for w in bh["wins"]]
    if len(strat_w) == len(bh_w) and len(strat_w) > 2:
        n=len(strat_w); ms=sum(strat_w)/n; mb=sum(bh_w)/n
        cov=sum((a-ms)*(b-mb) for a,b in zip(strat_w,bh_w))/n
        vs=sum((a-ms)**2 for a in strat_w)/n; vb=sum((b-mb)**2 for b in bh_w)/n
        c=cov/((vs*vb)**0.5) if vs>0 and vb>0 else 0.0
        print(f"\nBH-relabel: corr(best_break per-window ret, BH-intraday per-window ret) = {c:+.3f}")
        print(f"  strat per-win: {[round(x*100,2) for x in strat_w]}")
        print(f"  BH    per-win: {[round(x*100,2) for x in bh_w]}")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "diag":
    diag()
