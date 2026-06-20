"""Tests for runner/regime_backtest.py (Tier 2 Bar C Phase-1 evaluator).

Covers the four required invariants:
  1. Stand-in substitution works (deterministic code_fallback injected, no LLM).
  2. Risk-off reduces exposure vs risk-on.
  3. Risk-on == ungated baseline (parity).
  4. Determinism (two identical runs -> identical results).

Plus: lookahead guard, Phase-2 LLM path is blocked, CHOP handling.

Uses synthetic bars + decide_xsec_fn injection so no network / DB is
touched. Mirrors the construction style of tests/test_backtest_xsec.py.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import regime_backtest as rb  # noqa: E402
from runner.backtest_xsec import backtest_xsec  # noqa: E402
from runner.backtest import CostModel  # noqa: E402

# Load the actual candidate decide_xsec via the evaluator's loader.
CANDIDATE = "regime_gated_xsec_momentum_xa_c87bbf"
DECIDE, PARAMS, ROOT = rb.load_candidate(CANDIDATE)


# ---------------------------------------------------------------------------
# Synthetic bar construction
# ---------------------------------------------------------------------------

def _daily_bars(start: datetime, closes: List[float]) -> List[dict]:
    bars = []
    for i, c in enumerate(closes):
        t = (start + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z")
        bars.append({"t": t, "o": c, "h": c * 1.001, "l": c * 0.999,
                     "c": c, "v": 1000})
    return bars


def _trending(start: datetime, n: int, base: float, slope: float) -> List[dict]:
    return _daily_bars(start, [base + slope * i for i in range(n)])


def _make_basket(n: int = 360) -> Dict[str, List[dict]]:
    """6-asset basket where momentum ranking is deterministic and SPY has a
    clear up-then-down shape so the SPY-50 stand-in flips RISK_ON/RISK_OFF.

    Symbols chosen so TLT/GLD (defensive) are sometimes top-ranked, so the
    risk-off defensive-rotation branch is exercised.
    """
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    # SPY: rise for first 2/3, fall for last 1/3 -> stand-in flips to RISK_OFF.
    half = n
    spy_closes = ([100 + 0.3 * i for i in range(int(n * 0.66))]
                  + [100 + 0.3 * int(n * 0.66) - 0.5 * j
                     for j in range(n - int(n * 0.66))])
    spy = _daily_bars(start, spy_closes[:n])
    return {
        "SPY": spy,
        "EFA": _trending(start, n, 50.0, 0.10),
        "TLT": _trending(start, n, 90.0, 0.25),   # strong -> top-ranked often
        "VNQ": _trending(start, n, 80.0, 0.02),
        "DBC": _trending(start, n, 20.0, 0.30),   # strongest momentum
        "GLD": _trending(start, n, 160.0, 0.20),  # defensive + strong
    }


def _run(decide_fn, bars, params) -> object:
    return backtest_xsec("test", bars, params, decide_xsec_fn=decide_fn,
                         default_cost_model=CostModel.alpaca_stocks())


def _total_buy_notional(result) -> float:
    """Sum of cost basis deployed across the run (proxy for exposure)."""
    tot = 0.0
    for ps in result.per_symbol.values():
        # realized + final market value approximates deployed capital path;
        # use n_buys * per-leg is fragile, so use closed-trade qty*entry.
        for tr in ps.closed_trades:
            tot += tr["entry_price"] * tr["qty"]
        tot += ps.final_market_value
    return tot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStandinSubstitution(unittest.TestCase):
    def test_standin_decision_is_deterministic_and_llm_free(self):
        closes_up = [100 + i for i in range(80)]
        closes_down = [100 - i for i in range(80)]
        d_up = rb.standin_decision(closes_up, "2023-01-03", PARAMS)
        d_down = rb.standin_decision(closes_down, "2023-01-03", PARAMS)
        self.assertEqual(d_up["regime"], "RISK_ON")
        self.assertEqual(d_down["regime"], "RISK_OFF")
        self.assertEqual(d_up["source"], "standin")
        # Determinism: same input -> same output.
        self.assertEqual(rb.standin_decision(closes_up, "2023-01-03", PARAMS),
                         rb.standin_decision(closes_up, "2023-01-03", PARAMS))

    def test_injector_injects_decision_into_market_state(self):
        bars = _make_basket()
        seen = {}

        def spy_capture(ms, ps, p):
            reg = ms.get("regime") or {}
            seen["decision"] = reg.get("decision")
            return DECIDE(ms, ps, p)

        inj = rb.make_regime_injector(spy_capture, PARAMS, mode="standin")
        _run(inj, bars, PARAMS)
        # After the run a decision dict must have been injected.
        self.assertIsInstance(seen.get("decision"), dict)
        self.assertIn(seen["decision"]["regime"],
                      ("RISK_ON", "RISK_OFF", "CHOP"))

    def test_phase2_llm_path_is_blocked(self):
        inj = rb.make_regime_injector(DECIDE, PARAMS, mode="llm")
        with self.assertRaises(NotImplementedError):
            inj({"regime": {}, "symbols": {}, "clock_t": "2023-01-03T00:00:00Z"},
                {}, PARAMS)


class TestRiskOffReducesExposure(unittest.TestCase):
    def test_risk_off_deploys_less_than_risk_on(self):
        bars = _make_basket()
        on_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                         force_regime="RISK_ON")
        off_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                          force_regime="RISK_OFF")
        r_on = _run(on_inj, bars, PARAMS)
        r_off = _run(off_inj, bars, PARAMS)
        # Risk-off: K=1 @ 0.5 scale => ~$50/month deployed vs risk-on
        # K=2 @ full => ~$100/month. Final + realized deployed notional
        # must be strictly lower under risk-off.
        self.assertLess(_total_buy_notional(r_off),
                        _total_buy_notional(r_on))

    def test_risk_off_holds_fewer_names(self):
        bars = _make_basket()
        on_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                         force_regime="RISK_ON")
        off_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                          force_regime="RISK_OFF")
        r_on = _run(on_inj, bars, PARAMS)
        r_off = _run(off_inj, bars, PARAMS)
        held_on = sum(1 for ps in r_on.per_symbol.values() if ps.final_qty > 0)
        held_off = sum(1 for ps in r_off.per_symbol.values() if ps.final_qty > 0)
        self.assertLessEqual(held_off, held_on)
        self.assertLessEqual(held_off, int(PARAMS.get("risk_off_top_k", 1)))


class TestRiskOnMatchesBaseline(unittest.TestCase):
    def test_risk_on_equals_ungated_parent(self):
        bars = _make_basket()
        # Gated, forced RISK_ON every tick.
        on_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                         force_regime="RISK_ON")
        r_gated_on = _run(on_inj, bars, PARAMS)
        # Ungated: kill-switch flips gate off -> pure parent.
        ungated_params = dict(PARAMS)
        ungated_params["use_regime_gate"] = False
        off_inj = rb.make_regime_injector(DECIDE, ungated_params, mode="standin")
        r_ungated = _run(off_inj, bars, ungated_params)
        # Same trade counts and (within float tol) same return.
        self.assertEqual(r_gated_on.n_buys, r_ungated.n_buys)
        self.assertEqual(r_gated_on.n_closes, r_ungated.n_closes)
        self.assertAlmostEqual(r_gated_on.total_return_pct,
                               r_ungated.total_return_pct, places=9)

    def test_kill_switch_ignores_injected_risk_off(self):
        """use_regime_gate=False must ignore even a RISK_OFF injection."""
        bars = _make_basket()
        ungated_params = dict(PARAMS)
        ungated_params["use_regime_gate"] = False
        off_inj = rb.make_regime_injector(DECIDE, ungated_params, mode="forced",
                                          force_regime="RISK_OFF")
        r_killswitch = _run(off_inj, bars, ungated_params)
        # Compare to forced RISK_ON with gate on -> identical (gate ignored).
        on_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                         force_regime="RISK_ON")
        r_on = _run(on_inj, bars, PARAMS)
        self.assertEqual(r_killswitch.n_buys, r_on.n_buys)
        self.assertAlmostEqual(r_killswitch.total_return_pct,
                               r_on.total_return_pct, places=9)


class TestDeterminism(unittest.TestCase):
    def test_two_standin_runs_identical(self):
        bars = _make_basket()
        inj1 = rb.make_regime_injector(DECIDE, PARAMS, mode="standin")
        inj2 = rb.make_regime_injector(DECIDE, PARAMS, mode="standin")
        r1 = _run(inj1, bars, PARAMS)
        r2 = _run(inj2, bars, PARAMS)
        self.assertEqual(r1.n_buys, r2.n_buys)
        self.assertEqual(r1.n_closes, r2.n_closes)
        self.assertEqual(r1.equity_curve, r2.equity_curve)
        self.assertAlmostEqual(r1.total_return_pct, r2.total_return_pct,
                               places=12)


class TestLookaheadGuard(unittest.TestCase):
    def test_guard_rejects_non_list(self):
        with self.assertRaises(AssertionError):
            rb._assert_no_lookahead("not-a-list", "2023-01-03")

    def test_guard_allows_none_and_list(self):
        rb._assert_no_lookahead(None, "2023-01-03")        # no raise
        rb._assert_no_lookahead([1.0, 2.0], "2023-01-03")  # no raise


class TestChopHandling(unittest.TestCase):
    def test_chop_as_risk_off_default(self):
        bars = _make_basket()
        chop_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                           force_regime="CHOP")
        on_inj = rb.make_regime_injector(DECIDE, PARAMS, mode="forced",
                                         force_regime="RISK_ON")
        r_chop = _run(chop_inj, bars, PARAMS)
        r_on = _run(on_inj, bars, PARAMS)
        # chop_as_risk_off default True -> CHOP de-risks like RISK_OFF.
        self.assertLess(_total_buy_notional(r_chop),
                        _total_buy_notional(r_on))

    def test_chop_as_risk_on_when_disabled(self):
        bars = _make_basket()
        p = dict(PARAMS)
        p["chop_as_risk_off"] = False
        chop_inj = rb.make_regime_injector(DECIDE, p, mode="forced",
                                           force_regime="CHOP")
        on_inj = rb.make_regime_injector(DECIDE, p, mode="forced",
                                         force_regime="RISK_ON")
        r_chop = _run(chop_inj, bars, p)
        r_on = _run(on_inj, bars, p)
        self.assertEqual(r_chop.n_buys, r_on.n_buys)
        self.assertAlmostEqual(r_chop.total_return_pct,
                               r_on.total_return_pct, places=9)


if __name__ == "__main__":
    unittest.main()
