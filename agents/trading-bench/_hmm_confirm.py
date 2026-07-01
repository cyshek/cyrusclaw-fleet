"""HMM / Markov-switching latent-state regime gate — CONFIRM-OR-KILL vs the
incumbent SMA-200 + {30,90,180}-breadth binary/vol-target gate.

RESEARCH-ONLY. Writes ONLY:
  - reports/HMM_VERDICT_<UTCSTAMP>.md
  - reports/_hmm_result.json
Does NOT modify runner/, strategies/, crontab, any .db, or any tracker.
Does NOT pip install. Hand-rolled Gaussian HMM in pure numpy/scipy.

MECHANISM
=========
- Feature(s): daily log-returns of the sleeve underlying (QQQ). Baseline K=2/K=3.
  Also test augmenting with 20d realized vol as a 2nd emission channel, and
  optionally VIX level as a 3rd channel.
- Fit a K-state Gaussian HMM via Baum-Welch (forward-backward, FIT-ONLY) on an
  EXPANDING, PAST-ONLY window; re-fit MONTHLY (fit at month m uses data <= last
  day of month m-1 ONLY).
- Online FORWARD FILTER ONLY for the live posterior P(bear | data <= t). No
  Viterbi, no backward smoothing (would leak future). Bear state = higher-vol /
  lower-mean fitted state; stable label across re-fits (label-switch handled).
- Exposure rule: hold sleeve when P(bear) < theta; de-risk (to cash, and
  separately to the rotation sleeve) when P(bear) >= theta. Sweep theta.
- PAST-ONLY: exposure for bar t uses posterior computed through bar t-1 (idx-1),
  exactly like the incumbent gate.

HEAD-TO-HEAD (same instrument = TQQQ sleeve, same path, net 2bps)
- (1) INCUMBENT: SMA-200 + {30,90,180}-breadth vol-target gate (reconstructed
      via build_sleeves' VolTargetParams, READ-ONLY import).
- (2) UNGATED: always-in vol-target sleeve (no trend/breadth protection).
- (3) HMM-gate: SAME vol-target sizing, trend gate REPLACED by HMM posterior.

The APPLES-TO-APPLES swap: the incumbent's exposure = breadth_g * voltarget_w.
The HMM book's exposure = hmm_gate * voltarget_w, where voltarget_w is the
IDENTICAL inverse-vol sizing (target 25% ann vol, 20d window, w_max=1.0). Only
the trend/regime GATE differs (breadth-fraction vs HMM-posterior threshold).
So a win/loss is attributable purely to the gate mechanism.
"""
from __future__ import annotations

import bisect
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

import sys
sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from runner import fp_sharpe as fps
from runner.backtest import bars_per_year

# READ-ONLY reconstruction of the incumbent + sizing primitives
from strategies_candidates.leveraged_long_trend import backtest_daily_voltarget as bd
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget, realized_ann_vol,
)

TRADING_DAYS = 252
BPY = bars_per_year("1Day", False)  # 252 for equities
COST_BPS = 2.0
OOS_SPLIT = "2020-01-01"      # task text: IS<=2019, OOS 2020+
OOS_SPLIT_ALT = "2019-01-01"  # secondary split reported for robustness

RNG = np.random.default_rng(20260701)


