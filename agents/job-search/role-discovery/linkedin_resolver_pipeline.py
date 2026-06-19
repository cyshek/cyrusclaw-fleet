#!/usr/bin/env python3
"""LinkedIn → ATS resolver, weekly-pipeline edition.

Runs against `tracker.db` after `tracker_merger.py` has inserted fresh
LinkedIn-discovery rows and BEFORE `jd_llm_classifier.py`. Goal: replace
`linkedin.com/jobs/view/<id>` app_urls with the real ATS URL so the
classifier (and downstream auto-apply) can pick the role up.

Tactic ladder (free / no auth):
  1. **companies.yaml match** — if the row's company has a known adapter
     entry, look up the latest crawl JSON (`output/*-roles.json`) for a
     matching (company, title) and reuse the ATS URL discovered there.
  2. **LinkedIn JD fetch + ATS regex** — fetch the LinkedIn public job
     posting HTML and regex-scan for off-site ATS URLs
     (greenhouse / ashby / lever / workday / smartrecruiters).
  3. **Careers-page probe** — try common `careers.<co>.com` / `<co>.com/careers`
     URL shapes, scan returned HTML for off-site ATS URLs.

Adapted from `projects/job-search/linkedin_resolve.py` (the one-off Cyrus
ran 2026-05-24) with the following corrections:
- Notes go to `agent_notes`, NOT `cyrus_notes` (the one-off had this bug).
- No xlsx regen (weekly pipeline already calls `render_xlsx.py` later).
- `--dry-run` is the safety default-flag; `--apply` required to mutate DB.
- Hard cap on per-row timeout + total runtime (default 15min).

CLI:
    linkedin_resolver_pipeline.py [--limit N] [--apply] [--max-seconds 900]

By default runs dry-run (prints summary, no DB writes). Pass `--apply` to
commit.

Exit codes:
  0 — ran successfully (regardless of resolution rate)
  1 — fatal error (couldn't open DB, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests
import yaml

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DB = PROJ / "tracker.db"
COMPANIES_YAML = HERE / "companies.yaml"
OUTPUT_DIR = HERE / "output"
LOG_DIR = PROJ / "applications"

DEFAULT_TIMEOUT = 15
DEFAULT_MAX_SECONDS = 900  # 15min

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ATS_DOMAINS_RX = re.compile(
    r"(?:greenhouse\.io|boards\.greenhouse|job-boards\.greenhouse|"
    r"jobs\.lever\.co|jobs\.ashbyhq\.com|myworkdayjobs\.com|"
    r"smartrecruiters\.com|workable\.com|bamboohr\.com|recruitee\.com|"
    r"jobvite\.com|icims\.com|breezy\.hr|teamtailor\.com)",
    re.I,
)


# ---------------------------------------------------------------------------
# Normalization helpers (shared semantics with linkedin_resolve.py)
# ---------------------------------------------------------------------------

def normalize_title(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" sr ", " senior ").replace(" jr ", " junior ")
    s = re.sub(r"\bpm\b", "product manager", s)
    s = re.sub(r"\btpm\b", "technical program manager", s)
    return s


def title_match(a: str, b: str) -> float:
    """[0,1] score, ≥0.7 = high confidence."""
    common = {
        "manager", "product", "senior", "junior", "a", "the",
        "i", "ii", "iii", "iv", "and", "&", "of", "for",
    }
    sa = set(normalize_title(a).split())
    sb = set(normalize_title(b).split())
    sa2, sb2 = sa - common, sb - common
    if not sa2 or not sb2:
        sa2, sb2 = sa, sb
    if not sa2 or not sb2:
        return 0.0
    overlap = len(sa2 & sb2) / max(len(sa2), len(sb2))
    na, nb = normalize_title(a), normalize_title(b)
    if na in nb or nb in na:
        overlap = max(overlap, 0.85)
    return overlap


def norm_company(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (c or "").lower())


def company_slug_candidates(company: str) -> list[str]:
    base = re.sub(r"[^a-z0-9 ]", "", (company or "").lower()).strip()
    base = re.sub(r"\b(inc|llc|ltd|co|corp|the)\b", "", base).strip()
    base = re.sub(r"\s+", "", base)
    cands: list[str] = []
    if base:
        cands.append(base)
    h = re.sub(r"[^a-z0-9]+", "-", (company or "").lower()).strip("-")
    h = re.sub(r"-(inc|llc|ltd|co|corp|the)$", "", h)
    if h and h != base:
        cands.append(h)
    return cands


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except Exception:
        return None


def load_companies_yaml(path: Path = COMPANIES_YAML) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("companies", []) or []


def load_latest_roles_json(output_dir: Path = OUTPUT_DIR) -> list[dict]:
    files = sorted(output_dir.glob("*-roles.json"))
    if not files:
        return []
    try:
        with files[-1].open() as f:
            return json.load(f)
    except Exception:
        return []


def extract_ats_urls_from_html(html: str) -> list[str]:
    if not html:
        return []
    urls: set[str] = set()
    for m in re.finditer(r"https?://[^\s\"'<>]+", html):
        u = m.group(0).rstrip(".,);]\"'<>")
        if ATS_DOMAINS_RX.search(u):
            urls.add(u)
    return list(urls)


# ---------------------------------------------------------------------------
# Tactics
# ---------------------------------------------------------------------------

def tactic_yaml_match(
    company: str, role_title: str, yaml_cos: list[dict], roles_idx: list[dict]
) -> tuple[Optional[str], str]:
    cnorm = norm_company(company)
    if not cnorm:
        return None, ""
    for entry in yaml_cos:
        name = entry.get("name", "") or ""
        nnorm = norm_company(name)
        if not nnorm:
            continue
        is_match = (
            cnorm == nnorm
            or (cnorm in nnorm and len(cnorm) > 3)
            or (nnorm in cnorm and len(nnorm) > 3)
        )
        if not is_match:
            continue
        best_score, best_role = 0.0, None
        for r in roles_idx:
            if r.get("company") != name:
                continue
            score = title_match(role_title, r.get("title", ""))
            if score > best_score:
                best_score, best_role = score, r
        if best_role and best_score >= 0.7:
            url = best_role.get("url")
            if url:
                return url, f"yaml({entry.get('adapter')}) score={best_score:.2f}"
        if best_role:
            return None, f"yaml-near-miss(best={best_score:.2f})"
        return None, "yaml-listed-no-roles-match"
    return None, ""


def tactic_linkedin_fetch(
    linkedin_url: str, company: str
) -> tuple[Optional[str], str]:
    if not linkedin_url:
        return None, "no-linkedin-url"
    r = http_get(linkedin_url)
    if not r or r.status_code != 200:
        return None, f"linkedin-status={r.status_code if r else 'err'}"
    ats_urls = extract_ats_urls_from_html(r.text)
    if not ats_urls:
        return None, "linkedin-no-ats"
    cnorm = norm_company(company)
    scored: list[tuple[int, str]] = []
    for u in ats_urls:
        unorm = re.sub(r"[^a-z0-9]", "", u.lower())
        score = 1 if cnorm and cnorm in unorm else 0
        scored.append((score, u))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1], f"linkedin-jd(found={len(ats_urls)})"


def tactic_careers_page(company: str) -> tuple[Optional[str], str]:
    slugs = company_slug_candidates(company)
    if not slugs:
        return None, "no-slug"
    bases: list[str] = []
    for s in slugs:
        bases.extend(
            [
                f"https://www.{s}.com/careers",
                f"https://{s}.com/careers",
                f"https://careers.{s}.com",
                f"https://www.{s}.com/jobs",
                f"https://jobs.{s}.com",
            ]
        )
    cnorm = norm_company(company)
    seen: set[str] = set()
    for url in bases:
        if url in seen:
            continue
        seen.add(url)
        r = http_get(url, timeout=10)
        if not r or r.status_code >= 400:
            continue
        ats_urls = extract_ats_urls_from_html(r.text)
        if not ats_urls:
            continue
        for u in ats_urls:
            unorm = re.sub(r"[^a-z0-9]", "", u.lower())
            if cnorm and cnorm in unorm:
                return u, f"careers({url})"
        return ats_urls[0], f"careers({url}) generic"
    return None, "careers-tried"


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def derive_source_key(ats_url: str) -> str:
    u = urlparse(ats_url)
    host = (u.netloc or "").lower()
    path = u.path or ""
    if "greenhouse.io" in host or "boards.greenhouse" in host or "job-boards.greenhouse" in host:
        m = re.search(r"/(?:embed/job_app\?for=|)([^/]+)/jobs/(\d+)", path)
        if m:
            return f"greenhouse:{m.group(1)}:{m.group(2)}"
        m = re.search(r"gh_jid=(\d+)", ats_url)
        if m:
            m2 = re.search(r"jobs\.([a-z0-9-]+)\.com", host)
            return f"greenhouse:{m2.group(1) if m2 else 'unknown'}:{m.group(1)}"
        return f"greenhouse:unknown:{int(time.time())}"
    if "lever.co" in host:
        m = re.search(r"/([^/]+)/([0-9a-f-]+)", path)
        if m:
            return f"lever:{m.group(1)}:{m.group(2)}"
        return f"lever:unknown:{int(time.time())}"
    if "ashbyhq.com" in host:
        m = re.search(r"/([^/]+)/([0-9a-f-]+)", path)
        if m:
            return f"ashby:{m.group(1)}:{m.group(2)}"
        return f"ashby:unknown:{int(time.time())}"
    if "myworkdayjobs.com" in host:
        m = re.search(r"/job/[^/]+/[^/]+/([^/?_]+)", path)
        jid = m.group(1) if m else str(int(time.time()))
        tenant = host.split(".")[0]
        return f"workday:{tenant}:{jid}"
    if "smartrecruiters.com" in host:
        m = re.search(r"/([^/]+)/(\d+)", path)
        if m:
            return f"smartrecruiters:{m.group(1)}:{m.group(2)}"
    return f"ats:{host}:{int(time.time())}"


SELECT_TARGETS_SQL = """
    SELECT id, company, role, app_url
    FROM roles
    WHERE source_key LIKE 'linkedin:%'
      AND (status IS NULL OR status='')
      AND applied_by IS NULL
      AND (app_url LIKE '%linkedin.com%' OR app_url IS NULL)
      AND (agent_notes IS NULL OR agent_notes NOT LIKE 'LINKEDIN-PIPELINE %')
    ORDER BY id
