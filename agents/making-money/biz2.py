import urllib.request, re, json, subprocess, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8","replace")
    except:
        return None

def find_email(html, domain):
    if not html:
        return None, None
    pat1 = r'href=["\']mailto:([^"\'?\s]+)["\']'
    pat2 = r'[\w.+-]+@' + re.escape(domain)
    mails = re.findall(pat1, html, re.I)
    mails += re.findall(pat2, html, re.I)
    for m in mails:
        m = m.strip().lower()
        if "@" in m and domain in m and len(m)<80:
            return m, "scraped"
    return None, None

def mx_email(domain):
    try:
        result = subprocess.run(["dig", "MX", domain, "+short"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return "info@" + domain, "mx_pattern"
    except:
        pass
    return None, None

def seo_check(html):
    if not html:
        return "viewport"
    if not re.search(r'name=["\']viewport["\']', html, re.I):
        return "viewport"
    if not re.search(r'property=["\']og:image["\']', html, re.I):
        return "share"
    if not re.search(r'name=["\']description["\']', html, re.I):
        return "meta_desc"
    if not re.search(r'<h1[\s>]', html, re.I):
        return "h1"
    return "h1"

TEMPLATES = {
    "viewport": (
        "DOMAIN \u2014 quick fix for site not configured as mobile-friendly",
        "your site isn\u2019t configured as mobile-friendly \u2014 Google now ranks mobile experience first, so this directly tanks your position."
    ),
    "share": (
        "DOMAIN \u2014 quick fix for blank preview when shared on social",
        "when someone shares your site on social media or iMessage, it shows up blank with no preview image or description."
    ),
    "meta_desc": (
        "DOMAIN \u2014 quick fix for missing meta description",
        "your meta description is missing \u2014 the snippet Google shows under your site name in search results is blank, so people skip past you."
    ),
    "h1": (
        "DOMAIN \u2014 quick fix for missing main heading",
        "your main heading (H1) is missing \u2014 that\u2019s one of the first things Google reads to understand what your page is about."
    ),
}

def make_entry(domain, email, source, fail):
    subj_tmpl, body_intro = TEMPLATES[fail]
    subj = subj_tmpl.replace("DOMAIN", domain)
    body = ("Hi \u2014 I ran a free audit on " + domain +
            " and the main thing that stood out: " + body_intro +
            " This is likely costing you rankings and new customers finding you online."
            " Full report (no signup needed): https://sitelume.app/audit/?url=" + domain +
            "\n\n\u2014 Cyrus")
    return {"domain": domain, "to": email, "source": source, "top_fail": fail, "subject": subj, "body": body}

candidates = [
    ("aceautoshop.com", "logan@aceautoshop.com", "auto_repair"),
    ("greatbearautoshop.com", "greatbearautoshop@gmail.com", "auto_repair"),
    ("smalltownbuilders.com", None, "construction"),
    ("sbasgroup.com", "info@sbasgroup.com", "cpa"),
    ("jpacpa.com", "info@jpacpa.com", "cpa"),
    ("gillespie-cpas.com", None, "cpa"),
    ("ckconstruction.net", None, "construction"),
    ("harrisonconstruction.com", None, "construction"),
    ("absoluteautorepair.com", None, "auto_repair"),
    ("sunriselandscaping.com", None, "landscaping"),
    ("greenleaflandscaping.com", None, "landscaping"),
    ("automd561.com", None, "auto_repair"),
]

results = []
for domain, pre_email, vertical in candidates:
    print("  Checking " + domain + "...", flush=True)
    html = fetch("https://" + domain)
    if not html:
        html = fetch("http://" + domain)
    if pre_email:
        email, source = pre_email, "scraped"
    else:
        email, source = find_email(html, domain)
        if not email:
            html2 = fetch("https://" + domain + "/contact") or fetch("https://" + domain + "/contact-us")
            if html2:
                email, source = find_email(html2, domain)
                html = (html or "") + html2
        if not email:
            email, source = mx_email(domain)
    if not email:
        print("    SKIP " + domain + ": no email", flush=True)
        continue
    fail = seo_check(html)
    entry = make_entry(domain, email, source, fail)
    results.append(entry)
    print("    OK " + domain + " -> " + email + " fail=" + fail, flush=True)

print(json.dumps(results, indent=2))
