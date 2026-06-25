# Weekly Performance Summary — 2026-06-24

*Status doc. Generated 13:32 PT (20:32 UTC). Killswitch: ABSENT (book live). All figures pulled live from `tournament.db` + `polymarket_track.db`, synthetic rows excluded per standing guard.*

---

## 1. Live Book — Trip Accrual vs 30-Trip Gate

**Total clean live-book round-trips: 7 / 30** (canonical `edge_calibrator.calibration_report()`, post universe-filter fix). Calibrator remains in **pass-through mode** (`insufficient_data`, needs 30 to train). 3 of 8 strategies have ≥1 closed trip.

| Strategy | Trips | Wins | Net P&L | Status |
|---|---|---|---|---|
| breakout_xlk__mut_c382b1 | 3 | 3/3 (100%) | +$44.03 | accruing |
| sma_crossover_qqq_regime | 3 | 2/3 (67%) | +$0.01 | accruing |
| sma_crossover_qqq_rth | 1 | 1/1 (100%) | +$0.67 | accruing |
| rsi_oversold_spy | 0 | — | — | 1 open leg (SPY, entered 06-23) |
| tqqq_cot_combo | 0 | — | — | accumulating TQQQ (5 buys, no close yet) |
| allocator_blend | 0 | — | — | 3 open legs (QQQ/SPY/TQQQ, 06-22) |
| volume_breakout_qqq | 0 | — | — | no fills yet |
| macd_momentum_iwm | 0 | — | — | no fills yet |

Net realized across the 7 trips ≈ **+$44.71** (all-wins-dominated; one −$3.80 in qqq_regime).

### Days-to-gate — honest estimate
**~115 days at current cadence — NOT ~2 days.** The "14 evals/day" rate is the wrong denominator: evals overwhelmingly resolve to `hold`/`skip_market_closed`, not round-trips. The book is **low-turnover by design**.

- Observed trip-close cadence: **6 clean sell-closes in ~30 days ≈ 0.2 trips/day** across the whole live roster.
- 23 trips remaining ÷ 0.2/day ≈ **115 days** to organically reach 30.
- **Takeaway:** the 30-trip calibrator gate is far out at this turnover. tqqq_cot_combo (intraday vol-target) and the two unfired strategies (volume_breakout_qqq, macd_momentum_iwm) are the swing factors — if they start closing trips, cadence rises. This is a structural note for Cyrus, not a defect: the calibrator was always going to wait months on an 8-name low-turnover book.

---

## 2. Polymarket Paper P&L Snapshot

**Realized P&L: −$50.00** (matches prior record). Both losses already booked correctly:
- id11 ETH > $1,600 (Jun 22), side No → resolved YES → **−$25**
- id13 BTC → $66k (Jun 20), side Yes → resolved NO → **−$25**

**Open book: 11 bets, $875 stake outstanding** (8 Fed/macro bets @ $100 placed 06-16/17; 3 crypto/macro @ $25 placed 06-20). Live Gamma fetch confirms **0 resolved-but-unrecorded** — DB is reconciled to the exchange.

### Expiring within 7 days (≤ 2026-07-01)
- **id12 — Crude Oil (CL) settle > $63, end 2026-06-30** | side Yes, $25, our prior 0.99 vs mkt 0.947. WTI ~$76 → near-certain win; +$1.4 expected. *On track.*
- **id10 — BTC reach $70k in June, end 2026-07-01** | side Yes, $25, our prior 0.25 vs mkt 0.095. BTC well below $70k with days left → **likely −$25 loss**. Barrier bet, low base rate; flagged.

*(id9 BoI no-change, end 2026-07-06, is +12d — outside the 7d window. Mid drifted 0.09→0.10 favorable; thesis intact. Fed-complex bets #1-8 are far-dated, Jul–Dec/Jan.)*

**Net portfolio position:** −$50 realized + $875 at-risk paper. If id10 resolves loss and id12 win as expected: realized → ~−$73.6 next week.

---

## 3. Strategy Health Check (last 24h)

**All 8 live strategies HEALTHY. No errors, stalls, or missed evals.** Every strategy logged a decision at the most recent tick (20:30 UTC, 0.0h ago).

- Decisions in last 24h: breakout_xlk 31, macd_momentum_iwm 29, qqq_regime/qqq_rth/rsi_oversold/volume_breakout/tqqq_cot 28 each, allocator_blend 15.
- Current action across the board: `skip_market_closed` (expected — US market closed at gen time).
- decisions table: 3,058 rows, continuous 2026-05-25 → now. Hourly eval ticks intact during RTH.
- One synthetic XLK dust-sell (qty 1e-9) correctly flagged + excluded — no real position impact.
- **Watch item (not an error):** tqqq_cot_combo bought TQQQ 5× since 06-22 with no close — this is the ERC re-weighting (06-24) scaling into the new $160 base notional incrementally. Expected; position_drift was REAL_DRIFT=False after the dedup. Worth confirming it settles to target and doesn't keep adding.

---

## 4. Pending Cyrus Decisions

- **Paid market-data DB** — analyst estimate-revision *history* (Finnhub/Tiingo/SimFin/Zacks) is the one genuine funded edge not reachable on free tiers. Recommend if/when we pursue revision-momentum; costs money → his call.
- **80/20 mandate** — awaiting direction on whether to keep pure-explore (beat-SPX-raw, gates suspended) or shift allocation toward a risk-adjusted/graduation posture. Parked.
- **Lever / NopeCHA CAPTCHA key** — needed to unblock automated Polymarket order *placement* (and any CAPTCHA-walled data path). Paper tracker runs fine without it; only blocks live execution.

---

*Sources: `tournament.db` (trades/decisions), `polymarket_track.db` (paper_bets) + live Polymarket Gamma API. Synthetic-row guard applied. Trip counts via canonical `edge_calibrator.calibration_report()`.*
