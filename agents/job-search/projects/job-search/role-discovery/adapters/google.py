"""Google Careers public search — discovery-only.

Cyrus's directive (2026-05-28): we want to KEEP DISCOVERING Google roles
(so the tracker has them and Cyrus can ask to tailor a resume), but we
NEVER auto-apply. The `tracker_merger` tags google-sourced rows with
`manual-apply` so they stay out of any auto-submit queue; on top of that
the URL pattern this adapter emits (google.com/about/careers/...) is not
matched by `inline_submit.pick_batch`'s ATS regexes, so it's
double-locked.

Data source: the public careers SPA HTML at
  https://www.google.com/about/careers/applications/jobs/results/?q=<term>&page=<N>
embeds the search results in an `AF_initDataCallback({key: 'ds:1', ..., data:[...] })`
block. We extract the array, walk each record, and emit `Role` objects.

The older `careers.google.com/api/v3/search/` endpoint Google used to
expose now 404s for anonymous callers, so we don't try it any more.

REAL YOE FROM THE JD (Cyrus 2026-06-08 re-enable, BACKLOG #1):
  The search blob (ds:1) exposes neither YOE nor a posting date. So for
  EACH discovered role we additionally fetch its detail page
    https://www.google.com/about/careers/applications/jobs/results/<job_id>
  (HTTP 200, ~1.1MB server-rendered HTML) and parse the YOE FLOOR from the
  "Minimum qualifications" block ONLY, taking the MAX "<N> years" mention
  in that block (see `parse_min_quals_floor`). "Preferred qualifications"
  is ignored entirely. The floor is emitted as exp_required="exp:{N}+yrs",
  which core._EXP_NUM_RE parses to lower-bound N, and the standing
  `is_qualifying_experience` gate (unstated->keep, <=3 keep, >=4 drop)
  bites automatically. If no year is found in the min block we keep
  exp_required="exp:unstated" (unstated->keep is the standing rule).

  Detail fetches are polite (0.5-1.5s jitter), capped, and each wrapped in
  try/except so one bad detail page leaves that role unstated rather than
  crashing the crawl.
"""
from __future__ import annotations
import re
import json
import time
import random
from typing import List, Optional
from core import Role, http_get


# ---------------------------------------------------------------------------
# SEARCH TERMS  ==  the ONE place to expand role-type scope.
# ---------------------------------------------------------------------------
# Cyrus 2026-06-08: Google is a PERMANENT discovery source. When the
# role-type scope expands fleet-wide (e.g. we start discovering Software
# Engineer roles too), ADD THE NEW TERM HERE and Google roles of that type
# flow into the tracker automatically through the same JD-YOE + title + US
# gates. DO NOT re-opt-out Google (do not re-add it to the classifier
# COMPANY_BLOCKLIST). The block was removed on 2026-06-08 on purpose.
#
# If a SHARED/global role-type list is ever introduced that other adapters
# read (grep for where 'software engineer' would be toggled fleet-wide),
# prefer sourcing SEARCH_TERMS from that shared list so Google tracks the
# fleet scope automatically. As of 2026-06-08 no such shared list exists in
# this project (each adapter — google/microsoft/uber/bytedance/workday —
# hard-codes its own search terms / company slugs), so this local list + this
# comment is the single source of truth for GOOGLE's discovery seed.
#
# NB: the fleet-wide ROLE-FAMILY FILTER lives in core.QUALIFYING_TITLE_RE
# (is_qualifying_title). That gate currently does NOT include "software
# engineer", so turning on SWE means TWO edits, not one: (1) add the term to
# SEARCH_TERMS here (seeds Google SWE discovery) AND (2) add the SWE family to
# core.QUALIFYING_TITLE_RE (so SWE rows actually pass the gate fleet-wide).
# core.QUALIFYING_TITLE_RE is the closest thing to a shared role-type list —
# treat it as the fleet toggle and this SEARCH_TERMS list as the Google seed.
SEARCH_TERMS = [
    "product manager",
    "program manager",
    "technical program manager",
    "sales engineer",
    "solutions engineer",
    "customer engineer",
    "solutions architect",
    # --- Software Engineering: NOT in scope yet (Cyrus 2026-06-08). When SWE
    #     discovery is turned on fleet-wide, uncomment / add here:
    # "software engineer",
]

# Public careers SPA URL. The HTML is huge (~1.4MB/page) but it's the
# only anonymous surface that lists jobs reliably as of 2026-05-28.
SEARCH_URL = "https://www.google.com/about/careers/applications/jobs/results/"

# AF_initDataCallback regex. `ds:1` is the dataset that holds search
# results; `ds:0` is tenant metadata.
_DS1_RE = re.compile(
    r"AF_initDataCallback\(\{key: 'ds:1'[^}]*?data:(\[.*?\]), sideChannel",
    re.S,
)

MAX_PAGES = 8  # safety cap; Google paginates 20/page

# Detail-fetch politeness/safety knobs (Cyrus 2026-06-08).
DETAIL_FETCH_DELAY = (0.5, 1.5)   # jitter (seconds) between detail fetches
MAX_DETAIL_FETCHES = 400          # hard cap per crawl so we never hammer Google
_DETAIL_TIMEOUT = 45


