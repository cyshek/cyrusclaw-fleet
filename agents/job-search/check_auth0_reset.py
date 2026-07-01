#!/usr/bin/env python3
"""check_auth0_reset.py - Check Gmail for ANY Auth0 password reset email and extract the link."""
import imaplib, email, re, time
from email.header import decode_header as _dh

def _decode(h):
    parts = _dh(h or '')
    out = []
    for b, enc in parts:
        if isinstance(b, bytes):
            out.append(b.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(b)
    return ''.join(out)

def _msg_text(msg):
    parts = []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct in ('text/plain', 'text/html'):
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode('utf-8', errors='replace'))
            except Exception:
                pass
    return '\n'.join(parts)

pw = open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.gmail-app-password').read().strip()

M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
M.login('cyshekari@gmail.com', pw)

print("Checking Gmail for Auth0 reset emails (last 3 days)...")

found_links = []

for folder in ['[Gmail]/All Mail', 'INBOX', '[Gmail]/Spam', 'Job-Noise/Codes']:
    try:
        typ, _ = M.select(folder, readonly=True)
        if typ != 'OK':
            continue
        typ, data = M.search(None, 'SINCE 29-Jun-2026')
        ids = data[0].split() if data and data[0] else []
        print(f"\n{folder}: {len(ids)} messages since Jun 29")
        for msg_id in ids[-100:]:
            typ, md = M.fetch(msg_id, '(RFC822)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(md[0][1])
            frm = _decode(msg.get('From', ''))
            subj = _decode(msg.get('Subject', ''))
            dt = msg.get('Date', '')[-30:]
            # Check if it looks auth0/icims related
            body = _msg_text(msg)
            is_relevant = any(kw in (frm+subj+body).lower() for kw in [
                'auth0', 'login.icims', 'reset', 'password', 'keysight'
            ])
            if not is_relevant:
                continue
            print(f"  [{dt}] From={frm[:50]} | Subj={subj[:60]}")
            # Extract ALL URLs
            urls = re.findall(r'https?://[^\s"\'<>)]+', body)
            href_urls = re.findall(r'href=["\']([^"\']+)["\']', body, re.IGNORECASE)
            all_urls = list(set(urls + href_urls))
            for url in all_urls:
                if any(kw in url.lower() for kw in ['reset', 'password', 'auth0', 'login.icims', 'ticket', 'token']):
                    clean_url = url.replace('&amp;', '&')
                    print(f"    LINK: {clean_url[:120]}")
                    found_links.append(clean_url)
    except Exception as e:
        print(f"  Error {folder}: {e}")

M.logout()

for l in found_links:
    print(f"  {l}")
