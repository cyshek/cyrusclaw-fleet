"""Robustness sensitivity for the corr-risk-premium SPREAD probe.

Confirms the forward-sort FAILURE is not an artifact of the ONE normalization
choice (full-sample z-z). Re-runs the quintile sort under two alternative
defensible normalizations:
  (A) ROLLING z: z both legs over a trailing 252d window (causal, no lookahead),
      difference. This is what a live system would actually use.
  (B) PERCENTILE-RANK spread: trailing-252d percentile rank of each leg,
      difference. Scale-free, robustness against the CBOE-scale drift.
Also a SIGN-AGNOSTIC monotonicity readout so we don't bias toward one direction.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import corr_risk_premium_probe as P


def trailing_z(vals: List[float], win: int) -> List[float]:
    """Causal trailing z-score: z[i] uses vals[i-win+1..i]. NaN-ish (0) until
    a full window exists. No lookahead."""
    out: List[float] = []
    for i in range(len(vals)):
        lo = i - win + 1
        if lo < 0:
            out.append(float("nan"))
            continue
        w = vals[lo:i + 1]
        m = P.mean(w)
        s = P.std(w)
        out.append((vals[i] - m) / s if (math.isfinite(s) and s > 0) else float("nan"))
    return out


def trailing_pctrank(vals: List[float], win: int) -> List[float]:
    """Causal trailing percentile rank in [0,1]: fraction of trailing-window
    values <= current. No lookahead."""
    out: List[float] = []
    for i in range(len(vals)):
        lo = i - win + 1
        if lo < 0:
            out.append(float("nan"))
            continue
        w = vals[lo:i + 1]
        cur = vals[i]
        rank = sum(1 for x in w if x <= cur) / len(w)
        out.append(rank)
    return out


def sort_report(name: str, spread: Dict[str, float], fwd: Dict[int, Dict[str, float]],
                dates: List[str]) -> None:
    print(f"\n--- {name} ---")
    qres = {}
    for h in P.HORIZONS:
        qres[h] = P.quintile_sort(spread, fwd[h], dates)
    ql21, qm21, qb21 = qres[21]
    print(f"{'q':>3} | " + " | ".join(f"h={h:>2}%" for h in P.HORIZONS) + " |   n")
    for q in range(5):
        cells = " | ".join(f"{qres[h][1][q]*100:+7.3f}" for h in P.HORIZONS)
        print(f"Q{q+1:>1} | {cells} | {len(ql21[q]):>4}")
    q5q1 = {h: (qres[h][1][4] - qres[h][1][0]) for h in P.HORIZONS}
    print("Q5-Q1| " + " | ".join(f"{q5q1[h]*100:+7.3f}" for h in P.HORIZONS) + " |")
    steps = [qm21[q + 1] - qm21[q] for q in range(4)]
    nu = sum(1 for s in steps if s > 0)
    mono = "MONO-UP" if nu == 4 else ("MONO-DN" if nu == 0 else f"NON-MONO(up={nu}/4)")
    signs = {1 if q5q1[h] > 0 else -1 for h in P.HORIZONS}
    print(f"h=21: {mono}  Q5-Q1={q5q1[21]*100:+.3f}%  "
          f"sign-consistent={len(signs)==1}")
    # NW t on Q5-Q1 at h=21
    q1d, q5d = set(ql21[0]), set(ql21[4])
    f21 = fwd[21]
    q1r = [f21[d] for d in dates if d in q1d and d in f21]
    q5r = [f21[d] for d in dates if d in q5d and d in f21]
    m5, se5, _ = P.nw_tstat_mean(q5r, lag=21)
    m1, se1, _ = P.nw_tstat_mean(q1r, lag=21)
    sd = math.sqrt(se5 ** 2 + se1 ** 2)
    print(f"      Q5-Q1 t_diff(NW lag21) = {((m5-m1)/sd) if sd>0 else float('nan'):+.2f}")


def main() -> None:
    cor1m = P.load_cor1m()
    spy = P.load_adjclose("SPY")
    sector_px = {s: P.load_adjclose(s) for s in P.SECTORS}

    cor1m_dates = sorted(cor1m)
    spy_dates = sorted(spy)
    sector_starts = [min(sector_px[s]) for s in P.SECTORS]
    sector_ends = [max(sector_px[s]) for s in P.SECTORS]
    common_start = max(cor1m_dates[0], spy_dates[0], max(sector_starts))
    common_end = min(cor1m_dates[-1], spy_dates[-1], min(sector_ends))
    axis = [d for d in spy_dates if common_start <= d <= common_end]

    sector_rets = {s: P.build_log_returns(sector_px[s], axis) for s in P.SECTORS}
    realized = P.build_realized_corr_series(sector_rets, axis, P.N_REALIZED)
    both = [d for d in axis if d in cor1m and d in realized]
    impl = [cor1m[d] for d in both]
    real = [realized[d] for d in both]

    fwd = {h: P.build_forward_returns(spy, axis, h) for h in P.HORIZONS}

    print("=" * 70)
    print("ROBUSTNESS: forward-sort under ALTERNATIVE normalizations")
    print(f"n_both={len(both)}  span {both[0]} -> {both[-1]}")
    print("=" * 70)

    # baseline (full z-z) for reference
    zi = P.zscore_full(impl)
    zr = P.zscore_full(real)
    s_full = {both[i]: zi[i] - zr[i] for i in range(len(both))}
    sort_report("BASELINE full-sample z(impl)-z(real)", s_full, fwd, both)

    # (A) rolling 252d z-z
    ziR = trailing_z(impl, 252)
    zrR = trailing_z(real, 252)
    s_roll = {both[i]: ziR[i] - zrR[i] for i in range(len(both))
              if math.isfinite(ziR[i]) and math.isfinite(zrR[i])}
    sort_report("(A) rolling-252d z(impl)-z(real)  [causal]", s_roll, fwd,
                [d for d in both if d in s_roll])

    # (B) rolling 252d percentile-rank spread
    piR = trailing_pctrank(impl, 252)
    prR = trailing_pctrank(real, 252)
    s_pct = {both[i]: piR[i] - prR[i] for i in range(len(both))
             if math.isfinite(piR[i]) and math.isfinite(prR[i])}
    sort_report("(B) rolling-252d pctrank(impl)-pctrank(real)  [causal]", s_pct, fwd,
                [d for d in both if d in s_pct])

    print("\nIf all three normalizations show non-monotone / sign-flipping / "
          "noise-level Q5-Q1 at h=21, the RED is robust to the normalization "
          "choice (not an artifact).")


if __name__ == "__main__":
    main()
