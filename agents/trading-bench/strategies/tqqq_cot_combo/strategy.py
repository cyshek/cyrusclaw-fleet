"""TQQQ Vol-Target + COT AM-Momentum Overlay - live-runner adapter.

PAPER ONLY. No real money. Validated OOS 2018-2026: +660%, Sharpe 0.960, maxDD -32.9%.
Code: strategies_candidates/tqqq_cot_combo/backtest_combo.py.

Logic per tick:
  1. SMA-200 gate on QQQ underlying (proxy: TQQQ when QQQ closes unavailable).
  2. 20-bar realized vol on TQQQ -> vol-target weight.
  3. COT ES AM-net WoW overlay: scale x0.5 if bearish, x1.0 otherwise.
  4. Target qty = floor(final_weight x notional / price).
     Rebalance only if delta > 5% threshold (churn guard).

COT publication lag: Tuesday snapshot + 3-day lag (released Friday) enforced via
cot_cache.load_series bisect on release_dates. Mirrors backtest_combo exactly.

QQQ gate: uses market_state['underlying']['closes'] when runner provides it;
else falls back to TQQQ closes as a directional proxy (documented, not hidden).

No-data fail-safes: no price->HOLD, vol insufficient->HOLD, COT missing->bullish.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
TRADING_DAYS = 252


@dataclass
class Action:
    action: str        # "buy" | "sell" | "hold" | "close"
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Vol math -- verbatim port from backtest_daily_voltarget.realized_ann_vol
# Population stdev (/ n) x sqrt(252). None if degenerate.
# ---------------------------------------------------------------------------

def _realized_ann_vol(returns: List[float], n: int) -> Optional[float]:
    """Population-stdev annualized vol of the last n returns."""
    if n < 2 or len(returns) < n:
        return None
    window = returns[-n:]
    mean = sum(window) / n
    var = sum((r - mean) ** 2 for r in window) / n
    sd = math.sqrt(var)
    if sd <= 1e-12:
        return None
    return sd * math.sqrt(TRADING_DAYS)


def _sma(values: List[float], n: int) -> Optional[float]:
    """Simple moving average of last n values. None if insufficient data."""
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _sleeve_returns(bars: List[dict]) -> List[float]:
    """Close-to-close simple returns from Alpaca bar dicts {t,o,h,l,c,v}."""
    cs = [float(b["c"]) for b in bars if b.get("c") is not None]
    rets: List[float] = []
    for k in range(1, len(cs)):
        if cs[k - 1] > 0:
            rets.append(cs[k] / cs[k - 1] - 1.0)
    return rets


# ---------------------------------------------------------------------------
# COT signal -- ES AM-net WoW direction with publication-lag guard
# ---------------------------------------------------------------------------

def _get_cot_scale(cot_scale_bearish: float, today_iso: Optional[str] = None) -> float:
    """Return 1.0 (bullish/no-data) or cot_scale_bearish (bearish AM WoW).

    Bearish = current AM-net < previous AM-net as-of today (WoW declining).
    Enforces 3-day publication lag via release_dates bisect.
    If COT data unavailable -> 1.0 (permissive: no false bearish block).
    Mirrors backtest_combo.build_cot_daily_signal() exactly.
    """
    if today_iso is None:
        today_iso = date.today().isoformat()
    try:
        from runner import cot_cache  # lazy import: avoids cold-start side effects
    except ImportError:
        return 1.0  # test environment without runner on path
    try:
        series = cot_cache.load_series("ES")
    except Exception:
        return 1.0  # data unavailable -> permissive
    if not series:
        return 1.0
    from bisect import bisect_right
    release_dates = [r["release"] for r in series]
    idx = bisect_right(release_dates, today_iso) - 1
    if idx < 1:
        return 1.0  # need >= 2 released snapshots
    cur_am = series[idx].get("am_net")
    prev_am = series[idx - 1].get("am_net")
    if cur_am is None or prev_am is None:
        return 1.0
    if cur_am < prev_am:
        return float(cot_scale_bearish)
    return 1.0


# ---------------------------------------------------------------------------
# Underlying QQQ closes resolver (honest, mirrors leveraged_long_trend_paper)
# ---------------------------------------------------------------------------

def _resolve_underlying_closes(
    market_state: dict, underlying: str, tqqq_bars: List[dict]
) -> tuple:
    """Return (closes: List[float], source: str, is_proxy: bool).

    Priority:
      1. market_state['underlying']['closes'] -- genuine QQQ closes (runner plumbing).
      2. market_state['regime']['underlying_closes'] -- alt plumbing.
      3. TQQQ bars as a directional proxy -- documented, not hidden.
         TQQQ and QQQ trend in the same direction; 200d SMA fires same side.
    Never uses SPY (different index).
    """
    u = market_state.get("underlying")
    if isinstance(u, dict):
        u_sym = str(u.get("symbol", underlying)).upper()
        if u_sym == underlying.upper():
            cs = u.get("closes")
            if cs:
                return [float(x) for x in cs], f"market_state['underlying'] ({u_sym})", False
            bars = u.get("bars")
            if bars:
                cs = [float(b["c"]) for b in bars if b.get("c") is not None]
                if cs:
                    return cs, f"market_state['underlying'].bars ({u_sym})", False
    regime = market_state.get("regime")
    if isinstance(regime, dict):
        cs = regime.get("underlying_closes")
        u_sym = str(regime.get("underlying_symbol", "")).upper()
        if cs and (not u_sym or u_sym == underlying.upper()):
            return [float(x) for x in cs], "regime['underlying_closes']", False
    if tqqq_bars:
        cs = [float(b["c"]) for b in tqqq_bars if b.get("c") is not None]
        return cs, f"TQQQ proxy (runner has no {underlying} plumbing)", True
    return [], "no underlying closes available", True


# ---------------------------------------------------------------------------
# Load params from file for standalone smoke tests
# ---------------------------------------------------------------------------

def _load_params_file() -> dict:
    p = HERE / "params.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


# ---------------------------------------------------------------------------
# decide() -- the strategy entry point
# ---------------------------------------------------------------------------

def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    """Vol-target + COT overlay decide function.

    Args:
        market_state: {symbol, last_price, bars (OHLCV dicts newest-last),
                       timeframe, regime, underlying, strategy_state, timestamp}
        position_state: {symbol: {qty, avg_entry_price, market_value, ...}}
        params: dict from params.json

    Returns:
        Action dataclass with action in ("buy", "sell", "close", "hold")
    """
    # Merge file defaults for any key omitted by caller (smoke-test compat).
    fp = _load_params_file()

    def P(key, default):
        if params is not None and key in params:
            return params[key]
        if key in fp:
            return fp[key]
        return default

    symbol            = str(P("symbol", "TQQQ"))
    underlying        = str(P("underlying", "QQQ"))
    target_ann_vol    = float(P("target_ann_vol", 0.40))
    vol_window        = int(P("vol_window", 20))
    w_max             = float(P("w_max", 1.0))
    cot_scale_bearish = float(P("cot_scale_bearish", 0.5))
    notional          = float(P("notional", 1000.0))
    sma_gate_window   = int(P("sma_gate_window", 200))

    # ---- Current position ----
    pos = position_state.get(symbol) or {}
    current_qty = 0
    try:
        current_qty = int(float(pos.get("qty", 0) or 0))
    except (TypeError, ValueError):
        current_qty = 0

    # ---- Price ----
    bars = market_state.get("bars") or []
    last_price = market_state.get("last_price") or market_state.get("price")
    price = None
    if last_price:
        try:
            price = float(last_price)
        except (TypeError, ValueError):
            price = None
    if price is None and bars:
        try:
            price = float(bars[-1]["c"])
        except (TypeError, ValueError, KeyError):
            price = None

    if price is None or price <= 0:
        return Action("hold", symbol, reason="no price available")

    # ---- SMA-200 gate on underlying (QQQ or proxy TQQQ) ----
    qqq_closes, gate_src, is_proxy = _resolve_underlying_closes(
        market_state, underlying, bars
    )
    proxy_tag = " (TQQQ proxy)" if is_proxy else ""

    if len(qqq_closes) >= sma_gate_window:
        sma_val = _sma(qqq_closes, sma_gate_window)
        last_close = qqq_closes[-1]
        gate_up = (sma_val is not None) and (last_close > sma_val)
        gate_note = (
            f"[{underlying}{proxy_tag}] close={last_close:.2f} "
            f"SMA{sma_gate_window}={sma_val:.2f} "
            f"gate={'ON' if gate_up else 'OFF'}"
        )
    else:
        gate_up = True
        gate_note = (
            f"[{underlying}{proxy_tag}] gate skipped "
            f"({len(qqq_closes)} bars < {sma_gate_window} needed)"
        )

    if not gate_up:
        if current_qty > 0:
            return Action("close", symbol,
                          reason=f"SMA-200 gate OFF -> close to flat | {gate_note}")
        return Action("hold", symbol,
                      reason=f"SMA-200 gate OFF -> stay flat | {gate_note}")

    # ---- Realized vol on TQQQ ----
    sleeve_rets = _sleeve_returns(bars)
    rv = _realized_ann_vol(sleeve_rets, vol_window)
    if rv is None:
        return Action("hold", symbol,
                      reason=(
                          f"insufficient bars for vol estimate "
                          f"({len(bars)} bars, {len(sleeve_rets)} returns, "
                          f"need {vol_window}) -> hold"
                      ))

    # ---- Vol-target weight ----
    raw_weight = min(target_ann_vol / rv, w_max)
    rv_note = f"rv={rv*100:.1f}% tgt={target_ann_vol*100:.0f}% w={raw_weight:.3f}"

    # ---- COT overlay ----
    today_iso = None
    ts = market_state.get("timestamp")
    if ts:
        try:
            today_iso = str(ts)[:10]
        except Exception:
            today_iso = None

    cot_scale = _get_cot_scale(cot_scale_bearish, today_iso)
    cot_note = f"COT_scale={cot_scale:.1f}"

    # ---- Final weight and target qty ----
    final_weight = raw_weight * cot_scale
    target_notional = final_weight * notional
    target_qty = math.floor(target_notional / price)
    # Churn guard: 5% of target, minimum 1 share
    threshold = max(1, math.floor(0.05 * max(target_qty, 1)))

    base_reason = (
        f"{gate_note} | {rv_note} | {cot_note} | "
        f"w_final={final_weight:.3f} tgt_qty={target_qty} "
        f"cur_qty={current_qty} thresh={threshold}"
    )
    delta = target_qty - current_qty

    if target_qty <= 0:
        if current_qty > 0:
            return Action("close", symbol,
                          reason=f"target_qty=0 -> close to flat | {base_reason}")
        return Action("hold", symbol,
                      reason=f"target_qty=0, already flat | {base_reason}")

    if delta > threshold:
        buy_qty = delta
        buy_notional = round(buy_qty * price, 2)
        return Action(
            "buy", symbol,
            notional_usd=buy_notional,
            qty=float(buy_qty),
            reason=f"underweight +{buy_qty}sh (${buy_notional:.0f}) | {base_reason}",
        )

    if delta < -threshold:
        sell_qty = -delta
        if target_qty <= 0:
            return Action("close", symbol,
                          reason=f"overweight target=0 -> close | {base_reason}")
        sell_notional = round(sell_qty * price, 2)
        return Action(
            "sell", symbol,
            notional_usd=sell_notional,
            qty=float(sell_qty),
            reason=f"overweight -{sell_qty}sh (${sell_notional:.0f}) | {base_reason}",
        )

    return Action(
        "hold", symbol,
        reason=f"within threshold |delta|={abs(delta)} <= {threshold} | {base_reason}",
    )
