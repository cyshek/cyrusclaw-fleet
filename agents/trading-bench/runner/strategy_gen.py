"""LLM-in-the-loop strategy author + safety pipeline.

This module is the plumbing for *generating* new candidate strategies via
LLM subagents, *code-reviewing* them statically, and *evaluating* them via
walk-forward backtest against the live fitness gate. It deliberately does
NOT auto-promote anything. The flow is:

    generate_candidate(parent, directive)
        └─> spawns LLM subagent, returns {name, code, params, ...}
    code_review(candidate)
        └─> AST-level static checks (imports, decide signature, no FS, ...)
    evaluate(candidate)
        └─> writes to strategies_candidates/<name>/ (QUARANTINE, gitignored)
            └─> runs walk_forward() across 8 named windows
                └─> passes_fitness_gate() decides PROMOTE / REJECT_*
                    └─> if PROMOTE, flag for manual Tessera review.
                        We DO NOT move to strategies/ automatically.

Quarantine rationale: live runner / live crons import from `strategies/`,
not `strategies_candidates/`. A candidate that gets generated, passes code
review, runs in backtest, even passes the gate — never touches live trading
until a human (Tessera) reviews the code AND the walk-forward report and
moves the directory by hand. This is the gap between "looks good on paper"
and "I'm willing to risk paper capital on it tonight."

The LLM is not trusted: code_review runs BEFORE the candidate is even
written to disk, and quarantine + manual promotion is the second backstop.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
CANDIDATES_ROOT = WORKSPACE / "strategies_candidates"

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))


# ---------------------------------------------------------------------------
# Mutation directives — boring/standard mutations. Let LLM creativity emerge
# *within* a directive; don't ask for creativity at the directive level.
# ---------------------------------------------------------------------------

MUTATION_DIRECTIVES: List[str] = [
    # 1. Param sweep on lookback / period — most boring, highest signal-to-noise.
    "Take the parent strategy and try a different lookback / period parameter "
    "(e.g. SMA fast/slow, Donchian lookback, RSI period). Pick a value in the "
    "range 10-50 that is meaningfully different from the parent's value. Keep "
    "the rest of the strategy logic identical.",

    # 2. Volatility filter — gate trades when realized vol is too high.
    "Take the parent strategy and add a volatility filter that gates new "
    "entries when 20-bar realized volatility (stdev of pct returns) exceeds "
    "a threshold. CRITICAL: pick the threshold so that on the parent's "
    "historical bars the filter would skip at least 15% of entries — a "
    "filter that never fires is dead code. Pick a value in the range "
    "0.005–0.025 per-bar stdev. Document the chosen threshold in the "
    "docstring with one sentence explaining why. Already-open positions "
    "can still close normally. The filter must NEVER trap an existing "
    "position long.",

    # 3. Time-of-day filter — only trade during high-liquidity hours.
    "Take the parent strategy and add a time-of-day filter that only allows new "
    "entries during 14:30-20:00 UTC (US regular session). Bars are tagged with "
    "'t' in ISO8601 UTC. Closes still fire any time. The filter must NEVER trap "
    "an existing position long.",

    # 4. Combine two parents — pick a second seed and AND/OR the signals.
    "Take the parent strategy and combine its entry signal with a second "
    "signal (e.g. require both an SMA crossover AND a recent breakout). Be "
    "explicit about the logical combination (AND vs OR). CRITICAL: an AND "
    "combination filters out trades — prefer OR (more entries) when the "
    "goal is more opportunities, AND only when the goal is to filter out "
    "losers. Justify the choice in the docstring: explain which kind of "
    "parent trade you're trying to eliminate (a specific failure mode), or "
    "which kind of new trade you're trying to add. Exits fire on either "
    "parent's exit signal — never make a position harder to close than to "
    "open.",

    # 5. Different symbol, same sector — port the strategy to a sibling ETF.
    "Take the parent strategy and port it to a different symbol in the same "
    "asset class. For tech (XLK/QQQ), try SOXX, SMH, or VGT. For small-caps "
    "(IWM), try IJR or VB. Keep the strategy logic identical; only change the "
    "symbol and any symbol-specific params.",

    # 6. Tighter risk: trailing stop or hard stop-loss on entries.
    "Take the parent strategy and add a hard stop-loss: track entry price "
    "in position_state and close the position if price falls more than X% "
    "below entry. CRITICAL: the parent's own exit signal usually fires "
    "before any large drawdown, so X must be TIGHT to actually trigger. "
    "Pick X in the range 0.3%–1.0% (NOT 1.5%+) and explain in the "
    "docstring why you chose that value — what kind of intra-trade move "
    "is the stop trying to catch that the parent's exit misses. A stop "
    "that never fires in backtest is inert code, not edge. Stop-loss "
    "must NOT block the parent's own close signal (parent's exit runs "
    "first).",

    # 9. Take-profit overlay — exit on a target gain that parent would hold through.
    "Take the parent strategy and add a take-profit overlay: track entry "
    "price in position_state and close the position when price has risen "
    "more than X% above entry. Pick X in the range 0.8%–3.0% based on "
    "what fraction of typical winning trades you want to lock in. The "
    "hypothesis: the parent gives back gains on winners by holding too "
    "long. Justify the chosen X in the docstring. Take-profit must NOT "
    "block the parent's own close signal (parent's exit runs first); "
    "take-profit only fires when the parent would otherwise hold.",

    # 7. Regime score sizing — use regime_score() instead of regime_uptrend().
    "Take the parent strategy and replace the binary regime gate with a "
    "regime-score gate using `regime_score(spy_closes, period=50)`. Only "
    "enter when regime_score > 0.02 (SPY at least 2% above its 50d SMA). "
    "This is a stricter version of the regime filter.",

    # 8. Inverse / contrarian — flip the entry condition on a mean-revert symbol.
    "Take the parent strategy (which is trend-following) and produce a "
    "contrarian / mean-reverting variant: enter on pullbacks (e.g. close below "
    "lower band) instead of breakouts (close above upper band). Adjust the exit "
    "logic to match. Use a symbol that mean-reverts (e.g. IWM, GLD).",

    # 10. Regime-conditional stop — stops should be tight in bear, loose in bull.
    "Take the parent strategy and add a REGIME-CONDITIONAL hard stop-loss. "
    "Read SPY closes from `market_state['regime']`. When SPY is BELOW its "
    "50-day SMA (bear/chop regime), apply a TIGHT stop (e.g. 0.5%). When "
    "SPY is ABOVE its 50-day SMA (bull regime), apply a LOOSE stop or no "
    "stop at all — trends should be allowed to breathe. CRITICAL: the "
    "parent's regime filter (if any) only gates ENTRIES; this directive "
    "adds regime-conditional behavior on EXITS, which the parent doesn't "
    "have. Ground both stop thresholds in the PARENT PROFILE — the tight "
    "stop should be near the parent's p75 drawdown (close to the median); "
    "the loose stop should be near or beyond p25. Justify both numbers in "
    "the docstring. Stop must NOT block parent's own close signal.",

    # 11. Partial exit / scale-out — capture some gain, ride the rest.
    "Take the parent strategy and add a PARTIAL EXIT (scale-out): when an "
    "open position has risen X% above entry, close HALF the position and "
    "keep the other half running on the parent's normal exit logic. "
    "Hypothesis: parent winners give back gains by holding to exit; "
    "locking in half de-risks while preserving upside. Ground X in the "
    "PARENT PROFILE — X should sit near the median runup so it fires on "
    "~50% of winners. CRITICAL: position_state must track 'scaled_out' "
    "boolean per symbol so partial-exit only fires ONCE per trade. "
    "Implementation: emit a `sell` Action with `notional_usd=notional/2` "
    "or `qty=holding/2`. Parent's close signal still fires the remainder. "
    "Justify X in the docstring using the parent's runup percentiles.",

    # 12. Time-stop — force-close after N bars regardless of signal.
    "Take the parent strategy and add a TIME-STOP: track entry bar index "
    "in position_state and force-close the position after N bars have "
    "elapsed, regardless of the parent's exit signal. Hypothesis: trades "
    "that haven't worked within their typical holding window are dead "
    "money tying up capital. Ground N in the PARENT PROFILE's holding "
    "distribution — N should be near the p75 holding-bars value (force "
    "out the slow 25% of trades). Justify the chosen N in the docstring. "
    "Time-stop is a HARD exit; it fires alongside (and after) parent's "
    "close signal in the same way a stop-loss does. Document whether "
    "time-stopped trades counted toward the parent's profitable or "
    "unprofitable bucket on average (you can infer from raw_trades "
    "holding_bars vs pnl correlation).",

    # 13. Trailing stop — stop anchored to running max, not entry price.
    "Take the parent strategy and add a TRAILING STOP. Track the highest "
    "price seen since entry (running max) in position_state and close the "
    "position when price falls X% from that running max (NOT from entry "
    "price). Hypothesis: this lets winners run during sustained trends "
    "while still cutting them when a real reversal starts, capturing more "
    "of the parent's upside than a fixed-from-entry stop. Ground X in the "
    "PARENT PROFILE — the runup distribution shows how far typical "
    "winners run; X should be smaller than the median runup so the "
    "trailing stop fires on the give-back phase rather than the run-up "
    "phase. Justify the chosen X in the docstring. Trailing stop must NOT "
    "block parent's own close signal. position_state must reset "
    "running_max to entry_price on every new entry.",

    # 14. Entry-confirmation delay — require signal to persist N consecutive
    # bars before entering. Uses cross-flat `market_state['strategy_state']`.
    "Take the parent strategy and add an ENTRY-CONFIRMATION DELAY: require "
    "the parent's entry signal to remain TRUE for N consecutive bars "
    "before actually placing the buy. If the signal is false on any bar, "
    "reset the consecutive-bar counter to 0 immediately. Hypothesis: "
    "many false-positive entries are single-bar spikes (e.g. a one-bar "
    "breakout that reverses immediately, or an SMA crossover that flips "
    "back next bar). Forcing the signal to hold for N bars filters those "
    "out at the cost of entering N bars late on true trends. Pick "
    "`entry_confirm_bars` in the range 2–5. Justify the chosen N in the "
    "docstring relative to the parent's typical holding distribution "
    "(N should be a small fraction of median holding bars — otherwise "
    "the lag eats too much of the move).\n\n"
    "CRITICAL — use `market_state['strategy_state']` (NOT `position_state`) "
    "to count consecutive signal bars. `position_state` is cleared on "
    "close, but `strategy_state` survives across flat periods so the "
    "counter persists naturally between trades. The runner re-reads "
    "`market_state['strategy_state']` after `decide()` returns, so "
    "mutating the dict in-place is sufficient (no reassignment needed).\n\n"
    "This filter ONLY gates entries. Exits (parent's own close signal) "
    "must fire normally and must NEVER be blocked by the confirmation "
    "counter. Already-open positions must always be closeable.\n\n"
    "Code skeleton (adapt to the parent's specific entry-signal shape):\n"
    "```python\n"
    "def decide(market_state, position_state, params):\n"
    "    symbol = params['symbol']\n"
    "    n_confirm = int(params.get('entry_confirm_bars', 2))\n"
    "    state = market_state['strategy_state']  # survives flats\n"
    "\n"
    "    # ... compute indicators / parent signal ...\n"
    "    entry_signal = (last > hi)   # parent's own entry condition\n"
    "    exit_signal  = (last < lo)   # parent's own exit condition\n"
    "\n"
    "    holding = float((position_state.get(symbol) or {}).get('qty', 0))\n"
    "\n"
    "    # Exits ALWAYS run first and are never gated.\n"
    "    if holding > 0 and exit_signal:\n"
    "        state['confirm_count'] = 0  # reset on exit too\n"
    "        return Action('close', symbol, reason='...')\n"
    "\n"
    "    # Confirmation counter (only meaningful when flat).\n"
    "    if entry_signal:\n"
    "        state['confirm_count'] = state.get('confirm_count', 0) + 1\n"
    "    else:\n"
    "        state['confirm_count'] = 0   # ANY false bar resets\n"
    "\n"
    "    if holding == 0 and state.get('confirm_count', 0) >= n_confirm:\n"
    "        state['confirm_count'] = 0   # consume the confirmation\n"
    "        return Action('buy', symbol, notional_usd=notional,\n"
    "                      reason=f'entry confirmed {n_confirm} bars')\n"
    "\n"
    "    return Action('hold', symbol, reason='...')\n"
    "```\n\n"
    "Add `entry_confirm_bars` to params.json (default 2). Document in the "
    "docstring the chosen N AND what fraction of parent entries you "
    "expect this to filter out (if it filters <5% you picked N too low; "
    "if >50% you picked N too high — both are inert in different ways).",

    # 15. (reserved — volume-confirmation; blocked on bars lacking 'v' field)

    # 16. Post-loss cooldown — after closing a losing trade, skip the next
    # N bars before re-entering. Uses cross-flat `market_state['strategy_state']`.
    "Take the parent strategy and add a POST-LOSS COOLDOWN: after closing "
    "a trade that realized a loss (exit price < entry price), refuse to take "
    "ANY new entry for the next N bars. Decrement the remaining-cooldown "
    "counter by 1 on every bar. Exits are NEVER gated by the cooldown — "
    "already-open positions must always be closeable on the parent's normal "
    "exit signal. Hypothesis: a fresh realized loss is weak but non-zero "
    "evidence that the local regime is hostile to this strategy's edge "
    "(volatility spike, trend reversal, news shock). Sitting out N bars "
    "lets the worst-case path play through without re-entering into it. "
    "Pick `loss_cooldown_bars` in the range 3–20. Justify the chosen N in "
    "the docstring relative to the parent's typical holding distribution "
    "(roughly 0.25–1.0× median holding bars is a sane band — much smaller "
    "is inert, much larger eats too many trading opportunities).\n\n"
    "CRITICAL — use `market_state['strategy_state']` (NOT `position_state`) "
    "to track the cooldown counter. `position_state` is cleared on close "
    "(which is exactly when you need to ARM the cooldown), but "
    "`strategy_state` survives across flat periods so the counter persists "
    "naturally between trades. The runner re-reads "
    "`market_state['strategy_state']` after `decide()` returns, so mutating "
    "the dict in-place is sufficient (no reassignment needed).\n\n"
    "DETECTING THE LOSS — DO NOT mirror entry_price into strategy_state "
    "yourself. The runner already exposes the parent's average entry price "
    "via `position_state[symbol]['avg_entry_price']` while a position is "
    "open. On the bar where YOUR code decides to close, read that value "
    "BEFORE returning the close action and compare to `market_state"
    "['last_price']`: if last_price < avg_entry_price (ignoring fees — "
    "good-enough proxy for realized loss), set "
    "`strategy_state['cooldown_remaining'] = N` in the same call that "
    "emits the close. Reading avg_entry_price AFTER the close action is "
    "too late because position_state[symbol] is gone on the next bar. "
    "Don't try to detect the loss retroactively on a later bar.\n\n"
    "This filter ONLY gates entries. Exits (parent's own close signal) "
    "must fire normally and must NEVER be blocked by the cooldown counter. "
    "Safety backstops (`safety_max_loss_pct`, `safety_max_holding_bars`) "
    "also continue to fire unchanged — they short-circuit decide() before "
    "your code runs, so you don't need to special-case them.\n\n"
    "Code skeleton (adapt to the parent's specific entry-signal shape):\n"
    "```python\n"
    "def decide(market_state, position_state, params):\n"
    "    symbol = params['symbol']\n"
    "    cooldown_n = int(params.get('loss_cooldown_bars', 5))\n"
    "    state = market_state['strategy_state']  # survives flats\n"
    "    last = float(market_state['last_price'])\n"
    "\n"
    "    # ... compute indicators / parent signal ...\n"
    "    entry_signal = (last > hi)   # parent's own entry condition\n"
    "    exit_signal  = (last < lo)   # parent's own exit condition\n"
    "\n"
    "    pos = position_state.get(symbol) or {}\n"
    "    holding = float(pos.get('qty', 0))\n"
    "\n"
    "    # 1. Exits ALWAYS run first and are never gated by cooldown.\n"
    "    if holding > 0 and exit_signal:\n"
    "        # Detect realized loss BEFORE the close clears position_state.\n"
    "        entry_px = float(pos.get('avg_entry_price', 0.0) or 0.0)\n"
    "        if entry_px > 0 and last < entry_px:\n"
    "            state['cooldown_remaining'] = cooldown_n\n"
    "        return Action('close', symbol, reason='...')\n"
    "\n"
    "    # 2. Decrement cooldown once per bar (only when flat — exits above\n"
    "    #    already returned). Floor at 0; never negative.\n"
    "    cd = int(state.get('cooldown_remaining', 0) or 0)\n"
    "    if cd > 0:\n"
    "        state['cooldown_remaining'] = cd - 1\n"
    "\n"
    "    # 3. Block entries while cooldown is still arming (use the\n"
    "    #    pre-decrement value so a fresh cooldown_remaining=N blocks\n"
    "    #    the NEXT N entry opportunities, not N-1).\n"
    "    if holding == 0 and entry_signal and cd == 0:\n"
    "        return Action('buy', symbol, notional_usd=notional,\n"
    "                      reason='entry (no cooldown active)')\n"
    "\n"
    "    return Action('hold', symbol,\n"
    "                  reason=f'cooldown {cd}' if cd > 0 else 'no signal')\n"
    "```\n\n"
    "Add `loss_cooldown_bars` to params.json (default 5). Document in the "
    "docstring the chosen N AND your rough expectation of how often it "
    "will fire given the parent's typical loss rate (if the parent loses "
    "on <10% of trades the cooldown almost never engages and the directive "
    "is inert; if it loses on >60% of trades the cooldown is active most "
    "of the time and may smother the strategy). Either extreme is a sign "
    "the directive isn't a good fit for this parent — say so honestly in "
    "the docstring rather than picking N to hide it.",
]


# ---------------------------------------------------------------------------
# Static code review — runs BEFORE the candidate touches disk.
# ---------------------------------------------------------------------------

# Modules a candidate is allowed to import. Anything else is rejected.
# Conservative on purpose. Add more as legitimate needs surface.
_ALLOWED_IMPORTS = {
    "typing", "dataclasses", "math", "statistics", "__future__",
    "strategies", "strategies._lib", "strategies._lib.indicators",
}

# Names that are NEVER allowed (even as attribute access on something else).
_FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars",
}

# Modules that are NEVER allowed to be imported, even partially.
_FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "urllib", "urllib.request",
    "requests", "httpx", "pickle", "shelve", "marshal", "ctypes",
    "multiprocessing", "threading", "asyncio", "shutil", "tempfile",
    "pathlib", "io", "builtins", "importlib",
}


def _check_imports(tree: ast.Module) -> List[str]:
    violations: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                top = n.name.split(".")[0]
                if n.name in _FORBIDDEN_MODULES or top in _FORBIDDEN_MODULES:
                    violations.append(f"forbidden import: {n.name}")
                elif n.name not in _ALLOWED_IMPORTS and top not in {
                    "typing", "dataclasses", "math", "statistics", "__future__",
                    "strategies",
                }:
                    violations.append(f"unapproved import: {n.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0]
            if mod in _FORBIDDEN_MODULES or top in _FORBIDDEN_MODULES:
                violations.append(f"forbidden import-from: {mod}")
            elif mod not in _ALLOWED_IMPORTS and top not in {
                "typing", "dataclasses", "math", "statistics", "__future__",
                "strategies",
            }:
                violations.append(f"unapproved import-from: {mod}")
    return violations


def _check_forbidden_names(tree: ast.Module) -> List[str]:
    """Flag bare-name use of eval/exec/open/etc. Attribute access (e.g.
    `something.open(...)`) is allowed by this check; the import gate above
    catches `os.system`-style threats by blocking the import itself."""
    violations: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            violations.append(f"forbidden name reference: {node.id}")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in _FORBIDDEN_NAMES:
                violations.append(f"forbidden call: {f.id}(...)")
    return violations


def _check_decide_signature(tree: ast.Module) -> List[str]:
    """Verify a top-level `decide(market_state, position_state, params)` fn
    is defined and there's an `Action` class (local or imported)."""
    violations: List[str] = []
    has_decide = False
    has_action = False
    expected_args = ["market_state", "position_state", "params"]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "decide":
            has_decide = True
            args = [a.arg for a in node.args.args]
            if args != expected_args:
                violations.append(
                    f"decide() signature mismatch: got {args}, "
                    f"expected {expected_args}")
        elif isinstance(node, ast.ClassDef) and node.name == "Action":
            has_action = True
        elif isinstance(node, ast.ImportFrom):
            for n in node.names:
                if n.name == "Action" or (n.asname == "Action"):
                    has_action = True
    if not has_decide:
        violations.append("missing top-level decide(market_state, position_state, params)")
    if not has_action:
        violations.append("missing Action class (define locally or import from a shared lib)")
    return violations


