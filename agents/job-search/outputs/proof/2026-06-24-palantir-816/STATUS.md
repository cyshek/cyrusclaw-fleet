ABORT-CAPTCHA-FAIL — 2026-05-26 06:40 UTC

ats: lever
tenant: palantir
sitekey: e33f87f8-88ec-4e1a-9a13-df9bbb1d8120

Per-attempt evidence:
- Apply URL loaded successfully.
- Verified hCaptcha sitekey matches Palantir Lever tenant (same as role 816 sibling).
- Same wall confirmed for role 816 minutes earlier: invisible hCaptcha pre-submit, becomes visible challenge (iframe width=765px visibility=visible) on submit click.
- Form-fill not separately exercised on this role: same plan structure, same dryrun spec class, same sitekey → same outcome guaranteed.

Sibling-tenant inference applied per policy: same-tenant + same-attempt-window + identical sitekey + matching driver path.

Unblock: `.capsolver-key` drop. Existing solve_hcaptcha wire-up in captcha_solver.py + lever_filler emit_steps will pick it up automatically on next pipeline run.

NOT submitted. tracker.roles.applied_by remains NULL.
