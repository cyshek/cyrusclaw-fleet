# 🏆 Saturday Leaderboard — Week ending 2026-06-28 *(TEMPLATE — fill in Saturday)*

**Status:** TEMPLATE prepared 2026-06-22 (~2 PM PT); **partially pre-filled 2026-06-22 (~5 PM PT)** with live snapshots that won't change before Saturday (allocator Day-0 fills, tqqq_cot fills through 06-22, calibrator trip count, cron health). Fields tagged `⟢pre-filled 06-22` already carry live data but should be re-confirmed Saturday. Fill remaining bracketed `[…]` fields Saturday from live `tournament.db`, `allocator_paper.db`, and the Alpaca paper account.

> **Pre-fill note (06-22 5 PM PT):** Section 6 (breadth green-light) is **RESOLVED — the breadth lane was RUN today and came back CLOSE-REDUNDANT**; that section is rewritten below from a pending decision into a closed result. Section 4 trip count refreshed 14→**19/30**. Last-7-day cron health: **775 runs, 0 errors.**
**Data sources to pull Saturday:** `tournament.db` (per-strategy round-trips + P&L), `allocator_paper.db::daily_snapshots`, live Alpaca `account()` / `get_position()` for reconciliation, `runner/edge_calibrator.py` trip count, `reports/GO_LIVE_DECISION_PACKET.md` (gate checklist), `reports/LANE_BRIEF_breadth_regime.md` (breadth lane spec).

---

> # ⚠️ HARD CAVEAT — READ FIRST (do NOT bury this)
>
> **The tournament *looks* like 12 strategies but is effectively ~2.2 independent bets, sized ~9× on ONE tech-beta factor.**
>
> - **Effective bets (eff-N): 2.218 full / 2.534 downside** out of 12 live strategies.
> - **Top eigenvalue = 7.859/12 = ~65% of all variance on a single "long US-equity / NASDAQ-tech beta" factor.**
> - XLK×3 (`breakout_xlk` + `_regime` + `__mut_c382b1`), QQQ×3 (`sma_crossover_qqq` + `_regime` + `_rth`), TQQQ×2 (`leveraged_long_trend_paper` + `tqqq_cot_combo`), and `allocator_blend` (holds QQQ/SPY/TQQQ) are all the *same* tech-beta exposure.
> - Only genuine diversifiers in the book: the rotation/haven legs inside `allocator_blend` (GLD/TLT) and `tqqq_cot_combo`'s COT-driven de-risking.
> - **Naive equal-weight across the 12 = ~9× concentration on one factor.** Allocate by CLUSTER, not by strategy count.
> - Method: backtested DAILY return series, common window 2010-02-16→2026-06-18 (4111 days) — NOT the thin live trade log. Source: `reports/INTERSTRATEGY_CORRELATION_20260622.md` + `reports/_interstrategy_corr_matrix.json`.
>
> **The leaderboard below ranks 12 strategies. The book is one tech bet. Read every P&L number through that lens.**

---

## 📊 Section 1 — Per-Strategy Paper P&L vs SPX

**SPX benchmark for the week:** SPY/^GSPC [start → end], **[+/−X.XX%]** for the week (fill from Yahoo v8 chart API).

| Rank | Strategy | Cluster | Round-Trips | Realized P&L | Unrealized P&L | Total P&L | vs SPX (wk) | Win Rate |
|------|----------|---------|:-----------:|-------------:|---------------:|----------:|:-----------:|:--------:|
| [ ] | `breakout_xlk__mut_c382b1` | XLK-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `breakout_xlk_regime` | XLK-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `breakout_xlk` | XLK-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `sma_crossover_qqq` | QQQ-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `sma_crossover_qqq_regime` | QQQ-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `sma_crossover_qqq_rth` | QQQ-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `rsi_oversold_spy` ⭐ | SPY-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `volume_breakout_qqq` ⭐ | QQQ-tech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `macd_momentum_iwm` ⭐ | IWM-smallcap | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `tqqq_cot_combo` | TQQQ-tech (COT-gated) | [ ]† | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `leveraged_long_trend_paper` | TQQQ-tech | [ ]† | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | `allocator_blend` | multi-sleeve (diversifier) | [ ]† | [ ] | [ ] | [ ] | [ ] | [ ] |

