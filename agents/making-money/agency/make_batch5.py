#!/usr/bin/env python3
"""Build batch5_payload.json from harvest5_emailable.json — the PERSONALIZATION-FIRST batch.

Changes vs make_batch4:
  * GREETING uses a scraped OWNER first name (owner_first) when present + safe, else "there".
  * SOFTER first-touch CTA: a reply ask ("Want me to send over a 2-min demo... just reply"),
    and NO cal.com booking link in the first-touch body (link moves to follow-up). Zero links.
  * Prefers a personal inbox (carried as email_source = site-personal*) over generic.
  * Adds the Plumbing vertical (HVAC-style speed-to-lead copy).
  * Bodies plain text, ~95-120 words, "— Cyrus" sig, ZERO links on first touch.

ALL multi-line bodies are built with chr(10).join([...]) — zero bare newline literals — per the
write-tool mangling rule. Output row schema matches batch4_payload.json. NO SENDING.
"""
import json, re, os
from collections import Counter

NL = chr(10)
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "harvest5_emailable.json")
OUT = os.path.join(HERE, "batch5_payload.json")
TRADE = {"HVAC": "HVAC", "Roofing": "roofing", "Plumbing": "plumbing"}

# emails to DROP outright (placeholders / wrong-domain scrape false-positives)
EMAIL_BLOCKLIST = {
    "youremail@yourbusiness.com", "hello@mail.com", "rob@gafs.com", "eben@eyebytes.com",
}
JUNK_EMAIL_DOMAINS = {"mail.com", "yourbusiness.com", "example.com", "gafs.com",
                      "eyebytes.com", "wixpress.com", "sentry.io", "core.com"}

# Hard block of local-parts / tokens that must never become "Hi X,"
HARD_BLOCK = {"info", "office", "admin", "booking", "contact", "hello", "team",
              "reception", "frontdesk", "appointments", "intake", "justice", "support",
              "sales", "billing", "help", "mail", "service", "attorney", "attorneys",
              "lawyer", "law", "lawfirm", "legal", "firm", "clinic", "spa", "medspa",
              "care", "scheduling", "schedule", "newpatient", "youremail", "yourname",
              "email", "name", "company", "business", "officecrew", "estimate",
              "estimates", "quote", "quotes", "dispatch", "general", "main",
              "support", "dept", "department", "who", "what", "your", "our", "the",
              "we", "us", "meet", "about", "home", "welcome", "hours", "areas",
              "served", "financing", "privacy", "terms", "reviews", "review", "gallery",
              "customer", "customers", "client", "clients", "emergency", "free",
              "today", "call", "now", "here", "more", "learn", "get", "read", "owner",
              "founder", "president", "principal", "manager", "staff", "people",
              "contactus", "contact-us", "reachus", "emailus", "callus", "getintouch",
              "webmaster", "noreply", "no-reply", "donotreply", "enquiries", "enquiry",
              "inquiries", "inquiry", "peakview"}

BIZ_WORDS = ("law", "legal", "firm", "heating", "cooling", "hvac", "roof", "plumb",
             "spa", "clinic", "dental", "dent", "medi", "crew", "office", "team",
             "group", "associates", "construction", "aesthetic", "skin", "injury",
             "divorce", "mechanic", "electric", "comfort", "system", "contract",
             "solution", "drain", "sewer", "furnace")

