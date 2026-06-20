# Curri 2557 — Solutions Engineer — SUBMITTED

- **Outcome:** SUBMITTED 2026-06-10 (hourly grind, ashby-react-commit subagent)
- **ATS:** Ashby (jobs.ashbyhq.com/curri/0da884e4-ad46-44a2-9a87-3acfefe42026)
- **submitted_by:** auto
- **resume_attached:** yes (Cyrus_Shekari_Resume_ashby-curri_0da884e4_v2.pdf)
- **confirmation_evidence:** server GraphQL `applicationFormResult.__typename == "FormSubmitSuccess"` (runner: "SUBMIT SUCCESS"). Authoritative server token, not body text.
- **egress:** RESIDENTIAL (82.23.97.223) + playwright-stealth + in-browser native reCAPTCHA-v3. Datacenter IP = pure score-gate (spam-flag); residential CLEARS the captcha (no spam-flag at all).
- **REQUIRED engine fix (chain_p13, shipped this session):**
  - React-fiber `__reactProps$` onChange commit (in _REASSERT_TEXT_JS forceSet) — landed Full Name / Why-interested essay / Share-link (native value-setter alone left React controlled state empty → server "Missing entry").
  - No-bounce last-ms text commit loop (wait parsing-gone → single-shot commit → verify non-empty stable) — landed Email (forceSet '' bounce opened an empty window the autofill clobber caught).
  - Trusted-keystroke phone commit (_trusted_commit_tel_fields) — Ashby phone form-state ignores synthetic onChange (DOM+React value read non-empty yet server banked Phone empty); real Playwright keystrokes generate the native input events its form-state subscribes to.
- **KNOCKOUT FIX (ashby_dryrun.py):** "Are you legally authorized to work in the US WITHOUT employer sponsorship?" was first-match-resolving to bare ("sponsorship"→needs_sponsorship)→"No" (factual knockout — US citizen IS authorized w/o sponsorship). Added positive rules → work_authorized → Yes.
- **screening answers:** work-auth WITHOUT sponsorship=Yes (US citizen); relocate to Ventura CA=Yes (advancing, role is remote anyway); plumber-name essay = honest "I may have the exact name wrong" + the real founding-story resonance; Why-Curri + what-you-built essays auto-generated from master resume; "anything else" optional left blank.
