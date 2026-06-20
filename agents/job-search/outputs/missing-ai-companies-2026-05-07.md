# Missing AI Companies — Slug Validation 2026-05-07

Subagent task: probe Greenhouse / Lever / Ashby / SmartRecruiters / Workday for 12 AI-native companies and add valid entries to `projects/job-search/role-discovery/companies.yaml`.

Probe endpoints:
- GH:    `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- Lever: `https://api.lever.co/v0/postings/{slug}?mode=json`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}`
- SR:    `https://api.smartrecruiters.com/v1/companies/{slug}/postings` (NOTE: returns 200/empty for any string — must check `totalFound>0` or job content)

## Results (8 added, 4 skipped)

| # | Company | Found | Adapter | Slug | Notes |
|---|---|---|---|---|---|
| 1 | Anysphere | SKIP | — | — | Same as **Cursor** (already in yaml: `ashby/cursor`, 87 jobs). `posting-api/job-board/anysphere` → 404. No dup added. |
| 2 | Character.AI | ✅ | ashby | `character` | Tried `characterai`, `character-ai`, `charactertechnologies`, `character`. Only `character` returned 200 with jobs. |
| 3 | Hippocratic AI | ❌ | — | — | Tried GH/Lever/Ashby/SR with variants `hippocraticai`, `hippocratic-ai`, `hippocratic`. Public Ashby board exists at `jobs.ashbyhq.com/hippocraticai` but **posting-api returns 404** (private/disabled API). Commented-out placeholder added. |
| 4 | EvenUp | ❌ | — | — | Tried GH/Lever/Ashby/SR (`evenup`, `evenuplaw`, `evenup-law`, `even-up`). Public Ashby board at `jobs.ashbyhq.com/evenup` (orgId `a97fe582-...`) but **posting-api 404**. SR returns 0 jobs. Commented-out placeholder added. |
| 5 | Ironclad | ❌ | — | — | Tried GH/Lever/Ashby/SR (`ironclad`, `ironcladapp`, `ironclad-inc`, `ironcladhq`). Public Ashby board exists at `jobs.ashbyhq.com/ironclad` but **posting-api 404**. SR returns empty. Commented-out placeholder added. |
| 6 | CoreWeave | ✅ | greenhouse | `coreweave` | 200 OK, large board (241kb response). |
| 7 | Lambda (Labs) | ✅ | ashby | `lambda` | 200 OK posting-api, 474kb. Tried `lambda`, `lambdalabs`, `lambda-labs`, `lambdalabsinc`. |
| 8 | Baseten | ✅ | ashby | `baseten` | 200 OK posting-api, 672kb. |
| 9 | Figure (AI) | ✅ | greenhouse | `figureai` | **Important:** GH `figure` slug is a different company (Figure lending — Chief Credit Officer etc). `figureai` returns the humanoid-robotics jobs (Whole Body Control, etc). |
| 10 | Anduril | ✅ | greenhouse | `andurilindustries` | 200 OK boards-api (1.7MB, 1866 jobs). Tried `anduril`, `andurilindustries`, `anduril-industries`. |
| 11 | Shield AI | ✅ | lever | `shieldai` | Lever returned 3.5MB JSON. (GH `shield` returned 200 but is a different company; not used.) |
| 12 | Skydio | ✅ | ashby | `skydio` | 200 OK posting-api, 1.5MB. |

## Workday probe
None of the unfound companies' careers pages exposed `*.myworkdayjobs.com` URLs (checked Ironclad, EvenUp, Hippocratic AI, Character.AI, Anysphere). Character.AI explicitly proxies through Ashby (`ashbyhq.com/character`). No Workday entries to add.

## Why some Ashby boards 404 on posting-api
Several companies (Ironclad, EvenUp, Hippocratic, Anysphere) host public Ashby job boards under `jobs.ashbyhq.com/{slug}` but the corresponding `api.ashbyhq.com/posting-api/job-board/{slug}` endpoint returns 404 — those orgs have disabled the public posting-api or use a different `jobBoardName`. The render-time GraphQL endpoint (`/api/non-user-graphql`) requires an organization-scoped POST and is not stable for our crawler. Recommendation: either implement an Ashby Playwright/HTML scraper, or contact-form approach for these specifically.

## Summary
- **Added:** 8 companies (Character.AI, CoreWeave, Lambda, Baseten, Figure, Anduril, Shield AI, Skydio)
- **Skipped:** 4 (Anysphere = duplicate of Cursor; Ironclad/EvenUp/Hippocratic AI = Ashby private posting-api)
- **Total companies in yaml:** 267 (was 259)
- **Backup:** `companies.yaml.bak.add-ai-2026-05-07-0141`
- Probes used: ~70, well under budget.
- Cyrus's Monday cron will pick up the new entries automatically.