# geography + filler + common non-name nouns that the HTML owner-scraper sometimes grabs.
# Any of these as a "first name" -> fall back to "there".
GEO_JUNK = {
    "colorado", "springs", "texas", "mexico", "fresno", "albuquerque", "greenville",
    "paso", "reno", "nevada", "california", "carolina", "denver", "vegas", "rocky",
    "mountain", "north", "south", "east", "west", "central", "county", "city", "town",
    "valley", "river", "lake", "hill", "hills", "park", "sandia", "pikes", "front",
    "range", "desert", "mesa", "rio", "grande", "santa", "fe", "taos",
    # filler / sentence words
    "locally", "family", "owned", "operated", "trusted", "local", "proudly", "serving",
    "since", "years", "experience", "quality", "best", "top", "choice", "premier",
    "professional", "affordable", "reliable", "honest", "fast", "same", "day", "24",
    "hour", "emergency", "licensed", "insured", "bonded", "certified", "award",
    "winning", "voted", "rated", "google", "facebook", "yelp", "reviews", "happy",
    "satisfied", "guaranteed", "satisfaction", "free", "estimate", "estimates",
    "financing", "available", "call", "today", "now", "contact", "schedule", "book",
    "request", "learn", "read", "more", "here", "click", "get", "see", "view", "meet",
    "about", "home", "welcome", "thank", "thanks", "hello", "hi", "hey", "that",
    "this", "these", "those", "your", "you", "our", "their", "his", "her", "its",
    "past", "present", "future", "new", "old", "all", "any", "every", "some", "many",
    "grandma", "grandpa", "mom", "dad", "son", "daughter", "sister", "brother",
    "tips", "tip", "news", "blog", "faq", "info", "detail", "details", "area", "areas",
    "service", "services", "repair", "install", "installation", "replacement",
    "maintenance", "inspection", "commercial", "residential", "industrial",
    "oug", "bee", "vic",  # observed scraper junk / too-ambiguous 2-3 letter grabs
}

def safe_name(raw, business_name=""):
    """Final safety gate on a first name (from scraper). Returns clean cap-name or 'there'."""
    if not raw:
        return "there"
    cand = re.sub(r"[^A-Za-z]", "", str(raw)).lower()
    if not cand or not (2 < len(cand) < 13):
        return "there"
    if cand in HARD_BLOCK or cand in GEO_JUNK:
        return "there"
    if any(bw in cand for bw in BIZ_WORDS):
        return "there"
    bn = re.sub(r"[^a-z]", "", (business_name or "").lower())
    if len(cand) >= 6 and cand in bn:
        return "there"
    return cand.capitalize()

def poss(name):
    return name + "'" if name.rstrip().endswith(("s", "S")) else name + "'s"

def email_local_name(email):
    """Recover a first name from a PERSONAL on-domain email local-part, else None."""
    if not email or "@" not in email:
        return None
    local = email.split("@")[0].lower()
    # first.last / first_last / first-last -> take first token
    if re.match(r"^[a-z]{2,}[._\-][a-z]{2,}$", local):
        tok = re.split(r"[._\-]", local)[0]
        nm = safe_name(tok)
        return nm if nm != "there" else None
    # single alpha token, 3-11 chars
    if local.isalpha() and 3 <= len(local) <= 11:
        nm = safe_name(local)
        if nm == "there":
            return None
        known = {"chris","craig","brian","brent","grant","shane","steve","frank",
                 "glenn","wayne","scott","trent","blake","bruce","david","derek",
                 "keith","kevin","kyle","mark","nick","paul","ryan","sean","todd",
                 "tyler","chad","drew","seth","cole","dale","gary","greg","jack",
                 "joel","juan","luis","jose","raul","omar","saul","noah","alan",
                 "carl","gene","russ","kurt","neil","reed","ross","wade","vic",
                 "stan","jim","ben","adam","anna","erin","josh","lance","lois",
                 "patty","randy","roger","tracy","bart","jon","casey","shiloh",
                 "gabriel","jonathan","oreanna","cesar","angela","sarah","laura",
                 "maria","jason","aaron","kelly","diana","megan","erika","erin"}
        if local in known:
            return nm
        # initial + surname heuristic: single consonant-led token, no separator, >=5 chars
        # and not a known name -> almost always j.surname / p.surname / r.lobb -> reject
        if len(local) >= 5 and local[0] not in "aeiou":
            return None
        # very short single tokens are risky unless known
        if len(local) <= 4:
            return None
        return nm
    return None

