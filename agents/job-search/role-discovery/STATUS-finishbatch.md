# STATUS-finishbatch.md — browser-finish-ashbyloc-wdcohort

Started 2026-06-11 00:10 PDT. Sole browser-submit worker.
Commits confirmed present: chain_p14 7d84e9f (Ashby loc), b12fc52+b5d4d54+730c499 (WD WE-class).

## Plan
- TASK A: Ashby residential retry — 938 ElevenLabs, 1112 Higharc, 1235 Liquid AI
- TASK B: Workday WE-class fresh-account — 2546 Boeing, 2891 PayPal
- TASK C: render_xlsx + report

## Per-row log
(pending)

## Tally
submitted=0 banked=0 closed=0

### 938 ElevenLabs — DONE
- prep ok (12 fields, 0 blockers); residential egress 82.23.97.223 verified
- submit reached server -> ALREADY-APPLIED (90-day dedup block); prior submit was real
- DB: status=applied applied_by=auto-residential; STATUS.md written
- chain_p14 NOT falsified (passed location, hit dedup gate)

### 1112 Higharc — SUBMITTED ✅
- residential 82.23.97.223; real server FormSubmitSuccess POST + 'Thank you for applying' confirmation
- chain_p14 location ladder VALIDATED LIVE (early Missing-Location FormRender then clean FormSubmitSuccess = clobber-guard won)
- DB: status=applied applied_by=auto-residential block_reason=NULL; STATUS.md written

### 1235 Liquid AI — SUBMITTED ✅
- residential 82.23.97.223; dual FormSubmitSuccess (application+survey) + 'successfully submitted' confirmation
- chain_p14 region ladder VALIDATED LIVE (2nd tenant). No score-threshold error.
- DB: status=applied applied_by=auto-residential block_reason=NULL; STATUS.md written

## TASK A COMPLETE: 938 already-applied, 1112 SUBMITTED, 1235 SUBMITTED. chain_p14 WORKS LIVE (2/2 real tests submitted).

### 2546 Boeing — BANKED (1 dryrun, EXIT 5)
- WE-fix WORKED partially: dates committed, harden plateaued clean in-visit (total<=9 empty=0), 730c499 re-upload cleared upload-error
- REAL wall: Boeing respawns a fresh empty required WE block each Next-nav (idx 54->179->210->294); Next -> 'Errors Found'; loop-cap EXIT 5. NOADVANCE-DIAG = no real blocking field.
- block_reason: workday-we-regen-per-nav-climbing-index-EXIT5-after-730c499. STATUS.md written.
- Banked per anti-overflow rule (no 2nd identical dryrun, no DOM forensics).

### 2891 PayPal — BANKED (1 dryrun, EXIT 5)
- SAME pattern as Boeing: dates committed (persist, NOT EXIT-9), harden plateaued clean in-visit (total<=15 empty=0)
- WE block respawns each Next-nav (idx 82->273->436) -> 'Errors Found' -> loop-cap EXIT 5
- block_reason: workday-we-regen-per-nav-climbing-index-EXIT5 (confirmed 2-tenant cohort w/ Boeing). STATUS.md written.

## TASK B COMPLETE: Boeing 2546 + PayPal 2891 both BANKED (EXIT 5, identical WE-regen-per-nav wall). WE-fix partially works (converges in-visit) but does NOT clear this cohort.

## TASK C — render_xlsx DONE
- render_xlsx.py EXIT 0. Sheet: Applied=602, Open=0, Manual Ready=29, Manual Apply=146, Blocked=84.

## FINAL TALLY
- SUBMITTED: 2 (1112 Higharc, 1235 Liquid AI) — both real server FormSubmitSuccess
- ALREADY-APPLIED: 1 (938 ElevenLabs — server 90-day dedup; counted as applied)
- BANKED: 2 (2546 Boeing, 2891 PayPal — EXIT 5, identical WE-regen-per-nav wall)
- CLOSED: 0

## KEY FINDINGS
- chain_p14 location fix WORKS LIVE: 2/2 real location tests submitted (1112, 1235). 938 passed location too (hit dedup gate, not a location bounce). Fix is VALIDATED.
- WD WE-fix (b12fc52/b5d4d54/730c499) does NOT clear Boeing/PayPal: it converges WITHIN a visit (harden plateaus clean, dates persist) but a fresh empty required WE block respawns at a climbing index on EACH Next-nav (Boeing 54->179->210->294, PayPal 82->273->436) -> 'Errors Found' -> EXIT 5. Confirmed 2-tenant cohort. NOT EXIT-9 (dates persist), NOT upload.
- ENGINE EDITS: NONE (per anti-overflow rule, banked the cohort rather than deep-investigate). _ashby_runner.py ' M' in git is the pre-existing chain_p13 from another worker, untouched by me.

## CLEANUP
- Residential Chrome (CDP 19223) stopped. Shared relay left running. No stray submit python.
- DB backed up once: tracker.db.bak.20260611-070947-finishbatch.
