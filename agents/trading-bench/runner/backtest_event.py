"""Event-driven, SHARED-CASH portfolio backtest harness.

Third sibling to `runner/backtest.py` (single-symbol time-series) and
`runner/backtest_xsec.py` (cross-sectional, rank-and-allocate). Where those
two replay *continuously-trading* strategies, THIS module replays
**event-driven** strategies: strategies that act only when a discrete event
fires for a symbol (e.g. an earnings 8-K Item 2.02 filing), enter a position,
hold it for a fixed horizon, then exit -- with every position drawing from and
returning to ONE shared cash account.

## Why a NEW harness (the PEAD report's blocker)

`reports/BACKTEST_PEAD_20260530T171825Z.md` documents the gap precisely:

  - The single-symbol harness gives EACH symbol its own isolated $1000 cash.
    You can sum dollar P&L across symbols, but you CANNOT compute a
    portfolio-level Sharpe, drawdown, or true win-rate -- there is no shared
    equity curve.
  - PEAD wants to deploy $X on every positive-surprise event *regardless of
    which symbol fires*, carry up to N concurrent positions, with cash flowing
    through a single account. None of the existing harnesses model that.

This module fills that gap. It mirrors `backtest_xsec`'s discipline EXACTLY:
  - single shared clock (`build_clock`, reused),
  - no-lookahead bar slicing (only bars with t <= clock_t are visible),
  - the same CostModel (round-trip ~4 bps equities via spread_bps=2 one-way),
  - the same $1000 shared notional cap (risk.MAX_POSITION / starting_cash),
  - fills at the current bar close.

It does NOT modify any existing runner/*.py. New code, new file.

## The decide_event interface (strategy author contract)

An event-driven strategy module exports:

    decide_event(ctx) -> EventDecision | None

where `ctx` is an `EventContext` dataclass (read-only view, no lookahead):

    ctx.symbol        : str            # the symbol whose event is firing
    ctx.clock_t       : str            # ISO timestamp of the current tick
    ctx.event_date    : str            # YYYY-MM-DD of the event that triggered
    ctx.bars          : list[dict]     # oldest-first OHLCV, ONLY bars t<=clock_t
                                       #   (last bar = entry-candidate; bars[-2]
                                       #    is the reaction/surprise bar)
    ctx.reaction_bar  : dict           # the surprise bar (on/after event_date),
                                       #   fully in the PAST when we evaluate entry
    ctx.last_price    : float          # close of bars[-1] = the fill price if we enter
    ctx.params        : dict           # strategy params.json
    ctx.state         : dict           # mutable per-strategy persistent scratch

It returns an `EventDecision`:

    EventDecision(enter=bool, notional_usd=float, reason=str)

The harness owns ALL of: shared cash, concurrency cap, exit timing (hold H
bars / stop / take), cost model, no-lookahead. The strategy ONLY decides
whether an event is tradeable and how big. This is deliberate: the hard,
error-prone bookkeeping (shared cash, no negative cash, cap enforcement,
no-lookahead) lives in the tested harness, NOT in LLM-authored strategy code.

### Exit policy (harness-owned, parameterized)

    holding_bars : int   # exit after this many bars held (ticks where the
                         #   symbol printed a bar since entry)
    stop_pct     : float # exit if return-from-entry <= stop_pct (e.g. -0.05)
    take_pct     : float # exit if return-from-entry >= take_pct (e.g. +0.10)

First trigger wins; ties resolve stop > take > time.

### Entry discipline (no-lookahead, "enter AFTER the reaction bar")

Replicates the PEAD report's rule. An event has `event_date = D`. The bar ON
(or first trading bar after) D is the **reaction bar** -- it contains the
earnings surprise, which is NOT tradeable (already in that close). We enter at
the close of the NEXT bar after the reaction bar. So:

    reaction_bar = first bar with date >= D       (the surprise bar)
    entry_bar    = the bar immediately AFTER reaction_bar  (fill at its close)

At the entry tick, decide_event sees bars[-1] == entry_bar and
bars[-2] == reaction_bar. The surprise is measured from the reaction bar
(fully past relative to the fill) => ZERO lookahead.

(`require_gap_after_event` controls this; default True. Set False ONLY for
tests that want same-bar fills -- never for real PEAD lanes.)
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import bars_cache  # noqa: E402
from .backtest import CostModel, bars_per_year  # noqa: E402
from . import risk as risk_mod  # noqa: E402
from .backtest_xsec import build_clock, _index_by_t  # noqa: E402
from .fp_sharpe import sharpe_from_returns  # noqa: E402


# ---------------------------------------------------------------------------
# Strategy-author contract objects
# ---------------------------------------------------------------------------

@dataclass
class EventContext:
    """Read-only, no-lookahead view handed to decide_event(). See module doc."""
    symbol: str
    clock_t: str
    event_date: str
    bars: List[dict]
    reaction_bar: dict
    last_price: float
    params: dict
    state: dict


@dataclass
class EventDecision:
    """What decide_event() returns. enter=False (or None) => skip the event."""
    enter: bool
    notional_usd: float = 0.0
    reason: str = ""


# ---------------------------------------------------------------------------
# Internal position book (shared-cash). Strategies never see this.
# ---------------------------------------------------------------------------

@dataclass
class _EventPos:
    symbol: str
    qty: float
    cost_basis_usd: float          # cash spent on the buy (notional, pre-fee)
    avg_entry_price: float         # spread-adjusted fill price
    entry_tick: int
    entry_time: str
    event_date: str
    bars_held: int = 0
    trade_low_seen: Optional[float] = None
    trade_high_seen: Optional[float] = None


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------

@dataclass
class EventTrade:
    symbol: str
    event_date: str
    entry_tick: int
    entry_time: str
    entry_price: float
    exit_tick: int
    exit_time: str
    exit_price: float
    qty: float
    notional_usd: float
    pnl_usd: float
    pnl_pct: float
    bars_held: int
    max_drawdown_pct: float        # worst intra-trade DD from entry (<= 0)
    max_runup_pct: float
    exit_reason: str


@dataclass
class EventBacktestResult:
    strategy: str
    symbols: List[str] = field(default_factory=list)
    timeframe: str = "1Day"
    n_ticks: int = 0
    n_events: int = 0              # total distinct events across the universe
    n_events_eligible: int = 0     # events whose entry bar maps onto the clock
    n_events_in_window: int = 0    # subset of eligible whose REACTION bar is not
                                   #   clamped to bar[0] (i.e. the event date
                                   #   actually falls within the bar history --
                                   #   the genuinely tradeable events). Events
                                   #   predating the bar window collapse onto the
                                   #   first bars and are filtered by the strategy
                                   #   (insufficient history); this counts the real ones.
    n_entries: int = 0
    n_exits: int = 0
    n_skipped_cash: int = 0        # entries declined: not enough shared cash
    n_skipped_cap: int = 0         # entries declined: concurrency cap hit
    n_skipped_strategy: int = 0    # decide_event said no / enter=False
    starting_cash: float = 0.0
    final_equity: float = 0.0
    total_return_usd: float = 0.0
    total_return_pct: float = 0.0
    fp_continuous_sharpe: float = 0.0
    n_return_points: int = 0
    max_drawdown_pct: float = 0.0          # PORTFOLIO-NAV drawdown
    worst_instrument_dd_pct: float = 0.0   # deployed-capital: worst single leg DD
    ann_return_on_deployed: float = 0.0    # annualized return on deployed notional
    win_rate: float = 0.0
    n_trades: int = 0
    total_costs_usd: float = 0.0
    max_concurrent_positions: int = 0
    deployed_notional_total: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    trades: List[EventTrade] = field(default_factory=list)
    bh_spy_return_pct: Optional[float] = None
    beats_bh_spy: Optional[bool] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Event-date -> reaction-bar / entry-bar resolution (no lookahead)
# ---------------------------------------------------------------------------

def _bar_date(bar: dict) -> str:
    return str(bar.get("t", ""))[:10]


def resolve_event_entries(
    bars: List[dict],
    event_dates: List[str],
    *,
    require_gap_after_event: bool = True,
) -> List[Tuple[str, int, int]]:
    """Map each event_date to (event_date, reaction_bar_idx, entry_bar_idx).

    - reaction_bar_idx = index of the FIRST bar whose date >= event_date (the
      surprise bar; weekend/holiday events roll to the next trading bar).
    - entry_bar_idx    = reaction_bar_idx + 1 if require_gap_after_event else
      reaction_bar_idx (same-bar fill -- TESTS ONLY).

    Events with no bar at/after them, or whose entry bar would fall off the end
    of the series, are dropped. Returns one tuple per *resolvable* event,
    sorted by entry_bar_idx. This is the load-bearing no-lookahead anchor: the
    entry bar is strictly AFTER the reaction (surprise) bar.
    """
    if not bars:
        return []
    bar_dates = [_bar_date(b) for b in bars]
    out: List[Tuple[str, int, int]] = []
    for ed in sorted(set(str(e)[:10] for e in event_dates)):
        reaction_idx = None
        for i, bd in enumerate(bar_dates):
            if bd >= ed:
                reaction_idx = i
                break
        if reaction_idx is None:
            continue
        entry_idx = reaction_idx + 1 if require_gap_after_event else reaction_idx
        if entry_idx >= len(bars):
            continue
        out.append((ed, reaction_idx, entry_idx))
    out.sort(key=lambda x: x[2])
    return out


# ---------------------------------------------------------------------------
# Strategy loader
# ---------------------------------------------------------------------------

STRATEGIES_ROOT = WORKSPACE / "strategies"
CANDIDATES_ROOT = WORKSPACE / "strategies_candidates"


def load_event_strategy(name: str, *, from_candidates: bool = False) -> Tuple[Callable, dict]:
    """Load an event-driven strategy exporting `decide_event`.

    Looks under `strategies/<name>/` by default, or
    `strategies_candidates/<name>/` if from_candidates=True.
    """
    root = CANDIDATES_ROOT if from_candidates else STRATEGIES_ROOT
    pkg = "strategies_candidates" if from_candidates else "strategies"
    strat_dir = root / name
    params_path = strat_dir / "params.json"
    if not strat_dir.is_dir():
        raise FileNotFoundError(f"No strategy dir: {strat_dir}")
    if not params_path.exists():
        raise FileNotFoundError(f"No params.json: {params_path}")
    module = importlib.import_module(f"{pkg}.{name}.strategy")
    if not hasattr(module, "decide_event"):
        raise AttributeError(
            f"{pkg}.{name}.strategy must export decide_event(ctx) for the "
            f"event-driven harness")
    params = json.loads(params_path.read_text())
    return module.decide_event, params


# ---------------------------------------------------------------------------
# Same-path buy-and-hold SPY benchmark
# ---------------------------------------------------------------------------

def _bh_spy_return_on_clock(clock: List[str],
                            spy_closes: List[float],
                            spy_times: List[str]) -> Optional[float]:
    """Total buy-and-hold SPY return over the SAME clock span.

    We pick SPY's close on/just-before the first clock tick and the close
    on/just-before the last clock tick (no-lookahead boundaries) and return
    the simple return. Returns None if SPY data doesn't cover the span.
    """
    if not clock or not spy_closes or not spy_times:
        return None
    first_d = clock[0][:10]
    last_d = clock[-1][:10]
    # close on/just-before first_d
    start_px = None
    for px, st in zip(spy_closes, spy_times):
        if st[:10] <= first_d:
            start_px = px
        else:
            break
    end_px = None
    for px, st in zip(spy_closes, spy_times):
        if st[:10] <= last_d:
            end_px = px
        else:
            break
    if start_px is None or end_px is None or start_px <= 0:
        return None
    return (end_px - start_px) / start_px


# ---------------------------------------------------------------------------
# Core event-driven, shared-cash backtest
# ---------------------------------------------------------------------------

def backtest_event(
    strategy_name: str,
    bars_by_symbol: Dict[str, List[dict]],
    events_by_symbol: Dict[str, List[str]],
    params: dict,
    *,
    starting_cash: float = 1000.0,
    decide_event_fn: Optional[Callable] = None,
    cost_model_by_symbol: Optional[Dict[str, CostModel]] = None,
    default_cost_model: Optional[CostModel] = None,
    max_concurrent: int = 10,
    require_gap_after_event: bool = True,
    spy_closes: Optional[List[float]] = None,
    spy_times: Optional[List[str]] = None,
) -> EventBacktestResult:
    """Replay an event-driven strategy across a universe with ONE shared cash book.

    See module docstring for the full contract. Returns an EventBacktestResult
    with a portfolio equity curve, fp_continuous Sharpe, portfolio +
    worst-instrument DD, annualized return on deployed notional, win rate,
    trade count, and beats-BH-SPY-same-path.

    SHARED-CASH INVARIANTS (load-bearing, asserted by tests):
      - cash never goes negative: an entry is declined if its notional+fee
        exceeds available cash.
      - concurrency cap: at most `max_concurrent` open positions at once.
      - cash conservation: at any tick, cash + sum(position mark-to-cost) is
        only changed by realized P&L and costs -- there is one pool, not N.
    """
    timeframe = str(params.get("timeframe", "1Day"))
    symbols = sorted(bars_by_symbol.keys())
    holding_bars = int(params.get("holding_bars", 42))
    stop_pct = float(params.get("stop_pct", -0.05))
    take_pct = float(params.get("take_pct", 0.10))
    default_notional = float(params.get("notional_usd", 1000.0))
    # OPT-IN, ADDITIVE exit-fill mode (default "close" = legacy behaviour).
    #   "close"     -> exit fills at the triggering bar's CLOSE (spread-adjusted).
    #   "next_open" -> exit fills at the triggering bar's OPEN (spread-adjusted).
    # The "next_open" mode exists for OVERNIGHT strategies: with holding_bars=1
    # the hold-horizon exit fires on the bar AFTER entry, so filling at that
    # bar's open == selling at the next session's market-open (MOO). Combined
    # with a close-of-entry-bar buy (MOC) this isolates the pure overnight
    # (close->open) return WITHOUT washing in the next-session intraday move.
    # Default "close" preserves the legacy close->close path bit-for-bit.
    exit_fill = str(params.get("exit_fill", "close")).lower()
    if exit_fill not in ("close", "next_open"):
        exit_fill = "close"
    is_crypto = bool(symbols) and all("/" in s for s in symbols)

    result = EventBacktestResult(
        strategy=strategy_name,
        symbols=list(symbols),
        timeframe=timeframe,
        starting_cash=starting_cash,
    )

    if not symbols:
        result.equity_curve = [starting_cash]
        result.final_equity = starting_cash
        return result

    cm_map: Dict[str, CostModel] = {}
    for sym in symbols:
        if cost_model_by_symbol and sym in cost_model_by_symbol:
            cm_map[sym] = cost_model_by_symbol[sym]
        elif default_cost_model is not None:
            cm_map[sym] = default_cost_model
        else:
            cm_map[sym] = CostModel.for_symbol(sym)

    if decide_event_fn is None:
        decide_event_fn, _ = load_event_strategy(strategy_name)

    clock = build_clock(bars_by_symbol)
    if not clock:
        result.equity_curve = [starting_cash]
        result.final_equity = starting_cash
        return result
    clock_pos = {t: i for i, t in enumerate(clock)}

    idx_by_sym: Dict[str, Dict[str, int]] = {
        sym: _index_by_t(bars_by_symbol[sym]) for sym in symbols
    }
    cursor_by_sym: Dict[str, int] = {sym: -1 for sym in symbols}

    # Resolve every event to its entry tick on the shared clock.
    n_events_total = 0
    n_events_eligible = 0
    n_events_in_window = 0
    entries_at_tick: Dict[int, List[Tuple[str, str, int, int]]] = {}
    for sym in symbols:
        evs = events_by_symbol.get(sym, []) or []
        n_events_total += len(set(str(e)[:10] for e in evs))
        resolved = resolve_event_entries(
            bars_by_symbol[sym], evs, require_gap_after_event=require_gap_after_event)
        for ed, reaction_idx, entry_idx in resolved:
            # An event predating the bar window clamps reaction_idx to 0 (the
            # first bar with date >= ed is bar[0]); such events are NOT
            # genuinely in-window and get filtered downstream by the strategy
            # (insufficient history). reaction_idx > 0 means a real bar sits
            # before the reaction bar => a genuinely tradeable in-window event.
            if reaction_idx > 0:
                n_events_in_window += 1
            entry_bar = bars_by_symbol[sym][entry_idx]
            entry_t = str(entry_bar.get("t"))
            tick = clock_pos.get(entry_t)
            if tick is None:
                continue
            n_events_eligible += 1
            entries_at_tick.setdefault(tick, []).append(
                (sym, ed, reaction_idx, entry_idx))

    # Portfolio state -- ONE shared cash account.
    cash = float(starting_cash)
    positions: Dict[str, _EventPos] = {}
    persistent_state: dict = {}
    equity_curve: List[float] = []
    trades: List[EventTrade] = []
    total_costs_usd = 0.0
    deployed_notional_total = 0.0
    max_concurrent_seen = 0

    n_entries = 0
    n_exits = 0
    n_skipped_cash = 0
    n_skipped_cap = 0
    n_skipped_strategy = 0

    last_price_by_sym: Dict[str, Optional[float]] = {sym: None for sym in symbols}

    def _record_exit(pos: _EventPos, exit_tick: int, exit_time: str,
                     cur_px: float, sell_px: float, reason: str) -> float:
        """Close `pos`; sell_px is spread-adjusted, cur_px is the raw mark.
        Returns cash proceeds after fee. Appends an EventTrade."""
        nonlocal total_costs_usd, n_exits
        cm = cm_map[pos.symbol]
        proceeds = pos.qty * sell_px
        fee = cm.fee_on(proceeds)
        proceeds_after_fee = proceeds - fee
        pnl_usd = proceeds_after_fee - pos.cost_basis_usd
        pnl_pct = (pnl_usd / pos.cost_basis_usd) if pos.cost_basis_usd > 0 else 0.0
        spread_cost = (pos.qty * cur_px) * (cm.spread_bps / 1e4)
        total_costs_usd += fee + spread_cost
        if pos.avg_entry_price > 0 and pos.trade_low_seen is not None and pos.trade_high_seen is not None:
            max_dd = (pos.trade_low_seen - pos.avg_entry_price) / pos.avg_entry_price
            max_ru = (pos.trade_high_seen - pos.avg_entry_price) / pos.avg_entry_price
        else:
            max_dd = 0.0
            max_ru = 0.0
        trades.append(EventTrade(
            symbol=pos.symbol, event_date=pos.event_date,
            entry_tick=pos.entry_tick, entry_time=pos.entry_time,
            entry_price=pos.avg_entry_price, exit_tick=exit_tick,
            exit_time=exit_time, exit_price=sell_px, qty=pos.qty,
            notional_usd=pos.cost_basis_usd, pnl_usd=pnl_usd, pnl_pct=pnl_pct,
            bars_held=pos.bars_held, max_drawdown_pct=max_dd,
            max_runup_pct=max_ru, exit_reason=reason))
        n_exits += 1
        return proceeds_after_fee

    for tick_idx, t in enumerate(clock):
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

        # Update excursion + hold-clock for open positions printing this tick.
        for sym, pos in positions.items():
            if not has_bar_at_t.get(sym):
                continue
            bar = bars_by_symbol[sym][cursor_by_sym[sym]]
            close = float(bar["c"])
            try:
                bar_low = float(bar.get("l", close))
                bar_high = float(bar.get("h", close))
            except (TypeError, ValueError):
                bar_low = close
                bar_high = close
            if pos.trade_low_seen is None or bar_low < pos.trade_low_seen:
                pos.trade_low_seen = bar_low
            if pos.trade_high_seen is None or bar_high > pos.trade_high_seen:
                pos.trade_high_seen = bar_high
            pos.bars_held += 1

        # ---- 1) EXITS first (free cash + concurrency before entries) ----
        for sym in sorted(list(positions.keys())):
            pos = positions[sym]
            if not has_bar_at_t.get(sym):
                continue
            cur_px = last_price_by_sym[sym]
            if cur_px is None or cur_px <= 0:
                continue
            ret = ((cur_px - pos.avg_entry_price) / pos.avg_entry_price) if pos.avg_entry_price > 0 else 0.0
            reason = None
            if ret <= stop_pct:
                reason = f"stop {ret*100:.2f}% <= {stop_pct*100:.2f}%"
            elif ret >= take_pct:
                reason = f"take {ret*100:.2f}% >= {take_pct*100:.2f}%"
            elif pos.bars_held >= holding_bars:
                reason = f"held {pos.bars_held} bars >= {holding_bars}"
            if reason is None:
                continue
            cm = cm_map[sym]
            # exit_fill mode: "close" (legacy) sells at this bar's close;
            # "next_open" sells at this bar's OPEN (MOO for overnight). The
            # spread is applied to whichever raw mark we fill against.
            if exit_fill == "next_open":
                bar = bars_by_symbol[sym][cursor_by_sym[sym]]
                try:
                    raw_mark = float(bar.get("o", cur_px))
                except (TypeError, ValueError):
                    raw_mark = cur_px
                if raw_mark <= 0:
                    raw_mark = cur_px
            else:
                raw_mark = cur_px
            sell_px = cm.sell_fill_price(raw_mark)
            cash += _record_exit(pos, tick_idx, t, raw_mark, sell_px, reason)
            del positions[sym]

        # ---- 2) ENTRIES from events firing at this tick ----
        for (sym, event_date, reaction_idx, entry_idx) in entries_at_tick.get(tick_idx, []):
            if not has_bar_at_t.get(sym):
                # Entry bar didn't actually print at this tick (shouldn't
                # happen since entry_t was mapped to this tick, but guard).
                continue
            if sym in positions:
                n_skipped_strategy += 1
                continue
            cur = cursor_by_sym[sym]
            visible_bars = bars_by_symbol[sym][: cur + 1]
            reaction_bar = bars_by_symbol[sym][reaction_idx]
            cur_px = last_price_by_sym[sym]
            if cur_px is None or cur_px <= 0:
                n_skipped_strategy += 1
                continue

            ctx = EventContext(
                symbol=sym,
                clock_t=t,
                event_date=event_date,
                bars=visible_bars,
                reaction_bar=reaction_bar,
                last_price=cur_px,
                params=params,
                state=persistent_state,
            )
            try:
                decision = decide_event_fn(ctx)
            except Exception:
                # Strategy crash on one event => treat as no-entry, keep going.
                n_skipped_strategy += 1
                continue
            persistent_state = ctx.state if isinstance(ctx.state, dict) else persistent_state

            if decision is None or not getattr(decision, "enter", False):
                n_skipped_strategy += 1
                continue

            # Concurrency cap (shared-cash count cap).
            if len(positions) >= max_concurrent:
                n_skipped_cap += 1
                continue

            requested = float(getattr(decision, "notional_usd", 0.0) or 0.0)
            if requested <= 0:
                requested = default_notional
            # Per-trade notional cap (risk.MAX_NOTIONAL) AND shared-cash cap.
            requested = min(requested, risk_mod.MAX_NOTIONAL)
            cm = cm_map[sym]
            fee = cm.fee_on(requested)
            total_cost = requested + fee
            if total_cost > cash + 1e-9:
                # Not enough shared cash: decline (NO negative cash, ever).
                n_skipped_cash += 1
                continue

            fill_px = cm.buy_fill_price(cur_px)
            qty = requested / fill_px if fill_px > 0 else 0.0
            if qty <= 0:
                n_skipped_strategy += 1
                continue

            # Commit the buy against the ONE shared cash pool.
            cash -= requested
            cash -= fee
            spread_cost = requested * (cm.spread_bps / 1e4)
            total_costs_usd += fee + spread_cost
            deployed_notional_total += requested

            bar = bars_by_symbol[sym][cur]
            bclose = float(bar["c"])
            try:
                blow = float(bar.get("l", bclose))
                bhigh = float(bar.get("h", bclose))
            except (TypeError, ValueError):
                blow = bclose
                bhigh = bclose
            positions[sym] = _EventPos(
                symbol=sym, qty=qty, cost_basis_usd=requested,
                avg_entry_price=fill_px, entry_tick=tick_idx, entry_time=t,
                event_date=event_date, bars_held=0,
                trade_low_seen=blow, trade_high_seen=bhigh)
            n_entries += 1

        if len(positions) > max_concurrent_seen:
            max_concurrent_seen = len(positions)

        # Mark-to-market portfolio equity at end of tick.
        equity = cash
        for sym, pos in positions.items():
            px = last_price_by_sym.get(sym) or pos.avg_entry_price
            equity += pos.qty * px
        equity_curve.append(equity)

    # ---- Final: close out any still-open positions at the last visible mark
    #      (window-end liquidation), so the equity curve and trade list are
    #      complete. These are recorded as exit_reason='window_end'. ----
    last_tick = len(clock) - 1
    last_t = clock[-1] if clock else ""
    open_instrument_dds: List[float] = []
    for sym in sorted(list(positions.keys())):
        pos = positions[sym]
        cur_px = last_price_by_sym.get(sym)
        if cur_px is None or cur_px <= 0:
            cur_px = pos.avg_entry_price
        cm = cm_map[sym]
        sell_px = cm.sell_fill_price(cur_px)
        cash += _record_exit(pos, last_tick, last_t, cur_px, sell_px, "window_end")
        del positions[sym]

    # Metrics.
    final_equity = equity_curve[-1] if equity_curve else starting_cash
    # NB: equity_curve already marked open positions; the window-end close
    # realizes the same value (minus exit spread), so we report final_equity
    # from the marked curve for Sharpe/DD continuity and report realized cash
    # separately in total_costs. Use the marked curve as the canonical NAV.
    total_return_usd = final_equity - starting_cash
    total_return_pct = (total_return_usd / starting_cash) if starting_cash > 0 else 0.0

    # fp_continuous Sharpe on the portfolio per-tick return series.
    rets: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            rets.append((equity_curve[i] - prev) / prev)
    bpy = bars_per_year(timeframe, is_crypto)
    fp_sharpe = sharpe_from_returns(rets, bpy)

    # Portfolio-NAV drawdown.
    peak = -float("inf")
    max_dd = 0.0
    for e in equity_curve:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak
            if dd < max_dd:
                max_dd = dd

    # Worst-instrument (deployed-capital) drawdown: worst single-leg DD across
    # ALL trades (every position is closed by window-end, so trades is
    # complete). GATE #5(b) binds on THIS, undiluted by idle cash.
    instrument_dds = [float(tr.max_drawdown_pct) for tr in trades]
    worst_instrument_dd = min(instrument_dds) if instrument_dds else 0.0

    # Annualized return on deployed notional. We compute a per-trade simple
    # return weighted by capital-time (notional * bars_held), then annualize by
    # the average holding period. This answers "what does the capital earn
    # while it's actually deployed", which is GATE clause (f)'s intent for a
    # sparse event strategy (cash sits idle most of the time).
    n_trades = len(trades)
    wins = sum(1 for tr in trades if tr.pnl_usd > 0)
    win_rate = (wins / n_trades) if n_trades else 0.0
    if n_trades and deployed_notional_total > 0:
        total_pnl = sum(tr.pnl_usd for tr in trades)
        # capital-time weighted average holding period (in bars)
        cap_time = sum(tr.notional_usd * max(tr.bars_held, 1) for tr in trades)
        avg_hold_bars = cap_time / sum(tr.notional_usd for tr in trades)
        # mean per-trade return on its own notional
        mean_trade_ret = sum((tr.pnl_usd / tr.notional_usd) for tr in trades) / n_trades
        if avg_hold_bars > 0:
            periods_per_year = bpy / avg_hold_bars
            ann_on_deployed = (1.0 + mean_trade_ret) ** periods_per_year - 1.0
        else:
            ann_on_deployed = 0.0
    else:
        ann_on_deployed = 0.0

    # Same-path buy-and-hold SPY benchmark.
    bh_spy = None
    beats_bh = None
    if spy_closes and spy_times:
        bh_spy = _bh_spy_return_on_clock(clock, spy_closes, spy_times)
        if bh_spy is not None:
            beats_bh = total_return_pct > bh_spy

    result.n_ticks = len(clock)
    result.n_events = n_events_total
    result.n_events_eligible = n_events_eligible
    result.n_events_in_window = n_events_in_window
    result.n_entries = n_entries
    result.n_exits = n_exits
    result.n_skipped_cash = n_skipped_cash
    result.n_skipped_cap = n_skipped_cap
    result.n_skipped_strategy = n_skipped_strategy
    result.final_equity = final_equity
    result.total_return_usd = total_return_usd
    result.total_return_pct = total_return_pct
    result.fp_continuous_sharpe = fp_sharpe
    result.n_return_points = len(rets)
    result.max_drawdown_pct = max_dd
    result.worst_instrument_dd_pct = worst_instrument_dd
    result.ann_return_on_deployed = ann_on_deployed
    result.win_rate = win_rate
    result.n_trades = n_trades
    result.total_costs_usd = total_costs_usd
    result.max_concurrent_positions = max_concurrent_seen
    result.deployed_notional_total = deployed_notional_total
    result.equity_curve = equity_curve
    result.trades = trades
    result.bh_spy_return_pct = bh_spy
    result.beats_bh_spy = beats_bh
    return result


# ---------------------------------------------------------------------------
# Convenience loaders
# ---------------------------------------------------------------------------

def fetch_universe_bars(symbols: List[str], timeframe: str, days: int,
                        end_dt: Optional[datetime] = None) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for sym in symbols:
        out[sym] = bars_cache.get_bars(sym, timeframe, days=days, end_dt=end_dt)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Event-driven shared-cash backtest.")
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--candidates", action="store_true",
                    help="load strategy from strategies_candidates/")
    ap.add_argument("--days", type=int, default=720)
    ap.add_argument("--starting-cash", type=float, default=1000.0)
    ap.add_argument("--max-concurrent", type=int, default=10)
    ap.add_argument("--json", help="write result JSON here")
    args = ap.parse_args()

    decide_fn, params = load_event_strategy(args.strategy, from_candidates=args.candidates)
    universe = list(params.get("universe") or [])
    timeframe = str(params.get("timeframe", "1Day"))
    bars_by_symbol = fetch_universe_bars(universe, timeframe, days=args.days)
    events_by_symbol = {sym: params.get("events_by_symbol", {}).get(sym, [])
                        for sym in universe}
    r = backtest_event(args.strategy, bars_by_symbol, events_by_symbol, params,
                       starting_cash=args.starting_cash,
                       decide_event_fn=decide_fn,
                       max_concurrent=args.max_concurrent)
    print(f"[{args.strategy}] symbols={len(r.symbols)} ticks={r.n_ticks} "
          f"events={r.n_events} eligible={r.n_events_eligible} "
          f"entries={r.n_entries} exits={r.n_exits} trades={r.n_trades} "
          f"ret={r.total_return_pct*100:+.2f}% fp_sharpe={r.fp_continuous_sharpe:.2f} "
          f"maxDD={r.max_drawdown_pct*100:.2f}% worstInstrDD={r.worst_instrument_dd_pct*100:.2f}% "
          f"annDeployed={r.ann_return_on_deployed*100:+.2f}% win={r.win_rate*100:.0f}%")
    if args.json:
        d = r.to_dict()
        if len(d.get("equity_curve") or []) > 400:
            d["equity_curve"] = d["equity_curve"][-400:]
        Path(args.json).write_text(json.dumps(d, indent=2, default=str))
        print(f"Wrote JSON -> {args.json}")


if __name__ == "__main__":
    main()
