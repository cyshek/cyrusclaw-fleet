"""
classifier.py -- Scored interview-email classifier (replaces keyword-soup matching).

Philosophy: a REAL interview email is a human recruiter (or ATS on their behalf)
either (a) proposing availability, (b) confirming a scheduled time, or (c) sending a
calendar invite that contains an actual date/time. Application receipts, "thanks for
applying", job alerts, security codes, and rejections are NOT interviews.

Returns (is_interview: bool, score: int, label: str, reasons: list[str]).

Tuned against the real May->Jun inbox (104 emails) so the known false positives
(Google "update regarding your application", "Thanks for applying to Mintlify",
"Thank you for your interest in Instacart", bare "Regarding your application") are
rejected, while every genuine interview thread is kept.
"""

import re

# ---- Hard NEGATIVE: if subject/body screams "not an interview", bail out. ----
# Application-lifecycle acknowledgements (got your app / thanks for applying).
APPLICATION_RECEIPT = [
    r"thank you for applying",
    r"thanks for applying",
    r"thank you for your (?:interest|application)",
    r"we(?:'ve| have) received your application",
    r"application (?:has been )?received",
    r"your application (?:to|for|has been received|was received|is being)",
    r"regarding your application",          # Google/Workday status pings, NOT interviews
    r"update regarding your application",
    r"application (?:status|update)",
    r"successfully (?:applied|submitted)",
    r"we got your application",
]

# Rejections (kept from the old list — these are decisions, never interviews).
REJECTION = [
    r"will not be moving forward", r"not moving forward", r"decided not to move forward",
    r"not selected", r"not a fit", r"isn.t an ideal fit", r"is not an ideal fit",
    r"does not align", r"pursue other candidates", r"other candidates whose experience",
    r"we will not be proceeding", r"unfortunately.*not.*(?:move|proceed|advance)",
    r"after careful consideration", r"regret to inform", r"position.*has been filled",
    r"decided to go in a different direction", r"not.*successful",
]

# Automated junk: job alerts, security codes, portal access, marketing.
JUNK = [
    r"security code", r"verification code", r"one-time", r"verify your email",
    r"portal access", r"access code", r"job alert", r"jobs you may", r"may be a fit",
    r"posted on", r"recommended for you", r"new jobs", r"job recommendation",
    r"password", r"sign in", r"confirm your email",
]
JUNK_SENDERS = [
    "jobalerts", "jobs-noreply", "jobs-listings", "job-alerts", "linkedin.com",
    "no-reply@us.greenhouse-mail.io", "no-reply@eu.greenhouse-mail.io",
    "noreply@2captcha", "notifications@", "@indeed.com", "@ziprecruiter",
]

# ---- POSITIVE signals (scored). Higher = more clearly a real interview. ----
# Strong: an actual scheduled interview / invite with intent to meet.
STRONG_PHRASES = [
    (r"your interview (?:is|with).*(?:scheduled|confirmed|is scheduled for)", 5),
    (r"interview (?:is )?(?:scheduled|confirmed)", 5),
    (r"interview confirmation", 5),
    (r"confirmation from \w+", 4),                    # "Confirmation from Scale!"
    (r"interview availability", 4),
    (r"availability.*interview", 4),
    (r"schedule (?:your|a|an) interview", 5),
    (r"let.?s schedule your interview", 5),
    (r"(?:video|phone|virtual|onsite|on-site) (?:call|interview|meeting|screen)", 4),
    (r"interview request", 4),
    (r"upcoming interview", 5),
    (r"interview prep", 4),
    (r"interview packet", 5),
    (r"(?:next steps?|moving forward).*interview", 4),
    (r"phone screen", 4),
    (r"recruiter (?:phone )?call", 4),
    (r"recruiter screen", 4),
    (r"technical screen", 4),
    (r"hiring manager (?:call|chat|screen|interview)", 4),
    (r"meeting confirmation", 4),
    (r"video meeting confirmation", 5),
]
# Medium: scheduling language that needs a recruiter-domain sender to count.
MEDIUM_PHRASES = [
    (r"\bnext steps?\b", 2),
    (r"\bavailability\b", 2),
    (r"schedule.*(?:call|chat|time|meeting)", 2),
    (r"let.?s (?:connect|chat|find a time|schedule)", 2),
    (r"book(?:ing)? (?:a )?time", 2),
    (r"propose.*time", 2),
    (r"are you (?:available|free)", 2),
    (r"discussion with", 2),
]
# A calendar invite with an actual date/time is a strong structural signal.
# Gmail prefixes real invites as "Invitation:" OR "Invitation from an unknown sender:"
# OR "Updated invitation:" — accept all of those forms.
INVITE_SUBJECT = re.compile(
    r"^(?:invitation(?: from an unknown sender)?|invite|updated invitation):", re.I
)
INVITE_WITH_DATETIME = re.compile(
    r"@\s*\w{3,9}\s+\w{3,9}\s*\d{1,2}.*\d{1,2}(?::\d{2})?\s*(?:am|pm)", re.I
)
CANCELED_INVITE = re.compile(r"^(?:canceled event|cancelled event|declined):", re.I)
# A reminder for an already-scheduled interview/discussion is a real interview signal,
# even from a Calendly/notifications sender.
INTERVIEW_REMINDER = re.compile(
    r"^reminder:.*(?:interview|discussion|screen|call|meeting|chat with)", re.I
)

