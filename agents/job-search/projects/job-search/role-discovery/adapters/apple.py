"""Apple Jobs scraper.

The official `https://jobs.apple.com/api/role/search` endpoint started returning
404 in early 2026. The public search page still works, embeds posting data
inside an HTML-escaped JSON blob, and supports `page=N` pagination. We scrape
that blob.

Strategy:
1. GET https://jobs.apple.com/en-us/search?page=N&location=united-states-USA&sort=newest
2. Pull positionId / postingTitle / postDateInGMT / transformedPostingTitle / location / team
   from the embedded escaped JSON.
3. Walk pages until a page yields no NEW position ids.
4. Filter titles to PM / TPM / SE / Solutions / Customer-Engineer adjacencies.

This intentionally lives in the same `adapters/` folder so `run.py` picks it up
as part of the existing weekly cron — no separate sweep script.
"""
from __future__ import annotations
import re, html as _html, time
from typing import List
from core import Role, http_get, parse_experience


SEARCH_URL = "https://jobs.apple.com/en-us/search"
HEADERS = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}

# Keep this generous — we filter by these patterns after fetching.
TITLE_KEEP = re.compile(
    r"\b(product\s+manager|product\s+management|technical\s+program\s+manager|tpm|"
    r"program\s+manager|solutions?\s+(engineer|architect)|sales\s+engineer|"
    r"customer\s+engineer|partner\s+engineer|forward[-\s]?deployed|"
    r"developer\s+(advocate|relations))\b",
    re.I,
)
INTERN_RE = re.compile(r"\b(intern|interns|internship|co[-\s]?op)\b", re.I)

# Each posting object looks like (escaped JSON inside the page):
#   ..."positionId":"200662429",..."postingTitle":"Senior ...",..."postDateInGMT":"2026-05-08T...","transformedPostingTitle":"slug",..."team":"...
# We extract per-field arrays and zip by index. If page structure changes and the
# arrays misalign, we abort that page rather than fabricate matches.

PAT_ID = re.compile(r'\\"positionId\\":\\"(\d+)\\"')
PAT_DATE = re.compile(r'\\"postDateInGMT\\":\\"([^\\]+)\\"')
PAT_TITLE = re.compile(r'\\"postingTitle\\":\\"((?:[^\\]|\\.)+?)\\"')
PAT_SLUG = re.compile(r'\\"transformedPostingTitle\\":\\"([^\\]+)\\"')
# Apple stores team as a nested object: "team":{"teamCode":"APPST"}.
PAT_TEAM_CODE = re.compile(r'\\"teamCode\\":\\"([^\\]+)\\"')
# The compound id is e.g. "200660132-3247" — positionId + 4-digit team-view discriminator.
# Apple's URLs use this exact form between /details/ and /<slug>.
PAT_COMPOUND_ID = re.compile(r'\\"id\\":\\"(\d+-\d+)\\"')
PAT_MIN_QUALS = re.compile(r'\\"minimumQualifications\\":\\"((?:[^\\]|\\.){0,2000}?)\\"')
PAT_PREF_QUALS = re.compile(r'\\"preferredQualifications\\":\\"((?:[^\\]|\\.){0,2000}?)\\"')
PAT_DESCRIPTION = re.compile(r'\\"description\\":\\"((?:[^\\]|\\.){0,4000}?)\\"')


def _decode_title(s: str) -> str:
    # The blob uses backslash-escaped JSON, so \\u0026 → &, \\\" → ", etc.
    s = s.replace('\\u0026', '&').replace('\\u2019', '\u2019').replace('\\u2013', '\u2013')
    s = s.replace('\\"', '"').replace("\\\\", "\\")
    return _html.unescape(s)