> **⟢Pre-fill snapshot (06-23 00:00 UTC ranking, for sanity only — NOT the weekly P&L; refresh Saturday):** realized P&L by strat — `breakout_xlk__mut_c382b1` **+$44.05** (3 trips, wr 1.0), `breakout_xlk_regime` **+$4.68** (5), `breakout_xlk` **+$4.57** (5), `sma_crossover_qqq` **+$3.87** real / −$0.90 unrl (5), `sma_crossover_qqq_regime` **+$3.82** / −$0.95 (5), `sma_crossover_qqq_rth` **+$0.67** (2); long-only accumulators (0 trips, unrealized): `leveraged_long_trend_paper` **−$3.35**, `tqqq_cot_combo` **−$6.67**, `allocator_blend` ~$0 (just seeded). NOTE: `backstop_test` (−$120, synthetic) and the crypto/`any`/`bp2` legs are NOT in the live 12 — exclude from the book total. These are cumulative-since-inception marks, not weekly deltas; compute the weekly slice Saturday.

> ⭐ Strategies added 2026-06-13 — confirm whether any entries have triggered yet this week.
> † Long-only accumulators / monthly-rebalance allocator — may show 0 round-trips by design (buys/trims, no full sells). Report unrealized P&L for these.
>
> **Book-level (read with the eff-N caveat):**
> - Overall realized P&L (live strats): **[ ]**
> - Overall unrealized P&L: **[ ]**
> - Combined total P&L: **[ ]**
> - Combined P&L vs SPX buy-and-hold over the same window: **[ ]** *(the number that actually matters for the mission)*

---

## 📊 Section 2 — `allocator_blend` First Full-Week Status

*Context: allocator_blend seeded its first-ever live fills 2026-06-22 (~$68.75, QQQ/SPY/TQQQ), and is now wired into `cron_tick.sh` (the wiring gap noted in GO_LIVE_DECISION_PACKET §1 was closed). This is its FIRST full week of cron-driven fills — the headline new datum for this leaderboard.*

- **First full week of cron fills?** [confirm Saturday] — seeded 2026-06-22 ~16:09 UTC; first cron-driven week is 06-22→06-26.
- **Fills this week:** ⟢as of 06-22: **3 legs** (QQQ $27.90, SPY $27.90, TQQQ $12.95); total notional deployed: **$68.75** — *update Saturday with the full week*
- **Current target weights (latest snapshot 06-18):** w_tqqq=**0.442**, w_rot=**0.558**, rotation holds=**[SPY, QQQ]** ⟢pre-filled 06-22 — *refresh Saturday*
- **`allocator_paper.db` row count / latest snapshot date:** **2 rows (06-18, 06-22)** ⟢pre-filled 06-22 after manual backfill. **RESOLVED a yellow flag:** the 06-22 row was initially missing because the daily bar finalizes after markets close (~13:00 PT) but the cron window is `7-13 PT 1-5` — the post-close bar isn't captured until the *next morning's* tick. It self-heals on the following day's first tick (06-23 AM would have caught 06-22); I backfilled it manually 06-22 5 PM. **Not broken** — snapshot can lag ≤~1 day by design. Saturday: confirm 06-23→06-26 rows all present (expect them filled by each morning's tick).
- **Engine drift check:** snapshot `engine_full_sharpe`=1.013–1.014 == `ALLOCATOR_BLEND_20260621.md` (1.014) — **no drift** ⟢pre-filled 06-22
- **Paper-clock since inception (06-18, n=2 days):** blend **+1.65%** vs SPX **+0.71%** ⟢pre-filled 06-22 (sharpe_since_start meaningless at n=2)
- **Reconciliation:** live Alpaca legs == DB net positions to the share? [yes / discrepancy: ___] — *check Saturday*
- **Blend total P&L vs SPX this week:** [ ] (Day-0 snapshot: blend +1.89% vs SPX +1.08%)
- **Notes / anomalies:** the 1-row snapshot table is the one thing to verify Saturday.

---

## 📊 Section 3 — `tqqq_cot_combo` Fills

*Context: long-only TQQQ accumulator with a COT (leveraged-fund speculator-net percentile) exposure gate on top of the vol-target + SMA-200 sleeve. Day-0 (06-22): COT_scale flipped 0.5 → 1.0 (specs washed out → full target exposure). 5 fills, $500 notional, as of 06-22.*

| Date | Side | Qty | Notional | Price | COT_scale | rv% | gate | Reason |
|------|------|----:|--------:|------:|:---------:|:---:|:----:|--------|
| 06-15 | buy | 1.208 | $100 | 82.75 | 0.5 | 31.9% | ON | underweight +6sh; QQQ 721.31 > SMA200 625.36 |
| 06-16 | buy | 1.191 | $100 | 83.93 | 0.5 | 25.2% | ON | underweight +4sh |
| 06-17 | buy | 1.229 | $100 | 81.35 | 0.5 | 24.2% | ON | underweight +4sh |
| 06-18 | buy | 1.216 | $100 | 82.24 | 0.5 | 22.6% | ON | underweight +3sh |
| 06-22 | buy | 1.187 | $100 | 84.22 | **1.0** | 21.1% | ON | underweight +7sh; **COT flipped 0.5→1.0** (specs washed out → full target) |
> ⟢pre-filled 06-22 (5 fills through Mon). *Append 06-23→06-26 Saturday.*

