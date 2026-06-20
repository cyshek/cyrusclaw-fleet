# RESOLVED-NEXT-BATCH.md
Non-browser ATS URL resolution for LinkedIn-stranded roles. Generated 2026-06-10 by resolve-ats-next-batch subagent.
Method: direct ATS board-API / CXS queries via curl + web_search (NO browser, NO submit). Verified live where noted.

---

## 2531 | Airbnb | "Program Manager, Community Support" | greenhouse
NOT-FOUND.
- Airbnb greenhouse board (`boards-api.greenhouse.io/v1/boards/airbnb/jobs`, slug `airbnb`) is LIVE and complete (217 jobs). Apply URLs are `careers.airbnb.com/positions/<id>?gh_jid=<id>`.
- Grepped all 217 titles: ZERO match for "Program Manager, Community Support". No program/project-manager title containing "community" or "support" exists. Closest are Community-Support *engineering/ML* roles + "Senior Manager Global Capacity and Operational Planning (Community Support)" — none match.
- Conclusion: role is CLOSED / filled / delisted. The Airbnb GH board is authoritative and the title is simply absent.

## 2545 | Nordstrom | "Digital Asset & Content Supply Chain Product Manager" Seattle | workday
NOT-FOUND (likely too-new to index, but no canonical apply URL resolvable headlessly).
- Tenant CONFIRMED: `nordstrom.wd501.myworkdayjobs.com` site `nordstrom_careers` (CXS endpoint works: `…/wday/cxs/nordstrom/nordstrom_careers/jobs`). Careers front `careers.nordstrom.com` is bot-blocked (403 Access Denied) for both api/jobs and direct.
- Searched CXS with searchText "Digital Asset", "Content Supply Chain Product Manager", "Asset Content Supply", exact full title — the specific req does NOT appear in results (494 hits for "Digital Asset" are generic merchandising/stylist/PM roles; none titled Digital Asset & Content Supply Chain).
- web_search confirms the role IS live (Indeed jk=6a7177d99dbd4d8c, "2 days ago") but only via Indeed aggregator, not a resolvable Nordstrom apply URL. Brand-new req not yet in the CXS search index.
- If needed manually, base host to re-check shortly: `https://nordstrom.wd501.myworkdayjobs.com/en-US/nordstrom_careers` (search "Digital Asset Content Supply"). Indeed fallback: https://www.indeed.com/viewjob?jk=6a7177d99dbd4d8c

## 2542 | Gates Foundation | "Senior Technical Program Manager" | workday
FOUND (workday). VERIFIED live (CXS 200).
- URL: https://gatesfoundation.wd1.myworkdayjobs.com/en-US/Gates/job/Seattle-WA/Senior-Technical-Program-Manager--Microsoft-M365-Productivity---Collaboration_B021600-1
- Tenant `gatesfoundation.wd1.myworkdayjobs.com`, site `Gates`. Full title: "Senior Technical Program Manager, Microsoft M365 Productivity & Collaboration" (Seattle, WA). Matches the JD (jobrapido 2026-06-02: "productivity and collaboration services… support the foundation"). Req B021600-1.
- NOTE: `gatesventures` greenhouse slug exists (200) but that is Bill Gates' personal office (Gates Ventures), NOT the Foundation — do not use it.

## 2525 | Expedia Group | "Program Manager III" | workday
NOT-FOUND (tenant identified, exact req closed).
- Tenant CONFIRMED: `expedia.wd108.myworkdayjobs.com` site `search` (CXS works). NOT wd5/wd1/wd3 (all 500).
- The generic "Program Manager III" req surfaced in web_search (R-103304, `…/job/Program-Manager-III_R-103304/apply/applyManually`) is now CLOSED — job endpoint returns 404.
- Current live CXS "Program Manager III" results (total 6) are all specialized variants (Machine Learning Scientist III, Product Manager III - Content Team / B2B AI, UX Content Designer III, SDE III) — none is a plain "Program Manager III". No exact match live.
- If a new generic PM III opens, it'll be at `https://expedia.wd108.myworkdayjobs.com/en-US/search` (searchText "Program Manager III").

## 2530 | Docusign | "Lead Technology & Business Operations" | (iCIMS/careers-home)
FOUND (Docusign careers-home, backed by iCIMS). VERIFIED (careers page 302→SPA, req present in api/jobs).
- URL: https://careers.docusign.com/en/jobs/29221
- Req 29221, title "Lead Technology & Business Operations", Seattle. Found by paging `careers.docusign.com/api/jobs?page=N&limit=100` and grepping titles (server-side keyword param is ignored, must page+grep).
- Docusign is NOT greenhouse and NOT on a public Workday CXS. Careers front = careers.docusign.com (apply flows route through `uscareers-docusign.icims.com`). The stale SmartRecruiters `DocuSign` board (1 job, 2018) is dead — ignore.

## 2529 | Fanatics | "Manager, Product Strategy and Insights" | greenhouse
NOT-FOUND.
- Fanatics greenhouse slug = `fanaticsinc` (LIVE, 24 jobs; apply URLs `job-boards.greenhouse.io/fanaticsinc/jobs/<id>`). NOT `fanatics`/`fanaticsinc`→ only `fanaticsinc` works (plain `fanatics` 404).
- Grepped all 24 titles for manager+product/insight/strategy: ZERO match for "Manager, Product Strategy and Insights". Only strategy-adjacent title is "Director, Enterprise Payments Strategy & Partnerships" (different role/level).
- Also checked SmartRecruiters `Fanatics` → 0 postings. Conclusion: role CLOSED / filled, or it's a Fanatics sub-brand (Betting/Collectibles/Commerce) on a separate board — but not on the corporate `fanaticsinc` GH board.

---
## SUMMARY (terse)
- 2531 Airbnb — NOT-FOUND (closed; GH board authoritative, title absent)
- 2545 Nordstrom — NOT-FOUND (Workday tenant nordstrom.wd501/nordstrom_careers confirmed; req too-new/not in CXS index; careers-home bot-blocked)
- 2542 Gates Foundation — FOUND workday: https://gatesfoundation.wd1.myworkdayjobs.com/en-US/Gates/job/Seattle-WA/Senior-Technical-Program-Manager--Microsoft-M365-Productivity---Collaboration_B021600-1
- 2525 Expedia — NOT-FOUND (tenant expedia.wd108/search confirmed; exact "Program Manager III" req R-103304 now 404/closed)
- 2530 Docusign — FOUND careers-home/iCIMS: https://careers.docusign.com/en/jobs/29221
- 2529 Fanatics — NOT-FOUND (GH slug fanaticsinc confirmed; title absent/closed)
