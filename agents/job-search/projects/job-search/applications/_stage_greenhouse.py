#!/usr/bin/env python3
"""Stage per-role application packets for queued Greenhouse roles."""
from __future__ import annotations
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]  # projects/job-search/
TRACKER = ROOT / "tracker.md"
PERSONAL = ROOT / "personal-info.json"
OUT = ROOT / "applications" / "queued"
ERR = OUT / "FETCH-ERRORS.md"
INDEX = OUT / "INDEX.md"

OUT.mkdir(parents=True, exist_ok=True)

GH_PATTERNS = [
    re.compile(r"https?://job-boards\.greenhouse\.io/([^/]+)/jobs/(\d+)"),
    re.compile(r"https?://boards\.greenhouse\.io/([^/]+)/jobs/(\d+)"),
    re.compile(r"https?://([a-z0-9-]+)\.greenhouse\.io/(?:jobs|job-boards/[^/]+/jobs)/(\d+)"),
    # company-hosted /careers/jobs/{id}?gh_jid={id} — slug = subdomain or path part
    re.compile(r"https?://(?:www\.)?([a-z0-9-]+)\.(?:ai|com|io|co)/careers/jobs/(\d+)\?gh_jid=\d+"),
]

ORG_OVERRIDES = {
    # company host (lowercased) -> greenhouse board token
    "abnormal": "abnormalsecurity",
    "abnormalsecurity": "abnormalsecurity",
}


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_]+", "-", s)[:60]


def html_to_md(html: str) -> str:
    # GH returns HTML-entity-encoded HTML (e.g. &lt;p&gt;), so unescape first to reveal real tags,
    # then strip / convert. A second unescape after handles entities inside text.
    s = unescape(html)
    # block tags -> newlines
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</p>", "\n\n", s)
    s = re.sub(r"(?is)</div>", "\n", s)
    s = re.sub(r"(?is)</li>", "\n", s)
    s = re.sub(r"(?is)<li[^>]*>", "- ", s)
    s = re.sub(r"(?is)</h[1-6]>", "\n\n", s)
    s = re.sub(r"(?is)<h([1-6])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", s)
    s = re.sub(r"(?is)<strong[^>]*>(.*?)</strong>", r"**\1**", s)
    s = re.sub(r"(?is)<b[^>]*>(.*?)</b>", r"**\1**", s)
    s = re.sub(r"(?is)<em[^>]*>(.*?)</em>", r"*\1*", s)
    s = re.sub(r"(?is)<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", s)
    # strip remaining tags
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = unescape(s)
    # collapse whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_tracker():
    """Yield queued Greenhouse rows."""
    rows = []
    for line in TRACKER.read_text().splitlines():
        if not line.startswith("|"):
            continue
        if "| queued |" not in line:
            continue
        # Split on unescaped pipes only. Replace escaped \| with a placeholder, split, restore.
        SENT = "\x00PIPE\x00"
        safe = line.replace(r"\|", SENT)
        parts = [c.replace(SENT, "|").strip() for c in safe.split("|")]
        # |  | Company | Role | Level | Loc | Exp | JD | App | Status | Flags |
        if len(parts) < 10:
            continue
        company, role, level, loc, exp, jd_md, app_url, status = parts[1:9]
        flags = parts[9] if len(parts) > 9 else ""
        # extract URL
        url_match = re.search(r"https?://\S+", app_url) or re.search(r"https?://[^\s)]+", jd_md)
        if not url_match:
            continue
        url = url_match.group(0).rstrip(")")
        # only greenhouse
        gh = match_gh(url)
        if not gh:
            continue
        org, jid = gh
        rows.append({
            "company": company,
            "role": role,
            "level": level,
            "location": loc,
            "exp_required": exp,
            "apply_url": url,
            "jd_url": url,
            "ats": "greenhouse",
            "gh_org": org,
            "gh_jid": jid,
            "flags": flags,
        })
    return rows


def match_gh(url: str):
    for pat in GH_PATTERNS:
        m = pat.search(url)
        if m:
            org, jid = m.group(1), m.group(2)
            org = ORG_OVERRIDES.get(org.lower(), org.lower())
            return org, jid
    return None


