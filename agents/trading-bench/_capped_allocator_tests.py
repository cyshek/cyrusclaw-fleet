#!/usr/bin/env python3
"""
CAPPED / RETURN-AWARE ALLOCATOR — "what does crash insurance cost on this book?"

Context (2026-06-23): the third-sleeve study CLOSED the naive question — adding a
3rd low-corr trend sleeve to the validated 2-sleeve inverse-vol blend LIFTS Sharpe
and HALVES drawdown but LOSES to SPX on raw return, because vanilla inverse-vol
risk-parity hands the calm trend leg 40-60% of the book and starves the
levered-Nasdaq raw-return engine.

This study tests the OBVIOUS fix flagged in that report: CAP the trend sleeve's
weight (e.g. <=25%) so it trims tail risk WITHOUT gutting raw return. The output
is a frontier: for each cap, how much raw return do we give up vs how much
drawdown/Sharpe do we buy? i.e. the PRICE of crash insurance on this book.

Reuses the validated engine VERBATIM:
  build_sleeves(), synthetic_trend_sleeve(), blend_portfolio(), report_blend(),
  _solo_block(), invvol_wfn_factory() (as the uncapped baseline).
The ONLY new thing is `capped_invvol_wfn_factory`: identical inverse-vol math,
then clip sleeve[2] (trend) to `cap` and redistribute the excess to the other
two sleeves in proportion to THEIR inverse-vol weights (so we don't disturb the
TQQQ/ROT relative balance). Cap=1.0 reproduces the uncapped 3-sleeve exactly.

Deep window only (SYN_TREND, 2010-02 -> 2026-06) so the read spans 2011/2018/2020/
2022 stress. SPX on the traded path. 2bps inter-sleeve cost. No lookahead (PAST
returns only in the weight fn). No protected/live files touched.
"""
import json
import sys
from typing import Dict, List

# Reuse the validated third-sleeve harness (which itself reuses the validated
# allocator-blend engine verbatim).
from _third_sleeve_tests import (  # noqa: E402
    build_sleeves,
    synthetic_trend_sleeve,
    blend_portfolio,
    report_blend,
    invvol_wfn_factory,
    _solo_block,
    correlation_report,
    stats_from_returns,
    equity_to_daily_returns,
    annualized_vol,
)


def capped_invvol_wfn_factory(sleeves: List[List[float]], lookback: int = 63,
                              cap: float = 0.25, cap_index: int = 2):
    """Inverse-vol risk-parity over N sleeves, but the sleeve at `cap_index`
    (the trend leg) is clipped to <= `cap`. The clipped-off excess is
    redistributed to the OTHER sleeves in proportion to their own inverse-vol
    weights, preserving their relative balance. PAST returns only.

    cap >= 1.0 reproduces the uncapped inverse-vol weights exactly.
    """
    ns = len(sleeves)

    def fn(idx):
        if idx < 2:
            return [1.0 / ns] * ns
        lo = max(0, idx - lookback)
        ivs = []
        for k in range(ns):
            v = annualized_vol(sleeves[k][lo:idx])
            ivs.append(1.0 / v if v > 0 else 0.0)
        s = sum(ivs)
        if s <= 0:
            return [1.0 / ns] * ns
        w = [iv / s for iv in ivs]

        if cap >= 1.0 or w[cap_index] <= cap:
            return w

        # Clip the trend sleeve and redistribute excess to the others by their
        # inverse-vol share among themselves.
        excess = w[cap_index] - cap
        others = [k for k in range(ns) if k != cap_index]
        other_iv_sum = sum(ivs[k] for k in others)
        out = list(w)
        out[cap_index] = cap
        if other_iv_sum <= 0:
            # degenerate: split excess evenly
            for k in others:
                out[k] += excess / len(others)
        else:
            for k in others:
                out[k] += excess * (ivs[k] / other_iv_sum)
        return out

    return fn


