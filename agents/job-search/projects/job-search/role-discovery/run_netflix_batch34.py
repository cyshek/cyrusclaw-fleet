#!/usr/bin/env python3
import os, re, sqlite3, subprocess, datetime, time

WORKSPACE = "/home/azureuser/.openclaw/agents/job-search/workspace"
ROLE_DISCOVERY = os.path.join(WORKSPACE, "projects/job-search/role-discovery")
APPLICATIONS = os.path.join(WORKSPACE, "projects/job-search/applications")
DB_PATH = os.path.join(WORKSPACE, "projects/job-search/tracker.db")
VENV_PYTHON = os.path.join(ROLE_DISCOVERY, ".venv/bin/python")
FALLBACK_RESUME = os.path.join(APPLICATIONS, "queued/netflix-3066/Cyrus_Shekari_Resume_netflix_3066_v2.pdf")
GENERAL_RESUME = os.path.join(WORKSPACE, "projects/job-search/resume/Cyrus_Shekari_Resume.pdf")
TODAY = datetime.date.today().isoformat()

ROLES = [
    (978,  "Product Manager, Ads (Targeting)"),
    (980,  "Product Manager, Ads (Supply)"),
    (1060, "TPM (L6), Identity and Access Management"),
    (1394, "Product Manager, Content Intelligence"),
    (1539, "Support Solutions Engineer (L5), Graph Search"),
    (1998, "Product Manager, Games Discovery"),
    (2000, "Product Manager, Messaging Enablement Platform"),
    (2045, "Product Manager, Ads (Live Ad Serving)"),
    (2157, "Solutions Architect - Total Rewards"),
    (2299, "Product Manager, Partner Commerce"),
    (2343, "TPM (L6) - Ads Decisioning & Optimization"),
    (2852, "Product Manager, Plans Innovation"),
    (2859, "Product Manager, Content Aggregation Experiences"),
    (2861, "Product Manager - Games, TV as a Platform"),
    (2862, "Product Manager - AI Video"),
    (2863, "Product Manager (L6), Identity and Access"),
    (2864, "Product Manager, Data Movement Platform"),
    (2865, "Product Manager, Podcasts and New Content Exploration"),
    (2868, "AI Product Manager, Content Platform Operations (1)"),
    (2869, "AI Product Manager, Content Platform Operations (2)"),
    (2870, "Product Manager, Enterprise Developer Enablement"),
    (2873, "Ads Commercial Readiness Program Manager"),
    (2875, "Finance Program Manager"),
    (2876, "Program Manager, Design"),
    (2877, "TPM - Cloud Infrastructure and AI Platform"),
    (2878, "Program Manager, Program Delivery - Design & Construction"),
    (2880, "HR Program Manager, Partnerships and Ads"),
    (2881, "Program Manager, Brand Creative Studio - Netflix House"),
    (2883, "Support Solutions Engineer (L5), Cloud Networking"),
    (2884, "Support Solutions Engineer (L5) Data Platform"),
    (2885, "Solution Architect L4 - Workday Solutions"),
    (2936, "Product Manager, Ads Platform (Experimentation)"),
    (3065, "Program Manager, Live Media Operations"),
    (3701, "Product Manager, Core Discovery"),
]


def get_resume(role_id):
    for base in ["queued/netflix-{}".format(role_id), "submitted/netflix-{}".format(role_id)]:
        d = os.path.join(APPLICATIONS, base)
        if os.path.isdir(d):
            pdfs = [x for x in os.listdir(d) if x.endswith(".pdf")]
            if pdfs:
                return os.path.join(d, sorted(pdfs)[-1])
    return FALLBACK_RESUME if os.path.exists(FALLBACK_RESUME) else GENERAL_RESUME


def is_confirmed(role_id):
    f = os.path.join(APPLICATIONS, "submitted/netflix-{}".format(role_id), "STATUS.md")
    if not os.path.exists(f):
        return False
    c = open(f).read()
    return any(x in c for x in ["encId", "enc_id", "HTTP 201", "ALREADY APPLIED", "success: true"])


def write_status(role_id, title, status, enc_id=None, error=None):
    d = os.path.join(APPLICATIONS, "submitted/netflix-{}".format(role_id))
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, "STATUS.md")
    if status == "submitted":
        txt = "# Netflix {} SUBMITTED\n\nTitle: {}\nDate: {}\nencId: {}\nBy: auto (_eightfold_runner.py)\nHTTP: 201\n".format(
            role_id, title, TODAY, enc_id or "unknown")
    elif status == "already_applied":
        txt = "# Netflix {} ALREADY APPLIED\n\nTitle: {}\nDate: {}\nALREADY APPLIED confirmed {}\n".format(
            role_id, title, TODAY, TODAY)
    elif status == "closed":
        txt = "# Netflix {} CLOSED\n\nTitle: {}\nDate: {}\nCLOSED (req removed or 404)\n".format(
            role_id, title, TODAY)
    else:
        txt = "# Netflix {} ERROR\n\nTitle: {}\nDate: {}\nError: {}\n".format(
            role_id, title, TODAY, error or "unknown")
    open(fp, "w").write(txt)


