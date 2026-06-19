import smtplib, time, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"

with open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/new_targets.json') as f:\n    targets = json.load(f)\n\nsent = 0\nfor t in targets:\n    msg = MIMEMultipart()\n    msg['From'] = GMAIL\n    msg['To'] = t['to']\n    msg['Subject'] = t['subject']\n    msg.attach(MIMEText(t['body'], 'plain'))\n    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:\n        s.login(GMAIL, APP_PASS)\n        s.send_message(msg)\n    print(f"SENT: {t['to']}")\n    sent += 1\n    time.sleep(4)\n\nprint(f"All done — {sent}/{len(targets)} sent")\n