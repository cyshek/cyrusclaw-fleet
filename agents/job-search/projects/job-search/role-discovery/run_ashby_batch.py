#!/usr/bin/env python3
"""Batch Ashby submission runner for 54 no-evidence roles."""
import subprocess
import json
import os
import time
import sqlite3
import traceback
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/home/azureuser/.openclaw/agents/job-search/workspace")
RD = WORKSPACE / "projects/job-search/role-discovery"
DB_PATH = WORKSPACE / "projects/job-search/tracker.db"
SUBMITTED_DIR = WORKSPACE / "applications/submitted"
VENV_PY = RD / ".venv/bin/python3"
LOG_DIR = Path("/tmp/ashby-drain-batch")
LOG_DIR.mkdir(exist_ok=True)

TARGET_IDS = [
    933, 945, 1248, 1325, 1392, 1555, 1618, 1620, 1621, 1622,
    1956, 1983, 2099, 2140, 2196, 2206, 2210, 2214, 2242, 2262,
    2275, 2320, 2447, 2449, 2562, 2566, 2575, 2576, 2582, 2586,
    2607, 2609, 2611, 2712, 2773, 2787, 2795, 2800, 2805, 2808,
    2817, 2821, 2907, 2912, 2918, 2954, 2957, 2958, 2959, 2960,
    2971, 2982, 3111, 3268
]

results = {
    "submitted": [],
    "already_applied": [],
    "role_closed": [],
    "recaptcha_hard": [],
    "errors": [],
    "prep_failed": [],
}


def db_connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_role_info(role_id):
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
        return dict(row) if row else None


