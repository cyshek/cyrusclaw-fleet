# Natenberg — Batch 2B: Dynamic Hedging (ch8) + Risk Measurement II (ch9, partial)

> **Scope note / truncation flag.** This batch file (`02b_hedging_greeks2.txt`, 1975 lines) runs from the tail of ch7 (Risk Measurement I — delta interpretations, gamma, theta, vega, rho recap) through **all of ch8 Dynamic Hedging**, then into **ch9 Risk Measurement II but it CUTS OFF at book p.140 / Figure 9‑6 (Vanna).** So ch9 here only covers how **Delta** changes with vol & time (plus the two second‑order names *vanna* and *charm*). The deeper material the task asked for — **Gamma / Theta / Vega behavior across spot/time/vol (gamma & theta peaking ATM near expiry; vega peaking ATM and rising with time), and Lambda Λ (leverage/elasticity)** — is **NOT in this file**; it spills into the next batch. `grep` for "lambda/elasticity/leverage" returned nothing here. I cover the Lambda + Greek‑peaking material below from standard Natenberg knowledge and label it **`(NOT IN THIS BATCH — from next file / standard result, verify against source)`** so it isn't mistaken for verbatim text from this file.

---

## Chapter 7 tail — Delta recap, Gamma estimation, the Risk‑Measure position example

(This batch opens mid‑ch7; the genuinely new/useful pieces here:)

**Three+1 interpretations of delta** (all mathematically the same number; pick by use):
1. **Rate of change** of theoretical value w.r.t. underlying: a +500‑delta position changes ≈ 500% of the underlying's move (underlying +2.00 → +10.00; −1.25 → −6.25).
2. **Hedge ratio**: contracts of underlying per option for a neutral hedge = 100 / option‑delta. Delta‑50 call → 100/50 = 2 options : 1 underlying. Delta‑40 → 5 options : 2 underlying. Put delta −75 → 4 puts : 3 underlying.
3. **Equivalent underlying position**: each 100 deltas ≈ one underlying contract (50‑delta option = ½ underlying).
4. **Probability (approx.)**: |delta| ≈ P(finish ITM). 25‑delta ≈ 25% ITM. Only an approximation — interest/dividends distort it, and it's the **forward**‑ATM option (not spot‑ATM) whose delta is ~50. Because of lognormality, an exactly‑at‑the‑forward call has delta **slightly > 50**.

**Delta‑neutral** = sum of all position deltas = 0. Underlying contract delta is **always ±100**. Convention: deltas as whole numbers (calls 0→100, puts −100→0).

**Gamma (Γ)** = rate of change of delta per 1‑pt underlying move; **slope of the delta curve**. Add Γ to delta when underlying rises, subtract when it falls — **for both calls and puts** (gamma is always positive for long options). Long any option (call OR put) = **long gamma**; short options = short gamma. New traders warned off large (esp. negative) gamma because directional risk (delta) changes fast.

**Gamma‑improved value estimate** (delta alone is only an instantaneous, small‑move measure). Using the **average delta** over the move S1→S2:

> New value ≈ C + (S2−S1)·Δ + ½·(S2−S1)²·Γ

This is the **second‑order Taylor expansion** of option value in the underlying (delta term + ½·gamma·move²). The book writes it with (S1−S2) signs but the squared term makes it symmetric; the gamma term is **always a positive contribution for a long‑gamma holder** (convexity).
- *Worked:* S=97.50, C=3.65, Δ=40, Γ=2.5; underlying → 101.50 (move +4). New delta = 40 + 4·2.5 = 50. Avg delta = (40+50)/2 = 45. New value ≈ 3.65 + 4.00·0.45 = **5.45**. (Delta‑only would give 3.65 + 4·0.40 = 5.25; the +0.20 is the gamma/convexity pickup.)

**Theta (Θ)** = value lost per day, all else equal; quoted **negative**. Key fact (expanded in ch9): an **ATM option's theta grows as expiration nears** — e.g. −0.03 at 3 months → −0.06 at 3 weeks → −0.16 at 3 days. **Positive theta** is possible only in rare cases (deep‑ITM, European, **stock‑type settlement** ⇒ option trades at PV of intrinsic, so it rises toward intrinsic over time = negative time value). An American option here would just be exercised for the interest.

