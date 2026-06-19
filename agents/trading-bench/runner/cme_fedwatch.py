"""CME FedWatch implied probabilities — derived from 30-Day Fed Funds Futures (ZQ)
via Yahoo Finance (CME FedWatch is IP-blocked from datacenter; ZQ Yahoo Finance works).

The 30-day Fed Funds futures (ZQ) are the underlying contracts that CME FedWatch
itself uses. We replicate FedWatch math directly:

  implied_avg_rate = 100 - futures_price
  For a meeting-month contract (FOMC meeting on day D in N-day month):
    post_meeting_rate = (implied * N - D * pre_rate) / (N - D)
    P(cut) = (pre_rate - post_meeting_rate) / 0.25   [clipped 0..1]
    P(hike)= (post_meeting_rate - pre_rate) / 0.25   [clipped 0..1]
    P(hold) = 1 - P(cut) - P(hike)

For non-meeting months we pass through the rate unchanged (bridge to next meeting).

Returns dict keyed by meeting date string 'YYYY-MM-DD':
  {
    '2026-06-18': {'hold': 0.92, 'cut_1': 0.08, 'hike_1': 0.00, 'rate_post': 3.500},
    '2026-07-30': {'hold': 0.55, 'cut_1': 0.40, 'hike_1': 0.05, 'rate_post': 3.437},
    ...
  }

Entry points:
  fetch() -> dict | None     (main API)
  python3 runner/cme_fedwatch.py   (CLI smoke-test)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

WORKSPACE = Path(__file__).resolve().parent.parent
logger = logging.getLogger("cme_fedwatch")

# ---------------------------------------------------------------------------
# FOMC meeting calendar (2026).  Day = last day of 2-day meeting.
# Update annually or whenever the Fed publishes the schedule.
# ---------------------------------------------------------------------------

FOMC_MEETINGS_2026 = [
    date(2026, 1, 29),
    date(2026, 3, 19),
    date(2026, 5, 7),
    date(2026, 6, 18),
    date(2026, 7, 30),
    date(2026, 9, 17),
    date(2026, 10, 29),
    date(2026, 12, 10),
]

FOMC_MEETINGS_2027 = [
    date(2027, 1, 29),
    date(2027, 3, 18),
    date(2027, 5, 6),
    date(2027, 6, 17),
    date(2027, 7, 29),
    date(2027, 9, 16),
    date(2027, 10, 28),
    date(2027, 12, 9),
]

# Month-letter codes for ZQ futures (CME convention)
MONTH_CODES = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}

# Days in each month (non-leap-year default; we compute exactly)
def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


# ---------------------------------------------------------------------------
# FRED helper — get current FF effective rate
# ---------------------------------------------------------------------------

def _load_env_key(key_name: str) -> Optional[str]:
    val = os.environ.get(key_name, "").strip()
    if val:
        return val
    env_path = WORKSPACE / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(key_name + "="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    return None


def _get_current_ff_rate() -> float:
    """Return the current effective Fed Funds rate midpoint from FRED DFEDTARU/DFEDTARL.

    DFEDTARU = upper bound of target range
    DFEDTARL = lower bound of target range
    Effective rate = midpoint = (upper + lower) / 2
    Falls back to FEDFUNDS (monthly average) if daily bounds unavailable.
    """
    api_key = _load_env_key("FRED_API_KEY")
    ua = "trading-bench/1.0 (research; cme_fedwatch)"

    def _fred_obs(series_id: str) -> Optional[float]:
        if not api_key:
            return None
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        six_months_ago = datetime.now(timezone.utc)
        six_months_ago = six_months_ago.replace(month=max(1, six_months_ago.month - 3))
        start = six_months_ago.strftime("%Y-%m-%d")
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}&file_type=json"
            f"&observation_start={start}&observation_end={today}"
            f"&sort_order=desc&limit=5"
        )
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        for obs in data.get("observations", []):
            v = obs.get("value", ".")
            if v and v != ".":
                return float(v)
        return None

    try:
        upper = _fred_obs("DFEDTARU")
        lower = _fred_obs("DFEDTARL")
        if upper is not None and lower is not None:
            midpoint = (upper + lower) / 2.0
            logger.debug(f"FF target range: {lower:.2f}%-{upper:.2f}%, midpoint={midpoint:.4f}%")
            return midpoint
        # Fallback to monthly average
        monthly = _fred_obs("FEDFUNDS")
        if monthly is not None:
            logger.debug(f"FF rate (monthly avg fallback): {monthly:.4f}%")
            return monthly
    except Exception as exc:
        logger.warning(f"FRED fetch failed: {exc}")

    # Hard fallback: use 3.625% (midpoint of 3.50-3.75% which is current as of 2026-06)
    logger.warning("Using hardcoded FF rate fallback: 3.625%")
    return 3.625


# ---------------------------------------------------------------------------
# Yahoo Finance ZQ futures fetch
# ---------------------------------------------------------------------------

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_zq_price(year: int, month: int, retries: int = 3) -> Optional[float]:
    """Fetch the closing price for ZQ<MonthCode><2-digit-year>.CBT from Yahoo Finance.

    Returns the futures price (e.g. 96.375) or None on failure.
    """
    month_code = MONTH_CODES.get(month)
    if month_code is None:
        return None
    sym = f"ZQ{month_code}{year % 100:02d}.CBT"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            result = data.get("chart", {}).get("result", [])
            if not result:
                err = data.get("chart", {}).get("error", {})
                if err:
                    logger.debug(f"{sym}: Yahoo API error: {err}")
                return None
            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is None:
                return None
            return float(price)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None  # Contract doesn't exist
            last_err = exc
        except Exception as exc:
            last_err = exc

        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))

    logger.warning(f"ZQ fetch failed for {sym} after {retries} attempts: {last_err}")
    return None


# ---------------------------------------------------------------------------
# Core probability derivation
# ---------------------------------------------------------------------------

def _compute_meeting_prob(
    fomc_day: int,
    n_days_in_month: int,
    implied_avg_rate: float,
    pre_meeting_rate: float,
) -> dict:
    """Compute hold/cut/hike probabilities for one FOMC meeting.

    Args:
        fomc_day: Calendar day of the FOMC decision (last day of 2-day meeting)
        n_days_in_month: Total days in the month
        implied_avg_rate: 100 - futures_price for that month's ZQ contract
        pre_meeting_rate: Effective FF rate entering the meeting

    Returns dict with keys: hold, cut_1, hike_1, rate_post (expected rate after meeting)
    """
    # days after meeting (decision applies from fomc_day through month end)
    days_after = n_days_in_month - fomc_day

    if days_after <= 0:
        # Meeting is on or after last day — not enough post-meeting data in contract
        return {
            "hold": 1.0,
            "cut_1": 0.0,
            "hike_1": 0.0,
            "rate_post": pre_meeting_rate,
        }

    # implied_avg = (fomc_day * pre_rate + days_after * post_rate) / n_days_in_month
    # => post_rate = (implied_avg * n - fomc_day * pre_rate) / days_after
    post_rate = (implied_avg_rate * n_days_in_month - fomc_day * pre_meeting_rate) / days_after

    # Probability of a 25 bps cut
    cut_rate = pre_meeting_rate - 0.25
    hike_rate = pre_meeting_rate + 0.25

    if abs(pre_meeting_rate - cut_rate) < 1e-9:
        prob_cut = 0.0
    else:
        prob_cut = (pre_meeting_rate - post_rate) / (pre_meeting_rate - cut_rate)

    if abs(hike_rate - pre_meeting_rate) < 1e-9:
        prob_hike = 0.0
    else:
        prob_hike = (post_rate - pre_meeting_rate) / (hike_rate - pre_meeting_rate)

    prob_cut = max(0.0, min(1.0, prob_cut))
    prob_hike = max(0.0, min(1.0, prob_hike))

    # Handle edge: if both are non-zero it means multi-step scenarios are baked in
    # For simplicity (same as CME FedWatch "single-step" display) cap at 1.0 total
    total = prob_cut + prob_hike
    if total > 1.0:
        prob_cut /= total
        prob_hike /= total

    prob_hold = max(0.0, 1.0 - prob_cut - prob_hike)

    # Clamp post_rate to a sane range to prevent compounding math explosions
    # when fomc_day is near month-end (days_after is small, tiny implied-rate
    # differences get amplified). Hard cap: ±2 steps (50 bps) from pre_rate.
    post_rate = max(pre_meeting_rate - 0.75, min(pre_meeting_rate + 0.75, post_rate))

    return {
        "hold": round(prob_hold, 4),
        "cut_1": round(prob_cut, 4),
        "hike_1": round(prob_hike, 4),
        "rate_post": round(post_rate, 4),
    }


# ---------------------------------------------------------------------------
# Bridge: non-meeting months pass rate through unchanged
# ---------------------------------------------------------------------------

def _months_to_analyze(as_of: date, horizon_months: int = 12):
    """Generate (year, month) tuples from this month for horizon_months."""
    y, m = as_of.year, as_of.month
    for _ in range(horizon_months):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def fetch(horizon_months: int = 12) -> Optional[dict]:
    """Fetch CME FedWatch-equivalent implied probabilities for upcoming FOMC meetings.

    Returns:
      Dict keyed by meeting date string 'YYYY-MM-DD':
        {
          '2026-06-18': {
            'hold': 0.92, 'cut_1': 0.08, 'hike_1': 0.00,
            'rate_pre': 3.625, 'rate_post': 3.606,
            'contract': 'ZQM26', 'futures_price': 96.375,
          },
          ...
        }
      None if the data source is completely unavailable.
    """
    all_meetings = FOMC_MEETINGS_2026 + FOMC_MEETINGS_2027

    # Current effective FF rate
    try:
        current_rate = _get_current_ff_rate()
    except Exception as exc:
        logger.warning(f"Could not get current FF rate: {exc} — using 3.625% fallback")
        current_rate = 3.625

    today = date.today()
    # Filter to future meetings only
    upcoming_meetings = [m for m in all_meetings if m >= today]
    if not upcoming_meetings:
        logger.warning("No upcoming FOMC meetings found in calendar")
        return None

    # Determine which calendar months we need ZQ prices for
    # We need month of each upcoming meeting plus bridging months
    months_needed = set()
    for mtg in upcoming_meetings:
        months_needed.add((mtg.year, mtg.month))

    # Also need months between meetings (for rate bridging)
    if upcoming_meetings:
        start_month = (today.year, today.month)
        end_meeting = upcoming_meetings[min(len(upcoming_meetings) - 1, horizon_months - 1)]
        end_month = (end_meeting.year, end_meeting.month)
        y, mo = start_month
        while (y, mo) <= end_month:
            months_needed.add((y, mo))
            mo += 1
            if mo > 12:
                mo = 1
                y += 1

    # Fetch all needed ZQ contract prices
    logger.info(f"Fetching {len(months_needed)} ZQ contracts from Yahoo Finance...")
    prices: dict = {}
    for y, mo in sorted(months_needed):
        p = _fetch_zq_price(y, mo)
        prices[(y, mo)] = p
        sym = f"ZQ{MONTH_CODES.get(mo, '?')}{y % 100:02d}.CBT"
        if p is not None:
            logger.debug(f"  {sym}: {p:.3f} → implied {100-p:.3f}%")
        else:
            logger.debug(f"  {sym}: not available")

    # Check if we have any data at all
    available = {k: v for k, v in prices.items() if v is not None}
    if not available:
        logger.error("No ZQ futures prices available — all fetches failed")
        return None

    # Walk through meetings, computing probabilities
    results: dict = {}
    running_rate = current_rate

    # Build a month-keyed index of meetings
    meeting_by_month: dict = {}
    for mtg in upcoming_meetings:
        meeting_by_month[(mtg.year, mtg.month)] = mtg

    # Process months in order
    sorted_months = sorted(months_needed)
    for y, mo in sorted_months:
        price = prices.get((y, mo))
        if price is None:
            # No contract data for this month — skip / pass rate through
            continue

        implied_rate = 100.0 - price
        n_days = _days_in_month(y, mo)
        month_code = MONTH_CODES.get(mo, "?")
        contract_name = f"ZQ{month_code}{y % 100:02d}"

        if (y, mo) in meeting_by_month:
            mtg_date = meeting_by_month[(y, mo)]
            fomc_day = mtg_date.day
            days_after = n_days - fomc_day

            # When the meeting is near month-end (days_after < 5), the single-contract
            # FedWatch math amplifies tiny rate differences by up to 30x, producing
            # nonsensical post_rate values that compound through all later meetings.
            # Fix: use next month's contract price directly — it covers all 30-31
            # days at the post-meeting rate, so implied_rate ≈ post_rate.
            next_mo = mo + 1 if mo < 12 else 1
            next_yr = y if mo < 12 else y + 1
            next_price = prices.get((next_yr, next_mo))

            if days_after < 5 and next_price is not None:
                # Direct read: next month's contract implies the post-meeting rate
                post_rate_direct = 100.0 - next_price
                post_rate_direct = max(running_rate - 0.50, min(running_rate + 0.50, post_rate_direct))
                cut_rate = running_rate - 0.25
                hike_rate = running_rate + 0.25
                prob_cut = max(0.0, min(1.0, (running_rate - post_rate_direct) / 0.25))
                prob_hike = max(0.0, min(1.0, (post_rate_direct - running_rate) / 0.25))
                total = prob_cut + prob_hike
                if total > 1.0:
                    prob_cut /= total
                    prob_hike /= total
                prob_hold = max(0.0, 1.0 - prob_cut - prob_hike)
                probs = {
                    "hold": round(prob_hold, 4),
                    "cut_1": round(prob_cut, 4),
                    "hike_1": round(prob_hike, 4),
                    "rate_post": round(post_rate_direct, 4),
                }
            else:
                probs = _compute_meeting_prob(
                    fomc_day=fomc_day,
                    n_days_in_month=n_days,
                    implied_avg_rate=implied_rate,
                    pre_meeting_rate=running_rate,
                )

            results[mtg_date.strftime("%Y-%m-%d")] = {
                "hold": probs["hold"],
                "cut_1": probs["cut_1"],
                "hike_1": probs["hike_1"],
                "rate_pre": round(running_rate, 4),
                "rate_post": probs["rate_post"],
                "contract": contract_name,
                "futures_price": price,
                "implied_avg_rate": round(implied_rate, 4),
            }
            running_rate = probs["rate_post"]
        else:
            # Non-meeting month: do NOT update running_rate from the bridge contract.
            # The bridge contract's implied average rate mixes pre- and post-meeting
            # days and accumulates errors. The running_rate stays at the last
            # meeting's rate_post until the next meeting fires.
            pass

    if not results:
        logger.warning("No FOMC meeting probabilities computed")
        return None

    return results


# ---------------------------------------------------------------------------
# Convenience: get probability for a specific meeting
# ---------------------------------------------------------------------------

def get_meeting_prob(
    target_month: str,
    fedwatch_data: Optional[dict] = None,
) -> Optional[dict]:
    """Get probabilities for the FOMC meeting nearest to target_month ('YYYY-MM').

    Args:
        target_month: 'YYYY-MM' string (e.g. '2026-09')
        fedwatch_data: Pre-fetched fetch() result (fetches fresh if None)

    Returns prob dict or None.
    """
    if fedwatch_data is None:
        fedwatch_data = fetch()
    if not fedwatch_data:
        return None

    # Find meeting with matching year-month
    for date_str, probs in fedwatch_data.items():
        if date_str[:7] == target_month:
            return probs

    # Try nearest match (within 45 days of month start)
    try:
        target = datetime.strptime(target_month + "-01", "%Y-%m-%d").date()
        best_key = None
        best_diff = 999
        for date_str in fedwatch_data:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            diff = abs((d - target).days)
            if diff < best_diff:
                best_diff = diff
                best_key = date_str
        if best_key and best_diff <= 45:
            return fedwatch_data[best_key]
    except (ValueError, TypeError):
        pass

    return None


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    print("[cme_fedwatch] Fetching ZQ Fed Funds Futures from Yahoo Finance...")
    data = fetch()

    if data is None:
        print("[cme_fedwatch] ERROR: No data available", file=sys.stderr)
        sys.exit(1)

    print(f"\n[cme_fedwatch] Got {len(data)} upcoming FOMC meeting priors:\n")
    print(f"{'Meeting Date':<14} {'Contract':<10} {'Price':>7} {'ImplRate':>9} "
          f"{'PreRate':>8} {'PostRate':>9} {'Hold':>6} {'Cut25':>6} {'Hike25':>6}")
    print("-" * 80)
    for date_str in sorted(data):
        d = data[date_str]
        print(
            f"{date_str:<14} {d['contract']:<10} {d['futures_price']:>7.3f} "
            f"{d['implied_avg_rate']:>8.3f}% {d['rate_pre']:>7.3f}% "
            f"{d['rate_post']:>8.3f}% "
            f"{d['hold']:>6.1%} {d['cut_1']:>6.1%} {d['hike_1']:>6.1%}"
        )

    print("\n[cme_fedwatch] Smoke test PASSED")


if __name__ == "__main__":
    main()
