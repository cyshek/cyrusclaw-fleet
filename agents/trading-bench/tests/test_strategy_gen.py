"""Tests for the LLM strategy-generation + safety pipeline.

Focus: the safety layer (code_review) is correct, and the orchestrator
plumbing (tournament_loop) runs end-to-end in dry-run mode without
touching the LLM.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import strategy_gen
from runner import tournament_loop


# ---------------------------------------------------------------------------
# code_review
# ---------------------------------------------------------------------------

GOLD_BREAKOUT_REGIME = (WORKSPACE / "strategies/breakout_xlk_regime/strategy.py").read_text()


class TestCodeReview(unittest.TestCase):

    def test_rejects_os_import(self):
        bad = '''"""Bad: imports os to read filesystem.

This is exactly the kind of code we never want to backtest.
"""
import os
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    return Action("hold", "XLK")
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("os" in v for v in violations),
                        f"expected an 'os' violation, got: {violations}")

    def test_rejects_subprocess_import(self):
        bad = '''"""Bad: imports subprocess. Cannot be backtested safely.

This MUST be caught before the candidate touches disk.
"""
import subprocess
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    return Action("hold", "XLK")
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("subprocess" in v for v in violations))

    def test_rejects_eval_call(self):
        bad = '''"""Bad: uses eval() to evaluate untrusted-ish expressions.

eval is forbidden.
"""
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    x = eval("1 + 1")
    return Action("hold", "XLK")
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("eval" in v for v in violations))

    def test_rejects_missing_decide(self):
        bad = '''"""No decide function defined — should be rejected.

This module has the Action class but no decide(), which is the contract.
"""
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

# Note: no decide() function!
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("decide" in v for v in violations),
                        f"expected a 'decide' violation, got: {violations}")

    def test_rejects_wrong_decide_signature(self):
        bad = '''"""Decide signature is wrong (only 2 args). Must be rejected.

The runner calls decide(market_state, position_state, params).
"""
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

def decide(market_state, params):  # wrong arity
    return Action("hold", "XLK")
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("signature" in v.lower() for v in violations))

    def test_rejects_missing_action(self):
        bad = '''"""No Action class. Decide returns nothing useful.

The runner expects an Action; this should be rejected.
"""

def decide(market_state: dict, position_state: dict, params: dict):
    return None
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("Action" in v for v in violations))

    def test_rejects_while_true(self):
        bad = '''"""While True is forbidden — infinite-loop risk in a tick.

