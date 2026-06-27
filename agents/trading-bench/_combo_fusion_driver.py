"""Driver: run the macd_momentum_iwm × {breakout_xlk, volume_breakout_qqq} combo
sprint and emit a JSON verdict blob.

For each primary parent we compute, on the SAME windows / cost / split:
  - SOLO primary (no fusion)
  - AND-fusion (base D+1 lag, and +1-bar-lag canary)
  - OR-fusion  (base D+1 lag, and +1-bar-lag canary)

Metrics per variant: full-span return, FP-continuous Sharpe (1Hour annualized),
n_trades, maxDD, IS/OOS returns, median-of-5-windows return, SPY buy&hold bench.

Gate (per combo, per fusion mode):
  PASS requires BOTH:
    (a) median-of-windows return beats strongest solo parent by >= +0.10pp, AND
    (b) FP-continuous Sharpe does NOT drop below (parent_fp_sharpe - 0.10)
        [verdict lesson: OR dilutes Sharpe; we refuse a raw-return beat that is
         just added variance]
  AND the OOS return must be positive AND beat SPY OOS buy&hold.
  AND the base->canary Sharpe must not flip sign or collapse (robustness).
"""
from __future__ import annotations

import json
from typing import Dict, List

import _combo_fusion_lib as L

N_WINDOWS = 5
DELTA_PP = 0.10  # MUTATION_MIN_DELTA_PCT, +0.10pp median return


def solo_decide(primary_name):
    mod, _ = L.load_strategy_module_and_params(primary_name)
    return mod.decide


def eval_variant(primary_name, primary_bars_full, decide_fn, lookup_state,
                 label) -> Dict:
    # full span
    full = L.run_one(primary_name, primary_bars_full, decide_fn, lookup_state)
    # IS / OOS
    is_bars = L.slice_by_date(primary_bars_full, None, L.IS_END)
    oos_bars = L.slice_by_date(primary_bars_full, L.OOS_START, None)
    is_res = L.run_one(primary_name, is_bars, decide_fn, lookup_state)
    oos_res = L.run_one(primary_name, oos_bars, decide_fn, lookup_state)
    # median of N contiguous windows
    wins = L.chunk_windows(primary_bars_full, N_WINDOWS)
    win_results = [L.run_one(primary_name, w, decide_fn, lookup_state) for w in wins]
    med_ret = L.median([w["ret_pct"] for w in win_results])
    fp_s, fp_n = L.fp_sharpe_concat(win_results)
    return {
        "label": label,
        "full_ret_pct": full["ret_pct"],
        "full_sharpe": full["sharpe"],
        "fp_sharpe": fp_s,
        "fp_n": fp_n,
        "n_trades": full["n_trades"],
        "maxdd": full["maxdd"],
        "is_ret_pct": is_res["ret_pct"],
        "oos_ret_pct": oos_res["ret_pct"],
        "oos_n_trades": oos_res["n_trades"],
        "median_window_ret_pct": med_ret,
        "window_rets": [round(w["ret_pct"], 3) for w in win_results],
    }


def run_combo(primary_name: str, iwm_states) -> Dict:
    primary_bars = L.load_full_1h(primary_name_to_symbol(primary_name))
    # Sanity: confirm coverage
    cov = (primary_bars[0]["t"][:10], primary_bars[-1]["t"][:10], len(primary_bars)) if primary_bars else ("NA", "NA", 0)

    out = {"primary": primary_name, "coverage": cov, "variants": {}}

    # SOLO baseline (no lookup needed, but keep a dummy state)
    dummy_lookup, dummy_state = L.make_aligned_lookup(iwm_states, lag_bars=0)
    out["variants"]["solo"] = eval_variant(
        primary_name, primary_bars, solo_decide(primary_name), dummy_state, "solo")

    for lag, lag_label in [(0, "base_d1"), (1, "canary_lag1")]:
        # AND
        and_lookup, and_state = L.make_aligned_lookup(iwm_states, lag_bars=lag)
        and_fn = L.make_and_fusion(primary_name, and_lookup)
        out["variants"][f"and_{lag_label}"] = eval_variant(
            primary_name, primary_bars, and_fn, and_state, f"and_{lag_label}")
        # OR
        or_lookup, or_state = L.make_aligned_lookup(iwm_states, lag_bars=lag)
        or_fn, _prev = L.make_or_fusion(primary_name, or_lookup)
        out["variants"][f"or_{lag_label}"] = eval_variant(
            primary_name, primary_bars, or_fn, or_state, f"or_{lag_label}")

    # SPY bench on full span
    out["spy_full_buyhold_pct"] = L.spy_buyhold_return(primary_bars)
    oos_bars = L.slice_by_date(primary_bars, L.OOS_START, None)
    out["spy_oos_buyhold_pct"] = L.spy_buyhold_return(oos_bars)
    return out


