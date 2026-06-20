# Modal Labs — Customer Engineer (role 936)

STATUS: SUBMITTED ✅
submitted_on: 2026-06-11
submitted_by: auto-residential (Ashby residential-egress drain subagent, retry run)
resume_attached: yes (Cyrus_Shekari_Resume_ashby-modal_44b57790_v2.pdf)

## Confirmation evidence
- Runner _ashby_runner.py classify="submitted" - FormSubmitSuccess token in captured submit POST.
- Ashby post-submit page text: "Your application was successfully submitted. We'll reach out with any next steps!"
- app_url: https://jobs.ashbyhq.com/modal/44b57790-528e-4f97-8613-03564316be8a
- Egress: residential 82.23.97.223 (proxied Chrome CDP 127.0.0.1:19223) - NOT Azure datacenter IP.
- Run: 2026-06-11 ashby-residential-drain retry (prior worker missed this id from WORK list).

## Notes
- Modal is PERMISSIVE tenant - score gate not an issue.
- Prior chain_035 stamp claimed submitted but disk STATUS.md was still PREP-READY (no success block written).
  This run confirmed genuine submit via FormSubmitSuccess.
