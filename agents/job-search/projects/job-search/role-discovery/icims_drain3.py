#!/usr/bin/env python3
# icims_drain3 -- auto-generated sequential iCIMS drain
import subprocess, os, json, sqlite3, datetime, time, pathlib

WORK_DIR = pathlib.Path(__file__).parent
PROJECT_DIR = WORK_DIR.parent
DB_PATH = PROJECT_DIR / "tracker.db"
APPS_DIR = PROJECT_DIR / "applications" / "submitted"
VENV = str(WORK_DIR / ".venv" / "bin" / "python")
RUNNER = str(WORK_DIR / "_icims_runner.py")
LOG_FILE = "/tmp/icims_drain3.log"
TODAY = datetime.date.today().isoformat()

ROLES = [
    (3762, "AMD", "Cluster Applications PM", "https://careers-amd.icims.com/jobs/87265/login"),
    (3764, "AMD", "TPM Server Customer Eng", "https://careers-amd.icims.com/jobs/87117/login"),
    (3765, "AMD", "OH Program Manager", "https://careers-amd.icims.com/jobs/86326/login"),
    (3766, "AMD", "TPM Pre-Silicon Dev", "https://careers-amd.icims.com/jobs/86904/login"),
    (3767, "AMD", "Privacy Program Manager", "https://careers-amd.icims.com/jobs/86949/login"),
    (3768, "AMD", "Rack Expansion PM", "https://careers-amd.icims.com/jobs/86687/login"),
    (3769, "AMD", "PM Value Added Services", "https://careers-amd.icims.com/jobs/86615/login"),
    (3770, "AMD", "Ethics & Compliance PM", "https://careers-amd.icims.com/jobs/86479/login"),
    (3771, "AMD", "Software Solutions Arch", "https://canadacareers-amd.icims.com/jobs/86384/login"),
    (3772, "AMD", "PM Client Strategy", "https://careers-amd.icims.com/jobs/86128/login"),
    (3773, "AMD", "Customer PM Rack Scale", "https://careers-amd.icims.com/jobs/86406/login"),
    (3774, "AMD", "Logistics PM", "https://careers-amd.icims.com/jobs/79943/login"),
    (3775, "AMD", "TPM SOC", "https://careers-amd.icims.com/jobs/80554/login"),
    (3776, "AMD", "Solutions Architect", "https://careers-amd.icims.com/jobs/84726/login"),
    (3777, "AMD", "Enterprise Solutions PM", "https://careers-amd.icims.com/jobs/86014/login"),
    (3778, "AMD", "TPM AI Cluster", "https://careers-amd.icims.com/jobs/85750/login"),
    (3779, "AMD", "Software PM SoC", "https://careers-amd.icims.com/jobs/84929/login"),
    (3780, "AMD", "Embedded Diagnostics PM", "https://careers-amd.icims.com/jobs/84268/login"),
    (3781, "AMD", "TPM Training at Scale", "https://careers-amd.icims.com/jobs/80409/login"),
    (3782, "AMD", "AI/ML Silicon SE", "https://careers-amd.icims.com/jobs/80071/login"),
    (3783, "AMD", "Customer SE Hardware", "https://careers-amd.icims.com/jobs/80274/login"),
    (3787, "Keysight", "RFuW Field SE", "https://careers-keysight.icims.com/jobs/53104/login"),
    (3788, "Keysight", "Solutions Eng EDA", "https://careers-keysight.icims.com/jobs/51760/login"),
    (3789, "Keysight", "Electro Optical PM", "https://careers-keysight.icims.com/jobs/50012/login"),
]


def lg(msg):
    ts = datetime.datetime.utcnow().strftime('[%H:%M:%S]')
    line = ts + ' ' + msg
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + chr(10))


def get_status(rid):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT status FROM roles WHERE id=?', (rid,)).fetchone()
    conn.close()
    return row[0] if row else None


def db_mark(rid, status, reason=None):
    conn = sqlite3.connect(DB_PATH)
    if status == 'submitted':
        conn.execute('UPDATE roles SET status=?, applied_by=?, applied_on=?, prep_status=? WHERE id=?',
                     ('submitted','auto-icims',TODAY,'submitted',rid))
    elif status == 'blocked':
        conn.execute('UPDATE roles SET status=?, block_reason=? WHERE id=?',
                     ('blocked', reason or 'blocked', rid))
    elif status == 'closed':
        conn.execute('UPDATE roles SET status=?, block_reason=? WHERE id=?',
                     ('closed','req-closed',rid))
    conn.commit()
    conn.close()


