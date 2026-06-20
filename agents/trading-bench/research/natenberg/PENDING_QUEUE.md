# Natenberg read — pending chunk queue  (UPDATED 18:13Z — book is ~fully covered)

KEY REVISION: the first-wave agents that reported "context overflow" actually WROTE
complete, high-quality notes BEFORE dying (overflow fired on a post-write re-read step).
Verified on disk. So coverage is far better than the failures implied.

## Coverage map (chapter → note(s) on disk, verified)
- ch1-4   → 01_foundations.md ✅
- ch5     → 01c_ch5_pricing.md  ⏳ (ONLY real gap; patch agent natenberg_p5 spawned 18:13Z)
- ch6-9   → 02_greeks_hedging.md ✅ (full: all 5 Greeks Delta/Gamma/Theta/Vega/Rho + vol + hedging + ch9)
            also 02a_vol_greeks1.md (ch6+ch7Delta) + 02b_hedging_greeks2.md (ch8+ch9Delta) ✅
- ch10-14 → 03_spreads.md ✅  + 03a_volspreads.md (ch10-11) + 03b_verticals_synthetics.md (ch12-14) ✅
- ch15-17 → 04_arbitrage_exercise_hedging.md ✅ (parity, conversion/reversal/box/jellyroll, early exercise, hedging)
- ch18-21 → 05_models_vol_position.md ✅ (BS, binomial, vol-revisited+EWMA/GARCH/cones, position analysis)
            also 05a_bs_binomial.md + 05b_volrevisited_position.md ✅
- ch22-25 → 06_realworld_skew_volcontracts.md ✅ (index, model-failures A-G, skew, variance contracts)
            also 06a_realworld_indexfutures.md + 06b_skew_volcontracts.md (in flight; adds 1/K² detail) ⏳

## DROPPED as redundant (original notes already cover; do NOT spawn)
- ~~natenberg_p7 (ch7 full Greeks)~~ — 02_greeks_hedging.md already has all 5 Greeks in full.
- ~~natenberg_b4a / b4b (arbitrage/hedging re-split)~~ — 04_arbitrage_exercise_hedging.md already complete.

## Minor residual (note in synthesis, no re-run needed)
- ch9 tail (Gamma/Theta/Vega peaking + Lambda full): present as "standard definition" flag in 02_greeks; acceptable.
- 1/K² variance-swap weighting: b6b (in flight) is tasked to capture it.

## Then (gated on ch5 note landing + b6a/b6b finishing)
1. Synthesis agent → reports/NATENBERG_SYNTHESIS.md. Reconcile the prefer-original-vs-half notes (originals are the spine; halves add math-accuracy detail + seam flags). Produce: (a) consolidated theory digest, (b) "what's actionable for OUR project" — esp. vol estimation.
2. Implementation agent → vol toolkit (realized-vol estimators close-to-close/Parkinson/Garman-Klass/Yang-Zhang, EWMA + GARCH(1,1), vol-cone percentile + implied-minus-realized + IV term-structure slope signals, BS+binomial reference pricer+Greeks). Unit-tested vs known values. Walk-forward gated. PAPER-ONLY, NO options orders.

## Hard lesson (→ TOOLS.md): split big-PDF subagent reads by CHAPTER LINE-ANCHOR in the clean full-text extract, ≤~2800 lines/chunk. Page-number splits drift (PDF page ≠ printed page) and land mid-chapter; >~3000 lines overflows the read+write step. AND a context-overflow at the END of a run may still have produced a complete artifact — VERIFY the file before re-running.
