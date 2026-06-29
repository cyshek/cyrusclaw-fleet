#!/usr/bin/env python3
"""
apple_prep_parallel.py — Run Apple prep-only lane with parallel bullet_rewriter.

Strategy:
  - Fetch all JDs first (sequential, CDP-safe) -- store JD.md + meta.json
  - Then bulk-run bullet_rewriter in parallel (N workers, no CDP needed)

This is much faster than sequential: 540 roles × 4min bullet_rewriter
with 4 workers → ~90 min instead of ~36 hours.
"""
from __future__ import annotations
import sqlite3
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# Paths
HERE = Path(__file__).parent
DB_PATH = HERE.parent / "tracker.db"
APPS_DIR = HERE.parent / "applications" / "submitted"
VENV_PY = HERE / ".venv" / "bin" / "python"
PERSONAL_INFO = HERE / "role-discovery" / "personal-info.json"
if not PERSONAL_INFO.exists():
    PERSONAL_INFO = HERE / "personal-info.json"

MAX_WORKERS = 3  # parallel bullet_rewriter workers
LOG = Path("/tmp/apple_prep_parallel.log")


def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def get_remaining_roles() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, source_key, company, role, loc, exp_req, app_url, status, flags
        FROM roles
        WHERE source_key LIKE 'apple:%'
          AND status = 'blocked'
          AND (prep_status IS NULL OR prep_status = '')
        ORDER BY id
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        sk = r["source_key"] or ""
        reqid = sk.split(":", 1)[-1] if ":" in sk else ""
        slug = "apple-" + reqid
        workdir = APPS_DIR / slug
        result.append({
            "role_id": r["id"], "company": r["company"], "role": r["role"],
            "loc": r["loc"], "exp_req": r["exp_req"],
            "url": r["app_url"] or "", "app_url": r["app_url"] or "",
            "apple_reqid": reqid, "slug": slug,
            "workdir": workdir, "flags": r["flags"] or "",
        })
    return result


