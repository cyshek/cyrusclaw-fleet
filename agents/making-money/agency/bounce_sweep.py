import imaplib, email, csv, re

recipients = set()
names = {}
for fname in ["batch4_sendlog.csv", "followup1_sendlog.csv"]:
    fr = open(fname)
    for row in csv.DictReader(fr):
        e = row["to"].strip().lower()
        recipients.add(e)
        names[e] = row["name"].strip()
    fr.close()

print("Loaded", len(recipients), "unique recipients")

M = imaplib.IMAP4_SSL("imap.gmail.com")
M.login("cyshekari@gmail.com", "yjse lddd mhan gbpe")
print("Login OK")

bounces = []
seen_recips = set()

for folder in ["INBOX", "[Gmail]/Spam"]:
    try:
        status, _ = M.select(folder, readonly=True)
        if status != "OK":
            print("Could not select", folder)
            continue
        all_id_set = set()
        searches = [
            ("FROM", "mailer-daemon@googlemail.com"),
            ("FROM", "postmaster"),
            ("SUBJECT", "Delivery Status Notification"),
            ("SUBJECT", "Mail Delivery Subsystem"),
            ("SUBJECT", "Undeliverable"),
            ("SUBJECT", "delivery failed"),
        ]
        for criterion, value in searches:
            try:
                s2, data = M.search(None, criterion, value)
                if s2 == "OK" and data[0]:
                    for mid in data[0].split():
                        all_id_set.add(mid)
            except Exception as ex:
                print("Search error", criterion, value, ex)
        print(folder, len(all_id_set), "potential DSN messages")
        for mid in all_id_set:
            try:
                s3, msg_data = M.fetch(mid, "(RFC822)")
                if s3 != "OK":
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                full_text = ""
                for part in msg.walk():
                    try:
                        ct = part.get_content_type()
                        if ct in ("text/plain", "message/delivery-status", "text/html"):
                            payload = part.get_payload(decode=True)
                            if payload:
                                full_text += payload.decode("utf-8", errors="replace")
                    except Exception:
                        pass
                full_lower = full_text.lower()
                import re as re2
                for recip in recipients:
                    if recip in full_lower and recip not in seen_recips:
                        reason = "unknown"
                        m = re2.search(r"(5\d\d[^\n]{0,120})", full_text, re2.IGNORECASE)
                        if m:
                            reason = m.group(1).strip()
                        else:
                            m2 = re2.search(r"(Diagnostic[^\n]{0,120})", full_text, re2.IGNORECASE)
                            if m2:
                                reason = m2.group(1).strip()
                        bounces.append({"email": recip, "name": names[recip], "reason": reason, "folder": folder})
                        seen_recips.add(recip)
                        break
            except Exception as ex:
                print("Error fetching", mid, ex)
    except Exception as ex:
        print("Error in folder", folder, ex)

M.logout()
print("
=== BOUNCES FOUND:", len(bounces), "===")
for b in bounces:
    print(" -", b["name"], "<" + b["email"] + ">", "|", b["folder"], "|", b["reason"])
if not bounces:
    print("  (none)")
