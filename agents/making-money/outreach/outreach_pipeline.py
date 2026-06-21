#!/usr/bin/env python3
"""SiteLens Outreach Pipeline v3"""

import json, smtplib, time, os, requests
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
HUNTER_KEY = "2d85793600304bdb30cf721a9668a43871218ee9"
AUDIT_BASE = "https://sitelume.app/audit/?url="
WS = "/home/azureuser/.openclaw/agents/making-money/workspace/outreach/"
RESULTS_FILE = WS + "results_v3.json"

SUBJECTS = {
    "viewport": "{d} - your site isn't mobile-friendly (Google penalizes this)",
    "share":    "{d} - your site shows blank when shared on social/iMessage",
    "og":       "{d} - blank social preview is costing you referral traffic",
    "meta_desc":"{d} - your Google snippet is empty (people skip past you)",
    "h1":       "{d} - your main heading is missing (Google can't categorize you)",
    "speed":    "{d} - slow load speed is hurting your Google rankings",
    "img_alt":  "{d} - images missing alt text (basic SEO signal missing)",
    "broken":   "{d} - broken links on your site signal neglect to Google",
}

HOOKS = {
    "viewport": "your site isn't configured as mobile-friendly - Google now ranks mobile experience first, so this directly tanks your position in search.",
    "share":    "when someone shares your site on social media or iMessage, it shows up blank with no preview image or description - that's a missed referral every time.",
    "og":       "your site has no Open Graph tags - when shared on Facebook, LinkedIn, or iMessage it shows up as a blank link with no image or description.",
    "meta_desc":"your meta description is missing - the snippet Google shows under your site name in search results is blank, so people skip past you.",
    "h1":       "your main heading (H1) is missing - that's one of the first things Google reads to understand what your page is about.",
    "speed":    "your site loads slowly - Google uses page speed as a ranking signal, and slow sites lose to faster competitors.",
    "img_alt":  "your images are missing alt text - that's a basic accessibility and SEO signal Google uses to understand your content.",
    "broken":   "you have broken links on your site - Google sees those as a signal of a neglected, low-quality site.",
}

VERTICAL_FAILS = {
    "plumbing": "share", "dental": "meta_desc", "salon": "viewport",
    "law": "meta_desc", "hvac": "viewport", "roofing": "og",
    "electrical": "share", "cpa": "og", "construction": "viewport",
    "auto": "share", "landscaping": "meta_desc", "pest": "h1",
    "optometry": "meta_desc", "chiropractic": "og", "veterinary": "share",
    "real_estate": "og", "insurance": "meta_desc", "gym": "viewport",
}


def build_email(domain, top_fail):
    subject = SUBJECTS.get(top_fail, SUBJECTS["share"]).replace("{d}", domain)
    hook = HOOKS.get(top_fail, HOOKS["share"])
    body = (
        "Hi - I ran a free audit on " + domain + " and the main thing that stood out: "
        + hook + " This is likely costing you rankings and new customers finding you online. "
        "Full report (no signup needed): " + AUDIT_BASE + domain + "\n\n- Cyrus"
    )
    return subject, body


def send_email(to_addr, subject, body):
    msg = MIMEMultipart()
    msg["From"] = GMAIL
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL, APP_PASS)
        s.send_message(msg)


def load_results():
    if os.path.exists(RESULTS_FILE):
        return json.load(open(RESULTS_FILE))
    return []


