#!/usr/bin/env python3
"""ERC / cluster-aware capital weighting for the 8 live strategies.

Inputs: the structural backtested correlation matrix (4,111 common days) from
reports/_interstrategy_corr_matrix.json (the HONEST co-movement object — live
fills are far too sparse, <10 overlap days per pair, to correlate).

We compute, on the 8-strategy live submatrix:
  1. The full covariance Σ = D · R · D, where R is the correlation submatrix and
     D = diag(standalone daily-return vol). Vol per strategy is recovered from
     its standalone Sharpe + a common return scale is NOT needed for ERC weights
     (ERC is scale-free in the *target*), but we DO need relative vols. We use
     each strategy's standalone daily return std from the saved series stats if
     present; else fall back to equal vol (pure-correlation ERC).
  2. ERC (equal-risk-contribution) weights: solve for w s.t. each asset's risk
     contribution RC_i = w_i·(Σw)_i is equal. Standard cyclical-coordinate /
     Newton-free fixed-point iteration (Maillard-Roncalli-Teiletche 2010).
  3. Translate ERC *risk* weights into CAPITAL notionals, accounting for the
     leverage each sleeve already carries (TQQQ combo = 3x; allocator internally
     blended ~ effective 1.3x on its TQQQ sleeve; event strategies 1x). Capital
     is risk_weight / leverage_factor, renormalized to the $800 budget.

Output: prints a table + writes reports/_erc_weights.json (consumed by the
report + the params patch step). NO config is modified here.
"""
import json
import math
from pathlib import Path

WS = Path(__file__).resolve().parent
M = json.load(open(WS / "reports/_interstrategy_corr_matrix.json"))

labels_all = M["labels"]            # 12 labels, index-aligned to corr_full
R_all = M["corr_full"]              # 12x12

# Map the audit's 12 labels -> our 8 live strategy dir names.
# (audit labels are the same dir names per meta; confirm by substring)
LIVE = [
    "breakout_xlk__mut_c382b1",
    "sma_crossover_qqq_regime",
    "sma_crossover_qqq_rth",
    "rsi_oversold_spy",
    "volume_breakout_qqq",
    "macd_momentum_iwm",
    "tqqq_cot_combo",
    "allocator_blend",
]

# standalone daily-bar Sharpe from the audit's per-strategy diagnostics (table)
# (used only to derive RELATIVE vol; ERC target is scale-free)
STANDALONE_SHARPE = {
    "breakout_xlk__mut_c382b1": 0.510,
    "sma_crossover_qqq_regime": 0.532,
    "sma_crossover_qqq_rth": 0.514,
    "rsi_oversold_spy": 0.271,
    "volume_breakout_qqq": 0.164,
    "macd_momentum_iwm": 0.027,
    "tqqq_cot_combo": 0.90,      # VT+COT (report ~0.90)
    "allocator_blend": 1.006,
}

# Leverage / effective-beta factor each sleeve ALREADY carries inside its own
# notional (so equal CAPITAL != equal RISK). Event strategies trade the cash
# ETF 1x. tqqq_cot_combo trades TQQQ (3x daily-levered). allocator_blend is an
# internally risk-parity blend whose TQQQ sleeve is vol-targeted to ~25% and
# diluted by GLD/TLT/SPY legs -> effective single-name leverage ~1.3x.
LEVERAGE = {
    "breakout_xlk__mut_c382b1": 1.0,
    "sma_crossover_qqq_regime": 1.0,
    "sma_crossover_qqq_rth": 1.0,
    "rsi_oversold_spy": 1.0,
    "volume_breakout_qqq": 1.0,
    "macd_momentum_iwm": 1.0,
    "tqqq_cot_combo": 3.0,
    "allocator_blend": 1.3,
}

# find each live label's index in the audit's 12-vector
def idx_of(name):
    # exact match first
    if name in labels_all:
        return labels_all.index(name)
    # substring fallback
    for i, lb in enumerate(labels_all):
        if name in lb or lb in name:
            return i
    raise KeyError(name)

idxs = [idx_of(n) for n in LIVE]
print("label resolution:")
for n, i in zip(LIVE, idxs):
    print(f"  {n:30s} -> audit[{i}] = {labels_all[i]}")

n = len(LIVE)
# 8x8 correlation submatrix
R = [[R_all[idxs[a]][idxs[b]] for b in range(n)] for a in range(n)]

# relative vol proxy: a strategy's daily return vol is unknown in absolute terms
# from Sharpe alone (Sharpe = mean/vol). For ERC we need vols. Two honest options:
#  (A) PURE-CORRELATION ERC: set all vols equal (vol drops out) -> weights driven
#      purely by the correlation structure. This is the cleanest "diversification"
#      reading and is robust (doesn't need a vol estimate we don't have on a
#      common scale). We use this as the PRIMARY.
#  (B) vol-aware: would need the daily std series. Not in the JSON. Skip.
# So: Sigma = R (unit vol). ERC on the correlation matrix.
Sigma = [row[:] for row in R]

