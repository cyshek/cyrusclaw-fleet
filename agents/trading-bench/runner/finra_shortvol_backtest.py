"""
finra_shortvol_backtest.py - honest long/flat daily-overlay backtest for the FINRA
short-volume-ratio (SVR) signal. Self-contained, vectorized, anti-lookahead.

WHY a bespoke engine (not runner/backtest.py): the repo harness is built for intraday
OHLCV bar replay with a per-bar decide(); this lane is a clean DAILY long/flat overlay on a
single index using adjclose-to-adjclose returns and a known position vector. A vectorized
daily engine is more transparent and auditable here. We MIRROR the repo cost convention
exactly: CostModel.alpaca_stocks() = 2 bps one-way (~4 bps round-trip), charged on every
change in position (|pos_t - pos_{t-1}|) -- so strat and benchmark sit on identical footing.

ANTI-LOOKAHEAD (pre-registered): FINRA publishes day-T's short-vol file after the close on
day T. A signal computed from SVR through day T can only be ACTED ON at T+1 open or later.
Implementation: position[t] (decided from data <= close of day t) earns the day-(t+1) return.
Concretely we shift the signal forward one bar: pos_applied[t+1] = signal[t]. We never let
day-T's SVR capture the T-1 -> T move. Strict 1-bar lag.

Returns are adjclose-to-adjclose (split+div adjusted) from the repo's daily_bars_cache.

Metrics: total return, CAGR, Sharpe (annualized sqrt(252) on daily net returns), maxDD,
# round-trips. Benchmark = buy-and-hold of the SAME symbol over the SAME traded path, net of
the SAME cost model (one entry cost at t0, then held).
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from runner import daily_bars_cache as dbc
from runner import finra_shortvol_cache as fsv

ONE_WAY_BPS = 2.0          # CostModel.alpaca_stocks(): 2 bps one-way
TRADING_DAYS = 252


# --------------------------------------------------------------------------------------
# data assembly
# --------------------------------------------------------------------------------------

def _adjclose_map(symbol: str) -> Dict[str, float]:
    """date(iso) -> adjclose for `symbol` from the repo daily bars cache."""
    bars = dbc.get_daily(symbol, use_cache=True)
    return {b["date"]: float(b["adjclose"]) for b in bars if b.get("adjclose") is not None}


def build_aligned(symbol: str,
                  start: Optional[str] = None,
                  end: Optional[str] = None) -> Dict[str, np.ndarray]:
    """Align SVR (FINRA) and price (Yahoo adjclose) on the intersection of trading dates.

    Returns dict of equal-length arrays (ascending date):
        dates (str), svr (float), ret (float, adjclose-to-adjclose simple return for THAT
        day, i.e. close[t]/close[t-1]-1; ret[0]=0), price (adjclose).
    Only dates present in BOTH the FINRA SVR series and the price series are kept.
    """
    svr_rows = fsv.load_svr(symbol)
    px = _adjclose_map(symbol)
    # intersection, ascending
    pairs: List[Tuple[str, float, float]] = []
    for r in svr_rows:
        d = r["date"]
        if d in px:
            pairs.append((d, float(r["svr"]), px[d]))
    pairs.sort(key=lambda x: x[0])
    if start:
        pairs = [p for p in pairs if p[0] >= start]
    if end:
        pairs = [p for p in pairs if p[0] <= end]
    dates = np.array([p[0] for p in pairs])
    svr = np.array([p[1] for p in pairs], dtype=float)
    price = np.array([p[2] for p in pairs], dtype=float)
    ret = np.zeros(len(price), dtype=float)
    if len(price) > 1:
        ret[1:] = price[1:] / price[:-1] - 1.0
    return {"dates": dates, "svr": svr, "ret": ret, "price": price}


# --------------------------------------------------------------------------------------
# signal
# --------------------------------------------------------------------------------------

def rolling_z(x: np.ndarray, window: int) -> np.ndarray:
    """Trailing z-score of x using a window that ENDS at t (inclusive): uses x[t-window+1..t].
    Strictly causal -- no future data. First `window-1` entries are NaN."""
    n = len(x)
    z = np.full(n, np.nan)
    for t in range(window - 1, n):
        w = x[t - window + 1: t + 1]
        mu = w.mean()
        sd = w.std(ddof=0)
        z[t] = (x[t] - mu) / sd if sd > 1e-12 else 0.0
    return z


def rolling_pct(x: np.ndarray, window: int) -> np.ndarray:
    """Trailing percentile rank (0..1) of x[t] within x[t-window+1..t], causal."""
    n = len(x)
    p = np.full(n, np.nan)
    for t in range(window - 1, n):
        w = x[t - window + 1: t + 1]
        p[t] = (w <= x[t]).sum() / len(w)
    return p


def make_signal(svr: np.ndarray,
                window: int,
                threshold: float,
                direction: str,
                hold: int,
                use_pct: bool = False) -> np.ndarray:
    """Build a desired-position series in {0,1} from the SVR.

    direction == 'H1' (contrarian/capitulation): LONG when SVR is EXTREME-HIGH
        (z >= threshold), else flat. Thesis: short-sale over-pressure -> bounce.
    direction == 'H2' (informed-flow): FLAT when SVR is EXTREME-HIGH, else LONG.
        Thesis: elevated short-sale volume predicts weakness -> avoid.

    `hold`: once a trigger fires on day t, the position LATCHES for `hold` days
        (t, t+1, ..., t+hold-1) regardless of subsequent signal, then re-evaluates.
        hold=1 means re-evaluate every day.

    use_pct: interpret `threshold` as a percentile cut in [0,1] instead of a z-score.

    Returns desired position at the CLOSE of each day t (NOT yet lagged for execution).
    """
    n = len(svr)
    if use_pct:
        stat = rolling_pct(svr, window)
    else:
        stat = rolling_z(svr, window)

    extreme_high = np.zeros(n, dtype=bool)
    valid = ~np.isnan(stat)
    extreme_high[valid] = stat[valid] >= threshold

    if direction == "H1":
        base_long = extreme_high          # long when extreme-high
    elif direction == "H2":
        base_long = valid & ~extreme_high  # long when NOT extreme-high (flat when high)
    else:
        raise ValueError(f"bad direction {direction!r}")

    # apply latch/hold
    pos = np.zeros(n, dtype=float)
    if hold <= 1:
        pos[base_long] = 1.0
        # for H2, also require validity (handled above). For H1, before `window-1`
        # there's no signal -> stay flat (pos already 0).
        return pos

    t = 0
    while t < n:
        if base_long[t]:
            end = min(t + hold, n)
            pos[t:end] = 1.0
            t = end
        else:
            t += 1
    return pos


# --------------------------------------------------------------------------------------
# backtest core
# --------------------------------------------------------------------------------------

@dataclass
class StratResult:
    label: str = ""
    symbol: str = ""
    n_days: int = 0
    start: str = ""
    end: str = ""
    total_return: float = 0.0     # fraction, e.g. 0.5 = +50%
    cagr: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0     # negative fraction
    n_roundtrips: float = 0.0
    exposure: float = 0.0         # fraction of days in-market
    equity: List[float] = field(default_factory=list)


def _equity_metrics(net_ret: np.ndarray, dates: np.ndarray, label: str,
                    symbol: str, exposure: float, roundtrips: float) -> StratResult:
    eq = np.cumprod(1.0 + net_ret)
    total = eq[-1] - 1.0 if len(eq) else 0.0
    n = len(net_ret)
    years = n / TRADING_DAYS if n else 1.0
    cagr = (eq[-1] ** (1.0 / years) - 1.0) if (len(eq) and eq[-1] > 0 and years > 0) else float("nan")
    mu = net_ret.mean() if n else 0.0
    sd = net_ret.std(ddof=0) if n else 0.0
    sharpe = (mu / sd * math.sqrt(TRADING_DAYS)) if sd > 1e-12 else 0.0
    # max drawdown
    peak = np.maximum.accumulate(eq) if len(eq) else np.array([1.0])
    dd = (eq / peak - 1.0) if len(eq) else np.array([0.0])
    maxdd = dd.min() if len(dd) else 0.0
    return StratResult(
        label=label, symbol=symbol, n_days=n,
        start=str(dates[0]) if len(dates) else "", end=str(dates[-1]) if len(dates) else "",
        total_return=total, cagr=cagr, sharpe=sharpe, max_drawdown=maxdd,
        n_roundtrips=roundtrips, exposure=exposure, equity=list(eq),
    )


def backtest_overlay(data: Dict[str, np.ndarray],
                     desired_pos_close: np.ndarray,
                     label: str,
                     symbol: str,
                     one_way_bps: float = ONE_WAY_BPS) -> StratResult:
    """Run the long/flat overlay.

    desired_pos_close[t] = position decided at CLOSE of day t (in {0,1}).
    Execution lag (anti-lookahead): the position EARNED on day t's return is the one
    decided at the close of day t-1:  pos_eff[t] = desired_pos_close[t-1].
    Costs charged whenever pos_eff changes, on |pos_eff[t]-pos_eff[t-1]| * one_way_bps.
    """
    ret = data["ret"]
    dates = data["dates"]
    n = len(ret)

    pos_eff = np.zeros(n, dtype=float)
    pos_eff[1:] = desired_pos_close[:-1]      # strict 1-bar lag

    # transaction cost as a return drag on the day the position changes
    turn = np.zeros(n, dtype=float)
    turn[0] = abs(pos_eff[0])                  # initial entry if any
    turn[1:] = np.abs(pos_eff[1:] - pos_eff[:-1])
    cost = turn * (one_way_bps / 1e4)

    gross = pos_eff * ret
    net = gross - cost

    exposure = float((pos_eff > 0).mean()) if n else 0.0
    roundtrips = float(turn.sum() / 2.0)      # each round-trip = enter+exit = 2 units turnover
    return _equity_metrics(net, dates, label, symbol, exposure, roundtrips)


def backtest_buyhold(data: Dict[str, np.ndarray], symbol: str,
                     one_way_bps: float = ONE_WAY_BPS) -> StratResult:
    """Buy-and-hold benchmark on the SAME traded path: enter at first day (pay one-way cost
    once), hold fully thereafter."""
    ret = data["ret"]
    dates = data["dates"]
    n = len(ret)
    pos_eff = np.ones(n, dtype=float)
    cost = np.zeros(n, dtype=float)
    cost[0] = one_way_bps / 1e4               # single entry cost
    net = pos_eff * ret - cost
    return _equity_metrics(net, dates, "BUYHOLD", symbol, 1.0, 0.5)


if __name__ == "__main__":
    # quick self-check on whatever SPY data is cached
    d = build_aligned("SPY")
    print(f"SPY aligned days: {len(d['dates'])} "
          f"({d['dates'][0] if len(d['dates']) else '-'} -> "
          f"{d['dates'][-1] if len(d['dates']) else '-'})")
    print(f"SVR mean={d['svr'].mean():.3f} std={d['svr'].std():.3f} "
          f"min={d['svr'].min():.3f} max={d['svr'].max():.3f}")
    bh = backtest_buyhold(d, "SPY")
    print(f"buyhold: total={bh.total_return:.3f} cagr={bh.cagr:.3f} "
          f"sharpe={bh.sharpe:.3f} maxdd={bh.max_drawdown:.3f}")
