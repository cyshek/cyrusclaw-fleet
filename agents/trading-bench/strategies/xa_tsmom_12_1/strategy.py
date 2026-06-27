"""Cross-asset 12-1 ABSOLUTE (time-series) momentum — basket adapter (decide_xsec).

PAPER ONLY. No real money.

VALIDATED ARCHETYPE (report: reports/XA_TSMOM_12_1_GATE_20260626T164538Z.md)
---------------------------------------------------------------------------
Universe {SPY, TLT, GLD, DBC, UUP} (equity / long-Treasuries / gold /
broad-commodities / US-dollar). Each month, compute 12-1 absolute momentum per
asset = trailing-12-month total return SKIPPING the most recent month (return
from month-end t-13 to month-end t-1, on adjusted close). HOLD every asset whose
12-1 momentum > 0, equal-weight the survivors; if none positive -> cash.
Rebalance monthly at month-end. Classic Antonacci-style absolute TSMOM.

Honest gate verdict (D+1 lag audited, 2bps/side on turnover incl. cash leg,
IS/OOS @ 2018-01, SPY bench, full-period continuous Sharpe):
  FULL +222.7% / Sharpe 0.75 / maxDD -24.9%   (SPY +641% / 0.78 / -46.3%)
  OOS  +112.7% / Sharpe 1.14 / maxDD -10.6%   (SPY +213% / 0.90 / -23.9%)
  Robust plateau across 6-1/9-1/12-1/12-0 (all OOS Sharpe > SPY 0.90).
  2022 rate-shock: -1.06% vs SPY -18.18% (held DBC+UUP). Never fully cash.

WHY IT IS A PARENT, NOT A STANDALONE DEPLOY
-------------------------------------------
It LOSES to SPY on raw return in every segment (it is a Sharpe / drawdown /
regime-rotation play, not a return machine). Its value is genuine CROSS-ASSET
DNA that is orthogonal-by-construction to the equity-long / leveraged-long gene
pool. Added to GATE_PASSING_PARENTS as a risk-orthogonal mutation seed; its
offspring (vol-target, inverse-vol, modest leverage overlay on the low-DD curve)
are where the absolute-return upside can come from. Canonical lookback shipped
is 12-1 (literature anchor + robust plateau member) rather than the 9-1
single-cell OOS argmax (avoid in-neighborhood overfit; let mutation explore it).

LIVE == BACKTEST FAITHFULNESS
-----------------------------
The signal is computed from each leg's own visible daily bars (market_state
"symbols"[sym]["bars"], oldest-first, only bars whose t <= clock_t), reduced to
a monthly adjusted-close series exactly as the validated driver did (last
trading day of each calendar month; adjclose if present else close). The
decision uses ONLY closed bars (the runner already trims to <= clock_t), and the
basket runner trades these weights on the next eligible bar -> the same D+1 lag
the backtest audited. A monthly-cadence guard (default ON) only re-targets on a
calendar-month change so intramonth ticks HOLD, matching the monthly rebalance.

WEIGHTS -> ORDERS
-----------------
For each leg: target_notional = w * MAX_NOTIONAL; target_qty = floor(/last);
delta vs the leg's attributed held qty; churn guard (default 5% of target,
min 1 share) so weight drift doesn't thrash. delta > thr -> BUY; delta < -thr
with target<=0 -> CLOSE, else TRIM -delta (reduce-while-long, uses the runner's
partial-trim primitive); |delta| <= thr -> HOLD. cash = residual leg.

FAIL-SAFES
----------
Any per-leg compute gap (no price, too few months) -> HOLD that leg (never
flatten on a data hiccup). A leg with a positive signal but no visible price is
skipped this tick. We never panic-flatten the whole book on a transient error.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


DEFAULT_UNIVERSE = ["SPY", "TLT", "GLD", "DBC", "UUP"]
DEFAULT_LOOKBACK_MONTHS = 12   # L
DEFAULT_SKIP_MONTHS = 1        # K (12-1 = skip the most recent month)


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _monthly_adjclose(bars: List[dict]) -> List[Tuple[str, float]]:
    """Reduce oldest-first daily bars to (YYYY-MM, adjclose) for the LAST
    trading day of each calendar month. adjclose if present else close.
    Mirrors reports/_xa_tsmom_driver.monthly_adjclose."""
    by_month: Dict[str, Tuple[str, float]] = {}
    for b in bars or []:
        d = b.get("date") or b.get("t") or ""
        if not isinstance(d, str) or len(d) < 7:
            continue
        ym = d[:7]
        px = b.get("adjclose")
        if px is None:
            px = b.get("close")
        if px is None:
            continue
        try:
            pxf = float(px)
        except (TypeError, ValueError):
            pxf = float("nan")
        if not (pxf > 0):
            continue
        prev = by_month.get(ym)
        # keep the LATEST date within the month
        if prev is None or d >= prev[0]:
            by_month[ym] = (d, pxf)
    out = [(ym, v[1]) for ym, v in sorted(by_month.items())]
    return out


def _mom_12_1(monthly: List[Tuple[str, float]], L: int, K: int) -> Optional[float]:
    """12-1 absolute momentum at the latest available month: adjclose[t-K] /
    adjclose[t-(L+K)] - 1, using month-end series. Requires >= L+K+1 months so
    the recent endpoint (t-K) and far endpoint (t-(L+K)) both exist and the
    most-recent month is genuinely skipped. Returns None if insufficient."""
    n = len(monthly)
    if n < (L + K + 1):
        return None
    recent = monthly[n - 1 - K][1]
    far = monthly[n - 1 - (L + K)][1]
    if far <= 0:
        return None
    return recent / far - 1.0


def decide_xsec(market_state: dict, position_state: dict, params: dict) -> Dict[str, Action]:
    universe = list(params.get("basket") or params.get("universe") or DEFAULT_UNIVERSE)
    L = int(params.get("lookback_months", DEFAULT_LOOKBACK_MONTHS))
    K = int(params.get("skip_months", DEFAULT_SKIP_MONTHS))
    max_notional = float(params.get("max_notional_usd", params.get("notional_usd", 100.0)))
    churn_frac = float(params.get("churn_frac", 0.05))
    monthly_cadence = bool(params.get("monthly_cadence", True))

    syms = market_state.get("symbols") or {}
    state = market_state.get("strategy_state")
    if not isinstance(state, dict):
        state = {}

    # ---- monthly cadence guard: only re-target on a calendar-month change ----
    clock_t = str(market_state.get("clock_t") or "")
    cur_ym = clock_t[:7] if len(clock_t) >= 7 else ""
    if monthly_cadence and cur_ym:
        last_ym = state.get("xa_tsmom_last_ym")
        if last_ym == cur_ym:
            return {}  # already rebalanced this month -> HOLD everything
        # mark; if we end up acting below this stands as the rebalance month
        state["xa_tsmom_last_ym"] = cur_ym
        market_state["strategy_state"] = state

    # ---- compute 12-1 signal per leg from its own visible bars ----
    signals: Dict[str, Optional[float]] = {}
    prices: Dict[str, Optional[float]] = {}
    for s in universe:
        leg = syms.get(s) or {}
        bars = leg.get("bars") or []
        monthly = _monthly_adjclose(bars)
        signals[s] = _mom_12_1(monthly, L, K)
        lp = leg.get("last_price")
        prices[s] = float(lp) if isinstance(lp, (int, float)) and lp and lp > 0 else None

    # ---- weights: EW of assets with positive 12-1 momentum, else cash ----
    winners = [s for s in universe if signals.get(s) is not None and signals[s] > 0]
    n_win = len(winners)
    target_w: Dict[str, float] = {s: 0.0 for s in universe}
    if n_win > 0:
        w = 1.0 / n_win
        for s in winners:
            target_w[s] = w
    # if n_win == 0 -> all cash (every target_w stays 0.0)

    # ---- weights -> orders, churn-guarded, partial-trim aware ----
    actions: Dict[str, Action] = {}
    # union of universe + currently-held legs (so we can exit dropped legs)
    held = {s for s in universe if (position_state.get(s) or {}).get("qty", 0)}
    for s in (set(universe) | held):
        tw = target_w.get(s, 0.0)
        last = prices.get(s)
        pos = position_state.get(s) or {}
        cur_qty = float(pos.get("qty", 0) or 0)

        if tw <= 0.0:
            if cur_qty > 0:
                actions[s] = Action("close", s, reason=f"12-1 mom<=0 or dropped; exit {cur_qty:g}")
            # else flat already -> no action
            continue

        if last is None:
            # want it, but cannot price it this tick -> HOLD (don't size blind)
            continue

        target_notional = tw * max_notional
        target_qty = math.floor(target_notional / last)
        if target_qty <= 0:
            if cur_qty > 0:
                actions[s] = Action("close", s, reason="target floored to 0 shares")
            continue

        delta = target_qty - cur_qty
        thr = max(1, math.floor(churn_frac * max(target_qty, 1)))
        sig = signals.get(s)
        sig_txt = f"{sig:.3f}" if sig is not None else "na"
        if delta > thr:
            actions[s] = Action("buy", s, notional_usd=delta * last,
                                 reason=f"add {delta:g} (w={tw:.3f}, mom={sig_txt})")
        elif delta < -thr:
            actions[s] = Action("trim", s, qty=float(-delta),
                                 reason=f"trim {-delta:g} (w={tw:.3f}, mom={sig_txt})")
        # |delta| <= thr -> HOLD (no churn)

    return actions
