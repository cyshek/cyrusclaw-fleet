#!/usr/bin/env python3
"""
response_tracker.py — Scan Gmail for job-application responses (interview requests,
rejections, application confirmations) and pipe them into tracker.db.

Usage:
    python response_tracker.py [--days 90] [--dry-run] [--verbose]

What it does:
    1. Connects to Gmail via IMAP (same app password as gmail_imap.py).
    2. Scans the last N days (default 90) of inbox + sent + all mail.
    3. Classifies each email as: interview_request | rejection |
       application_received | unknown_response.
    4. Matches each email to a row in tracker.db via fuzzy company-name / domain
       matching against applied roles.
    5. Writes matches to the `responses` table (CREATE IF NOT EXISTS).
    6. Updates roles.response_status, last_response_at, last_email_subject,
       last_email_from for interview_request / rejection.
    7. Prints a summary.
"""

from __future__ import annotations

import argparse
import email
import imaplib
import re
import ssl
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]          # projects/job-search/
WORKSPACE = ROOT.parent.parent                       # workspace/
APP_PW_FILE = ROOT / ".gmail-app-password"
DB_FILE = ROOT / "tracker.db"

import json as _json
_PI = _json.loads((ROOT / "personal-info.json").read_text())
GMAIL_USER = _PI["contact"]["email"]
IMAP_HOST  = "imap.gmail.com"
IMAP_PORT  = 993

SCAN_MAILBOXES = ['"[Gmail]/All Mail"']             # All Mail covers inbox + sent

# ── Classification signal words ────────────────────────────────────────────
INTERVIEW_SIGNALS = [
    "interview", "schedule", "availability", "next steps", "move forward",
    "advance", "phone screen", "video call", "zoom", "meet with", "speak with",
    "recruiting", "recruiter", "talent acquisition", "impressed", "excited to",
    "pleased to", "delighted to", "love to connect", "chat with you", "sync with",
    "let's connect", "quick call", "would like to", "we'd like to", "we would like",
    "progressing", "moved you forward", "selected", "strong candidate",
    "hiring manager", "technical screen", "coding interview", "case study",
    "assessment", "take-home", "hiring process", "next round", "onsite",
]

REJECTION_SIGNALS = [
    "not moving forward", "decided not", "won't be moving", "will not be moving",
    "other candidates", "position has been filled", "no longer considering",
    "unfortunately", "regret to inform", "not selected", "at this time we",
    "we have decided", "we won't be", "we will not", "have chosen", "have decided",
    "moving forward with other", "not a fit", "not the right fit", "not right for",
    "not qualify", "not qualified", "does not meet", "don't meet", "don't align",
    "you won't be", "you will not be", "closed", "filled this position",
    "went with another", "went with a different", "thank you for your interest",
    "keep your information on file", "keep your resume", "wish you well",
    "all the best in", "best of luck",
]

RECEIVED_SIGNALS = [
    "received your application", "application has been received",
    "thank you for applying", "we've received", "we have received",
    "successfully submitted", "application submitted", "application received",
    "confirming receipt", "confirmation of your application",
    "application is under review", "we will review", "under consideration",
    "we'll review", "your application for", "applied to",
]

# Senders that are ATS auto-sends or job-board blasts — skip for interview matching
ATS_NOISE_DOMAINS = {
    "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com",
    "smartrecruiters.com", "jobvite.com", "bamboohr.com", "icims.com",
    "taleo.net", "successfactors.com", "ultipro.com", "paylocity.com",
    "applytojob.com", "ashbyhq.com", "rippling.com",
    "linkedin.com", "indeed.com", "glassdoor.com", "monster.com",
    "ziprecruiter.com", "careerbuilder.com",
    "noreply.com", "no-reply.com", "donotreply.com",
    "notifications.linkedin.com",
}

