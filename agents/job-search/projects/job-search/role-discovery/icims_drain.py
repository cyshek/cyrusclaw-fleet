#!/usr/bin/env python3
"""
icims_drain.py — Drain all open iCIMS roles sequentially.
Runs one role at a time. Monitor via: tail -f /tmp/icims_drain.log
"""
import subprocess, sys, os, json, time, sqlite3
from pathlib import Path

HERE = Path(__file__).parent.absolute()
DB = str(HERE.parent / "tracker.db")
APPS = str(HERE.parent / "applications" / "submitted")
PYTHON = str(HERE / ".venv" / "bin" / "python3")
RUNNER = str(HERE / "_icims_runner.py")
LOG = "/tmp/icims_drain.log"
TODAY = time.strftime("%Y-%m-%d", time.gmtime())

ICIMS_ROLES = [
    # SiriusXM
    (3758, "https://uscareers-siriusxmradio.icims.com/jobs/17396/login"),
    (3759, "https://uscareers-siriusxmradio.icims.com/jobs/17398/login"),
    (3760, "https://uscareers-siriusxmradio.icims.com/jobs/17393/login"),
    # AMD
    (3761, "https://careers-amd.icims.com/jobs/87205/login"),
    (3762, "https://careers-amd.icims.com/jobs/87265/login"),
    (3763, "https://careers-amd.icims.com/jobs/87077/login"),
    (3764, "https://careers-amd.icims.com/jobs/87117/login"),
    (3765, "https://careers-amd.icims.com/jobs/86326/login"),
    (3766, "https://careers-amd.icims.com/jobs/86904/login"),
    (3767, "https://careers-amd.icims.com/jobs/86949/login"),
    (3768, "https://careers-amd.icims.com/jobs/86687/login"),
    (3769, "https://careers-amd.icims.com/jobs/86615/login"),
    (3770, "https://careers-amd.icims.com/jobs/86479/login"),
    (3771, "https://canadacareers-amd.icims.com/jobs/86384/login"),
    (3772, "https://careers-amd.icims.com/jobs/86128/login"),
    (3773, "https://careers-amd.icims.com/jobs/86406/login"),
    (3774, "https://careers-amd.icims.com/jobs/79943/login"),
    (3775, "https://careers-amd.icims.com/jobs/80554/login"),
    (3776, "https://careers-amd.icims.com/jobs/84726/login"),
    (3777, "https://careers-amd.icims.com/jobs/86014/login"),
    (3778, "https://careers-amd.icims.com/jobs/85750/login"),
    (3779, "https://careers-amd.icims.com/jobs/84929/login"),
    (3780, "https://careers-amd.icims.com/jobs/84268/login"),
    (3781, "https://careers-amd.icims.com/jobs/80409/login"),
    (3782, "https://careers-amd.icims.com/jobs/80071/login"),
    (3783, "https://careers-amd.icims.com/jobs/80274/login"),
    # Keysight
    (3787, "https://careers-keysight.icims.com/jobs/53104/login"),
    (3788, "https://careers-keysight.icims.com/jobs/51760/login"),
    (3789, "https://careers-keysight.icims.com/jobs/50012/login"),
]


def lg(msg):
    ts = time.strftime("%H:%M:%S", time.gmtime())
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + chr(10))


def dbq(sql, params=()):
    con = sqlite3.connect(DB)
    con.execute(sql, params)
    con.commit()
    con.close()


def get_status(rid):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT status FROM roles WHERE id=?", (rid,)).fetchone()
    con.close()
    return row[0] if row else "unknown"


def get_info(rid):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT company, role, prep_path FROM roles WHERE id=?", (rid,)).fetchone()
    con.close()
    return row or ("Unknown", "Unknown", "")


def write_status_md(rid, url, hcap, outcome):
    company, role, prep = get_info(rid)
    slug = os.path.basename(prep) if prep else ("icims-%d" % rid)
    d = Path(APPS) / slug
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        "SUBMITTED -- %s" % TODAY,
        "role_id: %d" % rid,
        "company: %s" % company,
        "role: %s" % role,
        "url: %s" % url,
        "submitted_by: auto-icims (_icims_runner.py)",
        "confirmation: %s" % outcome,
        "hcaptcha_solve: %s" % str(hcap),
        "resume_attached: iCIMS profile (no file input in gate flow)",
    ]
    (d / "STATUS.md").write_text("\n".join(lines) + "\n")
    lg("  STATUS.md -> %s" % str(d))