- **Fills this week:** **5** ⟢as of 06-22; cumulative notional deployed: **$500** (5×$100); total shares held: **~6.03** ⟢as of 06-22 — *update Saturday*
- **COT_scale trajectory this week:** held 0.5 (06-15→06-18) → **flipped to 1.0 on 06-22** (leveraged-fund specs washed out below 20th pct → full target exposure)
- **SMA-200 gate state:** **ON** all week (QQQ close ~739.82 vs SMA200 ~628.61 on 06-22)
- **Unrealized P&L:** **−$6.67** ⟢as of 06-23 00:00 ranking snapshot (long-only accumulator, 0 round-trips by design) — *refresh Saturday*
- **Notes:** the COT 0.5→1.0 flip is the headline event — the gate added exposure into a still-uptrending tape.

---

## 📊 Section 4 — `edge_calibrator` Trip Count

*Context: the edge-calibration meta-model (`runner/edge_calibrator.py`) is in PASS-THROUGH mode until total round-trips across ALL strategies reach `MIN_ROUND_TRIPS_TOTAL = 30`. It auto-activates at 30 — no manual flip.*

- **Total round-trips across all strategies:** **19 / 30** ⟢pre-filled 06-22 (authoritative count via `ec._fifo_match_global`; supersedes the stale 14/30 from 06-15) — *re-count Saturday*
- **Mode:** **PASS-THROUGH** (<30) — confirmed `train_calibrator` returns `status=insufficient_data, n_samples=0, notes="19 round-trips total (need 30); calibrator in pass-through mode"` ⟢pre-filled 06-22
- **Trips by strategy (06-22):** sma_crossover_btc 4, breakout_xlk 2, sma_crossover_qqq 2, breakout_xlk_regime 2, sma_crossover_qqq_regime 2, any 2, backstop_test 2, sma_crossover_qqq_rth 1, breakout_xlk__mut_c382b1 2
- **Pace note:** +5 trips since 06-15 (14→19) over ~1 trading week. The big new sleeves (`leveraged_long_trend_paper`, `tqqq_cot_combo`, `allocator_blend`) are long-only accumulators that have NOT closed a single round-trip yet (all buys/trims) — so trip accrual is paced by the crossover/breakout strats only. At ~5 trips/wk, **30 lands ~2026-07-04 to 07-11**; the long-only legs will not accelerate it. [confirm Saturday count]
- **If it activated this week:** [N/A this week — still pass-through; confirm Saturday]

---

## ✅ Section 5 — Go-Live Gate Checklist

*Source of truth: `reports/GO_LIVE_DECISION_PACKET.md` §3. These are the REAL-MONEY rails — NOT suspended under explore-first. Update the status of each gate Saturday. The track-record gate is the binding constraint and can ONLY be cleared by the paper clock running.*

