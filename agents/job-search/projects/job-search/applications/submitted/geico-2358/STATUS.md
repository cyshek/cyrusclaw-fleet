# GEICO 2358 — SUBMITTED ✅

**Role:** GEICO — Technical Program Manager - Data Center Hardware Implementation (R0061267)
**ATS:** Workday (tenant=geico)
**Apply URL:** https://geico.wd1.myworkdayjobs.com/External/job/Palo-Alto-CA/Implementation-Manager---DCE_R0061267/apply
**Submitted:** 2026-06-10 ~19:35 PDT (run6, EXIT 0)
**Account:** fresh alias cyshekari+wd-geico-202606110006@gmail.com (signin_fresh)

## CONFIRMATION
- **confirmation_text:** "thank you for applying" (matched in submit-confirmation page body by `verify_confirmation`)
- **confirmation_method:** Workday Review → Submit (`pageFooterNextButton` labeled "Submit") → confirmation body keyword verified; runner returned EXIT 0 = "SUBMITTED - confirmation verified".
- **confirmation_screenshot:** `projects/job-search/.workday-debug/geico-after-submit.png` (post-submit confirmation page; the success-prune kept this as the evidence shot).
- **confirmation_url:** Workday submit-confirmation page (post-submit; the runner verifies by body text, GEICO does not expose a stable public confirmation URL — the proof is the screenshot + EXIT 0).
- **resume_attached:** YES — `Cyrus_Shekari_Resume_workday-geico_R0061267_v2.pdf` ("successfully uploaded" confirmed on My Experience step).

## ANSWERS GIVEN (Application Questions)
- Are you 18 years or older? → **Yes**
- Do you have a high school diploma or equivalent? → **Yes**
- Are you legally authorized to work in the United States? → **Yes** (US citizen)
- Will you now or in the future require sponsorship? → **No**
- Do you currently hold / have you ever held a professional state-issued license (legal)? → **No** (factual — Cyrus holds none)
- Do you have a familial/romantic/extraprofessional relationship with a current GEICO employee? → **No** (factual)
- Have you worked previously as a GEICO associate? → **No** (factual)
- Are you a current or former contractor of GEICO? → **No** (factual)
- Do you understand in-person attendance at the assigned GEICO office may be required? → **Yes**
- **"read and acknowledge"** ack listbox → **"I have read and acknowledge"**
- **"What is your desired salary?"** (free text) → **160000** (within posted range; maximize-advancing)
- **"List your reasons for leaving your last three positions."** (free text) → professional growth-oriented answer
- Voluntary disclosures (ethnicity/gender/veteran) → Decline; disability → do not want to answer; terms accepted.

## WHAT THE BLOCKER ACTUALLY WAS
The "read and acknowledge" ack widget was a **RED HERRING** — it's a `button[aria-haspopup=listbox]` whose placeholder VALUE is the text "read and acknowledge"; my resolver commits it fine ("I have read and acknowledge").
**The REAL EXIT-5 blockers** were TWO REQUIRED FREE-TEXT questionnaire fields (input/textarea, `id^=primaryQuestionnaire`) that NO listbox/checkbox handler touched and that the listbox-only DIAG never reported (showed `unanswered:[] errors:[]`):
- `...c3c50002` = "What is your desired salary?"
- `...c3c50001` = "List your reasons for leaving your last three positions."
Error only surfaced AFTER clicking Next: *"The field X is required and must have a value."* Found via a one-shot POSTNEXT forensic.

## RUNNER CHANGES (engine: role-discovery/_workday_runner.py)
1. **`fill_freetext_questions(page)` + `_freetext_answer_for(label)`** — generic, reusable: fills required empty free-text questionnaire fields (input/textarea id^=primaryQuestionnaire / aria-required) from label keywords (salary→160000, reasons-for-leaving→professional text, notice-period, how-did-you-hear→LinkedIn, linkedin/website URLs, numeric/text fallbacks). Wired into `handle_questions`.
2. **`handle_ack_widget(page)` + `_dump_ack_diag(page)`** — generic non-checkbox ack resolver (ARIA checkbox / radio group / placeholder-valued single-option listbox). Picks the affirmative option ("I have read and acknowledge"). Wired into `handle_questions` after `handle_ack_checkboxes`. NOT qid-hardcoded.
3. **`handle_questions` NEGATIVE list expanded** with generic factual-No phrasings (worked-previously-as / familial / romantic / extraprofessional / suspended-revoked / hold-professional-license) + ACK_Q affirmative-pick path — fixed harmful default-YES on GEICO knockout questions.
4. Set `_CUR_TENANT` global in `run()` (diag filenames). One-shot GEICO forensics (`_ACK_FORENSIC_DONE`/`_POSTNEXT_FORENSIC_DONE`) are run-once + tenant-gated, harmless.

## TESTS
- Added `test_workday_ack_widget.py` (7) + `test_workday_freetext_questions.py` (10).
- FULL Workday suite GREEN: **107 passed** (was 90 at start).
- Snapshots: `_workday_runner.py.bak.geico2358-*` (3 backups for rollback).

## INTENDED tracker.db UPDATE (PARENT RUNS — I did NOT touch tracker.db):
```sql
UPDATE roles
SET status='applied', applied_by='auto', applied_on='2026-06-10', block_reason='',
    agent_notes='SUBMITTED 2026-06-10 (auto, Workday): EXIT 0, confirmation "thank you for applying". Real blocker was 2 required FREE-TEXT questionnaire fields (desired salary + reasons-for-leaving), NOT the ack widget. Fixed via new generic fill_freetext_questions() + handle_ack_widget() in _workday_runner.py (107 tests green).'
WHERE id=2358;
```
Then run `render_xlsx.py` to refresh the spreadsheet.
