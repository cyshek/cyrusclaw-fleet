#!/usr/bin/env python3
"""Direct GH drain for specific PREP-READY roles."""
from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = ROOT / "tracker.db"
VENV_PY = HERE / ".venv" / "bin" / "python3"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

LOG_FILE = HERE / "output" / "drain_pass3_20260623_024438.log"

CAPSOLVER_KEY = (ROOT / ".capsolver-key").read_text().strip() if (ROOT / ".capsolver-key").exists() else ""

GH_ROLES = [
    ("chime-8530421002",        1437),
    ("figma-5837760004",        1089),
    ("figma-6009613004",        2344),
    ("nice-4847972101",         3296),
    ("nice-4849399101",         3297),
    ("otter-8402672002",        3239),
    ("path-robotics-8571279002", 3478),
    ("securitize-4173649009",   1030),
    ("yipitdata-8002296",       2974),
    ("ziprecruiter-7354406",    2409),
]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def build_env() -> dict:
    env = dict(os.environ)
    env["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
    env["ENABLE_CAPSOLVER"] = "1"
    if CAPSOLVER_KEY:
        env["CAPSOLVER_API_KEY"] = CAPSOLVER_KEY
    return env


def run_gh(plan_path: str, env: dict) -> tuple[bool, str]:
    r = subprocess.run(
        [str(VENV_PY), "_gh_submit.py", plan_path],
        cwd=str(HERE), env=env,
        capture_output=True, text=True, timeout=300,
    )
    output = (r.stdout + r.stderr).strip()
    # Check success
    confirmed = '"confirmed": true' in output or '"status": "submitted"' in output
    return confirmed, output


def mark_submitted(role_id: int, slug: str, runner_tail: str) -> None:
    import sqlite3
    status_dir = ROOT / "applications" / "submitted" / slug
    status_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    (status_dir / "STATUS.md").write_text(
        f"SUBMITTED\n\nsubmitted_by: auto\napplied_on: {TODAY}\n"
        f"role_id: {role_id}\nsubmitted_at: {ts}\n\nRunner tail:\n{runner_tail[-500:]}\n"
    )
    conn = sqlite3.connect(str(DB))
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=?, prep_status='submitted' WHERE id=?",
        (TODAY, role_id),
    )
    conn.commit()
    conn.close()
    log(f"  DB+STATUS.md updated: submitted")


def main() -> None:
    env = build_env()
    submitted, failed = [], []

    log(f"=== GH DRAIN v2 START | {len(GH_ROLES)} roles ===")

    for slug, role_id in GH_ROLES:
        plan = HERE / "output" / f"inline-plan-{slug}.json"
        log(f"\n=== {slug} (role_id={role_id}) ===")

        if not plan.exists():
            log(f"  SKIP: plan not found at {plan.name}")
            failed.append((slug, "no-plan"))
            continue

        log(f"  Running _gh_submit.py...")
        t0 = time.time()
        try:
            ok, output = run_gh(str(plan), env)
        except subprocess.TimeoutExpired:
            log(f"  TIMEOUT after 300s")
            failed.append((slug, "timeout"))
            continue
        except Exception as ex:
            log(f"  ERROR: {ex}")
            failed.append((slug, f"error:{ex}"))
            continue

        elapsed = time.time() - t0
        log(f"  Runner done: ok={ok} ({elapsed:.0f}s)")

        # Log runner tail
        with open(LOG_FILE, "a") as lf:
            lf.write(f"--- {slug} runner output ---\n")
            lf.write(output[-1500:] + "\n")
            lf.write("--- end ---\n")

        # Detect common fail reasons from output
        if ok:
            mark_submitted(role_id, slug, output)
            submitted.append(slug)
        elif "no longer open" in output or '"status": "closed"' in output:
            log(f"  CLOSED role")
            import sqlite3
            conn = sqlite3.connect(str(DB))
            conn.execute("UPDATE roles SET status='closed' WHERE id=?", (role_id,))
            conn.commit()
            conn.close()
            failed.append((slug, "closed"))
        elif "noinput" in output and "company-name-0" in output:
            log(f"  BLOCKED: GH Remix work-history repeater (company-name-0 unfilled)")
            failed.append((slug, "gh-remix-work-history"))
        elif "security-input-0" in output or "8-character code" in output:
            log(f"  BLOCKED: email-OTP gate")
            failed.append((slug, "email-otp"))
        elif "uncertain" in output:
            log(f"  uncertain - checking emptyRequired")
            # Extract emptyRequired
            import re
            m = re.search(r'"emptyRequired":\s*(\[[^\]]*\])', output)
            er = m.group(1) if m else "unknown"
            log(f"  emptyRequired: {er}")
            failed.append((slug, f"uncertain-emptyRequired:{er}"))
        else:
            log(f"  FAILED (unknown)")
            failed.append((slug, "runner-failed"))

    log(f"\n=== GH DRAIN RESULTS ===")
    log(f"Submitted ({len(submitted)}): {submitted}")
    log(f"Failed    ({len(failed)}): {[f'{s}:{r}' for s,r in failed]}")
    log(f"=== DONE ===")


if __name__ == "__main__":
    main()
