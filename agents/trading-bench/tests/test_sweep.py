"""Tests for the parameter/universe SWEEP HARNESS (runner/sweep.py) and the
canonical full-period continuous-span Sharpe helper (runner/fp_sharpe.py).

Coverage:
  1. Grid expansion + cell-cap combinatorial guard.
  2. Canonical FP-cont Sharpe against a HAND-COMPUTED series (the load-bearing
     ruler — pinned so it can never silently drift again).
  3. Plateau / knife-edge robustness classifier on synthetic grids:
       - one isolated passing cell  -> KNIFE_EDGE
       - a contiguous passing region -> PLATEAU
  4. Deployed-ann-return + cost-active guard.
  5. VALIDATION / regression anchor: run the harness on the already-
     characterized xsec momentum family over a tiny K x cadence grid on the
     existing 20-name universe and confirm it REPRODUCES the known reject
     (FP-cont Sharpe ~ -0.11..+0.21, every cell REJECT, basin is NOT a
     knife-edge ridge) matching reports/SS_MOMENTUM_MONTHLY.
"""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest import CostModel
from runner.fp_sharpe import (
    basket_is_crypto,
    concat_window_returns,
    equity_curve_returns,
    fp_continuous_sharpe,
    sharpe_from_returns,
)
from runner.sweep import (
    CellResult,
    SweepSpec,
    classify_robustness,
    deployed_ann_return_pct,
    enumerate_cells,
    expand_grid,
    run_sweep,
    _assert_cost_active,
    _verdict,
)


# ===========================================================================
# Test doubles
# ===========================================================================

@dataclass
class _FakeBT:
    equity_curve: List[float]
    total_return_usd: float = 0.0


@dataclass
class _FakeWindow:
    backtest: _FakeBT
    days: int = 90


def _win(ec, pnl=0.0, days=90):
    return _FakeWindow(backtest=_FakeBT(equity_curve=list(ec), total_return_usd=pnl),
                       days=days)


# ===========================================================================
# 1. Grid expansion + cell-cap guard
# ===========================================================================

def test_expand_grid_cartesian_product():
    cells = expand_grid({"k": [3, 5], "cad": [1, 3]})
    assert len(cells) == 4
    assert {"k": 3, "cad": 1} in cells
    assert {"k": 5, "cad": 3} in cells


def test_expand_grid_empty_is_single_cell():
    assert expand_grid({}) == [{}]


def test_expand_grid_rejects_empty_axis():
    with pytest.raises(ValueError):
        expand_grid({"k": []})


def test_expand_grid_deterministic_order():
    cells = expand_grid({"a": [1, 2], "b": [10, 20]})
    assert cells == [
        {"a": 1, "b": 10}, {"a": 1, "b": 20},
        {"a": 2, "b": 10}, {"a": 2, "b": 20},
    ]


def _dummy_decide(market_state, position_state, params):
    return {}


def test_cell_cap_guard_refuses_explosion():
    # 10 x 10 x 10 = 1000 cells > default 500 cap.
    spec = SweepSpec(
        family="single", decide_fn=_dummy_decide, base_params={"symbol": "SPY"},
        grid={"a": list(range(10)), "b": list(range(10)), "c": list(range(10))},
        cell_cap=500)
    with pytest.raises(ValueError, match="combinatorial-explosion"):
        enumerate_cells(spec)


def test_cell_cap_guard_allows_under_cap():
    spec = SweepSpec(
        family="single", decide_fn=_dummy_decide, base_params={"symbol": "SPY"},
        grid={"a": [1, 2, 3], "b": [1, 2]}, cell_cap=500)
    cells = enumerate_cells(spec)
    assert len(cells) == 6


