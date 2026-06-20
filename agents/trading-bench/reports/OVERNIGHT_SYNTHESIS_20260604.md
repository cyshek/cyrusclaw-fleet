# Overnight Research Synthesis — 2026-06-04

**Author:** Tessera (committer)
**Scope:** consolidates the overnight research session (10 research lanes + 1 candidate validation + 2 harness builds) into a single honest finding and frames the open decisions for Cyrus.
**Status of every lane below:** verified on disk by the committer (report exists, protected-file md5s unchanged, numbers read from the report not from memory). Zero promotions. Zero protected-file edits. Paper/backtest only. Zero spend.

---

## 1. The one-sentence finding

On the data surface available to us (Alpaca free IEX, daily + intraday, 2020-12 → 2026, single-name and simple-ETF-basket universes), **no strategy archetype tested carries a risk-adjusted edge that clears the front-door gate (FP-continuous-span Sharpe ≥ 1.0), and the wall they all hit (~0.5 Sharpe) is a _signal_ ceiling, not a _cost_ ceiling.**

This is an honest interim "we have not found graduating edge yet on this surface," not "edge is impossible." It is the expected outcome of a rigorous cull, and it is the correct thing to report rather than crowning a 0.5 as if it were a 1.0.

---

## 2. Why "signal ceiling, not cost ceiling" — the load-bearing claim

