#!/usr/bin/env python3
"""Sequential V2 burndown — walk EVERY open role by id ASC.

For each open + unapplied + no-prep role with no `BLOCKED 2026-05-25` note:
  1. Call inline_submit.py (auto-detects ATS, runs prep or browser plan).
  2. Capture result; if ok=false or browser-flow-needed, log BLOCKED note.
  3. Move on. No cluster pre-filters. No domain blacklists.

Each role gets a fair attempt. Browser-flow roles are flagged for solo
subagent follow-up; prep-only roles are completed inline.
"""
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "tracker.db"
PY = ROOT / "role-discovery" / ".venv" / "bin" / "python"
INLINE = ROOT / "role-discovery" / "inline_submit.py"
LOG = ROOT / "applications" / "_burndown-v2-sequential.md"
PER_ROLE_TIMEOUT = 180  # seconds — inline_submit's hard cap


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_queue():
    con = sqlite3.connect(DB)
    rows = list(
        con.execute(
            """SELECT id, company, role, app_url, llm_fit_score
               FROM roles
               WHERE status='' AND applied_by IS NULL AND prep_status IS NULL
               AND (agent_notes IS NULL OR agent_notes NOT LIKE '%BLOCKED 2026-05-25%')
               ORDER BY id ASC"""
        )
    )
    con.close()
    return rows


def append_note(role_id: int, note: str):
    con = sqlite3.connect(DB)
    con.execute(
        "UPDATE roles SET agent_notes = COALESCE(agent_notes||char(10),'') || ? WHERE id = ?",
        (note, role_id),
    )
    con.commit()
    con.close()


def log_line(line: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def attempt(role_id: int, company: str, role: str, app_url: str) -> dict:
    """Returns dict: {status, summary, needs_browser}."""
    try:
        proc = subprocess.run(
            [str(PY), str(INLINE), "--role-id", str(role_id)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=PER_ROLE_TIMEOUT,
        )
        out = proc.stdout.strip()
        err = (proc.stderr or "").strip()
        # inline_submit prints ONE JSON blob to stdout (logs go to stderr).
        # Parse the whole stdout; if that fails, walk back from the last '}'
        # to the matching top-level '{' as a fallback.
        def _parse(s: str):
            s = s.strip()
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
            # fallback: scan from end for matching brace
            if not s.endswith("}"):
                raise json.JSONDecodeError("no trailing }", s, 0)
            depth = 0
            for i in range(len(s) - 1, -1, -1):
                c = s[i]
                if c == '}':
                    depth += 1
                elif c == '{':
                    depth -= 1
                    if depth == 0:
                        return json.loads(s[i:])
            raise json.JSONDecodeError("no matching {", s, 0)
        try:
            payload = _parse(out)
            res = payload.get("results", [{}])[0]
            ok = res.get("ok", False)
            phase = res.get("phase_failed")
            mode = res.get("submit_mode", "?")
            ats = res.get("ats", "?")
            if ok and mode == "manual":
                return {"status": "MANUAL_READY", "summary": f"{ats} prep ok", "needs_browser": False}
            if ok and mode == "auto":
                return {"status": "AUTO_SUBMITTED", "summary": f"{ats} auto-submit", "needs_browser": False}
            # ok=false: prep failed; phase tells us why
            return {
                "status": "BLOCKED",
                "summary": f"{ats} phase={phase} stderr={err[-200:]!r}",
                "needs_browser": "browser" in str(phase).lower(),
            }
        except (ValueError, json.JSONDecodeError):
            # No parseable JSON. Distinguish the common failure modes from stderr.
            err_tail = err.splitlines()[-1] if err else ""
            if "unsupported ATS URL" in err:
                return {
                    "status": "BLOCKED",
                    "summary": f"unsupported-ats: {err_tail[:240]}",
                    "needs_browser": True,
                }
            if "Traceback" in err:
                return {
                    "status": "BLOCKED",
                    "summary": f"inline-crashed: {err_tail[:240]}",
                    "needs_browser": False,
                }
            return {
                "status": "BLOCKED",
                "summary": f"unparseable inline_submit (stdout={out[-120:]!r} stderr={err[-200:]!r})",
                "needs_browser": False,
            }
    except subprocess.TimeoutExpired:
        return {"status": "BLOCKED", "summary": f"timeout after {PER_ROLE_TIMEOUT}s", "needs_browser": False}
    except Exception as e:  # noqa: BLE001
        return {"status": "BLOCKED", "summary": f"driver-error: {e!r}", "needs_browser": False}


def main():
    queue = open_queue()
    log_line(f"\n# Sequential V2 burndown — {now()} — {len(queue)} roles to attempt\n")
    counts = {"AUTO_SUBMITTED": 0, "MANUAL_READY": 0, "BLOCKED": 0, "NEEDS_BROWSER": 0}
    for i, (rid, company, role, app_url, fit) in enumerate(queue, 1):
        t0 = time.time()
        r = attempt(rid, company, role, app_url)
        dt = time.time() - t0
        log_line(
            f"[{i}/{len(queue)}] id={rid} {company!s:.22} fit={fit} "
            f"-> {r['status']} ({dt:.1f}s) | {r['summary'][:200]}"
        )
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r["status"] == "BLOCKED":
            cat = "needs-browser-subagent" if r["needs_browser"] else "inline-failed"
            counts["NEEDS_BROWSER"] += 1 if r["needs_browser"] else 0
            note = f"BLOCKED 2026-05-25: sequential-driver | {cat} | {r['summary'][:200]}"
            append_note(rid, note)
        # progress checkpoint every 10
        if i % 10 == 0:
            log_line(f"  --- progress: {counts} ---")
    log_line(f"\n# DONE — final counts: {counts}\n")


if __name__ == "__main__":
    main()
