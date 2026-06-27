"""M-B: UUP x equity COMBO batch prep (main-directed 2026-06-26, pulled fwd).

GOAL: breed the de-correlator parent `trend_follow_uup` against the EQUITY
parents via combo mutation, guaranteeing UUP coverage at small n.

STRUCTURAL REALITY (forces the geometry):
  - The single-name harness exposes ONLY the traded symbol's bars +
    market_state["regime"] (= SPY closes). There is NO arbitrary second-asset
    feed, so an "equity-led, UUP-as-cross-asset-regime" child is physically
    impossible (a child trading XLK cannot read UUP bars). The only macro leg a
    child can read is SPY via market_state["regime"].
  - Prior UUP children that AND-gated UUP (vol filter, RSI-AND) went INERT
    (medRet +0.00%, 38% pos, Sharpe 0.00) -> AND-gating starves the thin
    dollar-trend of entries.

THEREFORE the valid, profileable reading of "combine UUP with equity parents"
is: UUP stays the TRADED LEG; we inject each EQUITY PARENT'S SIGNAL FAMILY
(Donchian breakout / MACD momentum / volume-confirmed breakout / SMA crossover)
computed on UUP's OWN daily bars, OR-combined to ADD entries (fixing the inert
failure), optionally confirmed by the SPY regime. Equity DNA = the signal
MECHANISM; dollar-trend = the leg. Each child is still independently held to the
absolute fitness gate, so a weak parent cannot leak a weak child.

We construct the (parent, directive) pairs DIRECTLY (not random sampling) so
every candidate is a genuine UUP x <named equity mechanism> combo. We reuse
_build_llm_prompt + the same /tmp round layout prepare_round uses, so
finalize_round() consumes it unchanged.
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

PARENT = "trend_follow_uup"

# Each directive: UUP SMA-trend is the base; OR-combine a DISTINCT equity-parent
# signal family ON UUP's OWN bars to ADD entries. Phrased to (a) keep UUP the
# traded leg, (b) prefer OR so the combo does not starve entries, (c) name the
# specific equity mechanism so the DNA is genuinely cross-pollinated, (d) keep
# UUP exits always reachable. The 'tag' becomes part of the candidate name so
# results are legible in the report.
COMBO_DIRECTIVES = [
    (
        "donchian",
        "The parent is a fast UUP (US-dollar ETF) SMA(50) TREND on DAILY bars "
        "(BUY when close>SMA, CLOSE when close<SMA). Combine it with the "
        "DONCHIAN-BREAKOUT entry mechanism borrowed from the equity breakout "
        "parents (e.g. breakout_xlk): also go long when UUP's close makes a new "
        "N-bar high (N in 15-30), computed on UUP's OWN daily bars. Combine the "
        "two ENTRY signals with OR (enter if EITHER the SMA-trend is up OR a "
        "fresh Donchian breakout fires) so the thin dollar-trend gains MORE "
        "entries rather than fewer -- a prior AND-combo made UUP inert (0 "
        "trades). EXIT when close<SMA(period) (parent exit) OR close<the "
        "M-bar Donchian low; a position must NEVER be harder to close than to "
        "open. Justify in the docstring why OR (add-entries) is correct for a "
        "thin de-correlator leg. Keep symbol=UUP, timeframe=1Day; set bar_limit "
        ">= 2x the longest lookback you use.",
    ),
    (
        "macd",
        "The parent is a fast UUP (US-dollar ETF) SMA(50) TREND on DAILY bars. "
        "Combine it with the MACD-MOMENTUM entry mechanism borrowed from the "
        "equity momentum parent (macd_momentum_iwm): compute MACD (EMA_fast - "
        "EMA_slow, e.g. 12/26) and its signal line on UUP's OWN daily closes, "
        "and also go long when the MACD line crosses ABOVE its signal line "
        "while MACD>0. Combine the two ENTRY signals with OR (SMA-trend up OR "
        "fresh MACD bullish cross) so the thin dollar-trend gains MORE entries "
        "-- a prior AND-combo made UUP inert. EXIT when close<SMA(period) OR "
        "MACD crosses back below its signal line; exits must always be "
        "reachable. EMA isn't in _lib.indicators -- implement it locally with "
        "only allowed imports (math/statistics). Keep symbol=UUP, "
        "timeframe=1Day; bar_limit >= 2x longest lookback. Justify the OR "
        "choice in the docstring.",
    ),
    (
        "volbreak",
        "The parent is a fast UUP (US-dollar ETF) SMA(50) TREND on DAILY bars. "
        "Combine it with the VOLUME-CONFIRMED-BREAKOUT mechanism borrowed from "
        "volume_breakout_qqq: also go long when UUP closes above its N-bar high "
        "(N in 15-30) AND that bar's volume exceeds vol_mult x the N-bar "
        "average volume (read volume via bar key 'v'). Combine this "
        "volume-confirmed-breakout entry with the parent SMA-trend entry using "
        "OR (enter if SMA-trend up OR a volume-confirmed breakout fires) so the "
        "thin dollar-trend gains entries rather than being starved. NOTE the "
        "volume CONFIRMATION (price-AND-volume) is internal to the breakout "
        "leg; the breakout leg is then OR'd with the trend leg. EXIT when "
        "close<SMA(period) OR close<the N-bar low. Handle bars with missing/zero "
        "volume gracefully (skip the volume leg, fall back to the trend leg). "
        "Keep symbol=UUP, timeframe=1Day; bar_limit >= 2x longest lookback. "
        "Justify OR in the docstring.",
    ),
    (
        "smacross",
        "The parent is a fast UUP (US-dollar ETF) SMA(50) single-threshold "
        "TREND on DAILY bars. Replace the single SMA threshold with the "
        "DUAL-SMA-CROSSOVER mechanism borrowed from sma_crossover_qqq: compute a "
        "FAST SMA (e.g. 10-20) and a SLOW SMA (e.g. 40-50) on UUP's OWN daily "
        "closes; go long when fast crosses ABOVE slow and flat when fast crosses "
        "BELOW slow. This is a genuine cross-pollination (the equity parent's "
        "two-MA crossover applied to the dollar leg) and naturally produces MORE "
        "responsive entries than the single SMA50 gate without AND-starving "
        "them. Keep exits always reachable (close when fast<slow). Keep "
        "symbol=UUP, timeframe=1Day; bar_limit >= 2x the slow SMA. Justify the "
        "fast/slow choice in the docstring grounded in the parent profile.",
    ),
    (
        "spyregime",
        "The parent is a fast UUP (US-dollar ETF) SMA(50) TREND on DAILY bars. "
        "Add a SPY-REGIME OVERLAY that exploits UUP's NEGATIVE correlation to "
        "equities (corr -0.415 to SPY): read SPY closes from "
        "market_state['regime'] (key 'spy_closes'); the dollar tends to catch a "
        "bid when equities are weak. Combine entries with OR: go long UUP when "
        "EITHER the UUP SMA-trend is up OR SPY is BELOW its 50-day SMA "
        "(risk-off, dollar-haven bid) -- this ADDS the haven entries the pure "
        "trend misses and is the genuine cross-asset edge. Use regime_score or "
        "compute the SPY SMA locally from spy_closes; handle regime==None / "
        "empty spy_closes gracefully (fall back to the pure UUP trend). EXIT "
        "when close<SMA(period) (parent exit); exits must always be reachable. "
        "Keep symbol=UUP, timeframe=1Day; bar_limit >= 100 (need SPY history). "
        "Justify in the docstring why OR-ing the risk-off haven condition is the "
        "correct way to express the dollar's negative-equity-beta DNA.",
    ),
]

round_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
round_dir = Path("/tmp") / f"tournament_round_{round_id}"
round_dir.mkdir(parents=True, exist_ok=True)

items = []
for i, (tag, directive) in enumerate(COMBO_DIRECTIVES, 1):
    h = hashlib.sha1(directive.encode()).hexdigest()[:6]
    name = f"{PARENT}__mut_{tag}_{h}"
    prompt = _build_llm_prompt(PARENT, directive, name)
    prompt_path = round_dir / f"prompt_{i:02d}.txt"
    prompt_path.write_text(prompt)
    items.append({
        "i": i,
        "parent": PARENT,
        "directive": directive,
        "candidate_name": name,
        "prompt_path": str(prompt_path),
        "output_path": str(round_dir / f"output_{i:02d}.txt"),
    })

meta = {"round_id": round_id, "round_dir": str(round_dir), "items": items}
(round_dir / "meta.json").write_text(json.dumps(meta, indent=2))

print(json.dumps({
    "round_id": round_id,
    "round_dir": str(round_dir),
    "n": len(items),
    "items": [
        {"i": it["i"], "parent": it["parent"], "name": it["candidate_name"],
         "tag": COMBO_DIRECTIVES[it["i"] - 1][0],
         "prompt_path": it["prompt_path"], "output_path": it["output_path"]}
        for it in items
    ],
}, indent=2))