def _check_loops_and_recursion(tree: ast.Module) -> List[str]:
    """Reject `while True:` (easy infinite loop) and self-recursive decide()
    (a strategy decide() shouldn't call itself — almost certainly a bug)."""
    violations: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            t = node.test
            is_true_literal = (
                (isinstance(t, ast.Constant) and t.value is True)
                or (isinstance(t, ast.NameConstant) and getattr(t, "value", None) is True)  # py<3.8 compat
            )
            if is_true_literal:
                violations.append("`while True:` not allowed (infinite-loop risk)")
    # Self-recursion in decide():
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "decide":
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    f = inner.func
                    if isinstance(f, ast.Name) and f.id == "decide":
                        violations.append("decide() must not call itself recursively")
    return violations


def _check_docstring(tree: ast.Module) -> List[str]:
    """Soft requirement: module-level docstring (the thesis). Warn-style;
    promoted to a real violation because we want LLM strategies to be
    self-documenting — opaque code is harder to post-mortem when it loses."""
    ds = ast.get_docstring(tree)
    if not ds or len(ds.strip()) < 20:
        return ["missing or trivially short module docstring (must explain the thesis)"]
    return []


def code_review(candidate: dict) -> Tuple[bool, List[str]]:
    """Static review of `candidate['code']`. Returns (passed, violations).

    Runs BEFORE the file is written to disk. Any non-empty violations list
    means REJECT the candidate; do not even try to backtest it.

    Checks:
        - parses as Python
        - defines top-level decide(market_state, position_state, params)
        - defines Action (local class or import)
        - no forbidden imports (os/sys/subprocess/socket/urllib/...)
        - no bare eval/exec/open/__import__ calls
        - no `while True:` or self-recursive decide()
        - has a substantive module docstring (thesis statement)
    """
    code = candidate.get("code") or ""
    if not code.strip():
        return (False, ["empty code"])
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return (False, [f"syntax error: {e}"])

    violations: List[str] = []
    violations += _check_imports(tree)
    violations += _check_forbidden_names(tree)
    violations += _check_decide_signature(tree)
    violations += _check_loops_and_recursion(tree)
    violations += _check_docstring(tree)
    return (len(violations) == 0, violations)


