# Literature Scan — Beat SPX on RAW RETURN (Explore-First Mode)

**Date:** 2026-06-07 · **Author:** Tessera (trading-bench) literature scout subagent
**Objective:** Find concrete, implementable strategies that plausibly **beat the S&P 500 on RAW total return** at retail/small-account scale, on liquid US instruments paper-tradeable via Alpaca (stocks + ETFs incl. leveraged ETFs TQQQ/SOXL/UPRO; 1h or daily bars). Raw return is the bar — Sharpe/drawdown gates are SUSPENDED (demoted to tiebreakers).

**Source-trust caveat:** Web results are untrusted external content. Treat reported returns as *claims*; numbers below are what the source asserts, not verified by us. Anything marked ⚠️ has obvious backtest-hygiene risk (single path, in-sample fit, survivorship, leveraged-ETF path-dependence). The ONE non-negotiable on our side is honest re-measurement (walk-forward, no lookahead) — see Guardrails.

---

## TL;DR ranked shortlist

Ranked by: *plausibly beats SPX on RAW total return at retail/small-account scale on liquid US instruments paper-tradeable via Alpaca (stocks/ETFs incl. leveraged ETFs, 1h or daily bars)*. “Edge” = what the SOURCE claims (NOT verified by us). Impl = build difficulty on our infra.