# ---------------------------------------------------------------------------
# Minimum-qualifications YOE floor parser  (the core re-enable change)
# ---------------------------------------------------------------------------
# Match "<N> years", "<N>+ years", "<N> yrs", "<N>+ yrs" (case-insensitive).
_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:years?|yrs?)\b", re.I)

# Section headings that TERMINATE the "Minimum qualifications" block. The
# first of these that appears AFTER the min-quals heading bounds the block.
_MIN_QUALS_HEADING_RE = re.compile(r"minimum\s+qualifications", re.I)
_NEXT_SECTION_RE = re.compile(
    r"(preferred\s+qualifications|about\s+the\s+job|about\s+this\s+role|"
    r"responsibilities|role\s+description|what\s+you[’'`]?ll\s+do|"
    r"benefits|why\s+google)",
    re.I,
)


def _decode_google_html(raw: str) -> str:
    """Google's careers HTML is DOUBLE-escaped (\\u003c for '<', etc).

    Decode the unicode escapes, unescape HTML entities, then strip tags and
    collapse whitespace so headings/text are contiguous and matchable.
    """
    import html as _html
    text = raw
    # Decode \uXXXX sequences (server embeds JSON-escaped HTML).
    try:
        text = text.encode("utf-8", "ignore").decode("unicode_escape", "ignore")
    except Exception:
        pass
    text = _html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_min_quals_block(detail_text: str) -> str:
    """Return ONLY the 'Minimum qualifications' block text.

    From the (decoded, tag-stripped) detail text, find the 'Minimum
    qualifications' heading and return everything up to the NEXT section
    heading (Preferred qualifications / About the job / Responsibilities /
    ...). Returns "" if the heading isn't present.
    """
    if not detail_text:
        return ""
    m = _MIN_QUALS_HEADING_RE.search(detail_text)
    if not m:
        return ""
    start = m.end()
    nxt = _NEXT_SECTION_RE.search(detail_text, start)
    end = nxt.start() if nxt else min(len(detail_text), start + 4000)
    return detail_text[start:end].strip()


def parse_min_quals_floor(detail_html_or_text: str) -> Optional[int]:
    """Parse the YOE FLOOR from a Google JD's Minimum-qualifications block.

    EXACT rule (Cyrus 2026-06-08):
      - Scope to the 'Minimum qualifications' block ONLY (heading -> next
        section heading).
      - Within that block find ALL '<N> years'/'<N>+ years'/'<N> yrs'
        mentions and return the MAXIMUM N. ("8 years of PM" + "3 years
        technical" => 8.)
      - IGNORE 'Preferred qualifications' entirely.
      - No year in the min block => None (caller keeps exp:unstated).

    Accepts either raw detail HTML (double-escaped, as fetched) OR already
    tag-stripped text; it decodes/strips defensively.
    """
    if not detail_html_or_text:
        return None
    text = detail_html_or_text
    # If it still looks like HTML (tags or \u003c escapes), decode it.
    if "<" in text or "\\u003c" in text or "\u003c" in text:
        text = _decode_google_html(text)
    block = extract_min_quals_block(text)
    if not block:
        return None
    nums = [int(x) for x in _YEARS_RE.findall(block)]
    if not nums:
        return None
    return max(nums)


def _exp_required_from_floor(floor: Optional[int]) -> str:
    """Map a parsed floor -> exp_required string core.py can parse.

    core._EXP_NUM_RE is r'exp:(\\d+)(?:-(\\d+))?', so 'exp:{N}+yrs' parses to
    lower-bound N. None => 'exp:unstated' (keep).
    """
    if floor is None:
        return "exp:unstated"
    return f"exp:{floor}+yrs"


# ---------------------------------------------------------------------------
# Posting-date scrape (best-effort).
# ---------------------------------------------------------------------------
# Cyrus 2026-06-08 wants the sheet's Google section ordered freshest-first.
# We try to scrape a real posting/updated date from the JD detail page, but
# DO NOT fake one. As verified live on 2026-06-08, Google's JD detail pages
# carry NO JSON-LD `datePosted`, no human "Posted"/"Updated" label, and no
# ISO date attributable to a posting date (only unattributable epoch
# timestamps in the SPA blob). So this returns "" in practice and the sheet
# falls back to first_seen DESC. The probe stays here so that if Google ever
# adds a labelled date we pick it up automatically.
_JSONLD_DATEPOSTED_RE = re.compile(r'"datePosted"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})', re.I)
_POSTED_LABEL_RE = re.compile(
    r"(?:posted|published|updated)(?:\s+on)?[:\s]+([0-9]{4}-[0-9]{2}-[0-9]{2})", re.I)


