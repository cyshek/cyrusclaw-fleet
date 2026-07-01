"""Pinning tests for the loss-postmortem ENRICHMENTS (regime, cost/edge,
signal-quality) and the generation-prompt postmortem-context injection.

These pin the new behavior added for BACKLOG [V]4 (loss-triggered postmortem
loop made smarter). All tests are pure/temp-DB; never touch tournament.db and
never hit the network (regime helper is tested via its pure inner function).
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.postmortem import (  # noqa: E402
    _cost_edge_breakdown,
    _signal_quality,
    _regime_label_from_metrics,
    BULL, BEAR, CHOP,
)


# ---------------------------------------------------------------------------
# Cost vs edge breakdown
# ---------------------------------------------------------------------------

def test_cost_edge_breakdown_splits_gross_and_drag():
    # gross_pnl = sum of round-trip PnL BEFORE cost is conceptual; here we feed
    # realized (net) pnl + turnover and a cost rate, and the helper reconstructs
    # the implied cost drag and gross.
    stats = {"realized_pnl": -3.0, "turnover": 1000.0, "n_rt": 10}
    out = _cost_edge_breakdown(stats, cost_bps=2.0)
    # cost drag = turnover * 2bps = 1000 * 0.0002 = 0.20
    assert out["cost_drag_usd"] == pytest.approx(0.20, abs=1e-9)
    # gross = net + cost_drag  (net was after costs, so gross is less negative)
    assert out["gross_pnl_usd"] == pytest.approx(-3.0 + 0.20, abs=1e-9)
    # cost fraction of |gross| reported, bounded
    assert out["cost_drag_usd"] >= 0.0


def test_cost_edge_breakdown_flags_cost_dominated():
    # A churn case: tiny negative net but big turnover -> cost dominates the loss.
    stats = {"realized_pnl": -0.50, "turnover": 5000.0, "n_rt": 40}
    out = _cost_edge_breakdown(stats, cost_bps=2.0)
    # cost drag = 5000 * 0.0002 = 1.00, which EXCEEDS the magnitude of the net loss
    assert out["cost_drag_usd"] == pytest.approx(1.00, abs=1e-9)
    assert out["cost_exceeds_net_loss"] is True


def test_cost_edge_breakdown_not_cost_dominated_for_big_directional_loss():
    # Big directional loss, modest turnover -> cost is a small fraction.
    stats = {"realized_pnl": -50.0, "turnover": 1000.0, "n_rt": 8}
    out = _cost_edge_breakdown(stats, cost_bps=2.0)
    assert out["cost_drag_usd"] == pytest.approx(0.20, abs=1e-9)
    assert out["cost_exceeds_net_loss"] is False


# ---------------------------------------------------------------------------
# Signal-quality metrics
# ---------------------------------------------------------------------------

def test_signal_quality_profit_factor_and_ratios():
    pnls = [10.0, 5.0, -4.0, -4.0, -2.0]  # gross win 15, gross loss 10
    out = _signal_quality(pnls)
    assert out["profit_factor"] == pytest.approx(15.0 / 10.0, abs=1e-9)
    assert out["hit_rate"] == pytest.approx(2 / 5, abs=1e-9)
    # avg win 7.5, avg loss -3.333..., ratio 2.25
    assert out["win_loss_ratio"] == pytest.approx(7.5 / (10.0 / 3.0), abs=1e-6)


def test_signal_quality_breakeven_hit_rate():
    # With win/loss ratio R, breakeven hit-rate = 1/(1+R).
    pnls = [9.0, -3.0]  # avg win 9, avg loss 3, R=3 -> breakeven 0.25
    out = _signal_quality(pnls)
    assert out["breakeven_hit_rate"] == pytest.approx(0.25, abs=1e-9)
    # actual hit rate 0.5 > breakeven 0.25 -> edge_vs_breakeven positive
    assert out["hit_rate_minus_breakeven"] == pytest.approx(0.5 - 0.25, abs=1e-9)


def test_signal_quality_all_losses_infinite_factor_guard():
    pnls = [-1.0, -2.0, -3.0]
    out = _signal_quality(pnls)
    # No wins: profit_factor must be 0.0 (guarded, not div-by-zero / inf)
    assert out["profit_factor"] == 0.0
    assert out["hit_rate"] == 0.0
    # breakeven undefined with no wins -> reported as 1.0 (need 100% to break even, impossible)
    assert out["breakeven_hit_rate"] == pytest.approx(1.0, abs=1e-9)


def test_signal_quality_empty():
    out = _signal_quality([])
    assert out["profit_factor"] == 0.0
    assert out["hit_rate"] == 0.0
    assert out["n"] == 0


# ---------------------------------------------------------------------------
# Regime label (pure inner function — no network)
# ---------------------------------------------------------------------------

def test_regime_label_bull():
    # Strong positive window return + price mostly above SMA -> BULL
    assert _regime_label_from_metrics(net_return_pct=8.0, frac_above_sma=0.9) == BULL


def test_regime_label_bear():
    # Negative window return + price mostly below SMA -> BEAR
    assert _regime_label_from_metrics(net_return_pct=-7.0, frac_above_sma=0.1) == BEAR


def test_regime_label_chop():
    # Near-flat return -> CHOP regardless of SMA position
    assert _regime_label_from_metrics(net_return_pct=0.4, frac_above_sma=0.5) == CHOP


def test_regime_label_mismatch_signal_for_bear():
    # A bear regime is exactly the context that makes REGIME_MISMATCH meaningful;
    # pin that BEAR is returned for a clearly-declining window even if frac_above
    # is middling (return sign dominates when magnitude is large).
    assert _regime_label_from_metrics(net_return_pct=-6.0, frac_above_sma=0.45) == BEAR


# ---------------------------------------------------------------------------
# Prompt injection: postmortem_context prefix in _build_llm_prompt
# ---------------------------------------------------------------------------

def test_build_llm_prompt_byte_identical_without_context():
    from runner.strategy_gen import _build_llm_prompt
    base = _build_llm_prompt("breakout_xlk", "add a stop loss", "cand_x")
    with_none = _build_llm_prompt("breakout_xlk", "add a stop loss", "cand_x",
                                  postmortem_context=None)
    assert base == with_none, "no-context path must be byte-identical (md5 enforcement)"


def test_build_llm_prompt_injects_context_prefix():
    from runner.strategy_gen import _build_llm_prompt
    ctx = "PARENT LOSS ANATOMY: regime=BEAR, cost ate 80% of gross edge."
    out = _build_llm_prompt("breakout_xlk", "add a stop loss", "cand_x",
                            postmortem_context=ctx)
    assert ctx in out, "postmortem context must appear in the prompt"
    # And it must appear ONCE (prefix), not duplicated
    assert out.count(ctx) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
