"""Guard tests for the LLM-mutation parent pool (GATE_PASSING_PARENTS).

Context: the mutation tournament breeds child strategies from the parents
listed in `runner.tournament_loop.GATE_PASSING_PARENTS`. The pool's documented
contract (see the inline comment at its definition) is: a member must have
PASSED the walk-forward fitness gate AND be eligible as a parent.

These tests pin two invariants that protect the breeding stream:

  1. STRUCTURAL COMPATIBILITY — every pool member must be a single-name
     strategy (`params['symbol']` set) with a working `decide()` that the
     `parent_profile.profile_parent_trades` path can run without crashing.
     The mutation/profile machinery is single-name only; a multi-sleeve /
     `decide_xsec` strategy (e.g. allocator_blend) would break the profiler
     and cannot be a parent. This test would fail loudly if such a strategy
     were ever added to the pool.

  2. FITNESS-GATE MEMBERSHIP — historically every pool member had to clear
     the absolute fitness gate on the 8-window walk-forward. As of
     2026-06-25 this is relaxed for DELIBERATE, EVIDENCE-BACKED de-correlator
     parents: a parent may be gate-FAILING on the equity-calibrated panel if
     (a) it is structurally compatible (single-name, profileable), and
     (b) a recorded parent-diversity eval justifies it as an orthogonal
     archetype that widens the mutation gene pool. This is SAFE because the
     CHILD mutations bred from any parent are still independently held to the
     absolute fitness gate (`passes_mutation_gate` requires the candidate to
     clear `passes_fitness_gate` on its OWN walk-forward, plus stability +
     risk-adjusted guards). A weak parent therefore cannot leak a weak child
     into the book — it only contributes structural genetic diversity to the
     LLM mutation prompt. `trend_follow_gld` (median Sharpe approx -1.21 on
     this panel, but corr +0.019 to the pool) is the canonical such case.
     See reports/PARENT_DIVERSITY_<ts>.md and memory/2026-06-25.md for the
     full include/exclude analysis.

The gate-failing-but-included parents are enumerated in
`DECORRELATOR_EXEMPT_PARENTS` below; every OTHER pool member must still pass
the absolute fitness gate.

Both are real (non-mocked) walk-forward runs over cached daily/intraday bars,
so they are a touch slower than a unit test but well under the suite budget.
They use only already-cached data (no network).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.tournament_loop import GATE_PASSING_PARENTS, _pick_pairs
from runner.strategy_gen import MUTATION_DIRECTIVES
from runner.parent_profile import profile_parent_trades
from runner.backtest import load_strategy_module_and_params
from runner.walk_forward import walk_forward, passes_fitness_gate

# Parents that are DELIBERATELY included in GATE_PASSING_PARENTS despite
# failing the equity-calibrated absolute fitness gate, because a recorded
# parent-diversity eval justified them as orthogonal de-correlator archetypes.
# This is safe: child mutations are still independently gated (see module
# docstring, invariant 2). Adding a name here is an INTENTIONAL act backed by
# a PARENT_DIVERSITY report — not a way to silence a regression.
#   trend_follow_gld: gold-trend archetype, corr +0.019 to the pool
#     (orthogonal to the equity-momentum cluster); profiles clean 8/8
#     windows / 20 trades. Eval 2026-06-25 (opus subagent). Median Sharpe
#     approx -1.21 on the equity panel — that weakness is filtered at the
#     CHILD gate, not by excluding the parent.
DECORRELATOR_EXEMPT_PARENTS = {"trend_follow_gld"}


def test_pool_is_nonempty_and_unique():
    assert len(GATE_PASSING_PARENTS) >= 1
    assert len(GATE_PASSING_PARENTS) == len(set(GATE_PASSING_PARENTS)), (
        "duplicate parent in GATE_PASSING_PARENTS"
    )


@pytest.mark.parametrize("parent", GATE_PASSING_PARENTS)
def test_pool_member_is_single_name_with_decide(parent):
    """Every parent must be single-name (has params['symbol']) with a
    top-level decide(). Multi-sleeve / decide_xsec strategies are NOT
    mutation-compatible and must never enter the pool."""
    module, params = load_strategy_module_and_params(parent)
    sym = params.get("symbol")
    assert sym, (
        f"{parent} has no params['symbol'] — multi-sleeve / decide_xsec "
        f"strategies are not mutation-compatible and must not be parents"
    )
    assert hasattr(module, "decide"), f"{parent} has no top-level decide()"
    assert not hasattr(module, "decide_xsec"), (
        f"{parent} exposes decide_xsec — cross-sectional strategies break the "
        f"single-name mutation/profile path and must not be parents"
    )


@pytest.mark.parametrize("parent", GATE_PASSING_PARENTS)
def test_pool_member_profiles_without_crash(parent):
    """The mutation prompt is grounded by profile_parent_trades(); a pool
    member must produce a usable (available=True) profile with >0 trades."""
    prof = profile_parent_trades(parent)
    assert prof.available, f"{parent} produced no profileable trades"
    assert prof.n_trades > 0, f"{parent} profile has zero trades"


@pytest.mark.parametrize("parent", GATE_PASSING_PARENTS)
def test_pool_member_passes_fitness_gate(parent):
    """The pool's documented contract: every member passes the fitness gate,
    EXCEPT the explicitly enumerated de-correlator exemptions
    (`DECORRELATOR_EXEMPT_PARENTS`). Those are deliberately gate-failing
    orthogonal archetypes whose OUTPUT (child mutations) is still gated; see
    the module docstring, invariant 2, and `test_decorrelator_parents_are_*`.
    """
    if parent in DECORRELATOR_EXEMPT_PARENTS:
        pytest.skip(
            f"{parent} is a deliberate de-correlator exemption (gate-failing "
            f"by design; child mutations are independently gated)"
        )
    agg = walk_forward(parent)
    passed, reason = passes_fitness_gate(agg)
    assert passed, f"{parent} no longer passes the fitness gate: {reason}"


def test_decorrelator_parents_are_gate_failing_but_compatible():
    """Pin the EXEMPTION rationale for de-correlator parents (trend_follow_gld).
    These are deliberately IN the pool despite failing the equity-calibrated
    fitness gate, because:
      (1) they are structurally compatible (single-name + profileable), and
      (2) a recorded parent-diversity eval justified them as orthogonal
          archetypes (corr ~+0.02 to the pool), and
      (3) the CHILD gate (`passes_mutation_gate`) independently enforces the
          absolute fitness bar on every bred candidate, so a weak parent
          cannot leak a weak strategy into the book.

    This test documents that the exemption is grounded in the parent ACTUALLY
    failing the gate (so the exemption is load-bearing, not vacuous) while
    remaining structurally valid as a parent. If gold ever starts PASSING the
    gate on its own, the skip in test_pool_member_passes_fitness_gate becomes
    moot and this test will flag that the exemption is no longer needed.
    """
    assert DECORRELATOR_EXEMPT_PARENTS, "no de-correlator exemptions defined"
    for parent in DECORRELATOR_EXEMPT_PARENTS:
        assert parent in GATE_PASSING_PARENTS, (
            f"{parent} is exempted but not actually in the pool — remove the "
            f"stale exemption"
        )
        # Structural compatibility: must be a profileable single-name parent.
        prof = profile_parent_trades(parent)
        assert prof.available and prof.n_trades > 0, (
            f"{parent} is exempted but does not profile cleanly — a parent must "
            f"still be structurally valid even if gate-failing"
        )
        # The exemption is load-bearing: confirm it really does fail the gate
        # (if it starts passing, the exemption is no longer needed).
        agg = walk_forward(parent)
        passed, _reason = passes_fitness_gate(agg)
        assert not passed, (
            f"{parent} now PASSES the fitness gate — the de-correlator exemption "
            f"is no longer load-bearing; it can be treated as a normal pool "
            f"member and removed from DECORRELATOR_EXEMPT_PARENTS"
        )


def test_pick_pairs_works_on_pool():
    """_pick_pairs must sample only real (parent, directive) tuples from the
    pool, including after any membership change."""
    pairs = _pick_pairs(25, GATE_PASSING_PARENTS, MUTATION_DIRECTIVES, seed=7)
    assert len(pairs) == 25
    for parent, directive in pairs:
        assert parent in GATE_PASSING_PARENTS
        assert directive in MUTATION_DIRECTIVES
