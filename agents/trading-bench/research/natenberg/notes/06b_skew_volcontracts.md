# Natenberg Batch 6B — Volatility Skews (ch24) + Volatility Contracts (ch25)

Source: `research/natenberg/batches/06b_skew_volcontracts.txt` (read end-to-end: ch24, ch25, "A Final Thought", glossary, appendix B math, index). Paper-quant study notes. No trades, no scheduling.

---

## Chapter 24 — Volatility Skews

### The core fact: implied vol varies by strike (smile / skew)
In a "perfect Black-Scholes world," underlying prices at expiration are lognormally distributed, and **every option with the same expiration should have the same implied volatility**. They don't. IV plotted against strike is not flat — it's a curve. That curve is the **volatility skew** (a.k.a. **volatility smile** — Natenberg's glossary treats the two as synonyms). The mere existence of the skew tells you the market is pricing a **non-lognormal** terminal distribution.

Two market archetypes:
- **Investment skew** (stock indexes, e.g. FTSE 100, S&P 500): lower exercise prices carry significantly *higher* IV than higher exercise prices. Steeply tilted down-to-the-right. Driven by demand for downside puts ("crash-o-phobia") + a real distribution with a **fatter left tail** than lognormal.
- **Demand / commodity skew** (wheat, energy, ags): higher exercise prices somewhat more inflated; more curvature, and skews vary more across expiration months (seasonality, short-term supply/demand). Up-side inflated because these markets get *more* volatile when price *rises*.

### Leading explanations for why the skew exists
1. **Demand for downside protection / crash-o-phobia** — hedgers buy OTM puts for insurance, bidding up their IV regardless of "fair" realized-vol pricing. (ch25 reinforces this: in falling markets *more hedgers* enter and pay up "without regard to considerations of realized volatility… driven by fear." This is why VIX is the "fear index.")
2. **The true distribution is not lognormal** — equity index returns have a longer left tail (negative skewness) and fatter tails generally (positive kurtosis) than the lognormal assumed by Black-Scholes. Options price in that real shape.
3. **Supply/demand imbalances** at specific strikes — especially in commodities and across expirations.

### Skewness vs kurtosis (the two shape parameters)
- **Skewness = the tilt** of the skew: how much low-strike IV differs from high-strike IV.
  - Negative skewness → longer left tail → greater odds of big down moves → demand for low strikes → low strikes inflated (the equity-index case).
  - Positive skewness → longer right tail → big up moves more likely → high strikes inflated.
- **Kurtosis = the curvature** of the skew: how much *both* wings are inflated vs the ATM IV.
  - Positive kurtosis = fat tails = greater odds of large moves either direction → both OTM wings bid up. **All exchange-traded markets exhibit positive kurtosis** (Natenberg ignores negative-kurtosis skews).

Natenberg's simple parametric skew model: a second-degree polynomial
> **y = a + b·x + c·x²**, where x = strike in standard deviations, y = IV at that strike.
- **a** = base vol (≈ ATM IV); raise/lower as overall IV moves.
- **b** = skewness (tilt); sign depends on whether high or low strikes are inflated.
- **c** = kurtosis (curvature); ~always positive for exchange-traded markets.
The skew enters the pricing model **as a formula, not a single number** (see Fig 24-11). ATM strike is the pivot: an exactly-ATM option has skewness & kurtosis sensitivity of 0.

Benchmarks practitioners use:
- **Skewness measure:** difference between IV of the **−25Δ put and the +25Δ call** (these ±25Δ options are most sensitive to a change in the slope).
- **Kurtosis:** no clean benchmark, but **±5Δ** options tend to be most sensitive to curvature changes.

### "Climbing the skew" (an illogical-model gotcha)
In an investment skew, as spot rises an OTM put moves *further* OTM → it's now more SDs away → in an investment skew its IV *rises*. If the skew is steep enough, lowering overall vol can paradoxically *raise* a put's theoretical value — which is illogical (all option values should fall when you cut vol). Skew models need guard-rails against generating such illogical values.

### Sticky-strike vs sticky-delta (sticky-moneyness) — HOW THE SKEW MOVES WITH SPOT
This is the practically crucial regime question. The chapter frames it via how the skew is anchored when spot moves (Fig 24-4 "floating skew"):

- **STICKY-STRIKE:** the IV attached to each *fixed strike* stays put as spot moves. The skew curve is pinned to the strike axis. Implication: when spot moves, a *given option's* IV doesn't change just because spot moved — but the ATM IV *does* change (because "ATM" is now a different strike on a fixed curve). Tends to describe quiet/range-bound regimes.
- **STICKY-DELTA / STICKY-MONEYNESS (the "floating skew"):** the skew is anchored to **moneyness / delta**, so the whole curve **shifts right/left with spot**. A given *strike's* IV changes as spot moves (the strike's moneyness changed), while the IV at a *fixed delta/moneyness* (e.g. the 25Δ put, or the ATM) stays roughly constant. Natenberg: as the skew shifts, "the volatility at some exercise prices will rise, while the volatility at other exercise prices will fall." This is the regime that creates **skew/adjusted ("skewed") deltas**.

