"""Disk cache + keyed-API ingest for FRED / ALFRED macro series.

RESEARCH/BACKTEST-ONLY. Parallel to `bars_cache.py` (which caches Alpaca OHLCV).

WHY THIS EXISTS (critical correctness — see memory 2026-06-05 FRED trap):
  The `fred.stlouisfed.org/graph/fredgraph.csv` path is POISON from this VM:
    - Akamai bot-walls it under light load (HTTP 000 / 403).
    - It SILENTLY IGNORES cosd/coed for many series and returns a fixed ~3yr
      rolling window with HTTP 200 (reproduced 2026-06-05 on BAMLH0A0HYM2:
      a 2010 or 2022 request returned 2023->2026 data, mislabeled). A backtest
      built on it would be silently corrupted.
  THEREFORE this module ONLY uses the keyed official JSON API:
      https://api.stlouisfed.org/fred/series/observations   (current-revised)
      https://api.stlouisfed.org/fred/series/observations?realtime_*  (ALFRED PIT)
  A free instant API key is required. Read from FRED_API_KEY (env or .env).
  We NEVER fall back to fredgraph.csv.

LOOKAHEAD GUARD (the make-or-break for revised macro series):
  Many FRED series are revised after release (NFCI, GDP-ish, etc). Serving the
  FINAL-revised value against a historical date is a silent lookahead leak
  (you "knew" on date d a number not published until d+weeks, later revised).
  Two safe modes:
    - vintage="latest"  : current-revised series. ONLY safe for series that are
      effectively un-revised by construction (market-priced spreads: HY OAS,
      T10Y2Y are daily market quotes; NFCI is lightly revised but we still PIT it).
    - vintage="alfred"  : point-in-time. We pull the ALFRED vintage as-of each
      query date via realtime_start/realtime_end so the value returned is what
      was ACTUALLY PUBLISHED on/before that date. Use this for any revised series.

  `observation_start`/`observation_end` are HONORED by the keyed API (verified),
  unlike the CSV path. We additionally ASSERT the returned date span is inside
  the requested window and raise StaleWindowError if not — so if the keyed API
  ever develops the CSV's ignore-dates bug, we fail LOUD instead of silent.

Cache key: (series_id, start, end, vintage[, asof]) -> JSON under
  `.cache/fred/{series_id}_{start}_{end}_{vintage}.json`
Stored format: list of {"date": "YYYY-MM-DD", "value": float|None}, oldest-first.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(__file__).resolve().parent.parent
CACHE_DIR = WORKSPACE / ".cache" / "fred"
API_BASE = "https://api.stlouisfed.org/fred/series/observations"

# Series we care about for the credit/curve/conditions lane (main's Tier-1 #1).
# Documented here so the lane and the cache agree on ids + revision profile.
SERIES = {
    # id            : (human, revised?)  -- revised? drives default vintage mode
    "BAMLH0A0HYM2":   ("ICE BofA US High Yield OAS (HY spread)", False),
    "BAMLC0A0CM":     ("ICE BofA US Corporate OAS (IG spread)",  False),
    "T10Y2Y":         ("10yr-2yr Treasury slope",                 False),
    "T10Y3M":         ("10yr-3mo Treasury slope",                 False),
    "NFCI":           ("Chicago Fed Natl Financial Conditions",   True),
    "VIXCLS":         ("CBOE VIX (level)",                         False),
}


class FredError(RuntimeError):
    pass


class StaleWindowError(FredError):
    """Raised when returned observation dates fall outside the requested window.

    This is the canary for the CSV-style 'ignores date params' corruption ever
    appearing on the keyed path. We refuse silently-wrong data.
    """


def _api_key() -> str:
    """Resolve the FRED API key from env or .env. Raise a clear, actionable error."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        env_path = WORKSPACE / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("FRED_API_KEY"):
                    # FRED_API_KEY=xxxx  or  export FRED_API_KEY="xxxx"
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    key = val
                    break
    if not key:
        raise FredError(
            "FRED_API_KEY not set (checked env and .env). Get a free instant key "
            "at https://fredaccount.stlouisfed.org/apikeys and put "
            "FRED_API_KEY=<key> in the workspace .env. We do NOT fall back to "
            "fredgraph.csv (it silently corrupts historical windows)."
        )
    if not (len(key) == 32 and key.isalnum() and key.islower()):
        raise FredError(
            f"FRED_API_KEY looks malformed (got {len(key)} chars). The keyed API "
            "requires a 32-char lowercase alphanumeric key."
        )
    return key


def _safe(series_id: str) -> str:
    return series_id.replace("/", "-").upper()


def _cache_path(series_id: str, start: str, end: str, vintage: str) -> Path:
    fname = f"{_safe(series_id)}_{start}_{end}_{vintage}.json"
    return CACHE_DIR / fname


def _http_get_json(url: str, retries: int = 4) -> dict:
    """GET a URL, parse JSON, with bounded backoff. Raises FredError on failure.

    Note: we use urllib (stdlib) — no third-party deps on this box. A realistic
    UA avoids trivial blocks; the keyed api host is not Akamai-bot-walled like
    the CSV graph host, but we stay polite (<=10 req/s upstream) anyway.
    """
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "trading-bench/1.0 (research; contact via workspace)"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("error_code"):
                # FRED returns 400 JSON with error_code/error_message
                raise FredError(
                    f"FRED API error {data.get('error_code')}: {data.get('error_message')}"
                )
            return data
        except FredError:
            raise  # an explicit API error (bad key, bad series) — don't retry blindly
        except Exception as e:  # noqa: BLE001 network/json transient
            last_err = e
            time.sleep(min(2.0 * (attempt + 1), 6.0))
    raise FredError(f"FRED request failed after {retries} attempts: {last_err}")


