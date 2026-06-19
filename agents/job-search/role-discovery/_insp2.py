import json, sys
d = json.load(open("../applications/dryrun/credera-7967308.json"))
print("KEYS:", list(d.keys()))
for k in ("unresolved","blockers","review","needs_review","declined","fields"):
    if k in d and d[k]:
        print("=== " + k + " (" + str(len(d[k])) + ") ===")
        print(json.dumps(d[k], indent=1)[:3000])