**Worked skewed-delta example (sticky-delta / floating investment skew):** OTM put, raw delta −20, vega 0.10. Spot rises 1.00. Naively expect option value −0.20. But as the put goes further OTM in an investment skew, its IV *rises* (climbing the skew) — say +0.5 vol pts → value gain 0.5 × 0.10 = +0.05. Net change ≈ −0.15 → the **skewed/adjusted delta is −15, not −20.** Including a skew model changes *every* Greek (Δ, Γ, Θ, vega) and complicates risk management. Natenberg's pragmatic advice: many traders use the skew model for *theoretical values* but a plain model for the *Greeks*; large books need accurate skewed sensitivities (financial engineers build these).

**Real-world delta of a "delta-neutral" straddle depends on regime:** an ATM straddle is delta-neutral in theory, but in an *equity index* (vol rises when market falls) the long straddle is effectively **delta-negative** (you prefer down moves → higher vol). In a *commodity* (vol rises when price rises) the long straddle is effectively **delta-positive**. "In neither case is the position truly delta neutral."

### Volatility surface
Combine the **term structure** (IV across expirations) with the **skew** (IV across strikes) → a **volatility surface** (Figs 24-12/13). More strikes × expirations = more accurate surface.

### How skew is traded (skew as a position)
- **Risk reversal** = the canonical skew trade. Buy one wing / sell the other (typically **+25Δ call vs −25Δ put**, the most slope-sensitive strikes), then neutralize the residual directional delta with the underlying. Example given:
  - +10 June 95 puts (−25Δ), −10 June 105 calls (+25Δ), +5 underlying. (or a December −15Δ/+15Δ version.)
  - Calls/puts more commonly chosen with **equal vega** (not equal delta) so the RR is **vega-neutral at inception** and reacts mainly to slope, not overall IV. A vega-neutral RR *tends* to be gamma-neutral too (not guaranteed).
  - Investment skew steeper-expected → buy low strikes, sell high strikes; flatter-expected → reverse. (Demand skew mirrored.)
- **Kurtosis trade** = buy/sell **strangles** (both OTM wings). Buy kurtosis → long strangle; sell kurtosis → short strangle. Strangles carry big vega, so to isolate kurtosis you offset vega with **ATM straddles** (ATM is kurtosis-neutral). When the strangle has exactly half the vega of the straddle, vega-neutral = **2 strangles : 1 straddle** = a **dragonfly**.
- **Cross-expiration skew/kurtosis trades:** if two months' skews are mispriced *relative to each other*, take opposing skew positions per month → effectively buying put calendars / selling call calendars (Fig 24-16). Choose ~equal-vega calendars to stay vega-neutral; hedge residual delta. If you *also* have an IV-term-structure view, pick the calendar side where skew and IV reinforce (don't pick the side where they offset). Same logic for kurtosis across months (buy June strangles / sell March strangles, Fig 24-17).

