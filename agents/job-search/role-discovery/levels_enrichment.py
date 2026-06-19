"""Levels.fyi compensation enrichment for the job-search tracker.

Goal: ADD comp estimates per company. Companies without Levels data
get NULL — never a penalty, never a filter. Comp is a tie-breaker /
prioritization signal on top of the existing ranking.

Data source:
  https://www.levels.fyi/company/<slug>/salaries/software-engineer
  https://www.levels.fyi/company/<slug>/salaries/product-manager

The page server-side renders a JSON blob in <script id="__NEXT_DATA__"> which
includes:
  pageProps.percentiles.tc.p50         -> median total comp
  pageProps.averages[*].count          -> sample counts per level
  pageProps.company                    -> verified company info

Slug resolution: try a handful of deterministic name transforms,
HTTP-probe each, cache the first 200. 404s are cheap.

Store in `company_comp` table; populate `roles.est_tc` by JOIN.

Usage:
  python3 levels_enrichment.py                 # enrich all stale companies
  python3 levels_enrichment.py --refresh-days 60
  python3 levels_enrichment.py --dry-run
  python3 levels_enrichment.py --only Anthropic Stripe Apple
  python3 levels_enrichment.py --populate-roles  # only fill roles.est_tc
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import urllib.request
import urllib.error

import requests
import yaml

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
from tracker_db import connect, DB_PATH  # noqa: E402

COMPANIES_YAML = THIS / "companies.yaml"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]
BASE = "https://www.levels.fyi"
REQ_DELAY = 1.8
LONG_COOLDOWN_EVERY = 60
LONG_COOLDOWN_SECS = 20
TIMEOUT = 25

JOB_FAMILIES = [
    ("software-engineer", "sw_engineer"),
    ("product-manager",   "pm"),
]

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)


_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.levels.fyi/",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Upgrade-Insecure-Requests": "1",
})

_req_count = [0]


def _rotate_ua():
    import random
    _SESSION.headers["User-Agent"] = random.choice(UAS)


def http_get(url: str, max_retries: int = 4) -> tuple[int, str]:
    """Polite GET via curl subprocess.

    Why curl? Python's requests/urllib have TLS fingerprints that Cloudflare
    on levels.fyi flags and serves 502/405 to, while curl breezes through.
    Tested: requests gets blocked after ~20 reqs; curl handles hundreds clean.
    """
    import random, subprocess
    _req_count[0] += 1
    if _req_count[0] % LONG_COOLDOWN_EVERY == 0:
        print(f"[cooldown] {LONG_COOLDOWN_SECS}s pause after {_req_count[0]} reqs", flush=True)
        time.sleep(LONG_COOLDOWN_SECS)

    ua = random.choice(UAS)
    last_status = 0
    for attempt in range(max_retries):
        try:
            proc = subprocess.run(
                [
                    "curl", "-sL", "--compressed",
                    "-A", ua,
                    "-H", "Referer: https://www.levels.fyi/",
                    "-H", "Accept: text/html,application/xhtml+xml",
                    "-H", "Accept-Language: en-US,en;q=0.9",
                    "-w", "\n__HTTP_STATUS__%{http_code}",
                    "--max-time", str(TIMEOUT),
                    url,
                ],
                capture_output=True, text=True, timeout=TIMEOUT + 5,
            )
        except subprocess.TimeoutExpired:
            time.sleep(3 * (attempt + 1))
            continue
        out = proc.stdout
        # Extract trailing status line
        if "__HTTP_STATUS__" in out:
            body, status_line = out.rsplit("\n__HTTP_STATUS__", 1)
            try:
                last_status = int(status_line.strip())
            except ValueError:
                last_status = 0
        else:
            body = out
            last_status = 0
        if last_status == 200:
            return 200, body
        if last_status in (404, 410):
            return last_status, ""
        if last_status in (405, 429, 502, 503, 504, 0):
            sleep_for = 15 + (2 ** attempt) * 10 + random.uniform(0, 5)
            print(f"[throttle] {last_status} on {url[-60:]} — sleep {sleep_for:.0f}s (try {attempt+1})", flush=True)
            time.sleep(sleep_for)
            ua = random.choice(UAS)
            continue
        return last_status, ""
    return last_status, ""


def candidate_slugs(name: str) -> list[str]:
    """Generate plausible Levels.fyi slugs for a company name."""
    n = name.strip()
    base = n.lower()
    base = re.sub(r"[''`]", "", base)
    base = re.sub(r"&", " and ", base)
    base = re.sub(r"\.(ai|io|com|co|app)\b", "", base)
    base = re.sub(r"[^a-z0-9]+", " ", base).strip()
    parts = base.split()

    cands: list[str] = []

    def add(s: str):
        s = re.sub(r"-+", "-", s).strip("-")
        if s and s not in cands:
            cands.append(s)

    # 1. exact join with dashes
    add("-".join(parts))
    # 2. concatenated (no dashes)
    add("".join(parts))
    # 3. drop common corporate suffixes / qualifiers
    stop = {"inc", "labs", "lab", "the", "and", "technologies", "tech",
            "platform", "platforms", "co", "corp", "corporation", "ltd",
            "holdings", "group", "ai", "company"}
    filtered = [p for p in parts if p not in stop]
    if filtered != parts:
        add("-".join(filtered))
        add("".join(filtered))
    # 4. just the first token (e.g. "Scale AI" -> "scale")
    if len(parts) > 1:
        add(parts[0])
    # 5. common suffix variants that Levels uses
    base_join = "-".join(parts)
    base_concat = "".join(parts)
    for suf in ("-ai", "-labs", "-inc", "-chase"):
        add(base_join + suf)
        add(base_concat + suf)
    # 6. drop trailing 'inc'/'ai' suffix from name (e.g. SnapInc -> snap covered above)

    return cands


def parse_next_data(html: str) -> Optional[dict]:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def extract_comp(html: str) -> Optional[dict]:
    """Returns {p50: int, sample_count: int, levels: int, company_slug: str, company_name: str} or None."""
    data = parse_next_data(html)
    if not data:
        return None
    try:
        pp = data["props"]["pageProps"]
    except (KeyError, TypeError):
        return None
    company = pp.get("company") or {}
    pct = (pp.get("percentiles") or {}).get("tc") or {}
    p50 = pct.get("p50")
    averages = pp.get("averages") or []
    sample_count = sum(int(a.get("count") or 0) for a in averages)
    if not p50 and averages:
        # fallback: weighted average of "total" by count
        tot = sum((a.get("total") or 0) * (a.get("count") or 0) for a in averages)
        cnt = sum(a.get("count") or 0 for a in averages)
        p50 = int(round(tot / cnt)) if cnt else None
    return {
        "p50": int(p50) if p50 else None,
        "sample_count": sample_count,
        "levels": len(averages),
        "company_slug": company.get("slug"),
        "company_name": company.get("name"),
    }


def resolve_and_fetch(display_name: str, hint_slug: Optional[str], force_slug: Optional[str], log) -> dict:
    """Try slugs until we find one with at least one job-family page returning data.

    Returns dict with: resolved_slug, sw, pm (each {p50, sample_count, levels} or None), tries
    """
    tries: list[tuple[str, str, int]] = []  # (slug, family, status)
    out = {"resolved_slug": None, "sw": None, "pm": None, "tries": tries}

    cands = []
    if force_slug:
        cands = [force_slug]
    else:
        if hint_slug:
            cands.append(hint_slug)
        for c in candidate_slugs(display_name):
            if c not in cands:
                cands.append(c)

    # We always check software-engineer first; if 200 -> lock slug. Then PM.
    for slug in cands:
        url = f"{BASE}/company/{quote(slug)}/salaries/software-engineer"
        status, body = http_get(url)
        tries.append((slug, "software-engineer", status))
        time.sleep(REQ_DELAY)
        if status == 200:
            sw = extract_comp(body)
            # Even if sw has no p50, the slug is valid — still try PM.
            valid_slug = bool(sw is not None)  # parsed page successfully
            if sw and (sw["p50"] or sw["sample_count"]):
                out["resolved_slug"] = slug
                out["sw"] = sw
                pm_url = f"{BASE}/company/{quote(slug)}/salaries/product-manager"
                pm_status, pm_body = http_get(pm_url)
                tries.append((slug, "product-manager", pm_status))
                time.sleep(REQ_DELAY)
                if pm_status == 200:
                    pm = extract_comp(pm_body)
                    if pm and (pm["p50"] or pm["sample_count"]):
                        out["pm"] = pm
                return out
            elif valid_slug:
                # Valid Levels page but no SWE samples — try PM
                pm_url = f"{BASE}/company/{quote(slug)}/salaries/product-manager"
                pm_status, pm_body = http_get(pm_url)
                tries.append((slug, "product-manager", pm_status))
                time.sleep(REQ_DELAY)
                if pm_status == 200:
                    pm = extract_comp(pm_body)
                    if pm and (pm["p50"] or pm["sample_count"]):
                        out["resolved_slug"] = slug
                        out["pm"] = pm
                        return out
                # No data anywhere on this valid slug; mark resolved anyway so we don't keep retrying
                out["resolved_slug"] = slug
                return out
            # else: page didn't parse — try next candidate
        elif status in (502, 503, 504, 405, 429, -1, 0):
            # Transient upstream error — don't poison this slug, try next candidate
            # (but we already retried multiple times in http_get). Skip caching this as failure.
            continue
        # 404/410/other -> next candidate
    return out


def confidence_label(n: int) -> str:
    if n >= 50:
        return "high"
    if n >= 10:
        return "med"
    return "low"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS company_comp (
      company_name        TEXT PRIMARY KEY,
      levels_slug         TEXT,
      sw_engineer_p50_tc  INTEGER,
      pm_p50_tc           INTEGER,
      ic_total_p50_tc     INTEGER,
      sample_count        INTEGER DEFAULT 0,
      confidence          TEXT,
      cyrus_override      INTEGER,
      last_updated        TEXT,
      tries_json          TEXT,
      notes               TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_company_comp_slug ON company_comp(levels_slug);
    """)
    # ALTER TABLE roles ADD COLUMN est_tc — idempotent
    cur = conn.execute("PRAGMA table_info(roles)")
    cols = {r[1] for r in cur.fetchall()}
    if "est_tc" not in cols:
        conn.execute("ALTER TABLE roles ADD COLUMN est_tc INTEGER")
    conn.commit()


