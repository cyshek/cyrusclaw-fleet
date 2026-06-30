import re, json, sys, html as htmlmod

def clean(s):
    if not s:
        return s
    return htmlmod.unescape(s).strip()

def parse(path):
    raw = open(path, encoding="utf-8", errors="ignore").read()
    blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', raw, re.S)
    out, seen = [], set()
    for b in blocks:
        try:
            d = json.loads(b)
        except Exception:
            continue
        items = d if isinstance(d, list) else [d]
        for o in items:
            if not isinstance(o, dict):
                continue
            if o.get("@type") != "LocalBusiness":
                continue
            nm = clean(o.get("name"))
            url = o.get("url")
            if not nm or not url:
                continue
            if nm in seen:
                continue
            seen.add(nm)
            addr = o.get("address") or {}
            agg = o.get("aggregateRating") or {}
            out.append({
                "name": nm,
                "website": url,
                "phone": clean(o.get("telephone")),
                "city": clean(addr.get("addressLocality")),
                "state": clean(addr.get("addressRegion")),
                "street": clean(addr.get("streetAddress")),
                "reviewCount": agg.get("reviewCount"),
                "ratingValue": agg.get("ratingValue"),
            })
    return out

if __name__ == "__main__":
    allrows = []
    for path in sys.argv[1:]:
        rows = parse(path)
        print("##### %s: %d providers #####" % (path, len(rows)), file=sys.stderr)
        allrows.extend(rows)
    print(json.dumps(allrows, ensure_ascii=False, indent=1))
