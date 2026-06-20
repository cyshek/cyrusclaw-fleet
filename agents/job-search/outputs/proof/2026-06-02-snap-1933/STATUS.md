STATUS: SUBMITTED ✅ (REAL — on-page confirmation captured)
Submitted: 2026-06-02 by _workday_runner.py (workday-proof subagent)

role_id: 1933
ats: workday (tenant: snap, wd1.myworkdaysite.com/recruiting/snapchat/snap)
company: Snap Inc.
role: Product Manager - Ads Platform
req: R0045214
location: New York, NY
resume used: resume/Cyrus_Shekari_Resume.pdf (base PM resume)

=====================================================================
ON-PAGE CONFIRMATION (server-authoritative):
  Modal: "✓ Application Submitted — Thanks for applying to Snap Inc!
          Your application has been received."
  Candidate Home > My Applications > Active (1):
     Product Manager - Ads Platform | R0045214 |
     Application Received | Date Submitted: June 2, 2026
  Runner log: confirmation matched: "application submitted" -> RESULT: SUBMITTED
  Screenshot: ../../.workday-debug/snap-after-submit.png

This is the FIRST real end-to-end Workday submit landed by the reusable
_workday_runner.py. It walked the full 6-step Snap flow:
  My Information -> My Experience (resume + work history + education + dates)
  -> Application Questions -> Voluntary Disclosures -> Self Identify -> Review -> Submit.

Application answers (verified in dryrun before live submit):
  Q1 authorized to work in US        -> Yes
  Q2 auth based on sponsorship       -> No
  Q3 need Snap to sponsor visa       -> No
  chained gating Q                   -> No
  relocate / live in location        -> Yes
  commit to office as advertised     -> Yes
  meet minimum qualification         -> Yes
  former EY/PwC/Deloitte/KPMG        -> No

KNOWN IMPERFECTION (non-blocking): education fieldOfStudy ("Computer Science")
did not commit (searchable multiselect prompt the runner couldn't open) — Snap
accepted the form without it (field of study is on the attached resume + degree
was set). Worth fixing for future Snap-class submits; not a blocker.
=====================================================================
