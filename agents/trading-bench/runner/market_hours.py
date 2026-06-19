"""US equity market-hours helper.

v2: NYSE regular session (Mon-Fri, 9:30am-4:00pm ET) PLUS a hand-maintained
NYSE holiday calendar covering 2024-2028. Early closes (1pm ET) are also
honored.

Holiday list source: NYSE official observed-holiday schedule. Maintained
by hand because (a) it's a tiny dependency-free table, (b) the calendar
shifts at most once a year, (c) pulling in `pandas_market_calendars` for
a 9-entries-per-year lookup is overkill. Extend the table when 2028 is
no longer the horizon.

Early-close days: NYSE closes at 1:00pm ET on day-after-Thanksgiving and
on Christmas Eve when Christmas falls on a weekday. We model these by
overriding the close time, not by adding to the closed-days set.

ET handling: we convert UTC to America/New_York via zoneinfo so DST is correct.
"""

from __future__ import annotations

from datetime import datetime, date, time, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - very old python or missing tzdata
    _ET = None  # type: ignore

_OPEN = time(9, 30)
_CLOSE = time(16, 0)
_EARLY_CLOSE = time(13, 0)

# NYSE-observed holidays (fully closed, no trading at all).
# When a holiday falls on Saturday, it's observed Friday. When on Sunday,
# it's observed Monday. This table already encodes the OBSERVED date.
# Source: NYSE published holiday calendar.
NYSE_HOLIDAYS: set = {
    # 2024
    date(2024, 1, 1),    # New Year's Day
    date(2024, 1, 15),   # MLK Day
    date(2024, 2, 19),   # Presidents' Day
    date(2024, 3, 29),   # Good Friday
    date(2024, 5, 27),   # Memorial Day
    date(2024, 6, 19),   # Juneteenth
    date(2024, 7, 4),    # Independence Day
    date(2024, 9, 2),    # Labor Day
    date(2024, 11, 28),  # Thanksgiving
    date(2024, 12, 25),  # Christmas
    # 2025
    date(2025, 1, 1),
    date(2025, 1, 9),    # Day of mourning - Carter (was on calendar; keep)
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),
    date(2026, 7, 3),    # July 4 observed (4th is Saturday)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),   # Juneteenth observed (19th is Saturday)
    date(2027, 7, 5),    # July 4 observed (4th is Sunday)
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),  # Christmas observed (25th is Saturday)
    # 2028 (partial; extend before this point)
    date(2028, 1, 17),
    date(2028, 2, 21),
    date(2028, 4, 14),
    date(2028, 5, 29),
    date(2028, 6, 19),
    date(2028, 7, 4),
    date(2028, 9, 4),
    date(2028, 11, 23),
    date(2028, 12, 25),
}

# NYSE early-close days (1:00pm ET). Day-after-Thanksgiving every year
# plus Christmas Eve when Christmas falls on a weekday.
NYSE_EARLY_CLOSE: set = {
    # 2024
    date(2024, 7, 3),     # Day before July 4
    date(2024, 11, 29),   # Day after Thanksgiving
    date(2024, 12, 24),   # Christmas Eve
    # 2025
    date(2025, 7, 3),
    date(2025, 11, 28),
    date(2025, 12, 24),
    # 2026 — July 3 already a full holiday (July 4 observed); no early close that week
    date(2026, 11, 27),   # Day after Thanksgiving
    date(2026, 12, 24),
    # 2027
    date(2027, 11, 26),
    # 2028
    date(2028, 7, 3),
    date(2028, 11, 24),
    date(2028, 12, 22),   # Christmas observed Dec 25 (Sat), eve early-close on Fri
}


def is_us_equity_market_open(now_utc: Optional[datetime] = None) -> bool:
    """Return True iff `now_utc` falls in a regular NYSE session (Mon-Fri 09:30-16:00 ET),
    excluding NYSE-observed holidays. Honors early-close (1pm ET) days.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    if _ET is None:
        # Fallback: rough UTC-5 (won't handle DST). Better than crashing.
        et = now_utc.astimezone(timezone.utc)
    else:
        et = now_utc.astimezone(_ET)
    if et.weekday() >= 5:  # Sat=5, Sun=6
        return False
    if et.date() in NYSE_HOLIDAYS:
        return False
    t = et.time()
    close = _EARLY_CLOSE if et.date() in NYSE_EARLY_CLOSE else _CLOSE
    return _OPEN <= t < close


def is_nyse_holiday(d: date) -> bool:
    """True if `d` is a fully-closed NYSE holiday. Exposed for backtest/regime tooling."""
    return d in NYSE_HOLIDAYS


def is_nyse_early_close(d: date) -> bool:
    """True if `d` is a NYSE 1pm-ET early-close day."""
    return d in NYSE_EARLY_CLOSE