def test_cell_cap_counts_universes_in_product():
    # 4 param cells x 3 universes = 12 cells; cap at 10 must trip.
    spec = SweepSpec(
        family="xsec", decide_fn=_dummy_decide, base_params={},
        grid={"k": [3, 5], "cad": [1, 3]},
        universes={"u1": ["A", "B"], "u2": ["C", "D"], "u3": ["E", "F"]},
        cell_cap=10)
    with pytest.raises(ValueError, match="12 cells > cell_cap 10"):
        enumerate_cells(spec)


def test_resolve_universe_from_list_and_jsonfile(tmp_path):
    spec = SweepSpec(
        family="xsec", decide_fn=_dummy_decide, base_params={},
        grid={"k": [3]}, universes={"inline": ["AAA", "BBB"]})
    cells = enumerate_cells(spec)
    assert cells[0][2] == ["AAA", "BBB"]
    # JSON-file universe
    f = tmp_path / "basket.json"
    f.write_text(json.dumps(["XLK", "XLF", "XLE"]))
    spec2 = SweepSpec(
        family="xsec", decide_fn=_dummy_decide, base_params={},
        grid={"k": [3]}, universes={"file": str(f)})
    cells2 = enumerate_cells(spec2)
    assert cells2[0][2] == ["XLK", "XLF", "XLE"]


# ===========================================================================
# 2. Canonical FP-cont Sharpe vs a HAND-COMPUTED series
# ===========================================================================

def test_fp_sharpe_against_hand_computed_series():
    # Build an equity curve EXACTLY from the target tick returns (multiplicative
    # compounding) so the recovered series is bit-for-bit the hand series.
    expected_rets = [0.01, -0.005, 0.02, 0.0, -0.01]
    ec = [100.0]
    for r in expected_rets:
        ec.append(ec[-1] * (1.0 + r))
    got = equity_curve_returns(ec)
    assert got == pytest.approx(expected_rets, abs=1e-12)
    # Hand-computed annualized Sharpe (sqrt 252).
    m = statistics.mean(expected_rets)
    sd = statistics.stdev(expected_rets)
    hand = (m / sd) * math.sqrt(252.0)
    sharpe, n = fp_continuous_sharpe([_win(ec)], timeframe="1Day", is_crypto=False)
    assert n == 5
    assert sharpe == pytest.approx(hand, rel=1e-9)
    assert sharpe == pytest.approx(3.95491837, abs=1e-6)


def test_fp_sharpe_concatenates_windows_not_bridging_seam():
    # Two windows; concatenated series = both windows' internal returns, no
    # synthetic seam return between win1's last tick and win2's first.
    w1 = _win([100.0, 101.0, 102.0])          # rets: +0.01, +0.00990...
    w2 = _win([200.0, 198.0, 202.0])          # rets: -0.01, +0.020202...
    rets = concat_window_returns([w1, w2])
    assert len(rets) == 4   # 2 + 2, NOT 5 (no bridge)
    assert rets[0] == pytest.approx(0.01)
    assert rets[2] == pytest.approx(-0.01)


def test_fp_sharpe_crypto_uses_365():
    expected_rets = [0.01, -0.005, 0.02, 0.0, -0.01]
    ec = [100.0]
    for r in expected_rets:
        ec.append(ec[-1] * (1.0 + r))
    eq_s, _ = fp_continuous_sharpe([_win(ec)], is_crypto=False)
    cr_s, _ = fp_continuous_sharpe([_win(ec)], is_crypto=True)
    # crypto annualization is sqrt(365/252) larger.
    assert cr_s / eq_s == pytest.approx(math.sqrt(365.0 / 252.0), rel=1e-9)


def test_fp_sharpe_degenerate_series_returns_zero():
    assert sharpe_from_returns([], 252.0) == 0.0
    assert sharpe_from_returns([0.01], 252.0) == 0.0
    assert sharpe_from_returns([0.01, 0.01, 0.01], 252.0) == 0.0  # zero variance
    s, n = fp_continuous_sharpe([_win([100.0])], is_crypto=False)
    assert (s, n) == (0.0, 0)


