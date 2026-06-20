import json
d = json.load(open("../applications/dryrun/credera-7967308.json"))
qids = {"question_67279824","question_67279829","question_67279830","question_67279831","question_67279834","question_67279835"}
for f in d["fields"]:
    if f["id"] in qids:
        print(f["id"], "|", f["type"], "| req=", f.get("required"), "| label=", f["label"][:50])
        if f.get("options"): print("   OPTIONS:", [o for o in f["options"]])
