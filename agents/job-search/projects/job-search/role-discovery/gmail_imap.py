#!/usr/bin/env python3
"""
gmail_imap.py — wait for a Greenhouse verification-code email and extract the
8-character alphanumeric code.

Connects via IMAP SSL using the app password at
`projects/job-search/.gmail-app-password` (16 chars, spaces stripped).

Public API:
    wait_for_verification_code(timeout_seconds=180, poll_seconds=5,
                               since_epoch=None) -> str
"""

from __future__ import annotations

import email
import imaplib
import re
import ssl
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PW_FILE = ROOT / ".gmail-app-password"
GMAIL_USER = "cyshekari@gmail.com"
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Gmail labels (XLIST/SELECT names). Inbox + Spam.
MAILBOXES = ["INBOX", '"[Gmail]/Spam"', '"[Gmail]/All Mail"']

SENDER_HINTS = ("greenhouse", "no-reply", "noreply", "candidate", "anthropic", "verification", "workday", "myworkdayjobs", "workdaysite", "talent", "careers", "icims", "auth0")
SUBJECT_HINTS = ("verification code", "verify your email", "verify your application", "confirm your application", "verification", "security code", "verify your account", "verify account", "verify your", "account verification")
BODY_HINTS = ("verification code", "verify your email", "verify your application", "confirm your", "security code", "verify your account", "account verification")

# Greenhouse codes observed: 8 chars, mix of uppercase letters + digits.
# Be permissive but anchored: standalone token of exactly 8 alnum chars,
# preferably uppercase.
CODE_REGEXES = [
    re.compile(r"\b([A-Z0-9]{8})\b"),
    re.compile(r"\b([A-Za-z0-9]{8})\b"),
]


def _load_password() -> str:
    raw = APP_PW_FILE.read_text().strip()
    return raw.replace(" ", "")


def _decode(s) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        try:
            return s.decode("utf-8", errors="replace")
        except Exception:
            return s.decode("latin-1", errors="replace")
    parts = decode_header(s)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)


def _msg_text(msg: email.message.Message) -> str:
    chunks = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True) or b""
                    chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            chunks.append(payload.decode(msg.get_content_charset() or "utf-8", errors="replace"))
        except Exception:
            pass
    return "\n".join(chunks)


def _looks_like_verification(subject: str, sender: str, body: str) -> bool:
    s = subject.lower()
    f = sender.lower()
    b = body.lower()
    if any(h in s for h in SUBJECT_HINTS):
        return True
    if any(h in b for h in BODY_HINTS) and any(h in f for h in SENDER_HINTS):
        return True
    return False


def _extract_code(body: str, subject: str = "") -> str | None:
    # Strip HTML tags but preserve content; also try to find <h1> contents which Greenhouse uses for the code.
    h1_matches = re.findall(r"<h1[^>]*>\s*([^<\s]+)\s*</h1>", body, re.IGNORECASE)
    for cand in h1_matches:
        cand = cand.strip()
        # Greenhouse: 8-char alnum. Workday/most ATS email-verify: 4-8 digit numeric.
        if re.fullmatch(r"[A-Za-z0-9]{8}", cand) or re.fullmatch(r"\d{4,8}", cand):
            return cand
    plain = re.sub(r"<[^>]+>", " ", body)
    plain = re.sub(r"&nbsp;|&#xA0;", " ", plain)
    haystacks = [subject, plain]
    # Look for "code" keyword nearby first (Greenhouse 8-char alnum form).
    for hay in haystacks:
        m = re.search(r"(?:security code|verification code|code)[^A-Za-z0-9]{0,40}([A-Za-z0-9]{8})\b", hay, re.IGNORECASE)
        if m:
            return m.group(1)
    # Workday & most other ATS email-verify senders use a 4-8 digit NUMERIC code, keyword-anchored.
    for hay in haystacks:
        m = re.search(r"(?:security code|verification code|one[- ]time|passcode|code is|your code|code)[^0-9]{0,40}(\d{4,8})\b", hay, re.IGNORECASE)
        if m:
            return m.group(1)
    # Fallback: any 8-char mixed alnum token (must contain at least one letter AND one digit)
    for hay in haystacks:
        for m in re.finditer(r"\b([A-Za-z0-9]{8})\b", hay):
            tok = m.group(1)
            has_digit = any(c.isdigit() for c in tok)
            has_alpha = any(c.isalpha() for c in tok)
            if has_digit and has_alpha:
                return tok
    # Last resort: a standalone 6-digit numeric token (common Workday OTP shape).
    for hay in haystacks:
        m = re.search(r"\b(\d{6})\b", hay)
        if m:
            return m.group(1)
    return None



