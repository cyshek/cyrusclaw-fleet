#!/usr/bin/env python3
"""
icims_submit_batch.py — orchestrate iCIMS submissions serially.
Runs inline_submit prep + _icims_runner for each role, then updates tracker.db.
"""
import subprocess, sys, os, json, sqlite3, datetime, time

VENV_PY = "role-discovery/.venv/bin/python"
DB_PATH = "tracker.db"
CDP = "http://127.0.0.1:18800"
TODAY = datetime.date.today().isoformat()
LOG_FILE = ".icims-batch-{}.log".format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))

ROLES = [
    # AMD x23
    (3761, "https://careers-amd.icims.com/jobs/87205/login",  "Program Manager", "AMD"),
    (3762, "https://careers-amd.icims.com/jobs/87265/login",  "Cluster Applications & Experience Program Manager", "AMD"),
    (3763, "https://careers-amd.icims.com/jobs/87077/login",  "Technical Program Manager - Manufacturing Test", "AMD"),
    (3764, "https://careers-amd.icims.com/jobs/87117/login",  "Technical Program Manager - Server Customer Escalations", "AMD"),
    (3765, "https://careers-amd.icims.com/jobs/86326/login",  "Occupational Health Program Manager", "AMD"),
    (3766, "https://careers-amd.icims.com/jobs/86904/login",  "Technical Program Manager, Pre-Silicon Development", "AMD"),
    (3767, "https://careers-amd.icims.com/jobs/86949/login",  "Privacy Program Manager", "AMD"),
    (3768, "https://careers-amd.icims.com/jobs/86687/login",  "Rack Expansion Program Manager", "AMD"),
    (3769, "https://careers-amd.icims.com/jobs/86615/login",  "Program Manager - Value Added Services", "AMD"),
    (3770, "https://careers-amd.icims.com/jobs/86479/login",  "Ethics & Compliance Program Manager", "AMD"),
    (3771, "https://canadacareers-amd.icims.com/jobs/86384/login", "Software Solutions Architect", "AMD"),
    (3772, "https://careers-amd.icims.com/jobs/86128/login",  "Product Manager - Client Strategy", "AMD"),
    (3773, "https://careers-amd.icims.com/jobs/86406/login",  "Customer Program Manager - Rack Scale CPU Solutions", "AMD"),
    (3774, "https://careers-amd.icims.com/jobs/79943/login",  "Logistics Principle Program Manager", "AMD"),
    (3775, "https://careers-amd.icims.com/jobs/80554/login",  "Technical Program Manager - SOC", "AMD"),
    (3776, "https://careers-amd.icims.com/jobs/84726/login",  "Solutions Architect", "AMD"),
    (3777, "https://careers-amd.icims.com/jobs/86014/login",  "Enterprise Solutions Product Manager", "AMD"),
    (3778, "https://careers-amd.icims.com/jobs/85750/login",  "Technical Program Manager - AI Cluster Validation", "AMD"),
    (3779, "https://careers-amd.icims.com/jobs/84929/login",  "Software Program Manager - SoC Diagnostics", "AMD"),
    (3780, "https://careers-amd.icims.com/jobs/84268/login",  "Embedded Diagnostics Program Manager", "AMD"),
    (3781, "https://careers-amd.icims.com/jobs/80409/login",  "Technical Program Manager - Training at Scale", "AMD"),
    (3782, "https://careers-amd.icims.com/jobs/80071/login",  "AI/ML Silicon Verification Solutions Engineer", "AMD"),
    (3783, "https://careers-amd.icims.com/jobs/80274/login",  "Customer Solutions Engineer - Hardware Systems", "AMD"),
    # Keysight x3
    (3787, "https://careers-keysight.icims.com/jobs/53104/login", "RFuW Field Solutions Engineer", "Keysight"),
    (3788, "https://careers-keysight.icims.com/jobs/51760/login", "Solutions Engineer - EDA", "Keysight"),
    (3789, "https://careers-keysight.icims.com/jobs/50012/login", "Electro Optical Software Product Manager", "Keysight"),
    # SiriusXM x3
    (3758, "https://uscareers-siriusxmradio.icims.com/jobs/17396/login", "Technical Program Manager", "SiriusXM"),
    (3759, "https://uscareers-siriusxmradio.icims.com/jobs/17398/login", "Associate Technical Program Manager", "SiriusXM"),
    (3760, "https://uscareers-siriusxmradio.icims.com/jobs/17393/login", "Technical Program Manager, Web Commerce & Marketing", "SiriusXM"),
]


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = "[{}] {}".format(ts, msg)
    print(line, flush=True)
    with open(LOG_FILE, "a") as fh:
        fh.write(line + "\n")


