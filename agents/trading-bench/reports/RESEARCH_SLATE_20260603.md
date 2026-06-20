# Research Slate — Parallel Thesis Roster (2026-06-03)

**Origin:** Cyrus — "why not 10 agents looking into different things to find profitable strategies, now?" Answer (agreed): yes to breadth, *provided* each agent owns a genuinely distinct, falsifiable hypothesis and all feed the ONE shared evaluator (gate + walk-forward + cost model + knife-edge/plateau classifier). 10 agents on the same bet = leverage masquerading as a portfolio (MEMORY.md). 10 agents each running their own eval = 10 ways to fool ourselves. So: distinct theses, shared ruler.

**This is the STARTING roster, not the ceiling.** "Yet" — we don't have 10 distinct theses today; the job is to surface more, not to cap ambition. Grow toward 10 as new falsifiable lanes appear.

**Precondition (mostly met):** shared evaluator must be trustworthy + not the bottleneck. Done recently: sweep harness, √252 Sharpe fix, deployed-capital DD fix, event-driven shared-cash backtester. Remaining funnel gaps logged in BACKLOG (single-name deployment path in walk_forward_xsec; gate-pass clause-(a) folding).

---

## What's already been tried (don't re-run as-is)

| Lane | Best honest FP-cont Sharpe | Verdict | Note |
|---|---|---|---|
| Price xsec (momentum/mean-rev/lowvol, single-stock + cross-asset) | ≤0.80, knife-edges | REJECT (conclusive) | Most-arbitraged signal on Earth. Lane closed. |
| Vol-regime timing (VIXY/realized/implied, binary+proportional) | +0.54 (honest), 0.87 was a mirage | REJECT, tapped out sub-threshold | Closest we've gotten, but R3 killed the 0.87. |
| Credit veto/regime (HYG-LQD) | [−1.56, −0.44] | REJECT (uniform fail) | No equity-timing edge net of cost. |
| Small-cap PEAD (event-driven) | −0.34 | REJECT | Harness built + validated though. |
| Dollar/FX lead-lag (UUP→SPY) | +0.55 | REJECT | Orthogonal but sub-bar. |

Pattern: everything *price-derived* is crowded; the two least-bad lanes (vol-regime +0.54, dollar +0.55) are real-but-sub-1.0. Edge, if it exists, is most likely in **non-price, harder-to-access, or structurally-uncrowded** signals.

---

## STARTING ROSTER — distinct falsifiable theses (each = 1 agent, all → shared gate)

1. **Earnings-drift on a REAL universe (PEAD, mid/large-cap).** Small-cap PEAD rejected, but the harness now exists. Re-aim at a liquid mid/large universe where drift is weaker but tradeable net of cost — falsifiable: does post-8K 42-bar drift clear 1.0 FP-cont on names we can actually fill?

2. **Cross-asset carry / term-structure (not price-trend).** Untested. E.g. VIX term-structure roll (VIXY vs VIXM contango/backwardation as a *carry* signal, not a vol-level timing signal — distinct from the rejected vol-regime lane). Falsifiable plateau test via sweep.

3. **Seasonality / calendar structure.** Turn-of-month, FOMC-drift, pre-holiday, sell-in-May. Cheap to test, genuinely orthogonal to price-momentum, often survives because it's "too dumb to arb." Falsifiable: does any calendar window beat BH-SPY risk-adjusted on the named windows?

4. **Dispersion / correlation regime.** Trade the *spread* between index vol and average single-name vol (implied correlation). Structurally different from directional timing. Needs a multi-name vol harness — flag if infra-blocked before spawning.

5. **Macro-nowcast / rate-of-change on real economic series.** Non-price by construction (claims, surprise indices, liquidity proxies). Highest "uncrowded" potential, highest data-plumbing cost. Falsifiable: does the signal lead SPY enough to time long/flat net of monthly rebalance cost?

6. **Quality/defensive factor timing (not the lowvol barbell).** Distinct from rejected lowvol: time *exposure* to a quality sleeve by macro regime rather than holding it statically. Falsifiable against the static-hold benchmark.

7b. **Leveraged-INSTRUMENT trend (Cyrus's "riskier to beat SPX on RAW return" ask).** TQQQ/SOXL/UPRO trend-following; leverage lives INSIDE the instrument (exposure <= cash, no rail change, NO margin/shorting/derivatives). This is the ONE lane aimed at out-RETURNING SPX rather than diversifying it. MUST report SPX-relative Sharpe + INSTRUMENT-level (not diluted-NAV) MaxDD front and center.

### Grow-to-10 candidates (surface a real hypothesis first, THEN seat)
7. Intraday / overnight microstructure on liquid ETFs (overnight-basket harness exists).
8. Options-implied skew / risk-reversal as a directional signal.
9. Pairs / stat-arb on cointegrated cross-asset pairs.
10. Sentiment / text signal (news/filings tone) — highest plumbing cost, park until a cheaper lane is exhausted.

**SLATE CONSOLIDATION NOTE (2026-06-04):** this file is the single canonical slate. A duplicate `RESEARCH_LANE_SLATE_20260604.md` was deleted; its only unique item (leveraged-instrument trend) folded in as 7b above. The point of lanes 1-6: we have ZERO strategies clearing the gate, and the two least-bad lanes ever found were sub-1.0 Sharpe. Most of these win (if they win) as UNCORRELATED diversifiers that beat SPX on RISK-ADJUSTED terms, not by out-returning it. Only 7b swings for raw return. Both are valid routes to "beat SPX."

**Rule:** an empty seat is not a thesis. Seats 7–10 stay empty until each has a written, falsifiable hypothesis. Better 5 real bets than 10 overlapping ones.

---

## Execution-side agents (Tier 3) — explicitly NOT now

Hiring traders before we have a trade. Gated behind ≥1 strategy with real edge clearing the gate. Revisit when the roster above produces a survivor.

## Spawn discipline

- Concurrency cap ~3–4 in flight; queue the rest (token budget is fine per MEMORY, but the shared gate + my review is the real throughput limit).
- Each agent: isolated scratch dir, NO edits to protected runner/evaluator files, writes a `reports/<LANE>_<ts>.md` with honest verdict, single committer (me) merges.
- Verdict bar is the existing gate — agents have NO promotion authority.
