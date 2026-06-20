# Natenberg Ch.5 — Theoretical Pricing Models

*Source: `batches/01c_ch5_pricing.txt` (Natenberg, *Option Volatility & Pricing*, 2nd ed., Ch.5). Read end-to-end. Paper-quant study note.*

---

## 0. Why this chapter exists: direction ISN'T enough — SPEED matters

The setup that motivates the whole pricing-model project:

- An **underlying** trader cares almost exclusively about **direction**. Be right on direction → wait → take profit. If the stock goes from $100 to your $115 target, you sell at $115. Guaranteed.
- An **option** trader must be right on **direction AND speed** (how *fast*, i.e. within *how much time*). Natenberg's worked example: stock at $100, you expect $115 within 5 months.
  - Buy a 3-month $110 call at $2: if the stock only reaches $115 *after* expiration, the option expires worthless → lose the $2, even though your directional call was correct.
  - Buy a 6-month $110 call at $6: now you're sure it's worth ≥$5 intrinsic when the stock hits $115 — but you paid $6, so you can *still* lose. Being right on direction did not save you.
- **Takeaway**: a favorable directional move that's too *slow* may not offset the option's time-value decay. Buying options for "limited risk / unlimited reward" is seductive but you must be right on **both** counts.
- This is why **many option strategies depend only on speed, not direction at all**. If you're genuinely great at predicting direction, just trade the underlying. Options are for when you have a view on **speed** (i.e. volatility). This "speed" concept *is* the seed of volatility (Ch.6).

---

## 1. The probability framing — option value = probability-weighted expected return

Core thesis: **you can never be certain about the future, so every trading decision is really a probability estimate.** Vague words (*likely, good chance, probable*) aren't enough — for option evaluation we must define probability **numerically** so we can do calculations. And probability drives strategy choice:

- **High probability of profit, low probability of loss** → trader is content with a *small* potential profit (the profit is relatively secure).
- **Low probability of profit** → trader *demands a large* profit before he'll take the bet (compensation for the long odds).

### 1a. Expected value — the die

Roll a fair 6-sided die, get paid $ = the face. Over infinitely many rolls, average payback:
- (1+2+3+4+5+6) / 6 = 21/6 = **$3.50 = expected value**.
- Pay **< $3.50** → expect a profit in the long run; pay **> $3.50** → expect a loss; pay **= $3.50** → break even.
- Critical qualifier: **"in the long run."** Expected value is only realized over *many* rolls. On a single roll you can't even *get* $3.50 (no face has 3.5 spots). But paying < EV puts the laws of probability on your side.

### 1b. Expected value — the roulette bet (the casino analogy — WALKED EXPLICITLY)

US roulette wheel = **38 slots** (1–36, plus 0 and 00). Casino offer: pick a number; if it hits you get **$36**, else nothing.
- Only 1 of 38 slots pays $36 → **EV = $36 / 38 = $0.9474 ≈ 95 cents**.
- A player paying **95¢** to pick a number ≈ breaks even in the long run.
- **No casino sells it at 95¢** — that's zero profit. Real price ≈ **$1**. The **5¢** gap between the $1 price and the 95¢ EV is the casino's **edge** (profit potential). Over time, ~5¢ kept per $1 bet.
- Mirror-image insight: a profit-seeker would rather **be the casino** (sell 95¢-value bets for $1 → +5¢ edge), or find a casino selling the bet **below** EV (e.g. 88¢ → player gets a +7¢ edge). **→ This is exactly the option trader's job: buy below theoretical value, or sell above it, to capture edge.**

### 1c. Theoretical value = present value of expected value (carry / interest discount — WALKED EXPLICITLY)

**Definition**: *theoretical value = the price you'd pay NOW to just break even in the long run.* So far EV alone gave the 95¢ "fair" price. Now add the **timing of cash flows**:

Casino changes the rules: you still pay your 95¢ now (and the casino collects it immediately if you lose), **but if you WIN, the casino pays your $36 in two months.** Does everyone still break even?