def upsert_company_comp(conn, *, company_name, levels_slug, sw, pm,
                       cyrus_override, tries, notes=None):
    sw_tc = sw["p50"] if sw else None
    pm_tc = pm["p50"] if pm else None
    sample = (sw["sample_count"] if sw else 0) + (pm["sample_count"] if pm else 0)
    # ic_total_p50: prefer software-engineer (broader), else PM, else override
    ic = sw_tc or pm_tc
    if cyrus_override:
        ic = cyrus_override
    conf = confidence_label(sample) if not cyrus_override else "override"
    conn.execute("""
        INSERT INTO company_comp(company_name, levels_slug, sw_engineer_p50_tc,
            pm_p50_tc, ic_total_p50_tc, sample_count, confidence, cyrus_override,
            last_updated, tries_json, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(company_name) DO UPDATE SET
          levels_slug         = excluded.levels_slug,
          sw_engineer_p50_tc  = excluded.sw_engineer_p50_tc,
          pm_p50_tc           = excluded.pm_p50_tc,
          ic_total_p50_tc     = excluded.ic_total_p50_tc,
          sample_count        = excluded.sample_count,
          confidence          = excluded.confidence,
          cyrus_override      = excluded.cyrus_override,
          last_updated        = excluded.last_updated,
          tries_json          = excluded.tries_json,
          notes               = excluded.notes
    """, (company_name, levels_slug, sw_tc, pm_tc, ic, sample, conf,
          cyrus_override, datetime.utcnow().isoformat(timespec="seconds"),
          json.dumps(tries), notes))
    conn.commit()


