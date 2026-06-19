"""Parent-trade profiling: ground LLM mutation prompts in real numbers.

Problem this solves
-------------------
When a mutation directive asks the LLM to add a stop-loss, take-profit, or
volatility filter with a threshold, the LLM has zero numeric grounding for
what "reasonable" looks like on the specific parent strategy + symbol +
timeframe. In rounds 2 and 3 we saw it pick thresholds like 1.5% stop or
2% per-bar stdev that never fired in any of the 8 walk-forward windows —
structurally correct mutations, but inert.

Fix: before building the prompt, run the parent through the same 8 named
walk-forward windows the gate uses, extract per-trade max drawdown / max
runup / holding-bars from each closed round-trip, and surface the aggregate
distribution to the LLM. Then the prompt can say:

    "When picking a stop-loss X%, pick BELOW the median trade's max
     drawdown (currently 0.34%) so it would have fired on at least
     half of historical trades."

That's grounding the LLM can actually act on.

Design notes
------------
- Runs the SAME 8 NAMED_WINDOWS the fitness gate uses — consistency matters.
  We do NOT invent fresh windows; the profile must reflect what the parent
  looks like in the regimes its mutations will be judged in.
- Caches per-process (parents don't change within a tournament run), same
  pattern as `_parent_wf_cached` in strategy_gen.py.
- Returns a `ParentProfile` dataclass. Empty-trades parents return a
  profile with `n_trades=0` and `available=False`; callers should render
  "no profile available" in the prompt rather than crash.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ParentProfile:
    """Aggregate per-trade statistics extracted from the parent's walk-forward
    backtest across all 8 named windows.

    Fields with `_pct` are signed fractions (e.g. -0.0034 = -0.34%).
    Drawdown is negative or zero; runup is positive or zero. holding_bars is
    in units of the strategy's own timeframe (1h / 4h / 1d).

    `available=False` means the parent produced zero closed trades across
    all windows (rare but possible — e.g. a parent whose entry signal never
    fired in any window, or a buy-and-hold that never closed). Callers
    should render a "no profile" message instead of bogus stats.
    """
    parent_name: str
    available: bool = False
    n_trades: int = 0
    n_windows_with_data: int = 0
    n_windows_with_trades: int = 0
    # Drawdown stats (signed fractions, negative or zero)
    drawdown_pct_p25: float = 0.0
    drawdown_pct_median: float = 0.0
    drawdown_pct_p75: float = 0.0
    # Runup stats (signed fractions, positive or zero)
    runup_pct_p25: float = 0.0
    runup_pct_median: float = 0.0
    runup_pct_p75: float = 0.0
    # Holding-bar stats (in strategy's own timeframe)
    holding_bars_p25: float = 0.0
    holding_bars_median: float = 0.0
    holding_bars_p75: float = 0.0
    # Fraction of trades that hit ≥1% drawdown / ≥1% runup at some point
    # during the trade. Useful sanity check: a parent whose median drawdown
    # is 0.05% but whose `frac_hit_1pct_drawdown` is 0.4 has skewed tails.
    frac_hit_1pct_drawdown: float = 0.0
    frac_hit_1pct_runup: float = 0.0
    # Optional metadata the prompt-builder may want.
    timeframe: str = ""
    symbol: str = ""
    # Raw per-trade rows kept on the dataclass for debugging; not surfaced
    # to the LLM (would blow up the prompt and the LLM doesn't need it).
    raw_trades: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Profile cache (per-process)
# ---------------------------------------------------------------------------

_PROFILE_CACHE: dict = {}


def _quantile(sorted_xs: List[float], q: float) -> float:
    """Linear-interpolated quantile of an already-sorted list. q in [0,1].
    Returns 0.0 for empty input. Matches numpy's default ('linear') method
    to 6 decimal places; we roll our own to keep numpy out of the runner."""
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_xs) - 1)
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def profile_parent_trades(parent_name: str) -> ParentProfile:
    """Run the parent through walk_forward over the 8 named windows and
    extract per-trade excursion stats. Caches per-process.

    Robust to:
      - parent that crashes (returns available=False profile, doesn't propagate)
      - parent that produces zero trades in every window (available=False)
      - windows that return no bars (already handled inside walk_forward)
    """
    if parent_name in _PROFILE_CACHE:
        return _PROFILE_CACHE[parent_name]

    # Lazy imports to keep this module cheap to import on its own.
    from .walk_forward import walk_forward
    from .backtest import load_strategy_module_and_params

    symbol = ""
    timeframe = ""
    try:
        _module, params = load_strategy_module_and_params(parent_name)
        symbol = params.get("symbol", "") or ""
        timeframe = str(params.get("timeframe", "") or "")
    except Exception:
        # If we can't even load the strategy, we can't profile it.
        prof = ParentProfile(parent_name=parent_name, available=False)
        _PROFILE_CACHE[parent_name] = prof
        return prof

    try:
        agg = walk_forward(parent_name)
    except Exception:
        prof = ParentProfile(
            parent_name=parent_name, available=False,
            symbol=symbol, timeframe=timeframe,
        )
        _PROFILE_CACHE[parent_name] = prof
        return prof

    # Collect per-trade rows across every window.
    all_trades: List[dict] = []
    n_windows_with_trades = 0
    for wr in agg.windows:
        win_trades = wr.backtest.closed_trades
        if win_trades:
            n_windows_with_trades += 1
        for t in win_trades:
            # Backtest now writes these fields; default to 0 for safety
            # (in case an older candidate run is mixed in).
            all_trades.append({
                "entry_price": float(t.get("entry_price", 0.0) or 0.0),
                "exit_price": float(t.get("exit_price", 0.0) or 0.0),
                "max_drawdown_pct": float(t.get("max_drawdown_pct", 0.0) or 0.0),
                "max_runup_pct": float(t.get("max_runup_pct", 0.0) or 0.0),
                "holding_bars": int(t.get("holding_bars", 0) or 0),
            })

    if not all_trades:
        prof = ParentProfile(
            parent_name=parent_name, available=False,
            n_trades=0, n_windows_with_data=agg.n_windows_with_data,
            n_windows_with_trades=0,
            symbol=symbol, timeframe=timeframe,
        )
        _PROFILE_CACHE[parent_name] = prof
        return prof

    drawdowns = sorted(t["max_drawdown_pct"] for t in all_trades)
    runups = sorted(t["max_runup_pct"] for t in all_trades)
    holds = sorted(float(t["holding_bars"]) for t in all_trades)
    n = len(all_trades)
    frac_dd_1pct = sum(1 for t in all_trades if t["max_drawdown_pct"] <= -0.01) / n
    frac_ru_1pct = sum(1 for t in all_trades if t["max_runup_pct"] >= 0.01) / n

    prof = ParentProfile(
        parent_name=parent_name,
        available=True,
        n_trades=n,
        n_windows_with_data=agg.n_windows_with_data,
        n_windows_with_trades=n_windows_with_trades,
        drawdown_pct_p25=_quantile(drawdowns, 0.25),
        drawdown_pct_median=statistics.median(drawdowns),
        drawdown_pct_p75=_quantile(drawdowns, 0.75),
        runup_pct_p25=_quantile(runups, 0.25),
        runup_pct_median=statistics.median(runups),
        runup_pct_p75=_quantile(runups, 0.75),
        holding_bars_p25=_quantile(holds, 0.25),
        holding_bars_median=statistics.median(holds),
        holding_bars_p75=_quantile(holds, 0.75),
        frac_hit_1pct_drawdown=frac_dd_1pct,
        frac_hit_1pct_runup=frac_ru_1pct,
        timeframe=timeframe,
        symbol=symbol,
        raw_trades=all_trades,
    )
    _PROFILE_CACHE[parent_name] = prof
    return prof


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def render_profile_for_prompt(profile: ParentProfile) -> str:
    """Format a ParentProfile as the PARENT PROFILE section of the LLM
    mutation prompt. Returns a complete markdown-ish block. If the profile
    has no data, returns a short "no profile available" notice."""
    if not profile.available or profile.n_trades == 0:
        return (
            "## PARENT PROFILE\n\n"
            f"_No profile available for `{profile.parent_name}`_ — the parent\n"
            "produced zero closed trades across the 8 walk-forward windows,\n"
            "so we cannot ground threshold choices in its history. If your\n"
            "directive asks for a threshold (stop-loss, take-profit, vol\n"
            "filter), pick a conservative value at the LOW end of the\n"
            "directive's suggested range and explain your reasoning.\n"
        )

    def pct(x: float) -> str:
        return f"{x * 100:+.2f}%"

    def pct_abs(x: float) -> str:
        return f"{abs(x) * 100:.2f}%"

    return f"""## PARENT PROFILE — `{profile.parent_name}` ({profile.symbol} @ {profile.timeframe})

This is the empirical distribution of `{profile.parent_name}`'s past trades
across all 8 walk-forward regime windows. **Use these numbers to ground any
threshold you pick — do not guess.**

- Total closed trades: **{profile.n_trades}** across {profile.n_windows_with_trades}/{profile.n_windows_with_data} windows with data.
- Max drawdown PER TRADE (lowest price between entry and exit, vs entry price):
    - p25 (deeper tail): {pct(profile.drawdown_pct_p25)}
    - median:            {pct(profile.drawdown_pct_median)}
    - p75 (shallower):   {pct(profile.drawdown_pct_p75)}
    - fraction of trades that touched ≥1% drawdown: **{profile.frac_hit_1pct_drawdown * 100:.0f}%**
- Max runup PER TRADE (highest price between entry and exit, vs entry price):
    - p25 (smaller):     {pct(profile.runup_pct_p25)}
    - median:            {pct(profile.runup_pct_median)}
    - p75 (bigger):      {pct(profile.runup_pct_p75)}
    - fraction of trades that touched ≥1% runup: **{profile.frac_hit_1pct_runup * 100:.0f}%**
- Holding period PER TRADE (bars at {profile.timeframe}):
    - p25: {profile.holding_bars_p25:.1f} · median: {profile.holding_bars_median:.1f} · p75: {profile.holding_bars_p75:.1f}

### How to use these numbers

- **Stop-loss threshold**: pick a value at or BELOW the median trade's max
  drawdown ({pct_abs(profile.drawdown_pct_median)}) so the stop would have
  fired on at least HALF of historical trades. A stop deeper than the p25
  ({pct_abs(profile.drawdown_pct_p25)}) is inert — it would never have
  fired in this parent's history.
- **Take-profit threshold**: pick a value at or BELOW the median trade's
  max runup ({pct_abs(profile.runup_pct_median)}) so it would have locked
  in at least half the winners. A target above the p75
  ({pct_abs(profile.runup_pct_p75)}) is inert.
- **Volatility filter**: 20-bar per-bar stdev for this symbol/timeframe is
  typically in the same order of magnitude as median runup/drawdown above;
  pick a vol cap near the runup median to gate out only the choppiest bars.
- **Don't guess. Don't pick round numbers (1%, 2%) without checking they
  fall inside this distribution.**
"""
