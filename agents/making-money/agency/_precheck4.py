import json, csv, os, re
HERE="."
b4=json.load(open("batch4_payload.json"))
b4_to={t["to"].strip().lower() for t in b4}
prior=set()
for sl in ["batch1_sendlog.csv","batch2_sendlog.csv","batch3_sendlog.csv"]:
    if os.path.exists(sl):
        for r in csv.DictReader(open(sl)):
            a=(r.get("to") or "").strip().lower()
            if a: prior.add(a)
overlap=b4_to & prior
bad=[t["to"] for t in b4 if not re.match(r"^[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}$", t["to"].strip())]
dupes=len(b4)-len(b4_to)
print("batch4 count:", len(b4))
print("unique recipients:", len(b4_to))
print("intra-batch dupes:", dupes)
print("overlap w/ batches 1-3:", len(overlap), sorted(overlap) if overlap else "")
print("malformed addresses:", bad if bad else "none")
print("links per email (should all be 1):", sorted({t["body"].count("http") for t in b4}))
