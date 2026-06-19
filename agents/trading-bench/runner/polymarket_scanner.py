"""Polymarket Scanner — pull active macro/finance markets from Polymarket's public API,
score implied probability vs quantitative priors, and flag markets with >5%–10% discrepancy.

Entry points:
  - scan() → List[ScanResult]   (importable)
  - python3 runner/polymarket_scanner.py   (CLI: prints table, writes report)

APIs used (no auth required):
  - Gamma API: https://gamma-api.polymarket.com  — market metadata, volume
  - FRED keyed API: via runner.fred_cache — NFCI for macro stress priors

Prior estimation:
  3a. Fed rate markets  → flag with "check CME FedWatch manually" (no live CME feed)
  3b. Macro stress      → FRED NFCI-based prior (NFCI bucket → recession probability)
  3c. Everything else   → our_prior=None, not flagged on discrepancy
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# CME FedWatch (derived from ZQ futures via Yahoo Finance)
try:
    if str(Path(__file__).resolve().parent.parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from runner.cme_fedwatch import fetch as _cme_fetch, get_meeting_prob as _cme_get_meeting_prob  # type: ignore
    _CME_AVAILABLE = True
except ImportError:
    _CME_AVAILABLE = False
    _cme_fetch = None  # type: ignore
    _cme_get_meeting_prob = None  # type: ignore

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parent.parent
REPORTS_DIR = WORKSPACE / "reports"

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Thresholds
MIN_VOLUME_USD = 100_000        # Skip thin markets
MIN_DAYS_TO_CLOSE = 14          # Skip short-horizon noise
DISCREPANCY_THRESHOLD = 0.05    # 5pp → flagged
MACRO_DISCREPANCY_THRESHOLD = 0.10  # 10pp for NFCI-based macro priors

# Categories to INCLUDE (keyword match from event title + question + tags)
# The Gamma API doesn't expose a clean category field on markets; we rely on
# keyword matching for macro/finance and tag-based exclusion for sports/crypto.
EXCLUDE_TAG_SLUGS = {
    "sports", "soccer", "basketball", "football", "baseball", "tennis",
    "golf", "mma", "ufc", "boxing", "esports", "crypto", "entertainment",
    "music", "celebrity", "tv", "movies", "gaming",
}

# Fee rates by feeType (from Polymarket docs)
FEE_RATES = {
    "geopolitics_fees": 0.0,
    "general_fees": 0.0,
    "politics_fees": 0.04,
    "economics_fees": 0.04,
    "finance_fees": 0.04,
    "sports_fees": 0.04,
    "sports_fees_v2": 0.04,
    "crypto_fees": 0.07,
}
DEFAULT_FEE_RATE = 0.04

# ---------------------------------------------------------------------------
# Keywords for market classification
# ---------------------------------------------------------------------------

FED_KEYWORDS = [
    "fed ", "federal reserve", "fomc", "interest rate", "basis point",
    "rate cut", "rate hike", "bps after", "fed decrease", "fed increase",
    "fed rate",
]

MACRO_STRESS_KEYWORDS = [
    "recession", "unemployment", "gdp", "inflation", "cpi", "pce",
    "shutdown", "government shutdown", "default", "debt ceiling",
    "debt limit", "treasury default", "fiscal cliff", "stagflation",
]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    market_id: str
    question: str
    category: str
    end_date: str              # ISO date string
    days_to_close: int
    volume_usd: float
    implied_prob: float        # current mid-price (0–1)
    our_prior: Optional[float] # our quantitative estimate, or None
    discrepancy: Optional[float]  # abs(implied_prob - our_prior), or None
    fee_rate: float
    flagged: bool
    flag_reason: str


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only — no requests dependency beyond what we wrap)
# ---------------------------------------------------------------------------

def _http_get(url: str, params: Optional[dict] = None, timeout: int = 15,
              retries: int = 3) -> dict | list:
    """GET url with optional query params; return parsed JSON. Raise on failure."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "trading-bench/1.0 (research; polymarket scanner)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"HTTP GET failed after {retries} attempts [{url}]: {last_err}")


