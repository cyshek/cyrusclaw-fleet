"""
gmail_scanner.py -- Interview-prep Gmail inbox scanner
Scans cyshekari@gmail.com for interview-related emails.
Returns a list of detected interview signals as dicts.
"""

import imaplib
import email
import email.header
import re
import json
import sqlite3
import datetime

GMAIL_USER = "cyshekari@gmail.com"
GMAIL_APP_PASSWORD = "yjse lddd mhan gbpe"
TRACKER_DB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"

INTERVIEW_SUBJECT_PATTERNS = [
    r"interview",
    r"phone screen",
    r"phone call",
    r"video call",
    r"virtual interview",
    r"onsite",
    r"on-site",
    r"hiring manager",
    r"technical screen",
    r"recruiter call",
    r"chat with",
    r"meet with",
    r"let.s connect",
    r"next steps",
    r"schedule.*with",
    r"invitation.*interview",
    r"interview.*invitation",
    r"calendar invite",
    r"zoom.*interview",
    r"teams.*interview",
]

RECRUITER_DOMAIN_HINTS = [
    "greenhouse.io", "lever.co", "ashbyhq.com", "workday.com",
    "icims.com", "taleo.net", "smartrecruiters.com", "jobvite.com",
    "calendly.com", "cal.com", "goodtime.io", "myinterview.com",
]

LOOKBACK_DAYS = 3

# Body phrases that indicate a rejection — skip even if subject matches interview patterns
REJECTION_BODY_PATTERNS = [
    r"will not be moving forward",
    r"not moving forward",
    r"decided not to move forward",
    r"not selected",
    r"not a fit",
    r"isn.t an ideal fit",
    r"is not an ideal fit",
    r"does not align",
    r"we.ve decided to pursue other candidates",
    r"other candidates whose experience",
    r"we will not be proceeding",
    r"unfortunately.*not.*move forward",
    r"after.*review.*not.*fit",
    r"after careful consideration",
    r"we appreciate your interest.*will not",
    r"we.re moving forward with other",
    r"application.*not.*successful",
    r"regret to inform",
    r"position.*has been filled",
    r"decided to go in a different direction",
]


def decode_header_str(raw):
    parts = email.header.decode_header(raw or "")
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def is_rejection(body_snippet):
    """Return True if the body clearly indicates a rejection."""
    for pat in REJECTION_BODY_PATTERNS:
        if re.search(pat, body_snippet, re.IGNORECASE):
            return True
    return False


def is_interview_signal(subject, sender, body_snippet=""):
    """Delegate to the scored classifier (classifier.py). Kept as a thin wrapper so
    existing callers keep working. The old keyword-soup logic is retired."""
    try:
        from classifier import classify
        is_int, _score, _label, _reasons = classify(subject, sender, body_snippet)
        return is_int
    except Exception as e:
        print(f"[gmail_scanner] classifier error ({e}) - falling back to keyword match")
        # Conservative fallback: only the literal word 'interview' in subject.
        return "interview" in (subject or "").lower()


