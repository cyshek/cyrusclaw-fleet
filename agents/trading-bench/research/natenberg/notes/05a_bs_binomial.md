# Batch 5A — Black-Scholes & Binomial Option Pricing

Source: Natenberg, *Option Volatility and Pricing*, ch18 (The Black-Scholes Model) + ch19 (Binomial Option Pricing).
Layout-extracted PDF; d1/d2, exponents, and σ reconstructed to standard forms. Ambiguities flagged "(verify: …)".

Notation note: Natenberg uses **X** for strike (this doc keeps both X and K interchangeably; the task brief uses K). Uses **t** = time to expiry in years, **σ** = annualized vol, **r** = interest rate, **e** = exp, **ln** = natural log, **N()** = cumulative standard normal, **n()** = standard normal density (pdf).

---

## Chapter 18 — The Black-Scholes Model

### What the model is solving for
Black & Scholes did NOT start by asking "what is the option worth." They asked: **if the stock moves randomly over time at a constant interest rate and volatility, what must the option price be at each instant so that a correctly (delta) hedged option position just breaks even?** Solving that no-arbitrage condition yields the model.

### The Black-Scholes PDE (the differential equation)
Plain-text reconstruction of the partial differential equation:

```
r*S*(∂C/∂S) + 0.5*σ^2*S^2*(∂²C/∂S²) + (∂C/∂t) = r*C
```

- `∂C/∂S` = **delta (Δ)**, `∂²C/∂S²` = **gamma (Γ)**, `∂C/∂t` = **theta (Θ)**.
- Interpretation: change in option value depends on sensitivity to underlying (delta), sensitivity of delta to underlying (gamma), and sensitivity to time (theta).
- Interest-rate term plays TWO roles: (1) `r*S` carries spot → forward; (2) `r*C` discounts the expected value back to present value.
- Volatility term `0.5*σ^2*S^2*(∂²C/∂S²) = 0.5*σ^2*S^2*Γ` — the gamma's effect scaled by how fast price moves (variance).
- **σ and r are inputs, NOT variables in the PDE** — only S and t change over the option's life; everything else is held constant (matches the dynamic-hedging framing of ch8).

### ASSUMPTIONS of Black-Scholes (the standard list — assembled from the chapter)
1. The underlying price moves **randomly/continuously** over time (a continuous diffusion; no jumps).
2. Returns are **lognormally distributed** → terminal prices lognormal; log-returns normal.
3. **Volatility (σ) is constant** and known over the life of the option.
4. **Interest rate (r) is constant** and known; can borrow/lend freely at r.
5. The option is **European** (no early exercise — closed form prices European only).
6. Original form: underlying is a **non-dividend-paying stock** (later extended via the carry term b — see below).
7. **Continuous, frictionless, costless dynamic hedging** is possible (no transaction costs, continuous rebalancing; this is what makes the hedged position break even). [The crash-of-1987 portfolio-insurance discussion in ch17 is essentially a warning that THIS assumption fails in real markets.]
8. No arbitrage; markets are continuous (you can always trade/hedge).
   - (verify: Natenberg presents these intuitively across ch18 rather than as a single numbered box; constant-σ, constant-r, lognormal, European, continuous hedging are stated explicitly. No-taxes / infinitely-divisible-shares are standard textbook BS assumptions implied but not spelled out here.)

### The formula structure (plain text)
For a European **call** on a non-dividend-paying stock:

```
C = S*N(d1) - X*e^(-r*t)*N(d2)
```