def scrape_posted_date(raw_html: str) -> str:
    """Best-effort ISO posting date from a Google JD page. "" if none found.

    Only accepts an EXPLICITLY labelled date (JSON-LD datePosted, or a
    Posted/Published/Updated label). Never guesses from bare epoch ints.
    """
    if not raw_html:
        return ""
    m = _JSONLD_DATEPOSTED_RE.search(raw_html)
    if m:
        return m.group(1)
    decoded = _decode_google_html(raw_html)
    m = _POSTED_LABEL_RE.search(decoded)
    if m:
        return m.group(1)
    return ""


def _fetch_detail(job_id: str) -> tuple[Optional[int], str]:
    """Fetch one role's detail page; return (yoe_floor_or_None, posted_iso).

    Wrapped by caller in the politeness loop. Raises nothing on HTTP/parse
    trouble for the YOE side — returns (None, "") so the role stays unstated.
    """
    url = _public_url(job_id, "")
    r = http_get(url, timeout=_DETAIL_TIMEOUT)
    if r.status_code != 200:
        return None, ""
    raw = r.text
    # NB: the literal "Job not found." string is bundled into EVERY page as a
    # client-side i18n template, so we can't use its mere presence to detect a
    # dead role. A genuinely removed role returns a SMALL page with no
    # qualifications content. Treat 'no Minimum-qualifications heading at all'
    # as not-found/unparseable -> unstated (keep).
    if "inimum qualifications" not in raw:
        return None, ""
    floor = parse_min_quals_floor(raw)
    posted = scrape_posted_date(raw)
    return floor, posted


def _fetch_page(term: str, page: int) -> list:
    """Return the raw `ds:1` jobs array for one (term, page), or []."""
    params = {"q": term, "page": page}
    r = http_get(SEARCH_URL, params=params, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(f"google HTTP {r.status_code} (page={page}, term='{term}')")
    m = _DS1_RE.search(r.text)
    if not m:
        return []
    try:
        ds1 = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"google ds:1 parse failed (page={page}, term='{term}'): {e}") from e
    # Shape: [jobs_list, None, total_results, page_size]
    if not ds1 or not isinstance(ds1[0], list):
        return []
    return ds1[0]


def _location_string(loc_field) -> str:
    """`loc_field` is field [9] in the record: a list of [display, addrs, city, zip, state, country]."""
    if not loc_field or not isinstance(loc_field, list):
        return ""
    parts = []
    for slot in loc_field:
        if isinstance(slot, list) and slot:
            disp = slot[0]
            if isinstance(disp, str):
                parts.append(disp)
        elif isinstance(slot, str):
            parts.append(slot)
    # Dedup, preserve order
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return "; ".join(out)


def _public_url(job_id: str, title: str) -> str:
    # The deep-link Cyrus's tracker stores. The signin URL in the record
    # is a tokenized apply link that expires; the canonical results-page
    # URL is stable.
    return f"https://www.google.com/about/careers/applications/jobs/results/{job_id}"


def fetch(company: str = "Google", slug: str = "", fetch_details: bool = True, **_) -> List[Role]:
    """Discover Google roles. `fetch_details` (default True) controls whether
    we fetch each role's JD detail page to parse a real Min-quals YOE floor
    + best-effort posting date. Set False to skip (search-only) for speed.
    """
    seen: dict[str, dict] = {}
    for term in SEARCH_TERMS:
        try:
            for page in range(1, MAX_PAGES + 1):
                jobs = _fetch_page(term, page)
                if not jobs:
                    break
                new_this_page = 0
                for j in jobs:
                    if not isinstance(j, list) or len(j) < 10:
                        continue
                    jid = j[0]
                    if not isinstance(jid, str) or jid in seen:
                        continue
                    seen[jid] = {
                        "id": jid,
                        "title": j[1] if isinstance(j[1], str) else "",
                        "loc": _location_string(j[9]) if len(j) > 9 else "",
                    }
                    new_this_page += 1
                # If the page returned only roles we already had, stop
                # paginating this term — Google's pagination loops back.
                if new_this_page == 0:
                    break
                if len(jobs) < 20:
                    break
        except RuntimeError as e:
            print(f"  [google] '{term}' failed: {e}")

    out: List[Role] = []
    detail_count = 0
    for jid, j in seen.items():
        exp_required = "exp:unstated"  # default: unstated -> keep
        posted_at = ""
        if fetch_details and detail_count < MAX_DETAIL_FETCHES:
            # Be polite: small jitter between detail fetches.
            lo, hi = DETAIL_FETCH_DELAY
            time.sleep(random.uniform(lo, hi))
            detail_count += 1
            try:
                floor, posted = _fetch_detail(jid)
                exp_required = _exp_required_from_floor(floor)
                posted_at = posted or ""
            except Exception as e:  # noqa: BLE001 — one bad page must not crash the crawl
                print(f"  [google] detail fetch failed for {jid} ({j.get('title','')!r}): {e}")
                exp_required = "exp:unstated"
                posted_at = ""
        out.append(Role(
            company="Google",
            title=j["title"],
            location=j["loc"],
            exp_required=exp_required,
            url=_public_url(jid, j["title"]),
            posted_at=posted_at,   # "" when Google exposes no labelled date (the norm)
            source="google",
            raw={"id": jid, "manual_apply_only": True},
        ))
    return out
