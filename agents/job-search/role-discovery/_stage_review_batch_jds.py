#!/usr/bin/env python3
"""One-off (2026-05-31): stage JD.md for review-batch rows from LinkedIn guest API.
Fetches the JD description text (no auth needed) and writes it to
applications/queued/<org>-<id>/JD.md with the role title as the first line.
Review-only batch; does NOT touch the tracker or submit anything.
"""
import re, html, sys, subprocess, pathlib

HERE = pathlib.Path(__file__).resolve().parent
QUEUED = HERE.parent / "applications" / "queued"

# (role_id, linkedin_numeric_id, org_slug, title)
ROWS = [
    (703,  "4404688198", "jpmorgan",   "Product Manager, Associate - Crypto Trading"),
    (1020, "4414248511", "paramount",  "Associate Product Manager, Content Discovery"),
    (1043, "4413463879", "mckinstry",  "Product Manager"),
    (1466, "4408397150", "philips",    "Upstream Product Manager - Ultrasound"),
    (1476, "4418660173", "tesla",      "Technical Program Manager, New Product Introduction"),
    (1491, "4418690778", "tesla",      "Technical Program Manager, Electronic Systems, Displays"),
    (1510, "4416385552", "providence", "Engineering Program Manager II"),
    (1303, "4415403081", "cloudera",   "Solutions Engineer"),
    (1546, "4416492098", "cisco",      "Solutions Engineer - Technical Program Manager"),
    (1602, "4409030197", "friedfrank", "Cloud Solutions Architect"),
]

def fetch_jd(li_id: str) -> str:
    raw = subprocess.run(
        ["curl", "-s", "-A", "Mozilla/5.0",
         f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{li_id}"],
        capture_output=True, text=True).stdout
    m = re.search(r'description__text[^>]*>(.*?)</section>', raw, re.S)
    if not m:
        return ""
    body = m.group(1)
    body = re.sub(r'<br\s*/?>', '\n', body)
    body = re.sub(r'</li>', '\n', body)
    body = re.sub(r'<[^>]+>', '', body)
    body = html.unescape(body)
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    return body

def main():
    for rid, li, org, title in ROWS:
        jd = fetch_jd(li)
        if len(jd) < 500:
            print(f"SKIP id={rid} {org}: JD too short ({len(jd)} chars)")
            continue
        d = QUEUED / f"{org}-{rid}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "JD.md").write_text(f"# {title}\n\n{jd}\n")
        print(f"OK   id={rid} {org}-{rid}: JD.md staged ({len(jd)} chars)")

if __name__ == "__main__":
    main()
