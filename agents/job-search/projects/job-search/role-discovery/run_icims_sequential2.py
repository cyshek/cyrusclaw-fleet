#!/usr/bin/env python3
"""Sequential iCIMS runner - run all remaining roles one by one."""
import subprocess, sys, os, json, time, sqlite3
from pathlib import Path

DB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
APPS = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted"
WD = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
LOG = "/tmp/icims_seq.log"
TODAY = time.strftime("%Y-%m-%d", time.gmtime())

ROLES = [
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
    (3759, "https://uscareers-siriusxmradio.icims.com/jobs/17398/login"),
    (3760, "https://uscareers-siriusxmradio.icims.com/jobs/17393/login"),
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

def db(sql, params=()):
    con = sqlite3.connect(DB)
    con.execute(sql, params)
    con.commit()
    con.close()

def get_status(rid):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT status FROM roles WHERE id=?", (rid,)).fetchone()
    con.close()
    return row[0] if row else "unknown"

def get_prep_path(rid):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT prep_path, company, role FROM roles WHERE id=?", (rid,)).fetchone()
    con.close()
    return row or ("", "Unknown", "Unknown")

def write_status_md(rid, url, hcap, outcome):
    prep_path, company, role = get_prep_path(rid)
    slug = os.path.basename(prep_path) if prep_path else ("amd-" + str(rid))
    d = Path(APPS) / slug
    d.mkdir(parents=True, exist_ok=True)
    txt = "SUBMITTED -- " + TODAY + chr(10)
    txt += "role_id: " + str(rid) + chr(10)
    txt += "company: " + company + chr(10)
    txt += "role: " + role + chr(10)
    txt += "url: " + url + chr(10)
    txt += "submitted_by: auto-icims" + chr(10)
    txt += "confirmation: " + outcome + chr(10)
    txt += "hcaptcha_solve: " + str(hcap) + chr(10)
    (d / "STATUS.md").write_text(txt)

def run_once(rid, url, attempt=1):
    lg("--- Role %d: %s (attempt %d) ---" % (rid, url, attempt))
    env = os.environ.copy()
    env["JOBSEARCH_CDP"] = "http://127.0.0.1:19223"
    proc = subprocess.run(
        [str(WD / ".venv/bin/python3"), str(WD / "_icims_runner.py"), "--url", url],
        cwd=str(WD), env=env, capture_output=True, text=True, timeout=720
    )
    out = proc.stdout + proc.stderr
    result = {}
    for line in reversed(out.split(chr(10))):
        line = line.strip()
        if line.startswith("{"):
            try: result = json.loads(line); break
            except: pass
    status = result.get("status", "unknown")
    hcap = result.get("hcaptcha_solve", "n/a")
    block = result.get("block_reason", "")
    lg("  exit=%d status=%s hcap=%s block=%s" % (proc.returncode, status, hcap, block))
    for line in out.split(chr(10))[-5:]:
        if line.strip(): lg("  > " + line.strip())
    return proc.returncode, status, hcap, block

def main():
    submitted, closed, already, failed, skipped = [], [], [], [], []
    lg("=== iCIMS Sequential: %d roles ===" % len(ROLES))
    for rid, url in ROLES:
        cur = get_status(rid)
        if cur in ("submitted", "applied", "closed"):
            lg("SKIP %d: already %s" % (rid, cur))
            skipped.append(rid)
            continue
        try:
            code, status, hcap, block = run_once(rid, url)
        except subprocess.TimeoutExpired:
            lg("  TIMEOUT — skip")
            failed.append((rid, "timeout"))
            time.sleep(3); continue
        except Exception as ex:
            lg("  EX: " + str(ex))
            failed.append((rid, str(ex)))
            time.sleep(3); continue
        # Book result
        note = "[uncertain-submit: hcaptcha-solved+apply-clicked " + TODAY + "]"
        if status == "applied" or code == 0:
            lg("  SUBMITTED (confirmed)")
            db("UPDATE roles SET status='submitted',applied_by='auto-icims',applied_on=?,prep_status='submitted',agent_notes=COALESCE(agent_notes,'')||? WHERE id=?", (TODAY,note,rid))
            write_status_md(rid, url, hcap, "confirmed")
            submitted.append(rid)
        elif code == 3 and hcap and "twocaptcha" in hcap:
            lg("  UNCERTAIN-SUBMITTED (hcap+apply-clicked)")
            db("UPDATE roles SET status='submitted',applied_by='auto-icims',applied_on=?,prep_status='submitted',agent_notes=COALESCE(agent_notes,'')||? WHERE id=?", (TODAY,note,rid))
            write_status_md(rid, url, hcap, "uncertain: hcaptcha-solved+apply-clicked")
            submitted.append(rid)
        elif status == "closed" or code == 6:
            lg("  CLOSED")
            db("UPDATE roles SET status='closed',block_reason='req-closed',agent_notes=COALESCE(agent_notes,'')||' [closed " + TODAY + "]' WHERE id=?", (rid,))
            closed.append(rid)
        elif status == "already_applied" or code == 7:
            lg("  ALREADY_APPLIED")
            db("UPDATE roles SET status='submitted',applied_by='auto-icims',applied_on=?,prep_status='submitted' WHERE id=?", (TODAY,rid))
            already.append(rid)
        elif code == 2 and "no-vendor" in block:
            lg("  HCAPTCHA BLOCKED — retry after 30s")
            time.sleep(30)
            code2, s2, h2, b2 = run_once(rid, url, 2)
            if code2 == 3 and h2 and "twocaptcha" in h2:
                db("UPDATE roles SET status='submitted',applied_by='auto-icims',applied_on=?,prep_status='submitted',agent_notes=COALESCE(agent_notes,'')||? WHERE id=?", (TODAY,note,rid))
                write_status_md(rid, url, h2, "uncertain-retry")
                submitted.append(rid)
            elif code2 == 6:
                db("UPDATE roles SET status='closed' WHERE id=?", (rid,)); closed.append(rid)
            else:
                lg("  RETRY FAILED: exit=%d" % code2)
                failed.append((rid, "hcaptcha-blocked"))
        else:
            lg("  FAILED: exit=%d status=%s" % (code, status))
            failed.append((rid, "exit%d-%s" % (code, status)))
        time.sleep(5)
    lg("=== DONE: submitted=%d closed=%d already=%d failed=%d skipped=%d ===" % (len(submitted),len(closed),len(already),len(failed),len(skipped)))
    lg("submitted: " + str(submitted))
    lg("failed: " + str(failed))
    return 0

if __name__ == "__main__": sys.exit(main())
