# 🏆 Saturday Leaderboard — Week ending 2026-06-28 *(TEMPLATE — fill in Saturday)*

**Status:** TEMPLATE prepared 2026-06-22 (~2 PM PT); **partially pre-filled 2026-06-22 (~5 PM PT)** with live snapshots that won't change before Saturday (allocator Day-0 fills, tqqq_cot fills through 06-22, calibrator trip count, cron health); **snapshots REFRESHED to 06-23 truth (mgmt-check, ~9 AM PT).** Fields tagged `⟢pre-filled` carry live data but should be re-confirmed Saturday. Fill remaining bracketed `[…]` fields Saturday from live `tournament.db`, `allocator_paper.db`, and the Alpaca paper account.

> **🔄 06-23 REFRESH note (mgmt-check ~9 AM PT):** Three pre-filled snapshots had drifted since 06-22 and are now corrected to current truth: **(1) Calibrator trip count 19→13/30** — the 19 was a POLLUTED count (included non-book backstop_test/any/sma_crossover_btc); the universe-filter fix shipped 06-23 (`EDGE_CALIBRATOR_ACCELERATION_VERDICT`) makes the authoritative LIVE-BOOK count **13/30** (still pass-through). **(2) tqqq_cot_combo** now **6 fills** (added 06-23) / **7.372 sh** / **−$43.6** unrealized (TQQQ fell ~$84→$75). **(3) Cron health 775→789 runs/7d, still 0 errors.** Also: test harness is GREEN (676 passed/1 skipped) after fixing the brittle `test_live_eurusd_cache_span` time-bomb (FX cache grew 5843→5852 bars; assertion converted to a floor). Broker reconcile verified PERFECT (Alpaca 11.157282 sh TQQQ = cot_combo 7.372 + lev_long 3.627 + allocator 0.158, to the 6th decimal).

> **Pre-fill note (06-22 5 PM PT):** Section 6 (breadth green-light) is **RESOLVED — the breadth lane was RUN today and came back CLOSE-REDUNDANT**; that section is rewritten below from a pending decision into a closed result. Section 4 trip count was refreshed 14→19/30 on 06-22 — **but SUPERSEDED 06-23: the authoritative live-book count is now 13/30** (the 19 was polluted by non-book strategies; see the 06-23 REFRESH note above). Cron health was 775 runs on 06-22 — **now 789 runs/7d, 0 errors.**
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

*Context: long-only TQQQ accumulator with a COT (leveraged-fund speculator-net percentile) exposure gate on top of the vol-target + SMA-200 sleeve. Day-0 (06-22): COT_scale flipped 0.5 → 1.0 (specs washed out → full target exposure). **6 fills, $600 notional, through 06-23** (was 5/$500 on 06-22).*

| Date | Side | Qty | Notional | Price | COT_scale | rv% | gate | Reason |
|------|------|----:|--------:|------:|:---------:|:---:|:----:|--------|
| 06-15 | buy | 1.208 | $100 | 82.75 | 0.5 | 31.9% | ON | underweight +6sh; QQQ 721.31 > SMA200 625.36 |
| 06-16 | buy | 1.191 | $100 | 83.93 | 0.5 | 25.2% | ON | underweight +4sh |
| 06-17 | buy | 1.229 | $100 | 81.35 | 0.5 | 24.2% | ON | underweight +4sh |
| 06-18 | buy | 1.216 | $100 | 82.24 | 0.5 | 22.6% | ON | underweight +3sh |
| 06-22 | buy | 1.187 | $100 | 84.22 | **1.0** | 21.1% | ON | underweight +7sh; **COT flipped 0.5→1.0** (specs washed out → full target) |
| 06-23 | buy | 1.340 | $100 | 74.62 | 1.0 | — | ON | underweight +7sh; QQQ 738.10 > SMA200 629.45 (TQQQ gapped down ~$84→$75) |
> ⟢pre-filled 06-22 (5 fills through Mon); **06-23 row added (mgmt-check)**. *Append 06-24→06-26 Saturday.*

