"""Meta Careers — GraphQL-based job discovery adapter.

Meta uses Facebook Relay/GraphQL internally. We replay the exact request the
browser makes when loading the job-search page (captured via Playwright network
intercept 2026-06-16). The endpoint is:

  POST https://www.metacareers.com/graphql
  doc_id: 27506805582236862  (CareersJobSearchResultsDataQuery)

No auth / DTSG token needed for the search query — __user=0 + __a=1 is enough
for the unauthenticated guest path.

Note: if Meta rotates the doc_id this adapter will 400. The fallback is to
scrape the search page HTML and extract anchor hrefs. Both paths are implemented.
"""
from __future__ import annotations
from typing import List, Any
import re, json, time, random
try:
    from core import Role, http_get
    import requests as _requests
except ImportError:
    from typing import NamedTuple
    class Role(NamedTuple):  # type: ignore
        company: str; title: str; location: str; exp_required: str
        url: str; posted_at: str; source: str; raw: Any

GRAPHQL_URL = "https://www.metacareers.com/graphql"

# Captured 2026-06-16 from Playwright network intercept. Increment __req each session.
# doc_id = CareersJobSearchResultsDataQuery
SEARCH_DOC_ID = "27506805582236862"

# CDP endpoint for Playwright-based fallback (needs browser cookies/session)
# Chrome on this VM binds to IPv4 127.0.0.1:18800 (checked 2026-06-16)
CDP_DEFAULT = "http://127.0.0.1:18800"

# Response path: data.job_search_with_featured_jobs.all_jobs (confirmed 2026-06-16)
# OR data.job_search.jobs.edges[].node (alternate Relay shape)
RESPONSE_KEYS = [
    lambda d: d.get("data", {}).get("job_search_with_featured_jobs", {}).get("all_jobs", []),
    lambda d: [e.get("node", {}) for e in d.get("data", {}).get("job_search", {}).get("jobs", {}).get("edges", []) if e.get("node")],
]

# Typical browser headers to avoid bot-detection
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.metacareers.com",
    "Referer": "https://www.metacareers.com/jobsearch/",
    "X-FB-Friendly-Name": "CareersJobSearchResultsDataQuery",
}

# Teams we want (classifier-aligned)
_PM_TPM_TEAMS = ["Product Management", "Technical Program Management"]
_SE_TEAMS = ["Sales & Marketing"]  # SE/SA often appear under sales


def _build_payload(teams: list[str]) -> str:
    """Build application/x-www-form-urlencoded body matching what the browser sends."""
    from urllib.parse import urlencode
    variables = {
        "search_input": {
            "q": None,
            "divisions": [],
            "offices": [],
            "roles": [],
            "leadership_levels": [],
            "saved_jobs": [],
            "saved_searches": [],
            "sub_teams": [],
            "teams": teams,
            "is_leadership": False,
            "is_remote_only": False,
            "sort_by_new": False,
            "results_per_page": None,
        },
        "viewasUserID": None,
        "isLoggedIn": False,
    }
    req_num = random.randint(2, 9)
    return urlencode({
        "av": "0",
        "__user": "0",
        "__a": "1",
        "__req": str(req_num),
        "__hs": "20621.HYP:comet_plat_default_pkg.2.1...0",
        "dpr": "1",
        "__ccg": "EXCELLENT",
        "__rev": "1041623636",
        "__comet_req": "31",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "CareersJobSearchResultsDataQuery",
        "server_timestamps": "true",
        "variables": json.dumps(variables),
        "doc_id": SEARCH_DOC_ID,
    })


