#!/usr/bin/env python3
"""icims_drain2.py -- Sequential iCIMS drain with proper OTP handling."""

import subprocess, json, re, sqlite3, datetime, os, time
from pathlib import Path

CDP = "http://127.0.0.1:19223"
VENV = ".venv/bin/python3"
RUNNER = "_icims_runner.py"
DB_PATH = "../tracker.db"
APPS_DIR = Path("../applications/submitted")
LOG_PATH = "/tmp/icims_drain2.log"
OTP_TIMEOUT = 300
TODAY = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

ROLES = [
    (3787, "https://careers-keysight.icims.com/jobs/53104/login", "RFuW Field Solutions Engineer", "Keysight"),
    (3788, "https://careers-keysight.icims.com/jobs/51760/login", "Solutions Engineer EDA", "Keysight"),
    (3789, "https://careers-keysight.icims.com/jobs/50012/login", "Electro Optical Software PM", "Keysight"),
    (3763, "https://careers-amd.icims.com/jobs/87077/login", "TPM Manufacturing Test", "AMD"),
    (3764, "https://careers-amd.icims.com/jobs/87117/login", "TPM Server Customer Engineering", "AMD"),
    (3765, "https://careers-amd.icims.com/jobs/86326/login", "OH Program Manager", "AMD"),
    (3766, "https://careers-amd.icims.com/jobs/86904/login", "TPM Pre-Silicon Dev", "AMD"),
    (3767, "https://careers-amd.icims.com/jobs/86949/login", "Privacy Program Manager", "AMD"),
    (3768, "https://careers-amd.icims.com/jobs/86687/login", "Rack Expansion PM", "AMD"),
    (3769, "https://careers-amd.icims.com/jobs/86615/login", "PM Value Added Services", "AMD"),
    (3770, "https://careers-amd.icims.com/jobs/86479/login", "Ethics & Compliance PM", "AMD"),
    (3771, "https://canadacareers-amd.icims.com/jobs/86384/login", "Software Solutions Architect", "AMD"),
    (3772, "https://careers-amd.icims.com/jobs/86128/login", "PM Client Strategy", "AMD"),
    (3773, "https://careers-amd.icims.com/jobs/86406/login", "Customer PM Rack Scale", "AMD"),
    (3774, "https://careers-amd.icims.com/jobs/79943/login", "Logistics PM", "AMD"),
    (3775, "https://careers-amd.icims.com/jobs/80554/login", "TPM SOC", "AMD"),
    (3776, "https://careers-amd.icims.com/jobs/84726/login", "Solutions Architect", "AMD"),
    (3777, "https://careers-amd.icims.com/jobs/86014/login", "Enterprise Solutions PM", "AMD"),
    (3778, "https://careers-amd.icims.com/jobs/85750/login", "TPM AI Cluster Validation", "AMD"),
    (3779, "https://careers-amd.icims.com/jobs/84929/login", "Software PM SoC Diagnostics", "AMD"),
    (3780, "https://careers-amd.icims.com/jobs/84268/login", "Embedded Diagnostics PM", "AMD"),
    (3781, "https://careers-amd.icims.com/jobs/80409/login", "TPM Training at Scale", "AMD"),
    (3782, "https://careers-amd.icims.com/jobs/80071/login", "AI/ML Silicon Verification SE", "AMD"),
    (3783, "https://careers-amd.icims.com/jobs/80274/login", "Customer SE Hardware Systems", "AMD"),
]

def ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("[%H:%M:%S]")

def lg(msg):
    line = f"{ts()} {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line + "\n")

def db_exec(sql, *args):
    con = sqlite3.connect(DB_PATH)
    con.execute(sql, args)
    con.commit()
    con.close()

def db_query(sql, *args):
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(sql, args)
    rows = cur.fetchall()
    con.close()
    return rows

def get_status(role_id):
    rows = db_query("SELECT status FROM roles WHERE id=?", role_id)
    return rows[0][0] if rows else None

def make_slug(rid, company, role_name):
    comp = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    return f"{comp}-{rid}"

def write_status(slug, content):
    d = APPS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "STATUS.md").write_text(content)

def book_submitted(rid, company, role_name, url, note="uncertain"):
    slug = make_slug(rid, company, role_name)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    write_status(slug, f"SUBMITTED -- {now}\nrole_id: {rid}\nslug: {slug}\ncompany: {company}\nrole: {role_name}\nurl: {url}\nsubmitted_by: icims_drain2\nnote: {note}\n")
    db_exec("UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on=?, prep_status='submitted', agent_notes=? WHERE id=?",
            TODAY, f"[submitted 2026-07-01 icims_drain2: {note}]", rid)
    lg(f"  SUBMITTED: {company} #{rid} -- {note}")