def book_submitted(rid, url, hcap, note):
    agent_note = "[uncertain-submit: hcaptcha-solved+apply-clicked %s]" % TODAY
    dbq(
        "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on=?, "
        "prep_status='submitted', agent_notes=COALESCE(agent_notes,'')||? WHERE id=?",
        (TODAY, " " + agent_note, rid),
    )
    write_status_md(rid, url, hcap, note)


def book_confirmed(rid, url, hcap):
    dbq(
        "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on=?, "
        "prep_status='submitted', agent_notes='[confirmed-submit %s]' WHERE id=?",
        (TODAY, rid),
    )
    write_status_md(rid, url, hcap, "confirmed")


def book_closed(rid):
    dbq(
        "UPDATE roles SET status='closed', block_reason='req-closed', "
        "agent_notes='[closed %s]' WHERE id=?" % TODAY,
        (rid,),
    )


def book_already(rid, url, hcap):
    dbq(
        "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on=?, "
        "prep_status='submitted', agent_notes='[already-applied %s]' WHERE id=?" % TODAY,
        (TODAY, rid),
    )
    write_status_md(rid, url, hcap, "already-applied")


def book_blocked(rid, reason):
    dbq(
        "UPDATE roles SET status='blocked', block_reason=?, "
        "agent_notes='[blocked %s: hcaptcha-timeout-or-unsolvable]' WHERE id=?" % TODAY,
        (reason, rid),
    )


