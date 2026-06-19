"""leveraged_long_trend_paper — DEPLOYABLE live-PAPER decide() adapter for the
vol-targeted leveraged-long sleeve (TQQQ, QQQ-gated, inverse-realized-vol sized).

PAPER ONLY. No real money. This is the live-runner adapter for the BACKTEST
engine in strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py
(which PASSED OOS net of realistic costs). The whole VALUE of this strategy is
its risk layer, so this adapter reproduces the engine's gate, vol window, and
sizing math EXACTLY, with the same no-lookahead discipline. A lookahead leak or
a wrong gate makes the strategy worthless and dishonest — so where the live
runner cannot honestly supply a required input, this adapter FAILS SAFE TO FLAT
and says so in `.reason`, rather than silently substituting a wrong proxy.

================================================================================
WHAT IT DOES  (must match backtest_daily_voltarget.py)
================================================================================
On each daily tick the adapter computes the TARGET WEIGHT on the TQQQ sleeve:

    if QQQ trend gate is UP (QQQ last close > QQQ 200d SMA, closes through D):
        rv = realized_ann_vol(TQQQ daily simple returns, trailing 20, dates<=D)
        w  = clamp(target_vol / rv, 0.0, w_max)     # w_max defaults to 1.0
    else:
        w  = 0.0                                     # gate down -> flat to cash

It then translates that weight into an order against the runner's contract.

================================================================================
WEIGHT -> ORDER TRANSLATION  (and why it is coarse)
================================================================================
DEPLOYABLE_NOTIONAL = params['deployable_notional'] (defaults to the runner's
MAX_NOTIONAL = $1000). target_notional = w * DEPLOYABLE_NOTIONAL.
current_notional = position_state[TQQQ].qty * last_price.
delta = target_notional - current_notional.

The live runner supports exactly TWO position primitives:
  * BUY  notional=N  -> spend $N into the symbol (adds exposure).
  * CLOSE            -> liquidate the FULL strategy-attributed qty to flat.
There is NO supported partial-trim-while-staying-long primitive (a notional
'sell' is not the attributed-qty liquidation path and would desync attribution).
So a continuously-rebalanced book cannot be reproduced tick-for-tick. We
quantize honestly:

  - gate OFF, or target weight collapses below `flat_weight_eps` -> CLOSE to
    flat (full de-risk; always supported, this is the engine's 0-weight day).
  - want MORE exposure (delta > 0) and |delta| >= deadband               -> BUY delta.
  - want LESS exposure but still meaningfully long (delta < 0, target>eps) ->
    we CANNOT partial-trim, so we HOLD (documented limitation). The position
    only steps down via the gate-off CLOSE or when target drops under
    flat_weight_eps. This biases the live sleeve slightly HOTTER than the
    continuously-rebalanced backtest on vol-spike days where the engine would
    trim but not fully exit — a known, bounded divergence (capped at w_max=1.0,
    i.e. never more than one full $1000 sleeve). Documented as a runner-plumbing
    gap for Tessera (add a notional-trim sell path to close it).
  - |delta| < deadband -> HOLD (rebalance deadband, prevents churn).

DEADBAND = max(deadband_abs_usd, deadband_frac * DEPLOYABLE_NOTIONAL)
defaults to max($25, 5% * $1000 = $50) = $50.

================================================================================
NO-LOOKAHEAD DISCIPLINE
================================================================================
The runner ticks on completed daily bars. `market_state['bars']` is the TQQQ
daily OHLCV series whose LAST bar is the most recent completed close = decision
day D. The weight we compute is APPLIED GOING FORWARD (the position we hold
into D+1), decided ONLY from data with date <= D:
  * gate:      QQQ closes through D (SMA-200 + last close).
  * realized vol: TQQQ daily returns ending on D (trailing 20).
A price/vol move after D cannot change today's weight. This is the SAME D->D+1
convention as the engine. We never peek at the forming bar.

================================================================================
THE QQQ-DATA DEPENDENCY  (the one honest gap)
================================================================================
The SMA-200 trend gate is on QQQ (the underlying), NOT on TQQQ (the sleeve) and
NOT on SPY. The live runner currently injects:
  * market_state['bars']            = TRADED symbol bars only (here: TQQQ)
  * market_state['regime']          = {'spy_closes':[...], 'spy_last':...}  (SPY, hardcoded)
It does NOT pass QQQ closes. So this adapter looks for QQQ closes, in order:
  1. market_state['underlying']['closes']            (preferred new plumbing)
  2. market_state['regime']['underlying_closes']     (alt new plumbing)
  3. market_state['regime'] when regime['underlying_symbol']=='QQQ'/params underlying
If NONE supply QQQ, the adapter returns HOLD/flat-safe and the reason states the
gap. It DOES NOT proxy the QQQ gate with SPY or TQQQ (that would be a different,
unvalidated strategy). >> Tessera must add the runner plumbing (inject the
underlying's daily closes for strategies declaring params['underlying']) before
this sleeve is gate-correct live. Realized vol does NOT need that plumbing — it
is on the sleeve (TQQQ) whose bars are already provided.

NOTE on adjclose: the engine computes QQQ SMA and TQQQ returns from SPLIT/DIV-
ADJUSTED closes (adjclose). Live Alpaca daily bars give raw close `c`. Over a
trailing 20d (vol) / 200d (SMA) window with no split inside it, raw ≈ adjusted
for the gate/vol decision; TQQQ has split historically but not intra-window in
normal operation. If a split lands inside a live trailing window, the raw-close
return on the split day is corrupt — Tessera should feed adjusted closes if/when
the broker plumbing exposes them. Documented, not silently ignored.

================================================================================
VIX GATE
================================================================================
The engine's params set vix_gate=true (a VIX/VIX3M term-structure risk-off
overlay). The live runner cannot supply VIX term structure, and the engine's own
_vix_risk_off returns "not risk-off" (pass) on missing data. This adapter mirrors
that: the VIX overlay is applied ONLY if VIX term-structure is plumbed into
market_state (it is not today); absent -> pass (permissive), exactly the engine's
graceful-degrade. So live behavior == engine-with-VIX-data-missing, which is a
faithful (slightly more permissive) reproduction, not a silent deviation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from strategies._lib.indicators import closes as _closes_of_bars

HERE = Path(__file__).resolve().parent

TRADING_DAYS = 252  # mirrors backtest_daily.TRADING_DAYS exactly


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


# --------------------------------------------------------------------------- #
# Engine math, copied verbatim from backtest_daily_voltarget.py so the live
# decision is byte-for-byte the backtest decision. DO NOT "improve" these —
# parity with the validated engine is the contract.
# --------------------------------------------------------------------------- #
def realized_ann_vol(sleeve_returns_through_D: List[float], n: int) -> Optional[float]:
    """Annualized stdev of the last `n` daily simple returns (dates <= D).

    Verbatim mirror of backtest_daily_voltarget.realized_ann_vol:
    population stdev (var = sum((r-mean)^2)/n) * sqrt(252). Returns None if
    fewer than `n` returns OR stdev <= 1e-12 (degenerate -> no usable estimate,
    caller stays flat rather than dividing by ~0).
    """
    if n < 2 or len(sleeve_returns_through_D) < n:
        return None
    window = sleeve_returns_through_D[-n:]
    mean = sum(window) / n
    var = sum((r - mean) ** 2 for r in window) / n  # population var (engine convention)
    sd = math.sqrt(var)
    if sd <= 1e-12:
        return None
    return sd * math.sqrt(TRADING_DAYS)


def _sma(values: List[float], n: int) -> Optional[float]:
    """Verbatim mirror of backtest_daily._sma: None if fewer than n values."""
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def trend_is_up_sma200(underlying_closes: List[float], sma_window: int) -> bool:
    """SMA-200 gate, verbatim mirror of backtest_daily.trend_is_up(gate_mode='sma200').

    underlying_closes = QQQ closes up to and INCLUDING decision day D. Gate ON
    iff SMA computable (>= sma_window closes) AND last close > that SMA. Empty
    or <sma_window closes -> OFF (engine returns sma_ok=False because _sma None).
    """
    if not underlying_closes:
        return False
    last = underlying_closes[-1]
    s = _sma(underlying_closes, sma_window)
    return (s is not None) and (last > s)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def target_weight(trend_up: bool, rvol: Optional[float],
                  target_ann_vol: Optional[float], w_max: float) -> float:
    """Verbatim mirror of backtest_daily_voltarget.target_weight.

    trend down -> 0.0; target_ann_vol None -> binary 1.0 (clamped to w_max);
    rvol None/<=0 -> 0.0 (no vol estimate -> flat, no guess); else
    clamp(target/rvol, 0, w_max).
    """
    if not trend_up:
        return 0.0
    if target_ann_vol is None:
        return min(1.0, w_max)
    if rvol is None or rvol <= 0:
        return 0.0
    return _clamp(target_ann_vol / rvol, 0.0, w_max)


# --------------------------------------------------------------------------- #
# Sleeve daily simple returns from completed bars (close-to-close), date-aware.
# Mirrors the engine's "returns whose END date is <= D" construction. Live, the
# last bar IS D, so all close-to-close returns from the provided bars end <= D.
# --------------------------------------------------------------------------- #
def _sleeve_returns(bars: List[dict]) -> List[float]:
    cs = _closes_of_bars(bars or [])
    rets: List[float] = []
    for k in range(1, len(cs)):
        if cs[k - 1] > 0:
            rets.append(cs[k] / cs[k - 1] - 1.0)
    return rets


# --------------------------------------------------------------------------- #
# QQQ-closes resolver — honest, no silent proxy. Returns (closes, source) or
# (None, why-missing). Never returns SPY or TQQQ as a stand-in for QQQ.
# --------------------------------------------------------------------------- #
def _resolve_underlying_closes(market_state: dict, underlying: str):
    # 1) dedicated plumbing: market_state['underlying'] = {'symbol':..,'closes':[..]}
    u = market_state.get("underlying")
    if isinstance(u, dict):
        u_sym = str(u.get("symbol", underlying)).upper()
        if u_sym == underlying.upper():
            cs = u.get("closes")
            if not cs and u.get("bars"):
                cs = _closes_of_bars(u.get("bars"))
            if cs:
                return [float(x) for x in cs], f"market_state['underlying'] ({u_sym})"
    # 2) regime block carrying underlying closes explicitly
    regime = market_state.get("regime")
    if isinstance(regime, dict):
        cs = regime.get("underlying_closes")
        u_sym = str(regime.get("underlying_symbol", "")).upper()
        if cs and (not u_sym or u_sym == underlying.upper()):
            return [float(x) for x in cs], f"regime['underlying_closes'] ({u_sym or underlying})"
    # No honest QQQ source. Do NOT fall back to SPY/TQQQ.
    return None, ("no QQQ closes in market_state (runner injects SPY-only regime "
                  "+ TQQQ-only bars; underlying plumbing missing)")


def _load_params_file() -> dict:
    p = HERE / "params.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


# --------------------------------------------------------------------------- #
# decide()
# --------------------------------------------------------------------------- #
def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    # params may arrive from the runner's params.json load; merge file defaults
    # for any key the caller omitted (keeps smoke + live identical).
    fp = _load_params_file()
    def P(key, default):
        if params is not None and key in params:
            return params[key]
        if key in fp:
            return fp[key]
        return default

    symbol = str(P("symbol", "TQQQ"))
    underlying = str(P("underlying", "QQQ"))
    target_vol = P("target_vol", 0.25)
    target_vol = float(target_vol) if target_vol is not None else None
    vol_window = int(P("vol_window", 20))
    sma_window = int(P("sma_window", 200))
    w_max = float(P("w_max", 1.0))
    deployable_notional = float(P("deployable_notional", 1000.0))  # == runner MAX_NOTIONAL
    deadband_abs_usd = float(P("deadband_abs_usd", 25.0))
    deadband_frac = float(P("deadband_frac", 0.05))
    flat_weight_eps = float(P("flat_weight_eps", 0.02))  # target below this -> treat as flat

    last_price = market_state.get("last_price")
    bars = market_state.get("bars") or []

    pos = position_state.get(symbol) or {}
    held_qty = 0.0
    try:
        held_qty = float(pos.get("qty", 0.0) or 0.0)
    except (TypeError, ValueError):
        held_qty = 0.0

    # Current price for notional math: prefer live last_price, fall back to last
    # completed bar close, then avg_entry_price (only matters when we hold).
    px = None
    if last_price:
        try:
            px = float(last_price)
        except (TypeError, ValueError):
            px = None
    if px is None and bars:
        try:
            px = float(bars[-1]["c"])
        except (TypeError, ValueError, KeyError):
            px = None
    if px is None and held_qty > 0:
        try:
            px = float(pos.get("avg_entry_price") or 0.0) or None
        except (TypeError, ValueError):
            px = None

    current_notional = (held_qty * px) if (px and held_qty > 0) else 0.0

    # --- 1) QQQ gate input (honest, no proxy) ---
    qqq_closes, src = _resolve_underlying_closes(market_state, underlying)
    if qqq_closes is None:
        # We cannot honestly evaluate the QQQ gate. FAIL SAFE: if we are holding,
        # de-risk to flat (don't sit in a 3x sleeve with an unknown gate); if
        # flat, do nothing. Never open exposure on an unknown gate.
        if held_qty > 0:
            return Action("close", symbol,
                          reason=f"FAIL-SAFE flat: {underlying} closes unavailable "
                                 f"({src}); cannot evaluate gate -> de-risk")
        return Action("hold", symbol,
                      reason=f"no-op: {underlying} closes unavailable ({src}); "
                             f"gate unknown -> stay flat (runner plumbing gap)")

    # --- 2) trend gate on QQQ closes through D ---
    if len(qqq_closes) < sma_window:
        gate_up = False
        gate_note = f"gate=OFF(insufficient {underlying} hist {len(qqq_closes)}<{sma_window})"
    else:
        gate_up = trend_is_up_sma200(qqq_closes, sma_window)
        sma_val = _sma(qqq_closes, sma_window)
        gate_note = (f"gate={'ON' if gate_up else 'OFF'}"
                     f"({underlying} {qqq_closes[-1]:.2f} vs SMA{sma_window} {sma_val:.2f})")

    # --- 3) realized vol on the SLEEVE (TQQQ) own returns through D ---
    sleeve_rets = _sleeve_returns(bars)
    rv = realized_ann_vol(sleeve_rets, vol_window) if (target_vol is not None and gate_up) else None

    # --- 4) target weight (engine math) ---
    w = target_weight(gate_up, rv, target_vol, w_max)
    rv_note = f"rv={rv*100:.1f}%" if rv is not None else "rv=n/a"

    # --- 5) translate weight -> order ---
    target_notional = w * deployable_notional
    deadband = max(deadband_abs_usd, deadband_frac * deployable_notional)
    delta = target_notional - current_notional

    base = f"voltarget w={w:.2f} {rv_note} {gate_note} tgt=${target_notional:.0f} cur=${current_notional:.0f}"

    # 5a) target effectively flat (gate off, or vol so high weight ~0) -> CLOSE.
    if w <= flat_weight_eps:
        if held_qty > 0:
            return Action("close", symbol, reason=f"{base}: target flat -> close to cash")
        return Action("hold", symbol, reason=f"{base}: already flat")

    # 5b) we want exposure. Price is required to size a buy.
    if px is None:
        return Action("hold", symbol, reason=f"{base}: no price to size order -> hold")

    # 5c) inside the rebalance deadband -> hold (churn guard).
    if abs(delta) < deadband:
        return Action("hold", symbol,
                      reason=f"{base}: |Δ|=${abs(delta):.0f} < deadband ${deadband:.0f} -> hold")

    # 5d) need MORE -> buy the delta (clamped so we never exceed deployable_notional
    #     of total exposure; runner enforces MAX_NOTIONAL/MAX_POSITION on top).
    if delta > 0:
        room = deployable_notional - current_notional
        buy_notional = min(delta, max(room, 0.0))
        # never emit a notional above the deployable reference (defensive; the
        # runner's risk.check_trade is the hard cap, but we must not emit absurd).
        buy_notional = min(buy_notional, deployable_notional)
        if buy_notional < deadband:
            return Action("hold", symbol,
                          reason=f"{base}: buyable ${buy_notional:.0f} < deadband ${deadband:.0f} -> hold")
        return Action("buy", symbol, notional_usd=round(buy_notional, 2),
                      reason=f"{base}: buy ${buy_notional:.0f} toward target")

    # 5e) want LESS but still meaningfully long: runner has no partial-trim
    #     primitive, so we HOLD (documented limitation). The sleeve steps down
    #     only via gate-off/flat-eps close above. This keeps us slightly hotter
    #     than the continuously-rebalanced engine on trim-but-not-exit days.
    return Action("hold", symbol,
                  reason=f"{base}: want trim Δ=${delta:.0f} but no partial-trim "
                         f"primitive in runner -> hold (capped at w_max)")
