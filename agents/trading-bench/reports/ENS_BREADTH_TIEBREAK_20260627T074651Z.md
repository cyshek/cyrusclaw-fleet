# ENS-BREADTH TIEBREAK — ens_sma_breadth{50,100,200} vs the live TQQQ vol-target sleeve

**UTC:** 2026-06-27T07:46:51Z · **Author:** trading-bench (subagent) · **Mode:** PAPER RESEARCH ONLY (no orders, no spend, engine/live-sleeve/runner untouched)
**Engine:** `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py :: run_backtest_voltarget` (ground truth, untouched)
**Driver:** `reports/_ens_breadth_tiebreak_driver.py` · **Results JSON:** `reports/_ens_breadth_tiebreak_result.json`

---

## ⛔ VERDICT — **NO.**

**Under the LIVE sleeve's real configuration (`vix_gate=False`) and the engine's own continuous-slice OOS convention, ens_sma_breadth {50,100,200} does NOT robustly beat the live single-SMA-200 vol-target sleeve OOS. It LOSES on Sharpe (OOS fp-Sharpe 0.810 vs base 0.837, ΔS −0.027) and only modestly compresses drawdown (−30.69% vs −34.52%, +3.83pp), and it does NOT beat the base under the +1-day canary. It is a weak drawdown-compressor with a Sharpe penalty — not a promotable edge. Do NOT wire {50,100,200} to the paper sleeve.**

**Which prior driver was right:** the **NEGATIVE** driver (`reports/_multihorizon_trend_driver.py`) was right *for the live sleeve*. It reported `sma_frac ΔS −0.025`; I reproduce **ΔS −0.027** through the real engine under the same convention.

**WHY the two drivers disagreed — it was the VIX gate, NOT the OOS-slicing convention.** A clean 2×2 decomposition (below) shows the ens-vs-base ΔSharpe sign is **entirely** determined by `vix_gate`, and is **invariant** to whether OOS is sliced-from-continuous or cold-resimmed. The PASS driver won only because it ran `vix_gate=True` — which is **not** the live sleeve.

---

## 1. The ground-truth correction that settles it

The task framed the PASS driver as "matching the live engine" because it applies the VIX gate. **That framing is inverted.** The live sleeve does **not** run the VIX gate:

| Source | `vix_gate` | FULL total | FULL Sharpe(pop) | FULL maxDD |
|---|---|---|---|---|
| **Live `params.json`** (`strategies/leveraged_long_trend_paper/`) | **`false`** | — | — | — |
| Engine `run_backtest_voltarget(vix_gate=False)` | False | **+2002.1%** | **0.854** | **−34.52%** |
| Engine `run_backtest_voltarget(vix_gate=True)` | True | +1262.2% | 0.774 | −34.88% |
| **Documented anchor** (`TQQQ_VOLTARGET_GATE_WRITEUP_20260621`, `VERDICT_20260613`) | "VIX-**off**" | +2,002% / +1,881%* | 0.854 / 0.842* | −34.5% |

\* The writeup's headline +1,881%/0.842 is the *ER-loaded* rung; the bare 2bps engine number is +2,002%/0.854. Both are the **VIX-off** path. The VERDICT explicitly describes the sleeve as *"TQQQ behind an SMA-200 gate, **VIX-off**, T-bill cash."*

- **`vix_gate=False` reproduces the documented anchor bit-for-bit** (+2002.1% / 0.854 / −34.52%). This is the live sleeve.
- **`vix_gate=True` (+1262%/0.774) is a DIFFERENT, non-live configuration.** The PASS driver (`_ensemble_trend_driver.py`, line 216 `vix_gate=True`) baselined against this. Its quoted "base +1262.2%, fpS 0.774" is the tell — that is the VIX-**on** engine, not the live sleeve.
- The engine's **own** frozen-OOS validator `validate_oos_voltarget.py` uses `vix_gate` default (**False**) and slices OOS from the continuous full-span equity via `subwindow_stats` — i.e. the **continuous-slice** convention this task mandates. So the mandated convention = the validator's convention = the live sleeve's convention.

