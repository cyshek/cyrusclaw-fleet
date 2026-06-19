"""Disk cache + ingest for Yahoo-v8 DAILY OHLCV bars (split+div-adjusted).

RESEARCH/BACKTEST-ONLY. Parallel to `bars_cache.py` (Alpaca intraday OHLCV),
`cboe_cache.py` (VIX complex), `fred_cache.py` (FRED macro), `cot_cache.py`
(CFTC COT). This is the free, deep, IP-UNWALLED daily-equity/ETF/index source
for the trend-gated leveraged-long engine (LEVERAGED_LONG_ENGINE_20260608).

DATA SOURCE (verified HTTP 200 + real JSON live from THIS VM 2026-06-08):
  Yahoo v8 chart API serves full daily history with a browser User-Agent:
      https://query1.finance.yahoo.com/v8/finance/chart/<SYM>
          ?period1=0&period2=9999999999&interval=1d&events=div,split
  JSON shape:
      chart.result[0].timestamp[]                         -> epoch seconds (UTC)
      chart.result[0].indicators.quote[0]                 -> open/high/low/close/volume arrays
      chart.result[0].indicators.adjclose[0].adjclose[]   -> split+DIV-adjusted close
      chart.result[0].events.splits                       -> split events (optional)

  *** USE adjclose, NOT raw close. ***
  Leveraged ETFs (TQQQ/UPRO/SOXL) split CONSTANTLY; raw `close` is garbage for
  a cumulative-return backtest. `adjclose` is split+dividend adjusted and is the
  only correct series for total-return compounding.

  Symbols verified live (2010+ window all present): TQQQ (2010-02-11, 4105 bars),
  SPY, QQQ, UPRO, SOXL, ^GSPC (URL-encode caret as %5EGSPC), ^NDX.
  NOTE: ^VIX specifically 429s from this VM — for the VIX complex use cboe_cache,
  NOT this module. Daily equity/ETF/broad-index bars are NOT walled here.

  Back off query1 -> query2 ONLY on an actual 429 (the old blanket "Yahoo 429s"
  warning is stale; it was ^VIX-specific).

============================ THE LOOKAHEAD GUARD ==============================
These are END-OF-DAY bars. The close/adjclose for trading date D is not known
until D's close. A decision made DURING date D (at the open, or any intraday/
same-day-open execution) may use a bar dated D for its OPEN, but must NOT use a
bar dated > D for any field, and must NOT use date D's CLOSE to inform a trade
placed at date D's open.

We provide two point-in-time accessors with explicit semantics:

  asof(symbol, date)        -> most-recent bar with bar_date <= `date`
                               (INCLUSIVE; the bar whose OPEN you can trade at on
                               `date`, or the last close known by EOD `date`).
                               Asserts bar_date <= date.
  asof_strict(symbol, date) -> most-recent bar with bar_date <  `date`
                               (STRICTLY before; the last CLOSE fully known
                               before a decision made at the open of `date`).
                               Asserts bar_date < date. Mirrors cboe_cache.asof.

The daily engine in strategies_candidates/leveraged_long_trend/ uses a 1-day
SIGNAL LAG: the gate is computed from closes through date D, and the resulting
position is applied to date D+1's return. That construction is leak-free by
design; these accessors are the defensive PIT primitives + what the lookahead
tests assert against.
==============================================================================

Cache layout under `data_cache/yahoo/`:
  - raw json:   <SYM>_raw.json        (fetched once)
  - parsed:     <SYM>_parsed.json     (list of {date, open, high, low, close, adjclose, volume})
A re-run hits the parsed cache and never re-downloads.

CLI:   python3 -m runner.daily_bars_cache          # runs the selftest battery
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(__file__).resolve().parent.parent
CACHE_DIR = WORKSPACE / "data_cache" / "yahoo"
HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
URL_TMPL = ("https://{host}/v8/finance/chart/{sym}"
            "?period1=0&period2=9999999999&interval=1d&events=div,split")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# In-process memo so repeated asof() calls in a backtest don't re-read disk.
_SERIES_MEMO: Dict[str, List[dict]] = {}
_DATES_MEMO: Dict[str, List[str]] = {}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class DailyBarsError(RuntimeError):
    """Base error for the Yahoo daily-bars cache."""


class DailyBarsFetchError(DailyBarsError):
    """Network/HTTP failure fetching from Yahoo (after query1->query2 retry)."""


class DailyBarsParseError(DailyBarsError):
    """Yahoo JSON did not have the expected shape."""


class DailyBarsLookaheadError(DailyBarsError):
    """An asof accessor was about to return a bar that violates its time bound."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _as_iso(d) -> str:
    """Coerce a date / datetime / 'YYYY-MM-DD...' string to an ISO date string."""
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


def _sym_key(symbol: str) -> str:
    """Filesystem-safe cache key for a symbol (^GSPC -> _GSPC)."""
    return symbol.upper().replace("^", "_").replace("/", "_")


