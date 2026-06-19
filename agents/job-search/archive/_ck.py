import json,sys
d=json.load(open(sys.argv[1]))
print("ready_to_submit:", d.get("ready_to_submit"))
print("counts:", d.get("counts"))
print("unresolved:", json.dumps(d.get("unresolved",[]),indent=1)[:800])
print("blockers:", json.dumps(d.get("blockers",[]),indent=1)[:800])
pf=[f for f in d.get("fields",[]) if "portfolio" in (f.get("label","").lower())]
print("PORTFOLIO FIELDS:", json.dumps(pf,indent=1)[:900])
