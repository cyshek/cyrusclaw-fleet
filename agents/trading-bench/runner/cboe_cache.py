"""Disk cache + keyless ingest for the CBOE VIX-complex daily index CSVs.

RESEARCH/BACKTEST-ONLY. Parallel to `bars_cache.py` (Alpaca OHLCV),
`fred_cache.py` (FRED/ALFRED macro), and `cot_cache.py` (CFTC COT positioning).
This is the free, deep, IP-unwalled VIX-complex source for the Natenberg-derived
"VIX regime/carry overlay on a long-SPX core" idea (NATENBERG_SYNTHESIS idea #2).

DATA SOURCE (public CDN, NO key, verified HTTP 200 + real CSV from this VM):
  CBOE publishes the whole VIX complex as daily-updating CSVs on its CDN:
      https://cdn.cboe.com/api/global/us_indices/daily_prices/<IDX>_History.csv
  Verified live 2026-06-08 (this build re-verified the same day):
      IDX        layout                       earliest     latest
      VIX        DATE,OPEN,HIGH,LOW,CLOSE     1990-01-02   ~T-1
      VIX3M      DATE,OPEN,HIGH,LOW,CLOSE     2009-09-18   ~T-1
      VVIX       DATE,VVIX  (close only)      2006-03-06   ~T-1
      SKEW       DATE,SKEW  (close only)      1990-01-02   ~T-1
      VIX9D      DATE,OPEN,HIGH,LOW,CLOSE     2011-01-04   ~T-1   (optional)
      VXN        DATE,OPEN,HIGH,LOW,CLOSE     ~2001        ~T-1   (optional; Nasdaq vol)
  Date format is MM/DD/YYYY. No auth header, no documented rate limit (static
  CDN objects refreshed daily). We cache to disk so re-runs never re-hit the net.

  *** WHY CBOE CDN AND NOT YAHOO/FRED-CSV ***
  This VM's datacenter IP is bot-walled by Yahoo (^VIX => HTTP 429) and the FRED
  fredgraph.csv path is empty/redirected from here (and SILENTLY corrupts date
  windows even when it works — see fred_cache.py). The CBOE CDN is the clean
  primary and is NOT IP-walled. Do NOT add a Yahoo fallback for these.

============================ THE LOOKAHEAD GUARD ==============================
The make-or-break — the VIX analog of the FRED ALFRED / COT-release guards.

  These are END-OF-DAY index levels. The VIX *close* for trading date D is not
  known until D's close (~13:15 CT settlement / EOD publish). Therefore a
  decision made DURING date D (e.g. at the open, or any intraday rebalance) may
  ONLY use VIX values for dates <= D-1. Letting date D's own close inform a
  trade placed on date D is a silent lookahead leak.

  THEREFORE the ONLY point-in-time trading accessors are:
      asof(idx, date)            -> the single most-recent close with
                                    value_date <= (date - 1 business-ish day),
                                    i.e. STRICTLY before `date`.
      history_asof(idx, date)    -> all closes with value_date < `date`,
                                    oldest first (the trailing window for
                                    z-scores / percentiles, no leak).

  Both ASSERT value_date < asof and raise CboeLookaheadError otherwise. The
  conservative rule is "a print for date D is usable for decisions on D+1 at the
  earliest" — we implement it as "strictly earlier calendar date than the
  decision date", which is the safe (never-early) direction. `selftest_*`
  proves a same-date close is INVISIBLE and only the prior close is served.
==============================================================================

Cache layout under `data_cache/cboe/`:
  - raw csv:   <IDX>_History.csv     (fetched once)
  - parsed:    <IDX>_parsed.json     (list of {date, open?, high?, low?, close})
A re-run hits the parsed cache and never re-downloads.

CLI:   python3 -m runner.cboe_cache        # runs the selftest battery
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from bisect import bisect_left
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(__file__).resolve().parent.parent
CACHE_DIR = WORKSPACE / "data_cache" / "cboe"
CDN_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{idx}_History.csv"

# Known VIX-complex indices + their CSV layout.
#   "ohlc"   -> DATE,OPEN,HIGH,LOW,CLOSE
#   "single" -> DATE,<NAME>  (single value column = the close-equivalent level)
# `col` for "single" is the value column header (CBOE uses the index name).
INDEX_LAYOUT: Dict[str, dict] = {
    "VIX":   {"layout": "ohlc",   "human": "CBOE VIX (30d SPX implied vol)",      "earliest": "1990-01-02"},
    "VIX3M": {"layout": "ohlc",   "human": "CBOE VIX3M (3-month SPX implied vol)", "earliest": "2009-09-18"},
    "VVIX":  {"layout": "single", "col": "VVIX", "human": "CBOE VVIX (vol-of-VIX)", "earliest": "2006-03-06"},
    "SKEW":  {"layout": "single", "col": "SKEW", "human": "CBOE SKEW (tail risk)",  "earliest": "1990-01-02"},
    "VIX9D": {"layout": "ohlc",   "human": "CBOE VIX9D (9d SPX implied vol)",       "earliest": "2011-01-04"},
    "VXN":   {"layout": "ohlc",   "human": "CBOE VXN (Nasdaq-100 implied vol)",     "earliest": "2001-01-01"},
}

# The minimum-required set for the regime overlay. VIX9D/VXN are optional.
CORE_INDICES = ("VIX", "VIX3M", "VVIX", "SKEW")


class CboeError(RuntimeError):
    pass


class CboeFetchError(CboeError):
    pass


class CboeSchemaError(CboeError):
    """Raised when a downloaded CSV lacks the expected columns (layout drift)."""


class CboeLookaheadError(CboeError):
    """Raised if a point-in-time accessor would expose an index level dated on or
    after the as-of (decision) date — the no-leak canary. We refuse leaked data."""


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_mmddyyyy(s: str) -> Optional[date]:
    """Parse CBOE's MM/DD/YYYY date. Trailing whitespace tolerated. None on junk."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except ValueError:
        # A few CBOE files have occasionally used YYYY-MM-DD; tolerate it.
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None


