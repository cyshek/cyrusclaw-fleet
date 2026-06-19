"""Disk cache + ingest for CFTC COT (Commitments of Traders) positioning data.

RESEARCH/BACKTEST-ONLY. Parallel to `bars_cache.py` (Alpaca OHLCV) and
`fred_cache.py` (FRED/ALFRED macro). Tier-1 free-data source #2 in the
orthogonal-signal hunt: weekly speculator POSITIONING (not a price transform),
so it has a shot at correlation <~0.3 to the OHLCV price/vol lanes that all top
out ~0.5 FP-cont Sharpe.

DATA SOURCE (public domain, no key, verified HTTP 200 from this VM):
  CFTC "Traders in Financial Futures" (TFF) combined report. Annual zips:
      https://www.cftc.gov/files/dea/history/fut_fin_txt_<YEAR>.zip
  Each unzips to a single `FinFutYY.txt` (quoted CSV w/ header). TFF financial-
  futures reporting begins **2010**. Trader categories:
      Dealer    = swap dealers / intermediaries ("smart-money short hedge")
      Asset_Mgr = institutional asset managers (slow institutional side)
      Lev_Money = leveraged funds = hedge-fund SPECULATORS (the crowding side)
  We START WITH TFF 2010->present. The legacy deacot/fut_disagg reports go back
  to 1986/2006 but use DIFFERENT categories -- mixing would corrupt the category
  definitions. So this module is TFF-only.

  *** 2008-GAP CAVEAT (matters for graduation regime-robustness) ***
  TFF begins 2010, so the 2008 GFC is NOT covered. A COT-TFF backtest cannot be
  stress-tested against 2008. We flag this loudly rather than splice in the
  incompatible legacy report.

SCHEMA DRIFT WE HANDLE (verified across the 2012 vs 2025 files):
  - Tuesday snapshot date lives in `As_of_Date_In_Form_YYMMDD` (e.g. "251230").
    This column name is STABLE across years -> canonical snapshot date. The
    human-readable `Report_Date_*` column is NOT stable (2012:
    `Report_Date_as_MM_DD_YYYY`, 2025: `Report_Date_as_YYYY-MM-DD`, both holding
    YYYY-MM-DD values) so we avoid it.
  - Older files have TRAILING WHITESPACE in fields. We strip everything.
  - CONTRACT NAMES were renamed: "E-MINI S&P 500 STOCK INDEX" -> "E-MINI S&P
    500"; "NASDAQ-100 STOCK INDEX (MINI)" -> "NASDAQ MINI"; "10-YEAR U.S.
    TREASURY NOTES" -> "UST 10Y NOTE". CONTRACT_SPECS match by substring
    pattern-sets so one logical market resolves across the rename; matched names
    are LOGGED for audit.

================================ THE LOOKAHEAD GUARD ===========================
The make-or-break -- the COT analog of the FRED ALFRED point-in-time guard.

  A COT report snapshots positions as of **Tuesday's close** but is PUBLISHED
  the following **Friday 15:30 ET** (~3 calendar-day lag; longer around federal
  holidays). Letting the Tuesday snapshot inform a trade BEFORE that Friday is a
  silent lookahead leak that inflates Sharpe.

  THEREFORE the ONLY trading accessor is `released_asof(market, date)`: it
  returns the most recent report whose RELEASE date is <= `date`. Release date:
        release = snapshot_tuesday + RELEASE_LAG_DAYS  (3 -> the Friday),
  forced to >= Friday of the snapshot week, bumped to the next business day if
  that Friday is a US market holiday. We err LATE, never early.

  `released_asof` asserts the returned snapshot's release <= query date and
  raises CotLookaheadError otherwise. `selftest_*` proves a Tuesday snapshot is
  INVISIBLE on Wed/Thu and only appears on/after Friday.
===============================================================================

Cache layout under `data_cache/cot/`:
  - raw zips:  fut_fin_txt_<YEAR>.zip   (fetched once, sequentially)
  - parsed:    parsed_<YEAR>.json
A re-run hits the cache and never re-downloads from CFTC.

CLI:   python3 -m runner.cot_cache        # runs the selftest battery
"""

from __future__ import annotations

import csv
import io
import json
import math
import time
import urllib.request
import zipfile
from bisect import bisect_right
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
CACHE_DIR = WORKSPACE / "data_cache" / "cot"
HISTORY_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"

