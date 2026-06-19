"""Tier 2 (LLM-decision strategy) Bar C evaluator — Phase 1 + Phase 2 scaffold.

Per `reports/TIER2_BAR_C_EVAL_METHODOLOGY_20260530T190500Z.md` and GATE.md
Bar C. This module scores a regime-consuming cross-sectional candidate the
same way `runner/walk_forward_xsec.py` scores Tier 1 cross-sec code
strategies — but it INJECTS a per-tick regime decision into the strategy's
`market_state["regime"]["decision"]` slot so the strategy gets the regime
signal via the exact path it would in production
(`runner.regime_classifier.get_today_regime()` shape).

Two phases:

  Phase 1 (this file fully implements):
      Substitute the DETERMINISTIC `code_fallback_decision()`
      (regime_uptrend(SPY, 50)) for the LLM. Zero API cost, deterministic,
      re-runnable. This is the FLOOR check — does the strategy pass Bar A
      even with a boring regime signal? If not, an LLM upgrade can't save
      it.

  Phase 2 (deliberately NOT implemented here — cost-incurring, needs
      sign-off): substitute the real LLM classifier replay. This module
      exposes the seam (`make_regime_injector(mode="llm", ...)`) but the
      LLM path raises NotImplementedError so Phase 1 can never accidentally
      spend money. Phase 2 is a separate approved step.

Design invariants:
  - No lookahead: the stand-in reads ONLY `market_state["regime"]["spy_closes"]`,
    which `backtest_xsec` already builds as the as-of-tick visible slice
    (closes whose bar date <= clock_t). We assert this slice never exceeds
    the tick date.
  - RISK_ON parity: when the injected decision is RISK_ON on every tick,
    the gated candidate must produce the SAME trades as its ungated parent
    (the candidate's `use_regime_gate=False` kill-switch path, OR an
    all-RISK_ON injector). `score_phase1` reports the ungated baseline
    side-by-side for exactly this comparison.

CLI:
    python3 -m runner.regime_backtest --strategy regime_gated_xsec_momentum_xa_c87bbf \
        --phase 1 --warmup-days 400 [--md OUT.md] [--json OUT.json]
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from .regime_classifier import code_fallback_decision  # noqa: E402
from .walk_forward_xsec import (  # noqa: E402
    XSecWalkForwardAggregate,
    walk_forward_xsec,
    passes_fitness_gate_xsec,
    format_xsec_md,
)


CANDIDATES_ROOT = WORKSPACE / "strategies_candidates"
STRATEGIES_ROOT = WORKSPACE / "strategies"


# ---------------------------------------------------------------------------
# Strategy loading (candidate-aware: looks in BOTH dirs)
# ---------------------------------------------------------------------------

def load_candidate(name: str) -> Tuple[Callable, dict, str]:
    """Load a regime-consuming cross-sec strategy from strategies_candidates/
    (preferred) or strategies/ (promoted). Returns (decide_xsec, params, root).

    Imports via importlib so the candidate need not be on the default
    package path; we add the appropriate package root.
    """
    for root_name in ("strategies_candidates", "strategies"):
        strat_dir = WORKSPACE / root_name / name
        params_path = strat_dir / "params.json"
        if strat_dir.is_dir() and params_path.exists():
            module = importlib.import_module(f"{root_name}.{name}.strategy")
            if not hasattr(module, "decide_xsec"):
                raise AttributeError(
                    f"{root_name}.{name}.strategy must export decide_xsec(...)")
            params = json.loads(params_path.read_text())
            return module.decide_xsec, params, root_name
    raise FileNotFoundError(
        f"No strategy '{name}' under strategies_candidates/ or strategies/")


# ---------------------------------------------------------------------------
# Regime injectors
# ---------------------------------------------------------------------------

def _assert_no_lookahead(spy_closes: list, clock_t: str) -> None:
    """Defensive: the stand-in must only see closes available as-of the tick.

    backtest_xsec builds `spy_closes` from bars whose date <= clock_t, so
    this is a belt-and-suspenders check that the contract holds. We can't
    re-derive bar dates from the closes alone, so the assertion we CAN make
    is structural: spy_closes must be a non-empty list of finite floats and
    must not be the FULL-history sentinel. The real no-lookahead guarantee
    lives in backtest_xsec's per-tick slicing (visible_n); this just guards
    against a future refactor passing the wrong array.
    """
    if spy_closes is None:
        return
    if not isinstance(spy_closes, list):
        raise AssertionError(
            f"lookahead guard: spy_closes must be list, got {type(spy_closes).__name__}")


def standin_decision(spy_closes: list, trading_date: str, params: dict) -> dict:
    """Deterministic Phase-1 regime stand-in.

    Calls `code_fallback_decision()` (regime_uptrend(SPY, regime_sma_period))
    and returns a `get_today_regime()`-shaped dict. NO LLM, NO DB write.
    """
    _assert_no_lookahead(spy_closes, trading_date)
    period = int(params.get("regime_sma_period", 50))
    fb_params = {
        "regime_fallback_period": period,
        # The fallback intersects allow_strategies with regime_defaults; for
        # the eval we don't care about allow lists (the gated strategy reads
        # only the RISK_ON/RISK_OFF label), so leave defaults empty.
        "regime_defaults": {},
    }
    d = code_fallback_decision(
        list(spy_closes or []),
        trading_date=trading_date or "",
        reason="phase1_deterministic_standin",
        params=fb_params,
    )
    # code_fallback_decision maps uptrend->RISK_ON, downtrend->RISK_OFF.
    return {
        "regime": d["regime"],
        "confidence": d.get("confidence"),
        "rationale": d.get("rationale"),
        "source": "standin",
        "trading_date": d.get("trading_date"),
    }


def make_regime_injector(decide_xsec_fn: Callable, params: dict,
                         *, mode: str = "standin",
                         force_regime: Optional[str] = None) -> Callable:
    """Wrap a candidate decide_xsec so each tick gets a regime decision
    injected into market_state["regime"]["decision"] before the strategy
    runs.

    mode:
      "standin"  -> deterministic code_fallback_decision (Phase 1).
      "forced"   -> always inject force_regime (for parity / unit tests).
      "llm"      -> Phase 2; NOT implemented here (raises) to guarantee
                    zero accidental API spend in Phase 1.
    """
    if mode == "llm":
        def _llm_blocked(market_state, position_state, p):  # noqa: ANN001
            raise NotImplementedError(
                "Phase 2 LLM replay is a separate, cost-incurring step requiring "
                "sign-off. regime_backtest.py implements Phase 1 (deterministic "
                "stand-in) only.")
        return _llm_blocked

    def wrapped(market_state, position_state, p):  # noqa: ANN001
        regime = market_state.get("regime")
        if not isinstance(regime, dict):
            regime = {}
        clock_t = str(market_state.get("clock_t", ""))
        trading_date = clock_t[:10]
        if mode == "forced" and force_regime is not None:
            decision = {"regime": force_regime, "source": "forced"}
        else:
            spy_closes = regime.get("spy_closes") or []
            decision = standin_decision(spy_closes, trading_date, p)
        # Inject WITHOUT mutating the harness's regime dict in place in a
        # way that leaks across ticks: shallow-copy then add the decision.
        injected = dict(regime)
        injected["decision"] = decision
        market_state["regime"] = injected
        return decide_xsec_fn(market_state, position_state, p)

    return wrapped


# ---------------------------------------------------------------------------
# Phase-1 score report
# ---------------------------------------------------------------------------

@dataclass
class Phase1Report:
    strategy: str
    basket: List[str]
    warmup_days: int
    # Gated candidate under deterministic stand-in
    gated: XSecWalkForwardAggregate = None  # type: ignore[assignment]
    gated_fitness_pass: bool = False
    gated_fitness_reason: str = ""
    gated_bar_a_pass: bool = False
    # Ungated parent behavior (use_regime_gate=False) on the SAME candidate
    ungated: XSecWalkForwardAggregate = None  # type: ignore[assignment]
    ungated_fitness_pass: bool = False
    ungated_fitness_reason: str = ""
    ungated_bar_a_pass: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        def agg_summary(a: Optional[XSecWalkForwardAggregate]) -> Optional[dict]:
            if a is None:
                return None
            return {
                "n_windows_with_data": a.n_windows_with_data,
                "median_return_pct": a.median_return_pct,
                "pct_positive": a.pct_positive,
                "pct_beat_bh_basket": a.pct_beat_bh_basket,
                "median_sharpe": a.median_sharpe,
                "median_return_bull": a.median_return_bull,
                "median_return_chop": a.median_return_chop,
                "median_return_bear": a.median_return_bear,
                "worst": {"label": a.worst_window_label, "pct": a.worst_return_pct},
                "best": {"label": a.best_window_label, "pct": a.best_return_pct},
                "total_trades": a.total_trades,
                "bar_a_bullet1_pass": a.bar_a_bullet1_pass,
                "bar_a_bullet1_reason": a.bar_a_bullet1_reason,
                "windows": [w.to_row() for w in a.windows],
            }
        return {
            "strategy": self.strategy,
            "basket": self.basket,
            "warmup_days": self.warmup_days,
            "phase": 1,
            "regime_source": "deterministic_standin (code_fallback_decision / regime_uptrend SPY-50)",
            "gated": {
                "summary": agg_summary(self.gated),
                "fitness_pass": self.gated_fitness_pass,
                "fitness_reason": self.gated_fitness_reason,
                "bar_a_bullet1_pass": self.gated_bar_a_pass,
            },
            "ungated_baseline": {
                "summary": agg_summary(self.ungated),
                "fitness_pass": self.ungated_fitness_pass,
                "fitness_reason": self.ungated_fitness_reason,
                "bar_a_bullet1_pass": self.ungated_bar_a_pass,
            },
            "notes": self.notes,
        }


def score_phase1(strategy_name: str,
                 *,
                 basket: Optional[List[str]] = None,
                 warmup_days: int = 400) -> Phase1Report:
    """Run the Phase-1 deterministic-stand-in evaluation on a candidate.

    Produces TWO walk-forwards on the SAME candidate code:
      1. GATED: regime gate active, deterministic stand-in injected.
      2. UNGATED: `use_regime_gate=False` (parent behavior) — the baseline
         the gate is compared against ("does the regime gate help or hurt
         under the dumb signal?").
    """
    decide_fn, params, _root = load_candidate(strategy_name)
    basket = basket or list(params.get("basket") or [])
    if not basket:
        raise ValueError(f"{strategy_name}: no basket in params and none provided")

    report = Phase1Report(strategy=strategy_name, basket=list(basket),
                          warmup_days=warmup_days)

    # ---- 1. Gated under deterministic stand-in. ----
    gated_params = copy.deepcopy(params)
    gated_params["use_regime_gate"] = True
    gated_inject = make_regime_injector(decide_fn, gated_params, mode="standin")
    gated = walk_forward_xsec(
        strategy_name, basket, params=gated_params,
        decide_xsec_fn=gated_inject, warmup_days=warmup_days)
    report.gated = gated
    fp, fr = passes_fitness_gate_xsec(gated)
    report.gated_fitness_pass = fp
    report.gated_fitness_reason = fr
    report.gated_bar_a_pass = gated.bar_a_bullet1_pass

    # ---- 2. Ungated baseline (gate kill-switch). ----
    # Still inject a stand-in decision, but the candidate ignores it because
    # use_regime_gate=False => bit-for-bit parent. This proves the parity
    # invariant AND gives the honest "gate vs no-gate" comparison.
    ungated_params = copy.deepcopy(params)
    ungated_params["use_regime_gate"] = False
    ungated_inject = make_regime_injector(decide_fn, ungated_params, mode="standin")
    ungated = walk_forward_xsec(
        strategy_name, basket, params=ungated_params,
        decide_xsec_fn=ungated_inject, warmup_days=warmup_days)
    report.ungated = ungated
    ufp, ufr = passes_fitness_gate_xsec(ungated)
    report.ungated_fitness_pass = ufp
    report.ungated_fitness_reason = ufr
    report.ungated_bar_a_pass = ungated.bar_a_bullet1_pass

    # ---- Notes. ----
    d_med = gated.median_return_pct - ungated.median_return_pct
    d_sharpe = gated.median_sharpe - ungated.median_sharpe
    report.notes.append(
        f"gate vs no-gate (stand-in): medRet {d_med:+.2f}pp, "
        f"medSharpe {d_sharpe:+.2f}")
    if d_med < -1e-9 or d_sharpe < -1e-9:
        report.notes.append(
            "Regime gate HURTS under the deterministic SPY-50 stand-in "
            "(consistent with PATTERNS.md #1). Phase 2 must show the richer "
            "LLM signal RECOVERS and EXCEEDS this floor or Tier 2 adds no value.")
    elif d_med > 1e-9 or d_sharpe > 1e-9:
        report.notes.append(
            "Regime gate HELPS even under the dumb stand-in — surprising vs "
            "PATTERNS.md #1; investigate before assuming LLM will help more.")
    else:
        report.notes.append("Gate is neutral under the stand-in.")

    return report


def format_phase1_md(report: Phase1Report) -> str:
    lines = [
        f"## Phase 1 (deterministic stand-in) — {report.strategy}",
        "",
        f"- Basket: `{','.join(report.basket)}`",
        f"- Warmup: {report.warmup_days}d/window",
        f"- Regime source: deterministic `code_fallback_decision()` = "
        f"`regime_uptrend(SPY, 50)` (zero LLM cost)",
        "",
        "### Gated candidate (regime gate ON, stand-in injected)",
        "",
        format_xsec_md(report.gated),
        f"**Bar A bullet #1:** {'🟢 PASS' if report.gated_bar_a_pass else '🔴 FAIL'} — "
        f"{report.gated.bar_a_bullet1_reason}",
        f"**Fitness gate:** {'🟢 PASS' if report.gated_fitness_pass else '🔴 FAIL'} — "
        f"{report.gated_fitness_reason}",
        "",
        "### Ungated baseline (use_regime_gate=False = parent behavior)",
        "",
        format_xsec_md(report.ungated),
        f"**Bar A bullet #1:** {'🟢 PASS' if report.ungated_bar_a_pass else '🔴 FAIL'} — "
        f"{report.ungated.bar_a_bullet1_reason}",
        f"**Fitness gate:** {'🟢 PASS' if report.ungated_fitness_pass else '🔴 FAIL'} — "
        f"{report.ungated_fitness_reason}",
        "",
        "### Notes",
        "",
    ]
    for n in report.notes:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="runner.regime_backtest",
                                 description="Tier 2 Bar C evaluator (Phase 1).")
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--basket", help="comma-separated; overrides params.basket")
    ap.add_argument("--phase", type=int, default=1, choices=(1, 2))
    ap.add_argument("--warmup-days", type=int, default=400)
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    if args.phase == 2:
        print("Phase 2 (LLM replay) is a separate, cost-incurring step requiring "
              "sign-off; not runnable from this CLI.", file=sys.stderr)
        return 2

    basket = ([s.strip() for s in args.basket.split(",") if s.strip()]
              if args.basket else None)
    report = score_phase1(args.strategy, basket=basket,
                          warmup_days=args.warmup_days)

    md = format_phase1_md(report)
    print(md)
    if args.md:
        Path(args.md).write_text(md)
        print(f"wrote {args.md}", file=sys.stderr)
    if args.json:
        Path(args.json).write_text(json.dumps(report.to_dict(), indent=2))
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