- Where did your 95¢ come from? Ultimately you **withdrew it from the bank.** Because winnings arrive 2 months late, you forgo **2 months of interest** you'd have earned leaving the 95¢ in the bank.
- So the true value is the **present value of the expected value** — the 95¢ EV **discounted by interest**. At 12%/yr:

  **TV = 95¢ / (1 + 0.12 × 2/12) ≈ 93 cents**

- Interpretation: even paying the 95¢ "expected return," you **lose ~2¢** to forgone interest; the casino takes your 95¢, parks it in an interest-bearing account, and earns that ~2¢ over the 2 months. Pay **93¢ today** for a payout in 2 months → *now* both sides break even.
- **The two most common option-evaluation considerations are therefore: expected return AND interest (cost of carry).**

### 1d. Dividends — a future bonus ADDS to theoretical value (WALKED EXPLICITLY)

Same roulette example: you're a good client, so the casino decides to send you a **1¢ bonus one month from now** (an inbound cash flow to *you*).
- Add it to the prior 93¢ TV → **new TV = 94 cents.**
- Natenberg's explicit analogy: **this 1¢ bonus is exactly like a dividend** paid to a stockholder. Dividends are an *additional* consideration in valuing both stock and stock options — a future inbound payment that **raises** what the proposition is worth to the holder today.

> **Mental model**: **Theoretical value = (probability-weighted expected value) − (carry cost of paying-now-vs-collecting-later) + (any future bonus/dividend inflow to the holder).** Expected value is the anchor; interest discounts it; dividends add back.

### 1e. Long run vs short run — why risk management matters as much as the value

Selling 95¢-EV bets for $1 *guarantees* casino profit **only if it survives to the long run.** In the short run, someone could hit their number 20 times straight — wildly unlikely, but the laws of probability permit it. If that bankrupts the casino, it **never reaches the long run.**
- Same for options: even a *correctly* computed theoretical value rests on probability, which is reliable **only in the long run.** So the trader must also manage **short-term bad luck (risk).**
- **Natenberg's repeated emphasis: a trader's ability to MANAGE RISK is at least as important as his ability to CALCULATE a theoretical value.** Getting the value right is only half the problem.

---

## 2. "A word on models" — what a model is, and garbage-in-garbage-out

- A **model** = a scaled-down / more manageable representation of the real world (physical like a model airplane, or mathematical like a formula). Useful, but **never an exact replica** — dangerous to treat model and reality as identical.
- Every effective model needs **prior assumptions** about the world; math models need **numbers quantifying those assumptions.** Feed bad data → get a bad picture. **"Garbage in, garbage out."**
- Option models are **someone's idea** of how an option might be valued under certain conditions. Either the *model* or the *inputs* can be wrong → **no guarantee** model values are accurate, nor that they resemble actual market prices.
- **The candle-in-a-dark-room metaphor** (important): a new trader with no model gropes in the dark; a trader with a basic model enters with a **candle** — sees the general layout, but the dimness hides detail and the **flicker distorts** some of what he sees. Still better than no light. *Footnote warning*: a trader with a candle might **drop it and burn the building down** — "financial crises seem to occur when many traders drop their candles at the same time." The real danger comes *after* the trader gains confidence and **sizes up**: now a misread of the dim/flickering room gets **magnified** into financial disaster.
- **Sensible approach**: use the model, but with **full awareness of what it can and cannot do** — its limitations as well as its strengths.

---

## 3. A simple approach — building a pricing model from EV + PV

Toy world: underlying can finish at **$80, $90, $100, $110, $120**, each **20%** likely.

- **Expected value of the underlying** = 0.20×(80+90+100+110+120) = **$100.**
- **Expected value of the 100 call** (intrinsic = max(S−100, 0)): worthless at 80/90/100; worth $10 at 110, $20 at 120:
  - (0.2×0)+(0.2×0)+(0.2×0)+(0.2×$10)+(0.2×$20) = **$6.**