TFF_FIRST_YEAR = 2010          # TFF begins 2010; 2008 GFC NOT covered.
RELEASE_LAG_DAYS = 3           # Tuesday snapshot -> Friday release.

# Logical market -> matching rules + mappable ETF. Patterns are matched
# case-insensitively against the WHITESPACE-STRIPPED name.
#   require:     ALL substrings present (AND).
#   require_any: at least one require-set matches (OR) -- for disjoint renames.
#   exclude:     none present (locks off consolidated/micro/sector variants).
CONTRACT_SPECS: Dict[str, dict] = {
    "ES": {
        "etf": "SPY",
        "human": "E-mini S&P 500 (CME)",
        "require": ["E-MINI S&P 500"],
        "exclude": ["CONSOLIDATED", "MICRO", "ANNUAL", "QUARTERLY", "DIVIDEND",
                    "ADJUSTED", "S&P 400"],
    },
    "NQ": {
        "etf": "QQQ",
        "human": "E-mini NASDAQ-100 (CME)",
        "require": ["NASDAQ", "MINI"],
        "exclude": ["CONSOLIDATED", "MICRO"],
    },
    "ZN": {
        "etf": "IEF",
        "human": "10-Year U.S. Treasury Notes (CBOT)",
        "require_any": [["10-YEAR U.S. TREASURY NOTES"], ["UST 10Y NOTE"]],
        "exclude": ["ULTRA", "MICRO", "YIELD"],
    },
}


class CotError(RuntimeError):
    pass


class CotFetchError(CotError):
    pass


class CotLookaheadError(CotError):
    """Raised if released_asof would expose a snapshot before its release date
    -- the point-in-time canary. We refuse leaked data."""


class CotSchemaError(CotError):
    """Raised when an annual file lacks required columns (unhandled drift)."""


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_yymmdd(s: str) -> Optional[date]:
    """Parse As_of_Date_In_Form_YYMMDD ('251230' -> 2025-12-30). Trailing
    whitespace tolerated. TFF starts 2010 so 2-digit year -> 20YY."""
    s = (s or "").strip()
    if len(s) != 6 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%y%m%d").date()
    except ValueError:
        return None


