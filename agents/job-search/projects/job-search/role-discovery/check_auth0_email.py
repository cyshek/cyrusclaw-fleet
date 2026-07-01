import imaplib, email, time, re
from email.utils import parsedate_to_datetime

def get_auth0_reset_link(timeout_seconds=120, since_epoch=None):
    """Read Auth0 password reset email from Gmail and return the reset link."""
    if since_epoch is None: since_epoch = time.time() - 300
    pw_path = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.gmail-app-password"
    pw = open(pw_path).read().strip()
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            M.login("cyshekari@gmail.com", pw)
            for mbox in ["INBOX", "[Gmail]/All Mail"]:
                typ, _ = M.select(mbox)
                if typ != "OK": continue
                since_str = time.strftime("%d-%b-%Y", time.gmtime(since_epoch - 86400))
                typ, data = M.search(None, "(SINCE %s)" % since_str)
                if typ != "OK" or not data or not data[0]: continue
                ids = list(reversed(data[0].split()))
                for msg_id in ids[:30]:
                    typ, md = M.fetch(msg_id, "(RFC822)")
                    if typ != "OK" or not md or not md[0]: continue
                    msg = email.message_from_bytes(md[0][1])
                    try:
                        dt = parsedate_to_datetime(msg.get("Date"))
                        if dt and dt.timestamp() < since_epoch - 5: break
                    except Exception: pass
                    subject = str(msg.get("Subject", ""))
                    sender = str(msg.get("From", ""))
                    s = subject.lower(); f = sender.lower()
                    # Auth0 reset email detection
                    is_auth0 = "auth0" in f or "icims" in f or "no-reply" in f or "noreply" in f
                    is_reset = any(x in s for x in ("reset", "password", "forgot", "change your"))
                    print(f"  Checking: {repr(subject[:60])} | {repr(sender[:50])} | match={is_auth0 and is_reset}")
                    if is_auth0 or is_reset:
                        # Extract all https URLs from the body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                ct = part.get_content_type()
                                if ct in ("text/plain", "text/html"):
                                    try: body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                                    except Exception: pass
                        else:
                            try: body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                            except Exception: pass
                        urls = re.findall(r'href=["\']([^"\']+)["\']', body)
                        urls += re.findall(r'https?://[^\s"\'<>)]+', body)
                        for u in urls:
                            if any(k in u.lower() for k in ("reset", "password", "ticket", "change")):
                                print(f"  Found reset URL: {u[:100]}")
                                M.logout()
                                return u
                        print(f"  Auth0/reset email found but no reset URL in {len(urls)} URLs")
                        print(f"  Subject: {subject}")
                        print(f"  Body snippet: {body[:200]}")
            M.logout()
        except Exception as e: print("Gmail err:", e)
        print(f"  Waiting 5s... ({int(deadline - time.time())}s remaining)")
        time.sleep(5)
    return None

import sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
since = time.time() - 600  # check last 10 min
link = get_auth0_reset_link(timeout_seconds=10, since_epoch=since)
print("RESULT:", link)
