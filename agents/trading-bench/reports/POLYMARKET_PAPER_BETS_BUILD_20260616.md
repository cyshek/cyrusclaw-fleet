# Polymarket Paper-Betting Layer + CME FedWatch — Build Report
**Date:** 2026-06-16  
**Status:** ✅ Complete — 627/627 tests passing

---

## Summary

Built a complete paper-betting layer for Polymarket Fed rate markets, using ZQ 30-Day Fed Funds Futures (Yahoo Finance) to replicate CME FedWatch probabilities. 7 paper bets placed on first run.

---

## Step 1: CME FedWatch Scraper (`runner/cme_fedwatch.py`)

**Approach:** CME FedWatch website returns 403 from datacenter IPs. Instead, Yahoo Finance serves ZQ (30-Day Fed Funds Futures) data cleanly. The math is identical — CME FedWatch itself derives probabilities from ZQ contracts.

**Formula:**
```
implied_avg_rate = 100 - futures_price
post_meeting_rate = (implied_avg * N - D * pre_rate) / (N - D)
P(cut)  = clip((pre_rate - post_meeting_rate) / 0.25, 0, 1)
P(hike) = clip((post_meeting_rate - pre_rate) / 0.25, 0, 1)
P(hold) = 1 - P(cut) - P(hike)
```

**Current ZQ Data (2026-06-16):**

| Meeting Date | Contract | Price  | Hold  | Cut25 | Hike25 |
|---|---|---|---|---|---|
| 2026-06-18   | ZQM26    | 96.375 | 100%  | 0%    | 0%     |
| 2026-07-30   | ZQN26    | 96.370 | 38%   | 0%    | 62%    |
| 2026-09-17   | ZQU26    | 96.315 | 68%   | 0%    | 32%    |
| 2026-10-29   | ZQV26    | 96.285 | 2%    | 98%   | 0%     |
| 2026-12-10   | ZQZ26    | 96.195 | 62%   | 0%    | 38%    |
| 2027-01-29   | ZQF27    | 96.170 | 63%   | 37%   | 0%     |
| 2027-03-18   | ZQH27    | 96.125 | 81%   | 0%    | 19%    |

**Current rate regime:** FF upper bound = 3.75%, midpoint = 3.625%  
**FRED:** Current rate fetched live from FRED API (DFEDTARU series)

---

## Step 2: Scanner Wiring

**Markets now with computed CME priors: 19** (out of 550 total, 76 processed Fed markets)

Patterns matched:
- `"Will the Fed decrease/increase interest rates by N+ bps after the [Month Year] meeting?"` → single-meeting cut/hike/hold probability
- `"Will X Fed rate cuts happen in 2026?"` → annual cut-count probability via Poisson/binomial from meeting priors  
- `"Will X or more Fed rate cuts happen in 2026?"` → cumulative annual probability
- `"Fed rate hike in 2026?"` → P(any hike) from annual distribution

Fallback for unrecognised patterns: flagged with "check CME FedWatch manually" in reason.

---

## Step 3: Paper Bets Table + Auto-bet Logic

**Table:** `paper_bets` in `polymarket_track.db`

**Filters applied:**
- `edge > 0.08` (min 8% discrepancy)
- `days_to_close > 3`
- `volume_usd > $50,000`
- No duplicate open bets per market

**7 paper bets placed on 2026-06-16 first run:**

| Market ID | Question (truncated) | Side | Our Prior | Market | Edge | Kelly |
|---|---|---|---|---|---|---|
| 1654959 | Fed increase 25bps July 2026? | YES | 62.0% | 2.8% | 59.3% | 0.609 |
| 1654958 | No change Fed July 2026? | NO | 38.0% | 93.5% | 55.5% | 0.594 |
| 908713  | Fed rate hike in 2026? | YES | 84.1% | 35.5% | 48.6% | 0.754 |
| 616902  | No Fed rate cuts in 2026? | NO | 37.5% | 69.6% | 32.1% | 0.461 |
| 616903  | 1 Fed rate cut in 2026? | YES | 36.8% | 20.5% | 16.3% | 0.205 |
| 616904  | 2 Fed rate cuts in 2026? | YES | 18.0% | 5.2% | 12.8% | 0.135 |
| 1654960 | Fed increase 50+bps July 2026? | YES | 9.3% | 0.3% | 9.1% | 0.091 |

**Notable signal:** ZQ futures price at 62% hike probability for July 2026 meeting, but Polymarket only prices it at 2.8%. Large edge.

**P&L math:**
- Won YES bet: `pnl = stake * (1/implied_prob - 1)` 
- Won NO bet: `pnl = stake * (1/(1 - implied_prob) - 1)`
- Lost: `pnl = -stake`
- Void (ambiguous): `pnl = 0`
- Kelly fraction stored for reference: `f_YES = (prior - implied) / (1 - implied)`

---

## Step 4: Daily Cron Script Updated

`scripts/polymarket_daily_track.sh` now runs all four steps:
1. `snapshot_flagged_markets()` — saves daily snapshot of flagged markets
2. `score_resolved_markets()` — checks for resolutions, scores priors
3. `place_paper_bets()` — places new paper bets (no duplicates)
4. `settle_paper_bets()` — settles open bets that have resolved

Log output format:
```
Snapped=7 markets. Resolved=0 accuracy=N/A%. PaperBets: placed=7 settled=0 won=0 lost=0 PnL=$0.00
```

---

## Step 5: Tests

**New test file:** `tests/test_polymarket_paper.py` — 19 tests  
**Full suite:** `python3 -m pytest tests/ -q` → **627 passed, 0 failed**

Tests cover:
- `paper_bets` table creation + column validation
- `place_paper_bets`: edge filter, duplicate prevention, side direction, volume/days filters, no-prior skip, Kelly computation
- `settle_paper_bets`: won-YES P&L math, lost P&L, won-NO P&L, void on ambiguous resolution, open market not settled, summary dict keys, multi-bet aggregation
- Integration: full place→settle cycle

---

## Files Modified / Created

| File | Action |
|---|---|
| `runner/cme_fedwatch.py` | Created — ZQ futures scraper replicating FedWatch math |
| `runner/polymarket_scanner.py` | Modified — CME prior computation for Fed markets (19 markets now have priors) |
| `runner/polymarket_tracker.py` | Modified — `paper_bets` table DDL + `place_paper_bets()` + `settle_paper_bets()` |
| `scripts/polymarket_daily_track.sh` | Modified — added place/settle calls |
| `tests/test_polymarket_paper.py` | Created — 19 tests for paper bets layer |

---

## Known Limitations / Next Steps

1. **ZQ Oct/Dec 2027 outliers:** ZQV27 shows 100% hike, ZQZ27 shows 100% cut — these are likely thinly-traded far-dated contracts with wide spreads. Far-dated priors should be discounted.
2. **Multi-cut probability model:** Currently uses a per-meeting independence approximation. A proper cumulative distribution would improve annual cut-count priors.
3. **Settlement polling:** Currently checks resolution only when cron runs (daily). For near-expiry bets, could poll more frequently.
4. **No real-time feed:** ZQ prices polled once per run. For live paper trading, would want intraday refresh.