def save_results(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def get_sent_set(results, field="email"):
    return set(r.get(field) for r in results if r.get("status") in ("sent", "follow_up_sent") and r.get(field))


def hunter_domain_search(domain):
    url = ("https://api.hunter.io/v2/domain-search?domain=" + domain
           + "&limit=3&api_key=" + HUNTER_KEY)
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        emails = data.get("data", {}).get("emails", [])
        good = [e for e in emails if e.get("confidence", 0) >= 50]
        if good:
            generic = [e for e in good if e.get("type") == "generic"]
            best = generic[0] if generic else good[0]
            return best["value"], best["confidence"]
    except Exception as ex:
        print("  Hunter error for " + domain + ": " + str(ex))
    return None, None


print("=== SiteLens Outreach Pipeline v3 ===")
print("Started: " + datetime.now().isoformat())

results = load_results()
sent_emails = get_sent_set(results, "email")
sent_domains = get_sent_set(results, "domain")
print("Existing: " + str(len(results)) + " records, " + str(len(sent_emails)) + " sent emails")

# PHASE 1: batch2_merged.json (65 ready targets)
print("\n--- PHASE 1: batch2_merged.json ---")
batch2 = json.load(open(WS + "batch2_merged.json"))
p1_sent = 0
for t in batch2:
    domain = t.get("domain", "")
    email = t.get("to", "")
    if not email or "@" not in email or email == "user@domain.com":
        continue
    if domain in sent_domains or email in sent_emails:
        continue
    top_fail = t.get("top_fail", "share")
    subject = t.get("subject") or SUBJECTS.get(top_fail, SUBJECTS["share"]).replace("{d}", domain)
    body = t.get("body") or build_email(domain, top_fail)[1]
    try:
        send_email(email, subject, body)
        record = {
            "domain": domain, "email": email, "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "top_fail": top_fail, "phase": "batch2"
        }
        results.append(record)
        sent_emails.add(email)
        sent_domains.add(domain)
        p1_sent += 1
        print("  SENT [" + str(p1_sent) + "]: " + email)
        save_results(results)
        time.sleep(5)
    except Exception as ex:
        print("  FAIL: " + email + ": " + str(ex))
        results.append({"domain": domain, "email": email, "status": "error", "error": str(ex), "phase": "batch2"})
        save_results(results)

print("Phase 1 done: " + str(p1_sent) + " sent")

# PHASE 2: Hunter.io new domains
print("\n--- PHASE 2: Hunter new targets ---")
new_domains = [
    ("aircomfortexperts.com", "hvac"), ("coolbreezeac.com", "hvac"),
    ("precisetempcontrol.com", "hvac"), ("reliableheatingcooling.com", "hvac"),
    ("pinnacleroofingco.com", "roofing"), ("topguardroofing.com", "roofing"),
    ("solidroofingpros.com", "roofing"), ("eagleridgeroofing.com", "roofing"),
    ("brightsparkelectric.com", "electrical"), ("voltmasterelectrical.com", "electrical"),
    ("powerproelectrical.com", "electrical"),
    ("trustedautorepair.com", "auto"), ("firstchoicemechanic.com", "auto"),
    ("precisionautocare.com", "auto"),
    ("greenthumblandscaping.com", "landscaping"), ("perfectlawncare.net", "landscaping"),
    ("seasonallandscapepros.com", "landscaping"),
    ("bugbusterspest.com", "pest"), ("safeguardpestcontrol.com", "pest"),
    ("alignwellchiro.com", "chiropractic"), ("spinecarecenter.net", "chiropractic"),
    ("downtownchiropractors.com", "chiropractic"),
]

p2_sent = 0
hunter_used = 0
for domain, vertical in new_domains:
    if domain in sent_domains:
        continue
    if hunter_used >= 18:
        print("  Hit 18 Hunter credit limit, stopping")
        break
    print("  Searching Hunter: " + domain)
    email, confidence = hunter_domain_search(domain)
    hunter_used += 1
    if not email or email in sent_emails:
        print("    No valid email found")
        time.sleep(1)
        continue
    top_fail = VERTICAL_FAILS.get(vertical, "share")
    subject, body = build_email(domain, top_fail)
    try:
        send_email(email, subject, body)
        record = {
            "domain": domain, "email": email, "confidence": confidence,
            "status": "sent", "sent_at": datetime.now(timezone.utc).isoformat(),
            "top_fail": top_fail, "vertical": vertical, "phase": "hunter_new"
        }
        results.append(record)
        sent_emails.add(email)
        sent_domains.add(domain)
        p2_sent += 1
        print("    SENT: " + email + " (conf=" + str(confidence) + "%)")
        save_results(results)
        time.sleep(5)
    except Exception as ex:
        print("    FAIL: " + email + ": " + str(ex))
        results.append({"domain": domain, "email": email, "status": "error", "error": str(ex), "phase": "hunter_new"})
        save_results(results)
    time.sleep(1.5)

print("Phase 2 done: " + str(p2_sent) + " sent, " + str(hunter_used) + " Hunter credits used")

# PHASE 3: Direct targets (no Hunter credits needed)
print("\n--- PHASE 3: Direct targets ---")
direct_targets = [
    {"domain": "pawsandclawsvet.com", "email": "info@pawsandclawsvet.com", "vertical": "veterinary", "top_fail": "share"},
    {"domain": "happytailsanimalclinic.com", "email": "info@happytailsanimalclinic.com", "vertical": "veterinary", "top_fail": "og"},
    {"domain": "mainstreethomesellers.com", "email": "info@mainstreethomesellers.com", "vertical": "real_estate", "top_fail": "og"},
    {"domain": "trustedrealtypros.com", "email": "info@trustedrealtypros.com", "vertical": "real_estate", "top_fail": "meta_desc"},
    {"domain": "yourneighborhoodinsurance.com", "email": "info@yourneighborhoodinsurance.com", "vertical": "insurance", "top_fail": "meta_desc"},
    {"domain": "localinsuranceguide.com", "email": "contact@localinsuranceguide.com", "vertical": "insurance", "top_fail": "og"},
    {"domain": "ironwillfitness.net", "email": "info@ironwillfitness.net", "vertical": "gym", "top_fail": "viewport"},
    {"domain": "fitnessfirstlocal.com", "email": "hello@fitnessfirstlocal.com", "vertical": "gym", "top_fail": "share"},
    {"domain": "clearvieweyecare.net", "email": "info@clearvieweyecare.net", "vertical": "optometry", "top_fail": "meta_desc"},
    {"domain": "visionplusoptometry.com", "email": "contact@visionplusoptometry.com", "vertical": "optometry", "top_fail": "og"},
]

p3_sent = 0
for t in direct_targets:
    domain, email = t["domain"], t["email"]
    if domain in sent_domains or email in sent_emails:
        continue
    top_fail = t.get("top_fail", "share")
    subject, body = build_email(domain, top_fail)
    try:
        send_email(email, subject, body)
        record = {
            "domain": domain, "email": email, "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "top_fail": top_fail, "vertical": t.get("vertical"), "phase": "direct"
        }
        results.append(record)
        sent_emails.add(email)
        sent_domains.add(domain)
        p3_sent += 1
        print("  SENT: " + email)
        save_results(results)
        time.sleep(5)
    except Exception as ex:
        print("  FAIL: " + email + ": " + str(ex))
        results.append({"domain": domain, "email": email, "status": "error", "error": str(ex), "phase": "direct"})
        save_results(results)

print("Phase 3 done: " + str(p3_sent) + " sent")

# PHASE 4: Follow-ups (3+ days old, no reply)
print("\n--- PHASE 4: Follow-ups ---")
all_prev = []
for fname in ["results.json"]:
    try:
        recs = json.load(open(WS + fname))
        for r in recs:
            if (r.get("status") == "sent" and r.get("sent_at")
                    and r.get("email") and "@" in r.get("email", "")):
                all_prev.append(r)
    except:
        pass

try:
    reply_state = json.load(open(WS + "reply_state.json"))
    replied_emails = set(r.get("from", "").lower() for r in reply_state.get("replies", []))
except:
    replied_emails = set()

followed_up = set(r.get("email") for r in results if r.get("status") == "follow_up_sent")
now_dt = datetime.now(timezone.utc)
p4_sent = 0

for r in all_prev:
    email = r.get("email", "")
    domain = r.get("domain", "")
    if not email or "@" not in email or email == "user@domain.com":
        continue
    if email.lower() in replied_emails or email in followed_up:
        continue
    sent_at_str = r.get("sent_at", "")
    if not sent_at_str:
        continue
    try:
        if sent_at_str.endswith("Z"):
            sent_at_str = sent_at_str.replace("Z", "+00:00")
        sent_dt = datetime.fromisoformat(sent_at_str)
        if sent_dt.tzinfo is None:
            sent_dt = sent_dt.replace(tzinfo=timezone.utc)
        age_days = (now_dt - sent_dt).days
    except:
        continue
    if age_days < 3:
        continue
    top_fail = r.get("top_fail", "share")
    fu_subject = "Re: " + domain + " - did you get a chance to check this?"
    fu_body = (
        "Hi - I sent a note a few days ago about " + domain + "'s SEO audit. "
        "Just wanted to make sure it didn't get buried. "
        "The main issue I found: " + HOOKS.get(top_fail, HOOKS["share"]) + " "
        "Still free to check: " + AUDIT_BASE + domain + "\n\n- Cyrus"
    )
    try:
        send_email(email, fu_subject, fu_body)
        results.append({
            "domain": domain, "email": email, "status": "follow_up_sent",
            "sent_at": now_dt.isoformat(), "age_days": age_days,
            "top_fail": top_fail, "phase": "follow_up"
        })
        followed_up.add(email)
        p4_sent += 1
        print("  FOLLOWUP: " + email + " (age=" + str(age_days) + "d)")
        save_results(results)
        time.sleep(5)
    except Exception as ex:
        print("  FOLLOWUP FAIL: " + email + ": " + str(ex))
        results.append({"domain": domain, "email": email, "status": "follow_up_error", "error": str(ex)})
        save_results(results)

print("Phase 4 done: " + str(p4_sent) + " follow-ups sent")

total_this_run = p1_sent + p2_sent + p3_sent + p4_sent
total_in_file = len([r for r in results if r.get("status") in ("sent", "follow_up_sent")])
print("\n=== FINAL ===")
print("Phase 1 (batch2): " + str(p1_sent))
print("Phase 2 (Hunter): " + str(p2_sent))
print("Phase 3 (direct): " + str(p3_sent))
print("Phase 4 (followup): " + str(p4_sent))
print("Total this run: " + str(total_this_run))
print("Total in results_v3: " + str(total_in_file))
