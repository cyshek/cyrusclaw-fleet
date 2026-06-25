import json, re, sys, subprocess, concurrent.futures as cf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def fetch(url, t=18):
    try:
        out = subprocess.run(["curl","-sL","--max-time",str(t),"--compressed",
                              "-A",UA,"-H","Accept-Language: en-US,en;q=0.9", url],
                             capture_output=True, timeout=t+5)
        return out.stdout.decode("utf-8","ignore")
    except Exception:
        return ""

BOOKING = ["calendly","vagaro","acuityscheduling","squareup.com/appointments","book.nexhealth","nexhealth","localmed","getweave","boulevard","blvd.co","mangomint","aestheticrecord","janeapp","setmore","schedulicity","zocdoc","book now","book online","book appointment","schedule online","request appointment","request an appointment","online scheduling"]
CHAT = ["podium","birdeye","tidio","intercom","drift.com","tawk.to","livechat","gohighlevel","leadconnector","hubspot.com/conversations","olark","gorgias","kustomer","chat widget","textus","weave"]
SLOWLANG = [r"within\s+24\s*hours", r"within\s+48\s*hours", r"within\s+72\s*hours",
            r"1\s*-?\s*2\s*business\s*days", r"one\s+business\s+day", r"24-48\s*hours",
            r"24\s*to\s*48\s*hours", r"get\s+back\s+to\s+you\s+(as\s+soon|within|shortly|soon)",
            r"respond\s+within", r"reply\s+within", r"we['’]?ll\s+be\s+in\s+touch"]
FORMHINT = ["wpforms","gravity","gform","contact-form-7","wpcf7","hubspotform","jotform","formstack","typeform","ninja_forms","<form"]

def analyze(url):
    html = fetch(url)
    res = {"ok": bool(html), "emails": [], "booking": False, "chat": False, "slow": None,
           "form": False, "phone": None, "platform": None, "len": len(html)}
    if not html:
        # try contact page guess
        return res
    low = html.lower()
    # emails
    em = re.findall(r'mailto:([^"\'<> ?]+@[^"\'<> ?]+)', html, re.I)
    em = [e.strip().lower() for e in em if "@" in e and not e.lower().endswith((".png",".jpg"))]
    # also bare emails in text
    bare = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', html)
    for b in bare:
        bl=b.lower()
        if bl not in em and not bl.endswith((".png",".jpg",".gif",".jpeg",".webp",".svg",".css",".js")) and "sentry" not in bl and "example" not in bl and "wixpress" not in bl and "@2x" not in bl:
            em.append(bl)
    # prioritize role-based
    def rank(e):
        for i,k in enumerate(["info@","office@","contact@","hello@","frontdesk@","reception@","admin@","appointments@","newpatients@","intake@"]):
            if e.startswith(k): return i
        return 50
    em = sorted(set(em), key=rank)
    res["emails"] = em[:3]
    res["booking"] = any(k in low for k in BOOKING)
    res["chat"] = any(k in low for k in CHAT)
    for pat in SLOWLANG:
        m = re.search(pat, low)
        if m:
            res["slow"] = m.group(0)[:40]; break
    res["form"] = any(k in low for k in FORMHINT)
    ph = re.findall(r'tel:\+?([0-9().\- ]{7,})', html)
    if ph: res["phone"] = ph[0].strip()
    for plat,kw in [("Wix","wix.com"),("Squarespace","squarespace"),("WordPress","wp-content"),("GoDaddy","godaddy"),("Webflow","webflow"),("Duda","dudaone"),("Weebly","weebly")]:
        if kw in low: res["platform"]=plat; break
    return res

def work(c):
    site=c.get("website")
    if not site:
        c["enrich"]={"ok":False}; return c
    a=analyze(site)
    # if no email on homepage, try /contact
    if a["ok"] and not a["emails"]:
        base=site.rstrip("/")
        for path in ["/contact","/contact-us","/contact/","/contact-us/"]:
            h2=fetch(base+path,12)
            if h2:
                em=re.findall(r'mailto:([^"\'<> ?]+@[^"\'<> ?]+)', h2, re.I)
                bare=re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', h2)
                cand=[e.lower() for e in em]+[b.lower() for b in bare]
                cand=[e for e in cand if not e.endswith((".png",".jpg",".gif",".jpeg",".webp",".svg",".css",".js")) and "sentry" not in e and "wixpress" not in e and "@2x" not in e]
                if cand:
                    def rank(e):
                        for i,k in enumerate(["info@","office@","contact@","hello@","frontdesk@","reception@","admin@","appointments@"]):
                            if e.startswith(k): return i
                        return 50
                    a["emails"]=sorted(set(cand),key=rank)[:3]
                    if not a.get("slow"):
                        for pat in SLOWLANG:
                            m=re.search(pat,h2.lower())
                            if m: a["slow"]=m.group(0)[:40]; break
                    break
    c["enrich"]=a
    return c

if __name__=="__main__":
    cands=json.load(open("candidates.json"))
    # optional slice
    if len(sys.argv)>2:
        cands=cands[int(sys.argv[1]):int(sys.argv[2])]
    out=[]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for c in ex.map(work, cands):
            out.append(c)
            e=c.get("enrich",{})
            sys.stderr.write("%-40s ok=%s email=%s book=%s chat=%s slow=%s\n" % (
                (c["name"][:38]), e.get("ok"), (e.get("emails") or ["-"])[0][:28], e.get("booking"), e.get("chat"), bool(e.get("slow"))))
    json.dump(out, open(sys.argv[3] if len(sys.argv)>3 else "enriched.json","w"), ensure_ascii=False, indent=0)
    sys.stderr.write("WROTE %d\n"%len(out))
