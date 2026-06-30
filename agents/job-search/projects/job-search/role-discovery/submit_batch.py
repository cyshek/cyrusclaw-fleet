#!/usr/bin/env python3
"""
submit_batch.py - Submit all prepped GH roles in this batch.
Handles both native greenhouse (_gh_submit.py) and iframe (greenhouse_iframe_runner.py).
Updates DB and writes STATUS.md on success.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SUBMITTED = ROOT / "applications" / "submitted"
DB_PATH = ROOT / "tracker.db"
VENV_PY = str(SCRIPT_DIR / ".venv" / "bin" / "python")
RESULTS_FILE = Path("/tmp/gh_drain_results.txt")

# (role_id, plan_path, company, role_name, ats)
ROLES = [
    # Native greenhouse
    (1375, "output/inline-plan-anduril-5142847007.json",        "Anduril",         "Program Manager - SkillBridge",             "greenhouse"),
    (2670, "output/inline-plan-scopely-5222228008.json",         "Scopely",         "Associate Manager, Product Management",      "greenhouse"),
    (3164, "output/inline-plan-sigma-computing-7767726003.json", "Sigma Computing", "Solution Engineer",                          "greenhouse"),
    (3506, "output/inline-plan-canonical-7490812.json",          "Canonical",       "Public Cloud Solution Architect",            "greenhouse"),
    (3507, "output/inline-plan-canonical-6969562.json",          "Canonical",       "Ubuntu Sales Engineer",                     "greenhouse"),
    # GH Iframe
    (877,  "output/inline-plan-stripe-7815794.json",             "Stripe",          "Collections Program Manager",               "greenhouse_iframe"),
    (3021, "output/inline-plan-stripe-7975723.json",             "Stripe",          "Solutions Architect, AI",                   "greenhouse_iframe"),
    (3025, "output/inline-plan-stripe-7377101.json",             "Stripe",          "Technical Solutions Engineer",              "greenhouse_iframe"),
    (3105, "output/inline-plan-brex-8443298002.json",            "Brex",            "Engineering Program Manager, AI",           "greenhouse_iframe"),
    (3369, "output/inline-plan-waymo-7922962.json",              "Waymo",           "Product Manager, Mapping (Data Quality)",   "greenhouse_iframe"),
    (3371, "output/inline-plan-waymo-7902413.json",              "Waymo",           "Product Manager, Pickup and Dropoff",       "greenhouse_iframe"),
    (3372, "output/inline-plan-waymo-7917617.json",              "Waymo",           "Program Manager, Mapping Operations",       "greenhouse_iframe"),
    (3373, "output/inline-plan-waymo-7939648.json",              "Waymo",           "Program Manager, Risk & Insurance",         "greenhouse_iframe"),
    (3374, "output/inline-plan-waymo-7403855.json",              "Waymo",           "Technical PM, Onboard Systems",             "greenhouse_iframe"),
    (3375, "output/inline-plan-waymo-7733791.json",              "Waymo",           "TPM, Systems Engineering",                  "greenhouse_iframe"),
    (3446, "output/inline-plan-ixl-learning-8444833002.json",    "IXL Learning",   "Product Manager, Digital Marketing",        "greenhouse_iframe"),
    (3453, "output/inline-plan-intersystems-7679435003.json",    "InterSystems",    "Innovation Program Manager",                "greenhouse_iframe"),
    (3455, "output/inline-plan-intersystems-7735610003.json",    "InterSystems",    "Sales Engineer",                            "greenhouse_iframe"),
    (3456, "output/inline-plan-intersystems-7735588003.json",    "InterSystems",    "Sales Engineer - Financial Services",       "greenhouse_iframe"),
]


def extract_status(output: str) -> str:
    """Try to extract the 'status' field from JSON output."""
    # Look for JSON blocks containing 'status'
    matches = list(re.finditer(r'\{[^{}]*"status"[^{}]*\}', output, re.DOTALL))
    if matches:
        for m in reversed(matches):
            try:
                d = json.loads(m.group())
                return d.get("status", "unknown")
            except Exception:
                pass
    # Try line-by-line JSON
    for line in reversed(output.strip().split("\n")):
        try:
            d = json.loads(line)
            if "status" in d:\n                return d["status"]
        except Exception:
            pass
    # Regex fallback
    m = re.search(r'"status":\s*"([^"]+)"', output)
    if m:\n        return m.group(1)\n    return "unknown"


def extract_confirm_url(output: str) -> str:
    """Extract confirmation URL from output."""
    # Look for final.url in JSON
    m = re.search(r'"final"[^}]*"url":\s*"([^"]+)"', output, re.DOTALL)
    if m:\n        return m.group(1)\n    # Look for any confirmation-ish URL\n    m = re.search(r'confirmation[^"]*":\s*"([^"]+)"', output)
    if m:\n        return m.group(1)\n    # Last "url" field
    urls = re.findall(r'"url":\s*"([^"]+)"', output)
    if urls:
        return urls[-1]
    return "n/a"


def write_status_md(workdir: Path, role_id: int, company: str, role_name: str, confirm_url: str):
    workdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = f"""STATUS: SUBMITTED
