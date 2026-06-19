"""Disk cache + ingest for Yahoo-v8 DAILY FX OHLC bars (FX majors).

RESEARCH/BACKTEST-ONLY. Parallel to `daily_bars_cache.py` (Yahoo-v8 equity/ETF
adjclose), `bars_cache.py` (Alpaca intraday), `cboe_cache.py` (VIX complex),
`fred_cache.py` (FRED macro), `cot_cache.py` (CFTC COT). This is the free, deep,
IP-UNWALLED daily FX-majors source standing up the FOREX research lane
(FX_LANE_20260609 — first-ever FX evaluation for this project).

DATA SOURCE (verified HTTP 200 + real JSON live from THIS VM 2026-06-09):
  Yahoo v8 chart API serves full daily FX history with a browser User-Agent:
      https://query1.finance.yahoo.com/v8/finance/chart/<SYM>
          ?period1=0&period2=9999999999&interval=1d
  FX symbols use the "=X" suffix on Yahoo:
      EURUSD=X  GBPUSD=X  USDJPY=X  AUDUSD=X  USDCHF=X  USDCAD=X
  JSON shape (identical to the equity daily endpoint):
      chart.result[0].timestamp[]                         -> epoch seconds (UTC)
      chart.result[0].indicators.quote[0]                 -> open/high/low/close/volume
      chart.result[0].indicators.adjclose[0].adjclose[]   -> adjusted close

  *** FX HAS NO SPLITS OR DIVIDENDS. ***
  For FX, adjclose == close (Yahoo still emits the adjclose array; it equals the
  raw close). We carry `close` as the load-bearing price field and also keep
  `adjclose` (== close) so this cache is field-compatible with daily_bars_cache.
  Volume is meaningless for spot FX (Yahoo reports 0 / null) — IGNORE it.

  Verified spans (live, 2026-06-09):
      EURUSD=X  5878 bars  2003-12-01 -> 2026-06-09
      GBPUSD=X  5878 bars  2003-12-01 -> 2026-06-09
      USDJPY=X  7726 bars  1996-10-30 -> 2026-06-09
      AUDUSD=X  5237 bars  2006-05-15 -> 2026-06-09
      USDCHF=X  5931 bars  2003-09-16 -> 2026-06-09
      USDCAD=X  5931 bars  2003-09-16 -> 2026-06-09
  The 2003-start window COVERS THE 2008-GFC BEAR — a key regime-robustness win
  for FX trend vs. shallower free FX sources.

  Back off query1 -> query2 ONLY on an actual 429.

============================ THE LOOKAHEAD GUARD ==============================
These are END-OF-DAY FX bars. The close for trading date D is not known until D's
close. A decision made DURING date D may use a bar dated D for its OPEN but must
NOT use a bar dated > D, and must NOT use date D's CLOSE to inform a trade placed
at date D's open.

Two point-in-time accessors with explicit semantics (mirror daily_bars_cache):

  asof(symbol, date)        -> most-recent bar with bar_date <= `date`
                               (INCLUSIVE). Asserts bar_date <= date.
  asof_strict(symbol, date) -> most-recent bar with bar_date <  `date`
                               (STRICTLY before — last close fully known before a
                               decision made at the open of `date`).
                               Asserts bar_date < date.

The FX strategies use a 1-day SIGNAL LAG: the signal is computed from closes
through date D, the position is applied to date D+1's close-to-close return. That
construction is leak-free by design; these accessors are the defensive PIT
primitives the lookahead tests assert against.
==============================================================================

Cache layout under `data_cache/yahoo_fx/`:
  - raw json:   <SYM>_raw.json        (fetched once;  EURUSD=X -> EURUSD_X_raw.json)
  - parsed:     <SYM>_parsed.json     (list of {date, open, high, low, close, adjclose, volume})
A re-run hits the parsed cache and never re-downloads.

CLI:   python3 -m runner.fx_bars_cache          # runs the selftest battery
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
CACHE_DIR = WORKSPACE / "data_cache" / "yahoo_fx"
HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
URL_TMPL = ("https://{host}/v8/finance/chart/{sym}"
            "?period1=0&period2=9999999999&interval=1d")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# The six FX majors this lane evaluates (Yahoo "=X" symbols).
FX_MAJORS = ("EURUSD=X", "GBPUSD=X", "USDJPY=X",
             "AUDUSD=X", "USDCHF=X", "USDCAD=X")

# In-process memo so repeated asof() calls in a backtest don't re-read disk.
_SERIES_MEMO: Dict[str, List[dict]] = {}
_DATES_MEMO: Dict[str, List[str]] = {}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class FxBarsError(RuntimeError):
    """Base error for the Yahoo FX-bars cache."""


class FxBarsFetchError(FxBarsError):
    """Network/HTTP failure fetching from Yahoo (after query1->query2 retry)."""


class FxBarsParseError(FxBarsError):
    """Yahoo JSON did not have the expected shape."""


class FxBarsLookaheadError(FxBarsError):
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
    """Filesystem-safe cache key for a symbol (EURUSD=X -> EURUSD_X)."""
    return symbol.upper().replace("=", "_").replace("^", "_").replace("/", "_")


def _url_sym(symbol: str) -> str:
    """URL form of an FX symbol. '=' is URL-safe in a path; pass through upper."""
    return symbol.upper()


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
            # 429 -> try the next host; other HTTP errors likely fatal but we
            # still try the alternate host once before giving up.
            time.sleep(0.5)
            continue
        except Exception as e:  # URLError, JSONDecodeError, socket timeout
            last_err = e
            time.sleep(0.5)
            continue
    raise FxBarsFetchError(f"fetch failed for {symbol!r}: {last_err}")


def _parse(symbol: str, raw: dict) -> List[dict]:
    """Convert the Yahoo JSON into a clean ascending list of bar dicts.

    For FX, `close` is the load-bearing price; `adjclose` (if present) equals
    close. Rows where BOTH close and adjclose are null are dropped (Yahoo emits
    occasional placeholder/holiday bars). Each bar:
    {date, open, high, low, close, adjclose, volume}.
    """
    try:
        result = raw["chart"]["result"][0]
        ts = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as e:
        err = None
        try:
            err = raw["chart"]["error"]
        except Exception:
            pass
        raise FxBarsParseError(f"unexpected Yahoo shape for {symbol!r} "
                               f"(yahoo_error={err}): {e}")

    # adjclose is optional for FX; fall back to close when absent.
    adj = None
    try:
        adj = result["indicators"]["adjclose"][0]["adjclose"]
    except (KeyError, IndexError, TypeError):
        adj = None

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    vols = quote.get("volume", [])
    n = len(ts)

    def _g(arr, i):
        return arr[i] if (arr is not None and i < len(arr)) else None

    out: List[dict] = []
    for i in range(n):
        cl = _g(closes, i)
        ac = _g(adj, i)
        # close is the load-bearing field for FX; skip rows missing both.
        if cl is None and ac is None:
            continue
        d = datetime.fromtimestamp(ts[i], tz=timezone.utc).date().isoformat()
        close_val = cl if cl is not None else ac
        out.append({
            "date": d,
            "open": _g(opens, i),
            "high": _g(highs, i),
            "low": _g(lows, i),
            "close": close_val,
            "adjclose": close_val,  # FX: no splits/divs -> adjclose == close
            "volume": _g(vols, i),  # meaningless for spot FX; carried for shape parity
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
    """Return the full ascending daily-bar list for an FX `symbol`.

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
            raise FxBarsParseError(f"no usable bars parsed for {symbol!r}")
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

    "The bar I can trade the OPEN of on `asof_date`" / "last close known by EOD
    `asof_date`". Asserts bar_date <= asof_date.
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
        raise FxBarsLookaheadError(
            f"asof({symbol},{asof_iso}) would return future bar {rec['date']}")
    return rec


