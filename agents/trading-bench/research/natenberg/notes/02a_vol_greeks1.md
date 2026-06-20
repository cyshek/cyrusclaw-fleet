# Batch 2A — Volatility (ch6) + Risk Measurement I / the Greeks (ch7, start)

> **Scope note (important):** The batch file `02a_vol_greeks1.txt` actually contains
> **ch5 Theoretical Pricing Models** (tail), **ch6 Volatility** (complete), and only the
> **opening of ch7 Risk Measurement I** — it cuts off mid-**Delta** (the "rate of change"
> interpretation + Fig 7-4/7-5), *before* Gamma/Theta/Vega/Rho are introduced. So:
> Delta is covered from the source text; **Gamma/Theta/Vega/Rho below are filled in from
> Natenberg's standard ch7 treatment** and are marked `[beyond file cut-off]`. ch7 also gives
> the full interest-rate/dividend sign tables (Fig 7-1/7-2/7-3), which ARE in the file.

---

## ch5 recap (tail of file — context for vol)

- An option's theoretical value = **present value of its expected value** at expiration, where
  expected value = Σ pᵢ · (option payoff at price Sᵢ). Call payoff `max(Sᵢ − X, 0)`; put `max(X − Sᵢ, 0)`.
- Black-Scholes needs **5 inputs**: exercise price, time to expiration, underlying price, interest
  rate, **volatility**. (Dividends = 6th, only for stock options that pay one.)
- Arbitrage-free constraint: the expected value of the underlying must equal the **forward price**
  → the forward price is the **mean** of the assumed price distribution. All BS variants
  (Black-Scholes stock / Black futures / Garman-Kohlhagen FX) differ only in *how they compute the
  forward price* and the *settlement procedure*.
- BS is a **continuous-time** model (volatility compounded continuously → lognormal terminal prices).
- Interest rate is the **least important** input in most cases; volatility is the hardest to pin down
  and usually the most important.

---

## ch6 — VOLATILITY

### Core definition
- **Volatility = the annualized standard deviation of (percent / log) returns of the underlying.**
  It is a trader's word for *standard deviation* (σ). It quantifies the **speed** of the market:
  slow market = low vol, fast market = high vol. Direction-agnostic — a symmetric measure of *how
  far* prices spread, not *which way*.
- Working definition Natenberg uses: **the volatility input represents a one-standard-deviation
  price change, in percent, over one year.**

### Normal distribution & the σ probability bands (memorize)
Returns are modeled as a random walk → bell curve. For a normal distribution:

| Range about mean | Probability | Trader fraction |
|---|---|---|
| ±1σ | **68.3%** | ≈ 2/3 |
| ±2σ | **95.4%** | ≈ 19/20 |
| ±3σ | **99.7%** | ≈ 369/370 |

- σ is **additive in units** (if 1σ = 3 troughs, 2σ = 6 troughs).
- Useful trader benchmark: a **>2σ daily move happens ~1 in 20 days ≈ once a month** (≈20 trading
  days/month). A >1σ daily move happens ~1 day in 3.
- **One-tail trick:** because the curve is symmetric, the chance of landing in the *upper* >2σ tail
  alone is half of 1-in-20 = **1 in 40** (used in the "30-to-1 odds is a bad bet" example).

### The √time scaling rule (THE key formula — get this right)
Volatility scales with the **square root of time**, NOT linearly (interest scales linearly; vol does not):

```
σ(period) = σ(annual) × √t          where t is the period length in YEARS
```

