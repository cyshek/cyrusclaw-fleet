#!/usr/bin/env python3
"""
linkedin_email_parser.py — discovery source: parse LinkedIn Job-Alert emails.

LinkedIn sends two relevant email families:
  - "LinkedIn Job Alerts" <jobalerts-noreply@linkedin.com>  (saved-search digest)
  - "LinkedIn"            <jobs-noreply@linkedin.com>        (recommended / single-role)

Both render an HTML body with job cards. Each card links to
  https://www.linkedin.com/comm/jobs/view/<jobid>/?...tracking...
and carries the role title + "<company> · <location>" as adjacent text lines.

This module:
  1. Connects via IMAP (reusing gmail_imap._connect / _load_password).
  2. Searches INBOX (+ optionally All Mail) for the two senders SINCE a date.
  3. Parses every job card out of each email's HTML body with BeautifulSoup.
  4. Idempotently upserts new rows into tracker.db with
        source_key = 'linkedin-email:<jobid>'
        app_url    = canonical https://www.linkedin.com/jobs/view/<jobid>/
        flags      include 'manual-apply' and 'source-email-alert'
        status     = NULL  (discovery row; classifier runs downstream)

CLI:
    python linkedin_email_parser.py --dry-run            # default: print, no write
    python linkedin_email_parser.py --apply              # write to DB
    python linkedin_email_parser.py --since-days 30 --limit 200

Idempotency: a row is skipped if its source_key already exists OR if any
existing row's app_url already references the same jobid. Running twice
inserts 0 new rows.
"""
from __future__ import annotations

import argparse
import email
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TRACKER_DB = ROOT / "tracker.db"

# Reuse the proven IMAP connection + decode helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gmail_imap import _connect, _decode  # noqa: E402

ALERT_SENDERS = ("jobalerts-noreply@linkedin.com", "jobs-noreply@linkedin.com")

# Anchors to a LinkedIn job-view URL. The "comm" tracking variant is what the
# emails ship; we also tolerate the plain /jobs/view/ form.
_JOBID_RE = re.compile(r"/(?:comm/)?jobs/view/(\d+)", re.IGNORECASE)
# "Company · Location"  (LinkedIn uses a middot U+00B7 between the two).
_COMPANY_LOC_RE = re.compile(r"^(.*?)\s+[·•]\s+(.*)$")
# Lines we never want as a company/location (card chrome).
_NOISE_PREFIXES = (
    "easy apply",
    "actively recruiting",
    "promoted",
    "viewed",
    "be an early applicant",
)
_NOISE_SUFFIXES = ("/ year", "/ hr", "/ hour", "connection", "connections",
                    "company alumni", "school alumni")


