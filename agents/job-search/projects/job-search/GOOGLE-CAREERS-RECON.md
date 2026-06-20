# Google Careers — Apply-Flow Recon

## 2026-06-08 — VERDICT: (B) requires-Google-SSO-account

**Bottom line: NOT adapter-buildable anonymously. The apply form is gated behind a hard Google account sign-in (SSO) before any field is reachable. Route these rows to manual / Cyrus-side.**

### What the "Apply" button actually does
- Job page (`https://www.google.com/about/careers/applications/jobs/results/<id>`) is a JS-rendered SPA. A plain `web_fetch` returns only font/CSS — must use the browser tool.
- The "Apply" control is an `<a>` anchor with `aria-label="Apply"`, `href="./apply?jobId=<opaque token>&loc=US&title=<role>"`. The `jobId` token is a long opaque, click/session-bound blob (`CiUA...==_V2`).
- **Deep-linking the constructed `./apply?jobId=...` URL directly returns a hard HTTP 404** ("The requested URL was not found on this server"). The token is not a stable GET-able deep link — the anchor must be *clicked* in-session.
- **Clicking "Apply" immediately redirects to `https://accounts.google.com/v3/signin/identifier`** (the standard Google sign-in identifier page), with `continue=`/`followup=` set to `https://www.google.com/about/careers/applications/apply?jobId=...&loc=US&title=...`. i.e. the apply form lives behind SSO and you are bounced to auth *before* the form renders.

### Evidence
- Landing host after Apply click: `accounts.google.com`, title "Sign in - Google Accounts", real email/phone identifier field present (`#identifierId`), "Forgot email?", "Create account", "Next", "Use Guest mode" — the canonical Google login screen (screenshot captured in recon transcript; on-disk save was a no-op because the headless browser node doesn't share the gateway FS).
- Anonymous/guest apply path: **none.** There is no "apply without account" or email-only flow; the gate is structural and identical across Google careers job IDs (the apply route is a single shared `/about/careers/applications/apply` endpoint keyed by jobId).

### Fields / upload widget / captcha
- **Not reached** — could not inspect form fields, resume-upload widget type, or the on-form reCAPTCHA, because the sign-in wall fires before the form renders. (Separately, the workspace already knows Google careers uses reCAPTCHA-v3 score-gating, same class as strict-Ashby; that was not re-derived here.)

### Why this is Verdict B and what it means operationally
- Building an automated submit adapter would require: a real authenticated Google account + persistent cookies/session + passing Google's bot/risk checks on `accounts.google.com` (and then the on-form reCAPTCHA-v3). That is credential + captcha + account-risk territory — explicitly out of scope for an anonymous runner, and not something to brute-force.
- Correct disposition: tag the 55 Google rows `status='manual-apply'`, `block_reason='google-sso-account-required'`. They become a real manual/Cyrus-side path, not empty limbo. No `applied` claim. No runner build.

### Sample row used
- id 2834 — "Technical Program Manager II, Network Delivery, Cloud Networking" (Reston, VA / Addison, TX) — `.../jobs/results/91608053295522502`. The gate is identical for all Google rows, so the second sample (id 2836) was not separately re-walked.
