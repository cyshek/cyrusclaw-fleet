#!/usr/bin/env python3
"""Direct Ashby residential drain for specific PREP-READY roles."""
from __future__ import annotations
import json, os, re, sqlite3, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = ROOT / "tracker.db"
VENV_PY = HERE / ".venv" / "bin" / "python3"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

LOG_FILE = HERE / "output" / "drain_pass3_20260623_024438.log"

CAPSOLVER_KEY = (ROOT / ".capsolver-key").read_text().strip() if (ROOT / ".capsolver-key").exists() else ""

# Ashby PREP-READY roles to drain (slug, role_id)
# Skip: cantina-labs (country bug), cape/cohere/thought-machine (already submitted)
# Skip hard cohort: openai, baseten, mercor, tavus, deepgram, scaled-cognition
ASHBY_ROLES = [
    ("agave-685cc476-4e5d-4406-86d8-b9835fed6d9b",               3275),
    ("anyscale-0c2602bc-3fb7-41a0-9837-afb03f7c9503",            3018),
    ("bedrock-robotics-7b7a74a2-61d6-4528-8aa9-6aa147aaa497",    3344),
    ("decagon-6321ea2f-4e21-4c18-8859-b4ef5489b6fe",             1426),
    ("edia-8a161495-4e3c-4045-ba36-6efed495e386",                1432),
    ("fluidstack-f93527ee-b4b2-47e4-9a25-51f783bbf3e3",          1495),
    ("harvey-9ea6dcda-7869-4181-b493-2822bbc14097",              3146),
    ("thumbtack-20b7b151-75bf-4265-995d-30c081e86b7d",           2287),
]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(str(LOG_FILE), "a") as f:
        f.write(line + "\n")


def build_env() -> dict:
    env = dict(os.environ)
    env["JOBSEARCH_CDP"] = "http://127.0.0.1:19223"
    env["ENABLE_CAPSOLVER"] = "1"
    if CAPSOLVER_KEY:
        env["CAPSOLVER_API_KEY"] = CAPSOLVER_KEY
    return env


def run_ashby(plan_path: str, env: dict) -> tuple[bool, str]:
    r = subprocess.run(
        [str(VENV_PY), "_ashby_runner.py", plan_path],
        cwd=str(HERE), env=env,
        capture_output=True, text=True, timeout=300,
    )
    output = (r.stdout + r.stderr).strip()
    confirmed = (
        '"confirmed": true' in output
        or '"status": "submitted"' in output
        or "FormSubmitSuccess" in output
        or "Application submitted" in output
        or '"submit_status": "success"' in output
    )
    return confirmed, output


def mark_submitted(role_id: int, slug: str, runner_tail: str) -> None:
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

    log(f"\n=== ASHBY RESIDENTIAL DRAIN v2 START | {len(ASHBY_ROLES)} roles ===")
    log(f"CDP: {env['JOBSEARCH_CDP']}")

    for slug, role_id in ASHBY_ROLES:
        plan = HERE / "output" / f"inline-plan-{slug}.json"
        log(f"\n=== {slug} (role_id={role_id}) ===")

        if not plan.exists():
            log(f"  SKIP: plan not found at {plan.name}")
            failed.append((slug, "no-plan"))
            continue

        log(f"  Running _ashby_runner.py (residential)...")
        t0 = time.time()
        try:
            ok, output = run_ashby(str(plan), env)
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

        with open(str(LOG_FILE), "a") as lf:
            lf.write(f"--- {slug} ashby runner output ---\n")
            lf.write(output[-2000:] + "\n")
            lf.write("--- end ---\n")

        if ok:
            mark_submitted(role_id, slug, output)
            submitted.append(slug)
        elif "RECAPTCHA_SCORE_BELOW_THRESHOLD" in output or "recaptcha_score_below" in output.lower():
            log(f"  BLOCKED: reCAPTCHA score (hard cohort)")
            failed.append((slug, "recaptcha-hard-cohort"))
        elif "no longer available" in output.lower() or "job is closed" in output.lower() or "position has been filled" in output.lower():
            log(f"  CLOSED role")
            conn = sqlite3.connect(str(DB))
            conn.execute("UPDATE roles SET status='closed' WHERE id=?", (role_id,))
            conn.commit()
            conn.close()
            failed.append((slug, "closed"))
        elif "ALREADY_APPLIED" in output or "already applied" in output.lower():
            log(f"  ALREADY_APPLIED")
            failed.append((slug, "already-applied"))
        else:
            m = re.search(r'"status":\s*"([^"]+)"', output[-500:])
            final_status = m.group(1) if m else "unknown"
            log(f"  FAILED: final status={final_status}")
            failed.append((slug, f"failed-status:{final_status}"))

    log(f"\n=== ASHBY RESIDENTIAL DRAIN RESULTS ===")
    log(f"Submitted ({len(submitted)}): {submitted}")
    log(f"Failed    ({len(failed)}): {[f'{s}:{r}' for s,r in failed]}")
    log(f"=== DONE ===")


if __name__ == "__main__":
    main()