# ---------------------------------------------------------------------------
# LLM prompt construction + generation
# ---------------------------------------------------------------------------

# Read once at import for inclusion in LLM prompts. The two gate-passing
# regime-filtered strategies are the gold-standard template; show both so
# the LLM sees the pattern is not specific to one indicator.
_GOLD_TEMPLATE_BREAKOUT = (WORKSPACE / "strategies/breakout_xlk_regime/strategy.py")
_GOLD_TEMPLATE_SMA = (WORKSPACE / "strategies/sma_crossover_qqq_regime/strategy.py")
_INDICATORS_PATH = (WORKSPACE / "strategies/_lib/indicators.py")


def _read_text_safe(p: Path) -> str:
    try:
        return p.read_text()
    except Exception:
        return f"<could not read {p}>"


def _build_llm_prompt(seed_strategy: Optional[str],
                      mutation_directive: str,
                      candidate_name: str,
                      *,
                      second_parent: Optional[str] = None,
                      postmortem_context: Optional[str] = None) -> str:
    """Construct the task message sent to the candidate-generation subagent.

    Constraints baked into the prompt are also enforced by code_review;
    the prompt is a *guidance* layer, code_review is the *enforcement* layer.

    `second_parent` (optional) enables GENUINE cross-parent combos: when set to
    another strategy's name, that parent's `strategy.py` source is injected as a
    clearly-labeled SECOND PARENT reference block so the LLM can borrow its real
    signal mechanism instead of reconstructing it from a prose description. When
    None (default) the prompt is byte-identical to the single-parent form.

    `postmortem_context` (optional) prepends a LOSS-ANATOMY guidance block built
    from the parent's most recent loss-postmortem (regime at loss, cost-vs-edge,
    signal-quality, classified cause + avoidance hints). It makes the mutation
    *learn from the specific way the parent lost*, not just mutate randomly. When
    None (default) the assembled prompt is BYTE-IDENTICAL to the form without it
    (preserves the protected-md5 enforcement path; verified by a pinning test).
    """
    parent_code = ""
    parent_params = ""
    parent_profile_section = ""
    if seed_strategy:
        sp = WORKSPACE / "strategies" / seed_strategy / "strategy.py"
        pp = WORKSPACE / "strategies" / seed_strategy / "params.json"
        parent_code = _read_text_safe(sp)
        parent_params = _read_text_safe(pp)
        # Pull empirical trade profile so the LLM can ground threshold
        # picks (stop-loss, take-profit, vol filter) in real numbers
        # instead of vague heuristics. Failures degrade gracefully —
        # render_profile_for_prompt handles the no-data case.
        try:
            from .parent_profile import (
                profile_parent_trades, render_profile_for_prompt,
            )
            prof = profile_parent_trades(seed_strategy)
            parent_profile_section = render_profile_for_prompt(prof)
        except Exception as _e:
            parent_profile_section = (
                "## PARENT PROFILE\n\n"
                f"_Profile generation failed: {type(_e).__name__}_ — "
                "pick conservative threshold values inside directive ranges.\n"
            )
    else:
        parent_profile_section = (
            "## PARENT PROFILE\n\n"
            "_No parent (synth-from-scratch) — no profile available._\n"
        )

    gold_breakout = _read_text_safe(_GOLD_TEMPLATE_BREAKOUT)
    indicators = _read_text_safe(_INDICATORS_PATH)

    # Optional SECOND PARENT block for genuine cross-parent combos. Empty string
    # when no second_parent is given -> the assembled prompt is byte-identical to
    # the single-parent form (preserves the protected-md5 enforcement path).
    second_parent_section = ""
    if second_parent:
        sp2 = WORKSPACE / "strategies" / second_parent / "strategy.py"
        if sp2.exists():
            second_code = _read_text_safe(sp2)
        else:
            second_code = (
                f"# (could not find strategies/{second_parent}/strategy.py "
                "— borrow the mechanism described in the directive instead)"
            )
        second_parent_section = (
            "\n\n## SECOND PARENT (`" + second_parent + "`) — borrow its entry-signal "
            "mechanism\n\nThis is the OTHER parent in the combo. Do NOT copy it "
            "wholesale; take its ENTRY-SIGNAL idea and fuse it with the primary "
            "parent above per the mutation directive (prefer OR-combining entries "
            "so the combo does not starve itself; exits must always stay "
            "reachable). The traded symbol/timeframe stays the PRIMARY parent's."
            "\n\nstrategy.py:\n```python\n" + second_code + "\n```"
        )

    # Optional LOSS-ANATOMY prefix. Empty string when no postmortem_context ->
    # the assembled prompt is byte-identical to the form without it (pinned by
    # test_build_llm_prompt_byte_identical_without_context).
    postmortem_prefix = ""
    if postmortem_context:
        postmortem_prefix = (
            "## PARENT LOSS ANATOMY (learn from how this parent recently lost)\n\n"
            "The parent strategy below recently failed/lost. Here is the diagnosed\n"
            "anatomy of that loss. Bias your mutation to ADDRESS this specific\n"
            "failure mode — do not reintroduce it:\n\n"
            + postmortem_context.strip()
            + "\n\n---\n\n"
        )

    return postmortem_prefix + f"""You are writing ONE new trading strategy module for the trading-bench
tournament. Output exactly two artifacts in your final message:

  1. A fenced block tagged ```python labelled `# === strategy.py ===` with
     the complete contents of strategy.py.
  2. A fenced block tagged ```json labelled `# === params.json ===` with
     the complete contents of params.json.

Nothing else after those two blocks. No commentary, no apology, no "here you go".

## The contract (NON-NEGOTIABLE — your code will be statically rejected if you violate any)

- Define a top-level function with EXACTLY this signature:
      def decide(market_state: dict, position_state: dict, params: dict) -> Action
- Define an `Action` dataclass with fields:
      action: str            # "buy" | "sell" | "close" | "hold"
      symbol: str
      notional_usd: float = 0.0
      qty: Optional[float] = None
      reason: str = ""
- Imports MUST be limited to: typing, dataclasses, math, statistics, __future__,
  and `from strategies._lib.indicators import ...`.
- FORBIDDEN imports: os, sys, subprocess, socket, urllib, requests, httpx,
  pickle, shutil, tempfile, pathlib, io, importlib, threading, asyncio, ctypes.
- FORBIDDEN names/calls: eval, exec, compile, __import__, open, input.
- No `while True:`. No filesystem I/O. No network I/O. No recursion in decide().
- Hold-when-not-enough-bars guard is MANDATORY. If you need N bars to compute
  your indicator, return `Action("hold", symbol, reason=f"not enough bars ...")`
  when `len(closes(bars)) < N`.
- Module-level docstring is MANDATORY: explain the thesis in 2-5 sentences.
  What's the entry signal? Exit signal? Why might this have edge?

## Available helpers (use ONLY these from strategies/_lib/indicators)

```python
{indicators}
```

## Mutation directive

> {mutation_directive}

{parent_profile_section}

## Parent strategy (`{seed_strategy or 'none'}`) — start from this

strategy.py:
```python
{parent_code if parent_code else '# (no parent — synthesize from scratch using the gold-standard template below)'}
```

params.json:
```json
{parent_params if parent_params else '{"symbol":"QQQ","timeframe":"1Hour","bar_limit":120,"notional_usd":1000.0}'}
```{second_parent_section}

## Gold-standard template (regime-filtered breakout, currently passing fitness gate)

```python
{gold_breakout}
```

## Hard rules from production strategies

- Risk caps live in the runner, not in strategies. Do not enforce position
  size in your code; just return an Action with notional_usd=params['notional_usd'].
- Already-open positions must ALWAYS be closeable. Any filter (regime, time,
  volatility, etc.) that blocks entries must NOT block exits. The gold template
  shows the pattern: close-logic first, entry-gate second.
- Use `market_state.get("regime")` to read SPY trend; it's pre-populated by
  the runner/backtester for stocks (None for crypto — your code should handle
  None gracefully and just fall through).
- `position_state[symbol]["qty"]` is your current long size. Always coerce
  with float(); position_state may be {{}} when flat.

## Naming + params

- Strategy module name: `{candidate_name}` (this is fixed; do not change).
- params.json MUST be valid JSON with at minimum:
    "symbol": string,
    "timeframe": "15Min"|"1Hour"|"4Hour"|"1Day",
    "bar_limit": int (>= 2x your longest lookback),
    "notional_usd": float (always 1000.0 unless directive says otherwise)

OUTPUT ONLY the two fenced blocks. Begin now.
"""