def _assert_window(rows: List[dict], start: str, end: str, series_id: str) -> None:
    """Refuse data whose dates fall outside [start, end] (CSV-corruption canary)."""
    real = [r["date"] for r in rows if r.get("date")]
    if not real:
        return  # empty window is allowed (e.g. series starts later); caller decides
    lo, hi = min(real), max(real)
    # Allow a small slack: FRED may clamp to series availability, but it must not
    # return data NEWER than requested end nor OLDER than requested start.
    if hi > end or lo < start:
        raise StaleWindowError(
            f"{series_id}: returned dates [{lo}..{hi}] fall outside requested "
            f"window [{start}..{end}] — refusing silently-wrong data."
        )


def get_series(series_id: str, start: str, end: str,
               vintage: str = "latest", asof: Optional[str] = None,
               use_cache: bool = True) -> List[dict]:
    """Return [{date, value}] for series_id over [start, end], oldest-first.

    vintage:
      "latest" -> current-revised values (safe only for unrevised series).
      "alfred" -> point-in-time as published as-of `asof` (default = end).
                  Implemented via realtime_start=realtime_end=asof so FRED
                  returns the vintage known on that date (no future revisions).

    Cached to disk under .cache/fred/. Raises FredError if no API key, and
    StaleWindowError if the API ignores the date window.
    """
    start = str(start)[:10]
    end = str(end)[:10]
    if vintage not in ("latest", "alfred"):
        raise ValueError(f"vintage must be 'latest' or 'alfred', got {vintage!r}")

    cache_tag = vintage if vintage == "latest" else f"alfred-{asof or end}"
    path = _cache_path(series_id, start, end, cache_tag)
    if use_cache and path.exists() and path.stat().st_size > 2:
        try:
            data = json.loads(path.read_text())
            if isinstance(data, list):
                return data
        except Exception:
            pass  # fall through to refetch

    key = _api_key()
    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "observation_start": start,
        "observation_end": end,
        "sort_order": "asc",
    }
    if vintage == "alfred":
        rt = asof or end
        params["realtime_start"] = rt
        params["realtime_end"] = rt
    url = API_BASE + "?" + urllib.parse.urlencode(params)
    payload = _http_get_json(url)

    obs = payload.get("observations") or []
    rows: List[dict] = []
    for o in obs:
        d = o.get("date")
        v = o.get("value")
        # FRED uses "." for missing values
        val: Optional[float]
        if v is None or v == "." or v == "":
            val = None
        else:
            try:
                val = float(v)
            except ValueError:
                val = None
        rows.append({"date": d, "value": val})

    _assert_window(rows, start, end, series_id)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(rows))
    except Exception:
        pass  # cache best-effort
    return rows


def get_values(series_id: str, start: str, end: str,
               vintage: str = "latest", asof: Optional[str] = None,
               drop_missing: bool = True) -> List[tuple]:
    """Convenience: return [(date, value)] tuples, optionally dropping None values."""
    rows = get_series(series_id, start, end, vintage=vintage, asof=asof)
    if drop_missing:
        return [(r["date"], r["value"]) for r in rows if r["value"] is not None]
    return [(r["date"], r["value"]) for r in rows]


def selftest_window_integrity() -> Dict[str, object]:
    """Run a battery proving (a) the key works, (b) date windows are HONORED,
    (c) 2008 + 2020 + 2022 history is actually reachable (the CSV path could not).

    Returns a dict report; raises if the key is missing/bad. Safe to call from a
    smoke test once the key is installed. Does NOT mutate anything but the cache.
    """
    report: Dict[str, object] = {}
    # 1) HY OAS deep-history reach: the CSV path capped at ~2023. The keyed API
    #    should reach the series origin (~1996 for BAMLH0A0HYM2).
    hy = get_series("BAMLH0A0HYM2", "1997-01-01", "2009-12-31", vintage="latest")
    hy_real = [r for r in hy if r["value"] is not None]
    report["hy_oas_1997_2009_n"] = len(hy_real)
    report["hy_oas_first"] = hy_real[0] if hy_real else None
    report["hy_oas_covers_2008"] = any(r["date"].startswith("2008") for r in hy_real)
    # 2) Date-window honored: ask a tight 2008 window, assert it returns 2008.
    w08 = get_series("T10Y2Y", "2008-09-01", "2008-09-30", vintage="latest")
    w08_real = [r for r in w08 if r["value"] is not None]
    report["t10y2y_2008sep_n"] = len(w08_real)
    report["t10y2y_2008sep_all_in_window"] = all(
        r["date"].startswith("2008-09") for r in w08_real
    )
    # 3) ALFRED point-in-time on a revised series (NFCI): as-of an old date must
    #    NOT contain observations dated after that as-of date.
    asof = "2010-06-30"
    nfci_pit = get_series("NFCI", "2008-01-01", "2010-12-31",
                          vintage="alfred", asof=asof)
    nfci_real = [r for r in nfci_pit if r["value"] is not None]
    report["nfci_pit_asof"] = asof
    report["nfci_pit_n"] = len(nfci_real)
    report["nfci_pit_no_future_leak"] = all(r["date"] <= asof for r in nfci_real)
    return report


if __name__ == "__main__":
    # Manual smoke once the key is installed:  python3 -m runner.fred_cache
    import pprint
    try:
        pprint.pprint(selftest_window_integrity())
    except FredError as e:
        print(f"[fred_cache] BLOCKED: {e}")
        raise SystemExit(2)