def _url_sym(symbol: str) -> str:
    """URL-encode a symbol for the Yahoo path (^ -> %5E)."""
    return symbol.upper().replace("^", "%5E")


def _cache_paths(symbol: str):
    key = _sym_key(symbol)
    return (CACHE_DIR / f"{key}_raw.json", CACHE_DIR / f"{key}_parsed.json")


# --------------------------------------------------------------------------- #
# Fetch + parse
# --------------------------------------------------------------------------- #
def _fetch_raw(symbol: str, timeout: int = 30) -> dict:
    """Hit Yahoo v8 for `symbol`, returning the decoded JSON. Tries query1 then
    query2 (the latter only meaningfully helps on a 429)."""
    last_err: Optional[Exception] = None
    for host in HOSTS:
        url = URL_TMPL.format(host=host, sym=_url_sym(symbol))
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
            return json.loads(body)
        except urllib.error.HTTPError as e:
            last_err = e
            # 429 -> try the next host; other HTTP errors are likely fatal but
            # we still try the alternate host once before giving up.
            time.sleep(0.5)
            continue
        except Exception as e:  # URLError, JSONDecodeError, socket timeout
            last_err = e
            time.sleep(0.5)
            continue
    raise DailyBarsFetchError(f"fetch failed for {symbol!r}: {last_err}")


def _parse(symbol: str, raw: dict) -> List[dict]:
    """Convert the Yahoo JSON into a clean ascending list of bar dicts.

    Drops any row where adjclose is null (Yahoo occasionally emits a trailing
    null placeholder bar). Each bar: {date, open, high, low, close, adjclose, volume}.
    """
    try:
        result = raw["chart"]["result"][0]
        ts = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        adj = result["indicators"]["adjclose"][0]["adjclose"]
    except (KeyError, IndexError, TypeError) as e:
        # Surface Yahoo's own error payload if present.
        err = None
        try:
            err = raw["chart"]["error"]
        except Exception:
            pass
        raise DailyBarsParseError(f"unexpected Yahoo shape for {symbol!r} "
                                  f"(yahoo_error={err}): {e}")

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    vols = quote.get("volume", [])
    n = len(ts)

    def _g(arr, i):
        return arr[i] if i < len(arr) else None

    out: List[dict] = []
    for i in range(n):
        ac = _g(adj, i)
        cl = _g(closes, i)
        # adjclose is the load-bearing field; skip rows missing it.
        if ac is None and cl is None:
            continue
        d = datetime.fromtimestamp(ts[i], tz=timezone.utc).date().isoformat()
        out.append({
            "date": d,
            "open": _g(opens, i),
            "high": _g(highs, i),
            "low": _g(lows, i),
            "close": cl,
            "adjclose": ac if ac is not None else cl,
            "volume": _g(vols, i),
        })
    # Ensure ascending + de-dup any repeated dates (keep last).
    out.sort(key=lambda r: r["date"])
    dedup: List[dict] = []
    for r in out:
        if dedup and dedup[-1]["date"] == r["date"]:
            dedup[-1] = r
        else:
            dedup.append(r)
    return dedup


# --------------------------------------------------------------------------- #
# Public: load / get_daily
# --------------------------------------------------------------------------- #
def get_daily(symbol: str, use_cache: bool = True, refresh: bool = False) -> List[dict]:
    """Return the full ascending daily-bar list for `symbol`.

    {date(iso), open, high, low, close, adjclose, volume}, sorted ascending.
    Cached to disk (parsed json). Set refresh=True to force a re-fetch.
    """
    key = _sym_key(symbol)
    if use_cache and not refresh and key in _SERIES_MEMO:
        return _SERIES_MEMO[key]

    raw_path, parsed_path = _cache_paths(symbol)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    parsed: Optional[List[dict]] = None
    if use_cache and not refresh and parsed_path.exists() and parsed_path.stat().st_size > 2:
        try:
            data = json.loads(parsed_path.read_text())
            if isinstance(data, list) and data:
                parsed = data
        except Exception:
            parsed = None

    if parsed is None:
        raw = _fetch_raw(symbol)
        try:
            raw_path.write_text(json.dumps(raw))
        except Exception:
            pass  # raw cache is best-effort
        parsed = _parse(symbol, raw)
        if not parsed:
            raise DailyBarsParseError(f"no usable bars parsed for {symbol!r}")
        parsed_path.write_text(json.dumps(parsed))

    _SERIES_MEMO[key] = parsed
    _DATES_MEMO[key] = [r["date"] for r in parsed]
    return parsed


def _dates_for(symbol: str) -> List[str]:
    key = _sym_key(symbol)
    if key not in _DATES_MEMO:
        get_daily(symbol)
    return _DATES_MEMO.get(key, [])