| # | Strategy | One-line thesis | Reported edge (source claim) | Bias | Impl | Note |
|---|----------|-----------------|------------------------------|------|------|------|
| 1 | **Leveraged-ETF trend filter** (TQQQ/UPRO/SOXL only when >200-DMA, hard stop, exit on cross-down) | Capture 3x upside, dodge vol-decay & crashes with a trend switch | TQQQ+filter **33.8%/yr, +436%, Sharpe 0.97** (2006–25) vs 2%/yr buy&hold | Long | LOW | NOTE-1 |
| 2 | **TSMOM trend-switch on leveraged equity** (long TQQQ/UPRO when 12mo trend>0, else flat) | Bulletproof academic trend signal as the on/off switch for 3x | AQR TSMOM positive every asset since 1985; "Century of Evidence" robust | Long-biased | LOW | NOTE-10 |
| 3 | **SPY intraday momentum ("noise area")** — Concretum, SSRN RP24-97 | Breakout beyond an open-anchored noise band, flat overnight | **+1,985% net, 19.6%/yr, Sharpe 1.33** (2007–24), published+reproducible code | Long/short intraday | MED | NOTE-5 |
| 4 | **Sector momentum rotation (top-3 of 11), levered variant** (TECL/SOXL/FAS…) | Overweight whatever sector is ripping, 3x it | Beats cap-weight S&P; combo mom+rotation > either alone | Long | LOW–MED | NOTE-7 |
| 5 | **Concentrated quant momentum (QMOM / DIY top-50 12-2)** | Hold the ~50 strongest-momentum US stocks; lever ~1.5–2x | Live since 2015; beats S&P in mom regimes (real OOS) | Long | LOW | NOTE-9 |
| 6 | **Leveraged-ETF monthly rotation w/ macro filter** (UPRO+TQQQ ↔ QQQ+SPY ↔ TLT) | Risk-on into 2×-leveraged sleeve when VIX/trend/breadth align | **CAR 24.4%** (2010–23), -54% DD, -48% in 2022 | Long | LOW–MED | NOTE-2 |
| 7 | **Accelerating Dual Momentum, levered** (UPRO/intl-3x/TLT via 1/3/6mo blend) | Faster dual-momentum; swap risk-on leg to 3x | "Most aggressive TAA we track," strong net-of-cost CAGR since 1990 | Long | LOW | NOTE-13 |
| 8 | **TQQQ via weekly MACD on QQQ** | Trend-filter on 1x, execute on 3x, weekly = low turnover | "+10,000%" 2012–25 ⚠️ bull-only window | Long-biased | LOW | NOTE-3 |
| 9 | **All-time-high "staircase" momentum (≤5 names)** | Buy accelerating new-ATH leaders, ultra-concentrated | "+1,269%" vs S&P ⚠️ single blog | Long | MED | NOTE-8 |
| 10 | **Naked 3x buy&hold (UPRO/TQQQ/SOXL)** — the baseline to beat | In an up-decade, raw 3x already crushes SPX; problem is path | UPRO **32.5%/yr** vs SPY 14.8% (since '09); SOXL ~58%/yr 10yr | Long | TRIVIAL | NOTE-11 |
| 11 | **HEDGEFUNDIE (UPRO/TMF risk-parity), trend-gated** | 3x stocks + 3x bonds; gate the bond leg by its own trend | High CAGR pre-2022; **broke in 2022** (stocks+bonds fell together) | Long | LOW | NOTE-12 |
| 12 | **Cross-sectional momentum on S&P 500 single stocks (or hold MTUM, lever it)** | Classic Jegadeesh-Titman; top-decile 6–12mo winners | S&P Momentum index beats S&P over 10/20yr (higher vol) | Long | MED (LOW via MTUM) | NOTE-4 |
| 13 | **Overnight drift on a leveraged ETF** (hold TQQQ/UPRO close→open only) | Stack the overnight equity premium × 3x leverage | Overnight = ~entire equity premium at 1/3 risk over 30yr | Long | MED | NOTE-14 |
| — | **Dual Momentum / GEM (vanilla)** | Robust but MODEST raw edge | ~11.3% CAGR, +90–440bps/yr — mostly DD reduction | Long | LOW | NOTE-6 (methodology anchor, weak raw) |
| — | **Short-term mean reversion / Buy-on-Gap (Chan)** | FALLBACK: uncorrelated, risk-adjusted not raw | High in-sample Sharpe, decayed; low raw return | Long(/short) | MED | NOTE-15 (fallback) |

**Top-3 to actually try first (raw-return × implementability × evidence quality):** #1 leveraged-ETF 200-DMA trend filter, #2 TSMOM trend-switch on leveraged equity (same family, best pedigree — build them together as one parameterized engine), #3 Concretum SPY intraday momentum (only one with a published, net-of-cost, Sharpe-1.33, reproducible track record).

---

## Working notes (raw, per-source — pruned into shortlist below)

### NOTE-1 · Leveraged-ETF trend filter (200-DMA + short holds) — fireswalker.com 19yr backtest
- **Mechanism:** Hold TQQQ (3x QQQ) ONLY when price > 200-day MA of the underlying/ETF; max holding ~2 weeks per trade; hard stop -22%; exit immediately on close below 200-DMA. (2x QLD variant: max 6 weeks, stop -20%.)
- **Reported (2006–2025, 19yr, no costs):** TQQQ-with-filter = **+436% total / 33.8% annualized**, MDD -42%, **Sharpe 0.97**, 64 trades, 64% win. vs TQQQ buy&hold = +12% total / 2.0% ann / -69% MDD / Sharpe ~0.00. QLD-with-filter = +156% / 17.7% ann / Sharpe 0.62.
- **Why it matters HERE:** 33.8% CAGR ≫ SPX ~10%. This is almost certainly the lane the old gate killed at "0.97 < 1.0 Sharpe." On RAW RETURN it obliterates SPX. The whole point of the filter is to dodge volatility decay (the L(L-1)σ²/2 drag that makes 3x buy&hold a trap).
- **Failure mode:** (1) No costs/slippage in the test — 64 trades over 19yr is low-turnover so cost drag is modest, but the 2-week-max rule forces churn. (2) Whipsaw around the 200-DMA in chop (2015, 2018) bleeds via repeated small stop-outs. (3) Single path, single product, in-sample MA choice (200 not validated OOS here). (4) Path-dependence of daily-reset 3x means the *exact* CAGR won't replicate; the EFFECT (filter ≫ buy&hold) is robust across many writeups though.
- **Instrument:** TQQQ / QLD / SOXL / UPRO (all daily-reset leveraged, Alpaca-tradeable). Signal computed on underlying index or the 1x ETF (QQQ/SPY) to avoid noise.
- **Implement difficulty:** LOW. Daily bars, one MA, one stop, one trend flag. Trivial on our infra.
- **Bias:** Long-only / long-biased (flat in downtrends; no shorting needed).

### NOTE-2 · Leveraged-ETF monthly rotation w/ macro filter — Alvarez Quant Trading (skeptical practitioner test)
- **Mechanism (monthly, last trading day):** IF VIX≤25 AND SPX>200-DMA AND VWO has positive blended momentum AND BND has positive blended momentum → 50% UPRO + 50% TQQQ. If 1–2 of those 4 false → 50% QQQ + 50% SPY. If 3–4 false → 100% TLT. Blended momentum = (1mo×12 + 3mo×4 + 6mo×2 + 12mo)/avg. Enter next open.
- **Reported (2010–2023, AmiBroker/Norgate):** CAR **24.4%**, MaxDD **-54%**. 2022 = **-48%** (the TLT-default failed when bonds crashed with stocks), then +64% in 2023.
- **Why it matters:** 24.4% CAR ≫ SPX. The author is openly skeptical (overfit risk, ETF-selection bias) which makes the *direction* credible even if the exact number is optimistic.
- **Failure mode:** TLT-as-safe-haven breaks in rate-shock regimes (2022). VWO filter is non-obvious (possible overfit). Unknown # of ETF combos tried = selection bias. -54% DD is brutal but IRRELEVANT to raw-return bar.
- **Instrument:** UPRO, TQQQ, QQQ, SPY, TLT, + VIX/VWO/BND as signals. All Alpaca-tradeable.
- **Implement difficulty:** LOW–MED. Monthly rebalance, blended-momentum calc, a few filters. Need VIX level (free) and VWO/BND bars.
- **Bias:** Long-only (rotates among long ETFs + bonds; no shorting).

### NOTE-3 · TQQQ via QQQ weekly MACD crossover — lambrospetrou.com
- **Mechanism:** Trade TQQQ (3x) using signals from the 1x QQQ/NDX on the WEEKLY timeframe. Long TQQQ on weekly MACD bullish cross; exit on bearish cross; strict stop-losses; ≤5 trades/month; closing prices only (no intraday). "Cross-symbol": signal from unleveraged, execution on leveraged.
- **Reported:** "+10,000% total profit 2012–2025" (TradingView strategy tester). ⚠️ window is post-GFC bull-only — heavy regime-luck; treat the *headline* as unreliable, the *mechanism* (weekly MACD on 1x → trade 3x) as a legit variant of trend-filtered leverage.
- **Why it matters:** Another instance of the same family (trend filter on 1x → leveraged exposure) producing >>SPX. Weekly timeframe → very low turnover, low cost drag.
- **Failure mode:** Cherry-picked start (2012, right after the bottom). MACD whipsaw in range markets. Depends explicitly on "US tech keeps winning" — author lists this as an assumption. No OOS shown.
- **Instrument:** TQQQ (US) signalled off QQQ/NDX. UPRO/SPX variant also mentioned.
- **Implement difficulty:** LOW. Weekly MACD + stop. Trivial.
- **Bias:** Long-only / long-biased.

### NOTE-4 · Cross-sectional momentum on S&P 500 single stocks — IBKR/academic (Jegadeesh-Titman lineage)
- **Mechanism:** Rank S&P 500 constituents by trailing 6–12mo price return; hold the top decile/quintile (equal-weight), rebalance monthly/quarterly, drop laggards. Pure price signal, no fundamentals. (S&P 500 Momentum Index is the investable benchmark version.)
- **Reported:** S&P 500 Momentum index "clearly outperforms" plain S&P 500 over 10/20yr horizons with higher cumulative return (and higher vol). This is the single most-replicated anomaly in finance (Jegadeesh & Titman 1993; Asness/AQR).
- **Why it matters:** Long, durable, real-money track record (MTUM ETF, S&P Momentum index live since 2014). Beats SPX on raw return over most multiyear windows; can be levered for more.
- **Failure mode:** Momentum CRASHES — violent reversals after bear-market bottoms (2009, 2020 recoveries) when prior losers rip. Higher vol & DD than index. Crowding/decay risk.
- **Instrument:** S&P 500 / liquid US large-caps. Or just hold MTUM (Alpaca-tradeable) as the off-the-shelf version; lever via 2x exposure for raw-return boost.
- **Implement difficulty:** MED for the DIY single-stock version (need 500-name universe + monthly rank); LOW if you just trade MTUM. Needs constituent price history (free-ish).
- **Bias:** Long-only (cross-sectional long top names).

### NOTE-5 · SPY intraday momentum ("noise area" breakout) — Concretum Research, SSRN/Swiss Finance Institute RP24-97 (PUBLISHED PAPER)
- **Mechanism:** Define a "noise area" = time-varying band around the day's open, built from SPY's avg absolute move-from-open at each intraday timestamp over the prior 14 sessions. When price breaks ABOVE the upper band → go long; below lower band → go short; position sized by vol target; flatten at close (intraday only, no overnight). Uses bars through the whole session, not just last 30min.
- **Reported (2007–2024):** ~**2,000% total return**, strong risk-adjusted (paper reports high Sharpe); published, peer-style, with full reproducible Python/MATLAB code on Polygon data.
- **Precise figures (blog):** Total return **1,985% net of costs**, **annualized 19.6%**, **Sharpe 1.33** — costs & slippage explicitly included. Risk control = dynamic trailing stops. Intraday only (flat overnight).
- **Why it matters:** 19.6% net-of-cost annualized ≫ SPX ~10%, AND it's a genuinely published paper with reproducible code — the gold-standard among these leads. Intraday/flat-overnight means no gap risk.
- **Failure mode:** (1) Needs intraday bars (we have 1h — the paper uses finer; 1h may dull the edge). (2) High turnover → cost-sensitive (they net it, but our fills differ). (3) Edge partly tied to dealer-gamma/0DTE microstructure that can decay. (4) Requires disciplined same-day exits.
- **Instrument:** SPY (could extend to QQQ). Alpaca-tradeable; needs intraday data feed.
- **Implement difficulty:** MED. Need intraday bars + noise-band calc + trailing stops + flatten-at-close. Code is public. 1h-bar adaptation is the main unknown.
- **Bias:** Long AND short intraday (the short leg matters less for raw return; a long-only intraday-breakout variant is viable).

### NOTE-6 · Dual Momentum / GEM (Antonacci) — optimalmomentum.com, book + NAAIM-award paper
- **Mechanism (monthly):** Absolute-momentum gate: is SPY 12mo return > T-bill? If NO → hold AGG (bonds). If YES → relative-momentum pick between US equities (SPY) and international (VEU), hold the higher 12mo performer. One position at a time, monthly check.
- **Reported:** GEM ~**+440bps/yr over S&P 500 since 1950** (relative-mom alone +200bps, absolute-mom alone +90bps). But headline CAGR only ~**11.3%** — so the raw-return edge over SPX is REAL but MODEST; most of GEM's fame is drawdown reduction (which the new bar de-prioritizes).
- **Why it matters / caveat:** As a RAW-RETURN play GEM is weak-ish (small edge, and the bond-default years drag). KEEP IT as (a) a robust, real-track-record methodology anchor and (b) a chassis to LEVER — GEM-on-leveraged-ETFs (hold UPRO instead of SPY when risk-on) converts its modest edge into a high-raw-return engine. The lever-up variant is the interesting one here.
- **Failure mode:** Whipsaw at the absolute-mom threshold; 2022 stock+bond joint drawdown; international leg has lagged for a decade.
- **Instrument:** SPY/VEU/AGG (vanilla) or UPRO/intl-3x/bonds (levered variant). Alpaca-tradeable.
- **Implement difficulty:** LOW. Monthly, 12mo returns, one switch. Very clean.
- **Bias:** Long-only.

### NOTE-7 · Sector momentum rotation — Quantpedia (FREE strategy) + QuantConnect
- **Mechanism (monthly):** Rank the ~9–11 US SPDR sector ETFs (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC) by trailing 12mo (or 3–6mo) return; hold the top 3 equal-weight; rebalance monthly; optionally add an absolute-momentum/200-DMA filter to go to cash/bonds in downtrends.
- **Reported:** Quantpedia/QuantConnect summaries cite outperformance vs buy&hold S&P with the top-3 12mo-momentum sector basket; combining momentum + rotation historically beats either alone (exact CAGR varies by window/source; typically low-to-mid teens with higher vol).
- **Why it matters:** Concentrated sector tilts (top-3 of 11) overweight whatever's ripping (often tech/energy) → can beat cap-weight SPX on raw return, especially levered (swap XLK→TECL, XLE→ERX, XLF→FAS for 3x sector exposure).
- **Failure mode:** Sector chop / frequent rotation → turnover & whipsaw; concentration risk when leadership flips fast; momentum crashes.
- **Instrument:** SPDR sector ETFs (vanilla) or 3x sector ETFs (Direxion: TECL/SOXL/FAS/ERX/etc.) for the aggressive raw-return version. Alpaca-tradeable.
- **Implement difficulty:** LOW–MED. Monthly rank of ~11 ETFs + hold top 3. Clean.
- **Bias:** Long-only.

### NOTE-8 · All-time-high "staircase" momentum (concentrated, 5 names) — ravenquant.com
- **Mechanism (monthly):** Scan universe for stocks making a NEW all-time high in each of last 3 consecutive months, each month's ATH ≥ 1.05× prior month's ATH (accelerating). From cohort, take up to 5 names equal-weight; hold in non-overlapping batches; rotate on schedule. Concentrated (≤5 positions).
- **Reported:** "+1,269%" headline beating S&P 500 (after-tax shown). ⚠️ single-source blog, unknown OOS.
- **Why it matters:** Highly CONCENTRATED (≤5 names) high-conviction tilt — exactly the low-diversification lane old gates killed. Accelerating-ATH filter targets explosive leaders; concentration → high raw return when it hits.
- **Failure mode:** 5-name concentration → brutal idiosyncratic DD; ATH-chasing tops at cycle peaks; thin qualifying set some months; survivorship in backtest universe.
- **Instrument:** Liquid US stocks (constrain to S&P 500 / Nasdaq-100). Alpaca-tradeable.
- **Implement difficulty:** MED. ATH tracking + 3-mo accelerating logic + monthly rebalance over universe.
- **Bias:** Long-only.

### NOTE-9 · QMOM — Alpha Architect US Quantitative Momentum ETF (LIVE record, off-the-shelf)
- **Mechanism:** From US universe pick ~50 stocks with HIGHEST relative momentum (12-2: 12mo return ex most-recent month) + "momentum quality/smoothness" screen (Frog-in-the-Pan path consistency). ~Quarterly rebalance. Concentrated vs broad index.
- **Reported:** Live since 2015 (real fund, not just backtest). Beats S&P 500 in strong-mom regimes, lags in mom-crashes/value years; higher vol. (Exact trailing CAGR on financecharts/ycharts.)
- **Why it matters:** Genuinely CONCENTRATED (~50-stock) momentum book with a REAL out-of-sample live record — can be HELD or levered ~1.5–2x via margin as a raw-return engine; zero selection-logic build needed.
- **Failure mode:** Momentum crashes (2009, brief 2020); multi-year value-regime underperformance (2016, 2022); concentration tracking error.
- **Instrument:** QMOM (hold directly); also IMOM (intl), VMOT (mom+trend overlay). Alpaca-tradeable.
- **Implement difficulty:** LOW (hold/rotate). DIY book version (top-decile 12-2, smoothness screen, ~50 names) is MED.
- **Bias:** Long-only.

### NOTE-10 · Time-series momentum / trend-following (TSMOM) on equity-index ETFs — AQR (Moskowitz-Ooi-Pedersen 2012) + Hurst-Ooi-Pedersen "Century of Evidence"
- **Mechanism:** For each asset, if trailing 12mo (or 1/3/12mo blend) return > 0 → long; if < 0 → flat/short. Vol-target each position. Monthly. Applied to SPY/QQQ/sector ETFs (long-only-when-positive variant avoids shorting). This is the engine behind managed futures/CTAs.
- **Reported:** AQR TSMOM positive for EVERY asset class tested since 1985; diversified TSMOM gross Sharpe ~1.8 (multi-asset). "Century of Evidence" (1880–2013): trend-following profitable across a century, strong crisis performance. NOTE: pure equity-only TSMOM's RAW return ≈ buy&hold-ish but with crash-avoidance; the raw-return juice comes from applying it to LEVERED equity ETFs.
- **Why it matters:** Most academically bulletproof trend signal. As a raw-return play, the move is TSMOM-as-the-on/off-switch for TQQQ/UPRO (long 3x when 12mo trend > 0, flat otherwise) — same family as NOTE-1, with the strongest literature pedigree.
- **Failure mode:** Whipsaw in trendless/choppy regimes (2011, 2015, 2018); sharp V-reversals; signal lag at turns.
- **Instrument:** SPY/QQQ + leveraged TQQQ/UPRO/SOXL for the aggressive version. Alpaca-tradeable. Long-only-when-positive needs no shorting.
- **Implement difficulty:** LOW. One sign-of-trailing-return check + vol target. Very clean.
- **Bias:** Long-biased (long-when-positive variant; classic version shorts but short leg optional).

### NOTE-11 · Naked 3x buy-&-hold (UPRO/TQQQ/SOXL) — the raw-return baseline to BEAT (and a real lane)
- **Mechanism:** Just hold the 3x ETF. UPRO=3x S&P, TQQQ=3x Nasdaq-100, SOXL=3x semis.
- **Reported:** UPRO since 2009 inception **CAGR 32.52% vs SPY 14.79%** (stdev 51% vs 17%). TQQQ ~42.8%/yr last 10yr; SOXL ~58%/yr last 10yr. (portfolioslab/etfportfolioblueprint.)
- **Why it matters:** On the RAW-RETURN bar over the post-2009 era, naked 3x already CRUSHED SPX. This is the brutal truth the old Sharpe/DD gates hid: 3x buy&hold's problem is path/drawdown (-90%+ in a crash, vol decay in chop), NOT raw CAGR in an up-decade. Any trend filter (NOTE-1/10) that keeps most of the upside while dodging the worst drawdowns is the actual prize. Use naked 3x as the BENCHMARK the filtered versions must beat or match with less ruin.
- **Failure mode:** Volatility decay in sideways/choppy markets; catastrophic -90%+ drawdown in a sustained bear (2022 TQQQ ≈ -79%); can be path-killed even if index recovers. Pure hold is fragile — but high raw return when the decade trends up.
- **Instrument:** UPRO / TQQQ / SOXL / SPXL / FAS / TECL. Alpaca-tradeable.
- **Implement difficulty:** TRIVIAL (buy and hold). The value is as a yardstick + a "risk-on sleeve" inside a timed strategy.
- **Bias:** Long-only.

### NOTE-12 · HEDGEFUNDIE's Excellent Adventure (UPRO/TMF risk-parity) — Bogleheads-famous concrete portfolio
- **Mechanism:** Hold a leveraged risk-parity mix: 55% UPRO (3x S&P) + 45% TMF (3x 20yr Treasuries); rebalance quarterly. Idea: 3x stocks for return, 3x long bonds as a (formerly) negatively-correlated crash hedge that's itself levered.
- **Reported:** Backtests pre-2022 showed very high CAGR (often >20%) with the bond leg cushioning equity crashes; widely forward-tracked since 2019.
- **Why it matters:** A concrete, documented leveraged-long portfolio with a real follow-along community. As raw-return it can beat SPX in bond-bull/stock-bull regimes.
- **Failure mode:** BROKE in 2022 — stocks AND long bonds fell together (TMF ≈ -70%), so the hedge failed and the combo got hammered. Stock-bond correlation regime risk is the whole ballgame. A trend-overlay on the bond leg (only hold TMF when its trend>0) is the obvious patch.
- **Instrument:** UPRO + TMF (and variants UPRO/TMF/managed-futures). Alpaca-tradeable.
- **Implement difficulty:** LOW. Two ETFs, quarterly rebalance. Patched (trend-gated) version is LOW–MED.
- **Bias:** Long-only.

### NOTE-13 · Accelerating Dual Momentum (ADM) — Engineered Portfolio (S.Hanly 2018), AllocateSmartly-verified
- **Mechanism (monthly, last close):** Momentum score = avg of 1mo + 3mo + 6mo total return. Compute for SPY and SCZ (intl small-cap). If score(SPY) > score(SCZ) AND > 0 → 100% SPY. If score(SCZ) > score(SPY) AND > 0 → 100% SCZ. Else → 100% TLT (or TIP, whichever has higher 1mo). Single asset at a time. Hold one month.
- **Reported (AllocateSmartly, 1990→present, NET of costs):** Strong long-run CAGR with much lower DD than buy&hold; AllocateSmartly flags it as "by TAA standards extremely aggressive — highest portfolio volatility of any strategy we track." (A 2021 "redux" tempered expectations on the longer history.)
- **Why it matters:** A cleaner, more responsive (1/3/6mo) dual-momentum than GEM with a third-party net-of-cost verification. The aggressive raw-return version: swap SPY→UPRO and SCZ→intl-3x (or just keep the SPY leg as UPRO) → turns the highest-vol TAA into a high-raw-return engine with a built-in TLT crash valve.
- **Failure mode:** Shorter lookback → more whipsaw/turnover/cost; TLT-fallback fails in 2022-style joint stock/bond selloffs (mitigated by the TIP option); intl-small leg adds noise.
- **Instrument:** SPY, SCZ, TLT/TIP (vanilla) or UPRO + intl-3x + TLT (aggressive). Alpaca-tradeable.
- **Implement difficulty:** LOW. Monthly, 3 lookbacks averaged, pick 1 of 3. Very clean.
- **Bias:** Long-only.

### NOTE-14 · Overnight (close-to-open) drift — Falkenstein/Cliff/Cooper; QuantConnect; ELM Wealth
- **Mechanism:** Buy SPY (or QQQ) at the close, sell at the next open — capture only the overnight session; sit out the intraday session. Repeat daily.
- **Reported:** Over ~30yr, SPY OPEN→CLOSE (intraday) grew $1→~$1.20 (below T-bills) while CLOSE→OPEN (overnight) captured essentially the ENTIRE equity premium at ~1/3 the risk. Robust, decades-long, cross-country anomaly (developed-market wide).
- **Why it matters (aggressive twist):** Vanilla overnight-only ≈ matches buy&hold raw return at lower risk — NOT a raw-return beater alone. BUT the documented aggressive version is **hold a LEVERAGED ETF (TQQQ/UPRO) overnight only** — capture 3x the overnight drift while dodging the intraday vol-decay churn that hurts 3x. That stacks two effects (leverage × overnight premium) and can plausibly beat SPX raw.
- **Failure mode:** Extremely slippage/fee sensitive (you trade every single day at open+close — the at-open fill is exactly where retail flow is worst). Edge has thinned post-2015. Gap-down overnight crash risk is concentrated in the held session. Leveraged version magnifies all of this.
- **Instrument:** SPY/QQQ (vanilla) or TQQQ/UPRO (aggressive overnight-only). Alpaca-tradeable; needs reliable MOC/MOO execution.
- **Implement difficulty:** MED. Mechanically simple but execution-cost-critical; needs MOC/MOO order discipline + honest slippage modeling (this is exactly where a naive backtest lies).
- **Bias:** Long-only.

### NOTE-15 · Short-term mean reversion / Buy-on-Gap (Ernie Chan, "Algorithmic Trading" ch.4) — FALLBACK lane
- **Mechanism (Buy-on-Gap):** At open, rank stocks that gapped DOWN below prior-day low by more than X× recent vol; buy the most-oversold N that are still above their 200-DMA (long-term uptrend filter); exit at the close (intraday hold). Daily. Variants: short-term reversal (buy 1-week losers, sell 1-week winners), Bollinger-band ETF mean reversion.
- **Reported (book):** Historically high Sharpe (often >1.5 in-sample) but LOW per-trade edge and modest raw return; widely reported as DECAYED in liquid US stocks post-2010 (Reddit/QC replications mixed).
- **Why it matters / caveat:** This is a RISK-ADJUSTED play, not a raw-return monster — so it's a FALLBACK under the new bar. Included because (a) it's uncorrelated to the trend/leverage lanes, (b) it can be LEVERED, and (c) it's a known, concrete, implementable chassis if the aggressive lanes stall.
- **Failure mode:** Edge decay/crowding; mean-reversion turns to momentum in crashes (catching falling knives 2008/2020); high turnover → cost-sensitive.
- **Instrument:** Liquid US stocks + ETFs. Alpaca-tradeable.
- **Implement difficulty:** MED. Daily universe scan + gap/vol ranking + intraday exit.
- **Bias:** Long-only (long-oversold variant); classic version is long/short.

---

## Aggressive lanes the old gates killed (explicit resurfacing)

The bench's prior "timid gates" (1.0-Sharpe minimum, tight max-DD, conservative cost haircuts, diversification preference) systematically rejected the highest-RAW-RETURN ideas. Under the new bar (raw return is the bar, Sharpe/DD demoted to tiebreakers), these are the lanes to UN-reject:

1. **Leveraged-ETF trend-following (the prior SOXL/TQQQ/UPRO lane) — REOPEN.**
   - The prior rejection killed this *only* for missing a 1.0-Sharpe gate. The most directly comparable published version (NOTE-1) scores **0.97 Sharpe** — i.e., it failed the old gate by a rounding error — while delivering **33.8%/yr / +436% total**. On the NEW bar (raw return), 33.8% CAGR vs SPX's ~10% is a blowout. **The 0.97 Sharpe is not a reason to reject; it's a footnote.** This should be re-instantiated immediately, with the trend filter (200-DMA and/or 12mo TSMOM) as the only thing standing between us and naked 3x.
   - Sibling evidence that the *direction* is robust across many independent authors: NOTE-2 (24.4% CAR), NOTE-3 (weekly-MACD on 3x), NOTE-10 (TSMOM pedigree), NOTE-11 (naked UPRO 32.5%/yr since '09). Five+ independent sources, same conclusion: **trend-gated leverage on equity indices beats SPX raw over the modern era.**

2. **Naked / lightly-managed 3x buy&hold as a legitimate raw-return sleeve — REOPEN.**
   - UPRO since 2009 = **32.5%/yr vs SPY 14.8%**. The old gates killed this on the -97%-theoretical-drawdown and 51% vol. But raw return is the bar now. The honest framing: naked 3x is the *upper bound* of the trend-filtered strategies and the benchmark they must justify themselves against. Don't deploy it naked (path risk is real — TQQQ ~-79% in 2022), but STOP treating "it can draw down a lot" as disqualifying. Use it as the risk-on engine inside a timing rule.

3. **Concentrated / low-diversification high-conviction tilts — REOPEN.**
   - NOTE-8 (\u22645-name accelerating-ATH momentum), NOTE-9 (QMOM ~50 names), NOTE-7 (top-3-of-11 sectors). The old "diversify / cut concentration risk" preference demoted exactly the books that produce high raw return. Concentration IS the raw-return lever for cross-sectional momentum. Embrace \u226450-name (even \u22645-name) sleeves; size them as a *fraction* of capital if ruin is a concern, but don't water them down to closet-index.

4. **Leveraged sector rotation — NEW aggressive lane.**
   - Swap the vanilla sector ETFs in a top-3 momentum rotation for their 3x Direxion cousins (TECL/SOXL/FAS/ERX/LABU/DRN). This stacks (sector selection) \u00d7 (3x leverage) \u00d7 (momentum) — high raw return when a sector trends hard. Gate with the same 200-DMA/TSMOM trend switch to avoid holding 3x sector funds in a downtrend.

5. **Leveraged overnight-drift / leveraged dual-momentum chassis — NEW aggressive lanes.**
   - NOTE-14 (hold 3x overnight-only) and NOTE-13/NOTE-6 levered (UPRO as the risk-on leg of ADM/GEM). Both convert a known robust effect into a high-raw-return engine. The leveraged-overnight one is the most slippage-fragile — flag for honest cost modeling — but conceptually stacks two edges.

**Common pattern across all aggressive lanes:** the raw-return engine is *leverage on a trending risk asset*; the only thing that separates "beats SPX with survivable path" from "ruin" is a TREND FILTER (200-DMA or 12mo TSMOM) that flips the leverage OFF in downtrends. Build that filter once, apply it to TQQQ/UPRO/SOXL/3x-sectors — that single primitive underlies ranks #1, #2, #4, #6, #7, #11, #13.

---

## Methodology guardrails to keep us honest (the ONE research constraint we keep)

Raw return is the bar, but **honest measurement is non-negotiable** — most of the eye-popping numbers above are single-path, in-sample, or cost-naive. Apply these (Lopez de Prado *Advances in Financial ML*; standard walk-forward hygiene) before believing ANY of them on our own re-test:

- **No lookahead / point-in-time data.** Signals must use only data available at decision time. Index-constituent lists must be point-in-time (avoid survivorship: backtesting today's S&P 500 members back 20yr inflates momentum/ATH results massively — this likely flatters NOTE-4/8). Use as-traded ETF inception dates; don't backfill leveraged ETFs with synthetic pre-inception data without flagging it.
- **Walk-forward / out-of-sample, not one in-sample fit.** Prefer **combinatorial purged cross-validation (CPCV)** with **purging + embargo** around train/test boundaries so overlapping-label leakage (esp. for multi-day holds) doesn't inflate results. Reserve a true holdout the parameters never touched.
- **Deflated Sharpe / multiple-testing correction.** We're scanning 15 ideas \u00d7 many parameter sets — the best-looking backtest is partly luck. Apply the **Deflated Sharpe Ratio** and account for the number of trials. A strategy found after 1000 configs needs a much higher bar than one tested once. (This is the antidote to "I found a +10,000% backtest.")
- **Realistic costs & path for leveraged ETFs.** Model commissions + **slippage at the actual fill** (overnight/intraday strategies trade at the worst-liquidity moments — NOTE-14 especially). For 3x ETFs, simulate **daily-reset path-dependence and volatility decay explicitly** (don't approximate 3x as 3\u00d7 the index return over multi-day spans) and include the ~0.9% expense ratio + borrow/financing drag. The fireswalker numbers (NOTE-1) are NET of nothing — re-run with costs.
- **Regime / sub-period robustness.** Report performance separately across 2008, 2011, 2015\u201316, 2018, 2020, 2022 (and choppy vs trending). A strategy that only works 2012\u201321 (NOTE-3/NOTE-12) is a bull-market artifact. Demand it survive at least one bad regime, even if degraded.
- **Turnover & capacity sanity.** Confirm the strategy's edge survives its own trading frequency (NOTE-13/14/15 are turnover-heavy). At small-account scale capacity isn't binding, but cost-per-turn is.
- **Decay awareness.** Published anomalies decay post-publication (intraday/overnight microstructure edges especially). Prefer ideas with a *structural/behavioral* reason to persist (trend-following, momentum) over pure statistical artifacts.

**Bottom line for the bench:** the literature strongly supports that **trend-gated leverage on equity indices** (ranks #1\u2013#2) is the highest-conviction, best-evidenced path to beating SPX on raw return, and it's LOW effort to build. Stand it up first, measure it honestly with the guardrails above, and let raw CAGR (not Sharpe) decide. Concretum intraday momentum (#3) is the single best *published* edge if we can handle intraday execution. Everything else is gravy or fallback.

*End of report. All performance figures are source claims from untrusted web content, not independently verified.*
