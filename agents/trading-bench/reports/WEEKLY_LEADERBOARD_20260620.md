# 🏆 Trading Tournament — Weekly Leaderboard
**Week ending:** Friday 2026-06-20 (as of 13:30 UTC)
**Generated:** 2026-06-20
**Active strategies:** 11 live | Tournament DB snapshot: `tournament.db`

---

## 📊 Rankings — All Live Strategies

| Rank | Strategy | Round-Trips | Realized P&L | Unrealized P&L | Total P&L | Win Rate |
|------|----------|:-----------:|-------------:|---------------:|----------:|:--------:|
| 🥇 1 | `breakout_xlk__mut_c382b1` | 3 | **+$44.05** | $0.00 | **+$44.05** | 100% |
| 🥈 2 | `breakout_xlk_regime` | 4 | +$4.68 | $0.00 | **+$4.68** | 100% |
| 🥉 3 | `breakout_xlk` | 4 | +$4.57 | $0.00 | **+$4.57** | 100% |
| 4 | `sma_crossover_qqq` | 4 | +$3.87 | $0.00 | **+$3.87** | 100% |
| 5 | `sma_crossover_qqq_regime` | 4 | +$3.82 | $0.00 | **+$3.82** | 100% |
| 6 | `sma_crossover_qqq_rth` | 2 | +$0.67 | $0.00 | **+$0.67** | 100% |
| 7 | `rsi_oversold_spy` ⭐ | 0 | $0.00 | $0.00 | $0.00 | — |
| 7 | `volume_breakout_qqq` ⭐ | 0 | $0.00 | $0.00 | $0.00 | — |
| 7 | `macd_momentum_iwm` ⭐ | 0 | $0.00 | $0.00 | $0.00 | — |
| 10 | `tqqq_cot_combo` | 0† | $0.00 | **-$1.55** | **-$1.55** | — |
| 11 | `leveraged_long_trend_paper` | 0† | $0.00 | **-$1.69** | **-$1.69** | — |

> ⭐ New strategies (added 2026-06-13) — running but no entries triggered yet
> † TQQQ strategies are long-only accumulators; no round-trips by design (buys only, no sells)
> All n_trades counts are filled orders (each buy counts as 1 trade entry)

---

## 📈 Week-over-Week Change (vs 2026-06-13)

| Strategy | Total P&L (now) | Total P&L (Jun 13) | WoW Δ |
|----------|----------------:|-------------------:|------:|
| `breakout_xlk__mut_c382b1` | +$44.05 | $0.00 | **+$44.05** |
| `breakout_xlk_regime` | +$4.68 | +$0.34 | +$4.34 |
| `breakout_xlk` | +$4.57 | +$0.27 | +$4.30 |
| `sma_crossover_qqq` | +$3.87 | +$0.96 | +$2.91 |
| `sma_crossover_qqq_regime` | +$3.82 | +$0.85 | +$2.97 |
| `sma_crossover_qqq_rth` | +$0.67 | +$0.67 | $0.00 (no new trade) |
| `leveraged_long_trend_paper` | -$1.69 | *(new)* | — |
| `tqqq_cot_combo` | -$1.55 | *(new)* | — |
| `rsi_oversold_spy` | $0.00 | *(new)* | — |
| `volume_breakout_qqq` | $0.00 | *(new)* | — |
| `macd_momentum_iwm` | $0.00 | *(new)* | — |

> Note: `sma_crossover_qqq_rth` last round-trip was 2026-06-04; no new entry since Jun 13.

---

## 🔓 Open Positions (TQQQ Strategies)

Both TQQQ strategies are long-only accumulators — they DCA into positions over time. No sells recorded.

### `tqqq_cot_combo`
| Date | Side | Qty | Notional | Price | Reason |
|------|------|----:|--------:|------:|--------|
| 2026-06-15 | BUY | 1.2083 | $100 | $82.75 | underweight +6sh; COT_scale=0.5; rv=31.9% |
| 2026-06-16 | BUY | 1.1914 | $100 | $83.93 | underweight +4sh; rv=25.2% |
| 2026-06-17 | BUY | 1.2292 | $100 | $81.35 | underweight +4sh; rv=24.2% |
| 2026-06-18 | BUY | 1.2159 | $100 | $82.24 | underweight +3sh; rv=22.6% |
| **Total open** | | **4.8447 sh** | **$400 in** | avg ~$82.57 | |

- Unrealized P&L: **-$1.55** (TQQQ ~$81.90 at last eval)

### `leveraged_long_trend_paper`
| Date | Side | Qty | Notional | Price | Reason |
|------|------|----:|--------:|------:|--------|
| 2026-06-15 | BUY | 1.2087 | $100 | $82.72 | voltarget w=0.33; rv=76.7%; gate=ON |
| 2026-06-16 | BUY | 1.1909 | $100 | $83.96 | voltarget w=0.31; rv=81.1%; gate=ON |
| 2026-06-17 | BUY | 1.2275 | $100 | $81.46 | voltarget w=0.30; rv=83.7%; gate=ON |
| **Total open** | | **3.6271 sh** | **$300 in** | avg ~$82.70 | |