def _split_artifacts(llm_output: str) -> Tuple[str, str]:
    """Pull strategy.py and params.json out of a markdown response.

    Permissive: looks for the first ```python block (= strategy.py) and the
    first ```json block (= params.json). Returns ("", "") if not both present.
    """
    code = ""
    params = ""
    # Find first ```python ... ```
    py_start = llm_output.find("```python")
    if py_start != -1:
        py_end = llm_output.find("```", py_start + len("```python"))
        if py_end != -1:
            block = llm_output[py_start + len("```python"):py_end]
            # Strip optional `# === strategy.py ===` first line marker.
            code = block.lstrip("\n")
            if code.lstrip().startswith("# === strategy.py"):
                code = code.split("\n", 1)[1] if "\n" in code else ""
            code = code.strip("\n")
    j_start = llm_output.find("```json")
    if j_start != -1:
        j_end = llm_output.find("```", j_start + len("```json"))
        if j_end != -1:
            block = llm_output[j_start + len("```json"):j_end]
            params = block.lstrip("\n")
            if params.lstrip().startswith("# === params.json"):
                params = params.split("\n", 1)[1] if "\n" in params else ""
            params = params.strip("\n")
    return (code, params)


def generate_candidate(seed_strategy: Optional[str],
                       mutation_directive: str,
                       *,
                       candidate_name: Optional[str] = None,
                       spawn_fn: Optional[Callable[..., dict]] = None,
                       postmortem_context: Optional[str] = None,
                       ) -> dict:
    """Spawn an LLM subagent to author ONE strategy module.

    Args:
        seed_strategy: parent strategy name (e.g. "breakout_xlk_regime").
            None means "no parent — synthesize from scratch" (not recommended
            in early rounds; we have no evidence the LLM can do this cold).
        mutation_directive: one entry from MUTATION_DIRECTIVES (or custom).
        candidate_name: override; default is derived from parent + directive
            hash so re-runs are idempotent-ish.
        spawn_fn: injectable for tests. Production wiring uses sessions_spawn
            from the OpenClaw runtime, which this module imports lazily.
        postmortem_context: optional LOSS-ANATOMY blob (from the parent's most
            recent loss-postmortem) injected as a prompt prefix so the mutation
            addresses the parent's specific failure mode. None -> prompt is
            byte-identical to the no-context form.

    Returns:
        {
            "name": str,                # candidate module name
            "code": str,                # contents of strategy.py
            "params": str,              # contents of params.json
            "parent": Optional[str],    # seed_strategy
            "directive": str,           # mutation_directive
            "agent_session_key": str,   # the subagent session id (for audit)
        }

    Does NOT write to disk. Does NOT call code_review (caller's job).
    """
    if candidate_name is None:
        # Short stable name: parent + 6-char hash of directive.
        import hashlib
        h = hashlib.sha1(mutation_directive.encode()).hexdigest()[:6]
        base = (seed_strategy or "synth").replace("/", "_")
        candidate_name = f"{base}__mut_{h}"

    prompt = _build_llm_prompt(seed_strategy, mutation_directive, candidate_name,
                               postmortem_context=postmortem_context)

    # In production, spawn an LLM subagent via OpenClaw's sessions_spawn.
    # Caller can inject `spawn_fn` (used by tests and the --dry-run path).
    if spawn_fn is None:
        spawn_fn = _default_spawn_fn

    spawn_result = spawn_fn(prompt=prompt, task_label=f"strategy-gen:{candidate_name}")
    llm_output = spawn_result.get("output", "") if isinstance(spawn_result, dict) else str(spawn_result)
    session_key = spawn_result.get("session_key", "") if isinstance(spawn_result, dict) else ""

    code, params = _split_artifacts(llm_output)

    return {
        "name": candidate_name,
        "code": code,
        "params": params,
        "parent": seed_strategy,
        "directive": mutation_directive,
        "agent_session_key": session_key,
        "raw_llm_output": llm_output,  # kept for audit; trimmed by reports.
    }


