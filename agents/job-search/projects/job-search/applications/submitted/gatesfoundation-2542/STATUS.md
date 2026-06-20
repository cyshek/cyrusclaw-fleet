# Gates Foundation 2542 — SUBMITTED (auto-workday-fresh)

- **Role:** Senior Technical Program Manager, Microsoft M365 Productivity & Collaboration (req B021600-1)
- **Company:** Gates Foundation (tenant gatesfoundation, wd1)
- **Submitted:** 2026-06-11 (PDT) by auto-workday-fresh
- **Account:** signin_fresh into existing fresh alias cyshekari+wd-gatesfoundation-202606110030@gmail.com
- **Apply URL:** https://gatesfoundation.wd1.myworkdayjobs.com/Gates/job/Seattle-WA/Senior-Technical-Program-Manager--Microsoft-M365-Productivity---Collaboration_B021600-1
- **submitted_by:** auto-workday-fresh
- **resume_attached:** YES — ../resume/Cyrus_Shekari_Resume.pdf (uploaded; "Cyrus_Shekari_Resume.pdf successfully uploaded")

## Confirmation (disk+DB rule — BOTH directions verified)
1. **Submit run (EXIT 0):** `[wd] clicking submit-ish: [data-automation-id=pageFooterNextButton] Submit`
   → `[wd] confirmation matched: thank you for applying`
   → `[wd] RESULT: SUBMITTED - confirmation verified` → EXIT 0.
   Confirmation route reached after Review step. Log: /tmp/gates2542-submit.log
2. **Idempotent re-check (EXIT 7 = server-side proof):** re-ran runner on same alias →
   `recover_to_step: TERMINAL state 'already_applied'` →
   `RESULT: ALREADY_APPLIED (Workday you-applied banner)` → EXIT 7.
   fail-state url=.../apply/applyManually showed the you-already-applied banner.
   Log: /tmp/gates2542-recheck.log

## WE-fix generalization evidence (the point of this run)
- Dryrun + submit both cleared My Experience cleanly via the new harden logic:
  `harden: filling lone permanent empty WE block[63]` → date-commit OK →
  `harden: WE count plateaued clean (total=6 empty=0, stable) -> safe to Next`.
- Account had 5 prefilled WE blocks (Microsoft×3 / Amazon Robotics / Pro Painters) from prior runs;
  `start_committed=True` on all (multi-source read), converged — NOT the EXIT-9 dupe-class.
- Application Questions auto-answered (work-auth=Yes, visa=No, 18+=Yes, interview-transcribe-consent=Yes,
  grantee-of-foundation=Yes, primaryQuestionnaire="Yes, I consent") per form-answer doctrine.
- Self-Identify disability: signed-date committed (06/11/2026), disability option committed=True.

**This is the SECOND tenant (after Nvidia 2829) proving the cross-nav WE fix generalizes.**