- Unrealized P&L: **-$1.69** (TQQQ ~$81.53 at last eval)

> ⚠️ Both TQQQ strategies bought into the Jun 15-17 dip. The slight red is due to TQQQ pulling back after entries. Gate remains ON (QQQ > SMA200).

---

## 🔍 Notable Observations

### 1. `breakout_xlk__mut_c382b1` — Clear Runaway Leader
The mutant variant of breakout_xlk has **10x the P&L** of its parent. Key reason: it deployed **$1,000 notional** per entry vs. $100 for the base strategies. Two clean round-trips (Jun 12 buy → Jun 14 sell at +$40.71, then Jun 18 sell of residual position). Win rate 100%, 3 total orders (1 large buy, 1 large sell, 1 residual sell).

### 2. New Strategies Running Clean — No Signals Yet
All three strategies added 2026-06-13 (`rsi_oversold_spy`, `volume_breakout_qqq`, `macd_momentum_iwm`) are:
- ✅ **Running:** 70 successful runs each over 7 days, zero errors
- ⏳ **No trades:** Their entry conditions haven't fired — not bugs, just patient strategies
- `rsi_oversold_spy`: Waits for RSI dip below oversold threshold on SPY
- `volume_breakout_qqq`: Waits for volume-confirmed breakout on QQQ
- `macd_momentum_iwm`: Waits for MACD signal on IWM (small-cap)

### 3. XLK + QQQ Strategies All Profitable
Breakout (XLK) and SMA crossover (QQQ) families are both 100% win-rate with consistent P&L. The XLK breakout strategies completed a second round-trip this week (Jun 12 buy → Jun 18 sell at ~190.44 vs ~182.60 entry = ~+4% gain). The QQQ SMA strategies matched this (Jun 12 buy → Jun 18 sell at QQQ 736.42 vs 715.39 entry = ~+2.9% gain).

### 4. `sma_crossover_qqq_rth` Lagging — No New Entry
Only 2 round-trips total; last entry was 2026-06-04. The RTH (regular trading hours only) variant is more restrictive and has missed the Jun 12 re-entry that the other QQQ variants caught.

### 5. TQQQ Gate Active — Trend-Follow Accumulating
Both TQQQ strategies have QQQ > SMA200 gate confirmed ON (QQQ ~721-744 vs SMA200 ~625-628). They're systematically accumulating into the position. The small unrealized loss (-$1.55 to -$1.69) reflects the Jun 18-20 pullback after entries on Jun 15-18.

---

## 🗑️ Orphan Strategies (in DB but NOT live)

These appear in `tournament.db` but are **not** in the active crontab:

| Strategy | Last P&L | Notes |
|----------|--------:|-------|
| `any` | $0.00 | Placeholder/test strategy |
| `backstop_test` | -$120.00 | Legacy test; large paper loss from testing |
| `bp2` | $0.00 | Old strategy slot |
| `breakout_ltc` | $0.00 | Crypto strategy (LTC) — not wired |
| `buy_and_hold_btc` | -$5.19 | Crypto BTC position — unrealized loss |
| `momentum_sol` | $0.00 | Crypto SOL strategy — not wired |
| `rsi_mean_revert_eth` | $0.00 | Crypto ETH strategy — not wired |
| `sma_crossover_btc` | -$2.04 | Crypto BTC SMA — realized loss |

> ✅ **No live strategies expected to be in DB are missing.** The 3 new strategies (rsi, vol_breakout, macd) have runs but no rankings rows yet (rankings are only written on actual trade events or scheduled snapshots that emit them — their zero-P&L state may not be written as a ranking row if they have never generated any scores).

---

## ⚙️ Crontab Status

All 11 live strategies confirmed wired in crontab:
```
*/30 7-13 * * 1-5 cron_tick.sh \
  breakout_xlk sma_crossover_qqq breakout_xlk_regime sma_crossover_qqq_regime \
  sma_crossover_qqq_rth breakout_xlk__mut_c382b1 leveraged_long_trend_paper \
  rsi_oversold_spy volume_breakout_qqq macd_momentum_iwm tqqq_cot_combo
```
- Cadence: every 30 min, Mon-Fri 07:00–13:30 PT (market hours)
- Last confirmed run: 2026-06-19T13:30 UTC for all 11 (market closed Jun 20 — Friday data)
- All strategies: 70-71 runs in last 7 days, **zero errors**

---

## 📋 Summary

| Metric | Value |
|--------|-------|
| Total strategies live | 11 |
| Strategies with realized gains | 6 |
| Strategies flat/waiting | 3 (new) |
| Strategies with open long positions | 2 (TQQQ) |
| Overall realized P&L (live strats) | **+$61.65** |
| Overall unrealized P&L | **-$3.24** |
| **Combined total P&L** | **+$58.41** |
| Crontab health | ✅ All 11 wired, 0 errors |

*Report generated by trading-bench subagent. Data source: `tournament.db` at 2026-06-20T13:30 UTC.*