def extract_company_from_email(subject, sender, body_snippet=""):
    domain_match = re.search(r'@([a-z0-9\-]+)\.(io|com|ai|co|net|org)', sender.lower())
    if domain_match:
        raw_company = domain_match.group(1)
        ats_domains = {
            "greenhouse", "lever", "ashbyhq", "workday", "icims", "taleo",
            "smartrecruiters", "jobvite", "calendly", "goodtime", "myinterview",
            "gmail", "google", "outlook", "microsoft",
        }
        if raw_company not in ats_domains:
            return raw_company.replace("-", " ").title()

    patterns = [
        r"(?:interview|call|screen|chat) (?:with|at|for) ([A-Z][A-Za-z0-9\s\-]+?)(?:\s*[-|,]|\s+for|\s+re:|\s*$)",
        r"^([A-Z][A-Za-z0-9]+)(?:\s*[-|]|\s+interview|\s+recruiting)",
        r"from ([A-Z][A-Za-z0-9\s]+?) (?:recruiting|talent|hr|team)",
    ]
    for pat in patterns:
        m = re.search(pat, subject, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return None


def extract_role_from_email(subject, body_snippet=""):
    text = f"{subject} {body_snippet}"
    patterns = [
        r"for the ([A-Za-z\s\-\/]+?) (?:position|role|opportunity|opening|req)",
        r"(?:interview|screen) for ([A-Za-z\s\-\/]+?)(?:\s+at|\s+with|\s*[-]|\s*$)",
        r"re:\s*([A-Za-z\s\-\/]+?) (?:interview|screen|call)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 3 < len(candidate) < 60:
                return candidate
    return None


def scan_gmail_inbox():
    signals = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        since_date = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
        _, message_ids = mail.search(None, f'(SINCE "{since_date}")')

        ids = message_ids[0].split()
        print(f"[gmail_scanner] {len(ids)} emails since {since_date}")

        for msg_id in ids:
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = decode_header_str(msg.get("Subject", ""))
            sender = decode_header_str(msg.get("From", ""))
            date_str = msg.get("Date", "")

            body_snippet = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body_snippet = part.get_payload(decode=True).decode("utf-8", errors="replace")[:500]
                        except Exception:
                            pass
                        break
            else:
                try:
                    body_snippet = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass

            if is_interview_signal(subject, sender, body_snippet):
                company = extract_company_from_email(subject, sender, body_snippet)
                role = extract_role_from_email(subject, body_snippet)
                signals.append({
                    "source": "email",
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "company_guess": company,
                    "role_guess": role,
                    "snippet": body_snippet[:200],
                })
                print(f"[gmail_scanner] SIGNAL: {subject!r} company={company} role={role}")

        mail.logout()
    except Exception as e:
        print(f"[gmail_scanner] ERROR: {e}")

    return signals


def lookup_tracker_role(company, role_hint=None):
    if not company:
        return None

    # Canonicalize the company name first so domain-derived guesses like
    # "Datadoghq" / "Newrelic" / "Ziphq" / "Everpuredata" match the clean names
    # stored in the roles table ("Datadog", "New Relic", "Zip", "Everpure").
    try:
        from classifier import canonical_company
        canon = canonical_company(company, "", "")
        if canon:
            company = canon
    except Exception:
        pass

    try:
        db = sqlite3.connect(TRACKER_DB, check_same_thread=False)
        db.row_factory = sqlite3.Row

        company_exact = company.strip()
        company_pattern = f"%{company_exact}%"
        # Try exact match first, then fuzzy — avoids "Podium Automation" beating "Podium"
        rows = db.execute("""
            SELECT id, company, role, status, applied_by, applied_on,
                   prep_path, jd_url, agent_notes
            FROM roles
            WHERE company = ?
              AND status IN ('applied', 'submitted', 'interview')
            ORDER BY applied_on DESC
        """, (company_exact,)).fetchall()
        if not rows:
            rows = db.execute("""
                SELECT id, company, role, status, applied_by, applied_on,
                       prep_path, jd_url, agent_notes
                FROM roles
                WHERE company LIKE ?
                  AND status IN ('applied', 'submitted', 'interview')
                ORDER BY applied_on DESC
            """, (company_pattern,)).fetchall()
        db.close()

        if not rows:
            print(f"[tracker] No rows for company={company!r}")
            return None

        if role_hint and len(rows) > 1:
            role_lower = role_hint.lower()
            for row in rows:
                if role_lower in (row["role"] or "").lower():
                    return dict(row)

        best = dict(rows[0])
        if len(rows) > 1:
            best["_ambiguous"] = True
            best["_all_matches"] = [
                {"id": r["id"], "role": r["role"], "applied_on": r["applied_on"]}
                for r in rows
            ]
        return best

    except Exception as e:
        print(f"[tracker] ERROR: {e}")
        return None


if __name__ == "__main__":
    print("=== Gmail scan ===")
    signals = scan_gmail_inbox()
    print(f"\nTotal signals: {len(signals)}")
    for s in signals:
        print(json.dumps(s, indent=2))
        tr = lookup_tracker_role(s.get("company_guess"), s.get("role_guess"))
        print(f"  Tracker match: {tr}")
