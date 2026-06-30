import json, re, csv

def dom(url):
    if not url:
        return ""
    d = re.sub(r"^https?://", "", url.strip(), flags=re.I)
    d = re.sub(r"^www\.", "", d, flags=re.I)
    return d.split("/")[0].split("?")[0].lower()

excluded = set(json.load(open("excluded_domains.json")))
rows = json.load(open("harvest4_raw.json"))

# attach vertical based on source-file naming is lost; infer from known metros+categories.
# Instead re-tag by re-parsing per target file with a label.
seen = set()
kept, dropped_excl, dropped_dup, dropped_nodom = [], [], [], []
for r in rows:
    d = dom(r.get("website"))
    if not d:
        dropped_nodom.append(r); continue
    if d in excluded:
        dropped_excl.append((r["name"], d)); continue
    if d in seen:
        dropped_dup.append((r["name"], d)); continue
    seen.add(d)
    r["domain"] = d
    kept.append(r)

json.dump(kept, open("harvest4_deduped.json", "w"), ensure_ascii=False, indent=1)
print("RAW:", len(rows))
print("KEPT (fresh, unique domain):", len(kept))
print("dropped - already contacted:", len(dropped_excl))
for n, d in dropped_excl:
    print("    EXCL", d, "|", n)
print("dropped - intra-batch dup:", len(dropped_dup))
for n, d in dropped_dup:
    print("    DUP", d, "|", n)
print("dropped - no domain:", len(dropped_nodom))