def is_stale(conn, name: str, refresh_days: int) -> bool:
    row = conn.execute(
        "SELECT last_updated, ic_total_p50_tc FROM company_comp WHERE company_name=?", (name,)
    ).fetchone()
    if not row:
        return True
    try:
        last = datetime.fromisoformat(row[0])
    except Exception:
        return True
    return datetime.utcnow() - last > timedelta(days=refresh_days)


def populate_roles_est_tc(conn) -> int:
    """Fill roles.est_tc from company_comp.ic_total_p50_tc by company match (case-insensitive)."""
    n = conn.execute("""
        UPDATE roles
           SET est_tc = (
                SELECT cc.ic_total_p50_tc
                  FROM company_comp cc
                 WHERE LOWER(cc.company_name) = LOWER(roles.company)
           )
    """).rowcount
    conn.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-days", type=int, default=30,
                    help="Skip companies updated within this many days (default 30).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Don't write to DB.")
    ap.add_argument("--only", nargs="*", default=None,
                    help="Only enrich these display names (smoke-test).")
    ap.add_argument("--populate-roles", action="store_true",
                    help="Just populate roles.est_tc from company_comp; no fetching.")
    ap.add_argument("--max-companies", type=int, default=None,
                    help="Cap how many companies to fetch (for time-bounded runs).")
    args = ap.parse_args()

    conn = connect()
    ensure_schema(conn)

    if args.populate_roles:
        n = populate_roles_est_tc(conn)
        print(f"[populate-roles] updated est_tc on {n} role rows")
        return

    with open(COMPANIES_YAML) as f:
        data = yaml.safe_load(f)
    companies = data.get("companies", [])

    if args.only:
        wanted = {x.lower() for x in args.only}
        companies = [c for c in companies if c.get("name", "").lower() in wanted]

    todo = []
    skipped_fresh = 0
    for c in companies:
        name = c.get("name")
        if not name:
            continue
        if c.get("skip") and not args.only:
            continue
        if not args.only and not is_stale(conn, name, args.refresh_days):
            skipped_fresh += 1
            continue
        todo.append(c)

    if args.max_companies:
        todo = todo[: args.max_companies]

    print(f"[levels-enrich] {len(todo)} companies queued "
          f"(skipped {skipped_fresh} fresh within {args.refresh_days}d)")

    started = time.time()
    n_ok = 0
    n_none = 0
    for i, c in enumerate(todo, 1):
        name = c["name"]
        hint = c.get("levels_slug") or c.get("slug")
        override = c.get("cyrus_comp_override")
        # If override is present, store it even if we have no Levels data.
        result = resolve_and_fetch(name, hint_slug=hint, force_slug=c.get("levels_slug_forced"),
                                   log=print)
        slug = result["resolved_slug"]
        sw = result["sw"]; pm = result["pm"]
        tries = result["tries"]

        any_data = bool(sw or pm)
        all_transient = bool(tries) and all(s in (502, 503, 504, 405, 429, -1, 0) for (_, _, s) in tries)
        if not any_data and not override:
            if all_transient:
                n_none += 1
                label = "[..]"  # transient — will retry next run, no DB write
            else:
                n_none += 1
                label = "[--]"  # genuine 404 — cache so we don't keep probing
        else:
            n_ok += 1
            label = "[OK]"
        sw_str = f"SWE p50=${sw['p50']/1000:.0f}K (n={sw['sample_count']})" if sw and sw["p50"] else "SWE -"
        pm_str = f"PM  p50=${pm['p50']/1000:.0f}K (n={pm['sample_count']})" if pm and pm["p50"] else "PM -"
        ovr_str = f" override=${override/1000:.0f}K" if override else ""
        elapsed = time.time() - started
        print(f"{label} [{i}/{len(todo)} {elapsed:.0f}s] {name:30s} slug={slug or '?'} | {sw_str} | {pm_str}{ovr_str} | tries={len(tries)}")

        if args.dry_run:
            continue
        # Skip DB write if everything was transient — retry next run
        if not any_data and not override and all_transient:
            continue
        upsert_company_comp(
            conn,
            company_name=name,
            levels_slug=slug,
            sw=sw,
            pm=pm,
            cyrus_override=override,
            tries=tries,
        )

    # Always finish by populating roles.est_tc (idempotent)
    if not args.dry_run:
        n_rows = populate_roles_est_tc(conn)
        print(f"[levels-enrich] populated roles.est_tc on {n_rows} rows")

    print(f"[levels-enrich] done: {n_ok} with data, {n_none} without, took {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
