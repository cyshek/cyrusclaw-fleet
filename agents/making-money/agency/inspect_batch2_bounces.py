import imaplib, email

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
TARGETS = {"info@allantelife.com": "Allante Life Med Spa", "info@jcooney.com": "Cooney Law Offices, P.S."}

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login(GMAIL, APP_PASS)
M.select("INBOX")
typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
ids = data[0].split()
for mid in ids:
    typ, md = M.fetch(mid, "(RFC822)")
    if not md or not md[0]:
        continue
    msg = email.message_from_bytes(md[0][1])
    subj = msg.get("Subject", "")
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
    for addr, name in TARGETS.items():
        if addr in low:
            print(f"==== {name} <{addr}> ====")
            print("SUBJECT:", subj)
            # find the status/diagnostic lines
            for line in body.splitlines():
                ll = line.lower()
                if any(k in ll for k in [addr, "status", "diagnostic", "550", "551", "552", "553", "554", "permanent", "temporar", "could not be delivered", "wasn't delivered", "rejected", "does not exist", "mailbox", "quota"]):
                    print("  |", line.strip()[:160])
            print("")
M.logout()
