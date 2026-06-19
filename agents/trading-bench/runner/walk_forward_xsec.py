"""Walk-forward harness for cross-sectional (basket) strategies.

Sister to `runner/walk_forward.py`. Mirrors its API and reuses
NAMED_WINDOWS + passes_fitness_gate so cross-sec candidates are scored
on the same multi-regime panel as single-symbol strategies.

Per-window result: backtest_xsec across one named window's bar slice
per symbol in the basket. Aggregate: median across windows + per-regime
medians (bull / chop / bear).

Plus: scores the 2026-05-30 amended Bar A bullet #1 — per-window pass
requires EITHER (a) positive return OR (b) return ≥ basket-equal-weight
buy-and-hold AND ≥25% bars-in-position, with (b) capped at 1 window per
strategy.

CLI:
    python3 -m runner.walk_forward_xsec --strategy xsec_momentum_<hash> \
        --basket XLB,XLC,XLE,XLF,XLI,XLK,XLP,XLRE,XLU,XLV,XLY

Used as the wave-3 driver for the cross-sec archetypes (#1 momentum,
#3 low-vol, #8 sector rotation).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import bars_cache  # noqa: E402
from .backtest import CostModel  # noqa: E402
from .backtest_xsec import (  # noqa: E402
    XSecBacktestResult,
    backtest_xsec,
    build_clock,
    load_xsec_strategy,
)
from .walk_forward import (  # noqa: E402
    NAMED_WINDOWS,
    WalkForwardAggregate,
    passes_fitness_gate,
)
from . import spy_relative  # noqa: E402


# ---------------------------------------------------------------------------
# SPY-relative reporting (ADDITIVE — not a gate). See runner/spy_relative.py.
# Mirrors runner/walk_forward.py. The xsec strategy's per-tick portfolio
# equity returns are compared to SPY buy-and-hold per-period returns over the
# SAME window, aligned by calendar date (YYYY-MM-DD). No lookahead: SPY bars
# come from the same (end_dt, days, timeframe) window the basket is scored on.
# ---------------------------------------------------------------------------

def _spy_returns_by_date_xsec(end_dt: datetime, days: int, timeframe: str) -> dict:
    bars = bars_cache.get_bars("SPY", timeframe, days=days, end_dt=end_dt)
    if not bars or len(bars) < 2:
        return {}
    out: dict = {}
    for i in range(1, len(bars)):
        prev = float(bars[i - 1]["c"])
        if prev > 0:
            out[str(bars[i]["t"])[:10]] = (float(bars[i]["c"]) - prev) / prev
    return out


def _xsec_strategy_returns_by_date(bt: XSecBacktestResult, clock: list) -> dict:
    """Per-tick portfolio EQUITY returns keyed by tick calendar date.

    equity_curve = [starting_cash, eq_after_tick0, ...]; return over clock[i]
    (i>=1) is (eq[i+1]-eq[i])/eq[i], dated at clock[i][:10]. If multiple ticks
    fall on the same date (intraday), the last one for that date wins — fine
    for a 1Day-dominant panel; this is reporting only.
    """
    eq = bt.equity_curve
    out: dict = {}
    for i in range(1, len(clock)):
        if i + 1 < len(eq) and eq[i] > 0:
            out[str(clock[i])[:10]] = (eq[i + 1] - eq[i]) / eq[i]
    return out


def _compute_spy_relative_xsec(bt: XSecBacktestResult, bars_by_sym: dict,
                               end_dt: datetime, days: int,
                               timeframe: str) -> dict:
    """Best-effort SPY-relative metrics for one xsec window. REPORTING ONLY.
    Never raises into the walk-forward run; degrades to excess=0/IR=None.
    """
    empty = {"spy_excess_ann_return": 0.0, "spy_information_ratio": None,
             "spy_rel_n_periods": 0}
    try:
        clock = build_clock(bars_by_sym)
        strat_by_date = _xsec_strategy_returns_by_date(bt, clock)
        spy_by_date = _spy_returns_by_date_xsec(end_dt, days, timeframe)
        if not strat_by_date or not spy_by_date:
            return empty
        s_aligned, b_aligned, _dates = spy_relative.align_returns_by_date(
            strat_by_date, spy_by_date)
        m = spy_relative.spy_relative_metrics(
            s_aligned, b_aligned, timeframe=timeframe)
        return {
            "spy_excess_ann_return": m["excess_return_annualized"],
            "spy_information_ratio": m["information_ratio"],
            "spy_rel_n_periods": m["n_periods"],
        }
    except (ValueError, Exception):
        return empty


# ---------------------------------------------------------------------------
# Per-window result for cross-sec backtests
# ---------------------------------------------------------------------------

class ZeroTradesError(RuntimeError):
    """Raised when a walk-forward produces 0 trades across every data window
    (warmup-starvation reproducibility trap). See walk_forward_xsec's
    allow_zero_trades arg."""


@dataclass
class XSecWindowResult:
    """One backtest_xsec result tagged with regime metadata + bh-basket bench."""
    label: str
    regime: str
    end_date: str
    days: int
    backtest: XSecBacktestResult
    bh_basket_return_pct: float
    beats_bh_basket: bool
    bars_in_position_pct: float    # 0-100; fraction of ticks holding ANY basket leg
    bar_a_pass: bool = False        # True iff this window cleared amended bullet #1
    bar_a_via_b: bool = False       # True iff it cleared via the (b) alt-pass
    # SPY-relative reporting (additive; not a gate). IR may be None.
    spy_excess_ann_return: float = 0.0
    spy_information_ratio: Optional[float] = None
    spy_rel_n_periods: int = 0

    def to_row(self) -> dict:
        bt = self.backtest
        # win_pct: aggregate across all closed trades in basket
        all_closed = [tr for ps in bt.per_symbol.values() for tr in ps.closed_trades]
        win_pct = (sum(1 for tr in all_closed if tr["pnl_usd"] > 0) / len(all_closed)
                   * 100) if all_closed else 0.0
        return {
            "label": self.label,
            "regime": self.regime,
            "end_date": self.end_date,
            "days": self.days,
            "n_ticks": bt.n_ticks,
            "n_trades": bt.n_trades,
            "n_basket_clamps": bt.n_basket_clamps,
            "return_pct": bt.total_return_pct * 100,
            "sharpe": bt.sharpe,
            "max_dd_pct": bt.max_drawdown_pct * 100,
            "win_pct": win_pct,
            "bh_basket_pct": self.bh_basket_return_pct * 100,
            "beats_bh_basket": self.beats_bh_basket,
            "bars_in_position_pct": self.bars_in_position_pct,
            "bar_a_pass": self.bar_a_pass,
            "bar_a_via_b": self.bar_a_via_b,
            "spy_excess_ann_pct": self.spy_excess_ann_return * 100,
            "spy_information_ratio": self.spy_information_ratio,
        }


@dataclass
class XSecWalkForwardAggregate:
    """Aggregate stats across N named windows for a cross-sec strategy."""
    strategy: str
    basket: List[str] = field(default_factory=list)
    n_windows: int = 0
    n_windows_with_data: int = 0
    # Population stats across all windows
    median_return_pct: float = 0.0
    mean_return_pct: float = 0.0
    stdev_return_pct: float = 0.0
    pct_positive: float = 0.0
    pct_beat_bh_basket: float = 0.0
    median_sharpe: float = 0.0
    worst_return_pct: float = 0.0
    best_return_pct: float = 0.0
    worst_window_label: str = ""
    best_window_label: str = ""
    # DEPLOYED-CAPITAL (instrument-level) max drawdown across all windows.
    # This is the worst single-leg DD-from-entry, NOT the diluted portfolio
    # NAV drawdown. GATE Bar A #5(b) binds on THIS number (RULING 2,
    # 2026-05-31). Stored <= 0 (a drawdown).
    worst_instrument_dd_pct: float = 0.0
    total_trades: int = 0
    # Regime-bucket medians (per Bar A bullet #1 (a))
    median_return_bull: Optional[float] = None
    median_return_chop: Optional[float] = None
    median_return_bear: Optional[float] = None
    # Amended Bar A bullet #1 verdict
    bar_a_b_used_count: int = 0
    bar_a_bullet1_pass: bool = False
    bar_a_bullet1_reason: str = ""
    # SPY-relative reporting (additive; not a gate).
    median_spy_excess_ann_return: float = 0.0
    median_spy_information_ratio: Optional[float] = None
    windows: List[XSecWindowResult] = field(default_factory=list)

    def as_compat_agg(self) -> WalkForwardAggregate:
        """Return a WalkForwardAggregate-shaped view so the existing
        passes_fitness_gate() can consume xsec results unchanged.

        We reuse pct_beat_bh_spy slot for pct_beat_bh_basket: same semantic
        (does the strategy beat the natural same-window benchmark?), just
        a different benchmark.
        """
        return WalkForwardAggregate(
            strategy=self.strategy,
            n_windows=self.n_windows,
            n_windows_with_data=self.n_windows_with_data,
            median_return_pct=self.median_return_pct,
            mean_return_pct=self.mean_return_pct,
            stdev_return_pct=self.stdev_return_pct,
            pct_positive=self.pct_positive,
            pct_beat_bh_spy=self.pct_beat_bh_basket,
            median_sharpe=self.median_sharpe,
            worst_return_pct=self.worst_return_pct,
            best_return_pct=self.best_return_pct,
            worst_window_label=self.worst_window_label,
            best_window_label=self.best_window_label,
            total_trades=self.total_trades,
        )


# ---------------------------------------------------------------------------
# BH-basket benchmark (equal-weight buy-and-hold across the basket)
# ---------------------------------------------------------------------------

_BH_BASKET_CACHE: dict = {}


def _bh_basket_return(basket: List[str], end_dt: datetime, days: int,
                      timeframe: str,
                      *, notional_usd: float = 1000.0,
                      starting_cash: float = 1000.0,
                      cost_model: Optional[CostModel] = None) -> float:
    """Equal-weight buy-and-hold of `basket` over [end_dt-days, end_dt].

    Scaled to bench equity, matching the strategy's `total_return_pct`
    denominator: a $100 notional is deployed across the basket, equal
    per leg; return is expressed as fraction of $1000 starting equity.

    Symbols with no bars in the window are dropped from the equal-weight
    bucket. If ALL symbols are missing, returns 0.
    """
    key = (tuple(sorted(basket)), end_dt.strftime("%Y-%m-%d"), days, timeframe,
           notional_usd, starting_cash)
    if key in _BH_BASKET_CACHE:
        return _BH_BASKET_CACHE[key]
    cm = cost_model if cost_model is not None else CostModel.alpaca_stocks()
    per_leg_notional = notional_usd / max(1, len(basket))
    leg_returns: List[float] = []
    for sym in basket:
        bars = bars_cache.get_bars(sym, timeframe, days=days, end_dt=end_dt)
        if not bars or len(bars) < 2:
            continue
        buy_px = cm.buy_fill_price(float(bars[0]["c"]))
        sell_px = cm.sell_fill_price(float(bars[-1]["c"]))
        if buy_px <= 0:
            continue
        leg_returns.append((sell_px - buy_px) / buy_px)
    if not leg_returns:
        _BH_BASKET_CACHE[key] = 0.0
        return 0.0
    avg_price_ret = sum(leg_returns) / len(leg_returns)
    # Scale to bench equity: ($100 notional / $1000 equity) = 0.1x.
    ret = avg_price_ret * (notional_usd / starting_cash)
    _BH_BASKET_CACHE[key] = ret
    return ret


# ---------------------------------------------------------------------------
# Position-occupancy tracker (wraps decide_xsec)
# ---------------------------------------------------------------------------

def _wrap_count_position_ticks(decide_fn: Callable, counter: List[int]) -> Callable:
    """Return a wrapped decide_xsec that increments counter[0] on each tick
    where position_state was non-empty BEFORE the strategy ran (= we were
    holding at least one basket leg)."""
    def wrapped(market_state, position_state, params):
        if position_state:
            counter[0] += 1
        return decide_fn(market_state, position_state, params)
    return wrapped


# ---------------------------------------------------------------------------
# Walk-forward execution
# ---------------------------------------------------------------------------

def walk_forward_xsec(
    strategy_name: str,
    basket: List[str],
    *,
    params: Optional[dict] = None,
    decide_xsec_fn: Optional[Callable] = None,
    windows: Optional[List[Tuple[str, datetime, int, str]]] = None,
    warmup_days: int = 0,
    cost_model: Optional[CostModel] = None,
    min_bars_per_symbol: int = 10,
    allow_zero_trades: bool = False,
) -> XSecWalkForwardAggregate:
    """Backtest a cross-sec strategy across multiple regime windows.

    Args:
        strategy_name: label / loader hint.
        basket: list of symbols, e.g. the 11 SPDR sector ETFs.
        params: override params (default: load from strategies/<name>).
        decide_xsec_fn: override decide fn (for tests).
        windows: list of (label, end_dt, days, regime). Default: NAMED_WINDOWS.
        warmup_days: extra calendar days fetched per window before each
            window's end_dt → start_dt. Slow-trigger strategies (e.g. 252d
            momentum lookback) need this so their signal can compute inside
            the labeled regime window. Trade activity is dominated by the
            labeled window because the strategy is flat during warmup.
        cost_model: applied to every symbol in the basket. Default:
            CostModel.alpaca_stocks().
        min_bars_per_symbol: drop a symbol from a window if it has fewer
            than this many bars in the slice (sparse Alpaca history for
            newer ETFs).
        allow_zero_trades: by default this harness RAISES if the strategy
            takes zero trades across EVERY window that had data — that is
            the signature of the warmup-starvation reproducibility trap
            (a slow-trigger lookback, e.g. 252d momentum, can't compute
            its signal because each window was sliced without enough
            priming history, so the strategy silently does nothing and
            the harness would otherwise report a do-nothing strategy as
            0 trades / +0.00% everywhere — exactly the silent path that
            produced the 2026-05-31 xsec_momentum promotion-record
            correction). Pass True only for a strategy you have
            independently confirmed is legitimately flat across the whole
            panel (rare). A real selective strategy trades in at least
            some windows; this guard fires only on the all-zero case.

    Returns: XSecWalkForwardAggregate.

    Raises:
        ZeroTradesError: when total_trades == 0 across all data windows
            and allow_zero_trades is False. Re-run with a larger
            --warmup-days (≥400 for 252d-lookback strategies) before
            trusting any number from this harness.
    """
    if params is None or decide_xsec_fn is None:
        loaded_decide, loaded_params = load_xsec_strategy(strategy_name)
        if params is None:
            params = loaded_params
        if decide_xsec_fn is None:
            decide_xsec_fn = loaded_decide
    timeframe = str(params.get("timeframe", "1Day"))
    if cost_model is None:
        cost_model = CostModel.alpaca_stocks()
    if windows is None:
        windows = NAMED_WINDOWS
    notional = float(params.get("notional_usd", 1000.0))

    agg = XSecWalkForwardAggregate(
        strategy=strategy_name, basket=list(basket), n_windows=len(windows))
    rets: List[float] = []
    sharpes: List[float] = []
    beats: List[bool] = []
    per_regime: Dict[str, List[float]] = {"bull": [], "chop": [], "bear": []}

    for label, end_dt, days, regime in windows:
        fetch_days = days + max(0, warmup_days)
        bars_by_sym: Dict[str, List[dict]] = {}
        for sym in basket:
            bars = bars_cache.get_bars(sym, timeframe, days=fetch_days, end_dt=end_dt)
            if bars and len(bars) >= min_bars_per_symbol:
                bars_by_sym[sym] = bars
        if len(bars_by_sym) < 2:
            # Need at least 2 symbols for cross-sectional ranking to mean anything.
            continue

        # Wrap decide to track position-occupancy ticks.
        occupancy_counter = [0]
        wrapped_decide = _wrap_count_position_ticks(decide_xsec_fn, occupancy_counter)

        bt = backtest_xsec(
            strategy_name, bars_by_sym, params,
            decide_xsec_fn=wrapped_decide,
            default_cost_model=cost_model)

        bars_in_position_pct = ((occupancy_counter[0] / bt.n_ticks) * 100.0
                                if bt.n_ticks > 0 else 0.0)

        bh = _bh_basket_return(
            list(bars_by_sym.keys()), end_dt, days, timeframe,
            notional_usd=notional, starting_cash=bt.starting_equity,
            cost_model=cost_model)
        beats_bh = bt.total_return_pct > bh

        spy_rel = _compute_spy_relative_xsec(bt, bars_by_sym, end_dt, days, timeframe)
        wr = XSecWindowResult(
            label=label, regime=regime,
            end_date=end_dt.strftime("%Y-%m-%d"), days=days,
            backtest=bt, bh_basket_return_pct=bh, beats_bh_basket=beats_bh,
            bars_in_position_pct=bars_in_position_pct,
            spy_excess_ann_return=spy_rel["spy_excess_ann_return"],
            spy_information_ratio=spy_rel["spy_information_ratio"],
            spy_rel_n_periods=spy_rel["spy_rel_n_periods"],
        )
        agg.windows.append(wr)
        rets.append(bt.total_return_pct * 100)
        sharpes.append(bt.sharpe)
        beats.append(beats_bh)
        agg.total_trades += bt.n_trades
        if regime in per_regime:
            per_regime[regime].append(bt.total_return_pct * 100)

    agg.n_windows_with_data = len(agg.windows)

    # --- Warmup-starvation guard (Finding 3a, 2026-05-31) -----------------
    # If the strategy took zero trades across EVERY window that had data,
    # the numbers below are a do-nothing artifact, almost always caused by
    # insufficient warmup priming a slow lookback. Fail loud instead of
    # silently reporting +0.00% — that silent path produced the
    # xsec_momentum_xa promotion-record correction. A legitimately-flat
    # strategy is rare; require an explicit opt-in to report it.
    if (agg.n_windows_with_data > 0 and agg.total_trades == 0
            and not allow_zero_trades):
        raise ZeroTradesError(
            f"{strategy_name}: 0 trades across all {agg.n_windows_with_data} "
            f"data windows (warmup_days={warmup_days}). This is the "
            f"warmup-starvation trap: a slow-trigger lookback could not "
            f"compute its signal, so the strategy did nothing and every "
            f"window reports +0.00%. Re-run with a larger --warmup-days "
            f"(>=400 for a 252d-lookback strategy). If this strategy is "
            f"genuinely flat across the whole panel, pass "
            f"allow_zero_trades=True to override.")

    if rets:
        agg.median_return_pct = statistics.median(rets)
        agg.mean_return_pct = statistics.mean(rets)
        agg.stdev_return_pct = statistics.stdev(rets) if len(rets) >= 2 else 0.0
        agg.pct_positive = sum(1 for r in rets if r > 0) / len(rets)
        agg.pct_beat_bh_basket = sum(1 for b in beats if b) / len(beats)
        agg.median_sharpe = statistics.median(sharpes)
        wi = min(range(len(rets)), key=lambda i: rets[i])
        bi = max(range(len(rets)), key=lambda i: rets[i])
        agg.worst_return_pct = rets[wi]
        agg.best_return_pct = rets[bi]
        agg.worst_window_label = agg.windows[wi].label
        agg.best_window_label = agg.windows[bi].label
        # Deployed-capital (instrument-level) DD: worst single-leg DD-from-
        # entry across ALL windows (closed + open-at-window-end trades).
        # This is the BINDING number for GATE Bar A #5(b) (RULING 2). It is
        # NOT diluted by the idle-cash sleeve the way bt.max_drawdown_pct is.
        inst_dds = [w.backtest.worst_instrument_dd_pct for w in agg.windows]
        agg.worst_instrument_dd_pct = min(inst_dds) * 100.0 if inst_dds else 0.0
        # SPY-relative aggregates (additive reporting only).
        excesses = [w.spy_excess_ann_return for w in agg.windows]
        if excesses:
            agg.median_spy_excess_ann_return = statistics.median(excesses)
        irs = [w.spy_information_ratio for w in agg.windows
               if w.spy_information_ratio is not None]
        agg.median_spy_information_ratio = (
            statistics.median(irs) if irs else None)
    for tag in ("bull", "chop", "bear"):
        if per_regime[tag]:
            setattr(agg, f"median_return_{tag}", statistics.median(per_regime[tag]))

    # Score amended Bar A bullet #1 (per-window (a) or (b), cap=1).
    _score_bar_a_bullet1(agg)
    return agg


# ---------------------------------------------------------------------------
# Bar A bullet #1 amended (2026-05-30) scorer
# ---------------------------------------------------------------------------

BAR_A_B_ALT_CAP = 1                  # ≤1 window may use the (b) alt-pass
BAR_A_B_MIN_BARS_IN_POSITION = 25.0  # %; must have deployed capital

def _score_bar_a_bullet1(agg: XSecWalkForwardAggregate) -> None:
    """Tag each window's bar_a_pass + bar_a_via_b, then set aggregate
    bar_a_bullet1_pass.

    Rule (amended 2026-05-30):
        Each regime window passes if EITHER:
          (a) post-cost return > 0, OR
          (b) post-cost return >= bh_basket_return AND bars_in_position
              >= 25%.
        The (b) escape hatch is capped at ≤1 window per strategy. If a
        strategy needs (b) on >1 windows it's chronically underperforming
        and the BH-crutch isn't admissible.
    """
    b_used = 0
    failed: List[str] = []
    for w in agg.windows:
        bt = w.backtest
        ret = bt.total_return_pct
        if ret > 0:
            w.bar_a_pass = True
            w.bar_a_via_b = False
            continue
        # Try (b)
        b_eligible = (ret >= w.bh_basket_return_pct - 1e-12
                      and w.bars_in_position_pct >= BAR_A_B_MIN_BARS_IN_POSITION)
        if b_eligible and b_used < BAR_A_B_ALT_CAP:
            w.bar_a_pass = True
            w.bar_a_via_b = True
            b_used += 1
        else:
            w.bar_a_pass = False
            w.bar_a_via_b = False
            why = []
            if not (ret >= w.bh_basket_return_pct - 1e-12):
                why.append(f"ret {ret*100:+.2f}% < bh-basket {w.bh_basket_return_pct*100:+.2f}%")
            if w.bars_in_position_pct < BAR_A_B_MIN_BARS_IN_POSITION:
                why.append(f"in-position {w.bars_in_position_pct:.0f}% < 25%")
            if b_eligible and b_used >= BAR_A_B_ALT_CAP:
                why.append(f"(b) already used (cap={BAR_A_B_ALT_CAP})")
            failed.append(f"{w.label}: " + ", ".join(why) if why
                          else f"{w.label}: negative return")
    agg.bar_a_b_used_count = b_used
    if not agg.windows:
        agg.bar_a_bullet1_pass = False
        agg.bar_a_bullet1_reason = "no windows with data"
        return
    all_pass = all(w.bar_a_pass for w in agg.windows)
    agg.bar_a_bullet1_pass = all_pass
    if all_pass:
        agg.bar_a_bullet1_reason = (
            f"all {len(agg.windows)} windows pass (b-alt used {b_used}/{BAR_A_B_ALT_CAP})")
    else:
        agg.bar_a_bullet1_reason = "; ".join(failed[:4])


# ---------------------------------------------------------------------------
# GATE Bar A bullet #5(b) — DEPLOYED-CAPITAL drawdown gate (RULING 2, 2026-05-31)
# ---------------------------------------------------------------------------

# Binding threshold for #5(b). A candidate FAILS if its worst single-leg
# instrument drawdown-from-entry exceeds this magnitude. 30% matches the
# candidate-stage MaxDD ceiling already in Bar A (bullet #5-old: MaxDD <= 30%
# post-cost); the point of RULING 2 is that this ceiling must bind on the
# DEPLOYED-CAPITAL (instrument-level) number, not the idle-cash-diluted
# portfolio NAV. Real-money Bar E stays at the stricter 20%.
BAR_A_5B_MAX_INSTRUMENT_DD_PCT = 30.0  # %, magnitude


def passes_bar_a_5b(agg: XSecWalkForwardAggregate) -> Tuple[bool, str]:
    """GATE Bar A bullet #5(b): deployed-capital / instrument-level max drawdown.

    RULING 2 (2026-05-31, main): #5(b) must bind on the DEPLOYED-CAPITAL
    drawdown — the worst single-instrument DD-from-entry — NOT the diluted
    90%-cash portfolio NAV drawdown. A -50% instrument crash that reports as
    -5% against portfolio NAV means the clause cannot see the wipeout it
    exists to catch. We bind on `agg.worst_instrument_dd_pct`, which is the
    worst single-leg DD across every window's trades (closed + still-open at
    window-end), computed in `backtest_xsec` from each trade's tracked
    intra-trade low vs its entry price.

    Returns (passes, reason). `worst_instrument_dd_pct` is stored <= 0
    (a drawdown); we compare its magnitude to the threshold.
    """
    dd = agg.worst_instrument_dd_pct  # <= 0, in percent
    mag = abs(dd)
    if mag > BAR_A_5B_MAX_INSTRUMENT_DD_PCT:
        return (False,
                f"#5(b) FAIL: worst instrument DD {dd:.2f}% "
                f"(magnitude {mag:.2f}%) exceeds {BAR_A_5B_MAX_INSTRUMENT_DD_PCT:.0f}% "
                f"deployed-capital ceiling — a single leg drew down past the "
                f"limit on deployed notional, regardless of how the idle-cash "
                f"sleeve dilutes the portfolio NAV figure.")
    return (True,
            f"#5(b) PASS: worst instrument DD {dd:.2f}% "
            f"within {BAR_A_5B_MAX_INSTRUMENT_DD_PCT:.0f}% deployed-capital ceiling.")


def passes_fitness_gate_xsec(agg: XSecWalkForwardAggregate) -> Tuple[bool, str]:
    """Adapt the existing single-symbol fitness gate to xsec aggregates.

    Delegates to `runner.walk_forward.passes_fitness_gate` on the
    compat WalkForwardAggregate view (pct_beat_bh_spy slot reused for
    pct_beat_bh_basket). Same thresholds; same semantics.
    """
    return passes_fitness_gate(agg.as_compat_agg())


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_xsec_md(agg: XSecWalkForwardAggregate) -> str:
    lines = [
        f"### {agg.strategy} — basket={','.join(agg.basket)}",
        "",
        "| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 | SPY-rel Excess Ann % | Info Ratio |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for w in agg.windows:
        r = w.to_row()
        tag = "✅" if r["bar_a_pass"] else "❌"
        if r["bar_a_via_b"]:
            tag += "(b)"
        ir_str = (f"{r['spy_information_ratio']:.2f}"
                  if r["spy_information_ratio"] is not None else "n/a")
        lines.append(
            f"| {r['label']} | {r['regime']} | {r['n_ticks']} | {r['n_trades']} | "
            f"{r['n_basket_clamps']} | {r['return_pct']:+.2f} | {r['sharpe']:.2f} | "
            f"{r['max_dd_pct']:.2f} | {r['win_pct']:.0f} | {r['bh_basket_pct']:+.2f} | "
            f"{'✅' if r['beats_bh_basket'] else '❌'} | "
            f"{r['bars_in_position_pct']:.0f} | {tag} | "
            f"{r['spy_excess_ann_pct']:+.2f} | {ir_str} |"
        )
    passed, reason = passes_fitness_gate_xsec(agg)
    gate = "🟢 PASS" if passed else "🔴 FAIL"
    bar_a_gate = "🟢 PASS" if agg.bar_a_bullet1_pass else "🔴 FAIL"
    lines += [
        "",
        f"**Aggregate:** median ret {agg.median_return_pct:+.2f}% · "
        f"{agg.pct_positive * 100:.0f}% windows positive · "
        f"{agg.pct_beat_bh_basket * 100:.0f}% beat BH-basket · "
        f"median Sharpe {agg.median_sharpe:.2f} · "
        f"worst {agg.worst_return_pct:+.2f}% ({agg.worst_window_label}) · "
        f"best {agg.best_return_pct:+.2f}% ({agg.best_window_label}) · "
        f"trades {agg.total_trades}",
        f"**Per-regime median:** bull={_fmt_opt(agg.median_return_bull)} · "
        f"chop={_fmt_opt(agg.median_return_chop)} · "
        f"bear={_fmt_opt(agg.median_return_bear)}",
        f"**SPY-relative (reporting only, not a gate):** median excess ann "
        f"{agg.median_spy_excess_ann_return * 100:+.2f}% · median info ratio "
        f"{_fmt_opt_ir(agg.median_spy_information_ratio)}",
        f"**Fitness gate (shared):** {gate} — {reason}",
        f"**Bar A bullet #1 (amended 2026-05-30, cap=1):** {bar_a_gate} — "
        f"{agg.bar_a_bullet1_reason}",
        "",
    ]
    return "\n".join(lines)


def _fmt_opt(x: Optional[float]) -> str:
    return f"{x:+.2f}%" if x is not None else "—"


def _fmt_opt_ir(x: Optional[float]) -> str:
    return f"{x:.2f}" if x is not None else "n/a"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_basket(arg: Optional[str]) -> List[str]:
    if not arg:
        return []
    return [s.strip() for s in arg.split(",") if s.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward for cross-sec basket strategies.")
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--basket", help="comma-separated symbols (overrides params.basket)")
    ap.add_argument("--warmup-days", type=int, default=0)
    ap.add_argument("--allow-zero-trades", action="store_true",
                    help="Override the warmup-starvation guard (only for "
                         "strategies confirmed legitimately flat panel-wide).")
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args()

    decide_fn, params = load_xsec_strategy(args.strategy)
    basket = _parse_basket(args.basket) or list(params.get("basket") or [])
    if not basket:
        ap.error("No basket provided: pass --basket or set params.basket")

    print(f"[{args.strategy}] basket={basket} warmup={args.warmup_days}d "
          f"windows={len(NAMED_WINDOWS)}", file=sys.stderr)
    try:
        agg = walk_forward_xsec(
            args.strategy, basket, params=params, decide_xsec_fn=decide_fn,
            warmup_days=args.warmup_days,
            allow_zero_trades=args.allow_zero_trades)
    except ZeroTradesError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)
    passed, reason = passes_fitness_gate_xsec(agg)
    print(f"  -> windows={agg.n_windows_with_data}/{agg.n_windows} "
          f"medRet={agg.median_return_pct:+.2f}% pos={agg.pct_positive*100:.0f}% "
          f"beatBH={agg.pct_beat_bh_basket*100:.0f}% medSharpe={agg.median_sharpe:.2f} "
          f"spyExcessAnn={agg.median_spy_excess_ann_return*100:+.2f}% "
          f"medIR={_fmt_opt_ir(agg.median_spy_information_ratio)} "
          f"BarA#1={'PASS' if agg.bar_a_bullet1_pass else 'FAIL'} "
          f"FIT={'PASS' if passed else 'FAIL'}", file=sys.stderr)
    if args.md:
        Path(args.md).write_text(format_xsec_md(agg))
        print(f"wrote {args.md}", file=sys.stderr)
    if args.json:
        payload = {
            "strategy": agg.strategy,
            "basket": agg.basket,
            "n_windows_with_data": agg.n_windows_with_data,
            "median_return_pct": agg.median_return_pct,
            "pct_positive": agg.pct_positive,
            "pct_beat_bh_basket": agg.pct_beat_bh_basket,
            "median_sharpe": agg.median_sharpe,
            "median_spy_excess_ann_return": agg.median_spy_excess_ann_return,
            "median_spy_information_ratio": agg.median_spy_information_ratio,
            "median_return_bull": agg.median_return_bull,
            "median_return_chop": agg.median_return_chop,
            "median_return_bear": agg.median_return_bear,
            "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
            "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
            "total_trades": agg.total_trades,
            "fitness_gate": list(passes_fitness_gate_xsec(agg)),
            "bar_a_bullet1_pass": agg.bar_a_bullet1_pass,
            "bar_a_bullet1_reason": agg.bar_a_bullet1_reason,
            "bar_a_b_used_count": agg.bar_a_b_used_count,
            "windows": [w.to_row() for w in agg.windows],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"wrote {args.json}", file=sys.stderr)
    print(format_xsec_md(agg))


if __name__ == "__main__":
    main()
