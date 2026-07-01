"""FX trend (TSMOM) + carry research harness — lookahead-safe, cost-aware.

RESEARCH/BACKTEST-ONLY. Stands up the FOREX-lane edge test on the free, deep,
IP-unwalled Yahoo daily FX-majors cache (`runner.fx_bars_cache`). This module
is INFRASTRUCTURE: it composes unlevered spot FX returns into clean,
lookahead-safe per-symbol and basket equity curves, applies the canonical
`runner.backtest.CostModel` (FX-appropriate one-way spread) on turnover, and
hands the resulting return series to the canonical Sharpe ruler
(`runner.fp_sharpe.sharpe_from_returns`). It NEVER imports/edits a protected
runner file beyond importing `CostModel` and `bars_per_year`.

================================ DESIGN ================================
Signal construction (THE lookahead guard):
  For trading date axis D[0..T], the position held INTO the return
  r_t = (P[t]/P[t-1] - 1) is decided from prices through D[t-1] ONLY. We build
  a `signal[t]` array where signal[t] is computed from closes[:t] (strictly
  prior to the bar whose return is r_t). Position = signal[t-1]-style alignment
  is folded in: `positions[t]` multiplies `r_t` and uses ONLY closes[:t].

  This is the standard 1-day signal lag the fx_bars_cache docstring describes:
  signal from closes through D, position applied to D->D+1 close-to-close ret.

No leverage:
  positions are in {-1, 0, +1} (or fractional <= 1 in magnitude for a basket
  equal-weight). |position| <= 1 at all times => unlevered notional. The basket
  equal-weights its legs so gross exposure <= 1.0 (1/N per leg).

Cost:
  Turnover_t = sum_i |w_i[t] - w_i[t-1]| (change in target weight). One-way
  spread cost = Turnover_t * spread_bps/1e4 is deducted from r_t. This is the
  standard linear transaction-cost model and matches how a round-trip costs
  ~2*spread_bps. FX majors: spread_bps ~ 1bp (cls.fx_majors()).
=======================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .backtest import CostModel, bars_per_year
from .fx_bars_cache import FX_MAJORS, close_series, get_daily

# FX-appropriate cost model: ~1bp one-way spread on majors (round-trip ~2bp).
# This is materially cheaper than the equity 2bp convention and ~400x cheaper
# than the crypto 200bp model. Explicitly conservative-ish for retail spot FX.
FX_SPREAD_BPS_ONEWAY = 1.0


def fx_cost_model(spread_bps: float = FX_SPREAD_BPS_ONEWAY) -> CostModel:
    """The FX one-way spread cost model used by this lane."""
    return CostModel(spread_bps=spread_bps, fee_bps=0.0)


# --------------------------------------------------------------------------- #
# Common trading-date axis + aligned closes
# --------------------------------------------------------------------------- #
def union_trading_dates(symbols: Sequence[str]) -> List[str]:
    """Sorted union of all trading dates across `symbols` (ISO strings)."""
    s = set()
    for sym in symbols:
        for bar in get_daily(sym):
            s.add(bar["date"])
    return sorted(s)


def aligned_closes(symbols: Sequence[str],
                   dates: Optional[List[str]] = None
                   ) -> Tuple[List[str], Dict[str, List[Optional[float]]]]:
    """Return (dates, {sym: forward-filled close aligned to dates}).

    Forward-fill is lookahead-safe (close_series only uses bars <= D). When a
    symbol has no bar at/before a date the value is None (pre-inception).
    """
    if dates is None:
        dates = union_trading_dates(symbols)
    out: Dict[str, List[Optional[float]]] = {}
    for sym in symbols:
        out[sym] = close_series(sym, dates)
    return dates, out


# --------------------------------------------------------------------------- #
# Return series
# --------------------------------------------------------------------------- #
def simple_returns(closes: Sequence[Optional[float]]) -> List[Optional[float]]:
    """Close-to-close simple returns; None where either endpoint is None/<=0.

    Index t of the output is the return realized over (t-1 -> t). Output[0] is
    always None (no prior bar). len(output) == len(closes).
    """
    out: List[Optional[float]] = [None]
    for t in range(1, len(closes)):
        a = closes[t - 1]
        b = closes[t]
        if a is None or b is None or a <= 0:
            out.append(None)
        else:
            out.append(b / a - 1.0)
    return out


# --------------------------------------------------------------------------- #
# TSMOM signal (lookahead-safe)
# --------------------------------------------------------------------------- #
def tsmom_signal(closes: Sequence[Optional[float]],
                 lookback: int,
                 skip: int = 0,
                 allow_short: bool = True) -> List[float]:
    """Time-series-momentum position array, lookahead-safe.

    positions[t] is the position HELD INTO return r_t (the t-1 -> t move). It is
    computed from the past return over (t-1-lookback-skip -> t-1-skip), i.e.
    closes strictly prior to the bar whose return r_t we are about to earn.

      - lookback : momentum window length in bars (e.g. 252 ~ 12mo).
      - skip     : skip the most-recent `skip` bars (e.g. 21 -> classic 12-1).
      - allow_short : if True position in {-1,0,+1} (sign of past return);
                      if False position in {0,+1} (long-or-flat).

    positions[t] == 0 until enough history exists. No future bar is ever read.
    """
    n = len(closes)
    pos = [0.0] * n
    need = lookback + skip + 1
    for t in range(n):
        # Position into r_t uses closes through index t-1 ONLY.
        end = t - 1 - skip            # most-recent close used (<= t-1)
        start = end - lookback        # close `lookback` bars before `end`
        if start < 0 or end < 0:
            continue
        p_end = closes[end]
        p_start = closes[start]
        if p_end is None or p_start is None or p_start <= 0:
            continue
        past = p_end / p_start - 1.0
        if past > 0:
            pos[t] = 1.0
        elif past < 0:
            pos[t] = -1.0 if allow_short else 0.0
        else:
            pos[t] = 0.0
    return pos


# --------------------------------------------------------------------------- #
# Single-symbol strategy equity (with cost)
# --------------------------------------------------------------------------- #
@dataclass
class StratResult:
    dates: List[str]
    rets: List[float]            # net per-bar strategy returns (post-cost)
    equity: List[float]          # cumulative equity (starts 1.0)
    positions: List[float]       # position held into each bar's return
    turnover: List[float]        # |w_t - w_{t-1}| per bar

    @property
    def n(self) -> int:
        return len(self.rets)


def run_single(closes: Sequence[Optional[float]],
               dates: Sequence[str],
               positions: Sequence[float],
               cost: Optional[CostModel] = None) -> StratResult:
    """Apply a position array to a single symbol's returns, net of turnover cost.

    net_ret_t = position_t * r_t - turnover_t * spread_bps/1e4
    where turnover_t = |position_t - position_{t-1}| (one-way notional traded).
    Bars with a None return are skipped (treated as no-trade, no return) and do
    NOT advance equity — they are dropped from the output series entirely so the
    Sharpe ruler sees a clean continuous return stream.
    """
    if cost is None:
        cost = fx_cost_model()
    spread = cost.spread_bps / 1e4
    rets = simple_returns(closes)
    out_dates: List[str] = []
    out_rets: List[float] = []
    out_pos: List[float] = []
    out_turn: List[float] = []
    equity = [1.0]
    prev_pos = 0.0
    for t in range(len(closes)):
        r = rets[t]
        p = positions[t]
        if r is None:
            # No realized return this bar; carry position forward without cost
            # accrual on a non-traded bar boundary. We still update prev_pos so a
            # gap doesn't fabricate turnover, but we emit nothing.
            prev_pos = p
            continue
        turn = abs(p - prev_pos)
        net = p * r - turn * spread
        prev_pos = p
        out_dates.append(dates[t])
        out_rets.append(net)
        out_pos.append(p)
        out_turn.append(turn)
        equity.append(equity[-1] * (1.0 + net))
    return StratResult(dates=out_dates, rets=out_rets, equity=equity,
                       positions=out_pos, turnover=out_turn)


# --------------------------------------------------------------------------- #
# Equal-weight basket strategy (with cost) — unlevered
# --------------------------------------------------------------------------- #
def run_basket(symbols: Sequence[str],
               signal_fn,
               cost: Optional[CostModel] = None,
               dates: Optional[List[str]] = None) -> StratResult:
    """Equal-weight TSMOM basket across `symbols`, unlevered, net of cost.

    For each symbol we get a per-bar position in {-1,0,+1} from `signal_fn`,
    then equal-weight: target weight w_i[t] = position_i[t] / N_active[t], where
    N_active[t] is the number of symbols with a defined return at t. Gross
    exposure sum_i |w_i[t]| <= 1.0 (unlevered). Per-bar basket return:
        R_t = sum_i w_i[t] * r_i[t]  -  (sum_i |w_i[t]-w_i[t-1]|) * spread
    Symbols not yet live (None close) contribute nothing and are excluded from
    the active count for that bar.

    `signal_fn(closes) -> List[float]` produces the lookahead-safe position
    array for one symbol's aligned close series.
    """
    if cost is None:
        cost = fx_cost_model()
    spread = cost.spread_bps / 1e4
    dates, closes = aligned_closes(symbols, dates)
    n = len(dates)
    per_ret: Dict[str, List[Optional[float]]] = {}
    per_pos: Dict[str, List[float]] = {}
    for sym in symbols:
        per_ret[sym] = simple_returns(closes[sym])
        per_pos[sym] = signal_fn(closes[sym])

    out_dates: List[str] = []
    out_rets: List[float] = []
    out_gross: List[float] = []
    out_turn: List[float] = []
    equity = [1.0]
    prev_w: Dict[str, float] = {s: 0.0 for s in symbols}
    for t in range(n):
        # Active symbols: those with a defined return this bar.
        active = [s for s in symbols if per_ret[s][t] is not None]
        if not active:
            continue
        nact = len(active)
        w: Dict[str, float] = {s: 0.0 for s in symbols}
        for s in active:
            w[s] = per_pos[s][t] / nact
        R = 0.0
        for s in active:
            R += w[s] * per_ret[s][t]
        turn = 0.0
        for s in symbols:
            turn += abs(w[s] - prev_w[s])
        net = R - turn * spread
        prev_w = w
        out_dates.append(dates[t])
        out_rets.append(net)
        out_gross.append(sum(abs(w[s]) for s in symbols))
        out_turn.append(turn)
        equity.append(equity[-1] * (1.0 + net))
    return StratResult(dates=out_dates, rets=out_rets, equity=equity,
                       positions=out_gross, turnover=out_turn)


# --------------------------------------------------------------------------- #
# Buy-and-hold basket benchmark (unlevered, equal-weight long)
# --------------------------------------------------------------------------- #
def run_basket_buyhold(symbols: Sequence[str],
                       dates: Optional[List[str]] = None) -> StratResult:
    """Equal-weight ALWAYS-LONG basket (the FX 'B&H' benchmark on the same path).

    Long every active symbol at 1/N weight, no shorting, no signal. Costs are
    effectively zero (no rebalancing turnover beyond entry), but we still run it
    through the same accounting with a constant long signal.
    """
    return run_basket(symbols, lambda c: _constant_long(c), dates=dates)


def _constant_long(closes: Sequence[Optional[float]]) -> List[float]:
    """Position = +1 whenever a close exists (else 0). Used by buy-and-hold."""
    return [1.0 if c is not None else 0.0 for c in closes]


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def sharpe(rets: Sequence[float], is_crypto: bool = False) -> float:
    """Annualized Sharpe via the canonical ruler convention (sqrt(252) for FX).

    Mirrors runner.fp_sharpe.sharpe_from_returns (ddof=1, no rf). FX is NOT
    crypto => sqrt(252).
    """
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0:
        return 0.0
    bpy = bars_per_year("1Day", is_crypto)
    return (mean / math.sqrt(var)) * math.sqrt(bpy)


def total_return(rets: Sequence[float]) -> float:
    """Cumulative compounded return of a per-bar return series."""
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    return eq - 1.0


def cagr(rets: Sequence[float], bars_per_yr: float = 252.0) -> float:
    """Compound annual growth rate from a per-bar return series."""
    n = len(rets)
    if n < 2:
        return 0.0
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    if eq <= 0:
        return -1.0
    years = n / bars_per_yr
    if years <= 0:
        return 0.0
    return eq ** (1.0 / years) - 1.0


def max_drawdown(equity: Sequence[float]) -> float:
    """Maximum peak-to-trough drawdown of an equity curve (negative number)."""
    if not equity:
        return 0.0
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = v / peak - 1.0
            if dd < mdd:
                mdd = dd
    return mdd


def pearson_corr(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Pearson correlation of two equal-length return series; None if degenerate."""
    n = min(len(a), len(b))
    if n < 2:
        return None
    a = list(a[:n])
    b = list(b[:n])
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((a[i] - ma) ** 2 for i in range(n))
    vb = sum((b[i] - mb) ** 2 for i in range(n))
    if va <= 0 or vb <= 0:
        return None
    return cov / math.sqrt(va * vb)


