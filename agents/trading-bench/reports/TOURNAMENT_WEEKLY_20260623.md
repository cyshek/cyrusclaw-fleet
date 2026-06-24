# 🏆 Tournament Weekly — LIVE DATA as of 2026-06-23

**Type:** Decision-grade live analysis (sibling of the fill-in-Saturday `SATURDAY_LEADERBOARD_20260628_TEMPLATE.md`; this is the *actual numbers as of 2026-06-23*, that one is the Saturday scaffold).
**Author:** Tessera, 2026-06-23 (~10 AM PT). Marks captured intraday 06-23.
**Source of truth:** `reports/_weekly_datapack_20260623.md` (live ground-truth gathered read-only by parent). Numbers below are used verbatim from that pack — DBs/broker were **not** re-queried for this write-up.
**Authority:** research/reporting only. No orders, no spend, no signups; only file written = this report (see footer).

---

## 1. 📣 HEADLINE — 3-line verdict *(this is the quotable verdict for Cyrus)*

> **1.** The book is **alive and healthy** — 789 cron runs/7d at 0 errors, broker↔DB fills reconciled to 6 decimals, every exposure gate firing as designed — but **n is tiny** (0–3 closed trips on every sleeve; nobody has a real track record yet).
> **2.** Net combined is **≈ −$14.4** (realized **+$58.15**, unrealized **−$72.58**), and that red is **almost entirely a single 1-day risk-off (06-23) landing on the leveraged TQQQ sleeves** — expected 3× beta on a down day, **not** a malfunction.
> **3.** The standing insight is **concentration, not any single strategy**: 12 nametags, **eff-N ≈ 2.2**, ~65% of variance on one NASDAQ-tech-beta factor — today's all-red correlated drawdown is the live proof. **Don't read any P&L figure without that lens, and don't crown or cull anyone on this sample.**

---

## 2. ⚠️ eff-N CONCENTRATION CAVEAT — READ FIRST (non-negotiable)

**The tournament *looks* like 12 strategies but is effectively ~2.2 independent bets, sized ~9× on ONE tech-beta factor.**

- **Effective bets (eff-N): 2.218 full / 2.534 downside** out of 12 live strategies.
- **Top eigenvalue = 7.859 / 12 = ~65% of all variance** on a single *"long US-equity / NASDAQ-tech beta"* factor.
- The clusters are all the **same** exposure: **XLK×3** (`breakout_xlk` + `_regime` + `__mut_c382b1`), **QQQ×3** (`sma_crossover_qqq` + `_regime` + `_rth`), **TQQQ×2** (`leveraged_long_trend_paper` + `tqqq_cot_combo`), plus `allocator_blend` (which itself holds QQQ/SPY/TQQQ). The lone structural diversifiers are the **rotation/haven legs inside `allocator_blend` (GLD/TLT)** and **`tqqq_cot_combo`'s COT-driven de-risking**.
- **Naive equal-weight across the 12 = ~9× concentration on one factor.** Allocate by **CLUSTER**, not by strategy count.
- Method: backtested daily return series, common window 2010-02-16→2026-06-18 (4111 days) — NOT the thin live trade log. Source: `reports/INTERSTRATEGY_CORRELATION_20260622.md` + `_interstrategy_corr_matrix.json`.

### 🔴 Today is the live demonstration
The **−$72.58 unrealized hit on 06-23 was perfectly correlated** — every TQQQ / QQQ / SPY / XLK leg printed red **together** on the same risk-off tape (TQQQ −3.8%, QQQ/SPY ~−1.6…−2.5%). That is exactly what eff-N ≈ 2.2 predicts: when the one factor moves, the "twelve strategies" all move as one. **This is THE insight for Cyrus** — the diversification on paper is mostly nominal, and the only real hedges in the book are the haven/rotation legs and the COT de-risk gate.

---

## 3. 📊 Per-strategy ranking — all 12 live-book strategies

Marks: **XLK 185.74, TQQQ 76.03, QQQ 718.48, SPY 737.03** (live 06-23, intraday). Ranked by **total P&L**. `realized$` = closed FIFO P&L; `unreal$` = open lots marked to live price; `trips` = closed round-trips. **Every figure below rests on n<10 closed trips (most n=0–3) → treat all of it as NOISE, not skill.** Excludes non-book noise (`any, backstop_test, bp2, breakout_ltc, buy_and_hold_btc, momentum_sol, rsi_mean_revert_eth, sma_crossover_btc`).

