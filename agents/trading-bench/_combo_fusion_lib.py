"""Combo sprint: macd_momentum_iwm × {breakout_xlk, volume_breakout_qqq}.

Deterministic CROSS-SYMBOL fusion (AND + OR), honest harness:
  - D+1 lag: cross-symbol IWM-MACD confirmation uses the most recent IWM bar
    STRICTLY BEFORE the primary bar's timestamp (no same-bar lookahead). A
    +1-bar-lag robustness canary is also run (the lethal test that killed
    VIX-term + SKEW).
  - 2 bps/side cost (CostModel.alpaca_stocks()).
  - IS/OOS split. 1Hour data floor is 2020-07-27 (Alpaca hourly depth), so the
    directive's "2018" split is infeasible; we use the deepest honest split:
    IS  = 2020-07-27 .. 2023-12-31
    OOS = 2024-01-01 .. 2026-06-24
  - SPY buy&hold benchmark on the SAME primary-symbol bar path.
  - Gate: combo median-return (per-window) must beat the strongest solo parent
    by >= +0.10pp (MUTATION_MIN_DELTA_PCT), AND combo full-period continuous
    Sharpe must not collapse vs parent (the verdict lesson: OR dilutes Sharpe).

The primary parent (breakout_xlk or volume_breakout_qqq) owns the symbol and the
position. macd_momentum_iwm contributes a cross-symbol IWM-MACD bullish state
(MACD>signal AND MACD>0), recomputed bar-by-bar on IWM with the SAME _macd()
logic as the live strategy.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from runner import bars_cache
from runner.backtest import (CostModel, backtest, bars_per_year,
                             load_strategy_module_and_params)
from runner.fp_sharpe import equity_curve_returns, sharpe_from_returns

# Reuse the live MACD math directly from the strategy module so the IWM
# confirmation signal is byte-identical to the real macd_momentum_iwm.
_macd_mod, _ = load_strategy_module_and_params("macd_momentum_iwm")
_macd = _macd_mod._macd  # (values, fast, slow, signal) -> (macd, signal, hist)

IS_END = "2023-12-31"
OOS_START = "2024-01-01"


def _parse_day(t: str) -> str:
    return t[:10]


def load_full_1h(symbol: str) -> List[dict]:
    """Deepest cached 1Hour series for a symbol (2020-07-27 .. 2026-06-24)."""
    bars = bars_cache.get_bars(symbol, "1Hour", days=6000,
                               end_dt=datetime(2026, 6, 25, tzinfo=timezone.utc))
    return bars or []


def build_iwm_macd_states(iwm_bars: List[dict], fast=12, slow=26,
                          signal=9) -> List[Tuple[str, bool]]:
    """For each IWM bar i (>= warmup), compute whether IWM-MACD is bullish
    (MACD>signal AND MACD>0) using ONLY closes[:i+1]. Returns a chronological
    list of (timestamp, bullish_bool). No lookahead within the IWM series.
    """
    closes = [float(b["c"]) for b in iwm_bars]
    out: List[Tuple[str, bool]] = []
    warm = slow + signal + 2
    for i in range(len(iwm_bars)):
        if i + 1 < warm:
            out.append((str(iwm_bars[i]["t"]), False))
            continue
        m, s, _ = _macd(closes[: i + 1], fast, slow, signal)
        bull = (m is not None and s is not None and m > s and m > 0.0)
        out.append((str(iwm_bars[i]["t"]), bool(bull)))
    return out


def make_aligned_lookup(iwm_states: List[Tuple[str, bool]], lag_bars: int):
    """Return a function f(primary_ts)->bool giving the IWM-MACD-bullish state
    as of the most recent IWM bar STRICTLY BEFORE primary_ts, then stepped back
    an additional `lag_bars` IWM bars (D+1 / canary lag). No lookahead.

    Implemented with a monotonic cursor for O(n) total across a sorted scan.
    """
    ts = [t for t, _ in iwm_states]
    vals = [b for _, b in iwm_states]
    n = len(ts)
    state = {"cur": -1}

    def f(primary_ts: str) -> bool:
        # advance cursor to last IWM index with ts[idx] < primary_ts
        cur = state["cur"]
        while cur + 1 < n and ts[cur + 1] < primary_ts:
            cur += 1
        state["cur"] = cur
        idx = cur - lag_bars
        if idx < 0:
            return False
        return vals[idx]

    return f, state


def reset_lookup(state):
    state["cur"] = -1


# ---------------------------------------------------------------------------
# Fusion decide-fn factories. They wrap the PRIMARY parent's decide and consult
# the aligned IWM-MACD bullish lookup. The primary parent owns symbol+position.
# ---------------------------------------------------------------------------
def make_and_fusion(primary_name: str, iwm_bull_at: Callable[[str], bool]):
    """AND: primary BUY only fires when IWM-MACD is bullish at the (lagged)
    aligned timestamp. SELL/HOLD pass through unchanged (exits always reachable).
    """
    mod, _ = load_strategy_module_and_params(primary_name)
    base_decide = mod.decide

    def decide(market_state, position_state, params):
        act = base_decide(market_state, position_state, params)
        if act.action == "buy":
            bars = market_state.get("bars") or []
            ts = str(bars[-1]["t"]) if bars else ""
            if not iwm_bull_at(ts):
                # veto the entry; hold flat
                act.action = "hold"
                act.notional_usd = 0.0
                act.reason = "AND-veto: IWM-MACD not bullish @ " + ts
        return act

    return decide


def make_or_fusion(primary_name: str, iwm_bull_at: Callable[[str], bool]):
    """OR: enter long when EITHER the primary breakout entry fires OR a FRESH
    IWM-MACD bullish transition (False->True) is seen at the aligned timestamp.
    Exit = primary parent's own exit. Single position on the primary symbol.
    """
    mod, _ = load_strategy_module_and_params(primary_name)
    base_decide = mod.decide
    prev = {"bull": False}

    def decide(market_state, position_state, params):
        symbol = params.get("symbol")
        notional = float(params.get("notional_usd", 100.0))
        act = base_decide(market_state, position_state, params)
        bars = market_state.get("bars") or []
        ts = str(bars[-1]["t"]) if bars else ""
        bull_now = iwm_bull_at(ts)
        fresh_cross = bull_now and not prev["bull"]
        prev["bull"] = bull_now

        pos = position_state.get(symbol)
        holding = float(pos.get("qty", 0)) if pos else 0.0

        # If primary already wants to act, respect it (covers exits + its own entry).
        if act.action in ("buy", "close", "sell"):
            return act
        # Primary is holding/flat with no action; add the OR entry trigger.
        if holding == 0 and fresh_cross:
            act.action = "buy"
            act.symbol = symbol
            act.notional_usd = notional
            act.reason = "OR-entry: fresh IWM-MACD bullish cross @ " + ts
        return act

    return decide, prev


# ---------------------------------------------------------------------------
# Window machinery: split a primary series into IS/OOS, and also into N
# contiguous sub-windows for a median-of-windows return (gate metric).
# ---------------------------------------------------------------------------
def slice_by_date(bars: List[dict], start: Optional[str], end: Optional[str]):
    out = []
    for b in bars:
        d = _parse_day(str(b["t"]))
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(b)
    return out


def chunk_windows(bars: List[dict], n_windows: int) -> List[List[dict]]:
    if n_windows <= 1:
        return [bars]
    size = len(bars) // n_windows
    return [bars[i * size:(i + 1) * size] for i in range(n_windows)] if size > 0 else [bars]


def run_one(primary_name: str, primary_bars: List[dict], decide_fn,
            lookup_state) -> dict:
    """Backtest the fusion decide_fn over one primary-bar window."""
    reset_lookup(lookup_state)
    _, params = load_strategy_module_and_params(primary_name)
    cm = CostModel.alpaca_stocks()
    res = backtest(primary_name, primary_bars, params,
                   starting_cash=1000.0, decide_fn=decide_fn, cost_model=cm)
    return {
        "ret_pct": res.total_return_pct,
        "sharpe": res.sharpe,
        "n_trades": res.n_trades,
        "maxdd": res.max_drawdown_pct,
        "equity_curve": list(res.equity_curve),
        "n_bars": res.n_bars,
    }


def spy_buyhold_return(primary_bars: List[dict]) -> float:
    """SPY buy&hold over the same calendar span as primary_bars, on SPY 1Hour
    bars sliced to [first_day, last_day]."""
    if not primary_bars:
        return 0.0
    d0 = _parse_day(str(primary_bars[0]["t"]))
    d1 = _parse_day(str(primary_bars[-1]["t"]))
    spy = load_full_1h("SPY")
    spy = slice_by_date(spy, d0, d1)
    if len(spy) < 2:
        return 0.0
    c0 = float(spy[0]["c"])
    c1 = float(spy[-1]["c"])
    cm = CostModel.alpaca_stocks()
    # one round-trip cost for buy&hold
    buy = cm.buy_fill_price(c0)
    sell = cm.sell_fill_price(c1)
    return (sell - buy) / buy * 100.0


def median(xs: List[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def fp_sharpe_concat(window_results: List[dict], timeframe="1Hour") -> Tuple[float, int]:
    rets: List[float] = []
    for w in window_results:
        rets.extend(equity_curve_returns(w["equity_curve"]))
    bpy = bars_per_year(timeframe, False)
    return sharpe_from_returns(rets, bpy), len(rets)