# --------------------------------------------------------------------------- #
# Point-in-time accessors (THE LOOKAHEAD GUARD)
# --------------------------------------------------------------------------- #
def asof(symbol: str, asof_date, use_cache: bool = True) -> Optional[dict]:
    """Most-recent bar with bar_date <= `asof_date` (INCLUSIVE).

    Use this for "the bar I can trade the OPEN of on `asof_date`" or "the last
    close known by EOD `asof_date`". Asserts bar_date <= asof_date.
    """
    get_daily(symbol, use_cache=use_cache)
    dates = _dates_for(symbol)
    if not dates:
        return None
    asof_iso = _as_iso(asof_date)
    pos = bisect_right(dates, asof_iso)  # first index with date > asof_iso
    if pos <= 0:
        return None
    rec = _SERIES_MEMO[_sym_key(symbol)][pos - 1]
    if rec["date"] > asof_iso:
        raise DailyBarsLookaheadError(
            f"asof({symbol},{asof_iso}) would return future bar {rec['date']}")
    return rec


def asof_strict(symbol: str, asof_date, use_cache: bool = True) -> Optional[dict]:
    """Most-recent bar with bar_date STRICTLY BEFORE `asof_date`.

    Use this for "the last CLOSE fully known before a decision made at the open
    of `asof_date`". Asserts bar_date < asof_date. Mirrors cboe_cache.asof.
    """
    get_daily(symbol, use_cache=use_cache)
    dates = _dates_for(symbol)
    if not dates:
        return None
    asof_iso = _as_iso(asof_date)
    pos = bisect_left(dates, asof_iso)  # first index with date >= asof_iso
    if pos <= 0:
        return None
    rec = _SERIES_MEMO[_sym_key(symbol)][pos - 1]
    if rec["date"] >= asof_iso:
        raise DailyBarsLookaheadError(
            f"asof_strict({symbol},{asof_iso}) would return non-prior bar {rec['date']}")
    return rec


def adjclose_asof(symbol: str, asof_date, strict: bool = False) -> Optional[float]:
    """Convenience: the adjclose at/just-before `asof_date`."""
    rec = (asof_strict if strict else asof)(symbol, asof_date)
    return None if rec is None else rec.get("adjclose")


def adjclose_series(symbol: str, dates: List[str]) -> List[Optional[float]]:
    """Return adjclose aligned to an explicit list of ISO `dates`.

    For each requested date D, returns the adjclose of the bar dated exactly D
    if present, else the most-recent prior bar's adjclose (forward-fill), else
    None. Forward-fill never looks ahead (only <= D). Useful to align a
    benchmark (^GSPC) onto the strategy's traded-date axis.
    """
    get_daily(symbol)
    out: List[Optional[float]] = []
    for d in dates:
        rec = asof(symbol, d)
        out.append(None if rec is None else rec.get("adjclose"))
    return out


def span(symbol: str, use_cache: bool = True) -> Dict[str, object]:
    """Report the available span for one symbol (first/last date + count)."""
    s = get_daily(symbol, use_cache=use_cache)
    return {
        "symbol": symbol.upper(),
        "n": len(s),
        "first": s[0]["date"] if s else None,
        "last": s[-1]["date"] if s else None,
    }


# --------------------------------------------------------------------------- #
# Selftest
# --------------------------------------------------------------------------- #
def selftest(symbols=("TQQQ", "QQQ", "^GSPC")) -> None:
    """Fetch a few symbols and prove the lookahead guard. Hits the network on a
    cold cache; uses disk on re-run. Raises on any invariant violation."""
    print(f"[daily_bars_cache] cache dir: {CACHE_DIR}")
    for sym in symbols:
        bars = get_daily(sym)
        sp = span(sym)
        print(f"  {sym:8s} n={sp['n']:5d}  first={sp['first']}  last={sp['last']}  "
              f"adjclose0={bars[0]['adjclose']!r}")
        assert bars[0]["adjclose"] is not None, f"{sym}: missing adjclose"
        assert all(bars[i]["date"] < bars[i + 1]["date"] for i in range(len(bars) - 1)), \
            f"{sym}: dates not strictly ascending"

        # Lookahead guard: asof_strict on a known bar date must return the PRIOR
        # bar, never the same-date bar.
        mid = bars[len(bars) // 2]
        prev = bars[len(bars) // 2 - 1]
        r_strict = asof_strict(sym, mid["date"])
        assert r_strict is not None and r_strict["date"] == prev["date"], \
            f"{sym}: asof_strict leaked same-date bar"
        # Inclusive asof on the same date returns that same-date bar.
        r_incl = asof(sym, mid["date"])
        assert r_incl is not None and r_incl["date"] == mid["date"], \
            f"{sym}: asof inclusive did not return same-date bar"
        # asof on a future date returns the last bar (never raises).
        r_future = asof(sym, "2999-01-01")
        assert r_future is not None and r_future["date"] == bars[-1]["date"]
    print("[daily_bars_cache] selftest OK")


if __name__ == "__main__":
    selftest()
