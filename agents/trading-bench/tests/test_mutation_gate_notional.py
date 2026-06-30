"""Regression test for the mutation-gate notional-asymmetry bug (2026-06-29).

BUG: `evaluate()` ran the candidate's walk-forward at the candidate's
declared `notional_usd` (e.g. 1000) but compared its median *return %*
against a parent baseline run at the parent's on-disk notional (e.g. 100).
In this engine `total_return_pct` = dollars-pnl / starting_equity and pnl
scales LINEARLY with notional, so the candidate's return % was inflated by
exactly notional_cand / notional_parent. That corrupted the
`MUTATION_MIN_DELTA_PCT` median-return check and manufactured a FALSE
PROMOTE for breakout_xlk__mut_232050.

FIX: `_parent_wf_cached(parent, notional_usd)` re-runs the parent baseline at
the candidate's notional so the return-% delta is apples-to-apples, and
caches per (parent, notional) so distinct-notional candidates don't collide.

These tests are hermetic: they monkeypatch the lazy-imported `walk_forward`
and `load_strategy_module_and_params` symbols so no network bars are needed.
They assert the two behaviours the fix guarantees:
  1. distinct notionals -> distinct cached baselines, each run at the
     requested notional;
  2. the parent params handed to walk_forward carry the candidate's notional.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import strategy_gen


class _FakeAgg:
    def __init__(self, name, notional):
        self.strategy = name
        self.notional = notional
        self.median_return_pct = 0.0


def _install_fakes(monkeypatch, calls):
    """Patch the symbols `_parent_wf_cached` lazily imports from walk_forward.

    `_parent_wf_cached` does `from .walk_forward import walk_forward,
    load_strategy_module_and_params` at call time, so patching the attributes
    on the walk_forward module is what the function actually resolves.
    """
    import runner.walk_forward as wf

    def _fake_walk_forward(name, params=None, decide_fn=None):
        notional = params.get("notional_usd") if params is not None else None
        calls.append(("wf", name, notional))
        return _FakeAgg(name, notional)

    def _fake_loader(name):
        # Parent's on-disk notional is 100; the fix must override it.
        mod = types.SimpleNamespace(decide=lambda *a, **k: None)
        return (mod, {"notional_usd": 100.0, "symbol": "SPY"})

    monkeypatch.setattr(wf, "walk_forward", _fake_walk_forward, raising=True)
    monkeypatch.setattr(wf, "load_strategy_module_and_params", _fake_loader, raising=True)


def test_parent_cache_keys_on_notional(monkeypatch):
    """Distinct candidate notionals must produce distinct parent baselines."""
    calls = []
    _install_fakes(monkeypatch, calls)
    strategy_gen._PARENT_WF_CACHE.clear()

    a100 = strategy_gen._parent_wf_cached("fake_parent", 100.0)
    a1000 = strategy_gen._parent_wf_cached("fake_parent", 1000.0)
    a100_again = strategy_gen._parent_wf_cached("fake_parent", 100.0)

    # Each distinct notional ran the parent at THAT notional (the fix).
    assert a100.notional == 100.0
    assert a1000.notional == 1000.0
    # Same (parent, notional) is served from cache — no re-run.
    assert a100_again is a100
    # walk_forward invoked once per distinct notional, not 3x.
    wf_calls = [c for c in calls if c[0] == "wf"]
    assert wf_calls == [("wf", "fake_parent", 100.0), ("wf", "fake_parent", 1000.0)], (
        f"expected one parent run per distinct notional, got {wf_calls}"
    )
    strategy_gen._PARENT_WF_CACHE.clear()


def test_candidate_notional_overrides_parent_on_disk(monkeypatch):
    """The parent's on-disk notional (100) must be overridden to the
    candidate's (1000) — this is the apples-to-apples fix itself."""
    calls = []
    _install_fakes(monkeypatch, calls)
    strategy_gen._PARENT_WF_CACHE.clear()

    strategy_gen._parent_wf_cached("fake_parent", 1000.0)
    wf_calls = [c for c in calls if c[0] == "wf"]
    assert wf_calls == [("wf", "fake_parent", 1000.0)], (
        "parent baseline must be re-run at the candidate's notional (1000), "
        f"not its on-disk 100; got {wf_calls}"
    )
    strategy_gen._PARENT_WF_CACHE.clear()


def test_none_notional_uses_default_path(monkeypatch):
    """Backward-compat: notional_usd=None keeps the original no-override path
    (calls walk_forward(parent_name) with no params override)."""
    calls = []

    import runner.walk_forward as wf

    def _fake_walk_forward(name, params=None, decide_fn=None):
        calls.append(("wf", name, params))
        return _FakeAgg(name, None)

    monkeypatch.setattr(wf, "walk_forward", _fake_walk_forward, raising=True)
    strategy_gen._PARENT_WF_CACHE.clear()

    strategy_gen._parent_wf_cached("fake_parent", None)
    # params is None on the default path (uses on-disk params inside walk_forward).
    assert calls == [("wf", "fake_parent", None)], (
        f"None-notional path must call walk_forward(name) with no params; got {calls}"
    )
    strategy_gen._PARENT_WF_CACHE.clear()