def db_update(role_id, status, applied_by=None, applied_on=None,
              block_reason=None, agent_notes=None):
    db = sqlite3.connect(DB_PATH)
    fields = ["status=?"]
    vals = [status]
    if applied_by is not None:
        fields.append("applied_by=?"); vals.append(applied_by)
    if applied_on is not None:
        fields.append("applied_on=?"); vals.append(applied_on)
    if block_reason is not None:
        fields.append("block_reason=?"); vals.append(block_reason)
    if agent_notes is not None:
        fields.append("agent_notes=?"); vals.append(agent_notes)
    vals.append(role_id)
    db.execute("UPDATE roles SET {} WHERE id=?".format(", ".join(fields)), vals)
    db.commit()
    db.close()


def write_status_md(slug, content):
    d = "role-discovery/applications/submitted/{}".format(slug)
    os.makedirs(d, exist_ok=True)
    with open("{}/STATUS.md".format(d), "w") as fh:
        fh.write(content)


def run_prep(role_id):
    """Run inline_submit.py --role-id to create the prep packet."""
    r = subprocess.run(
        [VENV_PY, "role-discovery/inline_submit.py", "--role-id", str(role_id)],
        capture_output=True, text=True, timeout=120
    )
    return r.returncode, r.stdout[-2000:], r.stderr[-500:]


def run_runner(url, role_id):
    """Run the iCIMS runner. Returns exit_code, stdout, stderr."""
    debug_dir = ".icims-debug/{}".format(role_id)
    os.makedirs(debug_dir, exist_ok=True)
    r = subprocess.run(
        [VENV_PY, "role-discovery/_icims_runner.py",
         "--url", url, "--apply",
         "--cdp", CDP,
         "--debug", debug_dir,
         "--max-seconds", "480",
         "--otp-timeout", "120"],
        capture_output=True, text=True, timeout=600
    )
    return r.returncode, r.stdout, r.stderr


def make_slug(role_id, company, role_name):
    """Generate slug: <company-slug>-<role-slug>-<id>"""
    c = company.lower().replace(" ", "-").replace("&", "and")
    r = role_name.lower().replace(" ", "-").replace(",", "").replace("(", "").replace(")", "").replace("/", "-")
    r = r[:40].rstrip("-")
    return "{}-{}-{}".format(c, r, role_id)