| # | Gate | Requirement | Current status (fill Saturday) |
|---|------|-------------|--------------------------------|
| 1 | Cyrus approval | Explicit per-request go-live approval (not standing, not main's to grant) | ❌ not requested |
| 2a | Paper track length | ≥ 4 weeks of live paper | [ ] — paper clock day ~[N] (allocator_blend live since 06-22; sleeves since 06-15) |
| 2b | Round-trips | ≥ 100 round-trips | [ ] / 100 |
| 2c | Realized Sharpe | realized paper Sharpe > 1.0 | [ ] *(sample likely still too small — say so)* |
| 2d | Realized maxDD | realized maxDD < 20% | [ ] |
| 2e | OOS confirmation | live paper behaves consistent with OOS backtest | [ ] |
| 3 | Cost realism | live fill cost ≤ 2× modeled (2bps assumption holds) | [ ] — measure from actual fills |
| 4 | Data sufficiency | ~20–40 trading days of fills before P&L is readable | [ ] — day ~[N] of ~20–40 |
| 5 | Physical rails | paper→live broker-URL flip ready, `STOP_TRADING` honored, risk caps in runner not strategy code | ✅ intact (verify Saturday) |

> **Bottom line to restate Saturday:** the engine is validated + hardened, but the **track-record gate (4wk / 100+ trips / realized Sharpe>1)** is binding and unmet. No amount of backtesting substitutes for the paper clock. Earliest the time gate alone can clear: ~[date].

---

## 🔴 Section 6 — Breadth Lane: RESOLVED (CLOSE-REDUNDANT)

*Updated 2026-06-22 (~5 PM PT): this section was a pending green-light. **The breadth lane was RUN on 2026-06-22 and is now CLOSED.** No Saturday decision needed — record the result.*

**Verdict: CLOSE-REDUNDANT (clean negative).** Report: `reports/BREADTH_REGIME_20260622.md`. Code: `strategies_candidates/leveraged_long_trend/backtest_voltarget_breadth.py` + `validate_breadth.py`.

- **Decisive lead-vs-coincident test FALSIFIED the hypothesis:** sector breadth (% of 11 SPDRs > own 200d-SMA) does NOT lead the SMA-200 gate. 2018-Q4: breadth & gate flip the **same day** (coincident). 2022: breadth **LAGS** the gate by 3–5 trading days (gate broke 2022-01-21 while breadth still healthy at 0.818; breadth didn't cross 0.50 until 01-26).
- **Every variant loses to the sleeve OOS@2bps** (−126 to −221pp return, −0.13 to −0.28 Sharpe), at every threshold 0.30→0.60 and every cost level (2/5/12bps concordant). Anti-overfit: in-sample-best threshold frozen to OOS still loses; 1-day-lag all negative.
- **Mechanism is backwards:** among gate-surviving days, LOW-breadth days carry HIGHER forward sleeve returns (+204%/yr vs +36%/yr) — low breadth on uptrending QQQ is a buy-the-dip tell, not a topping tell. De-risking sells the best days (COVID-2020 baseline +2.0% vs gates −14 to −17%). Also ~70–76% of low-breadth days already gated out by SMA-200.
- **This is the 3rd overlay in a row to die on the SMA-200 rock** (after VIX-term + SKEW, both 06-22). Locked into MEMORY.md: do NOT probe vol-complex or breadth overlays as return improvers. The sleeve is well-specified; bolt-on regime gates are redundant.
- **Reusable win:** survivorship-clean breadth primitive (`build_breadth_series`, proven no-lookahead via future-crash test, eligibility ramp handled).

**Next-lane bar (for Saturday discussion, NOT a breadth decision):** the next improvement must come from a **genuinely orthogonal signal CLASS** with a different return source (credit-spread momentum, earnings-drift/PEAD-adjacent, real cross-sectional internal with PIT constituents) — not a fourth regime modulator on the same sleeve.

---

## 🔍 Section 7 — Notable Observations *(fill Saturday)*

1. [ ]
2. [ ]
3. [ ]

---

## ⚙️ Section 8 — Crontab / Infra Health *(fill Saturday)*

- Live strategies wired (12): `breakout_xlk sma_crossover_qqq breakout_xlk_regime sma_crossover_qqq_regime sma_crossover_qqq_rth breakout_xlk__mut_c382b1 leveraged_long_trend_paper rsi_oversold_spy volume_breakout_qqq macd_momentum_iwm tqqq_cot_combo allocator_blend` — **confirmed in crontab** (`*/30 7-13 * * 1-5 .../cron_tick.sh ...`, all 12 args) ⟢pre-filled 06-22
- Runs in last 7 days / errors: **775 runs, 0 errors** ⟢pre-filled 06-22 (all-time: 2558 ok / 16 error / 11 killswitch — the 16 errors are old, none this week) — *refresh Saturday*
- `reconcile.py` running top of each tick? [confirm Saturday — was wired top of cron_tick.sh per 06-13 sprint]
- Discord cron-post step healthy? [confirm Saturday — Day-0 had an ambiguous-recipient post error]
- Killswitch `STOP_TRADING` absent (trading allowed)? **YES — absent** ⟢pre-filled 06-22 — *confirm Saturday*

---

## 📋 Section 9 — Summary Table *(fill Saturday)*

| Metric | Value |
|--------|-------|
| Strategies live | 12 |
| **Effective independent bets (eff-N)** | **2.218 full / 2.534 downside** ⚠️ |
| **Variance on top tech-beta factor** | **~65%** ⚠️ |
| Strategies with realized gains | [ ] |
| Round-trips this week (all strats) | [ ] |
| Total round-trips toward edge-calibrator (→30) | **19** / 30 ⟢pre-filled 06-22 |
| Combined total P&L | [ ] |
| Combined P&L vs SPX (the mission metric) | [ ] |
| Paper-clock day count | ~[N] |
| Go-live gates cleared | [ ] / 5 binding |
| Breadth lane | **CLOSED — CLOSE-REDUNDANT** (run 06-22; §6) |
| Crontab health | [ ] |

---

*Template by Tessera, 2026-06-22. Fill Saturday 2026-06-28 from live data. The eff-N caveat at the top is non-negotiable — the book is one tech bet wearing twelve nametags.*
