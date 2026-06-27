#!/usr/bin/env python3
"""
run_ashby_batch.py — Batch Ashby prep + submit.

For each open Ashby role:
1. Run inline_submit.py --role-id <id> to prep (creates plan JSON)
2. Run _ashby_runner.py <plan_path> to submit
3. On RECAPTCHA_SCORE_BELOW_THRESHOLD → retry with residential proxy
4. Update tracker.db on success
5. Write STATUS.md to applications/submitted/<slug>/

Hard cohort (Baseten, Mercor) → skip immediately with blocked status.
Deepgram → skip (60-day re-apply block from prior submissions).
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import date, timezone, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
DB_PATH = PROJECT / "tracker.db"
SUBMITTED_DIR = PROJECT / "applications" / "submitted"

# Hard cohort — blocked even with residential
HARD_COHORT_ORGS = {"baseten", "mercor", "tavus", "moment", "decagon"}

# Moderate cohort — need residential
MODERATE_COHORT_ORGS = {
    "notion", "skydio", "anrok", "tessera-labs", "dash0", "klarity",
    "attio", "atticus", "thought-machine", "picogrid", "brellium",
    "restate", "scaled-cognition", "antithesis",
}

# 60-day block
DEEPGRAM_BLOCK_UNTIL = "2026-07-30"

DATACENTER_CDP = "http://127.0.0.1:18800"
RESIDENTIAL_CDP = "http://127.0.0.1:19223"

VENV_PY = str(HERE / ".venv" / "bin" / "python")


def get_org_from_url(url: str) -> str:
    m = re.search(r"ashbyhq\.com/([^/]+)/", url)
    return m.group(1) if m else ""


def run_cmd(cmd: list, env: dict = None, timeout: int = 300) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    full_env = {**os.environ}
    if env:
        full_env.update(env)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=full_env,
            cwd=str(HERE),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:\n        return -1, "", str(e)


def prep_role(role_id: int) -> tuple[bool, str, str]:
    """Run inline_submit.py for role_id. Returns (ok, plan_path_or_error, slug)."""
    rc, stdout, stderr = run_cmd(
        [VENV_PY, "inline_submit.py", "--role-id", str(role_id)],
        timeout=300,
    )
    
    # Parse JSON output
    combined_output = stdout + stderr
    
    # Check for OPENAI hold
    if "openai-application-limit-hold" in combined_output.lower() or (
        "OPENAI" in combined_output and "hold" in combined_output.lower()
    ):
        return False, "openai-hold", ""
    
    # Try to parse JSON from stdout
    plan_path = None
    slug = None
    try:
        if stdout.strip():
            data = json.loads(stdout.strip())
            results = data.get("results", [data])
            for res in results:
                if res.get("ok"):
                    plan_path = res.get("plan_path")
                    slug = res.get("slug")
                elif res.get("phase_failed"):
                    error = res.get("error", "")
                    slug = res.get("slug", "")
                    # Check for CLOSED/404
                    if "404" in error or "closed" in error.lower() or "not found" in error.lower():
                        return False, f"closed:{error[:100]}", slug
                    return False, f"prep-failed:{res['phase_failed']}:{error[:150]}", slug
    except json.JSONDecodeError:
        pass
    
    if plan_path and Path(plan_path).exists():
        return True, plan_path, slug or ""
    
    # Look for plan path in output
    plan_match = re.search(r'(output/inline-plan-[^\s"]+\.json)', combined_output)
    if plan_match:
        plan = HERE / plan_match.group(1)
        if plan.exists():
            return True, str(plan), slug or ""
    
    # Check if it's a prep-ready status that emits plan
    if "PREP-READY" in combined_output:
        # Find the plan path from STATUS.md
        slug_match = re.search(r'\[inline_submit\] === \[.+\] (\S+) \(', stderr)
        if slug_match:
            slug = slug_match.group(1)
        return False, f"prep-only-no-runner:{combined_output[-200:]}", slug or ""
    
    error_snippet = (stderr + stdout)[-300:]
    if "ABORT" in error_snippet:
        phase_match = re.search(r"ABORT-([a-z-]+)", error_snippet)
        phase = phase_match.group(1) if phase_match else "unknown"
        return False, f"prep-abort:{phase}:{error_snippet[-100:]}", ""
    
    if rc != 0 or not plan_path:
        return False, f"prep-rc{rc}:{error_snippet[-200:]}", ""
    
    return False, "prep-no-plan", ""


def run_ashby(plan_path: str, residential: bool = False) -> tuple[bool, str]:
    """Run _ashby_runner.py. Returns (ok, result_json_or_error)."""
    env = {}
    if residential:
        env["JOBSEARCH_CDP"] = RESIDENTIAL_CDP
        env["JOBSEARCH_PROXY_MODE"] = "residential"
    else:
        env["JOBSEARCH_CDP"] = DATACENTER_CDP
    
    rc, stdout, stderr = run_cmd(
        [VENV_PY, "_ashby_runner.py", plan_path],
        env=env,
        timeout=600,
    )
    
    combined = stdout + stderr
    
    # Try to parse JSON result
    try:
        if stdout.strip():
            result = json.loads(stdout.strip())
            ok = result.get("ok", False)
            return ok, stdout
    except json.JSONDecodeError:
        pass
    
    # Check for success signals in output
    if "FormSubmitSuccess" in combined or "submitted" in combined.lower():
        return True, combined[-500:]
    
    # Check for specific failure modes
    if "RECAPTCHA_SCORE_BELOW_THRESHOLD" in combined:
        return False, "RECAPTCHA_SCORE_BELOW_THRESHOLD"
    if "ALREADY_APPLIED" in combined:
        return False, "ALREADY_APPLIED"
    if "CLOSED" in combined or "req_closed" in combined.lower():
        return False, "CLOSED"
    
    if rc == 0:
        return True, combined[-500:]
    
    return False, f"runner-rc{rc}:{combined[-300:]}"


def update_db(role_id: int, status: str, applied_by: str = None, block_reason: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = date.today().isoformat()
    if status == "submitted":
        c.execute(
            "UPDATE roles SET status=?, applied_by=?, applied_on=? WHERE id=?",
            ("submitted", applied_by or "auto", today, role_id)
        )
    elif status == "blocked":
        c.execute(
            "UPDATE roles SET status=?, block_reason=? WHERE id=?",
            ("blocked", block_reason or "", role_id)
        )
    elif status == "closed":
        c.execute("UPDATE roles SET status='closed' WHERE id=?", (role_id,))
    elif status == "skip":
        c.execute("UPDATE roles SET status='skip' WHERE id=?", (role_id,))
    conn.commit()
    conn.close()


def write_status_md(slug: str, role_id: int, company: str, role: str, result_data: str):
    """Write STATUS.md to the submitted folder."""
    folder = SUBMITTED_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    status = (
        f"SUBMITTED — {now}\n\n"
        f"role_id: {role_id}\n"
        f"company: {company}\n"
        f"role: {role}\n"
        f"submitted_by: auto\n"
        f"applied_on: {date.today().isoformat()}\n"
        f"screenshot: n/a\n\n"
        f"Runner output:\n{result_data[-500:]}\n"
    )
    (folder / "STATUS.md").write_text(status)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, company, role, app_url
        FROM roles
        WHERE status='open' AND (app_url LIKE '%ashbyhq%' OR jd_url LIKE '%ashbyhq%')
        ORDER BY id
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    
    print(f"\n[ashby-batch] Found {len(rows)} open Ashby roles\n")
    
    results = {
        "submitted": [],
        "blocked": [],
        "closed": [],
        "skipped": [],
    }
    
    for i, row in enumerate(rows, 1):
        role_id = row["id"]
        company = row["company"]
        role_name = row["role"]
        url = row["app_url"] or ""
        org = get_org_from_url(url)
        
        print(f"\n[{i}/{len(rows)}] {role_id} — {company} — {role_name}")
        print(f"  org={org} url={url[:60]}")
        
        # Skip OpenAI
        if "openai" in company.lower() or "openai" in org.lower():
            print(f"  → SKIP: OpenAI application-limit hold")
            update_db(role_id, "skip")
            results["skipped"].append(f"{role_id} {company} — OpenAI hold")
            continue
        
        # Skip Deepgram (60-day block)
        if "deepgram" in company.lower() or "deepgram" in org.lower():
            print(f"  → SKIP: Deepgram 60-day re-apply block (until ~2026-07-30)")
            update_db(role_id, "blocked", block_reason="deepgram-60-day-reapply-block-until-2026-07-30")
            results["blocked"].append(f"{role_id} {company} — deepgram-60day-block")
            continue
        
        # Hard cohort
        if org in HARD_COHORT_ORGS:
            print(f"  → BLOCKED (hard cohort): {org}")
            update_db(role_id, "blocked", block_reason=f"ashby-hard-recaptcha-residential-resistant:{org}")
            results["blocked"].append(f"{role_id} {company} — hard-cohort:{org}")
            continue
        
        # Determine if moderate (needs residential first)
        is_moderate = org in MODERATE_COHORT_ORGS
        
        # Step 1: Prep
        print(f"  → Prepping...")
        prep_ok, prep_result, slug = prep_role(role_id)
        
        if not prep_ok:
            if "closed" in prep_result.lower() or "404" in prep_result:
                print(f"  → CLOSED: {prep_result[:100]}")
                update_db(role_id, "closed")
                results["closed"].append(f"{role_id} {company} — closed")
                continue
            if "already_applied" in prep_result.lower() or "already-applied" in prep_result.lower():
                print(f"  → ALREADY APPLIED")
                update_db(role_id, "submitted", applied_by="auto")
                results["submitted"].append(f"{role_id} {company} — already-applied")
                continue
            if "openai-hold" in prep_result:
                print(f"  → SKIP: OpenAI hold")
                update_db(role_id, "skip")
                results["skipped"].append(f"{role_id} {company} — openai-hold")
                continue
            print(f"  → PREP FAILED: {prep_result[:200]}")
            update_db(role_id, "blocked", block_reason=f"prep-failed:{prep_result[:150]}")
            results["blocked"].append(f"{role_id} {company} — {prep_result[:100]}")
            continue
        
        plan_path = prep_result
        print(f"  → Prep OK, plan: {Path(plan_path).name}")
        
        # Step 2: Submit
        # For moderate cohort, go residential first
        if is_moderate:
            print(f"  → Moderate cohort ({org}), trying residential first...")
            ok, run_result = run_ashby(plan_path, residential=True)
        else:
            print(f"  → Trying datacenter...")
            ok, run_result = run_ashby(plan_path, residential=False)
        
        # If datacenter failed with captcha, retry residential
        if not ok and not is_moderate and "RECAPTCHA_SCORE_BELOW_THRESHOLD" in run_result:
            print(f"  → reCAPTCHA gate, retrying with residential proxy...")
            ok, run_result = run_ashby(plan_path, residential=True)
        
        if ok:
            print(f"  → SUBMITTED ✓")
            # Get slug from plan path or STATUS.md
            if not slug:
                plan_name = Path(plan_path).stem  # inline-plan-<slug>
                slug = plan_name.replace("inline-plan-", "")
            write_status_md(slug, role_id, company, role_name, run_result)
            update_db(role_id, "submitted", applied_by="auto")
            results["submitted"].append(f"{role_id} {company} — {role_name}")
        else:
            # Classify failure
            if "ALREADY_APPLIED" in run_result:
                print(f"  → Already applied")
                update_db(role_id, "submitted", applied_by="auto")
                results["submitted"].append(f"{role_id} {company} — already-applied")
            elif "CLOSED" in run_result:
                print(f"  → CLOSED")
                update_db(role_id, "closed")
                results["closed"].append(f"{role_id} {company} — closed")
            elif "RECAPTCHA_SCORE_BELOW_THRESHOLD" in run_result:
                reason = "ashby-hard-recaptcha-residential-resistant"
                print(f"  → BLOCKED: {reason}")
                update_db(role_id, "blocked", block_reason=reason)
                results["blocked"].append(f"{role_id} {company} — {reason}")
            else:
                reason = f"runner-failed:{run_result[:150]}"
                print(f"  → BLOCKED: {reason[:100]}")
                update_db(role_id, "blocked", block_reason=reason[:200])
                results["blocked"].append(f"{role_id} {company} — {reason[:100]}")
        
        # Small delay between submissions
        time.sleep(2)
    
    # Final summary
    print("\n" + "="*60)
    print("ASHBY BATCH SUMMARY")
    print("="*60)
    print(f"SUBMITTED ({len(results['submitted'])}):")
    for r in results["submitted"]:
        print(f"  ✓ {r}")
    print(f"\nBLOCKED ({len(results['blocked'])}):")
    for r in results["blocked"]:
        print(f"  ✗ {r}")
    print(f"\nCLOSED ({len(results['closed'])}):")
    for r in results["closed"]:
        print(f"  - {r}")
    print(f"\nSKIPPED ({len(results['skipped'])}):")
    for r in results["skipped"]:
        print(f"  ~ {r}")
    print(f"\nTotal: {len(rows)} roles | {len(results['submitted'])} submitted | {len(results['blocked'])} blocked | {len(results['closed'])} closed | {len(results['skipped'])} skipped")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
