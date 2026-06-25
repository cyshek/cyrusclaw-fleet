
import re, json, sys

def parse(path):
    html = open(path, encoding="utf-8", errors="ignore").read()
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        print("NO __NEXT_DATA__ in", path)
        return []
    data = json.loads(m.group(1))
    found = []
    def walk(o):
        if isinstance(o, dict):
            if "website" in o and "name" in o:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    out, seen = [], set()
    for p in found:
        nm = p.get("name")
        if not nm or nm in seen:
            continue
        seen.add(nm)
        out.append({
            "name": nm,
            "website": p.get("website"),
            "phone": p.get("phone") or p.get("telephone"),
            "city": p.get("city") or p.get("addressLocality"),
            "state": p.get("state") or p.get("addressRegion"),
            "street": p.get("streetAddress"),
            "reviewCount": p.get("reviewCount"),
            "ratingValue": p.get("ratingValue"),
        })
    return out

if __name__ == "__main__":
    for path in sys.argv[1:]:
        rows = parse(path)
        print("##### %s: %d providers #####" % (path, len(rows)))
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
