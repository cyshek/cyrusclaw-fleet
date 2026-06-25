#!/usr/bin/env python3
"""
Direct Ashby batch runner - uses existing plans, runs _ashby_runner.py for each.
Handles roles with PREP-READY or ABORT-BULLET-REWRITER status that have plans+PDFs.
"""
import json
import os
import subprocess
import sqlite3
from pathlib import Path

WORKDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search")
ROLE_DIR = WORKDIR / "role-discovery"
DB_PATH = WORKDIR / "tracker.db"
APPS_DIR = WORKDIR / "applications/submitted"
VENV_PY = str(ROLE_DIR / ".venv/bin/python3")
RUNNER = str(ROLE_DIR / "_ashby_runner.py")
TODAY = "2026-06-24"

# Role ID -> (plan_file_relative_to_ROLE_DIR, slug)
# All have confirmed plans + staged PDFs
READY_ROLES = [
    # PREP-READY roles with plans already
    (1618, "output/inline-plan-encord-9f97576a-5381-4839-a7cf-ebfa82089a63.json",
     "encord-9f97576a-5381-4839-a7cf-ebfa82089a63"),
    (1622, "output/inline-plan-meticulous-e4f7bc5d-1aac-4ed7-a8c3-b4f96002d416.json",
     "meticulous-e4f7bc5d-1aac-4ed7-a8c3-b4f96002d416"),
    (2140, "output/inline-plan-starbridge-3b0bd418-6de0-4cc1-a8fe-7a409238532c.json",
     "starbridge-3b0bd418-6de0-4cc1-a8fe-7a409238532c"),
    (2576, "output/inline-plan-pointone-834a8648-5581-4d69-80cb-41382928d220.json",
     "pointone-834a8648-5581-4d69-80cb-41382928d220"),
    (2607, "output/inline-plan-authzed-37f620ee-db46-40b8-97a9-c7c5b0c072fe.json",
     "authzed-37f620ee-db46-40b8-97a9-c7c5b0c072fe"),
    (2609, "output/inline-plan-oneschema-0b417842-572a-4524-b3a2-5f9435e9cc12.json",
     "oneschema-0b417842-572a-4524-b3a2-5f9435e9cc12"),
    (2773, "output/inline-plan-vendelux-cfd22eae-ecfe-4060-a862-daa2922ac874.json",
     "vendelux-cfd22eae-ecfe-4060-a862-daa2922ac874"),
    (2787, "output/inline-plan-bobyard-d621c5bb-fe6f-4210-8768-99cacda04c1b.json",
     "bobyard-d621c5bb-fe6f-4210-8768-99cacda04c1b"),
    (2800, "output/inline-plan-cape-602bd208-8d7f-4194-b592-e414962aff0a.json",
     "cape-602bd208-8d7f-4194-b592-e414962aff0a"),
    (2805, "output/inline-plan-starbridge-3b0bd418-6de0-4cc1-a8fe-7a409238532c.json",
     "starbridge-3b0bd418-6de0-4cc1-a8fe-7a409238532c"),
    (2808, "output/inline-plan-console-395c3f5b-759f-4bf1-b6ed-38db7f0c76ee.json",
     "console-395c3f5b-759f-4bf1-b6ed-38db7f0c76ee"),
    (2817, "output/inline-plan-mdcalc-0ac0c07a-7963-4b68-8819-8f7f85503309.json",
     "mdcalc-0ac0c07a-7963-4b68-8819-8f7f85503309"),
    (2821, "output/inline-plan-scaled-cognition-d8aa1291-3b54-4675-a876-42d12347eb23.json",
     "scaled-cognition-d8aa1291-3b54-4675-a876-42d12347eb23"),
    (2907, "output/inline-plan-clera-6464c937-9f80-4b69-8130-87bba4d63a39.json",
     "clera-6464c937-9f80-4b69-8130-87bba4d63a39"),
    (2912, "output/inline-plan-tenex-2a359a2a-d5ed-48e8-96b8-b93826110ee9.json",
     "tenex-2a359a2a-d5ed-48e8-96b8-b93826110ee9"),
    # ABORT-BULLET-REWRITER roles that DO have plans and PDFs
    (933, "output/inline-plan-cursor-66e67c2e-c828-4ddb-a2c0-7d3cb672f19d.json",
     "cursor-66e67c2e-c828-4ddb-a2c0-7d3cb672f19d"),
    (1983, "output/inline-plan-profound-b076c997-0ba3-4d3c-9dc9-ad0b3ed49b05.json",
     "profound-b076c997-0ba3-4d3c-9dc9-ad0b3ed49b05"),
    (2242, "output/inline-plan-skydio-b49e6784-2183-4de4-a0a1-7661203c254a.json",
     "skydio-b49e6784-2183-4de4-a0a1-7661203c254a"),
]

