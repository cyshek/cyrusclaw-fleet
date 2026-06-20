SUBMITTED — 2026-05-25T01:32 UTC

role_id: 1056
company: Axon
role: Product Manager II, Hardware
location: Seattle, WA
fit: 92 (llm)
yoe: 2
est_tc: $0 (not on Levels)
confirmation_url: https://job-boards.greenhouse.io/axon/jobs/7686536003/confirmation
confirmation_text: greenhouse confirmation page reached (conf=true, fieldErrs=[], grecapErr empty)
verification_code_used: kr8ikBZR
submitted_by: auto (job-search single-role worker, role 1056)
resume_attached: Cyrus_Shekari_Resume_axon_7686536003_v2.pdf
tracker_db_backup: tracker.db.bak.20260524-axon1056

Notes:
- Native Greenhouse board (job-boards.greenhouse.io/axon/...). NO iframe wrapper, so wrapper-iframe lookup failed and runner fell back to direct embed URL (the runner's standard native-GH fallback path). reCAPTCHA was invisible/no validity-token required — submit cleared.
- 28-field form, 24 filled / 4 declined-demographics / 0 needs-review / 0 blockers after two permanent LABEL_RULES additions to `greenhouse_dryrun.py` (pipeline fixes — apply to any future Axon-style rules):
    1. "verification of both your identity" / "provide verification of" → `work_authorized` (placed BEFORE the generic `work authorization` rule so phrasings like "Can you provide verification of both your identity and authorization to work in the United States…" map to Yes via work-auth resolver).
    2. "contractual obligations" / "impede or interfere with your ability" / "obligations, agreements, relationships" → `answer_no` (placed near the `non-compete` cluster — covers Axon's anti-conflict screener and any future tenant phrasing the same way).
- Gates filled per brief: AI=No (no question asked on Axon form), US-auth=Yes, sponsorship=No, demographics declined (gender/race/veteran/disability), school=Univ of Houston (no school question on Axon form), travel=100% (no travel% question on Axon form). Onsite=Yes acknowledged (4 days/week Tue-Fri). Located-near-hub=Yes (Kirkland WA).
- Single email verification code (`kr8ikBZR`) fetched via gmail_imap.wait_for_verification_code, one-shot fill of #security-input-0..7, click "Submit application" → confirmation page.
- Resume upload: `verify_resume` reported `filename_visible=true` (Filestack committed) even though `click_attach` reported "no #resume input and no filename in body" mid-step — same harmless Filestack timing quirk seen on Guidewheel/Comet runs.
- Cost: 1 LLM resume tailoring pass + 1 cover-answers pass + 1 email-verification IMAP fetch. ~5 min end-to-end after dryrun rebuild.
</content>
</invoke>
<invoke name="exec">
<parameter name="command">cd /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search && role-discovery/.venv/bin/python -c "
import sqlite3
c = sqlite3.connect('tracker.db')
c.execute(\"UPDATE roles SET applied_by='auto', applied_on='2026-05-24' WHERE id=1056\")
c.commit()
r = c.execute('SELECT id, company, role, applied_by, applied_on FROM roles WHERE id=1056').fetchone()
print('updated:', r)
"