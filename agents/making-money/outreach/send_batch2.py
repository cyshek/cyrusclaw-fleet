import smtplib
import time
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"

with open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/batch2_merged.json') as f:
    targets = json.load(f)

sent = 0
failed = 0
for t in targets:
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL
        msg['To'] = t['to']
        msg['Subject'] = t['subject']
        msg.attach(MIMEText(t['body'], 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL, APP_PASS)
            s.send_message(msg)
        print("SENT: " + t['to'])
        sent += 1
        time.sleep(4)
    except Exception as e:
        print("FAIL: " + t['to'] + " - " + str(e))
        failed += 1

print("Done - " + str(sent) + " sent, " + str(failed) + " failed")
