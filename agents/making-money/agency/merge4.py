import json, re

# Hunter results we salvaged from the partial run log (domain -> email, conf)
hunter = {
    "shjnevada.com": ("ttribble@shjnevada.com", 99),
    "nvlitigators.com": ("info@nvlitigators.com", 79),
    "renolawfirm.com": ("christi@renolawfirm.com", 99),
    "jessekalterlaw.com": ("jesse@jessekalterlaw.com", 84),
    "stephenosbornelaw.com": ("stephen@stephenosbornelaw.com", 92),
    "friedmanthroop.com": ("jthroop@friedmanthroop.com", 85),
    "puenteslaw.com": ("roberto@puenteslaw.com", 94),
    "jbplegal.com": ("fhellard@jbplegal.com", 99),
    "colawfirm.com": ("dara@colawfirm.com", 99),
    "steveray.lawyer": ("steve@steveray.lawyer", 94),
    "hsdlawfirm.com": ("alayna@hsdlawfirm.com", 99),
    "davidamestasllc.com": ("david@davidamestasllc.com", 67),
    "wicklaw.com": ("kward@wicklaw.com", 94),
    "machesterlaw.com": ("info@machesterlaw.com", 10),
    "cummingsandpetronelaw.com": ("joe@cummingsandpetronelaw.com", 69),
    "oreslaw.com": ("nick@oreslaw.com", 70),
}

rows = json.load(open("harvest4_sitescrape.json"))
emailable = []
for r in rows:
    dom = r["domain"]
    h = hunter.get(dom)
    site_email = r.get("site_email")
    # choose email: prefer Hunter (verified) unless its confidence is junk (<30) and a site email exists
    email = None
    source = None
    if h and h[1] >= 30:
        email, source = h[0], f"hunter(conf={h[1]})"
    elif site_email:
        email, source = site_email, "site"
    elif h:  # low-conf hunter as last resort
        email, source = h[0], f"hunter(conf={h[1]})"
    r["final_email"] = email
    r["email_source"] = source
    if email and r.get("site_hook"):
        emailable.append(r)

json.dump(rows, open("harvest4_merged.json", "w"), ensure_ascii=False, indent=1)
json.dump(emailable, open("harvest4_emailable.json", "w"), ensure_ascii=False, indent=1)

from collections import Counter
print("TOTAL harvested:", len(rows))
print("EMAILABLE (email + hook):", len(emailable))
print()
print("Emailable by vertical+metro:")
c = Counter((r["vertical"], r["metro"]) for r in emailable)
for k, v in sorted(c.items()):
    print("  ", k, v)
print()
print("Email source breakdown:")
cs = Counter(("hunter" if (r["email_source"] or "").startswith("hunter") else "site") for r in emailable)
for k, v in sorted(cs.items()):
    print("  ", k, v)
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