def _default_spawn_fn(*, prompt: str, task_label: str) -> dict:
    """Default subagent spawn — wires to OpenClaw's sessions_spawn at runtime.

    The actual `sessions_spawn` tool is part of the agent runtime, not a
    Python library, so it's resolved indirectly. For now this raises; the
    real call is made by the orchestrator subagent (the next turn's job).

    We deliberately don't auto-spawn from inside the runner Python — the
    orchestrator is a subagent itself, and it should explicitly drive the
    spawn so the agent-to-agent audit trail is clean.
    """
    raise NotImplementedError(
        "_default_spawn_fn must be overridden. Inject `spawn_fn=...` when "
        "calling generate_candidate(). The orchestrator subagent is "
        "responsible for actually invoking sessions_spawn — this Python "
        "module just builds the prompt and parses the response."
    )


# ---------------------------------------------------------------------------
# Quarantine I/O + evaluation
# ---------------------------------------------------------------------------

def _write_candidate_to_quarantine(candidate: dict) -> Path:
    """Write {strategy.py, params.json, __init__.py} into
    strategies_candidates/<name>/. Overwrites prior runs of same name."""
    name = candidate["name"]
    dest = CANDIDATES_ROOT / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "__init__.py").write_text("")
    (dest / "strategy.py").write_text(candidate["code"])
    (dest / "params.json").write_text(candidate["params"])
    return dest


