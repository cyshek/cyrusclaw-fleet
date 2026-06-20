"""Walk-forward harness tests.

Run with:
    python3 -m unittest tests.test_walk_forward
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.walk_forward import (  # noqa: E402
    WalkForwardAggregate,
    WindowResult,
    passes_fitness_gate,
    passes_mutation_gate,
    split_rolling_windows,
    FITNESS_MEDIAN_SHARPE,
    FITNESS_PCT_POSITIVE,
    FITNESS_PCT_BEAT_BH,
    MUTATION_MIN_DELTA_PCT,
    MUTATION_MIN_TOTAL_TRADES,
    MUTATION_SHARPE_DELTA_TOL,
    MUTATION_MIN_SHARPE_SIGN_CONSISTENCY,
)
from runner.backtest import BacktestResult  # noqa: E402


def _fake_window(label: str, ret_pct: float, sharpe: float,
                 bh_spy_pct: float = 0.0, n_trades: int = 12) -> WindowResult:
    bt = BacktestResult(strategy="fake")
    bt.total_return_pct = ret_pct / 100
    bt.sharpe = sharpe
    bt.n_trades = n_trades
    bt.n_bars = 100
    beats = bt.total_return_pct > bh_spy_pct / 100
    return WindowResult(label=label, regime="test", end_date="2024-01-01",
                        days=60, backtest=bt,
                        bh_spy_return_pct=bh_spy_pct / 100,
                        beats_bh_spy=beats)


def _agg_from_windows(name: str, windows: list[WindowResult]) -> WalkForwardAggregate:
    """Build a WalkForwardAggregate the same way walk_forward() does, but from
    synthetic per-window results. Mirrors the aggregation code in the harness."""
    import statistics
    agg = WalkForwardAggregate(strategy=name, n_windows=len(windows))
    agg.windows = windows
    agg.n_windows_with_data = len(windows)
    if not windows:
        return agg
    returns_pct = [w.backtest.total_return_pct * 100 for w in windows]
    sharpes = [w.backtest.sharpe for w in windows]
    beats = [w.beats_bh_spy for w in windows]
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
    agg.worst_window_label = windows[worst_idx].label
    agg.best_window_label = windows[best_idx].label
    agg.total_trades = sum(w.backtest.n_trades for w in windows)
    return agg


class TestRollingSplit(unittest.TestCase):
    """split_rolling_windows must be pure, deterministic, and produce
    contiguous-step windows stepping backwards from end_dt."""

    def test_basic_split(self):
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        wins = split_rolling_windows(total_days=180, window_days=60,
                                     step_days=30, end_dt=end)
        # 180-day budget, 60-day windows, 30-day step:
        # offsets 0, 30, 60, 90, 120 — next would need 60d+150d=210d > 180
        self.assertEqual(len(wins), 5)
        labels = [w[0] for w in wins]
        # First window ends at end_dt itself
        self.assertIn("2026-01-01", labels[0])
        # Each step-back must be exactly 30 days
        for i in range(1, len(wins)):
            self.assertEqual((wins[i - 1][1] - wins[i][1]).days, 30)
        # All windows are window_days long
        for _, _, d in wins:
            self.assertEqual(d, 60)

    def test_window_larger_than_total_returns_empty(self):
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(
            split_rolling_windows(total_days=30, window_days=60,
                                  step_days=30, end_dt=end), [])

    def test_zero_or_negative_inputs(self):
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(split_rolling_windows(0, 60, 30, end), [])
        self.assertEqual(split_rolling_windows(180, 0, 30, end), [])
        self.assertEqual(split_rolling_windows(180, 60, 0, end), [])

    def test_deterministic(self):
        """Same inputs must produce identical outputs across calls."""
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        a = split_rolling_windows(180, 60, 30, end)
        b = split_rolling_windows(180, 60, 30, end)
        self.assertEqual(a, b)


class TestFitnessGate(unittest.TestCase):
    """Boundary tests for passes_fitness_gate."""

    def test_too_few_windows(self):
        agg = _agg_from_windows("x", [
            _fake_window("w1", ret_pct=5.0, sharpe=2.0),
            _fake_window("w2", ret_pct=5.0, sharpe=2.0),
        ])
        ok, reason = passes_fitness_gate(agg)
        self.assertFalse(ok)
        self.assertIn("window", reason.lower())

    def test_clearly_passing(self):
        # 4 windows, all positive, all beat BH-SPY, high Sharpe
        wins = [_fake_window(f"w{i}", ret_pct=3.0 + i, sharpe=1.5,
                             bh_spy_pct=1.0) for i in range(4)]
        agg = _agg_from_windows("good", wins)
        ok, reason = passes_fitness_gate(agg)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "passed")

    def test_clearly_failing_all_negative(self):
        wins = [_fake_window(f"w{i}", ret_pct=-2.0, sharpe=-1.0,
                             bh_spy_pct=1.0) for i in range(4)]
        agg = _agg_from_windows("bad", wins)
        ok, reason = passes_fitness_gate(agg)
        self.assertFalse(ok)
        # Should fail on multiple criteria
        self.assertIn("median return", reason)

    def test_boundary_median_zero_fails(self):
        # Median == 0 must FAIL (gate is strict > 0).
        wins = [_fake_window("w1", 1.0, 1.0, bh_spy_pct=0.0),
                _fake_window("w2", -1.0, 1.0, bh_spy_pct=0.0),
                _fake_window("w3", 0.0, 1.0, bh_spy_pct=0.0),
                _fake_window("w4", 0.0, 1.0, bh_spy_pct=0.0)]
        agg = _agg_from_windows("boundary", wins)
        ok, reason = passes_fitness_gate(agg)
        self.assertFalse(ok)
        self.assertIn("median return", reason)

    def test_boundary_pct_positive_just_below(self):
        # 2/5 positive = 40%, below 50% threshold => fail
        wins = [
            _fake_window("w1", 5.0, 1.0, bh_spy_pct=0.0),
            _fake_window("w2", 5.0, 1.0, bh_spy_pct=0.0),
            _fake_window("w3", -2.0, -1.0, bh_spy_pct=0.0),
            _fake_window("w4", -2.0, -1.0, bh_spy_pct=0.0),
            _fake_window("w5", -2.0, -1.0, bh_spy_pct=0.0),
        ]
        agg = _agg_from_windows("boundary", wins)
        # median -2 < 0 fails too, but pct_positive 40% < 50% also fails
        ok, reason = passes_fitness_gate(agg)
        self.assertFalse(ok)
        self.assertIn("positive", reason)

    def test_boundary_pct_positive_just_above(self):
        # 3/5 positive = 60%, above 50% threshold
        wins = [
            _fake_window("w1", 5.0, 1.0, bh_spy_pct=0.0),
            _fake_window("w2", 5.0, 1.0, bh_spy_pct=0.0),
            _fake_window("w3", 5.0, 1.0, bh_spy_pct=0.0),
            _fake_window("w4", -2.0, -1.0, bh_spy_pct=0.0),
            _fake_window("w5", -2.0, -1.0, bh_spy_pct=0.0),
        ]
        agg = _agg_from_windows("ok", wins)
        ok, reason = passes_fitness_gate(agg)
        self.assertTrue(ok, reason)

    def test_boundary_median_sharpe(self):
        # Median sharpe exactly == FITNESS_MEDIAN_SHARPE must FAIL (gate is strict >).
        wins = [
            _fake_window("w1", 3.0, FITNESS_MEDIAN_SHARPE, bh_spy_pct=0.0),
            _fake_window("w2", 3.0, FITNESS_MEDIAN_SHARPE, bh_spy_pct=0.0),
            _fake_window("w3", 3.0, FITNESS_MEDIAN_SHARPE, bh_spy_pct=0.0),
        ]
        agg = _agg_from_windows("border", wins)
        ok, reason = passes_fitness_gate(agg)
        self.assertFalse(ok)
        self.assertIn("Sharpe", reason)

    def test_lucky_one_window_loser_overall(self):
        """Strategy with ONE huge winner and several small losers should fail.
        This is the regime-luck case the gate is designed to catch."""
        wins = [
            _fake_window("lucky", 50.0, 10.0, bh_spy_pct=2.0),  # huge winner
            _fake_window("w2", -3.0, -1.0, bh_spy_pct=2.0),
            _fake_window("w3", -2.0, -0.8, bh_spy_pct=2.0),
            _fake_window("w4", -1.0, -0.5, bh_spy_pct=2.0),
            _fake_window("w5", -2.0, -1.0, bh_spy_pct=2.0),
        ]
        agg = _agg_from_windows("lucky", wins)
        ok, reason = passes_fitness_gate(agg)
        self.assertFalse(ok, f"lucky single-winner strategy should fail: {reason}")


class TestMutationGate(unittest.TestCase):
    """passes_mutation_gate = absolute fitness gate AND beats parent by delta.

    Calibrated against the round-1 tournament outcome where 3/3 mutants
    were promoted despite only matching their parents' metrics. The gate
    must reject the 'matches parent' case and accept the 'beats parent
    by >= MUTATION_MIN_DELTA_PCT' case.
    """

    def _passing_agg(self, name: str, median_ret_pct: float) -> WalkForwardAggregate:
        """Build a synthetic agg that clearly clears the absolute gate, at the
        requested median return level."""
        # 4 windows, 3 positive at median_ret_pct, 1 small loser; high Sharpe.
        wins = [
            _fake_window("w1", median_ret_pct, 2.0, bh_spy_pct=0.0),
            _fake_window("w2", median_ret_pct, 2.0, bh_spy_pct=0.0),
            _fake_window("w3", median_ret_pct, 2.0, bh_spy_pct=0.0),
            _fake_window("w4", -0.5, -0.2, bh_spy_pct=0.0),
        ]
        return _agg_from_windows(name, wins)

    def test_no_parent_falls_back_to_absolute(self):
        """When parent_agg is None, behave like passes_fitness_gate."""
        agg = self._passing_agg("orphan", 3.0)
        ok, reason = passes_mutation_gate(agg, None)
        self.assertTrue(ok)
        self.assertIn("absolute + stability gate", reason)

    def test_no_parent_still_rejects_bad_absolute(self):
        """No parent + bad absolute = still REJECT."""
        bad_wins = [_fake_window(f"w{i}", -2.0, -1.0, bh_spy_pct=0.0)
                    for i in range(4)]
        agg = _agg_from_windows("bad_orphan", bad_wins)
        ok, reason = passes_mutation_gate(agg, None)
        self.assertFalse(ok)
        # Should be the absolute-gate failure reason, not a mutation-gate one
        self.assertNotIn("parent", reason)

    def test_fails_absolute_gate_short_circuits(self):
        """If absolute gate fails, mutation gate fails with the absolute
        gate's reason, NOT an additional 'beats parent' line on top."""
        parent = self._passing_agg("parent", 1.0)
        bad_wins = [_fake_window(f"w{i}", -2.0, -1.0, bh_spy_pct=0.0)
                    for i in range(4)]
        child = _agg_from_windows("child", bad_wins)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok)
        # Must short-circuit before the parent-delta check, so the parent-
        # comparison phrase 'beats parent' must NOT appear.
        self.assertNotIn("beats parent", reason)

    def test_round1_scenario_matching_parent_rejects(self):
        """The round-1 footgun: child median == parent median should REJECT.
        Without this gate, the round-1 mutations were promoted."""
        parent = self._passing_agg("parent", 2.0)
        child = self._passing_agg("child_matches", 2.0)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok, f"matching-parent child should REJECT: {reason}")
        self.assertIn("beats parent", reason)
        self.assertIn("+0.00pp", reason)

    def test_child_slightly_worse_than_parent_rejects(self):
        """Child clears absolute bar but is worse than parent => REJECT."""
        parent = self._passing_agg("parent", 3.0)
        child = self._passing_agg("child_worse", 2.5)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok)
        self.assertIn("beats parent", reason)

    def test_child_beats_parent_below_delta_rejects(self):
        """Beats parent but by less than MUTATION_MIN_DELTA_PCT => REJECT.
        Round-1 noise scenario: child marginally improves but not meaningfully."""
        parent = self._passing_agg("parent", 2.0)
        # Beat by exactly half the delta threshold
        child = self._passing_agg("child_marginal",
                                  2.0 + MUTATION_MIN_DELTA_PCT / 2)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok, f"sub-delta improvement should REJECT: {reason}")
        self.assertIn("beats parent", reason)

    def test_child_beats_parent_at_delta_boundary_accepts(self):
        """Code uses `delta < min_delta_pct`, so child beating parent by
        EXACTLY MUTATION_MIN_DELTA_PCT clears the gate. (Symmetric with
        `test_child_beats_parent_below_delta_rejects` — anything strictly
        less than the delta is rejected; at-or-above is accepted.)"""
        parent = self._passing_agg("parent", 2.0)
        target = 2.0 + MUTATION_MIN_DELTA_PCT
        wins = [
            _fake_window("w1", target, 2.0, bh_spy_pct=0.0),
            _fake_window("w2", target, 2.0, bh_spy_pct=0.0),
            _fake_window("w3", target, 2.0, bh_spy_pct=0.0),
            _fake_window("w4", -0.5, -0.2, bh_spy_pct=0.0),
        ]
        child = _agg_from_windows("child_exact_delta", wins)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertTrue(ok, f"exactly-at-delta child should ACCEPT: {reason}")
        self.assertIn("beats parent by", reason)

    def test_child_clearly_beats_parent_accepts(self):
        """Child beats parent comfortably above delta => ACCEPT."""
        parent = self._passing_agg("parent", 2.0)
        # Beat parent by 2x the delta threshold (well above the bar)
        child = self._passing_agg("child_better",
                                  2.0 + MUTATION_MIN_DELTA_PCT * 2)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertTrue(ok, f"clearly-better child should ACCEPT: {reason}")
        self.assertIn("beats parent by", reason)

    def test_parent_with_too_few_windows_falls_back_to_absolute(self):
        """If parent baseline is unreliable (too few windows of data), don't
        block the mutation gate — fall back to absolute-only with a note."""
        # Parent has only 2 windows with data
        parent_wins = [_fake_window("w1", 3.0, 2.0, bh_spy_pct=0.0),
                       _fake_window("w2", 3.0, 2.0, bh_spy_pct=0.0)]
        parent = _agg_from_windows("thin_parent", parent_wins)
        # Manually override n_windows_with_data, since _agg_from_windows sets
        # it from len(windows); we explicitly want < 3 to exercise the path.
        parent.n_windows_with_data = 2
        child = self._passing_agg("child", 1.0)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertTrue(ok)
        self.assertIn("absolute + stability gate", reason)