def canonical_url(jobid: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{jobid}/"


@dataclass
class JobEntry:
    jobid: str
    company: str
    role: str
    loc: str
    url: str
    source_key: str = ""

    def __post_init__(self):
        if not self.source_key:
            self.source_key = f"linkedin-email:{self.jobid}"


def _looks_like_company_loc(s: str) -> bool:
    low = s.strip().lower()
    if not low:
        return False
    if any(low.startswith(p) for p in _NOISE_PREFIXES):
        return False
    if any(low.endswith(suf) for suf in _NOISE_SUFFIXES):
        return False
    return bool(_COMPANY_LOC_RE.match(s.strip()))


def parse_email_html(html: str) -> list[JobEntry]:
    """Extract job entries from one LinkedIn alert email HTML body.

    Robust across both digest (job_posting trk) and recommended
    (JOBS_POSTING_SECTION trk) layouts: we key off the URL jobid and the
    "<company> · <location>" text line, NOT off tracking-param names.
    """
    soup = BeautifulSoup(html, "html.parser")
    by_jid: dict[str, JobEntry] = {}

    for a in soup.find_all("a", href=True):
        m = _JOBID_RE.search(a["href"])
        if not m:
            continue
        jobid = m.group(1)
        if jobid in by_jid:
            continue  # already captured a richer/earlier anchor for this job

        strings = [s.strip() for s in a.stripped_strings if s.strip()]
        if len(strings) < 2:
            continue  # logo / "view job" anchors carry no card text

        role = strings[0]
        # Find the first subsequent line that parses as "company · location".
        comp_loc = None
        for s in strings[1:]:
            if _looks_like_company_loc(s):
                comp_loc = s
                break
        if comp_loc is None:
            continue

        cm = _COMPANY_LOC_RE.match(comp_loc)
        company = cm.group(1).strip()
        loc = cm.group(2).strip()
        if not company or not role:
            continue

        by_jid[jobid] = JobEntry(
            jobid=jobid,
            company=company,
            role=role,
            loc=loc,
            url=canonical_url(jobid),
        )

    return list(by_jid.values())


def _html_body(msg: email.message.Message) -> str:
    """Prefer text/html; fall back to concatenated html parts."""
    htmls: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    payload = part.get_payload(decode=True) or b""
                    htmls.append(payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"))
                except Exception:
                    pass
    else:
        if msg.get_content_type() == "text/html":
            try:
                payload = msg.get_payload(decode=True) or b""
                htmls.append(payload.decode(
                    msg.get_content_charset() or "utf-8", errors="replace"))
            except Exception:
                pass
    return "\n".join(htmls)


def fetch_alert_emails(since_days: int = 30, limit: int = 500,
                       mailboxes: Iterable[str] = ("INBOX",)) -> list[dict]:
    """Return [{subject, sender, date, html}] for matching alert emails."""
    since_dt = datetime.now(timezone.utc) - timedelta(days=since_days)
    since_str = since_dt.strftime("%d-%b-%Y")
    # IMAP OR is binary; nest for >2 terms. Two senders -> single OR.
    crit = (f'(SINCE {since_str}) '
            f'(OR FROM "{ALERT_SENDERS[0]}" FROM "{ALERT_SENDERS[1]}")')

    out: list[dict] = []
    M = _connect()
    try:
        for mbox in mailboxes:
            typ, _ = M.select(mbox, readonly=True)
            if typ != "OK":
                continue
            typ, data = M.search(None, crit)
            if typ != "OK" or not data or not data[0]:
                continue
            ids = list(reversed(data[0].split()))  # newest first
            for mid in ids[:limit]:
                typ, md = M.fetch(mid, "(RFC822)")
                if typ != "OK" or not md or not md[0]:
                    continue
                msg = email.message_from_bytes(md[0][1])
                out.append({
                    "subject": _decode(msg.get("Subject", "")),
                    "sender": _decode(msg.get("From", "")),
                    "date": msg.get("Date", ""),
                    "html": _html_body(msg),
                })
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return out


def extract_jobs(since_days: int = 30, limit: int = 500,
                 mailboxes: Iterable[str] = ("INBOX",)) -> tuple[list[JobEntry], int]:
    """Fetch + parse. Returns (deduped_jobs, n_emails)."""
    emails = fetch_alert_emails(since_days, limit, mailboxes)
    by_jid: dict[str, JobEntry] = {}
    for em in emails:
        for job in parse_email_html(em["html"]):
            by_jid.setdefault(job.jobid, job)  # first (newest) wins
    return list(by_jid.values()), len(emails)


def existing_keys_and_jobids(conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    """Return (existing source_keys, jobids already referenced by any app_url)."""
    keys: set[str] = set()
    jobids: set[str] = set()
    cur = conn.execute("SELECT source_key, app_url FROM roles")
    for sk, app_url in cur.fetchall():
        if sk:
            keys.add(sk)
            jm = re.match(r"linkedin-email:(\d+)$", sk)
            if jm:
                jobids.add(jm.group(1))
        if app_url:
            um = _JOBID_RE.search(app_url)
            if um:
                jobids.add(um.group(1))
    return keys, jobids


def upsert_jobs(jobs: list[JobEntry], apply: bool = False) -> dict:
    """Idempotent insert of NEW discovery rows. Returns counts + the new rows."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(TRACKER_DB))
    try:
        keys, jobids = existing_keys_and_jobids(conn)
        to_insert: list[JobEntry] = []
        skipped: list[JobEntry] = []
        for j in jobs:
            if j.source_key in keys or j.jobid in jobids:
                skipped.append(j)
                continue
            to_insert.append(j)
            keys.add(j.source_key)
            jobids.add(j.jobid)

        if apply and to_insert:
            conn.executemany(
                """INSERT INTO roles
                       (source_key, company, role, loc, app_url, jd_url,
                        status, flags, first_seen, last_seen, agent_notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [(j.source_key, j.company, j.role, j.loc, j.url, j.url,
                  "queued", "manual-apply,source-email-alert",
                  now_iso, now_iso,
                  "discovered via linkedin_email_parser") for j in to_insert],
            )
            conn.commit()
        return {
            "inserted": len(to_insert),
            "skipped": len(skipped),
            "inserted_rows": to_insert,
            "skipped_rows": skipped,
            "applied": apply,
        }
    finally:
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since-days", type=int, default=30)
    ap.add_argument("--limit", type=int, default=500,
                    help="max emails per mailbox to scan")
    ap.add_argument("--all-mail", action="store_true",
                    help="also scan [Gmail]/All Mail")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="print what WOULD be inserted (default)")
    g.add_argument("--apply", action="store_true",
                   help="actually write new rows to tracker.db")
    args = ap.parse_args(argv)

    apply = bool(args.apply)
    mailboxes = ["INBOX"]
    if args.all_mail:
        mailboxes.append('"[Gmail]/All Mail"')

    jobs, n_emails = extract_jobs(args.since_days, args.limit, mailboxes)
    print(f"Scanned {n_emails} alert email(s); extracted {len(jobs)} unique job(s).")

    res = upsert_jobs(jobs, apply=apply)

    if not apply:
        print("\n--- DRY RUN: would insert these NEW rows ---")
        for j in res["inserted_rows"][:50]:
            print(f"  {j.company} | {j.role} | {j.loc} | {j.url}")
        print(f"\nWould INSERT {res['inserted']} new, SKIP {res['skipped']} "
              f"existing (by source_key or app_url jobid).")
    else:
        print(f"\nAPPLIED: inserted {res['inserted']} new, "
              f"skipped {res['skipped']} as duplicate.")
    return res


if __name__ == "__main__":
    main()