def run_role(rid, url, attempt=1):
    lg("  runner: %d %s (attempt %d)" % (rid, url.split("/jobs/")[1][:30], attempt))
    env = os.environ.copy()
    env["JOBSEARCH_CDP"] = "http://127.0.0.1:19223"
    # Ensure PROXY_2CAPTCHA is NOT set (forces proxyless hCaptcha)
    env.pop("PROXY_2CAPTCHA", None)
    env["PROXY_2CAPTCHA"] = ""

    try:
        proc = subprocess.run(
            [PYTHON, RUNNER, "--url", url, "--cdp", "http://127.0.0.1:19223"],
            cwd=str(HERE),
            env=env,
            capture_output=True,
            text=True,
            timeout=750,
        )
    except subprocess.TimeoutExpired:
        lg("  TIMEOUT (750s)")
        return None, "timeout", "n/a", ""

    out = proc.stdout + proc.stderr

    # Parse JSON result - handle both single-line and multi-line pretty-printed JSON
    result = {}
    # Try single-line JSON first
    for line in reversed(out.split("\n")):
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                result = json.loads(stripped)
                break
            except Exception:
                pass
    # If single-line failed, try to extract multi-line JSON block
    if not result:
        import re
        # Find the last { ... } block in the output
        matches = list(re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', out, re.DOTALL))
        if matches:
            try:
                result = json.loads(matches[-1].group(0))
            except Exception:
                pass

    status = result.get("status", "unknown")
    hcap = result.get("hcaptcha_solve", "n/a")
    block = result.get("block_reason", "")

    # Fallback: detect hcaptcha solved from raw output lines if JSON parse missed it
    if hcap == "n/a":
        if "hCaptcha solved via 2Captcha proxyless" in out or "solved-via-twocaptcha-proxyless" in out:
            hcap = "solved-via-twocaptcha-proxyless"
        elif "hCaptcha solved via nopecha" in out:
            hcap = "solved-via-nopecha"

    # Log last few lines
    tail = [l.strip() for l in out.split("\n") if l.strip()][-5:]
    for ln in tail:
        lg("  >> %s" % ln[:130])

    lg("  -> exit=%d status=%s hcap=%s" % (proc.returncode, status, str(hcap)[:80]))
    return proc.returncode, status, hcap, block


def process_role(rid, url):
    code, status, hcap, block = run_role(rid, url)

    if code is None:
        return "timeout"

    # Confirmed submit
    if status == "applied" or code == 0:
        lg("  SUBMITTED (confirmed)")
        book_confirmed(rid, url, hcap)
        return "submitted"

    # Uncertain submit: hCaptcha solved + Apply clicked (exit 3 = submit-no-confirm)
    if code == 3 and hcap and ("twocaptcha" in str(hcap) or "proxyless" in str(hcap) or "nopecha" in str(hcap)):
        lg("  UNCERTAIN-SUBMITTED (hCaptcha solved, Apply clicked)")
        book_submitted(rid, url, hcap, "uncertain: hcaptcha-solved+apply-clicked")
        return "submitted"

    # Closed
    if status == "closed" or code == 6:
        lg("  CLOSED")
        book_closed(rid)
        return "closed"

    # Already applied
    if status == "already_applied" or code == 7:
        lg("  ALREADY_APPLIED")
        book_already(rid, url, hcap)
        return "submitted"

    # hCaptcha blocked - retry once after 45s delay
    if code == 2 and "no-vendor" in str(block):
        lg("  hCaptcha blocked — retrying after 45s...")
        time.sleep(45)
        code2, status2, hcap2, block2 = run_role(rid, url, attempt=2)
        if code2 is None:
            return "timeout"
        if code2 == 3 and hcap2 and ("twocaptcha" in str(hcap2) or "proxyless" in str(hcap2)):
            lg("  RETRY: UNCERTAIN-SUBMITTED")
            book_submitted(rid, url, hcap2, "uncertain-retry2: hcaptcha-solved+apply-clicked")
            return "submitted"
        if status2 == "applied" or code2 == 0:
            lg("  RETRY: SUBMITTED (confirmed)")
            book_confirmed(rid, url, hcap2)
            return "submitted"
        if code2 == 6:
            book_closed(rid)
            return "closed"
        lg("  RETRY ALSO BLOCKED: exit=%d" % code2)
        book_blocked(rid, "hcaptcha-blocked-2x: %s" % str(block2)[:80])
        return "blocked"

    # hCaptcha timeout - retry once
    if code == 2 and "timeout" in str(block):
        lg("  hCaptcha timeout — retrying after 30s...")
        time.sleep(30)
        code2, status2, hcap2, block2 = run_role(rid, url, attempt=2)
        if code2 is None:
            return "timeout"
        if code2 == 3 and hcap2 and ("twocaptcha" in str(hcap2) or "proxyless" in str(hcap2)):
            lg("  RETRY: UNCERTAIN-SUBMITTED")
            book_submitted(rid, url, hcap2, "uncertain-retry2: hcaptcha-solved+apply-clicked")
            return "submitted"
        if status2 == "applied" or code2 == 0:
            book_confirmed(rid, url, hcap2)
            return "submitted"
        if code2 == 6:
            book_closed(rid)
            return "closed"
        book_blocked(rid, "hcaptcha-timeout-2x: %s" % str(block2)[:80])
        return "blocked"

    # Any other failure
    lg("  FAILED: exit=%d status=%s block=%s" % (code, status, block))
    return "failed"


def main():
    lg("=== iCIMS DRAIN START: %d roles ===" % len(ICIMS_ROLES))
    results = {"submitted": [], "closed": [], "blocked": [], "failed": [], "skipped": []}

    for rid, url in ICIMS_ROLES:
        cur = get_status(rid)
        if cur in ("submitted", "applied", "closed"):
            lg("SKIP %d: already %s" % (rid, cur))
            results["skipped"].append(rid)
            continue

        lg("=== Role %d ===" % rid)
        try:
            outcome = process_role(rid, url)
        except Exception as ex:
            lg("  EXCEPTION: %s" % str(ex))
            outcome = "failed"

        results.setdefault(outcome, []).append(rid)
        # Small pause between roles to avoid concurrent session issues
        time.sleep(8)

    lg("=== DONE ===")
    lg("submitted (%d): %s" % (len(results["submitted"]), results["submitted"]))
    lg("closed    (%d): %s" % (len(results["closed"]), results["closed"]))
    lg("blocked   (%d): %s" % (len(results["blocked"]), results["blocked"]))
    lg("failed    (%d): %s" % (len(results["failed"]), results["failed"]))
    lg("skipped   (%d): %s" % (len(results["skipped"]), results["skipped"]))


if __name__ == "__main__":
    main()
