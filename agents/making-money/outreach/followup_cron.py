#!/usr/bin/env python3
import json, time, smtplib, imaplib
import email as email_module
from email.mime.text import MIMEText
from email.header import decode_header
from datetime import datetime, timezone, timedelta
from pathlib import Path

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
RESULTS_FILE = "/home/azureuser/.openclaw/agents/making-money/workspace/outreach/results.json"
LOG_FILE = "/home/azureuser/.openclaw/agents/making-money/workspace/outreach/followup_log.json"
NL = chr(10)


def decode_str(s):
    if s is None: return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def check_replies():
    replied = set()
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL, APP_PASS)
        mail.select("INBOX")
        _, data = mail.search(None, "ALL")
        uids = data[0].split()[-200:]
        for uid in uids:
            _, msg_data = mail.fetch(uid, "(RFC822.HEADER)")
            msg = email_module.message_from_bytes(msg_data[0][1])
            from_addr = decode_str(msg.get("From", ""))
            if "@" in from_addr:
                from_domain = from_addr.split("@")[-1].rstrip(">").strip().lower()
                replied.add(from_domain)
        mail.logout()
    except Exception as e:
        print(f"IMAP error: {e}")
    return replied


def load_results():
    p = Path(RESULTS_FILE)
    return json.loads(p.read_text()) if p.exists() else []


def load_log():
    p = Path(LOG_FILE)
    return json.loads(p.read_text()) if p.exists() else {"followups_sent": []}


def save_log(data):
    Path(LOG_FILE).write_text(json.dumps(data, indent=2))


def send_followup(to_addr, domain, audit_url):
    body_parts = [
        f"Hi again — just wanted to make sure my note did not get buried. ",
        f"I ran a free audit on {domain} and found a quick fix that could help your Google rankings. ",
        f"No signup needed: {audit_url} — takes 30 seconds to review.",
        "",
        "— Cyrus",
    ]
    body = NL.join(body_parts)
    msg = MIMEText(body, "plain")
    msg["Subject"] = f"Re: {domain} SEO audit — just checking in"
    msg["From"] = GMAIL
    msg["To"] = to_addr
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.ehlo()
        s.starttls()
        s.login(GMAIL, APP_PASS)
        s.sendmail(GMAIL, [to_addr], msg.as_string())


def main():
    results = load_results()
    followup_log = load_log()
    already_followed = {e["domain"] for e in followup_log["followups_sent"]}

    replied_domains = check_replies()
    print(f"Domains with inbox replies: {len(replied_domains)}")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=3)
    sent_count = 0

    for r in results:
        if r.get("status") != "sent": continue
        domain = r["domain"]
        email_addr = r.get("email")
        sent_at_str = r.get("sent_at")
        if not email_addr or not sent_at_str: continue
        if domain in already_followed: continue
        if domain in replied_domains: continue
        try:
            sent_at = datetime.fromisoformat(sent_at_str)
        except Exception:
            continue
        if sent_at >= cutoff: continue

        audit_url = f"https://sitelume.app/audit/?url={domain}"
        try:
            send_followup(email_addr, domain, audit_url)
            print(f"  FOLLOWUP SENT: {domain} -> {email_addr}")
            followup_log["followups_sent"].append({
                "domain": domain, "email": email_addr,
                "sent_at": now.isoformat(),
            })
            already_followed.add(domain)
            sent_count += 1
            save_log(followup_log)
            time.sleep(8)
        except Exception as e:
            print(f"  FOLLOWUP ERROR: {domain} -> {e}")
            time.sleep(3)

    print(f"Follow-up run complete. Sent: {sent_count}")
    return sent_count


if __name__ == "__main__":
    main()