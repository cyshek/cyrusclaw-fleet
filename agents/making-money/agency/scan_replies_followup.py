"""
Pre-follow-up replier + bounce scan (FAST + fail-safe).

Scans Gmail INBOX + [Gmail]/Spam for:
  (1) inbound replies whose From-address matches a recipient we are about to follow up on,
  (2) hard bounces (mailer-daemon / postmaster DSNs) naming one of our recipients.
Writes the union (merged, sticky) to agency/followup_exclude.json so the sender skips them.

SPEED: bounded by IMAP SINCE (default 30 days), batched FETCH (one round-trip per box
instead of one-per-message), and a hard cap on messages scanned. Target < 25s.

FAIL-SAFE: on ANY IMAP error the prior followup_exclude.json is left intact (never
truncated), and we exit non-zero so the orchestrator can decide (it fails safe to the
last-known exclude rather than treating a scan crash as 'nobody to exclude').

Usage: python3 scan_replies_followup.py [--since-days N] [--max N]
"""
import imaplib, email, csv, json, os, re, glob, sys, time
from datetime import datetime, timedelta, timezone
from email.header import decode_header

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
HERE = os.path.dirname(os.path.abspath(__file__))

SINCE_DAYS = 30
MAX_MSGS = 600          # hard cap per box for the reply scan
if "--since-days" in sys.argv:
    SINCE_DAYS = int(sys.argv[sys.argv.index("--since-days") + 1])
if "--max" in sys.argv:
    MAX_MSGS = int(sys.argv[sys.argv.index("--max") + 1])

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


# Recipient universe + their domains (for a targeted reply search).
recipients = {}   # addr -> name
domains = set()
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
                if "@" in a:
                    domains.add(a.split("@", 1)[1])

print(f"Follow-up universe: {len(recipients)} recipients across {len(SENDLOGS)} batches, {len(domains)} domains")

since_str = (datetime.now(timezone.utc) - timedelta(days=SINCE_DAYS)).strftime("%d-%b-%Y")

replied = {}   # addr -> {name, subject, date, box}
bounced = {}   # addr -> set(boxes)


def parse_header_blob(blob):
    """Pull From/Subject/Date out of a HEADER.FIELDS blob."""
    hdr = blob.decode("utf-8", "ignore") if isinstance(blob, bytes) else blob
    fl = sl_ = dl = ""
    for line in hdr.splitlines():
        low = line.lower()
        if low.startswith("from:"):
            fl = line[5:].strip()
        elif low.startswith("subject:"):
            sl_ = line[8:].strip()
        elif low.startswith("date:"):
            dl = line[5:].strip()
    return fl, sl_, dl


t0 = time.time()
err = None
M = None
try:
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    M.login(GMAIL, APP_PASS)

    def sel(box):
        M.select('"%s"' % box if (" " in box or "[" in box) else box, readonly=True)

    # ---- (1) REPLIES: batched header fetch, bounded by SINCE + cap ----
    for box in ["INBOX", "[Gmail]/Spam"]:
        sel(box)
        typ, data = M.search(None, f'(SINCE {since_str})')
        ids = data[0].split()
        if len(ids) > MAX_MSGS:
            ids = ids[-MAX_MSGS:]
        if not ids:
            continue
        # ONE batched FETCH for the whole id set (huge speedup vs per-message).
        id_set = b",".join(ids).decode()
        typ, md = M.fetch(id_set, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        for item in md:
            if not isinstance(item, tuple) or not item[1]:
                continue
            fl, sl_, dl = parse_header_blob(item[1])
            fa = addr_only(fl)
            if fa in recipients and fa not in replied:
                replied[fa] = {"name": recipients[fa], "subject": decode_str(sl_), "date": dl, "box": box}

    # ---- (2) BOUNCES: only mailer-daemon/postmaster DSNs, batched full fetch ----
    for box in ["INBOX", "[Gmail]/Spam"]:
        sel(box)
        # (SINCE x) AND (mailer-daemon OR postmaster) — parenthesize the OR clause so
        # IMAP binds it correctly (bare 'SINCE x OR a b' mis-parses the trailing term).
        typ, data = M.search(None, f'SINCE {since_str} (OR FROM "mailer-daemon" FROM "postmaster")')
        ids = data[0].split()
        if not ids:
            # fall back: some servers dislike the grouped form — retry without SINCE.
            typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
            ids = data[0].split()
        if not ids:
            continue
        if len(ids) > 200:
            ids = ids[-200:]
        id_set = b",".join(ids).decode()
        typ, md = M.fetch(id_set, "(RFC822)")
        for item in md:
            if not isinstance(item, tuple) or not item[1]:
                continue
            try:
                msg = email.message_from_bytes(item[1])
            except Exception:
                continue
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

    M.logout()
except Exception as e:
    err = e
    try:
        if M is not None:
            M.logout()
    except Exception:
        pass

elapsed = time.time() - t0

if err is not None:
    # FAIL-SAFE: do NOT touch followup_exclude.json. Leave last-known intact.
    print(f"SCAN_ERROR after {elapsed:.1f}s: {err}")
    print("followup_exclude.json left UNCHANGED (fail-safe). Exiting non-zero.")
    sys.exit(2)

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

# MERGE with existing file (sticky excludes; IMAP window only sees recent mail).
exclude_path = os.path.join(HERE, "followup_exclude.json")
prev = {"replied": [], "bounced": [], "exclude": []}
try:
    with open(exclude_path) as _pf:
        _loaded = json.load(_pf)
        if isinstance(_loaded, dict):
            prev = _loaded
except Exception:
    pass
merged_replied = sorted(set(prev.get("replied", [])) | set(replied))
merged_bounced = sorted(set(prev.get("bounced", [])) | set(bounced))
merged_exclude = sorted(set(prev.get("exclude", [])) | set(merged_replied) | set(merged_bounced))
new_replied = sorted(set(replied) - set(prev.get("replied", [])))
new_bounced = sorted(set(bounced) - set(prev.get("bounced", [])))
# atomic write
tmp = exclude_path + ".tmp"
with open(tmp, "w") as f:
    json.dump({"replied": merged_replied, "bounced": merged_bounced, "exclude": merged_exclude}, f, indent=2)
os.replace(tmp, exclude_path)
print("")
print(f"Wrote followup_exclude.json — {len(merged_exclude)} addresses to exclude (merged). scan {elapsed:.1f}s")
if new_replied:
    print(f"  NEW replies this scan: {new_replied}")
if new_bounced:
    print(f"  NEW bounces this scan: {new_bounced}")