def fetch_gh(org: str, jid: str):
    api = f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs/{jid}"
    r = requests.get(api, timeout=15, headers={"User-Agent": "job-search-agent/1.0"})
    r.raise_for_status()
    return r.json()


def main():
    personal = json.loads(PERSONAL.read_text())
    rows = parse_tracker()
    print(f"Found {len(rows)} queued Greenhouse rows")

    errors = []
    staged = []
    seen_dirs = set()

    for i, row in enumerate(rows, 1):
        slug = slugify(row["company"])
        dirname = f"{slug}-{row['gh_jid']}"
        if dirname in seen_dirs:
            # disambiguate by role
            dirname = f"{slug}-{slugify(row['role'])[:30]}-{row['gh_jid']}"
        seen_dirs.add(dirname)
        pkt = OUT / dirname

        try:
            data = fetch_gh(row["gh_org"], row["gh_jid"])
        except Exception as e:
            errors.append(f"- **{row['company']} — {row['role']}** ({row['apply_url']}): {type(e).__name__}: {e}")
            print(f"  [{i}/{len(rows)}] ERR {row['company']} {row['gh_jid']}: {e}")
            continue

        pkt.mkdir(parents=True, exist_ok=True)

        title = data.get("title", row["role"])
        loc = (data.get("location") or {}).get("name", row["location"])
        absolute_url = data.get("absolute_url", row["apply_url"])
        content_html = data.get("content", "")
        jd_md = html_to_md(content_html)

        (pkt / "JD.md").write_text(
            f"# {title}\n\n**Company:** {row['company']}\n**Location:** {loc}\n"
            f"**Apply:** {absolute_url}\n**Greenhouse ID:** {row['gh_jid']}\n\n---\n\n{jd_md}\n"
        )

        meta = {
            "company": row["company"],
            "role": title,
            "location": loc,
            "exp_required": row["exp_required"],
            "apply_url": absolute_url,
            "jd_url": absolute_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ats": "greenhouse",
            "gh_org": row["gh_org"],
            "gh_jid": row["gh_jid"],
            "flags": row["flags"],
        }
        (pkt / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

        # prefill = flat copy of personal-info.json (placeholder; Track B will improve)
        (pkt / "prefill.json").write_text(json.dumps(personal, indent=2) + "\n")

        (pkt / "STATUS.md").write_text("queued — not yet submitted\n")

        staged.append({
            "dir": dirname,
            "company": row["company"],
            "role": title,
            "location": loc,
            "apply_url": absolute_url,
        })
        print(f"  [{i}/{len(rows)}] OK  {row['company']} — {title}")
        time.sleep(0.5)

    # INDEX.md
    lines = [
        "# Queued Application Packets (Greenhouse)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Total packets: {len(staged)}  |  Fetch errors: {len(errors)}",
        "",
        "Each folder contains: `JD.md`, `meta.json`, `prefill.json`, `STATUS.md`.",
        "Edit `STATUS.md` after manual submit (e.g. 'submitted 2026-05-08').",
        "",
        "| # | Company | Role | Location | Packet | Apply |",
        "| - | ------- | ---- | -------- | ------ | ----- |",
    ]
    for i, s in enumerate(sorted(staged, key=lambda x: (x["company"].lower(), x["role"].lower())), 1):
        loc_safe = s["location"].replace("|", "\\|")
        role_safe = s["role"].replace("|", "\\|")
        company_safe = s["company"].replace("|", "\\|")
        lines.append(
            f"| {i} | {company_safe} | {role_safe} | {loc_safe} | "
            f"[`{s['dir']}/`](./{s['dir']}/) | [apply]({s['apply_url']}) |"
        )
    INDEX.write_text("\n".join(lines) + "\n")

    if errors:
        ERR.write_text(
            "# Fetch errors\n\n"
            f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            + "\n".join(errors) + "\n"
        )
    elif ERR.exists():
        ERR.unlink()

    print(f"\nDone. Staged {len(staged)} packets, {len(errors)} errors.")


if __name__ == "__main__":
    main()
