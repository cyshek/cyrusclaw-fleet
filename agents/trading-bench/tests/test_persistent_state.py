"""Cross-flat persistent state tests.

Covers the strategy_state surface added 2026-05-26:
    - DB helpers (save / load / clear / empty-dict-deletes-row)
    - Backtester exposes market_state["strategy_state"] as a single dict
      that survives across bars AND across the position going flat.
    - Reassignment (strategy does `market_state["strategy_state"] = {}`)
      is captured, not silently lost.

Live runner is integration-tested separately via smoke runs; the unit
tests here are the contract pin that future refactors can't silently
break.

Run with:
    python3 -m unittest tests.test_persistent_state
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import db  # noqa: E402
from runner.backtest import backtest  # noqa: E402


def _bar(t_iso: str, c: float) -> dict:
    return {"t": t_iso, "o": c, "h": c, "l": c, "c": c, "v": 1.0}


def _series(closes: list[float]) -> list[dict]:
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    return [
        _bar((base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), c)
        for i, c in enumerate(closes)
    ]


class TestPersistentStateDB(unittest.TestCase):
    """DB helper contract: save / load / clear / empty-clears."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "test.db"
        db.init_db(self.tmp)

    def test_missing_returns_empty(self):
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp), {})

    def test_save_then_load_roundtrip(self):
        db.save_persistent_state("s", "SYM", {"cooldown_until": 5, "flag": True},
                                 db_path=self.tmp)
        got = db.get_persistent_state("s", "SYM", db_path=self.tmp)
        self.assertEqual(got, {"cooldown_until": 5, "flag": True})

    def test_save_overwrites(self):
        db.save_persistent_state("s", "SYM", {"a": 1}, db_path=self.tmp)
        db.save_persistent_state("s", "SYM", {"b": 2}, db_path=self.tmp)
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp),
                         {"b": 2})

    def test_save_empty_dict_deletes(self):
        db.save_persistent_state("s", "SYM", {"a": 1}, db_path=self.tmp)
        db.save_persistent_state("s", "SYM", {}, db_path=self.tmp)
        # Row gone (empty dict and missing-row both return {})
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp), {})

    def test_save_non_dict_is_noop(self):
        db.save_persistent_state("s", "SYM", {"a": 1}, db_path=self.tmp)
        db.save_persistent_state("s", "SYM", "not a dict", db_path=self.tmp)  # type: ignore[arg-type]
        # Should leave the prior state alone
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp),
                         {"a": 1})

    def test_clear_drops_row(self):
        db.save_persistent_state("s", "SYM", {"a": 1}, db_path=self.tmp)
        db.clear_persistent_state("s", "SYM", db_path=self.tmp)
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp), {})

    def test_per_symbol_isolation(self):
        db.save_persistent_state("s", "AAA", {"v": 1}, db_path=self.tmp)
        db.save_persistent_state("s", "BBB", {"v": 2}, db_path=self.tmp)
        self.assertEqual(db.get_persistent_state("s", "AAA", db_path=self.tmp), {"v": 1})
        self.assertEqual(db.get_persistent_state("s", "BBB", db_path=self.tmp), {"v": 2})

    def test_per_strategy_isolation(self):
        db.save_persistent_state("s1", "SYM", {"v": 1}, db_path=self.tmp)
        db.save_persistent_state("s2", "SYM", {"v": 2}, db_path=self.tmp)
        self.assertEqual(db.get_persistent_state("s1", "SYM", db_path=self.tmp), {"v": 1})
        self.assertEqual(db.get_persistent_state("s2", "SYM", db_path=self.tmp), {"v": 2})

    def test_lifecycle_separate_from_strategy_state(self):
        """strategy_state and strategy_persistent_state must not collide.
        Different rows, different tables — saving to one must not affect
        what the other sees."""
        db.save_strategy_state("s", "SYM", {"in_pos": 1}, db_path=self.tmp)
        db.save_persistent_state("s", "SYM", {"between": 2}, db_path=self.tmp)
        self.assertEqual(db.get_strategy_state("s", "SYM", db_path=self.tmp),
                         {"in_pos": 1})
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp),
                         {"between": 2})
        # Clearing in-position state must NOT touch persistent state.
        db.clear_strategy_state("s", "SYM", db_path=self.tmp)
        self.assertEqual(db.get_strategy_state("s", "SYM", db_path=self.tmp), {})
        self.assertEqual(db.get_persistent_state("s", "SYM", db_path=self.tmp),
                         {"between": 2})


# Tiny ad-hoc Action duck-type so tests don't depend on a specific strategy
# module's Action class.
class _Action:
    def __init__(self, action="hold", symbol=None, notional_usd=0.0,
                 reason=""):
        self.action = action
        self.symbol = symbol
        self.notional_usd = notional_usd
        self.reason = reason


