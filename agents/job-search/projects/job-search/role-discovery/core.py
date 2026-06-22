"""Shared types and helpers for the role-discovery pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json
import re
import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Role:
    company: str
    title: str
    location: str = ""
    exp_required: str = ""        # e.g. "exp:3+yrs", "exp:unstated"
    url: str = ""
    posted_at: str = ""           # ISO date
    source: str = ""              # adapter name
    raw: dict = field(default_factory=dict, repr=False)

    def to_dict(self):
        d = asdict(self)
        d.pop("raw", None)
        return d


def http_get(url: str, headers: dict = None, params: dict = None, timeout: int = 30):
    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)
    return requests.get(url, headers=h, params=params, timeout=timeout)


def http_post_json(url: str, body: dict, headers: dict = None, timeout: int = 30):
    h = dict(DEFAULT_HEADERS)
    h["Content-Type"] = "application/json"
    if headers:
        h.update(headers)
    return requests.post(url, headers=h, data=json.dumps(body), timeout=timeout)


# ---------- experience parsing ----------

EXP_PATTERNS = [
    (re.compile(r"\b(\d+)\+?\s*(?:to|-|–)\s*(\d+)\s*\+?\s*(?:years?|yrs?)\b", re.I), "range"),
    (re.compile(r"\bminimum\s+(?:of\s+)?(\d+)\+?\s*(?:years?|yrs?)\b", re.I), "min"),
    (re.compile(r"\bat\s*least\s*(\d+)\s*\+?\s*(?:years?|yrs?)\b", re.I), "min"),
    (re.compile(r"\b(\d+)\+\s*(?:years?|yrs?)\b", re.I), "min"),
    # "8 years of program management experience", "5 yrs of PM experience", etc.
    (re.compile(r"\b(\d+)\s*\+?\s*(?:years?|yrs?)['’]?\s+(?:of\s+)?[A-Za-z][A-Za-z\s/&,\-]{0,60}?\bexperience\b", re.I), "min"),
    # "5 years of experience" (no middle noun)
    (re.compile(r"\b(\d+)\s*\+?\s*(?:years?|yrs?)['’]?\s+of\s+experience\b", re.I), "min"),
    # bare "5 years experience" / "5 years' experience" / "5 yrs experience"
    (re.compile(r"\b(\d+)\s*\+?\s*(?:years?|yrs?)['’]?\s+experience\b", re.I), "min"),
]


def parse_experience(description_text: str) -> str:
    """Extract experience requirement from a description.

    Returns 'exp:Nyrs', 'exp:N-Myrs', 'exp:N+yrs', or 'exp:unstated'.

    YOE doctrine (Cyrus, reconciled 2026-06-02):
      - A RANGE counts as its LOWER bound. '2-4 years' -> floor 2 (KEEP, 2<=3);
        '3-10 years' -> floor 3 (KEEP); '4-8 years' -> floor 4 (DROP). The upper
        number of a range must NEVER be re-read as a separate 'min' requirement.
      - Across DISTINCT requirement phrases, the MAX lower-bound wins (so a
        primary '5 years overall' beats a secondary '1-2 years of [skill]').
      - Scans the FULL JD (no early char cap) so deep requirements aren't missed
        and wrongly labelled 'unstated'.
    """
    if not description_text:
        return "exp:unstated"

    text = description_text  # scan the ENTIRE JD (was capped at 8000 -> false 'unstated')

    # Pass 1: find all RANGE spans first; record their lower bound and char span.
    range_spans = []  # (start, end, lo, hi)
    range_pat = EXP_PATTERNS[0][0]  # the 'range' pattern
    for m in range_pat.finditer(text):
        try:
            lo = int(m.group(1)); hi = int(m.group(2))
        except (ValueError, IndexError):
            continue
        range_spans.append((m.start(), m.end(), lo, hi))

    best_lo = -1
    best_hi = None  # only set when the winning match was a range

    # Seed with ranges (count each by its LOWER bound).
    for _s, _e, lo, hi in range_spans:
        if lo > best_lo:
            best_lo = lo
            best_hi = hi

    # Pass 2: all non-range 'min' patterns, but SKIP any match whose NUMBER sits
    # inside a range span (that's the range's upper bound, not a new requirement).
    def _num_in_range_span(num_start):
        for s, e, _lo, _hi in range_spans:
            if s <= num_start < e:
                return True
        return False

    for pat, kind in EXP_PATTERNS[1:]:  # skip the range pattern (handled above)
        for m in pat.finditer(text):
            if _num_in_range_span(m.start(1)):
                continue
            try:
                lo = int(m.group(1))
            except (ValueError, IndexError):
                continue
            if lo > best_lo:
                best_lo = lo
                best_hi = None  # a bare min wins -> no range upper bound

    if best_lo < 0:
        return "exp:unstated"
    if best_hi is not None and best_hi >= best_lo:
        return f"exp:{best_lo}-{best_hi}yrs"
    return f"exp:{best_lo}+yrs"


# ---------- title normalization ----------

QUALIFYING_TITLE_RE = re.compile(
    r"\b("
    r"product\s*manager|product\s*management|"
    r"associate\s*product\s*manager|"
    r"\bAPM\b|\bPM\s*[I]+\b|\bPM\s*\d\b|\bPM\b|"
    r"technical\s*program\s*manager|\bTPM\b|"
    r"program\s*manager|"
    r"sales\s*engineer|"
    r"solutions?\s*engineer|"
    r"solutions?\s*architect|"
    r"customer\s*engineer|"
    r"forward\s*deployed\s*engineer"
    r")\b",
    re.I,
)

# Exclude high-seniority titles. Includes trailing level numbers (e.g. "PM 3", "Engineering Program Manager 4")
# and Roman-numeral level suffixes (III, IV, V) on PM/TPM/PgM/SA/SE titles.
SENIORITY_EXCLUDE_RE = re.compile(
    r"\b(senior|staff|principal|lead|director|head\s+of|vp|vice\s+president|"
    r"chief|distinguished|fellow|sr\.?|architect\s*[Ii][Vv]|architect\s*[3-9])\b",
    re.I,
)

# Trailing level suffix on PM/TPM/Program Manager/Solutions roles: e.g. "... Manager 3", "... Manager IV"
# Levels 3+ at most companies = Senior+. Allow 1, 2, I, II.
LEVEL_SUFFIX_EXCLUDE_RE = re.compile(
    r"(?:program\s+manager|product\s+manager|technical\s+program\s+manager|"
    r"solutions?\s+architect|solutions?\s+engineer|sales\s+engineer|customer\s+engineer|"
    r"\bPM|\bTPM)\s+(?:[3-9]|10|III|IV|V|VI|VII|VIII|IX|X)\b",
    re.I,
)

# Manager-of-managers exclusion (these usually require 5+ yrs)
MANAGER_OF_TEAMS_RE = re.compile(r"\bmanager\s+of\s+(?:product\s+management|solutions?)\b", re.I)

# Suffix "<TitleFamily> Manager" = manager of a team in that family (e.g.
# "Solutions Architect Manager", "Solutions Engineer Manager",
# "Sales Engineer Manager", "Customer Engineer Manager"). These are
# people-management roles, not IC roles. Added 2026-05-29 after Google
# discovery surfaced 2 such roles that no other rule caught.
TEAM_MANAGER_SUFFIX_RE = re.compile(
    r"\b(?:solutions?\s+architect|solutions?\s+engineer|sales\s+engineer|"
    r"customer\s+engineer)\s+manager\b",
    re.I,
)

# Intern / co-op exclusion (Cyrus rule, 2026-05-08): never apply to internships.
INTERN_EXCLUDE_RE = re.compile(r"\b(intern|interns|internship|co[-\s]?op)\b", re.I)


def is_qualifying_title(title: str) -> bool:
    if not title:
        return False
    if SENIORITY_EXCLUDE_RE.search(title):
        return False
    if LEVEL_SUFFIX_EXCLUDE_RE.search(title):
        return False
    if MANAGER_OF_TEAMS_RE.search(title):
        return False
    if TEAM_MANAGER_SUFFIX_RE.search(title):
        return False
    if INTERN_EXCLUDE_RE.search(title):
        return False
    # `has_senior_title` is defined below — forward reference is fine
    # because Python resolves at call time. Added 2026-05-29: this
    # catches Group/Partner PM/TPM patterns that SENIORITY_EXCLUDE_RE
    # doesn't cover (was leaking ~17 Group PMs through Google discovery).
    if has_senior_title(title):
        return False
    return bool(QUALIFYING_TITLE_RE.search(title))


_EXP_NUM_RE = re.compile(r"exp:(\d+)(?:-(\d+))?")

# Patterns that indicate a senior IC / people-manager role even when no
# explicit YOE is stated. Added 2026-05-17 after Adobe Group PM R165611-1
# ("Overall 10+ years ... minimum of 3 years managing a team of product
# managers") got auto-submitted in error.
MANAGES_PEOPLE_RE = re.compile(
    r"\b(managing|manager\s+of|lead(?:ing)?)\s+(?:a\s+team\s+of\s+)?"
    r"(product\s+managers|engineers|engineering\s+teams?|designers|pms|"
    r"direct\s+reports|people\s+managers)\b",
    re.I,
)

# Senior-title skip layer (Cyrus rule, 2026-05-24). Catches roles where the
# title alone signals seniority but the JD body is vague on YOE / management
# language. Origin story: Adobe Group PM R165611-1 auto-submitted on 2026-05-16
# despite the JD requiring 10+ yrs, because exp parser didn't pick up the
# phrasing and MANAGES_PEOPLE_RE missed too. Title-keyword guard catches
# Group/Principal/Director/Partner/VP/Chief/Fellow/Head-of/SVP/EVP/Sr-Director/
# Distinguished/Senior-Staff titles at the front gate.
#
# Deliberate exclusions:
#   - bare "Senior" (we already gate on YOE)
#   - bare "Staff" (borderline — leave for YOE filter unless "Senior Staff")
#   - bare "Manager" (would over-trigger on customer-success roles, etc.)
# Note on 'group' and 'partner': both appear in non-seniority contexts
# ("Vision Products Group" = team name; "Partner Solutions Architect" =
# channel-eng role, not senior). We only match them when followed by a
# product/program/management noun, which is how they're used as seniority
# markers (Group Product Manager, Partner Technical Program Manager, etc.).
SENIOR_TITLE_RE = re.compile(
    r"("
    # Position-anchored seniority for 'group' / 'partner': require a
    # management/IC noun within a few words after.
    r"\b(?:group|partner)\s+(?:\w+\s+){0,2}"
      r"(?:product\s+manager|program\s+manager|product\s+management|"
      r"engineering\s+manager|technical\s+program\s+manager|"
      r"\bpm\b|\btpm\b)\b"
    r"|"
    # Unambiguous seniority keywords
    r"\b(?:principal|director|senior\s+staff|distinguished|"
    r"head\s+of|vp|svp|evp|chief|fellow|sr\.?\s+director)\b"
    r")",
    re.I,
)


def has_senior_title(title: str | None) -> bool:
    """Return True if title contains a senior-title keyword.

    Used as a front-gate filter in inline_submit.pick_batch().
    """
    if not title:
        return False
    return bool(SENIOR_TITLE_RE.search(title))


# Inline self-tests (cheap; module import time). If any assertion trips, we
# want to know immediately rather than discover it in a retro-pass.
assert has_senior_title("Group Product Manager"), "should match 'Group PM'"
assert has_senior_title("Group Product Manager, Payments"), "Group PM with suffix"
assert has_senior_title("Group Product Manager I, Connections"), "Group PM I"
assert has_senior_title("Partner Technical Program Manager"), "should match 'Partner TPM'"
assert has_senior_title("Principal Engineer"), "should match 'Principal'"
assert has_senior_title("Director, ML Platform"), "should match 'Director'"
assert has_senior_title("VP Engineering"), "should match 'VP'"
assert has_senior_title("Head of Product"), "should match 'Head of'"
assert has_senior_title("Senior Staff Product Manager"), "should match 'Senior Staff'"
assert has_senior_title("Chief of Staff"), "should match 'Chief'"
assert has_senior_title("SVP, Engineering"), "should match 'SVP'"
assert has_senior_title("Distinguished Engineer"), "should match 'Distinguished'"
assert has_senior_title("Fellow, Research"), "should match 'Fellow'"
assert has_senior_title("Sr. Director of Product"), "should match 'Sr. Director'"
assert not has_senior_title("Senior Product Manager"), "bare 'senior' should NOT match"
assert not has_senior_title("Staff Engineer"), "bare 'staff' should NOT match"
assert not has_senior_title("Manager of Customer Success"), "bare 'manager' should NOT match"
assert not has_senior_title("Product Manager"), "vanilla PM should NOT match"
assert not has_senior_title("Technical Program Manager"), "vanilla TPM should NOT match"
assert not has_senior_title("Hardware Engineering Program Manager (EPM) - Vision Products Group"), \
    "'Group' as team-name suffix should NOT match"
assert not has_senior_title("Partner Solutions Architect"), "Partner SA (channel role) should NOT match"
assert not has_senior_title("Partner Solutions Engineer"), "Partner SE (channel role) should NOT match"
assert not has_senior_title("Program Manager, Partner Operations"), "Partner ops PM should NOT match"
assert not has_senior_title(""), "empty should NOT match"
assert not has_senior_title(None), "None should NOT match"


def exp_lower_bound(exp_required: str) -> int | None:
    """Return the lower-bound YOE as an int, or None if unstated/unknown."""
    if not exp_required:
        return None
    m = _EXP_NUM_RE.search(exp_required)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (ValueError, TypeError):
        return None


def is_overreach(exp_required: str | None, jd_text: str | None = None,
                 role_title: str | None = None,
                 yoe_cap: int = 6) -> tuple[bool, str]:
    """Return (is_overreach, reason). Used as the auto-submit guard.

    Overreach when:
      - exp_req lower bound >= yoe_cap, OR
      - JD text or role title contains a people-management phrase ("managing
        a team of product managers", "manager of engineers", etc.).

    JD text scan is bounded to first 12k chars for cost.
    """
    lo = exp_lower_bound(exp_required or "")
    if lo is not None and lo >= yoe_cap:
        return True, f"yoe:{lo}>={yoe_cap}"
    if role_title and has_senior_title(role_title):
        m = SENIOR_TITLE_RE.search(role_title)
        return True, f"senior-title:{m.group(0)!r}"
    if role_title and MANAGES_PEOPLE_RE.search(role_title):
        return True, f"title:manages-people:{MANAGES_PEOPLE_RE.search(role_title).group(0)!r}"
    if jd_text:
        m = MANAGES_PEOPLE_RE.search(jd_text[:12000])
        if m:
            return True, f"jd:manages-people:{m.group(0)!r}"
    return False, ""


def is_qualifying_experience(exp_required: str) -> bool:
    """Apply exp filter (Cyrus rule, updated 2026-06-21):
    - unstated -> KEEP
    - min stated <= 5 yrs -> KEEP (incl. "3+", "5+", "3-5")
    - min stated >= 6 yrs -> DROP
    """
    if not exp_required or "unstated" in exp_required:
        return True
    m = _EXP_NUM_RE.search(exp_required)
    if not m:
        return True
    lo = int(m.group(1))
    return lo <= 5


_NON_US_COUNTRIES = (
    # countries / regions that should disqualify (lowercased substrings)
    "india", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "delhi", "noida", "gurgaon",
    "indonesia", "jakarta", "singapore", "philippines", "manila", "vietnam", "ho chi minh", "hanoi",
    "thailand", "bangkok", "malaysia", "kuala lumpur",
    "japan", "tokyo", "osaka", "korea", "seoul",
    "china", "shanghai", "beijing", "hong kong", "taiwan", "taipei",
    "australia", "sydney", "melbourne", "brisbane", "perth", "new zealand", "auckland",
    "uk", "u.k.", "united kingdom", "england", "scotland", "wales", "london", "manchester", "edinburgh", "dublin",
    "ireland",
    "france", "paris", "toulouse", "germany", "berlin", "munich", "hamburg",
    "spain", "madrid", "barcelona", "italy", "milan", "rome",
    "netherlands", "amsterdam", "rotterdam", "switzerland", "zurich", "geneva",
    "sweden", "stockholm", "norway", "oslo", "finland", "helsinki", "denmark", "copenhagen", "aarhus",
    "poland", "warsaw", "krakow", "czech", "prague", "romania", "bucharest", "hungary", "budapest",
    "israel", "tel aviv", "jerusalem",
    "uae", "dubai", "abu dhabi", "saudi arabia", "riyadh", "egypt", "cairo",
    "south africa", "cape town", "johannesburg",
    "brazil", "sao paulo", "rio de janeiro", "argentina", "buenos aires",
    "chile", "santiago", "colombia", "bogota", "mexico city", "guadalajara",
    "costa rica", "san jose, costa", "heredia", "panama", "peru", "lima",
    "canada", "toronto", "vancouver", "montreal", "ottawa", "calgary", "edmonton",
    "remote - denmark", "remote - india", "remote - canada", "remote - uk",
    "emea", "apac", "latam",
)

# Strict US markers. State two-letter abbrevs must be preceded by a comma+space to avoid false hits like ", in" matching India.
_US_MARKERS = (
    "united states", " usa", "(usa)", " us)", " us,", " us-", "us-",
    "us-remote", "remote - us", "remote, us", "remote us", "us remote",
    "remote (us)", "americas", "north america",
)
_US_STATE_CODES = (
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME",
    "MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA",
    "RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
)
_US_CITIES = (
    "san francisco", "new york", "seattle", "austin", "boston", "chicago", "denver", "miami",
    "san jose", "palo alto", "mountain view", "sunnyvale", "los angeles", "atlanta", "houston",
    "dallas", "phoenix", "philadelphia", "san diego", "portland", "minneapolis", "nashville",
    "washington", "redmond", "kirkland", "bellevue", "cupertino", "menlo park", "santa clara",
    "raleigh", "charlotte", "salt lake city", "pittsburgh", "indianapolis", "columbus",
    "detroit", "tampa", "orlando", "st. louis", "cincinnati", "kansas city", "milwaukee",
    "cambridge, ma", "hawthorne, ca",
)


def _slot_is_us(slot: str) -> bool:
    """Check a single location string (no `;` or `|`)."""
    s = slot.lower().strip()
    if not s:
        return False
    # Reject if any non-US country marker present (word-boundary aware)
    for c in _NON_US_COUNTRIES:
        if re.search(r"\b" + re.escape(c) + r"\b", s):
            return False
    # Accept if any US marker
    if any(m in s for m in _US_MARKERS):
        return True
    if any(c in s for c in _US_CITIES):
        return True
    # State code check: needs ", XX" pattern (case-sensitive on original to require uppercase)
    for code in _US_STATE_CODES:
        if re.search(r",\s*" + code + r"\b", slot):
            return True
    return False


def is_us_location(loc: str) -> bool:
    """Return True if location is US-based or has a US option in a multi-location string.

    Strict mode: empty/unknown locations are REJECTED (defaults to OUT).
    For multi-location strings ('A; B' or 'A | B'), at least one slot must be US.
    """
    if not loc:
        return False  # strict: unknown → out
    # Split on common multi-location separators
    slots = re.split(r"[;|]", loc)
    return any(_slot_is_us(s) for s in slots)


# ---------- text helpers ----------

def strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