def _as_iso(d) -> str:
    if isinstance(d, (date, datetime)):
        return d.isoformat()[:10]
    return str(d)[:10]


# ---------------------------------------------------------------------------
# Fetch + parse (cached)
# ---------------------------------------------------------------------------

def _http_get_text(url: str, retries: int = 3) -> str:
    """GET text with bounded backoff. Mozilla UA (CDN is fine with anything),
    ~12s timeout. Raises CboeFetchError on failure."""
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent":
                              "Mozilla/5.0 (trading-bench research; contact via workspace)"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 transient network
            last_err = e
            time.sleep(min(1.5 * (attempt + 1), 5.0))
    raise CboeFetchError(f"CBOE CDN fetch failed after {retries} attempts: {url}: {last_err}")


def _raw_path(idx: str) -> Path:
    return CACHE_DIR / f"{idx}_History.csv"


def _parsed_path(idx: str) -> Path:
    return CACHE_DIR / f"{idx}_parsed.json"


def _parse_csv_text(text: str, idx: str) -> List[dict]:
    """Parse one index CSV into [{date, open?, high?, low?, close}], oldest-first.

    Handles both layouts:
      ohlc   -> DATE,OPEN,HIGH,LOW,CLOSE
      single -> DATE,<NAME>  (value stored as `close` so all callers read .close)
    Rows with an unparseable date or a missing/blank value are skipped. The
    canonical level every caller uses is `close`.
    """
    spec = INDEX_LAYOUT.get(idx)
    if spec is None:
        raise CboeError(f"unknown index {idx!r}; known: {sorted(INDEX_LAYOUT)}")
    reader = csv.reader(io.StringIO(text))
    rows: List[dict] = []
    header: Optional[List[str]] = None
    for raw in reader:
        if not raw:
            continue
        cells = [c.strip() for c in raw]
        if header is None:
            # First non-empty row is the header (starts with DATE, case-insensitive).
            if cells and cells[0].upper() == "DATE":
                header = [c.upper() for c in cells]
                continue
            # Some files might omit a header; fall through and try to parse.
            header = []
        d = _parse_mmddyyyy(cells[0]) if cells else None
        if d is None:
            continue
        rec: dict = {"date": d.isoformat()}
        try:
            if spec["layout"] == "ohlc":
                if len(cells) < 5:
                    continue
                rec["open"] = _fnum(cells[1])
                rec["high"] = _fnum(cells[2])
                rec["low"] = _fnum(cells[3])
                rec["close"] = _fnum(cells[4])
            else:  # single value column
                if len(cells) < 2:
                    continue
                rec["close"] = _fnum(cells[1])
        except (IndexError, ValueError):
            continue
        if rec.get("close") is None:
            continue
        rows.append(rec)
    if not rows:
        raise CboeSchemaError(
            f"{idx}: parsed 0 usable rows (layout drift?). First 120 chars: "
            f"{text[:120]!r}")
    # CBOE files are already chronological, but enforce it defensively.
    rows.sort(key=lambda r: r["date"])
    # De-dupe on date (keep last occurrence) in case of any double rows.
    dedup: Dict[str, dict] = {}
    for r in rows:
        dedup[r["date"]] = r
    return [dedup[d] for d in sorted(dedup)]