confirmation_url: {confirm_url}
submitted_by: auto
resume_attached: true
submitted_at: {ts}
role_id: {role_id}
company: {company}
role: {role_name}
"""
    (workdir / "STATUS.md").write_text(content)
    print(f"  Wrote STATUS.md to {workdir}")


def update_db(role_id: int):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now') WHERE id=?",
        (role_id,)
    )
    conn.commit()
    conn.close()
    print(f"  Updated tracker.db for role {role_id}")


def submit_role(role_id: int, plan_rel: str, company: str, role_name: str, ats: str) -> str:
    """Submit a single role. Returns 'SUBMITTED' or error status."""
    plan_path = str(SCRIPT_DIR / plan_rel)
    
    if not os.path.exists(plan_path):
        return f"PLAN-NOT-FOUND:{plan_rel}"

    plan = json.load(open(plan_path))
    slug = plan["slug"]
    workdir = SUBMITTED / slug

    print(f"\n{'='*60}")
    print(f"  Role {role_id}: {company} / {role_name}")
    print(f"  ATS: {ats}, Slug: {slug}")
    print(f"  Plan: {plan_rel}")

    if ats == "greenhouse":
        cmd = [VENV_PY, str(SCRIPT_DIR / "_gh_submit.py"), plan_path]
    else:
        cmd = [VENV_PY, str(SCRIPT_DIR / "greenhouse_iframe_runner.py"), "--slug", slug]

    print(f"  CMD: {' '.join(cmd)}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(SCRIPT_DIR),
        )
        output = proc.stdout + "\n" + proc.stderr
        status = extract_status(output)
        print(f"  Exit: {proc.returncode}, Status: {status}")

        if status == "SUBMITTED":
            confirm_url = extract_confirm_url(output)
            print(f"  ✅ SUBMITTED! Confirm URL: {confirm_url}")
            write_status_md(workdir, role_id, company, role_name, confirm_url)
            update_db(role_id)
        else:
            print(f"  ❌ Failed: {status}")
            # Save debug log
            log_path = f"/tmp/gh_fail_{role_id}.log"
            Path(log_path).write_text(output)
            print(f"  Debug log: {log_path}")

        return status

    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:\n        return f"ERROR:{e}"


def main():
    results = {"submitted": [], "failed": [], "closed": []}
    
    print(f"=== GH Batch Submit {datetime.now()} ===")
    print(f"Total roles to submit: {len(ROLES)}")

    for role_id, plan_rel, company, role_name, ats in ROLES:
        status = submit_role(role_id, plan_rel, company, role_name, ats)
        if status == "SUBMITTED":
            results["submitted"].append((role_id, company, role_name))
        else:
            results["failed"].append((role_id, company, role_name, status))

    # Write results file
    lines = [f"=== GH Batch Submit Results {datetime.now()} ===\n"]
    lines.append(f"\n--- SUBMITTED ({len(results['submitted'])}) ---\n")
    for rid, co, ro in results["submitted"]:
        lines.append(f"  ✅ {co}: {ro} (id={rid})\n")
    lines.append(f"\n--- FAILED ({len(results['failed'])}) ---\n")
    for rid, co, ro, st in results["failed"]:
        lines.append(f"  ❌ {co}: {ro} (id={rid}) -> {st}\n")

    RESULTS_FILE.write_text("".join(lines))
    print("\n" + "".join(lines))
    print(f"Results written to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
