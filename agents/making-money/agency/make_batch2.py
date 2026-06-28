#!/usr/bin/env python3
"""Generate batch-2 personalized outreach payload from prospects.csv.
- Excludes the 15 names already sent in batch 1 (read from batch1_sendlog.csv).
- Takes the remaining prospects (~38).
- Same per-vertical personalized templates as batch 1, BUT the CTA now offers a
  self-serve booking link (Cal.com) instead of "can I show you a demo?".
- Output: batch2_payload.json  [{name, vertical, city_state, website, to, subject, body, form_only}]
No sending here — drafting only. Sender script reads the JSON.
"""
import csv, re, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "prospects.csv")
SENDLOG = os.path.join(HERE, "batch1_sendlog.csv")
OUT = os.path.join(HERE, "batch2_payload.json")

DEMO = "http://40.65.93.84:8080/speed-to-lead-demo.html"
BOOK = "https://cal.com/cyshek"  # Cyrus's 15-min Intro Call booking page (Google Meet)

TRADE = {"HVAC": "HVAC", "Roofing": "roofing"}

# ---- reuse batch-1 personalization helpers verbatim ----
def first_name(email, name):
    local = email.split("@")[0].lower() if "@" in email else ""
    if local and local not in ("info","office","admin","booking","contact","justice",
                               "betterskin","farrelllaw","spapavone","gobutlerheating",
                               "casperheatcool","moorerdmedispa","officecrew",
                               "jeremylegacyroofing","amlabonne01"):
        cand = re.split(r"[._]", local)[0]
        if cand.isalpha() and 2 < len(cand) < 12 and cand not in ("info","office","admin"):
            return cand.capitalize()
    return "there"

def review_count(hook):
    m = re.search(r"(\d+)\s+reviews?", hook)
    return m.group(1) if m else None

def low_review_count(hook):
    """Only treat as a review-GAP angle if the count is genuinely low (<=12).
    Leading with 'only 28 reviews?' to a firm that has 28 is insulting + wrong."""
    rc = review_count(hook)
    if rc is not None and int(rc) <= 12:
        return rc
    return None

def plural(n):
    return "review" if str(n) == "1" else "reviews"

def sla_phrase(hook):
    m = re.search(r"'([^']+)'", hook)
    if m and m.group(1) not in ("get back to you soon","get back to you as soon"):
        return m.group(1)
    if "get back to you soon" in hook or "get back to you as soon" in hook:
        return "they'll get back to you soon"
    return None

# ---- CTA: the ONLY substantive change vs batch 1 — self-serve booking ----
def cta(name):
    # friendly, low-pressure, self-serve. 15 min, their pick of time.
    return (f"If it's worth a look, grab whatever 15-min slot works for you here: {BOOK} "
            f"— I'll walk you through exactly what it'd look like for {name} (no pressure, no hard sell).")