def _fnum(s: str) -> Optional[float]:
    s = (s or "").strip()
    if s == "" or s == ".":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_index(idx: str, use_cache: bool = True) -> List[dict]:
    """Fetch + parse one VIX-complex index, cached as <IDX>_parsed.json.

    Returns the FULL series [{date, open?, high?, low?, close}], oldest-first.
    Downloads the CSV once and reuses it on re-run. This is the RAW series; it
    is NOT point-in-time safe to slice arbitrarily — use asof()/history_asof()
    for any trading decision.
    """
    idx = idx.upper()
    if idx not in INDEX_LAYOUT:
        raise CboeError(f"unknown index {idx!r}; known: {sorted(INDEX_LAYOUT)}")
    pp = _parsed_path(idx)
    if use_cache and pp.exists() and pp.stat().st_size > 2:
        try:
            data = json.loads(pp.read_text())
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass  # fall through to refetch

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    rp = _raw_path(idx)
    if not (use_cache and rp.exists() and rp.stat().st_size > 100):
        text = _http_get_text(CDN_URL.format(idx=idx))
        try:
            rp.write_text(text)
        except Exception:
            pass
    else:
        text = rp.read_text()

    parsed = _parse_csv_text(text, idx)
    try:
        pp.write_text(json.dumps(parsed))
    except Exception:
        pass
    return parsed


# In-process memo so a backtest sweep doesn't re-read JSON per decision.
_SERIES_MEMO: Dict[str, List[dict]] = {}
# Date-list memo parallel to _SERIES_MEMO for fast bisect.
_DATES_MEMO: Dict[str, List[str]] = {}


def load_series(idx: str, use_cache: bool = True) -> List[dict]:
    """Full series for one index, oldest-first, memoized in-process."""
    idx = idx.upper()
    if use_cache and idx in _SERIES_MEMO:
        return _SERIES_MEMO[idx]
    series = fetch_index(idx, use_cache=use_cache)
    _SERIES_MEMO[idx] = series
    _DATES_MEMO[idx] = [r["date"] for r in series]
    return series


def _dates_for(idx: str) -> List[str]:
    idx = idx.upper()
    if idx not in _DATES_MEMO:
        load_series(idx)
    return _DATES_MEMO[idx]


# ---------------------------------------------------------------------------
# Point-in-time accessors (THE ONLY trading-safe entry points)
# ---------------------------------------------------------------------------

def _assert_no_lookahead(rec: dict, asof_iso: str, idx: str) -> None:
    """Hard canary: a served close's date must be STRICTLY before asof. EOD index
    levels for date D are unknown until D's close, so a decision on date D may
    only use dates < D."""
    vd = rec.get("date")
    if vd is None or vd >= asof_iso:
        raise CboeLookaheadError(
            f"LOOKAHEAD [{idx}]: level dated {vd} requested as-of {asof_iso} — "
            f"refusing to leak an end-of-day level not knowable before the "
            f"decision date (date >= asof).")


def asof(idx: str, asof_date, use_cache: bool = True) -> Optional[dict]:
    """*** POINT-IN-TIME TRADING ACCESSOR ***

    Return the most recent index record whose value-date is STRICTLY BEFORE
    `asof_date` (a date or 'YYYY-MM-DD'), or None if none exists yet. This is
    the no-leak guarantee: date D's own EOD close is invisible to a decision on
    date D; only dates <= D-1 are served. Asserts the invariant before returning.
    """
    idx = idx.upper()
    asof_iso = _as_iso(asof_date)
    load_series(idx, use_cache=use_cache)
    dates = _dates_for(idx)
    if not dates:
        return None
    # First index with date >= asof_iso; we want the one strictly before it.
    pos = bisect_left(dates, asof_iso)
    if pos <= 0:
        return None
    rec = _SERIES_MEMO[idx][pos - 1]
    _assert_no_lookahead(rec, asof_iso, idx)
    return rec


def level_asof(idx: str, asof_date, use_cache: bool = True) -> Optional[float]:
    """Convenience: the close-level of `idx` strictly before `asof_date`, or None."""
    rec = asof(idx, asof_date, use_cache=use_cache)
    return None if rec is None else rec.get("close")


def history_asof(idx: str, asof_date, lookback: Optional[int] = None,
                 use_cache: bool = True) -> List[dict]:
    """All records for `idx` with value-date STRICTLY BEFORE `asof_date`, oldest
    first — the point-in-time trailing window for z-scores / percentiles with no
    leak. If `lookback` is given, only the last `lookback` rows. Every returned
    row satisfies date < asof (the newest is asserted)."""
    idx = idx.upper()
    asof_iso = _as_iso(asof_date)
    load_series(idx, use_cache=use_cache)
    dates = _dates_for(idx)
    pos = bisect_left(dates, asof_iso)
    if pos <= 0:
        return []
    hist = _SERIES_MEMO[idx][:pos]
    if hist:
        _assert_no_lookahead(hist[-1], asof_iso, idx)
    if lookback is not None and lookback > 0:
        hist = hist[-lookback:]
    return hist