results = {"submitted": [], "recaptcha": [], "error": [], "closed": [], "already_applied": []}


def get_company_role(role_id):
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute("SELECT company, role FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.close()
    return row if row else ("Unknown", "Unknown")


def mark_submitted(role_id, slug, method="ashby-runner"):
    company, role = get_company_role(role_id)
    app_dir = APPS_DIR / slug
    app_dir.mkdir(parents=True, exist_ok=True)
    status_path = app_dir / "STATUS.md"
    status_path.write_text(
        f"STATUS: SUBMITTED\n\nsubmitted_by: auto\napplied_on: {TODAY}\n"
        f"role_id: {role_id}\ncompany: {company}\nrole: {role}\n"
        f"method: {method}\nconfirmation: auto-runner confirmed\n"
    )
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=?, "
        "prep_status='submitted', block_reason=NULL WHERE id=?",
        (TODAY, role_id)
    )
    conn.commit()
    conn.close()
    print(f"  [DB+STATUS updated] {role_id} {company} -> submitted")


def run_role(role_id, plan_rel, slug):
    company, role_name = get_company_role(role_id)
    plan_path = str(ROLE_DIR / plan_rel)

    print(f"\n{'='*50}")
    print(f"ROLE {role_id}: {company} -- {role_name}")
    print(f"Plan: {plan_rel}")

    if not Path(plan_path).exists():
        print(f"  ERROR: Plan file missing: {plan_path}")
        results["error"].append(f"{role_id} ({company}): plan file missing")
        return

    # Verify PDF staged
    try:
        plan_data = json.load(open(plan_path))
        staged = plan_data.get("pdf_path_staged", "")
        if staged and not Path(staged).exists():
            # Try to copy from local path
            local = plan_data.get("pdf_path_local", "")
            if local and Path(local).exists():
                import shutil
                Path(staged).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local, staged)
                print(f"  [PDF re-staged from local]")
            else:
                print(f"  WARNING: staged PDF missing and no local fallback: {staged}")
    except Exception as exc:
        print(f"  WARNING: Could not verify PDF: {exc}")

    env = os.environ.copy()
    env["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"

    try:
        proc = subprocess.run(
            [VENV_PY, RUNNER, plan_path],
            capture_output=True, text=True,
            timeout=300, cwd=str(ROLE_DIR), env=env
        )
        output = proc.stdout + proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        output = "TIMEOUT after 300s"
        exit_code = -1

    log_path = f"/tmp/ashby-role-{role_id}.log"
    with open(log_path, "w") as lf:
        lf.write(output)

    print(f"  Exit: {exit_code}")
    print(f"  Tail:\n{output[-1000:]}")

    success_signals = [
        "FormSubmitSuccess", "submitted successfully", "Application submitted",
        "application was successfully submitted", "SUBMIT SUCCESS"
    ]
    recaptcha_signals = ["RECAPTCHA_SCORE_BELOW_THRESHOLD", "score_below", "recaptcha_score",
                         "RECAPTCHA_SCORE", "captcha score"]
    closed_signals = ["ROLE_CLOSED", "Job no longer available", "no longer accepting",
                      "job is no longer", "position has been filled"]
    already_signals = ["ALREADY_APPLIED", "already applied", "already.applied",
                       "have applied for a position in this domain within the last 90"]

    if exit_code == 0 or any(s in output for s in success_signals):
        print(f"  >>> SUCCESS!")
        mark_submitted(role_id, slug, "ashby-runner")
        results["submitted"].append(f"{role_id} ({company})")
        return

    if any(s in output for s in already_signals):
        print(f"  >>> ALREADY APPLIED")
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE roles SET block_reason='already-applied-within-90d' WHERE id=?", (role_id,))
        conn.commit()
        conn.close()
        results["already_applied"].append(f"{role_id} ({company})")
        return

    if any(s in output for s in closed_signals):
        print(f"  >>> ROLE CLOSED")
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE roles SET status='blocked', block_reason='role-closed' WHERE id=?", (role_id,))
        conn.commit()
        conn.close()
        results["closed"].append(f"{role_id} ({company})")
        return

    if any(s.lower() in output.lower() for s in recaptcha_signals):
        print(f"  >>> RECAPTCHA -- trying residential...")
        env2 = env.copy()
        env2["JOBSEARCH_PROXY_MODE"] = "residential"
        try:
            proc2 = subprocess.run(
                [VENV_PY, RUNNER, plan_path],
                capture_output=True, text=True,
                timeout=300, cwd=str(ROLE_DIR), env=env2
            )
            output2 = proc2.stdout + proc2.stderr
            exit2 = proc2.returncode
        except subprocess.TimeoutExpired:
            output2 = "TIMEOUT"
            exit2 = -1

        with open(log_path, "a") as lf:
            lf.write("\n\n--- RESIDENTIAL RETRY ---\n" + output2)

        if exit2 == 0 or any(s in output2 for s in success_signals):
            print(f"  >>> SUCCESS (residential)!")
            mark_submitted(role_id, slug, "ashby-runner-residential")
            results["submitted"].append(f"{role_id} ({company}) [residential]")
        else:
            print(f"  >>> RECAPTCHA HARD BLOCK")
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "UPDATE roles SET block_reason='ashby-hard-recaptcha-residential-resistant' WHERE id=?",
                (role_id,)
            )
            conn.commit()
            conn.close()
            results["recaptcha"].append(f"{role_id} ({company})")
        return

    print(f"  >>> UNKNOWN ERROR (exit={exit_code})")
    results["error"].append(f"{role_id} ({company}): exit={exit_code}")


