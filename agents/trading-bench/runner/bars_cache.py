"""Disk cache for historical crypto bars.

Backtester-only. Live runner does NOT use this — live needs fresh bars every tick.

Cache key: (symbol, timeframe, start, end) → JSON file under
`.cache/bars/{safe_symbol}_{timeframe}_{start}_{end}.json`.

If the cache file exists and is non-empty, return its contents. Otherwise
fetch from Alpaca's data API and write it back. Same format as
`AlpacaClient.crypto_bars(...)`: list of {t,o,h,l,c,v}, oldest first.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from .broker_alpaca import AlpacaClient, AlpacaError

WORKSPACE = Path(__file__).resolve().parent.parent
CACHE_DIR = WORKSPACE / ".cache" / "bars"

# Reuse Alpaca's tf → minutes mapping
TF_MINUTES = {
    "1Min": 1, "5Min": 5, "15Min": 15, "30Min": 30,
    "1Hour": 60, "2Hour": 120, "4Hour": 240,
    "6Hour": 360, "12Hour": 720, "1Day": 1440,
}


def _safe(sym: str) -> str:
    return sym.replace("/", "-").upper()


def _cache_path(symbol: str, timeframe: str, start: str, end: str) -> Path:
    fname = f"{_safe(symbol)}_{timeframe}_{start}_{end}.json"
    return CACHE_DIR / fname


def _iso_date(d: datetime) -> str:
    """Cache-key serialization for a `datetime`.

    For midnight-UTC timestamps (the common case from `get_bars(end_dt=None)`,
    which snaps to the UTC day boundary) we emit YYYY-MM-DD so cache filenames
    stay short and human-readable. For any non-midnight timestamp we emit a
    full RFC3339-ish stamp `YYYY-MM-DDTHHMMSSZ` so two intraday fetches on the
    same calendar day (e.g. 14:30 vs 15:30) get distinct cache files instead
    of silently colliding. The `:` is replaced because some filesystems
    disallow it in filenames.
    """
    is_midnight = (d.hour == 0 and d.minute == 0 and d.second == 0
                   and d.microsecond == 0)
    if is_midnight:
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%dT%H%M%SZ")


def _is_crypto(symbol: str) -> bool:
    return "/" in symbol


def _fetch_range(client: AlpacaClient, symbol: str, timeframe: str,
                 start_dt: datetime, end_dt: datetime) -> List[dict]:
    """Fetch ALL bars in [start_dt, end_dt] across pagination.

    Routes to crypto (v1beta3) or stocks (v2 with feed=iex) based on symbol form.
    """
    sym = symbol.upper()
    out: List[dict] = []
    page_token: Optional[str] = None
    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    crypto = _is_crypto(symbol)
    # ascending so pagination "next" continues forward
    while True:
        if crypto:
            url = (f"{client.cfg.data_base}/v1beta3/crypto/us/bars"
                   f"?symbols={quote(sym)}&timeframe={timeframe}&limit=10000"
                   f"&start={start_iso}&end={end_iso}&sort=asc")
        else:
            url = (f"{client.cfg.data_base}/v2/stocks/{quote(sym)}/bars"
                   f"?timeframe={timeframe}&limit=10000&feed=iex"
                   f"&start={start_iso}&end={end_iso}&sort=asc&adjustment=raw")
        if page_token:
            url += f"&page_token={quote(page_token)}"
        payload = client._request("GET", url)
        if crypto:
            bars_by_sym = payload.get("bars", {})
            rows = bars_by_sym.get(sym) or next(iter(bars_by_sym.values()), [])
        else:
            rows = payload.get("bars") or []
        if rows:
            out.extend(rows)
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    # Defensive: dedupe by 't', preserve order
    seen = set()
    deduped = []
    for b in out:
        t = b.get("t")
        if t in seen:
            continue
        seen.add(t)
        deduped.append(b)
    return deduped


def get_bars(symbol: str, timeframe: str, days: int,
             client: Optional[AlpacaClient] = None,
             end_dt: Optional[datetime] = None) -> List[dict]:
    """Return historical bars for the last `days` days, oldest-first.

    Cached to disk. Pass the same (symbol, timeframe, days, end_dt) for a free rerun.
    """
    if timeframe not in TF_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}")
    if end_dt is None:
        # Snap to UTC day boundary for cache stability across reruns within a day.
        now = datetime.now(timezone.utc)
        end_dt = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    start = _iso_date(start_dt)
    end = _iso_date(end_dt)
    path = _cache_path(symbol, timeframe, start, end)
    if path.exists() and path.stat().st_size > 2:
        try:
            data = json.loads(path.read_text())
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass  # fall through to refetch
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    client = client or AlpacaClient()
    bars = _fetch_range(client, symbol, timeframe, start_dt, end_dt)
    try:
        path.write_text(json.dumps(bars))
    except Exception:
        pass  # cache best-effort
    return bars
