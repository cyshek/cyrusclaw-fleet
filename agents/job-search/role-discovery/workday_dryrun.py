#!/usr/bin/env python3
"""
workday_dryrun.py — Generate a prep-only dryrun spec for a Workday role.

Workday's per-tenant form-fill engine is NOT implemented. This script does
the *minimum* needed for the prep pipeline:

  1. Parse the Workday job URL → host, tenant, site, job-path.
  2. Try the Workday CXS detail endpoint:
       GET https://{host}/wday/cxs/{tenant}/{site}/job/{job_path}
     to fetch the JD body.
  3. Write applications/dryrun/workday-{tenant}-{reqid}.json with
       ready_to_submit: false
       blockers: ["workday-form-fill-not-implemented"]
     plus the apply URL, JD text, location, title, and a clear "manual
     submit required" marker.

If Workday is in maintenance mode (the CXS endpoint 303→
`community.workday.com/maintenance-page`), the spec is still written but
the JD body is replaced with a maintenance marker. Caller can detect this
via `spec["maintenance_mode"] == True` and skip the LLM-tailoring phases.

ZERO writes to Workday. Read-only. No POSTs. Ever.

Usage:
    .venv/bin/python workday_dryrun.py <workday_url>
    .venv/bin/python workday_dryrun.py <workday_url> --quiet

Output:
    ../applications/dryrun/workday-{tenant}-{reqid}.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
OUTPUT_DIR = PROJECT_ROOT / "applications" / "dryrun"
HTTP_TIMEOUT = 25

# Marker the runner watches for.
MAINTENANCE_HOST_SUBSTR = "community.workday.com/maintenance"

# e.g. https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295
WORKDAY_HOST_RX = re.compile(r"^([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com$", re.I)
WORKDAY_SITE_HOST_RX = re.compile(r"^(wd\d+)\.myworkdaysite\.com$", re.I)
# Job path typically ends with _R<digits> or _JR<digits> etc.
REQID_RX = re.compile(r"_([A-Z]{1,4}\d{4,})$|/([A-Z]{1,4}\d{4,})$")


def parse_workday_url(url: str) -> dict:
    """Extract host, tenant, site, job_path, reqid."""
    p = urlparse(url)
    host = p.netloc
    ms = WORKDAY_SITE_HOST_RX.match(host)
    if ms:
        all_parts = [s for s in p.path.split("/") if s]
        if all_parts and all_parts[0].lower() == "recruiting":
            all_parts = all_parts[1:]
        if len(all_parts) < 3:
            raise ValueError(f"myworkdaysite.com path too short: {p.path}")
        tenant = all_parts[0].lower()
        parts = all_parts[1:]
    else:
        m = WORKDAY_HOST_RX.match(host)
        if not m:
            raise ValueError(f"not a recognized Workday host: {host}")
        tenant = m.group(1).lower()
        # Path layout: /{site}/job/{...}/{Job-Title}_{REQID}
        # Some tenants use /{site}/d/job/ ; handle both.
        parts = [s for s in p.path.split("/") if s]
    if not parts:
        raise ValueError(f"empty path: {url}")
    site = parts[0]
    # Find the "job" segment and capture everything after it.
    try:
        idx = parts.index("job")
    except ValueError:
        # some tenants embed it as 'd/job/...'
        if "d" in parts and parts.index("d") + 1 < len(parts) and parts[parts.index("d") + 1] == "job":
            idx = parts.index("d") + 1
        else:
            raise ValueError(f"no /job/ segment found in {p.path}")
    job_path_parts = parts[idx + 1:]
    if not job_path_parts:
        raise ValueError(f"no job path after /job/ in {p.path}")
    job_path = "/".join(job_path_parts)
    # Extract reqid (last token of last segment)
    last = job_path_parts[-1]
    rm = re.search(r"_([A-Za-z]{0,5}\d{3,}(?:-\d+)?)$", last)
    if rm:
        reqid = rm.group(1)
    else:
        # fall back to whole last segment, slugified, capped to 40 chars
        reqid = re.sub(r"[^A-Za-z0-9]+", "-", last)[:40]
    return {
        "host": host, "tenant": tenant, "site": site,
        "job_path": job_path, "reqid": reqid,
    }


def _strip_html(html: str) -> str:
    s = unescape(html or "")
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</p>", "\n\n", s)
    s = re.sub(r"(?is)</li>", "\n", s)
    s = re.sub(r"(?is)<li[^>]*>", "- ", s)
    s = re.sub(r"(?is)</h[1-6]>", "\n\n", s)
    s = re.sub(r"(?is)<h([1-6])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", s)
    s = re.sub(r"(?is)<strong[^>]*>(.*?)</strong>", r"**\1**", s)
    s = re.sub(r"(?is)<b[^>]*>(.*?)</b>", r"**\1**", s)
    s = re.sub(r"(?is)<em[^>]*>(.*?)</em>", r"*\1*", s)
    s = re.sub(r"(?is)<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def fetch_workday_job(parts: dict, quiet: bool = False) -> dict:
    """Fetch JD via Workday CXS detail endpoint.

    Returns a dict with keys:
      maintenance_mode: bool
      http_status: int
      final_url: str
      title, location, posting_url, jd_text, jd_html, posted_on, end_date
      raw: full JSON if available
    """
    cxs_url = f"https://{parts['host']}/wday/cxs/{parts['tenant']}/{parts['site']}/job/{parts['job_path']}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (job-search-agent/1.0)",
        "X-Calypso-PageBlocked": "false",
    }
    sess = requests.Session()
    sess.max_redirects = 5
    try:
        r = sess.get(cxs_url, headers=headers, timeout=HTTP_TIMEOUT,
                     allow_redirects=True)
    except requests.RequestException as e:
        return {
            "maintenance_mode": False, "http_status": 0,
            "final_url": cxs_url, "title": "", "location": "",
            "posting_url": "", "jd_text": "", "jd_html": "",
            "posted_on": "", "end_date": "", "raw": None,
            "fetch_error": f"{type(e).__name__}: {e}",
        }
    final_url = r.url or ""
    if MAINTENANCE_HOST_SUBSTR in final_url:
        return {
            "maintenance_mode": True, "http_status": r.status_code,
            "final_url": final_url, "title": "", "location": "",
            "posting_url": "", "jd_text": "", "jd_html": "",
            "posted_on": "", "end_date": "", "raw": None,
        }
    if r.status_code != 200:
        return {
            "maintenance_mode": False, "http_status": r.status_code,
            "final_url": final_url, "title": "", "location": "",
            "posting_url": "", "jd_text": "", "jd_html": "",
            "posted_on": "", "end_date": "", "raw": None,
            "fetch_error": f"HTTP {r.status_code}",
        }
    try:
        data = r.json()
    except Exception as e:
        return {
            "maintenance_mode": False, "http_status": r.status_code,
            "final_url": final_url, "title": "", "location": "",
            "posting_url": "", "jd_text": "", "jd_html": "",
            "posted_on": "", "end_date": "", "raw": None,
            "fetch_error": f"json-decode-failed: {e}",
        }
    info = data.get("jobPostingInfo") or {}
    title = info.get("title") or ""
    loc = info.get("location") or ""
    posting_url = info.get("externalUrl") or info.get("jobPostingUrl") or ""
    jd_html = info.get("jobDescription") or ""
    jd_text = _strip_html(jd_html)
    posted_on = (info.get("postedOn") or "")[:24]
    end_date = (info.get("endDate") or "")[:24]
    return {
        "maintenance_mode": False, "http_status": r.status_code,
        "final_url": final_url, "title": title, "location": loc,
        "posting_url": posting_url, "jd_text": jd_text, "jd_html": jd_html,
        "posted_on": posted_on, "end_date": end_date, "raw": data,
    }


def build_spec(role_url: str, parts: dict, fetched: dict) -> dict:
    apply_url = fetched.get("posting_url") or role_url
    if apply_url and "/apply" not in apply_url and apply_url.endswith(parts["job_path"].split("/")[-1]):
        apply_url_apply = apply_url.rstrip("/") + "/apply"
    else:
        apply_url_apply = apply_url
    blockers = ["workday-form-fill-not-implemented"]
    if fetched.get("maintenance_mode"):
        blockers.append("workday-maintenance-mode")
    elif fetched.get("fetch_error"):
        blockers.append(f"workday-fetch-failed:{fetched['fetch_error'][:80]}")
    spec = {
        "ats": "workday",
        "role_url": role_url,
        "apply_url": apply_url,
        "apply_url_apply": apply_url_apply,
        "host": parts["host"],
        "tenant": parts["tenant"],
        "site": parts["site"],
        "job_path": parts["job_path"],
        "reqid": parts["reqid"],
        "job_title": fetched.get("title", ""),
        "job_location": fetched.get("location", ""),
        "posted_on": fetched.get("posted_on", ""),
        "end_date": fetched.get("end_date", ""),
        "jd_text": fetched.get("jd_text", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "maintenance_mode": bool(fetched.get("maintenance_mode")),
        "http_status": fetched.get("http_status", 0),
        "final_url": fetched.get("final_url", ""),
        "fetch_error": fetched.get("fetch_error", ""),
        "ready_to_submit": False,
        "blockers": blockers,
        "submit_mode": "manual",
        "notes": (
            "Prep-only pipeline. Workday auto-submit is not implemented "
            "(per-tenant variability + MFA + account creation). The packet "
            "(tailored resume + cover answers) is built for Cyrus to submit "
            "by hand at apply_url."
        ),
        # Compat: empty counts/fields so any tooling expecting GH-shape spec
        # doesn't NPE if it inspects it.
        "counts": {"total_fields": 0, "filled": 0, "filled_needs_review": 0,
                   "declined": 0, "unresolved": 0, "blockers": len(blockers)},
        "fields": [],
    }
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        parts = parse_workday_url(args.url)
    except ValueError as e:
        print(f"[workday_dryrun] URL parse failed: {e}", file=sys.stderr)
        return 2
    fetched = fetch_workday_job(parts, quiet=args.quiet)
    spec = build_spec(args.url, parts, fetched)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"workday-{parts['tenant']}-{parts['reqid']}.json"
    out_path.write_text(json.dumps(spec, indent=2, default=str) + "\n")
    if not args.quiet:
        print(f"[workday_dryrun] wrote {out_path}")
        if spec["maintenance_mode"]:
            print("[workday_dryrun] WARNING: Workday is in maintenance mode; JD body empty.")
        elif spec.get("fetch_error"):
            print(f"[workday_dryrun] WARNING: fetch error: {spec['fetch_error']}")
        else:
            print(f"[workday_dryrun] title={spec['job_title']!r} loc={spec['job_location']!r} "
                  f"jd_chars={len(spec['jd_text'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