"""


def fetch_targets(con: sqlite3.Connection, limit: Optional[int]) -> list[tuple]:
    rows = con.execute(SELECT_TARGETS_SQL).fetchall()
    if limit:
        rows = rows[:limit]
    return rows


def write_resolved(
    con: sqlite3.Connection, role_id: int, new_url: str, source_key: str,
    tactic_info: str, linkedin_url: str, stamp: str
) -> None:
    note = (
        f"LINKEDIN-PIPELINE {stamp}: resolved via {tactic_info} | "
        f"original: {linkedin_url or ''}"
    )
    con.execute(
        "UPDATE roles SET app_url=?, source_key=?, agent_notes=? WHERE id=?",
        (new_url, source_key, note, role_id),
    )


def write_unresolved(
    con: sqlite3.Connection, role_id: int, reasons: list[str], stamp: str
) -> None:
    note = (
        f"LINKEDIN-PIPELINE {stamp}: UNRESOLVED | "
        f"tried: yaml,linkedin-jd,careers | reasons: {'; '.join(reasons)}"
    )
    con.execute(
        "UPDATE roles SET agent_notes=? WHERE id=?",
        (note, role_id),
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def resolve_one(
    company: str, role: str, linkedin_url: str,
    yaml_cos: list[dict], roles_idx: list[dict],
) -> tuple[Optional[str], Optional[str], list[str]]:
    """Return (ats_url, tactic_info, all_reasons)."""
    reasons: list[str] = []

    url, info = tactic_yaml_match(company, role, yaml_cos, roles_idx)
    if info:
        reasons.append(info)
    if url:
        return url, info, reasons

    url, info = tactic_linkedin_fetch(linkedin_url, company)
    if info:
        reasons.append(info)
    if url:
        return url, info, reasons

    url, info = tactic_careers_page(company)
    if info:
        reasons.append(info)
    if url:
        return url, info, reasons

    return None, None, reasons


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Max rows to attempt (0 = no limit)")
    ap.add_argument("--apply", action="store_true",
                    help="Actually write to tracker.db (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Force dry-run (default behaviour; explicit override)")
    ap.add_argument("--max-seconds", type=int, default=DEFAULT_MAX_SECONDS)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    write_mode = args.apply and not args.dry_run
    log = (lambda *a, **k: None) if args.quiet else print

    yaml_cos = load_companies_yaml()
    roles_idx = load_latest_roles_json()
    log(f"[linkedin-pipeline] yaml-companies={len(yaml_cos)} roles-idx={len(roles_idx)} "
        f"db={args.db} mode={'APPLY' if write_mode else 'DRY-RUN'}", flush=True)

    try:
        con = sqlite3.connect(args.db)
    except Exception as e:
        print(f"[linkedin-pipeline] FATAL: can't open DB {args.db}: {e}", file=sys.stderr)
        return 1

    targets = fetch_targets(con, args.limit or None)
    log(f"[linkedin-pipeline] targets: {len(targets)}", flush=True)

    stamp = datetime.now().strftime("%Y-%m-%d")
    start = time.time()
    resolved = unresolved = 0
    by_ats: dict[str, int] = {}
    sample_rows: list[dict] = []

    for i, row in enumerate(targets, 1):
        if time.time() - start > args.max_seconds:
            log(f"[linkedin-pipeline] time-budget exhausted at row {i-1}", flush=True)
            break
        rid, company, role_title, app_url = row
        linkedin_url = app_url or ""
        try:
            ats_url, tactic_info, reasons = resolve_one(
                company or "", role_title or "", linkedin_url, yaml_cos, roles_idx
            )
        except Exception as e:
            reasons = [f"exc:{type(e).__name__}:{e}"]
            ats_url, tactic_info = None, None

        if ats_url:
            sk = derive_source_key(ats_url)
            ats = sk.split(":", 1)[0]
            by_ats[ats] = by_ats.get(ats, 0) + 1
            resolved += 1
            sample_rows.append({
                "id": rid, "company": company, "role": role_title,
                "ats": ats, "url": ats_url, "tactic": tactic_info,
            })
            if write_mode:
                write_resolved(con, rid, ats_url, sk, tactic_info or "?", linkedin_url, stamp)
        else:
            unresolved += 1
            if write_mode:
                write_unresolved(con, rid, reasons, stamp)

        # commit every 25 rows to limit blast radius if interrupted
        if write_mode and i % 25 == 0:
            con.commit()

    if write_mode:
        con.commit()
    con.close()

    summary = {
        "mode": "apply" if write_mode else "dry-run",
        "attempted": resolved + unresolved,
        "resolved": resolved,
        "unresolved": unresolved,
        "by_ats": by_ats,
        "elapsed_sec": int(time.time() - start),
        "sample_resolved": sample_rows[:5],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
