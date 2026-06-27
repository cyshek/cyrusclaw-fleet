"""DETERMINISTIC cross-symbol combo sprint driver.

Question: does fusing the WEAK-orthogonal momentum parent macd_momentum_iwm
(IWM, MACD 12/26/9) with the STRONG breakout parents breakout_xlk (XLK) and
volume_breakout_qqq (QQQ) produce a child that beats the BEST solo parent on
risk-adjusted edge (full-period continuous-span Sharpe), OUT-OF-SAMPLE, net of
2 bps one-way cost?

AND-fusion: enter P only when P's breakout fires AND IWM-MACD bullish (gate).
OR-fusion : enter P when P's breakout fires OR IWM-MACD bullish (union).

Honesty rails:
  - Cross-symbol alignment via INNER-JOIN on bar timestamps.
  - Gate state at panel bar T = IWM-MACD bull from the IWM bar that CLOSED
    at-or-before T, then lagged one IWM bar (D+1-lag). No same-bar leak.
  - CANARY: +1 extra bar of lag; a real edge survives, a leak dies.
  - Sharpe = full-period continuous-span (engine per-bar equity-return Sharpe on
    each contiguous slice), annualized bars_per_year("1Hour", False)=2142.

Reuses runner.backtest.backtest(...) so cost/fill/Sharpe MATCH the bench.
Reads runner/ + strategies/ + .cache/ only. Writes ONLY reports/. No orders.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import bars_cache
from runner.backtest import backtest, CostModel, bars_per_year
from strategies._lib.indicators import closes, highest, lowest

# --- perf: short-circuit the engine's internal SPY/1Day regime pre-fetch ---
# Our reconstructed strategies do NOT read market_state['regime']; the engine's
# SPY pre-fetch + per-bar linear scan is pure dead overhead here (O(n^2) across
# ~22 runs on a 12k-bar series). We wrap bars_cache.get_bars so a SPY 1Day call
# returns [] (engine then sets regime_state=None -> identical to the crypto
# path). All other fetches (our IWM/XLK/QQQ 1Hour) pass through UNCHANGED, so
# every result number is bit-for-bit what the engine would produce anyway.
import runner.backtest as _bt_mod
_ORIG_GET_BARS = _bt_mod.bars_cache.get_bars
def _patched_get_bars(symbol, timeframe, days, *a, **k):
    if symbol == 'SPY' and timeframe == '1Day':
        return []
    return _ORIG_GET_BARS(symbol, timeframe, days, *a, **k)
_bt_mod.bars_cache.get_bars = _patched_get_bars

END_DT = datetime(2026, 6, 25, tzinfo=timezone.utc)
DAYS = 2600

IS_START = "2020-07-27"
IS_END = "2023-12-31"
OOS_START = "2024-01-01"
OOS_END = "2026-06-24"

BARS_PER_YEAR = bars_per_year("1Hour", False)

BREAKOUT_XLK_PARAMS = json.loads(
    (WORKSPACE / "strategies" / "breakout_xlk" / "params.json").read_text())
VOLBREAK_QQQ_PARAMS = json.loads(
    (WORKSPACE / "strategies" / "volume_breakout_qqq" / "params.json").read_text())
MACD_IWM_PARAMS = json.loads(
    (WORKSPACE / "strategies" / "macd_momentum_iwm" / "params.json").read_text())


def _ema_series(values, period):
    if len(values) < period:
        return []
    alpha = 2.0 / (period + 1.0)
    ema = [sum(values[:period]) / period]
    for val in values[period:]:
        ema.append(alpha * val + (1.0 - alpha) * ema[-1])
    return ema


def macd_bull_state_per_iwm_bar(iwm_bars, fast=12, slow=26, signal=9):
    cs = closes(iwm_bars)
    n = len(cs)
    state = [None] * n
    ema_fast_full = _ema_series(cs, fast)
    ema_slow_full = _ema_series(cs, slow)
    if not ema_fast_full or not ema_slow_full:
        return state
    macd_line_by_absidx = {}
    for j in range(slow - 1, n):
        ef = ema_fast_full[j - (fast - 1)]
        es = ema_slow_full[j - (slow - 1)]
        macd_line_by_absidx[j] = ef - es
    macd_absidxs = sorted(macd_line_by_absidx.keys())
    macd_seq = [macd_line_by_absidx[j] for j in macd_absidxs]
    sig_seq = _ema_series(macd_seq, signal)
    if not sig_seq:
        return state
    for k, sv in enumerate(sig_seq):
        pos = (signal - 1) + k
        if pos >= len(macd_absidxs):
            break
        j = macd_absidxs[pos]
        mv = macd_seq[pos]
        state[j] = (mv > sv) and (mv > 0.0)
    return state


def build_gate_lookup(panel_ts, iwm_bars, iwm_bull_state, extra_lag=0):
    iwm_ts = [b["t"] for b in iwm_bars]
    n_iwm = len(iwm_ts)
    gate = {}
    j = 0
    for T in panel_ts:
        while j + 1 < n_iwm and iwm_ts[j + 1] <= T:
            j += 1
        if iwm_ts[j] > T:
            gate[T] = None
            continue
        lag = 1 + extra_lag
        src = j - lag
        gate[T] = iwm_bull_state[src] if src >= 0 else None
    return gate


class _Act:
    __slots__ = ("action", "symbol", "notional_usd", "qty", "reason")

    def __init__(self, action, symbol, notional_usd=0.0):
        self.action = action
        self.symbol = symbol
        self.notional_usd = notional_usd
        self.qty = None
        self.reason = ""


def _mk_action(action, symbol, notional_usd=0.0):
    return _Act(action, symbol, notional_usd)


def _macd_now(values, fast, slow, signal):
    if len(values) < slow + signal:
        return (None, None)
    ef = _ema_series(values, fast)
    es = _ema_series(values, slow)
    if not ef or not es:
        return (None, None)
    nf, ns = len(ef), len(es)
    mn = min(nf, ns)
    macd_line = [ef[nf - mn + i] - es[ns - mn + i] for i in range(mn)]
    if len(macd_line) < signal:
        return (None, None)
    sig = _ema_series(macd_line, signal)
    if not sig:
        return (None, None)
    return (macd_line[-1], sig[-1])


def make_breakout_solo_decide():
    def decide(market_state, position_state, params):
        sym = params.get("symbol")
        lookback = int(params.get("lookback", 20))
        notional = float(params.get("notional_usd", 100.0))
        cs = closes(market_state.get("bars") or [])
        if len(cs) < lookback + 1:
            return _mk_action("hold", sym)
        last = cs[-1]
        hi = highest(cs[:-1], lookback)
        lo = lowest(cs[:-1], lookback)
        pos = position_state.get(sym)
        holding = float(pos.get("qty", 0)) if pos else 0.0
        if hi is not None and last > hi and holding == 0:
            return _mk_action("buy", sym, notional)
        if lo is not None and last < lo and holding > 0:
            return _mk_action("close", sym)
        return _mk_action("hold", sym)
    return decide


def make_volbreak_solo_decide():
    def decide(market_state, position_state, params):
        sym = params.get("symbol")
        lookback = int(params.get("lookback", 20))
        exit_lb = int(params.get("exit_lookback", 10))
        vmult = float(params.get("volume_mult", 1.5))
        notional = float(params.get("notional_usd", 100.0))
        bars = market_state.get("bars") or []
        cs = closes(bars)
        vs = [float(b.get("v", 0)) for b in bars]
        if len(cs) < lookback + 1:
            return _mk_action("hold", sym)
        last_close = cs[-1]
        last_vol = vs[-1]
        hi = highest(cs[:-1], lookback)
        lo = lowest(cs[:-1], exit_lb)
        prev_vs = vs[:-1]
        avg_vol = (sum(prev_vs[-lookback:]) / lookback) if len(prev_vs) >= lookback else None
        pos = position_state.get(sym)
        holding = float(pos.get("qty", 0)) if pos else 0.0
        if hi is None or avg_vol is None:
            return _mk_action("hold", sym)
        if holding == 0:
            if last_close > hi and last_vol > avg_vol * vmult:
                return _mk_action("buy", sym, notional)
            return _mk_action("hold", sym)
        if holding > 0:
            if lo is not None and last_close < lo:
                return _mk_action("close", sym)
            return _mk_action("hold", sym)
        return _mk_action("hold", sym)
    return decide


def make_macd_solo_decide():
    def decide(market_state, position_state, params):
        sym = params.get("symbol")
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        notional = float(params.get("notional_usd", 100.0))
        cs = closes(market_state.get("bars") or [])
        mv, sv = _macd_now(cs, fast, slow, signal)
        st = market_state.get("strategy_state")
        if not isinstance(st, dict):
            st = {}
        market_state["strategy_state"] = st
        if mv is None:
            return _mk_action("hold", sym)
        pos = position_state.get(sym)
        holding = float(pos.get("qty", 0)) if pos else 0.0
        pm = st.get("_pm")
        ps = st.get("_ps")
        st["_pm"] = mv
        st["_ps"] = sv
        if holding == 0:
            crossed_above = (pm is not None and ps is not None and pm <= ps and mv > sv)
            if crossed_above and mv > 0:
                return _mk_action("buy", sym, notional)
            return _mk_action("hold", sym)
        if holding > 0:
            crossed_below = (pm is not None and ps is not None and pm >= ps and mv < sv)
            if crossed_below:
                return _mk_action("close", sym)
            return _mk_action("hold", sym)
        return _mk_action("hold", sym)
    return decide


def make_breakout_fusion_decide(gate_lookup, mode):
    def decide(market_state, position_state, params):
        sym = params.get("symbol")
        lookback = int(params.get("lookback", 20))
        notional = float(params.get("notional_usd", 100.0))
        bars = market_state.get("bars") or []
        cs = closes(bars)
        if len(cs) < lookback + 1:
            return _mk_action("hold", sym)
        last = cs[-1]
        T = bars[-1].get("t")
        hi = highest(cs[:-1], lookback)
        lo = lowest(cs[:-1], lookback)
        breakout_entry = (hi is not None and last > hi)
        breakout_exit_flat = (lo is not None and last < lo)
        gate_bull = bool(gate_lookup.get(T) is True)
        pos = position_state.get(sym)
        holding = float(pos.get("qty", 0)) if pos else 0.0
        if holding == 0:
            if mode == "and":
                if breakout_entry and gate_bull:
                    return _mk_action("buy", sym, notional)
            else:
                if breakout_entry or gate_bull:
                    return _mk_action("buy", sym, notional)
            return _mk_action("hold", sym)
        if holding > 0:
            if mode == "and":
                if breakout_exit_flat:
                    return _mk_action("close", sym)
            else:
                if breakout_exit_flat and (not gate_bull):
                    return _mk_action("close", sym)
            return _mk_action("hold", sym)
        return _mk_action("hold", sym)
    return decide


def make_volbreak_fusion_decide(gate_lookup, mode):
    def decide(market_state, position_state, params):
        sym = params.get("symbol")
        lookback = int(params.get("lookback", 20))
        exit_lb = int(params.get("exit_lookback", 10))
        vmult = float(params.get("volume_mult", 1.5))
        notional = float(params.get("notional_usd", 100.0))
        bars = market_state.get("bars") or []
        cs = closes(bars)
        vs = [float(b.get("v", 0)) for b in bars]
        if len(cs) < lookback + 1:
            return _mk_action("hold", sym)
        last_close = cs[-1]
        last_vol = vs[-1]
        T = bars[-1].get("t")
        hi = highest(cs[:-1], lookback)
        lo = lowest(cs[:-1], exit_lb)
        prev_vs = vs[:-1]
        avg_vol = (sum(prev_vs[-lookback:]) / lookback) if len(prev_vs) >= lookback else None
        breakout_entry = (hi is not None and avg_vol is not None and last_close > hi and last_vol > avg_vol * vmult)
        breakout_exit_flat = (lo is not None and last_close < lo)
        gate_bull = bool(gate_lookup.get(T) is True)
        pos = position_state.get(sym)
        holding = float(pos.get("qty", 0)) if pos else 0.0
        if holding == 0:
            if mode == "and":
                if breakout_entry and gate_bull:
                    return _mk_action("buy", sym, notional)
            else:
                if breakout_entry or gate_bull:
                    return _mk_action("buy", sym, notional)
            return _mk_action("hold", sym)
        if holding > 0:
            if mode == "and":
                if breakout_exit_flat:
                    return _mk_action("close", sym)
            else:
                if breakout_exit_flat and (not gate_bull):
                    return _mk_action("close", sym)
            return _mk_action("hold", sym)
        return _mk_action("hold", sym)
    return decide


def _slice(bars, start, end):
    return [b for b in bars if start <= b["t"][:10] <= end]


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return s[n // 2]
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


def _summ(res):
    trade_rets = [t["pnl_pct"] for t in res.closed_trades]
    return {
        "sharpe": round(res.sharpe, 4),
        "total_return_pct": round(res.total_return_pct * 100, 4),
        "max_dd_pct": round(res.max_drawdown_pct * 100, 4),
        "n_trades": res.n_trades,
        "n_closes": res.n_closes,
        "n_bars": res.n_bars,
        "win_rate": round(res.win_rate * 100, 2),
        "median_trade_ret_pct": round(_median(trade_rets) * 100, 4),
        "total_costs_usd": round(res.total_costs_usd, 4),
    }


def run_cfg(label, bars, params, decide_fn, cost_bps):
    cm = CostModel(spread_bps=cost_bps, fee_bps=0.0)
    res = backtest(label, bars, params, decide_fn=decide_fn, cost_model=cm)
    return _summ(res)


def main():
    iwm_bars = bars_cache.get_bars("IWM", "1Hour", days=DAYS, end_dt=END_DT)
    xlk_bars = bars_cache.get_bars("XLK", "1Hour", days=DAYS, end_dt=END_DT)
    qqq_bars = bars_cache.get_bars("QQQ", "1Hour", days=DAYS, end_dt=END_DT)

    iwm_bull = macd_bull_state_per_iwm_bar(
        iwm_bars, fast=int(MACD_IWM_PARAMS.get("fast", 12)),
        slow=int(MACD_IWM_PARAMS.get("slow", 26)),
        signal=int(MACD_IWM_PARAMS.get("signal", 9)))

    iwm_ts_set = set(b["t"] for b in iwm_bars)
    xlk_panel = [b for b in xlk_bars if b["t"] in iwm_ts_set]
    qqq_panel = [b for b in qqq_bars if b["t"] in iwm_ts_set]

    xlk_ts = [b["t"] for b in xlk_panel]
    qqq_ts = [b["t"] for b in qqq_panel]

    gate_xlk = build_gate_lookup(xlk_ts, iwm_bars, iwm_bull, extra_lag=0)
    gate_qqq = build_gate_lookup(qqq_ts, iwm_bars, iwm_bull, extra_lag=0)
    gate_xlk_canary = build_gate_lookup(xlk_ts, iwm_bars, iwm_bull, extra_lag=1)
    gate_qqq_canary = build_gate_lookup(qqq_ts, iwm_bars, iwm_bull, extra_lag=1)

    iwm_is = _slice(iwm_bars, IS_START, IS_END)
    iwm_oos = _slice(iwm_bars, OOS_START, OOS_END)
    xlk_native_is = _slice(xlk_bars, IS_START, IS_END)
    xlk_native_oos = _slice(xlk_bars, OOS_START, OOS_END)
    qqq_native_is = _slice(qqq_bars, IS_START, IS_END)
    qqq_native_oos = _slice(qqq_bars, OOS_START, OOS_END)

    xlk_panel_is = _slice(xlk_panel, IS_START, IS_END)
    xlk_panel_oos = _slice(xlk_panel, OOS_START, OOS_END)
    qqq_panel_is = _slice(qqq_panel, IS_START, IS_END)
    qqq_panel_oos = _slice(qqq_panel, OOS_START, OOS_END)

    breakout_solo = make_breakout_solo_decide()
    volbreak_solo = make_volbreak_solo_decide()
    macd_solo = make_macd_solo_decide()

    results = {}

    def add(name, full_bars, is_bars, oos_bars, params, decide_fn, cost_bps=2.0):
        results[name] = {
            "full": run_cfg(name + ":full", full_bars, params, decide_fn, cost_bps),
            "is": run_cfg(name + ":is", is_bars, params, decide_fn, cost_bps),
            "oos": run_cfg(name + ":oos", oos_bars, params, decide_fn, cost_bps),
            "cost_bps": cost_bps,
        }

    # TEST 1: solo baselines (native = sanity vs WF; panel = apples-to-apples)
    add("breakout_xlk_native", xlk_bars, xlk_native_is, xlk_native_oos, BREAKOUT_XLK_PARAMS, breakout_solo)
    add("volume_breakout_qqq_native", qqq_bars, qqq_native_is, qqq_native_oos, VOLBREAK_QQQ_PARAMS, volbreak_solo)
    add("macd_momentum_iwm_native", iwm_bars, iwm_is, iwm_oos, MACD_IWM_PARAMS, macd_solo)
    add("breakout_xlk_panel", xlk_panel, xlk_panel_is, xlk_panel_oos, BREAKOUT_XLK_PARAMS, breakout_solo)
    add("volume_breakout_qqq_panel", qqq_panel, qqq_panel_is, qqq_panel_oos, VOLBREAK_QQQ_PARAMS, volbreak_solo)

    # TEST 2: AND-fusion
    add("AND_xlk_gated_by_iwm", xlk_panel, xlk_panel_is, xlk_panel_oos,
        BREAKOUT_XLK_PARAMS, make_breakout_fusion_decide(gate_xlk, "and"))
    add("AND_qqq_gated_by_iwm", qqq_panel, qqq_panel_is, qqq_panel_oos,
        VOLBREAK_QQQ_PARAMS, make_volbreak_fusion_decide(gate_qqq, "and"))

    # TEST 3: OR-fusion
    add("OR_xlk_union_iwm", xlk_panel, xlk_panel_is, xlk_panel_oos,
        BREAKOUT_XLK_PARAMS, make_breakout_fusion_decide(gate_xlk, "or"))
    add("OR_qqq_union_iwm", qqq_panel, qqq_panel_is, qqq_panel_oos,
        VOLBREAK_QQQ_PARAMS, make_volbreak_fusion_decide(gate_qqq, "or"))

    # TEST 4: CANARY (+1 bar lag) on AND-fusion
    add("CANARY_AND_xlk_gated_by_iwm", xlk_panel, xlk_panel_is, xlk_panel_oos,
        BREAKOUT_XLK_PARAMS, make_breakout_fusion_decide(gate_xlk_canary, "and"))
    add("CANARY_AND_qqq_gated_by_iwm", qqq_panel, qqq_panel_is, qqq_panel_oos,
        VOLBREAK_QQQ_PARAMS, make_volbreak_fusion_decide(gate_qqq_canary, "and"))

    # TEST 5: cost sensitivity 0/2/5 bps (panel parent OOS + AND child OOS)
    cost_sens = {}
    for cb in (0.0, 2.0, 5.0):
        key = str(cb) + "bps"
        cost_sens[key] = {
            "breakout_xlk_panel_oos": run_cfg("cs", xlk_panel_oos, BREAKOUT_XLK_PARAMS, breakout_solo, cb),
            "AND_xlk_gated_oos": run_cfg("cs", xlk_panel_oos, BREAKOUT_XLK_PARAMS, make_breakout_fusion_decide(gate_xlk, "and"), cb),
            "volume_breakout_qqq_panel_oos": run_cfg("cs", qqq_panel_oos, VOLBREAK_QQQ_PARAMS, volbreak_solo, cb),
            "AND_qqq_gated_oos": run_cfg("cs", qqq_panel_oos, VOLBREAK_QQQ_PARAMS, make_volbreak_fusion_decide(gate_qqq, "and"), cb),
        }

    # gate diagnostics: fraction of panel bars where gate bull True
    def gate_frac(gl):
        vals = [v for v in gl.values()]
        n = len(vals)
        t = sum(1
 for v in vals if v is True)
        return round(t / n, 4) if n else 0.0

    diagnostics = {
        "gate_xlk_bull_frac": gate_frac(gate_xlk),
        "gate_qqq_bull_frac": gate_frac(gate_qqq),
        "n_iwm_bars": len(iwm_bars),
        "n_xlk_native": len(xlk_bars),
        "n_qqq_native": len(qqq_bars),
        "n_xlk_panel": len(xlk_panel),
        "n_qqq_panel": len(qqq_panel),
        "panel_first_ts": xlk_ts[0] if xlk_ts else None,
        "panel_last_ts": xlk_ts[-1] if xlk_ts else None,
    }

    # ---- GATE evaluation vs best solo parent (panel, OOS, 2bps) ----
    def beats(child_name, parent_name):
        c = results[child_name]["oos"]
        p = results[parent_name]["oos"]
        d_sharpe = round(c["sharpe"] - p["sharpe"], 4)
        d_medtrade = round(c["median_trade_ret_pct"] - p["median_trade_ret_pct"], 4)
        return {
            "child": child_name,
            "parent": parent_name,
            "child_oos_sharpe": c["sharpe"],
            "parent_oos_sharpe": p["sharpe"],
            "delta_sharpe": d_sharpe,
            "child_oos_medtrade_pct": c["median_trade_ret_pct"],
            "parent_oos_medtrade_pct": p["median_trade_ret_pct"],
            "delta_medtrade_pct": d_medtrade,
            "child_n_trades": c["n_trades"],
            "parent_n_trades": p["n_trades"],
            "promotes_sharpe_gt_parent": d_sharpe > 0.0,
            "promotes_medtrade_ge_0.10pp": d_medtrade >= 0.10,
        }

    gate_eval = {
        "AND_xlk_vs_breakout_xlk_panel": beats("AND_xlk_gated_by_iwm", "breakout_xlk_panel"),
        "AND_qqq_vs_volbreak_qqq_panel": beats("AND_qqq_gated_by_iwm", "volume_breakout_qqq_panel"),
        "OR_xlk_vs_breakout_xlk_panel": beats("OR_xlk_union_iwm", "breakout_xlk_panel"),
        "OR_qqq_vs_volbreak_qqq_panel": beats("OR_qqq_union_iwm", "volume_breakout_qqq_panel"),
        "CANARY_AND_xlk_vs_breakout_xlk_panel": beats("CANARY_AND_xlk_gated_by_iwm", "breakout_xlk_panel"),
        "CANARY_AND_qqq_vs_volbreak_qqq_panel": beats("CANARY_AND_qqq_gated_by_iwm", "volume_breakout_qqq_panel"),
    }

    out = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ"),
            "split": {"is": [IS_START, IS_END], "oos": [OOS_START, OOS_END]},
            "split_note": "DATA REALITY ADAPTATION: hourly floor 2020-07-27 makes the standard 2018 IS/OOS split impossible. Deepest honest split used.",
            "bars_per_year_1Hour_equity": BARS_PER_YEAR,
            "cost_model": "CostModel(spread_bps=2,fee_bps=0) == 2bps one-way (bench alpaca_stocks std); 0/5 sensitivity also run",
            "alignment": "INNER-JOIN on bar timestamps; gate = IWM-MACD bull (MACD>signal AND MACD>0) from IWM bar closed<=T, lagged 1 IWM bar (D+1). Canary adds +1 bar.",
            "sharpe": "full-period continuous-span (engine per-bar equity-return Sharpe on each contiguous slice)",
            "mutation_min_delta_pct": 0.10,
        },
        "diagnostics": diagnostics,
        "results": results,
        "cost_sensitivity": cost_sens,
        "gate_eval": gate_eval,
    }

    outpath = WORKSPACE / "reports" / "_combo_sprint_macd_breakout_result.json"
    outpath.write_text(json.dumps(out, indent=2))
    print("WROTE", outpath)
    # console summary
    def line(name):
        r = results[name]
        return (f"{name:32s} full_sh={r['full']['sharpe']:+.3f} "
                f"is_sh={r['is']['sharpe']:+.3f} oos_sh={r['oos']['sharpe']:+.3f} "
                f"oos_ret={r['oos']['total_return_pct']:+.2f}% "
                f"oos_ntr={r['oos']['n_trades']} "
                f"oos_medtr={r['oos']['median_trade_ret_pct']:+.3f}%")
    print("\n=== SOLO BASELINES ===")
    for nm in ("breakout_xlk_native", "breakout_xlk_panel", "volume_breakout_qqq_native",
               "volume_breakout_qqq_panel", "macd_momentum_iwm_native"):
        print(line(nm))
    print("\n=== AND-FUSION ===")
    for nm in ("AND_xlk_gated_by_iwm", "AND_qqq_gated_by_iwm"):
        print(line(nm))
    print("\n=== OR-FUSION ===")
    for nm in ("OR_xlk_union_iwm", "OR_qqq_union_iwm"):
        print(line(nm))
    print("\n=== CANARY (+1 bar lag) ===")
    for nm in ("CANARY_AND_xlk_gated_by_iwm", "CANARY_AND_qqq_gated_by_iwm"):
        print(line(nm))
    print("\n=== GATE EVAL (OOS, 2bps, vs best solo parent panel) ===")
    for k, v in gate_eval.items():
        print(f"{k}: dSharpe={v['delta_sharpe']:+.3f} dMedTrade={v['delta_medtrade_pct']:+.3f}pp "
              f"child_ntr={v['child_n_trades']} parent_ntr={v['parent_n_trades']} "
              f"PROMOTE={v['promotes_sharpe_gt_parent'] and v['promotes_medtrade_ge_0.10pp']}")
    print("\n=== DIAGNOSTICS ===")
    print(f"gate_xlk bull frac={diagnostics['gate_xlk_bull_frac']} "
          f"gate_qqq bull frac={diagnostics['gate_qqq_bull_frac']}")
    print(f"panel: xlk={diagnostics['n_xlk_panel']} qqq={diagnostics['n_qqq_panel']} "
          f"span {diagnostics['panel_first_ts']} -> {diagnostics['panel_last_ts']}")
    return out


if __name__ == "__main__":
    main()
