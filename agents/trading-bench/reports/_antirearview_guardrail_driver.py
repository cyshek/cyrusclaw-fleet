"""Anti-rearview allocator guardrail AUDIT (paper-research, read-only on engine).

BACKLOG P3 hygiene / AQR "Rearview Mirror" #5: does the live invvol_63d weighting
(inverse trailing-63d vol between the TQQQ vol-target sleeve and the sector-rotation
sleeve) over-react and abandon a diversifying sleeve right before it would have helped?
If so, does a cheap guardrail (min-weight FLOOR and/or longer SMOOTHING of the weight
signal) reduce that pathology WITHOUT degrading the validated operating point?

This driver READS/IMPORTS the validated engine (_allocator_blend_tests.py) and the live
tracker's invvol scheme; it reimplements NOTHING about the sleeves. It only:
  1. Builds the two sleeve daily-return streams via ab.build_sleeves() (validated).
  2. Reproduces the live invvol_63d weight function (identical to the tracker / engine
     main()), lookahead-safe: weights at a month-open use sleeve returns < that index.
  3. CHARACTERIZES the rearview risk: at each monthly rebalance, measures each sleeve's
     month-over-month weight change, isolates the biggest CUTS, and measures that
     sleeve's FORWARD 1/2/3-month standalone return after the cut vs unconditional.
  4. TESTS guardrail variants (floor, smoothing, combos) through the SAME engine
     (ab.blend_portfolio) on the SAME path, full + OOS (split 2018-12-31), net of cost.
  5. Reports full continuous-span Sharpe (fp_sharpe convention, ddof=1), OOS Sharpe,
     full+OOS maxDD, CAGR, and the rearview metric for each variant vs the baseline.

Honesty rails: headline Sharpe = full continuous-span (NEVER median-of-windows). Every
variant on the SAME path. No lookahead (smoothing uses only PAST weight vectors). A
guardrail that doesn't beat the unguarded baseline on DD/rearview (or breaks OOS) is a
CLEAN NO-OP.

WRITE: reports/_antirearview_guardrail_result.json (+ the verdict .md, written separately).
Run: python3 reports/_antirearview_guardrail_driver.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

import _allocator_blend_tests as ab  # validated engine (build_sleeves, blend_portfolio)

OOS_SPLIT = "2018-12-31"
VOL_LOOKBACK_DAYS = 63
BLEND_COST_BPS = 2.0
TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# fp_sharpe convention: full continuous-span, sample stdev (ddof=1), sqrt(252).
# This is the load-bearing ruler the task asks for. Applied IDENTICALLY to the
# baseline and every variant on the same path. (The engine's _stats_from_equity
# uses population stdev /n; on ~4100 points the two differ in the 4th decimal.)
# --------------------------------------------------------------------------- #
def fp_sharpe_from_equity(equity: List[float]) -> float:
    rets = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity)) if equity[i - 1] > 0]
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(TRADING_DAYS)


def maxdd_from_equity(equity: List[float]) -> float:
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < mdd:
            mdd = dd
    return mdd * 100.0


def cagr_from_equity(equity: List[float]) -> float:
    n = len(equity) - 1
    if n <= 0 or equity[0] <= 0:
        return 0.0
    years = n / TRADING_DAYS
    return ((equity[-1] / equity[0]) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0


def slice_idx(dates: List[str], start: str, end: str) -> Tuple[int, int]:
    import bisect
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    return lo, hi


def span_metrics(dates: List[str], equity: List[float], start: str, end: str) -> Dict:
    """fp-convention Sharpe + maxDD + CAGR over a date span [start, end] of the
    blend equity curve (rebased to span start)."""
    lo, hi = slice_idx(dates, start, end)
    if hi - lo < 3:
        return {"n": hi - lo, "sharpe": None, "maxdd_pct": None, "cagr_pct": None}
    base = equity[lo]
    sub = [v / base for v in equity[lo:hi]]
    return {
        "n": hi - lo,
        "sharpe": fp_sharpe_from_equity(sub),
        "maxdd_pct": maxdd_from_equity(sub),
        "cagr_pct": cagr_from_equity(sub),
    }


# --------------------------------------------------------------------------- #
# Month-open index list (first occurrence of each YYYY-MM) — same as engine.
# --------------------------------------------------------------------------- #
def month_open_indices(dates: List[str]) -> List[int]:
    mo: List[int] = []
    seen = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            mo.append(i)
    return mo


# --------------------------------------------------------------------------- #
# The live invvol_63d weight function (index 0 = TQQQ sleeve, 1 = rotation).
# IDENTICAL to runner/allocator_paper_tracker.invvol_wfn and engine main(). The
# returned weights at month-open idx use ONLY sleeve returns strictly < idx.
# --------------------------------------------------------------------------- #
def make_invvol_wfn(sleeves: List[List[float]], lookback: int) -> Callable[[int], List[float]]:
    def fn(idx: int) -> List[float]:
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - lookback)
        v0 = ab.annualized_vol(sleeves[0][lo:idx])
        v1 = ab.annualized_vol(sleeves[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0 / v0, 1.0 / v1
        s = iv0 + iv1
        return [iv0 / s, iv1 / s]
    return fn


# --------------------------------------------------------------------------- #
# GUARDRAIL transforms on the RAW invvol weight function.
#   floor: clamp each weight >= f, renormalize to sum 1 (two-sleeve: if f<=0.5 this
#          is feasible; f=0.5 forces fixed 50/50, the degenerate anchor).
#   smoothing: average the last K monthly RAW weight vectors (lookahead-safe — only
#          weight vectors at month-opens <= idx). EWMA variant: exponential decay.
#   longer vol lookback: just a different `lookback` in make_invvol_wfn (126/189d).
# All produced weight fns are pure functions of month-open idx using PAST data only.
# --------------------------------------------------------------------------- #
def apply_floor(w: List[float], f: float) -> List[float]:
    """Clamp each weight to >= f then renormalize to sum 1. For two sleeves with
    f in [0, 0.5] this always yields a valid simplex point; f=0.5 -> [0.5, 0.5]."""
    ns = len(w)
    if f * ns >= 1.0:
        # degenerate: equal weights (f>=1/ns means floor alone forces uniform)
        return [1.0 / ns] * ns
    clamped = [max(wi, f) for wi in w]
    s = sum(clamped)
    return [c / s for c in clamped]


def make_floored_wfn(base_fn: Callable[[int], List[float]], f: float) -> Callable[[int], List[float]]:
    def fn(idx: int) -> List[float]:
        return apply_floor(base_fn(idx), f)
    return fn


def make_smoothed_wfn(base_fn: Callable[[int], List[float]], mo_set: set,
                      k: int) -> Callable[[int], List[float]]:
    """Simple average of the RAW weight vectors at the last k month-opens that are
    <= idx (lookahead-safe: includes the current month-open's raw weight, which is
    itself computed from data < idx). For non-month-open idx (i==0 init) falls back
    to base_fn(idx)."""
    mo_sorted = sorted(mo_set)

    def fn(idx: int) -> List[float]:
        # collect month-open indices <= idx (chronological), take last k
        hist = [m for m in mo_sorted if m <= idx]
        if not hist:
            return base_fn(idx)
        use = hist[-k:]
        acc = [0.0, 0.0]
        for m in use:
            wv = base_fn(m)
            acc[0] += wv[0]
            acc[1] += wv[1]
        s0 = acc[0] / len(use)
        s1 = acc[1] / len(use)
        tot = s0 + s1
        return [s0 / tot, s1 / tot] if tot > 0 else [0.5, 0.5]
    return fn


def make_ewma_wfn(base_fn: Callable[[int], List[float]], mo_set: set,
                  alpha: float) -> Callable[[int], List[float]]:
    """EWMA of the RAW weight vectors over all month-opens <= idx with smoothing
    factor alpha (higher alpha = faster reaction). Lookahead-safe. alpha in (0,1]."""
    mo_sorted = sorted(mo_set)

    def fn(idx: int) -> List[float]:
        hist = [m for m in mo_sorted if m <= idx]
        if not hist:
            return base_fn(idx)
        ew = list(base_fn(hist[0]))
        for m in hist[1:]:
            wv = base_fn(m)
            ew[0] = alpha * wv[0] + (1 - alpha) * ew[0]
            ew[1] = alpha * wv[1] + (1 - alpha) * ew[1]
        tot = ew[0] + ew[1]
        return [ew[0] / tot, ew[1] / tot] if tot > 0 else [0.5, 0.5]
    return fn


# --------------------------------------------------------------------------- #
# Run one variant through the validated engine and collect metrics.
# --------------------------------------------------------------------------- #
def run_variant(name: str, dates: List[str], sleeves: List[List[float]],
                wfn: Callable[[int], List[float]]) -> Dict:
    b = ab.blend_portfolio(dates, sleeves, wfn,
                           blend_cost_bps=BLEND_COST_BPS,
                           vol_lookback_days=VOL_LOOKBACK_DAYS)
    eq = b["equity"]
    eqd = b["dates"]
    full_sharpe = fp_sharpe_from_equity(eq)
    full_mdd = maxdd_from_equity(eq)
    full_cagr = cagr_from_equity(eq)
    oos = span_metrics(eqd, eq, "2019-01-01", "2099-12-31")
    is_ = span_metrics(eqd, eq, "2000-01-01", OOS_SPLIT)
    # realized avg target weights from the weight log
    wl = b["weight_log"]
    avg_w_tqqq = sum(w["w"][0] for w in wl) / len(wl) if wl else None
    min_w_tqqq = min((w["w"][0] for w in wl), default=None)
    min_w_rot = min((w["w"][1] for w in wl), default=None)
    return {
        "name": name,
        "full": {"sharpe": full_sharpe, "maxdd_pct": full_mdd, "cagr_pct": full_cagr,
                 "total_return_pct": (eq[-1] / eq[0] - 1.0) * 100.0,
                 "engine_sharpe_popstdev": b["stats"]["sharpe"]},
        "is_2010_2018": is_,
        "oos_2019_today": oos,
        "n_rebal": b["n_rebal"],
        "avg_turnover_per_rebal": b["avg_turnover_per_rebal"],
        "avg_w_tqqq": avg_w_tqqq,
        "min_w_tqqq_target": min_w_tqqq,
        "min_w_rot_target": min_w_rot,
    }


# --------------------------------------------------------------------------- #
# PART 1: Rearview-risk characterization.
# At each monthly rebalance we know the RAW target weight vector. Compute the
# month-over-month change in each sleeve's weight. A "cut" of sleeve s at month m
# is a drop w_s(m) - w_s(m-1) < -threshold. We then measure that sleeve's FORWARD
# standalone return over the NEXT 1/2/3 calendar months (compounded daily sleeve
# returns from this month-open to the next 1/2/3 month-opens) and compare the
# distribution of forward returns AFTER a cut vs UNCONDITIONAL (all months).
#
# The classic rearview pathology = the allocator cuts a sleeve right before it
# rebounds, i.e. forward return AFTER a cut is systematically HIGHER than
# unconditional (you cut the diversifier just before it would have helped).
# Because inv-vol keys off VOLATILITY not return, the effect may be muted; we
# report it honestly either way. We also flag the specific shape: vol spikes at a
# sleeve's drawdown trough -> weight cut -> misses the recovery (forward return
# strongly positive right after the biggest cuts).
# --------------------------------------------------------------------------- #
def forward_sleeve_return(sleeve_r: List[float], mo: List[int], mo_pos: int,
                          horizon_months: int) -> float:
    """Compounded standalone return of one sleeve from month-open mo[mo_pos] to
    month-open mo[mo_pos + horizon_months] (exclusive of the start day's return,
    inclusive through the end month-open). Returns None if not enough future."""
    if mo_pos + horizon_months >= len(mo):
        return None
    i0 = mo[mo_pos]
    i1 = mo[mo_pos + horizon_months]
    g = 1.0
    for i in range(i0 + 1, i1 + 1):
        g *= (1.0 + sleeve_r[i])
    return g - 1.0


def characterize_rearview(dates: List[str], sleeves: List[List[float]],
                          raw_wfn: Callable[[int], List[float]]) -> Dict:
    mo = month_open_indices(dates)
    # raw weight vector at each month-open
    wvecs = [raw_wfn(m) for m in mo]
    sleeve_names = ["tqqq", "rot"]
    out: Dict = {"n_months": len(mo), "per_sleeve": {}}

    for s in (0, 1):
        # month-over-month weight change for sleeve s, indexed by mo position (>=1)
        dweights = []  # (mo_pos, dw) for mo_pos>=1
        for p in range(1, len(mo)):
            dw = wvecs[p][s] - wvecs[p - 1][s]
            dweights.append((p, dw))

        # unconditional forward returns of sleeve s at every month-open with future
        uncond = {h: [] for h in (1, 2, 3)}
        for p in range(len(mo)):
            for h in (1, 2, 3):
                fr = forward_sleeve_return(sleeves[s], mo, p, h)
                if fr is not None:
                    uncond[h].append(fr)

        sleeve_block: Dict = {
            "unconditional_fwd_ret": {
                str(h): {"mean": _mean(uncond[h]), "median": _median(uncond[h]),
                         "n": len(uncond[h])}
                for h in (1, 2, 3)
            },
            "by_cut_threshold": {},
            "biggest_cuts": [],
        }

        # forward returns conditioned on a cut > threshold
        for thr in (0.02, 0.05, 0.08, 0.10):
            cut_positions = [p for (p, dw) in dweights if dw < -thr]
            cond = {h: [] for h in (1, 2, 3)}
            for p in cut_positions:
                for h in (1, 2, 3):
                    fr = forward_sleeve_return(sleeves[s], mo, p, h)
                    if fr is not None:
                        cond[h].append(fr)
            sleeve_block["by_cut_threshold"]["gt_%.2f" % thr] = {
                "n_cuts": len(cut_positions),
                "fwd_ret": {
                    str(h): {
                        "mean": _mean(cond[h]), "median": _median(cond[h]), "n": len(cond[h]),
                        # rearview signal: cond_mean - uncond_mean (positive = cut before rebound)
                        "mean_minus_uncond": (
                            (_mean(cond[h]) - _mean(uncond[h]))
                            if cond[h] and uncond[h] else None),
                    }
                    for h in (1, 2, 3)
                },
            }

        # the 8 single biggest cuts (most negative dw) with their forward returns + date
        biggest = sorted(dweights, key=lambda x: x[1])[:8]
        for (p, dw) in biggest:
            sleeve_block["biggest_cuts"].append({
                "date": dates[mo[p]],
                "weight_before": round(wvecs[p - 1][s], 4),
                "weight_after": round(wvecs[p][s], 4),
                "weight_drop": round(dw, 4),
                "fwd_ret_1m": forward_sleeve_return(sleeves[s], mo, p, 1),
                "fwd_ret_3m": forward_sleeve_return(sleeves[s], mo, p, 3),
            })

        out["per_sleeve"][sleeve_names[s]] = sleeve_block

    return out


def _mean(xs: List[float]):
    return (sum(xs) / len(xs)) if xs else None


def _median(xs: List[float]):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #
def main():
    print(">>> build_sleeves() ...", flush=True)
    S = ab.build_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    sleeves = [tqqq_r, rot_r]
    mo = month_open_indices(dates)
    mo_set = set(mo)

    raw_wfn = make_invvol_wfn(sleeves, VOL_LOOKBACK_DAYS)

    out: Dict = {
        "meta": {
            "common_window": [dates[0], dates[-1]],
            "n_days": len(dates),
            "n_months": len(mo),
            "oos_split": OOS_SPLIT,
            "vol_lookback_days": VOL_LOOKBACK_DAYS,
            "blend_cost_bps": BLEND_COST_BPS,
            "sharpe_convention": "fp_sharpe: full continuous-span, sample stdev (ddof=1), sqrt(252)",
            "note": ("Baseline reproduces the 2026-06-21 report EXACTLY when truncated to "
                     "the report as-of date 2026-06-18 (full Sharpe 1.0144, OOS 1.1466, "
                     "maxDD -23.90%). On the current full cache (extra days) the recomputed "
                     "baseline is the apples-to-apples reference; ALL variants run on this "
                     "same path."),
        },
    }

    # ---- baseline (unguarded live invvol_63d) ----
    print(">>> baseline invvol_63d ...", flush=True)
    baseline = run_variant("baseline_invvol_63d", dates, sleeves, raw_wfn)
    out["baseline"] = baseline
    b = baseline["full"]
    print("   baseline: full Sharpe %.4f maxDD %.2f%% CAGR %.2f%% | OOS Sharpe %.4f maxDD %.2f%%" % (
        b["sharpe"], b["maxdd_pct"], b["cagr_pct"],
        baseline["oos_2019_today"]["sharpe"], baseline["oos_2019_today"]["maxdd_pct"]))
    print("   baseline realized avg w_tqqq=%.4f  min target w_tqqq=%.4f / w_rot=%.4f" % (
        baseline["avg_w_tqqq"], baseline["min_w_tqqq_target"], baseline["min_w_rot_target"]))


    # ---- PART 1: rearview characterization ----
    print(">>> characterizing rearview risk ...", flush=True)
    out["rearview_characterization"] = characterize_rearview(dates, sleeves, raw_wfn)
    for sname, blk in out["rearview_characterization"]["per_sleeve"].items():
        u = blk["unconditional_fwd_ret"]
        c = blk["by_cut_threshold"].get("gt_0.05", {})
        cr = c.get("fwd_ret", {})
        print("   [%s] uncond 1m mean=%s | after >5%% cut (n=%s) 1m mean=%s (delta %s)" % (
            sname,
            _fmt(u["1"]["mean"]), c.get("n_cuts"),
            _fmt(cr.get("1", {}).get("mean")),
            _fmt(cr.get("1", {}).get("mean_minus_uncond"))))

    # ---- PART 2: guardrail variants ----
    print(">>> running guardrail variants ...", flush=True)
    variants: Dict = {}

    # (a) MIN-WEIGHT FLOOR f in {0.10,0.15,0.20,0.25,0.30,0.50}
    for f in (0.10, 0.15, 0.20, 0.25, 0.30, 0.50):
        nm = "floor_%.2f" % f
        wfn = make_floored_wfn(raw_wfn, f)
        variants[nm] = run_variant(nm, dates, sleeves, wfn)

    # (b) SMOOTHING: simple average of last K monthly weight vectors, K in {2,3,6}
    for k in (2, 3, 6):
        nm = "smooth_avg_%dmo" % k
        wfn = make_smoothed_wfn(raw_wfn, mo_set, k)
        variants[nm] = run_variant(nm, dates, sleeves, wfn)

    # (b2) EWMA smoothing, a couple of decay settings
    for alpha in (0.5, 0.3):
        nm = "smooth_ewma_a%.1f" % alpha
        wfn = make_ewma_wfn(raw_wfn, mo_set, alpha)
        variants[nm] = run_variant(nm, dates, sleeves, wfn)

    # (b3) LONGER VOL LOOKBACK: 126d, 189d (different reaction speed of the raw signal)
    for lb in (126, 189):
        nm = "vol_lookback_%dd" % lb
        wfn_lb = make_invvol_wfn(sleeves, lb)
        variants[nm] = run_variant(nm, dates, sleeves, wfn_lb)

    # (c) COMBOS: floor + smoothing (apply floor to the smoothed signal)
    for (f, k) in ((0.15, 3), (0.20, 3), (0.20, 6)):
        nm = "floor_%.2f_smooth_avg_%dmo" % (f, k)
        sm = make_smoothed_wfn(raw_wfn, mo_set, k)
        wfn = make_floored_wfn(sm, f)
        variants[nm] = run_variant(nm, dates, sleeves, wfn)

    out["variants"] = variants

    # ---- PART 2b: rearview metric FOR each variant's effective weight fn ----
    # The guardrail's job is to shrink the rearview pathology. Measure, for each
    # variant, the same "biggest-cut forward-return delta" but on that variant's
    # EFFECTIVE (transformed) weight function, plus the max single monthly cut size.
    print(">>> rearview metric per variant ...", flush=True)
    variant_wfns = {
        "baseline_invvol_63d": raw_wfn,
        "floor_0.10": make_floored_wfn(raw_wfn, 0.10),
        "floor_0.15": make_floored_wfn(raw_wfn, 0.15),
        "floor_0.20": make_floored_wfn(raw_wfn, 0.20),
        "floor_0.25": make_floored_wfn(raw_wfn, 0.25),
        "floor_0.30": make_floored_wfn(raw_wfn, 0.30),
        "floor_0.50": make_floored_wfn(raw_wfn, 0.50),
        "smooth_avg_2mo": make_smoothed_wfn(raw_wfn, mo_set, 2),
        "smooth_avg_3mo": make_smoothed_wfn(raw_wfn, mo_set, 3),
        "smooth_avg_6mo": make_smoothed_wfn(raw_wfn, mo_set, 6),
        "smooth_ewma_a0.5": make_ewma_wfn(raw_wfn, mo_set, 0.5),
        "smooth_ewma_a0.3": make_ewma_wfn(raw_wfn, mo_set, 0.3),
        "vol_lookback_126d": make_invvol_wfn(sleeves, 126),
        "vol_lookback_189d": make_invvol_wfn(sleeves, 189),
        "floor_0.15_smooth_avg_3mo": make_floored_wfn(make_smoothed_wfn(raw_wfn, mo_set, 3), 0.15),
        "floor_0.20_smooth_avg_3mo": make_floored_wfn(make_smoothed_wfn(raw_wfn, mo_set, 3), 0.20),
        "floor_0.20_smooth_avg_6mo": make_floored_wfn(make_smoothed_wfn(raw_wfn, mo_set, 6), 0.20),
    }
    rv_summary: Dict = {}
    for nm, wfn in variant_wfns.items():
        rv = rearview_metric_summary(dates, sleeves, wfn, mo)
        rv_summary[nm] = rv
        # attach the headline rearview number to the variant block too
        if nm == "baseline_invvol_63d":
            out["baseline"]["rearview_metric"] = rv
        elif nm in out["variants"]:
            out["variants"][nm]["rearview_metric"] = rv
    out["rearview_metric_by_variant"] = rv_summary

    # ---- write JSON ----
    outpath = WORKSPACE / "reports" / "_antirearview_guardrail_result.json"
    with open(outpath, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wrote %s" % outpath)

    # ---- console summary table ----
    print("")
    print("=== VARIANT SUMMARY (full continuous-span fp Sharpe ddof=1; same path) ===")
    hdr = "%-30s %8s %8s %8s %8s %8s %10s %10s" % (
        "variant", "fullSh", "fullDD", "CAGR", "oosSh", "oosDD", "rv_worst", "maxCut")
    print(hdr)
    rows = [("baseline_invvol_63d", out["baseline"])] + sorted(
        out["variants"].items(), key=lambda kv: -kv[1]["full"]["sharpe"])
    for nm, v in rows:
        rv = v.get("rearview_metric", {})
        print("%-30s %8.4f %8.2f %8.2f %8.4f %8.2f %10s %10s" % (
            nm[:30], v["full"]["sharpe"], v["full"]["maxdd_pct"], v["full"]["cagr_pct"],
            v["oos_2019_today"]["sharpe"] or 0.0, v["oos_2019_today"]["maxdd_pct"] or 0.0,
            _fmt(rv.get("worst_cut_fwd1m_delta")), _fmt(rv.get("max_single_monthly_cut"))))

    return out


def _fmt(x):
    return ("%.4f" % x) if isinstance(x, (int, float)) else str(x)


def rearview_metric_summary(dates: List[str], sleeves: List[List[float]],
                            wfn: Callable[[int], List[float]], mo: List[int]) -> Dict:
    """Compact rearview metric for ONE (possibly transformed) weight fn:
      - max_single_monthly_cut: the largest single month-over-month weight DROP for
        either sleeve (how violently the scheme can yank a sleeve in one month).
      - worst_cut_fwd1m_delta: across both sleeves, the (cond - uncond) mean 1-month
        forward standalone return after a >5% cut. POSITIVE = rearview-prone (cut the
        sleeve right before it outperformed its own average). Near 0 / negative = not
        rearview-prone. We take the WORST (most positive) of the two sleeves.
      - per_sleeve fwd1m delta after >5% cut, plus n_cuts.
    """
    wvecs = [wfn(m) for m in mo]
    res: Dict = {"per_sleeve": {}}
    max_cut = 0.0
    worst_delta = None
    for s in (0, 1):
        # max single monthly drop for this sleeve
        for p in range(1, len(mo)):
            dw = wvecs[p][s] - wvecs[p - 1][s]
            if -dw > max_cut:
                max_cut = -dw
        # uncond + conditional (>5% cut) 1m forward
        uncond = []
        for p in range(len(mo)):
            fr = forward_sleeve_return(sleeves[s], mo, p, 1)
            if fr is not None:
                uncond.append(fr)
        cut_pos = [p for p in range(1, len(mo)) if (wvecs[p][s] - wvecs[p - 1][s]) < -0.05]
        cond = []
        for p in cut_pos:
            fr = forward_sleeve_return(sleeves[s], mo, p, 1)
            if fr is not None:
                cond.append(fr)
        delta = (_mean(cond) - _mean(uncond)) if cond and uncond else None
        nm = ["tqqq", "rot"][s]
        res["per_sleeve"][nm] = {
            "n_cuts_gt5pct": len(cut_pos),
            "fwd1m_after_cut_mean": _mean(cond),
            "fwd1m_uncond_mean": _mean(uncond),
            "fwd1m_delta": delta,
        }
        if delta is not None:
            if worst_delta is None or delta > worst_delta:
                worst_delta = delta
    res["max_single_monthly_cut"] = round(max_cut, 4)
    res["worst_cut_fwd1m_delta"] = worst_delta
    return res


if __name__ == "__main__":
    main()
