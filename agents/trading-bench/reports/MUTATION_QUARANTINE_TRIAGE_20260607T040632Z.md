# Mutation Quarantine Triage — 4-Family `__mut_` Pile

_Generated: 2026-06-07T04:06:32Z (UTC) · Subagent: mutation-quarantine-triage · PAPER/BACKTEST ONLY — nothing scheduled, nothing ordered._

**Scope:** the 48 `strategies_candidates/*__mut_*` dirs descended from 4 parent families
(`sma_crossover_qqq` 13, `breakout_xlk_regime` 13, `sma_crossover_qqq_regime` 12, `breakout_xlk` 10).
The ~48 other distinct-archetype dirs (`xsec_*`, `pead_*`, `credit_*`, `vol_regime_*`, `cot_*`, `tsmom_*`, …) were **not touched**.

Method: read each dir's `strategy.py` docstring + `params.json`; md5-hashed every `strategy.py`; cross-referenced all 117 `TOURNAMENT_ROUND_*.md` bodies by candidate name to pull walk-forward metrics (median return, % windows positive, median Sharpe, and the "beats parent by +Xpp" gate delta) for the round(s) each was scored in.

---

## 0. Headline findings (read these first)

1. **The pile is 2 edges in 48 costumes.** All 4 "parents" reduce to **two underlying signals**: a 10/30 **SMA crossover** (on QQQ) and a **20-bar Donchian breakout** (on XLK). The `_regime` variants are the same two signals + a "SPY > 50d SMA" entry gate. Everything in this quarantine is a stop/target/filter wrapper on one of those two signals. Diversification here is **illusory**.

2. **The dir NAME is unreliable — there is heavy cross-family relabeling.** Many dirs named `sma_crossover_qqq*` actually contain **breakout-XLK code** (e.g. `sma_crossover_qqq__mut_0b11ed/2728d3/bef4cc/d17bb6` are byte-identical to the breakout regime-gate). Classification below uses the **effective signal in the code**, not the dir name.

3. **11 of the 48 are byte-for-byte identical files** (md5 `c10653…`) — the *plain SPY-regime-gate breakout*, `symbol=XLK lookback=20 regime_period=50`, no extra threshold. They are duplicated across all 4 family names. **All 11 are REJECT_GATE (Δ≈+0.00pp) in every round they appear — they never actually promoted.** They are the regime-parent baseline re-measured under 11 different folder names. Pure clutter.

4. **The promotions are window-luck, not edge.** The gate fires on *median walk-forward return beating parent by ≥0.10pp*. The same candidate swings wildly across re-runs — e.g. `breakout_xlk__mut_87fa4b` medSharpe ranges **−0.88 … 3.18**, `sma_crossover_qqq__mut_eae738` **−1.39 … 3.18**, `breakout_xlk_regime__mut_9e748e` flips **REJECT_GATE(+0.33%) → PROMOTE(+3.17%)** across two rounds with the *same code*. That instability is the overfit signature: the "edge" is which 8-window split it landed in.

5. A recurring **`medRet≈+0.33% / pos=75% / medSharpe=3.18`** triplet is the **regime-parent's own number**. Any candidate reporting exactly that is contributing nothing over the parent.

---

## A. Dedupe — grouped by (effective signal × symbol × regime × mutation type)

Within each group, **KEEP** = best by (median Sharpe → % positive → median return) on its promote/best round; **REDUNDANT** = a sibling with the same mutation that adds nothing distinct.

### A1. The exact-duplicate cluster (md5 `c10653…`) — plain regime-gate breakout, XLK
11 identical files. None ever promoted (all REJECT_GATE, Δ≈+0.00pp, ~+0.33%/75%/3.18). **Keep 0 for promotion; if any single copy is retained it's only as the parent baseline reference.**

| dir | verdict history | disposition |
|---|---|---|
| `breakout_xlk__mut_bef4cc` | REJECT_GATE | **KEEP (canonical baseline ref only)** |
| `breakout_xlk__mut_f111eb` | REJECT_GATE | REDUNDANT (dup) |
| `breakout_xlk_regime__mut_87fa4b` | REJECT_GATE | REDUNDANT (dup) |
| `breakout_xlk_regime__mut_d17bb6` | REJECT/REJECT_GATE | REDUNDANT (dup) |
| `sma_crossover_qqq__mut_0b11ed` | REJECT_GATE | REDUNDANT (dup, mislabeled) |
| `sma_crossover_qqq__mut_2728d3` | REJECT_GATE | REDUNDANT (dup, mislabeled) |
| `sma_crossover_qqq__mut_bef4cc` | REJECT_GATE | REDUNDANT (dup, mislabeled) |
| `sma_crossover_qqq__mut_d17bb6` | REJECT_GATE | REDUNDANT (dup, mislabeled) |
| `sma_crossover_qqq_regime__mut_87fa4b` | REJECT_GATE | REDUNDANT (dup, mislabeled) |
| `sma_crossover_qqq_regime__mut_9e748e` | REJECT_GATE | REDUNDANT (dup, mislabeled) |
| `sma_crossover_qqq_regime__mut_d17bb6` | REJECT_GATE | REDUNDANT (dup, mislabeled) |