if __name__ == "__main__":
    print(f"Running Ashby direct batch: {len(READY_ROLES)} roles")
    print(f"CDP: http://127.0.0.1:18800\n")

    for role_id, plan_rel, slug in READY_ROLES:
        run_role(role_id, plan_rel, slug)

    print(f"\n{'='*60}")
    print("BATCH COMPLETE")
    print(f"{'='*60}")
    print(f"\nSUBMITTED ({len(results['submitted'])}):")
    for r in results["submitted"]:
        print(f"  + {r}")
    print(f"\nRECAPTCHA HARD ({len(results['recaptcha'])}):")
    for r in results["recaptcha"]:
        print(f"  x {r}")
    print(f"\nROLE CLOSED ({len(results['closed'])}):")
    for r in results["closed"]:
        print(f"  - {r}")
    print(f"\nALREADY APPLIED ({len(results['already_applied'])}):")
    for r in results["already_applied"]:
        print(f"  ~ {r}")
    print(f"\nERRORS ({len(results['error'])}):")
    for r in results["error"]:
        print(f"  ! {r}")
    print(
        f"\nTOTALS: submitted={len(results['submitted'])}, "
        f"recaptcha={len(results['recaptcha'])}, "
        f"closed={len(results['closed'])}, "
        f"already_applied={len(results['already_applied'])}, "
        f"errors={len(results['error'])}"
    )

    with open("/tmp/ashby-batch-results.json", "w") as jf:
        json.dump(results, jf, indent=2)
    print("\nResults saved to /tmp/ashby-batch-results.json")