def fetch_jd(role: dict, cdp: str = "http://127.0.0.1:18800") -> tuple[bool, str]:
    """Fetch JD via _apple_jd_fetch.py. Returns (success, error_msg)."""
    workdir = role["workdir"]
    workdir.mkdir(parents=True, exist_ok=True)
    jd_path = workdir / "JD.md"

    try:
        res = subprocess.run(
            [str(VENV_PY), str(HERE / "_apple_jd_fetch.py"),
             role["app_url"], "--out", str(jd_path)],
            capture_output=True, text=True, timeout=90,
        )
        if res.returncode == 0:
            jd_text = jd_path.read_text() if jd_path.exists() else ""
            if len(jd_text) >= 200:
                return True, ""
            return False, f"JD too short ({len(jd_text)} chars)"
        elif res.returncode == 2:
            return False, "boilerplate-only JD"
        elif res.returncode == 3:
            return False, "CDP attach failed"
        else:
            return False, f"_apple_jd_fetch exit {res.returncode}"
    except subprocess.TimeoutExpired:
        return False, "JD fetch timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def write_meta(role: dict, jd_text: str):
    """Write meta.json + prefill.json."""
    workdir = role["workdir"]
    reqid = role["apple_reqid"]
    apply_url = role["app_url"]

    # Prepend header to JD
    jd_full = (
        "# " + role["company"] + " — " + role["role"] + "\n\n"
        "**Location:** " + (role.get("loc") or "n/a") + "\n"
        "**Apply:** " + apply_url + "\n"
        "**Apple Req ID:** " + reqid + "\n"
        "**Submit mode:** MANUAL (Apple-ID SSO + 2FA required)\n\n"
        "---\n\n"
        + jd_text
    )
    (workdir / "JD.md").write_text(jd_full)

    personal = json.loads(PERSONAL_INFO.read_text()) if PERSONAL_INFO.exists() else {}
    meta = {
        "company": role["company"], "role": role["role"],
        "location": role.get("loc"), "apply_url": apply_url,
        "ats": "apple", "apple_reqid": reqid,
        "gh_org": "apple-" + reqid, "gh_jid": reqid,
        "submit_mode": "manual",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (workdir / "prefill.json").write_text(json.dumps(personal, indent=2) + "\n")


def mark_db(role_id: int, prep_status: str, workdir: Path | None = None):
    conn = sqlite3.connect(DB_PATH)
    if workdir:
        conn.execute("UPDATE roles SET prep_status=?, prep_path=? WHERE id=?",
                     (prep_status, str(workdir), role_id))
    else:
        conn.execute("UPDATE roles SET prep_status=? WHERE id=?", (prep_status, role_id))
    conn.commit()
    conn.close()


def run_bullet_rewriter_worker(role: dict) -> tuple[bool, str]:
    """Run bullet_rewriter for one role. Returns (success, error_msg)."""
    workdir = role["workdir"]
    reqid = role["apple_reqid"]
    gh_org = "apple-" + reqid
    gh_jid = reqid

    pdf_name = f"Cyrus_Shekari_Resume_{gh_org}_{gh_jid}_v2.pdf"
    pdf_fast = workdir / pdf_name
    if pdf_fast.exists() and pdf_fast.stat().st_size > 1024:
        return True, "fast-path"

    # Create symlink shim for bullet_rewriter
    queued_dir = HERE.parent / "applications" / "queued"
    queued_dir.mkdir(parents=True, exist_ok=True)
    shim = queued_dir / role["slug"]
    org_shim = queued_dir / f"{gh_org}-{gh_jid}"
    created_shim = created_org_shim = False
    if not (shim.exists() or shim.is_symlink()):
        shim.symlink_to(workdir, target_is_directory=True)
        created_shim = True
    if org_shim != shim and not (org_shim.exists() or org_shim.is_symlink()):
        org_shim.symlink_to(workdir, target_is_directory=True)
        created_org_shim = True

    try:
        res = subprocess.run(
            [str(VENV_PY), str(HERE / "bullet_rewriter.py"),
             "--org", gh_org, "--job-id", gh_jid, "--render", "--max-loops", "3"],
            capture_output=True, text=True, timeout=900,
        )
        if res.returncode != 0:
            return False, f"bullet_rewriter rc={res.returncode}: {res.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return False, "bullet_rewriter timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        for s, created in ((shim, created_shim), (org_shim, created_org_shim)):
            if created and s.is_symlink():
                try:
                    s.unlink()
                except Exception:
                    pass

    if pdf_fast.exists() and pdf_fast.stat().st_size > 1024:
        return True, ""
    return False, f"PDF missing after bullet_rewriter: {pdf_fast}"


def write_status_md(role: dict, pdf_path: Path | None, ok: bool, error: str = ""):
    workdir = role["workdir"]
    apply_url = role["app_url"]
    reqid = role["apple_reqid"]
    now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not ok:
        (workdir / "STATUS.md").write_text(
            f"ABORT-BULLET-REWRITER — {now_str}\n\n"
            f"role_id: {role['role_id']}\n"
            f"error: {error}\n"
        )
        return

    jd_full = (workdir / "JD.md").read_text() if (workdir / "JD.md").exists() else ""
    pdf_name = pdf_path.name if pdf_path else "n/a"
    cover_line = "(JD context + resume upload notes)"
    (workdir / "STATUS.md").write_text(
        "STATUS: PREP-READY-MANUAL-APPLE\n"
        f"Generated: {now_str}\n\n"
        f"role_id: {role['role_id']}\n"
        f"ats: apple (reqid: {reqid})\n"
        f"company: {role['company']}\n"
        f"role: {role['role']}\n\n"
        "=====================================================================\n"
        "APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):\n\n"
        f"    {apply_url}\n\n"
        "=====================================================================\n\n"
        "Packet contents:\n"
        f"  - JD.md                 ({len(jd_full)} chars of JD body)\n"
        f"  - {pdf_name}  (tailored resume PDF — upload this)\n"
        f"  - cover_answers.md      {cover_line}\n"
        "  - meta.json, prefill.json\n\n"
        "Apple-ID SSO + 2FA means auto-submit is not possible.\n"
        "Open the apply URL above, sign in with Apple ID, upload the tailored\n"
        "PDF, paste answers from cover_answers.md, submit.\n\n"
        "Once submitted, stamp tracker.db:\n"
        f"  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',\n"
        f"    prep_status='submitted' WHERE id={role['role_id']};\n"
        "then re-run render_xlsx.py.\n"
    )

    # Write cover_answers.md stub
    jd_preview = jd_full[:3000]
    (workdir / "cover_answers.md").write_text(
        f"# Application notes — {role['company']}: {role['role']}\n\n"
        "Apple's apply flow is a resume upload + optional cover letter.\n"
        "No ATS essay questions detected (Apple-ID SSO gated).\n\n"
        "## JD Preview (for cover letter / resume tailoring context)\n\n"
        + jd_preview + "\n"
    )


def process_role_rewriter(role: dict) -> dict:
    """Thread worker: run bullet_rewriter for a role that already has JD.md."""
    ok, err = run_bullet_rewriter_worker(role)
    reqid = role["apple_reqid"]
    gh_org = "apple-" + reqid
    pdf_path = role["workdir"] / f"Cyrus_Shekari_Resume_{gh_org}_{reqid}_v2.pdf"

    write_status_md(role, pdf_path if ok else None, ok, err)
    mark_db(role["role_id"], "manual_ready" if ok else "rewriter_failed", role["workdir"])
    return {"slug": role["slug"], "role_id": role["role_id"], "ok": ok, "error": err,
            "method": "fast-path" if err == "fast-path" else "rewriter"}


def main():
    log("=== Apple prep parallel runner starting ===")
    roles = get_remaining_roles()
    log(f"Found {len(roles)} unprepped blocked Apple roles")

    if not roles:
        log("Nothing to do.")
        return

    # Phase 1: sequential JD fetch (CDP-safe)
    log(f"=== Phase 1: JD fetch ({len(roles)} roles) ===")
    ready_for_rewrite = []
    fetch_failed = []

    for i, role in enumerate(roles, 1):
        # Skip if PDF already exists (prior partial run)
        reqid = role["apple_reqid"]
        pdf_fast = role["workdir"] / f"Cyrus_Shekari_Resume_apple-{reqid}_{reqid}_v2.pdf"
        if pdf_fast.exists() and pdf_fast.stat().st_size > 1024:
            log(f"[{i}/{len(roles)}] {role['slug']} — fast-path (PDF exists)")
            ready_for_rewrite.append(role)
            continue

        # Skip if JD.md already exists and is good
        jd_path = role["workdir"] / "JD.md"
        if jd_path.exists() and len(jd_path.read_text()) >= 200:
            log(f"[{i}/{len(roles)}] {role['slug']} — JD cached, skip fetch")
            ready_for_rewrite.append(role)
            continue

        ok, err = fetch_jd(role)
        if ok:
            jd_text = (role["workdir"] / "JD.md").read_text()
            write_meta(role, jd_text)
            log(f"[{i}/{len(roles)}] {role['slug']} — JD OK ({len(jd_text)} chars)")
            ready_for_rewrite.append(role)
        else:
            log(f"[{i}/{len(roles)}] {role['slug']} — JD FAIL: {err}")
            mark_db(role["role_id"], "fetch_failed")
            fetch_failed.append({"slug": role["slug"], "error": err})
            (role["workdir"] / "STATUS.md").write_text(
                f"FETCH-FAILED-APPLE — {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
                f"role_id: {role['role_id']}\n"
                f"error: {err}\n"
            )

    log(f"Phase 1 done. Ready for rewrite: {len(ready_for_rewrite)}, fetch_failed: {len(fetch_failed)}")

    # Phase 2: parallel bullet_rewriter
    log(f"=== Phase 2: bullet_rewriter ({len(ready_for_rewrite)} roles, {MAX_WORKERS} workers) ===")
    ok_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_role_rewriter, role): role for role in ready_for_rewrite}
        for future in as_completed(futures):
            result = future.result()
            if result["ok"]:
                ok_count += 1
                log(f"✓ {result['slug']} [{ok_count}/{len(ready_for_rewrite)}] ({result.get('method','')})")
            else:
                fail_count += 1
                log(f"✗ {result['slug']} FAIL: {result['error']}")

    log(f"=== DONE: {ok_count} manual_ready, {fail_count} rewriter_failed, {len(fetch_failed)} fetch_failed ===")

    # Final DB summary
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT prep_status, count(*) as cnt FROM roles
        WHERE source_key LIKE 'apple:%' GROUP BY prep_status
    """).fetchall()
    conn.close()
    log("Final Apple prep_status summary:")
    for r in rows:
        log(f"  {r[0]}: {r[1]}")


if __name__ == "__main__":
    main()
