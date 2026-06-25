
import re, json, sys

def extract_records(path):
    html = open(path, encoding="utf-8", errors="ignore").read()
    recs = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        blob = m.group(1).strip()
        try:
            data = json.loads(blob)
        except Exception:
            continue
        stack = [data]
        while stack:
            o = stack.pop()
            if isinstance(o, list):
                stack.extend(o)
            elif isinstance(o, dict):
                t = o.get("@type", "")
                if isinstance(t, list):
                    t = " ".join(t)
                if o.get("name") and (o.get("url") or o.get("telephone")) and ("Business" in t or "Organization" in t or "Attorney" in t or "Dentist" in t or "Physician" in t or "MedicalBusiness" in t or "HVAC" in t or "Service" in t or "LegalService" in t or "Store" in t or t==""):
                    addr = o.get("address", {})
                    if isinstance(addr, list):
                        addr = addr[0] if addr else {}
                    rating = o.get("aggregateRating", {}) or {}
                    recs.append({
                        "name": o.get("name"),
                        "website": o.get("url"),
                        "phone": o.get("telephone"),
                        "city": (addr or {}).get("addressLocality"),
                        "state": (addr or {}).get("addressRegion"),
                        "street": (addr or {}).get("streetAddress"),
                        "rating": rating.get("ratingValue"),
                        "reviews": rating.get("reviewCount") or rating.get("ratingCount"),
                    })
                for v in o.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
    # dedupe by name
    seen, out = set(), []
    for r in recs:
        key = (r["name"], r.get("website"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

if __name__ == "__main__":
    allrows = []
    for path in sys.argv[1:]:
        rows = extract_records(path)
        sys.stderr.write("%s -> %d\n" % (path, len(rows)))
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
