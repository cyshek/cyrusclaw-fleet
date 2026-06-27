import imaplib, email, json, sys
from email.header import decode_header

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
PAYLOAD = "/home/azureuser/.openclaw/agents/making-money/workspace/agency/batch1_payload.json"

with open(PAYLOAD) as f:
    targets = json.load(f)
sent_addrs = {t["to"].lower() for t in targets}

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login(GMAIL, APP_PASS)
M.select("INBOX")

# search recent messages from mailer-daemon / delivery subsystem
typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
ids = data[0].split()
bounced = set()
checked = 0
for mid in ids[-40:]:
    typ, md = M.fetch(mid, "(RFC822)")
    if not md or not md[0]:
        continue
    raw = md[0][1]
    msg = email.message_from_bytes(raw)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            try:
                body += part.get_payload(decode=True).decode("utf-8", "ignore")
            except Exception:
                pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", "ignore")
        except Exception:
            body = str(msg.get_payload())
    checked += 1
    for addr in sent_addrs:
        if addr in body.lower():
            bounced.add(addr)

M.logout()

print(f"Checked {checked} delivery-subsystem messages.")
if bounced:
    print(f"BOUNCED ({len(bounced)}/{len(sent_addrs)}):")
    for a in sorted(bounced):
        print(f"  - {a}")
else:
    print(f"No bounces detected among the {len(sent_addrs)} sent addresses.")