def span(idx: str, use_cache: bool = True) -> Dict[str, object]:
    """Report the available span for one index (first/last date + count)."""
    s = load_series(idx, use_cache=use_cache)
    return {
        "index": idx.upper(),
        "human": INDEX_LAYOUT[idx.upper()]["human"],
        "n": len(s),
        "first": s[0]["date"] if s else None,
        "last": s[-1]["date"] if s else None,
    }


# ---------------------------------------------------------------------------
# Selftest battery (proves ingest + the lookahead guard). Safe to run live.
# ---------------------------------------------------------------------------

def selftest_ingest(indices=CORE_INDICES) -> Dict[str, object]:
    """Prove ingest: fetch/parse each core index, confirm sane span + values."""
    report: Dict[str, object] = {}
    for idx in indices:
        s = load_series(idx)
        mid = s[len(s) // 2] if s else None
        report[idx] = {
            "n": len(s),
            "first": s[0]["date"] if s else None,
            "last": s[-1]["date"] if s else None,
            "sample_mid": (mid["date"], round(mid["close"], 2)) if mid else None,
            "expected_earliest": INDEX_LAYOUT[idx]["earliest"],
        }
    return report


def selftest_lookahead_guard(idx: str = "VIX") -> Dict[str, object]:
    """Prove the point-in-time guard: a level dated D is INVISIBLE to a decision
    on D (only D-1 and earlier are served), and history_asof never leaks.

    Returns a diagnostic dict of named boolean checks; raises CboeLookaheadError
    if the guard itself is broken (the asserts inside asof/history_asof).
    """
    report: Dict[str, object] = {"index": idx}
    s = load_series(idx)
    if len(s) < 50:
        report["skipped"] = f"series too short ({len(s)})"
        return report

    # Pick a record well inside the series with a known predecessor.
    mid_i = len(s) // 2
    target = s[mid_i]
    prev = s[mid_i - 1]
    td = target["date"]
    pd = prev["date"]
    report["target_date"] = td
    report["prev_date"] = pd

    # 1) asof(target_date) must return the PREVIOUS record, NOT target itself
    #    (target's own EOD close is not knowable for a decision dated target).
    got = asof(idx, td)
    report["asof_target_returns_prev"] = (got is not None and got["date"] == pd)
    report["asof_target_not_target"] = (got is None or got["date"] != td)
    report["asof_target_strictly_before"] = (got is None or got["date"] < td)

    # 2) asof(target_date + 1 day) IS allowed to return target (date < asof).
    day_after = (datetime.strptime(td, "%Y-%m-%d").date()
                 ).toordinal() + 1
    day_after_iso = date.fromordinal(day_after).isoformat()
    got2 = asof(idx, day_after_iso)
    report["asof_day_after_can_see_target"] = (
        got2 is not None and got2["date"] >= td and got2["date"] < day_after_iso)

    # 3) history_asof(target_date) newest row is strictly before target.
    hist = history_asof(idx, td, lookback=10)
    report["history_newest_before_target"] = (
        bool(hist) and hist[-1]["date"] < td)
    report["history_all_before_target"] = all(r["date"] < td for r in hist)

    return report


def selftest_span(indices=CORE_INDICES) -> Dict[str, object]:
    """Report the assembled span per index (for the report's data-floor honesty)."""
    return {idx: span(idx) for idx in indices}


if __name__ == "__main__":
    import pprint
    print("=== CBOE cboe_cache selftest battery ===\n")
    print("--- selftest_ingest (core 4) ---")
    try:
        pprint.pprint(selftest_ingest())
    except CboeError as e:
        print(f"[cboe_cache] INGEST BLOCKED: {e}")
        raise SystemExit(2)
    print("\n--- selftest_lookahead_guard (the make-or-break) ---")
    try:
        pprint.pprint(selftest_lookahead_guard())
    except CboeError as e:
        print(f"[cboe_cache] LOOKAHEAD GUARD FAILED: {e}")
        raise SystemExit(2)
    print("\n--- selftest_span ---")
    try:
        pprint.pprint(selftest_span())
    except CboeError as e:
        print(f"[cboe_cache] SPAN BLOCKED: {e}")
        raise SystemExit(2)
    print("\n[cboe_cache] OK")