**Vega (Θ/kappa Κ)** = value change per 1 vol‑point; **positive for both calls and puts**. Vega 0.15 ⇒ +1 vol pt → +0.15.

**Rho (Ρ)** = value change per 1 interest‑pt; sign depends on instrument/settlement (stock calls +, stock puts −; stock‑settled futures options both −; futures‑settled both = 0). Usually the least important input.

**Underlying contract Greeks:** delta = ±100, **gamma = theta = vega = rho = 0**. Only delta matters for the underlying.

### The Figure 7‑13/7‑14 position‑risk example — the conceptual payoff
A position's total Greeks are **additive** (Greek × signed contract count, summed). Walking Position 1 (**−10 June‑95 calls + 7 underlying**, ≈ delta‑neutral at delta −10):
- **Gamma −28** (negative). As stock rises, delta = −10 + (−28) = −38, then −66 → you get **more short** as it rises (don't want a rally). As stock falls, delta = −10 − (−28) = +18, then +46 → you get **more long** as it falls (don't want a selloff either). **Negative gamma ⇒ you want the market to sit still / move slowly.** Positive gamma ⇒ you want big, fast moves.
- **Delta = directional risk; Gamma = magnitude/speed risk.**
- **Theta +0.34** (positive, opposite sign to gamma). The profit for a short‑gamma holder who gets a quiet market **comes from theta** (collect ~0.34/day).
  - **Core principle: gamma and theta are (almost) always opposite in sign, and their magnitudes correlate** (big gamma ↔ big theta). *You can't have it both ways:* either movement helps you (long gamma) or time helps you (long/positive theta), not both. (Interest can rarely break this, but only by tiny amounts.)
