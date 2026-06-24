#!/usr/bin/env python3
"""drain_prep_ready.py — Drain existing PREP-READY packets through the ATS runners.

For each applications/submitted/<slug>/STATUS.md that starts with "PREP-READY —":
  1. Read the plan path from STATUS.md.
  2. If plan file is missing + role_id present -> re-prep via inline_submit.py.
  3. Detect ATS from the plan JSON 'ats' field.
  4. Dispatch:
       ashby      -> _ashby_runner.py <plan>
       greenhouse -> _gh_submit.py <plan>
       lever/workday/other -> skip (not auto-submittable via these runners)
  5. Parse runner output for success/failure.
  6. On success: write SUBMITTED STATUS.md + update tracker.db (status=submitted).
  7. After all batches: run render_xlsx.py.

Usage:
  python3 drain_prep_ready.py [--limit N] [--ats ashby|greenhouse|all] [--no-submit] [--residential]

Flags:
  --limit N        process at most N roles (default 200)
  --ats <type>     only drain 'ashby', 'greenhouse', or 'all' (default: all)
  --no-submit      dry-run: parse + log but don't update tracker or STATUS.md
  --residential    set JOBSEARCH_CDP to residential port 19223 (Ashby score-gate roles)
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = ROOT / "tracker.db"
SUBMITTED_DIR = ROOT / "applications" / "submitted"
OUTPUT_DIR = HERE / "output"
VENV_PY = HERE / ".venv" / "bin" / "python3"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def build_env() -> dict:
    """Build subprocess env: load ~/.openclaw/.env, set ENABLE_CAPSOLVER."""
    env = dict(os.environ)
    env_file = Path.home() / ".openclaw" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    env["ENABLE_CAPSOLVER"] = "1"
    return env


def parse_role_id(status_text: str) -> int | None:
    m = re.search(r"^role_id:\s*(\d+)", status_text, re.M)
    return int(m.group(1)) if m else None


def parse_plan_path(status_text: str) -> str | None:
    m = re.search(r"^plan:\s*(\S+)", status_text, re.M)
    return m.group(1) if m else None


def read_ats(plan_path: str) -> str | None:
    try:
        return json.loads(Path(plan_path).read_text()).get("ats")
    except Exception:
        return None


def stage_resume(plan_path: str, slug: str) -> None:
    """Copy the role's resume PDF to /tmp/openclaw/uploads/ if the plan expects it there."""
    try:
        txt = Path(plan_path).read_text()
    except Exception:
        return
    upload_paths = set(re.findall(r"/tmp/openclaw/uploads/[^\"\\ ]+\.pdf", txt))
    if not upload_paths:
        return
    uploads_dir = Path("/tmp/openclaw/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    slug_dir = SUBMITTED_DIR / slug
    all_exist = True
    for target in sorted(upload_paths):
        target_p = Path(target)
        if target_p.exists():
            continue
        all_exist = False
        base = target_p.name
        src = slug_dir / base
        if src.exists():
            shutil.copy2(src, target_p)
            log(f"  staged resume {base}")
            return
        # fallback: any *esume*.pdf in the slug dir
        cands = sorted(slug_dir.glob("*esume*.pdf"))
        if cands:
            shutil.copy2(cands[-1], target_p)
            log(f"  staged resume {cands[-1].name} -> {base} (fallback)")
            return
    if not all_exist:
        log(f"  WARN: could not stage resume for {slug}")


def reprep(role_id: int, env: dict, timeout_s: int = 360) -> int:
    """Re-run inline_submit.py for a role whose plan file is missing.
    
    Uses a process GROUP to ensure grandchildren (openclaw-infer etc.) are
    killed on timeout — subprocess.run(timeout=) only kills the direct child.
    """
    import signal
    log(f"  re-prepping role {role_id} (timeout={timeout_s}s)...")
    try:
        proc = subprocess.Popen(
            [str(VENV_PY), "inline_submit.py", "--role-id", str(role_id)],
            cwd=str(HERE), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,  # new process group -> we can killpg
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            log(f"  re-prep TIMEOUT after {timeout_s}s — killing process group")
            try:
                import os
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.communicate()
            return -1
        if proc.returncode != 0:
            log(f"  re-prep failed (rc={proc.returncode}): {stderr[-300:].decode(errors='replace')}")
        return proc.returncode
    except Exception as exc:
        log(f"  re-prep ERROR: {exc}")
        return -2


def run_ashby(plan_path: str, env: dict, no_submit: bool = False) -> tuple[bool, str]:
    cmd = [str(VENV_PY), "_ashby_runner.py", plan_path]
    if no_submit:
        cmd.append("--no-submit")
    try:
        r = subprocess.run(
            cmd, cwd=str(HERE), env=env, capture_output=True, text=True, timeout=320
        )
        raw = r.stdout + r.stderr
        # parse the trailing JSON result block
        jstart = raw.rfind("\n{")
        if jstart < 0 and raw.strip().startswith("{"):
            jstart = 0
        j: dict = {}
        if jstart >= 0:
            try:
                j = json.loads(raw[jstart:])
            except Exception:
                pass
        classify = j.get("classify", "")
        ok = bool(j.get("ok")) or classify == "submitted"
        if not ok:
            SUCCESS_KWS = [
                "FormSubmitSuccess", "EXIT_0", "SUBMITTED",
                "submitted successfully", "thank you for applying",
                "application successfully submitted",
            ]
            ok = any(kw.lower() in raw.lower() for kw in SUCCESS_KWS)
        return ok, raw[-600:]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT(320s)"
    except Exception as exc:
        return False, str(exc)


def run_gh(plan_path: str, env: dict, no_submit: bool = False) -> tuple[bool, str]:
    cmd = [str(VENV_PY), "_gh_submit.py", plan_path]
    if no_submit:
        cmd.append("--no-submit")
    try:
        r = subprocess.run(
            cmd, cwd=str(HERE), env=env, capture_output=True, text=True, timeout=240
        )
        raw = r.stdout + r.stderr
        SUCCESS_KWS = [
            "confirmation", "submitted", "thank you", "success",
            "application received", "SUBMITTED", "EXIT_0",
        ]
        ok = any(kw.lower() in raw.lower() for kw in SUCCESS_KWS)
        return ok, raw[-600:]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT(240s)"
    except Exception as exc:
        return False, str(exc)


def mark_submitted(role_id: int, slug: str, runner_tail: str, no_submit: bool = False) -> None:
    if no_submit:
        log(f"  [no-submit] would mark role {role_id} submitted")
        return
    status_file = SUBMITTED_DIR / slug / "STATUS.md"
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    status_file.write_text(
        f"SUBMITTED\n\nsubmitted_by: auto\napplied_on: {TODAY}\n"
        f"role_id: {role_id}\nsubmitted_at: {ts}\n\nRunner tail:\n{runner_tail}\n"
    )
    conn = sqlite3.connect(str(DB))
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=?, "
        "prep_status='submitted' WHERE id=?",
        (TODAY, role_id),
    )
    conn.commit()
    conn.close()
    log("  marked submitted in DB + STATUS.md")


def render_xlsx() -> None:
    log("Re-rendering XLSX...")
    r = subprocess.run(
        [str(VENV_PY), "render_xlsx.py"],
        cwd=str(HERE), capture_output=True, text=True, timeout=120,
    )
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in ("Wrote:", "Open:", "Applied:", "Submitted:")):
            log(f"  {line}")