def _extract_activation_link(body, host_hint=None):
    """Some ATS (notably many Workday tenants -- e.g. Gates Foundation) verify a new
    candidate account with a CLICKABLE ACTIVATION LINK rather than a numeric code:
      'Click this link to confirm your email address ...'
      https://<tenant>.wd1.myworkdayjobs.com/<Site>/activate/<token>/?redirect=...
    There is NO code to type; the account is activated by GETting the link. This is the
    correct path for those tenants (the old _extract_code mis-parsed '%2FSenior...' out
    of the redirect query and returned garbage like '2FSenior'). Returns the first
    activation-style URL found, preferring a host match when host_hint is given."""
    urls = re.findall(r'href=["\']([^"\']+)["\']', body, re.IGNORECASE)
    urls += re.findall(r'https?://[^\s"\'<>)]+', body)
    def _is_activation(u):
        ul = u.lower()
        return any(k in ul for k in ("/activate/", "/activation/", "confirmemail",
                                     "confirm-email", "verifyemail", "verify-email",
                                     "activateaccount", "emailconfirm"))
    cands = [u for u in urls if _is_activation(u)]
    if not cands:
        return None
    if host_hint:
        hh = host_hint.lower()
        for u in cands:
            if hh in u.lower():
                return u.replace("&amp;", "&")
    return cands[0].replace("&amp;", "&")


def wait_for_activation_link(timeout_seconds=180, poll_seconds=5,
                             since_epoch=None, host_hint=None):
    """Poll Gmail until a Workday-style account ACTIVATION LINK arrives, and return the
    URL. Mirrors wait_for_verification_code but extracts a clickable activate/confirm
    link instead of a numeric code. Raises TimeoutError if none arrives in the window."""
    if since_epoch is None:
        since_epoch = time.time() - 300
    deadline = time.time() + timeout_seconds
    last_err = None
    while time.time() < deadline:
        try:
            M = _connect()
            try:
                for mbox in MAILBOXES:
                    typ, _ = M.select(mbox)
                    if typ != "OK":
                        continue
                    since_str = time.strftime("%d-%b-%Y", time.gmtime(since_epoch - 86400))
                    typ, data = M.search(None, '(SINCE %s)' % since_str)
                    if typ != "OK" or not data or not data[0]:
                        continue
                    ids = list(reversed(data[0].split()))
                    for msg_id in ids[:50]:
                        typ, md = M.fetch(msg_id, "(RFC822)")
                        if typ != "OK" or not md or not md[0]:
                            continue
                        msg = email.message_from_bytes(md[0][1])
                        try:
                            dt = parsedate_to_datetime(msg.get("Date"))
                            if dt and dt.timestamp() < since_epoch - 5:
                                break
                        except Exception:
                            pass
                        subject = _decode(msg.get("Subject", ""))
                        sender = _decode(msg.get("From", ""))
                        body = _msg_text(msg)
                        if not _looks_like_verification(subject, sender, body):
                            continue
                        link = _extract_activation_link(body, host_hint=host_hint)
                        if link:
                            try:
                                M.store(msg_id, "+FLAGS", "\\Seen")
                            except Exception:
                                pass
                            return link
            finally:
                try:
                    M.logout()
                except Exception:
                    pass
        except Exception as e:
            last_err = e
        time.sleep(poll_seconds)
    raise TimeoutError("No activation link within %ss%s" % (
        timeout_seconds, (" (last_err=%s)" % last_err) if last_err else ""))


