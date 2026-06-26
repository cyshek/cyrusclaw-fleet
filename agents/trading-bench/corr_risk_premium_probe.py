"""Implied-realized correlation SPREAD probe (correlation risk premium).

RESEARCH-ONLY pre-committed prototype-gate. No trades, no config, no protected
files touched. Reads:
  - data_cache/cboe/COR1M_History.csv   (CBOE 1M implied index correlation)
  - runner.daily_bars_cache.get_daily   (Yahoo adjclose for SPY + 9 sectors)

Builds S(d) = z(COR1M_implied) - z(realized_avg_pairwise_corr) over the common
span, then runs:
  (1) ORTHOGONALITY: corr(S, SPY-63d-ret) and corr(S, SPY/SMA200).  GATE |corr|<0.3 both.
  (2) FORWARD-SORT: quintiles of S vs mean forward SPY return at h in {5,21,63}.
  (3) HONESTY: Q5-Q1 h=21 t-stat (Newey-West) + n; IS/OOS split pre-2016 / 2016+.
  (4) NO-LOOKAHEAD: signal at d, forward return strictly d+1..d+h.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from runner.daily_bars_cache import get_daily

WORKSPACE = Path(__file__).resolve().parent
COR1M_PATH = WORKSPACE / "data_cache" / "cboe" / "COR1M_History.csv"

SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB"]
N_REALIZED = 21          # trailing window for realized corr (match COR1M 1-month)
SMA_WIN = 200            # SPY trend proxy (ii)
TREND_RET_WIN = 63       # SPY trend proxy (i)
HORIZONS = [5, 21, 63]
OOS_SPLIT = "2016-01-01"


# --------------------------------------------------------------------------- #
# small stats helpers (no numpy dependency assumptions; use math only)
# --------------------------------------------------------------------------- #
def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs)


def std(xs: List[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def zscore_full(xs: List[float]) -> List[float]:
    m = mean(xs)
    s = std(xs)
    if not math.isfinite(s) or s == 0:
        return [0.0 for _ in xs]
    return [(x - m) / s for x in xs]


# --------------------------------------------------------------------------- #
# data loaders
# --------------------------------------------------------------------------- #
def load_cor1m() -> Dict[str, float]:
    """Return {iso_date: close} for COR1M. Source dates are MM/DD/YYYY."""
    out: Dict[str, float] = {}
    with COR1M_PATH.open() as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            ds = row["DATE"].strip()
            cs = row["CLOSE"].strip()
            if not ds or not cs:
                continue
            try:
                dt = datetime.strptime(ds, "%m/%d/%Y").date()
                val = float(cs)
            except ValueError:
                continue
            out[dt.isoformat()] = val
    return out


def load_adjclose(symbol: str) -> Dict[str, float]:
    """Return {iso_date: adjclose} for a symbol."""
    out: Dict[str, float] = {}
    for bar in get_daily(symbol):
        ac = bar.get("adjclose")
        if ac is not None:
            out[bar["date"]] = float(ac)
    return out


# --------------------------------------------------------------------------- #
# realized avg pairwise correlation (strictly trailing)
# --------------------------------------------------------------------------- #
def build_log_returns(series: Dict[str, float], dates: List[str]) -> Dict[str, float]:
    """Daily log returns keyed by the date the return is realized (close-to-close).

    ret[d_i] = ln(P[d_i] / P[d_{i-1}]) where d_{i-1} is the prior available date
    in `dates`. The first date has no return.
    """
    out: Dict[str, float] = {}
    prev: Optional[float] = None
    for d in dates:
        p = series.get(d)
        if p is None or p <= 0:
            prev = p if (p is not None and p > 0) else prev
            continue
        if prev is not None and prev > 0:
            out[d] = math.log(p / prev)
        prev = p
    return out


def avg_pairwise_corr(window_returns: Dict[str, List[float]]) -> Optional[float]:
    """Mean off-diagonal Pearson corr across the sector return vectors.

    window_returns: {sector: [r_t...]} all the SAME length (aligned dates).
    Returns None if fewer than 2 sectors have non-degenerate variance.
    """
    syms = [s for s in window_returns if len(window_returns[s]) >= 3
            and std(window_returns[s]) > 0]
    if len(syms) < 2:
        return None
    vals: List[float] = []
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            c = pearson(window_returns[syms[i]], window_returns[syms[j]])
            if math.isfinite(c):
                vals.append(c)
    if not vals:
        return None
    return mean(vals)


def build_realized_corr_series(
    sector_rets: Dict[str, Dict[str, float]],
    trade_dates: List[str],
    window: int,
) -> Dict[str, float]:
    """For each date d in trade_dates, realized avg pairwise corr over the
    trailing `window` aligned return observations ENDING at d (inclusive).

    Strictly trailing: only returns on dates <= d are used. The return on date d
    is the close-to-close move realized AT d's close (knowable EOD d).
    """
    # Precompute, per sector, the ordered list of (date, ret) it actually has.
    out: Dict[str, float] = {}
    # Build an index over trade_dates for fast trailing-window slicing.
    n = len(trade_dates)
    for idx in range(n):
        d = trade_dates[idx]
        # trailing window of dates ending at d (inclusive): dates[idx-window+1 .. idx]
        lo = idx - window + 1
        if lo < 0:
            continue
        win_dates = trade_dates[lo: idx + 1]
        # For each sector, collect the returns on exactly these dates; require
        # all sectors to have a return on each window date (drop a date if any
        # sector is missing it) so vectors stay aligned.
        # First, find the set of window dates where ALL sectors have a return.
        good_dates = [wd for wd in win_dates
                      if all(wd in sector_rets[s] for s in SECTORS)]
        if len(good_dates) < 3:
            continue
        window_returns = {s: [sector_rets[s][wd] for wd in good_dates] for s in SECTORS}
        rho = avg_pairwise_corr(window_returns)
        if rho is not None and math.isfinite(rho):
            out[d] = rho
    return out


# --------------------------------------------------------------------------- #
# SPY trend proxies + forward returns
# --------------------------------------------------------------------------- #
def build_spy_trend(spy: Dict[str, float], dates: List[str]
                    ) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Return (ret63, sma_ratio) keyed by date, strictly trailing.

    ret63[d]   = P[d]/P[d-63td] - 1   (63 trading days back within `dates`)
    sma_ratio[d] = P[d] / mean(P[d-199..d])   (200td SMA incl. d)
    Both use only closes <= d.
    """
    ret63: Dict[str, float] = {}
    sma_ratio: Dict[str, float] = {}
    n = len(dates)
    # Build aligned price array (forward-filled to the trade-date axis already).
    prices = [spy.get(d) for d in dates]
    for idx in range(n):
        d = dates[idx]
        p = prices[idx]
        if p is None or p <= 0:
            continue
        # 63td trailing return
        if idx - TREND_RET_WIN >= 0:
            p0 = prices[idx - TREND_RET_WIN]
            if p0 is not None and p0 > 0:
                ret63[d] = p / p0 - 1.0
        # 200td SMA ratio
        if idx - (SMA_WIN - 1) >= 0:
            window_p = [prices[k] for k in range(idx - SMA_WIN + 1, idx + 1)]
            if all(x is not None and x > 0 for x in window_p):
                sma = mean(window_p)  # type: ignore[arg-type]
                if sma > 0:
                    sma_ratio[d] = p / sma
    return ret63, sma_ratio