def asof_strict(symbol: str, asof_date, use_cache: bool = True) -> Optional[dict]:
    """Most-recent bar with bar_date STRICTLY BEFORE `asof_date`.

    "The last CLOSE fully known before a decision made at the open of
    `asof_date`". Asserts bar_date < asof_date.
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
        raise FxBarsLookaheadError(
            f"asof_strict({symbol},{asof_iso}) would return non-prior bar {rec['date']}")
    return rec


def close_asof(symbol: str, asof_date, strict: bool = False) -> Optional[float]:
    """Convenience: the close at/just-before `asof_date`."""
    rec = (asof_strict if strict else asof)(symbol, asof_date)
    return None if rec is None else rec.get("close")


def close_series(symbol: str, dates: List[str]) -> List[Optional[float]]:
    """Return close aligned to an explicit list of ISO `dates` (forward-fill).

    For each requested date D, returns the close of the bar dated exactly D if
    present, else the most-recent prior bar's close (forward-fill), else None.
    Forward-fill never looks ahead (only <= D). Useful to align two pairs onto a
    common trading-date axis for a basket.
    """
    get_daily(symbol)
    out: List[Optional[float]] = []
    for d in dates:
        rec = asof(symbol, d)
        out.append(None if rec is None else rec.get("close"))
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
def selftest(symbols=("EURUSD=X", "USDJPY=X")) -> None:
    """Fetch a couple majors and prove the lookahead guard. Hits the network on
    a cold cache; uses disk on re-run. Raises on any invariant violation."""
    print(f"[fx_bars_cache] cache dir: {CACHE_DIR}")
    for sym in symbols:
        bars = get_daily(sym)
        sp = span(sym)
        print(f"  {sym:10s} n={sp['n']:5d}  first={sp['first']}  last={sp['last']}  "
              f"close0={bars[0]['close']!r}")
        assert bars[0]["close"] is not None, f"{sym}: missing close"
        assert all(bars[i]["date"] < bars[i + 1]["date"] for i in range(len(bars) - 1)), \
            f"{sym}: dates not strictly ascending"
        # FX: adjclose must equal close.
        assert all(b["adjclose"] == b["close"] for b in bars[:50]), \
            f"{sym}: adjclose != close (unexpected for FX)"

        mid = bars[len(bars) // 2]
        prev = bars[len(bars) // 2 - 1]
        r_strict = asof_strict(sym, mid["date"])
        assert r_strict is not None and r_strict["date"] == prev["date"], \
            f"{sym}: asof_strict leaked same-date bar"
        r_incl = asof(sym, mid["date"])
        assert r_incl is not None and r_incl["date"] == mid["date"], \
            f"{sym}: asof inclusive did not return same-date bar"
        r_future = asof(sym, "2999-01-01")
        assert r_future is not None and r_future["date"] == bars[-1]["date"]
    print("[fx_bars_cache] selftest OK")


if __name__ == "__main__":
    selftest(FX_MAJORS)