# Companies with standing HOLD — never auto-submit regardless of PREP-READY status.
# Update this list when Cyrus lifts a hold.
_COMPANY_HOLDS: set[str] = {
    "OpenAI",   # application limit hit 2026-06-18; hold until Cyrus re-enables
    "Deepgram", # 60-day re-apply block; re-apply after ~2026-07-30
}


def is_on_hold(role_id: int | None) -> bool:
    """Return True when the role's company is on a standing submission hold."""
    if not role_id:
        return False
    conn = sqlite3.connect(DB)
    try:
        row = conn.execute(
            "SELECT company FROM roles WHERE id=?",
            (role_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return False
    return row[0] in _COMPANY_HOLDS


def is_already_applied(role_id: int | None) -> bool:
    """Return true when tracker already has a durable applied marker.

    Stale PREP-READY STATUS.md files can linger after a successful DB update.
    Do not let those consume the drain limit or trigger duplicate submissions.
    """
    if not role_id:
        return False
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT status, applied_by FROM roles WHERE id=?",
            (role_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return False
    return bool(row["applied_by"]) or row["status"] in ("applied", "submitted")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Drain PREP-READY packets through ATS runners")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--ats", default="all", choices=["all", "ashby", "greenhouse"])
    ap.add_argument("--no-submit", action="store_true")
    ap.add_argument("--residential", action="store_true")
    args = ap.parse_args()

    env = build_env()
    if args.residential:
        env["JOBSEARCH_CDP"] = "http://127.0.0.1:19223"
        log("Using residential CDP port 19223")
    else:
        env.setdefault("JOBSEARCH_CDP", "http://127.0.0.1:18800")

    log(f"=== drain_prep_ready START | limit={args.limit} ats={args.ats} "
        f"no_submit={args.no_submit} ===")

    # Collect PREP-READY slugs (sort alphabetically for deterministic ordering)
    candidates: list[tuple[str, int | None, str | None, str]] = []
    for status_file in sorted(SUBMITTED_DIR.glob("*/STATUS.md")):
        try:
            text = status_file.read_text()
        except Exception:
            continue
        first_line = text.split("\n")[0].strip()
        if not (first_line.startswith("PREP-READY —") or first_line.startswith("PREP-READY-")):
            continue
        slug = status_file.parent.name
        role_id = parse_role_id(text)
        plan_path = parse_plan_path(text)
        candidates.append((slug, role_id, plan_path, text))

    log(f"Found {len(candidates)} PREP-READY slugs")

    submitted_list: list[str] = []
    failed_list: list[tuple[str, str]] = []
    skipped_list: list[tuple[str, str]] = []
    processed = 0

    for slug, role_id, plan_path, _status_text in candidates:
        if processed >= args.limit:
            log(f"Reached limit {args.limit}, stopping")
            break

        log(f"\n=== [{processed + 1}] {slug} (role_id={role_id}) ===")

        if is_already_applied(role_id):
            log("  Already applied in DB — stale PREP-READY, skipping without consuming limit")
            skipped_list.append((slug, "already-applied-db"))
            continue

        if is_on_hold(role_id):
            log("  Company on standing hold — skipping without consuming limit")
            skipped_list.append((slug, "company-hold"))
            continue

        if not plan_path:
            log("  No plan path in STATUS.md — skipping")
            skipped_list.append((slug, "no-plan-in-status"))
            continue

        plan_p = Path(plan_path)
        if not plan_p.exists():
            if role_id:
                log(f"  Plan file missing — re-prepping role {role_id}")
                rc = reprep(role_id, env)
                if rc != 0 or not plan_p.exists():
                    log(f"  Re-prep failed (rc={rc}) — skipping")
                    failed_list.append((slug, f"reprep-failed-rc{rc}"))
                    processed += 1
                    continue
                log("  Re-prep succeeded")
            else:
                log("  Plan file missing + no role_id — skipping")
                skipped_list.append((slug, "no-plan-no-roleid"))
                continue

        ats = read_ats(str(plan_p))
        if not ats:
            log("  Could not read ATS from plan — skipping")
            skipped_list.append((slug, "no-ats-in-plan"))
            processed += 1
            continue

        ats_family = "greenhouse" if ats in ("greenhouse", "greenhouse_iframe") else ("ashby" if ats == "ashby_tenant_embed" else ats)

        if args.ats != "all" and ats_family != args.ats:
            log(f"  ATS={ats}, filter={args.ats} — skipping")
            skipped_list.append((slug, f"ats-filter-{ats}"))
            continue

        if ats_family not in ("ashby", "greenhouse"):
            log(f"  ATS={ats} not auto-submittable via these runners — skipping")
            skipped_list.append((slug, f"manual-ats-{ats}"))
            continue

        log(f"  ATS={ats} | plan={plan_p.name}")
        stage_resume(str(plan_p), slug)

        t0 = time.time()
        if ats_family == "ashby":
            ok, runner_tail = run_ashby(str(plan_p), env, no_submit=args.no_submit)
        else:
            ok, runner_tail = run_gh(str(plan_p), env, no_submit=args.no_submit)

        elapsed = time.time() - t0
        log(f"  runner result: ok={ok} ({elapsed:.0f}s)")

        if ok:
            if role_id:
                mark_submitted(role_id, slug, runner_tail, no_submit=args.no_submit)
            submitted_list.append(slug)
        else:
            log(f"  FAILED tail: {runner_tail[-200:]}")
            failed_list.append((slug, "runner-failed"))

        processed += 1

    log("\n=== RESULTS ===")
    log(f"Submitted ({len(submitted_list)}): {submitted_list[:20]}")
    log(f"Failed    ({len(failed_list)}): {[s for s, _ in failed_list[:10]]}")
    log(f"Skipped   ({len(skipped_list)}): {len(skipped_list)}")

    if submitted_list and not args.no_submit:
        render_xlsx()

    log("=== drain_prep_ready DONE ===")


if __name__ == "__main__":
    main()