def write_status_md(rid, company, role_name, url, rj, code):
    jid = url.split('/jobs/')[1].split('/')[0] if '/jobs/' in url else str(rid)
    co = company.lower().replace(' ','-').replace('/','')
    out_dir = APPS_DIR / (co + '-' + jid)
    out_dir.mkdir(parents=True, exist_ok=True)
    conf_url = (rj.get('final') or {}).get('conf_url') or url
    conf_text = (rj.get('final') or {}).get('conf_text') or ('Applied exit=%d' % code)
    txt = chr(10).join([
        '# ' + company + ' -- ' + role_name,
        'status: submitted',
        'submitted_by: auto-icims',
        'submitted_on: ' + TODAY,
        'confirmation_url: ' + conf_url,
        'confirmation_text: ' + conf_text,
        'hcaptcha: ' + str(rj.get('hcaptcha_solve','?')),
        'auth0: ' + str(rj.get('auth0','?')),
        'resume: ' + str(rj.get('resume','?')),
        'exit_code: ' + str(code),
    ]) + chr(10)
    (out_dir / 'STATUS.md').write_text(txt)
    lg('  STATUS.md: ' + str(out_dir))


def run_role(rid, company, role_name, url, attempt=1):
    env = os.environ.copy()
    env['JOBSEARCH_CDP'] = 'http://127.0.0.1:19223'
    env.pop('PROXY_2CAPTCHA', None)
    dbg = str(PROJECT_DIR / '.icims-debug' / str(rid))
    os.makedirs(dbg, exist_ok=True)
    cmd = [VENV, RUNNER, '--url', url, '--apply', '--debug', dbg,
           '--otp-timeout', '60', '--max-seconds', '480']
    lg('  runner #%d attempt=%d' % (rid, attempt))
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=str(WORK_DIR), env=env, timeout=550)
    except subprocess.TimeoutExpired:
        lg('  TIMEOUT #%d' % rid)
        return {}, 'timeout', 99
    elapsed = int(time.time()-t0)
    code = proc.returncode
    rj = {}
    for i, ln in enumerate(proc.stdout.splitlines()):
        if ln.strip().startswith('{'):
            try: rj = json.loads(chr(10).join(proc.stdout.splitlines()[i:]))
            except: pass
            break
    kws = ['icims]','error','blocked','solved','auth0','otp','submit','apply','resume','hcaptcha']
    for ln in proc.stderr.splitlines()[-40:]:
        if any(k in ln.lower() for k in kws):
            lg('  >> ' + ln)
    lg('  exit=%d status=%s t=%ds' % (code, rj.get('status','?'), elapsed))
    return rj, rj.get('status','?'), code


def process_role(rid, company, role_name, url):
    if get_status(rid) == 'submitted':
        lg('  SKIP #%d: already submitted' % rid)
        return 'skipped'
    rj, status, code = run_role(rid, company, role_name, url)
    if code in (0, 3):
        lg('  SUBMITTED #%d (exit=%d)' % (rid, code))
        write_status_md(rid, company, role_name, url, rj, code)
        db_mark(rid, 'submitted')
        return 'submitted'
    if code == 6:
        lg('  CLOSED #%d' % rid)
        db_mark(rid, 'closed')
        return 'closed'
    if code == 7:
        lg('  ALREADY_APPLIED #%d' % rid)
        db_mark(rid, 'submitted')
        return 'submitted'
    if code == 2:
        blk = rj.get('block_reason','')
        if 'no-vendor' in blk or 'unsolvable' in blk.lower() or 'twocaptcha-error' in blk:
            lg('  hCaptcha failed, retry 60s...')
            time.sleep(60)
            rj2, s2, c2 = run_role(rid, company, role_name, url, attempt=2)
            if c2 in (0, 3):
                lg('  SUBMITTED #%d retry' % rid)
                write_status_md(rid, company, role_name, url, rj2, c2)
                db_mark(rid, 'submitted')
                return 'submitted'
            r2 = rj2.get('block_reason') or ('exit='+str(c2))
            lg('  RETRY BLOCKED #%d: %s' % (rid, r2))
            db_mark(rid, 'blocked', r2)
            return 'blocked'
    reason = rj.get('block_reason') or ('exit='+str(code))
    lg('  BLOCKED #%d: %s' % (rid, reason))
    db_mark(rid, 'blocked', reason)
    return 'blocked'


def main():
    with open(LOG_FILE, 'a') as f:
        f.write(chr(10) + '='*60 + chr(10))
    lg('=== icims_drain3 START roles=%d ===' % len(ROLES))
    outcomes = {}
    for rid, company, role_name, url in ROLES:
        lg(chr(10) + '=== Role %d (%s: %s) ===' % (rid, company, role_name))
        result = process_role(rid, company, role_name, url)
        outcomes.setdefault(result, []).append(rid)
        time.sleep(8)
    lg(chr(10) + '=== DONE ===')
    for k in ('submitted','closed','blocked','skipped'):
        lg(k + ': ' + str(outcomes.get(k,[])))
    lg('Total submitted: %d' % len(outcomes.get('submitted',[])))


if __name__ == '__main__':
    main()