Even if the strategy logic seems benign, while True in a tick handler is
guaranteed to wedge the runner.
"""
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    while True:
        break
    return Action("hold", "XLK")
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("while True" in v for v in violations))

    def test_rejects_missing_docstring(self):
        bad = '''import math
from dataclasses import dataclass

@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: object = None
    reason: str = ""

def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    return Action("hold", "XLK")
'''
        passed, violations = strategy_gen.code_review({"code": bad})
        self.assertFalse(passed)
        self.assertTrue(any("docstring" in v.lower() for v in violations))

    def test_accepts_gold_standard_breakout_regime(self):
        """The currently-passing breakout_xlk_regime/strategy.py must
        pass code_review verbatim. If this fails, the gate is too strict."""
        passed, violations = strategy_gen.code_review({"code": GOLD_BREAKOUT_REGIME})
        self.assertTrue(passed,
                        f"gold-standard regime breakout must pass code_review; "
                        f"violations: {violations}")
        self.assertEqual(violations, [])


# ---------------------------------------------------------------------------
# tournament_loop --dry-run
# ---------------------------------------------------------------------------

class TestTournamentLoopDryRun(unittest.TestCase):

    def setUp(self):
        # Use a temp report dir so we don't pollute the workspace root.
        self.report_dir = WORKSPACE / "tests" / "_tmp_reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        # Track quarantine paths to clean up at tearDown.
        self._cleanup_paths = []

    def tearDown(self):
        # Wipe temp report dir.
        if self.report_dir.exists():
            shutil.rmtree(self.report_dir, ignore_errors=True)
        # Wipe any quarantine dirs created by the dry-run.
        for p in self._cleanup_paths:
            if Path(p).exists():
                shutil.rmtree(p, ignore_errors=True)

    def test_dry_run_produces_report(self):
        """--dry-run should generate a valid report with N candidates,
        all of which are verbatim copies of breakout_xlk_regime (so they
        pass code review). They MAY or may not pass the fitness gate
        (they're identical to the gold standard, but window data depends
        on Alpaca cache state). The important assertions here:

          1. The report file exists.
          2. All N candidates have a non-None verdict.
          3. None crashed at code-review (the dummy is a verbatim copy).
        """
        result = tournament_loop.run_one_round(
            n_candidates=2,
            dry_run=True,
            report_dir=self.report_dir,
            seed=42,
        )
        # Track quarantine paths for cleanup.
        for r in result["results"]:
            if r.get("quarantine_path"):
                self._cleanup_paths.append(r["quarantine_path"])

        self.assertEqual(result["n_candidates"], 2)
        self.assertEqual(len(result["results"]), 2)

        report_path = Path(result["report_path"])
        self.assertTrue(report_path.exists(),
                        f"report file not written: {report_path}")
        body = report_path.read_text()
        self.assertIn("# Tournament Round", body)
        self.assertIn("DRY-RUN", body)
        self.assertIn("Verdict counts", body)

        for r in result["results"]:
            self.assertIsNotNone(r["verdict"])
            # Dummy is verbatim copy → must pass code review.
            self.assertEqual(r["code_review"]["passed"], True,
                             f"dry-run dummy should pass code_review; "
                             f"violations: {r['code_review']['violations']}")
            # Verdict must NOT be REJECT_CODE_REVIEW.
            self.assertNotEqual(r["verdict"], "REJECT_CODE_REVIEW")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Dedup guards (2026-06-08) — clone + inert-mutation rejection
# ---------------------------------------------------------------------------
import statistics  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import List as _List  # noqa: E402

from runner.strategy_gen import (  # noqa: E402
    _normalize_code_for_hash,
    _code_md5,
    _find_code_clone,
    _trade_signature_set,
    _trade_overlap_jaccard,
    DEDUP_TRADE_OVERLAP_MAX,
    DEDUP_MIN_TRADES_FOR_OVERLAP,
)


@dataclass
class _FakeBT:
    closed_trades: _List[dict] = field(default_factory=list)


@dataclass
class _FakeWin:
    label: str
    backtest: _FakeBT


@dataclass
class _FakeAgg:
    strategy: str = "fake"
    windows: _List[_FakeWin] = field(default_factory=list)


def _trade(entry, exit_, hold, qty=1.0):
    return {"entry_price": entry, "exit_price": exit_,
            "holding_bars": hold, "qty": qty, "pnl_usd": 1.0}


def _agg_with_trades(trade_lists_by_window: dict) -> _FakeAgg:
    """trade_lists_by_window: {window_label: [trade_dict, ...]}."""
    wins = [_FakeWin(label=lbl, backtest=_FakeBT(closed_trades=tl))
            for lbl, tl in trade_lists_by_window.items()]
    return _FakeAgg(windows=wins)


class TestCodeCloneHash(unittest.TestCase):
    def test_module_name_stripped_so_renamed_clone_hashes_same(self):
        code_a = ("def decide(a, b, c):\n    # parent__mut_aaaaaa\n"
                  "    return parent__mut_aaaaaa_helper()\n")
        code_b = code_a.replace("parent__mut_aaaaaa", "parent__mut_bbbbbb")
        # Same file modulo the mut-hash name => same normalized md5 when each
        # is normalized against ITS OWN name.
        self.assertEqual(
            _code_md5(code_a, "parent__mut_aaaaaa"),
            _code_md5(code_b, "parent__mut_bbbbbb"),
            "renamed-only clone must hash identically",
        )

    def test_whitespace_only_diff_hashes_same(self):
        # Trailing-whitespace per line + trailing blank lines are normalized
        # away; the two below are the SAME logical file.
        a = "x = 1\ny = 2\n"
        b = "x = 1   \ny = 2\n\n\n"
        self.assertEqual(_code_md5(a), _code_md5(b))

    def test_collapsed_interior_blank_runs_hash_same(self):
        # 2+ consecutive interior blank lines collapse to one => same hash.
        a = "x = 1\n\ny = 2\n"
        b = "x = 1\n\n\n\ny = 2\n"
        self.assertEqual(_code_md5(a), _code_md5(b))

    def test_genuinely_different_code_differs(self):
        a = "x = 1\n"
        b = "x = 2\n"
        self.assertNotEqual(_code_md5(a), _code_md5(b))


class TestFindCodeClone(unittest.TestCase):
    def setUp(self):
        self.root = WORKSPACE / "tests" / "_tmp_candidates"
        self.root.mkdir(parents=True, exist_ok=True)
        self._orig_root = strategy_gen.CANDIDATES_ROOT
        strategy_gen.CANDIDATES_ROOT = self.root

    def tearDown(self):
        strategy_gen.CANDIDATES_ROOT = self._orig_root
        shutil.rmtree(self.root, ignore_errors=True)

    def _plant(self, name: str, code: str):
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "strategy.py").write_text(code)
        (d / "params.json").write_text("{}")

    def test_detects_renamed_clone(self):
        base = ("def decide(a, b, c):\n    return foo__mut_111111()\n")
        self._plant("foo__mut_111111", base)
        cand = {"name": "foo__mut_222222",
                "code": base.replace("foo__mut_111111", "foo__mut_222222")}
        # plant the candidate's own dir too (evaluate writes quarantine first)
        self._plant(cand["name"], cand["code"])
        self.assertEqual(_find_code_clone(cand), "foo__mut_111111")

    def test_no_false_positive_on_distinct(self):
        self._plant("foo__mut_111111", "def decide(a,b,c):\n    return A()\n")
        cand = {"name": "foo__mut_222222",
                "code": "def decide(a,b,c):\n    return TOTALLY_DIFFERENT()\n"}
        self._plant(cand["name"], cand["code"])
        self.assertIsNone(_find_code_clone(cand))

    def test_ignores_own_dir_only(self):
        # Only the candidate's own dir present => no clone.
        code = "def decide(a,b,c):\n    return Z()\n"
        cand = {"name": "solo__mut_333333", "code": code}
        self._plant(cand["name"], code)
        self.assertIsNone(_find_code_clone(cand))


class TestTradeOverlap(unittest.TestCase):
    def test_identical_tape_is_full_overlap(self):
        trades = [_trade(100.0, 101.0, 3), _trade(102.0, 103.5, 5)]
        child = _agg_with_trades({"w1": list(trades)})
        parent = _agg_with_trades({"w1": list(trades)})
        ov, n = _trade_overlap_jaccard(child, parent)
        self.assertEqual(ov, 1.0)
        self.assertEqual(n, 2)

    def test_disjoint_tape_is_zero_overlap(self):
        child = _agg_with_trades({"w1": [_trade(100.0, 101.0, 3)]})
        parent = _agg_with_trades({"w1": [_trade(200.0, 205.0, 9)]})
        ov, n = _trade_overlap_jaccard(child, parent)
        self.assertEqual(ov, 0.0)

    def test_window_label_prevents_cross_regime_collision(self):
        # Same price pattern, different window => NOT counted as same trade.
        t = _trade(100.0, 101.0, 3)
        child = _agg_with_trades({"bull": [t]})
        parent = _agg_with_trades({"bear": [dict(t)]})
        ov, n = _trade_overlap_jaccard(child, parent)
        self.assertEqual(ov, 0.0)
        self.assertEqual(n, 2)

    def test_partial_overlap_fraction(self):
        shared = _trade(100.0, 101.0, 3)
        child = _agg_with_trades({"w1": [shared, _trade(110.0, 111.0, 2)]})
        parent = _agg_with_trades({"w1": [shared, _trade(120.0, 121.0, 4)]})
        ov, n = _trade_overlap_jaccard(child, parent)
        # union = 3 distinct, inter = 1 => 1/3
        self.assertAlmostEqual(ov, 1.0 / 3.0, places=6)
        self.assertEqual(n, 3)

    def test_inert_threshold_semantics(self):
        # 20 identical trades + 1 changed => 20/21 ≈ 0.952 ≥ 0.95 => inert.
        shared = [_trade(100.0 + i, 101.0 + i, 3) for i in range(20)]
        child = _agg_with_trades({"w1": shared + [_trade(500.0, 501.0, 2)]})
        parent = _agg_with_trades({"w1": list(shared)})
        ov, n = _trade_overlap_jaccard(child, parent)
        self.assertGreaterEqual(n, DEDUP_MIN_TRADES_FOR_OVERLAP)
        self.assertGreaterEqual(ov, DEDUP_TRADE_OVERLAP_MAX)


if __name__ == "__main__":
    unittest.main()
