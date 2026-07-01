import json, csv, os, re
b5 = json.load(open("batch5_payload.json"))
b5_to = {t["to"].strip().lower() for t in b5}
prior = set()
for sl in ["batch1_sendlog.csv", "batch2_sendlog.csv", "batch3_sendlog.csv",
           "batch4_sendlog.csv"]:
    if os.path.exists(sl):
        for r in csv.DictReader(open(sl)):
            a = (r.get("to") or "").strip().lower()
            if a:
                prior.add(a)
overlap = b5_to & prior
bad = [t["to"] for t in b5 if not re.match(r"^[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}$", t["to"].strip())]
dupes = len(b5) - len(b5_to)
# domain overlap vs excluded_domains.json
excl = set(json.load(open("excluded_domains.json")))
def dom(e):
    return e.split("@")[-1].lower() if "@" in e else ""
dom_overlap = sorted({dom(t["to"]) for t in b5} & excl)
print("batch5 count:", len(b5))
print("unique recipients:", len(b5_to))
print("intra-batch dupes:", dupes)
print("recipient overlap w/ batches 1-4 sendlogs:", len(overlap), sorted(overlap) if overlap else "")
print("DOMAIN overlap w/ excluded_domains.json:", dom_overlap if dom_overlap else "NONE")
print("malformed addresses:", bad if bad else "none")
print("links per email (should all be 0):", sorted({t["body"].count("http") for t in b5}))
print("cal.com links (should be 0):", sum(t["body"].count("cal.com") for t in b5))
