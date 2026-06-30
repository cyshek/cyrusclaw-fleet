#!/usr/bin/env python3
"""Scrape each harvested business website for (a) a contact email and (b) a personalization
hook, WITHOUT using Hunter quota. Free fallback for the rows Hunter couldn't cover.

Hook detection mirrors what make_batch2 keys on:
  - low Google review count (from the Expertise listing, already on the row)
  - a slow SLA promise on the site ("within 24 hours", "next business day", "we'll get back")
  - a plain contact form with no instant/chat response
Email detection: mailto: links + email regex on home + likely contact pages.
"""
import json, re, time, sys, urllib.request, urllib.error
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_EMAIL_HINT = ("example.com", "sentry", "wixpress", "godaddy", "@2x", ".png", ".jpg",
                  ".gif", ".webp", "domain.com", "email.com", "yourdomain", "squarespace",
                  "cloudflare", "schema.org", "w3.org", "googleapis", "gstatic")

SLA_PATTERNS = [
    r"within\s+24\s*hours?", r"within\s+48\s*hours?", r"next\s+business\s+day",
    r"one\s+business\s+day", r"1\s+business\s+day", r"get\s+back\s+to\s+you\s+(?:as\s+soon|soon|shortly|within)",
    r"respond\s+within\s+\d+\s*(?:hours?|business\s+days?)", r"reply\s+within\s+\d+",
    r"24[\-\s]?48\s*hours?",
]

def fetch(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("Content-Type", "")
            if "html" not in ct and "text" not in ct:
                return ""
            return r.read(600000).decode("utf-8", "ignore")
    except Exception:
        return ""

def good_email(e, domain_stem):
    el = e.lower()
    if any(b in el for b in BAD_EMAIL_HINT):
        return False
    if el.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")):
        return False
    return True

def pick_site_email(emails, domain):
    """Prefer an email on the business's own domain; then info@/office@; then any."""
    stem = domain.split(".")[0].lower()
    ondom = [e for e in emails if e.lower().split("@")[-1].endswith(domain.lower())]
    pref_order = ["info", "office", "contact", "hello", "admin", "reception", "frontdesk"]
    def rank(e):
        local = e.lower().split("@")[0]
        return pref_order.index(local) if local in pref_order else 50
    if ondom:
        ondom.sort(key=rank)
        return ondom[0]
    if emails:
        emails_sorted = sorted(set(emails), key=rank)
        return emails_sorted[0]
    return None

def find_hook(html_lower, review_count):
    # 1) low review count is the strongest hook
    if review_count is not None and int(review_count) <= 12:
        return f"only {review_count} Google review" + ("" if int(review_count) == 1 else "s")
    # 2) slow SLA promise quoted from the site
    for pat in SLA_PATTERNS:
        m = re.search(pat, html_lower)
        if m:
            return f"site says '{m.group(0).strip()}'"
    # 3) contact form with no instant response (form present, no live chat widget)
    has_form = ("<form" in html_lower) or ("contact" in html_lower and "name=" in html_lower)
    has_chat = any(w in html_lower for w in ("intercom", "drift", "tawk.to", "livechat",
                                             "tidio", "podium", "live chat", "chat with us"))
    if has_form and not has_chat:
        return "contact form with no instant/auto response"
    return None

def main():
    rows = json.load(open("harvest4_deduped.json"))
    out = []
    for i, r in enumerate(rows, 1):
        url = r["website"]
        dom = r["domain"]
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        html = fetch(url)
        emails = []
        if html:
            emails += re.findall(EMAIL_RE, html)
            # also try a contact page
            for path in ("/contact", "/contact-us", "/contact-us/", "/about", "/about-us"):
                if "contact" in html.lower() or path in ("/contact", "/contact-us"):
                    c = fetch(urljoin(base, path), timeout=15)
                    if c:
                        emails += re.findall(EMAIL_RE, c)
                        html += "\n" + c
                    time.sleep(0.4)
                    break
        emails = [e for e in emails if good_email(e, dom)]
        site_email = pick_site_email(emails, dom)
        hook = find_hook(html.lower(), r.get("reviewCount"))
        rec = dict(r)
        rec["site_email"] = site_email
        rec["site_hook"] = hook
        rec["emails_found"] = sorted(set(emails))[:6]
        out.append(rec)
        print("[%2d/%d] %-28s email=%-28s hook=%s" % (
            i, len(rows), dom[:28], (site_email or "-")[:28], hook or "-"), file=sys.stderr)
        time.sleep(0.6)
    json.dump(out, open("harvest4_sitescrape.json", "w"), ensure_ascii=False, indent=1)
    have = [r for r in out if r.get("site_email")]
    hooks = [r for r in out if r.get("site_hook")]
    print("DONE. site_email found: %d/%d ; hooks found: %d/%d" % (
        len(have), len(out), len(hooks), len(out)), file=sys.stderr)

if __name__ == "__main__":
    main()
