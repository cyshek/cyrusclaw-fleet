import smtplib
import ssl
from email.mime.text import MIMEText

smtp_user = "cyshekari@gmail.com"
smtp_pass = "yjse lddd mhan gbpe"
seed_addr = "ft-dce405-2357cbc6@ft.glockdb.com"

subject = "3 reviews for Simons Hall Johnston?"

body_lines = [
    "Hi there,",
    "",
    "You've clearly handled serious cases -- but Simons Hall Johnston only shows 3 Google reviews. For a firm like yours that's leaving a lot on the table, because people pick a firm almost entirely on reviews and how fast someone responds.",
    "",
    "I set up two things for firms like yours: every new inquiry gets a response within 60 seconds (day or night -- that's when people reach out), and every client whose case resolves gets an automatic, tactful review request. Firms usually go from a couple dozen reviews to triple digits.",
    "",
    "If it's worth a look, grab whatever 15-min slot works for you here: https://cal.com/cyshek -- I'll walk you through exactly what it'd look like for Simons Hall Johnston (no pressure, no hard sell).",
    "",
    "-- Cyrus"
]
body = chr(10).join(body_lines)

msg = MIMEText(body, 'plain', 'utf-8')
msg['Subject'] = subject
msg['From'] = smtp_user
msg['To'] = seed_addr

context = ssl.create_default_context()
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [seed_addr], msg.as_string())
    print("EMAIL SENT SUCCESSFULLY to", seed_addr)
except Exception as e:\n    print("ERROR:", e)
