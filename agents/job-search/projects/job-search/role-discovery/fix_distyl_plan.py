import json, re
from pathlib import Path
plan_path = Path("output/inline-plan-distyl-9b44203a-1398-4a7a-a3a2-2a7c3afd15d3.json")
plan = json.loads(plan_path.read_text())
for r in plan["radios"]:
    if r.get("value") == "__UNRESOLVED__" and "bab5e60e" in r["name"]:
        r["value"] = "New York"
        r["alternates"] = ["new york", "nyc"]
        print("Fixed radio -> New York")
fixed_steps = 0
re_pattern = re.compile(r'(const __payload = )(\[.*?\])(;)', re.DOTALL)
for i, s in enumerate(plan.get("steps", [])):
    fn = s.get("args", {}).get("fn", "")
    if not fn:
        continue
    m = re_pattern.search(fn)
    if not m:
        continue
    try:
        payload = json.loads(m.group(2))
    except Exception:
        continue
    changed = False
    for entry in payload:
        if isinstance(entry, dict) and entry.get("value") == "__UNRESOLVED__" and "bab5e60e" in entry.get("name", ""):
            entry["value"] = "New York"
            entry["alternates"] = ["new york", "nyc"]
            print("  Step", i, "fixed -> New York")
            changed = True
    if changed:
        s["args"]["fn"] = fn[:m.start(2)] + json.dumps(payload) + fn[m.end(2):]
        fixed_steps += 1
print("Fixed", fixed_steps, "step(s)")
for r in plan["radios"]:
    print("  " + r["name"][-8:] + ": " + repr(r["value"]))
plan_path.write_text(json.dumps(plan, indent=2, default=str) + "\n")
print("Done.")