# ---------------------------------------------------------------------------
# Gamma API
# ---------------------------------------------------------------------------

def fetch_markets(limit_per_page: int = 100, max_pages: int = 10) -> list:
    """Fetch active markets from Gamma API, sorted by volume descending.

    Paginates via `offset` until fewer than `limit_per_page` results are
    returned or `max_pages` is reached. Returns raw list of market dicts.
    """
    all_markets: list = []
    for page in range(max_pages):
        offset = page * limit_per_page
        params = {
            "closed": "false",
            "active": "true",
            "limit": limit_per_page,
            "order": "volumeNum",
            "ascending": "false",
            "offset": offset,
        }
        try:
            batch = _http_get(f"{GAMMA_BASE}/markets", params=params, timeout=20)
        except RuntimeError as exc:
            if page == 0:
                raise  # First page failure = hard error
            print(f"[polymarket_scanner] Warning: page {page} fetch failed: {exc}",
                  file=sys.stderr)
            break
        if not isinstance(batch, list) or not batch:
            break
        all_markets.extend(batch)
        if len(batch) < limit_per_page:
            break  # Last page
    return all_markets


# ---------------------------------------------------------------------------
# Category / tag classification helpers
# ---------------------------------------------------------------------------

def _extract_tags(market: dict) -> set[str]:
    """Extract tag slug set from market's events[0].tags list."""
    events = market.get("events") or []
    if not events:
        return set()
    tags = events[0].get("tags") or []
    return {(t.get("slug") or "").lower() for t in tags}


def _classify_category(market: dict, question_lower: str) -> str:
    """Return a human-readable category string for display."""
    tag_slugs = _extract_tags(market)
    # Check tag-based category
    for slug in tag_slugs:
        if "sport" in slug or "soccer" in slug or "basketball" in slug \
                or "football" in slug or "baseball" in slug or "tennis" in slug \
                or "golf" in slug or "mma" in slug or "ufc" in slug:
            return "Sports"
        if "crypto" in slug or "bitcoin" in slug or "ethereum" in slug:
            return "Crypto"
        if "politics" in slug or "election" in slug or "political" in slug:
            return "Politics"
        if "economics" in slug or "finance" in slug or "economy" in slug:
            return "Economics"

    # Fall back to keyword-based
    if any(kw in question_lower for kw in FED_KEYWORDS + MACRO_STRESS_KEYWORDS):
        return "Economics"
    if any(kw in question_lower for kw in ["election", "vote", "senate", "congress",
                                             "president", "governor", "prime minister",
                                             "parliament", "democrat", "republican"]):
        return "Politics"
    if any(kw in question_lower for kw in ["war", "military", "sanction", "nuclear",
                                             "treaty", "diplomatic", "nato", "un "]):
        return "World"
    return "Other"


def _should_exclude(market: dict, question_lower: str) -> Optional[str]:
    """Return a skip reason string if market should be excluded, else None."""
    tag_slugs = _extract_tags(market)
    # Exclude sports / crypto / entertainment by tag
    if tag_slugs & EXCLUDE_TAG_SLUGS:
        matched = list(tag_slugs & EXCLUDE_TAG_SLUGS)
        return f"excluded tag: {matched[0]}"
    # Exclude sports / entertainment / crypto by question keyword
    skip_kw = [
        "world cup", "nba ", "nfl ", "mlb ", "nhl ", "premier league",
        "champions league", "formula 1", "f1 ", "super bowl", "olympic",
        "ncaa", "march madness", "wimbledon", "us open", "masters ",
        "bitcoin", "ethereum", "solana", "crypto", "dogecoin",
        "grammy", "oscar", "emmy", "billboard", "box office",
    ]
    for kw in skip_kw:
        if kw in question_lower:
            return f"excluded keyword: {kw!r}"
    return None


