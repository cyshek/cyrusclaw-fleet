# Natenberg — Batch 5 of 6: Models, Volatility Revisited, Position Analysis (Ch. 18–21)

> Study note. Math accuracy prioritized. The source was layout-extracted text; Greek letters,
> exponents, and subscripts were frequently garbled. Where a formula was reconstructed from
> garbled text, the intended/standard form is stated and flagged **(verify: ...)**.
> Paper-trading quant context. Read-only study artifact.

---

## CHAPTER 18 — The Black-Scholes Model

### 18.1 What the model is

Black-Scholes (BS) is a continuous-time, closed-form pricing model for **European** options
(exercise only at expiration). It assumes the underlying price evolves as **geometric Brownian
motion** — i.e., the *price* is lognormally distributed, equivalently the *log returns* are
normally distributed with constant volatility.

### 18.2 The assumptions (this is what the model bakes in — know them because every assumption is a place reality breaks)

1. **Frictionless markets** — no transaction costs, no taxes; you can trade continuously.
2. **Continuous trading / continuous hedging is possible** — the delta hedge can be rebalanced
   instantaneously (this is the heart of the no-arbitrage derivation: a continuously
   delta-hedged option earns the risk-free rate).
3. **Constant, known interest rate** over the life of the option.
4. **Constant, known volatility** over the life of the option. (Reality: volatility is neither
   constant nor known — this is *the* assumption the rest of the book attacks.)
5. **Lognormal price distribution / normally distributed returns** — returns are independent,
   no jumps; the distribution is continuous (no gaps).
6. **No early exercise** — European-style. (BS *cannot* price American early exercise; that's
   why the binomial model exists — Ch. 19.)
