#!/usr/bin/env python3
"""
Find contact emails for outreach domains, then send personalized emails.
"""

import smtplib
import time
import re
import json
import urllib.request
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"

TARGETS = [
    {"domain": "luxe.salon", "subject": "luxe.salon — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on luxe.salon and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=luxe.salon\n\n— Cyrus"},
    {"domain": "plumbline.com", "subject": "plumbline.com — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on plumbline.com and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=plumbline.com\n\n— Cyrus"},
    {"domain": "hillcrestplumbing.com", "subject": "hillcrestplumbing.com — quick fix for blank preview when shared on social", "body": "Hi — I ran a free audit on hillcrestplumbing.com and the main thing that stood out: when someone shares your site on social media or iMessage, it shows up blank with no preview image or description. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=hillcrestplumbing.com\n\n— Cyrus"},
    {"domain": "bluefrogplumbing.com", "subject": "bluefrogplumbing.com — quick fix for blank preview when shared on social", "body": "Hi — I ran a free audit on bluefrogplumbing.com and the main thing that stood out: when someone shares your site on social media or iMessage, it shows up blank with no preview image or description. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=bluefrogplumbing.com\n\n— Cyrus"},
    {"domain": "deardental.com", "subject": "deardental.com — quick fix for your meta description is blank", "body": "Hi — I ran a free audit on deardental.com and the main thing that stood out: your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=deardental.com\n\n— Cyrus"},
    {"domain": "gentledentalcare.com", "subject": "gentledentalcare.com — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on gentledentalcare.com and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=gentledentalcare.com\n\n— Cyrus"},
    {"domain": "familytreedental.com", "subject": "familytreedental.com — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on familytreedental.com and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=familytreedental.com\n\n— Cyrus"},
    {"domain": "lakesidedentalcare.com", "subject": "lakesidedentalcare.com — quick fix for your main heading is missing", "body": "Hi — I ran a free audit on lakesidedentalcare.com and the main thing that stood out: your main heading (H1) is missing — that's one of the first things Google reads to understand what your page is about. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=lakesidedentalcare.com\n\n— Cyrus"},
    {"domain": "mirrormirrorsalon.com", "subject": "mirrormirrorsalon.com — quick fix for your main heading is missing", "body": "Hi — I ran a free audit on mirrormirrorsalon.com and the main thing that stood out: your main heading (H1) is missing — that's one of the first things Google reads to understand what your page is about. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=mirrormirrorsalon.com\n\n— Cyrus"},
    {"domain": "riverside.plumbing", "subject": "riverside.plumbing — quick fix for your meta description is blank", "body": "Hi — I ran a free audit on riverside.plumbing and the main thing that stood out: your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=riverside.plumbing\n\n— Cyrus"},
    {"domain": "parkerandsons.com", "subject": "parkerandsons.com — quick fix for blank social preview when shared", "body": "Hi — I ran a free audit on parkerandsons.com and the main thing that stood out: when someone shares your site on Facebook or iMessage, it shows up blank — no image, no title, just a raw link. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=parkerandsons.com\n\n— Cyrus"},
    {"domain": "yourcommunitylawfirm.com", "subject": "yourcommunitylawfirm.com — quick fix for slow load speed hurting rankings", "body": "Hi — I ran a free audit on yourcommunitylawfirm.com and the main thing that stood out: your site loads slowly — Google uses page speed as a ranking signal, and slow sites lose to faster competitors. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=yourcommunitylawfirm.com\n\n— Cyrus"},
    {"domain": "hammondlawgroup.com", "subject": "hammondlawgroup.com — quick fix for your meta description is blank", "body": "Hi — I ran a free audit on hammondlawgroup.com and the main thing that stood out: your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=hammondlawgroup.com\n\n— Cyrus"},
    {"domain": "thompsonlawoffice.com", "subject": "thompsonlawoffice.com — quick fix for your meta description is blank", "body": "Hi — I ran a free audit on thompsonlawoffice.com and the main thing that stood out: your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=thompsonlawoffice.com\n\n— Cyrus"},
    {"domain": "oaktreelaw.com", "subject": "oaktreelaw.com — quick fix for images missing alt text", "body": "Hi — I ran a free audit on oaktreelaw.com and the main thing that stood out: your images are missing alt text — that's a basic accessibility and SEO signal Google uses to understand your content. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=oaktreelaw.com\n\n— Cyrus"},
    {"domain": "itsdone.com", "subject": "itsdone.com — quick fix for broken links on your site", "body": "Hi — I ran a free audit on itsdone.com and the main thing that stood out: you have broken links on your site — Google sees those and it signals a neglected, low-quality site. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=itsdone.com\n\n— Cyrus"},
    {"domain": "aaatoday.com", "subject": "aaatoday.com — quick fix for blank preview when shared on social", "body": "Hi — I ran a free audit on aaatoday.com and the main thing that stood out: when someone shares your site on social media or iMessage, it shows up blank with no preview image or description. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=aaatoday.com\n\n— Cyrus"},
    {"domain": "quickfix.repair", "subject": "quickfix.repair — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on quickfix.repair and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=quickfix.repair\n\n— Cyrus"},
    {"domain": "reliable.repair", "subject": "reliable.repair — quick fix for blank social preview when shared", "body": "Hi — I ran a free audit on reliable.repair and the main thing that stood out: when someone shares your site on Facebook or iMessage, it shows up blank — no image, no title, just a raw link. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=reliable.repair\n\n— Cyrus"},
    {"domain": "summit.builders", "subject": "summit.builders — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on summit.builders and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=summit.builders\n\n— Cyrus"},
    {"domain": "heritage.builders", "subject": "heritage.builders — quick fix for site not configured as mobile-friendly", "body": "Hi — I ran a free audit on heritage.builders and the main thing that stood out: your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=heritage.builders\n\n— Cyrus"},
    {"domain": "precision.builders", "subject": "precision.builders — quick fix for your meta description is blank", "body": "Hi — I ran a free audit on precision.builders and the main thing that stood out: your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=precision.builders\n\n— Cyrus"},
    {"domain": "foundations.construction", "subject": "foundations.construction — quick fix for blank social preview when shared", "body": "Hi — I ran a free audit on foundations.construction and the main thing that stood out: when someone shares your site on Facebook or iMessage, it shows up blank — no image, no title, just a raw link. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=foundations.construction\n\n— Cyrus"},
    {"domain": "ledger.cpa", "subject": "ledger.cpa — quick fix for blank social preview when shared", "body": "Hi — I ran a free audit on ledger.cpa and the main thing that stood out: when someone shares your site on Facebook or iMessage, it shows up blank — no image, no title, just a raw link. This is likely costing you rankings and new customers finding you online. Full report (no signup needed): https://sitelume.app/audit/?url=ledger.cpa\n\n— Cyrus"},
]