def build_forward_returns(spy: Dict[str, float], dates: List[str], h: int
                          ) -> Dict[str, float]:
    """fwd[d] = P[d+h]/P[d] - 1 where d+h is h trading days AFTER d in `dates`.

    The return window is strictly d+1..d+h (close at d -> close at d+h). Signal
    at d, return starts the next day. No overlap leak with the d-dated signal.
    """
    out: Dict[str, float] = {}
    n = len(dates)
    prices = [spy.get(d) for d in dates]
    for idx in range(n - h):
        d = dates[idx]
        p0 = prices[idx]
        p1 = prices[idx + h]
        if p0 is not None and p0 > 0 and p1 is not None and p1 > 0:
            out[d] = p1 / p0 - 1.0
    return out


# --------------------------------------------------------------------------- #
# Newey-West t-stat for a mean (HAC, lag = h to cover overlap in forward rets)
# --------------------------------------------------------------------------- #
def nw_tstat_mean(xs: List[float], lag: int) -> Tuple[float, float, float]:
    """Return (mean, se_nw, t). HAC/Newey-West SE of the sample mean with
    Bartlett kernel up to `lag`. Falls back to plain SE if lag<=0."""
    n = len(xs)
    if n < 5:
        return (mean(xs) if xs else float("nan"), float("nan"), float("nan"))
    m = mean(xs)
    e = [x - m for x in xs]
    gamma0 = sum(v * v for v in e) / n
    var = gamma0
    if lag > 0:
        for k in range(1, min(lag, n - 1) + 1):
            w = 1.0 - k / (lag + 1.0)
            gk = sum(e[t] * e[t - k] for t in range(k, n)) / n
            var += 2.0 * w * gk
    if var <= 0:
        return (m, float("nan"), float("nan"))
    se = math.sqrt(var / n)
    t = m / se if se > 0 else float("nan")
    return (m, se, t)