Earlier in the night I framed the ~0.5 wall as a *cost* ceiling (the intraday lane's "execution cost pins us near zero"). **That framing was wrong and I corrected it.** The disproof is the low-turnover dual-momentum lane:

- It trades **~24 times in ~5 years** → realistic cost is a rounding error (~0.13% of notional, total).
- With cost removed from the equation, the naked signal **still tops out at 0.524** (and that's a `top_k=1` knife-edge; the genuinely diversified region is ~0.39).

So: a **cost-free** signal (low-turnover momentum) and a **cost-dominated** signal (intraday microstructure) **both** land at ~0.5. Cost is therefore not the binding constraint. The binding constraint is the **information content of price/vol history itself** on this universe and sample. That is the central, corrected finding of the night.

A second independent confirmation: the notional re-run proved the cost model is pure-bps with fractional shares → **net Sharpe is scale-invariant**, so neither a bigger book nor a "cleaner fill" assumption recovers any rejected lane.

---

## 3. The evidence — every lane, honest headline

| Lane | Input class | Best honest FP-cont Sharpe | Verdict | Disqualifier (why not 1.0) |
|---|---|---|---|---|
| Notional re-run ($1000) | n/a (scale test) | — | STILL-REJECT all 3 | Sharpe is scale-invariant; notional/data upgrade recovers nothing |
| PEAD (mid/large, liquid) | earnings surprise | **0.926** | REJECT (near-miss) | < 1.0 front door **and** never beats BH-SPX on any cell (+13% vs +39% same path) |
| Leveraged-trend (SOXL) | 3x-ETF trend | screen ~0.97 | → sent to validation | (see next row) |
| SOXL validation | 3x-ETF trend | **0.973** full-span | FAILS Bar A | needs BH-crutch on 2 regime windows; cap is 1 window |
| Dispersion / implied-corr | xsec dispersion | **0.568** | REJECT | knife-edge; corr gauge was a vol-level relabel (r=0.65) |
| Macro-nowcast | tradeable-ETF macro proxies | **0.501** | REJECT | < BH-SPY bench (0.674); knife-edge; orthogonal but weak |
| Intraday microstructure | 5Min/1Min RTH | ~0.45 (RTH-corrected) | REJECT | no robust edge; confirms ceiling; **also surfaced a harness bug (§5)** |
| Low-turnover dual-momentum | monthly xsec+abs momentum | **0.524** (knife) / 0.39 (diversified) | REJECT | 0 of 36 cells ≥1.0; cost≈0 → **proves signal ceiling** |
| Options skew | options-derived IV/skew | apparent +1.62 → artifact | REJECT + DATA-LIMITED | "win" is disguised bull-beta in a 16-mo single-regime sample; thesis (fear→de-risk) LOSES −0.97 in the only bear window |
| Single-stock xsec (40 names) | published equity factors | mom **0.352** / lowvol **0.295** | REJECT | below passive SPX; the textbook anomaly habitat still underdelivers |
| Market breadth / internals | cross-sectional participation | knife +0.848 → relabel | RELABEL-REJECT | corr +0.56–0.74 to SPY momentum, ~0 forward content (IR +0.13); edge is one-bear-dodge luck |

**Two near-gate exceptions, each with a _non-tuning_ disqualifier** (i.e. not fixable by sliding a parameter):
- **PEAD 0.926** — real ~0.9–1.2 plateau, lookahead-clean, but **structurally earns less than buy-and-hold SPX** (event-sparse, often partly in cash). It is a defensible low-vol sleeve, not an index-beater.
- **SOXL 0.973** — clears the screen but **fails the held-out gate**: it requires the buy-and-hold crutch on 2 regime windows when the gate allows only 1. The gate held; it was not promoted.

Everything else clusters **0.30 – 0.57**, independent of cost, turnover, timeframe, or universe. (Breadth's lone +0.848 cell is the exception that proves the rule: a single-lookback knife whose entire margin over the ~0.45 SPY-trend control is one-bear timing luck, with a noise-level information ratio of +0.13 — caught precisely because the new SPY-relative IR metric (§5.2) surfaced it.)

---

## 4. What the night rules OUT (so we don't redo it)

- **More price/vol transforms on this data are low-EV.** Ten independent angles (vol, dollar, dispersion, macro, intraday, low-turnover momentum, options-as-IV, published xsec factors, single-stock xsec, market breadth) converge on the same ceiling. The marginal price-transform lane is padding the reject pile, not finding edge.
- **Buying SUE/SIP/notional upgrades does NOT help the rejected lanes** — scale-invariance + the two foreclosed data-purchase angles earlier prove the upgrade recovers nothing already rejected.
- **The relabel trap is real and was caught repeatedly:** ATM-IV (r=0.66 to realized vol) and the dispersion corr-gauge (r=0.65) were both the dead vol-level lane in disguise; rejected on that basis, not on Sharpe.

---

## 5. What the night BUILT / FIXED (durable infra wins, no spend)

1. **Notional consistency bug fixed** — 4 files defaulted `notional_usd=100.0`; corrected to 1000.0. Suite green.
**5.2 — SPY-relative gate metric shipped** (`runner/spy_relative.py`) — every walk-forward candidate now auto-emits SPY-relative excess return + tracking-error information ratio. Additive reporting only; not yet a *binding* gate (that's a Cyrus/main decision). IR math independently hand-verified; suite 289→302. This hardens the exact "below passive SPX" bar all 9 rejections leaned on.
3. **Intraday harness bug found + filed P2** — `BARS_PER_YEAR['5Min']=105120` is a 24/7 count; RTH equity is ~19,656/yr, so intraday Sharpe is inflated 2.313×. Direction is *conservative-toward-rejection* now (no false-promote risk), so P2 not P0. **Fix requires editing a PROTECTED file (`backtest.py`) → committer/main-supervised, not an overnight hand-patch.** Until fixed, every intraday report cites the RTH-corrected Sharpe.

---

## 6. The genuinely-orthogonal lead worth a real decision

The one input class that is **measurably orthogonal** to price/vol and might break the ceiling is **options skew** (corr 0.20 to realized vol, unlike ATM-IV's 0.66 relabel). The free-tier data cannot test it honestly — 16 months, one bull regime, no overlap with our equity history, approximate chains. To test skew across **multiple bear regimes** would need a paid IV-surface history (ORATS / CBOE DataShop back to ~2007, or Alpaca Algo Trader Plus). **This is the night's single strongest "spend money" case**, and unlike the earlier foreclosed SIP idea, it buys a *genuinely different signal*, not more of the same.

---

## 7. Decisions for Cyrus (surfaced, NOT pre-decided — each needs his explicit call)

1. **SOXL 0.973-vs-1.0 boundary.** Accept "gate held, not promoted" as final, or open a deliberate gate-boundary discussion (the only argument for SOXL is a 0.973 that needs a 2nd BH-crutch window). My recommendation: **gate held is correct** — moving the post for a single near-miss is exactly the goalpost-slide the gate exists to prevent.
2. **Buy options-IV-surface history (~$99–few-hundred/mo)** to test the one orthogonal lead (skew) across real bear regimes. This is a real research-dollar decision, not a paper action — needs explicit approval. My read: it's the highest-EV *next* spend if we spend anything, but it is genuinely optional.
3. **Accept "no graduating edge on this surface yet" as the honest interim answer.** This is a legitimate finding, not a failure. The alternative — lowering the 1.0 bar to crown a 0.5 — is the one thing SOUL.md forbids. The honest path is to widen the data (decision 2), not lower the bar.

---

## 8. Bottom line

The tournament did its job: it culled honestly and refused to crown a sub-bar strategy. We end the night with **zero promotions, two well-characterized near-misses with structural (non-tuning) disqualifiers, one orthogonal data-limited lead, and two durable infra hardenings** — and a corrected, evidence-backed understanding that the ceiling we keep hitting is in the *signal*, not the *cost*. The next genuine edge, if it exists on accessible data, most likely lives in a **new input class** (options skew with proper history, or fundamental/alt-data), not in another transform of the price history we already have.