def matvec(Mx, v):
    return [sum(Mx[i][j]*v[j] for j in range(len(v))) for i in range(len(v))]

def erc_weights(Sigma, iters=20000, tol=1e-12):
    """Cyclical coordinate descent for ERC (long-only, fully-invested).
    Maillard et al. 2010 fixed point: w_i <- TC_i / (Sigma w)_i style. We use the
    well-known multiplicative update that converges to ERC for PSD Sigma."""
    m = len(Sigma)
    w = [1.0/m]*m
    for it in range(iters):
        Sw = matvec(Sigma, w)
        # target: equal risk contribution. update w_i proportional to w_i / (Sigma w)_i? 
        # Use the standard fixed-point: w_i_new ∝ w_i * (sigma_target) ... 
        # Robust variant: w_i <- w_i * ( (1/m) / (w_i * Sw_i / sum_k w_k Sw_k) )^0.5
        port_var = sum(w[k]*Sw[k] for k in range(m))
        rc = [w[k]*Sw[k]/port_var for k in range(m)]  # risk-contribution fractions, sum=1
        # multiplicative pull toward 1/m each
        new = [w[k] * (( (1.0/m) / rc[k]) ** 0.5) for k in range(m)]
        s = sum(new)
        new = [x/s for x in new]
        diff = max(abs(new[k]-w[k]) for k in range(m))
        w = new
        if diff < tol:
            break
    return w, it

w_risk, iters_used = erc_weights(Sigma)
# verify risk contributions
Sw = matvec(Sigma, w_risk)
pv = sum(w_risk[k]*Sw[k] for k in range(n))
rc = [w_risk[k]*Sw[k]/pv for k in range(n)]

print(f"\nERC converged in {iters_used} iters. Risk-contribution spread: "
      f"min={min(rc):.4f} max={max(rc):.4f} (target {1/n:.4f})")

# Translate risk-weights -> CAPITAL, dividing out leverage so equal RISK maps to
# the right capital (a 3x sleeve needs 1/3 the capital for the same risk).
cap_raw = [w_risk[i] / LEVERAGE[LIVE[i]] for i in range(n)]
scap = sum(cap_raw)
BUDGET = 800.0
cap = [BUDGET * c/scap for c in cap_raw]

# effective N bets of the ERC-weighted book (participation ratio under R)
def eff_n(weights, Rm):
    # normalized weights
    s = sum(weights); wn = [x/s for x in weights]
    var = sum(wn[i]*wn[j]*Rm[i][j] for i in range(len(wn)) for j in range(len(wn)))
    # sum of squared *risk* shares ~ HHI; eff bets ~ 1/HHI on risk contributions
    Swn = matvec(Rm, wn)
    pv2 = sum(wn[k]*Swn[k] for k in range(len(wn)))
    rcn = [wn[k]*Swn[k]/pv2 for k in range(len(wn))]
    hhi = sum(x*x for x in rcn)
    return 1.0/hhi

en_flat = eff_n([1.0]*n, R)
en_erc = eff_n(w_risk, R)

print("\n=== ERC RESULT (8 live strategies) ===")
print(f"{'strategy':30s} {'risk_w':>8s} {'RC':>7s} {'lev':>4s} {'cap$':>8s}")
for i in range(n):
    print(f"{LIVE[i]:30s} {w_risk[i]*100:7.2f}% {rc[i]*100:6.2f}% "
          f"{LEVERAGE[LIVE[i]]:4.1f} {cap[i]:8.2f}")
print(f"{'TOTAL':30s} {'':8s} {'':7s} {'':4s} {sum(cap):8.2f}")
print(f"\nEffective bets (risk): flat-weight={en_flat:.2f}  ERC-weight={en_erc:.2f}")

out = {
    "method": "ERC on structural backtested correlation submatrix (4111d), "
              "leverage-adjusted capital translation, $800 budget",
    "live": LIVE,
    "corr_submatrix": R,
    "risk_weights": {LIVE[i]: w_risk[i] for i in range(n)},
    "risk_contributions": {LIVE[i]: rc[i] for i in range(n)},
    "leverage": LEVERAGE,
    "capital_usd": {LIVE[i]: round(cap[i], 2) for i in range(n)},
    "eff_bets_flat": en_flat,
    "eff_bets_erc": en_erc,
    "budget_usd": BUDGET,
}
json.dump(out, open(WS / "reports/_erc_weights.json", "w"), indent=2)
print("\nwrote reports/_erc_weights.json")