# Suffixes to strip when normalizing company names
COMPANY_STRIP_SUFFIXES = re.compile(
    r"\b(inc|llc|ltd|corp|corporation|co|company|technologies|technology|"
    r"solutions|systems|software|labs|group|team|holdings|international|"
    r"services|associates|enterprises|ventures|global)\b[.,]?$",
    re.IGNORECASE,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_password() -> str:
    return APP_PW_FILE.read_text().strip().replace(" ", "")


def _decode_header(s) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    parts = decode_header(s)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(txt))
    return "".join(out)


def _msg_text(msg: email.message.Message) -> str:
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    chunks.append(payload.decode(charset, errors="replace"))
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            chunks.append(payload.decode(charset, errors="replace"))
        except Exception:
            pass
    raw = "\n".join(chunks)
    # Strip HTML tags for signal matching
    plain = re.sub(r"<[^>]+>", " ", raw)
    plain = re.sub(r"&nbsp;|&#xA0;|&amp;|&lt;|&gt;", " ", plain)
    return plain


def _extract_sender_email(from_str: str) -> str:
    """Extract bare email address from 'Name <email>' or just 'email'."""
    m = re.search(r"<([^>]+)>", from_str)
    if m:
        return m.group(1).strip().lower()
    return from_str.strip().lower()


def _domain(email_addr: str) -> str:
    """Returns root domain without www (e.g. 'stripe.com' → 'stripe.com')."""
    parts = email_addr.split("@")
    if len(parts) != 2:
        return ""
    domain = parts[1].lower().strip()
    domain = re.sub(r"^www\.", "", domain)
    return domain


def _root(domain: str) -> str:
    """Returns the SLD part: 'mail.stripe.com' → 'stripe'."""
    parts = domain.rstrip(".").split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else ""


