#!/usr/bin/env python3
"""
fetch_company_code.py — like gmail_imap.wait_for_verification_code() but
filters by a company keyword in the subject line so it can't accidentally
pick the code from a different company's verification email.

Usage:
    python fetch_company_code.py "<company keyword>" <since_epoch> [--timeout 120] [--poll 5]

Prints the 8-char code to stdout on success. Exits non-zero on timeout.
"""
from __future__ import annotations
import argparse
import email
import imaplib
import re
import ssl
import sys
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PW = (ROOT / ".gmail-app-password").read_text().strip().replace(" ", "")

# ---- Personal info loader --------------------------------------------------
def _load_gmail_user():
    try:
        import json as _j
        pi = _j.load(open(ROOT / "personal-info.json"))
        return pi["identity"]["email"]
    except Exception:
        return ""

GMAIL_USER = _load_gmail_user()

CODE_RE_H1 = re.compile(r"<h1[^>]*>\s*([A-Za-z0-9]{8})\s*</h1>", re.I)
CODE_RE_NEAR = re.compile(
    r"(?:security code|verification code|code)[^A-Za-z0-9]{0,40}([A-Za-z0-9]{8})\b",
    re.I,
)
CODE_RE_ANY = re.compile(r"\b([A-Za-z0-9]{8})\b")


def _decode(s):
    if s is None:
        return ""
    if isinstance(s, bytes):
        try:
            return s.decode("utf-8", errors="replace")
        except Exception:
            return s.decode("latin-1", errors="replace")
    from email.header import decode_header
    parts = decode_header(s)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)


def _msg_text(msg):
    chunks = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True) or b""
                    chunks.append(
                        payload.decode(
                            part.get_content_charset() or "utf-8",
                            errors="replace",
                        )
                    )
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            chunks.append(
                msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or "utf-8", errors="replace"
                )
            )
        except Exception:
            pass
    return "\n".join(chunks)


def _extract_code(body, subject=""):
    m = CODE_RE_H1.search(body)
    if m:
        return m.group(1)
    plain = re.sub(r"<[^>]+>", " ", body)
    plain = re.sub(r"&nbsp;|&#xA0;", " ", plain)
    for hay in (subject, plain):
        m = CODE_RE_NEAR.search(hay)
        if m:
            return m.group(1)
    # Fallback: look for tokens with letters AND digits, 8 chars
    for hay in (subject, plain):
        for m in CODE_RE_ANY.finditer(hay):
            tok = m.group(1)
            if any(c.isalpha() for c in tok) and any(c.isdigit() for c in tok):
                return tok
    return None


def search(company_kw: str, since_epoch: float, timeout: int, poll: int):
    deadline = time.time() + timeout
    company_lc = company_kw.lower()
    last_err = None
    while time.time() < deadline:
        try:
            ctx = ssl.create_default_context()
            M = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
            M.login(GMAIL_USER, APP_PW)
            try:
                for mbox in ("INBOX", '"[Gmail]/Spam"'):
                    typ, _ = M.select(mbox)
                    if typ != "OK":
                        continue
                    since_str = time.strftime(
                        "%d-%b-%Y", time.gmtime(since_epoch - 86400)
                    )
                    typ, data = M.search(None, f"(SINCE {since_str})")
                    if typ != "OK" or not data or not data[0]:
                        continue
                    ids = list(reversed(data[0].split()))
                    for msg_id in ids[:60]:
                        typ, msg_data = M.fetch(msg_id, "(RFC822)")
                        if typ != "OK" or not msg_data or not msg_data[0]:
                            continue
                        raw = msg_data[0][1]
                        msg = email.message_from_bytes(raw)
                        try:
                            dt = parsedate_to_datetime(msg.get("Date"))
                            if dt and dt.timestamp() < since_epoch - 30:
                                break  # rest are older
                        except Exception:
                            pass
                        subject = _decode(msg.get("Subject", ""))
                        sender = _decode(msg.get("From", ""))
                        body = _msg_text(msg)
                        haystack = (subject + " " + sender).lower()
                        # MUST contain the company keyword
                        if company_lc not in haystack:
                            continue
                        # MUST be a verification email
                        sl = subject.lower()
                        bl = body.lower()
                        if not (
                            "security code" in sl
                            or "verification code" in sl
                            or "verify" in sl
                            or "confirm" in sl
                            or "security code" in bl
                            or "verification code" in bl
                        ):
                            continue
                        code = _extract_code(body, subject)
                        if code:
                            print(
                                f"FOUND_CODE\tcode={code}\tsubject={subject[:100]}\tfrom={sender[:80]}",
                                file=sys.stderr,
                            )
                            return code
            finally:
                try:
                    M.logout()
                except Exception:
                    pass
        except Exception as e:
            last_err = e
        time.sleep(poll)
    raise TimeoutError(
        f"No verification code matching '{company_kw}' within {timeout}s"
        + (f" (last err: {last_err})" if last_err else "")
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("company")
    ap.add_argument("since", type=int)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--poll", type=int, default=5)
    args = ap.parse_args()
    code = search(args.company, args.since, args.timeout, args.poll)
    print(code)