# Recruiter/ATS sender domains -> a real human at the hiring company (or its ATS).
ATS_OR_RECRUITER_DOMAINS = [
    "greenhouse.io", "lever.co", "ashbyhq.com", "workday.com", "myworkday.com",
    "icims.com", "smartrecruiters.com", "jobvite.com", "calendly.com", "cal.com",
    "goodtime.io", "modernloop.io", "dover.com", "gem.com", " message.greenhouse",
]
# Generic mailbox providers — NOT a company recruiter signal by themselves.
GENERIC_PROVIDERS = {"gmail", "yahoo", "outlook", "hotmail", "icloud", "aol", "proton"}


def _matches(patterns, text):
    return [p for p in patterns if re.search(p, text, re.I)]


def _sender_domain(sender):
    m = re.search(r"@([a-z0-9.\-]+)", sender.lower())
    return m.group(1) if m else ""


def _is_recruiter_sender(sender):
    """True if the sender looks like a real recruiter / ATS-on-behalf, not a generic inbox."""
    dom = _sender_domain(sender)
    if not dom:
        return False
    if any(a in dom for a in [d.split("@")[-1] for d in ATS_OR_RECRUITER_DOMAINS]):
        return True
    root = dom.split(".")[0]
    if root in GENERIC_PROVIDERS:
        return False
    # A named person @ a company domain (e.g. logan.boyko@cresta.ai) counts.
    return bool(re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", dom)) and root not in GENERIC_PROVIDERS


def classify(subject, sender, body=""):
    subject = subject or ""
    sender = sender or ""
    body = body or ""
    text = f"{subject} {body}"
    reasons = []

    # 1) Hard negatives first.
    if _matches(REJECTION, text):
        return (False, -10, "rejection", ["rejection language"])
    # An interview reminder (even via Calendly/notifications) IS a real signal — check
    # before the JUNK sender filter so we don't kill legitimate reminders.
    if INTERVIEW_REMINDER.search(subject):
        return (True, 6, "interview", ["interview/discussion reminder"])
    if _matches(JUNK, subject) or any(s in sender.lower() for s in JUNK_SENDERS):
        return (False, -8, "junk", ["job-alert / security-code / marketing"])
    # Application receipt with NO interview/scheduling words anywhere = not an interview.
    if _matches(APPLICATION_RECEIPT, text):
        # Allow through only if there's ALSO a strong interview phrase
        # (rare: "Application - Next Steps: schedule your interview").
        if not _matches([p for p, _ in STRONG_PHRASES], text):
            return (False, -5, "application-receipt", ["application acknowledgement, no interview"])

    # Canceled/declined invite — track as a state change but not an active interview.
    if CANCELED_INVITE.search(subject):
        return (False, -3, "canceled", ["calendar event canceled/declined"])

    # 2) Score positives.
    score = 0
    strong = _matches([p for p, _ in STRONG_PHRASES], text)
    for pat, pts in STRONG_PHRASES:
        if re.search(pat, text, re.I):
            score += pts
            reasons.append(f"strong:{pat[:30]}")

    recruiter = _is_recruiter_sender(sender)
    if recruiter:
        reasons.append(f"recruiter-sender:{_sender_domain(sender)}")

    # Medium phrases only count meaningfully when the sender is a recruiter/ATS.
    for pat, pts in MEDIUM_PHRASES:
        if re.search(pat, text, re.I):
            score += pts if recruiter else 0
            if recruiter:
                reasons.append(f"medium:{pat[:24]}")

    # Calendar invite WITH a real datetime = strong structural evidence.
    if INVITE_SUBJECT.search(subject) and INVITE_WITH_DATETIME.search(subject):
        score += 5
        reasons.append("calendar-invite+datetime")
    elif INVITE_SUBJECT.search(subject) and "interview" in subject.lower():
        score += 4
        reasons.append("calendar-invite:interview")

    # "your interview with <company>" anywhere = strong, regardless of sender parsing.
    if re.search(r"your interview with \w+", text, re.I):
        score += 4
        reasons.append("your-interview-with-X")

    # The literal word "interview" in the subject from a recruiter is a solid baseline.
    if "interview" in subject.lower() and recruiter:
        score += 2
        reasons.append("subject-has-interview+recruiter")

    # 3) Decide. Threshold 4 keeps real interviews, drops weak/ambiguous noise.
    THRESHOLD = 4
    is_interview = score >= THRESHOLD
    label = "interview" if is_interview else ("weak" if score > 0 else "not-interview")
    return (is_interview, score, label, reasons)


# Company-name canonicalization so 9 Scale emails collapse to ONE.
_COMPANY_FIXUPS = {
    "datadoghq": "Datadog", "newrelic": "New Relic", "ziphq": "Zip",
    "mediaalpha": "MediaAlpha", "everpuredata": "Everpure", "scale": "Scale",
    "scale ai": "Scale", "scale is scheduled": "Scale", "purestorage": "Everpure",
    "langchain": "LangChain", "goodtime": None, "calendly": None, "modernloop": None,
}

# Known company keywords to recover the org from a messy subject/sender when the
# domain is an ATS (goodtime/calendly/modernloop) that hides the real company.
_COMPANY_KEYWORDS = [
    ("datadog", "Datadog"), ("langchain", "LangChain"), ("new relic", "New Relic"),
    ("newrelic", "New Relic"), ("mediaalpha", "MediaAlpha"), ("media alpha", "MediaAlpha"),
    ("cresta", "Cresta"), ("anduril", "Anduril"), ("podium", "Podium"),
    ("everpure", "Everpure"), ("databricks", "Databricks"), ("scale", "Scale"),
    ("decagon", "Decagon"), ("zip", "Zip"), ("mintlify", "Mintlify"),
    ("instacart", "Instacart"), ("google", "Google"), ("anthropic", "Anthropic"),
]

_ATS_HIDE_DOMAINS = ("goodtime", "calendly", "modernloop", "greenhouse", "ashbyhq",
                     "lever", "dover", "gem.com")


def canonical_company(name, subject="", sender=""):
    """Best-effort company name. Falls back to subject/sender keyword recovery when the
    parsed name is missing or is an ATS placeholder (GoodTime/Calendly/etc.)."""
    if name:
        key = name.strip().lower()
        key = re.sub(r"\b(inc|llc|the|interview|with|for|your)\b", "", key).strip()
        if key in _COMPANY_FIXUPS:
            fixed = _COMPANY_FIXUPS[key]
            if fixed is not None:
                return fixed
            # fixed is None -> ATS placeholder, fall through to keyword recovery
        elif key:
            return name.strip().title()
    # Recover from subject/sender keywords.
    hay = f"{subject} {sender}".lower()
    for kw, canon in _COMPANY_KEYWORDS:
        if kw in hay:
            return canon
    return None
