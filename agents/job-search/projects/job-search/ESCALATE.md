# ESCALATE.md — items the burndown subagent kicked back

## ~~2026-05-24 17:14 — Pinterest greenhouse_iframe classification~~ — RESOLVED 17:18

Initial concern was conflicting evidence about whether Pinterest is a Greenhouse iframe tenant. Probed empirically:
- `pinterestcareers.com` is built on Happydance behind Cloudflare (CF blocked our scrape; HTML mentions `happydance.website`).
- The underlying GH board `https://job-boards.greenhouse.io/embed/job_app?for=pinterest&token=7714127` returns HTTP 200 with a real 77KB application form including `first_name` etc.

**Conclusion:** The 2026-05-13 scout report mapping (`pinterestcareers.com → pinterest` in `HOST_TO_GH_SLUG`) is correct. The BACKLOG claim was wrong. **No code change made; BACKLOG P0 follow-up #3 annotation reversed.**

Leaving this section here as a historical breadcrumb. No active escalations as of 2026-05-24 17:18.

---

(No open escalations.)