def process_role(role_id, url, role_name, company):
    log("")
    log("=" * 60)
    log("[{}] {} | {}".format(role_id, company, role_name))
    log("URL: {}".format(url))

    # Step 1: Prep
    log("Step 1: prep...")
    try:
        prep_rc, prep_out, prep_err = run_prep(role_id)
        log("Prep exit={}".format(prep_rc))
        if prep_out.strip():
            log("Prep stdout: {}".format(prep_out[-300:]))
        if prep_err.strip():
            log("Prep stderr: {}".format(prep_err[-200:]))
    except subprocess.TimeoutExpired:
        log("Prep TIMEOUT — continuing to runner anyway")
        prep_rc = -1

    # Step 2: Runner
    log("Step 2: _icims_runner --apply...")
    try:
        rc, stdout, stderr = run_runner(url, role_id)
    except subprocess.TimeoutExpired:
        log("Runner TIMEOUT (420s)")
        rc = 5
        stdout = ""
        stderr = "timeout"

    log("Runner exit={}".format(rc))
    if stdout.strip():
        log("Runner stdout: {}".format(stdout[-600:]))
    if stderr.strip():
        log("Runner stderr: {}".format(stderr[-300:]))

    # Parse JSON from stdout
    result_json = {}
    for line in stdout.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                result_json = json.loads(stripped)
            except Exception:
                pass

    slug = make_slug(role_id, company, role_name)
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    if rc == 0:
        outcome = "submitted"
        log("SUBMITTED [{}] {}".format(role_id, role_name))
        conf_url = result_json.get("confirmation_url", "")
        conf_text = result_json.get("confirmation_text", "")
        write_status_md(slug,
            "SUBMITTED -- {}\n\nrole_id: {}\nslug: {}\ncompany: {}\nrole: {}\nurl: {}\n"
            "submitted_by: _icims_runner\nresume_attached: yes\n"
            "confirmation_url: {}\nconfirmation_text: {}\n".format(
                now_ts, role_id, slug, company, role_name, url, conf_url, conf_text))
        db_update(role_id, "submitted", applied_by="auto", applied_on=TODAY,
                  block_reason=None, agent_notes="icims_runner auto-submit")

    elif rc == 2:
        outcome = "hcaptcha-blocked"
        block_r = result_json.get("block_reason", "icims-hcaptcha-no-vendor")
        log("HCAPTCHA/AUTH-BLOCKED [{}] {} -- {}".format(role_id, role_name, block_r))
        db_update(role_id, "blocked", block_reason=block_r,
                  agent_notes="iCIMS runner EXIT 2: {}".format(block_r))
        write_status_md(slug,
            "BLOCKED -- {}\nrole_id: {}\nblock_reason: {}\n".format(
                now_ts, role_id, block_r))

    elif rc == 6:
        outcome = "closed"
        log("CLOSED [{}] {}".format(role_id, role_name))
        db_update(role_id, "closed", block_reason="closed-req",
                  agent_notes="iCIMS runner EXIT 6: req closed")
        write_status_md(slug,
            "CLOSED -- {}\nrole_id: {}\n".format(now_ts, role_id))

    elif rc == 7:
        outcome = "already-applied"
        log("ALREADY-APPLIED [{}] {}".format(role_id, role_name))
        db_update(role_id, "submitted", applied_by="auto", applied_on=TODAY,
                  block_reason=None, agent_notes="iCIMS runner EXIT 7: already applied")

    elif rc == 10:
        outcome = "otp-timeout"
        log("OTP-TIMEOUT [{}] {}".format(role_id, role_name))
        db_update(role_id, "blocked", block_reason="icims-otp-timeout",
                  agent_notes="iCIMS runner EXIT 10: OTP not received within 120s budget")
        write_status_md(slug,
            "OTP-TIMEOUT -- {}\nrole_id: {}\n".format(now_ts, role_id))

    else:
        outcome = "error-exit-{}".format(rc)
        block_r = result_json.get("block_reason", "icims-runner-exit-{}".format(rc))
        log("EXIT={} [{}] {}: {}".format(rc, role_id, role_name, block_r))
        db_update(role_id, "blocked", block_reason=block_r,
                  agent_notes="iCIMS runner EXIT {}: {}".format(rc, block_r))
        write_status_md(slug,
            "BLOCKED -- {}\nrole_id: {}\nexit: {}\nblock_reason: {}\n".format(
                now_ts, role_id, rc, block_r))

    return rc, outcome


