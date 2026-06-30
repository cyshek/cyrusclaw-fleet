import smtplib, time, json, csv, sys, os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# Clone of send_batch2.py, for follow-up (touch-2) payloads.
# IMPORTANT: this only sends rows where "replied" is falsy (null/false). Set "replied": true
# (or delete the row) for anyone who already replied BEFORE running this.
# Usage: python3 send_followup.py followup1_payload.json followup1_sendlog.csv

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
FROM_NAME = "Cyrus"
HERE = os.path.dirname(os.path.abspath(__file__))

PAYLOAD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "followup1_payload.json")
LOG = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "followup1_sendlog.csv")
if not os.path.isabs(PAYLOAD):
    PAYLOAD = os.path.join(HERE, PAYLOAD)
if not os.path.isabs(LOG):
    LOG = os.path.join(HERE, LOG)

with open(PAYLOAD) as f:
    targets = json.load(f)

# Safety: skip anyone marked replied, and anyone with no recipient.
to_send = [t for t in targets if not t.get("replied") and t.get("to")]
skipped = [t for t in targets if t.get("replied") or not t.get("to")]
print(f"payload: {PAYLOAD}")
print(f"to send: {len(to_send)}   skipped (replied/no-to): {len(skipped)}")

rows = []
sent = 0
fail = 0
for i, t in enumerate(to_send, 1):
    msg = MIMEMultipart()
    msg["From"] = formataddr((FROM_NAME, GMAIL))
    msg["To"] = t["to"]
    msg["Subject"] = t["subject"]
    msg.attach(MIMEText(t["body"], "plain", "utf-8"))
    ts = datetime.now(timezone.utc).isoformat()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(GMAIL, APP_PASS)
            s.send_message(msg)
        status = "SENT"
        sent += 1
        print(f"[{i}/{len(to_send)}] SENT -> {t['name']} <{t['to']}>")
    except Exception as e:
        status = f"FAIL: {e}"
        fail += 1
        print(f"[{i}/{len(to_send)}] FAIL -> {t['name']} <{t['to']}>  {e}")
    rows.append([ts, t["name"], t["to"], t["subject"], status])
    if i < len(to_send):
        time.sleep(6)

with open(LOG, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp_utc", "name", "to", "subject", "status"])
    w.writerows(rows)

print(f"DONE - {sent} sent, {fail} failed out of {len(to_send)}. Log: {LOG}")
