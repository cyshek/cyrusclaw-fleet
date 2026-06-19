import json
d = json.load(open("../applications/dryrun/elastic-7960302.json"))
ids={u["id"] for u in d["unresolved"]}
for u in d["unresolved"]: print("UNRESOLVED:", u["id"], "| req=", u.get("required"), "|", u["label"][:90])
print("---field detail---")
for f in d["fields"]:
    if f["id"] in ids:
        print(f["id"], "|", f["type"], "| req=", f.get("required"))
        if f.get("options"): print("   OPTS:", [o.get("label") for o in f["options"]])
