#!/usr/bin/env python3
"""
rekey_blocked_urls.py - Re-key blocked roles that have raw https:// URLs as source_key.

Three cohorts:
  1. Greenhouse direct  (job-boards.greenhouse.io)   -> greenhouse:<org>:<token>
  2. Greenhouse via company site (gh_jid in URL)     -> greenhouse:<org>:<token>
  3. Ashby direct       (jobs.ashbyhq.com)           -> ashby:<tenant>:<uuid>
  4. Workday direct     (*.wd*.myworkdayjobs.com)    -> keep URL, set prep_status=manual_ready
"""

import argparse
import re
import sqlite3
from urllib.parse import urlparse, parse_qs

DB_PATH = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"

# Domain -> GH org slug mapping (from companies.yaml + boards.greenhouse.io URLs)
DOMAIN_TO_GH_ORG = {
    "abnormal.ai": "abnormalsecurity",
    "careers.datadoghq.com": "datadog",
    "careers.formlabs.com": "formlabs",
    "careers.roblox.com": "roblox",
    "careers.toasttab.com": "toast",
    "careers.withwaymo.com": "waymo",
    "coreweave.com": "coreweave",
    "databricks.com": "databricks",
    "hex.tech": "hextechnologies",
    "instacart.careers": "instacart",
    "jobs.dropbox.com": "dropbox",
    "stripe.com": "stripe",
    "wayve.firststage.co": "wayve",
    "wing.com": "wing",
    "www.brex.com": "brex",
    "www.catonetworks.com": "catonetworks",
    "www.coinbase.com": "coinbase",
    "www.fanduel.careers": "fanduel",
    "www.fastly.com": "fastly",
    "www.harness.io": "harnessinc",
    "www.intersystems.com": "intersystems",
    "www.ixl.com": "ixllearning",
    "www.klaviyo.com": "klaviyo",
    "www.okta.com": "okta",
    "www.pinterestcareers.com": "pinterest",
    "www.rubrik.com": "rubrik",
    "www.wiz.io": "wizinc",
}


def extract_gh_jid(url):
    """Extract the gh_jid value from query string."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "gh_jid" in qs:
        return qs["gh_jid"][0]
    return None


def get_gh_org_from_boards_url(url):
    """Extract org from boards.greenhouse.io/<org>/jobs/<token>"""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    if host == "boards.greenhouse.io":
        m = re.match(r"^/([^/]+)/jobs/", path)
        if m:
            return m.group(1)
        return None
    return None


def get_gh_org_from_careerpuck_url(url):
    """Extract org from app.careerpuck.com/job-board/<org>/job/<token>"""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    if host == "app.careerpuck.com":
        m = re.match(r"^/job-board/([^/]+)/", path)
        if m:
            return m.group(1)
        return None
    return None


def get_gh_org_from_domain(url):
    """Return GH org slug from domain lookup table."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return DOMAIN_TO_GH_ORG.get(host)


def get_gh_org(url):
    """Try all org-resolution methods."""
    org = get_gh_org_from_boards_url(url)
    if org:
        return org
    org = get_gh_org_from_careerpuck_url(url)
    if org:
        return org
    return get_gh_org_from_domain(url)


