"""One-off: scan Gmail for Ashby application confirmations from the
2026-05-04 batch. Reuses gmail_otp.py credential loader.

Looks at INBOX (and All Mail / Spam if visible) for emails since
2026-05-04 from Ashby tenants in our queue, prints subject/from/date
for anything that looks like an application acknowledgement.
"""
from __future__ import annotations

import email
import imaplib
import re
import time
from email.header import decode_header

from gmail_otp import _read_creds, _decode_subject, _get_body, IMAP_HOST, IMAP_PORT

TENANTS = ["decagon", "harvey", "openai", "sierra", "lovable", "ashby",
           "ashbyhq.com"]
CONF_RX = re.compile(
    r"(thank you for (applying|your application)|"
    r"we[' ]?ve received your application|"
    r"received your application|"
    r"application (received|received!|submitted|complete)|"
    r"your application (has been|to)|"
    r"applying to|"
    r"thanks for applying)",
    re.I,
)
SINCE_DATE_IMAP = "04-May-2026"  # IMAP SINCE is inclusive of date (UTC)


def main() -> None:
    email_addr, app_pw = _read_creds()
    print(f"Connecting as {email_addr}...")
    m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    m.login(email_addr, app_pw)
    seen_keys: set[str] = set()
    matches: list[dict] = []

    for mailbox in ('INBOX', '"[Gmail]/All Mail"', '"[Gmail]/Spam"'):
        try:
            typ, _ = m.select(mailbox, readonly=True)
            if typ != "OK":
                continue
        except Exception:
            continue
        typ, data = m.search(None, f'(SINCE {SINCE_DATE_IMAP})')
        if typ != "OK" or not data or not data[0]:
            continue
        ids = data[0].split()
        print(f"  {mailbox}: {len(ids)} msgs since {SINCE_DATE_IMAP}")
        # Walk newest-first, examine up to 200
        for raw_id in reversed(ids[-200:]):
            typ, idata = m.fetch(raw_id, "(BODY.PEEK[])")
            if typ != "OK" or not idata or not idata[0]:
                continue
            try:
                msg = email.message_from_bytes(idata[0][1])
            except Exception:
                continue
            from_addr = (msg.get("From") or "").lower()
            subj = _decode_subject(msg.get("Subject"))
            date_hdr = msg.get("Date", "")
            msg_id = msg.get("Message-ID", "") or f"{from_addr}|{subj}"
            if msg_id in seen_keys:
                continue
            # Quick filter: tenant in from-addr OR subject; or 'ashby' in headers
            blob = (from_addr + " " + subj).lower()
            if not any(t in blob for t in TENANTS):
                continue
            body = _get_body(msg)
            text = subj + "\n" + (body[:5000] if body else "")
            if CONF_RX.search(text):
                seen_keys.add(msg_id)
                matches.append({
                    "from": from_addr[:80],
                    "subject": subj[:120],
                    "date": date_hdr[:40],
                    "mailbox": mailbox.strip('"'),
                })
    try:
        m.logout()
    except Exception:
        pass

    print()
    print("=" * 70)
    print(f"Found {len(matches)} likely application-confirmation emails")
    print("=" * 70)
    for x in matches:
        print(f"  [{x['mailbox']}] {x['date'][:25]}  {x['from'][:40]}")
        print(f"    {x['subject']}")
    if not matches:
        print("  (none)")
    # Group by tenant for the rollup
    by_tenant: dict[str, int] = {}
    for x in matches:
        for t in TENANTS:
            if t in (x["from"] + x["subject"]).lower():
                by_tenant[t] = by_tenant.get(t, 0) + 1
                break
    print()
    print("By tenant:")
    for t, c in sorted(by_tenant.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
