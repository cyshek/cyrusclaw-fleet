import imaplib, email, csv

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
SENDLOG = "/home/azureuser/.openclaw/agents/making-money/workspace/agency/batch2_sendlog.csv"

# load the 27 batch-2 addresses
sent = {}
with open(SENDLOG, newline="") as f:\n    for row in csv.DictReader(f):
        sent[row["to"].strip().lower()] = row["name"]

print(f"Batch 2 sendlog: {len(sent)} addresses")

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login(GMAIL, APP_PASS)

bounced = {}  # addr -> set(boxes)
total_daemon = 0

for box in ["INBOX", "[Gmail]/Spam", "[Gmail]/All Mail"]:
    try:
        M.select(box)
        typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
        ids = data[0].split()
        total_daemon += len(ids)
        for mid in ids[-60:]:
            typ, md = M.fetch(mid, "(RFC822)")
            if not md or not md[0]:
                continue
            msg = email.message_from_bytes(md[0][1])
            body = ""
            if msg.is_multipart():
                for p in msg.walk():
                    try:
                        body += p.get_payload(decode=True).decode("utf-8", "ignore")
                    except Exception:
                        pass
            else:
                try:
                    body = msg.get_payload(decode=True).decode("utf-8", "ignore")
                except Exception:
                    body = str(msg.get_payload())
            low = body.lower()
            for addr in sent:
                if addr in low:
                    bounced.setdefault(addr, set()).add(box)
        print(f"{box}: {len(ids)} daemon msgs scanned")
    except Exception as e:\n        print(f"{box}: err {e}")

M.logout()

print("")
if bounced:
    print(f"BOUNCED ({len(bounced)}/{len(sent)}):")
    for a in sorted(bounced):
        print(f"  - {sent[a]} <{a}>  [{', '.join(sorted(bounced[a]))}]")
else:
    print(f"NO BOUNCES detected among the {len(sent)} batch-2 addresses.")
