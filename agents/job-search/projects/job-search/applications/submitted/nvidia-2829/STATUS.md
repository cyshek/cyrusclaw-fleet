# STATUS — Nvidia 2829 Infrastructure Solutions Architect (JR2019167) — SUBMITTED ✅

- **Outcome:** SUBMITTED (auto, Workday fresh-account) — 2026-06-11
- **Submitted by:** auto-workday-fresh (runner `_workday_runner.py`, mode=create_fresh→signin_fresh)
- **Account used:** cyshekari+wd-nvidia-202606110614@gmail.com (brand-new fresh alias minted this run; empty work-history filled from tailored resume)
- **Apply URL:** https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Infrastructure-Solutions-Architect_JR2019167
- **Tenant:** nvidia (wd5) | **Resume attached:** YES — ../resume/Cyrus_Shekari_Resume.pdf (uploaded; "Cyrus_Shekari_Resume.pdf successfully uploaded")

## Confirmation evidence (disk+DB rule — TWO independent authenticated signals)
1. **At submit time** (run log /tmp/nvidia2829-submit.log):
   - Review step reached → `clicking submit-ish: [data-automation-id=pageFooterNextButton] Submit`
   - `confirmation matched: application submitted`
   - `RESULT: SUBMITTED - confirmation verified` → **EXIT 0**
   - Screenshot: .workday-debug/nvidia-after-submit.png (06:20)
2. **Idempotent re-check** (run log /tmp/nvidia2829-recheck.log) — authoritative server-side proof:
   - Signed into the same alias → `recover_to_step: TERMINAL state 'already_applied' -- stopping recovery`
   - `RESULT: ALREADY_APPLIED (Workday you-applied banner)` → **EXIT 7**
   - Workday itself blocks re-application = the application exists server-side.
- NOTE: a standalone fresh-context JD navigation showed "Apply"/"Sign In" — that was a FALSE NEGATIVE
  (the standalone diagnostic session was logged OUT; only an authenticated session sees the
  already-applied terminal state, which the EXIT-7 re-check confirmed).

## Significance — Workday cross-nav WE-persistence wall BEATEN end-to-end
This is the first confirmed Workday auto-submit through the previously-impassable My Experience
cross-nav loop (`workday-fresh-we-block-uncommittable-on-nav`). The fix (commits b12fc52 + b5d4d54):
- `harden_my_experience_before_next()` makes the WE block COUNT plateau (delete parser-spawned empties +
  fill the lone permanent empty once) before click_next — log proof:
  `harden: WE count plateaued clean (total=5 empty=0, stable) -> safe to Next`.
- Multi-source committed-date read replaces the lying `start_filled=False` diagnostic — proved dates
  PERSIST across navigation/sessions: `date-repair block[8] Microsoft: start_committed=True (mon='3' yr='2024')`.
- Downstream Self-Identify disability loop fixed (date keyboard-commit + checked-state-verified option):
  `disability option committed: True`.

## Bookkeeping
- tracker.db backup: tracker.db.bak.20260611-062642-wepersist (BEFORE the UPDATE)
- roles UPDATE: applied_by='auto', applied_on='2026-06-11', status='applied' WHERE id=2829
- render_xlsx.py: run once after the UPDATE