| Rank | Strategy | Cluster | Realized $ | Unreal $ | **Total $** | Trips | Open position | One-line status |
|:---:|----------|---------|----------:|---------:|----------:|:-----:|---------------|-----------------|
| 1 | `breakout_xlk__mut_c382b1` | XLK-tech | **+44.05** | 0.00 | **+44.05** | 2 ⚠️ | flat | **NOISE, not a winner** — +44 on 2 closed trips; do **not** crown |
| 2 | `breakout_xlk_regime` | XLK-tech | +4.68 | −3.80 | **+0.88** | 2 | XLK 0.5179@193.08 | Working as designed; n=2, undecided |
| 3 | `breakout_xlk` | XLK-tech | +4.57 | −3.80 | **+0.77** | 2 | XLK 0.5179@193.07 | Working as designed; n=2, undecided |
| 4 | `sma_crossover_qqq_rth` | QQQ-tech | +0.67 | 0.00 | **+0.67** | 1 | flat | One trip, flat; nothing to read |
| 5 | `sma_crossover_qqq` | QQQ-tech | +0.16 | 0.00 | **+0.16** | 3 | flat | 3 trips, ~breakeven; nothing to read |
| 6 | `sma_crossover_qqq_regime` | QQQ-tech | +0.02 | 0.00 | **+0.02** | 3 | flat | 3 trips, ~breakeven; nothing to read |
| 7 | `macd_momentum_iwm` ⭐ | IWM-smallcap | 0.00 | 0.00 | **0.00** | 0 | flat | No entry triggered yet this week |
| 8 | `volume_breakout_qqq` ⭐ | QQQ-tech | 0.00 | 0.00 | **0.00** | 0 | flat | No entry triggered yet this week |
| 9 | `allocator_blend` | multi-sleeve (diversifier) | 0.00 | −1.83 | **−1.83** | 0† | QQQ 0.0379@735.49 · SPY 0.0375@744.25 · TQQQ 0.1582@81.78 | Seeded 06-22; first cron week; MTM noise |
| 10 | `rsi_oversold_spy` ⭐ | SPY-tech | 0.00 | +0.47 | **+0.47** | 0 | SPY 0.1363@733.55 | First small long open; the lone green open leg today |
| 11 | `leveraged_long_trend_paper` | TQQQ-tech (3×) | 0.00 | −24.19 | **−24.19** | 0† | TQQQ 3.6271@82.70 | Long-only accumulator; −24 = **expected 3× beta** on a down day |
| 12 | `tqqq_cot_combo` | TQQQ-tech (COT-gated 3×) | 0.00 | −39.44 | **−39.44** | 0† | TQQQ 7.3719@81.38 | Long-only accumulator; −39 = **expected 3× beta**, COT=1.0 full exposure |