Practical conversions (Natenberg's convenience constants):
```
σ_daily  ≈ σ_annual / √(trading days)   ≈ σ_annual / √256  = σ_annual / 16
σ_weekly ≈ σ_annual / √52              ≈ σ_annual / 7.2
```
- He uses **256 trading days** (not 250–260) purely because √256 = 16 is clean. Real count ≈ 250–260.
  (verify: if your model assumes 252 trading days, daily ≈ σ_annual/√252 = σ_annual/15.87 — the
  "/16" is the textbook approximation, not exact.)
- Weeks: there are **52 full trading weeks** (no week is fully closed), so weekly divides by √52 ≈ 7.2.
- To go to **any** horizon: multiply annual σ by √(days/256) or √(weeks/52) or generally √(t in years).
- The same ±1σ/±2σ probabilities (68%/95%) apply at **every** rescaled horizon.

**Worked example (from text):** stock at $45, σ_annual = 37%.
- 1σ daily move ≈ 45 × 0.37/16 ≈ **$1.04** → 1σ day range ≈ $43.96–$46.04; 2σ ≈ $42.92–$47.08.
- 1σ weekly move ≈ 45 × 0.37/7.2 ≈ **$2.31** → 1σ week range ≈ $42.69–$47.31; 2σ ≈ $40.38–$49.62.

(For a contract at 100 with σ=20%: 1σ daily = 20%/16 = 1.25%; 1σ weekly = 20%/7.2 ≈ 2.78%.)

### Annual interpretation example
Forward price 100, σ = 20%. One year out: ~68% chance in **80–120** (100±20%), ~95% in **60–140**,
~99.7% in **40–160**. For a *stock* (spot ≠ forward) you must first push spot to the **forward** and
take σ% of the **forward**: stock $100, r=8%, no div → forward $108; 1σ = 20%×108 = **$21.60** →
68% band $86.40–$129.60, etc. (A >3σ realized move isn't impossible — "unlikely ≠ impossible.")

### Lognormal vs normal (why prices aren't normal)
- **Normal** distribution of *prices* is symmetric → allows **negative prices**, which is impossible
  for stocks/commodities. That's its fatal flaw.
- Volatility is a **rate of return** (mix of + and − returns), like interest but two-sided. Continuously
  compounding *normally-distributed percent returns* produces a **lognormal distribution of prices**.
- Lognormal is **right-skewed / bounded by zero on the downside, open-ended on the upside**: a +12%
  continuous return gives +$127.50 on $1,000, but −12% gives only −$113.08 (e^0.12 vs e^−0.12). Up
  moves are larger in absolute terms than down moves.
- Consequence: **mean sits to the RIGHT of the mode (peak)** (long right tail carries the balance point).
- `$1,000 × e^0.12 = $1,127.50`, `$1,000 × e^−0.12 = $886.92`. Continuous compounding can never take an
  investment below zero (can't lose >100%).
- **Pricing consequence:** with the same forward 100 / σ=30% / 6mo, a 110 call > 90 put even though both
  are 10% OTM, because the call's upside is unbounded while the put maxes out at 90 (price floored at 0).

### Reading / interpreting volatility data
- **Realized (historical) volatility** = annualized σ of past underlying price changes. Must specify
  **interval** (daily/weekly/monthly) AND **window** (e.g., 50-day, 52-week). Each point on a 50-day
  vol graph = annualized σ of daily changes over the trailing 50 days.
- Computed from **settlement-to-settlement** changes (most standard), usually as **log returns**
  ln(Pₜ/Pₜ₋₁); for exchange contracts only **business days** count (price can only change then).
- **Future realized volatility** = what you actually need (the true vol over the option's life) but
  can't know; estimate it from history + forecasts. **Historical vol** = the past starting point.
- Choice of sampling interval (daily vs weekly vs monthly) usually doesn't materially change the
  one-year vol estimate — a day-volatile contract is generally week- and month-volatile too.
- **Implied volatility** = the σ that, plugged into the model, makes theoretical value = the option's
  **market price**. It's the model run *backwards*; the market's consensus forecast of future realized
  vol over the option's life. Depends on the model used and needs *contemporaneous* inputs.
  - Traders quote/price options **in vol points**, not just currency ("I bought it at 27.5%").
  - "Premium high/low" ≈ implied vol high/low. Compare implied vs expected-future-realized:
    **implied < expected → buy options; implied > expected → sell options.**

### "Volatility and observed price changes" (the sanity check)
- There's **no observable "current volatility"** the way there's a current price — a trader must judge
  whether his σ input is being realized. Method: compare actual daily moves to the predicted 1σ move.
- Example: $45 stock, σ=37% → predicted 1σ day ≈ $1.04, so expect a >$1.04 day ~1 in 3 (≈1–2 of any 5
  days). Five observed moves +0.98, −0.65, −0.70, +0.25, −0.85 had **zero** >$1.04 days → inconsistent
  with 37%; the realized vol of that sample ≈ **27.8%**. (Caveat: 5 days is a tiny sample; prefer
  20/50/100-day windows before concluding. Account for holiday/abnormal weeks first.)

### Effect of vol changes on option price (3 principles — also re-stated in ch7 setup)
1. In **total points**, a vol change moves the **at-the-money** option most.
2. In **percent terms**, a vol change moves the **out-of-the-money** option most.
3. A vol change moves a **long-dated** option more (in points) than an equivalent short-dated one.
- ITM options are **least** sensitive to vol (and most sensitive to underlying price). This is why
  most option **volume concentrates in ATM/OTM** strikes — those are the vol plays.
- Calls & puts at the **same strike + expiry** have ~equal implied vols and change by ~equal amounts
  when vol moves (a put-call parity consequence). A 2-point vol miss can wipe out the whole edge.

### Interest-rate products aside
- Eurocurrency futures quote as **100 − rate** → a 93.00 future = 7.00% rate. Vol can be **rate vol**
  (from the rate) or **price vol** (from 100−rate); for bonds also **yield vol** vs **price vol**.
- A 93.00 **call** (price terms) = a 7.00% **put** (rate terms): for the future to rise above 93 the
  rate must fall below 7% → indexing flips calls↔puts and subtracts strikes from 100.

**→ What a quant should remember (ch6):**
- Vol = annualized σ of (log) returns; **σ_period = σ_annual·√t**; daily ≈ σ_annual/16, weekly ≈ σ_annual/7.2.
- The 68/95/99.7 bands + "2σ day ≈ once a month" are your gut-check rulers.
- Model the world **lognormal** (price floored at 0, right-skewed, mean > mode), not normal.
- The number that *sets value* is **future realized vol**; the number the *market shows* is **implied vol**;
  trade the spread between them. Always size for being wrong about vol — margins for error are thin.

---

## ch7 — RISK MEASUREMENT I (the Greeks)

### Interest-rate & dividend sign effects (these ARE in the file — Fig 7-1/7-2/7-3)
General (any option):

| If… | Call value | Put value |
|---|---|---|
| Underlying ↑ | rise | fall |
| Underlying ↓ | fall | rise |
| Volatility ↑ | rise | rise |
| Volatility ↓ | fall | fall |
| Time passes | fall* | fall* |

\*Almost always decay; rare exceptions exist (deep-ITM European puts / cost-of-carry cases) — covered later.

**Interest rates** work through two channels: (a) the **forward price**, (b) the **present value** of the option.
- **Stock options:** ↑ rates → forward ↑ (favors calls) and PV ↓ (hurts both). For stock, forward effect
  dominates → **call ↑, put ↓** as rates rise. Rule: *avoid short stock* (short-stock hedging lowers the
  effective rate via borrow cost, shifting call/put values); many traders keep some long stock so any
  hedge sale is a long sale at the ordinary rate.
- **Futures options, futures-type settlement** (outside US): no cash moves → **interest-rate insensitive.**
- **Futures options, stock-type settlement** (US): forward unchanged, but PV ↓ → ↑ rates lower **both**
  call and put (small effect unless deep ITM).
- **FX options:** forward `F = S·(1+r_d·t)/(1+r_f·t)`. ↑ **domestic** rate → forward ↑ → call ↑, put ↓.
  ↑ **foreign** rate → forward ↓ → call ↓, put ↑.
- **Dividends** (stock): ↑ dividend → forward ↓ → **call ↓, put ↑**; cut dividend → call ↑, put ↓.

The Greeks (a.k.a. risk measures / partial derivatives) give the **direction AND magnitude** of these
sensitivities. They don't answer everything but are the starting point for position risk.

---

### Δ DELTA — sensitivity to underlying price *(fully covered in file)*
- **Definition:** the rate of change of the option's theoretical value w.r.t. a move in the underlying
  — i.e. the **slope** of the value-vs-underlying curve. ∂V/∂S.
- **What it measures / interpretations:**
  1. **Rate of change / hedge ratio:** delta 0.25 → option moves 25% as fast as underlying (underlying
     +1.00 → call +0.25; underlying +0.60 → call +0.45 at delta 0.75). Also = the number of underlying
     units to hedge one option (the riskless-hedge ratio).
  2. (Other standard interpretations Natenberg adds just past the cut-off: **equivalent underlying
     position** of the option, and **approx. probability the option finishes ITM**.) `[partly beyond file]`
- **Sign / bounds:**
  - **Calls: 0 → +1.00.** Far OTM → 0; deep ITM → +1.00; ATM ≈ +0.50. Positive delta = wants underlying up.
  - **Puts: 0 → −1.00.** Far OTM → 0; deep ITM → −1.00; ATM ≈ −0.50. Negative delta = wants underlying down.
  - A call can never gain/lose faster than the underlying (|slope| ≤ 1) nor move opposite to it.
- **How it moves:**
  - **vs spot:** rises toward +1 (calls) / −1 (puts) as the option goes ITM; toward 0 as it goes OTM
    (this curvature *is* gamma).
  - **vs time / vs vol:** as expiration nears OR vol falls, deltas get more **extreme** (ITM → ±1, OTM → 0,
    the curve sharpens toward the hockey-stick); more time or higher vol pulls deltas back toward ±0.50.

> The following Greeks are **beyond this file's cut-off** — standard Natenberg ch7, included for completeness.

### Γ GAMMA — sensitivity of delta to underlying price `[beyond file cut-off]`
- **Definition:** rate of change of **delta** w.r.t. the underlying. ∂Δ/∂S = ∂²V/∂S². "Curvature."
- **Measures:** how fast your directional exposure (delta) shifts as spot moves — i.e. the *instability*
  of the hedge. Quoted as delta-change per 1-point underlying move.
- **Sign:** **long options (calls OR puts) = +gamma; short options = −gamma.** (Same-signed for calls and
  puts, unlike delta.) Positive gamma = delta moves *with* you (helps); negative gamma = delta moves
  *against* you (hurts), the cost of being short premium.
- **How it moves:**
  - **vs spot:** **peaks at-the-money**, falls toward 0 deep ITM/OTM (delta is flat at the extremes).
  - **vs time:** **ATM gamma → ∞ as expiration approaches** (delta flips fast near the strike at the end);
    OTM/ITM gamma → 0 near expiry. More time → flatter, lower ATM gamma.
  - **vs vol:** higher vol *lowers* ATM gamma and spreads it across strikes; lower vol concentrates a tall
    gamma spike at the money.

### Θ THETA — sensitivity to the passage of time (time decay) `[beyond file cut-off]`
- **Definition:** rate of change of value w.r.t. time, normally per **one day** passing. −∂V/∂t.
- **Measures:** how much value the option bleeds as one day elapses, all else equal.
- **Sign:** **long options = −theta (you pay decay); short options = +theta (you collect).** Theta and
  gamma carry **opposite signs** — long gamma costs theta; short gamma earns theta. This trade-off is the
  central tension of option trading.
- **How it moves:**
  - **vs spot:** (in absolute size) **largest at-the-money.**
  - **vs time:** ATM theta **accelerates** as expiration nears (the famous non-linear decay; ATM decay ∝
    roughly 1/√(time left)). Deep ITM/OTM options decay slowly and more linearly.
  - **vs vol:** higher vol → larger theta (more extrinsic value to bleed).

### V (vega / kappa) VEGA — sensitivity to volatility `[beyond file cut-off]`
- **Definition:** change in value per **1 percentage-point** change in volatility. ∂V/∂σ. (Not a Greek
  letter; sometimes written kappa κ.)
- **Measures:** exposure to a shift in implied volatility.
- **Sign:** **long options (calls AND puts) = +vega; short = −vega.** Both calls and puts *gain* when vol
  rises (consistent with the ch6 table).
- **How it moves:**
  - **vs spot:** **peaks at-the-money**, → 0 deep ITM/OTM. (ATM options are the vol instrument — matches
    ch6 principle 1.)
  - **vs time:** vega is **larger for longer-dated options** and shrinks toward expiration (ch6 principle 3:
    a vol change moves long-dated options more in points).
  - **vs vol:** relatively stable for ATM; in % terms OTM options are most vol-sensitive (ch6 principle 2).

### ρ RHO — sensitivity to interest rates `[beyond file cut-off]`
- **Definition:** change in value per **1 percentage-point** change in the interest rate. ∂V/∂r.
- **Measures:** interest-rate exposure (smallest/least important of the Greeks for most positions).
- **Sign (stock options):** **call rho > 0** (↑ rates → call ↑); **put rho < 0** (↑ rates → put ↓) — matches
  Fig 7-2. FX options have a domestic-rate rho and a foreign-rate rho with opposite signs; futures options
  under futures-type settlement have ~zero rho.
- **How it moves:** **larger for longer-dated and deeper-ITM** options (more PV / forward to discount);
  near zero for short-dated options. Generally the Greek you worry about last, except for LEAPS / very
  long-dated or very large positions.

**→ What a quant should remember (ch7):**
- The Greeks = first/second partials of value: **Δ = ∂V/∂S, Γ = ∂Δ/∂S = ∂²V/∂S², Θ = ∂V/∂t, Vega = ∂V/∂σ,
  ρ = ∂V/∂r.** Each gives direction *and* magnitude of a specific risk.
- **Sign rosetta:** long-option positions are **long gamma, long vega, short theta**; delta sign depends
  on call(+)/put(−). Short-option positions flip all of these. Gamma↔theta always have opposite signs.
- **Where each lives on the curve:** Γ, Θ, Vega all **peak at-the-money**; Δ runs 0→±1 across the strike;
  ρ and vega grow with **time to expiry**, gamma and theta **spike near expiry** ATM.
- Interest-rate/dividend effects depend on **settlement type** (stock vs futures-type) and direction of
  the **forward** — don't memorize "rates up = calls up" blindly; reason via forward + present value.

---

## Batch 2A — top lessons
1. **Volatility = annualized σ of (log) returns**, and it scales with **√time**: `σ_period = σ_annual·√(t in years)`;
   daily ≈ **σ_annual/16** (√256), weekly ≈ **σ_annual/7.2** (√52). Interest scales linearly; vol does **not**.
2. **68 / 95 / 99.7%** for ±1/±2/±3σ; the same bands hold at every rescaled horizon. A **>2σ daily move ≈
   once a month**; a one-sided >2σ tail ≈ 1 in 40.
3. Real prices are **lognormal**, not normal: floored at zero, right-skewed, **mean > mode**; this is why a
   symmetric-strike call is worth more than the equal-distance put (unbounded upside vs floored downside).
4. Distinguish **future realized vol** (sets an option's true value, unknowable) from **implied vol** (the
   market's price, read by inverting the model). **Buy when implied < expected realized, sell when implied >**.
   Quote options in **vol points**; a 2-pt vol error can erase the whole edge.
5. **Sanity-check your vol** against realized 1σ moves (the "$1.04 day" test); never trust a 5-day sample —
   use 20/50/100-day windows and discount abnormal weeks.
6. **Vol-change response:** ATM moves most in *points*, OTM most in *percent*, long-dated more than short —
   so ATM/OTM strikes are the vol plays and carry the volume; ITM is least vol-sensitive.
7. The **Greeks** are partial derivatives giving direction + magnitude of risk: **Δ=∂V/∂S** (calls 0→+1, puts 0→−1), **Γ=∂²V/∂S²** (curvature, peaks ATM, spikes near expiry), **Θ=∂V/∂t** (decay, peaks ATM, accelerates near expiry), **Vega=∂V/∂σ** (peaks ATM, grows with time), **ρ=∂V/∂r** (grows with time/ITM, least important). **Sign rosetta:** long options ⇒ **long Γ, long Vega, short Θ** (delta sign = call+/put−); short options flip all; **Γ and Θ always oppose**. Interest-rate/dividend effects hinge on **settlement type** and the **forward** — reason via forward + present value, don't memorize.

> ⚠️ **File-coverage caveat:** `02a_vol_greeks1.txt` ends mid-Delta — Gamma/Theta/Vega/Rho and the later Delta interpretations (equivalent-underlying, ITM-probability) are reconstructed from Natenberg's standard ch7, not read verbatim. Confirm against the next batch if these Greeks recur there.