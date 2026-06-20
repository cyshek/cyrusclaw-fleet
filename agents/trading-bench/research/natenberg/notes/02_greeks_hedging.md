# Natenberg — Batch 2: The Greeks & Dynamic Hedging (Chapters 6–9)

> Study note compiled from an end-to-end read of `02_greeks_hedging.txt` (4,453 lines).
> Source: Sheldon Natenberg, *Option Volatility and Pricing*, 2nd ed.
> Coverage in this batch: **Ch. 6 Volatility** · **Ch. 7 Risk Measurement I (the Greeks)** · **Ch. 8 Dynamic Hedging** · **Ch. 9 Risk Measurement II** (the batch's text cut stops partway through Ch. 9, at the *vanna* figure on p.140 — see "Scope note" below).
>
> **Scope note / honesty flag:** This batch's text covers Delta, Gamma, Theta, Vega, Rho in full (Ch. 7) and re-opens Delta's second-order behavior (vanna, charm) at the start of Ch. 9, but it **ends before** the dedicated Ch. 9 sections on Gamma-behavior, Theta-behavior, Vega-behavior, and **Lambda**. **Lambda is never mentioned anywhere in this batch.** The Lambda section below is therefore sourced from the standard textbook definition and is **explicitly flagged**, not extracted from this file. Everything else is from the text.

---

## Chapter 6 — Volatility

### 6.1 The core idea: volatility = a standard deviation

- A theoretical pricing model needs a description of how the underlying price is likely to be distributed at expiration. Natenberg builds this from a **random walk / Galton board (pegboard)** analogy: many small independent up/down displacements pile up into a **bell-shaped normal distribution**.
- **A normal distribution is fully described by two numbers: the mean and the standard deviation.** The mean locates the distribution; the standard deviation (σ) measures how fast it spreads.
- **Volatility *is* the standard deviation.** "When we input a volatility into a theoretical pricing model, we are actually feeding in a standard deviation. Volatility is just a trader's term for standard deviation." The notation is the Greek sigma σ.
- Probability content of a normal distribution (the numbers to memorize):
  - **±1 σ ≈ 68.3%** (~"two days out of three", ~app. 68%)
  - **±2 σ ≈ 95.4%** (~"19 out of 20")
  - **±3 σ ≈ 99.7%** (~"369 out of 370")

### 6.2 Volatility is annualized — and scales with √time (the most important formula in the chapter)

Like interest rates, **volatility is always quoted as an annualized number.** But unlike interest (which scales *linearly* with time), **volatility scales with the *square root* of time.** The general rule:

```
σ_t = σ_annual × √t        (t expressed in YEARS)
```

To get a standard deviation over a sub-period, multiply annual vol by √(fraction of a year). Natenberg's convenience constants come from the number of trading periods per year:

- **Trading days ≈ 256** (chosen for convenience because √256 = 16 exactly; real exchanges have ~250–260):

```
σ_daily = σ_annual × √(1/256) = σ_annual × (1/16) = σ_annual / 16
```
  → **"To approximate a daily standard deviation, divide the annual volatility by 16."**

- **Trading weeks = 52** (√52 ≈ 7.2):

```
σ_weekly = σ_annual × √(1/52) ≈ σ_annual × (1/7.2) = σ_annual / 7.2
```
  → **"To approximate a weekly standard deviation, divide the annual volatility by 7.2."**

> **Quant note on the 252 vs 256 question (task asked for this explicitly):** Natenberg uses **256** because √256 = 16 is clean. The modern industry-standard convention is **252 trading days**, giving `σ_daily = σ_annual / √252 ≈ σ_annual / 15.87`. The two are interchangeable approximations; 16 is the back-of-envelope value, 15.87 (√252) is the "exact" market-standard divisor. **(verify: use 252 in code unless matching Natenberg's worked examples, which assume 256.)**

**Worked examples from the text (verified):**

- Contract at 100, σ_annual = 20%. One-day 1σ move = 20%/16 = **1.25%** → ±1.25 price points. Expect a move > 1.25 about 1 day in 3; > 2.50 about 1 day in 20.
- Contract at 100, σ_annual = 20%, weekly: 20%/7.2 ≈ **2.78%** → ±2.78 points per week (1σ).
- **$45 stock, σ_annual = 37%:**
  - Daily 1σ: $45 × (37%/16) ≈ **$1.04** → 1σ range $43.96–$46.04; 2σ range $42.92–$47.08.
  - Weekly 1σ: $45 × (37%/7.2) ≈ **$2.31** → 1σ range $42.69–$47.31; 2σ range $40.38–$49.62.
- **Same 68% / 95% probabilities still apply after scaling** — the √time rule preserves the normal-distribution coverage percentages.

### 6.3 Normal vs. Lognormal distributions

The normal-distribution assumption has a **fatal flaw: it is symmetric**, so for any possible upward move it admits an equal downward move — which would allow **negative prices** (e.g., a $50 contract dropping $75 to –$25). Real stocks/commodities can't go negative.

Fix: treat the **percent price changes (rate of return)** as normally distributed, and **compound them continuously**. Key mechanics:

- A rate of return must specify both the rate *and* the compounding interval. More frequent compounding of the same nominal rate raises the effective yield (e.g., +12% nominal → +12.75% continuously compounded). For losses, more frequent compounding *shrinks* the loss (–12% nominal → only –11.31% continuously compounded).
- **Continuous compounding uses the exponential function:** `$1000 × e^0.12 = $1,127.50` and `$1000 × e^(–0.12) = $886.92`.
- Because you can never lose more than 100% of an investment, **continuous compounding bounds the underlying at zero on the downside.** That produces a **lognormal distribution** of prices at expiration.

**Properties of the lognormal distribution (memorize):**
- **Bounded by zero on the downside**, open-ended (→ +∞) on the upside. More realistic than normal.
- **Right-skewed:** the right tail is longer than the left. So a 1σ *up* move is larger in absolute dollars than a 1σ *down* move (e.g., +$127.50 up vs. –$113.08 down for a 12% continuously-compounded rate).
- **Mean sits to the RIGHT of the peak (mode).** For a normal dist, mean = mode = median, all centered. For lognormal, the extra "weight" in the long right tail pulls the mean right of the mode.
- Effect on option values (forward 100, 6 mo, 30% vol): lognormal lowers the value of a downside 90 put (4.37 normal → **4.00 lognormal**) relative to normal because the downside is compressed. **(table in text; call side similarly affected)**
- Black-Scholes is a **continuous-time model** that assumes lognormal prices / continuously-compounded normal returns.

### 6.4 Types of volatility (the taxonomy — important for interpreting historical data)

Natenberg splits volatility into two families:

**Realized volatility** (a property of the *underlying contract*) = the annualized standard deviation of percent price changes. Must specify the **interval** (daily, weekly…) and the **number of observations**. Sub-types:
- **Future (realized) volatility** — the volatility the underlying *will* actually exhibit over the option's life. **This is what every trader wishes he knew**; feed the correct future vol into the model and you have the right "odds." Unknowable in advance.
- **Historical (realized) volatility** — past realized vol, computed from data. The practical starting point: "what has this contract typically done?" If a contract has historically run 10–30%, a guess outside that band needs justification. (Text shows the S&P 500 **250-day historical volatility** as an example; realized vol itself moves around over time.)
- **Forecast volatility** — output of a model built to *predict* future realized vol better than naive history.

**Implied volatility** (a property of *options*) = the volatility that, plugged into the model, makes the **theoretical value equal the option's market price**. It is the market's **consensus forecast of future realized volatility**.
- Solve for it by inverting the pricing model: hold strike, spot, time, rate fixed; find the σ that reproduces the market price. (Text example: a 105 call worth 3.60 in the market vs. 2.94 theoretical → the discrepancy is implied vol; another: 100 call at implied 27.51%/28.50%.)
- Implied vol changes constantly with supply/demand. Traders use "premium" and "implied vol" almost interchangeably ("options are expensive" = high implied vol).
- Use it to compare relative pricing across strikes/expiries and against recent historical vol (rich vs. cheap).

**What a quant should remember (Ch. 6):**
1. Volatility = annualized σ of returns; scale to other horizons with **× √t** (÷16 per day @256-day yr, ÷7.2 per week; use **÷√252** in production code).
2. Returns ~ normal ⇒ prices ~ **lognormal** (floored at 0, right-skewed, mean right of mode). This is why up-moves are bigger than down-moves in dollar terms and why puts/calls aren't symmetric.
3. **Future realized vol** is the only input you can't observe and the only one that ultimately determines a hedged option's P&L. **Implied vol** is the market's bet on it; **historical vol** is your prior.
4. Sanity-check your vol input against observed price changes: if a $1.04 1σ day "should" be breached ~1 day in 3 but isn't over a meaningful sample, your vol is too high. (5 days is too small a sample; prefer 20/50/100.) Use **settlement-to-settlement** changes, not high/low or open/close.

---

## Chapter 7 — Risk Measurement I: The Greeks

> The Greeks (a.k.a. risk measures / partial derivatives) give **direction and magnitude** of an option's value change as a market condition moves. **All risk measures are additive** across a position: multiply each by signed contract count (+buy / –sell) and sum.

### General effects of changing conditions (Figure 7-1 baseline)

| If… | Calls | Puts |
|---|---|---|
| Underlying rises | rise | fall |
| Underlying falls | fall | rise |
| Volatility rises | **rise** | **rise** |
| Volatility falls | fall | fall |
| Time passes | fall* | fall* |

\*Rare exception: an option can *gain* value as time passes (positive theta) — deeply-ITM, European, stock-type-settled options with negative time value (see Theta).

**Interest-rate / dividend effects (stock options):** rising rates raise the forward → **call values up, put values down** (forward effect dominates the present-value discount because the stock price >> option price). Short-stock hedging effectively lowers the rate → avoid short stock when possible ("Whenever possible a trader should avoid a short stock position"). **Futures options under futures-type settlement are rate-insensitive** (rho = 0). Raising a **dividend** lowers the forward → **calls down, puts up**.

---

### DELTA (Δ) — directional risk

- **Definition:** the rate of change of the option's theoretical value with respect to the underlying price — i.e., **the slope of the value-vs-underlying curve.** First derivative ∂V/∂S.
- **What it measures:** directional exposure. Positive Δ wants the underlying **up**; negative Δ wants it **down**.
- **Sign & bounds:**
  - **Calls: 0 → +1.00** (0.00 deep OTM, → 1.00 deep ITM). Quoted ×100 → 0 to 100.
  - **Puts: 0 → –1.00** (0 deep OTM, → –1.00 deep ITM).
  - ATM ≈ **±50**. (An at-the-forward call is actually *slightly* above 50 due to lognormality.)
- **Three interpretations Natenberg gives:**
  1. **Rate of change** — a 0.25-delta call gains/loses 25% of the underlying's move (underlying +1.00 → call +0.25).
  2. **Hedge ratio** — the number of underlying contracts (as a fraction) needed to be directionally neutral against one option. 40-delta call ⇒ hedge with 0.40 underlying (or 40 underlying per 100 options).
  3. **Approximate probability** — delta roughly approximates the probability the option finishes in the money (a 25-delta option ≈ 25% chance ITM). *Approximation, not exact.*
- **Behavior** (this batch + Ch. 9): Δ moves toward **50** as you **add volatility or time**, and away from 50 (toward 0 or 100) as you **cut volatility or time**. Time and volatility act similarly on delta. Its sensitivity to spot is **Gamma**; to vol is **vanna**; to time is **charm/delta-decay**.
- **Rule of thumb:** A position that is delta-neutral today may not be neutral tomorrow because delta drifts with vol and time — **delta neutrality is instantaneous, not durable.**

### GAMMA (Γ) — curvature / magnitude risk (sensitivity of delta)

- **Definition:** the rate of change of **delta** with respect to the underlying price — the **slope of the delta graph.** Second derivative ∂²V/∂S².
- **What it measures:** how fast directional risk changes; equivalently the **magnitude/speed** of move you want.
- **Sign convention:** **Gamma is always POSITIVE for long options — calls AND puts alike** (same-strike, same-expiry call and put have **equal gamma**). **Long options ⇒ long gamma; short options ⇒ short (negative) gamma.**
- **The delta-update rule (memorize):** **add gamma to the old delta as the underlying RISES; subtract gamma as it FALLS** — for both calls and puts.
  - ATM call Δ=50, put Δ=–50, both Γ=5. Underlying +1 → call 55, put –45. Underlying –1 → call 45, put –55.
- **Position interpretation:**
  - **Positive gamma** position **gains deltas as market rises, loses deltas as it falls** → you want **big/fast moves** (you get longer as it goes up, shorter as it goes down: the position auto-trades in your favor).
  - **Negative gamma** position does the opposite (loses deltas as market rises, gains as it falls) → you want the market to **sit still / move slowly.** New traders are warned to avoid large negative gamma — directional risk changes fast.
- **Gamma is a measure of *realized*-vol preference** (do you want the underlying to actually move a lot or a little).
- **Second-order value estimate (Taylor expansion — the key formula):** delta alone is only valid for tiny moves. Using the **average delta** over the move gives:

```
V(S2) ≈ C + Δ·(S2 − S1) + ½·Γ·(S2 − S1)²
```
  (equivalently `C + (S2−S1)·[Δ + ½·Γ·(S2−S1)]`, using average delta Δ + ½·Γ·ΔS).
  **Worked:** S 97.50→101.50 (+4), C=3.65, Δ=40, Γ=2.5. New Δ = 40 + 4×2.5 = 50; avg Δ = (40+50)/2 = 45; new value ≈ 3.65 + 4.00×0.45 = **5.45**.
  *Caveat: still approximate because gamma itself changes (third-order/"speed").*

### THETA (Θ) — time decay

- **Definition:** the rate at which an option loses value as **time passes**, all else held constant. Usually expressed as **value lost per one calendar day.** ∂V/∂t (with sign convention flipped to per-day decay).
- **Sign convention:** quoted as a **NEGATIVE number** (almost all options decay). Θ = –0.05 ⇒ loses 0.05/day. 4.00 today → 3.95 tomorrow → 3.90 the next day.
- **Behavior — the crucial rule:** for an **at-the-money** option, **theta GROWS (accelerates) as expiration approaches.** Text example for one ATM option: –0.03 at 3 months → –0.06 at 3 weeks → **–0.16 at 3 days.** (ATM time decay is non-linear, accelerating into expiry. ITM/OTM options decay differently — slower near expiry.)
- **Positive theta is possible but rare:** requires **deep-ITM, stock-type settlement, European** (no early exercise). Such an option has **negative time value** (worth the *present value* of intrinsic, e.g. 39 today for a 40-intrinsic option) and rises toward intrinsic as time passes. If it were American everyone would exercise immediately to capture interest.
- **Rule of thumb:** **gamma and theta are (almost) always opposite in sign, and correlated in magnitude.** Long gamma ⇒ negative theta (and vice versa); big gamma ⇒ big theta. **You can't have both** — either movement helps you (long gamma) or the passage of time helps you (positive theta), not both.

### VEGA (ν) — volatility risk (a.k.a. kappa/tau; not a real Greek letter)

- **Definition:** change in theoretical value per **one-percentage-point change in (implied) volatility.** ∂V/∂σ.
- **Sign convention:** **POSITIVE for both calls and puts** (higher vol raises both — more vol = more chance of big favorable moves, and the floor at zero/intrinsic limits the downside). Long options ⇒ long vega; short options ⇒ short vega.
- **What it measures:** exposure to **implied** volatility specifically. Vega = 0.20 ⇒ value moves 0.20 per 1 vol point.
- **Behavior:** vega is **largest for at-the-money options** and **grows with more time to expiration** (long-dated options are far more vega-sensitive than short-dated). It shrinks toward expiry and away from the money.
- **Key distinction vs. gamma:** **Gamma = preference for higher/lower *realized* volatility; Vega = preference for higher/lower *implied* volatility.** Usually correlated, but **not always** — the underlying can get more volatile while implied vol falls, or vice versa (volatility spreads, Ch. 11).
- **Position use:** breakeven / implied vol of a whole position ≈ evaluation vol + (total theoretical edge ÷ total vega). Text: edge +2.20, vega –1.70, eval vol 25% → breakeven ≈ 25% + (2.20/1.70) ≈ **27.29%** = the position's implied volatility.

### RHO (ρ) — interest-rate risk

- **Definition:** change in theoretical value per **one-percentage-point change in interest rate.** ∂V/∂r.
- **Sign convention (stock options, stock-type settlement):** **long calls → positive rho; long puts → negative rho** (rising rates lift the forward, helping calls, hurting puts). Signs flip for short positions.
- **Settlement dependence (the big caveat):** for **futures options under futures-type settlement, rho = 0** (no cash flows from holding either the option or the future, so rates are irrelevant). Under stock-type settlement, raising rates only discounts present value → both calls and puts decline slightly (small unless deep ITM).
- **Magnitude / rule of thumb:** rho **grows with more time to expiration** and is **largest for deep-ITM options** (bigger PV to discount). It is the **least important Greek** — "few individual traders worry about the rho"; usually disregarded in analysis. It's mainly a concern for very long-dated options and large institutional books.

---

### Worked position read (Figure 7-13/7-14 — how to *use* the Greeks together)

Position 1: short 10 June-95 calls @ 8.55 (theo 8.33) + long 7 underlying. Totals: **edge +2.20, Δ –10 (≈neutral), Γ –28, Θ +0.34, ν –1.70, ρ –1.55.**
- Negative gamma → as market rises delta goes more negative (don't want up); as it falls delta goes positive (don't want down) ⇒ **wants the market to sit still.** Worst case: a swift up-move (wrong on both delta and gamma).
- The reward for sitting still is **theta +0.34/day** (profit source). This is the gamma↔theta trade-off in a real position.
- Vega –1.70 ⇒ wants **implied vol to fall**; rho –1.55 ⇒ long-stock debit, wants rates to fall.

**Figure 7-15 summary of desires:** +Δ want up / –Δ want down · +Γ want big/fast moves / –Γ want quiet · (and by the opposite-sign rule, +Γ pairs with –Θ).

**What a quant should remember (Ch. 7):**
1. **Greeks are additive**; build a position's risk by signed-summing per-contract Greeks.
2. **Delta = direction, Gamma = magnitude/speed (realized-vol), Theta = time bleed, Vega = implied-vol, Rho = rates.**
3. **Long-gamma ⇔ short-theta** and the magnitudes scale together — the single most important structural trade-off in options.
4. Delta-neutrality is instantaneous; gamma guarantees it decays. Big negative gamma = fast, dangerous directional drift.
5. Value change for a real move = **Δ·ΔS + ½·Γ·ΔS²** (don't trust a constant delta for big moves).

---

## Chapter 8 — Dynamic Hedging

### 8.1 The mechanic of delta-neutral dynamic hedging

1. Find a theoretical edge (buy options below theo value, or sell above).
2. **Neutralize delta** immediately with the underlying (hedge ratio = position delta).
3. **Re-hedge periodically:** at each interval recompute the option delta, and **buy/sell the underlying to flatten delta back to zero.**
4. At expiration, close out: let OTM expire, exercise/sell ITM at parity, liquidate remaining underlying.

### 8.2 Why gamma forces re-hedging

Because the option has **gamma**, its delta changes every time the underlying moves: up-moves make the (long-option) position longer, down-moves make it shorter. To stay neutral you must **sell the underlying as it rises and buy as it falls.** Long gamma therefore mechanically forces you to **"buy low, sell high"** on every adjustment — that's the profit engine. (A short-gamma hedger is forced to do the opposite — buy high, sell low — and pays for it; that payment is offset by the theta they collect.)

### 8.3 The P&L decomposition — and how it ties to realized-vs-implied vol

Natenberg works two full examples. The punchline: **dynamic hedging lets you capture the difference between an option's theoretical value and its price**, *provided your volatility input is right*. The replication principle:

> *In theory you can replicate an option position through a dynamic hedging process. The cost of replication = the sum of all cash flows from hedging; the present value of that sum = the option's theoretical value.*

**Example A — long underpriced stock-option call.** Bought 100 June calls @ 5.00 (theo 5.89), hedged delta-neutral for 10 weeks, true realized vol over the period = **37.62%**. P&L components (Fig 8-2):

| Component | P&L |
|---|---|
| Original hedge (option + stock) | −422.50 |
| **Adjustment P&L** (the re-hedging trades) | **+467.55** |
| Carry on options | −5.75 |
| Carry (interest earned) on stock | +56.21 |
| Interest on adjustments | −5.27 |
| **Total cash flow** | **+90.24** |
| Discounted to present value | **+89.21** |
| **Predicted** = 100 × (5.89 − 5.00) | **+89.00** |

Realized P&L (89.21) ≈ predicted theoretical edge (89.00). The components that are profitable vs. not are **random in advance** (here the adjustments paid; you could construct a case where the original hedge pays and adjustments don't) — but **in some combination they sum to ≈ the model's prediction if your inputs are right.**

**Example B — short overpriced futures put.** Sold 100 March-60 puts @ 1.70 (theo 1.46, implied 23.92% vs. true 21.48%), hedged with futures (futures-type variation cash flows). Total P&L +24.33, PV +23.96, vs. predicted 100 × (1.70 − 1.46) = **+24.00.** Again realized ≈ predicted.

**The realized-vs-implied relationship (the quant heart of the chapter):**
- A delta-hedged option position is, net of carry, a **bet on realized volatility vs. the implied volatility you traded at.**
- **Long an option (long gamma)** and delta-hedging: you **profit if realized vol > the implied vol you paid**, lose if realized < implied. Your gamma scalps (buy-low/sell-high adjustments) earn more than the theta you bleed exactly when the underlying actually moves more than implied.
- **Short an option (short gamma)** and delta-hedging: you **profit if realized vol < implied vol you sold**; the theta you collect exceeds your adjustment losses when the market is quieter than implied.
- The whole point: dynamic hedging **strips out direction** and leaves a clean exposure to **(realized − implied) volatility**, which is the edge the model identified.

### 8.4 Frictions (why theory ≠ practice)

The model assumes a **frictionless market**: free borrow/short, one constant rate, zero transaction costs, no taxes. Reality violates all four:
- **Transaction costs** are the big one — frequent re-hedging racks up brokerage/exchange fees that can eat the entire edge. There's a tension: hedging continuously minimizes luck (variance) but maximizes cost.
- **Adjustment frequency does NOT change expected return** — it only **smooths** the distribution of outcomes (more bets at the same favorable odds = less variance). A trader who never adjusts still has the edge on average but is hostage to short-term luck on any single hedge.
- Professionals (low costs) adjust often; retail (high costs) adjust less and accept bigger luck swings — same long-run expectation.
- Short stock earns less than full interest; rates differ by participant; rate input is usually the least important. Futures limit-locks can prevent free trading. Taxes matter for portfolios.

**What a quant should remember (Ch. 8):**
1. Delta-hedging converts an option's theoretical edge into realized P&L by **scalping gamma**; the realized P&L ≈ model prediction **iff** your vol input matches realized vol.
2. A hedged book's P&L is fundamentally **(realized vol − implied vol)**, sign depending on long/short gamma. This is *the* mental model for vol trading.
3. **Adjustment frequency trades variance for transaction cost, not expected value.** Hedge bands / cost-aware re-hedging is the real-world optimization.
4. Replication: option value = PV of the dynamic-hedging cash-flow stream (the Black-Scholes self-financing argument, stated plainly).

---

## Chapter 9 — Risk Measurement II (partial — batch ends at p.140)

> Theme: **nothing stays constant.** The Greeks themselves move as conditions move; today's small risk is tomorrow's big risk. This batch reaches the **Delta** second-order discussion and stops at the **vanna** figure. The dedicated Gamma/Theta/Vega-behavior and Lambda sections fall *after* this batch's cut.

### Delta's second-order behavior (covered in this batch)

- **Delta vs. volatility (Fig 9-1):** as vol **rises**, OTM-call delta rises and ITM-call delta falls — **both converge toward 50**. As vol falls, deltas spread toward 0 (OTM) and 100 (ITM). ATM stays ≈ 50 (slightly >50 at the forward due to lognormality). Puts: toward –50 as vol rises; toward 0 / –100 as vol falls.
- **Delta vs. time (Fig 9-2):** identical shape — more time pushes deltas toward 50; less time pushes them to 0/100. **Time and volatility act the same way on delta** (both increase the chance of large moves). Useful heuristic: if you can't reason about a time effect, reason about the analogous vol effect, and vice versa.
- **Practical consequence — "is my book even delta-neutral?"** Delta depends on the (unknown future) volatility, so **the delta you compute is a guess.** Many traders use the **implied delta** (delta computed at *implied* vol). Then delta shifts as implied vol shifts even if spot is unchanged. Text example: own 40 calls, implied delta 25 → short 10 underlying to neutralize (40×25 = 1000). If implied vol rises 32%→36%, implied delta → 30, position delta = 40×30 − 10×100 = **+200** — **neutral became bullish with no move in the underlying.**
- **Delta also decays with time:** a neutral position today may not be neutral tomorrow even if nothing else moves — and near expiry, **one day is a large fraction of remaining life**, so the delta shift can be dramatic.

### Named second-order sensitivities (introduced here)

- **Gamma** = ∂Δ/∂(spot) — sensitivity of delta to the underlying price (covered Ch. 7).
- **Vanna** = ∂Δ/∂(volatility) — sensitivity of delta to **volatility**. Largest for deltas near **20 and 80** (calls) / **−20 and −80** (puts); ≈ 0 near ±50. Vanna **falls as vol rises**, rises as vol falls; barely affected by time.
- **Charm** (a.k.a. **delta decay**) = ∂Δ/∂(time) — sensitivity of delta to the **passage of time**. Same shape as vanna (greatest near 20/80 deltas, ≈0 near 50); **rises as expiration approaches**; barely affected by vol.
- All three (gamma, vanna, charm) are **second-order** sensitivities of the delta (to spot, vol, time respectively).

> **Beyond this batch (not in the text here):** Gamma's own behavior (peaks ATM, spikes near expiry for ATM, **"gamma rent"**), Theta behavior, Vega behavior (peaks ATM, grows with time), and **Lambda** are in the *later* part of Ch. 9 — not in `02_greeks_hedging.txt`. Flagging so the omission is explicit rather than silent.

---

## LAMBDA (Λ) — *NOT in this batch's text; standard definition, flagged*

> **(verify: sourced from the standard Natenberg/textbook definition, since the task requires Lambda but this batch's file never mentions it — see Scope note at top. Confirm against the later Ch. 9 batch when available.)**

- **Definition:** **Lambda (Λ), a.k.a. the leverage or elasticity** of an option = the **percentage change in the option's value for a 1% change in the underlying price.** Effectively delta expressed in *elasticity* terms.
- **Formula:** `Λ = Δ × (S / V)` — delta scaled by (underlying price ÷ option value). Equivalently `Λ = (∂V/V) / (∂S/S)`.
- **What it measures:** the **effective leverage** of holding the option vs. holding the underlying. A Λ of 8 means the option moves ~8× the *percentage* move of the underlying.
- **Sign:** positive for calls, negative for puts (inherits delta's sign).
- **Behavior / rule of thumb:** leverage is **highest for OTM options** (small V denominator, so a little delta produces a large % swing) and **lowest (→1) for deep-ITM options** that behave like the underlying. Lambda **shrinks as the option goes ITM** and as expiration nears for ITM options. It quantifies why cheap OTM options are "lottery tickets" — huge percentage leverage, low probability.

---

## Practical takeaways (cross-chapter)

- **Scale vol with √time, never linearly.** Daily ≈ annual/16 (Natenberg, 256-day) or annual/√252 (production); weekly ≈ annual/7.2. Carry the 68/95/99.7 rule in your head.
- **Prices are lognormal:** floored at zero, right-skewed, up-moves bigger than down-moves in dollars, mean right of mode. Don't model equity prices as plain normal.
- **The five core Greeks map to the five risks:** spot (Δ), curvature/realized-vol (Γ), time (Θ), implied-vol (ν), rates (ρ). Rho is usually negligible (and exactly 0 for futures-type-settled futures options).
- **Long gamma = short theta**, always, with correlated magnitudes. Decide which side of (realized vs implied) vol you want; that dictates your gamma/theta sign.
- **Delta-neutral is a snapshot.** Gamma, vanna (vol), and charm (time) all move your delta. Re-hedge; recognize that an implied-vol move alone can un-neutralize you (implied delta).
- **A delta-hedged position is a pure bet on realized − implied volatility.** Long options win when the world is wilder than implied; short options win when it's calmer.
- **Re-hedging frequency buys variance reduction, not expected return** — and costs transaction fees. Optimize with hedge bands, not reflexive continuous hedging.
- **Sanity-check vol against tape:** if observed moves are persistently smaller/larger than your 1σ estimate over a real sample, your vol (and therefore your probabilities and theo values) is wrong.

---

## Batch 2 — Top 10 durable lessons

1. **Volatility = annualized σ, and it scales with √time.** σ_daily ≈ σ_annual/16 (256-day convention) or σ_annual/√252 in code; σ_weekly ≈ σ_annual/7.2. Linear scaling is wrong.
2. **Returns normal ⇒ prices lognormal:** bounded at 0, right-skewed, mean to the right of the mode, up-moves > down-moves in dollar terms. This is why Black-Scholes uses continuous compounding and why option payoffs aren't symmetric.
3. **Delta = slope/direction (0→±1), doubles as hedge ratio and rough ITM-probability.** It drifts toward 50 with more vol/time and toward 0/100 with less. Neutrality is instantaneous only.
4. **Gamma = ∂delta/∂spot, always positive when long options (calls = puts), and it's your *realized*-vol exposure.** Add Γ to delta on up-moves, subtract on down-moves. Update value with **Δ·ΔS + ½·Γ·ΔS²**.
5. **Theta = per-day time decay, quoted negative, and it ACCELERATES into expiry for ATM options** (−0.03 → −0.06 → −0.16). Positive theta only in rare deep-ITM European stock-settled cases.
6. **Gamma and theta are equal-and-opposite, magnitude-correlated.** You can be paid by movement (long gamma) or by time (positive theta) — never both. This trade-off is the spine of options trading.
7. **Vega = per-vol-point sensitivity, positive for calls and puts, biggest ATM and for long-dated options — and it tracks *implied* vol, distinct from gamma's *realized* vol.** The two usually move together but can diverge.
8. **Rho is the runt:** small, rate-driven, calls + / puts − for stock options, and exactly **0 for futures-type-settled futures options**. Settlement convention changes everything about rate sensitivity.
9. **Dynamic delta-hedging monetizes a theoretical edge by scalping gamma; net of carry, a hedged book's P&L ≈ (realized vol − implied vol).** Long gamma profits when realized > implied; short gamma when realized < implied. Re-hedging frequency only trades variance for transaction cost — it doesn't move expected value.
10. **Nothing stays constant (Ch. 9):** the Greeks themselves move. Delta shifts with vol (**vanna**) and time (**charm**); even an implied-vol change with a frozen spot can flip you from neutral to directional. Manage second-order risk, not just first-order.