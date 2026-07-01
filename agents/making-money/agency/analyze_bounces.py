#!/usr/bin/env python3
"""
Deliverability bounce analysis.
Parses every mailer-daemon / Delivery-Status-Notification in INBOX + [Gmail]/Spam,
extracts the FAILED recipient address + SMTP reason/status code, maps each failed
address to the batch it belongs to, and prints a clean report + JSON.

No sending. Read-only IMAP.
"""
import imaplib, email, csv, json, os, re, glob
from collections import defaultdict

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
HERE = os.path.dirname(os.path.abspath(__file__))

# Build recipient -> batch map from all batch*_sendlog.csv (SENT rows only).
recip_batch = {}   # addr -> set(batch_ids)
all_recipients = set()
for sl in sorted(glob.glob(os.path.join(HERE, "batch*_sendlog.csv"))):
    m = re.search(r"batch(\d+)_sendlog\.csv$", sl)
    bid = m.group(1) if m else "?"
    for r in csv.DictReader(open(sl)):
        if (r.get("status") or "").strip().upper() == "SENT":
            a = (r.get("to") or "").strip().lower()
            if a:
                recip_batch.setdefault(a, set()).add(bid)
                all_recipients.add(a)

# Also include follow-up sendlogs so a bounce from a touch-2 is attributable.
for sl in sorted(glob.glob(os.path.join(HERE, "followup_*_sendlog.csv"))) + \
          [os.path.join(HERE, "followup1_sendlog.csv")]:
    if not os.path.exists(sl):
        continue
    tag = os.path.basename(sl).replace("_sendlog.csv", "")
    for r in csv.DictReader(open(sl)):
        if (r.get("status") or "").strip().upper() == "SENT":
            a = (r.get("to") or "").strip().lower()
            if a:
                recip_batch.setdefault(a, set()).add(tag)

def batch_of(addr):
    b = recip_batch.get(addr)
    return ",".join(sorted(b)) if b else "(not in any sendlog)"

M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
M.login(GMAIL, APP_PASS)

def sel(box):
    M.select('"%s"' % box if (" " in box or "[" in box) else box, readonly=True)

# reason classification
HARD_PATTERNS = [
    (r"550[ \-]?5\.1\.1", "550-5.1.1 mailbox does not exist"),
    (r"550[ \-]?5\.1\.10", "550-5.1.10 address does not exist"),
    (r"does not exist", "recipient address does not exist"),
    (r"no such user", "no such user"),
    (r"user unknown", "user unknown"),
    (r"unknown user", "unknown user"),
    (r"mailbox unavailable", "mailbox unavailable"),
    (r"recipient rejected", "recipient rejected"),
    (r"address rejected", "address rejected"),
    (r"domain[^.]{0,20}(not found|does not exist|couldn't be found)", "domain not found"),
    (r"nxdomain|dns error|couldn't be found.*domain", "domain/DNS not found"),
    (r"550[ \-]?5\.4\.1", "550-5.4.1 recipient rejected (no MX/relay)"),
    (r"553", "553 mailbox name not allowed"),
]
POLICY_PATTERNS = [
    (r"spam", "flagged as spam/policy"),
    (r"blocked", "blocked by policy"),
    (r"blacklist|blocklist|spamhaus|rbl", "listed on blocklist"),
    (r"reputation", "sender reputation"),
    (r"554[ \-]?5\.7", "554-5.7 policy rejection"),
    (r"550[ \-]?5\.7", "550-5.7 policy rejection"),
    (r"rate limit|too many|throttl", "rate-limited"),
]

def classify(body):
    low = body.lower()
    for pat, label in HARD_PATTERNS:
        if re.search(pat, low):
            return "HARD", label
    for pat, label in POLICY_PATTERNS:
        if re.search(pat, low):
            return "POLICY", label
    # generic 5xx = hard-ish permanent
    if re.search(r"\b5\d\d[ \-]5\.\d", low) or "permanent" in low or "failure" in low:
        return "HARD", "permanent failure (5xx, unspecified)"
    return "UNKNOWN", "unclassified"

def extract_failed_recipients(msg, body):
    """Find failed recipient addresses. Prefer the Final-Recipient DSN field; fall back
    to any of OUR sent recipients that appear in the body."""
    found = set()
    # 1) DSN Final-Recipient / Original-Recipient fields
    for m in re.finditer(r"(?:Final-Recipient|Original-Recipient)\s*:\s*[^;\n]*;\s*([^\s>]+@[^\s>]+)", body, re.I):
        found.add(m.group(1).strip().strip("<>").lower())
    # 2) "to <addr>" style
    for m in re.finditer(r"to\s+<([^>]+@[^>]+)>", body, re.I):
        found.add(m.group(1).strip().lower())
    # 3) fall back: any recipient of ours mentioned in the body
    low = body.lower()
    for a in all_recipients:
        if a in low:
            found.add(a)
    # normalize + keep only plausible addresses; drop our own from-address
    out = set()
    for a in found:
        a = a.strip().strip("<>.,;").lower()
        if "@" in a and a != GMAIL.lower():
            out.add(a)
    return out