7. **Underlying pays a known, continuous (or discretely adjustable) dividend / carry.**
8. Returns are serially independent (a random walk; today's move doesn't predict tomorrow's).

Natenberg's framing earlier in the book: a theoretical pricing model is a machine that takes
{underlying price, exercise price, time, interest rate, **volatility**, dividend} → theoretical
value + the Greeks. Volatility is the *only* input you can't directly observe, which is why the
whole second half of the study is about estimating it.

### 18.3 The formula structure (plain text, carefully)

For a **non-dividend-paying** European option:

```
Call C = S · N(d1)  −  X · e^(−r·t) · N(d2)
Put  P = X · e^(−r·t) · N(−d2)  −  S · N(−d1)
```

where
- `S` = current underlying (spot) price
- `X` = exercise (strike) price
- `t` = time to expiration in years
- `r` = risk-free interest rate (annualized)
- `σ` = annualized volatility (standard deviation of returns)
- `N(·)` = cumulative standard normal distribution function (area under the normal curve up to
  that point; ranges 0→1)

The two arguments:

```
d1 = [ ln(S/X) + (r + σ²/2)·t ] / ( σ·√t )
d2 = d1 − σ·√t
```

**(verify: d1/d2 numerators — the text's exponents/subscripts were garbled throughout; the
forms above are the standard Black-Scholes d1/d2 and are what the surrounding prose implies.
For a carry/cost-of-carry generalization, the `r` in the drift term becomes the cost of carry
`b`, and there's an extra `e^((b−r)t)` factor on the S term — see the Ch. 19 figure 19-13
generalization which uses `b`.)**

Intuition for the two terms of the call:
- `S · N(d1)` = expected value of *receiving the stock if exercised*, probability-weighted in a
  risk-neutral sense.
- `X · e^(−r·t) · N(d2)` = expected value of *paying the strike if exercised*, present-valued
  (`e^(−r·t)`) and weighted by the true risk-neutral probability of finishing in the money,
  `N(d2)`.
- The call value is the difference: expected benefit minus expected (discounted) cost.

### 18.4 Why N(d1) = delta, and what N(d2) is

- **N(d1) = delta of the call** (as a decimal 0→1; ×100 for the "62 delta" convention).
  Delta is the partial derivative ∂C/∂S, and differentiating the BS call formula w.r.t. S yields
  exactly `N(d1)` (the other terms cancel — this is the slick part of the derivation).
- **N(d2) = the *true* (risk-neutral) probability that the option finishes in the money**
  (i.e., probability S_T > X at expiration).
- Therefore for a call **N(d1) > N(d2) always** (because d1 > d2, since d1 − d2 = σ√t > 0).
  - Practical reading: **delta systematically OVERSTATES the probability of finishing ITM.**
    A "62 delta" call does NOT have a 62% chance of expiring in the money — its true ITM
    probability N(d2) is lower. The gap widens with higher volatility and more time
    (because σ√t grows).
- Put delta = call delta − 100 (in the ×100 convention), i.e. `delta_put = N(d1) − 1 = −N(−d1)`.

### 18.5 What each input does (sign of each effect)

| Input ↑ | Call value | Put value | Notes |
|---|---|---|---|
| Underlying S ↑ | ↑ | ↓ | This is delta. |
| Exercise price X ↑ | ↓ | ↑ | Higher strike = worse for call, better for put. |
| Time t ↑ | ↑ (usually) | ↑ (usually) | More time = more optionality (vega/theta). Deep-ITM European puts can be a mild exception due to carry. |
| Volatility σ ↑ | ↑ | ↑ | This is vega — *always positive* for long options. The single most important "judgment" input. |
| Interest rate r ↑ | ↑ | ↓ | This is rho. Higher r lowers PV of strike → helps calls. |
| Dividend ↑ | ↓ | ↑ | Dividends reduce the forward price of the stock. |

### 18.6 Distribution detail worth keeping (from the BS chapter's stats groundwork)

- Returns assumed **normal**; *prices* are therefore **lognormal** (can't go below 0, right-skewed,
  long right tail). For a lognormal, **mode < median < mean** (the mean is dragged up by the
  unbounded right tail).
- **The "40% rule" / peak-of-normal approximation**: the height of the standard normal density at
  its peak is `1/√(2π) ≈ 0.3989`. Natenberg uses this to approximate the expected absolute value
  of a move (the mean absolute deviation of a normal ≈ 0.7979·σ, and the per-1%-vol scaling lands
  near 0.00399·S per 1 standard-deviation-% ). **(verify: the exact constant 0.3989 = 1/√(2π) is
  right; the way the book scales it to a daily expected move was partially garbled in extraction —
  the principle is "expected move ≈ 0.8·σ for one std dev, and the density peak 0.399 underlies the
  quick approximations.")**
- A **zero-mean assumption** is standard for vol work (see Ch. 20) — traders treat the average
  return as 0 so that *all* movement counts as volatility.

### 18.7 What a quant should remember (Ch. 18)

- BS is an *equilibrium under a hedging argument*: the option price is the cost of replicating it
  via continuous delta hedging at the risk-free rate. The model is only as good as "constant known
  vol" and "continuous costless hedging" — both false in practice.
- **delta = N(d1); ITM-probability = N(d2); delta > true ITM prob.** Don't use delta as a
  probability.
- Vega is always positive for long options; volatility is the input that actually decides P&L if you
  hold and hedge.

---

## CHAPTER 19 — Binomial Option Pricing

### 19.1 The idea

Discretize time into `n` steps. At each step the underlying either multiplies by an **up factor u**
or a **down factor d**. This builds a recombining binomial tree of terminal prices. Then value the
option by **risk-neutral valuation**: assign pseudo-probabilities `p` and `1−p` to up/down moves
such that the underlying earns the risk-free rate in expectation, compute the option's expected
payoff at expiration, and **discount back**.

The binomial model's payoff: this is the *discrete* analog of BS and **converges to BS** as
`n → ∞` (for European options).

### 19.2 Up/down factors

To make the tree match a target annualized volatility σ, Natenberg uses (Fig. 19-13):

```
u = e^( σ · √(t/n) )
d = 1/u = e^( −σ · √(t/n) )
```

So `u·d = 1` (recombining, symmetric in log space). `t/n` is the length of one step in years.
**(verify: exponent is σ√(t/n); extraction rendered it as "eσ√t/n" which is the same thing.)**

### 19.3 Risk-neutral (pseudo) probability p

General form used in the book (per-step, with `t/n` = step length):

```
p = [ (1 + r·t/n) − d ] / ( u − d )
1 − p = ( u − 1 − r·t/n ) / ( u − d )
```

- Worked example in the text: u = 1.20, d = 0.90, (ignoring interest) p = (1 − 0.90)/(1.20 − 0.90)
  = 0.10/0.30 = **1/3**.
- Dividend/stock example: u = 1.05, d ≈ 0.9524, r = 4%, t = 0.75, n = 3 →
  p = [1 + 0.04·(0.75/3) − 0.9524]/(1.05 − 0.9524) = 0.0576/0.0976 ≈ **0.59**, 1−p ≈ 0.41.

**(verify: the book uses the simple-interest discrete form `1 + r·t/n` rather than the continuous
`e^(r·t/n)`. The TASK PROMPT's `p = (e^(rt)−d)/(u−d)` is the continuous-compounding single-period
equivalent; Natenberg's discrete per-step version with simple interest is the one literally in the
text. Both are "risk-neutral probability"; they agree in the limit. The general carry form replaces
`r` with cost-of-carry `b`: `p = [(1 + b·t/n) − d]/(u − d)`.)**

**Pseudo-probabilities can fall outside [0,1].** If interest is high relative to the up/down spread
(specifically if `u < 1 + r·t/n`), then p > 1 and 1−p < 0. Worked: at r = 40%, u = 1.05, d = 0.9524
→ p = (1.10 − 0.9524)/(1.05 − 0.9524) = 1.51, 1−p = −0.51. Economic meaning: the stock's upside
(5%/step) can't even cover the interest you forgo by buying it, so the "probabilities" stop looking
like probabilities — hence the name **pseudoprobabilities**. Requirement for valid p∈[0,1]:
`u > 1 + r·t/n` (with r=30%, t/n=0.25 → u must exceed 1.075).

### 19.4 Backward induction (the valuation engine)

1. Compute all **terminal** underlying prices (the leaves): `S · u^j · d^(n−j)` for j up-moves.
2. Compute each leaf's **payoff**: `max(S·u^j·d^(n−j) − X, 0)` for a call, `max(X − …, 0)` for a put.
3. Step **backward** node by node: each node's value = discounted expectation of its two children:
   `value = [ p·V_up + (1−p)·V_down ] / (1 + r·t/n)`.
4. The root `C(0,0)` is the option's present value.

Closed-form (sum over the binomial distribution), per Fig. 19-13:

```
Call = (1 / (1 + r·t/n)^n) · Σ_{j=0..n} [ n!/(j!(n−j)!) · p^j·(1−p)^(n−j) · max(S·u^j·d^(n−j) − X, 0) ]
Put  = (1 / (1 + r·t/n)^n) · Σ_{j=0..n} [ n!/(j!(n−j)!) · p^j·(1−p)^(n−j) · max(X − S·u^j·d^(n−j), 0) ]
```

`n!/(j!(n−j)!)` is the binomial coefficient "n choose j" — the number of distinct paths to a node.

### 19.5 American early exercise — the thing BS can't do

This is the **headline advantage of the tree**. During backward induction, at *every* node compare:
- the **continuation (European) value** = discounted expectation of children, vs.
- the **intrinsic value** = `max(S − X, 0)` (call) / `max(X − S, 0)` (put) if exercised right now.

Take the **larger**: `node value = max(continuation, intrinsic)`. If intrinsic wins, that node is an
optimal early-exercise point; you overwrite the continuation value with intrinsic and keep folding
back. BS has no mechanism for this node-by-node decision, so it cannot price American options. The
binomial tree handles it naturally because it evaluates the position at every intermediate node.

- For **American calls on non-dividend stock**, early exercise is essentially never optimal → value
  ≈ European → BS is fine. Early exercise of calls becomes relevant **around dividends** (exercise
  just before ex-div to capture the dividend).
- **American puts** *can* be optimally exercised early (deep ITM puts — you'd rather have the cash
  and earn interest), so they genuinely need the tree.

### 19.6 Dividends on a tree (the practical mess)

- Subtracting a discrete dividend from prices after the ex-date makes the tree **non-recombining**
  (each node spawns a fresh sub-tree → combinatorial blow-up with many dividends/steps).
- Practical approximations: (a) build a clean no-dividend tree then **reduce every node's stock
  price by the PV of dividends**; or (b) accept slightly inflated values from the simple
  "subtract dividend at every subsequent node" shortcut. Natenberg shows the shortcut over-values
  the call slightly vs. the exact non-recombining tree.

### 19.7 Convergence to Black-Scholes

For European options, as the number of steps `n` increases, the binomial value **oscillates and
converges** to the BS value. In the text's 3-period example, the European 100 call ≈ 5.22 and 100
put ≈ 2.28 — close to, and converging toward, the BS numbers as n grows. Convergence is not
monotone (it zig-zags around the BS value as n increases), which is why practitioners use larger n
or averaging/smoothing tricks.

### 19.8 Model variations by carry (Fig. 19-13)

The same machinery prices different underlyings by choosing the cost-of-carry `b` in
`p = [(1 + b·t/n) − d]/(u − d)`:
- `b = r > 0`: options on **stock**.
- `b = r = 0`: options on **futures**, futures-type (margined) settlement.
- `b = 0, r > 0`: options on **futures**, stock-type settlement (pay premium up front).
- `b = r − r_f`: options on **foreign currency** (carry = domestic minus foreign rate). **(verify:
  this currency line was implied by the "variations" list; the FX carry form is standard.)**

### 19.9 What a quant should remember (Ch. 19)

- **Backward induction + `max(continuation, intrinsic)` at each node = the general option pricer.**
  It subsumes BS in the European limit and uniquely handles American exercise.
- `u = e^(σ√(t/n))`, `d = 1/u`, risk-neutral `p` set so the underlying drifts at the carry rate.
- Risk-neutral probabilities are a *pricing device*, not real-world odds (they can exceed 1 /
  go negative = "pseudoprobabilities").

---

## CHAPTER 20 — Volatility Revisited  ⭐ (most relevant to our vol-signal project)

### 20.0 The three volatilities (keep these distinct — this is the chapter's backbone)

1. **Historical / realized volatility** — what the underlying *actually did*, measured from past
   price data. A backward-looking *measurement*.
2. **Implied volatility** — the volatility the *market* is pricing in *right now*, backed out of
   option prices via the model. A forward-looking *market expectation* (but a biased one).
3. **Future (realized) volatility** — what the underlying *will actually do* over the option's life.
   **This is the only thing that ultimately determines a held-to-expiry position's P&L** — and it's
   unknowable in advance. Everything else is an estimate of this.

**Core principle (stated twice in the chapter):** *The longer a position is held, the more important
realized volatility is and the less important implied volatility is. Held to expiration, realized
volatility is the ONLY thing that matters.* Implied vol matters for interim P&L, capital, and
exit timing — but value is set by realized vol.

### 20.1 Calculating historical volatility

Standard deviation, two denominators:
```
population:  σ = √[ Σ (xi − μ)² / n ]
sample:      σ = √[ Σ (xi − μ)² / (n − 1) ]
```
- Use **n − 1 (sample stdev)** for historical vol, because a finite sample misses extreme moves and
  would underestimate the population σ; dividing by n−1 corrects upward. **(verify: formulas had
  garbled radicals; these are the standard population vs. sample stdev.)**

- **Data points xi = price returns**, either simple `(p_n − p_{n−1})/p_{n−1}` or — more commonly —
  **log returns `ln(p_n / p_{n−1})`**.

- **Zero-mean assumption**: set μ = 0 regardless of the actual average. Rationale: if a contract
  rises exactly 1%/day for 10 days, the *deviation-from-mean* stdev is 0, which "feels wrong" to a
  trader — the moves clearly represent volatility. Forcing μ=0 makes every move count. Most
  historical-vol calcs use μ=0.

- **Annualization**: multiply the per-period stdev by `√(periods per year)`. Trading-day convention
  ≈ √252; calendar convention ≈ √365 (≈ 19.1). Whether you use 252 trading days or 365 calendar
  days (assigning 0 move to non-trading days) makes almost no practical difference (Fig. 20-1: the
  two S&P curves are near-identical).

- **Sampling frequency**: daily vs. weekly returns give similar pictures; **daily preferred** because
  more data points → smoother, more accurate estimate. Weekly is noisier (fewer points). Key
  empirical claim: *a contract volatile day-to-day is equally volatile week-to-week or
  month-to-month* — volatility is scale-consistent.

### 20.2 Range-based (intraday) estimators — more efficient than close-to-close

Close-to-close throws away intraday range; a day that whips around but closes flat reads as 0 vol,
which understates true volatility. Two range estimators:

- **Parkinson (extreme-value, high–low)**:
  ```
  σ_Park = √[ (1 / (4·ln2)) · (1/n) · Σ ( ln(h_i / l_i) )² / t ]
  ```
  uses the high `h_i` and low `l_i` of each interval. **(verify: the constant is 1/(4·ln2) ≈ 0.361;
  extraction showed "1/(2n·ln2)" lumped with the 1/n — the standard Parkinson per-observation
  factor is 1/(4 ln2). The √t in the denominator annualizes.)**

- **Garman–Klass (open–high–low–close)** — extends Parkinson with opens `o_i` and closes `c_i`:
  ```
  σ_GK ≈ √[ ( (1/2)·(1/n)·Σ (ln(h_i/l_i))²  −  (2·ln2 − 1)·(1/n)·Σ (ln(c_i/o_i))² ) / t ]
  ```
  **(verify: GK coefficients — standard GK is 0.5·(ln(H/L))² − (2ln2−1)·(ln(C/O))²; matches the text
  modulo garbled layout.)**

- Both Parkinson and GK are **more statistically efficient** (use more info per day) and typically
  read **lower** than close-to-close *for markets that aren't open continuously* (e.g., EuroStoxx 50
  trades ~10h/day; overnight moves aren't captured in the range). Fix: **weight** the range estimator
  by the fraction of the day the market is open and give the rest of the weight to close-to-close.
  Garman–Klass give a precise weighting; a practical shortcut is to **weight the estimators equally**.

> ⚙️ **For OUR project**: range-based estimators (Parkinson, Garman–Klass) extract more signal per
> day than close-to-close — directly useful if we want a higher-information vol estimate from OHLC
> bars, *provided* the instrument trades ~continuously over the bar. For partial-session products,
> blend with close-to-close.

### 20.3 The big volatility stylized facts (the heart of forecasting)

1. **Mean reversion** — vol oscillates around a long-run mean and reliably returns to it. S&P 500
   long-run mean ≈ 15–20%; Bund ≈ 5%. "If vol is far above the mean it will fall; far below, it
   will rise." This is the single most exploitable property.
2. **Serial correlation (vol clustering / persistence)** — vol over one period correlates with vol
   over the previous equal-length period. If last 4 weeks ran 15%, next 4 weeks are more likely
   near 15% than far from it. (This is the empirical fact GARCH/EWMA formalize — see 20.5.)
3. **Term structure / "volatility cone"** — plot min/avg/max realized vol vs. measurement-window
   length (Figs. 20-6 to 20-8). The envelope is **cone-shaped**: short windows show a wide
   min-to-max spread; long windows converge tightly to the mean.
   - Counterintuitive consequence: **long-horizon vol is EASIER to forecast than short-horizon vol**
     (large and small moves average out over long windows → more stable). E.g. S&P 2-week vol ranged
     ~5%→100% (avg ~18%), but 300-week vol ranged only ~14%→24% (avg ~19%).
   - **BUT** long-dated options have larger **vega**, so a given vol *error* costs far more on a
     long option. A 2–3 vol-point error on a long option can hurt more than a 5–6 point error on a
     short option. So "easier to forecast" ≠ "easier to value."
4. **Vol has trends and "technical" behavior** — vol charts (Fig. 20-2 gold) show multi-month
   up/down trends and minor swings, resembling price charts. You *can* apply technical-analysis
   ideas to vol, but cautiously: price and vol are related but not identical, so some TA rules don't
   transfer or must be modified.

### 20.4 Volatility forecasting (the practical recipe)

Given a set of historical vols over different lookbacks, e.g.:
```
6-week HV  = 28%
12-week HV = 22%
26-week HV = 19%
52-week HV = 18%
```
Approaches, in increasing sophistication:

- **Simple average** of available HVs: (28+22+19+18)/4 = 21.75%. Equal weight to all.
- **Recency-weighted**: give more weight to recent data, e.g. 40% to the 6-week, 20% each to the
   others → 23.0%.
- **Regressive (monotone-decaying) weighting**: progressively less weight to older data,
   e.g. 40/30/20/10 → 23.4%.
- **Match the forecast horizon to the option's life (KEY refinement via serial correlation)**: give
   the MOST weight to the HV whose window length is **closest to the time-to-expiration of the
   option you're pricing** — because vol is serially correlated, the best predictor of the next
   N-period vol is the most recent N-period vol.
   - Pricing a **5-month** option (≈26 weeks): weight 26-week HV most → e.g.
     (15%·28)+(25%·22)+(35%·19)+(25%·18) = **20.85%**.
   - Pricing a **3-month** option (≈12 weeks): weight 12-week HV most → e.g.
     (25%·28)+(35%·22)+(25%·19)+(15%·18) = **22.15%**.
   - Pricing **very long-dated** options: mean reversion dominates → the best forecast is just the
     **long-run mean vol** of the instrument.
- **More data = better**: more lookback windows let you match horizons more precisely and reveal the
   vol characteristics. Ideally hold HV series for exactly the horizons you trade.

**Caveat on time-series models (GARCH-type):** Formal time-series methods need data points that are
**independent** of each other. Overlapping rolling HVs (52-week overlaps 26/12/6-week) are NOT
independent → they don't form a true time series, so naive time-series modeling on overlapping
windows is statistically improper. **(verify: the chapter introduces time-series analysis and warns
that overlapping vol windows violate independence; in the truncated portion it gestures toward
proper non-overlapping series / EWMA-style weighting. The book does NOT appear to give an explicit
GARCH(1,1) equation in this batch — it conveys the *ideas* GARCH encodes: mean reversion +
recency-weighting + persistence — rather than the parametric model. Do not attribute a specific
GARCH formula to Natenberg from this text.)**

### 20.5 Implied volatility as a predictor of future volatility

Natenberg compares S&P 500 implied vol vs. subsequent realized vol (Figs. 20-9 to 20-11):

- **Realized vol tends to LEAD implied vol** — the market reacts to the underlying becoming
   more/less volatile; implied vol follows with a lag (very visible 2008→2009).
- **Implied is an imperfect, biased predictor.** Differences of ~10 vol points between implied and
   subsequent realized are common; 2008 saw extreme misses (Sept 8 2008: 3-mo implied 22% vs.
   3-mo realized 72% → implied too LOW by ~50 pts; Nov 20 2008: implied 65% vs realized 45% → too
   HIGH by ~20 pts).
- **Systematic bias: under normal conditions implied vol is TOO HIGH — options are, on average,
   overpriced.** Interpretation = an **insurance premium**: buyers knowingly overpay for the rare
   vol-explosion payoff (like buying insurance above expected value); sellers/market-makers charge
   for replication cost + model risk. This is the **volatility risk premium** (implied > realized on
   average). **(verify: chapter footnote ties this to the efficient-market hypothesis; the
   "insurance / overpriced on average" reading is explicit in the text.)**

### 20.6 Term structure of IMPLIED volatility

- Across expiration months, IVs don't move in lockstep. Because of **mean reversion**, a shock to
   front-month IV moves long-dated IV **less** (long-dated IV stays nearer the mean). Example: if
   March IV jumps 25%→30%, June might go to 28%, Sept to 26% (and symmetrically on the way down:
   20% / 22% / 24%). Typical term-structure shape in Fig. 20-12.
- **Implication for vega risk:** summing raw vegas across months OVERSTATES true IV risk, because
   distant-month IV moves at a *fraction* of the front-month's rate. You must **weight** each
   month's vega by how much that month's IV actually moves relative to the reference month.
   - Worked: raw vegas +15 / −36 / −21 / +42 sum to **0** (looks hedged), but after scaling distant
     months by their lower responsiveness, the position's true vega is about **−4.08** — i.e. it is
     NOT actually vega-neutral. **(verify: exact scaled numbers depend on the assumed
     responsiveness factors; the point is raw-vega-sum ≠ true IV risk.)**
- **IV term-structure models** need ≥3 inputs: (1) a **primary/reference month** (often but not
   always the front month — agricultural markets may anchor to planting/harvest months; front-month
   IV is often unstable near expiry and is frequently analyzed separately), (2) a **mean vol** to
   revert toward, and (3) a **"whippiness" factor** = how fast other months' IV moves vs. the
   reference month. Models are usually "home-grown."
- **Seasonality** can override term structure: natural-gas **October** options persistently carry
   elevated IV (Atlantic hurricane season peaking Aug–Sep, captured by Oct expiry); ag summer months
   trade richer (heat/drought risk). Seasonal vol factors make a clean term-structure model harder.
- Term structure can **invert and re-invert** over time (Fig. 20-14 EuroStoxx 2010: downward-sloping
   → inverted upward → back to downward → flat), tracking changes in underlying realized vol. Note a
   common quirk: **front-month IV often disconnects** from the rest of the curve.

### 20.7 Forward volatility & calendar-spread mispricing (a concrete vol-RV tool)

To judge whether one expiration is mispriced **relative to** another (not whether the whole surface
is cheap/rich):

- **Spread implied volatility**: the single vol that, applied to BOTH legs of a calendar spread,
   reprices the spread to its market price. Compare it to the term-structure best-fit to spot
   over/under-priced months. (Downward-sloping term structure → all calendar-spread IVs plot *below*
   the curve; upward-sloping → *above*.)
- **Quick estimate** (since ATM vega is ~constant in vol): for two ATM options with prices O₁,O₂ and
   vegas V₁,V₂,
   ```
   spread implied vol (in vol points) ≈ (O₂ − O₁) / (V₂ − V₁)
   ```
   i.e. **spread price ÷ spread vega**. Rough (rounding + vega drift) but fast.
- **Forward volatility** (the vol-analog of a forward interest rate). Because **variance is additive
   in time** (vol scales with √t), the vol implied between a near expiry t₁ (IV σ₁) and a far expiry
   t₂ (IV σ₂) is:
   ```
   σ_forward = √[ ( σ₂²·t₂ − σ₁²·t₁ ) / ( t₂ − t₁ ) ]
   ```
   from the identity `σ_f²·(t₂ − t₁) = σ₂²·t₂ − σ₁²·t₁`. Generalizes to a chain of consecutive
   forward vols whose variance-time-weighted average reconstructs total variance from t₀ to tₙ.
   **(verify: this forward-vol formula is given explicitly and is standard; the multi-period
   summation form was garbled but is the variance-additive generalization.)**
   - Forward vols and calendar-spread IVs give the **same** read on which month is rich/cheap
     (Fig. 20-21); they're alternative magnifying glasses for relative mispricing. A rich/cheap pair
     suggests a **calendar/time-butterfly** (e.g. buy the cheap April/June calendar, sell the rich
     June/September calendar).

### 20.8 What a quant should remember (Ch. 20)

- **Realized vol is what pays; implied vol is a biased (usually too-high) forecast that LEADS
   nothing — it lags realized.** The vol risk premium (implied > realized on average) is real and is
   the structural edge of being a net option seller — paid for tail risk.
- **Mean reversion + serial correlation + the vol cone** are the three facts that make vol
   forecastable; match your lookback window to your forecast horizon, and lean on the long-run mean
   for long horizons.
- **Variance is additive in time → forward vol = √[(σ₂²t₂ − σ₁²t₁)/(t₂−t₁)].** Use it (or
   calendar-spread implied vol ≈ spread price/spread vega) to find relative mispricing across
   expirations.
- **Range estimators (Parkinson, Garman–Klass)** beat close-to-close in efficiency for
   continuously-traded instruments.

---

## CHAPTER 21 — Position Analysis

### 21.1 The synthetic-rewrite trick (pre-computer, still a great intuition tool)

A tangled multi-leg book can sometimes be **rewritten into a recognizable strategy** using
put-call parity (synthetics). Replace every put with its synthetic equivalent
(`put = call − underlying` at the same strike, via `synthetic long stock = long call + short put`),
then net all the calls and underlying by strike. Natenberg's worked example collapses a 9-leg
call+put+underlying mess into a plain **long butterfly** (+42 / −84 / +42 across three strikes) — and
a long butterfly "wants" the underlying at the inside strike, so the position is clearly delta-long
below that strike. If the rewrite lands on a familiar structure, you instantly know the position's
bias. (In reality, complex books rarely simplify this cleanly → you need a model.)

### 21.2 Aggregating Greeks across legs

Total each Greek by summing **(contracts × per-option Greek)** across every leg, including the
underlying (underlying: delta = ±100/contract, all other Greeks = 0). Example position
(long 10 Sep-95 puts, short 10 Sep-105 calls, long 5 underlying) nets to **delta 0, gamma 0,
theta 0, vega 0** under current conditions — looks perfectly hedged.

**The central lesson of the chapter:** *Greeks are a snapshot under CURRENT conditions only.* A
position that is delta/gamma/theta/vega-neutral today will NOT stay neutral as price moves, vol
changes, or time passes — because the Greeks themselves move. "Zero Greeks now" ≠ "no risk."

### 21.3 Scenario / what-if reasoning (how the Greeks morph)

Driven by one fact: **gamma, theta, vega are all largest for AT-THE-MONEY options**, and **delta
moves toward 50 with higher vol/more time, away from 50 with lower vol/less time**. From these you
can reason out how a position evolves without a computer:

Worked (long 95 puts / short 105 calls / long 5 underlying, ATM-ish at 99.60):
| Market change | Δ becomes | Γ becomes | Θ becomes | Vega becomes |
|---|---|---|---|---|
| Underlying ↑ | negative | positive→ (gamma turns − on the way up) | negative | positive |
| Underlying ↓ | negative | positive | negative | positive |
| Time passes | positive | ~0 | ~0 | ~0 |
| Vol ↑ | negative | ~0 | ~0 | ~0 |
| Vol ↓ | positive | ~0 | ~0 | ~0 |

(The "delta goes negative whether price rises OR falls" oddity comes from gamma flipping sign across
the inflection point.) **Graphical reading:** P&L-vs-price curve — negative gamma = **frown**
(curves down, movement hurts), positive gamma = **smile** (curves up, movement helps); negative
delta = line sloping upper-left→lower-right. The current price can be a gamma **inflection point**
where the curve is locally straight.

### 21.4 Practical position metrics (memorize these quick estimates)

- **Where a negative-gamma position is maximally profitable** = where it becomes **delta neutral**.
   Estimate that price by stepping delta toward 0 using gamma:
   ```
   price_for_delta_neutral ≈ S − (position_delta / position_gamma)
   ```
   Worked: 101.25 − (297.4/24.13) ≈ 101.25 − 12.32 ≈ **88.93** (an *approximation* — gamma isn't
   constant; the true max was nearer 95 because gamma grew as price fell).
- **Breakeven (implied) volatility of the whole position** = how far vol can move before theoretical
   edge is wiped out:
   ```
   breakeven vol ≈ current_vol ± (theoretical_edge / |position_vega|)
   ```
   Worked (negative vega): 27.00 + (6.00/0.759) ≈ **34.90%** → you have ~7.9 vol points of margin
   for error. This is the **position's implied vol** (from Ch. 7). Improve the margin by raising edge
   (without raising vega) or cutting vega (without cutting edge).
- **Net contract position (the tail-risk check)** — ask: if the market gaps so far that ALL options
   go deep ITM (act like underlying) or deep OTM (vanish), what underlying position am I left with?
   - **Upside contract position** = (net calls + underlying) once all puts → 0 and all calls →
     underlying-equivalents.
   - **Downside contract position** = (net puts + underlying) once all calls → 0 and all puts → short
     underlying-equivalents.
   - This catches catastrophic gap risk that local Greeks miss. "Couldn't possibly go ITM" options
     do go ITM more often than expected (political/economic shocks, takeovers, disasters).
     (Aside: deep-OTM shorts still tie up margin → **cabinet bids**, ~1 currency unit, let traders
     close worthless options.)

### 21.5 Higher-order Greeks (Ch. 9 measures, used in the full position table Fig. 21-20)

| Name | = sensitivity of … | to a change in … |
|---|---|---|
| **Vanna** | delta | volatility |
| **Charm** | delta | passage of time |
| **Speed** | gamma | underlying price |
| **Color** | gamma | passage of time |
| **Volga** (vomma) | vega | volatility |
| **Vega decay** | vega | passage of time |
| **Zomma** | gamma | volatility |

- **Positive speed** means gamma grows as price rises (the position's curvature accelerates upward).
- **Positive volga** makes the vega-vs-vol curve bend upward → the *actual* breakeven vol comes out
   *higher* than the linear `edge/vega` estimate (worked: estimate 34.9%, true ≈ 36% because volga>0).
- These let you anticipate how the *first-order* Greeks themselves will drift — essential for big
   books where delta/gamma/vega "gyrate between positive and negative" across the price range
   (Figs. 21-15 to 21-20).

### 21.6 Market-making mindset & risk management

- A market maker repeats one loop: **"Get an edge … control the risk"** — capture bid-ask and/or
   theoretical mispricing, then hedge.
- Three questions: (1) what does the market think it's worth? (2) what do I think it's worth?
   (3) what am I already carrying? Adjust quotes (shade bid/ask up or down) to *acquire the trades
   that reduce your current risk* (e.g. if too short gamma, raise both bid and ask to bias toward
   buying options).
- **Diversify risk across strikes/expiries.** A book can net to zero total gamma yet hold a huge
   negative gamma concentrated at ONE strike (e.g. −2,388 at the 95 strike) — that concentration is
   dangerous as the underlying approaches that strike and time passes. Spread risk out like an
   investor diversifies.
- **Survival > optimization** on violent moves: when a fast move forces you to buy back protection
   at inflated IV, do it — staying in business to trade the next favorable setup matters more than
   any single trade's theoretical purity.
- **Set hard risk limits** (per delta/gamma/theta/vega/rho; clearing firm may require surviving a
   ±20% underlying move or a doubling of IV). When a limit is hit, quote to reduce, not to add.

### 21.7 Corporate-action mechanics (don't get blindsided)

- **Dividend change** on a position long stock: P&L change ≈ Δdividend × shares (long 3,300 shares →
   each $0.01 dividend change ≈ $33 position-value change). Hedge dividend risk by swapping real long
   stock for **synthetic long stock** (sell stock, buy call + sell put same strike → turns a
   conversion into a box).
- **Stock split Y-for-X** (each X shares → Y shares). To preserve equity:
   ```
   new stock price  = old price   × X/Y
   new strike       = old strike  × X/Y
   new option count = old count    × Y/X
   underlying contract size: unchanged (100 sh) if Y is a whole number
   new delta position = old delta × Y/X
   new gamma position = old gamma × (X/Y)²
   theta, vega, rho:  UNCHANGED
   ```
   For non-integer Y (e.g. 3-for-2), the clearinghouse keeps option count integer and instead
   **adjusts the contract's share multiplier** (100 × 3/2 = 150 shares/contract). Economically a
   split is just an accounting re-denomination — no real risk change — *unless* the dividend is also
   altered (splits often accompany dividend hikes).

### 21.8 What a quant should remember (Ch. 21)

- **Greeks are a tangent line at today's point.** Always run the position across a *range* of price,
   vol, and time (P&L graphs + a risk-sensitivity table) — local neutrality hides large directional/
   convexity risk elsewhere.
- Two back-of-envelope gems: **delta-neutral price ≈ S − delta/gamma**, and **breakeven vol ≈
   current vol ± edge/|vega|**.
- **Always compute the net upside/downside contract position** — the gap-risk you're left holding
   after a catastrophic move, which the smooth Greeks won't warn you about.
- Manage by **diversifying across strikes/expiries** and obeying preset risk limits; survival beats
   optimization.

---

## Batch 5 — Top 10 durable lessons

1. **delta = N(d1); true ITM probability = N(d2); and N(d1) > N(d2) always.** Delta is NOT a
   probability — it systematically overstates the chance of finishing in the money (gap grows with
   σ√t).
2. **Black-Scholes is a no-arbitrage *replication* price** built on continuous costless delta
   hedging at the risk-free rate with **constant, known volatility** — and every one of those
   assumptions is where real markets bite. It can't price American early exercise.
3. **The binomial tree is the general pricer:** backward induction taking `max(continuation,
   intrinsic)` at each node handles American exercise that BS cannot, and **converges to BS** for
   European options as steps → ∞. `u = e^(σ√(t/n))`, `d = 1/u`, risk-neutral `p` set so the
   underlying drifts at the carry rate (p can exceed 1 / go negative = *pseudoprobabilities*).
4. **Realized (future) volatility is the ONLY thing that determines a held-to-expiry P&L.** Implied
   vol matters for interim marks, capital, and exit timing — but value is set by realized vol.
5. **Implied vol LAGS realized vol and is a biased, usually-too-HIGH forecast** → options are on
   average overpriced (the **volatility risk premium**), the structural edge of net option selling,
   paid for bearing rare vol explosions (insurance analogy).
6. **Vol is forecastable because of three facts: mean reversion, serial correlation (clustering),
   and the vol cone (term structure).** Match your historical-vol lookback window to the option's
   time-to-expiration; for long horizons just use the long-run mean.
7. **Variance is additive in time (vol ∝ √t)** → forward volatility
   `σ_f = √[(σ₂²t₂ − σ₁²t₁)/(t₂−t₁)]`; and a calendar spread's implied vol ≈ **spread price ÷ spread
   vega**. Both surface which expiration is rich/cheap relative to others.
8. **Range-based historical-vol estimators (Parkinson high-low, Garman–Klass OHLC) are more
   efficient than close-to-close** for continuously-traded instruments; blend with close-to-close
   for partial-session products (weight by fraction of day the market is open).
9. **Greeks are a snapshot at today's point — zero Greeks now ≠ no risk.** Always stress the
   position across a *range* of price/vol/time (P&L graphs + sensitivity table). Two field gems:
   **delta-neutral price ≈ S − delta/gamma** and **breakeven vol ≈ current vol ± edge/|vega|**.
10. **Always compute the net upside/downside contract position** (what underlying exposure remains
    after a catastrophic gap) and **diversify risk across strikes/expiries** — concentrated risk at
    one strike/expiry is the silent killer. Survival beats optimization.

---

## Vol-estimation ideas for OUR project

Practical, implementable vol-estimation and vol-signal ideas extracted from this batch, oriented to
a paper-trading quant build. (Flagging where the book gives a method we can code vs. a principle to
respect.)

**A. Estimators we can compute from OHLCV bars**
1. **Close-to-close log-return stdev with zero-mean and n−1 denominator**, annualized by
   √(periods/yr). This is the baseline realized-vol feature. Use **log returns** `ln(p_t/p_{t-1})`
   and **force μ=0** (Natenberg's convention) so all movement counts.
2. **Parkinson (high-low) estimator**: `σ_Park ≈ √[ (1/(4 ln2)) · mean( ln(H/L)² ) / t ]`. Higher
   information per bar than close-to-close. **(verify constant 1/(4 ln2) ≈ 0.361.)**
3. **Garman–Klass (OHLC)**: `≈ √[ mean( 0.5·ln(H/L)² − (2ln2−1)·ln(C/O)² ) / t ]`. Use when the
   instrument trades ~continuously over the bar; **down-weight / blend with close-to-close for
   instruments with big untraded overnight gaps** (e.g. equities/index with overnight risk).
   → Actionable: build all three as parallel features; they disagree in informative ways (a
   close-to-close >> range estimator means the move was overnight-gap-driven, not intraday).

**B. Vol forecasting features (lean on the three stylized facts)**
4. **Compute a panel of historical vols over multiple lookbacks** (e.g. ~1w, 2w, 1m, 3m, 6m, 1y).
   This is the raw material for both forecasting AND the vol cone.
5. **Horizon-matched weighting**: when forecasting vol for a holding period of length H, weight the
   lookback window closest to H the most (serial-correlation justification). For long horizons,
   shrink hard toward the **long-run mean** (mean reversion).
6. **Mean-reversion signal**: track `current_HV − long_run_mean_HV`. A large positive gap is a
   *short-vol/expect-vol-to-fall* signal; large negative gap is *long-vol/expect-vol-to-rise*. This
   is the single most exploitable vol property in the book. (Pairs naturally with a z-score:
   `(HV − mean)/std_of_HV`.)
7. **Vol cone as a calibration/anomaly tool**: build the min/avg/max realized-vol envelope vs.
   window length from history; flag when current implied or realized vol for a given horizon pokes
   outside its historical cone band → "cheap/rich" relative to its own history (Burghardt–Lane
   "how to tell if options are cheap" idea cited in the text).
8. **Persistence/clustering**: vol is serially correlated → an AR/EWMA-style recency-weighted blend
   of recent HVs is a reasonable, low-parameter forecaster. (The book endorses recency + regressive
   weighting; it does NOT hand us a GARCH(1,1) equation — if we use GARCH we're going beyond
   Natenberg, but its three facts (mean reversion + persistence + recency) are exactly what GARCH
   parameterizes.)

**C. Implied-vs-realized as a signal (the vol risk premium)**
9. **Track the implied − realized spread.** Natenberg's data: implied is on average TOO HIGH (vol
   risk premium), and realized **leads** implied. Two usable signals:
   - **VRP carry**: when implied >> recent realized (and we expect mean reversion), the structural
     edge favors **net short vega/gamma** (selling premium) — but size for tail risk, because the
     rare miss (2008-style) is brutal (implied was too LOW by ~50 vol pts at the worst).
   - **Realized-leads-implied momentum**: a *rising* realized vol tends to drag implied up with a
     lag → if realized is breaking out, front-month implied is likely to follow (a long-vega entry
     before the IV catch-up).
10. **Don't treat implied vol as the truth.** It's a biased forecast; our realized-vol estimators +
    mean-reversion view are an independent (and per the book, often better-calibrated) opinion to
    trade against implied.

**D. Term-structure / relative-value (multi-expiry) vol signals**
11. **Forward vol** between two expiries: `σ_f = √[(σ₂²t₂ − σ₁²t₁)/(t₂−t₁)]`. Compute the forward-vol
    curve from listed IVs to spot which expiration is locally rich/cheap; a kinked forward-vol curve
    flags a calendar/time-butterfly opportunity.
12. **Calendar-spread implied vol ≈ spread price ÷ spread vega** (ATM). Cheap relative-value screen
    across adjacent expiries without a full surface fit.
13. **Respect IV term-structure dynamics in any vega aggregation**: distant-month IV moves at a
    *fraction* of front-month IV (mean reversion) → **weight each expiry's vega by its
    responsiveness** before calling a multi-expiry book "vega-neutral." Raw vega-sum can read 0 while
    true vega is materially nonzero.
14. **Seasonality overlay** where relevant (energy/ags): some expiries carry persistent IV premia
    (e.g. natgas October / hurricane season). If we ever trade those underlyings, model a seasonal
    vol factor, don't fit a single smooth term structure.

**E. Risk-management hygiene for any vol strategy we deploy**
15. **Position breakeven vol = entry_vol ± edge/|vega|** — compute it for every position so we know
    our vol margin-of-error up front.
16. **Always log the net upside/downside contract position** (gap exposure) and **diversify across
    strikes/expiries** — concentrated negative gamma at one strike is the classic blow-up. Local
    Greeks won't warn us; the contract-position check will.
17. **Stress across price × vol × time**, not just at spot — a delta/vega-neutral-today position can
    gyrate badly elsewhere (higher-order Greeks: vanna, volga, speed, color).

> **Bottom line for the project's vol-signal hunt:** the highest-conviction, most-Natenberg-endorsed
> edges are (1) **mean-reversion of realized vol** (trade current-vs-mean gaps), (2) the **volatility
> risk premium** (implied systematically > realized → net-short-premium carry, tail-sized), and
> (3) **realized-leads-implied** timing. Build robust realized-vol estimators (close-to-close +
> Parkinson + Garman–Klass), a multi-lookback vol panel, a vol cone, and an implied−realized spread
> series — those four artifacts feed all three edges.
