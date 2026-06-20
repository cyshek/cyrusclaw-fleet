# Uber Careers — account-creation wall (BLOCKED both rows)

Date: 2026-06-07 (PDT)
Driver: auto-live browser (shared OpenClaw chrome, port 18800)

## Rows
- 1882 — Product Manager II, Help Center Platform — https://www.uber.com/careers/list/158309/
- 1883 — Program Manager, AV Operational Safety — https://www.uber.com/careers/list/158015/

## Flow observed
1. `/careers/list/<id>/` → "Apply Now" → `/careers/apply/interstitial/<id>` → redirects to
   `/careers/apply/form/<id>?uclick_id=...`
2. The apply-form page renders ONLY an "Uber Careers account" card:
   - **Sign in** button (existing account)
   - **Create account** link → opens a dialog requiring **Email + Password**
     (password: ≥6 chars, ≥1 number). By creating an account you acknowledge the
     Candidate Privacy Notice. The account pre-fills/saves future applications.
3. There is **NO guest / continue-without-account path**. No resume upload, no
   contact fields, no screening questions are reachable until you are signed in.

## Why BLOCKED (not submitted)
- The application form is fully gated behind an Uber Careers **account login /
  account creation**. Creating the account binds Cyrus's real identity, requires
  choosing+storing a password, and likely triggers email verification (and may
  trip Akamai/CAPTCHA on signup). Per task + account-safety rules, the agent does
  NOT brute-force account creation. Banked truthfully.

## Resume packet status — TAILORED PACKETS ALREADY EXIST (ready for manual upload)
- `inline_submit.py` rejects Uber URLs outright (`unsupported ATS URL`) — no
  tailored PDF via THAT pipeline. BUT tailored resumes were already generated
  (2026-06-01, originally held for a Cyrus referral) and are ready:
  - Row 1882 (158309): `applications/queued/uber-158309/Cyrus_Shekari_Resume_uber_158309_v2.pdf` (+ .docx, JD.md, tailoring-notes.md)
  - Row 1883 (158015): `applications/queued/uber-158015/Cyrus_Shekari_Resume_uber_158015_v2.pdf` (+ .docx, JD.md, tailoring-notes.md)
- Fallback master resume: `projects/job-search/resume/Cyrus_Shekari_Resume.pdf`

## Unblock path (Cyrus-side)
- Cyrus creates/signs into an Uber Careers account ONCE (email cyshekari@gmail.com),
  then either (a) completes these 2 applications manually, or (b) hands the agent a
  logged-in browser session (profile=user) so the form fields become reachable.

## Evidence
- Screenshots captured inline in the subagent session (account card + Create-account
  email/password dialog for 158309; account card for 158015).