def run_cap_frontier(S: Dict, third_r_map: Dict[str, float], label: str,
                     caps: List[float], lookbacks: List[int]) -> Dict:
    """Build the cap x lookback frontier on the SHARED deep window."""
    tqqq_full = dict(zip(S["common_dates"], S["tqqq_r"]))
    rot_full = dict(zip(S["common_dates"], S["rot_r"]))
    spx_full = dict(zip(S["common_dates"], S["spx_r"]))

    shared = [d for d in S["common_dates"] if d in third_r_map]
    tqqq_r = [tqqq_full[d] for d in shared]
    rot_r = [rot_full[d] for d in shared]
    spx_r = [spx_full[d] for d in shared]
    third_r = [third_r_map[d] for d in shared]

    spx_curve = stats_from_returns(shared, spx_r)
    spx_dates, spx_equity = spx_curve["dates"], spx_curve["equity"]
    spx_stats = spx_curve["stats"]

    sleeves3 = [tqqq_r, rot_r, third_r]

    # correlation of trend leg vs 2-sleeve blend (for context, lb=63)
    wfn2 = invvol_wfn_factory([tqqq_r, rot_r], 63)
    blend2 = blend_portfolio(shared, [tqqq_r, rot_r], wfn2, blend_cost_bps=2.0)
    blend2_ret = equity_to_daily_returns(blend2["dates"], blend2["equity"])
    blend2_r = [blend2_ret.get(d, 0.0) for d in shared]
    rep2 = report_blend(blend2, "2sleeve_%s_window" % label, spx_dates, spx_equity)
    corr_third_vs_blend2 = correlation_report(shared, third_r, blend2_r)["full"]

    grid = {}
    for lb in lookbacks:
        grid[str(lb)] = {}
        for cap in caps:
            wfn = capped_invvol_wfn_factory(sleeves3, lb, cap=cap, cap_index=2)
            blend = blend_portfolio(shared, sleeves3, wfn, blend_cost_bps=2.0)
            rep = report_blend(blend, "3sleeve_%s_cap%.2f_lb%d" % (label, cap, lb),
                               spx_dates, spx_equity)
            avg_w = None
            if blend["weight_log"]:
                avg_w = [
                    sum(wl["w"][i] for wl in blend["weight_log"]) / len(blend["weight_log"])
                    for i in range(3)
                ]
            grid[str(lb)]["%.2f" % cap] = {
                "full": rep["full"],
                "oos_2019_today": rep["oos_2019_today"],
                "is_2010_2018": rep["is_2010_2018"],
                "avg_weights_tqqq_rot_trend": avg_w,
            }

    return {
        "label": label,
        "shared_window": [shared[0], shared[-1], len(shared)],
        "spx_full": {
            "sharpe": spx_stats["sharpe"], "cagr_pct": spx_stats["cagr_pct"],
            "maxdd_pct": spx_stats["max_drawdown_pct"],
            "total_return_pct": spx_stats["total_return_pct"],
        },
        "blend2_baseline": rep2,
        "trend_corr_vs_2sleeve_full": corr_third_vs_blend2,
        "trend_solo": _solo_block(shared, third_r),
        "grid_by_lookback_then_cap": grid,
    }


def main():
    caps = [0.15, 0.20, 0.25, 0.30, 1.00]   # 1.00 == uncapped (reproduces 3-sleeve)
    lookbacks = [21, 42, 63, 126]
    print(">>> build_sleeves() ...", flush=True)
    S = build_sleeves()

    print(">>> SYN_TREND deep sleeve (12-1 TSM long/flat [DBC,GLD,TLT,UUP]) ...", flush=True)
    syn = synthetic_trend_sleeve(["DBC", "GLD", "TLT", "UUP"], lookback_days=252, skip_days=21)
    out = {
        "meta": {
            "study": "capped_return_aware_allocator",
            "question": "What raw-return is sacrificed to cap the trend sleeve and buy drawdown/Sharpe? (price of crash insurance on this book)",
            "caps_tested": caps,
            "lookbacks_tested": lookbacks,
            "cost_bps": 2.0,
            "note": "cap clips trend-sleeve(idx2) weight; excess redistributed to TQQQ/ROT by their inv-vol share. cap=1.00 reproduces uncapped 3-sleeve. SYN_TREND deep window only.",
        },
        "SYN_TREND": run_cap_frontier(S, syn, "SYN_TREND", caps, lookbacks),
    }

    with open("reports/_capped_allocator_result.json", "w") as f:
        json.dump(out, f, indent=1)

    # ---- console frontier (lb=63 headline) ----
    r = out["SYN_TREND"]
    b2 = r["blend2_baseline"]["full"]
    spx = r["spx_full"]
    print("\n===== SYN_TREND deep window %s (n=%d) =====" % (
        tuple(r["shared_window"][:2]), r["shared_window"][2]), flush=True)
    print("trend corr vs 2-sleeve (full): %.3f" % r["trend_corr_vs_2sleeve_full"], flush=True)
    print("SPX raw: %.0f%% | 2-sleeve: raw %.0f%% sharpe %.3f oos %.3f maxDD %.1f%%" % (
        spx["total_return_pct"], b2["total_return_pct"], b2["sharpe"],
        r["blend2_baseline"]["oos_2019_today"]["sharpe"], b2["maxdd_pct"]), flush=True)
    print("\nlb=63 cap frontier (cap | raw%% | sharpe | oos | maxDD | avg trend wt | beats SPX raw?):", flush=True)
    g63 = r["grid_by_lookback_then_cap"]["63"]
    for cap in ["0.15", "0.20", "0.25", "0.30", "1.00"]:
        c = g63[cap]
        beats = "YES" if c["full"]["total_return_pct"] > spx["total_return_pct"] else "NO"
        print("  cap %s | %6.0f%% | %.3f | %.3f | %6.1f%% | %.2f | %s" % (
            cap, c["full"]["total_return_pct"], c["full"]["sharpe"],
            c["oos_2019_today"]["sharpe"], c["full"]["maxdd_pct"],
            c["avg_weights_tqqq_rot_trend"][2], beats), flush=True)

    print("\nwrote reports/_capped_allocator_result.json", flush=True)


if __name__ == "__main__":
    sys.exit(main())