def pick_greeting_name(r):
    """High-precision first name for the greeting.
    Priority: on-domain PERSONAL email local-part (strongest signal) >
    HTML owner-name that agrees with the email or appears in the business name.
    Anything ambiguous or contradicted -> 'there'."""
    name = r["name"]
    email = (r.get("final_email") or "").lower()
    src = (r.get("email_source") or "")
    html_name = safe_name(r.get("owner_first"), name)
    email_name = email_local_name(email) if src.startswith("site-personal") and \
        not src.endswith("offdomain") else None
    # 1) personal on-domain email gives the most reliable name
    if email_name:
        # if HTML name contradicts the email name, trust the email (it's the actual inbox owner)
        return email_name
    # 2) generic inbox: use HTML owner-name only if it also appears in the business name
    #    (e.g. 'Adam' in 'The Law Office of Adam Oakey') -> high confidence it's the principal.
    if html_name != "there":
        bn = re.sub(r"[^a-z]", "", name.lower())
        if html_name.lower() in bn:
            return html_name
        # otherwise, an HTML-only owner name on a generic inbox is too risky -> there
        return "there"
    return "there"

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
    s = sla.strip().lower()
    if s in ("get back to you as soon", "get back to you soon", "get back to you as soon as"):
        return "says they'll get back to you as soon as they can"
    if s in ("get back to you shortly",):
        return "says they'll get back to you shortly"
    if re.match(r"^(get back|reply|respond|contact)", s):
        return "says " + sla.strip()
    if re.match(r"^(within|in|under)\b", s):
        return "promises a response " + sla.strip()
    if re.match(r"^(one|two|three|\d|\d+\s*[-\u2013])", s):
        return "promises a response within " + sla.strip()
    return "says '" + sla.strip() + "'"

# --- soft reply CTAs (NO link on first touch) -------------------------------
def cta_demo(name):
    return ("Want me to send over a 2-minute demo so you can see exactly what your "
            "customers would experience? Just reply and I'll fire it over.")

def cta_demo_clients(name):
    return ("Want me to send over a 2-minute demo so you can see exactly what your "
            "clients would experience? Just reply and I'll fire it over.")

def join(parts):
    """Join body paragraphs with a blank line between them (chr(10)+chr(10))."""
    return (NL + NL).join(parts)

