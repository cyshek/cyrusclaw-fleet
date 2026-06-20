# 2546 Boeing — Project Management Specialist (JR2026510327-2)

OUTCOME: BANKED (deeper WE-regen-per-nav variant; WE-fix converges in-visit but not across navs)
Date: 2026-06-11
Tenant: boeing (wd1) | fresh-account (signin_fresh to alias cyshekari+wd-boeing-202606110651@gmail.com)
EXIT: 5 (My Experience revisited >3x without advancing, loop-cap)

## What the b12fc52/b5d4d54/730c499 fix DID accomplish here (progress, not full clear)
- All existing WE blocks committed dates fine: `date-repair block[7..51] ... start_committed=True`.
- harden converged WITHIN each visit: `harden: WE count plateaued clean (total=8/9 empty=0, stable) -> safe to Next`.
- Filled the lone permanent empty block as last resort + committed its date:
  `date-commit workExperience-179--startDate ... -> OK`, jobTitle='Technical Program Manager'.
- 730c499 re-upload cleared the upload-required error (`uploaded:true`).
- Next DID advance the heading: `click_next: advanced -> head_after='... | My Experience | Errors Found'`.

## REAL residual wall (one-line symptom; NOT a date-persistence or upload problem)
Boeing My-Experience RE-SPAWNS a fresh empty REQUIRED WE block at a CLIMBING index on
EACH Next navigation (observed 54 -> 179 -> 210 -> 294). harden deletes empties + fills
the permanent one and plateaus clean WITHIN a visit, but the NEXT nav regenerates a new
empty block, so the step is never truly empty-free across navigations -> Next lands on
"Errors Found" -> >3 revisits -> loop-cap EXIT 5.
NOADVANCE-DIAG showed NO real blocking field (select_one:[], domreq_empty:[], unchecked:[]);
the only "error" surfaced is the benign string "Cyrus_Shekari_Resume.pdf successfully uploaded".

block_reason set: `workday-we-regen-per-nav-climbing-index-EXIT5-after-730c499 (harden converges in-visit total<=9 empty=0 but Boeing respawns a fresh empty required WE block each Next-nav 54->179->210->294; Next advances only to 'Errors Found' whose sole surfaced error is the benign upload-success string; same root class as Nvidia WE fix but block regen outpaces cross-nav harden). 1 dryrun, banked per anti-overflow rule - no 2nd identical dryrun, no DOM forensics.`

## NEXT (for a future targeted engine session, NOT this run)
The Nvidia-class fix makes the COUNT plateau per-visit; Boeing needs the harden/cap to
also suppress the per-NAVIGATION regen (e.g. cap total WE blocks across visits, or detect
+ delete the freshly-regenerated empty immediately on each My-Experience re-entry before
re-running the parser, or stop re-uploading the resume after visit 1 so the parser stops
manufacturing a new block). Single obvious cause = resume re-parse spawning a new empty
block each nav; needs the resume-cap-that-holds across navigations, not just within one.

Logs: /tmp/boeing2546-dry.log
