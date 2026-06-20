"""THROWAWAY driver — full-history out-of-sample test of the leveraged-trend edge.

NOT a live strategy. Extends reports/LEVERAGED_TREND_20260604T055554Z.md (which
was capped at a single 2020-12 -> 2026 window riding the semis super-cycle) onto
FULL leveraged-ETF history (inception -> 2026) to answer the question the 06-04
report explicitly could not: does the SOXL/TQQQ/UPRO trend edge SURVIVE pre-2020
(2018-Q4 selloff, 2020 COVID crash, 2022 bear), or is +755% a super-cycle artifact?

Faithful standalone re-impl of strategies_candidates/leveraged_trend/strategy.py
trend logic (same 4 filters, same regime double-confirm), run on Yahoo-v8 adjclose
(split+div-adjusted — leveraged ETFs split constantly) from runner.daily_bars_cache.
Reuses the canonical rulers: runner.backtest.CostModel.alpaca_stocks() on every
fill, runner.fp_sharpe.sharpe_from_returns (sqrt(252) annualization).

LEAK-FREE CONSTRUCTION (1-day signal lag):
  - The trend gate for date D is computed from adjcloses through D (inclusive of
    D's own close — i.e. you observe D's close at EOD).
  - The resulting position (risk-on=full ETF / risk-off=cash) is applied to the
    NEXT bar's return r[D+1] = adj[D+1]/adj[D] - 1.
  This is the standard "decide at close D, hold into D+1" rule. It is exactly why
  a catastrophic 3x gap-down (COVID 2020-03) is NOT dodged for free: the exit
  signal fires on the close of the down day and only takes you flat the following
  day — the gap is eaten. We measure that honestly.

COST MODEL: alpaca_stocks() = 2 bps one-way spread. Charged as a return haircut on
every position TRANSITION (flat->held costs the buy spread; held->flat costs the
sell spread). Round-trip ~4 bps. Idle cash earns 0 (conservative; no T-bill yield).

INSTRUMENT-LEVEL MaxDD: the worst drawdown-from-entry on the 3x INSTRUMENT itself
while held (peak-to-trough of the held adjclose path within each holding spell),
NOT the idle-cash-diluted NAV DD. This is the binding number per the 06-04 report
+ BACKLOG warning.

Output: reports/_lev_trend_fullhist_results.json (consumed by the .md write-up).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from runner import daily_bars_cache as dbc
from runner.backtest import CostModel
from runner.fp_sharpe import sharpe_from_returns
from runner.backtest import bars_per_year

WORKSPACE = Path(__file__).resolve().parent.parent
OUT = WORKSPACE / "reports" / "_lev_trend_fullhist_results.json"

COST = CostModel.alpaca_stocks()          # 2 bps one-way
BUY_HAIRCUT = COST.spread_bps / 1e4       # fraction lost entering
SELL_HAIRCUT = COST.spread_bps / 1e4      # fraction lost exiting
BPY = bars_per_year("1Day", False)        # 252

_UNDERLYING = {"UPRO": "SPY", "TQQQ": "QQQ", "SOXL": "SOXX"}

# ---- the sweep grid (identical to 06-04) -------------------------------------
FILTER_MODES = ["sma", "sma_cross", "momentum", "donchian"]
SLOWS = [50, 100, 150, 200]
FASTS = [10, 20, 50]
REGIMES = [False, True]
REGIME_LOOKBACK = 100
INSTRUMENTS = ["SOXL", "TQQQ", "UPRO"]

# Walk-forward split boundary (ISO). Train = inception..2019-12-31; OOS = 2020-01-01..
SPLIT = "2020-01-01"


# ============================================================================ #
# Series assembly
# ============================================================================ #
def _adj_series(sym: str) -> Tuple[List[str], List[float]]:
    """(dates, adjcloses) ascending for `sym`."""
    bars = dbc.get_daily(sym)
    ds = [b["date"] for b in bars]
    ac = [float(b["adjclose"]) for b in bars]
    return ds, ac


def _aligned_underlying(under_dates: List[str], under_adj: List[float],
                        target_dates: List[str]) -> List[Optional[float]]:
    """Forward-fill the underlying adjclose onto the target (ETF) date axis with
    NO lookahead: for each target date D, the most-recent underlying bar with
    date <= D. Returns a list parallel to target_dates (None before first)."""
    out: List[Optional[float]] = []
    j = 0
    n = len(under_dates)
    last = None
    for d in target_dates:
        while j < n and under_dates[j] <= d:\n            last = under_adj[j]\n            j += 1\n        out.append(last)\n    return out\n\n\n# ============================================================================ #
# Trend signal (faithful to strategy.py _trend_on) — operates on adjclose
# ============================================================================ #
def _sma(vals: List[float], n: int, end: int) -> Optional[float]:
    """SMA of vals[end-n+1 .. end] inclusive (uses bars up to index `end`)."""
    if end + 1 < n:\n        return None\n    return sum(vals[end - n + 1:end + 1]) / n


def _signal_at(closes: List[float], i: int, mode: str, slow: int, fast: int
               ) -> Optional[bool]:
    """Trend stance using closes[0..i] INCLUSIVE (i = decision close, EOD D).
    Returns True=risk-on, False=risk-off, None=insufficient/ambiguous (caller
    holds prior stance). Mirrors strategy._trend_on exactly."""
    price = closes[i]
    if mode == "sma":
        s = _sma(closes, slow, i)
        return None if s is None else price > s
    if mode == "sma_cross":
        sf = _sma(closes, fast, i)
        ss = _sma(closes, slow, i)
        if sf is None or ss is None:
            return None
        return sf > ss
    if mode == "momentum":
        if i < slow:
            return None
        return closes[i] > closes[i - slow]
    if mode == "donchian":
        if i < slow:
            return None
        prior = closes[:i]               # exclude current bar from the channel
        hi = max(prior[-slow:])
        lo = min(prior[-fast:])
        if price >= hi:
            return True
        if price <= lo:
            return False
        return None                      # in-channel: hold current stance
    return None


def _stance_path(closes: List[float], und: Optional[List[Optional[float]]],
                 mode: str, slow: int, fast: int, regime: bool
                 ) -> List[bool]:
    """Risk-on/off stance DECIDED at each close i (EOD of date D), to be applied
    to the return from D->D+1. Handles donchian/insufficient 'hold prior' and the
    optional underlying regime double-confirm (price>SMA(REGIME_LOOKBACK))."""
    n = len(closes)
    stance = [False] * n
    cur = False
    for i in range(n):
        sig = _signal_at(closes, i, mode, slow, fast)
        if sig is None:
            cur = cur  # hold prior stance (donchian in-channel / priming)
        else:
            cur = sig
        on = cur
        if on and regime and und is not None:
            uv = und[i]
            # need REGIME_LOOKBACK underlying points up to i
            if uv is not None:
                us = _sma([x for x in und[:i + 1] if x is not None],
                          REGIME_LOOKBACK, end=None) if False else None
                # compute SMA over the last REGIME_LOOKBACK non-None underlying vals <= i
                vals = [x for x in und[:i + 1] if x is not None]
                if len(vals) >= REGIME_LOOKBACK:
                    sma_u = sum(vals[-REGIME_LOOKBACK:]) / REGIME_LOOKBACK
                    if uv <= sma_u:\n                        on = False\n        stance[i] = on\n    return stance\n\n\n# ============================================================================ #
# Backtest a single cell over a [lo,hi) index slice of the ETF series
# ============================================================================ #
def _run_cell(dates: List[str], adj: List[float], stance: List[bool],
              lo: int, hi: int) -> dict:
    """Apply `stance` (decided at close i) to the return i->i+1, over indices
    [lo, hi). Charges cost on transitions. Returns metrics dict.

    instrument-level MaxDD: worst peak-to-trough of the held adjclose path within
    each contiguous holding spell (drawdown-from-entry-or-peak on the 3x ETF).
    """
    rets: List[float] = []           # per-step strategy returns (net of cost)
    eq = 1.0
    equity = [1.0]
    prev_held = False
    n_trades = 0
    days_in = 0

    # instrument DD tracking within holding spells
    inst_peak = None                 # running peak adjclose while held
    worst_inst_dd = 0.0              # most negative (fraction)

    # i ranges over decision closes; apply to i->i+1 return. Need i+1 < len.
    start = max(lo, 1)               # need a prior bar to form a return baseline
    for i in range(start, hi):
        if i + 1 >= len(adj):
            break
        held = stance[i]             # stance decided at close i, held into i+1
        r_px = adj[i + 1] / adj[i] - 1.0
        # transition cost (charged on the step where the position changes)
        cost = 0.0
        if held and not prev_held:
            cost += BUY_HAIRCUT
            n_trades += 1
        elif (not held) and prev_held:
            cost += SELL_HAIRCUT
        step_ret = (r_px - cost) if held else (0.0 - cost)
        # when going flat, the sell cost still applies once (above); when staying
        # flat, step_ret=0. When staying held, r_px with no cost.
        if not held and not prev_held:
            step_ret = 0.0
        rets.append(step_ret)
        eq *= (1.0 + step_ret)
        equity.append(eq)

        # instrument DD: track only while held, on the raw adjclose path
        if held:
            days_in += 1
            px = adj[i + 1]
            if not prev_held or inst_peak is None:
                inst_peak = adj[i]      # entry baseline
            inst_peak = max(inst_peak, px)
            dd = px / inst_peak - 1.0
            if dd < worst_inst_dd:
                worst_inst_dd = dd
        else:
            inst_peak = None
        prev_held = held

    total_ret = eq - 1.0
    sharpe = sharpe_from_returns(rets, BPY)
    n_steps = len(rets)
    yrs = n_steps / BPY if n_steps else 0.0
    cagr = ((eq) ** (1.0 / yrs) - 1.0) if yrs > 0 and eq > 0 else float("nan")
    # NAV (diluted) DD for reference
    nav_peak = equity[0]
    nav_dd = 0.0
    for v in equity:
        nav_peak = max(nav_peak, v)
        nav_dd = min(nav_dd, v / nav_peak - 1.0)
    return {
        "total_ret_pct": total_ret * 100.0,
        "cagr_pct": cagr * 100.0 if cagr == cagr else None,
        "sharpe": sharpe,
        "inst_dd_pct": worst_inst_dd * 100.0,
        "nav_dd_pct": nav_dd * 100.0,
        "n_trades": n_trades,
        "n_steps": n_steps,
        "days_in_pct": (100.0 * days_in / n_steps) if n_steps else 0.0,
        "first": dates[start] if start < len(dates) else None,
        "last": dates[min(hi, len(dates)) - 1] if hi > 0 else None,
    }


def _buyhold(dates: List[str], adj: List[float], lo: int, hi: int) -> dict:
    """Buy-and-hold the instrument over [lo,hi) with one entry cost. instrument
    DD == NAV DD here (always fully invested)."""
    start = max(lo, 1)
    rets: List[float] = []
    eq = 1.0
    equity = [1.0]
    peak = None
    worst = 0.0
    first_step = True
    for i in range(start, hi):
        if i + 1 >= len(adj):
            break
        r = adj[i + 1] / adj[i] - 1.0
        if first_step:
            r -= BUY_HAIRCUT
            first_step = False
        rets.append(r)
        eq *= (1.0 + r)
        equity.append(eq)
        px = adj[i + 1]
        peak = adj[start] if peak is None else max(peak, px)
        worst = min(worst, px / peak - 1.0)
    total = eq - 1.0
    sharpe = sharpe_from_returns(rets, BPY)
    yrs = len(rets) / BPY if rets else 0.0
    cagr = (eq ** (1.0 / yrs) - 1.0) if yrs > 0 and eq > 0 else None
    return {
        "total_ret_pct": total * 100.0,
        "cagr_pct": cagr * 100.0 if cagr else None,
        "sharpe": sharpe,
        "inst_dd_pct": worst * 100.0,
        "n_steps": len(rets),
        "first": dates[start] if start < len(dates) else None,
        "last": dates[min(hi, len(dates)) - 1] if hi > 0 else None,
    }


def _idx_at_or_after(dates: List[str], iso: str) -> int:
    """First index with date >= iso (len if none)."""
    for k, d in enumerate(dates):
        if d >= iso:
            return k
    return len(dates)


# ============================================================================ #
# Driver
# ============================================================================ #
def main() -> dict:
    out: Dict[str, object] = {"split": SPLIT, "cost_bps_oneway": COST.spread_bps,
                              "instruments": {}}

    # preload underlyings once
    under_cache: Dict[str, Tuple[List[str], List[float]]] = {}
    for u in set(_UNDERLYING.values()):
        under_cache[u] = _adj_series(u)

    # benchmarks (full + OOS), aligned per-instrument span below
    for inst in INSTRUMENTS:
        dates, adj = _adj_series(inst)
        n = len(dates)
        und_sym = _UNDERLYING[inst]
        ud, ua = under_cache[und_sym]
        und_aligned = _aligned_underlying(ud, ua, dates)

        split_i = _idx_at_or_after(dates, SPLIT)

        cells: List[dict] = []
        for mode in FILTER_MODES:
            slow_list = SLOWS
            for slow in slow_list:
                fast_list = FASTS if mode in ("sma_cross", "donchian") else [0]
                for fast in fast_list:
                    for regime in REGIMES:
                        stance = _stance_path(adj, und_aligned, mode, slow,
                                              fast, regime)
                        full = _run_cell(dates, adj, stance, 0, n)
                        train = _run_cell(dates, adj, stance, 0, split_i)
                        oos = _run_cell(dates, adj, stance, split_i, n)
                        cells.append({
                            "mode": mode, "slow": slow, "fast": fast,
                            "regime": regime,
                            "full": full, "train": train, "oos": oos,
                        })

        # benchmarks over matched spans
        bh_inst_full = _buyhold(dates, adj, 0, n)
        bh_inst_oos = _buyhold(dates, adj, split_i, n)

        # SPY + ^GSPC benchmarks aligned to THIS instrument's date axis
        bench = {}
        for bsym in ("SPY", "^GSPC"):
            bd, ba = _adj_series(bsym)
            ba_aligned = _aligned_underlying(bd, ba, dates)
            # build a clean (date, adj) on the instrument axis (drop leading None)
            ax_dates, ax_adj = [], []
            for d, v in zip(dates, ba_aligned):
                if v is not None:
                    ax_dates.append(d)
                    ax_adj.append(v)
            bn = len(ax_dates)
            bsplit = _idx_at_or_after(ax_dates, SPLIT)
            bench[bsym] = {
                "full": _buyhold(ax_dates, ax_adj, 0, bn),
                "oos": _buyhold(ax_dates, ax_adj, bsplit, bn),
            }

        out["instruments"][inst] = {
            "span": {"first": dates[0], "last": dates[-1], "n": n,
                     "split_idx": split_i, "split_date": dates[split_i] if split_i < n else None},
            "cells": cells,
            "bh_instrument": {"full": bh_inst_full, "oos": bh_inst_oos},
            "benchmarks": bench,
        }

    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    res = main()
    print(f"[driver] wrote {OUT}")
    for inst, blob in res["instruments"].items():
        sp = blob["span"]
        print(f"{inst}: {sp['first']}..{sp['last']} n={sp['n']} "
              f"split@{sp['split_date']} cells={len(blob['cells'])}")
