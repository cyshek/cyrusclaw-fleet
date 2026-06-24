#!/usr/bin/env python3
"""Batch Workday submit for drain-pass10."""
import subprocess, sys, os, time

WORKSPACE = "/home/azureuser/.openclaw/agents/job-search/workspace"
RD = f"{WORKSPACE}/projects/job-search/role-discovery"
PYTHON = f"{RD}/.venv/bin/python3"
RUNNER = f"{RD}/_workday_runner.py"
APPS = f"{WORKSPACE}/projects/job-search/applications/submitted"

ROLES = [
    (3487, "micron-jr101596", "micron",
     "https://micron.wd1.myworkdayjobs.com/External/job/Manassas-VA----Fab-6/F6-SPMO-Cost-Program-Manager_JR101596/apply"),
    (3488, "micron-jr102001", "micron",
     "https://micron.wd1.myworkdayjobs.com/External/job/Boise-ID---Main-Site/HBM-Product-Manager--New-College-Grad-_JR102001/apply"),
    (3496, "micron-jr102729", "micron",
     "https://micron.wd1.myworkdayjobs.com/External/job/Boise-ID---Main-Site/Construction-Program-Manager---Cost-Specialist--Global-Facilities-US_JR102729/apply"),
    (3497, "analog-devices-r260762", "analogdevices",
     "https://analogdevices.wd1.myworkdayjobs.com/External/job/US-MA-Wilmington/Digital-Product-Manager_R260762/apply"),
    (3498, "analog-devices-r261690", "analogdevices",
     "https://analogdevices.wd1.myworkdayjobs.com/External/job/US-MA-Wilmington/Program-Manager--Data-Governance-and-Stewardship_R261690/apply"),
    (3501, "marvell-2602323", "marvell",
     "https://marvell.wd1.myworkdayjobs.com/MarvellCareers/job/Santa-Clara-CA/Technical-Program-Manager---Central-CAD---Design-Services_2602323/apply"),
    (3502, "marvell-2601773", "marvell",
     "https://marvell.wd1.myworkdayjobs.com/MarvellCareers/job/US-CA---Irvine/Engineering-Program-Manager---Project-Manager_2601773/apply"),
    (3503, "marvell-2601236", "marvell",
     "https://marvell.wd1.myworkdayjobs.com/MarvellCareers/job/Santa-Clara-CA/AI-Solutions-Analyst---Early-Career_2601236/apply"),
    (3515, "servicetitan-jr113481", "servicetitan",
     "https://servicetitan.wd1.myworkdayjobs.com/ServiceTitan/job/US-Remote/Solutions-Engineer--Enterprise_JR113481/apply"),
    (3508, "broadridge-jr1082401", "broadridge",
     "https://broadridge.wd5.myworkdayjobs.com/careers/job/New-York-NY/Sales-Support-Specialist--Hybrid--NYC-_JR1082401/apply"),
    (3509, "morgan-stanley-ai-product-manager-pt-jr037090", "ms",
     "https://ms.wd5.myworkdayjobs.com/External/job/New-York-New-York-United-States-of-America/AI-Product-Manager_PT-JR037090/apply"),
    (3511, "morgan-stanley-investment-advisory-program-manager-asso", "ms",
     "https://ms.wd5.myworkdayjobs.com/External/job/Purchase-New-York-United-States-of-America/Investment-Advisory-Program-Manager--Associate_PT-JR036790/apply"),
    (3512, "morgan-stanley-workplace-platforms-product-manager-asso", "ms",
     "https://ms.wd5.myworkdayjobs.com/External/job/Purchase-New-York-United-States-of-America/Workplace-Platforms-Product-Manager--Associate-AVP_PT-JR035812/apply"),
    (3514, "morgan-stanley-program-manager-parametric-pt-jr037957-1", "ms",
     "https://ms.wd5.myworkdayjobs.com/External/job/Seattle-Washington-United-States-of-America/Program-Manager---Parametric_PT-JR037957-1/apply"),
]

results = []

for role_id, slug, tenant, apply_url in ROLES:
    app_dir = f"{APPS}/{slug}"
    pdfs = [f for f in os.listdir(app_dir) if f.endswith('.pdf')] if os.path.isdir(app_dir) else []
    if not pdfs:
        print(f"[{role_id}] ERROR: No resume PDF in {app_dir}")
        results.append((role_id, slug, -99, "no-resume"))
        continue
    resume = f"{app_dir}/{pdfs[0]}"

    cmd = [PYTHON, RUNNER, "--url", apply_url, "--tenant", tenant,
           "--role-id", str(role_id), "--resume", resume, "--fresh-account"]

    print(f"\n{'='*60}")
    print(f"[{role_id}] {slug} ({tenant})")
    print(f"{'='*60}")
    sys.stdout.flush()

    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=RD)
        elapsed = int(time.time() - start)
        rc = proc.returncode
        stdout = proc.stdout[-4000:] if proc.stdout else ""
        stderr = proc.stderr[-500:] if proc.stderr else ""
        print(f"EXIT {rc} ({elapsed}s)")
        print(stdout)
        if stderr:
            print("STDERR:", stderr)
        results.append((role_id, slug, rc, stdout[-300:]))
        time.sleep(8 if rc == 0 else 3)
    except subprocess.TimeoutExpired:
        elapsed = int(time.time() - start)
        print(f"[{role_id}] TIMEOUT after {elapsed}s")
        results.append((role_id, slug, -1, "timeout"))
    except Exception as ex:
        print(f"[{role_id}] EXCEPTION: {ex}")
        results.append((role_id, slug, -2, str(ex)[:100]))

print("\n" + "="*70)
print("BATCH RESULTS SUMMARY")
print("="*70)
submitted = [r for r in results if r[2] == 0]
failed = [r for r in results if r[2] != 0]
print(f"Submitted: {len(submitted)}/{len(results)}")
for r in submitted:
    print(f"  OK  [{r[0]}] {r[1]}")
print(f"Failed: {len(failed)}/{len(results)}")
for r in failed:
    print(f"  FAIL [{r[0]}] {r[1]}: exit={r[2]}")
