"""Cross-sectional (multi-symbol) backtest harness.

Sister module to `runner/backtest.py`. Where `backtest.py` replays a
single symbol's bars through a single-symbol `decide()` function, this
module steps a *synced bar clock* across N symbols simultaneously and
calls a cross-sectional decide function:

    decide_xsec(market_state, position_state, params) -> {symbol: Action}

where:

    market_state = {
        "timeframe": str,
        "clock_t": str,                # ISO 8601 timestamp of the current tick
        "symbols": {
            sym: {
                "bars":  list[dict],   # oldest-first; only bars whose t <= clock_t
                "last_price": float|None,   # close of the most recent visible bar
                "has_bar": bool,       # True iff sym had a bar AT clock_t
            }
        },
        "regime": dict|None,           # same SPY regime slice as backtest.py
        "strategy_state": dict,        # cross-flat persistent state (mutable)
    }

    position_state = {
        sym: {
            "qty": float,
            "market_value": float,        # qty * last_price
            "avg_entry_price": float,
        }
    }   # ONLY contains held names; flat names absent.

    Action: same duck-typed object as the single-symbol harness
            (.action, .symbol, .notional_usd, .qty, .reason). One per
            symbol the strategy wants to act on this tick. Any symbol
            absent from the returned dict is implicitly "hold".

## Why a wrapper-of-singletons (design (A)) instead of a true multi-symbol rewrite (design (B))

The three target archetypes (cross-sec momentum, low-vol, sector rotation)
all share the same shape: compute features per symbol independently →
rank → allocate. None require *intra-bar* synchronous coordination
between symbols. So we don't need to rewrite the inner loop; we need a
synced clock + a ranking layer on top.

This module composes the existing single-symbol semantics (no-lookahead,
safety_backstop, cost model, per-trade excursion, regime injection) by
running per-symbol position state through the same fill mechanics as
`backtest.py`, but with one OUTER loop driving all symbols off a shared
clock. The strategy author gets cross-sectional visibility without us
forking the inner loop.

## Risk-cap enforcement (the load-bearing invariant)

`MAX_NOTIONAL = $100` is per-strategy, not per-symbol. With N symbols
the cap is SHARED across the basket. This module enforces:

    sum(action.notional_usd for buy/sell actions this tick)
      + current_total_position_usd
      <= MAX_POSITION

If the strategy proposes a basket whose total exceeds the cap, we
proportionally scale ALL buy notionals down so the basket fits. We do
NOT silently drop the basket — that would be a worse failure mode than
a clamped-but-deployed basket. Each individual leg still has to satisfy
the standard per-trade caps (notional <= MAX_NOTIONAL, projected
per-symbol position <= MAX_POSITION).

`MAX_TRADES_PER_DAY` is also per-strategy. Multiple symbols traded on
the same UTC day all count toward the same daily quota. A strategy
trying to rebalance 5 names on day 1 hits the daily cap after 4 fills;
the 5th is skipped (logged).

## CLI

    python3 -m runner.backtest_xsec --strategy xsec_test --basket BTC/USD,ETH/USD
    python3 -m runner.backtest_xsec --strategy xsec_test --basket-file baskets/sectors.txt
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import bars_cache  # noqa: E402
from . import safety_backstop  # noqa: E402
from .backtest import (  # noqa: E402
    BARS_PER_YEAR,
    bars_per_year,
    CostModel,
    MAX_NOTIONAL,
    MAX_POSITION,
    MAX_TRADES_PER_DAY,
    _bar_utc_day,
    _bt_check_trade,
)
from . import risk as risk_mod  # noqa: E402


STRATEGIES_ROOT = WORKSPACE / "strategies"


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------

@dataclass
class XSecPerSymbol:
    """Per-symbol slice of a cross-sectional backtest result."""
    symbol: str
    n_bars: int = 0
    n_buys: int = 0
    n_closes: int = 0
    n_skipped_risk: int = 0
    realized_pnl_usd: float = 0.0
    final_qty: float = 0.0
    final_market_value: float = 0.0
    closed_trades: List[dict] = field(default_factory=list)
    skipped_reasons: List[str] = field(default_factory=list)
    total_costs_usd: float = 0.0


@dataclass
class XSecBacktestResult:
    """Aggregate result for a cross-sectional backtest across N symbols."""
    strategy: str
    symbols: List[str] = field(default_factory=list)
    timeframe: str = ""
    n_ticks: int = 0
    n_trades: int = 0           # sum of buys + closes across all symbols
    n_buys: int = 0
    n_closes: int = 0
    n_skipped_risk: int = 0
    n_basket_clamps: int = 0    # # of ticks where basket got proportionally scaled
    total_return_usd: float = 0.0
    total_return_pct: float = 0.0
    sharpe: float = 0.0
    max_drawdown_pct: float = 0.0       # PORTFOLIO-NAV drawdown (diluted by idle cash)
    worst_instrument_dd_pct: float = 0.0  # DEPLOYED-CAPITAL drawdown: worst single-leg
                                          # DD-from-entry across all trades (closed +
                                          # open-at-window-end). NOT diluted by the ~90%
                                          # cash sleeve. This is the number GATE Bar A
                                          # #5(b) BINDS on (2026-05-31 RULING 2). A -50%
                                          # crash on one $100 leg shows here as -50%,
                                          # whereas max_drawdown_pct would dilute it to
                                          # ~-5% against the $1000 portfolio NAV.
    starting_equity: float = 0.0
    final_equity: float = 0.0
    total_costs_usd: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    per_symbol: Dict[str, XSecPerSymbol] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Bar-clock alignment
# ---------------------------------------------------------------------------

def build_clock(bars_by_symbol: Dict[str, List[dict]]) -> List[str]:
    """Union of all bar timestamps across all symbols, sorted ascending.

    Each clock tick is a distinct ISO timestamp. At a given tick t:
      - some symbols had a bar at exactly t (their `has_bar` is True);
      - other symbols' most recent bar is strictly older than t (they
        still get visible bars + a stale last_price, has_bar=False).

    This is the "synced bar clock" referenced in the module docstring.
    Sorting ISO 8601 lexicographically is correct because all timestamps
    use the same UTC `Z` suffix and identical width.
    """
    seen = set()
    for sym, bars in bars_by_symbol.items():
        for b in bars:
            t = b.get("t")
            if t is None:
                continue
            seen.add(str(t))
    return sorted(seen)


def _index_by_t(bars: List[dict]) -> Dict[str, int]:
    """Map bar timestamp -> 0-based index within `bars`. O(N) build, O(1) lookup."""
    out: Dict[str, int] = {}
    for i, b in enumerate(bars):
        t = b.get("t")
        if t is not None and t not in out:
            out[str(t)] = i
    return out


# ---------------------------------------------------------------------------
# Strategy loader (cross-sectional flavor)
# ---------------------------------------------------------------------------

CANDIDATES_ROOT = WORKSPACE / "strategies_candidates"


def load_xsec_strategy(name: str, *, candidate: bool = False) -> Tuple[Callable, dict]:
    """Load a cross-sectional strategy module.

    Convention: `strategies/<name>/strategy.py` must export `decide_xsec`
    (not `decide`). `params.json` should include a `basket` list
    (e.g. `"basket": ["XLK","XLF","XLE"]`) but the basket may be
    overridden at call-time via the `--basket` CLI flag.

    When `candidate=True`, the strategy is loaded from
    `strategies_candidates/<name>/strategy.py` instead, mirroring
    `runner.candidate_smoke.load_candidate` / `runner.load_strategy`.
    This lets in-evaluation xsec candidates run through the same harness
    as live strategies without the manual `spec_from_file_location`
    bypass the `_run_xsec_*_wf.py` driver scripts used to need.
    WORKSPACE is added to `sys.path` so the candidate's
    `from strategies._lib import ...` imports resolve exactly as they
    would in the live runner.
    """
    root = CANDIDATES_ROOT if candidate else STRATEGIES_ROOT
    pkg = "strategies_candidates" if candidate else "strategies"
    label = "candidate dir" if candidate else "strategy dir"
    strat_dir = root / name
    params_path = strat_dir / "params.json"
    if not strat_dir.is_dir():
        raise FileNotFoundError(f"No {label}: {strat_dir}")
    if not params_path.exists():
        raise FileNotFoundError(f"No params.json: {params_path}")
    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))
    module = importlib.import_module(f"{pkg}.{name}.strategy")
    if not hasattr(module, "decide_xsec"):
        raise AttributeError(
            f"{pkg}.{name}.strategy must export decide_xsec(...) for "
            f"the cross-sectional harness")
    params = json.loads(params_path.read_text())
    return module.decide_xsec, params


# ---------------------------------------------------------------------------
# Per-symbol mutable position state
# ---------------------------------------------------------------------------

@dataclass
class _PosBook:
    """Authoritative per-symbol cash-impact bookkeeping. Kept inside this
    module; strategies never see it directly. They see the read-only
    `position_state` view derived from this."""
    qty: float = 0.0
    cost_basis_usd: float = 0.0
    avg_entry_price: float = 0.0
    entry_bar_idx: Optional[int] = None   # tick index, not bar index
    trade_low_seen: Optional[float] = None
    trade_high_seen: Optional[float] = None
    # Strategy-owned bookkeeping the cross-flat protocol allows (running_max etc.).
    extras: Dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Risk: basket-level enforcement
# ---------------------------------------------------------------------------

def _clamp_basket(
    actions: Dict[str, "object"],
    books: Dict[str, _PosBook],
    last_price_by_sym: Dict[str, Optional[float]],
) -> Tuple[Dict[str, float], bool]:
    """Compute clamped notionals for the basket.

    Inputs:
      actions: {sym: Action} as returned by the strategy. Only buy/sell
               actions consume the basket cap; closes free it.
      books:   current per-symbol _PosBook.
      last_price_by_sym: most-recent visible close per symbol.

    Returns:
      (clamped_notionals, was_clamped)
      clamped_notionals: {sym: notional_to_use} for buy/sell actions only.
                        Closes are not present (notional is determined at
                        fill time from held qty).
      was_clamped: True iff the strategy's requested notionals exceeded
                   MAX_POSITION across the basket and we had to scale.

    Algorithm:
      - existing_pos_usd = sum(qty * last_price) over symbols currently held
                           and NOT being closed this tick.
      - requested_buy_usd = sum(notional) over buy/sell actions this tick.
      - cap_headroom = max(0, MAX_POSITION - existing_pos_usd).
      - If requested_buy_usd <= cap_headroom: pass through unchanged.
      - Else: scale each buy notional by (cap_headroom / requested_buy_usd).

    Per-leg notional caps (each leg <= MAX_NOTIONAL) are NOT enforced
    here — they're enforced downstream by _bt_check_trade. The basket
    clamp only enforces the SHARED cap; per-leg caps stay where they
    were.
    """
    closing_syms = {sym for sym, a in actions.items()
                    if getattr(a, "action", "hold") == "close"}
    # Existing exposure from positions NOT being closed this tick.
    existing_pos_usd = 0.0
    for sym, book in books.items():
        if book.qty <= 0:
            continue
        if sym in closing_syms:
            continue
        px = last_price_by_sym.get(sym) or book.avg_entry_price
        existing_pos_usd += book.qty * px
    # Requested fresh buy/sell notionals.
    requested: Dict[str, float] = {}
    for sym, a in actions.items():
        act = getattr(a, "action", "hold")
        if act in ("buy", "sell"):
            n = float(getattr(a, "notional_usd", 0.0) or 0.0)
            if n > 0:
                requested[sym] = n
    if not requested:
        return ({}, False)
    requested_total = sum(requested.values())
    cap_headroom = max(0.0, MAX_POSITION - existing_pos_usd)
    if requested_total <= cap_headroom + 1e-9:
        return (requested, False)
    if cap_headroom <= 0:
        # No room at all: zero out all buys, return clamped flag.
        return ({sym: 0.0 for sym in requested}, True)
    scale = cap_headroom / requested_total
    return ({sym: n * scale for sym, n in requested.items()}, True)


# ---------------------------------------------------------------------------
# Core cross-sectional backtest
# ---------------------------------------------------------------------------

def backtest_xsec(
    strategy_name: str,
    bars_by_symbol: Dict[str, List[dict]],
    params: dict,
    *,
    starting_cash: float = 1000.0,
    decide_xsec_fn: Optional[Callable] = None,
    cost_model_by_symbol: Optional[Dict[str, CostModel]] = None,
    default_cost_model: Optional[CostModel] = None,
) -> XSecBacktestResult:
    """Replay multiple symbols through a cross-sectional strategy.

    Args:
        strategy_name: label only.
        bars_by_symbol: {sym: oldest-first OHLCV bars}. Symbols may have
            *different* numbers of bars (e.g. a new listing). The harness
            handles this via the synced clock — at a given tick a symbol
            with no bar yet is exposed as `has_bar=False, last_price=None`
            and is NOT eligible for fills.
        params: strategy params dict; passed to decide_xsec.
        starting_cash: notional reference for total_return_pct.
        decide_xsec_fn: override decide function (for tests). If None,
            load from `strategies.<name>.strategy.decide_xsec`.
        cost_model_by_symbol: optional per-symbol CostModel. Symbols not
            in the map fall back to `default_cost_model`, which itself
            falls back to `CostModel.for_symbol(sym)` (crypto vs stocks
            auto-pick).
        default_cost_model: fallback CostModel for symbols not in the map.

    Returns: XSecBacktestResult.
    """
    timeframe = str(params.get("timeframe", "1Hour"))
    symbols = sorted(bars_by_symbol.keys())
    # Basket-aware per-day trade cap. xsec strategies that declare
    # `xsec_basket_size: K` in params get max(MAX_TRADES_PER_DAY, 2*K) so
    # a K-leg rebalance day (close K + open K) isn't silently truncated
    # at trade #4 by the legacy single-symbol cap. See runner/risk.py.
    max_trades_per_day = risk_mod.resolve_trades_per_day(params)

    result = XSecBacktestResult(
        strategy=strategy_name,
        symbols=list(symbols),
        timeframe=timeframe,
        starting_equity=starting_cash,
    )

    if not symbols:
        result.equity_curve = [starting_cash]
        result.final_equity = starting_cash
        return result

    # Resolve cost models per symbol.
    cm_map: Dict[str, CostModel] = {}
    for sym in symbols:
        if cost_model_by_symbol and sym in cost_model_by_symbol:
            cm_map[sym] = cost_model_by_symbol[sym]
        elif default_cost_model is not None:
            cm_map[sym] = default_cost_model
        else:
            cm_map[sym] = CostModel.for_symbol(sym)

    # Resolve strategy.
    if decide_xsec_fn is None:
        decide_xsec_fn, _ = load_xsec_strategy(strategy_name)

    # Build the synced clock + per-symbol t→idx maps.
    clock = build_clock(bars_by_symbol)
    if not clock:
        result.equity_curve = [starting_cash]
        result.final_equity = starting_cash
        return result

    idx_by_sym: Dict[str, Dict[str, int]] = {
        sym: _index_by_t(bars_by_symbol[sym]) for sym in symbols
    }
    # Most-recent visible bar index per symbol; starts at -1 (no bars yet).
    cursor_by_sym: Dict[str, int] = {sym: -1 for sym in symbols}

    # Optional regime fetch — at-most-once across all symbols.
    # Crypto baskets (any "/" in any symbol) skip regime by convention; if
    # mixed, we conservatively skip too (one strategy = one regime story).
    spy_closes_all: List[float] = []
    spy_times_all: List[str] = []
    any_crypto = any("/" in s for s in symbols)
    if not any_crypto:
        try:
            first_t = clock[0]
            last_t = clock[-1]
            from datetime import datetime as _dt
            try:
                end_dt_spy = _dt.strptime(last_t[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                end_dt_spy = None
            try:
                first_dt = _dt.strptime(first_t[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                first_dt = None
            if end_dt_spy and first_dt:
                span_days = (end_dt_spy - first_dt).days + 200
                spy_bars = bars_cache.get_bars("SPY", "1Day",
                                               days=max(span_days, 200),
                                               end_dt=end_dt_spy)
                spy_closes_all = [float(b["c"]) for b in (spy_bars or [])]
                spy_times_all = [str(b.get("t", "")) for b in (spy_bars or [])]
        except Exception:
            spy_closes_all = []
            spy_times_all = []

    # Portfolio state.
    cash = float(starting_cash)
    books: Dict[str, _PosBook] = {sym: _PosBook() for sym in symbols}
    per_sym_result: Dict[str, XSecPerSymbol] = {
        sym: XSecPerSymbol(symbol=sym) for sym in symbols
    }
    for sym in symbols:
        per_sym_result[sym].n_bars = len(bars_by_symbol[sym])

    trades_by_day: Dict[str, int] = {}
    equity_curve: List[float] = []
    total_costs_usd = 0.0
    n_basket_clamps = 0
    persistent_state: dict = {}

    n_buys_total = 0
    n_closes_total = 0
    n_skipped_total = 0

    for tick_idx, t in enumerate(clock):
        # Advance per-symbol cursor IF this symbol had a bar at exactly t.
        # Otherwise the cursor stays put (last visible bar is older than t).
        last_price_by_sym: Dict[str, Optional[float]] = {}
        has_bar_at_t: Dict[str, bool] = {}
        for sym in symbols:
            mapping = idx_by_sym[sym]
            if t in mapping:
                cursor_by_sym[sym] = mapping[t]
                has_bar_at_t[sym] = True
            else:
                has_bar_at_t[sym] = False
            cur = cursor_by_sym[sym]
            if cur >= 0:
                last_price_by_sym[sym] = float(bars_by_symbol[sym][cur]["c"])
            else:
                last_price_by_sym[sym] = None

        # Update per-trade excursion for any open positions (only for
        # symbols that had a bar this tick — otherwise we have no fresh
        # high/low to record).
        for sym, book in books.items():
            if book.qty > 0 and has_bar_at_t[sym]:
                bar = bars_by_symbol[sym][cursor_by_sym[sym]]
                close = float(bar["c"])
                try:
                    bar_low = float(bar.get("l", close))
                    bar_high = float(bar.get("h", close))
                except (TypeError, ValueError):
                    bar_low = close
                    bar_high = close
                if book.trade_low_seen is None or bar_low < book.trade_low_seen:
                    book.trade_low_seen = bar_low
                if book.trade_high_seen is None or bar_high > book.trade_high_seen:
                    book.trade_high_seen = bar_high

        # Build the regime slice once per tick (no per-symbol divergence).
        regime_state: Optional[dict] = None
        if spy_closes_all:
            tick_date = t[:10]
            visible_n = 0
            for ti, st in enumerate(spy_times_all):
                if st[:10] <= tick_date:
                    visible_n = ti + 1
                else:
                    break
            if visible_n > 0:
                visible_closes = spy_closes_all[:visible_n]
                regime_state = {
                    "spy_closes": visible_closes,
                    "spy_last": visible_closes[-1],
                }

        # Per-symbol bar slice (walk-forward: only bars whose t <= clock_t).
        symbols_view: Dict[str, dict] = {}
        for sym in symbols:
            cur = cursor_by_sym[sym]
            if cur < 0:
                symbols_view[sym] = {
                    "bars": [],
                    "last_price": None,
                    "has_bar": False,
                }
            else:
                symbols_view[sym] = {
                    "bars": bars_by_symbol[sym][: cur + 1],
                    "last_price": last_price_by_sym[sym],
                    "has_bar": has_bar_at_t[sym],
                }

        # Position state visible to strategy: only symbols currently held.
        position_state: Dict[str, dict] = {}
        for sym, book in books.items():
            if book.qty <= 0:
                continue
            px = last_price_by_sym.get(sym) or book.avg_entry_price
            pos = dict(book.extras)
            pos["qty"] = book.qty
            pos["market_value"] = book.qty * px
            pos["avg_entry_price"] = book.avg_entry_price
            position_state[sym] = pos

        # Safety backstop: per-symbol pre-decide check. If ANY symbol's
        # position trips a backstop we synthesize a close for THAT symbol
        # only and skip decide() for it — other symbols still get a vote.
        # We collect synthesized closes here, run decide_xsec next, then
        # let synthesized closes override the strategy's action for the
        # same symbol (safety rail wins).
        synthesized_closes: Dict[str, "object"] = {}
        for sym, book in books.items():
            if book.qty <= 0:
                continue
            pos_view = position_state.get(sym)
            cur_px = last_price_by_sym.get(sym)
            if pos_view is None or cur_px is None:
                continue
            bs = safety_backstop.check(pos_view, cur_px, params)
            if bs.fire:
                class _BSAction:
                    pass
                a = _BSAction()
                a.action = "close"
                a.symbol = sym
                a.notional_usd = 0.0
                a.qty = None
                a.reason = f"safety_backstop:{bs.trigger}: {bs.reason}"
                synthesized_closes[sym] = a

        market_state = {
            "timeframe": timeframe,
            "clock_t": t,
            "symbols": symbols_view,
            "regime": regime_state,
            "strategy_state": persistent_state,
        }
        try:
            raw_actions = decide_xsec_fn(market_state, position_state, params)
        except Exception as e:  # noqa: BLE001
            # A strategy crash shouldn't kill the whole run; record as a
            # tick-level skip with reason, treat as hold for all symbols.
            for sym in symbols:
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} t={t}: decide_xsec raised {type(e).__name__}: {e}"
                )
            raw_actions = {}
        persistent_state = market_state.get("strategy_state") or {}
        if not isinstance(persistent_state, dict):
            persistent_state = {}
        if raw_actions is None:
            raw_actions = {}
        if not isinstance(raw_actions, dict):
            raise TypeError(
                f"decide_xsec must return a dict[symbol -> Action], got "
                f"{type(raw_actions).__name__}")

        # Overlay synthesized safety closes (safety wins over strategy).
        actions: Dict[str, "object"] = {}
        for sym, a in raw_actions.items():
            if sym not in symbols:
                # Unknown symbol => log + drop.
                per_sym_result.setdefault(sym, XSecPerSymbol(symbol=sym))
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} t={t}: action for unknown symbol")
                continue
            actions[sym] = a
        actions.update(synthesized_closes)

        # Basket-level cap clamp (computes scaled notionals for buys).
        clamped_buys, was_clamped = _clamp_basket(actions, books, last_price_by_sym)
        if was_clamped:
            n_basket_clamps += 1

        day = t[:10] if len(t) >= 10 else ""

        # Process actions in deterministic order: closes first (free up
        # cap headroom), then buys in sorted-symbol order (deterministic
        # under same inputs even if strategy returns dict in arbitrary
        # order). Within the daily-trade-cap budget.
        ordered_syms = sorted(actions.keys())
        # Closes first.
        for sym in ordered_syms:
            a = actions[sym]
            act = getattr(a, "action", "hold")
            if act != "close":
                continue
            book = books[sym]
            n_today = trades_by_day.get(day, 0)
            # Risk check: only enforces daily cap for close.
            rc = _bt_check_trade("close", 0.0, book.qty * (last_price_by_sym.get(sym) or 0.0),
                                 n_today, max_trades_per_day=max_trades_per_day)
            if not rc.ok:
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} close: {rc.reason}")
                continue
            if book.qty <= 0:
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} close: no position")
                continue
            cur_px = last_price_by_sym.get(sym)
            if cur_px is None or cur_px <= 0:
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} close: no visible price")
                continue
            cm = cm_map[sym]
            sell_px = cm.sell_fill_price(cur_px)
            proceeds = book.qty * sell_px
            fee = cm.fee_on(proceeds)
            proceeds_after_fee = proceeds - fee
            pnl_usd = proceeds_after_fee - book.cost_basis_usd
            pnl_pct = (pnl_usd / book.cost_basis_usd) if book.cost_basis_usd > 0 else 0.0
            spread_cost = (book.qty * cur_px) * (cm.spread_bps / 1e4)
            total_costs_usd += fee + spread_cost
            per_sym_result[sym].total_costs_usd += fee + spread_cost
            if book.avg_entry_price > 0 and book.trade_low_seen is not None and book.trade_high_seen is not None:
                max_dd_from_entry = (book.trade_low_seen - book.avg_entry_price) / book.avg_entry_price
                max_ru_from_entry = (book.trade_high_seen - book.avg_entry_price) / book.avg_entry_price
            else:
                max_dd_from_entry = 0.0
                max_ru_from_entry = 0.0
            holding_ticks = (tick_idx - book.entry_bar_idx) if book.entry_bar_idx is not None else 0
            per_sym_result[sym].closed_trades.append({
                "exit_tick": tick_idx,
                "exit_time": t,
                "exit_price": sell_px,
                "entry_price": book.avg_entry_price,
                "qty": book.qty,
                "pnl_usd": pnl_usd,
                "pnl_pct": pnl_pct,
                "max_drawdown_pct": max_dd_from_entry,
                "max_runup_pct": max_ru_from_entry,
                "holding_bars": holding_ticks,
            })
            per_sym_result[sym].realized_pnl_usd += pnl_usd
            cash += proceeds_after_fee
            book.qty = 0.0
            book.cost_basis_usd = 0.0
            book.avg_entry_price = 0.0
            book.entry_bar_idx = None
            book.trade_low_seen = None
            book.trade_high_seen = None
            book.extras = {}
            per_sym_result[sym].n_closes += 1
            n_closes_total += 1
            trades_by_day[day] = n_today + 1

        # Buys (and sells treated as buys-into-existing — though typically
        # cross-sec strategies just use buy/close).
        for sym in ordered_syms:
            a = actions[sym]
            act = getattr(a, "action", "hold")
            if act not in ("buy", "sell"):
                continue
            # Take the clamped notional if present; else the original.
            requested_notional = float(getattr(a, "notional_usd", 0.0) or 0.0)
            notional = clamped_buys.get(sym, requested_notional)
            if notional <= 0:
                # Basket clamp zeroed this leg (or strategy asked for 0).
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} {act}: basket clamp -> 0 "
                    f"(requested {requested_notional:.2f})")
                continue
            book = books[sym]
            n_today = trades_by_day.get(day, 0)
            cur_px = last_price_by_sym.get(sym)
            if cur_px is None or cur_px <= 0 or not has_bar_at_t[sym]:
                # Can't fill: no bar at this exact tick. Strategy can try
                # again next tick when this symbol prints.
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} {act}: no bar at clock_t (stale price)")
                continue
            cur_pos_usd = book.qty * cur_px if book.qty > 0 else 0.0
            rc = _bt_check_trade(act, notional, cur_pos_usd, n_today,
                                 max_trades_per_day=max_trades_per_day)
            if not rc.ok:
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                per_sym_result[sym].skipped_reasons.append(
                    f"tick {tick_idx} {act} notional={notional:.2f}: {rc.reason}")
                continue
            cm = cm_map[sym]
            fill_px = cm.buy_fill_price(cur_px)
            buy_qty = notional / fill_px if fill_px > 0 else 0.0
            if buy_qty <= 0:
                n_skipped_total += 1
                per_sym_result[sym].n_skipped_risk += 1
                continue
            was_flat = book.qty == 0.0
            new_qty = book.qty + buy_qty
            book.cost_basis_usd = book.cost_basis_usd + notional
            book.avg_entry_price = book.cost_basis_usd / new_qty if new_qty > 0 else 0.0
            book.qty = new_qty
            cash -= notional
            fee = cm.fee_on(notional)
            cash -= fee
            spread_cost = notional * (cm.spread_bps / 1e4)
            total_costs_usd += fee + spread_cost
            per_sym_result[sym].total_costs_usd += fee + spread_cost
            per_sym_result[sym].n_buys += 1
            n_buys_total += 1
            trades_by_day[day] = n_today + 1
            if was_flat:
                book.entry_bar_idx = tick_idx
                bar = bars_by_symbol[sym][cursor_by_sym[sym]]
                close = float(bar["c"])
                try:
                    bar_low = float(bar.get("l", close))
                    bar_high = float(bar.get("h", close))
                except (TypeError, ValueError):
                    bar_low = close
                    bar_high = close
                book.trade_low_seen = bar_low
                book.trade_high_seen = bar_high

        # Mark-to-market equity at end of tick.
        equity = cash
        for sym, book in books.items():
            if book.qty > 0:
                px = last_price_by_sym.get(sym) or book.avg_entry_price
                equity += book.qty * px
        equity_curve.append(equity)

    # Final position bookkeeping.
    # open_instrument_dds collects DD-from-entry for positions STILL OPEN at
    # window-end. A trade that is never closed (e.g. a -50% crash a strategy
    # rode into the close) would otherwise be invisible to the closed-trades
    # DD scan — exactly the wipeout GATE #5(b) exists to catch. We use the
    # tracked intra-trade low (trade_low_seen), falling back to the last
    # mark if the low wasn't recorded.
    open_instrument_dds: List[float] = []
    for sym, book in books.items():
        per_sym_result[sym].final_qty = book.qty
        if book.qty > 0:
            px = last_price_by_sym.get(sym) or book.avg_entry_price
            per_sym_result[sym].final_market_value = book.qty * px
            if book.avg_entry_price > 0:
                low = book.trade_low_seen
                if low is None:
                    low = px
                # include the current mark too: an open loser's worst point
                # is min(intra-trade low, current price).
                low = min(low, px)
                open_instrument_dds.append(
                    (low - book.avg_entry_price) / book.avg_entry_price)
        else:
            per_sym_result[sym].final_market_value = 0.0

    # Metrics.
    final_equity = equity_curve[-1] if equity_curve else starting_cash
    total_return_usd = final_equity - starting_cash
    total_return_pct = (total_return_usd / starting_cash) if starting_cash > 0 else 0.0

    returns: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            returns.append((equity_curve[i] - prev) / prev)
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var)
        if std > 0:
            # FINDING 2 fix (2026-05-31 audit): annualize 1Day with 252 for
            # equities, 365 for crypto. A basket is crypto if its symbols use
            # the `/USD` form. Mixed baskets (shouldn't happen) treated as
            # crypto only if ALL legs are crypto; any equity leg => 252.
            xsec_is_crypto = bool(symbols) and all("/" in s for s in symbols)
            bpy = bars_per_year(timeframe, xsec_is_crypto)
            sharpe = (mean / std) * math.sqrt(bpy)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0
    peak = -float("inf")
    max_dd = 0.0
    for e in equity_curve:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak
            if dd < max_dd:
                max_dd = dd

    result.n_ticks = len(clock)
    result.n_buys = n_buys_total
    result.n_closes = n_closes_total
    result.n_trades = n_buys_total + n_closes_total
    result.n_skipped_risk = n_skipped_total
    result.n_basket_clamps = n_basket_clamps
    result.total_return_usd = total_return_usd
    result.total_return_pct = total_return_pct
    result.sharpe = sharpe
    result.max_drawdown_pct = max_dd

    # Deployed-capital (instrument-level) drawdown: the worst single-leg
    # DD-from-entry across every trade, closed or still-open. This is the
    # un-diluted number GATE Bar A #5(b) binds on (RULING 2, 2026-05-31).
    # max_dd_from_entry is stored <= 0 (a drawdown); worst = most negative.
    instrument_dds: List[float] = list(open_instrument_dds)
    for ps in per_sym_result.values():
        for tr in ps.closed_trades:
            instrument_dds.append(float(tr.get("max_drawdown_pct", 0.0)))
    result.worst_instrument_dd_pct = min(instrument_dds) if instrument_dds else 0.0

    result.final_equity = final_equity
    result.total_costs_usd = total_costs_usd
    result.equity_curve = equity_curve
    result.per_symbol = per_sym_result
    return result


# ---------------------------------------------------------------------------
# Convenience: load bars for a basket
# ---------------------------------------------------------------------------

def fetch_basket_bars(symbols: List[str], timeframe: str, days: int,
                      end_dt: Optional[datetime] = None) -> Dict[str, List[dict]]:
    """Use bars_cache.get_bars for each symbol. N cache hits, not N fetches."""
    out: Dict[str, List[dict]] = {}
    for sym in symbols:
        out[sym] = bars_cache.get_bars(sym, timeframe, days=days, end_dt=end_dt)
    return out


def backtest_xsec_by_name(strategy_name: str, basket: List[str],
                          days: int = 30,
                          end_dt: Optional[datetime] = None,
                          cost_model: Optional[CostModel] = None,
                          *, candidate: bool = False
                          ) -> XSecBacktestResult:
    decide_fn, params = load_xsec_strategy(strategy_name, candidate=candidate)
    timeframe = str(params.get("timeframe", "1Hour"))
    bars_by_symbol = fetch_basket_bars(basket, timeframe, days=days, end_dt=end_dt)
    return backtest_xsec(strategy_name, bars_by_symbol, params,
                         decide_xsec_fn=decide_fn,
                         default_cost_model=cost_model)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_basket_arg(basket: Optional[str], basket_file: Optional[str]) -> List[str]:
    if basket and basket_file:
        raise SystemExit("Use --basket OR --basket-file, not both")
    if basket:
        return [s.strip() for s in basket.split(",") if s.strip()]
    if basket_file:
        text = Path(basket_file).read_text()
        return [line.strip() for line in text.splitlines()
                if line.strip() and not line.strip().startswith("#")]
    return []


def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-sectional backtest.")
    ap.add_argument("--strategy", required=True, help="strategy dir name (must export decide_xsec)")
    ap.add_argument("--basket", help="comma-separated symbols e.g. 'XLK,XLF,XLE'")
    ap.add_argument("--basket-file", help="file with one symbol per line (# for comments)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--no-costs", action="store_true")
    ap.add_argument("--candidate", action="store_true",
                    help="load from strategies_candidates/ instead of strategies/")
    ap.add_argument("--json", help="write result JSON to this path")
    args = ap.parse_args()

    basket = _parse_basket_arg(args.basket, args.basket_file)
    if not basket:
        # Try params.json["basket"].
        try:
            _, params = load_xsec_strategy(args.strategy, candidate=args.candidate)
            basket = list(params.get("basket") or [])
        except Exception:
            basket = []
    if not basket:
        ap.error("No basket provided: pass --basket / --basket-file, or set params.basket")

    cm = CostModel(spread_bps=0.0, fee_bps=0.0) if args.no_costs else None
    r = backtest_xsec_by_name(args.strategy, basket, days=args.days, cost_model=cm,
                              candidate=args.candidate)
    print(f"[{args.strategy}] basket={r.symbols} ticks={r.n_ticks} "
          f"trades={r.n_trades} (buys={r.n_buys} closes={r.n_closes}) "
          f"skipped={r.n_skipped_risk} clamps={r.n_basket_clamps} "
          f"ret={r.total_return_pct * 100:+.2f}% sharpe={r.sharpe:.2f} "
          f"maxDD={r.max_drawdown_pct * 100:.2f}%")
    for sym, ps in r.per_symbol.items():
        print(f"  {sym}: bars={ps.n_bars} buys={ps.n_buys} closes={ps.n_closes} "
              f"skipped={ps.n_skipped_risk} realized_pnl=${ps.realized_pnl_usd:+.2f} "
              f"final_qty={ps.final_qty:.6f}")
    if args.json:
        # equity_curve can be large; truncate to last 200 for the JSON dump.
        d = r.to_dict()
        if len(d.get("equity_curve") or []) > 200:
            d["equity_curve"] = d["equity_curve"][-200:]
        Path(args.json).write_text(json.dumps(d, indent=2, default=str))
        print(f"Wrote JSON -> {args.json}")


if __name__ == "__main__":
    main()
