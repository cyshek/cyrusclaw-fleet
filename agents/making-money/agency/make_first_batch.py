#!/usr/bin/env python3
"""Generate personalized first-batch outreach drafts from prospects.csv.
Picks the strongest prospects per vertical and fills the right template per row.
Output: first-batch-drafts.md (human-readable, ready to copy-send or auto-send).
No sending here — drafting only."""
import csv, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "prospects.csv")
OUT = os.path.join(HERE, "first-batch-drafts.md")
DEMO = "http://40.65.93.84:8080/speed-to-lead-demo.html"

TRADE = {"HVAC": "HVAC", "Roofing": "roofing"}

def first_name(email, name):
    # owner-name gmail rows -> try to use a human first name; else fall back
    local = email.split("@")[0].lower() if "@" in email else ""
    # common owner-name patterns: sherry@, katie@, joe@, dana@, wayne@, craig...
    owners = ["sherry","katie","joe","dana","wayne","jeremy","craig","sdykstra","tallen","admin","attorney","betterskin","booking","justice","office","info","farrelllaw"]
    if local and local not in ("info","office","admin","booking","contact","justice","betterskin","farrelllaw","spapavone","gobutlerheating","casperheatcool","moorerdmedispa","officecrew","jeremylegacyroofing","amlabonne01"):
        cand = re.split(r"[._]", local)[0]
        if cand.isalpha() and 2 < len(cand) < 12 and cand not in ("info","office","admin"):
            return cand.capitalize()
    return "there"

def review_count(hook):
    m = re.search(r"(\d+)\s+reviews?", hook)
    return m.group(1) if m else None

def sla_phrase(hook):
    m = re.search(r"'([^']+)'", hook)
    if m and m.group(1) not in ("get back to you soon","get back to you as soon"):
        return m.group(1)
    if "get back to you soon" in hook or "get back to you as soon" in hook:
        return "they'll get back to you soon"
    return None

def draft(row):
    v = row["vertical"]; name = row["name"]; city = row["city_state"].split(",")[0]
    email = row["email"]; hook = row["personalization_hook"]
    fn = first_name(email, name)
    rc = review_count(hook); sla = sla_phrase(hook)
    form_only = email.startswith("FORM ONLY")
    to = "[contact form — see URL]" if form_only else email

    # choose template
    if v in ("HVAC","Roofing"):
        trade = TRADE[v]
        if rc:  # review-gap version
            subj = f"{rc} reviews for {name}?"
            body = f"""Hi {fn},

{name} does great work but only has {rc} Google reviews — and in {trade}, reviews are basically the whole ballgame for getting found.

I build a simple system that (1) texts every new lead back in under 60 seconds so you stop losing them to whoever answers first, and (2) automatically asks every happy customer for a review after the job — most shops 3-5x their review count in a few months.

Can I show you a quick demo of what it'd look like for {name}?

— Cyrus"""
        else:  # speed-to-lead / SLA version
            phrase = sla if sla else "you'll get back to folks soon"
            subj = f"quick one about {city} leads"
            body = f"""Hi {fn},

Saw {name}'s site says {phrase if sla else "you'll get back to folks soon"}. Not a knock — almost every {trade} shop does the same. The problem is the homeowner who fills that form usually messages 3 contractors and books whoever answers first (~78% go with the first responder).

I set up a system that texts every new lead back within 60 seconds, 24/7 — answers their question and books them — then automatically asks happy customers for a Google review after the job.

Happy to show you a 2-minute demo of exactly what your customers would see. Worth a look?

— Cyrus"""
    elif v in ("Personal injury law","Family law"):
        if rc:
            subj = f"{rc} reviews for {name}?"
            body = f"""Hi {fn},

You've clearly handled serious cases — but {name} only shows {rc} Google reviews. For a firm like yours that's leaving a lot on the table, because people pick a firm almost entirely on reviews and how fast someone responds.

I set up two things for firms like yours: every new inquiry gets a response within 60 seconds (day or night — that's when people reach out), and every client whose case resolves gets an automatic, tactful review request. Firms usually go from a couple dozen reviews to triple digits.

Open to a 2-minute demo of how it'd work for {name}?

— Cyrus"""
        else:
            subj = f"quick thought on {name}'s intake"
            body = f"""Hi {fn},

Saw {name}'s contact form has no instant response — someone reaching out at 9pm waits until business hours, and a lot of them call the next firm instead.

I build a system that responds to every inquiry within 60 seconds, 24/7, qualifies them, and gets them scheduled — plus it automatically asks resolved clients for a Google review.

Worth a quick demo to see what your potential clients would experience?

— Cyrus"""
    else:  # Med spa
        subj = "the leads who don't book online"
        body = f"""Hi {fn},

{name}'s booking page is great for people ready to book — but the leads who call, DM, or fill the form with a question (and don't book themselves) are the ones that quietly slip away when no one replies fast.

I set up a system that texts those leads back within 60 seconds, 24/7 — answers them and gets them booked — and automatically asks clients for a review after their visit. It basically recovers the inquiries you're already paying to generate.

Can I show you a 2-minute demo of exactly what your clients would see?

— Cyrus"""
    return to, subj, body, form_only

def main():
    rows = list(csv.DictReader(open(CSV)))
    # rank: prefer rows with a strong hook (explicit SLA quote or low review count), owner emails, not form-only
    def score(r):
        h = r["personalization_hook"]; e = r["email"]; s = 0
        if review_count(h): s += 3
        if sla_phrase(h): s += 3
        if not e.startswith("FORM ONLY"): s += 2
        if "@gmail" in e or not any(g in e for g in ("info@","office@","admin@")): s += 1
        return s
    by_v = {}
    for r in rows:
        by_v.setdefault(r["vertical"], []).append(r)
    # take top 3 per vertical by score for the first batch (~15)
    batch = []
    for v, rs in by_v.items():
        rs.sort(key=score, reverse=True)
        batch.extend(rs[:3])

    lines = ["# FIRST BATCH — personalized outreach drafts (READY TO SEND on Cyrus's OK)",
             "",
             f"_Generated from prospects.csv. {len(batch)} drafts (top ~3 per vertical by hook strength)._",
             "_Send from Cyrus's Gmail, plain text, 15-20/day spaced out. Nothing sent yet._",
             f"_Demo link for follow-ups: {DEMO}_",
             "", "---", ""]
    for i, r in enumerate(batch, 1):
        to, subj, body, form_only = draft(r)
        lines.append(f"## {i}. {r['name']} — {r['vertical']} ({r['city_state']})")
        lines.append(f"**To:** {to}" + ("  ⚠️ FORM-ONLY — paste into their contact form, no email" if form_only else ""))
        lines.append(f"**Phone:** {r['phone']}  ·  **Site:** {r['website']}")
        lines.append(f"**Subject:** {subj}")
        lines.append("")
        lines.append("```")
        lines.append(body)
        lines.append("```")
        lines.append("")
    open(OUT, "w").write("\n".join(lines))
    print(f"Wrote {len(batch)} drafts to {OUT}")
    # vertical counts
    from collections import Counter
    c = Counter(r["vertical"] for r in batch)
    for v, n in c.items(): print(f"  {v}: {n}")

if __name__ == "__main__":
    main()