→ **10 REDUNDANT** from this cluster alone.

### A2. Donchian breakout, XLK (no regime) — `breakout_xlk` parents
Each mutation type appears once; all distinct code. No intra-group dup. Metrics on best/promote round:

| dir | mutation | thr | medRet | pos | medSharpe | note |
|---|---|---|---|---|---|---|
| `breakout_xlk__mut_b58135` | +TP (add SMA-OR + TP) | tp 2.40% | +5.77 | 62% | **3.59** | best raw number in non-regime breakout, but pos only 62% |
| `breakout_xlk__mut_232050` | scale-out | 2.60% | +3.96 | 62% | 2.91 | = its regime twin's signal |
| `breakout_xlk__mut_3e03e4` | vol-gate | cap 1.1% | +3.96 | 62% | 2.91 | identical metrics to 232050 → filter barely bites |
| `breakout_xlk__mut_c382b1` | regime-cond-stop | 0.85/2.50% | +3.78 | 62% | 2.85 | |
| `breakout_xlk__mut_dd307e` | session-filter | RTH only | +2.38 | 62% | 1.88 | |
| `breakout_xlk__mut_386443` | confirm-delay | 2 bars | +0.23 | 62% | 1.51 | never promoted, Δ−0.17pp |
| `breakout_xlk__mut_eae738` | stop+TP, **SMH port** | 1.30/2.50% | +0.59 | 50% | 0.52 | weak; coin-flip pos |

**Group keep:** `breakout_xlk__mut_b58135` (highest Sharpe). Others distinct mutations, not exact dups, but several share the *same number* (232050≈3e03e4) → effectively redundant pair → mark `breakout_xlk__mut_3e03e4` REDUNDANT-vs-232050.

### A3. Donchian breakout, XLK + regime gate — `breakout_xlk_regime` parents

| dir | mutation | thr | medRet | pos | medSharpe | note |
|---|---|---|---|---|---|---|
| `breakout_xlk_regime__mut_c382b1` | regime-cond-stop | 0.6/1.8% | +3.47 | 62% | **3.62** | top Sharpe of this group |
| `breakout_xlk_regime__mut_0b11ed` | take-profit | 2.3% | +3.28 | 75% | 3.60 | nearly tied, better pos% |
| `breakout_xlk_regime__mut_2728d3` | cooldown | 12 bars | +3.33 | 75% | 3.33 | |
| `breakout_xlk_regime__mut_3e03e4` | vol-gate | cap 1.4% | +3.33 | 75% | 3.33 | identical to 2728d3 → filter inert |
| `breakout_xlk_regime__mut_9e748e` | time-stop | 43 bars (p75) | +3.17 | 88% | 3.18 | **OVERFIT — see C** |
| `breakout_xlk_regime__mut_f111eb` | trailing-stop | 1.4% | +2.66 | 75% | 2.92 | |
| `breakout_xlk_regime__mut_bef4cc` | stop-loss | 0.7% | +2.56 | 62% | 2.89 | |
| `breakout_xlk_regime__mut_dd307e` | session-filter | 14:30–20:00 | +2.53 | 75% | 2.41 | |
| `breakout_xlk_regime__mut_232050` | scale-out | 2.5% | +0.33 | 75% | 3.18 | = parent baseline, REJECT_GATE |
| `breakout_xlk_regime__mut_386443` | confirm-delay | 2 bars | +1.74 | 75% | 1.49 | |
| `breakout_xlk_regime__mut_eae738` | stop+TP, **SMH port** | 1.2/2.5% | +0.48 | 50% | 0.50 | weak |