> ⭐ Added 2026-06-13 — confirm whether entries have triggered.
> † Long-only accumulators / monthly-rebalance allocator — **0 round-trips by design** (they buy/trim, they don't fully sell). Report their unrealized P&L, not trips.

**Book-level (read through the eff-N caveat):**
- Overall **realized** P&L (live strats): **+$58.15**
- Overall **unrealized** P&L: **−$72.58**
- **Combined total P&L: ≈ −$14.43**
- The two leveraged TQQQ sleeves alone account for **−$63.63** of the −$72.58 unrealized (88%) — i.e. the entire net-negative book is one down day on the 3× sleeves. Strip the intraday TQQQ mark and the book is roughly flat-to-green on realized.

> **Why `breakout_xlk__mut_c382b1` is NOT the leader (explicit):** +$44.05 on **2 closed trips** is statistically indistinguishable from luck. Two winning round-trips is the kind of sample that flips sign on the third trade. It tops the table by arithmetic only. **Do not crown it, do not size to it, do not treat it as a validated edge.** It is the single loudest example of why this whole table is annotated "noise."

---

## 4. 🚩 Cull flags — honest read

**No structural culls this week. Sample is too small to cull anyone.** Gates are **SUSPENDED** (mission posture, MEMORY.md 2026-06-07): the mission bar is **BEAT SPX RAW RETURN on the honest traded path**, and the GATE.md graduation bars (Sharpe ≥ 1.0, 8 %/yr floor, DD ceilings, Bar E) are **not** active culling criteria right now. A "flag cull" here means **structurally broken / misbehaving / clearly dominated** — *not* "missed a suspended number."

Run against that bar:
- **Nobody is structurally broken.** Every sleeve's fills are clean and reconciled; every gate (COT scale, SMA-200, regime filters) fired correctly; the only red is mark-to-market beta on a down day, which is the design, not a fault.
- **Nobody is dominated yet** — at n=0–3 closed trips you cannot establish dominance; the apparent ranking is noise.
- **The −$39 / −$24 on the TQQQ sleeves is NOT a cull signal.** It is the expected behavior of a 3× ETF on a −3.8% TQQQ day. Culling a leveraged sleeve for a single down-day MTM would be precisely the wrong lesson.

**What I'd WATCH (not cull) going forward:**
- **`breakout_xlk__mut_c382b1`** — the +44 mutant. Watch trips 3–6: if the edge is real it persists; if it was luck it reverts. Do not act on the +44 either way until n is meaningful.
- **The 3 XLK breakout twins vs the 3 QQQ crossover twins** — these are near-duplicates within their clusters. The cull that *will* eventually matter is **intra-cluster redundancy** (keep the best of each triplet), not single-strategy P&L. That's an allocation decision once trips accrue, not a "broken strategy" flag today.
- **`leveraged_long_trend_paper` vs `tqqq_cot_combo`** — same TQQQ exposure; the COT gate is the only thing differentiating them. Watch whether the COT de-risk actually separates their paths in a future bear tape (it can't on this all-bull week — both ran ~full exposure).

---

## 5. 📊 `allocator_blend` vs solo-sleeves — paper-clock read

*Context: `allocator_blend` seeded its first live fills 2026-06-22 and is now cron-wired. This is its first full week.*

**Paper-clock (allocator_paper.db daily_snapshots), same path, blend vs SPX:**

| Date | w_tqqq | w_rot | rot holds | blend daily | blend cum | SPX daily | SPX cum | engine Sharpe |
|------|:------:|:-----:|-----------|:-----------:|:---------:|:---------:|:-------:|:-------------:|
| 2026-06-18 | 0.442 | 0.558 | [SPY, QQQ] | +1.894% | +1.894% | +1.085% | +1.085% | 1.0144 |
| 2026-06-22 | 0.442 | 0.558 | [SPY, QQQ] | −0.236% | +1.653% | −0.371% | +0.710% | 1.0134 |
| 2026-06-23 | 0.442 | 0.558 | [SPY, QQQ] | −2.463% | **−0.850%** | −1.602% | **−0.903%** | 1.0030 |

**READ:** since start the blend is **−0.85% vs SPX −0.90%** → **marginally ahead over 3 days**. But **n = 3 snapshots (started 06-18) is noise** — caveat this hard. On 06-23 the blend fell −2.46% vs SPX −1.60%; the blend is more volatile day-to-day because of its TQQQ weight, and it happened to be ahead cumulatively only because of the +1.89% Day-0. **No live edge is demonstrated or refuted at n=3.**

**Critical distinction — two different Sharpes, do not conflate:**
- **Backtested engine Sharpe = 1.003–1.014** (the `engine_full_sharpe` column above). This is the **blend's BACKTEST Sharpe, recomputed daily** off the model — it is **not** a realized live number. It == `ALLOCATOR_BLEND_20260621.md` (1.014), so **no engine drift**.
- **Realized LIVE Sharpe = undefined (n=3).** There is not enough live history to compute a meaningful realized Sharpe; anyone quoting "~1.01 live" would be misreading the backtest column.

**The validated case stands on backtest, not yet on live:** the allocator's documented value is **full-window Sharpe 1.014 and a ~10-point maxDD reduction vs the raw sleeves**. That case is **real but backtest-derived** — the paper clock has 3 days and cannot yet confirm it. The blend being marginally ahead of SPX over 3 days is consistent with the thesis but proves nothing. **The track-record gate (the binding real-money rail) requires the paper clock to actually run** — backtesting does not substitute.

---

## 6. 📊 `tqqq_cot_combo` — live vs backtest expectation (honest read)

*Long-only TQQQ accumulator with a COT (leveraged-fund speculator-net percentile) exposure gate layered on the vol-target + SMA-200 sleeve.*

**Live this week:** 6 daily BUYs Jun 15→23, **all filled**, net **7.3719 sh TQQQ @ avg 81.38**, cost **$599.94**, **0 closed trips**. Unrealized **−$39.44** @ TQQQ 76.03 (TQQQ fell ~6.6% below avg basis over the week). **COT_scale flipped 0.5 → 1.0 on 06-22** (specs washed out → full target exposure); **SMA-200 gate ON all week** (QQQ > 629).

**Backtest expectation:** the COT overlay's job is **drawdown reduction in bear regimes**, not return-juicing in bull tapes. Validated numbers: in 2022, vol-target-alone was −26.5% DD / −24.3% ret → **+COT improved to −19.8% DD / −17.4% ret** (raw 3× was −80%). In a **bull/up tape the combo just rides ~full TQQQ exposure (COT = 1.0)** — so a −6.6% week on a −3.8% TQQQ day is **fully consistent with "full exposure in a non-bear regime,"** not a divergence from backtest.

**🔒 HONEST READ — 1 week + 0 closed trips is FAR too little to validate or break the edge.** The only defensible claims are:
- **(a) Fills are clean and reconciled** — broker↔DB diff **0.000000**.
- **(b) Exposure logic is behaving as designed** — the COT 0.5→1.0 flip and the SMA-200 gate both fired correctly.
- **(c) The MTM loss is just beta on a down week** — expected for a 3× sleeve at full exposure.

**Do NOT claim the live week validates or breaks the COT edge.** It does neither — it confirms the *plumbing* and the *exposure logic*, nothing about the edge's live performance. The COT gate's actual value (bear-regime DD reduction) is structurally untestable on an all-bull week where it correctly sat at full exposure.

---

## 7. 🔍 Insights worth Cyrus's attention

1. **Concentration is the headline (lead with it).** eff-N ≈ 2.2 / ~65% on one tech-beta factor means the "12-strategy" diversification is mostly nominal. **Today's perfectly-correlated −$72.58 all-red drawdown is the live proof.** The actionable implication: **allocate by cluster, not by strategy count**, and treat intra-cluster duplicates (XLK×3, QQQ×3, TQQQ×2) as ~one bet each. This is the single most important thing in the book right now.

2. **The leveraged-sleeve beta reality on down days.** −$63.63 of the −$72.58 unrealized (88%) is the two TQQQ sleeves on a single −3.8% TQQQ day. This is **expected 3× behavior**, not a bug — but it's also a standing reminder that on any sharp risk-off day the book's drawdown will be dominated by the leveraged legs, and they all move together. Cyrus should expect double-digit single-day MTM swings from these sleeves as normal.

3. **What would actually change the picture:**
   - **More closed trips.** Everything in this report is gated on n. The crossover/breakout sleeves accrue ~5 trips/wk; the edge-calibrator's 30-trip activation lands ~2026-07-04→07-11. Until then, no ranking, no cull, no live-Sharpe claim is meaningful.
   - **A genuinely uncorrelated sleeve.** The only real diversification in the book is the **GLD/TLT haven leg that the allocator's rotation provides** (and the COT de-risk gate). That haven leg is the thing that would actually move eff-N off ~2.2. A fourth tech-beta strategy would not; a working haven/credit/cross-sectional sleeve would. (Note: vol-complex and breadth overlays are **closed dead ends** — 3 in a row died on the SMA-200 rock; do not re-probe them as return improvers.)

4. **The two parked decisions that are genuinely Cyrus's to make:**
   - **LEAPS / options cap-raise** — a standing parked decision requiring Cyrus (involves the capital/scope envelope). Flagged, not actioned.
   - **Nothing else needs him.** Everything operational (more backtests, edge-discovery, promoting a sleeve to more paper, building the haven leg, allocation-by-cluster work) is inside the explore-first / main-as-proxy mandate and does **not** require Cyrus. The only true Cyrus-gates remain: **paper → live with real money**, and **paid data signups**.

---

## ✅ Bottom line

The book is **healthy and behaving exactly as engineered** — clean reconciled fills, every gate firing, 0 cron errors. It is **also too young to judge**: 0–3 closed trips per sleeve means no one has a real track record, the apparent +44 "leader" is noise on 2 trips, and the −$14.4 net is one risk-off day on the leveraged legs. **The durable, actionable truth is concentration: this is one tech bet wearing twelve nametags, and today's all-red correlated drawdown proved it.** Don't crown anyone, don't cull anyone, watch the trip counts accrue, and the one structural improvement worth chasing is a genuinely uncorrelated (haven) sleeve — not a thirteenth flavor of NASDAQ beta.

---

## 🔒 FOOTER — integrity & authority

**Protected-file md5 (before == after, proving I touched none of them):**

| File | md5 (start) | md5 (end) | Unchanged |
|------|-------------|-----------|:---------:|
| `runner/runner.py` | `3811c37be962ea818e9958da675b1a03` | `3811c37be962ea818e9958da675b1a03` | ✅ |
| `runner/risk.py` | `e4c227e019c99e7e52224eb2f91389b8` | `e4c227e019c99e7e52224eb2f91389b8` | ✅ |
| `runner/backtest.py` | `ac0c579f8a20d11724879278a610fbb4` | `ac0c579f8a20d11724879278a610fbb4` | ✅ |
| `runner/backtest_xsec.py` | `fd39e011087d6e0295da83efbe858819` | `fd39e011087d6e0295da83efbe858819` | ✅ |
| `runner/broker_alpaca.py` | `2d82c8106496e7c80636684d2299cc89` | `2d82c8106496e7c80636684d2299cc89` | ✅ |

**Authority attestation:** Research/reporting only. **No orders placed, no spend, no signups. No edits to anything under `runner/`, `strategies/`, `tests/`, or any DB. The only file written this task = `reports/TOURNAMENT_WEEKLY_20260623.md`.** All numbers used verbatim from `reports/_weekly_datapack_20260623.md` (no DB/broker re-query).

*Report by Tessera, 2026-06-23. Sibling to `SATURDAY_LEADERBOARD_20260628_TEMPLATE.md` (the fill-in-Saturday scaffold). The eff-N caveat at the top is non-negotiable.*
