#!/usr/bin/env python3
"""Build batch4_payload.json from harvest4_emailable.json.

Mirrors make_batch2.py's voice + shape: per-vertical personalized subject/body, self-serve
Cal.com booking CTA, and the SAME QC rules:
  - singular/plural reviews ("1 review" not "1 reviews")
  - review-GAP angle only when reviewCount <= 12 (else neutral intake angle; never insult a
    firm with lots of reviews)
  - clean salutations: real first names only, else "there" (no "Hi Attorney,"/business words)
  - booking link CTA in every body
Output row shape matches send_batch2.py: {name, vertical, city_state, website, phone, to,
subject, body, form_only}.  NO SENDING.
"""
import json, re, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "harvest4_emailable.json")
OUT = os.path.join(HERE, "batch4_payload.json")
BOOK = "https://cal.com/cyshek"
TRADE = {"HVAC": "HVAC", "Roofing": "roofing"}

def first_name(email, business_name=""):
    if not email or "@" not in email:
        return "there"
    local, domain = email.split("@", 1)
    local = local.lower()
    domain_stem = domain.split(".")[0].lower()
    hard_block = {"sdykstra", "amlabonne", "officecrew", "betterskin", "farrelllaw",
                  "info", "office", "admin", "booking", "contact", "hello", "team",
                  "reception", "frontdesk", "appointments", "intake", "justice",
                  "support", "sales", "billing", "help", "mail", "service", "attorney",
                  "attorneys", "lawyer", "law", "lawfirm", "legal", "firm", "clinic",
                  "spa", "medspa", "care", "scheduling", "schedule", "newpatient",
                  "youremail", "yourname", "email", "name", "company", "business"}
    if local in hard_block:
        return "there"
    if re.search(r"\d$", local):
        return "there"
    cand = re.split(r"[._\-0-9]", local)[0]
    if not cand or not cand.isalpha() or not (2 < len(cand) < 12):
        return "there"
    if cand in hard_block:
        return "there"
    # reject first-initial + surname patterns (ttribble, jthroop, fhellard, kward):
    # a local with NO separator that is one leading consonant followed by 4+ letters and
    # is NOT itself a common short name -> almost always initial+lastname.
    if not re.search(r"[._\-]", local) and len(local) >= 5 and local[0] not in "aeiou" \
            and local == cand:
        # treat as initial+surname unless it's a known plausible first name
        known_first = {"chris", "craig", "brian", "brent", "grant", "shane", "steve",
                       "frank", "glenn", "wayne", "scott", "trent", "blake", "bruce",
                       "david", "derek", "keith", "kevin", "kyle", "mark", "nick",
                       "paul", "ryan", "sean", "todd", "tyler", "chad", "drew"}
        if local not in known_first:
            return "there"
    # reject long single-token locals that are almost certainly a surname (impallari, etc.)
    if not re.search(r"[._\-]", local) and len(local) >= 7 and local == cand:
        known_first_long = {"michael", "matthew", "jennifer", "jessica", "william",
                            "charles", "anthony", "patrick", "douglas", "raymond",
                            "timothy", "gregory", "jeffrey", "stephen", "andrew",
                            "nicholas", "jonathan", "benjamin", "samuel", "katherine",
                            "elizabeth", "christopher", "alexander", "nathaniel"}
        if local not in known_first_long:
            return "there"
    if cand == domain_stem or (len(cand) >= 5 and cand in domain_stem):
        return "there"
    biz_words = ("law", "legal", "firm", "heating", "cooling", "hvac", "roof", "plumb",
                 "spa", "clinic", "dental", "dent", "medi", "crew", "office", "team",
                 "group", "associates", "construction", "aesthetic", "skin", "injury",
                 "divorce")
    if any(bw in local for bw in biz_words):
        return "there"
    bn = re.sub(r"[^a-z]", "", (business_name or "").lower())
    if cand in bn and len(cand) >= 6:
        return "there"
    return cand.capitalize()

def poss(name):
    """Possessive of a business name: 'Sunworks' (ends in s) vs 'Acme's'."""
    return name + "'" if name.rstrip().endswith(("s", "S")) else name + "'s"

# emails to DROP outright (placeholders / wrong-domain scrape false-positives)
EMAIL_BLOCKLIST = {
    "youremail@yourbusiness.com", "hello@mail.com", "rob@gafs.com", "eben@eyebytes.com",
}
JUNK_EMAIL_DOMAINS = {"mail.com", "yourbusiness.com", "example.com", "gafs.com", "eyebytes.com"}

def review_count(hook):
    if not hook:
        return None
    m = re.search(r"only\s+(\d+)\s+Google\s+review", hook)
    return int(m.group(1)) if m else None

def plural(n):
    return "review" if int(n) == 1 else "reviews"

def sla_quote(hook):
    if not hook:
        return None
    m = re.search(r"site says '([^']+)'", hook)
    return m.group(1).strip() if m else None

def sla_says(sla):
    """Turn a raw captured SLA fragment into a grammatical clause after 'site ...'.
    Handles broken fragments like 'get back to you as soon' and bare time windows."""
    s = sla.strip().lower()
    # broken/awkward 'get back to you as soon' -> complete it
    if s in ("get back to you as soon", "get back to you soon", "get back to you as soon as"):
        return "says they'll get back to you as soon as they can"
    if s in ("get back to you shortly",):
        return "says they'll get back to you shortly"
    if re.match(r"^(get back|reply|respond|contact)", s):
        return "says " + sla.strip()
    # bare time windows -> 'promises a response within X'
    if re.match(r"^(within|in|under)\b", s):
        return "promises a response " + sla.strip()
    if re.match(r"^(one|two|three|\d|\d+\s*[-\u2013])", s):
        return "promises a response within " + sla.strip()
    # fallback: quote it plainly
    return "says '" + sla.strip() + "'"

