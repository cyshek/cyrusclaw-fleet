import json
from pathlib import Path
_PI = json.loads(Path(__file__).resolve().parents[1].joinpath("personal-info.json").read_text())
fp = "output/inline-plan-modern-treasury-5aceb245-03e3-49ea-9f99-14e541f5ad4a.json"
p = json.load(open(fp))
PHONE_ID = "2a7d75fc-0b77-4fee-96dc-1f4c5142a78f_d3d8a905-5394-4379-9b66-8139f4c5ea3e"
LOC_ID = "2a7d75fc-0b77-4fee-96dc-1f4c5142a78f__systemfield_location"
PHONE = _PI["contact"]["phone"]
LOC = "Kirkland, WA"
changed = []
for st in p.get("steps", []):
    if st.get("tool") == "ashby.type_text_fields":
        tf = st.setdefault("args", {}).setdefault("text_fields", {})
        if PHONE_ID not in tf:
            tf[PHONE_ID] = PHONE
            changed.append("phone->type_map")
        # location is a typeahead; add to map too so reassert covers it
        if LOC_ID not in tf:
            tf[LOC_ID] = LOC
            changed.append("location->type_map")
# Remove the two from 'skipped' so they aren't treated as blockers
before = len(p.get("skipped", []))
p["skipped"] = [s for s in p.get("skipped", []) if (s.get("id") not in (PHONE_ID, LOC_ID))]
changed.append(f"skipped {before}->{len(p['skipped'])}")
# Add a location typeahead step hint if the plan supports it: also set in a top-level
# location field if present. The runner's final_clobber_guard fills __systemfield_location
# via _LOCATION_COMBO_FILL_JS defaulting to Kirkland, WA, so the map entry + that path cover it.
json.dump(p, open(fp, "w"), indent=2)
print("patched:", changed)
