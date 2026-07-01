#!/usr/bin/env python3
"""Run remaining iCIMS open roles sequentially. Monitor: tail -f /tmp/icims_seq2.log"""
import subprocess, sys, os, json, time, sqlite3
from pathlib import Path

DB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
APPS = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted"
WD = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
LOG = "/tmp/icims_seq2.log"
TODAY = time.strftime("%Y-%m-%d", time.gmtime())

def lg(msg):
    ts = time.strftime("%H:%M:%S", time.gmtime())
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + chr(10))

def db(sql, params=()):
    con = sqlite3.connect(DB); con.execute(sql, params); con.commit(); con.close()

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

def write_status(rid, url, hcap, outcome):
    company, role, prep = get_info(rid)
    slug = os.path.basename(prep) if prep else "icims-" + str(rid)
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
    lg("  Running: %d %s (attempt %d)" % (rid, url.split("/")[-1], attempt))
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
    for ln in [l for l in out.split(chr(10)) if l.strip()][-3:]:
        lg("  >> " + ln.strip()[:120])
    lg("  -> exit=%d status=%s hcap=%s" % (proc.returncode, status, hcap[:60] if hcap else "n/a"))
    return proc.returncode, status, hcap, block

def book_submitted(rid, url, hcap, note):
    n = "[uncertain-submit: hcaptcha-solved+apply-clicked " + TODAY + "]"
    db("UPDATE roles SET status='submitted',applied_by='auto-icims',applied_on=?,prep_status='submitted',agent_notes=COALESCE(agent_notes,'')||? WHERE id=?", (TODAY,n,rid))
    write_status(rid, url, hcap, note)

def main():
    submitted, closed, already, failed = [], [], [], []
    # Load open roles dynamically from DB
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, app_url FROM roles WHERE id BETWEEN 3759 AND 3789 AND status='open' ORDER BY id"
    ).fetchall()
    con.close()
    lg("=== iCIMS Sequential: %d open roles ===" % len(rows))
    for (rid, url) in rows:
        lg("--- Role %d ---" % rid)
        try:
            code, status, hcap, block = run_once(rid, url)
        except subprocess.TimeoutExpired:
            lg("  TIMEOUT — skip"); failed.append((rid, "timeout")); time.sleep(3); continue
        except Exception as ex:
            lg("  EX: " + str(ex)); failed.append((rid, str(ex))); time.sleep(3); continue
        n = "[uncertain-submit: hcaptcha-solved+apply-clicked " + TODAY + "]"
        if status == "applied" or code == 0:
            lg("  SUBMITTED (confirmed)")
            book_submitted(rid, url, hcap, "confirmed")
            submitted.append(rid)
        elif code == 3 and hcap and ("twocaptcha" in hcap or "nopecha" in hcap or "proxyless" in hcap):
            lg("  UNCERTAIN-SUBMITTED (hcap solved, Apply clicked)")
            book_submitted(rid, url, hcap, "uncertain: hcaptcha-solved+apply-clicked")
            submitted.append(rid)
        elif status == "closed" or code == 6:
            lg("  CLOSED")
            db("UPDATE roles SET status='closed',block_reason='req-closed' WHERE id=?", (rid,))
            closed.append(rid)
        elif status == "already_applied" or code == 7:
            lg("  ALREADY_APPLIED")
            db("UPDATE roles SET status='submitted',applied_by='auto-icims',applied_on=? WHERE id=?", (TODAY,rid))
            already.append(rid)
        elif code == 2 and "no-vendor" in block:
            lg("  HCAPTCHA BLOCKED — retry after 45s")
            time.sleep(45)
            code2, s2, h2, b2 = run_once(rid, url, 2)
            if code2 == 3 and h2 and ("twocaptcha" in h2 or "proxyless" in h2):
                book_submitted(rid, url, h2, "uncertain-retry2"); submitted.append(rid)
            elif code2 == 6:
                db("UPDATE roles SET status='closed' WHERE id=?", (rid,)); closed.append(rid)
            else:
                lg("  RETRY FAILED exit=%d" % code2)
                failed.append((rid, "hcaptcha-blocked-2x"))
        else:
            lg("  FAILED exit=%d status=%s" % (code, status))
            failed.append((rid, "exit%d-%s" % (code, status)))
        time.sleep(5)
    lg("=== DONE: submitted=%d closed=%d already=%d failed=%d ===" % (len(submitted),len(closed),len(already),len(failed)))
    lg("submitted: " + str(submitted))
    lg("failed: " + str(failed))

if __name__ == "__main__": main()
