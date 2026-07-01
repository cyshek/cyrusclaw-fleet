#!/usr/bin/env python3
"""Batch-5 ENHANCED site scraper (NO Hunter). For each fresh business:
  (a) find a contact email, PREFERRING a personal-looking local-part
      (firstname@ / first.last@) over generic info@/office@/contact@;
  (b) find a personalization HOOK (low review count / slow SLA / contact-form-no-instant);
  (c) find an OWNER / principal FIRST NAME from About / Meet-the-team / Our-team / footer
      text and JSON-LD (Person/founder/author), applying strict name-safety so we never
      greet "Hi Attorney," / "Hi Officecrew," / initial+surname junk.

Crawls home + a handful of likely contact/about/team pages. Pure stdlib.
Reads harvest5_deduped.json -> writes harvest5_sitescrape.json.
"""
import json, re, time, sys, urllib.request, urllib.error
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_EMAIL_HINT = ("example.com", "sentry", "wixpress", "godaddy", "@2x", ".png", ".jpg",
                  ".gif", ".webp", "domain.com", "email.com", "yourdomain", "squarespace",
                  "cloudflare", "schema.org", "w3.org", "googleapis", "gstatic",
                  "yourbusiness", "youremail", "sentry.io", "wix.com", "jpeg", "@x.",
                  "mail.com", "core.com", "gafs.com", "eyebytes.com")

# generic local-parts that are NOT a person
GENERIC_LOCALS = {"info", "office", "contact", "hello", "admin", "reception", "frontdesk",
                  "front.desk", "booking", "bookings", "team", "support", "sales", "billing",
                  "help", "mail", "service", "intake", "scheduling", "schedule", "newpatient",
                  "appointments", "appointment", "estimate", "estimates", "quotes", "quote",
                  "dispatch", "accounting", "hr", "careers", "jobs", "marketing", "webmaster",
                  "noreply", "no-reply", "donotreply", "general", "main", "frontoffice",
                  "customerservice", "client", "clients", "reviews", "feedback", "press",
                  "media", "legal", "privacy", "abuse", "postmaster", "inquiries", "inquiry",
                  "ar", "ap", "invoices", "payments", "pay", "store", "shop", "orders"}

SLA_PATTERNS = [
    r"within\s+24\s*hours?", r"within\s+48\s*hours?", r"next\s+business\s+day",
    r"one\s+business\s+day", r"1\s+business\s+day", r"get\s+back\s+to\s+you\s+(?:as\s+soon|soon|shortly|within)",
    r"respond\s+within\s+\d+\s*(?:hours?|business\s+days?)", r"reply\s+within\s+\d+",
    r"24[\-\s]?48\s*hours?",
]

CONTACT_PATHS = ("/contact", "/contact-us", "/contact-us/", "/contactus",
                 "/about", "/about-us", "/about-us/", "/aboutus",
                 "/team", "/our-team", "/our-team/", "/meet-the-team", "/meet-our-team",
                 "/staff", "/our-staff", "/attorneys", "/our-attorneys", "/people")

# ---- owner-name detection ----------------------------------------------------
# common owner/principal trigger words near a person's name
OWNER_TRIGGERS = re.compile(
    r"(owner|founder|co-?founder|principal|president|proprietor|managing\s+partner|"
    r"managing\s+member|owned\s+and\s+operated\s+by|founded\s+by|started\s+by|"
    r"lead\s+attorney|managing\s+attorney|ceo)\b", re.I)

# A plausible human full name: First [Middle/Initial] Last (capitalized words)
NAME_NEAR = re.compile(r"\b([A-Z][a-z]{1,14})\s+(?:[A-Z]\.?\s+)?([A-Z][a-z]{1,16})\b")

