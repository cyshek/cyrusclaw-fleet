import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone

WORKDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = WORKDIR.parent / "tracker.db"
SUBMITTED = WORKDIR / "applications" / "submitted"
OUTPUT = WORKDIR / "output"

HARD_COHORT = {
    "bobyard", "characterai", "h-company", "hadrian", "plaud", "scaled-cognition",
    "fluidstack-8fd64f47", "fluidstack-93721a94", "tavus", "moment", "openai", "deepgram",
    "fluidstack-d6cb8be1", "mercor", "baseten", "bedrock-robotics", "decagon",
    "ramp-9972df9e",  # HARD reCAPTCHA: score-below-threshold even via residential (2026-06-23)
}

db = sqlite3.connect(str(DB))
db.row_factory = sqlite3.Row
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _jid_lookup(url):
    m = re.search(r'/jobs/(\d+)', url)
    return db.execute("SELECT id, applied_by FROM roles WHERE app_url LIKE ?", (f"%/jobs/{m.group(1)}%",)).fetchone() if m else None


def find_role(url):
    if not url:
        return None
    for try_url in (url, url.replace("job-boards.greenhouse.io", "boards.greenhouse.io")):
        row = db.execute("SELECT id, applied_by FROM roles WHERE app_url=?", (try_url,)).fetchone()
        if row:
            return row
    return _jid_lookup(url)


staged = 0
skipped = 0
no_row = []

for f in sorted(OUTPUT.glob("inline-plan-*.json")):
    slug = f.stem.replace("inline-plan-", "")
    if any(h in slug for h in HARD_COHORT):
        skipped += 1
        continue
    workdir = SUBMITTED / slug
    status_f = workdir / "STATUS.md"
    if status_f.exists():
        first = status_f.read_text().split("\n")[0]
        if any(x in first for x in ("SUBMITTED", "ABORT", "PREP-READY")):
            skipped += 1
            continue
    try:
        plan = json.loads(f.read_text())
    except Exception:
        continue
    ats = plan.get("ats", "")
    if ats not in ("ashby", "ashby-embed", "greenhouse", "greenhouse_iframe"):
        continue
    url = plan.get("url", plan.get("tenant_embed", ""))
    row = find_role(url)
    if not row:
        no_row.append((slug, ats, url[:70]))
        continue
    if row["applied_by"]:
        skipped += 1
        continue
    role_id = row["id"]
    if "role_id" not in plan:
        plan["role_id"] = role_id
        f.write_text(json.dumps(plan, ensure_ascii=False))
    workdir.mkdir(exist_ok=True)
    tag = "PREP-READY-IFRAME-RUNNER" if ats == "greenhouse_iframe" else "PREP-READY"
    lines = [
        f"{tag} — {NOW}", "",
        f"role_id: {role_id}", f"slug:    {slug}",
        f"plan:    {f}", f"pdf:     {plan.get('pdf_path_local', '')}",
        f"cover:   {plan.get('cover_answers', '')}", "",
    ]
    if ats == "greenhouse_iframe":
        lines.insert(7, f"wrapper: {plan.get('wrapper_url', '')}")
    status_f.write_text("\n".join(lines))
    staged += 1
    print(f"STAGED [{ats}]: {slug} (id={role_id})")

db.close()
print(f"\nStaged: {staged} | skipped: {skipped} | no-row: {len(no_row)}")
for s, a, u in no_row[:15]:
    print(f"  [{a}] {s}: {u}")