def _days_to_close(end_date_str: str) -> int:
    """Parse ISO end date → days from now (UTC). Returns -1 on parse failure."""
    try:
        # Gamma returns e.g. '2026-07-20T00:00:00Z' or '2026-07-20'
        s = end_date_str[:10]  # YYYY-MM-DD
        end = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, (end - now).days)
    except Exception:
        return -1


def _extract_implied_prob(market: dict) -> Optional[float]:
    """Extract YES implied probability from outcomePrices JSON string."""
    raw = market.get("outcomePrices")
    if not raw:
        return None
    try:
        prices = json.loads(raw)
        if not prices:
            return None
        return float(prices[0])
    except (json.JSONDecodeError, ValueError, IndexError):
        return None


def _get_fee_rate(market: dict) -> float:
    """Extract taker fee rate from market's feeType or feeSchedule."""
    # Prefer explicit feeSchedule.rate if present
    schedule = market.get("feeSchedule") or {}
    if isinstance(schedule, dict) and "rate" in schedule:
        try:
            return float(schedule["rate"])
        except (ValueError, TypeError):
            pass
    fee_type = (market.get("feeType") or "").lower()
    return FEE_RATES.get(fee_type, DEFAULT_FEE_RATE)


# ---------------------------------------------------------------------------
# FRED / NFCI prior
# ---------------------------------------------------------------------------