def align_returns_by_date(dates_a: Sequence[str], rets_a: Sequence[float],
                          dates_b: Sequence[str], rets_b: Sequence[float]
                          ) -> Tuple[List[float], List[float]]:
    """Inner-join two (dates, returns) series on common dates, preserving order."""
    mb = {d: r for d, r in zip(dates_b, rets_b)}
    oa: List[float] = []
    ob: List[float] = []
    for d, r in zip(dates_a, rets_a):
        if d in mb:
            oa.append(r)
            ob.append(mb[d])
    return oa, ob


def split_is_oos(result: StratResult, boundary: str = "2018-01-01"
                 ) -> Tuple[List[float], List[float]]:
    """Split a StratResult's returns into (in-sample < boundary, oos >= boundary)."""
    is_r: List[float] = []
    oos_r: List[float] = []
    for d, r in zip(result.dates, result.rets):
        if d < boundary:
            is_r.append(r)
        else:
            oos_r.append(r)
    return is_r, oos_r


def spy_returns(dates_filter: Optional[Sequence[str]] = None
                ) -> Tuple[List[str], List[float]]:
    """SPY daily simple returns from the equity cache (adjclose). Optionally
    restricted to a set of dates. Returns (dates, returns) aligned 1:1 (the
    return at index i is the i-1 -> i move; index 0 dropped)."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "data_cache" / "yahoo" / "SPY_parsed.json"
    bars = json.loads(p.read_text())
    bars.sort(key=lambda b: b["date"])
    ds: List[str] = []
    rs: List[float] = []
    prev = None
    for b in bars:
        px = b.get("adjclose") if b.get("adjclose") is not None else b.get("close")
        d = b["date"]
        if prev is not None and prev > 0 and px is not None:
            if dates_filter is None or d in dates_filter:
                ds.append(d)
                rs.append(px / prev - 1.0)
        prev = px
    return ds, rs
