#!/usr/bin/env python3
import imaplib, email, re
from email.header import decode_header as _dh

def decode_h(h):
    out = []
    for b, enc in _dh(h or ''):
        out.append(b.decode(enc or 'utf-8', errors='replace') if isinstance(b, bytes) else b)
    return ''.join(out)

def get_body(msg):
    parts = []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct in ('text/plain', 'text/html'):
            try:
                p = part.get_payload(decode=True)
                if p:
                    parts.append(p.decode('utf-8', errors='replace'))
            except Exception:
                pass
    return "\n".join(parts)



pw = open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.gmail-app-password').read().strip()
M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
M.login('cyshekari@gmail.com', pw)

found = []
for folder in ['INBOX', '[Gmail]/All Mail', '[Gmail]/Spam', 'Job-Noise/Codes']:
    try:
        typ, _ = M.select('"' + folder + '"', readonly=True)
        if typ != 'OK':
            print("  " + folder + ": SELECT failed")
            continue
        typ2, data = M.search(None, 'SINCE 29-Jun-2026')
        ids = data[0].split() if data and data[0] else []
        print("  " + folder + ": " + str(len(ids)) + " msgs")
        for mid in ids[-30:]:
            typ3, md = M.fetch(mid, '(RFC822)')
            if typ3 != 'OK':
                continue
            msg = email.message_from_bytes(md[0][1])
            frm = decode_h(msg.get('From', ''))
            subj = decode_h(msg.get('Subject', ''))
            dt = msg.get('Date', '')
            body = get_body(msg)
            combined = (frm + subj + body).lower()
            relevant = any(k in combined for k in ['icims','auth0','reset','password','keysight','forgot','verify email'])
            if relevant:
                print("  *** [" + dt[-20:] + "] From=" + frm[:60])
                print("      Subj=" + subj[:70])
                all_urls = re.findall(r'https?://[^\s"\'<>)]{15,}', body)
                all_urls += re.findall(r'href=["\']([^"\']{15,})["\']', body, re.IGNORECASE)
                for u in set(all_urls):
                    ul = u.lower()
                    if any(k in ul for k in ['reset','password','ticket','token','auth0','login.icims','activate','verify']):
                        print("      LINK: " + u.replace('&amp;','&')[:120])
                        found.append(u)
            else:
                print("  [" + dt[-16:] + "] " + frm[:38] + " | " + subj[:38])
    except Exception as e:
        print("  " + folder + ": error: " + str(e))

M.logout()
print("=== " + str(len(found)) + " reset links ===")
for l in found:
    print("  " + l)
