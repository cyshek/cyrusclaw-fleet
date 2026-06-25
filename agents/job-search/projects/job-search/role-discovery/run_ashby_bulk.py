#!/usr/bin/env python3
"""Batch-run all PREP-READY Ashby roles via residential CDP."""
import subprocess, json, os, sys, sqlite3, datetime, re

WDIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search"
RDIR = f"{WDIR}/role-discovery"
CDP = "http://127.0.0.1:19223"
DB = f"{WDIR}/../tracker.db"
VENV = f"{RDIR}/.venv/bin/python3"
RUNNER = f"{RDIR}/_ashby_runner.py"
PREP_LIST = "/tmp/all_prep_ready.txt"

HARD_COHORT = {"baseten", "mercor", "openai", "tavus", "decagon", "handshake"}


def extract_json(output):
    """Extract the top-level result JSON from runner stdout."""
    m = re.search(r'\{"slug":', output)
    if not m:\n        return None\n    start = m.start()\n    depth = 0\n    end = start\n    in_str = False\n    esc = False\n    for i, c in enumerate(output[start:]):
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"' and not esc:
            in_str = not in_str
        if not in_str:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = start + i + 1
                    break
    try:
        return json.loads(output[start:end])
    except Exception:
        return None


results = {"submitted": [], "spam": [], "already": [], "error": [], "skip": []}

with open(PREP_LIST) as fh:
    lines = [l.strip() for l in fh if l.strip()]

ashby_lines = []
for l in lines:
    parts = l.split('|', 2)
    if len(parts) == 3 and parts[0] == "ashby":
        ashby_lines.append((parts[0], parts[1], parts[2]))

print(f"Found {len(ashby_lines)} Ashby PREP-READY roles")

conn = sqlite3.connect(DB)

for ats, slug, plan_path in ashby_lines:
    company = slug.split('-')[0]
    if company in HARD_COHORT:
        print(f"[SKIP-HARD] {slug}")
        results["skip"].append(slug)
        continue

    status_path = f"{WDIR}/applications/submitted/{slug}/STATUS.md"
    if os.path.exists(status_path):
        with open(status_path) as fh:
            first_line = fh.readline().strip()
        if first_line.startswith("SUBMITTED"):
            print(f"[ALREADY-DONE] {slug}")
            results["already"].append(slug)
            continue

    print(f"\n[RUN] {slug}")
    sys.stdout.flush()

    env = os.environ.copy()
    env["JOBSEARCH_CDP"] = CDP

    try:
        proc = subprocess.run(
            [VENV, RUNNER, plan_path],
            capture_output=True, text=True, timeout=240, env=env
        )
        final = extract_json(proc.stdout)

        if not final:
            print(f"  -> PARSE-FAILED (exit={proc.returncode})")
            print(f"     tail: {proc.stdout[-200:]!r}")
            results["error"].append(slug)
            continue

        classify = final.get("classify", "?")
        ok = final.get("ok", False)
        error = final.get("error", "")

        print(f"  -> ok={ok} classify={classify} error={str(error)[:80]!r}")

        if ok and classify == "submitted":
            role_id = None
            if os.path.exists(status_path):
                with open(status_path) as fh:
                    for line in fh:
                        if line.startswith("role_id:"):
                            role_id = line.split(":")[1].strip()
                            break

            now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            resp = final.get("submit_response", "")
            if "successfully submitted" in resp:
                confirm_text = "Your application was successfully submitted."
            elif "has been received" in resp:
                confirm_text = "Your application has been received."
            elif "Thank you" in resp:
                confirm_text = "Thank you (submitted)"
            else:
                confirm_text = "submitted (classify=submitted)"

            with open(status_path, 'w') as fh:
                fh.write(f"SUBMITTED — {now}\n\n")
                fh.write(f"role_id: {role_id or '?'}\n")
                fh.write(f"slug: {slug}\n")
                fh.write(f"ats: ashby\n")
                fh.write(f"submitted_by: auto (_ashby_runner.py via residential CDP 19223)\n")
                fh.write(f"confirmation: {confirm_text}\n")
                fh.write(f"screenshot: n/a\n")
                fh.write(f"resume_attached: yes\n")

            if role_id:
                conn.execute(
                    "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now') WHERE id=?",
                    (int(role_id),)
                )
                conn.commit()
                print(f"  -> SUBMITTED role_id={role_id}")
            results["submitted"].append(slug)

        elif "spam-flag" in str(error) or classify == "spam-flag":
            print(f"  -> SPAM-FLAGGED (hard cohort)")
            results["spam"].append(slug)
        elif "already-applied" in str(error) or classify == "already-applied":
            print(f"  -> ALREADY APPLIED")
            results["already"].append(slug)
        else:
            results["error"].append(slug)

    except subprocess.TimeoutExpired:
        print(f"  -> TIMEOUT")
        results["error"].append(slug)
    except Exception as ex:
        print(f"  -> EXCEPTION: {ex}")
        results["error"].append(slug)

conn.close()

print("\n" + "=" * 60)
print("RESULTS:")
print(f"  Submitted: {len(results['submitted'])}")
print(f"  Spam-flagged: {len(results['spam'])}")
print(f"  Already applied/done: {len(results['already'])}")
print(f"  Error/timeout: {len(results['error'])}")
print(f"  Skipped (hard): {len(results['skip'])}")
print(f"\nSubmitted: {results['submitted']}")
print(f"Spam: {results['spam']}")
print(f"Errors: {results['error']}")