def test_fp_sharpe_skips_nonpositive_prior_equity():
    # A blown-up curve hitting 0 must not divide-by-zero.
    rets = equity_curve_returns([100.0, 0.0, 50.0, 60.0])
    # i=1: prev=100 -> (0-100)/100=-1.0 ; i=2: prev=0 -> skipped ;
    # i=3: prev=50 -> 0.2
    assert rets == pytest.approx([-1.0, 0.2])


def test_basket_is_crypto_rule():
    assert basket_is_crypto(["BTC/USD", "ETH/USD"]) is True
    assert basket_is_crypto(["BTC/USD", "AAPL"]) is False
    assert basket_is_crypto([]) is False


# ===========================================================================
# 3. Robustness classifier — KNIFE-EDGE vs PLATEAU
# ===========================================================================

def _cell(cid, params, passes, universe=None):
    c = CellResult(cell_id=cid, params=dict(params), universe_name=universe,
                   universe=[])
    c.front_door_pass = passes
    return c


def test_robustness_isolated_pass_is_knife_edge():
    # 3x3 grid; only the center (k=5,cad=2) passes, all 8 neighbors fail.
    grid = {"k": [3, 5, 7], "cad": [1, 2, 3]}
    cells = []
    cid = 0
    for k in grid["k"]:
        for cad in grid["cad"]:
            passes = (k == 5 and cad == 2)
            cells.append(_cell(cid, {"k": k, "cad": cad}, passes))
            cid += 1
    classify_robustness(cells, grid)
    center = next(c for c in cells if c.params == {"k": 5, "cad": 2})
    assert center.front_door_pass is True
    assert center.robustness == "KNIFE_EDGE"
    # non-passing cells stay blank
    assert all(c.robustness == "" for c in cells if not c.front_door_pass)


def test_robustness_contiguous_region_is_plateau():
    # 3x3 grid; a 2x2 contiguous passing block in the corner.
    grid = {"k": [3, 5, 7], "cad": [1, 2, 3]}
    passing = {(3, 1), (3, 2), (5, 1), (5, 2)}
    cells = []
    cid = 0
    for k in grid["k"]:
        for cad in grid["cad"]:
            cells.append(_cell(cid, {"k": k, "cad": cad}, (k, cad) in passing))
            cid += 1
    classify_robustness(cells, grid)
    for k, cad in passing:
        c = next(x for x in cells if x.params == {"k": k, "cad": cad})
        assert c.robustness == "PLATEAU", f"{(k,cad)} should be plateau"


def test_robustness_two_adjacent_passes_are_plateau():
    # Minimal plateau: two horizontally-adjacent passing cells support each
    # other (each is the other's +-1 neighbor).
    grid = {"k": [3, 5, 7], "cad": [1, 2, 3]}
    passing = {(5, 1), (5, 2)}
    cells = []
    cid = 0
    for k in grid["k"]:
        for cad in grid["cad"]:
            cells.append(_cell(cid, {"k": k, "cad": cad}, (k, cad) in passing))
            cid += 1
    classify_robustness(cells, grid)
    for k, cad in passing:
        c = next(x for x in cells if x.params == {"k": k, "cad": cad})
        assert c.robustness == "PLATEAU"


def test_robustness_diagonal_passes_are_knife_edges():
    # Two diagonal passing cells are NOT +-1 neighbors (diff on TWO axes),
    # so each is isolated -> both knife-edges.
    grid = {"k": [3, 5, 7], "cad": [1, 2, 3]}
    passing = {(3, 1), (5, 2)}   # diagonal
    cells = []
    cid = 0
    for k in grid["k"]:
        for cad in grid["cad"]:
            cells.append(_cell(cid, {"k": k, "cad": cad}, (k, cad) in passing))
            cid += 1
    classify_robustness(cells, grid)
    for k, cad in passing:
        c = next(x for x in cells if x.params == {"k": k, "cad": cad})
        assert c.robustness == "KNIFE_EDGE"