# --------------------------------------------------------------------------- #
# quintile sort
# --------------------------------------------------------------------------- #
def quintile_sort(
    signal: Dict[str, float],
    fwd: Dict[str, float],
    dates: List[str],
) -> Tuple[List[List[str]], List[float], List[Tuple[float, float]]]:
    """Sort the dates (that have BOTH signal and fwd) into quintiles by signal.

    Returns (quintile_date_lists, quintile_mean_fwd, [(signal_lo,signal_hi)...]).
    Quintile 0 = lowest signal, 4 = highest.
    """
    pairs = [(signal[d], fwd[d], d) for d in dates if d in signal and d in fwd]
    pairs.sort(key=lambda t: t[0])
    n = len(pairs)
    qlists: List[List[str]] = [[] for _ in range(5)]
    qmeans: List[float] = []
    qbounds: List[Tuple[float, float]] = []
    if n == 0:
        return qlists, [float("nan")] * 5, [(float("nan"), float("nan"))] * 5
    # cut points by rank
    for q in range(5):
        lo = q * n // 5
        hi = (q + 1) * n // 5
        chunk = pairs[lo:hi]
        qlists[q] = [c[2] for c in chunk]
        rets = [c[1] for c in chunk]
        qmeans.append(mean(rets) if rets else float("nan"))
        if chunk:
            qbounds.append((chunk[0][0], chunk[-1][0]))
        else:
            qbounds.append((float("nan"), float("nan")))
    return qlists, qmeans, qbounds


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    print("=" * 78)
    print("IMPLIED-REALIZED CORRELATION SPREAD PROBE (correlation risk premium)")
    print("=" * 78)

    # ---- load ----
    cor1m = load_cor1m()
    spy = load_adjclose("SPY")
    sector_px = {s: load_adjclose(s) for s in SECTORS}

    cor1m_dates = sorted(cor1m)
    spy_dates = sorted(spy)
    print(f"\nCOR1M span : {cor1m_dates[0]} -> {cor1m_dates[-1]}  (n={len(cor1m_dates)})")
    print(f"SPY span   : {spy_dates[0]} -> {spy_dates[-1]}  (n={len(spy_dates)})")
    for s in SECTORS:
        sd = sorted(sector_px[s])
        print(f"  {s}: {sd[0]} -> {sd[-1]}  (n={len(sd)})")

    # ---- trade-date axis: SPY dates within the common span ----
    sector_starts = [min(sector_px[s]) for s in SECTORS]
    sector_ends = [max(sector_px[s]) for s in SECTORS]
    common_start = max(cor1m_dates[0], spy_dates[0], max(sector_starts))
    common_end = min(cor1m_dates[-1], spy_dates[-1], min(sector_ends))
    print(f"\nCommon span: {common_start} -> {common_end}")

    # Master axis = SPY trading dates in [common_start, common_end].
    axis = [d for d in spy_dates if common_start <= d <= common_end]
    print(f"Trade-date axis (SPY): n={len(axis)}")

    # ---- realized avg pairwise corr (strictly trailing, N=21) ----
    # Build per-sector log returns on the SPY axis (close-to-close on axis dates).
    sector_rets = {s: build_log_returns(sector_px[s], axis) for s in SECTORS}
    realized = build_realized_corr_series(sector_rets, axis, N_REALIZED)
    print(f"Realized-corr series: n={len(realized)} "
          f"(first {min(realized) if realized else 'NA'})")

    # ---- align COR1M onto axis dates (exact-date match; COR1M is daily) ----
    # We only keep axis dates where BOTH legs exist.
    both_dates = [d for d in axis if d in cor1m and d in realized]
    print(f"Dates with BOTH implied+realized: n={len(both_dates)} "
          f"({both_dates[0]} -> {both_dates[-1]})")

    implied_vals = [cor1m[d] for d in both_dates]
    realized_vals = [realized[d] for d in both_dates]

    # quick sanity on scales
    print(f"\nCOR1M close   : mean={mean(implied_vals):.2f} sd={std(implied_vals):.2f} "
          f"min={min(implied_vals):.2f} max={max(implied_vals):.2f}")
    print(f"Realized corr : mean={mean(realized_vals):.3f} sd={std(realized_vals):.3f} "
          f"min={min(realized_vals):.3f} max={max(realized_vals):.3f}")
    print(f"raw corr(implied, realized) = {pearson(implied_vals, realized_vals):+.3f}")

    # ---- normalization: z-score BOTH legs over the full common span ----
    z_impl = zscore_full(implied_vals)
    z_real = zscore_full(realized_vals)
    spread = {both_dates[i]: z_impl[i] - z_real[i] for i in range(len(both_dates))}
    spread_vals = [spread[d] for d in both_dates]
    print(f"\nSPREAD S=z(impl)-z(real): mean={mean(spread_vals):+.4f} "
          f"sd={std(spread_vals):.4f} min={min(spread_vals):+.3f} max={max(spread_vals):+.3f}")

    # ---- SPY trend proxies on axis ----
    ret63, sma_ratio = build_spy_trend(spy, axis)

    # ---- (1) ORTHOGONALITY ----
    print("\n" + "-" * 78)
    print("(1) ORTHOGONALITY  (gate: |corr| < 0.30 on BOTH)")
    print("-" * 78)
    d_a = [d for d in both_dates if d in ret63]
    corr_ret63 = pearson([spread[d] for d in d_a], [ret63[d] for d in d_a])
    d_b = [d for d in both_dates if d in sma_ratio]
    corr_sma = pearson([spread[d] for d in d_b], [sma_ratio[d] for d in d_b])
    print(f"corr(S, SPY 63d-return) = {corr_ret63:+.3f}  "
          f"[n={len(d_a)}]  {'PASS' if abs(corr_ret63) < 0.30 else 'FAIL'}")
    print(f"corr(S, SPY/SMA200)     = {corr_sma:+.3f}  "
          f"[n={len(d_b)}]  {'PASS' if abs(corr_sma) < 0.30 else 'FAIL'}")
    orth_pass = abs(corr_ret63) < 0.30 and abs(corr_sma) < 0.30
    print(f"ORTHOGONALITY GATE: {'PASS' if orth_pass else 'FAIL'}")

    # Also report corr of the RAW implied level and realized level vs SPY trend
    # to contrast with the AQR finding (the level had high inverse-SPY content).
    impl_map = {both_dates[i]: implied_vals[i] for i in range(len(both_dates))}
    real_map = {both_dates[i]: realized_vals[i] for i in range(len(both_dates))}
    print("\n  [context] raw-LEVEL correlations vs SPY trend (expect implied LEVEL "
          "to carry inverse-SPY content the SPREAD should strip):")
    print(f"    corr(COR1M_impl_level, SPY63d)   = "
          f"{pearson([impl_map[d] for d in d_a], [ret63[d] for d in d_a]):+.3f}")
    print(f"    corr(COR1M_impl_level, SPY/SMA)  = "
          f"{pearson([impl_map[d] for d in d_b], [sma_ratio[d] for d in d_b]):+.3f}")
    print(f"    corr(realized_level,   SPY63d)   = "
          f"{pearson([real_map[d] for d in d_a], [ret63[d] for d in d_a]):+.3f}")
    print(f"    corr(realized_level,   SPY/SMA)  = "
          f"{pearson([real_map[d] for d in d_b], [sma_ratio[d] for d in d_b]):+.3f}")

    # ---- (2) FORWARD-RETURN SORT ----
    print("\n" + "-" * 78)
    print("(2) FORWARD-RETURN QUINTILE SORT  (gate: ~monotone at h=21, same sign h=5/63)")
    print("-" * 78)
    fwd = {h: build_forward_returns(spy, axis, h) for h in HORIZONS}

    # Full-sample table
    print("\nFULL SAMPLE  (mean forward SPY return %, by S-quintile)")
    print(f"{'quintile':>9} | {'S-range':>16} | "
          + " | ".join(f"h={h:>2} %" for h in HORIZONS) + " |   n")
    qres: Dict[int, Tuple] = {}
    for h in HORIZONS:
        qlists, qmeans, qbounds = quintile_sort(spread, fwd[h], both_dates)
        qres[h] = (qlists, qmeans, qbounds)
    # use h=21 quintile membership/bounds for the row labels & n
    qlists21, qmeans21, qbounds21 = qres[21]
    for q in range(5):
        lo, hi = qbounds21[q]
        row = f"{('Q'+str(q+1)):>9} | [{lo:+6.2f},{hi:+6.2f}] | "
        cells = []
        for h in HORIZONS:
            _, qm, _ = qres[h]
            cells.append(f"{qm[q]*100:+7.3f}")
        row += " | ".join(cells)
        row += f" | {len(qlists21[q]):>4}"
        print(row)
    # Q5 - Q1 spread per horizon
    print(f"\n{'Q5-Q1':>9} | {'':>16} | "
          + " | ".join(f"{(qres[h][1][4]-qres[h][1][0])*100:+7.3f}" for h in HORIZONS)
          + " |")

    # Monotonicity check at h=21 (Spearman-like: count of increasing steps)
    steps = [qmeans21[q + 1] - qmeans21[q] for q in range(4)]
    n_up = sum(1 for s in steps if s > 0)
    n_dn = sum(1 for s in steps if s < 0)
    mono = "MONOTONE-UP" if n_up == 4 else ("MONOTONE-DOWN" if n_dn == 4
            else f"NON-MONOTONE (up={n_up}/4, dn={n_dn}/4)")
    q5q1_21 = qmeans21[4] - qmeans21[0]
    # sign consistency across horizons
    signs = {}
    for h in HORIZONS:
        qm = qres[h][1]
        signs[h] = (qm[4] - qm[0])
    sign_consistent = (len({1 if signs[h] > 0 else -1 for h in HORIZONS}) == 1)
    print(f"\nh=21 monotonicity: {mono}")
    print(f"h=21 Q5-Q1 = {q5q1_21*100:+.3f}%   "
          f"signs(h=5,21,63) = "
          f"{signs[5]*100:+.3f} / {signs[21]*100:+.3f} / {signs[63]*100:+.3f}  "
          f"-> {'SIGN-CONSISTENT' if sign_consistent else 'SIGN-FLIPS'}")

    # ---- (3) STATISTICAL HONESTY: Q5-Q1 t-stat at h=21 (Newey-West, lag=21) ----
    print("\n" + "-" * 78)
    print("(3) STATISTICAL HONESTY  (Q5-Q1 forward return at h=21, Newey-West t)")
    print("-" * 78)
    # Per-observation Q5 and Q1 forward returns at h=21.
    q1_dates = set(qlists21[0])
    q5_dates = set(qlists21[4])
    fwd21 = fwd[21]
    q1_rets = [fwd21[d] for d in both_dates if d in q1_dates and d in fwd21]
    q5_rets = [fwd21[d] for d in both_dates if d in q5_dates and d in fwd21]
    # Build a paired-ish difference series by pooling: mean(Q5)-mean(Q1) with the
    # combined-sample HAC SE. We t-test each leg's mean and the difference of
    # independent means with NW SEs (lag=21 to absorb the h=21 overlap).
    m5, se5, t5 = nw_tstat_mean(q5_rets, lag=21)
    m1, se1, t1 = nw_tstat_mean(q1_rets, lag=21)
    diff = m5 - m1
    se_diff = math.sqrt((se5 ** 2 if math.isfinite(se5) else 0.0)
                        + (se1 ** 2 if math.isfinite(se1) else 0.0))
    t_diff = diff / se_diff if se_diff > 0 else float("nan")
    print(f"Q1 mean fwd(h=21) = {m1*100:+.3f}%  NW-SE={se1*100:.3f}  t={t1:+.2f}  "
          f"n={len(q1_rets)}")
    print(f"Q5 mean fwd(h=21) = {m5*100:+.3f}%  NW-SE={se5*100:.3f}  t={t5:+.2f}  "
          f"n={len(q5_rets)}")
    print(f"Q5-Q1            = {diff*100:+.3f}%  NW-SE(indep)={se_diff*100:.3f}  "
          f"t_diff={t_diff:+.2f}")
    print(f"(NW lag=21 Bartlett; n_total_both={len(both_dates)}; "
          f"overlapping daily obs, so effective independent n ~ n/21 ~ "
          f"{len(both_dates)//21})")

    # ---- IS/OOS sign-stability: pre-2016 vs 2016+ ----
    print("\n" + "-" * 78)
    print(f"IS/OOS SIGN STABILITY  (split at {OOS_SPLIT})")
    print("-" * 78)
    for label, lo_d, hi_d in [("PRE-2016 ", both_dates[0], OOS_SPLIT),
                               ("2016+    ", OOS_SPLIT, "2099-01-01")]:
        sub = [d for d in both_dates if lo_d <= d < hi_d] if label.startswith("PRE") \
              else [d for d in both_dates if d >= lo_d]
        if len(sub) < 50:
            print(f"{label}: too few obs (n={len(sub)})")
            continue
        # z-score the spread WITHIN the subsample? No — keep the same full-sample S
        # (the signal a live system would have used is the rolling/standardized one;
        #  for a sign-stability check we re-sort the EXISTING S within the subsample).
        ql, qm, qb = quintile_sort(spread, fwd[21], sub)
        q5q1 = qm[4] - qm[0]
        st = [qm[q + 1] - qm[q] for q in range(4)]
        nu = sum(1 for s in st if s > 0)
        mono_sub = "mono-up" if nu == 4 else (f"non-mono(up={nu}/4)")
        print(f"{label}: n={len(sub):4d}  Q1={qm[0]*100:+.3f}%  Q5={qm[4]*100:+.3f}%  "
              f"Q5-Q1={q5q1*100:+.3f}%  [{mono_sub}]")

    # ---- (4) NO-LOOKAHEAD STATEMENT ----
    print("\n" + "-" * 78)
    print("(4) NO-LOOKAHEAD")
    print("-" * 78)
    print("- COR1M close on date d is an implied/quoted index, knowable EOD d "
          "(not revised).")
    print("- Realized corr on date d uses sector log-returns through d's close "
          "(EOD-d knowable), trailing window only (dates <= d).")
    print("- SPY trend proxies (63d-ret, /SMA200) use closes <= d only.")
    print("- Forward returns use closes strictly d+1..d+h (P[d]->P[d+h]); signal "
          "at d, return starts d+1 -> NO overlap leak between signal and return.")
    print("- Sector + SPY adjclose are PIT by construction (a close at d was "
          "knowable at d).")

    # ---- machine-readable summary line for the report ----
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"ORTH: corr(S,SPY63d)={corr_ret63:+.3f} corr(S,SPY/SMA200)={corr_sma:+.3f} "
          f"-> {'PASS' if orth_pass else 'FAIL'}")
    print(f"SORT h=21: {mono}  Q5-Q1={q5q1_21*100:+.3f}%  t_diff={t_diff:+.2f}  "
          f"sign-consistent={sign_consistent}")


if __name__ == "__main__":
    main()