- **General formulas** (the heart of the chapter):
  - Call EV at expiration: **Σ pᵢ · max(Sᵢ − X, 0)**
  - Put EV at expiration: **Σ pᵢ · max(X − Sᵢ, 0)**
  - where Sᵢ = possible underlying price at expiration, pᵢ = its probability.
- **Then discount to present value** per the settlement procedure. Stock-type settlement = pay full price up front → TV = PV of the EV. At 12%/yr (1%/mo), 2 months out:
  - **TV = $6.00 / (1 + 0.12×2/12) = $6.00 / 1.02 ≈ $5.88.**

### 3a. Make the distribution realistic — concentrate probability near the current price

Equal 20% weights are unrealistic: **large moves are less likely than small moves** (if spot ≈ $100, $110 is far more likely than $250). Re-weight to bunch probability around the center (e.g. 10/20/40/20/10):
- New 100-call EV = (0×0)+(0.2×0)+(0×0)+(0.2×$10)+(0.1×$20) = **$4** → TV = 4/1.02 ≈ **$3.92.**
- Symmetric re-weighting around $100 leaves the **underlying's** EV at $100 (unchanged).

### 3b. The arbitrage-free constraint: EV of the underlying MUST equal the FORWARD price

Key correction to the naïve "center on spot" idea: whatever probabilities you assign, the underlying's EV should equal its **most likely / average** expiration value — and the only defensible answer is **the forward price**. Rationale: if the market's forward price differed from the theoretical forward, everyone would **arbitrage** it (buy/sell forward, offset in cash). So in an **arbitrage-free** market, **EV(underlying) = forward price.**

- Example: stock at $100, no dividend, 12%/yr, 2 months → **forward = 100 × (1 + 0.12×2/12) = $102.**
- Re-center probabilities around **$102** (not $100). With a 10/20/40/20/10 distribution around 102:
  - 100-call EV = (0.1×0)+(0.2×0)+(0.4×$2)+(0.2×$12)+(0.1×$22) = **$5.40** → TV = 5.40/1.02 ≈ **$5.29.**
- **Distributions need NOT be symmetric** — only EV(underlying) = forward is required. Natenberg's skewed example (prices 83/90/99/110/123 with probs 6/15/39/33/7) still gives EV = $102, and the 100-call TV ≈ **$4.81**.
- **Forward price is central to ALL option pricing models.** For **European** options, today's spot matters *only* insofar as it converts into a forward. Hence the distinction **at-the-money** (X = current underlying) vs **at-the-forward** (X = forward price). **At-the-forward options are often the most actively traded and used as a benchmark.**

### 3c. The 4 steps to build a model (verbatim summary)

1. **Propose** a series of possible underlying prices at expiration.
2. **Assign probabilities**, constrained so the market is **arbitrage-free** → EV(underlying) = forward price.
3. From prices, probabilities, and the chosen exercise price, **compute the option's expected value.**
4. Depending on **settlement procedure**, take the **present value** of that expected value.

> Real-world catch the chapter foreshadows: the toy model uses **5** outcomes; reality has an **infinite** number of possible prices. We'd ideally build a continuous probability distribution over *every* outcome — "an insurmountable obstacle" that later chapters (the lognormal/Black-Scholes machinery) show how to approximate.

---

## 4. The Black-Scholes model (conceptual intro)

### 4a. Brief history
- Charles Castelli, London **1877**, *"The Theory of Options in Stocks and Shares"* — described early strategies "call-of-more" & "call-and-put" (today = **covered-write** and **straddle**).
- Louis Bachelier (French mathematician), **1900**, *The Theory of Speculation* — first use of higher math to price options; academically interesting but little practical use (no organized option markets then).
- **1973**, concurrent with the **CBOE** opening: **Fischer Black** (U. Chicago) and **Myron Scholes** (MIT) built on Bachelier et al. to publish the **first practical** option pricing model. (Robert Merton, MIT, credited with parallel work → sometimes "**Black-Scholes-Merton**." Scholes & Merton won the 1997 Nobel; Black died 1995.)
- Original B-S: **European** options on **non-dividend-paying stocks**. Then a **dividend component** was added. **1976** Black adapted it for **futures** options (the **Black model**). **1983** Garman & Kohlhagen (UC Berkeley) adapted it for **foreign-currency** options (the **Garman-Kohlhagen model**).
- All three variants share the same valuation logic → collectively called **"the Black-Scholes model."** They differ **only** in (a) how they compute the **forward price** of the underlying and (b) the **settlement procedure** of the options. Trader just picks the appropriate form.