def test_robustness_isolates_per_universe():
    # Same param cell passes in two universes but they must NOT be treated as
    # neighbors of each other (different universe). Each is a lone pass.
    grid = {"k": [3, 5, 7]}
    cells = [
        _cell(0, {"k": 5}, True, universe="u1"),
        _cell(1, {"k": 3}, False, universe="u1"),
        _cell(2, {"k": 7}, False, universe="u1"),
        _cell(3, {"k": 5}, True, universe="u2"),
        _cell(4, {"k": 3}, False, universe="u2"),
        _cell(5, {"k": 7}, False, universe="u2"),
    ]
    classify_robustness(cells, grid)
    assert cells[0].robustness == "KNIFE_EDGE"
    assert cells[3].robustness == "KNIFE_EDGE"


def test_robustness_single_cell_grid_pass_is_knife_edge():
    # Degenerate empty/single grid: a lone off-grid pass has no neighbors.
    cells = [_cell(0, {}, True)]
    classify_robustness(cells, {})
    assert cells[0].robustness == "KNIFE_EDGE"


# ===========================================================================
# 4. Deployed-ann-return + cost-active guard
# ===========================================================================

def test_deployed_ann_return_basic():
    # +$100 pnl on $1000 deployed over 252 days (1 yr) -> +10%/yr.
    agg = type("A", (), {"windows": [_win([1000.0, 1100.0], pnl=100.0, days=252)]})()
    ann = deployed_ann_return_pct(agg, 1000.0)
    assert ann == pytest.approx(10.0, abs=1e-6)


def test_cost_active_guard_rejects_zero_cost():
    zero = CostModel(spread_bps=0.0, fee_bps=0.0)
    with pytest.raises(AssertionError, match="zero-cost"):
        _assert_cost_active(zero)


def test_cost_active_guard_accepts_real_cost():
    _assert_cost_active(CostModel.alpaca_stocks())  # no raise


def test_run_sweep_rejects_zero_cost_model():
    spec = SweepSpec(
        family="single", decide_fn=_dummy_decide, base_params={"symbol": "SPY"},
        grid={"a": [1]}, cost_model=CostModel(spread_bps=0.0, fee_bps=0.0))
    with pytest.raises(AssertionError, match="zero-cost"):
        run_sweep(spec)


# ===========================================================================
# 5. VALIDATION / regression anchor — reproduce the known momentum reject
# ===========================================================================

