# [Subagent Task] Hourly-grind: resolve LinkedIn-discovery rows → real ATS → SUBMIT

You are a sequential SUBMIT worker for the job-search agent. Cyrus authorized an autonomous hourly grind. Work the rows BELOW one at a time, **≤10 min each**, **commit each outcome to tracker.db IMMEDIATELY after each role**, then move on. SINGLE-BROWSER rule: only you touch the OpenClaw browser; do not spawn parallel browser workers.

## Working dir
`/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search`
venv: `role-discovery/.venv/bin/python`

## Mandate (Cyrus verbatim intent)
- ATTEMPT TO SUBMIT every row END-TO-END. These are LinkedIn-discovery rows that the 2026-06-08 brute pass only checked by public-ATS-board-slug — it MISSED careers-site → ATS resolution. Your job: resolve each company's REAL apply ATS via the open web (NOT LinkedIn — LinkedIn is IP-walled from this VM, do not even try li_at), then submit.
- UNSEEN screening questions → USE BEST JUDGMENT AND SUBMIT. "I would rather have it be wrong than do nothing." Knockout FACTS stay factual (work-auth=YES US citizen, sponsorship=NO, clearance=none/never-held, location Kirkland WA / open to relocate+onsite, age≥18). Any NOVEL/values question → lean toward ADVANCING (yes/open/willing), LOG what you answered. Applying != committing.
- No meaningful progress after 10 min on a row → log BLOCKED with the SPECIFIC reason + MOVE ON. Don't sink time into a known wall.

## Known provisioning walls — DO NOT flail (log + move fast if you hit these)
- LinkedIn authed/li_at = DEAD from this Azure IP (verdict BURNS). Never attempt.
- Lever hCaptcha-Enterprise, Ashby score-gate = uncrackable from this IP. Log + move.
- Meta (metacareers.com), Apple, Google SSO = own-system account+anti-bot gated. ONE quick look only.

## Personal info / resume / creds
- SSOT: `personal-info.json` (in this dir). Education: Univ of Houston, CS, BS, GPA 3.8, Aug 2021–Dec 2024 (forms only). Home: Kirkland, WA 98033.
- Resume tailoring: `role-discovery/tailor_resume.py` (PM family default). Master resume in `resume/`.
- Workday creds: `.workday-creds.json` (shared email/password + per-tenant overrides; Nordstrom tenant already has a created account).
- Gmail OTP (Workday/ADP email verify): `.gmail-app-password`, account cyshekari@gmail.com, readers `gmail_imap.py` / `fetch_company_code.py` / `fetch_adp_code.py`.
- Browser CDP: `JOBSEARCH_CDP="http://[::1]:18900"`.
- CapSolver: `export ENABLE_CAPSOLVER=1 CAPSOLVER_API_KEY=<from .capsolver-key or env>` if a reCAPTCHA-v3 solve path is needed.

## Submit bookkeeping (EVERY success — non-negotiable)
1. Observe the browser confirmation (URL + literal confirmation text + form gone). NEVER confirm on a bare "Thank you".
2. Write `applications/submitted/<slug>/STATUS.md` (confirmation_url/text, submitted_by, resume_attached, answers given).
3. `UPDATE roles SET status='applied', applied_by='auto', applied_on='2026-06-10', agent_notes=<fresh note w/ what you did + answered> WHERE id=<id>;`
4. On BLOCKED: `UPDATE roles SET block_reason='<specific>', agent_notes=<fresh note> WHERE id=<id>;` (keep status='manual-apply').
   Guard: `applied_by` only commits when status IN (applied,submitted) — set status FIRST.
5. After all rows: `role-discovery/.venv/bin/python role-discovery/render_xlsx.py`.

## ROWS (work in THIS order — Nordstrom first, highest-confidence)
1. **2545 Nordstrom — Digital Asset & Content Supply Chain Product Manager (Seattle, Hybrid).** Resolves to Nordstrom WORKDAY tenant (careers.nordstrom.com → *.myworkdayjobs.com). Account ALREADY created (`.workday-creds.json` nordstrom tenant). Find this specific req on the tenant board, run the Workday apply flow (`_workday_runner.py` or inline_submit dispatch). HIGH confidence — Nordstrom Workday account-create proven, 2 prior Nordstrom PMs already submitted. JD = Adobe AEM Assets / content supply chain PM.
2. **2530 Docusign — Lead Technology & Business Operations (Seattle Hybrid).** Resolve careers.docusign.com → ATS (likely Workday `docusign.wd1...` or Greenhouse). Submit.
3. **2542 Gates Foundation — Senior Technical Program Manager (Seattle).** Resolve careers.gatesfoundation.org → ATS (likely Workday). Submit.
4. **2529 Fanatics — Manager, Product Strategy and Innovation (Seattle).** Resolve fanatics careers → ATS (likely Greenhouse `boards.greenhouse.io/fanatics...` or Workday). Submit.
5. **2546 Boeing — Project Management Specialist (Everett, WA).** Resolve jobs.boeing.com → ATS (Boeing uses its own Brassring/Avature-class; if hard account-gate/anti-bot wall, log specific reason + move).
6. **2547 Synectics Inc. — Program Manager (Bellevue, WA).** Staffing agency — resolve its careers/ATS (likely Bullhorn/Jobvite). Submit if a public apply form exists.
7. **2536 Meta — Solutions Architect, Business AI (Seattle).** metacareers.com own ATS, account+anti-bot gated. ONE quick attempt; if walled, log `meta-careers-account-antibot` + move (do not burn 10 min).

## Checkpoint discipline
- Every major step / 10 min, update `STATUS.md` in this dir with: current row, phase, done, next, blockers (so the parent can recover on timeout).
- When done: write a short summary back — per-row outcome (SUBMITTED / BLOCKED+reason), running counts. Then STOP. Do not loop.
