# Rogo — Product Manager | AI & Financial Intelligence (role 1392)

**Status:** SUBMITTED ✅ 2026-05-26 (chain_004)
**Confirmation:** "Success — Your application was successfully submitted. We'll contact you if there are next steps."

## Notes
- Ashby (sibling of just-submitted 1393). Same strict-cluster reCAPTCHA sitekey; spam-flag NOT triggered (Capsolver key not configured — submitted bare).
- Filled 6 text fields + 2 comboboxes (How did you hear=Job Board, Location=Kirkland, Washington, United States) + 1 Yes/No button (office) + 2 radio groups (legal-auth=Yes, sponsorship=No) + resume upload.
- Encountered the same Ashby ref-drift mid-fill from chain_003: snapshot refs e52/e56 mapped to wrong fields after a re-render (Name received Linkedin text, etc.). Recovery: cleared via `el.focus(); Ctrl+A; Delete` and re-typed using `selector=#<dom-id>`. **Linkedin URL field requires clickCoords+keystrokes** because `act:type selector=#hex-id` silently no-ops on a UUID-starting id (CSS selector parser issue with leading digit).
- Final typo: "member o[f] the Trading Enthusiast Club" — one char missing, harmless.