def _load_fred_api_key() -> Optional[str]:
    """Load FRED API key from env or workspace .env. Returns None if not found."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        env_path = WORKSPACE / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("FRED_API_KEY"):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        key = val
                        break
    return key if key else None


def _fetch_nfci_latest() -> Optional[float]:
    """Fetch the most recent NFCI value from FRED API. Returns None on failure."""
    key = _load_fred_api_key()
    if not key:
        return None
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # NFCI is weekly; go back 90 days to ensure we get a recent reading
        start = datetime.now(timezone.utc)
        start = start.replace(year=start.year - 1)
        start_str = start.strftime("%Y-%m-%d")
        params = {
            "series_id": "NFCI",
            "api_key": key,
            "file_type": "json",
            "observation_start": start_str,
            "observation_end": today,
            "sort_order": "desc",
            "limit": 5,
        }
        url = "https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"User-Agent": "trading-bench/1.0 (research)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        obs = data.get("observations") or []
        # Find most recent non-missing value
        for o in obs:
            v = o.get("value", ".")
            if v and v != ".":
                return float(v)
    except Exception as exc:  # noqa: BLE001
        print(f"[polymarket_scanner] FRED NFCI fetch failed (graceful): {exc}",
              file=sys.stderr)
    return None


def _nfci_to_recession_prior(nfci: float) -> float:
    """Convert NFCI value to rough recession/stress probability prior.

    NFCI < -0.5 → loose conditions → low recession risk
    NFCI -0.5 to 0.0 → near-neutral
    NFCI 0.0 to 0.5 → slightly tight
    NFCI > 0.5 → tight → elevated recession risk
    """
    if nfci < -0.5:
        return 0.05
    elif nfci < 0.0:
        return 0.15
    elif nfci < 0.5:
        return 0.30
    else:
        return 0.50


# ---------------------------------------------------------------------------
# Scoring / classification
# ---------------------------------------------------------------------------

def _classify_market_type(question_lower: str) -> str:
    """Return 'fed_rate' | 'macro_stress' | 'other'."""
    if any(kw in question_lower for kw in FED_KEYWORDS):
        return "fed_rate"
    if any(kw in question_lower for kw in MACRO_STRESS_KEYWORDS):
        return "macro_stress"
    return "other"


# ---------------------------------------------------------------------------
# Fed rate question parsing + CME FedWatch prior
# ---------------------------------------------------------------------------

# Month name → month number
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def _parse_fed_question(question_lower: str) -> Optional[dict]:
    """Parse a Fed rate market question and return a structured dict.

    Returns None if unrecognised. Otherwise:
      {'type': 'single_meeting', 'meeting_month': 'YYYY-MM', 'action': 'cut'|'hike'|'hold', 'bps': 25|50}
    or
      {'type': 'annual_cuts', 'year': 2026, 'n_cuts': int}  (cumulative cuts in year)
    or
      {'type': 'annual_hike', 'year': 2026}  (any hike in year)
    """
    q = question_lower

    # Pattern 1: "will the fed decrease/increase interest rates by 25 bps after the <month> <year> meeting"
    m = re.search(
        r"will the fed (decrease|increase) interest rates by (\d+)\+? ?bps after the (\w+) (\d{4}) meeting",
        q,
    )
    if m:
        action = "cut" if m.group(1) == "decrease" else "hike"
        bps = int(m.group(2))
        month_name = m.group(3).lower()
        year = int(m.group(4))
        month_num = _MONTH_MAP.get(month_name)
        if month_num:
            return {
                "type": "single_meeting",
                "meeting_month": f"{year}-{month_num:02d}",
                "action": action,
                "bps": bps,
            }

    # Pattern 2: "will there be no change in fed interest rates after the <month> <year> meeting"
    m = re.search(
        r"will there be no change in fed interest rates after the (\w+) (\d{4}) meeting",
        q,
    )
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(2))
        month_num = _MONTH_MAP.get(month_name)
        if month_num:
            return {
                "type": "single_meeting",
                "meeting_month": f"{year}-{month_num:02d}",
                "action": "hold",
                "bps": 0,
            }

    # Pattern 3: "will N fed rate cuts happen in 2026"
    m = re.search(r"will (\d+) fed rate cuts? happen in (\d{4})", q)
    if m:
        n = int(m.group(1))
        year = int(m.group(2))
        return {"type": "annual_cuts", "year": year, "n_cuts": n}

    # Pattern 4: "will no fed rate cuts happen in 2026"
    m = re.search(r"will no fed rate cuts? happen in (\d{4})", q)
    if m:
        year = int(m.group(1))
        return {"type": "annual_cuts", "year": year, "n_cuts": 0}

    # Pattern 5: "will 12 or more fed rate cuts happen in 2026"
    m = re.search(r"will (\d+) or more fed rate cuts? happen in (\d{4})", q)
    if m:
        n = int(m.group(1))
        year = int(m.group(2))
        return {"type": "annual_cuts_gte", "year": year, "n_cuts": n}

    # Pattern 6: "fed rate hike in 2026"
    m = re.search(r"fed rate hike in (\d{4})", q)
    if m:
        year = int(m.group(1))
        return {"type": "annual_hike", "year": year}

    return None


def _compute_fed_prior(
    parsed: dict,
    fedwatch_data: Optional[dict],
) -> Optional[float]:
    """Compute our_prior probability using FedWatch data and parsed question.

    Returns float 0..1 or None if can't compute.
    """
    if fedwatch_data is None or not fedwatch_data:
        return None

    qtype = parsed.get("type")

    if qtype == "single_meeting":
        meeting_month = parsed["meeting_month"]
        action = parsed["action"]
        bps = parsed.get("bps", 25)

        # Find the meeting data for this month
        meeting_data = None
        for date_str, md in fedwatch_data.items():
            if date_str[:7] == meeting_month:
                meeting_data = md
                break

        if meeting_data is None:
            return None

        if action == "hold":
            return meeting_data.get("hold")
        elif action == "cut":
            if bps <= 25:
                return meeting_data.get("cut_1")
            elif bps <= 50:
                # 50+ bps = P(cut >= 2 steps) = rough approximation
                # We only have single-step probs, so use small residual
                p_cut_1 = meeting_data.get("cut_1", 0.0)
                # For very high cut-prob scenarios, some multi-step probability
                # Approximate: p(>=50bps) ~ p_cut_1 * 0.15 (rough)
                return min(p_cut_1 * 0.15, 0.20)
            return None
        elif action == "hike":
            if bps <= 25:
                return meeting_data.get("hike_1")
            elif bps <= 50:
                p_hike_1 = meeting_data.get("hike_1", 0.0)
                return min(p_hike_1 * 0.15, 0.20)
            return None

    elif qtype in ("annual_cuts", "annual_cuts_gte"):
        year = parsed["year"]
        n_target = parsed["n_cuts"]
        # Compute cumulative cut probability distribution across all meetings in year
        # We sum cut probabilities and model as approximate Poisson
        # P(exactly N cuts) uses simple binomial approximation
        year_meetings = [
            (date_str, md) for date_str, md in fedwatch_data.items()
            if date_str[:4] == str(year)
        ]
        if not year_meetings:
            return None

        # Expected number of cuts = sum of per-meeting cut probs
        expected_cuts = sum(md.get("cut_1", 0.0) for _, md in year_meetings)
        n_meetings = len(year_meetings)

        # Use Poisson distribution: P(X=k) = e^(-λ)*λ^k/k!
        import math
        lam = expected_cuts

        def poisson_pmf(k, lam):
            if lam <= 0:
                return 1.0 if k == 0 else 0.0
            try:
                return math.exp(-lam) * (lam ** k) / math.factorial(k)
            except (OverflowError, ValueError):
                return 0.0

        if qtype == "annual_cuts":
            # P(exactly n_target cuts)
            return min(1.0, poisson_pmf(n_target, lam))
        else:
            # P(>= n_target cuts)
            p_lt = sum(poisson_pmf(k, lam) for k in range(n_target))
            return max(0.0, min(1.0, 1.0 - p_lt))

    elif qtype == "annual_hike":
        year = parsed["year"]
        year_meetings = [
            (date_str, md) for date_str, md in fedwatch_data.items()
            if date_str[:4] == str(year)
        ]
        if not year_meetings:
            return None
        # P(at least 1 hike) = 1 - P(no hikes)
        p_no_hike = 1.0
        for _, md in year_meetings:
            p_no_hike *= (1.0 - md.get("hike_1", 0.0))
        return max(0.0, min(1.0, 1.0 - p_no_hike))

    return None


def _score_market(market: dict, nfci: Optional[float], fedwatch_data: Optional[dict] = None) -> tuple[Optional[float], float, bool, str]:
    """Compute (our_prior, discrepancy_or_0, flagged, flag_reason).

    Returns:
      our_prior: float 0–1 or None
      discrepancy: abs(implied - prior) or 0.0 if None
      flagged: bool
      flag_reason: str
    """
    question = (market.get("question") or "")
    question_lower = question.lower()
    implied_prob = _extract_implied_prob(market)
    if implied_prob is None:
        return None, 0.0, False, "no implied prob available"

    mtype = _classify_market_type(question_lower)

    if mtype == "fed_rate":
        # Try to compute prior from CME FedWatch (ZQ futures)
        parsed = _parse_fed_question(question_lower)
        if parsed is None:
            return None, 0.0, True, "Fed rate market — unrecognised pattern (check CME FedWatch manually)"

        if fedwatch_data is None:
            return None, 0.0, True, "Fed rate market — CME FedWatch data unavailable (ZQ fetch failed)"

        prior = _compute_fed_prior(parsed, fedwatch_data)
        if prior is None:
            return None, 0.0, True, f"Fed rate market — no FedWatch data for {parsed.get('meeting_month', parsed.get('year', '?'))}"

        disc = abs(implied_prob - prior)
        source_desc = f"ZQ-futures prior={prior:.3f} vs market={implied_prob:.3f} disc={disc:.3f}"

        if disc > DISCREPANCY_THRESHOLD:
            return prior, disc, True, f"CME edge: {source_desc}"
        else:
            return prior, disc, False, f"CME (no edge): {source_desc}"

    if mtype == "macro_stress":
        if nfci is None:
            # FRED unreachable — graceful degradation
            return None, 0.0, False, "FRED unavailable — macro prior skipped"
        prior = _nfci_to_recession_prior(nfci)
        disc = abs(implied_prob - prior)
        if disc > MACRO_DISCREPANCY_THRESHOLD:
            flagged = True
            flag_reason = (
                f"NFCI={nfci:.3f} → macro prior={prior:.2f} "
                f"vs market implied={implied_prob:.2f} "
                f"(discrepancy={disc:.2f})"
            )
        else:
            flagged = False
            flag_reason = (
                f"NFCI={nfci:.3f} → macro prior={prior:.2f} "
                f"vs market implied={implied_prob:.2f} "
                f"(within threshold)"
            )
        return prior, disc, flagged, flag_reason

    # Other — no prior
    return None, 0.0, False, "no prior available for this market type"


# Keep old signature working for callers that don't pass fedwatch_data
# (done via default arg above)


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------

def scan(verbose: bool = False) -> List[ScanResult]:
    """Fetch active markets and return a list of ScanResult.

    Applies filters (volume, days-to-close, category) then scores each
    eligible market against quantitative priors.
    """
    if verbose:
        print("[polymarket_scanner] Fetching markets from Gamma API...")

    raw_markets = fetch_markets()
    if verbose:
        print(f"[polymarket_scanner] Fetched {len(raw_markets)} raw markets")

    # Pre-fetch NFCI once (shared across all macro stress markets)
    if verbose:
        print("[polymarket_scanner] Fetching NFCI from FRED...")
    nfci = _fetch_nfci_latest()
    if verbose:
        if nfci is not None:
            print(f"[polymarket_scanner] NFCI latest = {nfci:.4f}")
        else:
            print("[polymarket_scanner] NFCI unavailable — macro priors disabled")

    # ZQ-based FedWatch priors are unreliable from datacenter IPs (Yahoo returns
    # stale/misrouted contract data; near-month-end FOMC dates amplify errors).
    # Disabled until a reliable source is wired. Existing paper bets retain their
    # locked-in priors from bet-placement time. New Fed rate markets won't be
    # flagged on CME discrepancy; NFCI macro priors remain active.
    fedwatch_data = None

    results: List[ScanResult] = []
    stats = {"total": len(raw_markets), "excluded_tag": 0, "excluded_vol": 0,
             "excluded_days": 0, "processed": 0}

    for m in raw_markets:
        question = m.get("question") or ""
        question_lower = question.lower()
        volume = float(m.get("volumeNum") or m.get("volume") or 0)
        end_date_raw = m.get("endDateIso") or m.get("endDate") or ""
        dtc = _days_to_close(end_date_raw)
        end_date = end_date_raw[:10] if end_date_raw else "unknown"

        # --- Filters ---
        skip_reason = _should_exclude(m, question_lower)
        if skip_reason:
            stats["excluded_tag"] += 1
            continue

        if volume < MIN_VOLUME_USD:
            stats["excluded_vol"] += 1
            continue

        if dtc < MIN_DAYS_TO_CLOSE:
            stats["excluded_days"] += 1
            continue

        stats["processed"] += 1
        category = _classify_category(m, question_lower)
        implied_prob = _extract_implied_prob(m)
        fee_rate = _get_fee_rate(m)

        if implied_prob is None:
            results.append(ScanResult(
                market_id=str(m.get("id", "")),
                question=question,
                category=category,
                end_date=end_date,
                days_to_close=dtc,
                volume_usd=volume,
                implied_prob=0.0,
                our_prior=None,
                discrepancy=None,
                fee_rate=fee_rate,
                flagged=False,
                flag_reason="no outcome prices available",
            ))
            continue

        our_prior, discrepancy_val, flagged, flag_reason = _score_market(m, nfci, fedwatch_data)

        results.append(ScanResult(
            market_id=str(m.get("id", "")),
            question=question,
            category=category,
            end_date=end_date,
            days_to_close=dtc,
            volume_usd=volume,
            implied_prob=implied_prob,
            our_prior=our_prior,
            discrepancy=discrepancy_val if our_prior is not None else None,
            fee_rate=fee_rate,
            flagged=flagged,
            flag_reason=flag_reason,
        ))

    if verbose:
        print(
            f"[polymarket_scanner] Stats: total={stats['total']} "
            f"excl_tag={stats['excluded_tag']} excl_vol={stats['excluded_vol']} "
            f"excl_days={stats['excluded_days']} processed={stats['processed']}"
        )
    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _format_table(results: List[ScanResult]) -> str:
    """Return a markdown table of all results."""
    lines = [
        "| Market ID | Question | Category | End Date | Days | Volume USD | Implied P | Our Prior | Discrepancy | Fee | Flagged | Reason |",
        "|-----------|----------|----------|----------|------|------------|-----------|-----------|-------------|-----|---------|--------|",
    ]
    for r in results:
        q = r.question[:60].replace("|", " ") + ("..." if len(r.question) > 60 else "")
        prior_s = f"{r.our_prior:.2f}" if r.our_prior is not None else "—"
        disc_s = f"{r.discrepancy:.3f}" if r.discrepancy is not None else "—"
        flagged_s = "🚩 YES" if r.flagged else "no"
        lines.append(
            f"| {r.market_id} | {q} | {r.category} | {r.end_date} | {r.days_to_close} "
            f"| {r.volume_usd:,.0f} | {r.implied_prob:.3f} | {prior_s} | {disc_s} "
            f"| {r.fee_rate:.0%} | {flagged_s} | {r.flag_reason[:60]} |"
        )
    return "\n".join(lines)


def write_report(results: List[ScanResult], nfci: Optional[float] = None) -> Path:
    """Write a markdown report to reports/polymarket_scan_<YYYYMMDD>.md."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = REPORTS_DIR / f"polymarket_scan_{date_str}.md"

    flagged = [r for r in results if r.flagged]
    n_fed = sum(1 for r in results if r.flagged and "CME" in r.flag_reason)
    n_macro = sum(1 for r in results if r.flagged and "NFCI" in r.flag_reason)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    nfci_s = f"{nfci:.4f}" if nfci is not None else "unavailable"

    report_lines = [
        f"# Polymarket Scanner — {date_str}",
        f"_Generated: {ts}_",
        "",
        "## Summary",
        f"- Markets fetched & filtered: **{len(results)}**",
        f"- Flagged markets: **{len(flagged)}** ({n_fed} Fed rate, {n_macro} macro NFCI)",
        f"- NFCI (Chicago Fed Financial Conditions): **{nfci_s}**",
        f"  - NFCI interpretation: {'< 0 = loose (low stress)' if nfci is not None and nfci < 0 else '>= 0 = tight (elevated stress)' if nfci is not None else 'N/A'}",
        "",
        "## Flagged Markets (Actionable)",
        "",
    ]

    if flagged:
        report_lines += [
            "| Market ID | Question | End Date | Days | Volume | Implied P | Our Prior | Discrepancy | Fee | Reason |",
            "|-----------|----------|----------|------|--------|-----------|-----------|-------------|-----|--------|",
        ]
        for r in flagged:
            q = r.question[:70].replace("|", " ") + ("..." if len(r.question) > 70 else "")
            prior_s = f"{r.our_prior:.2f}" if r.our_prior is not None else "—"
            disc_s = f"{r.discrepancy:.3f}" if r.discrepancy is not None else "—"
            report_lines.append(
                f"| {r.market_id} | {q} | {r.end_date} | {r.days_to_close} "
                f"| ${r.volume_usd:,.0f} | {r.implied_prob:.3f} | {prior_s} | {disc_s} "
                f"| {r.fee_rate:.0%} | {r.flag_reason[:80]} |"
            )
    else:
        report_lines.append("_No markets flagged this run._")

    report_lines += [
        "",
        "## All Scanned Markets",
        "",
        _format_table(results),
        "",
        "## Methodology",
        "- **Volume filter:** ≥ $100,000 (thin markets excluded)",
        "- **Duration filter:** ≥ 14 days to close (noise excluded)",
        "- **Category filter:** Sports/Crypto/Entertainment excluded by tag/keyword",
        "- **Fed rate prior:** No live CME FedWatch feed — manual review flagged",
        "- **Macro stress prior:** FRED NFCI → recession probability bucket (0.05/0.15/0.30/0.50)",
        "  - Flag threshold: |implied − prior| > 10pp",
        "- **Other markets:** No prior assigned",
        "",
        "## Notes",
        "- Polymarket blocks US IP for order placement; use Polymarket.us for US participants",
        "- All data from public Gamma API (no auth required)",
        "- Prices represent current mid (YES token first outcome price)",
    ]

    path.write_text("\n".join(report_lines) + "\n")
    return path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_flagged(flagged: List[ScanResult]) -> None:
    """Print flagged markets to stdout in a readable format."""
    if not flagged:
        print("\n[No markets flagged]\n")
        return
    print(f"\n{'='*80}")
    print(f"FLAGGED MARKETS ({len(flagged)})")
    print(f"{'='*80}")
    for r in flagged:
        print(f"\n  [{r.market_id}] {r.question}")
        print(f"  Category: {r.category} | End: {r.end_date} | Days: {r.days_to_close}")
        print(f"  Volume: ${r.volume_usd:,.0f} | Implied P: {r.implied_prob:.3f} | Fee: {r.fee_rate:.0%}")
        if r.our_prior is not None:
            print(f"  Our prior: {r.our_prior:.3f} | Discrepancy: {r.discrepancy:.3f}")
        print(f"  → {r.flag_reason}")
    print()


