"""Free point-in-time S&P 500 membership spine (Wikipedia change-log).

RESEARCH/BACKTEST-ONLY. Parallel to the other free ingest modules
(`cboe_cache.py`, `fred_cache.py`, `cot_cache.py`). This builds the *membership*
half of a survivorship-clean US-equity universe at $0 — the piece the
2026-06-23 survivorship-universe scout flagged as the only free-doable part.

    WHAT THIS DOES (and, crucially, what it DOES NOT)
    -------------------------------------------------
    DOES: reconstruct, point-in-time, the set of tickers that were S&P 500
          members on any past date D, by replaying Wikipedia's dated
          add/remove change-log backward from today's constituent snapshot.
          Verified live: 503 current names + 681 dated change rows (1994->now).

    DOES NOT: provide PRICES for delisted names. A stock that left the index and
          later went to zero needs its delisting-adjusted price series to be
          tradeable in a survivorship-clean backtest, and NO FREE SOURCE serves
          those (Yahoo purges delisted tickers). Per the scout, the cheapest
          honest fix is one paid EOD feed (EODHD ~$19.99/mo, delisted EOD +
          adjusted close). Until that feed exists, this membership table is
          NECESSARY BUT NOT SUFFICIENT for a survivorship-clean momentum/low-vol
          backtest: it tells you WHO was in the index on date D, but you still
          can't price the ones that subsequently died.

    THEREFORE: this module is deliberately the *spine only*. It is wired and
          tested so the moment a delisted-price feed is approved, the universe
          builder is a thin join away. Running a cross-sectional anomaly on this
          membership + Yahoo prices ALONE would silently reintroduce
          survivorship bias (the dead names just vanish) — do not do that; that
          is the exact mirage that closed BAB / xsec-momentum / PIT-value / PEAD
          on 2026-06-23.

POINT-IN-TIME CONVENTION
    A change dated D takes effect at the OPEN of D. So:
      - members_asof(D)   reflects the post-change membership for every change
                          with date <= D.
      - members_asof(D-1) reverses any change dated D.
    Reconstruction walks BACKWARD from the current snapshot: to step from the
    state at/after change c (date d_c) to the state strictly before d_c, we
    UNDO c — i.e. remove what c added and re-add what c removed.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.request
from typing import Dict, Iterable, List, Optional, Set

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_UA = {"User-Agent": "Mozilla/5.0 (research; sp500-pit-membership)"}

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _parse_change_date(s: str) -> Optional[dt.date]:
    """Parse 'January 10, 2024' OR '2024-01-10' -> date. None on failure."""
    if not s:
        return None
    s = s.strip()
    # ISO first
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    # Long form "Month D, YYYY"
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$", s)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon is None:
            return None
        try:
            return dt.date(int(m.group(3)), mon, int(m.group(2)))
        except ValueError:
            return None
    return None


def build_membership_table(current: Iterable[str],
                           changes: List[dict]) -> Dict[str, object]:
    """Pure transform: package a current snapshot + normalized change-log.

    current: iterable of ticker strings in the index TODAY.
    changes: list of {"date": <str|date>, "added": <ticker str>,
                      "removed": <ticker str>}; empty add/removed allowed.

    Returns a dict {"current": set, "changes": [ {date: date, added, removed} ]}
    sorted ascending by date. No network. Rows with unparseable dates dropped.
    """
    norm: List[dict] = []
    for row in changes:
        d = row.get("date")
        if isinstance(d, str):
            d = _parse_change_date(d)
        if not isinstance(d, dt.date):
            continue
        norm.append({
            "date": d,
            "added": (row.get("added") or "").strip().upper(),
            "removed": (row.get("removed") or "").strip().upper(),
        })
    norm.sort(key=lambda r: r["date"])
    return {"current": set(t.strip().upper() for t in current), "changes": norm}


def members_asof(table: Dict[str, object], as_of: dt.date) -> Set[str]:
    """Return the membership set on date `as_of` (point-in-time).

    Walks backward from the current snapshot, undoing every change whose date
    is STRICTLY AFTER as_of (those changes had not happened yet on as_of).
    """
    if not isinstance(as_of, dt.date):
        raise TypeError("as_of must be a datetime.date")
    members: Set[str] = set(table["current"])  # type: ignore[arg-type]
    changes: List[dict] = table["changes"]  # type: ignore[assignment]
    # Undo changes dated after as_of, most-recent first.
    for row in sorted(changes, key=lambda r: r["date"], reverse=True):
        if row["date"] <= as_of:
            break  # remaining changes are all <= as_of (already reflected)
        # UNDO: remove what it added, restore what it removed.
        if row["added"]:
            members.discard(row["added"])
        if row["removed"]:
            members.add(row["removed"])
    return members


# --- live ingest (network) ----------------------------------------------------

def _fetch_wiki_html(timeout: int = 30) -> str:
    req = urllib.request.Request(WIKI_URL, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _scrape_current_and_changes(html: str):
    """Best-effort scrape of the live page into (current_set, changes_list).

    NOTE: Wikipedia markup shifts over time; this is intentionally defensive and
    is exercised by a LIVE smoke, not the unit suite (which uses synthetic data).
    Returns (set_of_current_tickers, list_of_change_rows).
    """
    # Current constituents: first wikitable's symbol column. Tickers are linked
    # to their stock pages; grab uppercase 1-5 char symbols.
    current = set(re.findall(r'<td><a[^>]*>([A-Z]{1,5}(?:\.[A-Z])?)</a>', html))
    # Changes table rows carry a date cell + added/removed ticker cells.
    changes: List[dict] = []
    # Split on table rows and look for a parseable date + up to two tickers.
    for tr in re.findall(r"<tr>(.*?)</tr>", html, flags=re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)
        if not cells:
            continue
        # find a date in the first couple cells
        d = None
        for c in cells[:2]:
            txt = re.sub(r"<[^>]+>", "", c).strip()
            d = _parse_change_date(txt)
            if d:
                break
        if not d:
            continue
        tickers = re.findall(r'>([A-Z]{1,5}(?:\.[A-Z])?)<', tr)
        added = tickers[0] if len(tickers) >= 1 else ""
        removed = tickers[1] if len(tickers) >= 2 else ""
        changes.append({"date": d, "added": added, "removed": removed})
    return current, changes


def load_live_membership_table():
    """Fetch Wikipedia and build the PIT table. Network required."""
    html = _fetch_wiki_html()
    current, changes = _scrape_current_and_changes(html)
    return build_membership_table(current, changes)