CTX = ssl.create_default_context()

def scrape_contact_email(domain):
    emails = set()
    urls_to_try = [
        f"https://{domain}",
        f"https://{domain}/contact",
        f"https://{domain}/contact-us",
        f"https://{domain}/about",
        f"http://{domain}",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
    SKIP = ['example.', 'sentry.', 'schema.', 'w3.org', 'wpcf7', 'yourname',
            'youremail', 'email@', '@email', 'noreply', 'no-reply', 'wordpress',
            'jquery', 'googleapis', 'cloudflare', 'gmpg.org']

    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8, context=CTX) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                found = email_re.findall(html)
                for e in found:
                    e = e.lower()
                    if any(s in e for s in SKIP):
                        continue
                    if e.endswith(('.js', '.css', '.png', '.jpg', '.gif')):
                        continue
                    emails.add(e)
            if emails:
                break
        except Exception:
            continue

    domain_root = domain.split('.')[0]
    same_domain = [e for e in emails if domain.replace('www.', '') in e]
    if same_domain:
        return sorted(same_domain)[0]
    if emails:
        return sorted(emails)[0]
    return None

def send_email(to_addr, subject, body):
    msg = MIMEMultipart()
    msg['From'] = GMAIL
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL, APP_PASS)
        server.send_message(msg)

def main():
    results = []
    sent = 0
    skipped = 0

    print(f"{'Domain':<30} {'Email Found':<40} {'Status'}")
    print("-" * 85)

    for t in TARGETS:
        domain = t['domain']
        print(f"{domain:<30} {'scraping...':<40}", end='\r')
        email = scrape_contact_email(domain)

        if not email:
            print(f"{domain:<30} {'— not found':<40} SKIP")
            results.append({"domain": domain, "email": None, "status": "no_email_found"})
            skipped += 1
            continue

        try:
            send_email(email, t['subject'], t['body'])
            print(f"{domain:<30} {email:<40} SENT ✓")
            results.append({"domain": domain, "email": email, "status": "sent"})
            sent += 1
            time.sleep(4)
        except Exception as e:
            print(f"{domain:<30} {email:<40} FAIL: {e}")
            results.append({"domain": domain, "email": email, "status": f"failed: {e}"})

    print(f"\nSent: {sent} | Skipped (no email): {skipped} | Total: {len(TARGETS)}")

    out = Path("/home/azureuser/.openclaw/agents/making-money/workspace/outreach/results.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"Results saved to {out}")

if __name__ == "__main__":
    main()
