"""Backtesting harness.

Replays historical bars through a strategy's `decide()` function and reports
performance metrics. OFFLINE: never hits the Alpaca trade API. Uses the data
API only via `bars_cache.get_bars(...)` (which caches to disk).

Key contracts (must match live runner exactly so strategy code is unchanged):

    market_state = {
        "symbol": str,
        "last_price": float,
        "bars": list[dict],            # oldest-first OHLCV; only bars[:i+1] visible
        "timeframe": str,
    }

    position_state = {
        symbol: {
            "qty": float,
            "market_value": float,     # qty * current price (bar close)
            "avg_entry_price": float,
        }
    }   # empty dict if flat

    Action: any object with .action ('buy'|'sell'|'close'|'hold'), .symbol,
            .notional_usd (float), .qty (float|None), .reason (str)

Risk caps (mirrored from runner/risk.py):
    MAX_NOTIONAL          = $1000   (paper bump 2026-05-31)
    MAX_POSITION          = $1000
    MAX_TRADES_PER_DAY    = 4 (UTC day, per backtest run)

Fills: at bars[i].close, full notional, no slippage. Spread + fee modeled
via `CostModel` (see below). Default applies Alpaca-crypto-ish friction;
pass `CostModel(spread_bps=0, fee_bps=0)` (or `--no-costs` on the CLI) to
recover the optimistic zero-friction numbers.

Walk-forward: at bar index i, strategy only sees bars[:i+1]. The fill happens
at bars[i].close. No lookahead.

Deterministic: same bars + same params -> same result.

CLI:
    python3 -m runner.backtest --strategy sma_crossover_qqq
    python3 -m runner.backtest --all
    python3 -m runner.backtest --all --days 30
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from . import safety_backstop

WORKSPACE = Path(__file__).resolve().parent.parent
STRATEGIES_ROOT = WORKSPACE / "strategies"

# Make sure `strategies.*` imports resolve when invoked as a script.
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import risk as risk_mod  # noqa: E402
from . import bars_cache  # noqa: E402

# Mirror caps explicitly — read from risk module so they drift together.
MAX_NOTIONAL = risk_mod.MAX_NOTIONAL
MAX_POSITION = risk_mod.MAX_POSITION
MAX_TRADES_PER_DAY = risk_mod.MAX_TRADES_PER_DAY


def _bt_check_trade(side: str, notional_usd: float,
                    current_position_usd: float, n_today: int,
                    *,
                    max_trades_per_day: int = MAX_TRADES_PER_DAY) -> risk_mod.RiskCheck:
    """Backtest-local risk check. Mirrors runner/risk.check_trade EXACTLY but
    takes `n_today` as a parameter instead of reading from the live trades DB
    (which would leak production state into the backtest).

    `max_trades_per_day` defaults to the legacy cap. Basket strategies should
    pass `risk.resolve_trades_per_day(params)` so multi-leg rebalance days
    aren't silently truncated. See `runner/risk.py` for the resolution rules.
    """
    # A `sell` is de-risking exactly like a `close` (it strictly reduces an
    # existing long — partial trim or full exit). Mirror runner/runner.py,
    # which consults risk with CLOSE-semantics for trims: daily-trade-cap
    # only, NEVER blocked on notional. This is what lets a partial-exit
    # `Action('sell', qty=..., notional_usd=0.0)` through the gate; the buy
    # path below keeps the non-positive-notional and position-cap checks.
    if side in ("close", "sell"):
        if n_today >= max_trades_per_day:
            return risk_mod.RiskCheck(
                False, f"already {n_today} trades today; cap {max_trades_per_day}"
            )
        return risk_mod.RiskCheck(True)
    if notional_usd <= 0:
        return risk_mod.RiskCheck(False, f"non-positive notional {notional_usd}")
    if notional_usd > MAX_NOTIONAL:
        return risk_mod.RiskCheck(
            False, f"notional ${notional_usd:.2f} > cap ${MAX_NOTIONAL:.2f}"
        )
    if side == "buy":
        projected = current_position_usd + notional_usd
        if projected > MAX_POSITION:
            return risk_mod.RiskCheck(
                False,
                f"projected position ${projected:.2f} > cap ${MAX_POSITION:.2f}",
            )
    if n_today >= max_trades_per_day:
        return risk_mod.RiskCheck(
            False, f"already {n_today} trades today; cap {max_trades_per_day}"
        )
    return risk_mod.RiskCheck(True)


# Bars per year per timeframe (for annualizing Sharpe).
#
# NOTE (2026-05-31, harness integrity audit FINDING 2): the `1Day` entry is
# market-class-dependent. Equities trade ~252 sessions/yr; crypto trades 24/7
# (~365). Using 365 for equities inflated daily Sharpe by sqrt(365/252)=1.204x
# (~20%). Use `bars_per_year(timeframe, is_crypto)` instead of indexing this
# dict directly.
#
# CORRECTION 2026-06-25: the OLD claim below this dict ("intraday is clock-time
# based, so 365 is correct for both classes") was WRONG for EQUITIES. A US
# equity intraday bar only exists during the trading session the data feed
# delivers (~8.5h: pre-market 08:00 ET + RTH to 16:00 ET, empirically 12:00-
# 20:30 UTC from Alpaca IEX), on ~252 sessions/yr -- NOT 24h x 365d. Indexing
# this dict for an equity intraday timeframe overstated bars/year by ~5.35x and
# therefore Sharpe by sqrt(5.35)=2.31x at EVERY intraday TF (incl. the live
# default 1Hour). This dict is now the CRYPTO/legacy table; equity intraday is
# computed from the session model in bars_per_year(). See
# reports/INTRADAY_READINESS_AUDIT_20260625T155500Z.md.
BARS_PER_YEAR = {
    "1Min": 60 * 24 * 365,
    "5Min": 12 * 24 * 365,
    "15Min": 4 * 24 * 365,
    "30Min": 2 * 24 * 365,
    "1Hour": 24 * 365,
    "2Hour": 12 * 365,
    "4Hour": 6 * 365,
    "6Hour": 4 * 365,
    "12Hour": 2 * 365,
    "1Day": 365,
}

# Trading sessions per year for daily equity bars (NYSE ~252).
EQUITY_TRADING_DAYS_PER_YEAR = 252

# Effective minutes of equity bars the data feed delivers PER SESSION. Alpaca
# IEX returns ~08:00-16:00 ET (pre-market + RTH) = ~8.5h = 510 min. Used to
# annualize equity INTRADAY Sharpe from the bars the engine actually sees
# (honest-measurement choice: match the realized bar stream, not a theoretical
# pure-RTH 390 min). Crypto intraday uses the full 1440 min/day (24/7).
EQUITY_INTRADAY_MINUTES_PER_DAY = 510
CRYPTO_MINUTES_PER_DAY = 1440

# tf -> minutes (mirror of runner.bars_cache.TF_MINUTES; duplicated here to keep
# this module import-light / avoid a bars_cache import cycle).
_TF_MINUTES = {
    "1Min": 1, "5Min": 5, "15Min": 15, "30Min": 30,
    "1Hour": 60, "2Hour": 120, "4Hour": 240,
    "6Hour": 360, "12Hour": 720, "1Day": 1440,
}


def bars_per_year(timeframe: str, is_crypto: bool) -> float:
    """Annualization bar-count for a timeframe, market-class aware.

    Daily (`1Day`): equities ~252 sessions/yr, crypto 24/7 ~365.

    Intraday: now ALSO class-aware (fixed 2026-06-25). Equities only trade the
    ~8.5h session the feed delivers on ~252 days/yr, so equity intraday
    bars/year = (EQUITY_INTRADAY_MINUTES_PER_DAY / tf_minutes) * 252. Crypto
    trades 24/7, so crypto intraday = (1440 / tf_minutes) * 365 (== the legacy
    BARS_PER_YEAR table). Using the crypto count for equities overstated Sharpe
    by ~2.31x at every intraday timeframe -- see the note above BARS_PER_YEAR.

    Unknown timeframes fall back to the legacy crypto 24*365 (preserves old
    behavior for anything not in the tf map).
    """
    if timeframe == "1Day":
        return 365.0 if is_crypto else float(EQUITY_TRADING_DAYS_PER_YEAR)
    tf_min = _TF_MINUTES.get(timeframe)
    if tf_min is None or tf_min >= 1440:
        # not a recognized sub-daily tf -> legacy fallback (unchanged)
        return float(BARS_PER_YEAR.get(timeframe, 24 * 365))
    if is_crypto:
        return (CRYPTO_MINUTES_PER_DAY / tf_min) * 365.0
    return (EQUITY_INTRADAY_MINUTES_PER_DAY / tf_min) * float(
        EQUITY_TRADING_DAYS_PER_YEAR)


# ---------------------------------------------------------------------------
# Lookback / warmup time-convention helper + guard (audit §2, 2026-06-25)
# ---------------------------------------------------------------------------
#
# Strategy lookbacks (`slow`, `sma`, `rsi_period`, `lookback`, ...) are authored
# as BAR COUNTS assuming the live cadence (1Day / 1Hour). The same integer means
# a wildly different wall-clock window at a finer timeframe: `slow:30` is ~30
# trading days at 1Day, but only 30 MINUTES at 1Min. There is NO auto-rescaling
# of live params -- that would silently change the meaning of a validated book.
# Instead we give callers (a) a unit-conversion helper and (b) a non-fatal lint
# that WARNS when a daily-authored count is being run at a finer timeframe such
# that the window no longer even spans one trading day.

# Tokens (case-insensitive substrings) that mark a param as "lookback-ish".
# Mirrors the audit §2 list. Threshold-ish params (e.g. `exit_rsi`, `buy_below`)
# can be caught by the `rsi`/`period` tokens; that is an accepted conservative
# false-positive for a non-fatal lint -- callers pass an explicit `lookback_keys`
# override when they want to scope it tighter.
_LOOKBACK_TOKENS = (
    "slow", "fast", "window", "period", "lookback", "span",
    "sma", "rsi", "bars", "exit_lookback", "time_stop_bars",
)


def timeframe_to_daily_bars(timeframe: str, is_crypto: bool = False) -> float:
    """How many bars of `timeframe` equal ONE trading day.

    This is the unit bridge between a bar-count lookback and its daily intent:
        daily_equiv_days = bar_count / timeframe_to_daily_bars(tf)

    Conventions (reuse the same session model as bars_per_year):
        - `1Day`            -> 1.0  (one bar IS one day, both classes)
        - equity intraday   -> EQUITY_INTRADAY_MINUTES_PER_DAY / tf_minutes
                               (510/60 = 8.5 bars/day at 1Hour; 510 at 1Min)
        - crypto intraday   -> CRYPTO_MINUTES_PER_DAY / tf_minutes
                               (1440/60 = 24 at 1Hour; 1440 at 1Min)

    Unknown timeframe -> ValueError (explicit; never silently guess), so a
    typo in a params.json surfaces instead of producing a bogus scale factor.
    """
    if timeframe == "1Day":
        return 1.0
    tf_min = _TF_MINUTES.get(timeframe)
    if tf_min is None:
        raise ValueError(f"timeframe_to_daily_bars: unknown timeframe {timeframe!r}")
    per_day = CRYPTO_MINUTES_PER_DAY if is_crypto else EQUITY_INTRADAY_MINUTES_PER_DAY
    return float(per_day) / float(tf_min)


def assert_lookback_sane(params: dict,
                         timeframe: str,
                         is_crypto: bool = False,
                         *,
                         lookback_keys=None) -> list:
    """Lint a params dict for daily-authored lookbacks run at a finer timeframe.

    Returns a list of human-readable WARNING strings (possibly empty). It does
    NOT raise and does NOT mutate `params`; it is a guard/lint, not a gate. The
    live cadence is 1Hour/1Day where these counts are intentional, so:
        - `timeframe == "1Day"` always returns []  (one bar == one day).
        - normal daily-authored counts at 1Hour (e.g. slow=30 -> 8.5 bars/day
          -> ~3.5 trading days) return [] -- they still span >=1 trading day.

    A warning is emitted for a lookback-ish param when its bar count is LESS
    than one trading day's worth of bars at this timeframe
    (`value < timeframe_to_daily_bars(timeframe, is_crypto)`), i.e. the window
    covers under a single session -- a strong signal the count was authored in
    daily units and is being misapplied at an intraday timeframe.

    Args:
        params: strategy params dict (read-only).
        timeframe: bar timeframe the strategy will run at.
        is_crypto: 24/7 market -> use 1440 min/day for the bars-per-day base.
        lookback_keys: optional iterable of EXACT param keys to inspect; when
            given, the substring-token scan is bypassed and only those keys are
            considered (still only numeric, non-bool values).

    Unknown timeframe propagates ValueError from timeframe_to_daily_bars (an
    unknown tf is a real config error, not something to lint past).
    """
    warnings: list = []
    if not params:
        return warnings
    if timeframe == "1Day":
        # one bar == one day; bar-count lookbacks are in their authored unit.
        return warnings

    bars_per_day = timeframe_to_daily_bars(timeframe, is_crypto)

    if lookback_keys is not None:
        key_set = set(lookback_keys)

        def _selected(key: str) -> bool:
            return key in key_set
    else:
        def _selected(key: str) -> bool:
            kl = key.lower()
            return any(tok in kl for tok in _LOOKBACK_TOKENS)

    for key, value in params.items():
        if isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)):
            continue
        if not _selected(key):
            continue
        if value < bars_per_day:
            days_equiv = value / bars_per_day if bars_per_day else 0.0
            warnings.append(
                f"lookback param {key!r}={value} at timeframe {timeframe!r} "
                f"covers only {days_equiv:.2f} trading day(s) "
                f"({bars_per_day:.1f} bars/day); if this count was authored for "
                f"DAILY bars it is being misapplied at this finer timeframe "
                f"(it no longer spans a full session).")
    return warnings


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class CostModel:
    """Spread + per-side fee applied to every fill.

    - `spread_bps` is ONE-WAY in basis points. Buys fill at
      `close * (1 + spread_bps/1e4)`; sells/closes fill at
      `close * (1 - spread_bps/1e4)`. Round-trip spread cost ≈ 2*spread_bps.
    - `fee_bps` is per-side in bps of notional and is deducted from cash
      on top of the spread (Alpaca paper crypto is 0; modeled for future
      stocks / non-crypto venues).

    Defaults (`spread_bps=200, fee_bps=0`) are a rough estimate for the
    Alpaca crypto tier-0 retail spread observed mid-2026 — roughly 2%
    one-way / 4% round-trip on majors at $100 notional. Not a quoted figure;
    eyeballed from order-book screenshots and live-tournament fills. Tune
    when better data lands.
    """
    spread_bps: float = 200.0
    fee_bps: float = 0.0

    def buy_fill_price(self, close: float) -> float:
        return close * (1.0 + self.spread_bps / 1e4)

    def sell_fill_price(self, close: float) -> float:
        return close * (1.0 - self.spread_bps / 1e4)

    def fee_on(self, notional: float) -> float:
        return abs(notional) * self.fee_bps / 1e4

    @classmethod
    def alpaca_crypto(cls) -> "CostModel":
        """Alpaca paper crypto tier-0 mid-2026 rough estimate: ~2% one-way spread,
        zero per-side fee. Round-trip cost ≈ 4% of notional. See BACKTEST_RESULTS.md."""
        return cls(spread_bps=200.0, fee_bps=0.0)

    @classmethod
    def alpaca_stocks(cls) -> "CostModel":
        """Alpaca paper stocks (commission-free, liquid US ETFs): ~1-2 bps effective
        one-way spread on SPY/QQQ-class names, zero per-side fee. Round-trip cost
        ≈ 2-4 bps of notional. Conservative default 2 bps one-way."""
        return cls(spread_bps=2.0, fee_bps=0.0)

    @classmethod
    def for_symbol(cls, symbol: str) -> "CostModel":
        """Pick the right cost model based on symbol form (`/` => crypto)."""
        return cls.alpaca_crypto() if "/" in symbol else cls.alpaca_stocks()


@dataclass
class BacktestResult:
    strategy: str
    symbol: str = ""
    timeframe: str = ""
    n_bars: int = 0
    n_trades: int = 0
    n_buys: int = 0
    n_closes: int = 0
    n_skipped_risk: int = 0
    total_return_usd: float = 0.0
    total_return_pct: float = 0.0
    sharpe: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    avg_trade_pnl_usd: float = 0.0
    final_position_qty: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    closed_trades: List[dict] = field(default_factory=list)
    skipped_reasons: List[str] = field(default_factory=list)
    starting_equity: float = 0.0
    final_equity: float = 0.0
    total_costs_usd: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        # equity curve and closed trades are large; truncate for JSON dumps.
        return d


# ---------------------------------------------------------------------------
# Strategy loader
# ---------------------------------------------------------------------------

def load_strategy_module_and_params(name: str):
    strat_dir = STRATEGIES_ROOT / name
    params_path = strat_dir / "params.json"
    if not strat_dir.is_dir():
        raise FileNotFoundError(f"No strategy dir: {strat_dir}")
    if not params_path.exists():
        raise FileNotFoundError(f"No params.json: {params_path}")
    module = importlib.import_module(f"strategies.{name}.strategy")
    params = json.loads(params_path.read_text())
    _warn_lookback_if_intraday(name, params)
    return module, params


def _warn_lookback_if_intraday(name: str, params: dict) -> None:
    """Emit non-fatal lookback-sanity WARNINGs at load time, intraday only.

    Silent for the all-daily live book: only runs when timeframe != "1Day",
    so a daily strategy load produces ZERO new output. Never raises (a bad
    timeframe here must not block a load); guard failures are swallowed.
    """
    try:
        timeframe = str((params or {}).get("timeframe", "1Day"))
        if timeframe == "1Day":
            return
        is_crypto = bool((params or {}).get("is_crypto", False))
        for w in assert_lookback_sane(params, timeframe, is_crypto):
            print(f"[{name}] WARN lookback-sanity: {w}", file=sys.stderr)
    except Exception:  # pragma: no cover - lint must never break a load
        pass


# ---------------------------------------------------------------------------
# Core backtest
# ---------------------------------------------------------------------------

def _bar_utc_day(bar: dict) -> str:
    """YYYY-MM-DD from bar's 't' (ISO 8601). Used to apply daily trade cap."""
    t = bar.get("t") or ""
    return t[:10] if isinstance(t, str) and len(t) >= 10 else ""


