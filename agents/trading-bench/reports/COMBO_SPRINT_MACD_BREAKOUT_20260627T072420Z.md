# Deterministic Cross-Symbol Combo Sprint — macd_momentum_iwm × {breakout_xlk, volume_breakout_qqq}

_2026-06-27 · trading-bench · DETERMINISTIC mechanical fusion (the controlled re-run of yesterday's noisy-LLM prose round)_

## TL;DR — VERDICT: **CLOSE** (no robust promotable child)

Clean, leak-free, timestamp-aligned **mechanical** fusion of the WEAK-orthogonal
momentum parent `macd_momentum_iwm` (IWM, MACD 12/26/9) with the STRONG breakout
parents `breakout_xlk` (XLK) and `volume_breakout_qqq` (QQQ) **does NOT** produce a
child that robustly beats the best solo parent OOS net of cost.

- **One** AND-fusion child appears to win at face value — `AND_qqq_gated_by_iwm`
  (OOS Sharpe **+1.388** vs parent **+1.180**, ΔSharpe **+0.208**, Δmedian-trade
  **+1.079pp**, with FEWER trades 30 vs 56) — but it **fails the canary**: adding
  just **+1 bar** of extra lag to the IWM gate collapses it to **+0.873**
  (ΔSharpe vs parent **−0.307**). A genuine momentum-regime gate (regimes persist
  for dozens of hourly bars) cannot lose ~0.5 Sharpe from one extra hour of lag —
  this is the signature of a **timing-sensitive / near-leak fit, not a robust edge.**
- The other AND child (`AND_xlk_gated_by_iwm`) **fails outright** (ΔSharpe −0.056).
  So AND-fusion does NOT help BOTH strong parents — it fragilely helps one and
  hurts the other. The "win must be robust across both parents" rail is not met.
- **OR-fusion cleanly reproduces yesterday's prose-round dilution finding**:
  `OR_qqq` ΔSharpe **−0.910** (massive dilution), `OR_xlk` +0.008 (neutral).

**Conclusion:** cross-parent equity **signal-level** fusion is value-destructive /
non-robust here, **mechanically** — not merely as an artifact of the LLM's noisy
prose reconstruction. Yesterday's REJECT holds under an exact, controlled,
leak-free construction. This **CLOSES the cross-parent-equity signal-fusion lane**
with confidence. (Book-level allocation/sleeve weighting remains a separate,
untested avenue — see prior verdict's lesson #3.)

## Why this sprint (context)

`reports/EQUITY_CROSSPARENT_COMBO_VERDICT_20260626.md` ran LLM-PROSE macd×breakout
fusion → all 5 REJECT_GATE (medSharpe 0.55 < parent 0.66; OR-fusion diluted with
the weaker signal's lower-quality entries → raw return up, Sharpe DOWN). Its
lesson #2: a winner must pair STRONG + WEAK-ORTHOGONAL (exactly
macd_momentum_iwm × breakout) — but done as **controlled mechanical fusion**, not
noisy LLM reconstruction. This sprint is that deterministic cross-symbol AND/OR
test: replace the LLM's blind prose fusion with an exact, timestamp-aligned,
leak-free mechanical fusion and see if the clean version survives where the noisy
one failed. **It does not.**

## Data, split, alignment (stated adaptations)

- **Panel:** Alpaca 1Hour bars via `runner/bars_cache`. IWM/XLK/QQQ all span
  **2020-07-27T13:00Z → 2026-06-24T20:00Z** (IWM 12,154 / XLK 10,523 / QQQ 12,703
  native bars). The three symbols sit on **different hourly grids**.
- **DATA REALITY ADAPTATION:** the standard IS/OOS@2018 split is **impossible**
  (Alpaca hourly floor = 2020-07-27). Used the **deepest honest split**:
  **IS 2020-07-27 → 2023-12-31, OOS 2024-01-01 → 2026-06-24.**
- **Cross-symbol alignment (the leak-sensitive part):** fusion children trade on
  the **INNER-JOIN** of (strong-parent symbol ∩ IWM) timestamps — XLK panel
  10,483 bars, QQQ panel 11,939 bars. Naive same-index alignment WOULD leak
  (XLK has 45, QQQ 2,225, IWM 1,676 non-shared timestamps). The IWM-MACD gate
  state for the decision at panel bar T is taken from the IWM bar that **closed
  at-or-before T**, then **lagged one IWM bar** (D+1-lag discipline at hourly
  granularity) → the gating state is from a bar that closed **strictly before T**;
  **no same-bar information is used.** Canary adds **+1 more bar**.
- **Sharpe:** full-period **continuous-span** (the bench's load-bearing ruler) —
  the engine's per-bar equity-return Sharpe on each contiguous slice, annualized
  with `runner.backtest.bars_per_year("1Hour", is_crypto=False)` = (510/60)×252 =
  **2142 bars/yr**. Headline numbers are NEVER median-of-windows.
- **Cost:** 2 bps one-way on traded notional (bench `alpaca_stocks` standard);
  0/5 bps sensitivity also run.
- **Engine fidelity:** every config runs through `runner.backtest.backtest(...)`
  with a custom `decide_fn`, so cost/fill/Sharpe/risk-cap conventions MATCH the
  bench exactly. **Validated:** the REAL parent `strategy.py` modules run through
  the engine on the native OOS slice produce **bit-identical** OOS Sharpe / trade
  counts to my reconstructed solo `decide_fn`s (breakout_xlk −0.122/142,
  volbreak_qqq +1.003/60, macd_iwm −0.203/152) → the mechanical reconstruction is
  faithful (same indicator math, lookback, entry/exit).

## (1) Solo baselines (panel, 2 bps)

| Strategy | full Sharpe | IS Sharpe | OOS Sharpe | OOS ret | OOS trades | OOS med-trade |
|---|---|---|---|---|---|---|
| breakout_xlk (panel) | +0.272 | +1.021 | **−0.146** | −1.36% | 142 | −0.696% |
| volume_breakout_qqq (panel) | +0.510 | +0.211 | **+1.180** | +1.12% | 56 | −0.222% |
| macd_momentum_iwm (native) | +0.034 | +0.207 | **−0.203** | −0.44% | 152 | −0.257% |

**Sanity vs known WF Sharpes (~1.36 / ~1.39 / ~0.66):** the IS breakout_xlk
+1.02 is in the right ballpark; the lower full/OOS numbers are the **honest
FP-continuous-span** values, which `runner/fp_sharpe.py` explicitly documents as
generally LOWER than the median-of-windows WF aggregates the ~1.36/~1.39 quotes
come from. Critically, the reconstruction reproduces the **real strategy modules
bit-for-bit** (see Engine fidelity), so these are the true single-span OOS
numbers, not a reconstruction error. Best solo parent OOS = **volume_breakout_qqq
+1.180**.

## (2) AND-fusion (confirmation gate) — vs the relevant strong parent (OOS, 2 bps)

| Child | OOS Sharpe | ΔSharpe vs parent | Δmed-trade | trades (child→parent) | PROMOTE? |
|---|---|---|---|---|---|
| AND_xlk_gated_by_iwm | −0.202 | **−0.056** | +0.247pp | 106 → 142 | ❌ |
| AND_qqq_gated_by_iwm | +1.388 | **+0.208** | +1.079pp | 30 → 56 | ✅ (pre-canary) |

The gate does exactly what the thesis predicted **mechanically** — it cuts trades
(56→30 for QQQ; 142→106 for XLK) and on QQQ lifts both Sharpe and per-trade
return. But it only helps ONE parent (QQQ); on XLK the gate removes good trades
too and nets slightly worse.

## (3) OR-fusion (entry union) — confirms the prose-round dilution (OOS, 2 bps)

| Child | OOS Sharpe | ΔSharpe vs parent | trades (child→parent) |
|---|---|---|---|
| OR_xlk_union_iwm | −0.138 | +0.008 (neutral) | 160 → 142 |
| OR_qqq_union_iwm | +0.271 | **−0.910** | 242 → 56 |

OR-fusion balloons QQQ trade count 56 → 242 by pulling in every IWM-bull bar and
**craters** the Sharpe (+1.180 → +0.271). This is a **clean deterministic
replication** of yesterday's finding: the union dilutes with lower-quality entries
— raw participation up, risk-adjusted edge down. A clean replication of the
negative is itself a result.

## (4) CANARY — the decisive leak / robustness test (+1 extra bar of gate lag)

| Child | OOS Sharpe (lag 1) | OOS Sharpe (lag 2, canary) | ΔSharpe vs parent (canary) | survives? |
|---|---|---|---|---|
| AND_qqq_gated_by_iwm | +1.388 | **+0.873** | −0.307 | ❌ collapses |
| AND_xlk_gated_by_iwm | −0.202 | −0.285 | −0.140 | ❌ (already failing) |

**The one apparent winner does NOT survive the canary.** AND_qqq loses ~0.51
Sharpe (and falls below its parent) from a single extra bar of gate lag. Because
momentum regimes persist for many hourly bars, a *robust* regime gate would be
nearly insensitive to a one-bar shift; this fragility means the +0.208 edge was
**timing-sensitive noise**, not a durable cross-symbol signal. This is the lethal
cheap test and it fails.

## (5) Cost sensitivity (OOS) — academic, given the canary failure

| Config | 0 bps | 2 bps | 5 bps |
|---|---|---|---|
| breakout_xlk panel | −0.111 | −0.146 | −0.197 |
| AND_xlk gated | −0.176 | −0.202 | −0.241 |
| volume_breakout_qqq panel | +1.292 | +1.180 | +1.016 |
| AND_qqq gated | +1.464 | +1.388 | +1.276 |

AND_qqq beats its parent at every cost level — but this is moot: the canary shows
the edge isn't real, so cost-robustness of a non-robust edge is irrelevant.

## Honest answer to the sprint question

> Does clean DETERMINISTIC mechanical fusion survive where the noisy LLM prose
> round failed?

**No.** (a) OR-fusion reproduces the dilution REJECT mechanically. (b) AND-fusion
helps at most ONE of the two strong parents, and that single apparent win
(`AND_qqq`) **dies under a +1-bar canary** and is **not replicated by `AND_xlk`** —
failing the robustness rail (must help both / survive the canary). There is **no
promotable fusion child.** The cross-parent equity **signal-fusion** lane is
**confirmed value-destructive / non-robust here mechanically**, not just via the
LLM. **Lane CLOSED at the signal level.**

## Artifacts

- Driver: `reports/_combo_sprint_macd_breakout_driver.py`
- Result JSON: `reports/_combo_sprint_macd_breakout_result.json`
- This report: `reports/COMBO_SPRINT_MACD_BREAKOUT_20260627T072420Z.md`
- **No** file under `runner/`, `strategies/`, `crontab`, or any `*.db` was
  modified (all read-only). **No** orders placed, **no** spend. Paper-research only.

### Note on the driver's one perf shim (results-neutral)

The driver monkeypatches `runner.backtest.bars_cache.get_bars` **within the driver
process only** so the engine's internal SPY/1Day regime pre-fetch returns `[]`
(the engine then sets `regime=None`, identical to its crypto path). None of the
three reconstructed strategies read `market_state["regime"]`, so this removes a
dead O(n²) per-bar SPY scan **without changing any result** — confirmed by the
bit-identical real-module validation above. It does NOT modify any file on disk.
