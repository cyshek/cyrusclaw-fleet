# MANUAL-APPLY PACKETS — 21 rows

> **After all done, delete this file.** It's a one-shot, throwaway sitting-pose packet.

**Built:** 2026-05-29 by job-search subagent.
**Cohort:** `flags LIKE '%manual-apply%'` AND not applied AND not (llm-overreach | discovery-only | staffing-firm | location-mismatch) AND status open/null. Exactly 21 rows.

## ⚠️ Read this first — likely-dead listings (skip unless you really want to chase)

Per prior LINKEDIN-BRUTE / chain_026 notes, these LinkedIn URLs are almost certainly stale (role pulled, but LinkedIn keeps a "no longer available" stub at HTTP 200):

| id | company | role | reason |
|---:|---|---|---|
| 992  | Spot & Tango | Product Manager | greenhouse(spotandtango) board has 0 PM roles; listing-pulled |
| 1036 | Otter | PM, Money Platform — NYC | both `otter` + `otterai` greenhouse boards have 0 Money-Platform / NYC PM; listing-pulled |
| 1166 | Sitetracker | Solution Architect | lever(sitetracker) board has 0 SA-family role; listing-pulled |
| 1304 | Weights & Biases | AI SE, Post Sales Scale | W&B was acquired by CoreWeave; current `weights_and_biases` board has 0 matching role; listing-pulled |

The other 17 are real / unverified-but-plausible.

**How to mark applied:**
```bash
projects/job-search/role-discovery/.venv/bin/python projects/job-search/role-discovery/mark_applied.py --id N --method manual
```
(or `--method easy-apply` for LinkedIn one-tap submits; add `--notes "..."` if you want.)

Standard answers (work auth, address, etc.) — `projects/job-search/personal-info.json`. You're a US citizen, no sponsorship, Kirkland WA, 2 yrs FT (3 with internships), email-only contact.

---

## [1/21] Moment — Forward Deployed Engineer — $TC unknown (id=1213) ⭐ PREP-READY
**Apply URL:** https://jobs.ashbyhq.com/moment/752a96ec-5ad1-456e-a98d-6c64c6dfa256
**JD URL:** https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-moment-4386953210
**Why manual:** PREP-READY-MANUAL (driver flagged 2026-05-25; Ashby form with prep packet already at `applications/submitted/moment-752a96ec-.../`). Likely a low-effort polish-and-submit on phone.
**Cover-letter line:** "Deployment Strategist work at Moment maps directly to my Microsoft Copilot Studio rollout experience — I deploy LLM-powered tools into customer environments end-to-end (discovery → integration → measurement) and ship the workflow automation that makes them stick."
**After-apply action:** `mark_applied.py --id 1213 --method manual --notes "ashby moment prep-ready"`

---

## [2/21] Hammerspace — Forward Deployed Engineer — $TC unknown (id=1614)
**Apply URL:** https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-hammerspace-4387455544
**JD URL:** same
**Why manual:** LinkedIn Easy-Apply only (no public ATS board hit). One-tap.
**Cover-letter line:** "Hammerspace's parallel global filesystem is the kind of distributed-data infra I program-manage at Microsoft — I'd be the FDE who actually understands the storage layer when customers deploy it across regions."
**After-apply action:** `mark_applied.py --id 1614 --method easy-apply`

---

## [3/21] turbalance — Forward Deployed Engineer — $TC unknown (id=1207)
**Apply URL:** https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-turbalance-4413468573
**JD URL:** same
**Why manual:** LinkedIn Easy-Apply (no public ATS board). Tiny startup, low signal.
**Cover-letter line:** *(skip unless required — early stage, recruiter just wants resume)*
**After-apply action:** `mark_applied.py --id 1207 --method easy-apply`

---

