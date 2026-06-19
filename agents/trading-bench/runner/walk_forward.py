"""Walk-forward validation harness.

Backtest each strategy across multiple historical windows — both rolling
windows and hand-picked named regime windows (bull / chop / bear) — and
aggregate the results into per-strategy stats that survive regime cherry-pick.

Why this exists: a single 60-day backtest with Sharpe 16 means nothing if
the window happened to be long-friendly. This harness makes regime-luck
visible by re-running the same strategy across multiple, *deliberately
diverse*, historical windows and reporting:

  - median return across windows (not headline single-window return)
  - % of windows positive
  - % of windows that beat the same-window buy-and-hold-SPY benchmark
  - worst window (regime stress)
  - median Sharpe (NOT max — max is the regime-luck story)

It also exposes `passes_fitness_gate(...)`, the function that LLM-generated
strategies will have to clear before being scheduled to live paper.

Data caveat: Alpaca's free IEX feed gives reliable US-equity bars from
roughly 2022 onward. Earlier windows (Mar-2020 crash, 2015 chop, etc.)
return zero or near-zero bars and are excluded automatically. We use the
deepest bear we can actually fetch (2022 H1: SPY -17%) plus several chops.

CLI:
    python3 -m runner.walk_forward --strategy sma_crossover_qqq
    python3 -m runner.walk_forward --all
    python3 -m runner.walk_forward --all --md WALK_FORWARD_RESULTS.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import bars_cache  # noqa: E402
from .backtest import (  # noqa: E402
    BacktestResult,
    CostModel,
    backtest,
    load_strategy_module_and_params,
    STOCK_STRATEGIES,
)
from . import spy_relative  # noqa: E402


# ---------------------------------------------------------------------------
# SPY-relative reporting (ADDITIVE — not a gate). See runner/spy_relative.py.
# ---------------------------------------------------------------------------

def _spy_per_period_returns_by_date(end_dt: datetime, days: int, timeframe: str) -> dict:
    """SPY buy-and-hold close-to-close per-period returns over a window,
    keyed by the bar date that the return *ends on*.

    No lookahead: SPY bars are fetched for the SAME (end_dt, days, timeframe)
    window the strategy is scored on; each return uses only the prior close.
    """
    bars = bars_cache.get_bars("SPY", timeframe, days=days, end_dt=end_dt)
    if not bars or len(bars) < 2:
        return {}
    out: dict = {}
    for i in range(1, len(bars)):
        prev = float(bars[i - 1]["c"])
        if prev > 0:
            out[str(bars[i]["t"])] = (float(bars[i]["c"]) - prev) / prev
    return out


def _strategy_per_period_returns_by_date(bt: BacktestResult, bars: list) -> dict:
    """Strategy per-bar EQUITY returns keyed by the bar date the return ends on.

    equity_curve = [starting_cash, eq_after_bar0, eq_after_bar1, ...], so the
    return realized over bars[i] (i>=1) is (eq[i+1]-eq[i])/eq[i] and is dated
    at bars[i]['t']. Mirrors the equity-return convention backtest.py uses
    for Sharpe.
    """
    eq = bt.equity_curve
    out: dict = {}
    # eq has len(bars)+1 entries when bars is non-empty.
    for i in range(1, len(bars)):
        if i + 1 < len(eq) and eq[i] > 0:
            out[str(bars[i]["t"])] = (eq[i + 1] - eq[i]) / eq[i]
    return out


def _compute_spy_relative(bt: BacktestResult, bars: list, end_dt: datetime,
                          days: int, timeframe: str) -> dict:
    """Best-effort SPY-relative metrics for one window. REPORTING ONLY.

    Returns a dict with excess_return_annualized / information_ratio (IR may
    be None when undefined). On any data shortfall (no overlap, <2 aligned
    periods) returns excess=0.0 and IR=None rather than raising — this is a
    reporting add-on and must never break the walk-forward run or any gate.
    """
    empty = {"spy_excess_ann_return": 0.0, "spy_information_ratio": None,
             "spy_rel_n_periods": 0}
    try:
        strat_by_date = _strategy_per_period_returns_by_date(bt, bars)
        spy_by_date = _spy_per_period_returns_by_date(end_dt, days, timeframe)
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
# Named regime windows (end_date, days, label, description)
# ---------------------------------------------------------------------------
# Hand-picked from a probe of SPY drift over candidate windows. All are
# present in the Alpaca IEX feed (verified at module-build time). Older
# windows (Mar 2020, 2015, 2018-Q4) return zero bars on the free tier
# and are intentionally omitted — we don't fabricate.
#
# Format: (label, end_date_utc, days, regime_tag)
# regime_tag in {"bear", "chop", "bull"}

NAMED_WINDOWS: List[Tuple[str, datetime, int, str]] = [
    # The brutal 2022 H1 — SPY -17% over 60 trading days. Cleanest bear we can fetch.
    ("2022-H1 bear",        datetime(2022, 7, 1,  tzinfo=timezone.utc), 90, "bear"),
    # 2022 Q3 — choppy bear-rally then resumed decline. SPY -4 to -6%.
    ("2022-Q3 chop",        datetime(2022, 10, 1, tzinfo=timezone.utc), 90, "chop"),
    # 2023 H1 — banking-crisis dip + Mag-7 led recovery. SPY +7%.
    ("2023-H1 recovery",    datetime(2023, 4, 1,  tzinfo=timezone.utc), 90, "bull"),
    # 2023 Q3 — sideways with a -3.5% drift. Classic chop.
    ("2023-Q3 chop",        datetime(2023, 10, 1, tzinfo=timezone.utc), 90, "chop"),
    # 2024 Q2 — clean +5% bull leg.
    ("2024-Q2 bull",        datetime(2024, 7, 1,  tzinfo=timezone.utc), 90, "bull"),
    # 2025 Q1+April — tariff-news bear, SPY -8%. Second bear regime.
    ("2025-Q1 tariff bear", datetime(2025, 5, 1,  tzinfo=timezone.utc), 90, "bear"),
    # 2025 Q3 — +6.5% bull.
    ("2025-Q3 bull",        datetime(2025, 10, 1, tzinfo=timezone.utc), 90, "bull"),
    # Original 60-day window from BACKTEST_RESULTS.md, for direct comparison.
    ("2026-recent bull",    datetime(2026, 5, 25, tzinfo=timezone.utc), 60, "bull"),
]


# ---------------------------------------------------------------------------
# Buy-and-hold-SPY benchmark per window (cached so we only compute once)
# ---------------------------------------------------------------------------

_BH_SPY_CACHE: dict = {}


def _benchmark_spy_return(end_dt: datetime, days: int, timeframe: str,
                          *, notional_usd: float = 1000.0,
                          starting_cash: float = 1000.0) -> float:
    """SPY buy-and-hold return at the BENCH SCALE — i.e. as a fraction of
    `starting_cash`, given we only deploy `notional_usd` into the SPY trade.

    The bench backtest uses $1000 starting cash and $100 notional per trade,
    so the strategy's `total_return_pct` is dollars-pnl / $1000. To compare
    apples-to-apples with that, we must scale the raw price return by
    `notional / starting_cash` (typically /10).

    Without this scaling, a -17% SPY move would compare against a strategy's
    -1.7% equity drawdown and the strategy would "beat" SPY simply because
    it had 90% cash. That's not edge; it's lower exposure.

    Applies the stocks CostModel (buy at ask, sell at bid) to match how
    `buy_and_hold_spy.decide()` would actually fill.
    """
    key = (end_dt.strftime("%Y-%m-%d"), days, timeframe, notional_usd, starting_cash)
    if key in _BH_SPY_CACHE:
        return _BH_SPY_CACHE[key]
    bars = bars_cache.get_bars("SPY", timeframe, days=days, end_dt=end_dt)
    if not bars or len(bars) < 2:
        _BH_SPY_CACHE[key] = 0.0
        return 0.0
    cm = CostModel.alpaca_stocks()
    buy_px = cm.buy_fill_price(float(bars[0]["c"]))
    sell_px = cm.sell_fill_price(float(bars[-1]["c"]))
    price_ret = (sell_px - buy_px) / buy_px
    # Scale to bench equity: $100 notional / $1000 equity = 0.1x amplifier.
    ret = price_ret * (notional_usd / starting_cash)
    _BH_SPY_CACHE[key] = ret
    return ret


# ---------------------------------------------------------------------------
# Window splitting (rolling)
# ---------------------------------------------------------------------------

def split_rolling_windows(total_days: int, window_days: int, step_days: int,
                          end_dt: datetime) -> List[Tuple[str, datetime, int]]:
    """Return list of (label, end_date_utc, window_days) for rolling windows
    that step backward from end_dt by step_days, each window_days long, until
    we'd exceed total_days lookback.

    Pure date arithmetic — no data fetched. Deterministic for tests.
    """
    if window_days <= 0 or step_days <= 0 or total_days < window_days:
        return []
    windows = []
    offset = 0
    while offset + window_days <= total_days:
        win_end = end_dt - timedelta(days=offset)
        label = f"rolling@{win_end.strftime('%Y-%m-%d')}-{window_days}d"
        windows.append((label, win_end, window_days))
        offset += step_days
    return windows


# ---------------------------------------------------------------------------
# Walk-forward execution
# ---------------------------------------------------------------------------

@dataclass
class WindowResult:
    """One backtest result tagged with its window metadata."""
    label: str
    regime: str
    end_date: str
    days: int
    backtest: BacktestResult
    bh_spy_return_pct: float
    beats_bh_spy: bool
    # SPY-relative reporting (additive; not a gate). IR may be None.
    spy_excess_ann_return: float = 0.0
    spy_information_ratio: Optional[float] = None
    spy_rel_n_periods: int = 0

    def to_row(self) -> dict:
        return {
            "label": self.label,
            "regime": self.regime,
            "end_date": self.end_date,
            "days": self.days,
            "n_bars": self.backtest.n_bars,
            "n_trades": self.backtest.n_trades,
            "return_pct": self.backtest.total_return_pct * 100,
            "sharpe": self.backtest.sharpe,
            "max_dd_pct": self.backtest.max_drawdown_pct * 100,
            "bh_spy_pct": self.bh_spy_return_pct * 100,
            "beats_bh_spy": self.beats_bh_spy,
            "spy_excess_ann_pct": self.spy_excess_ann_return * 100,
            "spy_information_ratio": self.spy_information_ratio,
        }


@dataclass
class WalkForwardAggregate:
    strategy: str
    n_windows: int = 0
    n_windows_with_data: int = 0
    median_return_pct: float = 0.0
    mean_return_pct: float = 0.0
    stdev_return_pct: float = 0.0
    pct_positive: float = 0.0
    pct_beat_bh_spy: float = 0.0
    median_sharpe: float = 0.0
    worst_return_pct: float = 0.0
    best_return_pct: float = 0.0
    worst_window_label: str = ""
    best_window_label: str = ""
    total_trades: int = 0
    # SPY-relative reporting (additive; not a gate).
    median_spy_excess_ann_return: float = 0.0
    median_spy_information_ratio: Optional[float] = None
    windows: List[WindowResult] = field(default_factory=list)


def walk_forward(strategy_name: str,
                 params: Optional[dict] = None,
                 *,
                 windows: Optional[List[Tuple[str, datetime, int, str]]] = None,
                 cost_model: Optional[CostModel] = None,
                 decide_fn: Optional[Callable] = None,
                 min_bars: int = 10) -> WalkForwardAggregate:
    """Backtest `strategy_name` across multiple windows.

    Args:
        strategy_name: e.g. 'sma_crossover_qqq'
        params: override params (default: load from disk)
        windows: list of (label, end_dt, days, regime). Default: NAMED_WINDOWS.
        cost_model: default: CostModel.for_symbol(params.symbol)
        decide_fn: override decide fn (for tests)
        min_bars: skip windows with fewer than this many bars (free-tier IEX
            sometimes returns near-empty for pre-2022 stocks).

    Returns: WalkForwardAggregate with per-window results and aggregate stats.
    """
    if params is None or decide_fn is None:
        module, loaded_params = load_strategy_module_and_params(strategy_name)
        if params is None:
            params = loaded_params
        if decide_fn is None:
            decide_fn = module.decide
    symbol = params.get("symbol", "")
    timeframe = str(params.get("timeframe", "1Hour"))
    if cost_model is None:
        cost_model = CostModel.for_symbol(symbol)
    if windows is None:
        windows = NAMED_WINDOWS
    notional = float(params.get("notional_usd", 1000.0))

    agg = WalkForwardAggregate(strategy=strategy_name, n_windows=len(windows))
    returns_pct: List[float] = []
    sharpes: List[float] = []
    beats: List[bool] = []
    for label, end_dt, days, regime in windows:
        bars = bars_cache.get_bars(symbol, timeframe, days=days, end_dt=end_dt)
        if not bars or len(bars) < min_bars:
            # Skip empty/sparse window; record nothing (aggregate will reflect).
            continue
        bt = backtest(strategy_name, bars, params,
                      decide_fn=decide_fn, cost_model=cost_model)
        # Bench scale: BH-SPY return as a fraction of $1000 starting equity,
        # given the bench deploys `notional` per trade. See _benchmark_spy_return.
        bh = _benchmark_spy_return(end_dt, days, timeframe,
                                    notional_usd=notional,
                                    starting_cash=bt.starting_equity)
        beats_bh = bt.total_return_pct > bh
        spy_rel = _compute_spy_relative(bt, bars, end_dt, days, timeframe)
        wr = WindowResult(
            label=label, regime=regime,
            end_date=end_dt.strftime("%Y-%m-%d"), days=days,
            backtest=bt, bh_spy_return_pct=bh, beats_bh_spy=beats_bh,
            spy_excess_ann_return=spy_rel["spy_excess_ann_return"],
            spy_information_ratio=spy_rel["spy_information_ratio"],
            spy_rel_n_periods=spy_rel["spy_rel_n_periods"],
        )
        agg.windows.append(wr)
        returns_pct.append(bt.total_return_pct * 100)
        sharpes.append(bt.sharpe)
        beats.append(beats_bh)
        agg.total_trades += bt.n_trades

    agg.n_windows_with_data = len(agg.windows)
    if returns_pct:
        agg.median_return_pct = statistics.median(returns_pct)
        agg.mean_return_pct = statistics.mean(returns_pct)
        agg.stdev_return_pct = (statistics.stdev(returns_pct)
                                if len(returns_pct) >= 2 else 0.0)
        agg.pct_positive = sum(1 for r in returns_pct if r > 0) / len(returns_pct)
        agg.pct_beat_bh_spy = sum(1 for b in beats if b) / len(beats)
        agg.median_sharpe = statistics.median(sharpes)
        worst_idx = min(range(len(returns_pct)), key=lambda i: returns_pct[i])
        best_idx = max(range(len(returns_pct)), key=lambda i: returns_pct[i])
        agg.worst_return_pct = returns_pct[worst_idx]
        agg.best_return_pct = returns_pct[best_idx]
        agg.worst_window_label = agg.windows[worst_idx].label
        agg.best_window_label = agg.windows[best_idx].label
        # SPY-relative aggregates (additive reporting only).
        excesses = [w.spy_excess_ann_return for w in agg.windows]
        if excesses:
            agg.median_spy_excess_ann_return = statistics.median(excesses)
        irs = [w.spy_information_ratio for w in agg.windows
               if w.spy_information_ratio is not None]
        agg.median_spy_information_ratio = (
            statistics.median(irs) if irs else None)
    return agg


# ---------------------------------------------------------------------------
# Fitness gate — the bar new (LLM-generated) strategies must clear
# ---------------------------------------------------------------------------

# Thresholds tuned for $100-notional, sub-100-trade-per-strategy bench.
# Calibrated for long-only strategies on a regime-balanced panel (currently
# 5 bull / 2 chop / 3 bear named windows means a long-only strategy will
# structurally lose ~3/8 windows simply because the market did). Tighten
# when short/flat capability is added — then a strategy SHOULD be positive
# in bears too, and pct_positive can return to 0.66+.
FITNESS_MEDIAN_RETURN_PCT = 0.0     # must be > 0
FITNESS_PCT_POSITIVE = 0.50          # ≥ 50% of windows positive
FITNESS_PCT_BEAT_BH = 0.50           # ≥ 50% of windows beat BH-SPY
FITNESS_MEDIAN_SHARPE = 0.5          # median Sharpe across windows

# Mutation gate: a candidate must beat its parent's median return by at
# least this much (in absolute percentage points) to be considered an
# improvement worth promoting. Without this, mutations that merely match
# their parent (no edge added) get promoted, inflating the leaderboard
# with noise. 0.10pp ≈ 10bps on a $1000 bench, comparable to one extra
# round-trip's worth of fee drag — small enough that real improvements
# clear it, large enough that pure noise won't.
MUTATION_MIN_DELTA_PCT = 0.10

# --- Stability / risk-adjusted hardening of the mutation gate (2026-06-08) ---
# WHY: the +0.10pp-median-RETURN-only gate above was a redundant-dir factory.
# Independent triage (reports/MUTATION_QUARANTINE_TRIAGE_20260607*.md) showed
# the SAME candidate code flips REJECT<->PROMOTE across re-runs and its
# per-window Sharpe swings the full -1.4...+3.6 range by split selection =
# textbook overfit-to-window-selection. A +0.10pp median-return bump is pure
# window luck, not edge. These three guards force a mutation to demonstrate it
# is (a) sampled on enough trades to be non-accidental, (b) not a risk-adjusted
# DEGRADATION of its parent, and (c) directionally consistent across regimes
# rather than one lucky window dragging a noisy median.
#
# MUTATION_MIN_TOTAL_TRADES: floor on total closed trades summed across all 8
#   walk-forward windows. Below this, the median-return delta is statistically
#   meaningless (a 6-trade "edge" is a coin-flip). 40 ≈ 5 trades/window avg.
MUTATION_MIN_TOTAL_TRADES = 40
# MUTATION_SHARPE_DELTA_TOL: a mutation may not degrade parent median Sharpe by
#   more than this. Catches "juiced raw return by adding leverage/variance"
#   mutations that beat on return but are WORSE risk-adjusted (not alpha).
#   Small negative tolerance allows genuine noise wobble without waving through
#   a real risk-adjusted regression.
MUTATION_SHARPE_DELTA_TOL = -0.10
# MUTATION_MIN_SHARPE_SIGN_CONSISTENCY: fraction of data-windows whose Sharpe
#   must share the sign of the median Sharpe. A candidate whose window Sharpes
#   are +3.6 / -1.4 / +0.1 / ... (median barely positive only because one
#   window mooned) is overfit to window selection; require the median to be
#   REPRESENTATIVE, not an artifact. 0.60 = at least 60% of windows agree.
MUTATION_MIN_SHARPE_SIGN_CONSISTENCY = 0.60


def _window_sharpes(agg: WalkForwardAggregate) -> List[float]:
    """Per-window Sharpe values for windows that had data. Order matches
    `agg.windows`. Used by the stability checks in the mutation gate."""
    return [w.backtest.sharpe for w in agg.windows]


def _sharpe_sign_consistency(agg: WalkForwardAggregate) -> Tuple[float, int]:
    """Return (fraction_of_windows_agreeing_with_median_sharpe_sign, n).

    A window agrees if its Sharpe has the same sign as the median Sharpe.
    Windows with exactly-zero Sharpe (no trades / flat) are treated as
    non-agreeing so an inert candidate can't pass on a pile of zeros. If the
    median Sharpe is ~0, consistency is undefined -> returns (0.0, n) so the
    caller fails it (a 0-median candidate has no directional edge anyway).
    """
    sharpes = _window_sharpes(agg)
    n = len(sharpes)
    if n == 0:
        return (0.0, 0)
    med = agg.median_sharpe
    if abs(med) < 1e-9:
        return (0.0, n)
    med_sign = 1.0 if med > 0 else -1.0
    agree = sum(1 for s in sharpes
                if (s > 0 and med_sign > 0) or (s < 0 and med_sign < 0))
    return (agree / n, n)


def passes_fitness_gate(agg: WalkForwardAggregate) -> Tuple[bool, str]:
    """Decide if a strategy clears the multi-regime fitness bar.

    Calibrated for long-only strategies on a regime-balanced panel. A
    long-only strategy that's always-in-market will lose in bear windows
    by construction, so requiring >66% positive is structurally
    unachievable when the panel includes ~3/8 bear/chop regimes. We use
    50% positive instead, which still requires a strategy to be positive
    more often than not (a coin-flip strategy would fail in expectation).
    Tighten back to 0.66+ when short/flat capability is added — at that
    point a graduating strategy should be positive in bears too.

    Returns (True, "passed") iff ALL of:
        - median_return_pct > 0
        - pct_positive >= 0.50
        - pct_beat_bh_spy >= 0.50
        - median_sharpe > 0.5

    Otherwise (False, "<reason>").

    Need at least 3 windows-with-data; fewer => fail with reason.
    """
    if agg.n_windows_with_data < 3:
        return (False, f"only {agg.n_windows_with_data} window(s) with data "
                       f"(need ≥3 for fitness gate)")
    reasons = []
    if agg.median_return_pct <= FITNESS_MEDIAN_RETURN_PCT:
        reasons.append(f"median return {agg.median_return_pct:+.2f}% ≤ "
                       f"{FITNESS_MEDIAN_RETURN_PCT:+.2f}%")
    if agg.pct_positive < FITNESS_PCT_POSITIVE:
        reasons.append(f"only {agg.pct_positive * 100:.0f}% of windows "
                       f"positive (need ≥{FITNESS_PCT_POSITIVE * 100:.0f}%)")
    if agg.pct_beat_bh_spy < FITNESS_PCT_BEAT_BH:
        reasons.append(f"only {agg.pct_beat_bh_spy * 100:.0f}% beat BH-SPY "
                       f"(need ≥{FITNESS_PCT_BEAT_BH * 100:.0f}%)")
    if agg.median_sharpe <= FITNESS_MEDIAN_SHARPE:
        reasons.append(f"median Sharpe {agg.median_sharpe:.2f} ≤ "
                       f"{FITNESS_MEDIAN_SHARPE:.2f}")
    if reasons:
        return (False, "; ".join(reasons))
    return (True, "passed")


def passes_mutation_gate(
    agg: WalkForwardAggregate,
    parent_agg: Optional[WalkForwardAggregate],
    *,
    min_delta_pct: float = MUTATION_MIN_DELTA_PCT,
) -> Tuple[bool, str]:
    """Stricter gate for LLM-generated mutations.

    A mutation must:
      1. Pass the standard `passes_fitness_gate` (absolute quality bar), AND
      2. Clear the stability guards on the candidate itself: enough total
         trades (`MUTATION_MIN_TOTAL_TRADES`) and a median-Sharpe sign that is
         REPRESENTATIVE across windows (`MUTATION_MIN_SHARPE_SIGN_CONSISTENCY`),
         AND
      3. Not degrade the parent's median Sharpe beyond `MUTATION_SHARPE_DELTA_TOL`
         (raw-return beats that come from added leverage/variance are not
         alpha), AND
      4. Beat its parent's median return by at least `min_delta_pct`
         percentage points (relative-improvement bar).

    Rationale: round 1 of the tournament promoted 3/3 mutants whose
    metrics merely matched (or slightly trailed) their parents'. Then the
    hourly cron turned into a redundant-dir factory (triage
    2026-06-07): the SAME candidate code flipped REJECT<->PROMOTE across
    re-runs because a +0.10pp median-return bump is window luck, not edge.
    Requirements 2 and 3 force each accepted mutation to be sampled on
    enough trades, directionally consistent, and not a risk-adjusted
    regression — not just noise dressed in new code.

    The stability guards (req 2) bind even when `parent_agg` is None or has
    too few windows; only the parent-comparison guards (req 3, 4) fall back
    to absolute-only in that case.

    Returns (passed, reason).
    """
    base_pass, base_reason = passes_fitness_gate(agg)
    if not base_pass:
        return (False, base_reason)

    # --- Stability / risk-adjusted hardening (2026-06-08) --------------------
    # These guards bind on the CANDIDATE itself (independent of parent) so an
    # orphan mutation still has to clear them. They run before the parent
    # comparison so a window-luck candidate is rejected even when no parent
    # baseline is available. See the constant docstrings above for the
    # overfit-to-window-selection evidence that motivated them.
    if agg.total_trades < MUTATION_MIN_TOTAL_TRADES:
        return (False, f"only {agg.total_trades} total trades across windows "
                       f"(need ≥{MUTATION_MIN_TOTAL_TRADES}); median-return "
                       f"delta is statistically meaningless below this")
    consistency, _ncons = _sharpe_sign_consistency(agg)
    if consistency < MUTATION_MIN_SHARPE_SIGN_CONSISTENCY:
        return (False, f"only {consistency * 100:.0f}% of windows agree with "
                       f"median-Sharpe sign (need ≥"
                       f"{MUTATION_MIN_SHARPE_SIGN_CONSISTENCY * 100:.0f}%); "
                       f"median Sharpe is a window-selection artifact, not "
                       f"a representative edge")

    if parent_agg is None:
        return (True, "passed (absolute + stability gate — no parent baseline available)")
    if parent_agg.n_windows_with_data < 3:
        return (True, f"passed (absolute + stability gate — parent had only "
                       f"{parent_agg.n_windows_with_data} window(s) of data)")

    # Risk-adjusted regression guard: a mutation may beat parent on RAW return
    # while degrading risk-adjusted return (e.g. by adding leverage/variance).
    # That is leverage, not alpha — reject it.
    sharpe_delta = agg.median_sharpe - parent_agg.median_sharpe
    if sharpe_delta < MUTATION_SHARPE_DELTA_TOL:
        return (False, f"median Sharpe {agg.median_sharpe:.2f} degrades parent "
                       f"({parent_agg.median_sharpe:.2f}) by {sharpe_delta:+.2f} "
                       f"(tol {MUTATION_SHARPE_DELTA_TOL:+.2f}); raw-return beat "
                       f"is leverage/variance, not risk-adjusted edge")

    delta = agg.median_return_pct - parent_agg.median_return_pct
    if delta < min_delta_pct:
        return (False, f"median return {agg.median_return_pct:+.2f}% only "
                       f"beats parent ({parent_agg.median_return_pct:+.2f}%) "
                       f"by {delta:+.2f}pp; need ≥{min_delta_pct:+.2f}pp")
    return (True, f"passed (beats parent by {delta:+.2f}pp on median return; "
                  f"Sharpe {sharpe_delta:+.2f} vs parent; {agg.total_trades} trades)")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_per_strategy_md(agg: WalkForwardAggregate) -> str:
    """Per-strategy table of windows."""
    lines = [f"### {agg.strategy}", ""]
    lines.append("| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? | SPY-rel Excess Ann % | Info Ratio |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for w in agg.windows:
        bt = w.backtest
        ir_str = (f"{w.spy_information_ratio:.2f}"
                  if w.spy_information_ratio is not None else "n/a")
        lines.append(
            f"| {w.label} | {w.regime} | {bt.n_bars} | {bt.n_trades} | "
            f"{bt.total_return_pct * 100:+.2f} | {bt.sharpe:.2f} | "
            f"{bt.max_drawdown_pct * 100:.2f} | "
            f"{w.bh_spy_return_pct * 100:+.2f} | "
            f"{'✅' if w.beats_bh_spy else '❌'} | "
            f"{w.spy_excess_ann_return * 100:+.2f} | {ir_str} |"
        )
    passed, reason = passes_fitness_gate(agg)
    gate = "🟢 PASS" if passed else "🔴 FAIL"
    lines.append("")
    med_ir = (f"{agg.median_spy_information_ratio:.2f}"
              if agg.median_spy_information_ratio is not None else "n/a")
    lines.append(
        f"**Aggregate:** median ret {agg.median_return_pct:+.2f}% · "
        f"{agg.pct_positive * 100:.0f}% windows positive · "
        f"{agg.pct_beat_bh_spy * 100:.0f}% beat BH-SPY · "
        f"median Sharpe {agg.median_sharpe:.2f} · "
        f"worst {agg.worst_return_pct:+.2f}% ({agg.worst_window_label}) · "
        f"best {agg.best_return_pct:+.2f}% ({agg.best_window_label})"
    )
    lines.append(
        f"**SPY-relative (reporting only, not a gate):** median excess ann "
        f"{agg.median_spy_excess_ann_return * 100:+.2f}% · median info ratio {med_ir}"
    )
    lines.append(f"**Fitness gate:** {gate} — {reason}")
    lines.append("")
    return "\n".join(lines)


def format_ranking_md(aggs: List[WalkForwardAggregate]) -> str:
    """Aggregate ranking table across all strategies."""
    # Rank by a stability-weighted score:
    #   score = median_return_pct * pct_positive
    # This penalizes strategies that win one window by a lot but lose another.
    def score(a: WalkForwardAggregate) -> float:
        return a.median_return_pct * a.pct_positive

    ranked = sorted(aggs, key=score, reverse=True)
    lines = ["| Rank | Strategy | Windows | Median Ret % | % Pos | % Beat BH | Median Sharpe | Worst % | Best % | Fitness |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, a in enumerate(ranked, 1):
        passed, _ = passes_fitness_gate(a)
        gate = "🟢" if passed else "🔴"
        lines.append(
            f"| {i} | {a.strategy} | {a.n_windows_with_data}/{a.n_windows} | "
            f"{a.median_return_pct:+.2f} | "
            f"{a.pct_positive * 100:.0f}% | "
            f"{a.pct_beat_bh_spy * 100:.0f}% | "
            f"{a.median_sharpe:.2f} | "
            f"{a.worst_return_pct:+.2f} | "
            f"{a.best_return_pct:+.2f} | "
            f"{gate} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_for_names(names: List[str]) -> List[WalkForwardAggregate]:
    out: List[WalkForwardAggregate] = []
    for n in names:
        print(f"[{n}] walk-forward across {len(NAMED_WINDOWS)} named windows...",
              file=sys.stderr)
        agg = walk_forward(n)
        passed, reason = passes_fitness_gate(agg)
        gate = "PASS" if passed else "FAIL"
        med_ir = (f"{agg.median_spy_information_ratio:.2f}"
                  if agg.median_spy_information_ratio is not None else "n/a")
        print(f"  -> windows={agg.n_windows_with_data}/{agg.n_windows} "
              f"medRet={agg.median_return_pct:+.2f}% "
              f"pos={agg.pct_positive * 100:.0f}% "
              f"beatBH={agg.pct_beat_bh_spy * 100:.0f}% "
              f"medSharpe={agg.median_sharpe:.2f} "
              f"worst={agg.worst_return_pct:+.2f}% "
              f"spyExcessAnn={agg.median_spy_excess_ann_return * 100:+.2f}% "
              f"medIR={med_ir} "
              f"FITNESS={gate} ({reason})",
              file=sys.stderr)
        out.append(agg)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward backtest across regimes.")
    ap.add_argument("--strategy", help="single strategy name")
    ap.add_argument("--all", action="store_true",
                    help="run all 6 stocks strategies")
    ap.add_argument("--md", help="write Markdown report to this path")
    ap.add_argument("--json", help="dump JSON aggregate to this path")
    args = ap.parse_args()

    if not args.strategy and not args.all:
        ap.error("Provide --strategy NAME or --all")

    names = STOCK_STRATEGIES if args.all else [args.strategy]
    aggs = _run_for_names(names)

    if args.md:
        chunks = ["# Walk-Forward Report\n"]
        chunks.append("## Aggregate Ranking\n")
        chunks.append(format_ranking_md(aggs))
        chunks.append("\n\n## Per-Strategy Detail\n")
        for a in aggs:
            chunks.append(format_per_strategy_md(a))
        Path(args.md).write_text("\n".join(chunks))
        print(f"Wrote Markdown report -> {args.md}")

    if args.json:
        payload = []
        for a in aggs:
            payload.append({
                "strategy": a.strategy,
                "n_windows_with_data": a.n_windows_with_data,
                "median_return_pct": a.median_return_pct,
                "pct_positive": a.pct_positive,
                "pct_beat_bh_spy": a.pct_beat_bh_spy,
                "median_sharpe": a.median_sharpe,
                "median_spy_excess_ann_return": a.median_spy_excess_ann_return,
                "median_spy_information_ratio": a.median_spy_information_ratio,
                "worst": {"label": a.worst_window_label, "pct": a.worst_return_pct},
                "best":  {"label": a.best_window_label,  "pct": a.best_return_pct},
                "fitness_gate": passes_fitness_gate(a),
                "windows": [w.to_row() for w in a.windows],
            })
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"Wrote JSON aggregate -> {args.json}")

    # Always print ranking table to stdout.
    print()
    print("=== Aggregate Ranking ===")
    print(format_ranking_md(aggs))


if __name__ == "__main__":
    main()
