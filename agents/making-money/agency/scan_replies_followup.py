"""
Pre-follow-up replier + bounce scan.
Scans the Gmail inbox/spam/all-mail for ANY inbound mail whose From-address matches
a recipient we are about to follow up on (batches 1-3). Flags repliers (positive OR
negative) so they can be excluded before sending touch-2, and flags hard bounces.

Output: prints REPLIED and BOUNCED address lists, and writes them to
agency/followup_exclude.json so the sender can skip them.

Usage: python3 scan_replies_followup.py
"""
import imaplib, email, csv, json, os, re, glob
from email.header import decode_header

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
HERE = os.path.dirname(os.path.abspath(__file__))

# Follow-up universe = EVERY batch we've sent. Auto-discover all batch*_sendlog.csv so
# new batches (batch4, batch5, ...) are covered automatically without editing this list.
SENDLOGS = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "batch*_sendlog.csv")))

def decode_str(s):
    if not s:
        return ""
    out = []
    for part, enc in decode_header(s):
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out)

def addr_only(raw):
    if not raw:
        return ""
    m = re.search(r"[\w.\-+]+@[\w.\-]+", raw)
    return m.group(0).lower() if m else ""

# Build the set of recipient addresses across all follow-up batches.
recipients = {}  # addr -> name
for sl in SENDLOGS:
    p = os.path.join(HERE, sl)
    if not os.path.exists(p):
        print(f"(missing {sl}, skipping)")
        continue
    with open(p, newline="") as f:
        for row in csv.DictReader(f):
            a = (row.get("to") or "").strip().lower()
            if a:
                recipients[a] = row.get("name", "")

print(f"Follow-up universe: {len(recipients)} recipient addresses across {len(SENDLOGS)} batches")

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login(GMAIL, APP_PASS)

replied = {}   # addr -> {subject, date}
bounced = {}   # addr -> set(boxes)

# 1) Direct replies: any inbound message whose From matches a recipient address.
def sel(box):
    # Gmail special-use mailboxes with spaces/brackets must be quoted in SELECT.
    M.select('"%s"' % box if (" " in box or "[" in box) else box, readonly=True)

for box in ["INBOX", "[Gmail]/Spam"]:
    try:
        sel(box)
        typ, data = M.search(None, "ALL")
        ids = data[0].split()
        # Only scan the most recent slice for speed (plenty for a few-day window).
        for mid in ids[-400:]:
            typ, md = M.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if not md or not md[0]:
                continue
            hdr = md[0][1].decode("utf-8", "ignore")
            from_line = ""
            subj_line = ""
            date_line = ""
            for line in hdr.splitlines():
                low = line.lower()
                if low.startswith("from:"):
                    from_line = line[5:].strip()
                elif low.startswith("subject:"):
                    subj_line = line[8:].strip()
                elif low.startswith("date:"):
                    date_line = line[5:].strip()
            fa = addr_only(from_line)
            if fa in recipients and fa not in replied:
                replied[fa] = {"name": recipients[fa], "subject": decode_str(subj_line), "date": date_line, "box": box}
    except Exception as e:
        print(f"{box}: reply-scan err {e}")

# 2) Bounces: mailer-daemon / postmaster messages mentioning a recipient address.
for box in ["INBOX", "[Gmail]/Spam"]:
    try:
        sel(box)
        typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
        ids = data[0].split()
        for mid in ids[-80:]:
            typ, md = M.fetch(mid, "(RFC822)")
            if not md or not md[0]:
                continue
            msg = email.message_from_bytes(md[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    try:
                        body += (part.get_payload(decode=True) or b"").decode("utf-8", "ignore")
                    except Exception:
                        pass
            else:
                try:
                    body = (msg.get_payload(decode=True) or b"").decode("utf-8", "ignore")
                except Exception:
                    body = str(msg.get_payload())
            low = body.lower()
            for a in recipients:
                if a in low:
                    bounced.setdefault(a, set()).add(box)
    except Exception as e:
        print(f"{box}: bounce-scan err {e}")

M.logout()

print("")
print(f"REPLIED ({len(replied)}):")
for a in sorted(replied):
    r = replied[a]
    print(f"  - {r['name']} <{a}>  subj={r['subject']!r}  [{r['box']}]  {r['date']}")
if not replied:
    print("  (none)")

print("")
print(f"BOUNCED ({len(bounced)}):")
for a in sorted(bounced):
    print(f"  - {recipients[a]} <{a}>  [{', '.join(sorted(bounced[a]))}]")
if not bounced:
    print("  (none)")

# Write exclusion set (union of replied + bounced) for the sender to honor.
exclude = sorted(set(replied) | set(bounced))
with open(os.path.join(HERE, "followup_exclude.json"), "w") as f:
    json.dump({"replied": sorted(replied), "bounced": sorted(bounced), "exclude": exclude}, f, indent=2)
print("")
print(f"Wrote followup_exclude.json — {len(exclude)} addresses to exclude from follow-ups.")
