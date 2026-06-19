import subprocess, json, re, time, urllib.request, ssl

TARGETS = [
    {"domain": "csgcpa.com", "vertical": "accounting"},
    {"domain": "perrymancpa.com", "vertical": "accounting"},
    {"domain": "kgacpa.com", "vertical": "accounting"},
    {"domain": "nwbcpa.com", "vertical": "accounting"},
    {"domain": "murphymcpa.com", "vertical": "accounting"},
    {"domain": "sunrisebuildersco.com", "vertical": "construction"},
    {"domain": "peakconstruction.com", "vertical": "construction"},
    {"domain": "apexbuilders.com", "vertical": "construction"},
    {"domain": "bridgewoodconstruction.com", "vertical": "construction"},
    {"domain": "azhomeconstruction.com", "vertical": "construction"},
    {"domain": "greasemonkeyauto.com", "vertical": "auto_repair"},
    {"domain": "garysautorepair.com", "vertical": "auto_repair"},
    {"domain": "mikeautocare.com", "vertical": "auto_repair"},
    {"domain": "aceuraauto.com", "vertical": "auto_repair"},
    {"domain": "proautoservice.com", "vertical": "auto_repair"},
    {"domain": "greenlawncare.com", "vertical": "landscaping"},
    {"domain": "perfectlawn.com", "vertical": "landscaping"},
    {"domain": "texaslandscapepros.com", "vertical": "landscaping"},
    {"domain": "premierlawn.com", "vertical": "landscaping"},
    {"domain": "eliteoutdoorliving.com", "vertical": "landscaping"},
    {"domain": "bugbusters.com", "vertical": "pest_control"},
    {"domain": "pestproservice.com", "vertical": "pest_control"},
    {"domain": "allpestcontrol.com", "vertical": "pest_control"},
    {"domain": "safeguardpest.com", "vertical": "pest_control"},
    {"domain": "pestfreehome.com", "vertical": "pest_control"},
]

def fetch_page(url, timeout=10):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)'}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None

def find_email(html):
    if not html:
        return None
    emails = re.findall(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html)
    valid = [e for e in emails if not re.search(r'(noreply|no-reply|donotreply|example|unsubscribe)', e, re.I)]
    return valid[0] if valid else None

def check_mx(domain):
    try:
        r = subprocess.run(['dig', 'MX', domain, '+short'], capture_output=True, text=True, timeout=5)
        return bool(r.stdout.strip())
    except Exception:
        return False

def check_seo(html):
    if not html:
        return "viewport"
    if not re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I):
        return "viewport"
    if not re.search(r'og:image', html, re.I):
        return "share"
    if not re.search(r'<meta[^>]+name=["\']description["\']', html, re.I):
        return "meta_desc"
    if not re.search(r'<h1[\s>]', html, re.I):
        return "h1"
    return "h1"

for b in TARGETS:
    domain = b['domain']
    print(f"Processing {domain}...", flush=True)
    homepage_html = None
    for proto in ['https', 'http']:
        html = fetch_page(f"{proto}://{domain}/")
        if html and len(html) > 200:
            homepage_html = html
            b['reachable'] = True
            break
    if not homepage_html:
        b['reachable'] = False
        b['email'] = None
        b['source'] = None
        b['seo_fail'] = None
        print(f"  -> NOT REACHABLE", flush=True)
        time.sleep(0.2)
        continue
    b['seo_fail'] = check_seo(homepage_html)
    email = find_email(homepage_html)
    source = "scraped" if email else None
    if not email:
        for path in ['/contact', '/contact-us', '/contact.html', '/about', '/about-us']:
            contact_html = fetch_page(f"https://{domain}{path}")
            if contact_html:
                email = find_email(contact_html)
                if email:
                    source = "scraped"
                    break
            time.sleep(0.1)
    if not email:
        if check_mx(domain):
            email = f"info@{domain}"
            source = "mx_pattern"
    b['email'] = email
    b['source'] = source
    print(f"  -> email={email}, seo={b.get('seo_fail')}", flush=True)
    time.sleep(0.3)

with open('outreach/biz_results.json', 'w') as fout:
    json.dump(TARGETS, fout, indent=2)
reachable = sum(1 for b in TARGETS if b.get('reachable'))
with_email = sum(1 for b in TARGETS if b.get('email'))
print(f"Done. Reachable={reachable}, With email={with_email}", flush=True)