def book_blocked(rid, reason):
    db_exec("UPDATE roles SET status='blocked', agent_notes=? WHERE id=?",
            f"[blocked 2026-07-01: {reason}]", rid)
    lg(f"  BLOCKED: #{rid} -- {reason}")

def book_closed(rid):
    db_exec("UPDATE roles SET status='closed', block_reason='req-closed', agent_notes='[closed 2026-07-01]' WHERE id=?", rid)
    lg(f"  CLOSED: #{rid}")

def run_runner(rid, url, attempt=1, otp_timeout=None):
    env = os.environ.copy()
    env["PROXY_2CAPTCHA"] = ""
    cmd = [VENV, RUNNER, "--url", url, "--cdp", CDP, "--apply"]
    if otp_timeout:
        cmd += ["--otp-timeout", str(otp_timeout)]
    lg(f"  runner #{rid} attempt={attempt} otp_timeout={otp_timeout or 90}")
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=700, env=env)
    elapsed = time.time() - t0
    code = proc.returncode
    stderr = proc.stderr
    stdout = proc.stdout
    for line in stderr.strip().split("\n"):
        if line.strip() and any(kw in line for kw in ["[icims]", "hCaptcha", "Auth0", "OTP", "Error", "block_reason"]):
            lg(f"  >> {line[:130]}")
    result = {}
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                result = json.loads(line)
                break
            except Exception:
                pass
    hcap = result.get("hcaptcha_solve", "")
    if not hcap and "hCaptcha solved via 2Captcha proxyless" in stderr:
        hcap = "solved-via-twocaptcha-proxyless"
    lg(f"  exit={code} status={result.get('status','?')} hcap={hcap} t={elapsed:.0f}s")
    result["_exit_code"] = code
    result["_hcap"] = hcap
    return code, result

def process_role(rid, url, role_name, company):
    cur = get_status(rid)
    if cur in ("submitted", "closed"):
        lg(f"SKIP #{rid}: already {cur}")
        return cur
    lg(f"=== Role {rid} ({company}: {role_name}) ===")
    is_amd = "amd.icims.com" in url
    otp_to = OTP_TIMEOUT if is_amd else 90

    def attempt(n, otp=None):
        try:
            return run_runner(rid, url, attempt=n, otp_timeout=otp)
        except subprocess.TimeoutExpired:
            lg(f"  TIMEOUT attempt {n}")
            return -1, {"_exit_code": -1, "_hcap": "", "status": "timeout"}
        except Exception as ex:
            lg(f"  ERROR attempt {n}: {ex}")
            return -99, {"_exit_code": -99, "_hcap": "", "status": "error"}

    def handle(code, res, n):
        hcap = res.get("_hcap", "")
        if code == 0:
            book_submitted(rid, company, role_name, url, note=f"exit=0 attempt{n}")
            return "submitted"
        if code == 3 and "twocaptcha" in hcap:
            book_submitted(rid, company, role_name, url, note=f"uncertain-hcaptcha attempt{n}")
            return "submitted"
        if code == 6:
            book_closed(rid)
            return "closed"
        if code == 7:
            book_submitted(rid, company, role_name, url, note=f"already-applied exit=7")
            return "submitted"
        if code == 10 and n < 3:
            wait_s = 240 if is_amd else 120
            lg(f"  OTP timeout (attempt {n}) -- waiting {wait_s}s for email delivery...")
            time.sleep(wait_s)
            c2, r2 = attempt(n + 1, otp=300)
            return handle(c2, r2, n + 1)
        if code == 2 and n < 3:
            lg(f"  hCaptcha UNSOLVABLE (attempt {n}) -- retrying in 60s...")
            time.sleep(60)
            c2, r2 = attempt(n + 1, otp=otp_to)
            return handle(c2, r2, n + 1)
        if code == 10:
            book_blocked(rid, f"otp-timeout-{n}x")
            return "blocked"
        if code == 2:
            book_blocked(rid, f"hcaptcha-unsolvable-{n}x")
            return "blocked"
        book_blocked(rid, f"exit={code} status={res.get('status','?')}")
        return "blocked"

    c, r = attempt(1, otp=otp_to)
    return handle(c, r, 1)

def main():
    lg(f"=== icims_drain2 START ===")
    lg(f"Roles: {len(ROLES)} | AMD OTP timeout: {OTP_TIMEOUT}s")
    outcomes = {}
    for rid, url, role_name, company in ROLES:
        outcomes[rid] = process_role(rid, url, role_name, company)
        time.sleep(3)
    s = [r for r, o in outcomes.items() if o == "submitted"]
    c = [r for r, o in outcomes.items() if o == "closed"]
    b = [r for r, o in outcomes.items() if o == "blocked"]
    lg(f"=== DONE | submitted={len(s)} closed={len(c)} blocked={len(b)} ===")
    lg(f"submitted: {s}")
    lg(f"closed:    {c}")
    lg(f"blocked:   {b}")

if __name__ == "__main__":
    main()