class TestBacktestPersistentState(unittest.TestCase):
    """market_state["strategy_state"] must survive bars AND flat periods
    within a single backtest run."""

    def test_state_present_and_empty_on_first_bar(self):
        observed = []

        def decide(market_state, position_state, params):
            observed.append(dict(market_state.get("strategy_state", {})))
            return _Action()

        bars = _series([100.0, 101.0, 102.0])
        backtest("probe", bars=bars, params={"symbol": "SYM"},
                 decide_fn=decide)
        # First bar sees empty dict (no prior state).
        self.assertEqual(observed[0], {})

    def test_state_survives_across_bars(self):
        """Counter incremented every bar; final tick sees high count."""
        observed_last = {}

        def decide(market_state, position_state, params):
            st = market_state["strategy_state"]
            st["n"] = st.get("n", 0) + 1
            observed_last.clear()
            observed_last.update(st)
            return _Action()

        bars = _series([100.0] * 50)
        backtest("probe", bars=bars, params={"symbol": "SYM"},
                 decide_fn=decide)
        self.assertEqual(observed_last["n"], 50)

    def test_state_survives_position_going_flat(self):
        """Open a position, close it — state set BEFORE the position
        must still be visible AFTER it closes, AND remain visible on
        subsequent flat bars. This is the post-loss-cooldown use case."""
        events = []  # list of (bar_idx_at_decide, state_snapshot)

        def decide(market_state, position_state, params):
            st = market_state["strategy_state"]
            i = st.get("bar_idx", 0)
            st["bar_idx"] = i + 1
            events.append((i, dict(st)))
            symbol = market_state["symbol"]
            in_pos = bool(position_state.get(symbol))
            # Open at bar 1, close at bar 5 (round trip 1)
            # Then open at bar 10, close at bar 15 (round trip 2)
            if i == 1 and not in_pos:
                return _Action("buy", symbol=symbol, notional_usd=100.0)
            if i == 5 and in_pos:
                return _Action("close", symbol=symbol)
            if i == 10 and not in_pos:
                # Tag state on a known-flat bar after a round trip.
                # If state were wiped on flat, bar_idx wouldn't have
                # survived monotonically from i==5 to here.
                st["saw_flat_after_rt1"] = True
                return _Action("buy", symbol=symbol, notional_usd=100.0)
            if i == 15 and in_pos:
                return _Action("close", symbol=symbol)
            return _Action()

        bars = _series([100.0 + i for i in range(20)])
        backtest("probe", bars=bars, params={"symbol": "SYM"},
                 decide_fn=decide)
        # Counter never reset: all 20 ticks saw monotonically increasing idx.
        idxs = [e[0] for e in events]
        self.assertEqual(idxs, list(range(20)),
                         "bar_idx counter should never reset across position "
                         "open/close")
        # The flat-period marker set at bar 10 should still be visible at
        # bar 19 — proves state survived the second round trip too.
        last_state = events[-1][1]
        self.assertTrue(last_state.get("saw_flat_after_rt1"),
                        f"saw_flat_after_rt1 should persist; got {last_state}")
        # bar_idx is captured AFTER increment, so the final observation
        # at i=19 shows bar_idx==20.
        self.assertEqual(last_state["bar_idx"], 20)

    def test_state_reassignment_captured(self):
        """Strategy reassigning market_state["strategy_state"] = {} must
        be visible to the NEXT bar via market_state["strategy_state"]
        (i.e. the runner re-reads the dict after decide; reassignment
        isn't silently lost). Mirrors live-runner behavior where the
        post-decide save reads market_state["strategy_state"] freshly."""
        bars_seen = []  # state observed at START of each bar

        def decide(market_state, position_state, params):
            bars_seen.append(dict(market_state["strategy_state"]))
            st = market_state["strategy_state"]
            n = st.get("n", 0)
            if n < 3:
                st["n"] = n + 1
            elif n == 3:
                # Wipe via reassignment, not mutation.
                market_state["strategy_state"] = {}
            return _Action()

        bars = _series([100.0] * 6)
        backtest("probe", bars=bars, params={"symbol": "SYM"},
                 decide_fn=decide)
        # Sequence of state-at-start-of-bar should be:
        #   bar 0: {} (fresh)
        #   bar 1: {n: 1}
        #   bar 2: {n: 2}
        #   bar 3: {n: 3}  -> strategy reassigns to {}
        #   bar 4: {}      <-- THIS is the contract assertion: the
        #                      reassignment from bar 3 was captured.
        #   bar 5: {n: 1}
        self.assertEqual(bars_seen[0], {})
        self.assertEqual(bars_seen[3], {"n": 3})
        self.assertEqual(bars_seen[4], {},
                         "bar 4 must see the {} that bar 3 reassigned — if "
                         "reassignment isn't captured, this sees {'n': 3}")

    def test_state_isolated_per_backtest_run(self):
        """Each backtest() call starts with empty state. Two sequential
        backtests must not share state — critical for walk-forward
        windows to be independent."""
        def decide_writes(market_state, position_state, params):
            market_state["strategy_state"]["touched"] = True
            return _Action()

        bars = _series([100.0, 101.0])
        backtest("probe", bars=bars, params={"symbol": "SYM"},
                 decide_fn=decide_writes)

        observed_first = {}

        def decide_observes(market_state, position_state, params):
            if not observed_first:
                observed_first.update(market_state["strategy_state"])
            return _Action()

        backtest("probe", bars=bars, params={"symbol": "SYM"},
                 decide_fn=decide_observes)
        # Second run's FIRST observation must NOT see prior run's state.
        self.assertNotIn("touched", observed_first)


if __name__ == "__main__":
    unittest.main()
