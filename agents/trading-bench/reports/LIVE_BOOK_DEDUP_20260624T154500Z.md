# Live-Book De-Duplication — Acting on the Inter-Strategy Correlation Audit

**Date:** 2026-06-24 (UTC stamp `20260624T154500Z`)
**Author:** Tessera (trading-bench)
**Type:** Risk-officer hardening action on the LIVE paper tournament book
**Trigger:** `reports/INTERSTRATEGY_CORRELATION_20260622.md` produced concrete cull/downweight
recommendations on 2026-06-22 but **nothing had been acted on** — the live crontab still ran all
12 strategies including the proven duplicates. This report closes that gap.

---

## TL;DR

**The live cron roster was ~9 copies of one long-equity-beta bet (≈2.2 effective independent bets).**
Acted on the audit: **collapsed the three proven-duplicate clusters to one representative each**,
taking the live cron from **12 → 8 strategies**, and **flattened the one dangling position** left by a
retired sleeve. Net effect: effective independent bets rise from ~2.2 toward ~3–3.5 **without removing
a single genuine edge** — just by not paying 9× of the risk budget for one factor. Fully reversible
(all code + tournament history retained; only the crontab roster line changed).

---

## 1. Evidence the duplicates are real (LIVE fills, not just backtest correlation)

The 2026-06-22 audit measured backtested daily-return correlation. I cross-checked against **actual
live paper fills** in `tournament.db` — the duplicates are confirmed empirically:

| Pair | Backtest ρ | Live fills | Verdict |
|---|---|---|---|
| `breakout_xlk` vs `breakout_xlk_regime` | **1.00** | Identical: same days, same qty, prices 184.41 vs 184.49 — regime gate **never changed a live decision** | Pure duplicate |
| `sma_crossover_qqq` vs `sma_crossover_qqq_regime` | **0.99** | Identical: same days, same qty, prices 728.07 vs 728.45 — regime gate **never changed a live decision** | Pure duplicate |
| `leveraged_long_trend_paper` vs `tqqq_cot_combo` | **0.91** | Same 3 buys 6/15–6/17 at near-identical prices; combo is a strict superset (COT only de-risks crowded weeks) | Redundant; combo dominates |
| `sma_crossover_qqq_rth` vs `sma_crossover_qqq` | 1.00 *(daily artifact)* | **Genuinely diverged** live: only 2 fills, entered 15:01 not 14:00, **skipped** the 6/12 & 6/22 entries the parent took (RTH gate binds on the live 1Hour clock) | **Real variant — KEPT** |

The regime-variant ρ≈1.00 is *expected by construction* (same parent + a filter that rarely binds) —
and the live fills prove the filter has **never once** produced an independent decision. They do not
earn separate capital slots.

## 2. The decision (logged, reversible)

| Cluster | Members | KEPT (why) | RETIRED from cron (why) |
|---|---|---|---|
| **XLK breakout** | breakout_xlk, breakout_xlk_regime, breakout_xlk__mut_c382b1 | **breakout_xlk__mut_c382b1** — best standalone Sharpe 0.510, regime-conditional stop = best DD behavior, current leaderboard #1 | breakout_xlk, breakout_xlk_regime (ρ=1.00, zero live divergence) |
| **QQQ SMA-cross** | sma_crossover_qqq, sma_crossover_qqq_regime, sma_crossover_qqq_rth | **sma_crossover_qqq_regime** (marginally best Sharpe 0.532) **+ sma_crossover_qqq_rth** (genuinely divergent live) | sma_crossover_qqq (ρ=1.00 to regime, zero live divergence) |
| **TQQQ vol-target** | leveraged_long_trend_paper, tqqq_cot_combo, allocator_blend | **tqqq_cot_combo** (strict superset, COT cuts 2022 DD) **+ allocator_blend** (adds GLD/TLT/SPY rotation) | leveraged_long_trend_paper — its VT sleeve already lives **inside** allocator_blend → triple-count of TQQQ |
| Diversifiers / other | rsi_oversold_spy, macd_momentum_iwm, volume_breakout_qqq | **All kept** — rsi_oversold_spy (ρ≈0.02, negative in stress = the book's only real hedge), macd_momentum_iwm (ρ≈0.21, weak but real), volume_breakout_qqq (loosely attached) | — |

**New live roster (8):** `breakout_xlk__mut_c382b1`, `sma_crossover_qqq_regime`, `sma_crossover_qqq_rth`,
`rsi_oversold_spy`, `volume_breakout_qqq`, `macd_momentum_iwm`, `tqqq_cot_combo`, `allocator_blend`.

## 3. Execution + safety

1. **Crontab:** backed up verbatim (`memory/crontab_backup_20260624T153329Z.txt`), then a **single-line
   surgical edit** (Python replace, asserted exactly 1 occurrence). Diff = exactly one line; all 7
   other-agent/task cron lines (job-search, making-money, canvas, polymarket) preserved byte-for-byte;
   20 lines → 20 lines.
2. **Dangling positions:** checked net attributed position of all 4 retired strategies. Three were
   already **FLAT**; `leveraged_long_trend_paper` held **3.627 TQQQ** (~$273, bought 6/15–6/17 at the
   old $1000-notional scale, never sold). Removing it from cron would orphan that exposure.
3. **Flatten:** one-shot `_flatten_retired.py` reusing the runner's OWN primitives verbatim
   (`build_position_state` → clamped `submit_market_order(sell, qty=held)` → `log_trade` +
   `clear_strategy_state`) — the exact CLOSE branch the runner runs. Killswitch + paper-account guards
   honored. Dry-ran first, then executed: **SELL 3.627 TQQQ @ $75.30** (trade_id 75), reconciled to
   `filled`. The clamp sold **only** the retired sleeve's attributed qty — the other strategies'
   commingled TQQQ (tqqq_cot_combo 12.707sh, allocator_blend 0.158sh) was untouched.
4. **Integrity:** `position_drift` → `REAL_DRIFT = False`; all equities match Alpaca to **0.00e+00**
   (TQQQ DB 12.865 = Alpaca 12.865, XLK flat). Book fully consistent post-action.

## 4. What this does and does NOT change

- **DOES:** lift effective independent bets ~2.2 → ~3–3.5 by retiring zero-information duplicates;
  remove an off-parity ($1000-scale) dangling TQQQ position; align the live capital footprint with the
  audit's risk-parity-aware recommendation.
- **DOES NOT:** delete any strategy code, candidate, or tournament history (all retained; re-addable to
  cron in one line). Does NOT touch any protected runner/risk file. Does NOT change the champion
  (`allocator_blend` paper clock continues unaffected). Does NOT move real money.

## 5. Caveats / open follow-ups

- The audit's §6 also recommended *overweighting* the two real diversifiers (rsi_oversold_spy,
  macd_momentum_iwm) under an ERC framing. The tournament currently runs **flat $100 per strategy**, so
  capital weighting is uniform-by-strategy; a cluster-aware / ERC weighting layer is a **separate
  infra item** (not done here — flagged to BACKLOG). De-duplication is the high-leverage first step
  (it fixes the *9×-counting*); ERC weighting is the polish.
- For the **Saturday leaderboard**, the retired strategies still have their historical fills and remain
  scoreable as past competitors; they simply no longer accrue new trades.

---
*Artifacts: crontab backup `memory/crontab_backup_20260624T153329Z.txt`; flatten tool
`_flatten_retired.py`; source audit `reports/INTERSTRATEGY_CORRELATION_20260622.md`. No protected file
modified.*
