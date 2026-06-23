# FINRA Short-Volume Lane — PRE-REGISTRATION (written BEFORE seeing any results)

Timestamp (UTC): see file mtime. Author: trading-bench subagent (finra-shortvol-lane).

## What the data IS (honest framing)
FINRA daily `CNMSshvol` files report, per symbol per day, the **short-SALE volume** (shares
sold short that day on FINRA-reported venues) as a fraction of total reported volume.
This is a **flow / daily-pressure proxy**, NOT short interest (which is bi-monthly stock of
open short positions). The core feature is:

    SVR_t = ShortVolume_t / TotalVolume_t      (short-volume ratio, per symbol per day)

Typical SVR for liquid ETFs sits ~0.40–0.55 (a lot of "short" volume is bona-fide market-maker
hedging, not directional bearish bets) — so the LEVEL is not interpretable in isolation; we use
a **trailing z-score / percentile** of SVR to define "extreme".

## Pre-registered hypotheses (BOTH tested, no cherry-picking the sign)
- **H1 (contrarian / capitulation):** an extreme-HIGH SVR (z or pct of SVR over trailing window)
  = short-sale over-pressure / capitulation → next-few-days mean-reversion UP.
  Rule: go LONG the index when SVR is extreme-high; else cash.
- **H2 (informed-flow / momentum):** elevated SVR PREDICTS weakness → go FLAT/cash when SVR high,
  long otherwise. (Exact opposite sign of H1.)

Tested as a LONG/FLAT timing overlay on **SPY** and (separately) **QQQ**. Harness can't short, so
"avoid" = sit in cash (0% return on flat days), never short.

## Pre-registered timing / anti-lookahead assumption
FINRA publishes day-T's file AFTER market close on day T (next-morning availability is the safe
assumption). Therefore a signal computed from day-T short-vol can only be ACTED ON at day-T+1
open or later. Implementation: signal from data through close of day T → position held over the
day-(T+1) bar return. Concretely, since the harness fills at close and we use adjclose-to-adjclose
daily returns, the signal at day T (using SVR_t and its trailing window, all ≤ T) sets the
position EARNED over the **T+1** return. I.e. `position[t] applies to return[t+1]` — a strict
1-day lag, no same-day peeking. (This is conservative: even if some traders see the file pre-open
T+1, we never use it to capture the T→T+1 move from T's close; we shift one full bar.)

## Pre-registered knob sweep (report the WHOLE surface, flag knife-edge vs plateau)
- Lookback window for z/percentile: {21, 42, 63, 126, 252} trading days.
- Threshold: z ∈ {+0.5, +1.0, +1.5, +2.0} (and percentile equivalents ~70/80/90/95).
- Holding horizon: {1, 3, 5, 10} days held after a trigger (signal "latches" for H days).
- Both H1 and H2 directions.

## Pre-registered benchmark + metrics
- Benchmark: SPY (resp. QQQ) **buy-and-hold** over the SAME window, **on the path actually
  traded**, net of costs. Cost model: repo `CostModel.alpaca_stocks()` = 2 bps one-way
  (≈4 bps round-trip), the repo's standard liquid-ETF convention.
- Metrics, strat vs benchmark: RAW total return, CAGR, Sharpe (annualized √252, on daily
  strategy returns net of cost), maxDD, # round-trips. Reported for FULL window AND an OOS
  split (train 2019–2022 / test 2023–2026) plus a walk-forward sanity check.
- Data span: 2019-01-02 → present (~2026-06). Caveat: NO 2008 GFC (FINRA archive starts 2019);
  covers 2020 COVID crash + 2022 bear. Note this depth limit prominently.

## Pre-registered orthogonality check
Correlate the SVR signal (the raw SVR and its z) to (a) SPY trailing return and (b) SPY trailing
realized vol. If |corr| is high, the "edge" is just a price/vol relabel (every prior orthogonal
reject at this bench died as a secret vol relabel) → discount accordingly. Report the numbers.

## Pre-registered verdict rule
Primary bar (per current mission): does the strategy BEAT SPY on RAW RETURN **out-of-sample**?
- If best honest OOS config does NOT beat SPY raw return → **CLOSE the lane**, report the killer
  number (the OOS raw-return gap + Sharpe), do not manufacture a winner.
- If it DOES beat OOS AND isn't a knife-edge AND isn't a pure vol relabel → **PROMISING**, name
  the exact next honest step (more depth, paper clock).
- A clean documented negative is a real result and closes the lane.