(Task's form with K: `Call = S*N(d1) - K*e^(-r*t)*N(d2)` — identical, X≡K.)

**Put** via put-call parity:

```
P = X*e^(-r*t)*N(-d2) - S*N(-d1)
```

with d1, d2:

```
d1 = [ ln(S/X) + (r + 0.5*σ^2)*t ] / ( σ*sqrt(t) )
d2 = d1 - σ*sqrt(t)
   = [ ln(S/X) + (r - 0.5*σ^2)*t ] / ( σ*sqrt(t) )
```

These match the task-supplied forms exactly. (Natenberg's raw text drops some parentheses in the numerator — `ln(S/X) + r + (σ²/2) t` — but the standard, correct grouping is `(r + σ²/2)*t`, confirmed by his Figure 18-5 breakdown and the put column of Figure 18-6.)

### Put-call parity derivation (how the formula's pieces arise)
Parity (continuous compounding): `C - P = S - X*e^(-r*t)` (from `C - P = (F - X)/(1+r*t)` with `F = S*(1+r*t)`, then swapping simple interest `1/(1+r*t)` for continuous `e^(-r*t)`).
- The European-call lower arbitrage bound is `max(0, S - X*e^(-r*t))`. The BS formula is exactly this bound but with **N(d1) attached to S** and **N(d2) attached to X*e^(-r*t)** — the N() terms are the probability weights that turn the bound into the fair value.

### What d1, d2 mean (the intuition Natenberg builds)
BS reframes pricing as two separate questions:
1. **If held to expiration, what is the average value of all stock that finishes above the strike?** → answered by `S*e^(r*t)*N(d1)` = (forward price) × N(d1) = average value of stock above X.
2. **What is the probability the option finishes ITM (you actually pay the strike)?** → answered by `N(d2)`; `X*N(d2)` = average amount paid at expiration.

Expected value at expiration = `S*e^(r*t)*N(d1) - X*N(d2)`. Discount by `e^(-r*t)` to get present value → `S*N(d1) - X*e^(-r*t)*N(d2)`. (i.e. `S*e^(r*t)*N(d1)` × e^(-r*t) = S*N(d1).)

Building d1 piece by piece (Figure 18-5):
- `ln(S/X)` — relationship of underlying to strike in lognormal space (>0 ⇒ ITM call, <0 ⇒ OTM).
- `+ r*t` — spot→forward carry adjustment (options valued off the forward). Equivalent to replacing S with forward `S*e^(r*t)`: `ln(S/X) + r*t = ln(S*e^(r*t)/X)`.
- `+ σ²*t/2` — shifts to the **mean** of the lognormal distribution (the lognormal's elongated right tail puts the mean to the right of the mode; shift = σ²t/2).
- divide by `σ*sqrt(t)` — the **normalization factor**: one standard deviation over time t is `σ*sqrt(t)`, so dividing converts the gap into a number of standard deviations.

**d2 = d1 - σ*sqrt(t)** locates the **median** of the lognormal (median sits σ*sqrt(t) to the LEFT of the mean). `N(d2)` uses the median to give the true probability of finishing ITM / being exercised.

### Why N(d1) = delta of a call
- In BS, the call **delta = N(d1)** (for the b=r stock case; general carry: `Δ_call = e^((b-r)*t)*N(d1)`).
- Earlier (ch7) delta was approximated as "the probability the option finishes ITM" — but the *true* ITM probability is **N(d2)**, not N(d1).
- N(d1) is the factor on S (the average-stock-above-strike term). Mathematically it's also the option's sensitivity to S → the delta. **N(d1) is ALWAYS larger than N(d2)** (since d1 > d2), though they're close for short-dated options.
- Consequence: an at-the-**forward** call has delta slightly > 50; put delta = call delta − 100, so put delta is slightly < −50 in absolute value ⇒ an at-the-forward **straddle has a positive delta**. The straddle is exactly delta-neutral when d1 = 0, i.e. forward `S = X*e^(-(r+σ²/2)*t)` (forward sits below the strike, and that gap grows with time/vol). (verify: text prints `S = Xe^(−r+(σ²/2)t)` ambiguously; correct delta-neutral condition is d1=0.)

### Role of N() as the cumulative normal
- `n(x)` = **standard normal density** (pdf): bell curve, mean 0, sd 1; total area under it = 1. Its peak value ≈ **0.398942** (≈0.399) at x=0.
- `N(x)` = **standard cumulative normal** (CDF): area under n() from −∞ to x = P(occurrence < x standard deviations).
- Key values: `N(−∞)=0`, `N(+∞)=1`, `N(0)=0.5`, and the symmetry identity **`N(x) = 1 − N(−x)`**.
- BS computes everything with NORMAL probabilities; the lognormal-ness of prices is handled by feeding `ln(S/X)`-based, mean/median-adjusted arguments (d1, d2) into N().

### What each input does to the price
- **S (underlying/spot)** ↑ → call ↑, put ↓ (call delta positive, put delta negative).
- **X / K (strike)** ↑ → call ↓ (harder to finish ITM), put ↑.
- **r (interest rate)** ↑ → call ↑, put ↓ (raises the forward; discounts the strike you pay more heavily). This is **rho**: `ρ_call = +t*X*e^(-r*t)*N(d2)`, `ρ_put = −t*X*e^(-r*t)*N(-d2)` (for b≠0).
- **t (time to expiry)** ↑ → generally both calls AND puts ↑ (more time value / wider terminal distribution). Caveat from ch18: for stock options with r>0, since the forward moves with time, **vega can actually DECREASE with more time** under high rates (e.g. r=20% ⇒ vega declines beyond ~10 months); not strictly monotonic.
- **σ (volatility)** ↑ → both calls AND puts ↑ (wider distribution ⇒ more upside for the holder, downside truncated at 0). This is **vega**: `vega = S*e^((b-r)*t)*n(d1)*sqrt(t)` (same for calls & puts). ATM vega is roughly constant in σ but declines slightly as σ rises.
- **dividends (q)** ↑ → call ↓, put ↑ (dividends lower the forward; holder of a call misses the dividend). Handled by discounting S or via the carry term b = r − q.

### The carry term b (generalizing BS — Figure 18-6)
Full form:
```
C = S*e^((b-r)*t)*N(d1) - X*e^(-r*t)*N(d2)
P = X*e^(-r*t)*N(-d2) - S*e^((b-r)*t)*N(-d1)
d1 = [ ln(S/X) + (b + σ²/2)*t ] / (σ*sqrt(t)),   d2 = d1 - σ*sqrt(t)
```
- **b = r** → original Black-Scholes, options on (non-dividend) **stock**.
- **b = 0** → **Black model**, options on **futures** (stock-type settlement; futures have no carry).
- **b = r − rf** → **Garman-Kohlhagen**, options on **FX** (rf = foreign rate).
- **b = r = 0** → BS for futures options with futures-type settlement.
- Dividend-paying stock: set **b = r − q** (q = annual dividend yield), or more exactly subtract PV of each discrete dividend from S: `S → S − ΣD_i*e^(r*t_d)` (t_d = time from each dividend to expiry).

### Useful no-computer approximation (the "40% rule")
For an **exactly at-the-forward European option** (F = X), expected value ≈
```
X * (σ*100) * sqrt(t) * 0.00399
```
and theoretical value = that ÷ (1+r*t) (or × e^(-r*t)).
- The magic number **0.00399 = n(0)/100 ≈ 0.398942/100** (peak of the standard normal, scaled because 1 vol point = 1/100 of a sd).
- Often rounded to 0.004 → **40% rule**: an at-the-forward option's value ≈ 40% of one standard deviation, where 1 sd = `F*σ*sqrt(t)`.
- Holds for both call and put (parity: at-the-forward call = put). Approximation runs slightly HIGH for large σ/long t (because ATM vega drifts down with σ, magnified by time).

### Maximum gamma / theta / vega (critical underlying prices, b-general)
- Delta = 50 at `S = X*e^((-b - σ²/2)*t)` (verify sign: text prints `S = Xe^((−b−σ²/2)t)`).
- Max **gamma** at `S = X*e^((-b - 3σ²/2)*t)`.
- Max **theta** at `S = X*e^((b + σ²/2)*t)`.
- Max **vega** at `S = X*e^((-b + σ²/2)*t)`.
- At b=0: max gamma & theta occur at the SAME underlying (above the strike); max vega below the strike. These are only at the exact strike in the idealized at-the-money approximation.

### Theta decomposition (3 effects of time passing)
```
Θ = -[S*e^((b-r)*t)*n(d1)*σ] / (2*sqrt(t))   ← volatility-value decay ("driftless theta")
    + (b-r)*S*e^((b-r)*t)*N(d1)              ← spot drifting toward forward
    - r*X*e^(-r*t)*N(d2)                      ← change in PV of expected payout
```
- First term (volatility decay) is the same sign for calls and puts and **usually dominates**.
- If r=0 or futures-type settlement, terms 2 & 3 vanish → only the **driftless theta** remains.
- Theta formula in Figure 18-6 is per-year; divide by 365 for daily decay.

### **Ch18 — what a quant should remember**
- BS = closed-form price for a **European** option derived from a **no-arbitrage, continuously-delta-hedged** argument; price is the discounted risk-neutral expected payoff.
- Memorize: `C = S*N(d1) - X*e^(-r*t)*N(d2)`; `P = X*e^(-r*t)*N(-d2) - S*N(-d1)`; `d1 = [ln(S/X)+(r+σ²/2)t]/(σ√t)`; `d2 = d1 - σ√t`.
- **N(d2) = true probability of finishing ITM (risk-neutral); N(d1) = call delta** (always N(d1) > N(d2)). Don't conflate them.
- d1's pieces: log-moneyness + carry-to-forward + lognormal-mean shift (σ²t/2), all normalized by 1 sd = σ√t. d2 steps from mean to median (−σ√t).
- The single closed form generalizes via carry **b**: b=r stock, b=0 futures (Black), b=r−rf FX (Garman-Kohlhagen), b=r−q dividend stock.
- Greeks fall out as partial derivatives: Δ=N(d1)·e^((b-r)t), Γ & vega identical for call/put, vega = S·e^((b-r)t)·n(d1)·√t, ρ scales with t·X·e^(-rt)·N(d2).
- The model breaks when its assumptions break — constant vol, continuous costless hedging (the 1987 portfolio-insurance failure is the canonical real-world counterexample).

---

## Chapter 19 — Binomial Option Pricing

Cox-Ross-Rubinstein (CRR) model, 1979 — a discrete-tree way to teach/compute option pricing without advanced math, and (crucially) able to price **American** options that closed-form BS cannot.

### Risk-neutral probability (the core idea)
Stock at S can go to Su (up) or Sd (down) next period. For an investor to be **indifferent** to buying vs selling (risk-neutral world), the expected value must equal the no-arbitrage forward, NOT the real-world expected value. With no carry the expected value just equals S:
```
p*Su + (1-p)*Sd = S    →    p = (1 - d)/(u - d)
```
For a non-dividend stock you must match the **forward** `S*(1+r*t)`:
```
p*Su + (1-p)*Sd = S*(1+r*t)   →   p = [ (1 + r*t) - d ] / (u - d)
```
Per-period (n periods of length t/n), discrete-compounding form Natenberg uses:
```
p = [ (1 + r*t/n) - d ] / (u - d),     1 - p = (u - p... )  [= 1 - p]
```
Continuous-compounding / carry-general standard CRR form (equivalent):
```
p = ( e^(b*t/n) - d ) / (u - d)      [task-brief form: p = (e^(r*t) - d)/(u - d) for a single period, b=r]
```
- **p is a RISK-NEUTRAL ("pseudo") probability, not a real-world probability.** It's the probability that makes the discounted expected payoff arbitrage-free. Real-world up/down odds never enter pricing.
- Worked example: S=100, up to 120 / down to 90 (u=1.20, d=0.90), no carry → p = (1−0.90)/(1.20−0.90) = 0.10/0.30 = **1/3**. Check: ⅓·120 + ⅔·90 = 40+60 = 100. ✓

### Up/down factors u and d (linking the tree to volatility)
Choose u and d so the tree (a) **recombines** and (b) is **driftless**:
- **u·d = 1** (u and d are multiplicative inverses) → an up-then-down (or down-then-up) returns to the start price; no drift. (If instead u=1.25, d=0.75, then u·d=0.9375 ⇒ a downward drift — bad.)
- Recombining means `u·d = d·u`, so terminal price depends only on the NET number of up moves, not the path → number of nodes grows linearly, not exponentially.
- To match a lognormal (so binomial → BS), set u/d to a **one-standard-deviation move per step**:
```
u = e^( σ*sqrt(t/n) )        d = 1/u = e^( -σ*sqrt(t/n) )
```
- Back out the implied vol from a chosen u: e.g. n=3, t=0.75, u=1.05 → 1.05 = e^(σ√(0.75/3)) = e^(0.5σ) → ln(1.05)=0.5σ → σ ≈ **9.76%**.

### Valuing a European option on the tree (forward / closed binomial form)
Terminal payoff at expiration = intrinsic: call `max(S - X, 0)`, put `max(X - S, 0)`. Terminal prices are `S*u^j*d^(n-j)` for j=0..n; number of paths to each = the binomial coefficient `n! / (j!(n-j)!)`. Value = PV of probability-weighted terminal payoffs:
```
Call = (1/(1+r*t/n)^n) * Σ_{j=0..n} [ n!/(j!(n-j)!) * p^j * (1-p)^(n-j) * max(S*u^j*d^(n-j) - X, 0) ]
Put  = (1/(1+r*t/n)^n) * Σ_{j=0..n} [ n!/(j!(n-j)!) * p^j * (1-p)^(n-j) * max(X - S*u^j*d^(n-j), 0) ]
```
- One-period: `C = [ p*max(Su-X,0) + (1-p)*max(Sd-X,0) ] / (1+r*t)`.
- Two-period middle node Sud has TWO paths (ud and du) → weight `2*p*(1-p)`.

### Backward induction (the practical algorithm)
Instead of summing all paths, **roll back node-by-node**. At any node value the option as the discounted risk-neutral expectation of its two children:
```
C[i,j] = ( p*C[i+1,j+1] + (1-p)*C[i+1,j] ) / (1 + r*t/n)
P[i,j] = ( p*P[i+1,j+1] + (1-p)*P[i+1,j] ) / (1 + r*t/n)
```
- Start at the terminal column (set each to intrinsic value), then work LEFT to the root `C[0,0]` = today's theoretical value.
- Worked 3-period example (S=100, t=0.75, r=4%, u=1.05, d≈0.9524, p≈0.59): European 100 call = **5.22**, 100 put = **2.28**. Parity check: forward F = 100·(1+0.75·0.04/3)^3 ≈ 103.03; (F−X)/(1+r·t/n)^n = 3.03/1.0303 = 2.94 = 5.22−2.28. ✓
- Node notation `S[i,j]`: i = step (left→right, 0..n), j = up-moves (bottom→top).

### Risk-neutral valuation intuition (why discounting at r with p works)
- The binomial tree reproduces the **dynamic-hedging / replication** result of ch8: buy the option at theoretical value, sell Δ of stock to be delta-neutral, and over one step you break **exactly even** whether the stock goes up or down — once you include interest earned/paid on the hedge's cash flow.
  - Example check (3-period root, Δ=62): up move → +2.53 on option, −3.10 on stock = −0.57; down move → −3.51 on option, +2.95 on stock = −0.56; the cash credit (−5.22 + 0.62·100 = +56.78) earns 1%·56.78 ≈ +0.57 interest, which exactly offsets the loss → break-even.
- Because a delta-hedged option is **riskless** over each step, it must earn the risk-free rate → you can price it AS IF the world were risk-neutral: weight outcomes by p (not real probabilities) and discount at r. That's the whole justification for the formula.
- Greeks fall out of the tree's intermediate node values:
  - Delta: `Δ[i,j] = (C[i+1,j+1] - C[i+1,j]) / (S[i+1,j+1] - S[i+1,j])`.
  - Gamma: `Γ[i,j] = (Δ[i+1,j+1] - Δ[i+1,j]) / (S[i+1,j+1] - S[i+1,j])`.
  - Theta (approx): underlying only returns to itself after TWO steps (up+down), so theta is measured over 2 periods: `Θ_annual[i,j] ≈ (C[i+2,j+1] - C[i,j]) / t`; daily ≈ that ÷ 365. (Natenberg's worked example: C[0,0]=5.22 → C[2,1]=2.92, drop 2.30 over 2 periods = 0.75·365/3·... ⇒ ~91.25 days, daily theta ≈ −2.30/91.25 ≈ −0.0252.)
  - **Vega and rho have NO simple tree arithmetic** — you must re-run the tree with a bumped σ (vega) or bumped r (rho) and difference the values.

### "Gamma rent" (movement needed to offset decay)
- A delta-neutral position taken at fair value breaks even if the underlying moves by exactly u or d — and u, d are defined as a **one-standard-deviation** move per step (`e^(±σ√(t/n))`). So over any interval, the move needed to offset theta ≈ **one standard deviation**. Traders call vol trading "renting the gamma," with the rent = theta. (Only approximate: theta changes as time passes while u,d stay fixed.)

### WHY the binomial tree can value AMERICAN early exercise (BS cannot)
This is the headline advantage. Because backward induction visits **every node**, at each node you can compare the rolled-back "hold" (continuation) value against the **intrinsic value of exercising right now**, and take the larger:
```
American C[i,j] = max( intrinsic[i,j],  (p*C[i+1,j+1] + (1-p)*C[i+1,j]) / (1+r*t/n) )
American P[i,j] = max( intrinsic[i,j],  (p*P[i+1,j+1] + (1-p)*P[i+1,j]) / (1+r*t/n) )
```
- If intrinsic > continuation at a node, **replace** the node value with intrinsic, then keep rolling back — the early-exercise premium propagates toward the root.
- BS gives only a single closed-form for the European payoff and has **no mechanism to test exercise at intermediate times**, so it cannot price American optionality. The tree's node-by-node structure is exactly what supplies that.
- **Worked American put** (same 3-period tree): at node P[2,0], underlying = 90.70, European value = 8.31 but intrinsic = 9.30 → exercise early, replace 8.31 with 9.30. Rolling back: P[1,0] becomes 4.90 (was 4.50 European), and the **American put root = 2.44** vs European 2.28. Early-exercise also shifts the Greeks: American put Δ = −42 (vs −38 European), Γ = 6.1 (vs 5.1).
- **Calls on non-dividend stock: American = European** (never optimal to exercise a call early on a non-dividend stock — confirmed because no node's value falls below intrinsic). **Dividends change this:** a dividend drops the post-dividend tree prices by the dividend amount; a deep-ITM call just before an ex-dividend node can have intrinsic > continuation → early exercise becomes optimal (worked example: American call on a dividend-paying stock exercised early when stock=110.25, intrinsic 10.25 > European 9.26; American call root 4.33 vs European 3.99).

### Dividends on the tree
- Reduce post-dividend node prices by the dividend (its price typically drops by ~the dividend amount). Problem: subtracting a fixed dividend mid-tree makes subsequent nodes **fail to recombine** (each becomes a new sub-tree) → calculations blow up, especially with multiple dividends / many steps.
- Practical approximation: build the full no-dividend tree, then subtract total dividends from each node's price. Only approximate (slightly overvalues vs the exact non-recombining tree), but tractable.

### Pseudoprobabilities (p can leave [0,1])
- p and 1−p are NOT guaranteed to sit in [0,1] — hence "pseudoprobabilities." If u is too small relative to interest (e.g. r=40%, u=1.05): p = (1+0.40·0.75/3 − 0.9524)/(1.05−0.9524) = (1.1−0.9524)/0.0976 ≈ **1.51**, so 1−p ≈ **−0.51**.
- Meaning: the up-move isn't large enough to beat just earning interest in the bank → the no-arbitrage "probability" goes out of range. Requirement for sane p: **u > 1 + r·t/n** (raise volatility/u and p falls back into [0,1]).

### Convergence to Black-Scholes as steps → ∞
- For **European** options, the binomial price converges to BS as n→∞. The error **oscillates** in sign (over/under) but its magnitude shrinks toward 0; an infinite tree gives exactly the BS value.
- Example (S=X=100, t=0.25, σ=9.76%, r=4%): 3-period binomial call=5.22, put=2.28; BS call=5.01, put=2.05 (binomial high). 4-period: 4.79 / 1.84. Error swings + then − with growing n.
- **How many periods?** More steps = more accuracy but cost grows fast (≈ exponentially in compute). Common practical choice: **50–100 periods**.
- **Half-step averaging** trick: average the n-period and (n+1)-period values (a "n½-period" value) to cancel much of the oscillation — e.g. averaging the 9- and 10-period values cut the 100-call error from ~±0.07/0.09 down to ~0.01.

### Carry-general binomial (Figure 19-13)
Same variations as BS via b: `p = [(1 + b*t/n) - d]/(u-d)`; **b=r** stock, **b=0** Black/futures (stock-type settlement), **b=r=0** futures (futures-type settlement), **b=r−rf** FX. (Discount factor stays `(1+r*t/n)^n` using the actual r.)

### **Ch19 — what a quant should remember**
- Binomial (CRR) = discrete lattice; price = **PV of risk-neutral expected payoff**, computed by **backward induction** from terminal intrinsic values.
- Risk-neutral prob **p = (e^(b·t/n) − d)/(u − d)** (or `(1+r·t/n − d)/(u−d)` discrete); it's a no-arbitrage weight, NOT real-world odds. Real probabilities never enter pricing.
- Set **u = e^(σ√(t/n)), d = 1/u** so the tree is recombining (path-independent terminal price) and driftless, and matches a lognormal ⇒ converges to BS.
- **The killer feature: American/early exercise.** At each node take `max(intrinsic, discounted continuation)`. BS can't do this; the lattice can, because it evaluates exercise at every node. Early exercise also alters Δ/Γ.
- Non-dividend stock call: American=European (no early exercise). Dividends create early-exercise value for calls; puts can have early-exercise value generally (deep ITM).
- Greeks read off node values (Δ, Γ, Θ from value differences); **vega/rho require re-pricing with bumped inputs**.
- p can exceed 1 or go negative (pseudoprobabilities) when u is too small vs carry — a modeling red flag, not a real probability.
- Convergence to BS is **oscillating**; use ~50–100 steps, and half-step averaging to damp the oscillation.

---

## Batch 5A — top lessons

1. **Two routes, one answer.** BS (closed form) and Binomial (lattice) both compute the **present value of the risk-neutral expected payoff** under a no-arbitrage, delta-hedged argument. Binomial → BS as steps → ∞ (oscillating, shrinking error). Use BS for fast European pricing; use Binomial when you need American/early-exercise or path/dividend structure.
2. **Memorize the core forms.** `C = S·N(d1) − X·e^(−rt)·N(d2)`, `P = X·e^(−rt)·N(−d2) − S·N(−d1)`, `d1 = [ln(S/X)+(r+σ²/2)t]/(σ√t)`, `d2 = d1 − σ√t`. Binomial: `p = (e^(bt/n) − d)/(u−d)`, `u = e^(σ√(t/n))`, `d = 1/u`, roll back `V[i,j] = (p·V_up + (1−p)·V_down)/(1+rt/n)`.
3. **N(d2) vs N(d1) — don't confuse them.** N(d2) = true risk-neutral probability of finishing ITM. N(d1) = call **delta** (and the weight on S = average stock value above strike). Always N(d1) > N(d2).
4. **d1 is just a standardized moneyness:** log-moneyness `ln(S/X)`, plus carry-to-forward `bt` (or rt), plus the lognormal mean shift `σ²t/2`, all divided by one standard deviation `σ√t`. d2 steps from the distribution's mean to its median (`−σ√t`).
5. **Risk-neutral pricing = hedging.** Both models price by the fact that a continuously delta-hedged option is riskless and must earn r. That's why you weight outcomes by p (not real odds) and discount at r. The binomial break-even arithmetic (option P&L + stock P&L + interest on the hedge cash = 0) is the concrete demonstration.
6. **The lattice's edge is American exercise:** `max(intrinsic, continuation)` at every node — something closed-form BS structurally cannot do. Non-dividend calls have no early-exercise value; dividends (calls) and deep-ITM puts do.
7. **One model, many assets, via carry b:** b=r (stock), b=0 (futures/Black), b=r−rf (FX/Garman-Kohlhagen), b=r−q (dividend stock). Same skeleton for both BS and binomial.
8. **Inputs → price (signs):** S↑ call↑/put↓; X↑ call↓/put↑; σ↑ both↑ (vega, identical call/put); t↑ usually both↑ (but stock-option vega can fall with time at high r); r↑ call↑/put↓ (rho); dividends↑ call↓/put↑.
9. **Know the model's failure modes.** BS assumes constant σ, constant r, continuous frictionless hedging, lognormal returns, European exercise. Real markets violate these (1987 portfolio-insurance blowup = the canonical lesson: dynamic replication got far costlier than the model assumed when vol jumped). Binomial pseudoprobabilities leaving [0,1] is another tell that inputs/assumptions are off.
10. **Practical numerics:** binomial steps 50–100 trade accuracy vs speed; half-step averaging cancels the over/under oscillation cheaply. The "40% rule" (ATM-forward value ≈ `F·σ·√t·0.4`, from n(0)≈0.399) is a fast sanity check without a computer.

*(Math reconstructed to standard textbook forms; items tagged "(verify: …)" are where the PDF's layout dropped parentheses/signs and I restored the conventional grouping rather than inventing precision.)*