---

## 2. PARITY — the wrapper IS the real engine (not a near-copy)

The driver's baseline path was reconciled against `run_backtest_voltarget` over the full span, **both** VIX settings:

| Parity check | max&#124;Δequity&#124; over 4118 days | engine FULL total | engine FULL Sharpe(pop) | engine FULL maxDD |
|---|---|---|---|---|
| `vix_off` | **0.00e+00** | +2002.1% | 0.854 | −34.52% |
| `vix_on` | **0.00e+00** | +1262.2% | 0.774 | −34.88% |

Zero divergence on every one of 4118 days. The breadth path reuses the identical helpers (`bd.dbc` adjclose, `realized_ann_vol`, `target_weight`, `_clamp`, `bd._vix_risk_off`, `bd._tbill_daily_rate`) and differs from the baseline **only** in the risk-on scaler `g`. So every number below is the true engine, with the live VIX-off setting.

---

## 3. The decisive decomposition — VIX gate flips the sign; OOS-slicing does not

OOS fp-Sharpe ΔS = (ens{50,100,200} − base), all four regimes, real engine:

| Regime | base OOS fpS | ens OOS fpS | **ΔS** | sign |
|---|---|---|---|---|
| `vix=False`, **continuous-slice** (live + validator) | 0.837 | 0.810 | **−0.027** | **ens LOSES** |
| `vix=False`, cold-resim-from-2018 | 0.837 | 0.810 | **−0.027** | ens LOSES |
| `vix=True`, continuous-slice | 0.778 | 0.805 | **+0.028** | ens wins |
| `vix=True`, cold-resim-from-2018 | 0.778 | 0.805 | **+0.027** | ens wins |

**Read this table directly:**
- **The OOS-slicing convention is irrelevant to the ΔS sign.** Within each `vix` setting, continuous-slice and cold-resim give the *same* ΔS (−0.027 = −0.027; +0.028 ≈ +0.027). The 2018-split harness artifact the task flagged (baseline level 0.858 vs 0.837) shifts the *baseline level* but cancels in the ens-minus-base *difference*.
- **The VIX gate is the entire driver of the disagreement.** Flip `vix_gate` and the sign flips: VIX-off → −0.027, VIX-on → +0.027.
- **The live sleeve is VIX-off** → the live-relevant number is **ΔS −0.027 (ens loses on Sharpe).**

Mechanism: with the VIX overlay OFF, the binary SMA-200 gate is the sleeve's *only* regime filter. Replacing it with a soft breadth scaler dilutes the clean in/out call (holding 2/3 or 1/3 through gate edges) and gives up Sharpe without enough DD payoff. With the VIX overlay ON, the engine already carries a second risk layer, so the gentler breadth de-risking complements rather than competes — hence the apparent win. The live sleeve does not run VIX-on, so that synergy is not available to it.

---

## 4. Primary {50,100,200} vs base — full / IS / OOS (live convention, vix-off, 2bps)

| Segment | base fpS | base maxDD | base avgW | ens fpS | ens maxDD | ens avgW | **ΔfpS** | **ΔmaxDD** |
|---|---|---|---|---|---|---|---|---|
| FULL | 0.854 | −34.52% | 0.515 | — | — | — | — | — |
| IS (≤2017) | 0.849 | −33.16% | 0.594 | — | — | — | — | — |
| **OOS (≥2018)** | **0.837** | **−34.52%** | 0.442 | **0.810** | **−30.69%** | 0.417 | **−0.027** | **+3.83pp** |