# A reasonable set of NON-name capitalized words to reject as a "first name"
NOT_A_NAME = {
    "The", "Our", "Your", "We", "Us", "Home", "About", "Contact", "Team", "Meet",
    "Service", "Services", "Heating", "Cooling", "Plumbing", "Roofing", "Air", "Law",
    "Legal", "Office", "Offices", "Firm", "Group", "Associates", "Company", "Inc",
    "Llc", "Pllc", "Pc", "Co", "And", "Family", "Personal", "Injury", "Attorney",
    "Attorneys", "Lawyer", "Lawyers", "Client", "Clients", "Free", "Call", "Today",
    "New", "Mexico", "Colorado", "Texas", "Springs", "Paso", "Fresno", "Albuquerque",
    "Greenville", "Best", "Top", "Quality", "Trusted", "Local", "Emergency", "Repair",
    "Installation", "Commercial", "Residential", "Heater", "Furnace", "Conditioning",
    "Conditioner", "Drain", "Sewer", "Water", "Comfort", "Mechanical", "Electric",
    "Electrical", "Construction", "Contractors", "Contractor", "Solutions", "Systems",
    "Read", "More", "Learn", "Get", "Schedule", "Book", "Request", "Estimate", "Quote",
    "Privacy", "Policy", "Terms", "Reviews", "Review", "Testimonials", "Gallery",
    "Areas", "Served", "Financing", "Specials", "Coupons", "Careers", "Blog", "Faq",
    "Hours", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    "Sunday", "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "North", "South", "East", "West",
    "United", "States", "America", "Google", "Facebook", "Yelp", "Twitter", "Instagram",
    "Lead", "Managing", "Partner", "President", "Owner", "Founder", "Principal", "Ceo",
    "Senior", "Junior", "Master", "Certified", "Licensed", "Insured", "Bonded", "Trade",
}

# A whitelist-ish guard: a token is a plausible FIRST name if it's alphabetic, 2<len<13,
# capitalized, not in NOT_A_NAME, and not a business/role word.
BIZ_WORD_FRAG = ("law", "legal", "firm", "heating", "cooling", "hvac", "roof", "plumb",
                 "spa", "clinic", "dental", "dent", "medi", "crew", "office", "team",
                 "group", "associat", "construction", "aesthetic", "skin", "injury",
                 "divorce", "mechanic", "electric", "comfort", "service", "system",
                 "contract", "solution", "drain", "sewer", "furnace")

def plausible_first(tok):
    if not tok or not tok.isalpha():
        return False
    if not (2 < len(tok) < 13):
        return False
    if tok in NOT_A_NAME:
        return False
    low = tok.lower()
    if any(b in low for b in BIZ_WORD_FRAG):
        return False
    return True

def fetch(url, timeout=18):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                    "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("Content-Type", "")
            if "html" not in ct and "text" not in ct:
                return ""
            return r.read(800000).decode("utf-8", "ignore")
    except Exception:
        return ""

def good_email(e):
    el = e.lower()
    if any(b in el for b in BAD_EMAIL_HINT):
        return False
    if el.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")):
        return False
    if el.count("@") != 1:
        return False
    return True

def is_personal_local(local):
    """True if the local-part looks like a person (not a generic role inbox)."""
    l = local.lower()
    if l in GENERIC_LOCALS:
        return False
    # firstname.lastname / firstname_lastname / first-last
    if re.match(r"^[a-z]{2,}[._\-][a-z]{2,}$", l):
        # make sure neither half is a generic word
        parts = re.split(r"[._\-]", l)
        if not any(p in GENERIC_LOCALS for p in parts):
            return True
    # single token that is a plausible name (alpha, 3-11 chars, not generic, not biz word)
    if l.isalpha() and 2 < len(l) < 12 and l not in GENERIC_LOCALS \
            and not any(b in l for b in BIZ_WORD_FRAG):
        return True
    return False

def pick_email(emails, domain):
    """Choose best on-domain email: personal > generic ranked > any on-domain > any.
    Returns (email, source_tag)."""
    dl = domain.lower()
    ondom = [e for e in emails if e.lower().split("@")[-1].endswith(dl)]
    pool = ondom if ondom else emails
    if not pool:
        return None, None
    # split personal vs generic
    personal = [e for e in pool if is_personal_local(e.split("@")[0])]
    if personal:
        # prefer first.last over single-token (slightly more confidently a real person)
        personal.sort(key=lambda e: (0 if re.search(r"[._\-]", e.split("@")[0]) else 1,
                                      len(e)))
        tag = "site-personal" + ("" if ondom else "-offdomain")
        return personal[0], tag
    # else ranked generic
    pref = ["info", "office", "contact", "hello", "admin", "reception", "frontdesk"]
    def rank(e):
        loc = e.lower().split("@")[0]
        return pref.index(loc) if loc in pref else 50
    pool_sorted = sorted(set(pool), key=rank)
    tag = "site-generic" + ("" if ondom else "-offdomain")
    return pool_sorted[0], tag

