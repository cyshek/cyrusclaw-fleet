"""
calendar_scanner.py -- Google Calendar iCal feed scanner
Fetches Cyrus private iCal URL, parses upcoming events, detects interview signals.
"""

import urllib.request
import re
import datetime
import json

ICAL_URL = "https://calendar.google.com/calendar/ical/cyshekari%40gmail.com/private-3620dae5cb533b6290296e4bce814b22/basic.ics"

INTERVIEW_KEYWORDS = [
    "interview", "phone screen", "phone call", "video call", "virtual interview",
    "onsite", "on-site", "hiring manager", "technical screen", "recruiter",
    "chat with", "meet with", "hiring loop", "assessment", "coding challenge",
    "intro chat", "intro call", "informational", "career chat",
]

RECRUITER_ORGANIZER_DOMAINS = [
    "greenhouse.io", "lever.co", "ashbyhq.com", "workday.com", "goodtime.io",
    "scale.com", "scale.ai", "microsoft.com", "amazon.com", "google.com",
    "meta.com", "apple.com", "linkedin.com",
]

LOOKAHEAD_DAYS = 14


def fetch_ical():
    req = urllib.request.Request(ICAL_URL, headers={"User-Agent": "interview-prep/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_ical_events(ical_text):
    events = []
    current = {}
    in_event = False
    for raw_line in ical_text.splitlines():
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            current = {}
            continue
        if line == "END:VEVENT":
            in_event = False
            if current:
                events.append(current)
            current = {}
            continue
        if not in_event:
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key_base = key.split(";")[0].upper()
            current[key_base] = val
    return events


def parse_ical_date(date_str):
    date_str = date_str.strip()
    try:
        if "T" in date_str:
            ds = date_str.rstrip("Z")
            return datetime.datetime.strptime(ds[:15], "%Y%m%dT%H%M%S")
        else:
            return datetime.datetime.strptime(date_str[:8], "%Y%m%d")
    except Exception:
        return None


def is_interview_event(summary, description="", organizer=""):
    text = f"{summary} {description}".lower()
    for kw in INTERVIEW_KEYWORDS:
        if kw in text:
            return True
    # Calendly-style "Person A and Person B" meetings from recruiter domains
    org_lower = organizer.lower()
    for domain in RECRUITER_ORGANIZER_DOMAINS:
        if domain in org_lower:
            # Only flag if description has any job/company context
            if any(w in text for w in ["chat", "call", "meet", "connect", "excited", "opportunity", "role"]):
                return True
    return False


def extract_company_from_event(summary, description="", organizer=""):
    # Try organizer domain first (most reliable)
    import re as _re
    org_match = _re.search(r'@([a-z0-9\-]+)\.(com|ai|io|co|net)', organizer.lower())
    if org_match:
        domain = org_match.group(1)
        skip = {"greenhouse","lever","ashbyhq","workday","goodtime","gmail","google","calendly","cal"}
        if domain not in skip:
            return domain.replace("-", " ").title()
    # Try "Event Name\nCompany Xxx" pattern in description
    if description:
        en_match = _re.search(r'Event Name[\\n\n]+([A-Za-z0-9][A-Za-z0-9\s]+?)(?:\s+(?:Intro|Chat|Call|Interview|Screen)|\n)', description)
        if en_match:
            candidate = en_match.group(1).strip()
            if 2 < len(candidate) < 50:
                return candidate
    text = f"{summary} {description}"
    patterns = [
        r"(?:interview|screen|call|chat) (?:with|at|for) ([A-Z][A-Za-z0-9][A-Za-z0-9-]*)(?:\s|$|,|-)",
        r"([A-Z][A-Za-z0-9]+) (?:interview|screen|call|recruiting)",
        r"^([A-Z][A-Za-z0-9]+)\s+[-|]",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 2 < len(candidate) < 50:
                return candidate
    return None


def extract_role_from_event(summary, description=""):
    text = f"{summary} {description}"
    patterns = [
        r"for the ([A-Za-z\s\-\/]+?) (?:position|role|opportunity|opening)",
        r"(?:interview|screen) for ([A-Za-z\s\-\/]+?)(?:\s+at|\s+with|\s*[-]|\s*$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 3 < len(candidate) < 60:
                return candidate
    return None


def scan_calendar():
    signals = []
    try:
        ical_text = fetch_ical()
        events = parse_ical_events(ical_text)
        print(f"[calendar_scanner] Parsed {len(events)} total events")
        now = datetime.datetime.now()
        cutoff = now + datetime.timedelta(days=LOOKAHEAD_DAYS)
        for ev in events:
            summary = ev.get("SUMMARY", "")
            description = ev.get("DESCRIPTION", "")
            dtstart_raw = ev.get("DTSTART", "")
            dtstart = parse_ical_date(dtstart_raw)
            if not dtstart:
                continue
            if dtstart < now or dtstart > cutoff:
                continue
            organizer = ev.get("ORGANIZER", "")
            if is_interview_event(summary, description, organizer):
                company = extract_company_from_event(summary, description, organizer)
                role = extract_role_from_event(summary, description)
                signals.append({
                    "source": "calendar",
                    "subject": summary,
                    "sender": "Google Calendar",
                    "date": dtstart.isoformat(),
                    "company_guess": company,
                    "role_guess": role,
                    "snippet": description[:200],
                })
                print(f"[calendar_scanner] SIGNAL: {summary!r} on {dtstart.date()} company={company} role={role}")
    except Exception as e:
        print(f"[calendar_scanner] ERROR: {e}")
    return signals


if __name__ == "__main__":
    print("=== Calendar scan ===")
    signals = scan_calendar()
    print(f"Total signals: {len(signals)}")
    for s in signals:
        print(json.dumps(s, indent=2))
