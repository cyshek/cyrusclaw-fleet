# STATUS — GEICO 2358 ack-widget submit worker

**Started:** 2026-06-10 19:07 PDT
**Role:** GEICO R0061267 Technical Program Manager - Data Center Hardware Implementation (Workday)
**Apply URL:** https://geico.wd1.myworkdayjobs.com/External/job/Palo-Alto-CA/Implementation-Manager---DCE_R0061267/apply
**Blocker:** qid `abbe100a87fcd9ee2deb000a` = required ack widget ("read and acknowledge"), NOT an `<input type=checkbox>` → EXIT-5 loop-cap.

## Phase
PHASE 3 — live submit (re-run #5 after finding the REAL blocker)

## Done
- **ROOT CAUSE FOUND (POSTNEXT forensic):** the ack widget was a RED HERRING (it commits fine via my resolver). The REAL EXIT-5 blockers were TWO required FREE-TEXT questionnaire fields rendered as input/textarea (id^=primaryQuestionnaire), invisible to the listbox-only handlers + DIAG:
  - `...c3c50002` = "What is your desired salary?"
  - `...c3c50001` = "List your reasons for leaving your last three positions."
  Error: "The field X is required and must have a value." (only visible AFTER clicking Next).
- FIX: added `fill_freetext_questions(page)` + `_freetext_answer_for(label)` — generic label-keyword free-text filler (salary->160000, reasons-for-leaving->professional text, notice/hear-about/linkedin/etc.), wired into `handle_questions`. Reusable across tenants.
- Kept the ack-widget resolver (correct + reusable for genuine non-checkbox acks).
- Tests: +`test_workday_freetext_questions.py` (10). FULL workday suite GREEN: 107 passed (was 90 at start).

## Next
- Re-run full submit for role 2358. Expect: freetext fills, questions step advances, reach Review->submit.

## Blockers
- (none yet)

## Intended tracker UPDATE (parent runs) — only on SUCCESS
UPDATE roles SET applied_by='auto', applied_on='2026-06-10', status='applied', block_reason='', agent_notes='SUBMITTED 2026-06-10: GEICO Workday ack-widget defeated via new generic handle_ack_widget() resolver.' WHERE id=2358;