def main():
    log("=== iCIMS BATCH START {} ===".format(datetime.datetime.now()))
    log("CDP: {}".format(CDP))
    log("Total roles: {}".format(len(ROLES)))

    # Per-tenant hCaptcha tracking
    tenant_hcaptcha = {}  # tenant_host -> consecutive_block_count
    skipped = {}          # role_id -> reason

    summary = []  # (role_id, company, role_name, outcome)

    for role_id, url, role_name, company in ROLES:
        if role_id in skipped:
            reason = skipped[role_id]
            log("SKIP [{}] {} ({})".format(role_id, role_name, reason))
            summary.append((role_id, company, role_name, "skipped:" + reason))
            continue

        rc, outcome = process_role(role_id, url, role_name, company)
        summary.append((role_id, company, role_name, outcome))

        tenant = url.split("/")[2]  # e.g. careers-amd.icims.com

        if rc == 2:
            tenant_hcaptcha[tenant] = tenant_hcaptcha.get(tenant, 0) + 1
            count = tenant_hcaptcha[tenant]

            # AMD: after 3 consecutive hcaptcha blocks, declare tenant blocked
            if company == "AMD" and count >= 3:
                remaining = [r for r in ROLES
                             if r[3] == "AMD" and r[0] not in {s[0] for s in summary}
                             and r[0] not in skipped]
                log("AMD hCaptcha count={} (>=3) -- declaring tenant blocked, skipping {} remaining".format(
                    count, len(remaining)))
                for rem_id, rem_url, rem_name, rem_co in remaining:
                    skipped[rem_id] = "AMD-tenant-hcaptcha"
                    db_update(rem_id, "blocked",
                              block_reason="icims-hcaptcha-no-vendor",
                              agent_notes="AMD tenant hcaptcha after {} blocks".format(count))
                    write_status_md(make_slug(rem_id, rem_co, rem_name),
                        "BLOCKED -- {}\nrole_id: {}\nblock_reason: icims-hcaptcha-no-vendor\n"
                        "agent_notes: AMD tenant hcaptcha declared after {} consecutive blocks\n".format(
                            datetime.datetime.now().isoformat(), rem_id, count))
                    log("  marked blocked: [{}] {}".format(rem_id, rem_name))

            # SiriusXM: first block -> skip remaining 2
            if company == "SiriusXM":
                remaining_sxm = [r for r in ROLES
                                  if r[3] == "SiriusXM"
                                  and r[0] not in {s[0] for s in summary}
                                  and r[0] not in skipped]
                if remaining_sxm:
                    log("SiriusXM first hCaptcha block -- skipping {} remaining".format(
                        len(remaining_sxm)))
                    for rem_id, rem_url, rem_name, rem_co in remaining_sxm:
                        skipped[rem_id] = "SiriusXM-tenant-hcaptcha"
                        db_update(rem_id, "blocked",
                                  block_reason="icims-hcaptcha-no-vendor",
                                  agent_notes="SiriusXM tenant hcaptcha: first role blocked, skipping remainder")
                        write_status_md(make_slug(rem_id, rem_co, rem_name),
                            "BLOCKED -- {}\nrole_id: {}\nblock_reason: icims-hcaptcha-no-vendor\n"
                            "agent_notes: SiriusXM tenant hcaptcha declared\n".format(
                                datetime.datetime.now().isoformat(), rem_id))
                        log("  marked blocked: [{}] {}".format(rem_id, rem_name))
        else:
            # Reset consecutive hcaptcha count on non-block
            tenant_hcaptcha[tenant] = 0

        time.sleep(3)

    # Print summary
    log("")
    log("=" * 60)
    log("=== BATCH SUMMARY ===")

    submitted = [(r, c, n) for r, c, n, o in summary if o == "submitted"]
    already = [(r, c, n) for r, c, n, o in summary if o == "already-applied"]
    blocked = [(r, c, n) for r, c, n, o in summary if "hcaptcha-blocked" in o]
    closed = [(r, c, n) for r, c, n, o in summary if o == "closed"]
    otp = [(r, c, n) for r, c, n, o in summary if o == "otp-timeout"]
    errors = [(r, c, n, o) for r, c, n, o in summary if o.startswith("error-exit")]
    skip_items = [(r, c, n, o) for r, c, n, o in summary if o.startswith("skipped:")]

    if submitted:
        log("\nSUBMITTED ({})".format(len(submitted)))
        for r, c, n in submitted:
            log("  [{}] {} | {}".format(r, c, n))
    if already:
        log("\nALREADY-APPLIED ({})".format(len(already)))
        for r, c, n in already:
            log("  [{}] {} | {}".format(r, c, n))
    if blocked:
        log("\nhCAPTCHA-BLOCKED ({})".format(len(blocked)))
        for r, c, n in blocked:
            log("  [{}] {} | {}".format(r, c, n))
    if skip_items:
        log("\nSKIPPED-TENANT-BLOCKED ({})".format(len(skip_items)))
        for r, c, n, o in skip_items:
            log("  [{}] {} | {}".format(r, c, n))
    if closed:
        log("\nCLOSED ({})".format(len(closed)))
        for r, c, n in closed:
            log("  [{}] {} | {}".format(r, c, n))
    if otp:
        log("\nOTP-TIMEOUT ({})".format(len(otp)))
        for r, c, n in otp:
            log("  [{}] {} | {}".format(r, c, n))
    if errors:
        log("\nERROR ({})".format(len(errors)))
        for r, c, n, o in errors:
            log("  [{}] {} | {} ({})".format(r, c, n, o))

    log("")
    log("TOTALS: submitted={} already={} hcaptcha-blocked={} skipped={} closed={} otp={} errors={}".format(
        len(submitted), len(already), len(blocked), len(skip_items),
        len(closed), len(otp), len(errors)))
    log("Log: {}".format(LOG_FILE))

    return summary


if __name__ == "__main__":
    main()
