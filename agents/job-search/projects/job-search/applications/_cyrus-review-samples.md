# Cyrus Review Samples — 5 random successful applications

_Generated 2026-05-17 by job-search subagent. Three ATSes represented: Workday, Greenhouse, Greenhouse-iframe. (Ashby skipped — reCAPTCHA wall blocking all auto-submits; Lever skipped — hCaptcha wall, see MEMORY.md.)_

## 1. Adobe — Engineering Product Manager (Workday)

- **Role id:** 9
- **ATS:** Workday (Adobe tenant — first end-to-end auto-submit, 2026-05-16)
- **Applied:** 2026-05-16, response `received` ("Thanks for Applying to Adobe" email confirmed)
- **Workday confirmation ID:** `688ddd4f2bc490002b74f725a3910000`
- **Confirmation screenshot:** [`applications/submitted/adobe-r163295/confirmation.png`](submitted/adobe-r163295/confirmation.png)
- **Resume:** _master resume — Workday Adobe submit pre-dates bullet_rewriter integration. Workday packets from 2026-05-17 onward use tailored resumes (see new HPE/Intel/Nvidia/Baker Hughes packets in Manual Ready tab)._
- **Tailoring note:** N/A for this packet.

## 2. Anthropic — Technical Program Manager, Security (Greenhouse)

- **Role id:** 929
- **ATS:** Greenhouse (native, job-boards.greenhouse.io/anthropic)
- **Applied:** 2026-05-13, response `received` ("Thank you for applying to Anthropic")
- **Confirmation screenshot:** [`applications/submitted/anthropic-4989788008/screenshots/confirmation.png`](submitted/anthropic-4989788008/screenshots/confirmation.png)
- **Resume:** [`applications/submitted/anthropic-4989788008/Cyrus_Shekari_Resume_anthropic_4989788008_v2.pdf`](submitted/anthropic-4989788008/Cyrus_Shekari_Resume_anthropic_4989788008_v2.pdf)
- **Tailoring note:** All swappable Microsoft/Amazon roles re-titled to "Technical Program Manager"; security & compliance bullets emphasized.

## 3. Anduril — Program Manager, Safety and Standards (Greenhouse)

- **Role id:** 21
- **ATS:** Greenhouse (native, job-boards.greenhouse.io/andurilindustries)
- **Applied:** 2026-05-13, response `received` ("Thank you for applying to Anduril Industries, Cyrus!")
- **Confirmation screenshot:** _not captured (Greenhouse path didn't default to screenshot save on 2026-05-13; Gmail confirmation serves as proof of submit)._
- **Resume:** [`applications/submitted/anduril-5006277007/Cyrus_Shekari_Resume_andurilindustries_5006277007_v2.pdf`](submitted/anduril-5006277007/Cyrus_Shekari_Resume_andurilindustries_5006277007_v2.pdf)
- **Tailoring note:** All swappable roles re-titled to "Program Manager"; safety/standards/regulatory framing emphasized.

## 4. MongoDB — Pre-Sales Solutions Architect (Greenhouse-iframe)

- **Role id:** 751
- **ATS:** Greenhouse-iframe (mongodb.com careers → embed/job_app)
- **Applied:** 2026-05-13, response `received` ("Thank you for applying to MongoDB")
- **Confirmation screenshot:** _not captured (Greenhouse-iframe path; Gmail confirmation = proof)._
- **Resume:** [`applications/submitted/mongodb-7458644/Cyrus_Shekari_Resume_mongodb_7458644_v2.pdf`](submitted/mongodb-7458644/Cyrus_Shekari_Resume_mongodb_7458644_v2.pdf)
- **Tailoring note:** Microsoft FT re-titled "Technical Program Manager"; intern roles split between TPM/Technical Product Manager Intern; database/solutions-architect framing emphasized.

## 5. CoreWeave — Solutions Architect (Greenhouse-iframe)

- **Role id:** 603
- **ATS:** Greenhouse-iframe (coreweave.com careers → embed/job_app)
- **Applied:** 2026-05-13, response `received` ("Thank you for applying to CoreWeave")
- **Confirmation screenshot:** _not captured; Gmail confirmation = proof._
- **Resume:** [`applications/submitted/coreweave-4622845006/Cyrus_Shekari_Resume_coreweave_4622845006_v2.pdf`](submitted/coreweave-4622845006/Cyrus_Shekari_Resume_coreweave_4622845006_v2.pdf)
- **Tailoring note:** Microsoft FT re-titled "Technical Program Manager"; pro_painters role re-titled "Technical Product Manager Intern"; GPU/infrastructure/solutions framing emphasized.

---

## Notes for future runs

- **Screenshots aren't standard for Greenhouse / iframe paths.** Only the new Workday driver (`workday_playwright.py`) auto-saves `confirmation.png`. Greenhouse-driver subagents from 2026-05-13 evening did NOT default to screenshot capture (per Cyrus 2026-05-13: "I don't need you to take screenshots unless I ask"). Gmail "Thanks for applying" emails are the canonical proof.
- **Tailoring coverage:** every successful Greenhouse / iframe auto-submit since 2026-05-13 has a `Cyrus_Shekari_Resume_<org>_<jid>_v2.pdf` + `cover_answers.md` + `tailoring-notes.md` + `rewrites.json` in its packet folder. The Adobe Workday packets from 2026-05-16 used the master resume (Workday driver was first-light); the new Workday packets prepped tonight (2026-05-17) include tailored resumes.