# ======================================================================== #
# PURE-NUMPY GAUSSIAN HMM  (Baum-Welch fit + online forward filter)
# ======================================================================== #
class GaussianHMM:
    """Diagonal-covariance Gaussian HMM, hand-rolled.

    States K, emission dim D. Params:
      pi (K,)         initial state dist
      A  (K,K)        row-stochastic transition matrix  A[i,j]=P(s_t=j|s_{t-1}=i)
      mu (K,D)        emission means
      var (K,D)       emission variances (diagonal cov)

    FIT: Baum-Welch EM (forward-backward on a FIXED past-only window). Uses
    scaled forward-backward for numerical stability. This looks at the WHOLE
    training window (that is fine: fitting is done only on past data, re-fit
    monthly on the expanding past-only window; the LIVE signal never uses
    backward smoothing).

    LIVE: forward_filter() returns the FORWARD-ONLY posterior gamma_t =
    P(s_t | x_1..x_t) for every t — no future data. This is the signal.
    """

    def __init__(self, K: int, D: int):
        self.K = int(K)
        self.D = int(D)
        self.pi = np.full(K, 1.0 / K)
        self.A = np.full((K, K), 1.0 / K)
        self.mu = np.zeros((K, D))
        self.var = np.ones((K, D))
        self.fitted = False
        self.loglik = -np.inf

    # ---- emission log-density: log N(x | mu_k, diag(var_k)) ----
    def _log_emission(self, X: np.ndarray) -> np.ndarray:
        """X (T,D) -> logB (T,K) log emission prob of each obs under each state."""
        T = X.shape[0]
        v = np.maximum(self.var, 1e-12)          # (K,D) floor
        # log N = -0.5*[ D*log(2pi) + sum_d log v_kd + sum_d (x_d-mu_kd)^2 / v_kd ]
        const = -0.5 * (self.D * math.log(2.0 * math.pi) + np.sum(np.log(v), axis=1))  # (K,)
        logB = np.empty((T, self.K))
        for k in range(self.K):
            diff = X - self.mu[k]                 # (T,D)
            quad = np.sum((diff * diff) / v[k], axis=1)  # (T,)
            logB[:, k] = const[k] - 0.5 * quad
        return logB

    # ---- scaled forward pass (numerically stable) ----
    def _forward_scaled(self, logB: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """Return (alpha_hat (T,K) normalized filtered posteriors, c (T,) scaling
        factors, loglik). alpha_hat[t] = P(s_t | x_1..x_t) (the FORWARD FILTER).
        We work with B (not logB) per-row-rescaled by the row max to avoid
        underflow while keeping the normalization exact per step."""
        T = logB.shape[0]
        K = self.K
        alpha = np.empty((T, K))
        c = np.empty(T)
        # convert logB rows to unnormalized B via per-row max subtraction; the
        # per-row constant cancels in alpha_hat because we renormalize each step.
        rowmax = np.max(logB, axis=1, keepdims=True)     # (T,1)
        B = np.exp(logB - rowmax)                        # (T,K) scaled emissions
        # t=0
        a0 = self.pi * B[0]
        s0 = a0.sum()
        if s0 <= 0:
            s0 = 1e-300
        alpha[0] = a0 / s0
        c[0] = s0
        for t in range(1, T):
            at = (alpha[t - 1] @ self.A) * B[t]
            st = at.sum()
            if st <= 0:
                st = 1e-300
            alpha[t] = at / st
            c[t] = st
        # loglik = sum log(c_t) + sum rowmax (the per-row constants we pulled out)
        loglik = float(np.sum(np.log(np.maximum(c, 1e-300))) + np.sum(rowmax))
        return alpha, c, loglik

    # ---- scaled backward pass (FIT-ONLY; never used for the live signal) ----
    def _backward_scaled(self, logB: np.ndarray, c: np.ndarray) -> np.ndarray:
        T = logB.shape[0]
        K = self.K
        beta = np.empty((T, K))
        rowmax = np.max(logB, axis=1, keepdims=True)
        B = np.exp(logB - rowmax)
        beta[T - 1] = 1.0
        for t in range(T - 2, -1, -1):
            bt = self.A @ (B[t + 1] * beta[t + 1])
            # scale by same c[t+1] used in forward (keeps gamma/xi consistent)
            denom = c[t + 1] if c[t + 1] > 0 else 1e-300
            beta[t] = bt / denom
        return beta

    def fit(self, X: np.ndarray, n_iter: int = 40, tol: float = 1e-3,
            n_restarts: int = 3) -> "GaussianHMM":
        """Baum-Welch EM with random restarts; keep best loglik. Early-stop on
        relative loglik improvement < tol (per-point) after a warm-up."""
        best = None
        best_ll = -np.inf
        for _ in range(n_restarts):
            self._init_params(X)
            ll_prev = -np.inf
            for _it in range(n_iter):
                logB = self._log_emission(X)
                alpha, c, ll = self._forward_scaled(logB)
                beta = self._backward_scaled(logB, c)
                # gamma (T,K) = smoothed posterior (FIT-ONLY)
                gamma = alpha * beta
                gsum = gamma.sum(axis=1, keepdims=True)
                gsum[gsum <= 0] = 1e-300
                gamma = gamma / gsum
                self._m_step(X, logB, alpha, beta, c, gamma)
                # relative per-point improvement early-stop
                if _it > 3 and (ll - ll_prev) < tol * abs(ll_prev):
                    ll_prev = ll
                    break
                ll_prev = ll
            # final loglik with the last params
            logB = self._log_emission(X)
            _, _, ll_final = self._forward_scaled(logB)
            if ll_final > best_ll:
                best_ll = ll_final
                best = (self.pi.copy(), self.A.copy(), self.mu.copy(), self.var.copy())
        # restore best
        self.pi, self.A, self.mu, self.var = best
        self.loglik = best_ll
        self.fitted = True
        self._canonical_order()
        return self

    def _init_params(self, X: np.ndarray) -> None:
        T, D = X.shape
        K = self.K
        # random-restart init: pick K distinct rows as means, global var, mild
        # sticky transitions (HMM regimes persist), uniform pi.
        idx = RNG.choice(T, size=K, replace=False)
        self.mu = X[idx].astype(float).copy()
        gvar = np.var(X, axis=0)
        gvar[gvar <= 0] = 1e-6
        self.var = np.tile(gvar, (K, 1)).astype(float)
        # sticky prior: 0.95 self, rest spread
        A = np.full((K, K), (0.05 / max(K - 1, 1)))
        np.fill_diagonal(A, 0.95)
        self.A = A
        self.pi = np.full(K, 1.0 / K)

    def _m_step(self, X, logB, alpha, beta, c, gamma) -> None:
        T, D = X.shape
        K = self.K
        rowmax = np.max(logB, axis=1, keepdims=True)
        B = np.exp(logB - rowmax)
        # xi_t(i,j) propto alpha_t(i) A(i,j) B_{t+1}(j) beta_{t+1}(j) / c_{t+1}
        # VECTORIZED over t (no Python loop). For the transition M-step only the
        # SUM over t of the per-step-NORMALIZED xi matters; but the standard
        # Baum-Welch update A_ij = sum_t xi_t(i,j) / sum_t gamma_t(i) uses the
        # UN-per-step-normalized xi with the same global scaling. We use the
        # scaled recursion's identity: sum_t alpha_t(i) A_ij Bp_t(j) beta_{t+1}(j)/c_{t+1}
        # where Bp_t(j)=B[t+1,j]. Assemble tensor and sum.
        denom = np.where(c[1:] > 0, c[1:], 1e-300)          # (T-1,)
        left = alpha[:-1]                                    # (T-1,K)  alpha_t(i)
        right = (B[1:] * beta[1:]) / denom[:, None]          # (T-1,K)  Bp beta / c
        # xi_sum[i,j] = A[i,j] * sum_t left[t,i]*right[t,j]
        outer = left.T @ right                              # (K,K) = sum_t left_i right_j
        A_new = self.A * outer                              # (K,K)
        rowsum = A_new.sum(axis=1, keepdims=True)
        rowsum[rowsum <= 0] = 1e-300
        self.A = A_new / rowsum
        # pi = gamma_0
        self.pi = gamma[0] / max(gamma[0].sum(), 1e-300)
        # means / vars weighted by gamma
        Nk = gamma.sum(axis=0)                    # (K,)
        Nk_safe = np.where(Nk > 0, Nk, 1e-300)
        for k in range(K):
            w = gamma[:, k][:, None]              # (T,1)
            mu_k = (w * X).sum(axis=0) / Nk_safe[k]
            diff = X - mu_k
            var_k = (w * diff * diff).sum(axis=0) / Nk_safe[k]
            var_k = np.maximum(var_k, 1e-10)      # variance floor
            self.mu[k] = mu_k
            self.var[k] = var_k

    def _canonical_order(self) -> None:
        """Sort states by ascending mean of channel-0 (the return channel) so the
        HIGHEST-index state is the most bearish is NOT guaranteed; instead we
        expose bear_state() explicitly. Here we just fix a deterministic order
        (by return-channel mean ascending) to make params readable/stable."""
        order = np.argsort(self.mu[:, 0])          # ascending return-mean
        self.mu = self.mu[order]
        self.var = self.var[order]
        self.pi = self.pi[order]
        self.A = self.A[order][:, order]

    def bear_state(self) -> int:
        """Identify the 'bear' state = the state with the LOWEST return-channel
        mean (mu[:,0]). Ties broken by HIGHER total variance (more turbulent).
        After _canonical_order the lowest-return state is index 0, but we compute
        explicitly to be robust and to support the label-stability anchor."""
        ret_mean = self.mu[:, 0]
        # candidates with (near-)lowest mean; pick highest variance among them
        lo = np.min(ret_mean)
        cand = np.where(ret_mean <= lo + 1e-12)[0]
        if len(cand) == 1:
            return int(cand[0])
        totvar = self.var.sum(axis=1)
        return int(cand[np.argmax(totvar[cand])])

    def forward_filter(self, X: np.ndarray) -> np.ndarray:
        """Online FORWARD-ONLY filtered posterior gamma_hat (T,K).
        gamma_hat[t] = P(s_t | x_1..x_t). NO future data. This is the live
        signal. Returns the full (T,K) array; caller takes column bear_state()."""
        logB = self._log_emission(X)
        alpha, _c, _ll = self._forward_scaled(logB)
        return alpha


# ======================================================================== #
# SANITY CHECK — recover a planted 2-regime series
# ======================================================================== #
def sanity_check_synthetic() -> Dict:
    """Plant a known 2-regime series (calm: mu=+0.0005 sd=0.008; storm: mu=-0.002
    sd=0.030) with sticky switching, fit K=2, confirm recovered means/vols and
    that the filtered bear-posterior separates the true regimes."""
    T = 4000
    p_stay = 0.98
    true_mu = np.array([0.0005, -0.002])
    true_sd = np.array([0.008, 0.030])
    states = np.zeros(T, dtype=int)
    s = 0
    for t in range(1, T):
        if RNG.random() > p_stay:
            s = 1 - s
        states[t] = s
    x = RNG.normal(true_mu[states], true_sd[states])
    X = x.reshape(-1, 1)
    hmm = GaussianHMM(2, 1).fit(X, n_restarts=5)
    bs = hmm.bear_state()
    gamma = hmm.forward_filter(X)
    pbear = gamma[:, bs]
    # recovered params (bear vs bull)
    bull = 1 - bs if hmm.K == 2 else int(np.argmax(hmm.mu[:, 0]))
    rec = {
        "true_mu": true_mu.tolist(), "true_sd": true_sd.tolist(),
        "rec_mu_bear": float(hmm.mu[bs, 0]), "rec_sd_bear": float(math.sqrt(hmm.var[bs, 0])),
        "rec_mu_bull": float(hmm.mu[bull, 0]), "rec_sd_bull": float(math.sqrt(hmm.var[bull, 0])),
        # discrimination: mean filtered P(bear) in TRUE-storm vs TRUE-calm bars
        "pbear_in_true_storm": float(pbear[states == 1].mean()),
        "pbear_in_true_calm": float(pbear[states == 0].mean()),
        "bear_state_idx": int(bs),
    }
    # pass criteria: bear vol clearly > bull vol; discrimination gap > 0.4
    rec["PASS"] = bool(
        rec["rec_sd_bear"] > 1.5 * rec["rec_sd_bull"] and
        (rec["pbear_in_true_storm"] - rec["pbear_in_true_calm"]) > 0.4
    )
    return rec


# ======================================================================== #
# DATA / FEATURES
# ======================================================================== #
def load_underlying_logrets(sym: str = "QQQ") -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Return (dates, logret, close) for the underlying. dates[k] is the END date
    of logret[k] (close-to-close). close[k] is adjclose on dates[k]."""
    bars = dbc.get_daily(sym)
    d = [b["date"] for b in bars]
    c = np.array([b["adjclose"] for b in bars], dtype=float)
    lr = np.zeros(len(c))
    lr[1:] = np.log(c[1:] / c[:-1])
    return d, lr, c


def realized_vol_channel(logret: np.ndarray, n: int = 20) -> np.ndarray:
    """Trailing n-day realized vol (stdev of logret through t, PAST-ONLY at each t).
    rv[t] uses logret[t-n+1..t]. For t<n uses expanding. Annualization NOT applied
    (HMM only needs a consistent scale); we z-ish scale later."""
    T = len(logret)
    rv = np.zeros(T)
    for t in range(T):
        lo = max(0, t - n + 1)
        w = logret[lo:t + 1]
        if len(w) >= 2:
            rv[t] = float(np.std(w))
        else:
            rv[t] = 0.0
    return rv


def load_vix_channel(dates: List[str]) -> Optional[np.ndarray]:
    """VIX level aligned to `dates`, PAST-ONLY (asof). Returns None if unavailable."""
    try:
        from runner import cboe_cache as cboe
        out = np.full(len(dates), np.nan)
        for i, d in enumerate(dates):
            lv = cboe.level_asof("VIX", d)
            if lv is not None:
                out[i] = float(lv)
        # forward-fill leading nans with first valid
        if np.all(np.isnan(out)):
            return None
        # simple ffill
        last = None
        for i in range(len(out)):
            if not np.isnan(out[i]):
                last = out[i]
            elif last is not None:
                out[i] = last
        # back-fill any leading nans
        first = None
        for i in range(len(out)):
            if not np.isnan(out[i]):
                first = out[i]
                break
        if first is not None:
            out[np.isnan(out)] = first
        return out
    except Exception:
        return None


# ======================================================================== #
# HMM GATE SIGNAL  (monthly re-fit, expanding past-only, forward-filter live)
# ======================================================================== #
def month_key(d: str) -> str:
    return d[:7]


def build_hmm_pbear(
    dates: List[str],
    feat: np.ndarray,           # (T, D) feature matrix, standardized per-fit
    K: int,
    min_train: int = 504,       # ~2y before first live signal
    refit_monthly: bool = True,
) -> Tuple[np.ndarray, List[Dict]]:
    """Produce the LIVE forward-filter P(bear|data<=t) for every t.

    - Re-fit at each month-open using data with END date <= last day of the
      PRIOR month (strictly past). Between re-fits, the SAME fitted model is
      used to forward-filter incoming bars.
    - Standardize features using ONLY the training window's mean/std (no future).
    - Label stability: bear_state defined by lowest-return-mean; we also anchor
      the posterior column by matching the new fit's bear-state mean vector to
      the previous fit (handled implicitly since bear_state() is a stable
      functional of the params, not an EM label index).
    - Returns (pbear (T,), fit_log). pbear[t] is P(bear | x_1..x_t) from the
      model fitted on data < current month. For t < min_train, pbear = 0.0
      (insufficient history -> treat as bull / fully-in, conservative).
    """
    T = feat.shape[0]
    pbear = np.zeros(T)
    fit_log: List[Dict] = []

    # month-open indices
    month_open = []
    seen = set()
    for i, d in enumerate(dates):
        mk = month_key(d)
        if mk not in seen:
            seen.add(mk)
            month_open.append(i)

    # Precompute month-open -> next-month-open segments. For month mi (open=mo),
    # the model fitted on data[:mo] (strictly before this month) governs bars
    # [mo, next_mo). We forward-filter data[:end] with the current model and
    # read alpha[t] for t in that segment. alpha carries state across bars.
    n_fits = 0
    for mi in range(len(month_open)):
        mo = month_open[mi]
        seg_end = month_open[mi + 1] if mi + 1 < len(month_open) else T
        # Need >= min_train past bars to fit; else leave pbear=0 for this segment.
        if mo < min_train:
            continue
        # (a) FIT on strictly-past data: feat[:mo] (END dates < this month-open).
        train = feat[:mo]
        cur_mean = train.mean(axis=0)
        cur_std = train.std(axis=0)
        cur_std[cur_std <= 1e-12] = 1.0
        Xtr = (train - cur_mean) / cur_std
        model = GaussianHMM(K, feat.shape[1]).fit(Xtr, n_restarts=4)
        bs = model.bear_state()
        n_fits += 1
        # (b) FORWARD-FILTER data[:seg_end] with this model, standardized by the
        #     TRAINING mean/std (no future leakage into the scaler). Read the
        #     bear-column posterior for bars in [mo, seg_end).
        Xall = (feat[:seg_end] - cur_mean) / cur_std
        alpha = model.forward_filter(Xall)     # (seg_end, K)
        pbear[mo:seg_end] = alpha[mo:seg_end, bs]
        fit_log.append({
            "month": dates[mo][:7], "fit_bars": int(mo),
            "bear_idx": int(bs),
            "mu": model.mu[:, 0].tolist(),
            "sd": np.sqrt(model.var[:, 0]).tolist(),
            "self_trans": np.diag(model.A).tolist(),
            "pbear_seg_mean": float(np.mean(pbear[mo:seg_end])) if seg_end > mo else 0.0,
        })
    return pbear, fit_log


# ======================================================================== #
# BACKTEST — apples-to-apples gate swap on the TQQQ vol-target sleeve
# ======================================================================== #
def _stats_from_daily_returns(dates: List[str], rets: np.ndarray) -> Dict:
    """CAGR / maxDD / ann vol / FP-Sharpe / total return from a daily-return
    series. FP-Sharpe uses the canonical ruler (sharpe_from_returns, sqrt(252))."""
    eq = np.empty(len(rets) + 1)
    eq[0] = 1.0
    for i, r in enumerate(rets):
        eq[i + 1] = eq[i] * (1.0 + r)
    n = len(rets)
    years = n / TRADING_DAYS if n else 0.0
    total = eq[-1] / eq[0] - 1.0
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0 if years > 0 and eq[-1] > 0 else 0.0
    # maxDD
    peak = eq[0]
    mdd = 0.0
    for v in eq:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < mdd:
            mdd = dd
    ann_vol = float(np.std(rets, ddof=1) * math.sqrt(TRADING_DAYS)) if n > 1 else 0.0
    sharpe = fps.sharpe_from_returns(rets.tolist(), BPY)
    return {
        "fp_sharpe": sharpe, "cagr_pct": cagr * 100.0, "max_drawdown_pct": mdd * 100.0,
        "ann_vol_pct": ann_vol * 100.0, "total_return_pct": total * 100.0, "n_days": n,
    }


def _slice_returns(dates: List[str], rets: np.ndarray, start: str, end: str) -> Tuple[List[str], np.ndarray]:
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    return dates[lo:hi], rets[lo:hi]


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or len(b) < 3:
        return float("nan")
    c = np.corrcoef(a, b)
    return float(c[0, 1])


# ---------------------------------------------------------------------- #
# Apples-to-apples gate-swap simulator.
# Replicates run_backtest_voltarget's inner loop EXACTLY (same vol-target
# sizing, same tbill cash, same 2bps abs-weight cost) but with a PLUGGABLE
# gate g(d_prev) in [0,1] that scales the vol-target weight. gate == None ->
# ungated (g=1 always). For the HMM book, gate returns 1.0 if P(bear)<theta
# (through d_prev) else 0.0 (or a soft version). PAST-ONLY: g(d_prev) uses only
# info with date <= d_prev, matching the incumbent idx-1 discipline.
# ---------------------------------------------------------------------- #
from strategies_candidates.leveraged_long_trend import backtest_daily as _base


def simulate_voltarget_gated(
    gate_fn,                       # callable(d_prev_iso)->g in [0,1], or None=ungated
    *,
    sleeve: str = "TQQQ",
    target_ann_vol: float = 0.25,
    vol_window: int = 20,
    w_max: float = 1.0,
    switch_cost_bps: float = COST_BPS,
    use_tbill_cash: bool = True,
    derisk_ret_map: Optional[Dict[str, float]] = None,  # de-risk destination daily rets (else cash)
) -> Dict:
    """Return dict(dates, equity, weights, daily_ret, stats). g scales the
    vol-target weight; the (1-w) remainder earns cash (or, if derisk_ret_map is
    given, the de-risk-destination return for the de-risked portion).

    IMPORTANT apples-to-apples note: the incumbent's exposure is
    w = clamp(breadth_g * voltarget_w). Here w = clamp(gate_g * voltarget_w),
    with voltarget_w = clamp(target/rvol, 0, w_max) computed IDENTICALLY. So the
    ONLY difference vs the incumbent is gate_g (breadth-fraction -> HMM gate)."""
    sleeve_bars = dbc.get_daily(sleeve)
    sleeve_by = {b["date"]: b for b in sleeve_bars}
    cal = [b["date"] for b in sleeve_bars]

    sleeve_dates = [b["date"] for b in sleeve_bars]
    sleeve_close = [b["adjclose"] for b in sleeve_bars]
    sret_end_dates: List[str] = []
    sret_vals: List[float] = []
    for k in range(1, len(sleeve_close)):
        if sleeve_close[k - 1] > 0:
            sret_end_dates.append(sleeve_dates[k])
            sret_vals.append(sleeve_close[k] / sleeve_close[k - 1] - 1.0)

    def sleeve_rets_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(sret_end_dates, d_iso)
        return sret_vals[:idx]

    equity = [1.0]
    out_dates = [cal[0]]
    weights: List[float] = []
    daily_ret: List[float] = []
    prev_w = 0.0
    REBAL_EPS = 1e-9
    n_rebal = 0
    turnover = 0.0

    for i in range(1, len(cal)):
        d_prev = cal[i - 1]
        d = cal[i]
        # vol-target weight (trend factored OUT; supplied via gate g)
        rv = realized_ann_vol(sleeve_rets_through(d_prev), vol_window)
        vt = bd_target_weight(rv, target_ann_vol, w_max)  # clamp(target/rvol)
        g = 1.0 if gate_fn is None else float(gate_fn(d_prev))
        w = max(0.0, min(w_max, g * vt))
        # sleeve close-to-close ret over held day
        b_now = sleeve_by.get(d)
        b_prev = sleeve_by.get(d_prev)
        if b_now and b_prev and b_prev["adjclose"] > 0:
            sleeve_ret = b_now["adjclose"] / b_prev["adjclose"] - 1.0
        else:
            sleeve_ret = 0.0
        # de-risked portion earns cash (default) OR the de-risk destination
        if derisk_ret_map is not None:
            dest = derisk_ret_map.get(d, 0.0)
        else:
            dest = _base._tbill_daily_rate(d_prev) if use_tbill_cash else 0.0
        blended = w * sleeve_ret + (1.0 - w) * dest
        dw = abs(w - prev_w)
        cost = (switch_cost_bps / 10000.0) * dw
        if dw > REBAL_EPS:
            n_rebal += 1
        turnover += dw
        new_eq = equity[-1] * (1.0 + blended) * (1.0 - cost)
        equity.append(new_eq)
        out_dates.append(d)
        weights.append(w)
        daily_ret.append(blended - cost)  # net daily return (cost folded)
        prev_w = w

    rets = np.array(daily_ret)
    stats = _stats_from_daily_returns(out_dates[1:], rets)
    stats["avg_weight"] = float(np.mean(weights)) if weights else 0.0
    stats["n_rebalances"] = n_rebal
    stats["turnover_units"] = float(turnover)
    stats["turnover_cost_pct"] = float(turnover * switch_cost_bps / 10000.0 * 100.0)
    return {
        "dates": out_dates[1:], "equity": equity[1:], "weights": weights,
        "daily_ret": rets, "stats": stats,
    }


def bd_target_weight(rvol: Optional[float], target_ann_vol: float, w_max: float) -> float:
    """Continuous vol-target weight = clamp(target/rvol, 0, w_max). Trend gate is
    applied SEPARATELY via the gate multiplier (mirrors the breadth path where
    breadth_g multiplies target_weight(True, rv, target, w_max)). rvol None ->
    0 (no vol estimate -> flat, conservative, matches the incumbent)."""
    if rvol is None or rvol <= 0:
        return 0.0
    return max(0.0, min(w_max, target_ann_vol / rvol))


if __name__ == "__main__":
    pass