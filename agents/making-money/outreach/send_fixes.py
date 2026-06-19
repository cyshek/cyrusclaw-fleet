import json, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"

SUBJECTS = {
    "viewport": "{d} — quick fix for site not configured as mobile-friendly",
    "share": "{d} — quick fix for blank preview when shared on social",
    "og": "{d} — quick fix for blank preview when shared on social",
    "meta_desc": "{d} — quick fix for missing meta description",
    "h1": "{d} — quick fix for missing main heading",
    "speed": "{d} — quick fix for slow load speed hurting rankings",
    "img_alt": "{d} — quick fix for images missing alt text",
    "broken": "{d} — quick fix for broken links on your site",
}

HOOKS = {
    "viewport": "your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position.",
    "share": "when someone shares your site on social media or iMessage, it shows up blank with no preview image or description.",
    "og": "when someone shares your site on social media or iMessage, it shows up blank with no preview image or description.",
    "meta_desc": "your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you.",
    "h1": "your main heading (H1) is missing — that's one of the first things Google reads to understand what your page is about.",
    "speed": "your site loads slowly — Google uses page speed as a ranking signal, and slow sites lose to faster competitors.",
    "img_alt": "your images are missing alt text — that's a basic accessibility and SEO signal Google uses to understand your content.",
    "broken": "you have broken links on your site — Google sees those and it signals a neglected, low-quality site.",
}

with open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/batch2_merged.json') as f:
    targets = json.load(f)

bad = [t for t in targets if 'subject' not in t]
print(f"Fixing and sending {len(bad)} entries")

sent = 0
for t in bad:
    d = t['domain']
    tf = t.get('top_fail', 'share')
    hook = HOOKS.get(tf, HOOKS['share'])
    subject = SUBJECTS.get(tf, SUBJECTS['share']).format(d=d)
    
    body = ("Hi — I ran a free audit on " + d + " and the main thing that stood out: " + hook + " This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=" + d + "\n\n— Cyrus")
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL
        msg['To'] = t['to']
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL, APP_PASS)
            s.send_message(msg)
        print("SENT: " + t['to'])
        sent += 1
        time.sleep(4)
    except Exception as e:
        print("FAIL: " + t['to'] + " - " + str(e))

print("Done - " + str(sent) + "/" + str(len(bad)) + " sent")