def _fetch_page(page: int) -> str:
    params = {
        "page": str(page),
        "location": "united-states-USA",
        "sort": "newest",
    }
    r = http_get(SEARCH_URL, headers=HEADERS, params=params, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(f"apple HTTP {r.status_code} (page={page})")
    return r.text


def _parse_page(html_text: str) -> list[dict]:
    ids = PAT_ID.findall(html_text)
    dates = PAT_DATE.findall(html_text)
    titles = PAT_TITLE.findall(html_text)
    slugs = PAT_SLUG.findall(html_text)
    teams = PAT_TEAM_CODE.findall(html_text)
    compound_ids = PAT_COMPOUND_ID.findall(html_text)
    # ids/dates/titles/slugs/teams must align 1:1 — Apple emits exactly one of each per posting.
    # compound_ids may be short by 1 (e.g. PIPE-/managed pipeline records use a different id form),
    # so we map by positionId prefix instead of zipping by index.
    n = min(len(ids), len(dates), len(titles), len(slugs), len(teams))
    if n == 0:
        return []
    if not (len(ids) == len(dates) == len(titles) == len(slugs) == len(teams)):
        print(f"  [apple] field misalign on page (ids={len(ids)} dates={len(dates)} titles={len(titles)} slugs={len(slugs)} teams={len(teams)})")
        return []
    disc_by_pid = {}
    for cid in compound_ids:
        pid = cid.split("-", 1)[0]
        disc_by_pid.setdefault(pid, cid.split("-", 1)[1])
    out = []
    for i in range(n):
        pid = ids[i]
        out.append({
            "positionId": pid,
            "postDateInGMT": dates[i],
            "postingTitle": _decode_title(titles[i]),
            "slug": slugs[i],
            "team": teams[i],
            "discriminator": disc_by_pid.get(pid, "0836"),  # fallback; Apple ignores it for routing
        })
    return out


def fetch(company: str = "Apple", slug: str = "", **_) -> List[Role]:
    seen: dict[str, dict] = {}
    consecutive_no_new = 0
    page = 1
    MAX_PAGES = 60  # ~1200 postings ceiling
    while page <= MAX_PAGES:
        try:
            html_text = _fetch_page(page)
        except RuntimeError as e:
            print(f"  [apple] page {page} failed: {e}")
            break
        items = _parse_page(html_text)
        if not items:
            break
        new = 0
        for it in items:
            pid = it["positionId"]
            if pid in seen:
                continue
            seen[pid] = it
            new += 1
        if new == 0:
            consecutive_no_new += 1
            if consecutive_no_new >= 2:
                break  # we've seen this page's IDs already; reached the end
        else:
            consecutive_no_new = 0
        page += 1
        time.sleep(0.4)  # be polite

    # First pass: filter to qualifying titles
    candidates = []
    for pid, j in seen.items():
        title = j["postingTitle"]
        if INTERN_RE.search(title):
            continue
        if not TITLE_KEEP.search(title):
            continue
        candidates.append((pid, j))
    print(f"  [apple] {len(candidates)} title-qualifying postings; fetching JD detail for each to extract YOE...")

    out: List[Role] = []
    for idx, (pid, j) in enumerate(candidates):
        team = j.get("team") or "SFTWR"
        slug = j.get("slug") or "role"
        disc = j.get("discriminator") or "0836"
        url = f"https://jobs.apple.com/en-us/details/{pid}-{disc}/{slug}?team={team}"
        exp_required = ""
        try:
            r = http_get(url, headers=HEADERS, timeout=45)
            if r.status_code == 200:
                t = r.text
                blob = " ".join(
                    _decode_title(m.group(1))
                    for m in (PAT_MIN_QUALS.search(t),
                              PAT_PREF_QUALS.search(t),
                              PAT_DESCRIPTION.search(t))
                    if m
                )
                if blob.strip():
                    exp_required = parse_experience(blob)
        except Exception as e:
            print(f"  [apple] detail fetch failed for {pid}: {e}")
        time.sleep(0.25)  # be polite
        out.append(Role(
            company="Apple",
            title=j["postingTitle"],
            location="United States",
            exp_required=exp_required,  # filled from JD detail page when available
            url=url,
            posted_at=(j.get("postDateInGMT") or "")[:10],
            source="apple",
            raw=j,
        ))
    print(f"  [apple] kept {len(out)} matching roles (from {len(seen)} total US postings)")
    return out
