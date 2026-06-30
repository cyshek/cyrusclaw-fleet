#!/usr/bin/env python3
"""Generate a "touch 2" follow-up payload from a batch sendlog + its original payload.

Usage:
    python3 make_followup.py batch1_sendlog.csv batch1_payload.json followup1_payload.json

- Reads everyone who was SENT in the given batch sendlog.
- Looks up their vertical + recipient email + first-name treatment from the original
  batch payload (matched by the 'to' email, falling back to name).
- Emits a SHORTER touch-2 email per vertical (see followup-templates.md), same booking CTA.
- Marks every row with "replied": null so the parent/Cyrus can flip repliers to true
  (or just delete them) BEFORE sending. We CANNOT reliably detect replies here, so every
  contacted business is included and the file is clearly flagged.
- Output shape mirrors send_batch2.py's expected payload:
    [{name, vertical, city_state, website, to, subject, body, replied, touch}]
  so a send_followup.py clone can fire it after repliers are removed.

NO SENDING. Drafting only.
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = "https://cal.com/cyshek"

TRADE = {"HVAC": "HVAC", "Roofing": "roofing"}

def norm(s):
    return (s or "").strip().strip('"').lower()

def first_name_from_email(email, business_name=""):
    """Return a plausible HUMAN first name from the email local-part, else 'there'.
    Mirrors batch2's intent but generically rejects business-y / role locals so we never
    greet someone 'Hi Betterskin,' / 'Hi Farrelllaw,' / 'Hi Attorney,' / 'Hi Officecrew,'."""
    if not email or "@" not in email:
        return "there"
    local, domain = email.split("@", 1)
    local = local.lower()
    domain_stem = domain.split(".")[0].lower()
    # explicit non-name locals observed in our data (vanity handles, initial+surname, etc.)
    hard_block = {"sdykstra", "amlabonne", "amlabonne01", "officecrew", "betterskin",
                  "farrelllaw", "jeremylegacyroofing", "casperheatcool", "gobutlerheating",
                  "moorerdmedispa", "spapavone"}
    if local in hard_block:
        return "there"
    # vanity handles: a local-part ending in digits is almost never a first name
    if re.search(r"\d$", local):
        return "there"
    generic = {"info", "office", "admin", "booking", "contact", "hello", "team",
               "reception", "frontdesk", "appointments", "intake", "justice",
               "support", "sales", "hr", "billing", "help", "mail", "service",
               "officecrew", "office.crew", "attorney", "attorneys", "lawyer",
               "law", "lawfirm", "legal", "firm", "betterskin", "clinic", "spa",
               "medspa", "frontoffice", "customerservice", "care", "newpatient",
               "newpatients", "scheduling", "schedule", "enquiries", "inquiries"}
    # business-y substrings that disqualify a local-part from being a first name
    biz_words = ("law", "legal", "firm", "heating", "cooling", "hvac", "roof",
                 "plumb", "spa", "clinic", "dental", "dent", "medi", "med",
                 "crew", "office", "team", "group", "associates", "construction",
                 "aesthetic", "skin", "injury", "divorce", "realty", "insurance")
    cand = re.split(r"[._\-0-9]", local)[0]
    if not cand:
        return "there"
    if local in generic or cand in generic:
        return "there"
    if not cand.isalpha():
        return "there"
    if not (2 < len(cand) < 12):
        return "there"
    # reject if it IS the domain stem or contained in it (e.g. farrelllaw@farrelllaw.com)
    if cand == domain_stem or (len(cand) >= 5 and cand in domain_stem):
        return "there"
    # reject obvious business words
    if any(bw in local for bw in biz_words):
        return "there"
    # reject if the candidate is a chunk of the business name (e.g. 'sdykstra' vs 'G.R.I.P.S.')
    bn = re.sub(r"[^a-z]", "", (business_name or "").lower())
    if cand in bn and len(cand) >= 6:
        return "there"
    return cand.capitalize()

def touch2_body(vertical, fname, name, city):
    if vertical in ("HVAC", "Roofing"):
        trade = TRADE.get(vertical, "home services")
        subj = f"re: {city} leads" if city else "re: your leads"
        body = (
            f"Hi {fname},\n\n"
            f"Floating this back up in case it got buried. The short version: I set up a system "
            f"that texts every new {trade} lead back within 60 seconds, 24/7 — so you stop losing "
            f"them to whoever answers first — and auto-asks happy customers for a Google review.\n\n"
            f"If it's worth 15 min: {BOOK}\n\n"
            f"Totally fine if it's not a fit — just reply \"not now\" and I'll leave you be.\n\n"
            f"— Cyrus"
        )
    elif vertical in ("Personal injury law", "Family law"):
        subj = "re: your intake"
        body = (
            f"Hi {fname},\n\n"
            f"Didn't hear back — no worries at all. Just floating this back up: I set up a system "
            f"that responds to every new inquiry within 60 seconds, day or night (that's when people "
            f"reach out), qualifies them, and gets them scheduled — plus automatic, tactful review "
            f"requests as cases resolve.\n\n"
            f"Worth 15 min? {BOOK}\n\n"
            f"If it's not a fit, reply \"not now\" and I'll stop bugging you.\n\n"
            f"— Cyrus"
        )
    else:  # Med spa / aesthetics + any default
        subj = "re: the leads who don't book online"
        body = (
            f"Hi {fname},\n\n"
            f"Floating this back up in case it slipped by. Quick version: I set up a system that "
            f"texts back the leads who call/DM/fill the form but don't book themselves — within 60 "
            f"seconds, 24/7 — and gets them booked, plus auto review requests after visits. It "
            f"recovers inquiries you're already paying to generate.\n\n"
            f"Worth a quick 15 min? {BOOK}\n\n"
            f"Not a fit? Just reply \"not now\" — no hard feelings.\n\n"
            f"— Cyrus"
        )
    return subj, body

def touch3_body(vertical, fname, name, city):
    """The single 'breakup' email — same for all verticals. Sent ONCE at ~7-10 days, then stop."""
    subj = "closing the loop"
    body = (
        f"Hi {fname},\n\n"
        f"I'll take the hint and stop here — figured {name} either has lead response handled "
        f"or it's just not a priority right now, both totally fair.\n\n"
        f"If that ever changes, the door's open: {BOOK}\n\n"
        f"Wishing you a great rest of the year.\n\n"
        f"— Cyrus"
    )
    return subj, body


def main():
    # Optional --touch N flag (default 2). Strip it out before positional parsing.
    argv = sys.argv[1:]
    touch = 2
    if "--touch" in argv:
        i = argv.index("--touch")
        touch = int(argv[i + 1])
        del argv[i:i + 2]
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    sendlog = argv[0] if os.path.isabs(argv[0]) else os.path.join(HERE, argv[0])
    payload = argv[1] if os.path.isabs(argv[1]) else os.path.join(HERE, argv[1])
    out = argv[2] if len(argv) > 2 else os.path.join(HERE, "followup1_payload.json")
    if not os.path.isabs(out):
        out = os.path.join(HERE, out)
    body_fn = touch3_body if touch == 3 else touch2_body

    # original payload indexed by recipient email + by name for enrichment
    orig = json.load(open(payload))
    by_to = {norm(r.get("to")): r for r in orig if r.get("to")}
    by_name = {norm(r.get("name")): r for r in orig}

    # prospects.csv fallback (older payloads like batch1 lack vertical/city_state/website).
    # index by name AND by email domain so we can recover vertical for any contacted row.
    prospects_csv = os.path.join(HERE, "prospects.csv")
    pby_name, pby_dom = {}, {}
    if os.path.exists(prospects_csv):
        for pr in csv.DictReader(open(prospects_csv)):
            pby_name[norm(pr.get("name"))] = pr
            w = re.sub(r"^https?://(www\.)?", "", (pr.get("website") or "").strip(), flags=re.I)
            w = w.split("/")[0].lower()
            if w:
                pby_dom[w] = pr

    def enrich(name, to):
        """Best-effort vertical/city_state/website for a contacted business."""
        src = by_to.get(norm(to)) or by_name.get(norm(name)) or {}
        vertical = src.get("vertical") or ""
        city_state = src.get("city_state") or ""
        website = src.get("website") or ""
        if not vertical:  # fall back to prospects.csv
            dom = to.split("@")[1].lower() if "@" in to else ""
            p = pby_name.get(norm(name)) or pby_dom.get(dom) or {}
            vertical = p.get("vertical") or vertical
            city_state = city_state or p.get("city_state") or ""
            website = website or p.get("website") or ""
        return vertical, city_state, website

    rows = []
    skipped = []
    for r in csv.DictReader(open(sendlog)):
        if (r.get("status") or "").strip().upper() != "SENT":
            skipped.append((r.get("name"), r.get("status")))
            continue
        to = (r.get("to") or "").strip()
        name = (r.get("name") or "").strip()
        vertical, city_state, website = enrich(name, to)
        city = city_state.split(",")[0].strip() if city_state else ""
        fname = first_name_from_email(to, name)
        subj, body = body_fn(vertical, fname, name, city)
        rows.append({
            "name": name,
            "vertical": vertical,
            "city_state": city_state,
            "website": website,
            "to": to,
            "subject": subj,
            "body": body,
            "replied": None,   # <-- auto-excluded by the scan if they replied/bounced
            "touch": touch,
        })

    json.dump(rows, open(out, "w"), ensure_ascii=False, indent=2)
    from collections import Counter
    c = Counter(x["vertical"] or "(unknown)" for x in rows)
    print(f"sendlog:        {sendlog}")
    print(f"original payload: {payload}")
    print(f"touch-{touch} drafted:  {len(rows)}  -> {out}")
    for v, n in sorted(c.items()):
        print(f"   {v}: {n}")
    if skipped:
        print(f"skipped (not SENT): {len(skipped)} -> {skipped}")
    print("\n*** NOTE: every contacted business is included. Reply detection is NOT done here.")
    print("*** Before sending: remove rows for anyone who replied (set 'replied':true or delete).")

if __name__ == "__main__":
    main()