def main() -> None:
    print("[polymarket_scanner] Starting scan...")
    t0 = time.time()

    nfci = _fetch_nfci_latest()
    print(f"[polymarket_scanner] NFCI = {nfci:.4f}" if nfci is not None
          else "[polymarket_scanner] NFCI unavailable (FRED unreachable)")

    results = scan(verbose=True)
    elapsed = time.time() - t0

    flagged = [r for r in results if r.flagged]
    print(f"\n[polymarket_scanner] Done in {elapsed:.1f}s")
    print(f"  Markets after filtering: {len(results)}")
    print(f"  Flagged: {len(flagged)}")

    _print_flagged(flagged)

    # Print summary of all scanned
    print(f"\n{'─'*80}")
    print(f"ALL SCANNED MARKETS ({len(results)})")
    print(f"{'─'*80}")
    print(f"{'ID':>8}  {'Implied':>7}  {'Prior':>7}  {'Disc':>6}  {'Vol':>12}  {'Days':>5}  Question")
    print(f"{'─'*8}  {'─'*7}  {'─'*7}  {'─'*6}  {'─'*12}  {'─'*5}  {'─'*40}")
    for r in sorted(results, key=lambda x: x.volume_usd, reverse=True):
        prior_s = f"{r.our_prior:.3f}" if r.our_prior is not None else "    —  "
        disc_s = f"{r.discrepancy:.3f}" if r.discrepancy is not None else "    —"
        flag_s = "🚩" if r.flagged else "  "
        q_short = r.question[:55] + "..." if len(r.question) > 55 else r.question
        print(f"{r.market_id:>8}  {r.implied_prob:>7.3f}  {prior_s:>7}  {disc_s:>6}  "
              f"${r.volume_usd:>11,.0f}  {r.days_to_close:>5}  {flag_s} {q_short}")

    report_path = write_report(results, nfci=nfci)
    print(f"\n[polymarket_scanner] Report written → {report_path}")


if __name__ == "__main__":
    main()