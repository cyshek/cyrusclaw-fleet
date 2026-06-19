# STATUS — Workday cross-nav WORK-EXPERIENCE persistence engine fix (run4)

- **Started:** 2026-06-10 21:20 PDT (hourly-grind subagent `we-persist-fix`)
- **Backup made:** `_workday_runner.py.bak.run4-wepersist` (190810 bytes) BEFORE any edit.
- **Sole browser worker** (AGENTS.md one-at-a-time rule honored).

## PHASE 1 — CONFIRMED ROOT CAUSE (true create_fresh probe, EXIT 5 reproduced)

DEFINITIVE on a TRULY FRESH account (cyshekari+wd-nvidia-202606110424, empty start):
- Visit 1: runner fills 3 history blocks (idx 66 MSFT 3/2024, 105 Amazon 8/2023, 140 ProPainters 5/2021).
  PERSIST-PROBE proves ALL committed in DOM + React fiber.mProps.value + hiddenInputs. **DATES PERSIST.**
  BUT resume upload's PARSER leaves an extra empty REQUIRED block (idx 179). Next bounces on it.
- Visit 2: WARN "3 prefilled WE blocks: ['Technical Program Manager Intern','Technical Program Manager Intern',
  'Program Manager Intern']" = the **resume PARSER auto-created its OWN blocks from the PDF text**.
  resume NOT re-uploaded (file-widget skip OK). prefill-guard converges empty=0. YET a NEW empty (idx 304)
  materializes AFTER converge -> Next bounces. total grows 4->5.