def draft(r):
    v = r["vertical"]; name = r["name"]
    city = (r.get("metro") or r.get("city") or "").split(",")[0].strip()
    email = r["final_email"]; hook = r.get("site_hook")
    fn = pick_greeting_name(r)
    rc = review_count(hook)
    sla = sla_quote(hook)
    greet = "Hi " + fn + ","

    if v in ("HVAC", "Roofing", "Plumbing"):
        trade = TRADE[v]
        if rc is not None:
            subj = f"{rc} {plural(rc)} for {name}?"
            body = join([
                greet,
                (f"{name} does great work but only has {rc} Google {plural(rc)} — and in "
                 f"{trade}, reviews are basically the whole ballgame for getting found."),
                ("I build a simple system that (1) texts every new lead back in under 60 "
                 "seconds so you stop losing them to whoever answers first, and (2) "
                 "automatically asks every happy customer for a review after the job — most "
                 "shops 3-5x their review count in a few months."),
                cta_demo(name),
                "— Cyrus",
            ])
        elif sla:
            subj = f"quick one about {city} leads" if city else "a quick one about your leads"
            says = sla_says(sla)
            body = join([
                greet,
                (f"Saw {poss(name)} site {says}. Not a knock — almost every {trade} shop does "
                 f"the same. The problem is the homeowner who fills that form usually messages "
                 f"3 contractors and books whoever answers first (~78% go with the first "
                 f"responder)."),
                ("I set up a system that texts every new lead back within 60 seconds, 24/7 — "
                 "answers their question and books them — then automatically asks happy "
                 "customers for a Google review after the job."),
                cta_demo(name),
                "— Cyrus",
            ])
        else:
            subj = f"quick one about {city} leads" if city else "a quick one about your leads"
            body = join([
                greet,
                (f"Saw {poss(name)} site has a contact form but no instant response — a "
                 f"homeowner who fills it out usually messages a few {trade} shops and books "
                 f"whoever answers first (~78% go with the first responder)."),
                ("I set up a system that texts every new lead back within 60 seconds, 24/7 — "
                 "answers their question and books them — then automatically asks happy "
                 "customers for a Google review after the job."),
                cta_demo(name),
                "— Cyrus",
            ])
    elif v in ("Personal injury law", "Family law"):
        if rc is not None:
            subj = f"{rc} {plural(rc)} for {name}?"
            body = join([
                greet,
                (f"You've clearly handled serious cases — but {name} only shows {rc} Google "
                 f"{plural(rc)}. For a firm like yours that's leaving a lot on the table, "
                 f"because people pick a firm almost entirely on reviews and how fast someone "
                 f"responds."),
                ("I set up two things for firms like yours: every new inquiry gets a response "
                 "within 60 seconds (day or night — that's when people reach out), and every "
                 "client whose case resolves gets an automatic, tactful review request. Firms "
                 "usually go from a couple dozen reviews to triple digits."),
                cta_demo_clients(name),
                "— Cyrus",
            ])
        else:
            subj = "a quick thought on your intake"
            body = join([
                greet,
                (f"Saw {poss(name)} contact form has no instant response — someone reaching "
                 f"out at 9pm waits until business hours, and a lot of them call the next firm "
                 f"instead."),
                ("I build a system that responds to every inquiry within 60 seconds, 24/7, "
                 "qualifies them, and gets them scheduled — plus it automatically asks "
                 "resolved clients for a Google review."),
                cta_demo_clients(name),
                "— Cyrus",
            ])
    else:  # Med spa / other
        subj = "the leads who don't book online"
        body = join([
            greet,
            (f"{poss(name)} booking page is great for people ready to book — but the leads who "
             f"call, DM, or fill the form with a question (and don't book themselves) are the "
             f"ones that quietly slip away when no one replies fast."),
            ("I set up a system that texts those leads back within 60 seconds, 24/7 — answers "
             "them and gets them booked — and automatically asks clients for a review after "
             "their visit. It basically recovers the inquiries you're already paying to "
             "generate."),
            cta_demo_clients(name),
            "— Cyrus",
        ])

    return {
        "name": name, "vertical": v, "city_state": r.get("metro", ""),
        "website": r.get("website", ""), "phone": r.get("phone", ""),
        "to": email, "subject": subj, "body": body, "form_only": False,
        "email_source": r.get("email_source"), "review_count_listing": r.get("reviewCount"),
    }

def main():
    rows = json.load(open(SRC))
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
    # also keep a stable full-set copy so the selector can re-run idempotently
    full = os.path.join(HERE, "batch5_payload_full.json")
    json.dump(payload, open(full, "w"), ensure_ascii=False, indent=2)
    c = Counter(p["vertical"] for p in payload)
    named = sum(1 for p in payload if not p["body"].startswith("Hi there,"))
    personal = sum(1 for p in payload if (p.get("email_source") or "").startswith("site-personal"))
    print(f"EMAILABLE source rows: {len(rows)}")
    print(f"dropped (junk/placeholder/wrong-domain email): {len(dropped)} -> {dropped}")
    print(f"batch5 drafted: {len(payload)} -> {OUT}")
    for v, n in sorted(c.items()):
        print(f"   {v}: {n}")
    print(f"real-first-name greetings: {named}/{len(payload)} "
          f"({100*named/max(1,len(payload)):.0f}%)")
    print(f"personal-inbox recipients: {personal}/{len(payload)} "
          f"({100*personal/max(1,len(payload)):.0f}%)")

if __name__ == "__main__":
    main()
