#!/usr/bin/env python3
"""Phase 1 — Build company→ATS mapping for LinkedIn-stranded rows.

For each stranded company:
  1. If already in companies.yaml → use that entry's ATS data verbatim.
  2. Otherwise, probe slug variants against Greenhouse / Ashby / Lever
     public board APIs (parallel). First hit with >=1 job wins.
  3. Big-name overrides: Google/Amazon/Uber/Deloitte don't have free public
     ATS APIs (custom/Workday-internal). Mark UNKNOWN — they need different
     handling.

Output: `_linkedin_stranded_ats_map.json` next to this script.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import yaml

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DB = PROJ / "tracker.db"
COMPANIES_YAML = HERE / "companies.yaml"
OUT = HERE / "_linkedin_stranded_ats_map.json"
sys.path.insert(0, str(HERE))

# Reuse the SAME company normalization the LinkedIn adapter / dedup / the better
# company-ATS resolver use, so "Docusign" lines up with companies.yaml's
# "DocuSign", "JP Morgan" with "JPMorgan Chase", etc. Exact-name matching missed
# these (the old yaml_by_name.get(c) was case/punct/whitespace sensitive).
from adapters.linkedin import _norm_company  # noqa: E402

# Statuses the brute resolver actually targets (mirror
# linkedin_stranded_brute_resolver.RESOLVABLE_STATUSES). The map MUST cover
# every company the resolver will look up; previously this builder only saw
# status IN ('','blocked') while the resolver also targets 'manual-apply' and
# 'queued' -> those companies were NEVER mapped -> the resolver got NO-ATS for
# the entire LinkedIn-stranded 'manual-apply' cohort (the real-world bulk).
RESOLVABLE_STATUSES = ("", "blocked", "manual-apply", "queued")

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}

# Companies known to NOT use the cheap public ATS APIs — mark UNKNOWN
# (they need workday-tenant-knowledge or custom adapters not buildable in this run).
KNOWN_UNKNOWN = {
    "Google": "custom Google careers ATS (no public board API)",
    "Amazon": "amazon.jobs custom ATS",
    "Amazon Web Services (AWS)": "amazon.jobs custom ATS",
    "Uber": "custom Uber careers ATS",
    "Deloitte": "custom Workday tenant requires auth gating",
    "Cisco": "in yaml as Workday",  # will use yaml
    "AMD": "custom Workday tenant",
    "Philips": "custom ATS",
    "Goldman Sachs": "in yaml as Workday",
    "JP Morgan": "in yaml as Workday",
    "Lockheed Martin": "in yaml as Workday (ITAR — never apply anyway)",
    "Tradeweb": "custom",
    "Nordstrom": "custom Workday",
    "Providence Health & Services": "custom Workday",
    "NBCUniversal": "icims (not in our adapter set)",
    "Paramount+": "icims/iCIMS variant",
    "Forbes": "custom careers site",
    "Tesla": "in yaml",
    "Snowflake": "in yaml as Ashby",
    "Netflix": "in yaml as Lever",
    "Atlassian": "in yaml as Workday",
    "Box": "in yaml as Workday",
    "Rivian": "in yaml as Workday",
    "monday.com": "monday.com Comeet ATS",
    "Schrödinger": "custom careers ATS",
    "Tri-State Energy": "small company, custom",
    "Storm2": "staffing firm — should be skipped anyway",
    "Sanderson King": "staffing firm",
    "Stefanini North America and APAC": "consulting staffing",
    "Yochana": "staffing",
    "Ursus, Inc.": "staffing",
    "Tanisha Systems, Inc": "staffing",
    "Stefanini": "staffing",
    "Alexander Chapman": "staffing",
    "Jack & Jill": "staffing",
    "Confiz": "staffing/consulting",
    "Altimetrik": "consulting",
}

# Companies known to use Workday that we can probe with curated tenants.
# Build off careers-page redirects others have documented.
WORKDAY_TENANT_HINTS = {
    # tenant, site
    "AMD": ("amd.wd1.myworkdayjobs.com", "amd", "External"),
    "Deloitte": ("deloitte.wd103.myworkdayjobs.com", "deloitte", "Deloitte_US_External_Careers"),
    "Philips": ("philips.wd3.myworkdayjobs.com", "philips", "jobs-and-careers"),
    "Cloudera Government Solutions": ("clouderagovernment.wd5.myworkdayjobs.com", "clouderagovernment", "External"),
    "First Advantage": ("fadv.wd1.myworkdayjobs.com", "fadv", "External"),
    "McKinstry": ("mckinstry.wd1.myworkdayjobs.com", "mckinstry", "External"),
    "Nordstrom": ("nordstrom.wd5.myworkdayjobs.com", "nordstrom", "nordstrom_careers"),
    "Tradeweb": ("tradeweb.wd1.myworkdayjobs.com", "tradeweb", "External"),
    "Providence Health & Services": ("providence.wd5.myworkdayjobs.com", "providence", "Providence-Careers"),
    "Trelleborg Sealing Solutions": ("trelleborg.wd3.myworkdayjobs.com", "trelleborg", "Trelleborg_External_Career_Site"),
    "Diligent": ("diligent.wd1.myworkdayjobs.com", "diligent", "External"),
}


def slug_variants(name: str) -> list[str]:
    s = (name or "").lower()
    s = re.sub(r"[\u2019']", "", s)  # apostrophes
    s = re.sub(r"\s*\([^)]*\)", "", s)  # strip parens (e.g., "Synth (YC S21)" → "synth")
    s = re.sub(r"&", "and", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    base = s
    no_corp = re.sub(r"\b(inc|llc|ltd|co|corp|the|ai)\b", "", s).strip()
    out = []
    for v in [base, no_corp]:
        v = v.strip()
        if not v:
            continue
        out.append(v.replace(" ", ""))
        out.append(v.replace(" ", "-"))
        out.append(v.replace(" ", "_"))
        # first-word-only (e.g., "BioCatch" → "biocatch")
        first = v.split(" ")[0]
        if first:
            out.append(first)
        # collapsed + "ai" appended
        if "ai" not in v:
            out.append(v.replace(" ", "") + "ai")
    # de-dupe preserving order
    seen = set()
    uniq = []
    for v in out:
        if v and v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq[:8]  # cap at 8 per company


def probe_greenhouse(slug: str) -> tuple[bool, int]:
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            headers=HEADERS, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            return (len(jobs) > 0, len(jobs))
    except Exception:
        pass
    return (False, 0)


def probe_ashby(slug: str) -> tuple[bool, int]:
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            headers=HEADERS, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            return (len(jobs) > 0, len(jobs))
    except Exception:
        pass
    return (False, 0)


def probe_lever(slug: str) -> tuple[bool, int]:
    try:
        r = requests.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            headers=HEADERS, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return (len(data) > 0, len(data))
    except Exception:
        pass
    return (False, 0)


def probe_workday(host: str, tenant: str, site: str) -> tuple[bool, int]:
    """POST to Workday CXS jobs endpoint with empty searchText to get job count."""
    try:
        r = requests.post(
            f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
            json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            return (total > 0, total)
    except Exception:
        pass
    return (False, 0)


def probe_one_company(name: str) -> dict:
    """Try all slug variants × all 3 ATSes. Return first hit."""
    variants = slug_variants(name)
    if not variants:
        return {"company": name, "ats": "UNKNOWN", "reason": "no-slug-derivable"}

    # Try in priority order: Greenhouse > Ashby > Lever. Each ATS gets all variants.
    for ats, probe_fn in [
        ("greenhouse", probe_greenhouse),
        ("ashby", probe_ashby),
        ("lever", probe_lever),
    ]:
        for v in variants:
            ok, n = probe_fn(v)
            if ok:
                return {
                    "company": name, "ats": ats, "slug": v,
                    "jobs_count": n, "variants_tried": variants,
                }
    return {
        "company": name, "ats": "UNKNOWN",
        "reason": "no-public-board-hit",
        "variants_tried": variants,
    }


def main() -> int:
    con = sqlite3.connect(str(DB))
    _status_in = ", ".join("'%s'" % s for s in RESOLVABLE_STATUSES)
    rows = con.execute(
        "SELECT DISTINCT company FROM roles "
        f"WHERE status IN ({_status_in}) "
        "AND (applied_by IS NULL OR applied_by='') "
        "AND app_url LIKE '%linkedin.com%' "
        "ORDER BY company"
    ).fetchall()
    companies = [r[0] for r in rows]
    con.close()
    print(f"[phase1] {len(companies)} distinct stranded companies", flush=True)

    yaml_data = yaml.safe_load(COMPANIES_YAML.read_text())
    # Index by BOTH exact name and normalized name; normalized lookup catches
    # case/punctuation/suffix differences ("Docusign"->"DocuSign",
    # "Gamma Reality Inc."->"Gamma"). Exact name wins first to avoid a
    # normalized collision overriding an intentional exact entry.
    yaml_by_name = {c.get("name"): c for c in (yaml_data.get("companies") or [])}
    yaml_by_norm: dict[str, dict] = {}
    for c in (yaml_data.get("companies") or []):
        if not c.get("adapter"):
            continue
        k = _norm_company(c.get("name") or "")
        if k:
            yaml_by_norm.setdefault(k, c)  # first write wins

    mapping: dict[str, dict] = {}
    to_probe: list[str] = []

    for c in companies:
        # 1. yaml hit (exact name, then normalized)
        yaml_entry = yaml_by_name.get(c)
        if not (yaml_entry and yaml_entry.get("adapter")):
            yaml_entry = yaml_by_norm.get(_norm_company(c or ""))
        if yaml_entry and yaml_entry.get("adapter"):
            # already known
            mapping[c] = {
                "company": c, "ats": yaml_entry["adapter"],
                "slug": yaml_entry.get("slug"),
                "host": yaml_entry.get("host"),
                "tenant": yaml_entry.get("tenant"),
                "site": yaml_entry.get("site"),
                "source": "yaml",
                "skip": yaml_entry.get("skip", False),
                "skip_reason": yaml_entry.get("reason"),
            }
            continue
        # 2. known unknown
        if c in KNOWN_UNKNOWN:
            mapping[c] = {
                "company": c, "ats": "UNKNOWN",
                "reason": KNOWN_UNKNOWN[c], "source": "known-unknown",
            }
            continue
        # 3. workday-tenant hint
        if c in WORKDAY_TENANT_HINTS:
            host, tenant, site = WORKDAY_TENANT_HINTS[c]
            ok, n = probe_workday(host, tenant, site)
            if ok:
                mapping[c] = {
                    "company": c, "ats": "workday",
                    "host": host, "tenant": tenant, "site": site,
                    "jobs_count": n, "source": "workday-hint",
                }
                continue
            else:
                # fall through to probe
                pass
        to_probe.append(c)

    print(f"[phase1] yaml hits: {sum(1 for v in mapping.values() if v.get('source')=='yaml')}", flush=True)
    print(f"[phase1] known-unknown: {sum(1 for v in mapping.values() if v.get('source')=='known-unknown')}", flush=True)
    print(f"[phase1] workday-hint hits: {sum(1 for v in mapping.values() if v.get('source')=='workday-hint')}", flush=True)
    print(f"[phase1] to probe: {len(to_probe)}", flush=True)

    # Parallel probe with ThreadPool
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(probe_one_company, c): c for c in to_probe}
        for i, fut in enumerate(as_completed(futures), 1):
            c = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"company": c, "ats": "UNKNOWN", "reason": f"exc:{e}"}
            res["source"] = "probe"
            mapping[c] = res
            tag = res.get("ats", "?")
            slug = res.get("slug", "")
            print(f"  [{i}/{len(to_probe)}] {c}: {tag} {slug}", flush=True)

    # Summarize
    by_ats: dict[str, int] = {}
    for v in mapping.values():
        by_ats[v.get("ats", "?")] = by_ats.get(v.get("ats", "?"), 0) + 1

    OUT.write_text(json.dumps({
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "company_count": len(mapping),
        "by_ats": by_ats,
        "mapping": mapping,
    }, indent=2))
    print(f"\n[phase1] DONE — wrote {OUT}", flush=True)
    print(f"[phase1] by_ats: {by_ats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
