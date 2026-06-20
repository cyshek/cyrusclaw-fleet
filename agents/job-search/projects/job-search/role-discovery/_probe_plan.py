import json, os, sys, glob

slug = sys.argv[1] if len(sys.argv) > 1 else "eliseai-d400f45b"
base = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"

def show(path, tag):
    d = json.load(open(path))
    print("=== %s: %s ===" % (tag, os.path.basename(path)))
    print("ready_to_submit:", d.get("ready_to_submit"), "| blockers:", d.get("blockers"), "| unresolved:", d.get("unresolved"))
    fields = d.get("fields") or d.get("resolved_fields") or []
    if not fields and isinstance(d.get("dryrun"), dict):
        fields = d["dryrun"].get("fields") or []
    for fld in fields:
        lbl = fld.get("label") or fld.get("name") or fld.get("title")
        st = fld.get("status") or fld.get("resolution") or fld.get("resolved")
        req = fld.get("required")
        val = fld.get("value")
        if val is None:
            val = fld.get("answer")
        bad = (st in ("unresolved", "needs_review", "declined")) or (req and not val)
        mark = "   <<< PROBLEM" if bad else ""
        print("  [%s] req=%s | %r = %r%s" % (st, req, lbl, str(val)[:55], mark))
    print()

matches = sorted(glob.glob(os.path.join(base, "applications/dryrun", "*" + slug + "*")))
for m in matches:
    show(m, "DRYRUN")
if not matches:
    print("NO cached dryrun matching", slug)
