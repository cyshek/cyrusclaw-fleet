# TQQQ + COT Combo — 2022 Bear-Market Stress Test

**Date:** 2026-06-21
**Strategy:** `tqqq_cot_combo` (live paper — TQQQ vol-target + COT AM-momentum overlay)
**Window:** 2022-01-03 → 2022-12-30 (251 trading days — the full rate-hike bear)
**Engine:** same no-lookahead engine the live strategy uses
(`strategies_candidates/_archive/tqqq_cot_combo/backtest_combo.py` →
`run_combo_backtest`), sliced to 2022. COT publication lag (Tuesday snapshot +
3-day release) enforced via `cot_cache` release-date bisect — a price/vol move
on day D+1 cannot change today's weight.

---

## VERDICT — DID the COT filter add value in 2022?

# ✅ YES. The COT filter ADDED VALUE in 2022 — it reduced drawdown AND improved return.

- maxDD: **−26.5% (vol-target alone) → −19.8% (with COT)** — a **6.7pt / ~25% drawdown reduction**.
- 2022 return: **−24.3% → −17.4%** — COT saved **~6.9pts** of loss.
- The combo also beat plain SPX buy-and-hold on drawdown (−19.8% vs −25.4%) and roughly matched it on return (−17.4% vs −20.0%), while the raw 3x sleeve was wiped (−80%).
- The filter **signalled bearish on 2022-01-10 — at the market top, BEFORE the crash** — and stayed bearish through the worst of the Jan/Feb selloff.

This is the cleanest possible confirmation: the aggregate OOS Sharpe (0.960) does **not** mask a 2022 failure. In the single worst year for the sleeve, the COT overlay did exactly what it was designed to do.

---

## 1. Book comparison (2022, NAV rebased to 1.0 on first 2022 day)

| Book | 2022 Return | MaxDD | Ann Vol | Sharpe | Avg Weight |
|------|-------------|-------|---------|--------|------------|
| (a) TQQQ buy & hold (raw 3x) | **−79.7%** | **−81.0%** | 95.5% | −1.196 | 1.00 |
| (b) TQQQ vol-target (no COT) | −24.3% | −26.5% | 12.3% | −2.222 | 0.040 |
| **(c) TQQQ + COT combo** | **−17.4%** | **−19.8%** | 8.6% | −2.183 | 0.028 |
| (d) SPX buy & hold | −20.0% | −25.4% | 24.2% | −0.807 | — |

> Note on Sharpe: in a year where every book loses money, Sharpe is negative and **less negative ≠ better** in an intuitive sense — the meaningful 2022 metrics are **total return and maxDD**, both of which the COT overlay improved. (The combo's Sharpe is marginally less negative than vol-target's −2.222 → −2.183; not the headline.)

**Drawdown ladder:** raw 3x −81.0% → vol-target gate+sizing −26.5% → **+COT −19.8%**. Each layer compounds the protection; COT is the final ~6.7pt cut.

---

## 2. Did the COT filter signal bearish BEFORE the crash? — YES

- **First COT-bearish day in 2022: 2022-01-10.** QQQ topped the first week of January 2022; the COT Asset-Manager-net-WoW signal flipped bearish on Jan 10 and **cut the sleeve to half weight right as the selloff began**.
- COT was **bearish 138 / 251 days (55.0%)** of 2022 and bullish 113 days (45.0%).
- Bearish days were front- and back-loaded around the two legs of the bear (Jan–Jun and Sep–Oct), exactly the high-damage windows:
  `Jan 15, Feb 19, Mar 14, Apr 14, May 11, Jun 16, Jul 1, Aug 8, Sep 16, Oct 15, Dec 9` bearish-days/month.

---

## 3. Days in / out of market, and where COT actually acted

The SMA-200 trend gate is the first line of defense and it dominated 2022:

- **SMA-200 gate UP only 18 / 251 days (7.2%)** — all in one window, **2022-01-03 → 2022-04-05**. After QQQ lost its 200d SMA in spring it never reclaimed it in 2022, so the gate held the sleeve in **cash for ~93% of the year**. That alone is why both managed books lost only ~20–26% while raw TQQQ lost 80%.
- **The COT overlay can only act when the gate is UP** (it scales an existing position; it can't add risk-off below zero). So its entire 2022 opportunity was those **18 in-market days** — and it used them well.
- **Combo in-market days: 18 | vol-target in-market days: 18** (same — COT scales weight, it doesn't change the in/out gate).
- **On 11 of those 18 in-market days COT was bearish and actively halved exposure.**
- **Average weight: 0.040 (vol-target) → 0.028 (combo)** — COT shaved **31% off average exposure** across the year.

### Day-by-day on the 18 in-market days (the only days COT could matter)

The COT cut to x0.5 from Jan 10 caught the brutal down days at half size:

| Date | COT | w_vt → w_combo | TQQQ that day |
|------|-----|----------------|---------------|
| 2022-01-03 → 01-07 | bull | ~0.59 (full) | +2.9, −3.9, **−9.2**, −0.3, −3.3% |
| **2022-01-10** (flip) | **BEAR** | 0.598 → **0.299** | +0.4% |
| 2022-01-11 → 01-14 | BEAR | ~0.61 → ~0.30 | +4.4, +1.1, **−7.3**, +1.5% |
| 2022-01-18 → 01-20 | BEAR | ~0.61 → ~0.30 | **−7.2**, −3.5, −3.9% |
| 2022-02-02 → 02-03 | BEAR | ~0.48 → ~0.24 | +2.4, **−12.0**% |
| 2022-02-10 | BEAR | 0.438 → 0.219 | **−6.6%** |
| 2022-03-30, 04-05 | bull | ~0.41–0.46 (full) | −3.0, −6.6% |

**Quantified COT effect on the in-market days:** sum of daily `weight × sleeve_return`
= **−29.1% (vol-target) vs −20.8% (combo)** → **COT contributed +8.3%** on exactly the days it could act. The average TQQQ return on the 11 COT-cut days was **−2.79%** — i.e. the cut consistently landed on **down** days. It did not give back gains on up days net-net (Jan 11 +4.4% at half size was the main "cost", swamped by the −7.3/−7.2/−12.0/−6.6% days caught at half size).

---

## 4. Drawdown trough timing (2022)

| Book | Trough date | MaxDD |
|------|-------------|-------|
| (a) TQQQ buy & hold | 2022-12-28 | −81.0% |
| (b) vol-target | 2022-04-05 | −26.5% |
| (c) **COT combo** | 2022-04-05 | **−19.8%** |

Both managed books bottomed **2022-04-05** (the last gate-UP day before the sleeve went fully to cash for the rest of the year) — so the entire managed-book drawdown was incurred in that Jan–Apr in-market window, which is precisely where the COT cut applied. Raw TQQQ kept bleeding into a −81% December trough because it had no gate and no overlay.

---

## 5. Caveats & honest framing

- **The gate did most of the heavy lifting in 2022, not COT.** SMA-200 took the sleeve to cash for ~93% of the year; that's the −80% → −26% rescue. COT's contribution is the incremental −26.5% → −19.8% on top — real and in the right direction, but second-order to the gate. The headline "COT helped" is true; "COT was the primary protector" would be overstating it.
- **Small in-market sample.** COT's value in 2022 was demonstrated on 18 in-market days (11 cut days). The effect is clean and consistent (cuts landed on down days), but it's a small-N window — 2022 is one regime, and the COT overlay's standalone OOS Sharpe (0.929) carries known regime-dependency risk.
- **The 0.5 scale factor is judgment, not optimized.** A deeper cut (0.25/0.0) would have helped more in 2022 specifically, but that's hindsight-fit; 0.5 is the deployed, un-optimized value and it still added value.
- **2008 is uncovered** — CFTC TFF data begins 2010-07, so this overlay has never been stress-tested against the GFC. 2022 is the most severe drawdown it *can* be tested on.
- **Survivorship:** TQQQ exists because 3x Nasdaq went up 2010–2026. Vol-targeting + COT reshapes the surviving sleeve's risk; it does not fix survivorship.

---

## 6. Bottom line

In the 2022 rate-hike bear — the toughest available stress for this strategy — the
COT AM-momentum overlay **helped, not hurt**: it flipped bearish at the January
top, halved exposure into the worst down days, cut full-year drawdown from −26.5%
to −19.8% and full-year loss from −24.3% to −17.4%, and beat SPX on drawdown. The
aggregate OOS stats do not hide a 2022 failure. **COT filter: confirmed
value-additive in 2022.**

---

*Generated by trading-bench subagent. Research only. Paper account, TQQQ. No real orders.*
*Repro: `python3 stress_test_tqqq_cot_2022.py` (+ `_diag_inmarket_2022.py` for the in-market day breakdown). JSON: `/tmp/tqqq_cot_2022_stress.json`.*