bounces = {}   # addr -> {reason, kind, boxes:set, dates:set}
dsn_count = 0
scanned = 0

for box in ["INBOX", "[Gmail]/Spam"]:
    try:
        sel(box)
        typ, data = M.search(None, '(OR FROM "mailer-daemon" FROM "postmaster")')
        ids = data[0].split()
        for mid in ids:
            typ, md = M.fetch(mid, "(RFC822)")
            if not md or not md[0]:
                continue
            scanned += 1
            msg = email.message_from_bytes(md[0][1])
            subj = str(msg.get("Subject") or "")
            date = str(msg.get("Date") or "")
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
            # only treat as DSN if it looks like a failure notice
            if not re.search(r"delivery status|failure|undeliver|delivery.*failed|returned to sender|wasn'?t delivered|couldn'?t be delivered", (subj + " " + body).lower()):
                continue
            dsn_count += 1
            kind, reason = classify(body)
            for addr in extract_failed_recipients(msg, body):
                rec = bounces.setdefault(addr, {"reason": reason, "kind": kind, "boxes": set(), "dates": set()})
                rec["boxes"].add(box)
                rec["dates"].add(date[:31])
                # prefer a HARD/POLICY classification over UNKNOWN
                if rec["kind"] == "UNKNOWN" and kind != "UNKNOWN":
                    rec["kind"], rec["reason"] = kind, reason
    except Exception as e:
        print(f"{box}: err {e}")

M.logout()

# Only keep bounces that are actually addresses we sent to (defensible bounce rate).
our_bounces = {a: v for a, v in bounces.items() if a in all_recipients}
other_bounces = {a: v for a, v in bounces.items() if a not in all_recipients}

hard = {a: v for a, v in our_bounces.items() if v["kind"] == "HARD"}
policy = {a: v for a, v in our_bounces.items() if v["kind"] == "POLICY"}
unknown = {a: v for a, v in our_bounces.items() if v["kind"] == "UNKNOWN"}

total_recip = len(all_recipients)
n_hard = len(hard)
rate = (n_hard / total_recip * 100) if total_recip else 0.0

print("=" * 70)
print(f"DSN messages scanned (mailer-daemon/postmaster): {scanned}")
print(f"Parsed as delivery-failure DSNs: {dsn_count}")
print(f"Total unique recipients sent (all batches): {total_recip}")
print("=" * 70)
print(f"UNIQUE HARD bounces (our recipients): {n_hard}")
print(f"POLICY/spam bounces (our recipients): {len(policy)}")
print(f"UNKNOWN-class bounces (our recipients): {len(unknown)}")
print(f"HARD bounce rate = {n_hard}/{total_recip} = {rate:.1f}%")
print("=" * 70)
print("HARD BOUNCE LIST (address | reason | batch):")
for a in sorted(hard):
    v = hard[a]
    print(f"  {a} | {v['reason']} | {batch_of(a)} | [{','.join(sorted(v['boxes']))}]")
if policy:
    print("")
    print("POLICY/SPAM BOUNCES (reputation risk):")
    for a in sorted(policy):
        v = policy[a]
        print(f"  {a} | {v['reason']} | {batch_of(a)}")
if unknown:
    print("")
    print("UNKNOWN-CLASS (manual review):")
    for a in sorted(unknown):
        v = unknown[a]
        print(f"  {a} | {v['reason']} | {batch_of(a)}")
if other_bounces:
    print("")
    print(f"(DSNs mentioning addresses NOT in our sendlogs: {len(other_bounces)} — excluded from rate)")
    for a in sorted(other_bounces):
        print(f"    {a} | {other_bounces[a]['reason']}")

# dump JSON for the report/exclude step
out = {
    "total_recipients_sent": total_recip,
    "hard_bounces": {a: {"reason": v["reason"], "batch": batch_of(a), "boxes": sorted(v["boxes"]), "dates": sorted(v["dates"])} for a, v in hard.items()},
    "policy_bounces": {a: {"reason": v["reason"], "batch": batch_of(a)} for a, v in policy.items()},
    "unknown_bounces": {a: {"reason": v["reason"], "batch": batch_of(a)} for a, v in unknown.items()},
    "hard_bounce_rate_pct": round(rate, 2),
}
json.dump(out, open(os.path.join(HERE, "bounce_analysis.json"), "w"), indent=2)
print("")
print("Wrote bounce_analysis.json")