class TestMutationStabilityGuards(unittest.TestCase):
    """The 2026-06-08 risk-adjusted / stability hardening of the mutation gate.

    Each guard must REJECT a candidate that would otherwise clear the old
    absolute-gate + parent-delta-only bar. These pin the guards as ENFORCED
    (the constants existed before this but were dead — never called).
    """

    def _clean_parent(self) -> WalkForwardAggregate:
        # 4 windows, all + with agreeing Sharpe sign, plenty of trades.
        wins = [_fake_window(f"w{i}", 2.0, 2.0, bh_spy_pct=0.0, n_trades=12)
                for i in range(4)]
        return _agg_from_windows("parent", wins)

    def test_too_few_total_trades_rejects(self):
        """Candidate beats parent on return but is sampled on too few trades.
        A 6-trade 'edge' is a coin flip => REJECT on the trade floor."""
        parent = self._clean_parent()
        # Beats parent comfortably on return, agreeing Sharpe signs, BUT only
        # ~2 trades/window => total 8 < MUTATION_MIN_TOTAL_TRADES.
        wins = [_fake_window(f"w{i}", 4.0, 2.0, bh_spy_pct=0.0, n_trades=2)
                for i in range(4)]
        child = _agg_from_windows("child_thin", wins)
        self.assertLess(child.total_trades, MUTATION_MIN_TOTAL_TRADES)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok, f"thin-sample child should REJECT: {reason}")
        self.assertIn("total trades", reason)

    def test_trade_floor_binds_even_with_no_parent(self):
        """The trade floor is a candidate-level guard => binds even orphan."""
        wins = [_fake_window(f"w{i}", 4.0, 2.0, bh_spy_pct=0.0, n_trades=2)
                for i in range(4)]
        child = _agg_from_windows("orphan_thin", wins)
        ok, reason = passes_mutation_gate(child, None)
        self.assertFalse(ok, f"thin orphan should REJECT: {reason}")
        self.assertIn("total trades", reason)

    def test_sharpe_sign_inconsistency_rejects(self):
        """Median Sharpe clears the absolute floor (>0.5) but is NOT
        representative: half the windows are flat/no-trade (Sharpe 0.0, which
        the guard counts as non-agreeing) => only 50% of windows agree with
        the positive median sign < 60% floor => REJECT. This is the 'high
        median propped up by a couple of windows while the rest are inert'
        case the guard exists to catch — and which the absolute median-Sharpe
        floor alone does NOT reject (median 1.0 sails through it)."""
        parent = self._clean_parent()
        # Sharpes 2.0 / 2.0 / 0.0 / 0.0 => median 1.0 (>0.5, clears absolute),
        # returns all healthy & beat parent (return-delta clears), trades ample,
        # yet only 2/4 = 50% of windows have a Sharpe agreeing with the +median.
        wins = [
            _fake_window("w1", 4.0, 2.0, bh_spy_pct=0.0, n_trades=12),
            _fake_window("w2", 4.0, 2.0, bh_spy_pct=0.0, n_trades=12),
            _fake_window("w3", 4.0, 0.0, bh_spy_pct=0.0, n_trades=12),
            _fake_window("w4", 4.0, 0.0, bh_spy_pct=0.0, n_trades=12),
        ]
        child = _agg_from_windows("child_unstable", wins)
        # Sanity: it must clear the absolute fitness gate so we KNOW the
        # rejection comes from the sign-consistency guard, not the abs floor.
        abs_ok, _ = passes_fitness_gate(child)
        self.assertTrue(abs_ok, "fixture must clear the absolute gate first")
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok, f"sign-inconsistent child should REJECT: {reason}")
        self.assertIn("median-Sharpe sign", reason)

    def test_sharpe_risk_adjusted_regression_rejects(self):
        """Candidate beats parent on RAW return but its median Sharpe is much
        WORSE than parent's (leverage/variance, not alpha) => REJECT."""
        # Parent: solid Sharpe ~2.0.
        parent = self._clean_parent()
        # Child: beats parent on return (+4 vs +2) but median Sharpe collapses
        # to ~0.6 (still same positive sign so consistency passes; still > the
        # absolute 0.5 floor) — degradation vs parent 2.0 is -1.4 < tol -0.10.
        wins = [_fake_window(f"w{i}", 4.0, 0.6, bh_spy_pct=0.0, n_trades=12)
                for i in range(4)]
        child = _agg_from_windows("child_leveraged", wins)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertFalse(ok, f"risk-adjusted-regression child should REJECT: {reason}")
        self.assertIn("degrades parent", reason)

    def test_clean_candidate_still_passes_all_guards(self):
        """A genuine improvement — more return, enough trades, consistent &
        non-degrading Sharpe — clears every guard."""
        parent = self._clean_parent()
        wins = [_fake_window(f"w{i}", 3.0, 2.2, bh_spy_pct=0.0, n_trades=12)
                for i in range(4)]
        child = _agg_from_windows("child_real_edge", wins)
        ok, reason = passes_mutation_gate(child, parent)
        self.assertTrue(ok, f"genuine-edge child should PASS: {reason}")
        self.assertIn("beats parent by", reason)


if __name__ == "__main__":
    unittest.main()