def _normalize_company(name: str) -> str:
    """Lowercase, strip punctuation, remove legal suffixes."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = COMPANY_STRIP_SUFFIXES.sub("", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _classify(subject: str, body: str, sender: str) -> str:
    """
    Returns one of: interview_request | rejection | application_received | unknown_response
    Priority: interview_request > rejection > application_received > unknown_response
    """
    text = (subject + " " + body).lower()
    subj_lower = subject.lower()

    # Count signals
    interview_hits = sum(1 for s in INTERVIEW_SIGNALS if s in text)
    rejection_hits = sum(1 for s in REJECTION_SIGNALS if s in text)
    received_hits  = sum(1 for s in RECEIVED_SIGNALS if s in text)

    # If "unfortunately" or "regret" appear alongside "thank you for applying" → rejection
    if rejection_hits > 0 and (interview_hits == 0 or rejection_hits >= interview_hits):
        return "rejection"

    if interview_hits > 0:
        return "interview_request"

    if received_hits > 0:
        return "application_received"

    return "unknown_response"


# Sender domains that are never job-related
NOISE_SENDER_DOMAINS = frozenset([
    "hertz.com", "discounttire-email.com", "amazon.com", "ups.com", "fedex.com",
    "paypal.com", "netflix.com", "apple.com", "microsoft.com", "google.com",
    "bank.com", "wellsfargo.com", "chase.com", "bankofamerica.com",
    "doordash.com", "ubereats.com", "grubhub.com", "instacart.com",
    "noreply@linkedin.com", "notifications.linkedin.com",
    "jobalerts-noreply@linkedin.com", "jobalerts@linkedin.com",
])

# Subject patterns that indicate non-job emails
NOISE_SUBJECT_PATTERNS = re.compile(
    r"(appointment reminder|order confirmation|shipment|receipt|invoice|payment|billing|"
    r"traffic violation|subscription|account update|password|security alert|"
    r"discount|promotion|sale|offer expires|unsubscribe|"
    r"\"sales engineer\"|\"program manager\"|\"product manager\")",
    re.IGNORECASE,
)


def _is_job_related(subject: str, sender_email: str, body: str) -> bool:
    """Quick filter: is this email plausibly about a job application?"""
    # Reject known noise senders
    domain = _domain(sender_email)
    if domain in NOISE_SENDER_DOMAINS or sender_email in NOISE_SENDER_DOMAINS:
        return False
    # Reject noise subjects
    if NOISE_SUBJECT_PATTERNS.search(subject):
        return False
    text = (subject + " " + body[:2000]).lower()
    job_keywords = [
        "application", "apply", "applied", "position applied", "role", "job",
        "opportunity", "candidate", "hiring", "recruit", "interview", "career",
        "resume", "cover letter", "talent", "employment", "openings",
    ]
    return any(kw in text for kw in job_keywords)


# ── Database helpers ────────────────────────────────────────────────────────

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id         INTEGER,
            company         TEXT,
            email_date      TEXT,
            sender          TEXT,
            subject         TEXT,
            classification  TEXT,
            matched_role_id INTEGER,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add response_status columns to roles if missing (they should exist already)
    cur = conn.execute("PRAGMA table_info(roles)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col, typedef in [
        ("response_status",     "TEXT"),
        ("last_response_at",    "TEXT"),
        ("last_email_subject",  "TEXT"),
        ("last_email_from",     "TEXT"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE roles ADD COLUMN {col} {typedef}")
    conn.commit()


def load_applied_roles(conn: sqlite3.Connection) -> list[dict]:
    """Load all applied roles for matching."""
    cur = conn.execute("""
        SELECT id, company, role, applied_on
        FROM roles
        WHERE applied_by IS NOT NULL OR status = 'applied'
    """)
    rows = []
    for row in cur.fetchall():
        rows.append({
            "id":         row[0],
            "company":    row[1],
            "role":       row[2],
            "applied_on": row[3],
            "norm":       _normalize_company(row[1]),
        })
    return rows


def already_recorded(conn: sqlite3.Connection, sender: str, subject: str) -> bool:
    """Check if we already stored this sender+subject combination."""
    cur = conn.execute(
        "SELECT id FROM responses WHERE sender=? AND subject=? LIMIT 1",
        (sender, subject),
    )
    return cur.fetchone() is not None


# ── Matching ────────────────────────────────────────────────────────────────

def match_role(
    sender_email: str,
    subject: str,
    applied_roles: list[dict],
    threshold: float = 0.7,
) -> Optional[dict]:
    """
    Try to match an email to an applied role.
    Strategy:
      1. Sender domain root → compare to normalized company names.
      2. Subject keywords → compare to role title + company name.
    Returns the best-matching role dict or None.
    """
    domain = _domain(sender_email)
    domain_root = _root(domain)
    subj_lower = subject.lower()

    best_role = None
    best_score = 0.0

    for role in applied_roles:
        norm = role["norm"]  # already normalized

        # Strategy 1: domain root vs company name tokens
        if domain_root and len(domain_root) > 2:
            # Exact substring match in normalized company
            if domain_root in norm or domain_root in role["company"].lower():
                score = 0.95
            else:
                score = _fuzzy_score(domain_root, norm)
            if score > best_score:
                best_score = score
                best_role = role

        # Strategy 2: normalized company name in subject
        if norm and len(norm) > 3:
            if norm in subj_lower:
                score = 0.90
                if score > best_score:
                    best_score = score
                    best_role = role

        # Strategy 3: fuzzy match of company name against subject tokens
        words = re.findall(r"[a-z]{4,}", subj_lower)
        for word in words:
            s = _fuzzy_score(word, norm)
            if s > best_score and s >= threshold:
                best_score = s
                best_role = role

    if best_score >= threshold:
        return best_role
    return None


# ── Gmail scanning ──────────────────────────────────────────────────────────



def _subject_interesting(subject: str, sender: str) -> bool:
    """Fast header pre-filter: does this subject look job-related?"""
    s = subject.lower()
    all_signals = INTERVIEW_SIGNALS[:18] + REJECTION_SIGNALS[:12] + RECEIVED_SIGNALS[:8]
    if any(kw in s for kw in all_signals):
        return True
    return any(h in s for h in [
        "application", "your application", "applied", "applying",
        "job application", "position", "opportunity", "interview",
        "thank you for", "next steps", "follow up", "follow-up",
        "update", "status", "decision",
    ])
def _connect() -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    M.login(GMAIL_USER, _load_password())
    return M


def scan_gmail(days: int = 90, verbose: bool = False) -> list[dict]:
    """
    Two-pass Gmail scan:
      Pass 1: Batch header fetch (cheap) - subject pre-filter
      Pass 2: Full RFC822 body fetch for candidates only
    """
    since_epoch = time.time() - (days * 86400)
    since_str   = time.strftime("%d-%b-%Y", time.gmtime(since_epoch - 86400))
    cutoff_dt   = datetime.fromtimestamp(since_epoch, tz=timezone.utc)
    results: list[dict] = []
    seen: set = set()
    M = _connect()
    try:
        for mbox in SCAN_MAILBOXES:
            typ, _ = M.select(mbox, readonly=True)
            if typ != "OK":
                print(f"  [WARN] SELECT {mbox} failed", file=sys.stderr)
                continue
            typ, data = M.search(None, f"(SINCE {since_str})")
            if typ != "OK" or not data or not data[0]:
                continue
            all_ids = list(reversed(data[0].split()))[:3000]
            print(f"  {mbox}: {len(all_ids)} messages in window - pass 1 (headers)...")
            sys.stdout.flush()
            # Pass 1: batch header fetch
            candidate_ids: list[bytes] = []
            CHUNK = 200
            for ci in range(0, len(all_ids), CHUNK):
                chunk = all_ids[ci:ci + CHUNK]
                id_str = b",".join(chunk)
                try:
                    typ, hdr_data = M.fetch(id_str, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if typ != "OK" or not hdr_data:
                        continue
                    for item in hdr_data:
                        if not isinstance(item, tuple) or len(item) < 2:
                            continue
                        uid_m = re.match(rb"^(\d+)", item[0])
                        if not uid_m:
                            continue
                        uid = uid_m.group(1)
                        hm  = email.message_from_bytes(item[1])
                        try:
                            dt = parsedate_to_datetime(hm.get("Date", ""))
                            if dt < cutoff_dt:
                                continue
                        except Exception:
                            pass
                        subj = _decode_header(hm.get("Subject", ""))
                        frm  = _decode_header(hm.get("From", ""))
                        if _subject_interesting(subj, frm):
                            candidate_ids.append(uid)
                except Exception:
                    continue
            print(f"  {mbox}: {len(candidate_ids)} candidates - pass 2 (bodies)...")
            sys.stdout.flush()
            # Pass 2: full body for candidates only
            for mid in candidate_ids:
                try:
                    typ, md = M.fetch(mid, "(RFC822)")
                    if typ != "OK" or not md or not md[0]:
                        continue
                    msg  = email.message_from_bytes(md[0][1])
                    subj = _decode_header(msg.get("Subject", ""))
                    frm  = _decode_header(msg.get("From", ""))
                    sndr = _extract_sender_email(frm)
                    dt_s = msg.get("Date", "")
                    key  = (sndr, subj)
                    if key in seen:
                        continue
                    seen.add(key)
                    body = _msg_text(msg)
                    if not _is_job_related(subj, sndr, body):
                        continue
                    cls = _classify(subj, body, sndr)
                    if cls == "unknown_response":
                        continue
                    results.append({
                        "sender": sndr, "from_display": frm,
                        "subject": subj, "date": dt_s,
                        "classification": cls, "body_snippet": body[:500],
                    })
                    if verbose:
                        print(f"  [{cls}] {subj[:60]} | {sndr}")
                except Exception as e:
                    if verbose:
                        print(f"  [ERR] {mid}: {e}", file=sys.stderr)
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return results

# ── Main pipeline ───────────────────────────────────────────────────────────

def run(days: int = 90, dry_run: bool = False, verbose: bool = False) -> dict:
    """
    Full pipeline: scan Gmail → match → write DB.
    Returns summary dict.
    """
    print(f"[response_tracker] Scanning Gmail last {days} days (dry_run={dry_run})...")

    # Scan Gmail
    emails = scan_gmail(days=days, verbose=verbose)
    print(f"  Found {len(emails)} job-related emails (interview/rejection/received)")

    # Load DB
    conn = sqlite3.connect(str(DB_FILE))
    ensure_schema(conn)
    applied_roles = load_applied_roles(conn)
    print(f"  {len(applied_roles)} applied roles in tracker.db for matching")

    # Tally
    counts: dict[str, int] = {
        "interview_request":    0,
        "rejection":            0,
        "application_received": 0,
        "unmatched":            0,
        "duplicate_skipped":    0,
        "total_scanned":        len(emails),
    }

    for rec in emails:
        classification = rec["classification"]

        # Check dedup against DB
        if already_recorded(conn, rec["sender"], rec["subject"]):
            counts["duplicate_skipped"] += 1
            continue

        # Match to a role
        matched = match_role(rec["sender"], rec["subject"], applied_roles)
        matched_role_id = matched["id"] if matched else None
        matched_company = matched["company"] if matched else None

        # Extract company from sender domain as fallback label
        domain = _domain(rec["sender"])
        domain_root = _root(domain)
        display_company = matched_company or domain_root or rec["sender"].split("@")[-1]

        if verbose:
            match_str = f"→ {matched_company} (id={matched_role_id})" if matched else "→ UNMATCHED"
            print(f"  [{classification}] {rec['subject'][:55]} | {rec['sender']} {match_str}")

        if not dry_run:
            # Insert into responses table
            conn.execute("""
                INSERT INTO responses
                  (role_id, company, email_date, sender, subject, classification, matched_role_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                matched_role_id,
                display_company,
                rec["date"],
                rec["sender"],
                rec["subject"],
                classification,
                matched_role_id,
            ))

            # Update roles table for interview requests and rejections
            if matched_role_id and classification in ("interview_request", "rejection"):
                conn.execute("""
                    UPDATE roles
                    SET response_status    = ?,
                        last_response_at   = ?,
                        last_email_subject = ?,
                        last_email_from    = ?
                    WHERE id = ?
                """, (
                    classification,
                    datetime.utcnow().strftime("%Y-%m-%d"),
                    rec["subject"],
                    rec["sender"],
                    matched_role_id,
                ))

            conn.commit()

        # Tally
        if matched:
            counts[classification] = counts.get(classification, 0) + 1
        else:
            counts["unmatched"] += 1
            if classification != "application_received":
                # Still count classification
                counts[classification] = counts.get(classification, 0) + 1

    conn.close()
    return counts


def print_summary(counts: dict) -> None:
    print("\n" + "=" * 55)
    print("  Gmail Response Tracker — Summary")
    print("=" * 55)
    print(f"  Total emails scanned :  {counts['total_scanned']}")
    print(f"  Interview requests   :  {counts.get('interview_request', 0)}")
    print(f"  Rejections           :  {counts.get('rejection', 0)}")
    print(f"  App confirmations    :  {counts.get('application_received', 0)}")
    print(f"  Unmatched            :  {counts.get('unmatched', 0)}")
    print(f"  Duplicates skipped   :  {counts.get('duplicate_skipped', 0)}")
    print("=" * 55)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scan Gmail for job application responses")
    ap.add_argument("--days",     type=int,  default=90,    help="Days back to scan (default 90)")
    ap.add_argument("--dry-run",  action="store_true",       help="Don't write to DB")
    ap.add_argument("--verbose",  action="store_true",       help="Show each email match")
    args = ap.parse_args()

    counts = run(days=args.days, dry_run=args.dry_run, verbose=args.verbose)
    print_summary(counts)