**Group keep:** `breakout_xlk_regime__mut_c382b1` (Sharpe 3.62) **or** `__mut_0b11ed` (3.60 @ 75% pos — better positive rate, prefer this). Mark `breakout_xlk_regime__mut_3e03e4` REDUNDANT-vs-2728d3 (identical metrics, filter doesn't bite); `__mut_232050` REDUNDANT (= parent baseline).

### A4. SMA crossover, QQQ (no regime) — `sma_crossover_qqq` parents

| dir | mutation | thr | medRet | pos | medSharpe | note |
|---|---|---|---|---|---|---|
| `sma_crossover_qqq__mut_f111eb` | trailing-stop | 0.85% | +3.69 | 62% | **3.04** | best of group |
| `sma_crossover_qqq__mut_dd307e` | plain port (no extra) | — | +3.24 | 62% | 2.83 | |
| `sma_crossover_qqq__mut_232050` | scale-out | 1.17% | +3.13 | 62% | 2.68 | |
| `sma_crossover_qqq__mut_3e03e4` | vol-gate | cap 1.1% | +3.13 | 62% | 2.68 | identical to 232050 → filter inert |
| `sma_crossover_qqq__mut_9e748e` | time-stop | 39 bars | +3.13 | 62% | 2.68 | identical to 232050 → stop inert |
| `sma_crossover_qqq__mut_a6c41b` | regime-floor | floor 2% | +2.63 | 62% | 2.44 | |
| `sma_crossover_qqq__mut_386443` | confirm-delay | 2 bars | +2.11 | 62% | 1.88 | |
| `sma_crossover_qqq__mut_eae738` | plain port, **SMH** | — | +0.33 | 75% | 3.18→ but Sharpe range −1.39..3.18 | unstable, REJECT_GATE |
| `sma_crossover_qqq__mut_87fa4b` | **RSI mean-rev, IWM** | tp1.15/sl1.6/39 | −0.37 | 50% | −0.12 | losing; archetype drift |

**Group keep:** `sma_crossover_qqq__mut_f111eb` (Sharpe 3.04). Mark `__mut_3e03e4` and `__mut_9e748e` REDUNDANT-vs-232050 (all three print the identical +3.13/62%/2.68 → the vol-gate and the 39-bar time-stop never fire; they collapse to the same scale-out-or-parent behavior).

### A5. SMA crossover, QQQ + regime gate — `sma_crossover_qqq_regime` parents

| dir | mutation | thr | medRet | pos | medSharpe | note |
|---|---|---|---|---|---|---|
| `sma_crossover_qqq_regime__mut_c382b1` | regime-cond-stop | 0.48/1.32% | +4.76 | 75% | **3.47** | top number of the ENTIRE pile |
| `sma_crossover_qqq_regime__mut_bef4cc` | stop-loss | 0.6% | +4.47 | 75% | 3.31 | 2nd best |
| `sma_crossover_qqq_regime__mut_232050` | scale-out | 1.34% | +4.10 | 75% | 3.08 | |
| `sma_crossover_qqq_regime__mut_2728d3` | cooldown | 8 bars | +4.10 | 75% | 3.08 | identical to 232050 → cooldown inert |
| `sma_crossover_qqq_regime__mut_f111eb` | trailing-stop | 0.70% | +4.10 | 75% | 3.08 | identical to 232050 → trail inert |
| `sma_crossover_qqq_regime__mut_386443` | confirm-delay | 3 bars | +4.09 | 75% | 2.76 | |
| `sma_crossover_qqq_regime__mut_dd307e` | plain port | — | +3.05 | 75% | 2.47 | |
| `sma_crossover_qqq_regime__mut_b58135` | add-breakout-OR | lb 10 | +2.96 | 88% | 2.33 | highest pos% but lowest Sharpe |
| `sma_crossover_qqq_regime__mut_0b11ed` | take-profit | 1.1% | +0.41 | 75% | 2.95 | = parent baseline, REJECT_GATE |

**Group keep:** `sma_crossover_qqq_regime__mut_c382b1` (Sharpe 3.47, medRet +4.76, pos 75%). Mark `__mut_2728d3` and `__mut_f111eb` REDUNDANT-vs-232050 (identical +4.10/75%/3.08 → cooldown & 0.70% trail never trigger over these windows).

---

## B. Cross-family reality check (stated plainly)

> **This whole quarantine is 2 trading edges wearing 48 costumes.**
> - **Edge 1:** 10/30 SMA crossover, QQQ (the `sma_crossover_qqq[_regime]` lineage).
> - **Edge 2:** 20-bar Donchian breakout, XLK (the `breakout_xlk[_regime]` lineage).
> The `_regime` suffix just adds a "SPY above its 50-day SMA" entry gate to the same signal. Ports to IWM/SMH/SMH and the "OR a breakout"/"OR an SMA-cross" variants are the same two signals on a correlated tech/large-cap ETF. **Promoting more than one of these does NOT diversify the book** — they will be long the same tech-momentum factor at the same time. Treat the entire pile as **two correlated candidates max**, not 48.

---

## C. Overfit flags

- **`breakout_xlk_regime__mut_9e748e` (p75 time-stop = 43 bars) — textbook curve-fit, confirmed by its own docstring.** The author's honest-edge note computes that on the parent's 29 raw trades, holding-bars vs realized-return correlation is **+0.955**: the 8 trades held ≥43 bars averaged **+5.98% at 100% win-rate**, while the 21 trades under 43 bars averaged **−0.55% at 38% win-rate**. The p75 time-stop **amputates the parent's single best cohort** (the slow holds = all the winners) yet the gate still "improved" median return → the improvement is an artifact of the median statistic shifting, not a real edge. **Do not promote.** (It also flip-flopped REJECT_GATE→PROMOTE across rounds — instability on top of the structural flaw.)
- **Inert-filter family (filters that don't bite → metrics identical to the un-filtered sibling).** Strong overfit-adjacent smell — the cron promoted them as "distinct" but they collapse to the parent/sibling: `breakout_xlk__mut_3e03e4` (vol-gate ≡ 232050), `breakout_xlk_regime__mut_3e03e4` (vol-gate ≡ 2728d3), `sma_crossover_qqq__mut_3e03e4`+`__mut_9e748e` (vol-gate / 39-bar stop ≡ 232050), `sma_crossover_qqq_regime__mut_2728d3`+`__mut_f111eb` (cooldown / 0.70% trail ≡ 232050). When a threshold change produces *zero* metric change, the threshold is doing nothing — promoting it is noise.
- **Knife-edge / window-luck instability (huge metric swing, same code across rounds):** `breakout_xlk__mut_87fa4b` (Sharpe −0.88…3.18), `sma_crossover_qqq__mut_eae738` (−1.39…3.18), `sma_crossover_qqq_regime__mut_87fa4b` (−0.82…3.18), `breakout_xlk__mut_eae738` (0.52…3.18). These pass the gate only on the lucky split.
- **Archetype drift (not the family's edge at all):** `sma_crossover_qqq__mut_87fa4b` and `breakout_xlk__mut_87fa4b` are **RSI/Donchian mean-reversion on IWM** — a contrarian flip, not the parent's momentum signal. `sma_crossover_qqq__mut_87fa4b` is outright **losing (medRet −0.37%, Sharpe −0.12)**. These shouldn't be filed under these parents.
- **Sample size caveat (applies to ALL 48):** "8 walk-forward windows" / 29–45 parent trades is a tiny sample. A +3pp median-return beat on 8 windows is **not** statistically distinguishable from noise. Median-return-beats-parent is a **weak gate** (see D).
- **Unit-convention inconsistency (housekeeping, not overfit):** params mix `0.012`(=1.2%) and `1.30`(=1.3%) styles for the same concept across dirs. Code reads each consistently, so it's not a bug today, but it's an accident waiting to happen. (Checked: `trail_pct=0.7`→0.70% and `scale_out_pct=1.34`→1.34% are **correctly** the parent p25/median runup, NOT broken 70%/134% values — not flagged.)

---

## D. VERDICT

**Honest read: NONE of the 48 clears the bar for a paper-trading clock. Recommend purge + fix the gate.**

Rationale (skeptical, per SOUL.md — Sharpe + sample size, not vibes):
- The gate that promoted these — *median walk-forward return beats parent by ≥0.10pp over 8 windows* — is a **weak, noise-dominated bar**. The same code flips PROMOTE↔REJECT across re-runs; medSharpe for individual candidates swings across **the full −1.4 → +3.6 range** depending on the split. That is the definition of overfitting to the window selection.
- "Best" numbers (`sma_crossover_qqq_regime__mut_c382b1` +4.76%/Sharpe 3.47; `breakout_xlk_regime__mut_0b11ed` Sharpe 3.60) sit on **62–75% positive over only 8 windows** — a positive rate that a coin-flip-plus-drift can produce. **Zero live out-of-sample trades exist.**
- The pile is **2 correlated edges**; even the survivors don't diversify.

**If — and only if — Tessera insists on giving exactly ONE candidate a paper clock to generate real OOS data, the least-bad three to consider (with the caveat that this is "least-bad," not "good"):**

1. **`sma_crossover_qqq_regime__mut_c382b1`** — regime-conditional stop on QQQ SMA-cross. Highest medRet (+4.76%) and best Sharpe@75%-pos (3.47) of the whole pile; the mutation (asymmetric stop tight-in-bear/loose-in-bull) is *economically motivated*, not a fitted filter, and it's a distinct code path (not a clone). **Top pick if one must ship.**
2. **`breakout_xlk_regime__mut_0b11ed`** — take-profit on the breakout regime signal. Sharpe 3.60 @ 75% pos; represents the *other* underlying edge (breakout, not SMA-cross), so if you wanted two, this is the diversifying second — but it's still the same tech-momentum factor.
3. **`sma_crossover_qqq__mut_f111eb`** — peak-trailing-stop on the un-regime-gated QQQ cross (Sharpe 3.04). Only as a "no regime gate" comparison arm.

**But the recommended action is to ship none and fix the process first.** Paper-trading a window-luck winner just launders overfit into "it traded live" credibility.

### REDUNDANT dir count: **18**

Composition: **10** exact-clones (the `c10653…` cluster minus the 1 kept as baseline ref) **+ 6** inert-filter siblings (threshold doesn't bite → metrics byte-identical to a kept sibling) **+ 2** "= parent baseline" REJECT_GATE dirs (contribute exactly the parent's number). Note: this 18 is the *strictly-provable* redundant set; the looser truth is that **~40 of the 48 add nothing** once you keep one representative per genuinely-distinct mutation, because the whole pile is only 2 edges (Section B).

Full REDUNDANT dir list (safe-to-purge — none of these is the keep-pick or a distinct-edge candidate):

**Exact code-clones (10):**
```
breakout_xlk__mut_f111eb
breakout_xlk_regime__mut_87fa4b
breakout_xlk_regime__mut_d17bb6
sma_crossover_qqq__mut_0b11ed
sma_crossover_qqq__mut_2728d3
sma_crossover_qqq__mut_bef4cc
sma_crossover_qqq__mut_d17bb6
sma_crossover_qqq_regime__mut_87fa4b
sma_crossover_qqq_regime__mut_9e748e
sma_crossover_qqq_regime__mut_d17bb6
```
(kept as canonical baseline ref: `breakout_xlk__mut_bef4cc`)

**Inert-filter siblings — metrics identical to a kept sibling, so the mutation does nothing over these windows (6):**
```
breakout_xlk__mut_3e03e4                (vol-gate ≡ breakout_xlk__mut_232050)
breakout_xlk_regime__mut_3e03e4         (vol-gate ≡ breakout_xlk_regime__mut_2728d3)
sma_crossover_qqq__mut_3e03e4           (vol-gate ≡ sma_crossover_qqq__mut_232050)
sma_crossover_qqq__mut_9e748e           (39-bar time-stop ≡ sma_crossover_qqq__mut_232050)
sma_crossover_qqq_regime__mut_2728d3    (cooldown ≡ sma_crossover_qqq_regime__mut_232050)
sma_crossover_qqq_regime__mut_f111eb    (0.70% trail ≡ sma_crossover_qqq_regime__mut_232050)
```

**= parent baseline (REJECT_GATE, +0.00pp over parent) (2):**
```
breakout_xlk_regime__mut_232050         (scale-out → +0.33%/75%/3.18 = parent)
sma_crossover_qqq_regime__mut_0b11ed    (take-profit → +0.41%/75%/2.95 = parent)
```

---

## E. Recommendation for the hourly mutation cron

**One line:** **THROTTLE + TIGHTEN-THE-GATE + DIVERSIFY-PARENTS — and de-dup before promote.** Specifically: (a) the cron is re-promoting byte-identical files and inert-filter no-ops under different names — add an **md5/behavior dedup + "filter must change ≥X% of trades or it's rejected" check** before any PROMOTE; (b) replace the weak *"+0.10pp median walk-forward return beats parent"* gate with a **risk-adjusted, stability-aware bar** (require a Sharpe improvement that holds across a *fixed* window set, plus a minimum-trades floor, plus penalize candidates whose metric swings sign across re-runs); (c) **stop fanning the same 2 signals** — the parent pool is just SMA-cross-QQQ and breakout-XLK, so it can only ever produce correlated overfit; feed it genuinely different base archetypes; (d) **throttle from hourly** — hourly LLM mutation on a 2-signal pool with a noise-level gate is a redundant-dir factory, not research. Until the gate is fixed, **freeze promotions from these 4 families.**

---

_End of report. Subagent took no mutating action on `strategies/`, scheduled no cron, placed no orders._