## [4/21] Haystack — Product Manager — $TC unknown (id=1017)
**Apply URL:** https://www.linkedin.com/jobs/view/product-manager-at-haystack-4414748997
**JD URL:** same
**Why manual:** LinkedIn Easy-Apply (no public ATS board hit).
**Cover-letter line:** *(skip unless required)*
**After-apply action:** `mark_applied.py --id 1017 --method easy-apply`

---

## [5/21] AceStack — Technical Product Manager (Seattle/Austin) — $TC unknown (id=1051)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-product-manager-seattle-wa-austin-tx-at-acestack-4415101635
**JD URL:** same
**Why manual:** LinkedIn Easy-Apply, contract/staffing-adjacent. Seattle works (you're in Kirkland).
**Cover-letter line:** *(skip unless required)*
**After-apply action:** `mark_applied.py --id 1051 --method easy-apply`

---

## [6/21] AceStack — Technical Product Manager (Seattle/Austin) — $TC unknown (id=1253)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-product-manager-seattle-wa-austin-tx-at-acestack-4415663530
**JD URL:** same
**Why manual:** Same title/company as id=1051, separate posting. Apply to both.
**Cover-letter line:** *(skip unless required)*
**After-apply action:** `mark_applied.py --id 1253 --method easy-apply`

---

## [7/21] Programming.com — Technical Program Manager — $TC unknown (id=1260)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-program-manager-at-programming-com-4415501221
**JD URL:** same
**Why manual:** LinkedIn Easy-Apply, no ATS board. Generic agency posting.
**Cover-letter line:** *(skip unless required)*
**After-apply action:** `mark_applied.py --id 1260 --method easy-apply`

---

## [8/21] Tradeweb — AVP, Product Manager, Fixed Income Credit — $TC unknown (id=1448)
**Apply URL:** https://www.linkedin.com/jobs/view/avp-product-manager-fixed-income-credit-at-tradeweb-4408594613
**JD URL:** same
**Why manual:** Custom ATS not in our adapter set — likely LinkedIn Apply → external redirect. May ask the standard ~6 prefill questions.
**Quick answers:** YOE=2 FT / 3 w/ internships; location Kirkland WA; willing to relocate yes; sponsorship no; US citizen.
**Cover-letter line:** "Fixed-income electronic trading is exactly the high-throughput, low-latency systems work I program-manage at Microsoft — I'd bring product chops *and* the technical fluency to ship credit-trading features cross-functionally."
**After-apply action:** `mark_applied.py --id 1448 --method manual`

---

## [9/21] Alibaba Cloud — Solutions Architect — $TC unknown (id=1129)
**Apply URL:** https://www.linkedin.com/jobs/view/solutions-architect-at-alibaba-cloud-4403171502
**JD URL:** same
**Why manual:** LinkedIn Easy-Apply, no public board. (Note: Alibaba US-presence is small — may be remote/SF.)
**Cover-letter line:** *(skip unless required)*
**After-apply action:** `mark_applied.py --id 1129 --method easy-apply`

---

## [10/21] Paramount+ — Associate Product Manager, Content Discovery — $TC unknown (id=1020)
**Apply URL:** https://www.linkedin.com/jobs/view/associate-product-manager-content-discovery-at-paramount%2B-4414248511
**JD URL:** same
**Why manual:** iCIMS ATS — not in our adapter set, so manual on phone. iCIMS likes a quick account creation; use Google SSO if offered.
**Quick answers:** YOE=2 FT / 3 w/ internships; current employer Microsoft; willing to relocate yes.
**Cover-letter line:** "Content discovery is recommender-systems + UX — the same instincts I use building Copilot Studio agents at Microsoft (surface the right answer, surface it fast, learn from the click)."
**After-apply action:** `mark_applied.py --id 1020 --method manual --notes "icims"`

---

## [11/21] NBCUniversal — Associate Product Manager — $TC unknown (id=1028)
**Apply URL:** https://www.linkedin.com/jobs/view/associate-product-manager-at-nbcuniversal-4415399217
**JD URL:** same
**Why manual:** iCIMS ATS (same drill as Paramount+ above).
**Quick answers:** standard (YOE=2 / 3-w-internships, Kirkland WA, US citizen, no sponsorship).
**Cover-letter line:** *(skip unless required)*
**After-apply action:** `mark_applied.py --id 1028 --method manual --notes "icims"`

---

## [12/21] Amazon — TPM, Testing and User Experience, Fauna — $TC unknown (id=1090)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-program-manager-testing-and-user-experience-fauna-at-amazon-4404519321
**JD URL:** same
**Why manual:** amazon.jobs custom ATS — not in our adapter. ~5min on phone. Sign in via your existing amazon.jobs account if you have one.
**Quick answers:** YOE 2 FT (3 w/ internships); current employer Microsoft TPM; willing to relocate yes; sponsorship no.
**Cover-letter line:** "I'm a TPM at Microsoft shipping AI-agent infra; Fauna's testing-and-UX scope across a globally-distributed DB is exactly the cross-stack program work I run today."
**After-apply action:** `mark_applied.py --id 1090 --method manual --notes "amazon.jobs"`

---

## [13/21] Amazon — Technical Infrastructure Program Manager, Tech Deploy NA — $TC unknown (id=1093)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-infrastructure-program-manager-deployment-optimization-tech-deploy-north-america-at-amazon-4414659740
**JD URL:** same
**Why manual:** amazon.jobs (same login as id=1090; do these back-to-back).
**Quick answers:** standard.
**Cover-letter line:** "Deployment optimization across NA infra is the *exact* shape of my Microsoft work — rollout sequencing, dependency-graph cleanup, blast-radius gates."
**After-apply action:** `mark_applied.py --id 1093 --method manual --notes "amazon.jobs"`

---

## [14/21] AWS — Solutions Architect, Games — $TC unknown (id=1164)
**Apply URL:** https://www.linkedin.com/jobs/view/solutions-architect-games-at-amazon-web-services-aws-4392036273
**JD URL:** same
**Why manual:** amazon.jobs (third in the Amazon batch — same session).
**Quick answers:** standard.
**Cover-letter line:** "Cloud SA work for game studios = latency-critical, spiky workloads, multi-region failover. I program-manage that pattern at Microsoft today."
**After-apply action:** `mark_applied.py --id 1164 --method manual --notes "amazon.jobs"`

---

## [15/21] AWS — Forward Deployed Engineer, WWPS ProServe — $TC unknown (id=1336)
**Apply URL:** https://www.linkedin.com/jobs/view/forward-deployed-engineer-wwps-proserve-at-amazon-web-services-aws-4414960926
**JD URL:** same
**Why manual:** amazon.jobs (fourth/last in the Amazon batch — knock all 4 out in one login).
**Quick answers:** standard. ⚠️ WWPS = World-Wide Public Sector → may ask security-clearance questions. You have **none** (per `personal-info.json`); answer truthfully.
**Cover-letter line:** "I bring TPM rigor + hands-on AI-agent deployment experience — exactly what ProServe customers need to take a Bedrock POC into production."
**After-apply action:** `mark_applied.py --id 1336 --method manual --notes "amazon.jobs WWPS"`

---

## [16/21] AMD — Technical Program Manager — AI Cluster Validation — $TC unknown (id=1478)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-program-manager-ai-cluster-validation-at-amd-4405576921
**JD URL:** same
**Why manual:** Workday-CXS tenant (auth-walled for anonymous HTTP) — phone with logged-in Workday session works. Likely 2-3min after login.
**Quick answers:** YOE 2 FT (3 w/ internships); standard the rest. **Important:** AMD will ask "have you previously applied" — answer no unless you have.
**Cover-letter line:** "MI300/MI325 cluster validation is the high-stakes hardware-bringup TPM work I love — I'd own the test-plan execution and the cross-team escalation path from silicon issue → fleet rollback."
**After-apply action:** `mark_applied.py --id 1478 --method manual --notes "workday"`

---

## [17/21] Tesla — TPM, Electronic Systems, Displays — $TC unknown (id=1491)
**Apply URL:** https://www.linkedin.com/jobs/view/technical-program-manager-electronic-systems-displays-at-tesla-4418690778
**JD URL:** same
**Why manual:** Workday-CXS auth-walled. Tesla's careers portal often demands account creation; use Google/LinkedIn SSO if available.
**Quick answers:** YOE 2 FT (3 w/ internships); Kirkland WA → ⚠️ Tesla role likely Palo Alto / Austin on-site; willing-to-relocate=yes.
**Cover-letter line:** "Vehicle-display program management = hardware-software co-design under brutal schedule pressure. That's the exact muscle I built at Microsoft shipping cross-stack AI features."
**After-apply action:** `mark_applied.py --id 1491 --method manual --notes "workday"`

---

## [18/21] Spot & Tango — Product Manager — $TC unknown (id=992) ⚠️ likely listing-pulled
**Apply URL:** https://www.linkedin.com/jobs/view/product-manager-at-spot-tango-4393243517
**JD URL:** same
**Why manual:** LinkedIn link is live but greenhouse(spotandtango) board has 0 PM roles — role probably pulled. **Skip unless you specifically want to try.**
**After-apply action:** `mark_applied.py --id 992 --method manual` (or just leave unapplied; closed-out via weekly auto-close)

---

## [19/21] Otter — PM, Money Platform (NYC) — $TC unknown (id=1036) ⚠️ likely listing-pulled
**Apply URL:** https://www.linkedin.com/jobs/view/product-manager-money-platform-new-york-ny-at-otter-4371708110
**JD URL:** same
**Why manual:** Otter + OtterAI greenhouse boards have 0 NYC Money-Platform PM — almost certainly killed. **Skip.**
**After-apply action:** `mark_applied.py --id 1036 --method manual` (or skip)

---

## [20/21] Sitetracker — Solution Architect — $TC unknown (id=1166) ⚠️ likely listing-pulled
**Apply URL:** https://www.linkedin.com/jobs/view/solution-architect-at-sitetracker-4410197158
**JD URL:** same
**Why manual:** lever(sitetracker) board has 0 SA-family role. **Skip.**
**After-apply action:** `mark_applied.py --id 1166 --method manual` (or skip)

---

## [21/21] Weights & Biases — AI SE, Post Sales Scale — $TC unknown (id=1304) ⚠️ likely listing-pulled
**Apply URL:** https://www.linkedin.com/jobs/view/ai-solutions-engineer-post-sales-scale-w-b-at-weights-biases-4373720490
**JD URL:** same
**Why manual:** W&B acquired by CoreWeave; current `weights_and_biases` board has 0 matching role. **Skip** — but if you want to look at CoreWeave SA roles, they're already on the main board (you have many CoreWeave rows in the tracker).
**After-apply action:** `mark_applied.py --id 1304 --method manual` (or skip)

---

## Summary

- **17 real ones** to fire through (ids 1213, 1614, 1207, 1017, 1051, 1253, 1260, 1448, 1129, 1020, 1028, 1090, 1093, 1164, 1336, 1478, 1491).
- **4 likely-dead** at the bottom (992, 1036, 1166, 1304) — skip or mark applied "for closure" with `mark_applied.py`.
- **Two batched logins to optimize:** all 4 Amazon/AWS rows (1090, 1093, 1164, 1336) share the amazon.jobs login. The 2 iCIMS (1020, 1028) and 2 Workday-CXS (1478, 1491) are all separate tenants — no batching there.
- Helper `projects/job-search/role-discovery/mark_applied.py` is tested (dry-run + refusal-on-already-applied). It backs up tracker.db once per day before the first write.

Delete this file when done.
