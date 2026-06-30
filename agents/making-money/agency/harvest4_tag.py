import json, sys
from parse_expertise2 import parse

# map source file -> (vertical_label, metro)
FILES = {
    "raw/pi_reno_nv.html":        ("Personal injury law", "Reno, NV"),
    "raw/pi_fortcollins_co.html": ("Personal injury law", "Fort Collins, CO"),
    "raw/hvac_reno_nv.html":      ("HVAC", "Reno, NV"),
    "raw/hvac_tacoma_wa.html":    ("HVAC", "Tacoma, WA"),
    "raw/roof_fortcollins_co.html": ("Roofing", "Fort Collins, CO"),
    "raw/roof_tacoma_wa.html":    ("Roofing", "Tacoma, WA"),
}

allrows = []
for f, (vert, metro) in FILES.items():
    rows = parse(f)
    for r in rows:
        r["vertical"] = vert
        r["metro"] = metro
    print("%-32s %-22s %d" % (f, vert, len(rows)), file=sys.stderr)
    allrows.extend(rows)

json.dump(allrows, open("harvest4_raw.json", "w"), ensure_ascii=False, indent=1)
print("TOTAL:", len(allrows), file=sys.stderr)