def cta(name):
    return (f"If it's worth a look, grab whatever 15-min slot works for you here: {BOOK} "
            f"— I'll walk you through exactly what it'd look like for {name} (no pressure, no hard sell).")

def draft(r):
    v = r["vertical"]; name = r["name"]
    city = (r.get("metro") or r.get("city") or "").split(",")[0].strip()
    email = r["final_email"]; hook = r.get("site_hook")
    fn = first_name(email, name)
    rc = review_count(hook)          # already guaranteed <=12 by the scraper's hook rule
    sla = sla_quote(hook)
    call = cta(name)

    if v in ("HVAC", "Roofing"):
        trade = TRADE[v]
        if rc is not None:
            subj = f"{rc} {plural(rc)} for {name}?"
            body = (
                f"Hi {fn},\n\n"
                f"{name} does great work but only has {rc} Google {plural(rc)} — and in {trade}, "
                f"reviews are basically the whole ballgame for getting found.\n\n"
                f"I build a simple system that (1) texts every new lead back in under 60 seconds so "
                f"you stop losing them to whoever answers first, and (2) automatically asks every "
                f"happy customer for a review after the job — most shops 3-5x their review count in "
                f"a few months.\n\n{call}\n\n— Cyrus"
            )
        elif sla:
            subj = f"quick one about {city} leads" if city else "a quick one about your leads"
            says = sla_says(sla)
            body = (
                f"Hi {fn},\n\n"
                f"Saw {poss(name)} site {says}. Not a knock — almost every {trade} shop does the same. "
                f"The problem is the homeowner who fills that form usually messages 3 contractors and "
                f"books whoever answers first (~78% go with the first responder).\n\n"
                f"I set up a system that texts every new lead back within 60 seconds, 24/7 — answers "
                f"their question and books them — then automatically asks happy customers for a Google "
                f"review after the job.\n\n{call}\n\n— Cyrus"
            )
        else:
            subj = f"quick one about {city} leads" if city else "a quick one about your leads"
            body = (
                f"Hi {fn},\n\n"
                f"Saw {poss(name)} site has a contact form but no instant response — a homeowner who fills "
                f"it out usually messages a few {trade} shops and books whoever answers first "
                f"(~78% go with the first responder).\n\n"
                f"I set up a system that texts every new lead back within 60 seconds, 24/7 — answers "
                f"their question and books them — then automatically asks happy customers for a Google "
                f"review after the job.\n\n{call}\n\n— Cyrus"
            )
    elif v in ("Personal injury law", "Family law"):
        if rc is not None:
            subj = f"{rc} {plural(rc)} for {name}?"
            body = (
                f"Hi {fn},\n\n"
                f"You've clearly handled serious cases — but {name} only shows {rc} Google "
                f"{plural(rc)}. For a firm like yours that's leaving a lot on the table, because "
                f"people pick a firm almost entirely on reviews and how fast someone responds.\n\n"
                f"I set up two things for firms like yours: every new inquiry gets a response within "
                f"60 seconds (day or night — that's when people reach out), and every client whose "
                f"case resolves gets an automatic, tactful review request. Firms usually go from a "
                f"couple dozen reviews to triple digits.\n\n{call}\n\n— Cyrus"
            )
        else:
            subj = "a quick thought on your intake"
            body = (
                f"Hi {fn},\n\n"
                f"Saw {poss(name)} contact form has no instant response — someone reaching out at 9pm "
                f"waits until business hours, and a lot of them call the next firm instead.\n\n"
                f"I build a system that responds to every inquiry within 60 seconds, 24/7, qualifies "
                f"them, and gets them scheduled — plus it automatically asks resolved clients for a "
                f"Google review.\n\n{call}\n\n— Cyrus"
            )
    else:  # Med spa / other
        subj = "the leads who don't book online"
        body = (
            f"Hi {fn},\n\n"
            f"{poss(name)} booking page is great for people ready to book — but the leads who call, DM, "
            f"or fill the form with a question (and don't book themselves) are the ones that quietly "
            f"slip away when no one replies fast.\n\n"
            f"I set up a system that texts those leads back within 60 seconds, 24/7 — answers them "
            f"and gets them booked — and automatically asks clients for a review after their visit. "
            f"It basically recovers the inquiries you're already paying to generate.\n\n{call}\n\n— Cyrus"
        )

    return {
        "name": name, "vertical": v, "city_state": r.get("metro", ""),
        "website": r.get("website", ""), "phone": r.get("phone", ""),
        "to": email, "subject": subj, "body": body, "form_only": False,
        "email_source": r.get("email_source"), "review_count_listing": r.get("reviewCount"),
    }

def main():
    rows = json.load(open(SRC))
    # filter out junk/placeholder/wrong-domain emails before drafting
    kept, dropped = [], []
    for r in rows:
        em = (r.get("final_email") or "").lower().strip()
        edom = em.split("@")[1] if "@" in em else ""
        if (not em) or ("@" not in em) or em in EMAIL_BLOCKLIST or edom in JUNK_EMAIL_DOMAINS:
            dropped.append((r["name"], em or "(none)"))
            continue
        kept.append(r)
    payload = [draft(r) for r in kept]
    json.dump(payload, open(OUT, "w"), ensure_ascii=False, indent=2)
    c = Counter(p["vertical"] for p in payload)
    print(f"EMAILABLE source rows: {len(rows)}")
    print(f"dropped (junk/placeholder/wrong-domain email): {len(dropped)} -> {dropped}")
    print(f"batch4 drafted: {len(payload)} -> {OUT}")
    for v, n in sorted(c.items()):
        print(f"   {v}: {n}")

if __name__ == "__main__":
    main()
