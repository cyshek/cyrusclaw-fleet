import json, sys
d = json.load(open(sys.argv[1]))
print("TOP KEYS:", list(d.keys()))
for fld in ["unresolved","emptyRequired","needs_review","needs_review_dropdowns","blockers","essays","fields"]:
    if fld in d:
        print("==="+fld+"===")
        print(json.dumps(d[fld], indent=1)[:2500])