def _looks_like_icims(subject: str, sender: str, body: str) -> bool:
    """Tighter filter for iCIMS one-time-code mail. iCIMS career-portal /
    Universal-Login (Auth0) verification mail is branded: the sender domain is an
    icims.com host (e.g. ``no-reply@icims.com``, ``*@hire.icims.com``,
    ``*@talent.icims.com``) or Auth0-on-behalf-of-iCIMS, and the subject/body
    mentions a verification code. Requiring an iCIMS/Auth0 signal prevents an
    unrelated Workday/Greenhouse code sitting in the inbox from being grabbed
    mid-iCIMS-run."""
    s = (subject or "").lower()
    f = (sender or "").lower()
    b = (body or "").lower()
    brand = ("icims" in f) or ("icims" in s) or ("icims" in b) or ("auth0" in f)
    code_ctx = any(h in s or h in b for h in (
        "verification code", "one-time", "one time", "passcode", "security code",
        "verify your", "your code", "6-digit", "6 digit"))
    return bool(brand and code_ctx)


def _extract_icims_otp(body: str, subject: str = "") -> str | None:
    """Extract an iCIMS one-time verification code. iCIMS Universal Login (Auth0,
    effective Apr-2025) and candidate career-portal verification both deliver a
    **6-digit numeric** code. We anchor on the code keyword where possible, then
    fall back to a styled HTML cell (``<h1>/<strong>/<span>/<td>123456</td>``),
    then a standalone 6-digit token. Returns the 6-digit string, or None.

    Deliberately STRICT to 6 digits (the Auth0/iCIMS shape) so we never mistype a
    zip code, year, or phone fragment into the OTP field. Distinct from the
    generic Greenhouse 8-char alnum / Workday 4-8 digit extractor."""
    raw = body or ""
    # 1. Styled HTML element holding ONLY the code (iCIMS/Auth0 email layout).
    for m in re.finditer(r"<(?:h1|h2|strong|b|span|td|div|p)[^>]*>\s*(\d{6})\s*</",
                         raw, re.IGNORECASE):
        return m.group(1)
    # Strip tags for text-based matching.
    plain = re.sub(r"<[^>]+>", " ", raw)
    plain = re.sub(r"&nbsp;|&#xA0;|&#160;", " ", plain)
    haystacks = [subject or "", plain]
    # 2. Keyword-anchored 6-digit code ("verification code: 123456",
    #    "your code is 123456", "one-time passcode 123456").
    for hay in haystacks:
        m = re.search(
            r"(?:verification code|security code|one[- ]time(?: passcode| password| code)?|"
            r"passcode|your code(?: is)?|code is|enter (?:the )?code|6[- ]digit code)"
            r"[^0-9]{0,40}(\d{6})\b",
            hay, re.IGNORECASE)
        if m:
            return m.group(1)
    # 3. Fallback: a standalone 6-digit token NOT adjacent to other digits and not
    #    a 4-digit-year-looking sequence inside a longer number.
    for hay in haystacks:
        for m in re.finditer(r"(?<!\d)(\d{6})(?!\d)", hay):
            tok = m.group(1)
            # Reject an obvious year-prefixed token like 202612 only if it also
            # appears in a date context; otherwise a 6-digit OTP is fine.
            return tok
    return None