def draft(row):
    v = row["vertical"]; name = row["name"]; city = row["city_state"].split(",")[0]
    email = row["email"]; hook = row["personalization_hook"]
    fn = first_name(email, name)
    rc = low_review_count(hook); sla = sla_phrase(hook)
    form_only = email.startswith("FORM ONLY")
    to = "" if form_only else email
    call = cta(name)

    if v in ("HVAC","Roofing"):
        trade = TRADE[v]
        if rc:
            subj = f"{rc} {plural(rc)} for {name}?"
            body = f"""Hi {fn},

{name} does great work but only has {rc} Google {plural(rc)} — and in {trade}, reviews are basically the whole ballgame for getting found.

I build a simple system that (1) texts every new lead back in under 60 seconds so you stop losing them to whoever answers first, and (2) automatically asks every happy customer for a review after the job — most shops 3-5x their review count in a few months.

{call}

— Cyrus"""
        else:
            phrase = sla if sla else "you'll get back to folks soon"
            subj = f"quick one about {city} leads"
            # make the SLA quote grammatical: time-windows ('within 24 hours', 'one business day')
            # need a verb; conversational quotes ("you'll get back...") read fine as-is.
            if sla and not re.search(r"\b(you|they|we|i)'?ll\b|get back|respond|reply|contact", sla, re.I):
                says = f"promises a response within {sla.strip().lstrip('within ').strip()}" if re.search(r"^(within|in|under|one|two|\d)", sla.strip(), re.I) else f"says ‘{sla.strip()}’"
            else:
                says = f"says {phrase}"
            body = f"""Hi {fn},

Saw {name}'s site {says}. Not a knock — almost every {trade} shop does the same. The problem is the homeowner who fills that form usually messages 3 contractors and books whoever answers first (~78% go with the first responder).

I set up a system that texts every new lead back within 60 seconds, 24/7 — answers their question and books them — then automatically asks happy customers for a Google review after the job.

{call}

— Cyrus"""
    elif v in ("Personal injury law","Family law"):
        if rc:
            subj = f"{rc} {plural(rc)} for {name}?"
            body = f"""Hi {fn},

You've clearly handled serious cases — but {name} only shows {rc} Google {plural(rc)}. For a firm like yours that's leaving a lot on the table, because people pick a firm almost entirely on reviews and how fast someone responds.

I set up two things for firms like yours: every new inquiry gets a response within 60 seconds (day or night — that's when people reach out), and every client whose case resolves gets an automatic, tactful review request. Firms usually go from a couple dozen reviews to triple digits.

{call}

— Cyrus"""
        else:
            subj = "a quick thought on your intake"
            body = f"""Hi {fn},

Saw {name}'s contact form has no instant response — someone reaching out at 9pm waits until business hours, and a lot of them call the next firm instead.

I build a system that responds to every inquiry within 60 seconds, 24/7, qualifies them, and gets them scheduled — plus it automatically asks resolved clients for a Google review.

{call}

— Cyrus"""
    else:  # Med spa
        subj = "the leads who don't book online"
        body = f"""Hi {fn},

{name}'s booking page is great for people ready to book — but the leads who call, DM, or fill the form with a question (and don't book themselves) are the ones that quietly slip away when no one replies fast.

I set up a system that texts those leads back within 60 seconds, 24/7 — answers them and gets them booked — and automatically asks clients for a review after their visit. It basically recovers the inquiries you're already paying to generate.

{call}

— Cyrus"""
    return {"name": name, "vertical": v, "city_state": row["city_state"],
            "website": row["website"], "phone": row.get("phone",""),
            "to": to, "subject": subj, "body": body, "form_only": form_only}

def main():
    rows = list(csv.DictReader(open(CSV)))
    # names already sent in batch 1 (normalize: strip quotes/whitespace, lowercase)
    sent = set()
    if os.path.exists(SENDLOG):
        for r in csv.DictReader(open(SENDLOG)):
            n = (r.get("name") or "").strip().strip('"').lower()
            if n: sent.add(n)
    def norm(n): return (n or "").strip().strip('"').lower()

    remaining = [r for r in rows if norm(r["name"]) not in sent]
    # only those with a real email (skip pure form-only for an EMAIL batch; flag them separately)
    emailable = [r for r in remaining if (r.get("email") or "").strip()
                 and not r["email"].startswith("FORM ONLY")]
    formonly = [r for r in remaining if r["email"].startswith("FORM ONLY")
                or not (r.get("email") or "").strip()]

    payload = [draft(r) for r in emailable]
    json.dump(payload, open(OUT, "w"), indent=2)

    from collections import Counter
    c = Counter(p["vertical"] for p in payload)
    print(f"batch1 already sent: {len(sent)}")
    print(f"remaining prospects: {len(remaining)}")
    print(f"EMAILABLE (batch 2): {len(payload)}  -> {OUT}")
    for v, n in sorted(c.items()): print(f"  {v}: {n}")
    if formonly:
        print(f"form-only / no-email (NOT in batch 2, handle manually): {len(formonly)}")
        for r in formonly: print(f"  - {r['name']} ({r['website']})")

if __name__ == "__main__":
    main()
