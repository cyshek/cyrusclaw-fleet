import json, sys, os
from parse_expertise2 import parse

# map source file -> (vertical_label, metro). Only FRESH metros (not in prior batches 1-4).
FILES = {
    # Colorado Springs, CO
    "raw5/pi_coloradosprings_co.html":    ("Personal injury law", "Colorado Springs, CO"),
    "raw5/hvac_coloradosprings_co.html":  ("HVAC", "Colorado Springs, CO"),
    "raw5/roof_coloradosprings_co.html":  ("Roofing", "Colorado Springs, CO"),
    "raw5/plumb_coloradosprings_co.html": ("Plumbing", "Colorado Springs, CO"),
    # Albuquerque, NM
    "raw5/pi_albuquerque_nm.html":        ("Personal injury law", "Albuquerque, NM"),
    "raw5/hvac_albuquerque_nm.html":      ("HVAC", "Albuquerque, NM"),
    "raw5/roof_albuquerque_nm.html":      ("Roofing", "Albuquerque, NM"),
    "raw5/plumb_albuquerque_nm.html":     ("Plumbing", "Albuquerque, NM"),
    # El Paso, TX
    "raw5/pi_elpaso_tx.html":             ("Personal injury law", "El Paso, TX"),
    "raw5/hvac_elpaso_tx.html":           ("HVAC", "El Paso, TX"),
    "raw5/roof_elpaso_tx.html":           ("Roofing", "El Paso, TX"),
    # Fresno, CA (backup depth)
    "raw5/pi_fresno_ca.html":             ("Personal injury law", "Fresno, CA"),
    "raw5/hvac_fresno_ca.html":           ("HVAC", "Fresno, CA"),
    "raw5/roof_fresno_ca.html":           ("Roofing", "Fresno, CA"),
    # Greenville, SC (backup depth)
    "raw5/pi_greenville_sc.html":         ("Personal injury law", "Greenville, SC"),
    "raw5/hvac_greenville_sc.html":       ("HVAC", "Greenville, SC"),
}

allrows = []
for f, (vert, metro) in FILES.items():
    if not os.path.exists(f):
        print("MISSING %s" % f, file=sys.stderr)
        continue
    rows = parse(f)
    for r in rows:
        r["vertical"] = vert
        r["metro"] = metro
    print("%-38s %-22s %d" % (f, vert, len(rows)), file=sys.stderr)
    allrows.extend(rows)

json.dump(allrows, open("harvest5_raw.json", "w"), ensure_ascii=False, indent=1)
print("TOTAL:", len(allrows), file=sys.stderr)