def _load_candidate_module_and_params(name: str):
    """Load a quarantine candidate's module + params, the same way the
    backtester loads `strategies.<name>` — but from `strategies_candidates/`.
    We use importlib.util.spec_from_file_location so the quarantine dir is
    never on sys.path (live runner imports from `strategies.*` and must not
    accidentally pick up `strategies_candidates.*`)."""
    candidate_dir = CANDIDATES_ROOT / name
    strat_file = candidate_dir / "strategy.py"
    params_file = candidate_dir / "params.json"
    if not strat_file.exists() or not params_file.exists():
        raise FileNotFoundError(f"candidate not found: {candidate_dir}")
    # Unique module name (prefixed) so we don't shadow `strategies.<name>`.
    mod_name = f"_candidate_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, strat_file)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register in sys.modules BEFORE exec_module so @dataclass et al. can
    # resolve cls.__module__ via sys.modules.get(...). Without this, the
    # dataclass decorator throws AttributeError on Python 3.10+.
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(mod_name, None)
        raise
    params = json.loads(params_file.read_text())
    return module, params


# Cache parent WalkForward aggregates within a process run — parents
# don't change between candidates in the same tournament round, but
# walk-forward is heavy (8 windows * full bar fetch). One-line cache.
_PARENT_WF_CACHE: dict = {}


def _parent_wf_cached(parent_name: str, notional_usd: float | None = None):
    """Run walk-forward for `parent_name` (a strategy in `strategies/`) and
    cache it. Returns a WalkForwardAggregate. Lazy import to avoid pulling
    bars_cache at module load.

    NOTIONAL-MATCH (bugfix 2026-06-29): the mutation gate compares the
    candidate's median *return %* against the parent's. In this engine
    `total_return_pct` = dollars-pnl / starting_equity and pnl scales
    LINEARLY with `notional_usd` (verified ratio exactly notional/100), so a
    candidate that declares notional=1000 produces a 10x-inflated return %
    vs a parent baseline run at its on-disk notional=100 — corrupting the
    `MUTATION_MIN_DELTA_PCT` median-return check (it manufactured a FALSE
    PROMOTE for breakout_xlk__mut_232050 on 2026-06-29). Fix: run the parent
    baseline at the CANDIDATE's notional so the return-% delta is
    apples-to-apples. The Sharpe-delta guard is notional-invariant and was
    unaffected; this only closes the return-delta hole. Cache key includes
    the notional so distinct-notional candidates don't collide.
    """
    key = (parent_name, None if notional_usd is None else round(float(notional_usd), 6))
    if key in _PARENT_WF_CACHE:
        return _PARENT_WF_CACHE[key]
    from .walk_forward import walk_forward, load_strategy_module_and_params
    if notional_usd is None:
        agg = walk_forward(parent_name)
    else:
        # Re-run the parent at the candidate's notional (apples-to-apples).
        module, p_params = load_strategy_module_and_params(parent_name)
        p_params = dict(p_params)
        p_params["notional_usd"] = float(notional_usd)
        agg = walk_forward(parent_name, params=p_params, decide_fn=module.decide)
    _PARENT_WF_CACHE[key] = agg
    return agg


