"""Equity CROSS-PARENT combo round (main-greenlit hardening, 2026-06-26).

Now that `_build_llm_prompt` supports a `second_parent` kwarg (injects the second
parent's REAL strategy.py so the LLM fuses actual mechanisms, not a prose
description), breed genuine cross-parent combos WITHIN the equity GATE_PASSING_
PARENTS. This is the structural parent-diversity lever main flagged: mechanically
different from solo mutations.

Pairing principle: fuse a STRENGTH-entry parent (breakout / momentum / trend)
with a WEAKNESS-entry parent (RSI mean-reversion) or a different momentum
confirm, so the two entry signals are genuinely orthogonal. The PRIMARY parent's
symbol+timeframe is the traded leg; the SECOND parent contributes its entry-signal
mechanism computed on the primary's own bars. OR-combine entries (add signal),
keep exits always reachable.

Same two-step orchestrator contract as `_prep_xa_round.py`: dump prompts to
/tmp/tournament_round_<id>/, spawn one opus gen subagent per prompt ->
output_NN.txt, then finalize_round(round_dir).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.strategy_gen import _build_llm_prompt  # noqa: E402

# (primary_seed, second_parent, tag, directive)
# Each directive tells the LLM to fuse the primary's entry with the SECOND
# PARENT's entry mechanism (whose real code is now injected), OR-combined.
COMBO_PAIRS = [
    (
        "breakout_xlk", "rsi_oversold_spy", "brkxlk_x_rsispy",
        "PRIMARY = breakout_xlk (Donchian N-bar-high breakout on XLK 1Hour). "
        "Fuse it with the SECOND PARENT's RSI-OVERSOLD MEAN-REVERSION entry "
        "(RSI(14) < oversold threshold), computed on XLK's OWN bars. OR-combine "
        "the two ENTRYS: go long when EITHER a fresh Donchian breakout fires "
        "(momentum) OR RSI is oversold and turning up (mean-reversion dip-buy). "
        "These are deliberately ORTHOGONAL entry regimes (buy-strength vs "
        "buy-weakness) so the combo captures more of the return distribution. "
        "EXIT on the breakout parent's exit (close < N-bar low) OR a sensible "
        "RSI exit (RSI > overbought); exits must ALWAYS be reachable. Keep "
        "symbol=XLK, timeframe=1Hour; bar_limit >= 2x longest lookback. Justify "
        "the OR-fusion of momentum+mean-reversion in the docstring.",
    ),
    (
        "sma_crossover_qqq", "macd_momentum_iwm", "smaqqq_x_macdiwm",
        "PRIMARY = sma_crossover_qqq (fast/slow SMA crossover on QQQ 1Hour). "
        "Fuse it with the SECOND PARENT's MACD-MOMENTUM entry (MACD line crosses "
        "above signal line while MACD>0), computed on QQQ's OWN closes (implement "
        "EMA locally with math/statistics — not in _lib.indicators). Require BOTH "
        "as a CONFIRMATION combo here (this pair is a momentum-AND-momentum "
        "filter, not orthogonal): go long only when the SMA fast>slow regime is "
        "up AND MACD confirms bullish — this should REDUCE false crossovers. "
        "BUT keep exits always reachable: close when fast<slow OR MACD turns "
        "bearish, and NEVER let the AND-gate trap an open position (close logic "
        "runs first, unconditionally). Keep symbol=QQQ, timeframe=1Hour; "
        "bar_limit >= 2x slow window. Justify why MACD-confirmation cuts SMA "
        "whipsaw in the docstring.",
    ),
    (
        "volume_breakout_qqq", "rsi_oversold_spy", "volbrkqqq_x_rsispy",
        "PRIMARY = volume_breakout_qqq (breakout confirmed by above-average "
        "volume on QQQ 1Hour). Fuse it with the SECOND PARENT's RSI-OVERSOLD "
        "MEAN-REVERSION entry computed on QQQ's OWN bars. OR-combine entries: go "
        "long when EITHER a volume-confirmed breakout fires OR RSI is oversold "
        "and turning up. Orthogonal regimes (breakout-strength vs dip-buy). EXIT "
        "on the breakout parent's exit OR RSI>overbought; exits ALWAYS reachable. "
        "Handle missing/zero volume gracefully (fall back to the RSI leg). Keep "
        "symbol=QQQ, timeframe=1Hour; bar_limit >= 2x longest lookback. Justify "
        "the OR-fusion in the docstring.",
    ),
    (
        "macd_momentum_iwm", "breakout_xlk", "macdiwm_x_brkxlk",
        "PRIMARY = macd_momentum_iwm (MACD momentum entry on IWM 1Hour). Fuse it "
        "with the SECOND PARENT's DONCHIAN N-bar-high BREAKOUT entry, computed on "
        "IWM's OWN bars. OR-combine entries: go long when EITHER MACD turns "
        "bullish (MACD>signal, MACD>0) OR IWM makes a fresh N-bar high. Both are "
        "momentum-family but capture DIFFERENT triggers (oscillator cross vs "
        "price-channel break) so OR-ing them should add entries in trends the "
        "other misses. EXIT when MACD turns bearish OR close<N-bar low; exits "
        "ALWAYS reachable. Keep symbol=IWM, timeframe=1Hour; bar_limit >= 2x "
        "longest lookback. Justify the OR-fusion of two momentum triggers in the "
        "docstring.",
    ),
    (
        "rsi_oversold_spy", "sma_crossover_qqq", "rsispy_x_smatrend",
        "PRIMARY = rsi_oversold_spy (RSI(14) oversold mean-reversion dip-buy on "
        "SPY 1Hour). Fuse it with the SECOND PARENT's SMA-TREND regime as a "
        "QUALITY FILTER computed on SPY's OWN closes: only take the RSI dip-buy "
        "when the fast SMA > slow SMA (i.e. buy dips ONLY in an uptrend — the "
        "classic 'buy-the-dip-in-an-uptrend' construct). This is an AND-filter, "
        "so it will REDUCE entries (cuts the catch-a-falling-knife dips in "
        "downtrends). CRITICAL: the trend filter must gate ENTRIES ONLY — an open "
        "position must ALWAYS be closeable (RSI>overbought exit runs first, "
        "unconditionally), never trapped long by the filter. Keep symbol=SPY, "
        "timeframe=1Hour; bar_limit >= 2x slow SMA. Justify why trend-filtering "
        "the dip-buy improves it in the docstring.",
    ),
]

round_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
round_dir = Path("/tmp") / f"tournament_round_{round_id}"
round_dir.mkdir(parents=True, exist_ok=True)

items = []
for i, (seed, second, tag, directive) in enumerate(COMBO_PAIRS, 1):
    h = hashlib.sha1((tag + directive).encode()).hexdigest()[:6]
    name = f"{seed}__x_{tag}_{h}"
    prompt = _build_llm_prompt(seed, directive, name, second_parent=second)
    prompt_path = round_dir / f"prompt_{i:02d}.txt"
    prompt_path.write_text(prompt)
    items.append({
        "i": i, "parent": seed, "primary": seed, "second_parent": second,
        "tag": tag, "directive": directive,
        "candidate_name": name, "prompt_path": str(prompt_path),
        "output_path": str(round_dir / f"output_{i:02d}.txt"),
    })

meta = {"round_id": round_id, "round_dir": str(round_dir),
        "kind": "equity_cross_parent_combo", "items": items}
(round_dir / "meta.json").write_text(json.dumps(meta, indent=2))

print(json.dumps({
    "round_id": round_id, "round_dir": str(round_dir), "n": len(items),
    "items": [{"i": it["i"], "primary": it["primary"],
               "second_parent": it["second_parent"], "name": it["candidate_name"],
               "prompt_path": it["prompt_path"], "output_path": it["output_path"]}
              for it in items],
}, indent=2))
