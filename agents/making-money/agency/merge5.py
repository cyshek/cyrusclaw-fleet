import json, os, re
from collections import Counter

NL = chr(10)
rows = json.load(open("harvest5_sitescrape.json"))

# free webmail / hosting / builder domains that are NEVER a business's real inbox for cold
# outreach -> an off-domain email on one of these (or any domain != business domain) is a
# scrape false-positive (footer 'john@smith.com', a yahoo gmail, a host sg-host.com, a
# web-dev agency address). Drop it: better to fall back to 'there'/no-email than mis-send.
FREEMAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
            "icloud.com", "live.com", "msn.com", "comcast.net", "sbcglobal.net",
            "me.com", "mac.com", "protonmail.com", "ymail.com"}
BAD_HOST_FRAG = ("sg-host.com", "wixpress", "sentry", "awesomeservice.com", "smith.com",
                 "example.com", "squarespace", "godaddy", "clovisroofs.com")

def email_domain(e):
    return e.split("@")[-1].lower() if e and "@" in e else ""

def on_domain(email, biz_domain):
    ed = email_domain(email)
    bd = (biz_domain or "").lower()
    if not ed or not bd:
        return False
    # accept exact or subdomain match (mail.acme.com matches acme.com)
    return ed == bd or ed.endswith("." + bd) or bd.endswith("." + ed) or ed == bd.replace("www.", "")

emailable = []
for r in rows:
    site_email = (r.get("site_email") or "").strip()
    edom = email_domain(site_email)
    # REJECT off-domain / freemail / known-bad-host emails -> not a safe cold-outreach target
    if site_email and (
        not on_domain(site_email, r.get("domain")) or
        edom in FREEMAIL or
        any(b in site_email.lower() for b in BAD_HOST_FRAG)
    ):
        r["final_email"] = None
        r["email_source"] = (r.get("email_source") or "") + "|REJECTED-offdomain"
        continue
    email = site_email or None
    r["final_email"] = email
    if not r.get("email_source") and email:
        r["email_source"] = "site"
    if email and r.get("site_hook"):
        emailable.append(r)

# --- inject the recoverable lead: Paschall Plumbing, Heating, and Cooling (Reno, NV) ---
# verified MX on paschallplus.com; batch4 used a typo'd domain (pashallplus.com).
# Personal-looking inbox angela@ -> owner first name "Angela". Intentionally included
# despite Reno not being a "fresh" city: it is a correction of a prior-batch typo.
paschall_dom = "paschallplus.com"
already = {r["domain"] for r in rows}
if paschall_dom not in already:
    emailable.append({
        "name": "Paschall Plumbing, Heating, and Cooling",
        "vertical": "HVAC",
        "metro": "Reno, NV",
        "city": "Reno", "state": "NV",
        "website": "https://www.paschallplus.com/",
        "phone": "7758572300",
        "domain": paschall_dom,
        "reviewCount": None,
        "site_email": "angela@paschallplus.com",
        "final_email": "angela@paschallplus.com",
        "email_source": "site-personal(recovered-lead; verified MX)",
        "owner_first": "Angela",
        "owner_first_source": "recovered-lead",
        "site_hook": "contact form with no instant/auto response",
        "emails_found": ["angela@paschallplus.com"],
    })
    print("INJECTED recoverable lead: angela@paschallplus.com")
else:
    print("Paschall domain already present in harvest; not re-injecting")

json.dump(rows, open("harvest5_merged.json", "w"), ensure_ascii=False, indent=1)
json.dump(emailable, open("harvest5_emailable.json", "w"), ensure_ascii=False, indent=1)

print("TOTAL harvested:", len(rows))
print("EMAILABLE (email + hook):", len(emailable))
print()
print("Emailable by vertical+metro:")
c = Counter((r["vertical"], r["metro"]) for r in emailable)
for k, v in sorted(c.items()):
    print("  ", k, v)
print()
print("Email source breakdown:")
def src_bucket(s):
    s = s or ""
    if s.startswith("site-personal"):
        return "personal-inbox"
    if s.startswith("site-generic"):
        return "generic-inbox"
    return s or "unknown"
cs = Counter(src_bucket(r.get("email_source")) for r in emailable)
for k, v in sorted(cs.items()):
    print("  ", k, v)
print()
print("Owner-name found (pre-safety):", sum(1 for r in emailable if r.get("owner_first")))
print()
print("Hook types:")
def hooktype(h):
    if not h:
        return "none"
    if "review" in h:
        return "review-gap"
    if "says" in h:
        return "slow-SLA"
    return "form-no-instant"
ch = Counter(hooktype(r.get("site_hook")) for r in emailable)
for k, v in sorted(ch.items()):
    print("  ", k, v)