def _graphql_search(teams: list[str], cdp: str | None = None) -> list[dict]:
    """Call the Meta GraphQL search and return raw job dicts (or [] on failure).

    Meta's /graphql endpoint requires browser session cookies — direct HTTP fails
    (returns 400). Strategy: use Playwright CDP to execute the fetch() call inside
    the existing browser session, which has the correct cookies.
    Falls back to HTTP requests if cdp is None and browser is unavailable.
    """
    import os
    cdp = cdp or os.environ.get("JOBSEARCH_CDP", CDP_DEFAULT)
    variables = {
        "search_input": {
            "q": None, "divisions": [], "offices": [], "roles": [],
            "leadership_levels": [], "saved_jobs": [], "saved_searches": [],
            "sub_teams": [], "teams": teams,
            "is_leadership": False, "is_remote_only": False,
            "sort_by_new": False, "results_per_page": None,
        },
        "viewasUserID": None,
        "isLoggedIn": False,
    }
    params = {
        "av": "0", "__user": "0", "__a": "1", "__req": str(random.randint(2, 9)),
        "__hs": "20621.HYP:comet_plat_default_pkg.2.1...0", "dpr": "1",
        "__ccg": "EXCELLENT", "__rev": "1041623636", "__comet_req": "31",
        "lsd": "AdRXxBwXsBAnYbSj6V6PEdwY80Y",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "CareersJobSearchResultsDataQuery",
        "server_timestamps": "true",
        "variables": json.dumps(variables),
        "doc_id": SEARCH_DOC_ID,
    }
    # Build URLSearchParams JS string
    qs_pairs = ", ".join(f"[{json.dumps(k)}, {json.dumps(v)}]" for k, v in params.items())
    js_fetch = f"""
    async () => {{
        const params = new URLSearchParams([{qs_pairs}]);
        const r = await fetch('/graphql', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: params.toString()
        }});
        if (!r.ok) return JSON.stringify({{error: r.status}});
        return await r.text();
    }}
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            # Ensure we are on metacareers.com so relative /graphql resolves correctly
            page = None
            for pg in ctx.pages:
                if "metacareers.com" in pg.url:
                    page = pg
                    break
            if page is None:
                page = ctx.new_page()
                page.goto("https://www.metacareers.com/jobsearch/", timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(3)
            text = page.evaluate(js_fetch)
        if not text or isinstance(text, dict):
            return []
        text = text.strip()
        if text.startswith("for (;;);"):
            text = text[len("for (;;);"):]
        data = json.loads(text)
        for extractor in RESPONSE_KEYS:
            jobs = extractor(data)
            if jobs:
                return jobs
        return []
    except Exception as ex:
        # Fallback: plain HTTP (usually fails for unauthenticated requests from server)
        try:
            import requests
            payload = _build_payload(teams)
            r = requests.post(GRAPHQL_URL, data=payload, headers=_HEADERS, timeout=30)
            if r.status_code != 200:
                return []
            text = r.text.strip()
            if text.startswith("for (;;);"):
                text = text[len("for (;;);"):]
            data = json.loads(text)
            for extractor in RESPONSE_KEYS:
                jobs = extractor(data)
                if jobs:
                    return jobs
        except Exception:
            pass
        return []


def _scrape_search_page(teams: list[str]) -> list[dict]:
    """
    Fallback: load the search page (without q= text query so we get results)
    and parse job card anchors from the rendered HTML.
    Only works if the page SSR embeds job data; otherwise returns [].
    """
    from urllib.parse import urlencode
    import requests
    params = {"teams[0]": teams[0]}
    for i, t in enumerate(teams[1:], 1):
        params[f"teams[{i}]"] = t
    url = "https://www.metacareers.com/jobsearch/?" + urlencode(params)
    hdrs = {
        "User-Agent": _HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        r = requests.get(url, headers=hdrs, timeout=30)
        html = r.text
    except Exception:
        return []
    # Try extracting job IDs from anchor hrefs
    hrefs = re.findall(r'/profile/job_details/(\d+)', html)
    # Try extracting job titles from nearby text (rough heuristic)
    if hrefs:
        return [{"id": jid, "title": "", "locations": []} for jid in dict.fromkeys(hrefs)]
    return []


_NON_US_KEYWORDS = [
    "brazil", "uk", "ireland", "singapore", "japan", "australia", "canada",
    "germany", "france", "india", "china", "israel", "hong kong", "mexico",
    "poland", "netherlands", "sweden", "denmark", "spain", "italy",
    "south korea", "korea", "apac", "emea", "latam"
]


def _is_us_role(j: dict) -> bool:
    """Return True if the job has at least one US location (or Remote, US)."""
    locs = j.get("locations", [])
    for loc in locs:
        loc_str = (loc.get("name", str(loc)) if isinstance(loc, dict) else str(loc)).lower()
        # Check for US states/cities or Remote US
        if "remote, us" in loc_str or ", wa" in loc_str or ", ca" in loc_str or \
           ", ny" in loc_str or ", tx" in loc_str or ", ma" in loc_str or \
           ", dc" in loc_str or ", or" in loc_str or ", co" in loc_str or \
           ", il" in loc_str or ", ga" in loc_str or ", fl" in loc_str or \
           ", la" in loc_str or ", oh" in loc_str or ", in" in loc_str or \
           ", ut" in loc_str or ", id" in loc_str or ", sc" in loc_str or \
           ", nc" in loc_str or ", al" in loc_str or ", ok" in loc_str:
            return True
        # Reject obvious non-US
        if any(nk in loc_str for nk in _NON_US_KEYWORDS):
            continue
    # If no locations match US pattern but none are explicitly non-US, keep
    if not locs:
        return True  # no location info = keep
    # If all locations are non-US, drop
    all_non_us = all(
        any(nk in (loc.get("name", str(loc)) if isinstance(loc, dict) else str(loc)).lower()
            for nk in _NON_US_KEYWORDS)
        for loc in locs
    )
    return not all_non_us


def _job_to_role(j: dict) -> "Role":
    jid = str(j.get("id", ""))
    title = j.get("title", j.get("job_title", ""))
    raw_locs = j.get("locations", j.get("location_list", []))
    loc_strs = []
    for loc in raw_locs[:3]:
        if isinstance(loc, dict):
            loc_strs.append(loc.get("name", loc.get("city", str(loc))))
        else:
            loc_strs.append(str(loc))
    location = ", ".join(loc_strs)
    apply_url = f"https://www.metacareers.com/profile/create_application/{jid}/"
    return Role(
        company="Meta",
        title=title,
        location=location,
        exp_required="exp:unstated",
        url=apply_url,
        posted_at="",
        source="meta",
        raw={"id": jid, "job_details_url": f"https://www.metacareers.com/profile/job_details/{jid}/"},
    )


def fetch(company: str = "Meta", slug: str = "", teams: list[str] | None = None, cdp: str | None = None, **_) -> List[Role]:
    """Main adapter entry point. Returns list of Role objects."""
    all_teams = teams or (_PM_TPM_TEAMS + _SE_TEAMS)
    # Batch into two queries: PM/TPM and SE separately to avoid large result sets
    batch_groups = [_PM_TPM_TEAMS, _SE_TEAMS] if not teams else [all_teams]

    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    for group in batch_groups:
        jobs = _graphql_search(group, cdp=cdp)
        if not jobs:
            # Fallback to scrape
            jobs = _scrape_search_page(group)
        for j in jobs:
            jid = str(j.get("id", ""))
            if jid and jid not in seen_ids and _is_us_role(j):
                seen_ids.add(jid)
                all_jobs.append(j)
        time.sleep(0.5)  # gentle rate limit between batches

    return [_job_to_role(j) for j in all_jobs]


if __name__ == "__main__":
    # Quick test
    print("Fetching Meta PM/TPM/SE jobs via GraphQL...")
    roles = fetch()
    print(f"Found {len(roles)} roles")
    for r in roles[:10]:
        print(f"  [{r.raw.get('id')}] {r.title} | {r.location}")
        print(f"    Apply: {r.url}")
