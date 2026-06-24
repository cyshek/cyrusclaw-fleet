"""Reusable parameter / universe SWEEP HARNESS — the edge-search force multiplier.

Every recent swing hand-spawned a subagent that tested ~5 param cells with an
ad-hoc throwaway driver (reports/_lowturn_driver.py, _ss_momentum_driver.py,
_dispersed_universe_driver.py — each reinvented the same wheel). This module
is the first-class replacement: feed it a strategy family + a parameter grid
(+ optional universes) and it runs the FULL walk-forward over the cartesian
product through the EXISTING evaluators, ranks every cell by the CANONICAL
full-period continuous-span Sharpe, and AUTO-CLASSIFIES each passing cell as a
robust PLATEAU (neighbors also pass) or an overfit KNIFE-EDGE (isolated pass).

What it does NOT do: it does not hunt for a winning strategy or promote
anything. It is INFRASTRUCTURE — the machine that lets a future lane test
hundreds of configs systematically and trust a "pass" without a human
re-running jitter by hand every time.

Design guarantees:
  - Reuses runner.walk_forward_xsec.walk_forward_xsec / runner.walk_forward.
    walk_forward — the evaluator is NOT reimplemented.
  - Reuses passes_bar_a_5b, passes_fitness_gate_xsec, passes_fitness_gate.
  - FP-cont Sharpe comes from the ONE canonical helper (runner.fp_sharpe).
  - Cost model is ALWAYS active (asserted; no zero-cost path).
  - Combinatorial-explosion guard: refuses to run > cell_cap cells (default
    500) unless explicitly raised.
  - Touches NO protected runner file. Imports the public evaluator API only.

Usage (xsec basket family):

    from runner.sweep import SweepSpec, run_sweep
    spec = SweepSpec(
        family="xsec",
        decide_fn=decide_xsec,          # candidate's decide_xsec
        base_params=base_params,        # candidate params.json (dict)
        grid={"lookback_bars": [126, 252], "top_k": [3, 5]},
        universes={"lc20": UNIVERSE},   # name -> list[str] (or basket-file path)
        warmup_days=420,
    )
    report = run_sweep(spec)
    print(report.to_markdown())

Front-door verdict per cell uses the same gates the manual drivers asserted:
fitness gate + Bar A bullet #1 + #5(b) deployed-capital DD. A cell PASSES the
front door iff all three pass.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from .backtest import CostModel
from .fp_sharpe import basket_is_crypto, fp_continuous_sharpe
from .walk_forward import (
    NAMED_WINDOWS,
    passes_fitness_gate,
    walk_forward,
)
from .walk_forward_xsec import (
    ZeroTradesError,
    passes_bar_a_5b,
    passes_fitness_gate_xsec,
    walk_forward_xsec,
)

DEFAULT_CELL_CAP = 500

# IS/OOS consistency-guard defaults (defined up here because SweepSpec uses
# DEFAULT_IS_OOS_SPLIT as a field default). The canonical NAMED_WINDOWS span
# 2022-H1 .. 2026-recent; cutting at 2024-01-01 puts 2022/2023 in-sample and
# 2024+ out-of-sample. A cell that only earns its keep AFTER this date (flat or
# negative before) is a single-regime artifact, not a forward edge.
DEFAULT_IS_OOS_SPLIT = "2024-01-01"
# A cell is flagged REGIME_ARTIFACT when OOS looks promotable but IS does not
# corroborate (mirrors the bond-leg/commodity-leg post-mortem: full-period ~0
# with a positive OOS-only tail is the exact signature).
REGIME_ARTIFACT_OOS_MIN = 0.5      # OOS Sharpe that would otherwise look promotable
IS_CORROBORATION_FLOOR = 0.0       # IS Sharpe must be at least break-even


# ---------------------------------------------------------------------------
# Sweep spec
# ---------------------------------------------------------------------------

@dataclass
class SweepSpec:
    """A declarative sweep: a strategy family + a parameter grid + universes.

    family: "xsec" (basket strategy via walk_forward_xsec) or "single"
        (single-symbol strategy via walk_forward).
    decide_fn: the strategy's decide function. For "xsec" this is
        decide_xsec(market_state, position_state, params); for "single" it is
        decide(market_state, position_state, params). Required (we run via the
        decide_fn override path so no strategy needs to live in strategies/).
    base_params: the strategy's baseline params dict (e.g. params.json). Each
        cell starts from a copy of this and overrides the swept keys.
    grid: param_name -> list of values. Cartesian product over all keys. An
        empty grid means a single cell (just base_params).
    universes: OPTIONAL. name -> basket (list[str]) OR name -> path to a basket
        file (one symbol per line, or a JSON list). If provided, the product is
        taken over (grid_cell x universe). For "single" family the universe is
        ignored (symbol comes from params).
    strategy_label: label passed to the evaluator (loader hint / report id).
    warmup_days: forwarded to walk_forward_xsec (primes slow lookbacks).
    windows: override NAMED_WINDOWS (mostly for tests).
    cost_model: forwarded to the evaluator. Default alpaca_stocks(). NEVER
        None-disabled; a zero-cost model is rejected by the active-cost assert.
    cell_cap: refuse to run more than this many cells (combinatorial guard).
    allow_zero_trades: forwarded to walk_forward_xsec (rarely needed).
    """
    family: str
    decide_fn: Callable
    base_params: dict
    grid: Dict[str, List] = field(default_factory=dict)
    universes: Optional[Dict[str, Union[str, Sequence[str]]]] = None
    strategy_label: str = "sweep_candidate"
    warmup_days: int = 0
    windows: Optional[List[Tuple[str, datetime, int, str]]] = None
    cost_model: Optional[CostModel] = None
    cell_cap: int = DEFAULT_CELL_CAP
    allow_zero_trades: bool = False
    is_oos_split: str = DEFAULT_IS_OOS_SPLIT   # IS/OOS-consistency guard cutoff
    ew_control: bool = True                    # run the EW-of-universe baseline

    def __post_init__(self):
        if self.family not in ("xsec", "single"):
            raise ValueError(
                f"family must be 'xsec' or 'single', got {self.family!r}")
        if not callable(self.decide_fn):
            raise TypeError("decide_fn must be callable")
        if not isinstance(self.base_params, dict):
            raise TypeError("base_params must be a dict")


# ---------------------------------------------------------------------------
# Grid expansion + cell-cap guard
# ---------------------------------------------------------------------------

def _resolve_universe(u: Union[str, Sequence[str]]) -> List[str]:
    """A universe entry is either a list of symbols or a path to a basket file
    (one symbol per line OR a JSON list)."""
    if isinstance(u, (list, tuple)):
        return [str(s) for s in u]
    p = Path(str(u))
    text = p.read_text()
    text_stripped = text.strip()
    if text_stripped.startswith("["):
        return [str(s) for s in json.loads(text_stripped)]
    out: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def expand_grid(grid: Dict[str, List]) -> List[Dict]:
    """Cartesian product of a param grid -> list of override dicts.

    Order is deterministic: keys in insertion order, values in given order. An
    empty grid yields a single empty override (one cell = base_params)."""
    if not grid:
        return [{}]
    keys = list(grid.keys())
    value_lists = [list(grid[k]) for k in keys]
    for k, vals in zip(keys, value_lists):
        if len(vals) == 0:
            raise ValueError(f"grid axis {k!r} has no values")
    cells = []
    for combo in itertools.product(*value_lists):
        cells.append(dict(zip(keys, combo)))
    return cells


def enumerate_cells(
        spec: SweepSpec) -> List[Tuple[Dict, Optional[str], List[str]]]:
    """Full list of (param_override, universe_name, universe_symbols) cells.

    For "single" family universes are ignored -> universe_name is None and
    symbols is []. For "xsec" with no universes given, a single None universe
    is used (the basket comes from base_params -> handled in run_sweep). Raises
    ValueError if the cell count exceeds spec.cell_cap.
    """
    param_cells = expand_grid(spec.grid)
    out: List[Tuple[Dict, Optional[str], List[str]]] = []
    if spec.family == "single" or not spec.universes:
        for pc in param_cells:
            out.append((pc, None, []))
    else:
        for uname, uval in spec.universes.items():
            syms = _resolve_universe(uval)
            for pc in param_cells:
                out.append((pc, uname, syms))
    n = len(out)
    if n > spec.cell_cap:
        raise ValueError(
            f"sweep would run {n} cells > cell_cap {spec.cell_cap}. This is a "
            f"combinatorial-explosion guard. Narrow the grid/universes or "
            f"raise cell_cap explicitly if you really mean it.")
    return out


# ---------------------------------------------------------------------------
# Per-cell result
# ---------------------------------------------------------------------------

def _hashable(v):
    """Make a grid value hashable for neighbor-lookup keys (lists -> tuples)."""
    if isinstance(v, list):
        return tuple(v)
    return v


@dataclass
class CellResult:
    """One swept cell: its config, its metrics, and its front-door verdict."""
    cell_id: int
    params: Dict                       # the swept override (NOT full params)
    universe_name: Optional[str]
    universe: List[str]
    # Metrics
    fp_cont_sharpe: float = 0.0        # PRIMARY rank key (clause a). Canonical.
    n_fp_returns: int = 0
    is_fp_sharpe: float = 0.0          # in-sample sub-Sharpe (IS/OOS guard)
    oos_fp_sharpe: float = 0.0         # out-of-sample sub-Sharpe (IS/OOS guard)
    n_is_returns: int = 0
    n_oos_returns: int = 0
    median_window_sharpe: float = 0.0  # SECONDARY / generous. A mirage.
    worst_instrument_dd_pct: float = 0.0
    ann_return_on_deployed_pct: float = 0.0
    round_trip_count: int = 0
    median_return_pct: float = 0.0
    pct_positive: float = 0.0
    # EW-of-same-universe control deltas (filled in run_sweep; nan = no control)
    ew_full_sharpe: float = float("nan")
    ew_oos_sharpe: float = float("nan")
    beats_ew_full: Optional[bool] = None
    beats_ew_oos: Optional[bool] = None
    # Verdict
    fitness_pass: bool = False
    bar_a1_pass: bool = False
    dd5b_pass: bool = False
    front_door_pass: bool = False
    reject_clauses: List[str] = field(default_factory=list)
    # Robustness (filled in by classify_robustness)
    robustness: str = ""               # "" | "PLATEAU" | "KNIFE_EDGE"
    # Honesty flags (filled in run_sweep AFTER robustness): a passing PLATEAU
    # cell can still be untrustworthy if it is an OOS-only regime artifact or
    # loses to the no-signal EW control. trustworthy gates surfacing.
    regime_artifact: bool = False
    fails_ew_control: bool = False
    trustworthy: bool = False
    error: Optional[str] = None        # set if the cell raised

    @property
    def grid_key(self) -> Tuple:
        return (self.universe_name,
                tuple(sorted((k, _hashable(v)) for k, v in self.params.items())))


# ---------------------------------------------------------------------------
# Deployed annualized return (consolidated from the throwaway drivers)
# ---------------------------------------------------------------------------

def deployed_ann_return_pct(agg, deployed: float) -> float:
    """Annualized (compound) return on DEPLOYED notional over the full WF span.

    Consolidates the identical deployed_ann_return copies in
    _ss_momentum_driver.py / _lowturn_driver.py. total_return_usd is direct USD
    pnl per window; ret_on_deployed = sum(pnl)/deployed, annualized by total
    trading days / 252.
    """
    windows = getattr(agg, "windows", [])
    total_pnl = sum(getattr(w.backtest, "total_return_usd", 0.0) for w in windows)
    total_days = sum(getattr(w, "days", 0) for w in windows)
    if total_days <= 0 or deployed <= 0:
        return 0.0
    ret_on_deployed = total_pnl / deployed
    years = total_days / 252.0
    if years <= 0:
        return 0.0
    try:
        return ((1.0 + ret_on_deployed) ** (1.0 / years) - 1.0) * 100.0
    except (ValueError, OverflowError):
        return (ret_on_deployed / years) * 100.0


# ---------------------------------------------------------------------------
# Cost-model guard (always active — no zero-cost path)
# ---------------------------------------------------------------------------

def _assert_cost_active(cm: CostModel) -> None:
    """Refuse a zero-cost model. Edge must survive friction; a sweep cell that
    silently ran cost-free would be a fake pass. Mirrors the assert every
    manual driver carries."""
    spread = float(getattr(cm, "spread_bps", 0.0) or 0.0)
    fee = float(getattr(cm, "fee_bps", 0.0) or 0.0)
    if spread <= 0.0 and fee <= 0.0:
        raise AssertionError(
            "cost model is zero-cost (spread_bps and fee_bps both 0) — refusing "
            "to run a cost-free sweep. A real cost model is mandatory.")


# ---------------------------------------------------------------------------
# IS/OOS consistency guard  +  EW-of-same-universe control
# (the two disciplines that killed three research lanes on 2026-06-23: every
#  one died OOS-positive-but-IS-negative, or losing to a no-signal EW hold of
#  its own instruments. The plateau/knife-edge classifier alone could not see
#  either — a gaudy OOS plateau IS the mirage. These guards make those kills
#  automatic.)
# ---------------------------------------------------------------------------

# Default IS/OOS split: the canonical NAMED_WINDOWS span 2022-H1 .. 2026-recent.
# Cutting at 2024-01-01 puts the 2022/2023 windows in-sample and 2024+ out.
# A cell that only earns its keep AFTER this date (and is flat/negative before)
# is a single-regime artifact, not a forward edge.
DEFAULT_IS_OOS_SPLIT = "2024-01-01"

# A cell is flagged REGIME_ARTIFACT when its OOS sub-Sharpe looks good but its
# IS sub-Sharpe does NOT corroborate. "Looks good OOS" = oos >= this; "does not
# corroborate" = is_sharpe below IS_CORROBORATION_FLOOR. These mirror the
# bond-leg/commodity-leg post-mortem: full-period ~0 with a positive OOS-only
# tail is the exact signature.
REGIME_ARTIFACT_OOS_MIN = 0.5      # OOS Sharpe that would otherwise look promotable
IS_CORROBORATION_FLOOR = 0.0       # IS Sharpe must be at least break-even


def _window_end_naive(w) -> Optional[datetime]:
    """Best-effort window end as a naive datetime for IS/OOS splitting.

    walk-forward windows expose `.end_date` as an ISO date string (e.g.
    '2024-07-01'). Returns None if it can't be parsed (the caller then treats
    the window as IS by default — never silently OOS, which would flatter a
    cell)."""
    ed = getattr(w, "end_date", None)
    if ed is None:
        return None
    if isinstance(ed, datetime):
        return ed.replace(tzinfo=None)
    try:
        s = str(ed).replace("Z", "")
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def is_oos_split_sharpe(
        windows, *, split_date: str, timeframe: str, is_crypto: bool
) -> Tuple[float, float, int, int]:
    """Split walk-forward windows at `split_date` and return
    (is_fp_sharpe, oos_fp_sharpe, n_is_returns, n_oos_returns).

    IS = windows ending strictly before split_date; OOS = the rest. Windows
    whose end-date can't be parsed are counted IS (conservative — they cannot
    inflate the OOS tail). Empty side -> 0.0 Sharpe / 0 returns. Reuses the ONE
    canonical FP-cont Sharpe helper on each subset (no metric reimplementation).
    """
    try:
        cut = datetime.fromisoformat(str(split_date)).replace(tzinfo=None)
    except (ValueError, TypeError):
        cut = datetime.fromisoformat(DEFAULT_IS_OOS_SPLIT)
    is_w, oos_w = [], []
    for w in windows:
        end = _window_end_naive(w)
        if end is not None and end >= cut:
            oos_w.append(w)
        else:
            is_w.append(w)
    is_fps, n_is = (fp_continuous_sharpe(
        is_w, timeframe=timeframe, is_crypto=is_crypto) if is_w else (0.0, 0))
    oos_fps, n_oos = (fp_continuous_sharpe(
        oos_w, timeframe=timeframe, is_crypto=is_crypto) if oos_w else (0.0, 0))
    return is_fps, oos_fps, n_is, n_oos


def _is_regime_artifact(is_fps: float, oos_fps: float, full_fps: float) -> bool:
    """True iff the cell's edge is an OOS-only single-regime artifact: OOS looks
    promotable but IS does not corroborate (and the full-period Sharpe is not
    itself strong). This is the commodity-leg mirage detector."""
    if oos_fps < REGIME_ARTIFACT_OOS_MIN:
        return False               # not even an OOS sparkle -> ordinary reject path
    if is_fps >= IS_CORROBORATION_FLOOR and full_fps >= IS_CORROBORATION_FLOOR:
        return False               # IS corroborates -> genuine, not an artifact
    return True


class _EWControlAction:
    """Minimal Action for the no-signal equal-weight baseline (mirrors the
    `_BHAction` shape every manual driver hand-rolled)."""
    __slots__ = ("action", "symbol", "notional_usd", "qty", "reason")

    def __init__(self, action: str, symbol: str, notional: float):
        self.action = action
        self.symbol = symbol
        self.notional_usd = notional
        self.qty = None
        self.reason = "ew_control_baseline"


def _decide_xsec_equal_weight(market_state, position_state, params):
    """No-signal control: hold every basket name at equal weight, buy once then
    hold. The cell under test must BEAT this, OOS net of cost, or its 'edge' is
    survivorship/beta of the universe rather than the signal (the fundamentals-
    PIT + BAB lesson)."""
    syms = list(params.get("basket", []))
    if not syms:
        return {}
    notional = float(params.get("notional_usd",
                                params.get("max_notional_usd", 1000.0))) / len(syms)
    out: Dict[str, object] = {}
    for s in syms:
        held = position_state.get(s)
        qty = getattr(held, "qty", None) if held is not None else None
        if not qty:
            out[s] = _EWControlAction("buy", s, notional)
        else:
            out[s] = _EWControlAction("hold", s, 0.0)
    return out


def ew_control_sharpe(
        spec: "SweepSpec", basket: List[str], cost_model: CostModel,
) -> Tuple[float, float, int]:
    """Full + OOS FP-cont Sharpe of a no-signal equal-weight hold of `basket`,
    run through the SAME evaluator/windows/cost as the cells (apples-to-apples).
    Returns (full_fps, oos_fps, n_returns). On any evaluator error returns
    (nan, nan, 0) and the caller skips the EW gate for that universe (a broken
    baseline must not silently pass or fail cells)."""
    import math
    if not basket:
        return (float("nan"), float("nan"), 0)
    params = dict(spec.base_params)
    params["basket"] = list(basket)
    windows = spec.windows or NAMED_WINDOWS
    try:
        agg = walk_forward_xsec(
            f"{spec.strategy_label}__ewctrl", basket, params=params,
            decide_xsec_fn=_decide_xsec_equal_weight, windows=windows,
            warmup_days=spec.warmup_days, cost_model=cost_model,
            allow_zero_trades=True)
    except Exception:  # noqa: BLE001 — a broken baseline must not gate cells
        return (float("nan"), float("nan"), 0)
    is_crypto = basket_is_crypto(basket)
    tf = str(params.get("timeframe", "1Day"))
    full_fps, nret = fp_continuous_sharpe(agg.windows, timeframe=tf,
                                          is_crypto=is_crypto)
    _, oos_fps, _, _ = is_oos_split_sharpe(
        agg.windows, split_date=spec.is_oos_split or DEFAULT_IS_OOS_SPLIT,
        timeframe=tf, is_crypto=is_crypto)
    return (full_fps, oos_fps, nret)


# ---------------------------------------------------------------------------
# Single-cell evaluation
# ---------------------------------------------------------------------------

def _eval_cell_xsec(spec: SweepSpec, override: Dict, basket: List[str],
                    cost_model: CostModel) -> Tuple[dict, Optional[str]]:
    """Run one xsec cell through walk_forward_xsec. Returns (metrics, error)."""
    params = dict(spec.base_params)
    params.update(override)
    windows = spec.windows or NAMED_WINDOWS
    try:
        agg = walk_forward_xsec(
            spec.strategy_label, basket, params=params,
            decide_xsec_fn=spec.decide_fn, windows=windows,
            warmup_days=spec.warmup_days, cost_model=cost_model,
            allow_zero_trades=spec.allow_zero_trades)
    except ZeroTradesError as e:
        return ({}, f"ZeroTradesError: {e}")
    deployed = float(params.get("notional_usd",
                                params.get("max_notional_usd", 1000.0)))
    is_crypto = basket_is_crypto(basket)
    tf = str(params.get("timeframe", "1Day"))
    fps, nret = fp_continuous_sharpe(
        agg.windows, timeframe=tf, is_crypto=is_crypto)
    is_fps, oos_fps, n_is, n_oos = is_oos_split_sharpe(
        agg.windows, split_date=spec.is_oos_split or DEFAULT_IS_OOS_SPLIT,
        timeframe=tf, is_crypto=is_crypto)
    fit_pass, _ = passes_fitness_gate_xsec(agg)
    dd_pass, _ = passes_bar_a_5b(agg)
    metrics = {
        "fp_cont_sharpe": fps,
        "n_fp_returns": nret,
        "is_fp_sharpe": is_fps,
        "oos_fp_sharpe": oos_fps,
        "n_is_returns": n_is,
        "n_oos_returns": n_oos,
        "median_window_sharpe": agg.median_sharpe,
        "worst_instrument_dd_pct": agg.worst_instrument_dd_pct,
        "ann_return_on_deployed_pct": deployed_ann_return_pct(agg, deployed),
        "round_trip_count": agg.total_trades,
        "median_return_pct": agg.median_return_pct,
        "pct_positive": agg.pct_positive,
        "fitness_pass": fit_pass,
        "bar_a1_pass": agg.bar_a_bullet1_pass,
        "dd5b_pass": dd_pass,
    }
    return metrics, None


def _eval_cell_single(spec: SweepSpec, override: Dict,
                      cost_model: CostModel) -> Tuple[dict, Optional[str]]:
    """Run one single-symbol cell through walk_forward. Returns (metrics, err)."""
    params = dict(spec.base_params)
    params.update(override)
    windows = spec.windows or NAMED_WINDOWS
    agg = walk_forward(
        spec.strategy_label, params=params, decide_fn=spec.decide_fn,
        windows=windows, cost_model=cost_model)
    deployed = float(params.get("notional_usd", 1000.0))
    tf = str(params.get("timeframe", "1Day"))
    is_crypto = ("/" in str(params.get("symbol", "")))
    fps, nret = fp_continuous_sharpe(
        agg.windows, timeframe=tf, is_crypto=is_crypto)
    is_fps, oos_fps, n_is, n_oos = is_oos_split_sharpe(
        agg.windows, split_date=spec.is_oos_split or DEFAULT_IS_OOS_SPLIT,
        timeframe=tf, is_crypto=is_crypto)
    fit_pass, _ = passes_fitness_gate(agg)
    # Single-symbol deployed-capital DD is the portfolio max_drawdown_pct (a
    # single-symbol strategy is not a diluted basket). Worst across windows.
    dds = [w.backtest.max_drawdown_pct for w in agg.windows]
    worst_dd = (min(dds) * 100.0) if dds else 0.0
    dd_pass = abs(worst_dd) <= 30.0
    metrics = {
        "fp_cont_sharpe": fps,
        "n_fp_returns": nret,
        "is_fp_sharpe": is_fps,
        "oos_fp_sharpe": oos_fps,
        "n_is_returns": n_is,
        "n_oos_returns": n_oos,
        "median_window_sharpe": agg.median_sharpe,
        "worst_instrument_dd_pct": worst_dd,
        "ann_return_on_deployed_pct": deployed_ann_return_pct(agg, deployed),
        "round_trip_count": agg.total_trades,
        "median_return_pct": agg.median_return_pct,
        "pct_positive": agg.pct_positive,
        "fitness_pass": fit_pass,
        "bar_a1_pass": True,   # Bar A #1 is an xsec-specific bullet; n/a single
        "dd5b_pass": dd_pass,
    }
    return metrics, None


def _verdict(metrics: dict) -> Tuple[bool, List[str]]:
    """Front-door PASS iff fitness + Bar A #1 + #5(b)-DD all pass. Also records
    clause (a) FP-cont Sharpe < 1.0 as a reject reason (the load-bearing bar)."""
    clauses: List[str] = []
    if metrics["fp_cont_sharpe"] < 1.0:
        clauses.append("a")        # FP-cont Sharpe below 1.0
    if not metrics["fitness_pass"]:
        clauses.append("fitness")
    if not metrics["bar_a1_pass"]:
        clauses.append("#1")
    if not metrics["dd5b_pass"]:
        clauses.append("#5b")
    front = (metrics["fitness_pass"] and metrics["bar_a1_pass"]
             and metrics["dd5b_pass"])
    return front, clauses


# ---------------------------------------------------------------------------
# Robustness classifier (PLATEAU vs KNIFE-EDGE) — the single most important feature
# ---------------------------------------------------------------------------

def classify_robustness(cells: List[CellResult], grid: Dict[str, List]) -> None:
    """Tag each PASSING cell as PLATEAU or KNIFE_EDGE in-place.

    A passing cell is a PLATEAU if AT LEAST ONE immediate neighbor (a cell that
    differs by exactly ±1 grid step on a SINGLE axis) also passes. A passing
    cell whose every ±1 neighbor fails (or that has no in-grid neighbors at
    all) is a KNIFE_EDGE = overfit, auto-flagged NOT robust.

    Non-passing cells get robustness "" (blank). The classifier operates within
    each universe independently (neighbors must share the same universe_name).
    A fully degenerate single-cell grid yields no neighbors, so a lone pass is a
    KNIFE_EDGE by definition (nothing supports it).
    """
    axes = list(grid.keys())
    value_index: Dict[str, Dict] = {}
    for ax in axes:
        value_index[ax] = {_hashable(v): i for i, v in enumerate(grid[ax])}

    def pos_vector(cell: CellResult) -> Optional[Tuple]:
        """Integer coordinate of a cell along the swept axes, or None if the
        cell's params don't sit on the grid (e.g. base-only cell)."""
        coords = []
        for ax in axes:
            if ax not in cell.params:
                return None
            key = _hashable(cell.params[ax])
            if key not in value_index[ax]:
                return None
            coords.append(value_index[ax][key])
        return tuple(coords)

    pass_at: Dict[Tuple, bool] = {}
    for c in cells:
        pv = pos_vector(c)
        if pv is None:
            continue
        pass_at[(c.universe_name, pv)] = c.front_door_pass

    for c in cells:
        if not c.front_door_pass:
            c.robustness = ""
            continue
        pv = pos_vector(c)
        if pv is None:
            c.robustness = "KNIFE_EDGE"  # off-grid pass, nothing supports it
            continue
        neighbor_passes = []
        for ai in range(len(axes)):
            for delta in (-1, +1):
                coord = list(pv)
                coord[ai] += delta
                if coord[ai] < 0 or coord[ai] >= len(grid[axes[ai]]):
                    continue
                nkey = (c.universe_name, tuple(coord))
                if nkey in pass_at:
                    neighbor_passes.append(pass_at[nkey])
        if neighbor_passes and any(neighbor_passes):
            c.robustness = "PLATEAU"
        else:
            c.robustness = "KNIFE_EDGE"


# ---------------------------------------------------------------------------
# Sweep report
# ---------------------------------------------------------------------------

@dataclass
class SweepReport:
    spec_label: str
    family: str
    cells: List[CellResult]
    grid: Dict[str, List]
    universes: List[str]
    cost_model_desc: str
    n_cells: int = 0
    n_pass: int = 0
    n_plateau: int = 0
    n_knife_edge: int = 0
    n_error: int = 0

    def ranked(self) -> List[CellResult]:
        """Cells ranked by FP-cont Sharpe descending (primary). Errored last."""
        return sorted(self.cells,
                      key=lambda c: (c.error is not None, -c.fp_cont_sharpe))

    def plateaus(self) -> List[CellResult]:
        """Robust passing cells surfaced for human review (FP-cont desc)."""
        return [c for c in self.ranked() if c.robustness == "PLATEAU"]

    def _fmt_params(self, c: CellResult) -> str:
        if not c.params:
            return "(base)"
        return " ".join(f"{k}={c.params[k]}" for k in c.params)

    def to_markdown(self) -> str:
        L: List[str] = []
        L.append(f"# Sweep Report — {self.spec_label} ({self.family})")
        L.append("")
        L.append(
            f"- **cells:** {self.n_cells}  ·  "
            f"**front-door pass:** {self.n_pass}  ·  "
            f"**PLATEAU (robust):** {self.n_plateau}  ·  "
            f"**KNIFE-EDGE (overfit):** {self.n_knife_edge}  ·  "
            f"**errored:** {self.n_error}")
        L.append(f"- **grid:** {json.dumps(self.grid)}")
        L.append(f"- **universes:** {', '.join(self.universes) or '(from params)'}")
        L.append(f"- **cost model:** {self.cost_model_desc} (ACTIVE — asserted)")
        L.append(f"- **primary rank key:** full-period continuous-span Sharpe "
                 f"(clause a). median-window Sharpe shown SECONDARY/generous.")
        L.append("")
        L.append("| rank | universe | params | FP-cont Sharpe (a) | med-win Sharpe (gen) | worst instr DD% | ann/deployed% | round-trips | verdict | robustness |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for i, c in enumerate(self.ranked(), start=1):
            if c.error:
                L.append(
                    f"| {i} | {c.universe_name or '-'} | {self._fmt_params(c)} | "
                    f"ERR | - | - | - | - | ERROR | {c.error[:40]} |")
                continue
            verdict = "PASS" if c.front_door_pass else "REJECT"
            if c.reject_clauses:
                verdict += "(" + ",".join(c.reject_clauses) + ")"
            rob = c.robustness or "-"
            L.append(
                f"| {i} | {c.universe_name or '-'} | {self._fmt_params(c)} | "
                f"{c.fp_cont_sharpe:+.2f} | {c.median_window_sharpe:+.2f} | "
                f"{c.worst_instrument_dd_pct:.2f} | "
                f"{c.ann_return_on_deployed_pct:+.2f} | {c.round_trip_count} | "
                f"{verdict} | {rob} |")
        L.append("")
        plats = self.plateaus()
        if plats:
            L.append(f"## ROBUST PLATEAUS surfaced for human review ({len(plats)})")
            for c in plats:
                L.append(
                    f"- **{c.universe_name or '-'} / {self._fmt_params(c)}**: "
                    f"FP-cont Sharpe {c.fp_cont_sharpe:+.2f}, "
                    f"ann {c.ann_return_on_deployed_pct:+.2f}%/yr, "
                    f"{c.round_trip_count} round-trips — passing neighbors confirm "
                    f"this is NOT a knife-edge.")
        else:
            L.append("## ROBUST PLATEAUS: none")
            L.append("No front-door-passing cell sits on a robust plateau. "
                     "Any passing cell present is an auto-flagged KNIFE-EDGE "
                     "(overfit / isolated) and is NOT trustworthy.")
        L.append("")
        return "\n".join(L)


# ---------------------------------------------------------------------------
# Top-level driver
# ---------------------------------------------------------------------------

def run_sweep(spec: SweepSpec, *, verbose: bool = False) -> SweepReport:
    """Execute the full sweep: enumerate cells (with the cell-cap guard), run
    each through the EXISTING evaluator, score the canonical FP-cont Sharpe +
    gates, classify robustness, and return a ranked SweepReport.

    The cost model is asserted ACTIVE before any cell runs (no zero-cost path).
    Errored cells (e.g. ZeroTradesError) are recorded with `.error` set and
    sorted last; they never count as passes and never anchor a plateau.
    """
    cost_model = spec.cost_model or CostModel.alpaca_stocks()
    _assert_cost_active(cost_model)
    cell_specs = enumerate_cells(spec)

    cells: List[CellResult] = []
    for cid, (override, uname, syms) in enumerate(cell_specs):
        if spec.family == "xsec":
            basket = syms if syms else list(spec.base_params.get("basket", []))
            metrics, err = _eval_cell_xsec(spec, override, basket, cost_model)
        else:
            metrics, err = _eval_cell_single(spec, override, cost_model)
        cr = CellResult(
            cell_id=cid, params=dict(override), universe_name=uname,
            universe=list(syms))
        if err is not None:
            cr.error = err
        else:
            cr.fp_cont_sharpe = metrics["fp_cont_sharpe"]
            cr.n_fp_returns = metrics["n_fp_returns"]
            cr.is_fp_sharpe = metrics.get("is_fp_sharpe", 0.0)
            cr.oos_fp_sharpe = metrics.get("oos_fp_sharpe", 0.0)
            cr.n_is_returns = metrics.get("n_is_returns", 0)
            cr.n_oos_returns = metrics.get("n_oos_returns", 0)
            cr.median_window_sharpe = metrics["median_window_sharpe"]
            cr.worst_instrument_dd_pct = metrics["worst_instrument_dd_pct"]
            cr.ann_return_on_deployed_pct = metrics["ann_return_on_deployed_pct"]
            cr.round_trip_count = metrics["round_trip_count"]
            cr.median_return_pct = metrics["median_return_pct"]
            cr.pct_positive = metrics["pct_positive"]
            cr.fitness_pass = metrics["fitness_pass"]
            cr.bar_a1_pass = metrics["bar_a1_pass"]
            cr.dd5b_pass = metrics["dd5b_pass"]
            front, clauses = _verdict(metrics)
            cr.front_door_pass = front
            cr.reject_clauses = clauses
        cells.append(cr)
        if verbose:
            tag = cr.error or ("PASS" if cr.front_door_pass else "REJECT")
            print(f"[cell {cid}] {uname or '-'} {override} -> "
                  f"FPcont={cr.fp_cont_sharpe:+.2f} {tag}")

    classify_robustness(cells, spec.grid)

    report = SweepReport(
        spec_label=spec.strategy_label, family=spec.family, cells=cells,
        grid=dict(spec.grid),
        universes=list(spec.universes.keys()) if spec.universes else [],
        cost_model_desc=(f"spread {cost_model.spread_bps}bps / "
                         f"fee {cost_model.fee_bps}bps"))
    report.n_cells = len(cells)
    report.n_pass = sum(1 for c in cells if c.front_door_pass)
    report.n_plateau = sum(1 for c in cells if c.robustness == "PLATEAU")
    report.n_knife_edge = sum(1 for c in cells if c.robustness == "KNIFE_EDGE")
    report.n_error = sum(1 for c in cells if c.error is not None)
    return report