def backtest(strategy_name: str,
             bars: List[dict],
             params: dict,
             *,
             starting_cash: float = 1000.0,
             decide_fn: Optional[Callable] = None,
             cost_model: Optional[CostModel] = None) -> BacktestResult:
    """Replay bars through a strategy and compute metrics.

    Args:
        strategy_name: label only, for the result.
        bars: oldest-first OHLCV list (Alpaca shape: {t,o,h,l,c,v}).
        params: strategy params dict (passed straight to decide()).
        starting_cash: notional reference for total_return_pct. The bench
            uses $100 trades, so $1000 is a sensible default scale; changing
            it does NOT change strategy behavior, only pct denominators.
        decide_fn: override decide function (for tests). If None, the
            strategy module's `decide` is used.

    Returns: BacktestResult.
    """
    symbol = params.get("symbol", "")
    timeframe = str(params.get("timeframe", "1Hour"))
    if cost_model is None:
        cost_model = CostModel()
    result = BacktestResult(strategy=strategy_name, symbol=symbol,
                            timeframe=timeframe, n_bars=len(bars),
                            starting_equity=starting_cash)

    if not bars:
        result.equity_curve = [starting_cash]
        result.final_equity = starting_cash
        return result

    # Load the strategy unless an override is supplied.
    if decide_fn is None:
        module, _ = load_strategy_module_and_params(strategy_name)
        decide_fn = module.decide

    # ---- Regime pre-fetch ----
    # For stocks (non-crypto), pre-fetch SPY 1Day bars covering the full
    # backtest window so regime-aware strategies can read SPY trend at each
    # step. For crypto (no SPY equivalent) regime is None throughout.
    #
    # Slicing rule: at bar i we expose only SPY bars whose timestamp is
    # ≤ bars[i].t. That preserves no-lookahead even though the SPY series
    # is on a different timeframe (1Day) than the strategy bars (e.g. 1Hour).
    spy_closes_all: List[float] = []
    spy_times_all: List[str] = []
    is_crypto = "/" in symbol
    if not is_crypto:
        try:
            first_t = bars[0].get("t", "")
            last_t = bars[-1].get("t", "")
            # Parse end date from last bar; fetch ~150 days back so we always
            # have ≥50 bars of SPY history before the first strategy bar.
            from datetime import datetime as _dt
            try:
                end_dt_spy = _dt.strptime(last_t[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                end_dt_spy = None
            try:
                first_dt = _dt.strptime(first_t[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                first_dt = None
            if end_dt_spy and first_dt:
                span_days = (end_dt_spy - first_dt).days + 200
                spy_bars = bars_cache.get_bars("SPY", "1Day",
                                               days=max(span_days, 200),
                                               end_dt=end_dt_spy)
                spy_closes_all = [float(b["c"]) for b in (spy_bars or [])]
                spy_times_all = [str(b.get("t", "")) for b in (spy_bars or [])]
        except Exception:
            spy_closes_all = []
            spy_times_all = []

    # Portfolio state.
    cash = float(starting_cash)
    qty = 0.0
    avg_entry_price = 0.0
    cost_basis_usd = 0.0  # qty * avg_entry_price; kept in sync

    # Per-trade excursion tracking. Reset on each new entry (buy from flat).
    # We record the lowest LOW and highest HIGH seen at any point *between*
    # entry-bar and exit-bar (inclusive of intervening bars) so the parent-
    # profile module can compute realistic stop/take-profit thresholds.
    entry_bar_idx: Optional[int] = None
    trade_low_seen: Optional[float] = None   # lowest LOW since entry
    trade_high_seen: Optional[float] = None  # highest HIGH since entry

    # Bookkeeping.
    trades_by_day: dict[str, int] = {}
    n_buys = 0
    n_closes = 0
    n_skipped = 0
    skipped_reasons: List[str] = []
    closed_trades: List[dict] = []  # each: {entry_price, exit_price, qty, pnl_usd, pnl_pct, max_drawdown_pct, max_runup_pct, holding_bars}
    equity_curve: List[float] = []
    total_costs_usd = 0.0

    # Persistent strategy state. Hoisted out of the per-bar loop so that
    # custom keys a strategy writes to position_state[symbol] (e.g.
    # `running_max`, `scaled_out`, `entry_bar_index`) survive across bars
    # while a position is open. Broker-truth keys (qty/market_value/
    # avg_entry_price) are refreshed each bar from authoritative
    # backtester state. Position state is cleared on close. This mirrors
    # how the live runner SHOULD behave; runner/runner.py needs the same
    # fix (separate change).
    position_state: dict = {}

    # Cross-flat persistent state, exposed to the strategy as
    # market_state["strategy_state"]. Mirrors the live runner's
    # `db.get_persistent_state` / `db.save_persistent_state` pair, but
    # in-memory only — a backtest run gets a fresh empty dict, fully
    # determined by what the strategy writes within the run.
    persistent_state: dict = {}

    for i, bar in enumerate(bars):
        close = float(bar["c"])
        # Update per-trade excursion every bar a position is open. Use the
        # bar's high/low so we capture intra-bar excursion, not just close.
        if qty > 0 and entry_bar_idx is not None:
            try:
                bar_low = float(bar.get("l", close))
                bar_high = float(bar.get("h", close))
            except (TypeError, ValueError):
                bar_low = close
                bar_high = close
            if trade_low_seen is None or bar_low < trade_low_seen:
                trade_low_seen = bar_low
            if trade_high_seen is None or bar_high > trade_high_seen:
                trade_high_seen = bar_high
        # Build market_state with walk-forward visibility.
        # Regime slice: only SPY bars dated on/before this strategy bar.
        regime_state: Optional[dict] = None
        if spy_closes_all:
            bar_date = (bar.get("t") or "")[:10]
            # Binary-search-ish linear scan (SPY bars sorted; cheap enough).
            visible_n = 0
            for ti, t in enumerate(spy_times_all):
                if t[:10] <= bar_date:
                    visible_n = ti + 1
                else:
                    break
            if visible_n > 0:
                visible_closes = spy_closes_all[:visible_n]
                regime_state = {
                    "spy_closes": visible_closes,
                    "spy_last": visible_closes[-1],
                }
        market_state = {
            "symbol": symbol,
            "last_price": close,
            "bars": bars[: i + 1],
            "timeframe": timeframe,
            "regime": regime_state,
            "strategy_state": persistent_state,
        }        # Build/refresh position_state. Broker-truth keys are overwritten
        # every bar; custom strategy bookkeeping keys (e.g. running_max,
        # scaled_out) are preserved across bars while a position is open.
        if qty > 0:
            pos = position_state.get(symbol) or {}
            pos["qty"] = qty
            pos["market_value"] = qty * close
            pos["avg_entry_price"] = avg_entry_price
            position_state[symbol] = pos
        else:
            # Flat: drop any stale per-symbol state so a stale running_max
            # from a prior trade can't leak into the next one.
            position_state.pop(symbol, None)

        # Safety backstop: same contract as live runner. If params.json
        # has `safety_max_loss_pct` (or other triggers) and the current
        # position trips it, synthesize a close action and skip decide().
        # The strategy doesn't get to argue with the safety rail.
        bs_pos = position_state.get(symbol)
        bs_action = safety_backstop.check(bs_pos, close, params)
        if bs_action.fire:
            class _BSAction:
                pass
            action = _BSAction()
            action.action = "close"
            action.symbol = symbol
            action.notional_usd = 0.0
            action.reason = f"safety_backstop:{bs_action.trigger}: {bs_action.reason}"
        else:
            # Strategy decides on this bar (only sees bars[:i+1]).
            action = decide_fn(market_state, position_state, params)
        # Capture strategy_state by reassignment (mutation already captured
        # by reference). Mirrors live runner behavior where the post-decide
        # save reads market_state["strategy_state"] freshly.
        persistent_state = market_state.get("strategy_state") or {}
        if not isinstance(persistent_state, dict):
            persistent_state = {}

        # Normalize Action fields with safe defaults.
        a_act = getattr(action, "action", "hold")
        a_sym = getattr(action, "symbol", symbol) or symbol
        a_notional = float(getattr(action, "notional_usd", 0.0) or 0.0)
        a_reason = getattr(action, "reason", "") or ""

        if a_act == "hold":
            pass
        elif a_act in ("buy", "sell", "close"):
            day = _bar_utc_day(bar)
            n_today = trades_by_day.get(day, 0)
            cur_pos_usd = qty * close if qty > 0 else 0.0
            # Risk-gate mirroring runner/risk.py (same caps, same semantics)
            # but using our local per-backtest day counter so we don't read
            # the production trades DB.
            rc = _bt_check_trade(a_act, a_notional, cur_pos_usd, n_today)

            if not rc.ok:
                n_skipped += 1
                skipped_reasons.append(
                    f"bar {i} {a_act} {a_sym} notional={a_notional:.2f}: {rc.reason}"
                )
            else:
                if a_act == "buy":
                    # Fill at close + half-spread; fee charged on notional.
                    fill_px = cost_model.buy_fill_price(close)
                    buy_qty = a_notional / fill_px if fill_px > 0 else 0.0
                    if buy_qty > 0:
                        # Spread cost is embedded in the higher fill price:
                        # we spend `a_notional` cash but receive qty as if
                        # we paid `fill_px > close`. cost_basis tracks
                        # what we actually paid.
                        was_flat = qty == 0.0
                        new_qty = qty + buy_qty
                        cost_basis_usd = cost_basis_usd + a_notional
                        avg_entry_price = cost_basis_usd / new_qty if new_qty > 0 else 0.0
                        qty = new_qty
                        cash -= a_notional
                        fee = cost_model.fee_on(a_notional)
                        cash -= fee
                        spread_cost = a_notional * (cost_model.spread_bps / 1e4)
                        total_costs_usd += fee + spread_cost
                        n_buys += 1
                        trades_by_day[day] = n_today + 1
                        # Open excursion tracking on transition from flat.
                        # Seed low/high with this bar so excursion includes
                        # the entry bar itself.
                        if was_flat:
                            entry_bar_idx = i
                            try:
                                bar_low = float(bar.get("l", close))
                                bar_high = float(bar.get("h", close))
                            except (TypeError, ValueError):
                                bar_low = close
                                bar_high = close
                            trade_low_seen = bar_low
                            trade_high_seen = bar_high
                elif a_act in ("close", "sell"):
                    if qty > 0:
                        # ----- Resolve the requested sell qty (mirror runner.py) -----
                        # A `sell` may be a PARTIAL trim (scale-out / de-risk) that
                        # keeps the position long. Resolution order, identical to
                        # runner/runner.py: explicit action.qty (float > 0) wins;
                        # else derive from notional_usd / price; else (and for an
                        # explicit `close`) sell the WHOLE position.
                        req_qty = None
                        if a_act == "sell":
                            a_qty_raw = getattr(action, "qty", None)
                            if a_qty_raw is not None:
                                try:
                                    a_qty_f = float(a_qty_raw)
                                    if a_qty_f > 0:
                                        req_qty = a_qty_f
                                except (TypeError, ValueError):
                                    req_qty = None
                            if req_qty is None and a_notional > 0 and close > 0:
                                req_qty = a_notional / close
                        # `close`, or a `sell` with no usable qty/notional, exits full.
                        sell_qty = qty if req_qty is None else min(req_qty, qty)
                        # A trim that sweeps (or overshoots) the whole position is a
                        # full close — go cleanly flat rather than leave dust.
                        is_partial = sell_qty < qty - 1e-9

                        sell_px = cost_model.sell_fill_price(close)
                        proceeds = sell_qty * sell_px
                        fee = cost_model.fee_on(proceeds)
                        proceeds_after_fee = proceeds - fee
                        # Cost basis attributed to the shares being sold (pro-rata
                        # of avg entry). Pop only this slice; the remainder keeps
                        # the same avg_entry_price.
                        slice_cost_basis = cost_basis_usd * (sell_qty / qty) if qty > 0 else cost_basis_usd
                        pnl_usd = proceeds_after_fee - slice_cost_basis
                        pnl_pct = (pnl_usd / slice_cost_basis) if slice_cost_basis > 0 else 0.0
                        spread_cost = (sell_qty * close) * (cost_model.spread_bps / 1e4)
                        total_costs_usd += fee + spread_cost
                        # Compute per-trade excursion vs avg_entry_price.
                        # max_drawdown_pct is signed (negative); max_runup_pct
                        # is signed (positive). Both measured at the worst /
                        # best bar between entry and this exit bar (inclusive).
                        if avg_entry_price > 0 and trade_low_seen is not None and trade_high_seen is not None:
                            max_dd_from_entry = (trade_low_seen - avg_entry_price) / avg_entry_price
                            max_ru_from_entry = (trade_high_seen - avg_entry_price) / avg_entry_price
                        else:
                            max_dd_from_entry = 0.0
                            max_ru_from_entry = 0.0
                        holding_bars = (i - entry_bar_idx) if entry_bar_idx is not None else 0
                        closed_trades.append({
                            "exit_bar": i,
                            "exit_time": bar.get("t"),
                            "exit_price": sell_px,
                            "entry_price": avg_entry_price,
                            "qty": sell_qty,
                            "pnl_usd": pnl_usd,
                            "pnl_pct": pnl_pct,
                            "max_drawdown_pct": max_dd_from_entry,
                            "max_runup_pct": max_ru_from_entry,
                            "holding_bars": holding_bars,
                            "partial": is_partial,
                        })
                        cash += proceeds_after_fee
                        if is_partial:
                            # PARTIAL TRIM: reduce qty + cost basis pro-rata, STAY
                            # LONG. avg_entry_price is unchanged (basis/qty ratio
                            # preserved). Excursion + entry_bar_idx carry forward so
                            # the remainder's eventual exit measures from the
                            # original entry. This is the behavior runner.py would
                            # actually execute (submit_market_order sell qty).
                            qty = qty - sell_qty
                            cost_basis_usd = cost_basis_usd - slice_cost_basis
                            n_closes += 1
                            trades_by_day[day] = n_today + 1
                        else:
                            # FULL EXIT: go flat and clear all per-trade state.
                            qty = 0.0
                            cost_basis_usd = 0.0
                            avg_entry_price = 0.0
                            entry_bar_idx = None
                            trade_low_seen = None
                            trade_high_seen = None
                            n_closes += 1
                            trades_by_day[day] = n_today + 1
                    else:
                        # close with no position — strategy bug, log but don't trade.
                        n_skipped += 1
                        skipped_reasons.append(
                            f"bar {i} close requested but no position"
                        )
        else:
            # Unknown action — treat as hold but record.
            n_skipped += 1
            skipped_reasons.append(f"bar {i} unknown action {a_act!r}")

        equity = cash + qty * close
        equity_curve.append(equity)

    # ---- Metrics ----
    final_equity = equity_curve[-1] if equity_curve else starting_cash
    total_return_usd = final_equity - starting_cash
    total_return_pct = (total_return_usd / starting_cash) if starting_cash > 0 else 0.0

    # Per-bar returns of EQUITY (not price). Captures both realized P&L and
    # open-position mark-to-market.
    returns: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            returns.append((equity_curve[i] - prev) / prev)

    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var)
        if std > 0:
            bpy = bars_per_year(timeframe, is_crypto)
            sharpe = (mean / std) * math.sqrt(bpy)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # Max drawdown (% from running peak).
    peak = -float("inf")
    max_dd = 0.0
    for e in equity_curve:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak  # negative
            if dd < max_dd:
                max_dd = dd
    max_dd_pct = max_dd  # already a fraction (negative)

    # Win rate over CLOSED trades only.
    if closed_trades:
        wins = sum(1 for t in closed_trades if t["pnl_usd"] > 0)
        win_rate = wins / len(closed_trades)
        avg_trade_pnl = sum(t["pnl_usd"] for t in closed_trades) / len(closed_trades)
    else:
        win_rate = 0.0
        avg_trade_pnl = 0.0

    result.n_trades = n_buys + n_closes
    result.n_buys = n_buys
    result.n_closes = n_closes
    result.n_skipped_risk = n_skipped
    result.total_return_usd = total_return_usd
    result.total_return_pct = total_return_pct
    result.sharpe = sharpe
    result.max_drawdown_pct = max_dd_pct
    result.win_rate = win_rate
    result.avg_trade_pnl_usd = avg_trade_pnl
    result.final_position_qty = qty
    result.equity_curve = equity_curve
    result.closed_trades = closed_trades
    result.skipped_reasons = skipped_reasons[:50]  # cap noise
    result.final_equity = final_equity
    result.total_costs_usd = total_costs_usd
    return result


# ---------------------------------------------------------------------------
# Convenience: backtest a strategy by name over last N days
# ---------------------------------------------------------------------------

ALL_STRATEGIES = [
    # NOTE: original Session 2 crypto slate retired 2026-05-30 (see `strategies_retired/`).
    # Alpaca crypto ~4% round-trip spread invalidated the entire slate; can't pass Bar E.
    # Stocks tournament (Session 3 port to lower-cost venue)
    "buy_and_hold_spy",
    "sma_crossover_qqq",
    "rsi_mean_revert_iwm",
    "breakout_xlk",
    "momentum_arkk",
    "trend_follow_gld",
    # Regime-filtered variants
    "breakout_xlk_regime",
    "sma_crossover_qqq_regime",
    "sma_crossover_qqq_rth",
    # Promoted mutant (2026-06-11): regime-conditional hard stop on breakout_xlk.
    "breakout_xlk__mut_c382b1",
    # NOTE: leveraged_long_trend_paper (TQQQ vol-target sleeve, promoted to live
    # PAPER 2026-06-13) is deliberately NOT in these lists. It is a DAILY
    # CONTINUOUS-WEIGHT rebalance strategy whose validated backtest is the
    # separate harness strategies_candidates/leveraged_long_trend/
    # backtest_daily_voltarget.py — NOT this event-driven engine. Running it
    # through backtest()/ranking/walk_forward --all would produce a meaningless
    # number. The LIVE runner drives it directly from the crontab tick line +
    # strategies/leveraged_long_trend_paper/. Do not add it here without porting
    # its sizing semantics into the event engine first.
]

CRYPTO_STRATEGIES: list[str] = [
    # Retired 2026-05-30. Kept as empty list so any importer doesn't break;
    # historical names live at `strategies_retired/` for code-fixture / audit purposes.
]
STOCK_STRATEGIES = [
    "buy_and_hold_spy", "sma_crossover_qqq", "rsi_mean_revert_iwm",
    "breakout_xlk", "momentum_arkk", "trend_follow_gld",
    # Regime-filtered variants (Session 3+: gate entries on SPY > 50d SMA).
    "breakout_xlk_regime", "sma_crossover_qqq_regime", "sma_crossover_qqq_rth",
    # Promoted mutant (2026-06-11): regime-conditional hard stop on breakout_xlk.
    "breakout_xlk__mut_c382b1",
]


def backtest_by_name(strategy_name: str, days: int = 30,
                     end_dt: Optional[datetime] = None,
                     cost_model: Optional[CostModel] = None) -> BacktestResult:
    module, params = load_strategy_module_and_params(strategy_name)
    symbol = params.get("symbol", "BTC/USD")
    timeframe = str(params.get("timeframe", "1Hour"))
    bars = bars_cache.get_bars(symbol, timeframe, days=days, end_dt=end_dt)
    return backtest(strategy_name, bars, params, decide_fn=module.decide,
                    cost_model=cost_model)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_comparison_table(results: List[BacktestResult]) -> str:
    headers = ["strategy", "sym", "tf", "bars", "trades", "ret %", "sharpe",
               "maxDD %", "win %", "avg $/trade", "final qty"]
    rows = []
    for r in results:
        rows.append([
            r.strategy,
            r.symbol,
            r.timeframe,
            str(r.n_bars),
            str(r.n_trades),
            f"{r.total_return_pct * 100:+.2f}",
            f"{r.sharpe:.2f}",
            f"{r.max_drawdown_pct * 100:.2f}",
            f"{r.win_rate * 100:.1f}" if r.n_closes > 0 else "—",
            f"{r.avg_trade_pnl_usd:+.2f}" if r.n_closes > 0 else "—",
            f"{r.final_position_qty:.6f}".rstrip("0").rstrip(".") or "0",
        ])
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]

    def fmt_row(cells):
        return "  ".join(c.ljust(w) for c, w in zip(cells, widths))

    out_lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    for row in rows:
        out_lines.append(fmt_row(row))
    return "\n".join(out_lines)


def format_markdown_table(results: List[BacktestResult]) -> str:
    headers = ["Strategy", "Symbol", "TF", "Bars", "Trades", "Return %",
               "Sharpe", "MaxDD %", "Win %", "Avg $/Trade", "Final Qty"]
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in results:
        cells = [
            r.strategy,
            r.symbol,
            r.timeframe,
            str(r.n_bars),
            str(r.n_trades),
            f"{r.total_return_pct * 100:+.2f}",
            f"{r.sharpe:.2f}",
            f"{r.max_drawdown_pct * 100:.2f}",
            f"{r.win_rate * 100:.1f}" if r.n_closes > 0 else "—",
            f"{r.avg_trade_pnl_usd:+.2f}" if r.n_closes > 0 else "—",
            f"{r.final_position_qty:.6f}".rstrip("0").rstrip(".") or "0",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest one or all strategies.")
    ap.add_argument("--strategy", help="strategy directory name")
    ap.add_argument("--all", action="store_true", help="run every strategy")
    ap.add_argument("--days", type=int, default=30, help="lookback in days")
    ap.add_argument("--md", help="write Markdown table to this path")
    ap.add_argument("--no-costs", action="store_true",
                    help="zero out CostModel (spread=0, fees=0)")
    ap.add_argument("--spread-bps", type=float, default=None,
                    help="override one-way spread in bps; if unset, auto-pick"
                         " alpaca_crypto/alpaca_stocks per symbol")
    ap.add_argument("--fee-bps", type=float, default=None,
                    help="override per-side fee in bps; same auto-pick rules")
    args = ap.parse_args()

    if not args.strategy and not args.all:
        ap.error("Provide --strategy NAME or --all")

    def _cm_for(strategy_name: str) -> CostModel:
        if args.no_costs:
            return CostModel(spread_bps=0.0, fee_bps=0.0)
        if args.spread_bps is not None or args.fee_bps is not None:
            # Caller overrode; honor exactly.
            base = CostModel()
            return CostModel(
                spread_bps=args.spread_bps if args.spread_bps is not None else base.spread_bps,
                fee_bps=args.fee_bps if args.fee_bps is not None else base.fee_bps,
            )
        # Auto-pick from the strategy's symbol.
        try:
            _, params = load_strategy_module_and_params(strategy_name)
            sym = params.get("symbol", "")
        except Exception:
            sym = ""
        return CostModel.for_symbol(sym)

    names = ALL_STRATEGIES if args.all else [args.strategy]
    results = []
    for name in names:
        cm = _cm_for(name)
        try:
            r = backtest_by_name(name, days=args.days, cost_model=cm)
            results.append(r)
            print(f"[{name}] cm(spread={cm.spread_bps}bp fee={cm.fee_bps}bp) "
                  f"bars={r.n_bars} trades={r.n_trades} "
                  f"ret={r.total_return_pct * 100:+.2f}% sharpe={r.sharpe:.2f} "
                  f"maxDD={r.max_drawdown_pct * 100:.2f}% skipped={r.n_skipped_risk}")
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] ERROR: {e}", file=sys.stderr)
            raise

    if len(results) > 1 or args.all:
        print("\n=== Comparison ===")
        print(format_comparison_table(results))

    if args.md:
        Path(args.md).write_text(format_markdown_table(results))
        print(f"\nWrote Markdown table → {args.md}")


if __name__ == "__main__":
    main()