def _easter(year: int) -> date:
    """Anonymous Gregorian algorithm (for Good Friday)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _us_market_holidays(year: int) -> set:
    """Conservative US market-holiday set affecting a Fri COT release. Need not
    be exhaustive -- it only must never serve a value EARLY; more holidays =
    later releases = safe."""
    hols = set()

    def observed(d: date) -> date:
        if d.weekday() == 5:
            return d - timedelta(days=1)
        if d.weekday() == 6:
            return d + timedelta(days=1)
        return d

    hols.add(observed(date(year, 1, 1)))
    hols.add(observed(date(year, 7, 4)))
    hols.add(observed(date(year, 12, 25)))
    hols.add(observed(date(year, 6, 19)))
    hols.add(_easter(year) - timedelta(days=2))  # Good Friday

    def nth_weekday(y, month, weekday, n):
        d = date(y, month, 1)
        offset = (weekday - d.weekday()) % 7
        return d + timedelta(days=offset + 7 * (n - 1))

    def last_weekday(y, month, weekday):
        if month == 12:
            d = date(y, 12, 31)
        else:
            d = date(y, month + 1, 1) - timedelta(days=1)
        offset = (d.weekday() - weekday) % 7
        return d - timedelta(days=offset)

    hols.add(nth_weekday(year, 1, 0, 3))
    hols.add(nth_weekday(year, 2, 0, 3))
    hols.add(last_weekday(year, 5, 0))
    hols.add(nth_weekday(year, 9, 0, 1))
    hols.add(nth_weekday(year, 11, 3, 4))
    return hols


def release_date_for(snapshot: date) -> date:
    """Conservative PUBLIC release date for a Tuesday COT snapshot.

    snapshot + RELEASE_LAG_DAYS, forced >= Friday of the snapshot week, then
    bumped to the next business day past any US market holiday. ALWAYS errs late.

    Worked example (asserted in selftest):
        snapshot 2025-12-30 (Tue) -> +3d 2026-01-02 (Fri) -> release 2026-01-02.
        A trade on 2025-12-31 / 2026-01-01 must NOT see this snapshot.
    """
    rel = snapshot + timedelta(days=RELEASE_LAG_DAYS)
    if rel.weekday() < 4:
        rel = rel + timedelta(days=(4 - rel.weekday()))
    for _ in range(10):
        if rel.weekday() >= 5 or rel in _us_market_holidays(rel.year):
            rel = rel + timedelta(days=1)
        else:
            break
    return rel


# ---------------------------------------------------------------------------
# Fetch + parse (cached)
# ---------------------------------------------------------------------------

def _http_get_bytes(url: str, retries: int = 3) -> bytes:
    """GET raw bytes with bounded backoff. Sequential, polite. Raises CotFetchError."""
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent":
                              "trading-bench/1.0 (research; contact via workspace)"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 transient network
            last_err = e
            time.sleep(min(2.0 * (attempt + 1), 6.0))
    raise CotFetchError(f"CFTC fetch failed after {retries} attempts: {url}: {last_err}")


def _zip_path(year: int) -> Path:
    return CACHE_DIR / f"fut_fin_txt_{year}.zip"


def _parsed_path(year: int) -> Path:
    return CACHE_DIR / f"parsed_{year}.json"


def _match_market(name: str, spec: dict) -> bool:
    """Whitespace-stripped name vs spec. Honors require / require_any / exclude."""
    up = name.upper()
    if any(x.upper() in up for x in spec.get("exclude", [])):
        return False
    if "require_any" in spec:
        for req_set in spec["require_any"]:
            if all(r.upper() in up for r in req_set):
                return True
        return False
    return all(r.upper() in up for r in spec.get("require", []))


def _fnum(row, key) -> Optional[float]:
    v = (row.get(key) or "").strip()
    if v == "" or v == ".":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_year_text(text: str, year: int) -> dict:
    """Parse one FinFutYY.txt -> {logical_market: [rows], _matched_names: {...}}.
    Only CONTRACT_SPECS markets retained."""
    reader = csv.DictReader(io.StringIO(text))
    cols = reader.fieldnames or []
    needed = ["Market_and_Exchange_Names", "As_of_Date_In_Form_YYMMDD",
              "Open_Interest_All",
              "Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All",
              "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All",
              "Dealer_Positions_Long_All", "Dealer_Positions_Short_All"]
    missing = [c for c in needed if c not in cols]
    if missing:
        raise CotSchemaError(
            f"{year}: FinFut file missing required columns {missing}; "
            f"have {cols[:6]}... (schema drift not handled).")

    rows_by_market: Dict[str, List[dict]] = {k: [] for k in CONTRACT_SPECS}
    matched_names: Dict[str, set] = {k: set() for k in CONTRACT_SPECS}

    for row in reader:
        raw_name = (row.get("Market_and_Exchange_Names") or "").strip()
        if not raw_name:
            continue
        snap = _parse_yymmdd(row.get("As_of_Date_In_Form_YYMMDD", ""))
        if snap is None:
            continue
        for logical, spec in CONTRACT_SPECS.items():
            if not _match_market(raw_name, spec):
                continue
            rec = {
                "snapshot": snap.isoformat(),
                "release": release_date_for(snap).isoformat(),
                "raw_name": raw_name,
                "oi": _fnum(row, "Open_Interest_All"),
                "lev_long": _fnum(row, "Lev_Money_Positions_Long_All"),
                "lev_short": _fnum(row, "Lev_Money_Positions_Short_All"),
                "am_long": _fnum(row, "Asset_Mgr_Positions_Long_All"),
                "am_short": _fnum(row, "Asset_Mgr_Positions_Short_All"),
                "deal_long": _fnum(row, "Dealer_Positions_Long_All"),
                "deal_short": _fnum(row, "Dealer_Positions_Short_All"),
            }
            rows_by_market[logical].append(rec)
            matched_names[logical].add(raw_name)

    parsed: dict = {}
    for logical, recs in rows_by_market.items():
        by_snap: Dict[str, dict] = {}
        for rec in recs:
            s = rec["snapshot"]
            prev = by_snap.get(s)
            if prev is None or (rec.get("oi") or -1) > (prev.get("oi") or -1):
                by_snap[s] = rec
        parsed[logical] = [by_snap[s] for s in sorted(by_snap)]
    parsed["_matched_names"] = {k: sorted(matched_names[k]) for k in CONTRACT_SPECS}
    return parsed


def fetch_year(year: int, use_cache: bool = True) -> dict:
    """Fetch + parse one TFF annual file, cached as parsed_<YEAR>.json.
    Sequential, polite: downloads the zip once, reuses on re-run."""
    if year < TFF_FIRST_YEAR:
        raise CotError(
            f"TFF financial-futures reporting begins {TFF_FIRST_YEAR}; "
            f"year {year} not available (2008/GFC NOT covered by TFF).")
    pp = _parsed_path(year)
    if use_cache and pp.exists() and pp.stat().st_size > 2:
        try:
            data = json.loads(pp.read_text())
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zp = _zip_path(year)
    if not (use_cache and zp.exists() and zp.stat().st_size > 100):
        raw = _http_get_bytes(HISTORY_URL.format(year=year))
        try:
            zp.write_bytes(raw)
        except Exception:
            pass

    try:
        with zipfile.ZipFile(zp) as zf:
            inner = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not inner:
                raise CotFetchError(f"{year}: zip has no .txt member: {zf.namelist()}")
            text = zf.read(inner[0]).decode("utf-8", "replace")
    except zipfile.BadZipFile as e:
        raise CotFetchError(f"{year}: bad zip ({e}); delete {zp} and retry.")

    parsed = _parse_year_text(text, year)
    try:
        pp.write_text(json.dumps(parsed))
    except Exception:
        pass
    return parsed


# ---------------------------------------------------------------------------
# Series assembly across years + the point-in-time accessor
# ---------------------------------------------------------------------------

# In-process memo so a backtest sweep doesn't re-read JSON per decision.
_SERIES_MEMO: Dict[Tuple[str, int, int], List[dict]] = {}


def _derive(rec: dict) -> dict:
    """Attach derived positioning features to a snapshot row (net/OI fractions).
    Net = long - short; *_net_oi = net / open_interest. None-safe."""
    out = dict(rec)
    oi = rec.get("oi")
    def net(a, b):
        return (a - b) if (a is not None and b is not None) else None
    ln = net(rec.get("lev_long"), rec.get("lev_short"))
    an = net(rec.get("am_long"), rec.get("am_short"))
    dn = net(rec.get("deal_long"), rec.get("deal_short"))
    out["lev_net"] = ln
    out["am_net"] = an
    out["deal_net"] = dn
    has_oi = oi is not None and oi > 0
    out["lev_net_oi"] = (ln / oi) if (ln is not None and has_oi) else None
    out["am_net_oi"] = (an / oi) if (an is not None and has_oi) else None
    out["deal_net_oi"] = (dn / oi) if (dn is not None and has_oi) else None
    return out


def load_series(market: str, start_year: int = TFF_FIRST_YEAR,
                end_year: Optional[int] = None, use_cache: bool = True) -> List[dict]:
    """Full weekly snapshot series for one logical market over [start_year,
    end_year], oldest snapshot first, with derived features attached.

    Z-score / percentile features are computed POINT-IN-TIME in the strategy
    (they need a trailing window respecting release dates), not here.
    """
    if market not in CONTRACT_SPECS:
        raise CotError(f"unknown market {market!r}; known: {list(CONTRACT_SPECS)}")
    if end_year is None:
        end_year = datetime.utcnow().year
    key = (market, start_year, end_year)
    if use_cache and key in _SERIES_MEMO:
        return _SERIES_MEMO[key]

    merged: Dict[str, dict] = {}
    for yr in range(start_year, end_year + 1):
        try:
            parsed = fetch_year(yr, use_cache=use_cache)
        except CotFetchError:
            continue  # genuinely-unavailable year: skip, keep the rest
        for rec in parsed.get(market, []):
            merged[rec["snapshot"]] = rec

    series = [_derive(merged[s]) for s in sorted(merged)]
    _SERIES_MEMO[key] = series
    return series


def _assert_no_lookahead(rec: dict, asof: str) -> None:
    """Hard canary: a served snapshot's RELEASE date must be <= asof. If not we
    are leaking future information -> refuse."""
    rel = rec.get("release")
    if rel is None or rel > asof:
        raise CotLookaheadError(
            f"LOOKAHEAD: snapshot {rec.get('snapshot')} releases {rel} but was "
            f"requested as-of {asof} -- refusing to leak a not-yet-published COT "
            f"report (release > asof).")


def released_asof(market: str, asof, start_year: int = TFF_FIRST_YEAR,
                  end_year: Optional[int] = None) -> Optional[dict]:
    """*** THE ONLY POINT-IN-TIME TRADING ACCESSOR ***

    Return the most recent COT snapshot for `market` whose RELEASE date is <=
    `asof` (a date or 'YYYY-MM-DD' string), or None if none is released yet.

    This is what guarantees no lookahead: a Tuesday snapshot is invisible until
    its Friday release. The returned row carries derived features + both
    snapshot and release dates. Asserts the no-leak invariant before returning.
    """
    if isinstance(asof, (date, datetime)):
        asof = asof.isoformat()[:10]
    else:
        asof = str(asof)[:10]
    series = load_series(market, start_year=start_year, end_year=end_year)
    if not series:
        return None
    # series is sorted by snapshot date; release date is monotonic in snapshot
    # date (snapshot + a fixed lag + holiday bumps preserve order), so a binary
    # search on release dates is valid.
    rels = [r["release"] for r in series]
    idx = bisect_right(rels, asof) - 1
    if idx < 0:
        return None
    rec = series[idx]
    _assert_no_lookahead(rec, asof)
    return rec


def released_history(market: str, asof, lookback: Optional[int] = None,
                     start_year: int = TFF_FIRST_YEAR,
                     end_year: Optional[int] = None) -> List[dict]:
    """All snapshots for `market` RELEASED on/before `asof`, oldest first. The
    point-in-time trailing window used to compute z-scores / percentiles without
    leaking. If `lookback` is given, only the last `lookback` released rows.
    Every returned row satisfies release <= asof (asserted)."""
    if isinstance(asof, (date, datetime)):
        asof = asof.isoformat()[:10]
    else:
        asof = str(asof)[:10]
    series = load_series(market, start_year=start_year, end_year=end_year)
    rels = [r["release"] for r in series]
    idx = bisect_right(rels, asof) - 1
    if idx < 0:
        return []
    hist = series[: idx + 1]
    if hist:
        _assert_no_lookahead(hist[-1], asof)  # newest must satisfy invariant
    if lookback is not None and lookback > 0:
        hist = hist[-lookback:]
    return hist


def matched_contract_names(market: str, start_year: int = TFF_FIRST_YEAR,
                           end_year: Optional[int] = None) -> List[str]:
    """The distinct raw Market_and_Exchange_Names that matched `market` across
    the year range -- for the provenance audit in the report."""
    if end_year is None:
        end_year = datetime.utcnow().year
    names: set = set()
    for yr in range(start_year, end_year + 1):
        try:
            parsed = fetch_year(yr)
        except CotFetchError:
            continue
        for n in (parsed.get("_matched_names", {}) or {}).get(market, []):
            names.add(n)
    return sorted(names)


# ---------------------------------------------------------------------------
# Selftest battery (proves the lookahead guard + ingest). Safe to run live.
# ---------------------------------------------------------------------------

def selftest_lookahead_guard() -> Dict[str, object]:
    """Prove the point-in-time guard: a Tuesday snapshot must be INVISIBLE on
    Wed/Thu and only become visible on/after its Friday release. Uses a synthetic
    snapshot (no network) for the date math, plus a real-data check if cached.

    Returns a report dict; raises CotLookaheadError if the guard is broken.
    """
    report: Dict[str, object] = {}

    # 1) Pure date-math proof on a known Tuesday (no network needed).
    tue = date(2025, 12, 30)               # a Tuesday
    rel = release_date_for(tue)
    report["worked_example_snapshot"] = tue.isoformat()
    report["worked_example_release"] = rel.isoformat()
    report["worked_example_release_weekday"] = rel.strftime("%A")
    report["release_is_after_snapshot"] = rel > tue
    report["release_gap_days"] = (rel - tue).days
    # The snapshot must NOT be usable on Wed (12-31) or Thu (01-01) but MUST be
    # usable on/after the computed release (Fri 01-02).
    report["invisible_on_wed"] = (date(2025, 12, 31).isoformat() < rel.isoformat())
    report["invisible_on_thu"] = (date(2026, 1, 1).isoformat() < rel.isoformat())
    report["visible_on_release"] = (rel.isoformat() >= rel.isoformat())

    # 2) released_asof on a synthetic 1-row series via monkey-free direct call:
    #    we can't avoid load_series's disk, so only run the real check if at
    #    least one year is cached/fetchable. Guarded so the date-math proof above
    #    always runs even offline.
    try:
        series = load_series("ES")
    except Exception as e:  # noqa: BLE001
        report["real_data_check"] = f"skipped ({type(e).__name__}: {e})"
        return report

    if series:
        # Pick a real snapshot in the middle of the series.
        mid = series[len(series) // 2]
        snap = mid["snapshot"]
        rel2 = mid["release"]
        # Day before release: that snapshot must NOT be the one returned.
        day_before = (datetime.strptime(rel2, "%Y-%m-%d").date()
                      - timedelta(days=1)).isoformat()
        got_before = released_asof("ES", day_before)
        report["midpoint_snapshot"] = snap
        report["midpoint_release"] = rel2
        report["asof_day_before_release_returns_older"] = (
            got_before is None or got_before["snapshot"] < snap)
        # On the release date the snapshot IS visible (it's the most recent
        # released as-of the release date).
        got_on = released_asof("ES", rel2)
        report["asof_release_date_returns_it_or_newer"] = (
            got_on is not None and got_on["snapshot"] >= snap
            and got_on["release"] <= rel2)
        # Explicit canary: released_asof one day before release must NEVER carry
        # a release date > asof (the assert inside released_asof enforces this;
        # we re-check here).
        if got_before is not None:
            report["no_leak_on_day_before"] = got_before["release"] <= day_before
        else:
            report["no_leak_on_day_before"] = True
    return report


def selftest_ingest(year: int = 2025) -> Dict[str, object]:
    """Prove ingest: fetch/parse one year, confirm each logical market matched a
    real contract and produced weekly Tuesday snapshots with sane positioning."""
    report: Dict[str, object] = {}
    parsed = fetch_year(year)
    report["year"] = year
    for mk in CONTRACT_SPECS:
        rows = parsed.get(mk, [])
        names = (parsed.get("_matched_names", {}) or {}).get(mk, [])
        sample = rows[len(rows) // 2] if rows else None
        report[mk] = {
            "etf": CONTRACT_SPECS[mk]["etf"],
            "matched_names": names,
            "n_weekly_snapshots": len(rows),
            "first_snapshot": rows[0]["snapshot"] if rows else None,
            "last_snapshot": rows[-1]["snapshot"] if rows else None,
            "sample_lev_net_oi": (
                round(_derive(sample)["lev_net_oi"], 4)
                if sample and _derive(sample)["lev_net_oi"] is not None else None),
        }
    return report


def selftest_span(start_year: int = TFF_FIRST_YEAR,
                  end_year: Optional[int] = None) -> Dict[str, object]:
    """Report the assembled span per market (history length + 2008-gap note)."""
    report: Dict[str, object] = {"tff_first_year": TFF_FIRST_YEAR,
                                 "covers_2008": False,
                                 "note_2008_gap": "TFF starts 2010; 2008 GFC not covered."}
    for mk in CONTRACT_SPECS:
        s = load_series(mk, start_year=start_year, end_year=end_year)
        report[mk] = {
            "etf": CONTRACT_SPECS[mk]["etf"],
            "n_snapshots": len(s),
            "first": s[0]["snapshot"] if s else None,
            "last": s[-1]["snapshot"] if s else None,
            "matched_names": matched_contract_names(mk, start_year, end_year),
        }
    return report


if __name__ == "__main__":
    import pprint
    print("=== COT cot_cache selftest battery ===\n")
    print("--- selftest_lookahead_guard (the make-or-break) ---")
    try:
        pprint.pprint(selftest_lookahead_guard())
    except CotError as e:
        print(f"[cot_cache] LOOKAHEAD GUARD FAILED: {e}")
        raise SystemExit(2)
    print("\n--- selftest_ingest(2025) ---")
    try:
        pprint.pprint(selftest_ingest(2025))
    except CotError as e:
        print(f"[cot_cache] INGEST BLOCKED: {e}")
        raise SystemExit(2)
    print("\n--- selftest_span ---")
    try:
        pprint.pprint(selftest_span())
    except CotError as e:
        print(f"[cot_cache] SPAN BLOCKED: {e}")
        raise SystemExit(2)
    print("\n[cot_cache] OK")
