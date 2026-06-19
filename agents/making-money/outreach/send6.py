import smtplib, time, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"

with open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/send6_data.json') as f:\n    targets = json.load(f)\n\nfor t in targets:
    msg = MIMEMultipart()
    msg['From'] = GMAIL
    msg['To'] = t['to']
    msg['Subject'] = t['subject']
    msg.attach(MIMEText(t['body'], 'plain'))\n    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:\n        s.login(GMAIL, APP_PASS)\n        s.send_message(msg)\n    print(f"SENT: {t['to']}")
    time.sleep(4)

print("All done")