# ---------------------------------------------------------------------------
# Dedup guards (2026-06-08) — stop the redundant-dir factory
# ---------------------------------------------------------------------------
# WHY: the quarantine had grown to 100+ dirs that were "2 edges in 48
# costumes" (Cyrus). Two distinct redundancy modes slip past the fitness +
# stability gates:
#   (1) EXACT CODE CLONE — the LLM re-emits a strategy.py byte-for-byte
#       identical (modulo whitespace/the module name) to one already in
#       quarantine. A clone cannot be new edge; it's pure clutter.
#   (2) INERT MUTATION — the directive asked for a filter/tweak, but the
#       added logic NEVER changes a trade vs the parent (e.g. a guard whose
#       threshold never binds on the backtest panel). The candidate's
#       executed trades are ~identical to the parent's, so any metric delta
#       is pure backtest noise, not a behavioral change. This is the single
#       most common factory mode: a "new" strategy that trades exactly like
#       its parent.
# Both are REJECT-before-PROMOTE: they only suppress a would-be PROMOTE, and
# they NEVER touch the live strategies/ dir (quarantine only).

# A candidate whose executed-trade signature overlaps its parent's by AT OR
# ABOVE this Jaccard fraction is judged behaviorally inert (the mutation
# didn't actually change what it trades). 0.95 leaves headroom for a couple
# of genuinely-changed trades while catching "identical trade tape".
DEDUP_TRADE_OVERLAP_MAX = 0.95
# Below this many combined distinct trades there isn't enough signal to judge
# overlap reliably — skip the inert check (the trade-floor guard in the
# mutation gate already rejects ultra-thin candidates on its own).
DEDUP_MIN_TRADES_FOR_OVERLAP = 8


def _normalize_code_for_hash(code: str, name: str = "") -> str:
    """Canonicalize strategy source for clone detection.

    Strips trailing whitespace per line, blank-line runs, and — critically —
    the candidate's own module name wherever it appears, so two byte-identical
    strategies that differ ONLY by their `__mut_<hash>` suffix hash the same.
    Not a full AST canonicalization (comments/varnames still count); this is a
    deliberately conservative 'literally the same file' detector, not a
    semantic-equivalence oracle.
    """
    text = code.replace(name, "_CAND_") if name else code
    lines = [ln.rstrip() for ln in text.splitlines()]
    # collapse consecutive blank lines
    out: List[str] = []
    for ln in lines:
        if ln == "" and out and out[-1] == "":
            continue
        out.append(ln)
    return "\n".join(out).strip()


def _code_md5(code: str, name: str = "") -> str:
    import hashlib
    return hashlib.md5(_normalize_code_for_hash(code, name).encode()).hexdigest()


def _find_code_clone(candidate: dict) -> Optional[str]:
    """Return the name of an existing quarantine candidate whose normalized
    strategy.py is byte-identical to this candidate's, or None.

    Compares against every other dir in strategies_candidates/ (excluding the
    candidate's own dir, since evaluate() writes quarantine BEFORE this runs).
    """
    me = candidate["name"]
    my_hash = _code_md5(candidate.get("code", ""), me)
    if not CANDIDATES_ROOT.exists():
        return None
    for d in sorted(CANDIDATES_ROOT.iterdir()):
        if not d.is_dir() or d.name == me or d.name.startswith("__"):
            continue
        sf = d / "strategy.py"
        if not sf.exists():
            continue
        try:
            other = sf.read_text()
        except Exception:
            continue
        if _code_md5(other, d.name) == my_hash:
            return d.name
    return None


def _trade_signature_set(agg) -> set:
    """Build a set of canonical executed-trade signatures from a
    WalkForwardAggregate. Each closed trade across all windows becomes a
    tuple keyed on (window label, entry/exit prices rounded, holding bars,
    qty rounded) — stable identifiers of 'this specific trade happened',
    independent of pnl. Used to measure behavioral overlap between a
    candidate and its parent. Window label is included so the same price
    pattern in different regimes doesn't false-collide.
    """
    sig: set = set()
    for w in getattr(agg, "windows", []) or []:
        label = getattr(w, "label", "")
        for t in getattr(w.backtest, "closed_trades", []) or []:
            sig.add((
                label,
                round(float(t.get("entry_price", 0.0)), 4),
                round(float(t.get("exit_price", 0.0)), 4),
                int(t.get("holding_bars", 0)),
                round(float(t.get("qty", 0.0)), 6),
            ))
    return sig


def _trade_overlap_jaccard(child_agg, parent_agg) -> Tuple[float, int]:
    """Jaccard overlap of executed-trade signatures between child and parent.
    Returns (overlap_fraction, n_union). overlap = |A∩B| / |A∪B|. 1.0 means
    the candidate executed exactly the parent's trades (behaviorally inert);
    0.0 means completely different trade tape.
    """
    a = _trade_signature_set(child_agg)
    b = _trade_signature_set(parent_agg)
    union = a | b
    if not union:
        return (0.0, 0)
    inter = a & b
    return (len(inter) / len(union), len(union))


