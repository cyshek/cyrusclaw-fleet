"""
finra_shortvol_cache.py - FINRA daily short-SALE-volume (RegSHO CNMSshvol) fetch + cache.

Source (verified live from this VM, 2026-06-22):
    https://cdn.finra.org/equity/regsho/daily/CNMSshvol<YYYYMMDD>.txt
    - Requires a browser User-Agent (HTTP 200 with one).
    - Pipe-delimited: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
    - ONE file per TRADING day; ALL ~10k symbols in it.
    - Archive starts 2019-01-02. NON-TRADING days (weekends/holidays) return 403 OR 404
      (FINRA uses 403 for many missing days), so 403 is NOT an off-archive signal --
      we detect the real archive boundary via a consecutive-no-file circuit breaker.

Core feature: per-symbol short-volume RATIO  SVR = ShortVolume / TotalVolume (short-SALE
flow, a daily pressure proxy, NOT short interest). Use a trailing z/percentile of SVR.

We only PARSE+STORE a small whitelist of symbols. Raw daily files are NOT kept on disk.

Cache layout:
    data_cache/finra_shortvol/<SYM>.json   -> {"symbol","rows":[{date,short,total,svr}, ...]}
    data_cache/finra_shortvol/_fetched_days.json -> {"YYYYMMDD": "ok"|"nofile", ...}
"""

from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional

WORKSPACE = Path(__file__).resolve().parent.parent
CACHE_DIR = WORKSPACE / "data_cache" / "finra_shortvol"
FETCHED_LOG = CACHE_DIR / "_fetched_days.json"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ymd}.txt"

DEFAULT_SYMBOLS = [
    "SPY", "QQQ",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE",
    "IWM", "DIA",
]

ARCHIVE_START = _dt.date(2019, 1, 2)


class FinraFetchError(RuntimeError):
    pass


def _ensure_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_fetched() -> Dict[str, str]:
    if FETCHED_LOG.exists():
        try:
            return json.loads(FETCHED_LOG.read_text())
        except Exception:
            return {}
    return {}


def _save_fetched(d: Dict[str, str]):
    tmp = FETCHED_LOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, sort_keys=True))
    tmp.replace(FETCHED_LOG)


def _sym_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol.upper().replace('/', '_')}.json"


def _load_symbol(symbol: str) -> Dict[str, object]:
    p = _sym_path(symbol)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"symbol": symbol.upper(), "rows": []}


def _save_symbol(symbol: str, obj: Dict[str, object]):
    p = _sym_path(symbol)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj))
    tmp.replace(p)


def _fetch_day_raw(ymd: str, timeout: int = 30) -> Optional[str]:
    url = _BASE.format(ymd=ymd)
    backoff = 2.0
    for _attempt in range(5):
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None  # non-trading day OR off-archive (caller decides)
            if e.code == 429 or 500 <= e.code < 600:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise FinraFetchError(f"HTTP {e.code} for {ymd}")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(backoff)
            backoff *= 2
            continue
    raise FinraFetchError(f"exhausted retries for {ymd}")


def _parse_day(body: str, wanted: set) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for line in body.splitlines():
        if not line or line.startswith("Date|"):
            continue
        parts = line.split("|")
        if len(parts) < 5:
            continue
        sym = parts[1].strip().upper()
        if sym not in wanted:
            continue
        try:
            date = parts[0].strip()
            short = float(parts[2])
            total = float(parts[4])
        except (ValueError, IndexError):
            continue
        if total <= 0:
            continue
        out[sym] = {
            "date": f"{date[0:4]}-{date[4:6]}-{date[6:8]}",
            "short": short,
            "total": total,
            "svr": short / total,
        }
    return out


def _daterange(start: _dt.date, end: _dt.date) -> Iterable[_dt.date]:
    d = start
    one = _dt.timedelta(days=1)
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += one


def build_cache(symbols: Optional[List[str]] = None,
                start: Optional[_dt.date] = None,
                end: Optional[_dt.date] = None,
                sleep_s: float = 0.12,
                verbose: bool = True,
                checkpoint_every: int = 100,
                max_consec_nofile: int = 40) -> Dict[str, int]:
    _ensure_dir()
    symbols = [s.upper() for s in (symbols or DEFAULT_SYMBOLS)]
    wanted = set(symbols)
    start = start or ARCHIVE_START
    end = end or _dt.date.today()

    fetched = _load_fetched()
    series: Dict[str, Dict[str, dict]] = {}
    for s in symbols:
        obj = _load_symbol(s)
        series[s] = {r["date"]: r for r in obj.get("rows", [])}

    n_new_days = 0
    n_nofile = 0
    n_with_data = 0
    consec_nofile = 0
    days = [d for d in _daterange(start, end)]
    for i, d in enumerate(days):
        ymd = d.strftime("%Y%m%d")
        if ymd in fetched:
            continue
        try:
            body = _fetch_day_raw(ymd)
        except FinraFetchError as e:
            if verbose:
                print(f"[finra] transient STOP at {ymd}: {e}")
            break
        if body is None:
            fetched[ymd] = "nofile"
            n_nofile += 1
            consec_nofile += 1
            if consec_nofile >= max_consec_nofile:
                if verbose:
                    print(f"[finra] {consec_nofile} consecutive no-file days ending "
                          f"{ymd}; assuming off-archive, stopping.")
                break
        else:
            parsed = _parse_day(body, wanted)
            for sym, rec in parsed.items():
                series[sym][rec["date"]] = {
                    "date": rec["date"], "short": rec["short"],
                    "total": rec["total"], "svr": rec["svr"],
                }
            fetched[ymd] = "ok"
            n_new_days += 1
            consec_nofile = 0
            if parsed:
                n_with_data += 1
        if sleep_s:
            time.sleep(sleep_s)
        if (i + 1) % checkpoint_every == 0:
            for s in symbols:
                rows = sorted(series[s].values(), key=lambda r: r["date"])
                _save_symbol(s, {"symbol": s, "rows": rows})
            _save_fetched(fetched)
            if verbose:
                print(f"[finra] {i+1}/{len(days)} days scanned "
                      f"({n_new_days} new, {n_nofile} no-file); checkpoint saved")

    for s in symbols:
        rows = sorted(series[s].values(), key=lambda r: r["date"])
        _save_symbol(s, {"symbol": s, "rows": rows})
    _save_fetched(fetched)
    if verbose:
        print(f"[finra] DONE. new_days={n_new_days} no_file={n_nofile} "
              f"days_with_wanted_data={n_with_data}")
    return {"new_days": n_new_days, "no_file": n_nofile, "with_data": n_with_data}


def load_svr(symbol: str) -> List[dict]:
    obj = _load_symbol(symbol)
    return sorted(obj.get("rows", []), key=lambda r: r["date"])


def span(symbol: str) -> Dict[str, object]:
    rows = load_svr(symbol)
    if not rows:
        return {"symbol": symbol.upper(), "n": 0}
    return {"symbol": symbol.upper(), "n": len(rows),
            "first": rows[0]["date"], "last": rows[-1]["date"]}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "span":
        for s in DEFAULT_SYMBOLS:
            print(span(s))
    else:
        build_cache()
