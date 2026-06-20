"""Broader scan: ANY email from ashbyhq.com domain or with Ashby tenant
keywords since 2026-05-04 — print subject/from to help diagnose what
confirmation patterns we're missing.
"""
from __future__ import annotations

import email
import imaplib

from gmail_otp import _read_creds, _decode_subject, IMAP_HOST, IMAP_PORT


def main() -> None:
    email_addr, app_pw = _read_creds()
    print(f"Connecting as {email_addr}...")
    m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    m.login(email_addr, app_pw)

    seen: set[str] = set()
    rows: list[tuple[str, str, str, str]] = []

    for mailbox in ('INBOX', '"[Gmail]/All Mail"', '"[Gmail]/Spam"'):
        try:
            typ, _ = m.select(mailbox, readonly=True)
            if typ != "OK":
                continue
        except Exception:
            continue
        typ, data = m.search(None, '(SINCE 04-May-2026)')
        if typ != "OK" or not data or not data[0]:
            continue
        ids = data[0].split()
        for raw_id in reversed(ids[-300:]):
            typ, idata = m.fetch(raw_id, "(BODY.PEEK[HEADER])")
            if typ != "OK" or not idata or not idata[0]:
                continue
            try:
                msg = email.message_from_bytes(idata[0][1])
            except Exception:
                continue
            from_addr = (msg.get("From") or "").lower()
            subj = _decode_subject(msg.get("Subject"))
            date_hdr = msg.get("Date", "")
            mid = msg.get("Message-ID", "") or f"{from_addr}|{subj}"
            blob = (from_addr + " " + subj).lower()
            keywords = ["ashby", "decagon", "harvey", "openai", "sierra",
                        "lovable"]
            if not any(k in blob for k in keywords):
                continue
            if mid in seen:
                continue
            seen.add(mid)
            rows.append((mailbox.strip('"'), date_hdr[:25], from_addr[:55],
                         subj[:90]))
    try:
        m.logout()
    except Exception:
        pass

    print(f"\n{len(rows)} matches:\n")
    rows.sort(key=lambda r: r[1])
    for mb, d, frm, sj in rows:
        print(f"[{mb[:12]:<12}] {d[:25]:<25} {frm[:50]:<50} {sj}")


if __name__ == "__main__":
    main()