def parse_greenhouse_direct(url):
    """Parse job-boards.greenhouse.io/<org>/jobs/<token>. Returns (org, token) or None."""
    m = re.match(r"https://job-boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    return None


def parse_ashby(url):
    """Parse jobs.ashbyhq.com/<tenant>/<uuid>. Returns (tenant, uuid) or None."""
    m = re.match(
        r"https://jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})",
        url,
        re.IGNORECASE,
    )
    if m:
        return m.group(1), m.group(2)
    return None


def is_workday(url):
    return bool(re.search(r"https://[^/]+\.wd\d+\.myworkdayjobs\.com/", url))


def main():
    parser = argparse.ArgumentParser(description="Re-key blocked raw-URL roles")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without committing")
    args = parser.parse_args()
    dry = args.dry_run

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = cur.execute(
        """
        SELECT id, source_key, company, role
        FROM roles
        WHERE status = 'blocked'
          AND (block_reason IS NULL OR block_reason = '')
          AND source_key LIKE 'https://%'
        ORDER BY source_key
        """
    ).fetchall()

    print(f"Found {len(rows)} candidate rows")

    existing_keys = set(
        r[0]
        for r in cur.execute("SELECT source_key FROM roles").fetchall()
    )

    stats = {
        "gh_direct": 0,
        "gh_via_company": 0,
        "ashby": 0,
        "workday": 0,
        "linkedin_skipped": 0,
        "google_skipped": 0,
        "microsoft_skipped": 0,
        "collision_skipped": 0,
        "no_org_skipped": 0,
        "other_skipped": 0,
    }

    updates = []  # (id, new_source_key, new_status, new_prep_status)

    for row in rows:
        url = row["source_key"]

        if "linkedin.com" in url:
            stats["linkedin_skipped"] += 1
            continue
        if "google.com" in url:
            stats["google_skipped"] += 1
            continue
        if "microsoft.com" in url:
            stats["microsoft_skipped"] += 1
            continue

        # --- Greenhouse direct ---
        if url.startswith("https://job-boards.greenhouse.io/"):
            result = parse_greenhouse_direct(url)
            if result:
                org, token = result
                new_key = f"greenhouse:{org}:{token}"
                if new_key in existing_keys and new_key != url:
                    print(f"  COLLISION skip: {new_key} (row {row['id']})")
                    stats["collision_skipped"] += 1
                    continue
                updates.append((row["id"], new_key, "queued", None))
                existing_keys.add(new_key)
                stats["gh_direct"] += 1
                if dry:
                    print(f"  GH-direct: {url}")
                    print(f"         -> {new_key}")
            else:
                print(f"  SKIP (unparse GH direct): {url}")
                stats["other_skipped"] += 1
            continue

        # --- Ashby direct ---
        if url.startswith("https://jobs.ashbyhq.com/"):
            result = parse_ashby(url)
            if result:
                tenant, uuid = result
                new_key = f"ashby:{tenant}:{uuid}"
                if new_key in existing_keys and new_key != url:
                    print(f"  COLLISION skip: {new_key} (row {row['id']})")
                    stats["collision_skipped"] += 1
                    continue
                updates.append((row["id"], new_key, "queued", None))
                existing_keys.add(new_key)
                stats["ashby"] += 1
                if dry:
                    print(f"  Ashby: {url}")
                    print(f"      -> {new_key}")
            else:
                print(f"  SKIP (unparse Ashby): {url}")
                stats["other_skipped"] += 1
            continue

        # --- Workday direct ---
        if is_workday(url):
            updates.append((row["id"], url, "queued", "manual_ready"))
            stats["workday"] += 1
            if dry:
                print(f"  Workday (prep_status=manual_ready): {url[:80]}")
            continue

        # --- Greenhouse via company site (gh_jid in URL) ---
        gh_jid = extract_gh_jid(url)
        if gh_jid:
            org = get_gh_org(url)
            if not org:
                print(f"  SKIP (no org mapping for gh_jid URL): {url}")
                stats["no_org_skipped"] += 1
                continue
            new_key = f"greenhouse:{org}:{gh_jid}"
            if new_key in existing_keys and new_key != url:
                print(f"  COLLISION skip: {new_key} (row {row['id']})")
                stats["collision_skipped"] += 1
                continue
            updates.append((row["id"], new_key, "queued", None))
            existing_keys.add(new_key)
            stats["gh_via_company"] += 1
            if dry:
                print(f"  GH-via-company: {url}")
                print(f"              -> {new_key}")
            continue

        stats["other_skipped"] += 1

    print()
    print("=== Summary ===")
    print(f"  Greenhouse direct:      {stats['gh_direct']}")
    print(f"  Greenhouse via-company: {stats['gh_via_company']}")
    print(f"  Ashby:                  {stats['ashby']}")
    print(f"  Workday:                {stats['workday']}")
    print(f"  LinkedIn skipped:       {stats['linkedin_skipped']}")
    print(f"  Google skipped:         {stats['google_skipped']}")
    print(f"  Microsoft skipped:      {stats['microsoft_skipped']}")
    print(f"  Collision skipped:      {stats['collision_skipped']}")
    print(f"  No-org skipped:         {stats['no_org_skipped']}")
    print(f"  Other skipped:          {stats['other_skipped']}")
    print(f"  Total to update:        {len(updates)}")

    if dry:
        print()
        print("[DRY RUN] No changes committed.")
        con.close()
        return

    updated = 0
    for item in updates:
        row_id, new_key, new_status, new_prep = item
        cur.execute(
            """
            UPDATE roles
            SET source_key   = ?,
                status       = ?,
                prep_status  = ?,
                block_reason = NULL
            WHERE id = ?
            """,
            (new_key, new_status, new_prep, row_id),
        )
        updated += 1

    con.commit()
    print(f"Committed {updated} updates.")
    con.close()


if __name__ == "__main__":
    main()