- Visit 3: "successfully uploaded" text GONE (Workday dropped file display) -> file_present=False -> RE-UPLOAD
  (cap was only 1, not 2, because visit-2 skip didn't increment) -> parser re-runs -> total 5->6 -> loop-cap EXIT5.

### TRUE ROOT CAUSE (NOT date persistence):
The **block COUNT never plateaus**. Two compounding sources spawn a fresh empty REQUIRED WE block each visit:
  (1) The resume PARSER auto-creates/keeps a blank "add-another" template block after parsing the PDF.
  (2) On revisit the "successfully uploaded" marker disappears -> `file_present`=False -> RE-UPLOAD ->
      parser RE-RUNS -> more blocks. The `_RESUME_UPLOADED` cap doesn't increment on the skip path, so the
      2-upload cap effectively allows re-upload again on visit 3.
The converge loop reports empty=0 but a new empty appears in the settle BETWEEN converge-return and click_next.
The `date-repair block[N]: start_filled=False` lines are a FALSE-NEGATIVE diagnostic (probe proves value present).

## PHASE 2 — FIX (IMPLEMENTED + COMMITTED 2026-06-11)
All three fixes landed in `_workday_runner.py` (commit on top of f6a55e1). Suite green (117/117).
1. **DONE** Resume cap that holds on a fresh account: in `handle_experience`, once
   `_RESUME_UPLOADED >= 1` AND `_ACCOUNT_MODE in (create_fresh, signin_fresh)`, re-upload is
   skipped unconditionally (typed WORK_HISTORY is the source of truth; re-parse only respawns
   empty blocks). Non-fresh still respects the 2-upload cap.
2. **DONE** `harden_my_experience_before_next(page)` added (right after `delete_empty_we_blocks`)
   and CALLED as the last action in the `My Experience` step branch, before the shared
   `click_next`. Bounded loop: delete every empty WE block + re-measure until 0-empty AND total
   stable x2 consecutive (settle waits); fills a lone non-deletable permanent empty once from
   WORK_HISTORY[0] as last resort.
3. **DONE** Lying `start_filled={start_empty}` log replaced with multi-source committed read
   (`_wd_read_date_section` -> value || aria-valuetext || hidden); logs `start_committed=...`.
   Date-persist logic itself UNTOUCHED.
   Also removed the one-shot `WD_PERSIST_PROBE` forensic block (Phase-1 diagnostic that was
   displacing the EXIT-9 fast-fail and clicking Next mid-step).

Tests: `test_workday_we_persist.py` (10 tests: harden plateau/permanent-fill/no-op, cap-holds
fresh+non-fresh, source contracts). FULL Workday suite = **117 passed**.

## PHASE 3 — VALIDATE (IN PROGRESS)
- [x] pytest test_workday*.py green (117).
- [x] test_workday_we_persist.py added + green.
- [x] **LIVE Nvidia 2829 dryrun #1: WE WALL FIXED.** My Experience ADVANCED past the WE step
      into 'Application Question' (first time this cohort cleared WE). Evidence:
      `start_committed=True (mon='3' yr='2024')` (new multi-source log; old would lie False);
      parser respawned empty block idx 70 -> `harden: filling lone permanent empty WE block[70]`
      -> `harden: WE count plateaued clean (total=6 empty=0, stable) -> safe to Next` -> iter 2
      = Application Question. EXACTLY as Phase-1 predicted.
- [!] dryrun #1 then EXIT-5'd at a DISTINCT DOWNSTREAM step: **Self Identify (disability)** form
      loop-capped ('Please choose' / page error; the 3 disabilityStatus options + signed-date
      weren't committing). NOT the WE bug, NOT caused by my changes (commit touched no self-id code).
- [x] Applied a bounded self-id fix (workday-selfid-fix): keyboard-commit signed date via
      `_fill_wd_date` + checked-state-verified single disability-option selection (reads .checked,
      not .value, clears others, retries 3x). Suite still 117 green.
- [ ] dryrun #2 in progress: confirm it now reaches Review (EXIT 0).
- [ ] one real submit attempt (only after a clean dryrun-to-Review).

## PHASE 3 — RESUME (subagent workday-we-persist-finish, 2026-06-10 23:12 PDT)
- [x] Baseline suite re-confirmed GREEN: `pytest test_workday*.py -q` = **121 passed**. Safe tree.
- [x] Confirmed DB role 2829 = status='blocked', applied_by=NULL, NOT booked. No `applications/submitted/nvidia-2829/` dir. Prior 06:01 run reached `nvidia-after-submit.png` but recorded NO confirmation (disk+DB rule: not a submit).
- [x] Forced TRUE fresh: backed up `.workday-creds.json` -> `.bak.20260610-2312-wepersist`, CLEARED nvidia `fresh_alias`/`fresh_password`/`fresh_created` so resolve_account_for_tenant() mints a brand-new alias (empty work-history, no prior-run carry-over). No persistent browser ctx dir existed.
- [ ] LIVE dryrun #2 launching (--dryrun --fresh-account).
- [x] **LIVE dryrun #2 = CLEAN PASS TO REVIEW, EXIT 0** (alias cyshekari+wd-nvidia-202606110614, 2026-06-10 23:1x PDT). Full chain cleared:
      My Information committed -> My Experience filled 3 jobs from tailored resume, parser spawned lone empty req block[182],
      `harden: filling lone permanent empty WE block[182]` -> `harden: WE count plateaued clean (total=4 empty=0, stable) -> safe to Next`
      (WE-persist fix WORKS) -> Application Questions (work-auth=Yes, sponsorship=No) -> Voluntary Disclosure -> Self Identify
      (date committed err=False, `disability option committed: True` -> self-id fix WORKS) -> Review. `DRYRUN: reached Review, stopping before submit` -> EXIT 0.
      No downstream loop. No engine edit needed. Log: /tmp/nvidia2829-dryrun2.log
- [ ] ONE real submit (next step).
- [x] **ONE real submit = CONFIRMED SUBMITTED, EXIT 0** (2026-06-11). Signed into the dryrun's fresh alias (signin_fresh),
      My Experience re-cleared (4 prefilled blocks -> `start_committed=True` proving cross-SESSION date persistence ->
      parser empty block[52] -> `harden: WE count plateaued clean (total=5 empty=0) -> safe to Next`), questions/voluntary/self-id
      cleared -> Review -> `clicking submit-ish: pageFooterNextButton Submit` -> `confirmation matched: application submitted`
      -> `RESULT: SUBMITTED - confirmation verified` -> EXIT 0. Log: /tmp/nvidia2829-submit.log
- [x] **Idempotent corroboration (disk+DB rule): EXIT 7 ALREADY_APPLIED.** Re-ran runner on same alias ->
      `recover_to_step: TERMINAL state 'already_applied'` -> EXIT 7 = Workday blocks re-application = server-side proof the app exists.
      (A standalone logged-OUT fresh-context nav showed 'Apply' = FALSE NEGATIVE; authenticated re-check is authoritative.)
      Log: /tmp/nvidia2829-recheck.log
- [x] **Bookkeeping DONE:** tracker.db.bak.20260611-062642-wepersist -> wrote applications/submitted/nvidia-2829/STATUS.md ->
      UPDATE roles id=2829 status='applied' applied_by='auto' applied_on='2026-06-11' (block_reason cleared, fresh agent_note) ->
      render_xlsx.py (Applied=598). NO engine edit needed this run (dryrun+submit clean on first pass).

## VERDICT (FINAL)
**The Workday cross-nav WORK-EXPERIENCE persistence wall is BEATEN END-TO-END** — first confirmed Workday
auto-submit through the My Experience cross-nav loop. Fix = commits b12fc52 (WE count plateau / harden) +
b5d4d54 (self-id loop). Suite green (121). Nvidia 2829 SUBMITTED + confirmed twice.
**Other WD rows now candidate to batch** (parent decides cohort): all rows previously banked
`workday-fresh-we-block-uncommittable-on-nav` / EXIT-5-on-My-Experience are now worth re-attempting with
the fresh-account runner (see parent's WD queue). Caveat: the SEPARATE EXIT-9 `_WE_PREFILL_UNCOMMITTABLE`
LEGACY-profile class (EXFO/RBI dupe blocks) is a DIFFERENT wall (Cyrus-side profile dedupe) — not unblocked by this fix.

Nvidia 2829: tenant=nvidia (wd5), role 'Infrastructure Solutions Architect',
url=.../NVIDIAExternalCareerSite/.../Infrastructure-Solutions-Architect_JR2019167
resume=../resume/Cyrus_Shekari_Resume.pdf. Forcing --fresh-account (brand-new, no Phase-1
probe carry-over).

## Next:
- Run probe live vs Nvidia 2829. Capture exact persistence mechanism. Then implement + test.

## SUBAGENT PHASE 2 — FIX IMPLEMENTED (wd-boeing-paypal-WE-fix, 2026-06-13)

### Root Cause (CONFIRMED from existing dryrun logs — no new probe needed)
Both Boeing 2546 + PayPal 2891: `harden_my_experience_before_next` fills the permanent empty
WE block with `WORK_HISTORY[0]` (current Microsoft TPM job, `current=True`, no end date).
The `currentlyWorkHere` checkbox commit uses `page.evaluate` JS `.click()` — does NOT reliably
fire React's synthetic onChange. Result: endDate fields stay required in Workday's React model.
Next click returns `'My Experience | Errors Found'` instead of advancing => loop-cap EXIT-5.

### Fix implemented (commit c6167af)
1. `harden_my_experience_before_next`: selects LAST past job (`current=False`, has `end`) for
   permanent empty block fill instead of `WORK_HISTORY[0]`. Past job commits start+end via
   keyboard — no currentlyWorkHere checkbox needed.
2. `click_next`: dumps visible Workday error text when `'Errors Found'` appears in post-Next
   heading (diagnostic improvement, does not change behavior).
3. Tests: 4 new tests added to `test_workday_we_persist.py` (18 total). Full suite: **126 passed**.

### Phase 3: Live dryrun + submit (IN PROGRESS — wd-boeing-paypal-WE-fix subagent 2026-06-13)
- [x] post_next_we_guard also fixed to use past job (commit 8e28b3f)
- [x] Cleared PayPal + Boeing browser data (prevent session carryover from partial run)
- [x] Cleared PayPal fresh_alias to force true fresh account (partial run had polluted account)
- [ ] Dryrun PayPal 2891 (IN PROGRESS)
- [ ] Dryrun Boeing 2546
- [ ] Real submit PayPal 2891 (if dryrun clean)
- [ ] Real submit Boeing 2546 (if dryrun clean)

### Root cause CONFIRMED (from existing dryrun logs — no new probe needed)

**Boeing 2546** has a "Boeing-class required-upload widget": its resume upload field DROPS its
display on EVERY My-Experience revisit (file_present=False → "upload field REQUIRED-EMPTY on revisit
→ allow a bounded re-upload despite fresh-acct cap"). This bypass was added to prevent the empty-resume
blocker, but it has an unintended cascading effect:

EVERY revisit → resume re-parsed by Workday → parser spawns a NEW "add-another" REQUIRED empty WE block
(non-deletable, no delete button, permanent). The harden() function fills it, plateaus clean (empty=0,
stable). BUT click_next STILL BOUNCES — My Experience keeps reappearing each iteration.

**The harden IS working correctly** (WE count plateaued clean ✓). The blocker is NOT the WE count itself.

**ACTUAL ROOT CAUSE**: Boeing's resume upload field ITSELF is `aria-required=true` and the file display
drops on each revisit. The DIAG on visit 2 confirms it: `"errors":["Error-Upload a file (5MB max)The field Upload a file (5MB max) is required and must have a value."]`. The **resume upload field itself is what's blocking Next**, not the WE blocks.

- Fresh-acct upload cap (`_RESUME_UPLOADED >= 1` → skip) correctly skips re-upload.
- But the file widget's REQUIRED check is still active and unmet (the file is actually uploaded server-side but the client-side display dropped = the form widget shows as required+empty again).
- So Next is rejected by the REQUIRED RESUME UPLOAD FIELD, not by any WE block.

### The per-nav-regen sub-class (true Boeing/PayPal pattern)
- Boeing's WD tenant uses a STRICT required-upload widget that drops its visual marker on each visit.
- `file_present` detection is CSS/DOM-only (checks "successfully uploaded" text or file-item widget).
- Workday may be using an iframe or shadow DOM for the file widget that resets on re-render.
- Re-upload is needed BUT causes parser to spawn empty WE blocks, which harden fills.
- The root issue: the cycle repeats without limit because each re-upload triggers a parser block.

### Fix strategy
**OPTION A (preferred, minimal)**: DELETE all filled WE blocks that were generated by the parser (excess
duplicates beyond WORK_HISTORY count) before clicking Next. Boeing re-uploads the resume every visit →
parser creates 1 extra block → harden fills it → 4 blocks total. On Next, the WE step is cleared (since
we have N correctly filled blocks + the file is uploaded). The resume re-upload is what's actually required.

The problem isn't the WE blocks — it's that the `_RESUME_UPLOADED >= 1` cap is PREVENTING re-upload on
Boeing-class tenants that have a MANDATORY re-upload requirement. We need to allow re-upload when the
widget is "required-empty" regardless of cap, but also DELETE the new empty block the parser creates.

**FIX**: On Boeing-class "required-upload on revisit" path:
1. Allow re-upload (already done via the bypass).
2. After populate_work_history + harden, DELETE any WE blocks beyond the expected count (trim to `len(WORK_HISTORY)` + 1 for the "current role" filled block, or just trim all with jobTitle == job[0]['title'] beyond the first).
3. The actual per-nav-regen: after the re-upload, delete the NEW parser-spawned block BEFORE harden even runs.

Actually, examining the logs more carefully:

**Simpler diagnosis**: The bypass for "Boeing-class required-upload widget" re-uploads the resume on EVERY revisit. Each re-upload → parser makes 1 new permanent empty block. Harden fills it. But then Next still bounces because:
- On visit 2, `uploaded=false` → error "Upload a file is required" → this is what blocks Next.

This means: re-upload IS happening (visit 1 with bypass), but the file display DROPS AGAIN on visit 3
(after Boeing's Next bounce brings back My Experience), making the resume appear un-uploaded again.

**The cycle**: Nav to My Experience → re-upload file → parser makes empty block → harden fills → Next bounces (because resume STILL shows as not-uploaded? No... visit 1 shows uploaded=true, visit 2 shows it too... but visit 2 STILL gets REQUIRED-EMPTY bypass!)

**REAL issue found**: `_RESUME_UPLOADED >= 1` cap fires on visit 2 ONLY when the fresh-acct logic is
running AND `file display dropped = False`. But the Boeing-class bypass happens BEFORE the cap check.
On visit 3 (dryrun.log), the skip fires because `_RESUME_UPLOADED >= 1` and `uploaded=false` → the
bypass is for "Boeing-class required-upload widget" but the error still shows on visit 2.

**Key log difference**: dryrun.log visit 2 says `uploaded=false` but the error text says "Error-Upload a file" — this means Boeing is flagging the resume as NOT uploaded on the server even though we uploaded it in visit 1. The fix is to simply re-upload on EVERY Boeing-class visit, but also to DELETE the extra parser-spawned blocks.

### Confirmed root cause (one line):
**Boeing/PayPal WD tenant drops the resume file widget on each navigation → REQUIRES re-upload every visit → each re-upload spawns 1 new permanent "add-another" WE block → WE block count climbs each visit → harden always has N+1 blocks to fill but the resume re-upload error is still blocking Next.**

The actual blocker is: **the resume file widget is `aria-required` and Workday considers the file unuploaded after navigation, regardless of what we did before.** The harden fills the WE blocks correctly. We need to ALSO delete the excess WE blocks (those filled by harden beyond the WORK_HISTORY count) so the form stays clean. And the resume upload MUST happen every visit on these tenants.

