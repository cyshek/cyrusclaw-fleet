"""
Gmail OTP poller.

Polls cyshekari@gmail.com via IMAP for the most recent Greenhouse "verification
code" email and extracts the 8-character security code. Used as the
`_otp_provider` hook in greenhouse.py so the auto-apply bot can complete the
reCAPTCHA-fallback submit step without human intervention.

Setup (one-time):
  1. Generate a Google App Password at https://myaccount.google.com/apppasswords
     (requires 2FA enabled). 16 chars, no spaces.
  2. Create C:\\OpenClaw\\apply_bot\\assets\\.gmail_credentials with two lines:
        cyshekari@gmail.com
        xxxxxxxxxxxxxxxx
  3. The file is gitignored. Never commit it.

Usage:
  from gmail_otp import GmailOtpPoller
  poller = GmailOtpPoller()                    # raises if creds missing
  applier._otp_provider = poller.fetch_otp
  # or the convenience binding via apply.py --gmail-imap
"""
from __future__ import annotations

import email
import imaplib
import re
import time
from email.header import decode_header
from pathlib import Path
from typing import Callable, Optional

CRED_PATH = Path(__file__).parent / "assets" / ".gmail_credentials"
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Greenhouse OTP emails subject patterns observed in the wild
SUBJECT_PATTERNS = [
    re.compile(r"verification code", re.I),
    re.compile(r"security code", re.I),
    re.compile(r"greenhouse.*code", re.I),
    re.compile(r"confirm.*application", re.I),
]
# 8-char alphanumeric code, mixed case (e.g. "nt53rWbm"). Can appear in subject or body.
CODE_RX = re.compile(r"\b([A-Za-z0-9]{8})\b")


def _read_creds() -> tuple[str, str]:
    if not CRED_PATH.exists():
        raise FileNotFoundError(
            f"Gmail credentials not found at {CRED_PATH}. "
            "See gmail_otp.py docstring for setup."
        )
    lines = [l.strip() for l in CRED_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(lines) < 2:
        raise ValueError(f"{CRED_PATH} must have 2 non-empty lines: email, then app password")
    return lines[0], lines[1]


def _decode_subject(raw: str | None) -> str:
    if not raw:
        return ""
    parts = decode_header(raw)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _extract_code(subject: str, body: str) -> Optional[str]:
    """Find the most likely 8-char OTP. Body wins over subject (Greenhouse OTPs
    are in the body, not the subject)."""
    def _looks_like_code(s: str) -> bool:
        if len(s) != 8:
            return False
        if not any(c.isdigit() for c in s):
            return False  # exclude word-like tokens (e.g. "security", "Cyrus...")
        if s.isdigit():
            if s.startswith("19") or s.startswith("20"):
                return False  # exclude years
        if s in ("ABCDEFGH", "12345678", "00000000"):
            return False
        return True

    # Prefer a code that follows the giveaway phrase
    trigger_pat = re.compile(
        r"(?:security code field on your application|paste this code|verification code)([\s\S]{0,200})",
        re.I,
    )
    m = trigger_pat.search(body)
    if m:
        for tok in CODE_RX.finditer(m.group(1)):
            if _looks_like_code(tok.group(1)):
                return tok.group(1)
    # Fallback: scan whole body, then subject
    for src in (body, subject):
        for tok in CODE_RX.finditer(src):
            if _looks_like_code(tok.group(1)):
                return tok.group(1)
    return None


def _get_body(msg: email.message.Message) -> str:
    """Extract text/plain body (or text/html as fallback)."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(part.get_content_charset() or "utf-8",
                                              errors="replace")
                except Exception:
                    continue
        # Fallback to HTML
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html = payload.decode(part.get_content_charset() or "utf-8",
                                              errors="replace")
                        # Strip tags rough-ly
                        return re.sub(r"<[^>]+>", " ", html)
                except Exception:
                    continue
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return ""


class GmailOtpPoller:
    """Polls Gmail IMAP for the latest Greenhouse OTP email."""

    def __init__(self, since_minutes: int = 5):
        self.email_addr, self.app_password = _read_creds()
        self.since_minutes = since_minutes
        self._poll_started_at: Optional[float] = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        m.login(self.email_addr, self.app_password)
        m.select("INBOX")
        return m

    def _scan_once(self, baseline_ts: float) -> Optional[str]:
        """Single inbox scan: return OTP from any Greenhouse-looking email arrived
        after baseline_ts (unix timestamp), or None."""
        try:
            m = self._connect()
        except Exception as e:
            print(f"  [gmail] connection failed: {e}")
            return None
        try:
            # Search recent. Gmail IMAP supports SINCE in date form (granularity = day).
            # We re-filter by INTERNALDATE in Python for sub-day precision.
            day = time.strftime("%d-%b-%Y", time.gmtime(baseline_ts - 86400))
            typ, data = m.search(None, f'(SINCE {day})')
            if typ != "OK" or not data or not data[0]:
                return None
            ids = data[0].split()
            # Walk newest first, examine up to 30 most recent
            for raw_id in reversed(ids[-30:]):
                typ, idata = m.fetch(raw_id, "(BODY.PEEK[])")
                if typ != "OK" or not idata or not idata[0]:
                    continue
                msg = email.message_from_bytes(idata[0][1])
                # Filter by date
                date_hdr = msg.get("Date", "")
                try:
                    msg_ts = email.utils.mktime_tz(email.utils.parsedate_tz(date_hdr))
                except Exception:
                    msg_ts = 0
                if msg_ts < baseline_ts:
                    continue
                # Filter by sender (greenhouse) or subject keyword
                from_addr = (msg.get("From") or "").lower()
                subj = _decode_subject(msg.get("Subject"))
                if "greenhouse" not in from_addr and \
                        not any(p.search(subj) for p in SUBJECT_PATTERNS):
                    continue
                body = _get_body(msg)
                code = _extract_code(subj, body)
                if code:
                    print(f"  [gmail] found OTP '{code}' in subject='{subj[:60]}' from='{from_addr[:60]}'")
                    return code
            return None
        finally:
            try:
                m.close()
                m.logout()
            except Exception:
                pass

    def fetch_otp(self, _recipient: str = "", timeout_s: int = 90,
                  poll_interval_s: float = 3.0) -> Optional[str]:
        """Block up to `timeout_s` seconds waiting for a fresh OTP email.
        `_recipient` arg is for compatibility with the _otp_provider signature."""
        baseline = self._poll_started_at or (time.time() - 60)  # 1-min back-window
        deadline = time.time() + timeout_s
        print(f"  [gmail] polling {self.email_addr} for OTP (timeout={timeout_s}s)...")
        while time.time() < deadline:
            code = self._scan_once(baseline)
            if code:
                return code
            time.sleep(poll_interval_s)
        print(f"  [gmail] no OTP arrived within {timeout_s}s")
        return None

    def mark_poll_start(self) -> None:
        """Call right before clicking Submit so we ignore older inbox emails."""
        self._poll_started_at = time.time()


def make_provider() -> Callable[[str], Optional[str]]:
    """Convenience: returns a callable suitable for `applier._otp_provider`."""
    poller = GmailOtpPoller()
    poller.mark_poll_start()
    return poller.fetch_otp