- **Fills this week:** **6** ⟢through 06-23; cumulative notional deployed: **$600** (6×$100); total shares held: **7.372** ⟢through 06-23 (broker-reconciled) — *update Saturday*
- **COT_scale trajectory this week:** held 0.5 (06-15→06-18) → **flipped to 1.0 on 06-22** (leveraged-fund specs washed out below 20th pct → full target exposure); held 1.0 on 06-23
- **SMA-200 gate state:** **ON** all week (QQQ close 738.10 vs SMA200 629.45 on 06-23)
- **Unrealized P&L:** **−$43.6** ⟢as of 06-23 (TQQQ ~$75.47 vs avg cost $81.38; long-only accumulator, 0 round-trips by design) — *refresh Saturday* (was −$6.67 on 06-22; the ~$9 TQQQ drop = a leveraged ~10% move on ~3.3% QQQ decline, NOT a bug — each order correctly $100 notional)
- **Notes:** the COT 0.5→1.0 flip (06-22) is the headline event — the gate added exposure into a still-uptrending tape, just before a sharp TQQQ pullback on 06-23; the drawdown is expected leveraged-ETF behavior within an intact uptrend (SMA-200 still ON).

---

## 📊 Section 4 — `edge_calibrator` Trip Count

*Context: the edge-calibration meta-model (`runner/edge_calibrator.py`) is in PASS-THROUGH mode until total round-trips across ALL strategies reach `MIN_ROUND_TRIPS_TOTAL = 30`. It auto-activates at 30 — no manual flip.*

- **Total round-trips across all strategies:** **13 / 30** ⟢REFRESHED 06-23 (authoritative LIVE-BOOK count via `calibration_report()` with the universe filter; **supersedes the 19/30 from 06-22, which was POLLUTED by non-book strategies** — backstop_test/any/sma_crossover_btc are now excluded per the 06-23 universe-filter fix) — *re-count Saturday*
- **Mode:** **PASS-THROUGH** (<30) — confirmed `calibration_report` returns `Model status: insufficient_data`, `Training notes: 13 round-trips total (need 30); calibrator in pass-through mode`, `Training samples: 0` ⟢REFRESHED 06-23
- **Trips by strategy (LIVE-BOOK, 06-23):** breakout_xlk 2, breakout_xlk__mut_c382b1 2, breakout_xlk_regime 2, sma_crossover_qqq 3, sma_crossover_qqq_regime 3, sma_crossover_qqq_rth 1 (= 13 total; the long-only sleeves leveraged_long_trend_paper / tqqq_cot_combo / allocator_blend have 0 closed trips by design)
- **Pace note:** 13 live-book trips; accrual paced ONLY by the crossover/breakout strats (~5/wk) since the big sleeves are long-only accumulators (no closed round-trips). At ~5 trips/wk, **30 lands ~2026-07-04 to 07-11**. NOTE: this is a HONEST 13 (post-pollution-fix), not a regression from 19 — the 19 counted synthetic-harness + crypto noise that should never have trained the calibrator. [confirm Saturday count]
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