- **Anchor confirmed:** base FULL +2002.1% / Sharpe 0.854 / maxDD −34.52%, base OOS total +363.0% vs SPX OOS +172.8% (+190pp). This matches the documented +2,002% / OOS ~+387% anchor (the small OOS gap is end-date: the writeup's +387% used an earlier as-of date; the *full* +2,002%/0.854 is exact). Baseline = ground truth for "the live sleeve." ✅
- **Canary:** base OOS canary fpS 0.864; ens{50,100,200} OOS canary fpS 0.837. **The ensemble under +1d (0.837) does not beat the base under +1d (0.864)** → `beatsUnderCanary=False`. The DD win survives the canary, but as a Sharpe matter the gap is not an edge.

---

## 5. Robustness — is {50,100,200} a robust win or a knife-edge? (live convention, vix-off)

OOS metrics for all 8 nearby SMA triples, same convention + canary. `dOOSfp` and `dMdd_pp` are vs base (base OOS fpS 0.837, maxDD −34.52%). `canDrop` = ens own +1d-canary fpS minus ens fpS.

| Triple | OOS fpS | dOOSfp | OOS maxDD% | dMdd_pp | OOS tot% | canary OOS fpS | beats base Sharpe? | beats base under canary? | classification |
|---|---|---|---|---|---|---|---|---|---|
| **50-100-200** ← asked | 0.810 | **−0.027** | −30.69 | +3.83 | 298.5 | 0.837 | ❌ | ❌ | **DD-only (weak)** |
| 40-100-200 | 0.817 | −0.019 | −28.43 | +6.10 | 297.5 | 0.861 | ❌ | ❌ | DD-only |
| 60-120-200 | 0.814 | −0.023 | −30.33 | +4.20 | 307.5 | 0.897 | ❌ | ✅ | DD-only |
| 50-100-150 | 0.826 | −0.010 | −31.16 | +3.36 | 312.7 | 0.841 | ❌ | ❌ | DD-only |
| 50-125-250 | 0.832 | −0.004 | −27.48 | +7.04 | 321.1 | 0.880 | ❌ | ✅ | DD-only |
| **30-90-180** | **0.855** | **+0.018** | **−22.55** | **+11.97** | 315.2 | 0.920 | ✅ | ✅ | **PASS** |
| 75-150-250 | 0.820 | −0.017 | −25.64 | +8.88 | 320.1 | 0.861 | ❌ | ❌ | DD-only |
| 20-100-200 | 0.826 | −0.011 | −26.06 | +8.46 | 285.3 | 0.869 | ❌ | ✅ | DD-only |

**Findings:**
- **{50,100,200} is BELOW-pack on Sharpe** (ΔS −0.027, the *worst* of the 8) **and smallest on DD compression** (+3.83pp, the *worst* of the 8). It is the weakest member of the family, not a mid-of-pack robust win.
- **7 of 8 triples lose on OOS Sharpe** under the live VIX-off convention. Only **{30,90,180}** beats base on Sharpe (ΔS +0.018) AND survives the canary AND compresses DD most (+11.97pp). So a breadth scaler *can* help the live sleeve — but it needs **shorter horizons** {30,90,180}, not the asked {50,100,200}. That is a genuinely interesting follow-up, but it is not the question posed, and {30,90,180}'s +0.018 Sharpe edge is still small.
- **Every triple compresses drawdown** (all dMdd_pp positive). So the breadth construction is a reliable *DD compressor* across the family; it is just not a reliable *Sharpe* improver under VIX-off.

---

## 6. Per-year OOS — is the DD win broad or one event? (base vs {50,100,200})

| Year | base ret% | ens ret% | base fpS | ens fpS | base maxDD% | ens maxDD% |
|---|---|---|---|---|---|---|
| 2018 | −8.5 | −2.7 | −0.178 | 0.010 | −28.71 | **−21.43** |
| 2019 | 24.8 | 15.7 | 0.998 | 0.724 | −22.66 | −30.69 |
| 2020 | 41.6 | 37.3 | 1.394 | 1.355 | −20.76 | −18.83 |
| 2021 | 40.5 | 24.3 | 1.345 | 0.957 | −16.47 | −16.09 |
| 2022 | −17.8 | −16.4 | −2.534 | −2.013 | −17.81 | −16.36 |
| 2023 | 50.8 | 50.5 | 1.794 | 1.938 | −18.17 | −16.20 |
| 2024 | 34.0 | 25.4 | 1.173 | 0.978 | −19.71 | −19.16 |
| 2025 | 15.2 | 19.8 | 0.696 | 0.892 | −16.65 | −11.29 |
| 2026 | 8.8 | 11.9 | 0.768 | 1.076 | −16.65→−14.34 | −11.19 |

**Reading:**
- The DD compression is **broad-ish but shallow** — ens has the shallower (better) max-DD in 7 of 9 years, but only by a few points each (2018: +7.3pp, 2025: +5.4pp, 2026: +3.2pp). Net OOS maxDD improves +3.83pp.
- **It costs return/Sharpe in the strong-trend years** (2019: −9.1pp ret / −0.27 Sharpe; 2021: −16.2pp / −0.39; 2024: −8.6pp / −0.20) because the breadth scaler holds *less* than full during clean uptrends when the binary gate would be fully on. That is exactly why the OOS Sharpe loses.
- 2019 is the one year where ens has a **worse** max-DD (−30.69% vs −22.66%) — the soft scaler stayed partially exposed into the Q4-2018→2019 chop where the binary gate had cleanly exited. So even the DD story has a hole.
- Net: not a single-event artifact, but a **diffuse small DD trim bought with a diffuse Sharpe/return give-up** — a wash that tilts slightly negative on the risk-adjusted ruler.

---

## 7. Honest bottom line

- **ens_sma_breadth {50,100,200} on the live (VIX-off) sleeve = a weak drawdown compressor with a Sharpe penalty.** OOS Sharpe 0.810 < 0.837 (ΔS −0.027), OOS maxDD −30.69% vs −34.52% (+3.83pp). It does not beat the base under the canary. **NO — do not promote it.**
- **The NEGATIVE driver was right for the live sleeve.** The PASS driver's +0.027 win was real arithmetic but on the **wrong baseline** (`vix_gate=True`, +1262%/0.774), which is not the live sleeve (`vix_gate=False`, +2002%/0.854).
- **The flip was the VIX gate, full stop — not the OOS-slicing convention** (2×2 decomposition §3: ΔS is invariant to slicing, flips with VIX). The OOS-slicing artifact the task identified is real but affects only the baseline *level*, not the ens-vs-base *delta*.
- **If anything is worth a follow-up** (separate question), it is **{30,90,180}**: the only triple that beats the live base on OOS Sharpe (ΔS +0.018) AND survives the canary AND compresses DD the most (+11.97pp, OOS maxDD −22.55%). Even so its Sharpe edge is small (+0.018) and it is a leverage-premium reshaping, not new alpha. Recommend a dedicated canary+cost-ladder pass before considering it — but that is NOT a green light to wire {50,100,200}.

---

## 8. Integrity check

| Item | BEFORE | AFTER | status |
|---|---|---|---|
| `runner/backtest.py` md5 | `717c36e68941b9258f86bc99950de788` | `717c36e68941b9258f86bc99950de788` | ✅ unchanged |
| `runner/risk.py` md5 | `e303317e0d2ac796a1fa43e372f0a113` | `e303317e0d2ac796a1fa43e372f0a113` | ✅ unchanged |
| `runner/runner.py` md5 | `0f763975f2d8ba535352f6a8306afb8b` | `0f763975f2d8ba535352f6a8306afb8b` | ✅ unchanged |
| `strategies/leveraged_long_trend_paper/strategy.py` | mtime 2026-06-13 07:36:40 | mtime 2026-06-13 07:36:40 | ✅ untouched |
| `strategies/leveraged_long_trend_paper/params.json` | mtime 2026-06-13 07:36:40 | mtime 2026-06-13 07:36:40 | ✅ untouched |
| Engine `backtest_daily_voltarget.py` | mtime 2026-06-09 05:08 | mtime 2026-06-09 05:08 | ✅ untouched |

New files written (reports/ only): `_ens_breadth_tiebreak_driver.py`, `_ens_breadth_tiebreak_result.json`, this verdict. No orders, no spend, no STOP_TRADING change, no crontab/*.db touched.

**Reproduce:** `cd <workspace> && PYTHONPATH=. python3 reports/_ens_breadth_tiebreak_driver.py`