### Implied distributions from butterfly prices (the bridge to ch25/VIX)
A butterfly (buy 95C, −2×100C, buy 105C) pays 0 outside the wings, max = wing-width at the body. **Buy every adjacent butterfly across all strikes → the strip is always worth exactly the strike increment (e.g. 5.00), regardless of terminal price.** Therefore the sum of all butterfly prices = that increment. Consequently:
> **Probability of the underlying finishing at a given strike ≈ (that butterfly's price) / (total of all butterfly prices).**
e.g. 75/80/85 fly priced 0.15, total 5.00 → P(80) = 0.15/5.00 = 3%. Shrink the increment toward 0 → a **continuous implied (risk-neutral) probability distribution** (Figs 24-19/20). For the FTSE 100, the market-implied distribution vs lognormal showed: greater prob of small up moves & of *large down* moves; smaller prob of intermediate down moves & of large up moves — the classic equity-index left-skew. **(verify: the butterfly→probability identity is the risk-neutral / state-price density; mapping it to real-world probabilities requires a risk-premium adjustment Natenberg glosses over. Conceptually it's the second derivative ∂²C/∂K² of call price wrt strike — Breeden-Litzenberger.)**

### Ch24 — what a quant should remember
- A non-flat IV-by-strike curve is the market pricing a **non-lognormal terminal density**: equity indexes = left-skewed + fat-tailed. Skew is *information*, not just a quirk.
- **Skewness = tilt (slope), kurtosis = curvature.** Model them separately (b and c). ±25Δ = slope-sensitive; ±5Δ = curvature-sensitive.
- **The sticky-strike vs sticky-delta regime determines your real delta.** Sticky-delta ("floating skew") generates skewed deltas; a model that ignores skew will mis-hedge directionally. Know which regime your market is in before trusting a Greek.
- **Risk reversal = tradable skew; strangle/dragonfly = tradable kurtosis.** Equal-vega construction isolates the shape you care about from overall IV.
- Butterfly prices ≈ a (risk-neutral) probability distribution; the smooth limit is the implied density — this is *exactly* the machinery VIX/variance swaps generalize.

---

## Chapter 25 — Volatility Contracts

### Why these contracts exist
Pre-options, no clean way to trade vol. Post-options, you *could* capture a vol mispricing by buying/selling options and **dynamically delta-hedging** (ch8) — but in practice that's noisy and costly:
- **Path dependence**: the *order* of price changes affects a dynamic-hedge P&L.
- **Gaps** break the continuous-rehedging assumption.
- Returns aren't truly normal.
- Rehedging bleeds the **bid-ask spread + fees** each adjustment.
- **Worst structural flaw:** vega exposure is *not constant* — vega is highest ATM and decays as the option moves ITM/OTM, so your vol exposure drifts as spot moves.

So practitioners built **volatility contracts** whose payoff at expiration depends only on a clean vol calc, no dynamic hedging required. Two families:
- **Realized-volatility contracts** → settle on realized vol of the underlying over a window.
- **Implied-volatility contracts** → settle on implied vol (e.g. VIX) on a date.

### Realized-vol contracts = variance swaps
Expiration value = annualized stdev of log returns over the contract's life. With 252 trading days:
> realized vol = sqrt( 252 · Σ_{i=1..n} [ ln(x_i) ]² / n ),  where x_i = p_i / p_{i−1} (today's settle / yesterday's settle).

Two conventions baked in:
- **Population stdev (÷ n, not n−1):** the expiration value is the *true* realized vol over the period, not an estimate.
- **Zero mean assumed:** uses ln(x_i), not ln(x_i) − μ → the calc is independent of price trend.

P&L: `notional_per_vol_point × (realized_vol − strike_vol)`. e.g. struck at 20, $1,000/pt, realized 23.75 → +$3,750.

**But most "vol" contracts actually settle in VARIANCE, not vol** → hence **variance swaps**:
> **variance = volatility²**, volatility = √variance.

Two reasons variance is the settlement unit:
1. **Variance replicates cleanly with a static option strip; volatility does not** (the central ch25 result — see below).
2. **Variance is additive in time** (proportional to time). For successive windows t1, t2 with variances σ1², σ2²:
   > combined variance = (t1·σ1² + t2·σ2²) / (t1 + t2).
   So variance contracts stitch across consecutive (even unequal) periods. Worked: 2-mo vol 25 then 1-mo vol 22 → 3-mo variance = (2/12·625 + 1/12·484)/(3/12) = 578.

**Variance-point valuation** (quoted in vol pts w/ notional vega, settled in variance pts), by convention:
> **Value per variance point = vega_notional / (2 × volatility_price).**
e.g. pay 20 for $10,000 vega notional → $10,000/(2·20) = **$250/variance pt**.
- realized 19 → $250·(19²−20²) = $250·(361−400) = **−$9,750**.
- realized 23 → $250·(23²−20²) = **+$32,250**.
- realized 50 → $250·(2,500−400) = **+$525,000** (seller's symmetric loss).

**Convexity / caps:** because payoff is in *variance* (vol²), a single dramatic move makes settlement escalate non-linearly — variance swaps are **long convexity in vol** (buyer wins big on a tail event). Sellers often demand a **cap** (e.g. vol cap 40 = variance cap 1,600). Caps are common on **single-stock** variance (idiosyncratic gap risk) and rarer on **broad-index** variance (one component can't blow up the whole index). Variance swaps are mostly **OTC** → counterparty risk matters.

### Implied-vol contracts: VIX
VIX = CBOE's theoretical **30-day implied volatility**. History: launched 1993 from OEX options; switched to **SPX options in 2003**; methodology overhauled 2003 to the model-free strip method (from a 1999 Goldman Sachs paper, Demeterfi-Derman-Kamal-Zou, "More than You Ever Wanted to Know about Volatility Swaps").

**Old VIX (pre-2003):** averaged call+put IVs at the two strikes bracketing ATM, weighted by distance to spot, then interpolated the two near expirations to 30 days. Two fatal objections for a *tradable* product: (1) it required a **pricing model** (which model? which inputs? OEX is American) → disputes over settlement value; (2) it used **only ATM** options, ignoring the skew the market cared about.

**New VIX = model-free implied variance from an option strip.** The motivating question (Goldman): can you build an option position that captures the underlying's true vol under *all* vol scenarios? Steps in the reasoning:
- One option's vega isn't constant (decays off-ATM).
- Buying *one* option at every strip strike still isn't constant-vega: ATM options at higher strikes have *more* vega than at lower strikes → total vega slopes up with spot.
- **Fix: weight each strike inversely to the square of the strike → buy 1/X² of each option** (X = strike). That produces a **constant variance exposure** (Fig 25-3). ⇐ THE KEY WEIGHTING.

So **VIX value ≈ cost of a 1/K²-weighted strip of OTM options**, turned into a vol number. Mechanics (no pricing model needed — only option prices + one interest rate):
1. Uses only **time value** → only **OTM options** (vs the forward) enter; ITM intrinsic is excluded.
2. **Forward** derived via **put-call parity** at the nearest-to-ATM strike.
3. Each option valued at **mid (avg of bid/ask)**.
4. Stop adding strikes once **two consecutive zero-bid** strikes appear (truncates the wings).
5. Each option's contribution is **weighted by the spacing between adjacent strikes (ΔK)** as well as 1/K² (because only finitely many strikes exist).
6. Two expirations bracketing 30 days are each computed and **weighted to 30 days**.
Interest input = risk-free (T-bill nearest the expiration). Settlement uses **actual opening trade prices** (special opening rotation) on expiration Wednesday — can cause jumps if everything prints at bid (low) or ask (high).

> **Replication intuition (ties ch24→ch25):** a variance swap ≈ a static, **1/K²-weighted strip of OTM options** plus a dynamic delta hedge that, because the weighting makes the strip's gamma deliver a *constant* dollar-gamma per unit variance, captures realized variance independent of path. Variance (not vol) is what this strip replicates *linearly/statically*; vol needs √, which is non-linear, so a fixed strip can't pin vol exposure (see table below). **(verify the exact continuous formula:** the textbook stays at the 1/K² intuition; the standard closed form is
> Var_swap_fair = (2/T)·[ ∫₀^F P(K)/K² dK + ∫_F^∞ C(K)/K² dK ] − (1/T)·(F/K₀ − 1)²  (the −(F/K₀−1)² is the discretization/forward-correction term that shows up in the CBOE white paper). Get this from the CBOE VIX white paper before using numerically.**)

**Why variance replicates but volatility doesn't (the table):** a 1/K² strip gives *constant variance* exposure but *not* constant vol exposure, because vol = √variance is non-linear. Natenberg's comparison (struck variance 400 = vol 20, $250/var pt vs $10,000/vol pt):

| Realized variance | Variance P&L | Realized vol | Volatility P&L |
|---|---|---|---|
| 250 | −$37,500 | 15.81 | −$41,900 |
| 300 | −$25,000 | 17.32 | −$26,800 |
| 350 | −$12,500 | 18.71 | −$12,900 |
| **400** | **0** | **20** | **0** |
| 450 | +$12,500 | 21.21 | +$12,100 |
| 500 | +$25,000 | 22.36 | +$23,600 |
| 550 | +$37,500 | 23.45 | +$34,500 |

They match only exactly at strike; they diverge as realized moves away. The static strip pins *variance* P&L, not *vol* P&L → so contracts settle in **variance points** to make hedging exact. (If you could replicate a long-vol leg at vol 19 against a short-vol at vol 20, you'd lock a 39-variance-pt arb = 39·$250 = $9,750. The CBOE VIX method is literally "turn the cost of the strip into an implied vol," analogous to inverting an option price into an IV — but for a constant-variance position.)

### VIX empirical character (important for signal use)
- **VIX is strongly *negatively* correlated with the S&P 500.** 2003–2012: corr of % changes = **−0.7444**; best-fit slope ≈ **% change in VIX is ~5.7× the % change in SPX, opposite sign.** Index down → VIX up.
- **VIX has essentially NO predictive power for *future realized* vol.** Change-in-VIX vs change-in-realized-vol (next 30d vs prior 30d) corr ≈ **+0.1561** (tiny, "probably insignificant"). Natenberg's reading: VIX is driven more by **demand for crash protection / fear** than by an unbiased forecast of realized vol → "**fear index**."
- **Falling markets *are* moderately more volatile than rising ones:** 30-day SPX move vs 30-day realized vol corr ≈ **−0.3895** (more high-vol points on the down side). Moderate, not strong.
- **VIX mean-reverts** (low → likely to rise, high → likely to fall) and lives in a **bounded range** (you basically never see index IV <5% or >100% for long).

### VIX is NOT directly tradable → derivatives diverge from the index
The index components/weights change continuously as options move ITM/OTM, so you can't cheaply replicate VIX like a stock index. You trade it via **VIX futures (2004, $1,000/pt)** and **VIX options (2006, European, $100/pt)** — and these famously *disappoint* newcomers:
- **VIX futures have a term structure**, usually **contango** (longer = higher), sometimes **backwardation** (crisis, e.g. flipped in late 2008). In contango with no change, a future **rolls down the curve and bleeds value** as time passes.
- **A VIX future almost never moves as much as the index** — it prices *expected* IV at *its* maturity, not spot IV. Spot VIX can jump 4.4 pts while the front future moves 2.0; near expiry the future tracks the index more tightly (must converge at settlement).
- Futures spreads: with a curved term structure the short-dated leg moves faster. Expect contango→flatter/backward to favor **selling the spread** (sell long / buy short); backward→contango to favor **buying the spread** (buy long / sell short).
- **VIX options** must be hedged with VIX *futures* (since the index itself isn't tradable), and **futures are less volatile than the index** → VIX options carry **lower IV than the index's own historical vol would suggest**; hedge expectations should track the *future's* vol, not the index's.
- **VIX's own skew is a "half-frown,"** not a smile: low-strike IV drops off fast; high-strike IV rises then flattens. Its implied distribution (via the butterfly method) has a **restricted left tail** (almost no chance VIX < 10 at expiry), a somewhat restricted right tail vs lognormal, but a hint of a **fat far-right tail** (small chance of a vol explosion). This shape reflects VIX's bounded, mean-reverting nature.

### Replicating VIX in practice (why it's hard, briefly)
Theoretically: buy the long-dated strip, sell the short-dated strip; the two strips' gammas roughly cancel → **total gamma ≈ 0 → no delta rehedging needed**; carry to expiration. In practice it breaks because: the two strips **don't expire on the same day** (mismatch risk), out-of-the-money options drift **into the money** and must be converted back to OTM via the underlying (synthetics) — but **SPX has no single tradable underlying** (it's 500 stocks; use SPX futures or combos as a proxy). Net: replication is real in theory but impractical for most traders.

### Volatility-contract applications
- **Speculate on vol** (the main use): variance swap = bet on *realized* vol; VIX futures = bet on *implied* vol; VIX options = bet on *VIX's* vol.
- **Hedge a vol book:** a gamma (realized-vol) position → hedge with variance swaps; a vega (implied-vol) position → hedge with VIX contracts.
- **Hedge an equity portfolio:** because SPX↔VIX is inversely correlated, a long-equity manager goes **long VIX** (buy VIX futures/calls, sell VIX puts) so a market drop → VIX rise offsets some equity loss.
- **Indirect/structural vol positions:** an option market-maker profits from higher *volume* (which tracks higher vol) → has an indirect *long* vol position → may sell VIX to hedge. A manager facing periodic **rebalancing costs** (worse when spreads widen in high vol) is indirectly *short* vol → buys VIX. **Covered-call** writers want the market to sit still → effectively *short* vol → hedge by buying VIX futures.

### "A Final Thought" (Natenberg's closer)
A model forces many uncertain decisions and you'll be wrong about some inputs — but disciplined model users win long-run. Have faith in the model, **not blind faith**: when it returns values that defy common sense, adjust it or set it aside. Trading is art + science; the model should be **servant, not master**.

### Ch25 — what a quant should remember
- **Variance swap pays (realized_variance − strike_variance); variance, not vol, is the natural unit** because (a) it's **time-additive** and (b) it **replicates statically** with a **1/K²-weighted OTM option strip**. Vol = √variance is non-linear → no fixed strip pins vol exposure → settle in variance points.
- **The 1/K² weighting is THE result of the chapter** — memorize it. It's what turns a strip into constant-dollar-variance exposure and is the backbone of model-free implied variance (VIX). The continuous fair-variance integral with 1/K² weighting + a forward-correction term is the formal version (verify against CBOE white paper).
- **VIX = model-free 30-day implied variance from a strip of OTM SPX options, mid-priced, ΔK-weighted, forward from put-call parity.** No pricing model in the loop → that's the whole point (settlement is unambiguous).
- **Variance swaps are long vol-convexity** → caps on single-name; **VIX is the "fear index"** (driven by hedging demand, ~no power to forecast realized vol, corr +0.16).
- **VIX derivatives ≠ VIX**: term structure (usually contango → roll-down decay), futures move *less* than the index, options hedged with the *less-volatile* futures → lower IV than the index's vol. Never assume the future moves 1:1 with the index.

---

## Batch 6B — top lessons
1. **A non-flat IV curve = the market's non-lognormal density.** Equity indexes: left tail fat (crash-o-phobia), both tails fat (positive kurtosis). The skew is a *signal*, encoding the risk-neutral distribution.
2. **Decompose shape into slope (skewness, ±25Δ, the risk-reversal) and curvature (kurtosis, ±5Δ, the strangle/dragonfly).** These are two orthogonal axes you can read and trade separately.
3. **Sticky-strike vs sticky-delta is the regime that sets your true delta.** Sticky-delta ("floating skew") generates skewed/adjusted deltas — a skew-blind model mis-hedges direction. Identify the regime first.
4. **Variance is the clean unit: time-additive AND statically replicable via a 1/K²-weighted OTM option strip.** Vol = √variance is non-linear, so no fixed strip pins vol exposure. This is *the* reason variance swaps (and VIX) settle in variance.
5. **VIX = cost of a 1/K²-weighted OTM SPX strip, expressed as 30-day implied vol — model-free.** Butterfly prices → implied density is the same machinery generalized.
6. **VIX ≈ priced fear, not a realized-vol forecast** (corr to future realized ≈ +0.16; corr to SPX % change ≈ −0.74). Mean-reverting, bounded, half-frown skew.
7. **A vol *index* is not a vol *instrument*.** VIX futures/options carry term structure, roll decay, and damped sensitivity — the index isn't replicable, so derivatives detach from it. Critical caveat for any VIX-derived signal or any attempt to "trade the level."

---

## Skew / vol-surface signals for OUR project

Context: we hunt tradable signals on **free data**. This chapter pair says the IV *surface* (skew × term structure) and the model-free *variance* construction are rich, and several CBOE indices expose slices of it for free. Map:

### CBOE SKEW index — the slope/left-tail gauge (free, daily)
- SKEW is CBOE's published measure of **S&P 500 risk-neutral skewness / left-tail fatness** derived from OTM SPX option prices — i.e. it packages exactly the ch24 "skewness (b)" + left-tail-of-the-implied-distribution idea into one daily number (≈100 = lognormal/no skew; higher = steeper crash-protection bid / fatter left tail). **(verify: SKEW = 100 − 10·(risk-neutral skewness) per CBOE's definition; confirm the exact transform and that higher SKEW = more negative skew = fatter left tail before using directionally.)**
- **Signal value:** SKEW is the steepness of the put-side investment skew distilled to a scalar. Rising SKEW = market paying up for crash insurance = the −25Δ-put-vs-call spread widening. It is **largely orthogonal to VIX level**: VIX is roughly the ATM/overall variance (the "a" term), SKEW is the tilt ("b" term). You can have low VIX + high SKEW (complacent index, expensive tails). **Pair them** — VIX (level) × SKEW (tilt) is a 2-factor read on the surface, not one redundant factor.
- Caveats from the text: skew is driven by **hedging demand/fear, not a realized-vol forecast** — so SKEW is better read as *positioning/insurance demand* than as a crash predictor. Backtest accordingly (it may mean-revert; extreme SKEW ≠ imminent crash).

### VVIX — vol-of-vol / curvature & tail gauge (free, daily)
- VVIX is the **VIX of VIX** = implied vol of VIX options = the model-free implied vol of the VIX itself. It's the ch25 observation that *VIX is highly volatile* (50-day vol of VIX reached ~200%) turned into a tradable index.
- **Signal value:** VVIX proxies **demand for tail/convexity hedges** and the **kurtosis of the vol distribution** — the curvature axis, distinct from both VIX (level) and SKEW (equity-tail tilt). Spikes in VVIX without VIX spikes can flag stress building in the vol-hedging complex. Treat as a **third near-orthogonal factor**: {VIX = level, SKEW = equity left-tail tilt, VVIX = vol-of-vol/convexity}.
- Caveat: VVIX inherits the "VIX derivatives ≠ VIX" damping (VIX options are hedged with less-volatile VIX futures), so VVIX reflects *futures-anchored* expectations, not pure spot-index vol.

### IV term-structure slope — the contango/backwardation regime flag (free)
- ch20/ch25: SPX implied-vol term structure is usually **contango (upward)**, flipping to **backwardation in stress** (late-2008 example). VIX futures reflect this and **roll down in contango**.
- **Free proxies:** VIX (30d) vs VIX3M/VXV (3-month) ratio, or VIX vs front-vs-second **VIX futures** spread (CBOE publishes settlements). **VIX/VIX3M < 1 = contango (calm); > 1 = backwardation (stress).**
- **Signal value:** the slope is a **regime indicator** (risk-on vs risk-off) and a **carry signal** — persistent contango is the structural tailwind behind short-vol/roll-down strategies; a flip toward backwardation is an early stress flag. This is **orthogonal to the *level*** of vol: you can be high-VIX-and-still-contango or moderate-VIX-flipping-backward. Variance is time-additive (ch25), so a clean way to read the slope is **forward variance** between two tenors (σ_fwd² = (t₂σ₂² − t₁σ₁²)/(t₂−t₁)) rather than raw vol differences — do the math in variance space.
- Caveat: term-structure carry (roll-down) is *not* a realized-vol edge — it's a risk premium that pays until it doesn't (the 2008/Volmageddon tail). Size for the convex blow-up.

### Put-call skew (−25Δ put IV minus +25Δ call IV) — DIY slope on single names/ETFs (free-ish)
- ch24's own benchmark for skewness is literally **IV(−25Δ put) − IV(+25Δ call)**. Where we have an option chain (e.g. SPY/QQQ/IWM and liquid single names via free/cheap chains), we can compute this directly instead of relying only on the index.
- **Signal value:** a **per-name / per-ETF risk-reversal level** — relative richness of downside vs upside protection. Cross-sectional dispersion (which names have abnormally steep put skew) can be a positioning/sentiment signal; changes in skew (steepening/flattening) are tradable views even when level (ATM IV) is flat. Construct **equal-vega** when reasoning about isolating slope (per the chapter).
- Caveat: requires clean OTM mid-quotes and a consistent delta/moneyness definition; sticky-strike vs sticky-delta drift contaminates naive day-over-day strike-anchored comparisons — **anchor to delta/moneyness, not fixed strikes**, exactly as the floating-skew discussion warns.

### How these compose into orthogonal factors (the takeaway)
Think of the free vol-surface signals as roughly independent coordinates of the same surface:
- **Level** → VIX (≈ ATM/overall implied variance; the "a").
- **Equity-tail tilt** → CBOE SKEW and/or DIY −25Δ put-minus-call risk-reversal (the "b"/skewness).
- **Curvature / vol-of-vol** → VVIX (≈ kurtosis/convexity demand; the "c").
- **Term-structure slope / regime+carry** → VIX vs VIX3M (or VIX-futures spread); read in **variance/forward-variance** space.

Because the chapter shows these capture *different* moments of the implied distribution (mean-ish level, skewness, kurtosis) and *different* axes (strike vs expiration), combining them should add signal rather than collinearity — the explicit goal of an orthogonal-signal hunt. **Hard caveat threaded through both chapters:** every one of these is dominated by **hedging demand / risk premia**, not by unbiased forecasts of realized vol or of crashes (VIX→realized corr ≈ +0.16). So treat them as **positioning / risk-appetite / carry** signals and validate empirically; don't assume "high SKEW ⇒ crash soon" or "high VIX ⇒ realized will spike." And whenever you trade a level, remember the index is not the instrument (roll, damping, term structure).
