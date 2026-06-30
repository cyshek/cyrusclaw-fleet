import smtplib, time, json, csv, sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
FROM_NAME = "Cyrus"
PAYLOAD = "/home/azureuser/.openclaw/agents/making-money/workspace/agency/batch4_payload.json"
LOG = "/home/azureuser/.openclaw/agents/making-money/workspace/agency/batch4_sendlog.csv"

with open(PAYLOAD) as f:
    targets = json.load(f)

rows = []
sent = 0
fail = 0
for i, t in enumerate(targets, 1):
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
        print(f"[{i}/{len(targets)}] SENT -> {t['name']} <{t['to']}>")
    except Exception as e:
        status = f"FAIL: {e}"
        fail += 1
        print(f"[{i}/{len(targets)}] FAIL -> {t['name']} <{t['to']}>  {e}")
    rows.append([ts, t["name"], t["to"], t["subject"], status])
    if i < len(targets):
        time.sleep(6)

with open(LOG, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp_utc", "name", "to", "subject", "status"])
    w.writerows(rows)

print(f"DONE — {sent} sent, {fail} failed out of {len(targets)}. Log: {LOG}")
