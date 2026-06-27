import imaplib, email, json

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"

with open("agency/batch1_payload.json") as f:
    targets = json.load(f)
sent = {t["to"].lower() for t in targets}

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login(GMAIL, APP_PASS)

for box in ['[Gmail]/Spam', '[Gmail]/All Mail']:
    try:
        M.select(box)
        typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
        ids = data[0].split()
        hits = set()
        for mid in ids[-30:]:
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
            for a in sent:
                if a in body.lower():
                    hits.add(a)
        print(f"{box}: {len(ids)} daemon msgs, {len(hits)} match our sent list -> {sorted(hits) if hits else 'none'}")
    except Exception as e:
        print(f"{box}: err {e}")

M.logout()