def name_from_email(email):
    """If the chosen email IS personal, try to recover a first name from it."""
    if not email or "@" not in email:
        return None
    local = email.split("@")[0].lower()
    if local in GENERIC_LOCALS:
        return None
    cand = re.split(r"[._\-0-9]", local)[0]
    if plausible_first(cand.capitalize()) and cand.isalpha():
        # avoid initial+surname: single leading consonant + 4+ letters, no separator
        if not re.search(r"[._\-]", local) and len(local) >= 5 and local[0] not in "aeiou":
            known = {"chris","craig","brian","brent","grant","shane","steve","frank",
                     "glenn","wayne","scott","trent","blake","bruce","david","derek",
                     "keith","kevin","kyle","mark","nick","paul","ryan","sean","todd",
                     "tyler","chad","drew","seth","cole","dale","gary","greg","jack",
                     "joel","juan","luis","jose","raul","omar","saul","noah","alan",
                     "carl","gene","russ","kurt","neil","reed","ross","wade"}
            if local not in known:
                return None
        return cand.capitalize()
    return None

def owner_name_from_html(html):
    """Find an owner/principal first name from page text + JSON-LD. Conservative."""
    # 1) JSON-LD Person / founder / author
    for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(b)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for o in items:
            if not isinstance(o, dict):
                continue
            for key in ("founder", "author", "employee", "member"):
                v = o.get(key)
                cands = v if isinstance(v, list) else [v]
                for c in cands:
                    if isinstance(c, dict) and c.get("@type") in ("Person", "person"):
                        nm = c.get("name") or ""
                        first = nm.strip().split(" ")[0] if nm else ""
                        if plausible_first(first):
                            return first, "jsonld-person"
    # 2) text near an owner/principal trigger
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    for m in OWNER_TRIGGERS.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 60]
        # look for a Name pattern in the window, prefer the one closest to the trigger
        best = None
        for nm in NAME_NEAR.finditer(window):
            first, last = nm.group(1), nm.group(2)
            if plausible_first(first) and last not in NOT_A_NAME:
                best = first
                break
        if best:
            return best, "owner-trigger"
    return None, None

def main():
    rows = json.load(open("harvest5_deduped.json"))
    out = []
    for i, r in enumerate(rows, 1):
        url = r["website"]
        dom = r["domain"]
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        pages = []
        home = fetch(url)
        if home:
            pages.append(home)
        emails = []
        # crawl a few likely contact/about/team pages (cap to keep it polite/fast)
        tried = 0
        for path in CONTACT_PATHS:
            if tried >= 4:
                break
            c = fetch(urljoin(base, path), timeout=12)
            if c:
                pages.append(c)
                tried += 1
            time.sleep(0.25)
        blob = chr(10).join(pages)
        if blob:
            emails += re.findall(EMAIL_RE, blob)
        emails = [e for e in emails if good_email(e)]
        email, esource = pick_email(emails, dom)
        # owner first name: try html triggers/jsonld first, then the email itself
        oname, osrc = owner_name_from_html(blob) if blob else (None, None)
        if not oname:
            en = name_from_email(email)
            if en:
                oname, osrc = en, "email-local"
        hook = find_hook(blob.lower(), r.get("reviewCount")) if blob else \
               find_hook("", r.get("reviewCount"))
        rec = dict(r)
        rec["site_email"] = email
        rec["email_source"] = esource
        rec["owner_first"] = oname
        rec["owner_first_source"] = osrc
        rec["site_hook"] = hook
        rec["emails_found"] = sorted(set(emails))[:8]
        out.append(rec)
        print("[%3d/%d] %-26s mail=%-26s name=%-10s hook=%s" % (
            i, len(rows), dom[:26], (email or "-")[:26], (oname or "-")[:10],
            (hook or "-")[:24]), file=sys.stderr)
        time.sleep(0.4)
    json.dump(out, open("harvest5_sitescrape.json", "w"), ensure_ascii=False, indent=1)
    have = [r for r in out if r.get("site_email")]
    named = [r for r in out if r.get("owner_first")]
    personal = [r for r in out if (r.get("email_source") or "").startswith("site-personal")]
    hooks = [r for r in out if r.get("site_hook")]
    print("DONE. email=%d/%d  personal-inbox=%d  owner-name=%d  hooks=%d/%d" % (
        len(have), len(out), len(personal), len(named), len(hooks), len(out)),
        file=sys.stderr)

def find_hook(html_lower, review_count):
    if review_count is not None and int(review_count) <= 12:
        return f"only {review_count} Google review" + ("" if int(review_count) == 1 else "s")
    for pat in SLA_PATTERNS:
        m = re.search(pat, html_lower)
        if m:
            return f"site says '{m.group(0).strip()}'"
    has_form = ("<form" in html_lower) or ("contact" in html_lower and "name=" in html_lower)
    has_chat = any(w in html_lower for w in ("intercom", "drift", "tawk.to", "livechat",
                                             "tidio", "podium", "live chat", "chat with us"))
    if has_form and not has_chat:
        return "contact form with no instant/auto response"
    return None

if __name__ == "__main__":
    main()
