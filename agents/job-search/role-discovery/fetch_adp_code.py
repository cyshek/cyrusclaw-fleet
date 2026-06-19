#!/usr/bin/env python3
"""fetch_adp_code.py - fetch ADP email verification code (4-8 digit) from cyshekari@gmail.com.

Usage: python fetch_adp_code.py <since_epoch> [--timeout 150] [--poll 6]
Prints numeric code to stdout; exit 2 on timeout.
"""
from __future__ import annotations
import argparse, email, imaplib, re, ssl, sys, time
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PW = (ROOT / ".gmail-app-password").read_text().strip().replace(" ", "")
GMAIL_USER = "cyshekari@gmail.com"
MAILBOXES = ['"[Gmail]/All Mail"', "INBOX"]

NEAR_RE = re.compile(r"(?:verification code|security code|one[- ]time|passcode|code is|your code)[^0-9]{0,40}(\d{4,8})\b", re.I)
ANY6_RE = re.compile(r"\b(\d{6})\b")
SENDER_HINTS = ("adp", "myadp", "workforcenow", "recruiting", "no-reply", "noreply", "donotreply")
SUBJ_HINTS = ("verification", "security code", "verify", "code", "one-time", "passcode", "confirm")
NL = chr(10)


def _txt(msg):
    out = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for p in parts:
        if p.get_content_type() in ("text/plain", "text/html"):
            try:
                out.append(p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace"))
            except Exception:
                pass
    return NL.join(out)


def _extract(subject, body):
    plain = re.sub(r"<[^>]+>", " ", body)
    plain = re.sub(r"&nbsp;|&#xA0;", " ", plain)
    for hay in (subject, plain):
        m = NEAR_RE.search(hay)
        if m:
            return m.group(1)
    m = ANY6_RE.search(plain)
    if m:
        return m.group(1)
    return None


def _connect():
    M = imaplib.IMAP4_SSL("imap.gmail.com", ssl_context=ssl.create_default_context())
    M.login(GMAIL_USER, APP_PW)
    return M


def fetch(since_epoch, timeout=150, poll=6):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            M = _connect()
            try:
                for mbox in MAILBOXES:
                    try:
                        M.select(mbox, readonly=True)
                    except Exception:
                        continue
                    typ, data = M.search(None, "ALL")
                    ids = data[0].split()
                    for mid in reversed(ids[-40:]):
                        typ, raw = M.fetch(mid, "(RFC822)")
                        if not raw or not raw[0]:
                            continue
                        msg = email.message_from_bytes(raw[0][1])
                        try:
                            dt = parsedate_to_datetime(msg.get("Date"))
                            if dt and dt.timestamp() < since_epoch - 30:
                                continue
                        except Exception:
                            pass
                        subject = str(msg.get("Subject", ""))
                        sender = str(msg.get("From", "")).lower()
                        body = _txt(msg)
                        hint = any(h in sender for h in SENDER_HINTS) or any(h in subject.lower() for h in SUBJ_HINTS) or ("adp" in body.lower())
                        if not hint:
                            continue
                        code = _extract(subject, body)
                        if code:
                            return code
            finally:
                try:
                    M.logout()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(poll)
    raise TimeoutError("No ADP code within %ds" % timeout)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("since", type=float, nargs="?", default=time.time() - 120)
    ap.add_argument("--timeout", type=int, default=150)
    ap.add_argument("--poll", type=int, default=6)
    args = ap.parse_args()
    try:
        print(fetch(args.since, args.timeout, args.poll))
    except TimeoutError as e:
        print("TIMEOUT: %s" % e, file=sys.stderr)
        sys.exit(2)
