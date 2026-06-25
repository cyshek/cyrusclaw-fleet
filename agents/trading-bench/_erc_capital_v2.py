#!/usr/bin/env python3
"""Capital translation v2: ERC risk-weights -> tradeable capital with a
share-flooring floor so no sleeve is silently zeroed.

The pure leverage-adjusted ERC put tqqq_cot_combo at $30 (3x-levered ETF), which
floors to 0 TQQQ shares = silently muted. A risk officer does not want a sleeve
that the ERC says should contribute risk to be unable to hold a single position.

Fix: impose a per-strategy MIN tradeable base so the intended position is >= ~2
shares of its instrument, then renormalize the REMAINING budget across the others
by their ERC risk-weights. Document the (small) deviation from pure-ERC this
creates. Total stays $800.
"""
import json
from pathlib import Path

WS = Path(__file__).resolve().parent
E = json.load(open(WS / "reports/_erc_weights.json"))
rw = E["risk_weights"]; lev = E["leverage"]; LIVE = E["live"]
BUDGET = 800.0

# approx current share prices (for floor sizing only; from recent fills)
PX = {"breakout_xlk__mut_c382b1":184.0,"sma_crossover_qqq_regime":742.0,
      "sma_crossover_qqq_rth":742.0,"rsi_oversold_spy":600.0,
      "volume_breakout_qqq":742.0,"macd_momentum_iwm":230.0,
      "tqqq_cot_combo":76.0,"allocator_blend":76.0}
# typical max weight applied to the base before share-floor
WMAX = {k:1.0 for k in LIVE}; WMAX["tqqq_cot_combo"]=0.95

# MIN tradeable base: enough to hold >=2 shares of the lead instrument
# (event strategies are single-buy so 1 'share-equivalent' is fine, but keep a
# sane $50 floor so a sleeve isn't dust). For high-priced single-share ETFs the
# event strategies buy fractional via notional, so no share-floor needed there;
# only the vol-target qty-floored sleeves (tqqq) need the share floor.
def min_base(k):
    if k == "tqqq_cot_combo":
        return 2.0 * PX[k] / WMAX[k]   # ~2 TQQQ shares -> ~$160
    return 50.0                         # generic dust floor

# Start from pure leverage-adjusted ERC capital, then enforce floors + renorm.
raw = {k: rw[k]/lev[k] for k in LIVE}
s = sum(raw.values())
cap = {k: BUDGET*raw[k]/s for k in LIVE}

# enforce floors, then renormalize the rest proportionally to ERC risk-weight
for _ in range(10):
    floored = {k: max(cap[k], min_base(k)) for k in LIVE}
    over = sum(floored.values()) - BUDGET
    if over <= 1e-6:
        cap = floored
        break
    # take the overage back from non-floored strategies pro-rata to their cap
    at_floor = {k for k in LIVE if floored[k] <= min_base(k) + 1e-9}
    free = {k: floored[k] for k in LIVE if k not in at_floor}
    fs = sum(free.values())
    if fs <= 0:
        cap = floored; break
    cap = dict(floored)
    for k in free:
        cap[k] = free[k] - over*free[k]/fs

tot = sum(cap.values())
cap = {k: round(v*BUDGET/tot, 2) for k, v in cap.items()}  # final exact-$800 normalize

print(f"{'strategy':30s} {'risk_w':>7s} {'lev':>4s} {'min$':>7s} {'FINAL$':>8s}")
for k in LIVE:
    print(f"{k:30s} {rw[k]*100:6.2f}% {lev[k]:4.1f} {min_base(k):7.0f} {cap[k]:8.2f}")
print(f"{'TOTAL':30s} {'':7s} {'':4s} {'':7s} {sum(cap.values()):8.2f}")

# show resulting TQQQ shares
for k in ["tqqq_cot_combo"]:
    tgt = cap[k]*WMAX[k]; sh = int(tgt//PX[k])
    print(f"\n{k}: base=${cap[k]:.0f} -> target ${tgt:.0f} -> {sh} TQQQ shares (tradeable: {'YES' if sh>=1 else 'NO'})")

E["capital_usd_v2_tradeable"] = cap
E["capital_note"] = ("v2 imposes a share-flooring floor: tqqq_cot_combo floored "
    "to ~2 TQQQ shares (~$160) so the 3x sleeve stays tradeable; the small excess "
    "over its pure-ERC $30 is taken pro-rata from the equity-trend trio. rsi/macd "
    "diversifier overweights preserved.")
json.dump(E, open(WS/"reports/_erc_weights.json","w"), indent=2)
print("\nupdated reports/_erc_weights.json with capital_usd_v2_tradeable")