def primary_name_to_symbol(name: str) -> str:
    return {"breakout_xlk": "XLK", "volume_breakout_qqq": "QQQ"}[name]


def gate_combo(combo: Dict) -> Dict:
    solo = combo["variants"]["solo"]
    solo_med = solo["median_window_ret_pct"]
    solo_fp = solo["fp_sharpe"]
    spy_oos = combo["spy_oos_buyhold_pct"]
    verdicts = {}
    for mode in ["and", "or"]:
        base = combo["variants"][f"{mode}_base_d1"]
        canary = combo["variants"][f"{mode}_canary_lag1"]
        cond_med = base["median_window_ret_pct"] >= solo_med + DELTA_PP
        cond_sharpe = base["fp_sharpe"] >= solo_fp - 0.10
        cond_oos_pos = base["oos_ret_pct"] > 0.0
        cond_oos_spy = base["oos_ret_pct"] > spy_oos
        # robustness: canary sharpe same sign and within 0.25 of base
        cond_robust = (
            (base["fp_sharpe"] >= 0) == (canary["fp_sharpe"] >= 0)
            and abs(base["fp_sharpe"] - canary["fp_sharpe"]) <= 0.25
        )
        passed = all([cond_med, cond_sharpe, cond_oos_pos, cond_oos_spy, cond_robust])
        verdicts[mode] = {
            "PASS": passed,
            "cond_median_beat_+0.10pp": cond_med,
            "cond_sharpe_not_collapse": cond_sharpe,
            "cond_oos_positive": cond_oos_pos,
            "cond_oos_beats_spy": cond_oos_spy,
            "cond_canary_robust": cond_robust,
            "solo_median": round(solo_med, 4),
            "combo_median": round(base["median_window_ret_pct"], 4),
            "solo_fp_sharpe": round(solo_fp, 4),
            "combo_fp_sharpe": round(base["fp_sharpe"], 4),
            "canary_fp_sharpe": round(canary["fp_sharpe"], 4),
            "combo_oos_ret": round(base["oos_ret_pct"], 4),
            "spy_oos": round(spy_oos, 4),
        }
    return verdicts


def main():
    iwm_bars = L.load_full_1h("IWM")
    iwm_states = L.build_iwm_macd_states(iwm_bars)
    n_bull = sum(1 for _, b in iwm_states if b)
    print(f"IWM bars={len(iwm_bars)} bullish_frac={n_bull/max(len(iwm_states),1):.3f}")

    results = {}
    for primary in ["breakout_xlk", "volume_breakout_qqq"]:
        print(f"\n=== {primary} ===")
        combo = run_combo(primary, iwm_states)
        combo["gate"] = gate_combo(combo)
        results[primary] = combo
        for k, v in combo["variants"].items():
            print(f"  {k:16s} ret={v['full_ret_pct']:8.2f}% fpS={v['fp_sharpe']:+.3f} "
                  f"trades={v['n_trades']:4d} medWin={v['median_window_ret_pct']:+.3f}% "
                  f"OOS={v['oos_ret_pct']:+.2f}%")
        print(f"  SPY full={combo['spy_full_buyhold_pct']:.2f}% OOS={combo['spy_oos_buyhold_pct']:.2f}%")
        for mode, gv in combo["gate"].items():
            print(f"  GATE[{mode}]: {'PASS' if gv['PASS'] else 'REJECT'} {gv}")

    with open("_combo_fusion_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nwrote _combo_fusion_results.json")


if __name__ == "__main__":
    main()