### 4b. The 5 required inputs (THE key list)
To get a theoretical value, B-S needs at minimum **five** characteristics:

1. **Exercise (strike) price** — fixed by contract; never changes (a March 60 call can't become a March 55 call). *(Exchanges may adjust strikes for splits/extraordinary dividends — purely an accounting change.)*
2. **Time to expiration** — fixed date; entered **annualized** (days/365). For *price-movement* likelihood, only **business days** matter; for *interest*, **every** day counts. Software scales business-day vol to an annual number, so you can just input actual calendar days. Finer increments (hours/minutes) → theoretically more accurate near expiry, but very close to expiration **model values become unreliable** (inputs become unreliable) and many traders **stop using model values altogether**.
3. **Current price of the underlying** — *not* always obvious. There's a **bid-ask spread** (e.g. last 75.25, market 75.20–75.40). Which to feed? Disciplined answer: use the price at which you can make the **hedging** trade. Buying calls / selling puts (long positions) → you hedge by **selling** underlying → use ~**bid**. Selling calls / buying puts (short) → hedge by **buying** underlying → use ~**ask**. Very liquid market → midpoint is fine; illiquid/wide/fast market → think carefully (may not even fill at quoted prices).
4. **Interest rate** over the option's life — see §4d.
5. **Volatility** of the underlying — see §4e. **THE ONLY INPUT NOT DIRECTLY OBSERVABLE** (see §5).

*(+ **Dividends** for stock options — a 6th input, but only relevant when the stock pays a dividend over the option's life; see §4d.)*

### 4c. The riskless hedge & hedge ratio (why B-S is more than EV)
Beyond the simple EV approach, Black & Scholes added the **riskless hedge**: for every option position there's a theoretically equivalent underlying position such that, **for small price changes**, the option gains/loses value at exactly the same rate as the underlying. To exploit a mispriced option you **offset it with this equivalent underlying position**; the correct proportion is the option's **hedge ratio** (delta).
- **Why hedge?** An option's value depends on the *probabilities* of various outcomes, and **those probabilities shift as the underlying moves** (drop spot $100→$90 and the probability assigned to $120 falls). By establishing a riskless hedge and **re-adjusting it as conditions change**, you continuously account for the changing probabilities.
- An option is thus a **substitute** for an underlying position: **call ↔ long**, **put ↔ short**. Whether the substitute beats the outright depends on theoretical value vs market price (buy calls/sell puts below value → cheaper long; buy puts/sell calls above value → cheaper short).
- **The four basic hedges** (memorize — beginners get puts backwards):

  | Option position | Market position | Hedge |
  |---|---|---|
  | Buy call(s) | Long | **Sell** underlying |
  | Sell call(s) | Short | **Buy** underlying |
  | Buy put(s) | Short | **Buy** underlying |
  | Sell put(s) | Long | **Sell** underlying |

  Rule of thumb: with **calls** do the **opposite** to the underlying; with **puts** do the **same** as the underlying. (Buying puts AND selling the underlying = no hedge at all.)

### 4d. Interest & dividends inputs (detail)
- **Interest plays two roles**: (1) it affects the **forward price** — for stock-type settlement, ↑rates ↑forward → ↑call values, ↓put values; (2) it affects the **present value** of the option — for stock-type settlement, ↑rates ↓PV of the option. Usually one rate serves both; foreign-currency options need **two** rates (foreign + domestic) → Garman-Kohlhagen.
  - Which rate? Textbooks say the **risk-free rate** (government yield matched to the option's life, e.g. 60-day option ↔ 60-day T-bill). In practice no one borrows/lends at the gov rate, so traders use **LIBOR** / **Eurocurrency** / **Eurodollar futures (CME)** benchmarks. Strictly the correct rate depends on whether the trade creates a **credit** (borrowing rate) or **debit** (lending rate). **But interest is the LEAST important input** — a rate that "makes sense" is fine, *except* for very large positions or very long-dated options where small rate changes matter a lot.
- **Dividends** — only matter for **stock** options, and only if a dividend falls within the option's life. Needed to get the **forward price** right → must estimate **amount** and **date**. Traders focus on the **ex-dividend date** (date the stock trades without dividend rights) more than the payment date, because **ownership of the stock is what carries the dividend right** — a deep ITM option resembles stock but does *not* earn the dividend. Default assumption: a company continues its past dividend policy (e.g. 75¢/quarter) — but it's not certain until declared (can be raised/cut/omitted). Watch a **late-quarter ex-date**: a few days' slip can push ex-date *past* expiration, which for valuation = **eliminating the dividend entirely**.

### 4e. Volatility input (intro — full treatment Ch.6)
- **Volatility = a measure of the SPEED of the market.** Slow market = low vol; fast market = high vol. If the underlying doesn't move fast enough, options are worth less (lower chance of crossing the strike).
- It's the input **most difficult to understand** yet **most important** in real trading decisions — changes in vol assumptions dramatically swing option **values**, and how the *market* assesses vol dramatically swings option **prices**.
- From the chapter's earlier logic, vol is tied to **the speed of the underlying** and/or **the probabilities of different price outcomes** — i.e. it's literally the numerical handle for the probability distribution we hand-waved in §3. Needs to be **quantified** to feed the model. (Natenberg's 2008 crude-oil example — +58% then −69% in one year vs the far-calmer S&P 500 — illustrates that markets differ greatly in volatility.) Detailed in Ch.6.

---

## 5. What a pricing model DOES, and its limitations

- **What it does (one sentence)**: a pricing model **converts your assumptions about the future price distribution of the underlying into a single fair (theoretical) value** — it takes the 5 (+dividend) inputs and outputs one number (Figure 5-6: exercise price, time, underlying price, interest, volatility → pricing model → theoretical value).
- **The decision it enables**: compare that theoretical value to the **market price** → judge whether the option is too cheap or too rich, and whether the **theoretical edge** justifies a trade (just like the casino capturing the 5¢).
- **Limitations the chapter explicitly foreshadows**:
  - **Garbage-in-garbage-out** — the value is *no better than the inputs*. Four of the five inputs are essentially observable; **volatility is the only one not directly observable** → it's an *estimate*, and it's the input the model is most sensitive to. A wrong vol guess → a wrong value, confidently displayed.
  - **The model is only as good as its assumptions** — it's "someone's idea" of valuation; neither the model nor its data is guaranteed correct, and model values needn't match market prices.
  - The **candle/flicker** caution: the model illuminates dimly and distorts some detail; the danger **scales with position size** — small misreads become disasters when magnified.
  - The toy discrete distribution (5 prices) is a stand-in for a continuous one (infinite prices) — the realism of the output depends entirely on how well the assumed distribution matches reality.
  - **Probability is only reliable in the long run** → even a correct theoretical value requires **risk management** to survive short-run bad luck. *Value ≠ safety.*

---

## What a quant should remember

- **Options price PROBABILITY, not just direction.** The whole model is: enumerate future underlying prices, weight by probability, take the payoff's expected value, discount to present. `EV_call = Σ pᵢ·max(Sᵢ−X,0)`, `EV_put = Σ pᵢ·max(X−Sᵢ,0)`.
- **Theoretical value = present value of expected value + dividend inflows.** Three ingredients: (1) probability-weighted EV, (2) **discount for carry** (you pay now, collect later), (3) **add future dividends/bonuses** to the holder. The roulette walk: 95¢ EV → discount to ~93¢ for 2 months' interest at 12% → +1¢ bonus = ~94¢.
- **The arbitrage-free constraint pins the distribution's mean to the FORWARD price**, not spot. `EV(underlying) = forward = S·(1 + r·t)` for stock-type settlement. For **European** options, spot matters only via the forward; this is why **at-the-forward** options are the standard benchmark. Distributions need NOT be symmetric — only the *mean = forward* constraint binds.
- **5 model inputs** (+ dividends for stock): exercise price, time to expiration, underlying price, interest rate, volatility. **Volatility is the ONLY one not directly observable** — and it's the one the value is most sensitive to → it's where the real edge and the real error both live.
- **Input hierarchy of importance**: volatility ≫ underlying price > time ≫ interest (interest is the *least* important — "makes sense" is fine, except large/long-dated positions). Exercise price and expiration are fixed and unambiguous.
- **Underlying price is hedge-dependent**: feed the price at which you'd make the *offsetting* trade — ~bid when you'll sell the underlying (long calls / short puts), ~ask when you'll buy it (short calls / long puts). Midpoint only in deep-liquid markets.
- **A model CONVERTS assumptions about the future price distribution into one fair value.** It is a candle, not sunlight — GIGO on the vol input, distorts detail, and the danger scales with size. Use it *with full awareness of its limits*.
- **Computing the value is only half the job.** Probability is reliable only in the long run; surviving the short run is **risk management**, which Natenberg rates *at least as important* as getting the value right.
- **Delta = hedge ratio.** B-S's riskless hedge offsets each option with an equivalent underlying position; you *re-adjust* it as the underlying moves because the outcome probabilities shift. Calls → trade opposite the underlying; puts → trade the same direction. Getting puts backwards = no hedge at all.
- **Operationally for our paper book**: when we mark theoretical values, our edge is entirely a bet that *our* volatility (and forward/carry/dividend) inputs are closer to reality than the market's. Treat the vol input as the assumption to stress-test first, and never confuse a confidently-printed model value with a *safe* trade.

---

## Chapter 5 — top lessons

1. **Direction is necessary but not sufficient for options — SPEED (volatility) is the second axis.** The underlying trader needs only to be right on direction; the option buyer must be right on direction *and* speed, or time decay eats a correct directional call. Many option strategies trade speed alone.
2. **Every option value is a probability-weighted expected payoff, discounted to today.** `TV = PV( Σ pᵢ · payoffᵢ )`. Master the die/roulette intuition: expected value is the long-run average payback; you only have an edge if you transact away from it.
3. **Theoretical value layers three effects: expected value, then a CARRY discount (pay now / collect later), then a DIVIDEND/bonus add-back.** The roulette walk (95¢ → ~93¢ → ~94¢) is the entire pricing logic in miniature.
4. **The mean of the price distribution must equal the FORWARD price (no-arbitrage), not spot.** Forward = S·(1+r·t) (stock-type). This is the pivot of *all* option models; European-option value depends on spot only through the forward. Symmetry is optional; mean-equals-forward is not.
5. **A model needs 5 inputs (+ dividends for stock), and VOLATILITY is the only one you can't observe.** Four are essentially given; vol must be *estimated*, and the value is most sensitive to it — so it is simultaneously the source of edge and the source of error.
6. **Garbage in, garbage out — and the candle can burn the building down.** A model is a dim, flickering map, not reality; its danger grows with position size. The mature stance: use it, but know exactly what it can and cannot do.
7. **Calculating the value is only half the problem; managing short-run risk is the other half.** Probability pays off only over the long run, and you must survive the long run to collect — Natenberg weights risk management *at least* as heavily as valuation.
8. **Black-Scholes is one engine, many bodies** (BS for stock, Black for futures, Garman-Kohlhagen for FX). Same valuation logic; they differ only in how they compute the forward and handle settlement. Pick the right form for the instrument.