def update_db(role_id, status, enc_id=None):
    conn = sqlite3.connect(DB_PATH)
    try:
        if status == "submitted":
            conn.execute(
                "UPDATE roles SET status='submitted', applied_by='auto', applied_on=?, "
                "agent_notes=COALESCE(agent_notes,'') || ? WHERE id=?",
                (TODAY, " | EF-CONFIRMED " + TODAY + " encId=" + str(enc_id), role_id)
            )
        elif status == "already_applied":
            conn.execute(
                "UPDATE roles SET status='submitted', agent_notes=COALESCE(agent_notes,'') || ? WHERE id=?",
                (" | ALREADY APPLIED confirmed " + TODAY, role_id)
            )
        elif status == "closed":
            conn.execute(
                "UPDATE roles SET status='closed', agent_notes=COALESCE(agent_notes,'') || ? WHERE id=?",
                (" | CLOSED " + TODAY, role_id)
            )
        conn.commit()
    finally:
        conn.close()


def run_role(role_id, title):
    resume = get_resume(role_id)
    print("  resume: " + os.path.basename(resume), flush=True)
    cmd = [VENV_PYTHON, os.path.join(ROLE_DISCOVERY, "_eightfold_runner.py"),
           "--role-id", str(role_id), "--resume", resume]
    start = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=ROLE_DISCOVERY)
        elapsed = time.time() - start
        out = r.stdout + r.stderr
        print("  exit=" + str(r.returncode) + " elapsed=" + str(int(elapsed)) + "s", flush=True)
        for line in out.strip().split("\n")[-6:]:
            print("  | " + line, flush=True)
        if r.returncode == 0:
            m = re.search(r"enc_id=([A-Za-z0-9_-]+)", r.stdout)
            if not m:
                m = re.search(r'"encId":\s*"([^"]+)"', r.stdout + r.stderr)
            enc = m.group(1) if m else None
            return ("submitted", enc, out)
        elif r.returncode == 7:
            return ("already_applied", None, out)
        elif r.returncode == 6:
            return ("closed", None, out)
        else:
            return ("error", None, out)
    except subprocess.TimeoutExpired:
        return ("error", None, "TIMEOUT")
    except Exception as exc:
        return ("error", None, str(exc))


def main():
    res = {"submitted_new": [], "already_applied": [], "closed": [], "error": [], "skipped": []}
    print("Netflix batch " + str(len(ROLES)) + " roles  TODAY=" + TODAY, flush=True)
    for i, (role_id, title) in enumerate(ROLES):
        print("\n[{}/{}] netflix-{}: {}".format(i + 1, len(ROLES), role_id, title), flush=True)
        if is_confirmed(role_id):
            print("  SKIP confirmed", flush=True)
            res["skipped"].append(role_id)
            continue
        classify, enc_id, output = run_role(role_id, title)
        if classify == "submitted":
            write_status(role_id, title, "submitted", enc_id=enc_id)
            update_db(role_id, "submitted", enc_id=enc_id)
            res["submitted_new"].append(role_id)
            print("  SUCCESS SUBMITTED encId=" + str(enc_id), flush=True)
        elif classify == "already_applied":
            write_status(role_id, title, "already_applied")
            update_db(role_id, "already_applied")
            res["already_applied"].append(role_id)
            print("  SUCCESS ALREADY_APPLIED", flush=True)
        elif classify == "closed":
            write_status(role_id, title, "closed")
            update_db(role_id, "closed")
            res["closed"].append(role_id)
            print("  CLOSED", flush=True)
        else:
            write_status(role_id, title, "error", error=output[-200:])
            res["error"].append(role_id)
            print("  ERROR", flush=True)
        time.sleep(3)
    print("\nBATCH DONE", flush=True)
    for k, v in res.items():
        print("  " + k + ": " + str(len(v)) + " " + str(v), flush=True)
    rx = subprocess.run(
        [VENV_PYTHON, os.path.join(ROLE_DISCOVERY, "render_xlsx.py")],
        capture_output=True, text=True, timeout=120, cwd=ROLE_DISCOVERY
    )
    print("render_xlsx: " + ("OK" if rx.returncode == 0 else "ERROR: " + rx.stderr[-100:]), flush=True)
    return res


if __name__ == "__main__":
    main()