def evaluate(candidate: dict, *, write_to_disk_temp: bool = True) -> dict:
    """Full evaluation pipeline for a candidate.

    1. code_review — if it fails, REJECT_CODE_REVIEW (no disk write).
    2. Write to strategies_candidates/<name>/ (quarantine).
    3. Walk-forward backtest across all 8 named regime windows.
    4. passes_fitness_gate() → PROMOTE or REJECT_GATE.
    5. PROMOTE is a flag only. Tessera reviews + moves the dir manually.

    Catches strategy runtime crashes -> REJECT_CRASH.

    Returns:
        {
            "candidate": {...},                        # echoed back, trimmed
            "code_review": {"passed": bool, "violations": [...]},
            "walk_forward_results": dict | None,       # WalkForwardAggregate as dict
            "fitness_gate": {"passed": bool, "reason": str} | None,
            "verdict": "PROMOTE" | "REJECT_GATE" |
                       "REJECT_CODE_REVIEW" | "REJECT_CRASH",
            "quarantine_path": str | None,
            "error": str | None,                       # only on REJECT_CRASH
        }
    """
    trimmed = {k: v for k, v in candidate.items() if k != "raw_llm_output"}
    out = {
        "candidate": trimmed,
        "code_review": None,
        "walk_forward_results": None,
        "fitness_gate": None,
        "verdict": None,
        "quarantine_path": None,
        "error": None,
    }

    # ----- 1. Static code review -----
    passed, violations = code_review(candidate)
    out["code_review"] = {"passed": passed, "violations": violations}
    if not passed:
        out["verdict"] = "REJECT_CODE_REVIEW"
        return out

    if not write_to_disk_temp:
        # Caller wants gate-by-static-only (e.g. dry-run). Stop here.
        out["verdict"] = "PROMOTE"  # passed code review; backtest skipped.
        return out

    # ----- 2. Quarantine write -----
    try:
        path = _write_candidate_to_quarantine(candidate)
        out["quarantine_path"] = str(path)
    except Exception as e:
        out["verdict"] = "REJECT_CRASH"
        out["error"] = f"quarantine write failed: {e}"
        return out

    # ----- 3. Walk-forward backtest -----
    try:
        module, params = _load_candidate_module_and_params(candidate["name"])
        # Lazy import — walk_forward pulls in bars_cache etc., heavy.
        from .walk_forward import (
            walk_forward,
            passes_fitness_gate,
            passes_mutation_gate,
        )
        agg = walk_forward(candidate["name"], params=params, decide_fn=module.decide)
    except Exception as e:
        out["verdict"] = "REJECT_CRASH"
        out["error"] = f"walk-forward crashed: {type(e).__name__}: {e}"
        return out

    # ----- 4. Fitness gate (absolute) + Mutation gate (relative to parent) -----
    parent_name = candidate.get("parent")
    parent_agg = None
    if parent_name:
        try:
            # Notional-match the parent baseline to the candidate so the
            # mutation gate's median-return delta is apples-to-apples
            # (return % scales linearly with notional in this engine).
            cand_notional = None
            try:
                cand_notional = float(params.get("notional_usd")) if params else None
            except (TypeError, ValueError):
                cand_notional = None
            parent_agg = _parent_wf_cached(parent_name, cand_notional)
        except Exception as e:
            # Don't fail the whole eval if parent baseline isn't reproducible;
            # log and fall back to absolute-gate-only behavior.
            out["parent_baseline_error"] = (
                f"parent walk-forward failed ({type(e).__name__}: {e}); "
                f"mutation gate falls back to absolute-only"
            )
    gate_passed, reason = passes_mutation_gate(agg, parent_agg)
    out["fitness_gate"] = {"passed": gate_passed, "reason": reason}
    if parent_agg is not None:
        out["parent_baseline"] = {
            "strategy": parent_agg.strategy,
            "median_return_pct": parent_agg.median_return_pct,
            "pct_positive": parent_agg.pct_positive,
            "median_sharpe": parent_agg.median_sharpe,
            "n_windows_with_data": parent_agg.n_windows_with_data,
        }
    # Also stash the pure absolute-gate result for diagnostics (e.g. a
    # candidate that clears the absolute bar but fails the relative one
    # is interesting — means the mutation is competent but not an
    # improvement, useful signal for tuning directives).
    abs_passed, abs_reason = passes_fitness_gate(agg)
    out["absolute_fitness_gate"] = {"passed": abs_passed, "reason": abs_reason}

    # Serialize WF results — just the headline aggregates + per-window summary.
    out["walk_forward_results"] = {
        "strategy": agg.strategy,
        "n_windows_with_data": agg.n_windows_with_data,
        "n_windows": agg.n_windows,
        "median_return_pct": agg.median_return_pct,
        "pct_positive": agg.pct_positive,
        "pct_beat_bh_spy": agg.pct_beat_bh_spy,
        "median_sharpe": agg.median_sharpe,
        "worst_return_pct": agg.worst_return_pct,
        "worst_window_label": agg.worst_window_label,
        "best_return_pct": agg.best_return_pct,
        "best_window_label": agg.best_window_label,
        "total_trades": agg.total_trades,
        "windows": [w.to_row() for w in agg.windows],
    }

    # ----- 5. Dedup guards (only gate a would-be PROMOTE) -----
    # A candidate that already fails the fitness/stability gate stays
    # REJECT_GATE; we don't relabel it. But a PASS must additionally not be a
    # redundant clone or a behaviorally-inert copy of its parent, or we're
    # back to minting "2 edges in 48 costumes". Dedup runs on the already-
    # quarantined candidate; it NEVER touches strategies/.
    out["dedup"] = {"code_clone_of": None, "trade_overlap": None}
    if gate_passed:
        clone_of = None
        try:
            clone_of = _find_code_clone(candidate)
        except Exception as e:  # dedup must never crash a real eval
            out["dedup"]["error"] = f"clone-scan failed: {type(e).__name__}: {e}"
        out["dedup"]["code_clone_of"] = clone_of
        if clone_of:
            out["verdict"] = "REJECT_DUPLICATE"
            out["fitness_gate"] = {
                "passed": False,
                "reason": (f"passed gate but strategy.py is byte-identical "
                           f"(normalized) to existing candidate '{clone_of}' "
                           f"— clone, not new edge"),
            }
            return out
        # Inert-mutation check: did this candidate actually trade differently
        # from its parent? Only meaningful when we have a parent baseline and
        # enough combined trades to judge.
        if parent_agg is not None:
            overlap, n_union = _trade_overlap_jaccard(agg, parent_agg)
            out["dedup"]["trade_overlap"] = {
                "jaccard": overlap, "n_union": n_union,
                "threshold": DEDUP_TRADE_OVERLAP_MAX,
            }
            if (n_union >= DEDUP_MIN_TRADES_FOR_OVERLAP
                    and overlap >= DEDUP_TRADE_OVERLAP_MAX):
                out["verdict"] = "REJECT_INERT"
                out["fitness_gate"] = {
                    "passed": False,
                    "reason": (f"passed gate but executed trade tape is "
                               f"{overlap * 100:.0f}% identical to parent "
                               f"'{parent_agg.strategy}' (≥"
                               f"{DEDUP_TRADE_OVERLAP_MAX * 100:.0f}%) — the "
                               f"mutation is behaviorally inert; any metric "
                               f"delta is backtest noise, not changed behavior"),
                }
                return out

    # ----- 6. Verdict -----
    out["verdict"] = "PROMOTE" if gate_passed else "REJECT_GATE"
    return out
