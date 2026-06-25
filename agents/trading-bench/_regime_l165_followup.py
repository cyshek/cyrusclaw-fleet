"""L165 follow-up: focused counterfactuals on the real gate candidates
(tqqq_cot_combo, allocator_blend) + an honest 'is it alpha or just lower vol?'
check. Vol-normalize the gated book to the baseline's full-period vol and
re-measure Sharpe/CAGR — if the Sharpe gain survives vol-matching it's a
risk-adjusted improvement, not just de-risking.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from runner.fp_sharpe import sharpe_from_returns
from runner import lane_honesty

import importlib.util
spec = importlib.util.spec_from_file_location("_rl", "_regime_l165.py")
RL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RL)

SQRT_252 = math.sqrt(252.0)


def stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def main():
    names, series, dates = RL.load_series()
    weights, cap, captot = RL.load_weights(names)
    spy_map = RL.load_spy()
    labels, diag, _ = RL.build_regime_labels(dates, spy_map)

    book = RL.book_returns(dates, series, names, weights)
    split = int(len(dates) * 0.70)

    base_vol = stdev(book)

    def report(tag, gated):
        gbook = RL.book_returns_gated(dates, series, names, weights, labels, gated, "BEAR")
        # vol-match: scale gated returns so full-period stdev == base_vol
        gvol = stdev(gbook)
        scale = base_vol / gvol if gvol > 0 else 1.0
        gbook_vm = [r * scale for r in gbook]
        out = {
            "gated": gated,
            "base": RL.full_metrics(book),
            "gated_raw": RL.full_metrics(gbook),
            "gated_volmatched": RL.full_metrics(gbook_vm),
            "OOS_base": RL.full_metrics(book[split:]),
            "OOS_gated_raw": RL.full_metrics(gbook[split:]),
            "IS_base": RL.full_metrics(book[:split]),
            "IS_gated_raw": RL.full_metrics(gbook[:split]),
            "base_vol_ann_pct": round(base_vol * SQRT_252 * 100, 3),
            "gated_vol_ann_pct": round(gvol * SQRT_252 * 100, 3),
            "vol_match_scale": round(scale, 4),
        }
        print(f"\n=== {tag} (gate {gated} flat in BEAR) ===")
        print(f"  vol: base {out['base_vol_ann_pct']}% -> gated {out['gated_vol_ann_pct']}% (scale {scale:.3f})")
        b = out["base"]; gr = out["gated_raw"]; gv = out["gated_volmatched"]
        print(f"  FULL base     : Sh={b['sharpe']} So={b['sortino']} CAGR={b['cagr_pct']}% mdd={b['maxdd_pct']}%")
        print(f"  FULL gated raw: Sh={gr['sharpe']} So={gr['sortino']} CAGR={gr['cagr_pct']}% mdd={gr['maxdd_pct']}%")
        print(f"  FULL gated VM : Sh={gv['sharpe']} So={gv['sortino']} CAGR={gv['cagr_pct']}% mdd={gv['maxdd_pct']}%  <- vol-matched to base")
        ob = out["OOS_base"]; og = out["OOS_gated_raw"]
        print(f"  OOS  base     : Sh={ob['sharpe']} So={ob['sortino']} CAGR={ob['cagr_pct']}% mdd={ob['maxdd_pct']}%")
        print(f"  OOS  gated    : Sh={og['sharpe']} So={og['sortino']} CAGR={og['cagr_pct']}% mdd={og['maxdd_pct']}%")
        print(f"  OOS  dSharpe  : {round(og['sharpe']-ob['sharpe'],4):+}   dSortino {round((og['sortino'] or 0)-(ob['sortino'] or 0),4):+}")
        return out

    res = {}
    res["tqqq_only"] = report("TQQQ ONLY", ["tqqq_cot_combo"])
    res["alloc_only"] = report("ALLOCATOR ONLY", ["allocator_blend"])
    res["tqqq_alloc"] = report("TQQQ + ALLOCATOR", ["tqqq_cot_combo", "allocator_blend"])
    res["levered_pair_plus_trend"] = report("TQQQ+ALLOC+TREND-TRIO",
        ["tqqq_cot_combo", "allocator_blend", "breakout_xlk__mut_c382b1",
         "sma_crossover_qqq_regime", "sma_crossover_qqq_rth"])
    res["all8"] = report("ALL 8", names)

    # Also: what fraction of book bear-loss is tqqq? Decompose bear-regime book mean
    bear_idx = [i for i, dd in enumerate(dates) if labels[dd] == "BEAR"]
    contrib = {}
    for n in names:
        c = sum(weights[n] * series[n][i] for i in bear_idx) / len(bear_idx)
        contrib[n] = round(c * 1e4, 3)  # bps/day mean contribution in bear
    res["bear_mean_contrib_bps"] = contrib
    print("\n=== BEAR-regime book mean-return contribution (bps/day, weighted) ===")
    tot = sum(contrib.values())
    for n, c in sorted(contrib.items(), key=lambda kv: kv[1]):
        print(f"  {n:28s} {c:+.3f} bps   ({round(c/tot*100,1) if tot else 0}% of total {round(tot,3)})")

    Path("_regime_l165_followup.json").write_text(json.dumps(res, indent=2))
    print("\nWROTE _regime_l165_followup.json")


if __name__ == "__main__":
    main()