def _load_momentum_candidate():
    cdir = WS / "strategies_candidates" / "xsec_ss_momentum_lc20_v2"
    if not (cdir / "strategy.py").exists():
        pytest.skip("xsec_ss_momentum_lc20_v2 candidate not present")
    spec = importlib.util.spec_from_file_location(
        "cand_mom_v2_sweep", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


MOM_UNIVERSE = ["AAPL", "MSFT", "JNJ", "XOM", "JPM", "PG", "KO", "WMT", "CVX",
                "HD", "MRK", "PEP", "CSCO", "VZ", "DIS", "MCD", "NKE", "UNH",
                "BA", "CAT"]


@pytest.mark.slow
def test_validation_reproduces_known_momentum_reject():
    """Regression anchor: the harness must agree with the hand-run momentum
    reject documented in reports/SS_MOMENTUM_MONTHLY_*.md.

    Known result (corrected ruler): every lookback x cadence x K cell lands
    FP-cont Sharpe in [-0.13, +0.21] — an order of magnitude under 1.0 — and
    EVERY cell REJECTS at the front door. The basin is uniformly failing, NOT
    a knife-edge ridge (so there is no spurious PLATEAU to surface).
    """
    decide, base_params = _load_momentum_candidate()
    # Tiny K x cadence grid (the canonical 12-1 monthly cell is included).
    spec = SweepSpec(
        family="xsec", decide_fn=decide, base_params=base_params,
        grid={"rebalance_months": [1, 3], "top_k": [3, 5]},
        universes={"lc20": MOM_UNIVERSE},
        strategy_label="xsec_ss_momentum_lc20_v2",
        warmup_days=420)
    report = run_sweep(spec)

    assert report.n_cells == 4
    assert report.n_error == 0
    # Every cell rejects (the hand-run conclusion).
    assert report.n_pass == 0, "harness must reproduce the all-REJECT result"
    # No spurious plateau — there is nothing robust to surface.
    assert report.n_plateau == 0

    # FP-cont Sharpe band check (matches the doc: -0.13..+0.21, well under 1.0).
    fps = [c.fp_cont_sharpe for c in report.cells]
    assert max(fps) < 0.5, f"no cell should approach 1.0; got max {max(fps):.2f}"
    assert max(fps) < 1.0
    # The canonical 12-1 monthly K5 cell (rebalance_months=1, top_k=5,
    # lookback 252 from base params) is the documented -0.11 worst-of-clean.
    canonical = next(
        c for c in report.cells
        if c.params == {"rebalance_months": 1, "top_k": 5})
    assert canonical.fp_cont_sharpe < 0.2
    assert canonical.front_door_pass is False
    assert "a" in canonical.reject_clauses  # FP-cont Sharpe < 1.0
    # Markdown renders without error and reports zero plateaus.
    md = report.to_markdown()
    assert "ROBUST PLATEAUS: none" in md


# ---------------------------------------------------------------------------
# Clause-(a) fold into the front-door verdict (BACKLOG P2 misread-trap fix).
# Before the fix, `front` = fitness AND #1 AND #5b only, so a cell that cleared
# those secondary clauses but had FP-cont Sharpe < 1.0 rendered a bold PASS(a)
# even though clause (a) is THE load-bearing primary gate. These pin that a
# sub-1.0 cell is now a REJECT(a), and that the positive path is unaffected.
# ---------------------------------------------------------------------------

def _metrics(fp, *, fitness=True, a1=True, dd5b=True):
    return {
        "fp_cont_sharpe": fp,
        "fitness_pass": fitness,
        "bar_a1_pass": a1,
        "dd5b_pass": dd5b,
    }


def test_verdict_subthreshold_fp_cont_is_reject_even_if_secondary_clauses_pass():
    # The exact misread-trap: all secondary clauses pass, but FP-cont 0.85 < 1.0.
    front, clauses = _verdict(_metrics(0.85))
    assert front is False                 # was True before the fix (bug)
    assert clauses == ["a"]               # clause (a) is the ONLY failure
    # And it must render as REJECT(a), never PASS(a).
    c = CellResult(cell_id=0, params={}, universe_name="u", universe=[])
    c.fp_cont_sharpe = 0.85
    c.front_door_pass, c.reject_clauses = front, clauses
    verdict = ("PASS" if c.front_door_pass else "REJECT")
    if c.reject_clauses:
        verdict += "(" + ",".join(c.reject_clauses) + ")"
    assert verdict == "REJECT(a)"


def test_verdict_exactly_one_point_zero_passes_clause_a():
    # Boundary: FP-cont == 1.0 satisfies the >= 1.0 gate.
    front, clauses = _verdict(_metrics(1.0))
    assert front is True
    assert clauses == []


def test_verdict_full_pass_when_fp_cont_above_one_and_all_clauses_pass():
    front, clauses = _verdict(_metrics(1.20))
    assert front is True
    assert clauses == []


def test_verdict_subthreshold_fp_cont_stacks_with_other_clause_failures():
    # FP-cont below 1.0 AND a secondary clause also failing -> both recorded,
    # clause (a) listed first (primary), still a REJECT.
    front, clauses = _verdict(_metrics(0.50, fitness=False))
    assert front is False
    assert clauses == ["a", "fitness"]