def wait_for_icims_otp(timeout_seconds: int = 90, poll_seconds: int = 5,
                       since_epoch: float | None = None) -> str:
    """Poll Gmail until an iCIMS one-time verification code arrives; return the
    6-digit string. Mirrors wait_for_verification_code but uses the iCIMS-branded
    sender/subject filter and the strict 6-digit extractor, and defaults to a
    90s budget (the iCIMS code is fast and short-lived). Raises TimeoutError if
    none arrives in the window -> caller maps that to EXIT 10 (otp-timeout).

    Args:
        timeout_seconds: total wall-clock budget (default 90).
        poll_seconds: sleep between IMAP polls.
        since_epoch: only consider mail received at-or-after this epoch. Defaults
            to now-180 (the email is requested moments before this is called).
    """
    if since_epoch is None:
        since_epoch = time.time() - 180
    deadline = time.time() + timeout_seconds
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            M = _connect()
            try:
                for mbox in MAILBOXES:
                    typ, _ = M.select(mbox)
                    if typ != "OK":
                        continue
                    since_str = time.strftime("%d-%b-%Y",
                                              time.gmtime(since_epoch - 86400))
                    typ, data = M.search(None, "(SINCE %s)" % since_str)
                    if typ != "OK" or not data or not data[0]:
                        continue
                    for msg_id in list(reversed(data[0].split()))[:50]:
                        typ, md = M.fetch(msg_id, "(RFC822)")
                        if typ != "OK" or not md or not md[0]:
                            continue
                        msg = email.message_from_bytes(md[0][1])
                        try:
                            dt = parsedate_to_datetime(msg.get("Date"))
                            if dt and dt.timestamp() < since_epoch - 5:
                                break
                        except Exception:
                            pass
                        subject = _decode(msg.get("Subject", ""))
                        sender = _decode(msg.get("From", ""))
                        body = _msg_text(msg)
                        if not _looks_like_icims(subject, sender, body):
                            continue
                        code = _extract_icims_otp(body, subject)
                        if code:
                            try:
                                M.store(msg_id, "+FLAGS", "\\Seen")
                            except Exception:
                                pass
                            return code
            finally:
                try:
                    M.logout()
                except Exception:
                    pass
        except Exception as e:
            last_err = e
        time.sleep(poll_seconds)
    raise TimeoutError("No iCIMS OTP within %ss%s" % (
        timeout_seconds, (" (last_err=%s)" % last_err) if last_err else ""))


def _connect() -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    M.login(GMAIL_USER, _load_password())
    return M


def _scan_mailbox(M: imaplib.IMAP4_SSL, mailbox: str, since_epoch: float) -> tuple[str | None, list[bytes]]:
    """Return (code, list_of_uids_marked_seen)."""
    typ, _ = M.select(mailbox)
    if typ != "OK":
        return None, []
    # IMAP SINCE granularity is one day. We post-filter by Date header epoch.
    since_str = time.strftime("%d-%b-%Y", time.gmtime(since_epoch - 86400))
    typ, data = M.search(None, f'(SINCE {since_str})')
    if typ != "OK" or not data or not data[0]:
        return None, []
    ids = data[0].split()
    # Newest first
    ids = list(reversed(ids))
    marked: list[bytes] = []
    for msg_id in ids[:50]:
        typ, msg_data = M.fetch(msg_id, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        # Filter by date
        try:
            dt = parsedate_to_datetime(msg.get("Date"))
            if dt and dt.timestamp() < since_epoch - 5:
                # Older than our window; remaining are also older.
                break
        except Exception:
            pass
        subject = _decode(msg.get("Subject", ""))
        sender = _decode(msg.get("From", ""))
        body = _msg_text(msg)
        if not _looks_like_verification(subject, sender, body):
            continue
        code = _extract_code(body, subject)
        if code:
            # Mark this message as seen so we don't re-read.
            try:
                M.store(msg_id, "+FLAGS", "\\Seen")
            except Exception:
                pass
            marked.append(msg_id)
            return code, marked
    return None, marked


def wait_for_verification_code(timeout_seconds: int = 180,
                                poll_seconds: int = 5,
                                since_epoch: float | None = None) -> str:
    """Poll Gmail until a Greenhouse-style verification code arrives.

    Args:
        timeout_seconds: total wall-clock budget.
        poll_seconds: sleep between IMAP polls.
        since_epoch: only consider messages received at-or-after this epoch.
            Defaults to now - 300 (last 5 minutes).
    """
    if since_epoch is None:
        since_epoch = time.time() - 300
    deadline = time.time() + timeout_seconds
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            M = _connect()
            try:
                for mbox in MAILBOXES:
                    code, _ = _scan_mailbox(M, mbox, since_epoch)
                    if code:
                        return code
            finally:
                try:
                    M.logout()
                except Exception:
                    pass
        except Exception as e:
            last_err = e
        time.sleep(poll_seconds)
    if last_err:
        raise TimeoutError(f"No verification code within {timeout_seconds}s (last error: {last_err})")
    raise TimeoutError(f"No verification code within {timeout_seconds}s")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--poll", type=int, default=5)
    ap.add_argument("--since", type=int, default=None,
                    help="Epoch seconds; only consider messages >= this. Default now-300.")
    args = ap.parse_args()
    code = wait_for_verification_code(args.timeout, args.poll, args.since)
    print(code)
