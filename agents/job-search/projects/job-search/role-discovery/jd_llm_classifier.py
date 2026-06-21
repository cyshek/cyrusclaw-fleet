#!/usr/bin/env python3
"""JD-level deterministic classifier (NO LLM, simplified 2026-05-29).

For each open role missing `llm_classified_at`:
  1. Fetch JD via the appropriate path (greenhouse/ashby/lever/workday/apple/linkedin/generic).
  2. Cache JD text under role-discovery/jd_cache/<source_key>.txt.
  3. Regex-extract YOE from JD body.
  4. Apply simplified skip gates (see decide_skip below).
  5. Stamp llm_classified_at + llm_yoe_required on the row.

Simplified gate logic (Cyrus 2026-05-29):
  GATE 1 (YOE-from-JD): regex-scan JD body for "N year(s) [of] experience".
    If a number >= YOE_THRESHOLD (=6) is found -> skip with 'yoe-threshold'.
  GATE 2 (title fallback, ONLY when JD had no YOE): title-keyword blocklist
    (Senior / Staff / Principal / Director / Head / VP / Chief / Lead / etc.).
    Match -> skip with 'senior-title'.
  GATE 3 (independent): non-US location signal in JD body or stored location
    field. Flag: 'non-us'.

The LLM call is RETIRED. The legacy DB columns (llm_is_people_manager,
llm_seniority, llm_fit_score, llm_reason) are preserved for backward compat
with retro_apply_new_classifier_gates.py / backfill_stripe_exp.py /
render_xlsx.py / sequential_burndown.py, but this classifier no longer
writes to them and no longer reads them for the skip decision.

CLI:
    jd_llm_classifier.py [--limit N] [--role-id ID] [--dry-run] [--force]

Errors logged to applications/_classifier-errors-<stamp>.json. Never
re-classifies rows where llm_classified_at IS NOT NULL unless --force.
Never touches applied_by/applied_on.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DB = PROJ / "tracker.db"
JD_CACHE = HERE / "jd_cache"
JD_CACHE.mkdir(exist_ok=True)
ERR_DIR = PROJ / "applications"

UA = "job-search-agent/1.0 (jd-classifier)"
HTTP_TIMEOUT = 25


# ---------------------------------------------------------------------------
# JD fetchers
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "meta", "link"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in ("br", "p", "li", "div", "section"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in ("p", "li", "div", "section"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        # collapse runs of whitespace and blank lines
        lines = [l.strip() for l in raw.splitlines()]
        return "\n".join(l for l in lines if l)


def html_to_text(html: str) -> str:
    p = _HTMLTextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.text()


def _http_get(url: str, *, headers: Optional[dict] = None) -> requests.Response:
    h = {"User-Agent": UA, "Accept": "text/html,application/json"}
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, timeout=HTTP_TIMEOUT, allow_redirects=True)
    return r


# --- ATS-specific fetchers ---

def fetch_jd_greenhouse(url: str) -> str:
    # url like https://boards.greenhouse.io/<org>/jobs/<id>
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=|boards/)?([a-z0-9_-]+)/jobs/(\d+)", url)
    if not m:
        # try ?for=org&token=id
        m2 = re.search(r"for=([a-z0-9_-]+).*token=(\d+)", url)
        if m2:
            org, jid = m2.group(1), m2.group(2)
        else:
            raise ValueError(f"can't parse greenhouse URL: {url}")
    else:
        org, jid = m.group(1), m.group(2)
    api = f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs/{jid}"
    r = _http_get(api, headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    title = data.get("title", "")
    content_html = data.get("content", "")
    return f"# {title}\n\n" + html_to_text(content_html)


# --- Greenhouse-by-job-id fallback ------------------------------------------
# MANY employer career-site wrappers (careers.datadoghq.com, www.okta.com,
# www.fanduel.careers, www.credera.com, www.dealpath.com, www.harness.io, ...)
# host a Greenhouse-backed posting but on their OWN domain, carrying the GH job
# id only as a ?gh_jid=<id> query param. The host is NOT *.greenhouse.io, so the
# normal greenhouse dispatch misses them and they fall to fetch_jd_generic,
# which returns 0 chars (JS-rendered shells) -> "JD body too short" -> the row
# can NEVER be classified and is stuck in the open queue forever.
#
# Fix: when a URL carries gh_jid, resolve the JD straight off the Greenhouse
# public boards API. The only unknown is the org board TOKEN; we derive a small
# ordered set of candidate tokens from the company name and try each until one
# returns the posting (matching id confirms it). Added 2026-06-08 (autonomous
# tick) to unblock the freshly-discovered gh_jid wrapper cohort.

_GH_JID_RX = re.compile(r"[?&]gh_jid=(\d{4,})", re.I)


def _gh_jid_from_url(url: str) -> Optional[str]:
    """Return the gh_jid query-param value, or None."""
    if not url:
        return None
    m = _GH_JID_RX.search(url)
    return m.group(1) if m else None


def _gh_token_candidates(company: Optional[str], url: str) -> list[str]:
    """Ordered, de-duplicated candidate Greenhouse board tokens.

    Derived from the company name (the GH token is almost always the company
    name lowercased, space/punct-stripped) plus a host-label fallback. Pure
    string work; no network.
    """
    cands: list[str] = []

    def _add(tok: Optional[str]) -> None:
        if not tok:
            return
        tok = tok.strip().lower()
        if tok and tok not in cands:
            cands.append(tok)

    name = (company or "").strip().lower()
    if name:
        compact = re.sub(r"[^a-z0-9]", "", name)           # "data dog inc" -> "datadoginc"
        _add(compact)
        # drop a single trailing corp suffix (inc/llc/co/corp/ltd/group)
        stripped = re.sub(r"(inc|llc|co|corp|ltd|group|labs|ai|hq)$", "", compact)
        _add(stripped)
        first = re.sub(r"[^a-z0-9]", "", name.split()[0]) if name.split() else ""
        _add(first)
        _add(re.sub(r"[^a-z0-9]", "", name).replace(" ", ""))
    # Host label fallback: careers.datadoghq.com -> datadoghq -> datadog
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    parts = [p for p in host.split(".") if p not in ("www", "careers", "jobs", "com", "io", "net", "co", "careers")]
    if parts:
        label = re.sub(r"[^a-z0-9]", "", parts[0])
        _add(label)
        _add(re.sub(r"(hq|inc|labs|ai)$", "", label))
    return cands


def fetch_jd_greenhouse_by_jid(url: str, company: Optional[str] = None) -> str:
    """Resolve a gh_jid-carrying wrapper URL via the GH boards API.

    Tries each candidate org token; the first board that returns the matching
    job id wins. Raises if no candidate resolves (caller records a fetch error
    exactly as before, so behaviour is unchanged for genuinely unresolvable
    rows).
    """
    jid = _gh_jid_from_url(url)
    if not jid:
        raise ValueError(f"no gh_jid in url: {url}")
    tokens = _gh_token_candidates(company, url)
    if not tokens:
        raise ValueError(f"no candidate GH token for company={company!r}")
    last_err: Optional[str] = None
    for tok in tokens:
        api = f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{jid}"
        try:
            r = _http_get(api, headers={"Accept": "application/json"})
        except Exception as e:  # pragma: no cover - network hiccup
            last_err = str(e)
            continue
        if r.status_code != 200:
            last_err = f"{tok}->HTTP {r.status_code}"
            continue
        try:
            data = r.json()
        except Exception as e:
            last_err = f"{tok}->bad json: {e}"
            continue
        # Confirm it's the right posting (id match guards against a token
        # collision returning some other org's job).
        if str(data.get("id")) != str(jid):
            last_err = f"{tok}->id mismatch ({data.get('id')})"
            continue
        title = data.get("title", "")
        content_html = data.get("content", "")
        return f"# {title}\n\n" + html_to_text(content_html)
    raise ValueError(f"gh_jid {jid} unresolved across tokens {tokens} ({last_err})")


# --- Eightfold (explore.jobs.<co>.net) --------------------------------------
# Netflix (and other Eightfold tenants) host postings at
#   explore.jobs.netflix.net/careers/job/<positionId>
# which is a JS-rendered shell (generic strip -> 0 chars). The clean JD lives
# in the Eightfold public position API:
#   https://explore.jobs.<tenant>.net/api/apply/v2/jobs/<positionId>?domain=<co>
# returning JSON with job_description (HTML) + name. Added 2026-06-08 to unblock
# the 35 freshly-discovered Netflix Eightfold rows (all stuck unclassified).

_EIGHTFOLD_HOST_RX = re.compile(r"^explore\.jobs\.([a-z0-9-]+)\.net$", re.I)
_EIGHTFOLD_JOB_RX = re.compile(r"/careers/job/(\d{4,})", re.I)


def _parse_eightfold_url(url: str) -> Optional[tuple[str, str]]:
    """Return (tenant, position_id) for an Eightfold careers URL, else None."""
    try:
        p = urlparse(url)
    except Exception:
        return None
    host = (p.hostname or "").lower()
    hm = _EIGHTFOLD_HOST_RX.match(host)
    if not hm:
        return None
    jm = _EIGHTFOLD_JOB_RX.search(p.path or "")
    if not jm:
        return None
    return hm.group(1), jm.group(1)


def fetch_jd_eightfold(url: str) -> str:
    """Eightfold-hosted careers (explore.jobs.<tenant>.net/careers/job/<id>)."""
    parsed = _parse_eightfold_url(url)
    if not parsed:
        raise ValueError(f"can't parse eightfold URL: {url}")
    tenant, pid = parsed
    # domain param is the tenant's apex (netflix -> netflix.com); Eightfold uses
    # it to scope the position lookup.
    api = (f"https://explore.jobs.{tenant}.net/api/apply/v2/jobs/{pid}"
           f"?domain={tenant}.com")
    r = _http_get(api, headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    title = data.get("name") or data.get("posting_name") or ""
    body_html = data.get("job_description") or data.get("custom_JD") or ""
    loc = data.get("location") or ""
    return f"# {title}\n{loc}\n\n" + html_to_text(body_html)


def fetch_jd_ashby(url: str) -> str:
    # https://jobs.ashbyhq.com/<org>/<jid>
    m = re.search(r"ashbyhq\.com/([^/]+)/([a-f0-9-]+)", url)
    if not m:
        raise ValueError(f"can't parse ashby URL: {url}")
    org, jid = m.group(1), m.group(2)
    api = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true"
    r = _http_get(api, headers={"Accept": "application/json"})
    r.raise_for_status()
    for job in (r.json().get("jobs") or []):
        if job.get("id") == jid:
            title = job.get("title", "")
            desc_html = job.get("descriptionHtml") or job.get("descriptionPlain") or ""
            txt = html_to_text(desc_html) if "<" in desc_html else desc_html
            return f"# {title}\n\n{txt}"
    raise RuntimeError(f"ashby job {jid} not found on board {org}")


def fetch_jd_lever(url: str) -> str:
    # https://jobs.lever.co/<org>/<uuid>
    m = re.search(r"lever\.co/([^/]+)/([a-f0-9-]+)", url)
    if not m:
        raise ValueError(f"can't parse lever URL: {url}")
    org, jid = m.group(1), m.group(2)
    api = f"https://api.lever.co/v0/postings/{org}/{jid}?mode=json"
    r = _http_get(api, headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    parts = [f"# {data.get('text','')}", data.get("descriptionPlain", "")]
    for lst in (data.get("lists") or []):
        if isinstance(lst, dict):
            parts.append("\n## " + (lst.get("text") or ""))
            parts.append(html_to_text(lst.get("content") or ""))
    extra = data.get("additionalPlain") or ""
    if extra:
        parts.append("\n" + extra)
    return "\n".join(p for p in parts if p)


def fetch_jd_workday(url: str) -> str:
    # Reuse parse_workday_url + CXS endpoint.
    sys.path.insert(0, str(HERE))
    from workday_dryrun import parse_workday_url, fetch_workday_job  # type: ignore
    parts = parse_workday_url(url)
    info = fetch_workday_job(parts, quiet=True)
    if info.get("maintenance_mode"):
        raise RuntimeError("workday maintenance_mode")
    title = info.get("title", "")
    jd = info.get("jd_text") or html_to_text(info.get("jd_html") or "")
    return f"# {title}\n\n{jd}"


_APPLE_RX = {
    "min": re.compile(r'\\"minimumQualifications\\":\\"((?:[^\\]|\\.){0,3000}?)\\"'),
    "pref": re.compile(r'\\"preferredQualifications\\":\\"((?:[^\\]|\\.){0,3000}?)\\"'),
    "desc": re.compile(r'\\"description\\":\\"((?:[^\\]|\\.){0,5000}?)\\"'),
    "title": re.compile(r'\\"postingTitle\\":\\"((?:[^\\]|\\.){0,300}?)\\"'),
}


def _apple_decode(s: str) -> str:
    # The HTML embeds JSON inside an attribute, so quotes are double-escaped.
    # First decode the JSON-string escapes (\\n -> \n, \\" -> "), then strip HTML.
    try:
        decoded = bytes(s, "utf-8").decode("unicode_escape")
    except Exception:
        decoded = s
    decoded = decoded.replace('\\"', '"').replace("\\/", "/")
    return html_to_text(decoded)


def fetch_jd_apple(url: str) -> str:
    r = _http_get(url)
    r.raise_for_status()
    t = r.text
    parts = []
    title_m = _APPLE_RX["title"].search(t)
    if title_m:
        parts.append(f"# {_apple_decode(title_m.group(1))}")
    for key in ("desc", "min", "pref"):
        m = _APPLE_RX[key].search(t)
        if m:
            label = {"desc": "Description", "min": "Minimum Qualifications",
                     "pref": "Preferred Qualifications"}[key]
            parts.append(f"\n## {label}\n{_apple_decode(m.group(1))}")
    if not parts:
        # last-ditch: plain HTML scrape
        return html_to_text(t)
    return "\n".join(parts)


_LI_DESC_RX = re.compile(
    r'<div[^>]*class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
    re.S,
)
_LI_TITLE_RX = re.compile(
    r'<h1[^>]*top-card-layout__title[^>]*>(.*?)</h1>', re.S,
)


def fetch_jd_linkedin(url: str) -> str:
    # public guest view
    r = _http_get(url, headers={
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    })
    r.raise_for_status()
    t = r.text
    title_m = _LI_TITLE_RX.search(t)
    desc_m = _LI_DESC_RX.search(t)
    if not desc_m:
        raise RuntimeError("linkedin: no JD body in public view (may need login)")
    title = html_to_text(title_m.group(1)) if title_m else ""
    body = html_to_text(desc_m.group(1))
    return f"# {title}\n\n{body}" if title else body


def fetch_jd_generic(url: str) -> str:
    """Fallback: plain HTML fetch + crude text extraction."""
    r = _http_get(url)
    r.raise_for_status()
    return html_to_text(r.text)


def fetch_jd_microsoft(url: str) -> str:
    """Microsoft careers (apply.careers.microsoft.com/careers/job/<id>).

    The SPA HTML embeds the full JD inside the og:description meta tag
    (concatenation of duties + qualifications). Title is in <title>.
    """
    r = _http_get(url)
    r.raise_for_status()
    text = r.text
    title_m = re.search(r"<title>([^<]+)</title>", text)
    title = (title_m.group(1) if title_m else "").strip()
    desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', text)
    if not desc_m:
        desc_m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', text)
    desc = desc_m.group(1) if desc_m else ""
    import html as _html
    desc = _html.unescape(desc)
    return f"# {title}\n\n{desc}"


def fetch_jd_google(url: str) -> str:
    """Google careers (google.com/about/careers/applications/jobs/results/<id>...).

    The page server-renders all visible sections (incl. 'Minimum qualifications'
    and 'Preferred qualifications' + 'About the job'). Extract the first
    qualifications-anchored region; if the JD page returns 'Job not found.'
    surface that so the caller can mark the role closed.
    """
    r = _http_get(url)
    r.raise_for_status()
    import html as _html
    raw = r.text
    if "Job not found." in raw:
        return ""
    text = _html.unescape(raw)
    text = text.encode().decode("unicode_escape", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    # Carve out the first ~6000 chars centered on 'Minimum qualifications'
    m = re.search(r"Minimum qualifications", text, re.IGNORECASE)
    if m:
        start = max(0, m.start() - 200)
        body = text[start:start + 6000]
        return body.strip()
    # Fallback: just return the cleaned text head
    return text[:6000].strip()


_RIPPLING_URL_RX = re.compile(r"ats\.rippling\.com/([^/]+)/jobs/([A-Za-z0-9-]{6,})", re.I)


# --- BambooHR ---------------------------------------------------------------
# Hosted careers pages: <tenant>.bamboohr.com/careers/<id>  (canonical)
#                       <tenant>.bamboohr.com/jobs/view.php?id=<n>
#                       <tenant>.bamboohr.com/jobs/embed2.php?id=<n>
# Added 2026-05-30 (chain_034a) for Uphold and any future BambooHR tenants.
_BAMBOO_HOST_RX = re.compile(r"^([a-z0-9-]+)\.bamboohr\.com$", re.I)
_BAMBOO_PATH_CAREERS = re.compile(r"/careers/(\d+)(?:/|$|\?)")
_BAMBOO_PATH_VIEWPHP = re.compile(r"/jobs/(?:view|embed2)\.php")


def _parse_bamboohr_url(url: str) -> Optional[tuple[str, str]]:
    try:
        p = urlparse(url)
    except Exception:
        return None
    host = (p.hostname or "").lower()
    m = _BAMBOO_HOST_RX.match(host)
    if not m:
        return None
    tenant = m.group(1)
    m2 = _BAMBOO_PATH_CAREERS.search(p.path or "")
    if m2:
        return tenant, m2.group(1)
    if _BAMBOO_PATH_VIEWPHP.search(p.path or ""):
        from urllib.parse import parse_qs
        q = parse_qs(p.query or "")
        ids = q.get("id") or []
        if ids and ids[0].isdigit():
            return tenant, ids[0]
    return None


def fetch_jd_bamboohr(url: str) -> str:
    """BambooHR-hosted careers (<tenant>.bamboohr.com).

    BambooHR exposes a tidy JSON endpoint per posting:
        https://<tenant>.bamboohr.com/careers/<id>/detail
    Returns a payload with the JD HTML under `jobOpening.description` (or
    similar). We fall back to scraping the SPA's __NEXT_DATA__/__INITIAL_STATE__
    blob, and finally to a generic text strip if neither works.
    """
    parsed = _parse_bamboohr_url(url)
    if not parsed:
        raise ValueError(f"can't parse bamboohr URL: {url}")
    tenant, jid = parsed
    api = f"https://{tenant}.bamboohr.com/careers/{jid}/detail"
    title = ""
    desc_html = ""
    try:
        r = _http_get(api, headers={"Accept": "application/json"})
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {}
            jo = (data.get("jobOpening") or data.get("result") or data) if isinstance(data, dict) else {}
            title = jo.get("jobOpeningName") or jo.get("title") or ""
            desc_html = jo.get("description") or jo.get("jobDescription") or ""
    except Exception:
        pass
    if not desc_html:
        # Fallback: fetch the SPA HTML and run generic strip.
        try:
            r2 = _http_get(f"https://{tenant}.bamboohr.com/careers/{jid}")
            if r2.status_code == 200:
                desc_html = r2.text
        except Exception:
            pass
    body = html_to_text(desc_html) if desc_html else ""
    if not body:
        raise RuntimeError(f"bamboohr job {jid} on tenant {tenant}: empty JD body")
    return f"# {title}\n\n{body}" if title else body



def fetch_jd_rippling(url: str) -> str:
    """Rippling-hosted ATS (ats.rippling.com/<slug>/jobs/<uuid>).

    The JD page is a Next.js server-rendered shell that carries the full
    job posting at `__NEXT_DATA__.props.pageProps.apiData.jobPost`. The
    description is sectioned HTML (company/role/responsibilities/...);
    we concat all string-valued sections to produce JD text.

    Added 2026-05-30 (chain `rippling-adapter-2026-05-30`) for Hammerspace
    and any future Rippling tenants.
    """
    m = _RIPPLING_URL_RX.search(url)
    if not m:
        raise ValueError(f"can't parse rippling URL: {url}")
    slug, jid = m.group(1), m.group(2)
    # Reuse the adapter's helper so the section-merging logic stays in one
    # place (avoid divergence if Rippling adds new section types).
    from adapters.rippling import _fetch_jd_text  # type: ignore
    title, body = _fetch_jd_text(slug, jid)
    if not body:
        raise RuntimeError(f"rippling job {jid} on board {slug}: empty JD body")
    return f"# {title}\n\n{body}" if title else body


def fetch_jd_stripe(url: str) -> str:
    """Stripe routes job URLs through their React wrapper at stripe.com/jobs/...
    but the underlying ATS is Greenhouse. The numeric id in the URL is the
    same gh_jid the Greenhouse public boards API serves.

    Supported URL shapes:
      https://stripe.com/jobs/listing/<slug>/<gh_jid>            (JD page)
      https://stripe.com/jobs/listing/<slug>/<gh_jid>/apply      (wrapper)
      https://stripe.com/jobs/search?gh_jid=<gh_jid>             (301 redirect)

    All three resolve to GH API:
      https://boards-api.greenhouse.io/v1/boards/stripe/jobs/<gh_jid>

    Background: 2026-05-24 6 Stripe submits slipped past the YOE classifier
    because `detect_and_fetch` had no stripe.com branch — it fell through to
    `fetch_jd_generic` and the React-rendered shell yielded no JD text, so
    the classifier silently skipped them. Roles entered the submit queue
    unclassified. See memory/2026-05-24.md "Stripe cracked today".
    """
    gh_jid: Optional[str] = None
    # /jobs/listing/<slug>/<id>[/apply]
    m = re.search(r"/jobs/listing/[^/]+/(\d+)(?:/|$|\?)", url)
    if m:
        gh_jid = m.group(1)
    if not gh_jid:
        m2 = re.search(r"[?&]gh_jid=(\d+)", url)
        if m2:
            gh_jid = m2.group(1)
    if not gh_jid:
        # Last-ditch: any 6+ digit number in the path
        m3 = re.search(r"/(\d{6,})(?:/|$)", url)
        if m3:
            gh_jid = m3.group(1)
    if not gh_jid:
        raise ValueError(f"can't parse stripe URL (no gh_jid): {url}")
    api = f"https://boards-api.greenhouse.io/v1/boards/stripe/jobs/{gh_jid}"
    r = _http_get(api, headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    title = data.get("title", "")
    content_html = data.get("content", "")
    return f"# {title}\n\n" + html_to_text(content_html)


def detect_and_fetch(url: str, company: Optional[str] = None) -> tuple[str, str]:
    """Return (ats_label, jd_text)."""
    if not url:
        raise ValueError("empty url")
    host = (urlparse(url).hostname or "").lower()
    if "greenhouse.io" in host:
        return "greenhouse", fetch_jd_greenhouse(url)
    if _EIGHTFOLD_HOST_RX.match(host):
        return "eightfold", fetch_jd_eightfold(url)
    if "ashbyhq.com" in host:
        return "ashby", fetch_jd_ashby(url)
    if "lever.co" in host:
        return "lever", fetch_jd_lever(url)
    if "myworkdayjobs.com" in host:
        return "workday", fetch_jd_workday(url)
    if "apple.com" in host:
        return "apple", fetch_jd_apple(url)
    if "linkedin.com" in host:
        return "linkedin", fetch_jd_linkedin(url)
    if host == "stripe.com" or host.endswith(".stripe.com"):
        return "stripe", fetch_jd_stripe(url)
    if host == "ats.rippling.com" or host.endswith(".rippling.com"):
        return "rippling", fetch_jd_rippling(url)
    if host.endswith(".bamboohr.com"):
        return "bamboohr", fetch_jd_bamboohr(url)
    if host.endswith("careers.microsoft.com") or host == "apply.careers.microsoft.com":
        return "microsoft", fetch_jd_microsoft(url)
    if host == "www.google.com" or host == "google.com":
        if "/about/careers/" in url:
            return "google", fetch_jd_google(url)
    # gh_jid wrapper fallback: any non-greenhouse host that still carries a
    # ?gh_jid=<id> param is a Greenhouse-backed posting on the employer's own
    # domain (Datadog/Okta/FanDuel/Credera/Dealpath/Harness class). Resolve via
    # the GH boards API before giving up to the (0-char) generic strip.
    if _gh_jid_from_url(url):
        try:
            return "greenhouse-jid", fetch_jd_greenhouse_by_jid(url, company)
        except Exception:
            pass  # fall through to generic
    return "generic", fetch_jd_generic(url)


def get_cached_jd(source_key: str, url: str,
                  company: Optional[str] = None) -> tuple[str, str]:
    """Return (ats_label, jd_text), caching to disk."""
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", source_key)[:200]
    cache_path = JD_CACHE / f"{safe}.txt"
    meta_path = JD_CACHE / f"{safe}.meta"
    if cache_path.exists() and meta_path.exists():
        try:
            return meta_path.read_text().strip(), cache_path.read_text()
        except Exception:
            pass
    ats, txt = detect_and_fetch(url, company)
    if not txt or len(txt.strip()) < 50:
        raise RuntimeError(f"JD body too short ({len(txt)} chars)")
    cache_path.write_text(txt)
    meta_path.write_text(ats)
    return ats, txt



# ---------------------------------------------------------------------------
# Gate logic (simplified 2026-05-29: YOE-from-JD + title-keyword fallback)
# ---------------------------------------------------------------------------
#
# Cyrus directive 2026-05-29: the queue gate is ONLY:
#   1. Regex-scan JD body for "N year(s) [of] experience". If a number is
#      found and >= YOE_THRESHOLD -> skip with 'yoe-threshold'.
#   2. If no YOE was found in the JD, fall back to title-keyword scan
#      (Senior / Staff / Principal / Director / Head / VP / Chief / Lead /
#      etc.). Any match -> skip with 'senior-title'.
#   3. Optional: non-US location signal -> skip with 'non-us' (deterministic,
#      JD-derived, not LLM-derived; kept because it's the same shape of gate).
#
# The LLM call (is_people_manager / seniority / fit_score / reason) is
# RETIRED. Those DB columns remain (referenced by retro_apply_new_classifier_gates,
# backfill_stripe_exp, render_xlsx, sequential_burndown) but this classifier
# no longer writes to them and no longer reads them for the skip decision.

# Title-keyword blocklist (HARD): if a title contains any of these
# (word-boundary, case-insensitive), SKIP. Specific terms first so the
# reported keyword name is the most informative one.
HARD_BLOCKLIST = [
    ("chief",         r"\bchief\b"),
    ("distinguished", r"\bdistinguished\b"),
    ("fellow",        r"\bfellow\b"),
    ("head of",       r"\bhead\s+of\b"),
    ("principal",     r"\bprincipal\b"),
    ("director",      r"\bdirector\b"),
    ("svp",           r"\bsvp\b"),
    ("evp",           r"\bevp\b"),
    ("vp",            r"\bvp\b"),
    ("vice president", r"\bvice\s+president\b"),
    ("senior",        r"\bsenior\b"),
    ("sr",            r"\bsr\.?\b"),
    ("mgr",           r"\bmgr\b"),
    # NOTE: 'staff' and 'lead' moved to _ROLE_TYPE_RE (target-role carve-out)
    # so 'Lead TPM' / 'Staff TPM' are KEPT but 'Lead Engineer' / 'Staff SWE' skip.
    # 2026-06-20 Cyrus directive.
]
_HARD_RE = [(k, re.compile(p, re.I)) for k, p in HARD_BLOCKLIST]

# Role-type blocklist (CLEARED 2026-06-20 per Cyrus full-unblock directive).
# FDE + all SWE discipline blocks removed — pipeline now applies to all role
# types including FDE, SWE IC, ML, data, infra, frontend, backend, mobile.
# Only staff/lead remain here (still carve out for Lead TPM / Staff TPM).
ROLE_TYPE_BLOCKLIST = [
    # staff/lead: skip unless paired with a target role (Lead TPM = KEEP, Lead Engineer = SKIP)
    # Moved from HARD_BLOCKLIST 2026-06-20 (Cyrus directive).
    ("staff",         r"\bstaff\b"),
    ("lead",          r"\blead\b"),
]
_ROLE_TYPE_RE = [(k, re.compile(p, re.I)) for k, p in ROLE_TYPE_BLOCKLIST]

# FDE hard block REMOVED 2026-06-20 (Cyrus full-unblock directive).
_FDE_HARD_RE = []

# Positional senior-signal: "Group <PM-like> Manager" or "Group PM/TPM/EPM".
_POSITIONAL_PREFIX_RE = re.compile(
    r"\bgroup\s+"
    r"(?:product|program|project|technical\s+program|engineering\s+program)\s+"
    r"manager\b",
    re.I,
)
_POSITIONAL_ABBREV_RE = re.compile(
    r"\bgroup\s+(?:PM|TPM|EPM|PgM|APM|TPgM)\b",
    re.I,
)

# Soft 'manager' — word-boundary; carve-out applies via TARGET_ROLE_SUBSTRINGS.
_MANAGER_RE = re.compile(r"\bmanager\b", re.I)

TARGET_ROLE_SUBSTRINGS = [
    "product manager",
    "program manager",
    "project manager",
    "technical program manager",
    "engineering program manager",
    "product marketing manager",
    "solutions engineer",
    "solution engineer",
    "sales engineer",
    "solutions architect",
    "solution architect",
    "customer engineer",
]
# NOTE 2026-06-20: FDE + all SWE discipline keywords REMOVED from blocklist per Cyrus full-unblock directive.
_TARGET_ROLE_ABBREV_RE = re.compile(
    r"\b(?:PM|TPM|EPM|PgM|SE|SA|APM|TPgM)\b"
)


def title_has_target_role(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    if any(sub in t for sub in TARGET_ROLE_SUBSTRINGS):
        return True
    if _TARGET_ROLE_ABBREV_RE.search(title):
        return True
    return False


def extract_title_skip(title: Optional[str]) -> Optional[str]:
    """Return matched skip-keyword, or None if title should KEEP.

    Order matters:
      1. HARD_BLOCKLIST (senior/staff/director/etc) — never carved out.
         "Senior Solutions Engineer" still skips.
      2. ROLE_TYPE_BLOCKLIST (FDE/SWE/full-stack/etc) — carved out IF the
         title also matches a TARGET_ROLE_SUBSTRINGS entry.
         "Customer Solutions Engineer (Full Stack)" keeps.
         "Software Engineer, Backend" skips.
    """
    if not title:
        return None
    for kw, rx in _HARD_RE:
        if rx.search(title):
            return kw
    # FDE hard block removed 2026-06-20 (Cyrus full-unblock).
    if not title_has_target_role(title):
        for kw, rx in _ROLE_TYPE_RE:
            if rx.search(title):
                return kw
    if _POSITIONAL_PREFIX_RE.search(title):
        return "group"
    if _POSITIONAL_ABBREV_RE.search(title):
        return "group"
    if _MANAGER_RE.search(title) and not title_has_target_role(title):
        return "manager"
    return None


# --- YOE regex extraction ---------------------------------------------------
YOE_THRESHOLD = 6  # JD-stated minimum YOE >= this -> deterministic skip (raised 4->6 2026-06-20: keeps '3-5' and '5+' roles)

# Company-level blocklist (Cyrus handles these himself, 2026-05-31).
# Matched case-insensitively as a word against the `company` field. Keep this
# narrow + exact to avoid catching e.g. "Microsoft-Partner-X" startups, but
# Google/Alphabet and Microsoft cover the intent.
COMPANY_BLOCKLIST = [
    # Google + Alphabet RE-ENABLED for discovery (Cyrus 2026-06-08, BACKLOG #1).
    # Google careers is now a permanent discovery source: adapters/google.py
    # fetches each role's JD and parses a REAL Min-quals YOE floor, and
    # tracker_merger keeps Google rows manual-apply / discovery-only (never
    # auto-submitted). So the company-level block here is removed; the standing
    # title + YOE + US-location gates do the filtering. (microsoft/amazon/aws
    # stay blocked — Cyrus still handles those himself.)
    #   ("google",    r"\bgoogle\b"),   # removed 2026-06-08 re-enable
    #   ("alphabet",  r"\balphabet\b"), # removed 2026-06-08 re-enable
    ("microsoft", r"\bmicrosoft\b"),
    # Amazon exclusion (Cyrus 2026-05-31, same pattern as Google/Microsoft).
    # "amazon" catches Amazon, Amazon Web Services, Amazon Prime, etc.
    # "aws" catches the "Amazon Web Services (AWS)" / bare "AWS" company strings.
    ("amazon",    r"\bamazon\b"),
    ("aws",       r"\baws\b"),
]
_COMPANY_BLOCK_RE = [(k, re.compile(p, re.I)) for k, p in COMPANY_BLOCKLIST]

# Subsidiary SAFELIST (Cyrus 2026-05-31): Google/Alphabet/Microsoft own these,
# but Cyrus WANTS them in scope (e.g. Waymo). If a company name matches any of
# these, it is NEVER company-blocked — even if the name also contains a parent
# keyword (e.g. "Google DeepMind" -> kept because of "deepmind").
# Subsidiaries whose names DON'T contain a parent keyword (Waymo, Verily,
# GitHub, LinkedIn, Xbox, ...) are already safe via the word-boundary match;
# this list only matters for parent-prefixed names.
COMPANY_SAFELIST = [
    r"\bdeepmind\b",
    r"\bwaymo\b",
    r"\bverily\b",
    r"\bisomorphic\b",
    r"\bintrinsic\b",
    r"\bgithub\b",
    r"\blinkedin\b",
    r"\bxbox\b",
    # Amazon-owned subsidiaries whose names DON'T contain "Amazon" — Cyrus wants
    # these in scope (2026-05-31), explicitly Twitch. Most are already safe via
    # word-boundary (their names lack "amazon"/"aws"); listed for clarity +
    # to guard against a name like "Amazon Audible" / "AWS Annapurna".
    r"\btwitch\b",
    r"\bzappos\b",
    r"\baudible\b",
    r"\bring\b",
    r"\bwhole foods\b",
    r"\bimdb\b",
    r"\bgoodreads\b",
    r"\bannapurna\b",
]
_COMPANY_SAFE_RE = [re.compile(p, re.I) for p in COMPANY_SAFELIST]


def company_is_blocked(company: Optional[str]) -> Optional[str]:
    """Return matched blocklist keyword if company is Cyrus-handled, else None.

    A subsidiary-safelist match (Waymo, DeepMind, GitHub, ...) overrides the
    parent blocklist — those stay in scope per Cyrus 2026-05-31.
    """
    if not company:
        return None
    for rx in _COMPANY_SAFE_RE:
        if rx.search(company):
            return None
    for kw, rx in _COMPANY_BLOCK_RE:
        if rx.search(company):
            return kw
    return None
_YOE_PATTERNS = [
    # "5+ years of relevant experience", "4 years overall experience",
    # "Minimum 5 yrs experience in..."
    re.compile(
        r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\b[^.\n\r]{0,80}?\bexperience\b",
        re.I,
    ),
    # "3-5 years" / "4 to 7 yrs" — take upper bound
    re.compile(
        r"\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\+?\s*(?:years?|yrs?)\b",
        re.I,
    ),
    # "YOE: 5" / "YOE = 6"
    re.compile(r"\bYOE\s*[:=>]?\s*(\d{1,2})\b", re.I),
    # "minimum/at least/requires N+ years"
    re.compile(
        r"\b(?:minimum|at\s+least|requires?|require)\s+(?:of\s+)?(\d{1,2})\+?\s*(?:years?|yrs?)\b",
        re.I,
    ),
]


def extract_yoe_from_jd_text(jd: Optional[str]) -> Optional[int]:
    """Scan JD body for YOE statements. Returns MAX integer or None.

    Values > 25 are ignored as junk. The range pattern returns the upper bound.
    """
    if not jd:
        return None
    values: list[int] = []
    for rx in _YOE_PATTERNS:
        for m in rx.finditer(jd):
            for g in m.groups():
                if not g:
                    continue
                try:
                    n = int(g)
                except (TypeError, ValueError):
                    continue
                if 0 < n < 25:
                    values.append(n)
    if not values:
        return None
    return max(values)


# --- Non-US location detection ----------------------------------------------
NON_US_CITIES = [
    # Europe
    "london", "manchester", "edinburgh", "glasgow", "dublin", "belfast",
    "paris", "lyon", "berlin", "munich", "hamburg", "frankfurt", "cologne",
    "amsterdam", "rotterdam", "utrecht", "the hague", "brussels", "antwerp",
    "copenhagen", "stockholm", "oslo", "helsinki", "reykjavik",
    "madrid", "barcelona", "lisbon", "porto", "rome", "milan", "turin",
    "zurich", "geneva", "vienna", "prague", "warsaw", "krakow", "budapest",
    "athens", "istanbul", "bucharest", "sofia",
    # APAC
    "tokyo", "osaka", "kyoto", "yokohama",
    "seoul", "busan",
    "beijing", "shanghai", "shenzhen", "guangzhou", "hangzhou", "chengdu",
    "hong kong", "taipei", "singapore",
    "bangalore", "bengaluru", "hyderabad", "mumbai", "delhi", "new delhi",
    "chennai", "pune", "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad",
    "jakarta", "manila", "bangkok", "kuala lumpur", "ho chi minh", "hanoi",
    "sydney", "melbourne", "brisbane", "perth", "auckland", "wellington",
    # Americas (non-US)
    "toronto", "vancouver", "montreal", "ottawa", "calgary", "edmonton",
    "mexico city", "guadalajara", "monterrey",
    "sao paulo", "são paulo", "rio de janeiro", "brasilia", "buenos aires",
    "santiago", "bogota", "bogotá", "lima",
    # MENA / Africa
    "dubai", "abu dhabi", "doha", "riyadh", "tel aviv", "cairo",
    "nairobi", "lagos", "johannesburg", "cape town",
]
NON_US_COUNTRIES = [
    "united kingdom", "uk", "england", "scotland", "wales", "ireland",
    "germany", "france", "netherlands", "belgium", "spain", "portugal",
    "italy", "switzerland", "austria", "poland", "czech republic", "czechia",
    "sweden", "norway", "denmark", "finland", "iceland",
    "japan", "south korea", "china", "taiwan", "hong kong", "singapore",
    "india", "indonesia", "philippines", "thailand", "malaysia", "vietnam",
    "australia", "new zealand",
    "canada", "mexico", "brazil", "argentina", "chile", "colombia", "peru",
    "uae", "united arab emirates", "qatar", "saudi arabia", "israel", "egypt",
    "kenya", "nigeria", "south africa",
]
NON_US_EXCLUSIVE_PATTERNS = [
    re.compile(r"\bremote\s*[-–—,:\s]\s*(?:uk|emea|europe|apac|india|canada(?:\s+only)?|eu(?:\s+only)?)\b", re.I),
    re.compile(r"\b(?:uk|eu|emea|apac|india|canada)\s+only\b", re.I),
    re.compile(r"\bbased\s+in\s+(?:london|berlin|paris|toronto|bangalore|bengaluru|hyderabad|mumbai|delhi|dublin|amsterdam|singapore|sydney|tokyo|tel\s+aviv|dubai)\b", re.I),
    re.compile(r"\bmust\s+(?:be\s+)?(?:located|reside|based)\s+in\s+(?:the\s+)?(?:uk|eu|emea|apac|india|canada|europe|asia)\b", re.I),
]
US_ALLOW_PATTERNS = [
    re.compile(r"\b(?:usa?|united\s+states|u\.s\.|u\.s\.a\.)\b", re.I),
    re.compile(
        r"\b(?:san\s+francisco|sf\s+bay\s+area|silicon\s+valley|new\s+york|nyc|brooklyn|manhattan|seattle|austin|boston|chicago|denver|portland|los\s+angeles|la\b|san\s+diego|san\s+jose|sunnyvale|mountain\s+view|palo\s+alto|cupertino|menlo\s+park|redwood\s+city|oakland|berkeley|atlanta|miami|washington\s+dc|washington,?\s+d\.c\.|dallas|houston|philadelphia|phoenix|salt\s+lake|nashville|minneapolis|raleigh|durham|pittsburgh|detroit|cleveland|charlotte|tampa|orlando|kansas\s+city|st\.?\s+louis|cincinnati|columbus|indianapolis|milwaukee|las\s+vegas|reno|sacramento|fresno|long\s+beach|anaheim|santa\s+monica|santa\s+clara|fremont|hayward|arlington|alexandria|bethesda|reston|herndon|tysons|mclean|cambridge|somerville|providence|new\s+haven|hartford|stamford|jersey\s+city|newark|princeton)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new\s+hampshire|new\s+jersey|new\s+mexico|north\s+carolina|north\s+dakota|ohio|oklahoma|oregon|pennsylvania|rhode\s+island|south\s+carolina|south\s+dakota|tennessee|texas|utah|vermont|virginia|washington\s+state|west\s+virginia|wisconsin|wyoming)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[,\s])(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)(?:[,\s]|$)"
    ),
    re.compile(r"\bremote\s*[-–—,:\s]\s*us(?:a)?\b", re.I),
    re.compile(r"\bUS\s+remote\b", re.I),
    re.compile(r"\b(?:us|usa)\s*(?:only|based)\b", re.I),
]
_NON_US_CITY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in NON_US_CITIES) + r")\b", re.I
)
_NON_US_COUNTRY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in NON_US_COUNTRIES) + r")\b", re.I
)


def _has_us_signal(text: str) -> bool:
    return any(rx.search(text) for rx in US_ALLOW_PATTERNS)


def detect_non_us_location(jd: Optional[str], location_field: Optional[str]) -> Optional[str]:
    """Return a short reason string if the role is clearly non-US, else None."""
    loc = (location_field or "").strip()
    jd_head = (jd or "")[:3000]
    combined_for_us = f"{loc}\n{jd_head}"
    us_signal = _has_us_signal(combined_for_us)
    for rx in NON_US_EXCLUSIVE_PATTERNS:
        m = rx.search(loc) or rx.search(jd_head)
        if m:
            return f"non-us:{m.group(0).strip()[:40]}"
    if loc:
        loc_has_us = _has_us_signal(loc)
        if not loc_has_us:
            m = _NON_US_CITY_RE.search(loc) or _NON_US_COUNTRY_RE.search(loc)
            if m:
                return f"non-us-loc:{m.group(0).strip()[:40]}"
    if not us_signal and jd_head:
        m = _NON_US_CITY_RE.search(jd_head) or _NON_US_COUNTRY_RE.search(jd_head)
        if m:
            return f"non-us-jd:{m.group(0).strip()[:40]}"
    return None


def _merge_flag(existing_flags: Optional[str], new_flag: str) -> str:
    existing = (existing_flags or "").strip()
    parts = [f for f in re.split(r"[;,\s]+", existing) if f]
    if new_flag not in parts:
        parts.append(new_flag)
    return ";".join(parts)


def _merge_flags(existing_flags: Optional[str], new_flags: list[str]) -> str:
    out = existing_flags
    for f in new_flags:
        out = _merge_flag(out, f)
    return out or ""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def fetch_target_rows(con: sqlite3.Connection, *, limit: Optional[int],
                      role_id: Optional[int], force: bool) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    where = []
    params: list = []
    if role_id is not None:
        where.append("id = ?")
        params.append(role_id)
    else:
        where.append("(status = '' OR status IS NULL)")
        where.append("applied_by IS NULL")
        if not force:
            where.append("llm_classified_at IS NULL")
    sql = (
        "SELECT id, source_key, company, role, loc, app_url, jd_url, status, flags, applied_by "
        "FROM roles WHERE " + " AND ".join(where)
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    return con.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# The new (simplified) gate logic
# ---------------------------------------------------------------------------

def decide_skip(title: Optional[str], jd_text: Optional[str],
                location_field: Optional[str] = None,
                company: Optional[str] = None
                ) -> tuple[list[str], list[str], Optional[int]]:
    """Apply the simplified gate logic. Pure function (no DB, no LLM, no I/O).

    Logic (Cyrus 2026-05-29):
      0. Company blocklist (Cyrus 2026-05-31): Google/Alphabet/Microsoft ->
         skip with 'company-blocked' (Cyrus handles these himself).
      1. Regex-scan JD body for "N year(s) [of] experience".
         If a number >= YOE_THRESHOLD is found -> skip with 'yoe-threshold'.
      2. If NO YOE was found in JD, fall back to title-keyword blocklist
         (Senior / Staff / Principal / Director / Head / VP / Chief / Lead /
         etc.). Match -> skip with 'senior-title'.
      3. Independent: non-US location signal -> skip with 'non-us'.

    is_people_manager / seniority / fit_score signals are NOT consulted.

    Returns (new_flags, reasons, jd_yoe_value_for_logging).
    """
    new_flags: list[str] = []
    reasons: list[str] = []

    # Gate 0: company blocklist (short-circuits — Cyrus handles these).
    blocked_company = company_is_blocked(company)
    if blocked_company:
        new_flags.append("company-blocked")
        reasons.append(f"company:{blocked_company}")
        return new_flags, reasons, None

    jd_yoe = extract_yoe_from_jd_text(jd_text)

    # Gate 0.5 (HARD, independent of YOE): FDE role-type block. Cyrus directive
    # 2026-05-30 / re-confirmed 06-02 — FDE is a HARD block that must NEVER be
    # rescued, including by a sub-threshold parsed YOE. Previously the title-skip
    # check only ran in the `jd_yoe is None` branch below, so an FDE row whose JD
    # parsed a low YOE (e.g. "3 years") bypassed the FDE block entirely and leaked
    # as keep (6 leaks found 2026-06-03 in the li-resolve harvest: Addepar,
    # PubMatic, Actively AI, Charta Health, Console, Scaled Cognition). Run the
    # FDE hard-block here, unconditionally.
    for kw, rx in _FDE_HARD_RE:
        if rx.search(title or ""):
            new_flags.append("fde-block")
            reasons.append(f"fde:{kw}")
            # Still record YOE / non-US below for completeness, but FDE alone
            # is sufficient to skip.
            break

    # Gate 1: YOE from JD
    if jd_yoe is not None and jd_yoe >= YOE_THRESHOLD:
        new_flags.append("yoe-threshold")
        reasons.append(f"jd-yoe:{jd_yoe}")
    elif jd_yoe is None:
        # Gate 2 (fallback only when JD had no YOE signal): title keyword.
        # (FDE already handled above; extract_title_skip also returns FDE but
        # the dedupe in _merge_flags / set-membership keeps flags clean.)
        title_kw = extract_title_skip(title)
        if title_kw and title_kw not in ("forward deployed", "fde"):
            new_flags.append("senior-title")
            reasons.append(f"title:{title_kw}")
        elif title_kw in ("forward deployed", "fde") and "fde-block" not in new_flags:
            new_flags.append("fde-block")
            reasons.append(f"fde:{title_kw}")

    # Gate 3 (independent): non-US location
    non_us = detect_non_us_location(jd_text, location_field)
    if non_us:
        new_flags.append("non-us")
        reasons.append(non_us)

    return new_flags, reasons, jd_yoe


def maybe_skip(con: sqlite3.Connection, row: sqlite3.Row,
               cls: Optional[dict], jd_text: Optional[str],
               *, dry_run: bool) -> Optional[dict]:
    """Apply simplified skip gates. Returns dict describing the flip or None.

    `cls` is accepted for backward-compat with callers (retro_apply_*) but
    is IGNORED — the simplified gate does not consult LLM-derived signals.
    """
    if row["applied_by"]:
        return None
    if row["status"] and row["status"] != "":
        return None

    try:
        loc_field = row["loc"]
    except (IndexError, KeyError):
        loc_field = None

    new_flags, reasons, jd_yoe = decide_skip(row["role"], jd_text, loc_field,
                                             company=row["company"])
    if not new_flags:
        return None

    flip = {
        "id": row["id"],
        "company": row["company"],
        "role": row["role"],
        "new_flags": new_flags,
        "reasons": reasons,
        "jd_yoe": jd_yoe,
    }
    if dry_run:
        return flip

    merged = _merge_flags(row["flags"], new_flags)
    if jd_yoe is not None:
        con.execute(
            "UPDATE roles SET llm_yoe_required = ? WHERE id = ?",
            (jd_yoe, row["id"]),
        )
    con.execute(
        "UPDATE roles SET status = 'skip', flags = ? WHERE id = ?",
        (merged, row["id"]),
    )
    return flip


def mark_classified(con: sqlite3.Connection, role_id: int,
                    jd_yoe: Optional[int]) -> None:
    """Stamp llm_classified_at + llm_yoe_required (so re-runs skip the row).

    The legacy LLM columns (llm_is_people_manager, llm_seniority,
    llm_fit_score, llm_reason) are left untouched. We never write to them
    again from this classifier.
    """
    con.execute(
        "UPDATE roles SET llm_classified_at = ?, llm_yoe_required = ? "
        "WHERE id = ?",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            jd_yoe,
            role_id,
        ),
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def backup_db_once() -> Optional[Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    bak = DB.with_suffix(f".db.bak.{stamp}-classifier-run")
    if not bak.exists():
        shutil.copy2(DB, bak)
        return bak
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--role-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="re-classify even if llm_classified_at is set")
    args = ap.parse_args()

    if not DB.exists():
        print(f"ERR tracker.db missing: {DB}", file=sys.stderr)
        return 2

    con = sqlite3.connect(DB)
    cols = {r[1] for r in con.execute("PRAGMA table_info(roles)").fetchall()}
    if "llm_classified_at" not in cols:
        print("ERR run migrate_llm_classifier_columns.py first", file=sys.stderr)
        return 2

    rows = fetch_target_rows(con, limit=args.limit, role_id=args.role_id,
                             force=args.force)
    print(f"[classifier] {len(rows)} rows to process (dry_run={args.dry_run})")
    if not rows:
        print("[classifier] nothing to do.")
        return 0

    if not args.dry_run:
        bak = backup_db_once()
        if bak:
            print(f"[classifier] backed up DB -> {bak.name}")

    classified = 0
    flipped = 0
    errors: list[dict] = []
    t0 = time.time()

    for i, row in enumerate(rows, 1):
        rid = row["id"]
        url = row["jd_url"] or row["app_url"]
        company = row["company"] or ""
        title = row["role"] or ""
        try:
            ats, jd = get_cached_jd(row["source_key"], url, company)
        except Exception as e:
            errors.append({
                "id": rid, "company": company, "title": title,
                "url": url, "stage": "fetch",
                "error": str(e)[:500],
            })
            print(f"  [{i}/{len(rows)}] id={rid} ERR fetch: {str(e)[:120]}")
            continue

        jd_yoe = extract_yoe_from_jd_text(jd)

        if args.dry_run:
            flip = maybe_skip(con, row, None, jd, dry_run=True)
            tag = f"[SKIP {'+'.join(flip['new_flags'])}]" if flip else ""
            print(f"  [{i}/{len(rows)}] id={rid} {company[:20]:20s} | "
                  f"yoe={jd_yoe} {tag}")
        else:
            mark_classified(con, rid, jd_yoe)
            flip = maybe_skip(con, row, None, jd, dry_run=False)
            tag = (f" [FLIPPED→skip {'+'.join(flip['new_flags'])}]"
                   if flip else "")
            if flip:
                flipped += 1
            con.commit()
            print(f"  [{i}/{len(rows)}] id={rid} {company[:20]:20s} | "
                  f"yoe={jd_yoe}{tag}")
        classified += 1

    if errors:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        err_path = ERR_DIR / f"_classifier-errors-{stamp}.json"
        ERR_DIR.mkdir(exist_ok=True)
        err_path.write_text(json.dumps(errors, indent=2))
        print(f"[classifier] wrote {len(errors)} errors -> {err_path}")

    dt = time.time() - t0
    print(f"[classifier] DONE classified={classified} flipped_to_skip={flipped} "
          f"errors={len(errors)} elapsed={dt:.0f}s")
    print(f"Classifier: {classified} classified, {flipped} flagged as overreach, {len(errors)} errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