> **⟢Research-sprint status to fold in Saturday (week of 06-23 — the "what lane next" context):** This week the research side ran a **6-lane cull, all CLOSED** — no new tradeable edge, but the negatives are now airtight and the binding constraint is identified. Closed this week:
> - **4 cross-sectional/event lanes died the SAME day on the IDENTICAL root cause** (survivorship-beta-in-disguise on our fixed modern-survivor universe): fundamentals-PIT quality/value, BAB (betting-against-beta), xsec-momentum (sector-neutral), PEAD (large-cap). Each killed by the **EW-of-same-universe control** → locked the **CROSS-SEC FACTOR GATE** methodology rule (L/S spread + EW control mandatory before any cross-sec pitch).
> - **Carry family now FULLY exhausted on free data** (H1 cross-asset carry): **bond-curve-carry** = honest near-miss (full Sharpe 0.578, OOS 0.434, orthogonal, beats both controls — but misses the 0.5 magnitude bar standalone → shelf-with-trigger); **commodity-carry ETF proxy** = CLOSE (dirty-proxy mirage, failed EW control −77.5pp OOS, neg IS); **commodity-carry true WTI futures calendar-spread** (the clean reopen, run 06-23) = CLOSE but the *honest* near-miss — **k4 PASS: the backwardation premium is REAL and exists pre-2019** (+0.168 IS Sharpe, corr to bond ≈0, near-zero equity beta), it's just **too thin to beat static-long-WTI or lift the combined sleeve** (combined full 0.464 < bond-alone 0.560). Defensive overlay, not alpha. Report: `H1_CARRY_COMMODITY_FUTURES_20260623T221400Z.md`.
> - **BINDING CONSTRAINT identified = the UNIVERSE, not the signal.** Every cross-sec/event factor on the survivor universe reproduces the survivorship mirage. Next genuinely-new lane must bring a **delisting-inclusive PIT-constituent universe** (data not free yet — EODHD $19.99/mo flagged as top rec, Cyrus's call) OR be a fundamentally different construct (path-dependent/allocator/regime). The live, non-contaminated track = the **allocator-blend + haven-sleeve** work.
> - **Harness hardened:** the survivorship + OOS-mirage guards were extracted into a shared `lane_honesty` module (+15 regression tests reproducing each closed-lane signature) so a future lane author can't forget to run them.
> - **Saturday "what next" decision:** with the carry sprint done and all free-universe cross-sec lanes exhausted, the next research lane is genuinely gated on either (a) Cyrus approving the PIT-universe data spend, or (b) a path-dependent/allocator construct. Worth surfacing to main/Cyrus as the actual fork.

---

## ⚙️ Section 8 — Crontab / Infra Health *(fill Saturday)*

- Live strategies wired (12): `breakout_xlk sma_crossover_qqq breakout_xlk_regime sma_crossover_qqq_regime sma_crossover_qqq_rth breakout_xlk__mut_c382b1 leveraged_long_trend_paper rsi_oversold_spy volume_breakout_qqq macd_momentum_iwm tqqq_cot_combo allocator_blend` — **confirmed in crontab** (`*/30 7-13 * * 1-5 .../cron_tick.sh ...`, all 12 args) ⟢pre-filled 06-22
- Runs in last 7 days / errors: **789 runs, 0 errors** ⟢REFRESHED 06-23 (all-time: 2726 ok / 16 error / 11 killswitch — the 16 errors are old, none this week) — *refresh Saturday*
- `reconcile.py` running top of each tick? **YES** ⟢verified 06-23 — broker reconcile is PERFECT (Alpaca TQQQ 11.157282 sh == DB net across cot_combo+lev_long+allocator to 6 decimals); confirm Saturday
- Discord cron-post step healthy? [confirm Saturday — Day-0 had an ambiguous-recipient post error]
- Killswitch `STOP_TRADING` absent (trading allowed)? **YES — absent** ⟢verified 06-23 — *confirm Saturday*

---

## 📋 Section 9 — Summary Table *(fill Saturday)*

| Metric | Value |
|--------|-------|
| Strategies live | 12 |
| **Effective independent bets (eff-N)** | **2.218 full / 2.534 downside** ⚠️ |
| **Variance on top tech-beta factor** | **~65%** ⚠️ |
| Strategies with realized gains | [ ] |
| Round-trips this week (all strats) | [ ] |
| Total round-trips toward edge-calibrator (→30) | **13** / 30 ⟢REFRESHED 06-23 (live-book; was 19 polluted) |
| Combined total P&L | [ ] |
| Combined P&L vs SPX (the mission metric) | [ ] |
| Paper-clock day count | ~[N] |
| Go-live gates cleared | [ ] / 5 binding |
| Breadth lane | **CLOSED — CLOSE-REDUNDANT** (run 06-22; §6) |
| Crontab health | [ ] |

---

*Template by Tessera, 2026-06-22; snapshots refreshed to 06-23 truth (mgmt-check). Fill Saturday 2026-06-28 from live data. The eff-N caveat at the top is non-negotiable — the book is one tech bet wearing twelve nametags.*