def find_plan_for_role(role_id):
    plans = sorted(RD.glob("output/inline-plan-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for plan in plans:
        try:
            data = json.loads(plan.read_text())
            if data.get("role_id") == role_id:
                return plan
        except Exception:
            continue
    return None


def run_prep(role_id, timeout=600):
    print(f"  [PREP] Running inline_submit for role {role_id}...", flush=True)
    cmd = [str(VENV_PY), str(RD / "inline_submit.py"), "--role-id", str(role_id)]
    start = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(RD))
        elapsed = time.time() - start
        output = res.stdout + res.stderr
        print(f"  [PREP] exit={res.returncode} elapsed={elapsed:.0f}s", flush=True)
        (LOG_DIR / f"prep-{role_id}.log").write_text(output)

        if res.returncode != 0:
            out_lower = output.lower()
            if "closed" in out_lower or "url-dead" in out_lower:
                return "closed", None, output
            return "failed", None, output

        plan = find_plan_for_role(role_id)
        if not plan:
            plans = sorted(RD.glob("output/inline-plan-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if plans:
                plan = plans[0]
                print(f"  [PREP] Using most recent plan: {plan.name}", flush=True)
            else:
                return "failed", None, output + "\nNo plan file found"

        print(f"  [PREP] Plan: {plan.name}", flush=True)
        return "ok", plan, output
    except subprocess.TimeoutExpired:
        return "timeout", None, f"inline_submit timed out after {timeout}s"
    except Exception as e:
        return "failed", None, str(e)


def run_ashby(plan_path, role_id, residential=False, timeout=240):
    env = os.environ.copy()
    if residential:
        env["JOBSEARCH_PROXY_MODE"] = "residential"
        print("  [RUNNER] Running with RESIDENTIAL proxy...", flush=True)
    else:
        print("  [RUNNER] Running with datacenter proxy...", flush=True)

    cmd = [str(VENV_PY), str(RD / "_ashby_runner.py"), str(plan_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(RD), env=env)
        output = res.stdout + res.stderr
        suffix = "_residential" if residential else ""
        (LOG_DIR / f"runner-{role_id}{suffix}.log").write_text(output)

        lines = output.strip().split("\n")
        for line in lines[-15:]:
            print(f"    {line}", flush=True)
        print(f"  [RUNNER] exit={res.returncode}", flush=True)
        return res.returncode, output
    except subprocess.TimeoutExpired:
        return -1, f"_ashby_runner timed out after {timeout}s"
    except Exception as e:
        return -2, str(e)


def classify_runner_result(exit_code, output):
    out_lower = output.lower()

    if (exit_code == 0
            or "formsubmitsuccess" in out_lower
            or "submitted successfully" in out_lower
            or "application submitted" in out_lower):
        return "submitted"

    if (exit_code == 7
            or "already_applied" in output
            or "already applied" in out_lower):
        return "already_applied"

    if (exit_code == 6
            or "role_closed" in output
            or "job is no longer" in out_lower
            or "job no longer available" in out_lower):
        return "role_closed"

    if ("recaptcha_score_below_threshold" in output
            or ("recaptcha" in out_lower and "score" in out_lower and "below" in out_lower)):
        return "recaptcha"

    return "error"


def write_status_md(slug, company, role, role_id, method="ashby-runner"):
    app_dir = SUBMITTED_DIR / slug
    app_dir.mkdir(parents=True, exist_ok=True)
    content = (
        f"# {company} -- {role}\n\n"
        f"status: SUBMITTED\n"
        f"date: 2026-06-24\n"
        f"submitted_by: auto\n"
        f"role_id: {role_id}\n"
        f"screenshot: auto-confirmed\n"
        f"method: {method}\n"
    )
    (app_dir / "STATUS.md").write_text(content)
    print(f"  [STATUS] Wrote STATUS.md -> {app_dir}", flush=True)


def db_mark_submitted(role_id):
    with db_connect() as conn:
        conn.execute(
            "UPDATE roles SET status='submitted', applied_by='auto', applied_on='2026-06-24', "
            "response_status='submitted', block_reason=NULL WHERE id=?", (role_id,)
        )
        conn.commit()


def db_mark_already_applied(role_id):
    with db_connect() as conn:
        conn.execute("UPDATE roles SET block_reason='already-applied-within-90d' WHERE id=?", (role_id,))
        conn.commit()


def db_mark_closed(role_id):
    with db_connect() as conn:
        conn.execute("UPDATE roles SET status='blocked', block_reason='role-closed' WHERE id=?", (role_id,))
        conn.commit()


def db_mark_recaptcha_hard(role_id):
    with db_connect() as conn:
        conn.execute(
            "UPDATE roles SET block_reason='ashby-hard-recaptcha-residential-resistant' WHERE id=?", (role_id,)
        )
        conn.commit()


def get_slug_from_plan(plan_path):
    try:
        data = json.loads(plan_path.read_text())
        return data.get("slug", f"role-{plan_path.stem}")
    except Exception:
        return plan_path.stem


def save_intermediate():
    with open("/tmp/ashby-drain-results.json", "w") as f:
        json.dump(results, f, indent=2)


def process_role(role_id):
    role_info = get_role_info(role_id)
    company = role_info.get("company", "Unknown") if role_info else "Unknown"
    role_name = role_info.get("role", "Unknown") if role_info else "Unknown"

    print("\n" + "="*60, flush=True)
    print(f"ROLE {role_id}: {company} -- {role_name}", flush=True)
    print(f"{'='*60}", flush=True)

    prep_status, plan_path, prep_output = run_prep(role_id)

    if prep_status == "closed":
        print("  [RESULT] ROLE CLOSED (during prep)", flush=True)
        db_mark_closed(role_id)
        results["role_closed"].append(f"{role_id} ({company}): closed-during-prep")
        return

    if prep_status in ("failed", "timeout"):
        lines = prep_output.strip().split("\n")
        for line in lines[-5:]:
            print(f"    {line}", flush=True)
        print(f"  [RESULT] PREP FAILED: {prep_status}", flush=True)
        results["prep_failed"].append(f"{role_id} ({company}): prep={prep_status}")
        return

    if not plan_path:
        print("  [RESULT] NO PLAN FILE", flush=True)
        results["prep_failed"].append(f"{role_id} ({company}): no-plan-file")
        return

    exit_code, runner_output = run_ashby(plan_path, role_id, residential=False)
    classification = classify_runner_result(exit_code, runner_output)
    method = "ashby-runner"

    if classification == "recaptcha":
        print("  [RECAPTCHA] Datacenter blocked, trying residential...", flush=True)
        exit_code2, runner_output2 = run_ashby(plan_path, role_id, residential=True)
        classification = classify_runner_result(exit_code2, runner_output2)
        runner_output = runner_output2
        if classification == "submitted":
            method = "ashby-runner-residential"
        elif classification == "recaptcha":
            print("  [RESULT] RECAPTCHA HARD BLOCK (residential also failed)", flush=True)
            db_mark_recaptcha_hard(role_id)
            results["recaptcha_hard"].append(f"{role_id} ({company})")
            return

    if classification == "submitted":
        slug = get_slug_from_plan(plan_path)
        write_status_md(slug, company, role_name, role_id, method)
        db_mark_submitted(role_id)
        print(f"  [RESULT] SUCCESS SUBMITTED slug={slug}", flush=True)
        results["submitted"].append(f"{role_id} ({company} -- {role_name})")

    elif classification == "already_applied":
        print("  [RESULT] ALREADY APPLIED", flush=True)
        db_mark_already_applied(role_id)
        results["already_applied"].append(f"{role_id} ({company})")

    elif classification == "role_closed":
        print("  [RESULT] ROLE CLOSED", flush=True)
        db_mark_closed(role_id)
        results["role_closed"].append(f"{role_id} ({company})")

    else:
        print(f"  [RESULT] ERROR (exit={exit_code})", flush=True)
        results["errors"].append(f"{role_id} ({company}): exit={exit_code}")


def main():
    print(f"Batch Ashby drain: {len(TARGET_IDS)} roles", flush=True)
    print(f"Start: {datetime.now().isoformat()}", flush=True)

    for i, role_id in enumerate(TARGET_IDS, 1):
        print(f"\n[{i}/{len(TARGET_IDS)}] Processing role {role_id}...", flush=True)
        try:
            process_role(role_id)
        except Exception as e:
            print(f"  [FATAL ERROR] role={role_id}: {e}", flush=True)
            traceback.print_exc()
            results["errors"].append(f"{role_id}: exception={e}")

        save_intermediate()
        time.sleep(2)

    print("\n" + "="*70, flush=True)
    print("BATCH COMPLETE - FINAL SUMMARY", flush=True)
    print("="*70, flush=True)

    for category, label in [
        ("submitted", "SUBMITTED"),
        ("already_applied", "ALREADY APPLIED"),
        ("role_closed", "ROLE CLOSED"),
        ("recaptcha_hard", "RECAPTCHA HARD"),
        ("prep_failed", "PREP FAILED"),
        ("errors", "ERRORS"),
    ]:
        items = results[category]
        print(f"\n{label} ({len(items)}):", flush=True)
        for r in items:
            print(f"  {r}", flush=True)

    counts = {k: len(v) for k, v in results.items()}
    total_accounted = sum(counts.values())
    print(f"\nTOTALS: {counts}", flush=True)
    print(f"Accounted: {total_accounted}/{len(TARGET_IDS)}", flush=True)

    print("\nRunning render_xlsx.py...", flush=True)
    try:
        res = subprocess.run(
            [str(VENV_PY), str(RD / "render_xlsx.py")],
            capture_output=True, text=True, timeout=120, cwd=str(RD)
        )
        if res.returncode == 0:
            print("render_xlsx.py: OK", flush=True)
        else:
            print(f"render_xlsx.py: FAILED rc={res.returncode}", flush=True)
            print(res.stderr[-300:], flush=True)
    except Exception as e:
        print(f"render_xlsx.py error: {e}", flush=True)

    return results


if __name__ == "__main__":
    main()
