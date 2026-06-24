"""lane_honesty.py — shared honesty guards for research-lane backtests.

WHY THIS EXISTS (2026-06-23)
----------------------------
On 2026-06-23 THREE separate research lanes (fundamentals-PIT quality/value, BAB,
commodity-roll-yield carry) all died on the SAME TWO failure modes:

  (1) SURVIVORSHIP-BETA-IN-DISGUISE — a long-only sleeve "beats SPY" purely because
      our universe is today's survivors. The tell: it LOSES to a dumb equal-weight
      hold of its OWN universe (the no-signal EW control), and/or its market-neutral
      long-short (L/S) spread is negative/absent. The long-only "win" is just beta.

  (2) OOS-REGIME-ARTIFACT MIRAGE — a sleeve shows a gaudy out-of-sample Sharpe while
      its in-sample (and full-period) Sharpe is ~0 or negative. The OOS number is a
      single-regime artifact (e.g. one post-2018 backwardation window), not a robust
      forward edge. A robustness sweep that looks great is ALL the same artifact.

Each lane re-implemented these checks from scratch in its own one-off test file, which
means a future lane author has to REMEMBER to write them again — and the day they
forget is the day an overfit sleeve gets promoted. This module crystallizes both guards
as importable, tested pure functions so every future lane gets the catch automatically
in minutes, not after a full opus run.

These guards encode the standing MEMORY.md rule "🔬 CROSS-SEC FACTOR GATE" plus the
IS-consistency analog discovered in the commodity-carry lane. They are HONESTY checks,
not promotion gates — promotion is a separate, stricter decision. A lane that fails any
of these is disqualified regardless of how good its headline number looks.

USAGE (typical lane)
--------------------
    from runner.lane_honesty import (
        sharpe, assert_lane_honest, survivorship_verdict, oos_mirage_verdict,
    )

    verdict = assert_lane_honest(
        signal_daily=sig_rets,          # the strategy's daily returns (full sample)
        ew_control_daily=ew_rets,       # no-signal EW hold of the SAME universe
        oos_split_index=split_i,        # index into the daily series where OOS begins
        ls_spread_daily=ls_rets,        # optional: market-neutral L/S spread daily rets
    )
    print(verdict.summary())
    if not verdict.passed:
        # disposition CLOSE/PARTIAL — do NOT pitch as a promotable edge
        ...

All functions are dependency-free (pure Python) so they match the conventions of the
existing lane test files (BAB / fundamentals / commodity) to the decimal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

TRADING_DAYS = 252

# Thresholds below are the PROVEN ones used by the three lanes that established this
# pattern on 2026-06-23. They are deliberately conservative (honesty floor, not a
# promotion bar). Override per-lane only with an explicit, logged reason.
DEFAULT_OOS_MIRAGE_FULL_SHARPE_FLOOR = 0.15   # full-period Sharpe must clear this...
DEFAULT_OOS_MIRAGE_IS_SHARPE_FLOOR = 0.0      # ...AND in-sample Sharpe must not be negative


# ---------------------------------------------------------------------------
# Core stats — convention-matched to the lane test files (BAB/fundamentals/commodity)
# ---------------------------------------------------------------------------
def sharpe(rets: Sequence[float], trading_days: int = TRADING_DAYS) -> float:
    """Annualized Sharpe of a daily return series. Matches BAB/fundamentals convention.

    Returns 0.0 for degenerate inputs (n<2 or zero variance) rather than raising, so a
    guard never crashes a lane on an empty slice.
    """
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(trading_days)


def total_return(rets: Sequence[float]) -> float:
    """Compounded total return (as a fraction, e.g. 0.42 == +42%)."""
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    return eq - 1.0


def cagr(rets: Sequence[float], trading_days: int = TRADING_DAYS) -> float:
    """Compound annual growth rate as a percent. Matches BAB convention."""
    if not rets:
        return 0.0
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    yrs = len(rets) / trading_days
    if yrs <= 0 or eq <= 0:
        return 0.0
    return (eq ** (1.0 / yrs) - 1.0) * 100.0


def _slice_oos(daily: Sequence[float], oos_split_index: int) -> List[float]:
    """Return the OOS tail of a daily series. oos_split_index is the FIRST OOS index."""
    if oos_split_index is None:
        return list(daily)
    if oos_split_index < 0:
        oos_split_index = max(0, len(daily) + oos_split_index)
    return list(daily[oos_split_index:])


def _slice_is(daily: Sequence[float], oos_split_index: int) -> List[float]:
    """Return the in-sample head of a daily series (everything before OOS)."""
    if oos_split_index is None:
        return list(daily)
    if oos_split_index < 0:
        oos_split_index = max(0, len(daily) + oos_split_index)
    return list(daily[:oos_split_index])


# ---------------------------------------------------------------------------
# Guard 1 — SURVIVORSHIP: must beat no-signal EW-of-same-universe + honest L/S spread
# ---------------------------------------------------------------------------
@dataclass
class SurvivorshipVerdict:
    passed: bool
    reason: str
    signal_oos_total: float
    ew_oos_total: float
    delta_oos_total: float          # signal − EW, OOS net total return (the make-or-break)
    signal_oos_sharpe: float
    ew_oos_sharpe: float
    ls_spread_oos_total: Optional[float] = None
    ls_spread_oos_sharpe: Optional[float] = None

    def summary(self) -> str:
        ls = ""
        if self.ls_spread_oos_total is not None:
            ls = (f" | L/S spread OOS tot {self.ls_spread_oos_total:+.4f} "
                  f"Sharpe {self.ls_spread_oos_sharpe:+.3f}")
        return (f"[SURVIVORSHIP {'PASS' if self.passed else 'FAIL'}] "
                f"signal OOS tot {self.signal_oos_total:+.4f} vs EW {self.ew_oos_total:+.4f} "
                f"(Δ {self.delta_oos_total:+.4f}){ls} — {self.reason}")


def survivorship_verdict(
    signal_daily: Sequence[float],
    ew_control_daily: Sequence[float],
    oos_split_index: Optional[int],
    ls_spread_daily: Optional[Sequence[float]] = None,
) -> SurvivorshipVerdict:
    """The cross-sec survivorship honesty test (MEMORY.md 🔬 CROSS-SEC FACTOR GATE).

    MAKE-OR-BREAK: the signal must beat a no-signal equal-weight hold of its OWN universe,
    OOS, net of cost. If a dumb EW hold of the same names beats the factor, the 'edge' is
    100% survivorship of today's winners and the tilt SUBTRACTS value.

    If a market-neutral L/S spread series is supplied, it must ALSO be non-negative OOS —
    a long-only "beats SPY" with a negative/absent L/S spread is beta, every time.

    Both signal and EW control MUST be computed on the SAME path, universe, and cost.
    """
    sig_oos = _slice_oos(signal_daily, oos_split_index)
    ew_oos = _slice_oos(ew_control_daily, oos_split_index)

    sig_oos_tot = total_return(sig_oos)
    ew_oos_tot = total_return(ew_oos)
    delta = sig_oos_tot - ew_oos_tot

    sig_oos_sh = sharpe(sig_oos)
    ew_oos_sh = sharpe(ew_oos)

    ls_tot = ls_sh = None
    ls_ok = True
    if ls_spread_daily is not None:
        ls_oos = _slice_oos(ls_spread_daily, oos_split_index)
        ls_tot = total_return(ls_oos)
        ls_sh = sharpe(ls_oos)
        ls_ok = ls_tot > 0

    beats_ew = delta > 0
    passed = beats_ew and ls_ok

    if not beats_ew:
        reason = (f"LOSES to no-signal EW hold of same universe by "
                  f"{delta * 100:.1f}pp OOS — survivorship beta, not alpha")
    elif not ls_ok:
        reason = (f"beats EW but L/S spread is NEGATIVE OOS ({ls_tot * 100:+.1f}pp) — "
                  f"long-only win is just beta")
    else:
        reason = "beats no-signal EW control OOS" + (
            " and L/S spread is positive OOS" if ls_spread_daily is not None else "")

    return SurvivorshipVerdict(
        passed=passed, reason=reason,
        signal_oos_total=round(sig_oos_tot, 6), ew_oos_total=round(ew_oos_tot, 6),
        delta_oos_total=round(delta, 6),
        signal_oos_sharpe=round(sig_oos_sh, 4), ew_oos_sharpe=round(ew_oos_sh, 4),
        ls_spread_oos_total=None if ls_tot is None else round(ls_tot, 6),
        ls_spread_oos_sharpe=None if ls_sh is None else round(ls_sh, 4),
    )


# ---------------------------------------------------------------------------
# Guard 2 — OOS-MIRAGE: a gaudy OOS Sharpe with ~0 IS/full Sharpe is a regime artifact
# ---------------------------------------------------------------------------
@dataclass
class OOSMirageVerdict:
    passed: bool
    reason: str
    full_sharpe: float
    is_sharpe: float
    oos_sharpe: float
    full_sharpe_floor: float
    is_sharpe_floor: float

    def summary(self) -> str:
        return (f"[OOS-MIRAGE {'PASS' if self.passed else 'FAIL'}] "
                f"full {self.full_sharpe:+.3f} / IS {self.is_sharpe:+.3f} / "
                f"OOS {self.oos_sharpe:+.3f} — {self.reason}")


def oos_mirage_verdict(
    signal_daily: Sequence[float],
    oos_split_index: int,
    full_sharpe_floor: float = DEFAULT_OOS_MIRAGE_FULL_SHARPE_FLOOR,
    is_sharpe_floor: float = DEFAULT_OOS_MIRAGE_IS_SHARPE_FLOOR,
) -> OOSMirageVerdict:
    """The IS-consistency honesty test (commodity-carry lane, 2026-06-23).

    A sleeve whose edge appears ONLY out-of-sample — negative in-sample Sharpe while its
    FULL-period Sharpe is ~0 — is a single-regime artifact, not a robust forward edge.
    The gaudy OOS number (and any robustness sweep built on the same window) cannot be
    trusted as forward expectation.

    FAIL when (full_sharpe < full_sharpe_floor) AND (is_sharpe < is_sharpe_floor): the
    edge lives entirely in the OOS window and neither the full sample nor the in-sample
    period supports it. This is the exact `commodity_regime_artifact` condition that
    saved us from promoting the commodity-carry sleeve.
    """
    is_rets = _slice_is(signal_daily, oos_split_index)
    oos_rets = _slice_oos(signal_daily, oos_split_index)

    full_sh = sharpe(signal_daily)
    is_sh = sharpe(is_rets)
    oos_sh = sharpe(oos_rets)

    is_artifact = (full_sh < full_sharpe_floor) and (is_sh < is_sharpe_floor)
    passed = not is_artifact

    if is_artifact:
        reason = (f"OOS-only regime artifact: full Sharpe {full_sh:+.3f} < {full_sharpe_floor} "
                  f"AND IS Sharpe {is_sh:+.3f} < {is_sharpe_floor} — gaudy OOS "
                  f"{oos_sh:+.3f} is one-regime luck, not forward edge")
    else:
        reason = "full/IS Sharpe support the OOS result (not an OOS-only mirage)"

    return OOSMirageVerdict(
        passed=passed, reason=reason,
        full_sharpe=round(full_sh, 4), is_sharpe=round(is_sh, 4), oos_sharpe=round(oos_sh, 4),
        full_sharpe_floor=full_sharpe_floor, is_sharpe_floor=is_sharpe_floor,
    )


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------
@dataclass
class LaneHonestyVerdict:
    passed: bool
    survivorship: Optional[SurvivorshipVerdict]
    oos_mirage: Optional[OOSMirageVerdict]
    failures: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"=== LANE HONESTY: {'PASS' if self.passed else 'FAIL'} ==="]
        if self.survivorship is not None:
            lines.append("  " + self.survivorship.summary())
        if self.oos_mirage is not None:
            lines.append("  " + self.oos_mirage.summary())
        if self.failures:
            lines.append("  FAILURES: " + "; ".join(self.failures))
        return "\n".join(lines)


def assert_lane_honest(
    signal_daily: Sequence[float],
    oos_split_index: int,
    ew_control_daily: Optional[Sequence[float]] = None,
    ls_spread_daily: Optional[Sequence[float]] = None,
    full_sharpe_floor: float = DEFAULT_OOS_MIRAGE_FULL_SHARPE_FLOOR,
    is_sharpe_floor: float = DEFAULT_OOS_MIRAGE_IS_SHARPE_FLOOR,
    raise_on_fail: bool = False,
) -> LaneHonestyVerdict:
    """Run both recurring-failure-mode guards and return a combined verdict.

    - Survivorship guard runs only if ``ew_control_daily`` is supplied (it is MANDATORY
      for any cross-sectional factor on our fixed modern-survivor universe; omit it only
      for a single-asset timing sleeve where there is no universe to EW-hold).
    - OOS-mirage guard always runs (every lane has IS/OOS/full).

    Set ``raise_on_fail=True`` to turn a dishonest lane into an AssertionError (handy in
    a lane's own test suite so a regression can't silently promote an overfit sleeve).
    """
    failures: List[str] = []

    surv = None
    if ew_control_daily is not None:
        surv = survivorship_verdict(
            signal_daily, ew_control_daily, oos_split_index, ls_spread_daily)
        if not surv.passed:
            failures.append("SURVIVORSHIP: " + surv.reason)

    mir = oos_mirage_verdict(
        signal_daily, oos_split_index,
        full_sharpe_floor=full_sharpe_floor, is_sharpe_floor=is_sharpe_floor)
    if not mir.passed:
        failures.append("OOS-MIRAGE: " + mir.reason)

    passed = len(failures) == 0
    verdict = LaneHonestyVerdict(
        passed=passed, survivorship=surv, oos_mirage=mir, failures=failures)

    if raise_on_fail and not passed:
        raise AssertionError(verdict.summary())
    return verdict
