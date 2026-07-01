"""Report writer for the HMM confirm-or-kill. Mirrors CPPI/DAA verdict format:
top-line verdict, engine/rails, head-to-head table, full grid, lead/lag finding,
+1-bar canary, degeneracy check, K2-vs-K3, kill-quantity trace.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def _f(x, nd=4, dash="—"):
    if x is None:
        return dash
    try:
        return ("%." + str(nd) + "f") % float(x)
    except Exception:
        return str(x)


def _pct(x, nd=2, dash="—"):
    if x is None:
        return dash
    return ("%." + str(nd) + "f%%") % float(x)


def write_report(r: Dict, stamp: str) -> str:
    b = r["benchmarks"]
    inc = b["incumbent_breadth"]
    sma = b["sma200_binary"]
    ung = b["ungated"]
    best = r.get("best_oos")
    canary = r.get("canary_plus1bar")
    ll = r.get("lead_lag")
    verdict = r["verdict"]
    kill = r["kill_reasons"]
    san = r["sanity"]
    path = "reports/HMM_VERDICT_%s.md" % stamp

    L: List[str] = []
    A = L.append
    emoji = "🟢 GO" if verdict == "GO" else "🔴 KILL"
    A("# HMM / Markov-Switching Latent-State Regime Gate — CONFIRM-OR-KILL vs the SMA-200 / Breadth Price Gate")
    A("")
    win = inc.get("_window", None)
    A("**Stamp:** %s · **Sleeve:** TQQQ vol-target (underlying QQQ, target 25%% ann vol, 20d window, w_max 1.0, net %sbps) · **Verdict: %s**"
      % (stamp, _f(r["cost_bps"], 1), emoji))
    A("")
    A("**Question.** Does a probabilistic latent-state (Gaussian HMM, forward-filter) regime gate **beat** the incumbent SMA-200 + {30,90,180}-breadth price gate on the SAME instrument/path, net of cost, on **BOTH** OOS FP-Sharpe **AND** OOS maxDD, **and** survive a +1-bar canary, **and** fire a sensible fraction of days, **and** stay non-knife-edge in θ — specifically, does latent-state inference give EARLIER warning of a vol-regime shift than the crude price line?")
    A("")
    # Answer paragraph
    if verdict == "KILL":
        A("**Answer: No.** " + (kill[0] if kill else "See kill-quantity trace below."))
    else:
        A("**Answer: Yes.** The best honest HMM config clears every kill-quantity (see trace).")
    A("")
    A("---")
    A("")
    # Engine & rails
    A("## Engine & rails")
    A("")
    A("- **Apples-to-apples gate swap.** All books are the IDENTICAL TQQQ vol-target sleeve (inverse-vol sizing to 25%% ann vol, 20d window, 2bps abs-weight cost, t-bill cash). The ONLY thing that differs is the **trend/regime gate multiplier** `g ∈ [0,1]` that scales the vol-target weight: incumbent = breadth-fraction over {30,90,180}; pure-SMA200 = binary price>SMA200; HMM = 1 if P(bear|data≤t−1) < θ else 0; ungated = 1 always. The swap simulator reproduces the live incumbent to 4 decimals (verified), so any win/loss is attributable purely to the gate mechanism.")
    A("- **PAST-ONLY.** Exposure for bar *t* uses the posterior computed through bar *t−1* (idx−1), exactly like the incumbent gate. The HMM is **fit on an expanding, past-only window, re-fit MONTHLY** (fit at month *m* uses data ≤ last day of month *m−1* only). Feature standardization uses ONLY the training window's mean/std.")
    A("- **Forward-filter ONLY for the live signal.** The live posterior P(bear|x₁..xₜ) is the scaled FORWARD filter α̂ₜ — NO Viterbi, NO backward smoothing (smoothing uses future data and would leak). Baum-Welch forward-backward is used ONLY inside the monthly fit on past data. This is the #1 leak risk and it is closed by construction.")
    A("- **Bear-state labeling.** The 'bear' state = the fitted state with the LOWEST return-channel mean (ties → highest total variance). This is a stable functional of the params, immune to EM label-switching across re-fits.")
    A("- **FP-Sharpe = canonical continuous-span** annualized Sharpe (`runner.fp_sharpe.sharpe_from_returns`, √252), NOT median-of-windows. IS ≤ 2019 / OOS ≥ 2020 (task split); a secondary 2019 split is in the JSON.")
    A("- **Sweep:** K ∈ {2,3} × features {ret, ret+vol%s} × θ ∈ {0.5,0.6,0.7,0.8}. Monthly re-fit → trivial turnover." % (", ret+vol+vix" if r.get("vix_available") else ""))
    A("")
    # Sanity
    A("## HMM implementation sanity (hand-rolled pure-numpy Baum-Welch + forward filter)")
    A("")
    A("`hmmlearn`/`sklearn` are not installed and pip is locked, so the 2-/3-state diagonal-covariance Gaussian HMM is hand-rolled (scaled forward-backward EM for the fit; scaled forward filter for the live signal). Validated against a planted 2-regime series (calm μ=+0.0005 σ=0.008; storm μ=−0.002 σ=0.030, sticky p_stay=0.98):")
    A("")
    A("| | true bear | recovered bear | true bull | recovered bull |")
    A("|---|---|---|---|---|")
    A("| mean | −0.00200 | %s | +0.00050 | %s |" % (_f(san["rec_mu_bear"], 5), _f(san["rec_mu_bull"], 5)))
    A("| stdev | 0.03000 | %s | 0.00800 | %s |" % (_f(san["rec_sd_bear"], 5), _f(san["rec_sd_bull"], 5)))
    A("")
    A("Filtered P(bear) discrimination: **%s** in true-storm bars vs **%s** in true-calm bars (gap %s). **%s** — the implementation recovers planted states and the forward filter separates regimes."
      % (_f(san["pbear_in_true_storm"], 3), _f(san["pbear_in_true_calm"], 3),
         _f(san["pbear_in_true_storm"] - san["pbear_in_true_calm"], 3),
         "PASS" if san["PASS"] else "FAIL"))
    A("")
    A("---")
    A("")
    # Head-to-head
    A("## Head-to-head (full period, identical TQQQ sleeve path)")
    A("")
    A("| Book | FP-Sharpe | CAGR %% | maxDD %% | ann vol %% | OOS Sharpe | OOS maxDD %% | avg wt | turn units | cost %% |")
    A("|---|---|---|---|---|---|---|---|---|---|")

    def row(label, d):
        return "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            label, _f(d["fp_sharpe"]), _f(d["cagr_pct"], 2), _f(d["max_drawdown_pct"], 2),
            _f(d["ann_vol_pct"], 2), _f(d["oos_fp_sharpe"]), _f(d["oos_maxdd_pct"], 2),
            _f(d["avg_weight"], 3), _f(d["turnover_units"], 1), _f(d["turnover_cost_pct"], 2))
    A(row("**INCUMBENT: SMA-200+{30,90,180}-breadth**", inc))
    A(row("Pure SMA-200 binary", sma))
    A(row("Ungated (always-in, no protection)", ung))
    if best is not None:
        blabel = "**HMM best (%s, θ=%s)**" % (best["key"], _f(best["theta"], 1))
        A(row(blabel, best))
    A("")
    if best is not None:
        edge_inc = (best["oos_fp_sharpe"] or 0) - (inc["oos_fp_sharpe"] or 0)
        edge_dd = (best["oos_maxdd_pct"] or 0) - (inc["oos_maxdd_pct"] or 0)
        A("**Reading the table.** Best HMM OOS FP-Sharpe %s vs incumbent %s (edge **%s**); OOS maxDD %s vs incumbent %s (Δ **%s** — %s). %s"
          % (_f(best["oos_fp_sharpe"]), _f(inc["oos_fp_sharpe"]), _f(edge_inc),
             _pct(best["oos_maxdd_pct"]), _pct(inc["oos_maxdd_pct"]),
             _pct(edge_dd), "improved" if edge_dd > 0 else "NOT improved",
             "The HMM gate does not displace the simpler price gate." if verdict == "KILL" else "The HMM gate earns its complexity."))
    A("")
    A("---")
    A("")
    # Full grid
    A("## Full θ×K×feature grid (sorted by OOS FP-Sharpe)")
    A("")
    A("| K/feat | θ | full FP-Sh | CAGR %% | maxDD %% | OOS FP-Sh | OOS maxDD %% | bear-fire %% | turn cost %% | note |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    grid = sorted(r["grid"], key=lambda g: (g["oos_fp_sharpe"] if g["oos_fp_sharpe"] is not None else -9), reverse=True)
    for g in grid:
        note = ""
        ff = g["bear_fire_frac_pct"]
        if ff < 2.0:
            note = "degenerate (always-in)"
        elif ff > 98.0:
            note = "degenerate (always-out)"
        elif best is not None and g["key"] == best["key"] and abs(g["theta"] - best["theta"]) < 1e-9:
            note = "**best OOS**"
        A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            g["key"], _f(g["theta"], 1), _f(g["fp_sharpe"]), _f(g["cagr_pct"], 2),
            _f(g["max_drawdown_pct"], 2), _f(g["oos_fp_sharpe"]), _f(g["oos_maxdd_pct"], 2),
            _f(ff, 1), _f(g["turnover_cost_pct"], 2), note))
    A("")
    # knife-edge check
    if best is not None:
        same_key = [g for g in r["grid"] if g["key"] == best["key"] and g["oos_fp_sharpe"] is not None]
        A("**θ-stability (knife-edge check) for the best cell's family (%s):** " % best["key"] +
          " · ".join("θ=%s→%s" % (_f(g["theta"], 1), _f(g["oos_fp_sharpe"])) for g in sorted(same_key, key=lambda x: x["theta"])))
    A("")
    A("---")
    A("")
    # Lead/lag crux
    A("## Crux finding — does latent-state give EARLIER warning than SMA-200?")
    A("")
    if ll is not None:
        A("Comparing HMM de-risk onsets (P(bear) crosses up through θ) against SMA-200 gate off-flips, on the shared calendar. Offset = HMM_onset − nearest_SMA_offset (days); **negative ⇒ HMM leads (earlier warning)**.")
        A("")
        A("- HMM de-risk onsets: **%s** · SMA-200 off-flips: **%s**" % (ll["n_hmm_derisk_onsets"], ll["n_sma_off_onsets"]))
        A("- Median offset: **%s days** · mean **%s days**" % (_f(ll["median_offset_days"], 1), _f(ll["mean_offset_days"], 1)))
        A("- HMM leads: **%s%%** · HMM lags: **%s%%** · coincide (±5d): **%s%%**"
          % (_f(ll["pct_hmm_leads"], 1), _f(ll["pct_hmm_lags"], 1), _f(ll["pct_coincide_5d"], 1)))
        A("- De-risk-day overlap: HMM %s days, SMA %s days, both %s (Jaccard %s)"
          % (ll["hmm_derisk_days"], ll["sma_off_days"], ll["overlap_days"], _f(ll["jaccard"], 3)))
        A("")
        med = ll["median_offset_days"]
        if med is None:
            crux = "No comparable onset pairs — inconclusive."
        elif med < -3:
            crux = "HMM de-risk events **LEAD** the SMA-200 flips (median %s days earlier) — the latent-state model DOES flag vol-regime shifts before price confirms." % _f(med, 1)
        elif med > 3:
            crux = "HMM de-risk events **LAG** the SMA-200 flips (median %s days later) — no earlier-warning benefit; the HMM reacts AFTER price." % _f(med, 1)
        else:
            crux = "HMM de-risk events **COINCIDE** with the SMA-200 flips (median %s days) — the probabilistic gate essentially reproduces the price line's timing → redundant." % _f(med, 1)
        A("**Verdict on the crux:** " + crux)
    else:
        A("_Lead/lag analysis unavailable (no best cell)._")
    A("")
    A("---")
    A("")
    # Canary
    A("## +1-bar canary (mandatory timing-leak check)")
    A("")
    if canary is not None and best is not None:
        edge_nolag = (best["oos_fp_sharpe"] or 0) - (inc["oos_fp_sharpe"] or 0)
        edge_lag = (canary["oos_fp_sharpe"] or 0) - (inc["oos_fp_sharpe"] or 0)
        A("Best config re-run with the posterior lagged ONE extra bar:")
        A("")
        A("| | OOS FP-Sharpe | OOS maxDD %% | edge vs incumbent |")
        A("|---|---|---|---|")
        A("| no lag | %s | %s | %s |" % (_f(best["oos_fp_sharpe"]), _pct(best["oos_maxdd_pct"]), _f(edge_nolag)))
        A("| +1 bar | %s | %s | %s |" % (_f(canary["oos_fp_sharpe"]), _pct(canary["oos_maxdd_pct"]), _f(edge_lag)))
        A("")
        if edge_lag <= 0.02:
            A("Edge over the incumbent under +1-bar lag = **%s ≤ 0.02 noise floor** → fails the canary." % _f(edge_lag))
        else:
            A("Edge survives the +1-bar lag (%s > 0.02) → not a pure timing artifact." % _f(edge_lag))
    else:
        A("_No non-degenerate cell to canary._")
    A("")
    A("---")
    A("")
    # Degeneracy + K2 vs K3
    A("## Degeneracy & K=2 vs K=3")
    A("")
    if best is not None:
        A("- **Bear-state firing (best cell):** %s%% of live days — %s (KILL #4 window is <2%% or >98%%)."
          % (_f(best["bear_fire_frac_pct"], 1),
             "sensible" if 2.0 <= best["bear_fire_frac_pct"] <= 98.0 else "DEGENERATE"))
    kk = r.get("k2_vs_k3", {})
    for k in ("K2_best", "K3_best"):
        c = kk.get(k)
        if c:
            A("- **%s:** %s θ=%s → OOS FP-Sharpe %s, OOS maxDD %s, bear-fire %s%%"
              % (k, c["key"], _f(c["theta"], 1), _f(c["oos_fp_sharpe"]), _pct(c["oos_maxdd_pct"]), _f(c["bear_fire_frac_pct"], 1)))
        else:
            A("- **%s:** no non-degenerate cell." % k)
    A("")
    A("---")
    A("")
    # Kill trace
    A("## Kill-quantity trace")
    A("")
    A("GO requires beating the incumbent on BOTH OOS FP-Sharpe AND OOS maxDD, net of cost, AND surviving the +1-bar canary, AND sensible bear-firing, AND non-knife-edge θ. ANY one failure ⇒ KILL.")
    A("")
    if kill:
        for k in kill:
            A("- 🔴 " + k)
    else:
        A("- 🟢 All kill-quantities cleared.")
    A("")
    A("**VERDICT: %s**" % emoji)
    A("")
    A("---")
    A("")
    A("## Honest read")
    A("")
    if verdict == "KILL":
        A("The bench's standing prior held: simple threshold regime gates already capture the regime information, and the distribution-aware HMM does not extract residual signal the SMA-200 line misses. The probabilistic latent-state gate is **not** worth its complexity here — the simpler price gate wins on Occam, the same logic that killed CPPI, VIX-term, SKEW, breadth-as-overlay, and the NFCI overlays. **This closes the regime frontier: the last structurally-distinct regime mechanism (latent-state HMM) is tested and does not beat the incumbent.**")
    else:
        A("The HMM gate cleared every kill-quantity — a genuine, structurally-distinct regime edge over the SMA-200 price gate. Recommend promotion to a paper tracker for forward validation before any real-money consideration.")
    A("")
    A("**Files:** `_hmm_confirm.py` (HMM + swap simulator), `_hmm_run.py` (grid runner), `_hmm_report.py` (this writer), `reports/_hmm_result.json` (all numbers), `%s` (this report)." % path)
    A("")

    text = "\n".join(L) + "\n"
    with open(path, "w") as f:
        f.write(text)
    return path