- **Vega −1.70** (negative ⇒ want **implied** vol to fall). **Critical distinction:** **gamma = preference for higher/lower REALIZED vol** (how much the underlying actually moves); **vega = preference for higher/lower IMPLIED vol** (the market's vol price). They're usually correlated but **can diverge** (underlying gets more volatile while IV falls, or vice‑versa — covered in ch11 vol spreads).
- **Position "implied (breakeven) volatility"**: vol at which the whole position just breaks even ≈ entry vol + (total theoretical edge / total vega). Here: 25% + (+2.20 / −1.70) = 25% + 1.29% ≈ **27.29%** breakeven IV. Bumping vol from 25→26% changes edge by adding the vega: +2.20 + (−1.70) = +0.50; →27%: +0.50 + (−1.70) = −1.20.
- A position can carry a **negative theoretical edge** (Position 2): nobody enters one on purpose, but markets shift and a once‑sensible position can become a long‑run loser — when that happens, **close it; holding longer only raises the expected loss.**
- Caution closing remark: the Greeks **identify** risk, they don't **eliminate** it. Don't over‑analyze into "paralysis through analysis" — use them to pre‑decide which risks are acceptable.

**Ch7 — what a quant should remember:** delta = 1st‑order/direction; gamma = 2nd‑order/convexity/speed‑of‑delta; value ≈ delta·dS + ½·gamma·dS². Greeks are additive across a book. **Long options ⇒ long gamma, short theta, long vega; short options ⇒ flipped.** Gamma↔theta opposite sign & correlated magnitude. **Gamma = realized‑vol view; vega = implied‑vol view** — keep them mentally separate. Position‑level breakeven IV = entry vol + edge/vega.

---

## Chapter 8 — Dynamic Hedging (the heart of this batch)

### Why a model needs dynamic hedging
A theoretical pricing model is **probability‑based**: even with perfect inputs, any single trade can deviate (often a lot) from predicted P&L; only **over many trades** does realized ≈ predicted. The trick to make ONE option trade behave like the long‑run average: treat the option's life as a **series of bets** rather than one bet — by **continuously re‑hedging to delta‑neutral**, you replicate long‑term probability theory on a single position. (This is the path‑replication intuition behind Black‑Scholes.)

### The stock example, walked end to end (Figures 8‑1, 8‑2, 8‑3)
**Setup:** Stock 97.70, June expiry in 10 weeks, r = 6%, **assumed/known future realized vol = 37.62%**. June‑100 call: **theoretical value 5.89** (at 37.62% vol) but **market price 5.00** (which corresponds to **implied vol 32.40%**). The call is **underpriced by 0.89** → **buy it** and hedge.

**Establish the neutral hedge:** call delta = 50. Buy **100 calls** (+5,000 deltas), sell **50 underlying** (−5,000 deltas) ⇒ delta‑neutral. (One stock "contract" = 100 shares, so this = short 5,000 shares.)

**Rebalancing logic (why gamma forces it):** each week, recompute the delta from the new spot, new (shorter) time, **same** r and **same** vol (models assume r and σ constant over the option's life). The option's delta drifts because of **gamma**; the underlying's delta is frozen at 100. So a mismatch ("unhedged amount") opens up, and you trade underlying to zero the net delta again. Each rebalance = "end one bet, start the next," and **every new bet depends only on realized vol, not direction.** These rebalancing trades are **adjustments** — they have **zero theoretical edge** (underlying has no theoretical value to an option trader); their sole purpose is to keep the hedge neutral.

Week‑by‑week (Fig 8‑1, weekly intervals chosen "because 10 lines fit on a page"):
| wk | spot | call Δ | total Δ before adj | adjustment |
|----|------|--------|--------------------|------------|
| 0 | 97.70 | 50 | 0 | — (short 50) |
| 1 | 99.50 | 54 | +400 | sell 4 |
| 2 | 92.75 | 35 | −1900 | buy 19 |
| 3 | 95.85 | 43 | +800 | sell 8 |
| 4 | 96.20 | 43 | 0 | none |
| 5 | 102.45 | 62 | +1900 | sell 19 |
| 6 | 93.30 | 28 | −3400 | buy 34 |
| 7 | 91.15 | 17 | −1100 | buy 11 |
| 8 | 95.20 | 27 | +1000 | sell 10 |
| 9 | 102.80 | 72 | +4500 | sell 45 |
| 10 | 103.85 | (expiry) | — | buy in 22 |

**Notice the mechanic:** spot up → delta goes **positive** → you **sell** underlying (sell high); spot down → delta **negative** → you **buy** underlying (buy low). Being **long gamma forces you to systematically buy low / sell high** — that is literally where the money comes from.

**P&L decomposition (Figure 8‑2), book's numbers:**
- **Original hedge: −422.50.** Option: 100·(3.85 − 5.00) = **−115.00** (calls worth 3.85 intrinsic at expiry vs 5.00 paid). Stock: 50·(97.70 − 103.85) = **−307.50** (sold at 97.70, bought back at 103.85). *Looks like a disaster.*
- **Adjustments: +467.55** — the cash flow from all the buy‑low/sell‑high rebalances. **This is the engine; it more than offsets the original‑hedge loss.**
- **Carry on the options: −5.75** = 100·(−5.00)·6%·70/365 (financing the 500 outlay for 70 days).
- **Carry on the stock: +56.21** = 50·(+97.70)·6%·70/365 (interest earned on short‑sale proceeds).
- **Interest on the adjustments: −5.27/−5.28** (net of weekly credits/debits, each carried to expiry).
- **Total cash flow = +90.24** (at week 10). **Discount back:** 90.24 / (1 + 0.06·70/365) = **89.21**.
- **Predicted P&L = 100·(5.89 − 5.00) = +89.00.** Realized **89.21 ≈ predicted 89.00.** ✅ The dynamic hedge **captured the mispricing**, almost exactly.

Two positive components (adjustments, stock interest), three negative (original hedge, option carry, adjustment interest) — but **which components win is random ex ante** (you could construct a case where the original hedge profits and adjustments lose). All that's guaranteed (with correct inputs) is the **sum** ≈ model prediction. The 10 weekly returns were engineered to annualize to exactly 37.62% (Appendix B).

### The "race" framing & the realized‑vs‑implied result (THE KEY TAKEAWAY)
The hedge is a **race between the option's time decay (theta) and the cash thrown off by adjustments (gamma harvest)**, with the pricing model as referee:
- If you **bought** the option **below** theoretical value, the **adjustments win** the race → profit.
- If you bought **above** value, **time decay wins** → loss.

Stated as vol: the hedge's **breakeven volatility = the option's implied vol at the trade price (32.40%)**.
- If **realized vol > 32.40%** ⇒ bigger/more frequent price swings ⇒ more & larger adjustments ⇒ **profit** (consistent with "higher vol ⇒ options worth more").
- If **realized vol < 32.40%** ⇒ fewer/smaller swings ⇒ smaller adjustment harvest ⇒ **loss**.

> **The central result of the chapter (and of practical options trading):** a **delta‑hedged long option position's P&L ≈ a function of REALIZED vol minus IMPLIED vol.** **Long gamma profits when realized > implied** (you bought "cheap" vol and the world delivered more movement than you paid for); **loses when realized < implied.** A short‑gamma (sold‑option) position is the mirror: it profits when realized < implied (collects more theta than it pays out in re‑hedge slippage) but carries the negative‑convexity tail risk of a big move.

### Frictionless‑market assumptions & real‑world frictions
Model assumes: (1) freely buy/sell underlying, (2) borrow/lend unlimited at one constant rate, (3) zero transaction costs, (4) no taxes. Reality breaks all four:
- **Short sales** may be restricted; you rarely earn **full** interest on short proceeds.
- **Futures limit‑up/down** can lock the market (can't trade the underlying freely).
- **Different rates** for different participants; **borrow rate > lend rate** (a spread). But rho is the least important input, so this perturbs P&L only mildly.
- **Transaction costs** are the real bite — they can eat the entire edge, and they **scale with adjustment frequency**.

### How often to rehedge? (the gamma/theta/cost tradeoff in practice)
Continuous rehedging is the theoretical ideal (infinite bets → exact replication of the option value); impossible in reality. Two practical schemes: **(a) fixed time intervals**, or **(b) rehedge when delta drifts past a preset threshold** (e.g. accept up to ±500/±1000/±1500 deltas — with a ±1000 band you'd skip the wk‑1/+400, wk‑3/+800, wk‑8/+1000 adjustments).
- **More frequent adjustment ⇒ realized result hugs the model prediction more tightly**, but ⇒ **more transaction cost.**
- **Adjusting does NOT change expected return** — it only **smooths** (reduces variance of) the outcome by forcing more bets at the same favorable odds. A retail customer (high costs) adjusts less, accepts more luck‑driven dispersion, but **same long‑run EV** as the pro (who adjusts often because his costs are tiny — plus the pro's real edge is buying bid / selling ask).

### You don't always have to hold to expiry
If **implied vol re‑rates** from 32.40% up toward your realized forecast 37.62%, the call price rises 5.00 → 5.89; **sell the calls and unwind the underlying** (underlying price is unaffected by IV — IV is an option property) to bank the full **+89.00 immediately**, no need to hold 10 weeks. Holding shorter also cuts the risk of input error over time. But IV may **not** re‑rate (or may move **against** you first — e.g. IV dips 32.40→30.35%, call 5.00→4.65, instant −35.00). If your **realized‑vol** forecast is right, hold and adjust anyway — by expiry you still collect the +89.00. **You can rarely pick the exact top/bottom in implied vol any more than in price; an adverse IV move with a correct realized‑vol thesis is just noise to sit through.**

### The futures put example (Figures 8‑4/8‑5) — confirms it the other way
**Sell** an **overpriced** option. Futures 61.85, March expiry 10 wks, r = 8%, known realized vol **21.48%**. March‑60 put: **theoretical 1.46**, **price 1.70** (**IV 23.92%**), delta −35. **Sell 100 puts** (delta −35 ⇒ +3,500 position delta from short puts) and **sell 35 futures** to neutralize. Rehedge weekly. Difference vs the stock case: futures use **futures‑type settlement** → no upfront cash, but **variation** cash flows (and interest on them) replace the "interest on stock + interest on adjustments" lines. Result (Fig 8‑5): original hedge **+144.40** (option +31.00, futures +113.40), adjustments **−122.01**, option carry **+2.61**, variation interest **−0.67** ⇒ total **+24.33**, discounted **23.96 ≈ predicted 100·(1.70−1.46) = 24.00.** ✅ Here the original hedge profited and adjustments lost — opposite split from the stock case, **same matched total.**

### The replication principle (chapter's closing law)
> **An option position can be replicated by a dynamic hedging process. The cost of replication = the sum of all cash flows from that process; the present value of that sum = the option's theoretical value.** Buying a call and delta‑hedging it = synthetically *selling* that call at fair value; selling a put and delta‑hedging = synthetically *buying* it at fair value.

**Ch8 — what a quant should remember:**
- **Delta‑hedged option P&L ≈ realized vol vs implied vol.** Long gamma wins iff realized > implied; the option's **implied vol = the hedge's breakeven realized vol.** This is the single most important practical sentence in the book.
- **Gamma is what forces re‑hedging** (option delta drifts, underlying delta is fixed at 100); long gamma ⇒ you mechanically **buy low / sell high** and that harvest ≈ the option's value; short gamma ⇒ you're forced to buy high / sell low (pay the harvest) but pocket theta.
- The famous P&L identity in continuous time (book states it numerically, not symbolically): dynamic hedging P&L over a step ≈ **½·Γ·S²·(σ_realized² − σ_implied²)·dt** style term `(NOT IN THIS BATCH as a formula — the book demonstrates it via the cash‑flow table; flagged so I don't claim the eq. appears verbatim here)`.
- Adjustment frequency trades **variance of outcome vs transaction cost**, and does **not** move expected return. Continuous hedging → exact replication (idealized).
- Rho/interest is the small term; transaction costs and the realized‑vs‑implied gap dominate.
- You can monetize early if IV converges to your realized forecast; otherwise hold-and-adjust to expiry still pays the predicted edge if your vol call is right.

---

## Chapter 9 — Risk Measurement II (PARTIAL — only the Delta section is in this batch)

> The file ends at p.140 / Fig 9‑6. Only **Delta's** behavior vs vol & time (and the second‑order names vanna & charm) is present. Gamma/Theta/Vega‑behavior and Lambda are flagged as next‑batch below.

**Opening principle:** *nothing stays constant.* The sensitivities themselves move as market conditions move — today's small risk is tomorrow's big risk — so risk must be re‑examined across a range of spot/time/vol scenarios, not just at today's snapshot.

### Delta vs **volatility** (Figures 9‑1, 9‑3)
As **volatility rises**, **all** deltas migrate **toward 50** (puts toward −50):
- **OTM** call delta **rises** toward 50 (higher vol ⇒ better chance it reaches ITM).
- **ITM** call delta **falls** toward 50 (higher vol ⇒ better chance it falls back OTM).
- **ATM** delta stays ≈ 50 regardless of vol (though it edges **slightly up** with vol because of lognormality / forward‑pricing; an at‑the‑forward call is already a hair above 50).
As **volatility falls**, deltas spread **away from 50** toward 0 (OTM) or 100 (ITM) — the option becomes more "binary."

**Practical consequence — delta is only as good as your vol guess.** The delta you compute *depends on the volatility input*, which is an unknowable future number; **guess the vol wrong and your delta (hence your "neutral" hedge) is wrong.** Many traders therefore use the **implied delta** (delta computed at the *implied* vol). Then the delta — and thus the hedge — **shifts as implied vol changes even if spot is unchanged.**
- *Worked (book):* own 40 calls, implied delta 25 each → 40·25 = 1,000 → sell 10 underlying to be neutral. If IV rises 32%→36%, deltas drift toward 50, say to 30 each → new position delta = 40·30 − 10·100 = **+200**. **The position silently went from neutral to bullish with no move in the underlying** — purely from the vol change. For a large book, computing "the" delta is genuinely hard because it's vol‑dependent and vol is unknown.

### Delta vs **time** (Figures 9‑2, 9‑4, 9‑5)
Time acts like volatility: **more time = higher vol** (both raise the chance of large moves), **less time = lower vol**.
- **More time to expiry ⇒ deltas migrate toward 50** (OTM up, ITM down).
- **Less time ⇒ deltas spread toward 0 / 100** — and near expiry this happens **fast**, because one day is a large fraction of remaining life.
- **Heuristic:** if you can't reason out the effect of changing *time* on some option quantity, reason about changing *volatility* instead — they usually act the same way (and vice‑versa).
- **Consequence:** a delta‑neutral book today **need not be neutral tomorrow even with spot, vol, rates all unchanged** — pure time passage re‑shapes deltas. Far from expiry this drift is slow; close to expiry it's dramatic.

### Second‑order names introduced here: **Vanna** and **Charm**
- **Vanna** = sensitivity of **delta to a change in volatility** (= ∂Δ/∂σ = ∂Vega/∂S). A 2nd‑order Greek.
- **Charm** (a.k.a. **delta decay**) = sensitivity of **delta to the passage of time** (= ∂Δ/∂t). Also 2nd‑order.
- Footnote framing: **gamma, vanna, charm are the three second‑order sensitivities of delta** — to underlying, vol, and time respectively (∂Δ/∂S, ∂Δ/∂σ, ∂Δ/∂t).
- **Where vanna/charm are largest (Figs 9‑6/9‑7):** identical shape for calls and puts; **≈ 0 around delta 50 / −50**, and **greatest near deltas ~20 and ~80** (puts ~−20/−80) — i.e. the "wing" options whose deltas have the most room to race toward 50 (on a vol/time increase) or away from 50 (on a vol/time decrease). Options already pinned near 0, 50, or 100 barely move.
- **Vanna falls as vol rises** (rises as vol falls); **charm falls with more time to expiry** (rises with less time). Cross‑effects are weak: **vanna is driven by vol but barely by time; charm is driven by time but barely by vol.** (Subtle note: vanna is actually 0 at a delta slightly above 50 / below −50, due to the asymmetry of the lognormal distribution.)

**Ch9 (Delta portion) — what a quant should remember:**
- **Higher vol OR more time pushes every delta toward 50; lower vol OR less time pushes deltas to the 0/100 extremes.** ATM ≈ 50 throughout (a touch above 50 from lognormality). Time and vol are interchangeable intuition tools.
- **"Delta neutral" is conditional on a vol assumption and on "now."** It decays with time (charm) and shifts with implied vol (vanna). Re‑hedging isn't only a response to *price* moves — vol moves and time alone re‑bias the book. Using **implied delta** is one (imperfect) discipline for this.
- Vanna/charm bite hardest on **~20/~80‑delta wing options**, not ATM.

---

## ⚠️ Material the task asked for that is NOT in this batch (truncated past p.140)

`(NOT IN THIS BATCH — file cuts at Figure 9‑6. The following are the standard Natenberg ch9 results that appear in the NEXT batch file; recorded here for completeness and explicitly flagged as not verbatim from 02b. Verify against the source batch that continues ch9.)`

- **Gamma behavior:** for a given expiry, **gamma peaks at‑the‑money**; **ATM gamma rises sharply as expiration approaches** (short‑dated ATM options are the highest‑gamma instruments) and is **low/flat for deep ITM/OTM**. Across vol: **higher vol lowers and broadens** the ATM gamma peak (spreads gamma across strikes); **lower vol makes a tall, narrow** ATM spike. **(verify against next batch.)**
- **Theta behavior:** mirrors gamma in magnitude (gamma↔theta opposite sign, correlated size). **ATM theta is most negative and grows in magnitude into expiry** (the −0.03→−0.06→−0.16 progression from ch7). Deep ITM/OTM theta is small. **(verify.)**
- **Vega behavior:** **vega peaks at‑the‑money** and **increases with time‑to‑expiration** (long‑dated options carry the most vega; vega → 0 at expiry). Roughly flat‑ish vs vol level near ATM but the wings' vega rises with vol. So **gamma/theta are a short‑dated‑ATM story; vega is a long‑dated‑ATM story.** **(verify.)**
- **Lambda (Λ) — leverage / elasticity:** **Λ = Δ · (S / option price)** = the percentage change in the option's value for a 1% change in the underlying = the option's built‑in **leverage/elasticity**. OTM options have the **highest lambda** (small price, modest delta ⇒ huge % swings); deep‑ITM options have lambda → 1 (behave like the underlying). Lambda is **not** constant — it changes with spot, vol, and time. **(NOT IN THIS BATCH — definition is the standard Natenberg one; verify the exact wording/figure in the continuing batch.)**

---

## Batch 2B — top lessons

1. **THE headline result (ch8): a delta‑hedged option's P&L ≈ ½·Γ·S²·(realized² − implied²) integrated over the trade** — practically, **long gamma makes money iff REALIZED vol > IMPLIED vol you paid; short gamma makes money iff realized < implied.** The option's **implied vol is exactly the breakeven realized vol** of the hedge. Trading options = trading the realized‑vs‑implied vol spread. *(The ½ΓS²(σ²−σ²) formula itself is standard; this batch proves it via the cash‑flow table, not as an equation — flagged.)*
2. **Gamma is the engine of dynamic hedging.** The option's delta drifts (because Γ≠0) while the underlying's delta is frozen at ±100; closing that drift = re‑hedging. **Long gamma ⇒ forced to buy‑low/sell‑high** (the adjustment cash flow ≈ the option's value); **short gamma ⇒ forced to sell‑low/buy‑high**, paying that harvest but collecting **theta** in return.
3. **Gamma/theta tradeoff is unavoidable and opposite‑signed:** long gamma = pay theta (bleed time value, want movement); short gamma = collect theta but eat negative convexity (want stillness, fear the gap). You cannot be paid by both movement and time at once.
4. **Gamma = realized‑vol view; Vega = implied‑vol view.** Same underlying, two different vols. They usually correlate but can diverge — a long‑gamma/short‑vega (or vice‑versa) book is a real, deliberate position.
5. **Re‑hedging frequency changes variance, not expected value.** Continuous = exact replication (ideal); discrete/threshold hedging just smooths luck. Real‑world limiter is **transaction cost** (scales with frequency), not EV. Rho/interest is the small term.
6. **Replication law:** any option = a dynamic‑hedging cash‑flow stream whose PV equals the option's theoretical value. Buy‑and‑hedge a call = synthetically sell it at fair value, and vice‑versa.
7. **Greeks are additive across a book**, and **position‑level breakeven IV ≈ entry vol + (total edge / total vega).** A position can drift to negative edge as markets move — when it does, close it; time only compounds the expected loss.
8. **"Delta‑neutral" is fragile (ch9 Delta section):** delta depends on a *guessed* future vol, and it **moves with implied vol (vanna)** and **decays with time (charm)** even when spot doesn't move. Higher vol or more time → deltas toward 50; lower vol or less time → deltas toward 0/100, fast near expiry. Vanna/charm bite hardest on ~20/~80‑delta wings. Use **implied delta** as one discipline.
9. **Time ≈ volatility as an intuition shortcut** throughout ch9: if a time effect is unclear, reason about the analogous vol effect (both raise the odds of big moves).
10. **(Carried in from ch8, applies to live trading):** you can bank the edge early if IV converges to your realized forecast (sell the option, unwind the hedge) — IV is an option property, the underlying price is unaffected. If IV instead moves against you but your realized‑vol thesis is right, hold‑and‑adjust still pays the predicted P&L by expiry.

> **Coverage caveat repeated:** the Gamma/Theta/Vega‑peaking detail and **Lambda Λ** requested by the task are **not in `02b`** (file ends at Fig 9‑6); they're recorded above under the flagged "NOT IN THIS BATCH" section and should be confirmed against the next batch file that continues ch9.