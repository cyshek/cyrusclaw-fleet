import imaplib, email, json, os
from email.header import decode_header
from datetime import datetime

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
STATE_FILE = "/home/azureuser/.openclaw/agents/making-money/workspace/outreach/reply_state.json"

# Domains we sent outreach to
OUTREACH_DOMAINS = [
    "luxe.salon", "plumbline.com", "hillcrestplumbing.com", "bluefrogplumbing.com",
    "deardental.com", "gentledentalcare.com", "familytreedental.com", "lakesidedentalcare.com",
    "mirrormirrorsalon.com", "riverside.plumbing", "parkerandsons.com", "yourcommunitylawfirm.com",
    "hammondlawgroup.com", "thompsonlawoffice.com", "oaktreelaw.com", "itsdone.com",
    "aaatoday.com", "quickfix.repair", "reliable.repair", "summit.builders",
    "heritage.builders", "precision.builders", "foundations.construction", "ledger.cpa",
    "plumbprofessionals.com", "aceplumbing.com", "beavertondentalcenter.com", "brooksidedental.com",
    "purehairdesign.com", "theblowoutbar.com", "johnsonlawfirm.com", "goldberglawgroup.com",
    "comfortzonehvac.com", "tristatehvac.com", "peakroofingcontractors.com", "nextlevelroofing.com",
    "kpmcpa.com", "omegaconstruction.com", "simpsonlawoffice.com"
]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:\n            return json.load(f)\n    return {"seen_uids": [], "replies": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:\n        json.dump(state, f, indent=2)\n\ndef decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)

def check_replies():
    state = load_state()
    seen = set(state["seen_uids"])
    new_replies = []

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL, APP_PASS)
    mail.select("INBOX")

    # Search for emails with sitelume in subject or from known outreach domains
    _, data = mail.search(None, '(OR SUBJECT "sitelume" SUBJECT "quick fix")')
    uids = data[0].split()

    for uid in uids:
        uid_str = uid.decode()
        if uid_str in seen:
            continue
        _, msg_data = mail.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        from_addr = decode_str(msg.get("From", ""))
        subject = decode_str(msg.get("Subject", ""))
        date = msg.get("Date", "")

        # Check if it's from one of our outreach domains
        from_domain = from_addr.split("@")[-1].rstrip(">").strip().lower() if "@" in from_addr else ""
        is_reply = any(d in from_domain for d in OUTREACH_DOMAINS)

        if is_reply:
            new_replies.append({
                "uid": uid_str,
                "from": from_addr,
                "subject": subject,
                "date": date,
                "domain": from_domain
            })

        seen.add(uid_str)

    mail.logout()

    state["seen_uids"] = list(seen)
    if new_replies:
        state["replies"].extend(new_replies)
    save_state(state)

    return new_replies

if __name__ == "__main__":
    replies = check_replies()
    if replies:
        print(f"NEW REPLIES: {len(replies)}")
        for r in replies:
            print(f"  - {r['from']} | {r['subject']} | {r['date']}")
    else:
        print("No new replies")
