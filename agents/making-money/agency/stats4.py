import json
from collections import Counter
d = json.load(open("harvest4_deduped.json"))
print("By vertical+metro:")
c = Counter((r["vertical"], r["metro"]) for r in d)
for k, v in sorted(c.items()):
    print("  ", k, v)
print()
def bucket(rc):
    if rc is None:
        return "none"
    rc = int(rc)
    if rc <= 12:
        return "a:<=12 (review-gap)"
    if rc <= 40:
        return "b:13-40"
    return "c:40+"
cb = Counter(bucket(r.get("reviewCount")) for r in d)
print("Review-count buckets:")
for k, v in sorted(cb.items()):
    print("  ", k, v)
print()
print("Low-review (<=12) targets:")
for r in d:
    rc = r.get("reviewCount")
    if rc is not None and int(rc) <= 12:
        print("  %-38s %-20s rc=%s  %s" % (r["name"][:38], r["vertical"], rc, r["domain"]))
