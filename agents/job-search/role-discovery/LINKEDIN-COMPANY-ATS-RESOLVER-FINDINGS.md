# LinkedIn company→ATS resolver — run summary (2026-06-10)

Script: `role-discovery/linkedin_company_ats_resolver.py` (committed `0cbfb5e`)
Report: `role-discovery/linkedin_resolve_report.json`
DB backup before --apply: `tracker.db.bak.linkedin-resolve-20260610-070930`

## Result (out of 100 stranded LinkedIn rows)
| Bucket | Count |
|---|---|
| RESOLVED (real ATS URL, written back, status='') | **1** |
| BLOCKLISTED_SKIP (Microsoft — Cyrus handles) | 1 |
| BOARD_BUT_NO_TITLE_MATCH | 15 |
| NO_BOARD_MATCH | 83 (81 distinct cos) |

**Applied:** 1 row changed (id 2543 TikTok), integrity_check ok before+after.
- id 2543 TikTok "TikTok Shop - Angel Oncall Program Manager" (EXACT title+loc match)
  - OLD `linkedin.com/jobs/view/4423272858/`
  - NEW `https://lifeattiktok.com/position/7645414641002989829/detail`
  - status manual-apply → '' (back in actionable queue). Stranded 100→99.

## Why only 1 (honest diagnosis)
The strict matcher PREVENTED DB corruption. A first pass with a loose substring
rule produced 4 FALSE matches (e.g. "Product Manager I, AI/ML" → bare "Product
Manager"; "Technical Program Manager" → "Principal Lead TPM - Windows…"). Fixed
to: normalized-exact OR Jaccard≥0.7 + a shared distinctive (non-generic) token.

Several name-MATCHED companies are actually **name COLLISIONS** with a different
company on our board — correctly rejected at title stage:
- "Valence" → companies.yaml `valencelabs` = a Montréal biology lab (not the SE-AI Valence)
- "Gamma Reality Inc." → `gamma` = an AI-slides startup (all SWE roles)
- "Epic" → `epicgames` = Epic Games (the stranded SE role is almost certainly Epic **Systems**, healthcare)
- "EMAG Group" → `emag` = eMAG (Romanian e-commerce); stranded Farmington-MI role is EMAG LLC (German machine tools)
JP Morgan / Cisco Workday configs return 422/404 (stale host/site) → 0 postings.

## ⚠️ KEY FINDING — this overlaps an EXISTING pipeline stage
`weekly_run.sh` ALREADY runs three LinkedIn→ATS resolvers after the crawl:
- 3a0 `linkedin_db_crosslink_resolver.py` (zero-HTTP, copies sibling-row ATS URL)
- 3a  `linkedin_resolver_pipeline.py` (companies.yaml → JD scrape → careers probe)
- 3a2 `linkedin_stranded_brute_resolver.py` (probes company board APIs + difflib fuzzy)

My script is functionally a **duplicate of 3a2**. These 100 rows survived 3a2
because 3a2 selects `status IN ('','blocked')` AND `agent_notes NOT LIKE
'%LINKEDIN-BRUTE%'` — these are `status='manual-apply'` AND already tagged
LINKEDIN-BRUTE (the residue 3a2 gave up on). My win (TikTok) came because 3a2's
prebuilt `_linkedin_stranded_ats_map.json` is STALE/incomplete: only 23 companies,
17 UNKNOWN, and MISSING TikTok/Airbnb/Nintendo/Fanatics/Valence even though those
have working adapters in companies.yaml. My resolver reads companies.yaml directly.

## STEP 2 — residual NO_BOARD_MATCH (what the ~$0.50 search key unlocks)
81 distinct companies. Split:
- **A) Staffing/recruiting/consulting (~22)** — LinkedIn post points to a CLIENT
  role, no single own-ATS; a search key likely WON'T help (dead ends):
  AceStack, adly, Alignerr, Archon Resources, Averro, Canopy, CapTech, CHAMP,
  Cindavi, Dartronics, Dexian, Flowtec Group, Hashlist, Iceberg, ProActivate,
  ReachMobi, Rise Technical, Synectics, Tailored Management, Topa Group,
  Triverus Consulting, VeeAR Projects.
- **B) REAL companies not in companies.yaml (~59)** — the search key (#16, Serper/
  Brave) from company+title → real careers/ATS URL WOULD unlock these:
  Alibaba Cloud, Apex Fintech, Atlas Copco, AvtechTyee, Boeing, ChargeAfter,
  Checkmarx, Chromalox, Copeland, Docusign, Dorner, Eaton, EDMO, ELLWOOD,
  Expedia Group, Fives, Gates Foundation, GEICO, Geiger Pump, hackajob, Harvard
  Business School, HAVI, Haystack, Hilti NA, InvestCloud, ITRS, Kaiser Permanente,
  Kastle Systems, Kidde, Mayo Clinic, Meta, NeuReality, Nexthermal, Nordstrom,
  Paramount+, PEAK6, Perpetual, Productboard, R.F. MacDonald, Ryerson, Sager
  Electronics, Softchoice, Spot AI, Sécheron, Teachers FCU, Teradata, The
  Associated Press, Thea Energy, TikTok USDS JV, Tradeweb, TrueLearn, Uniguest,
  Univ. of Washington, UST, VIAVI, Vsimple, Weir Minerals, Well, World Wide Tech.
  (Several — Meta, Nordstrom, Docusign, Expedia, Boeing, Tradeweb, Productboard —
  are BIG cos absent from companies.yaml; adding them as adapters is an
  alternative to the search key for those.)

## STEP 3 — pipeline integration recommendation
DO **NOT** add a 4th overlapping stage. Instead, the cheap high-leverage fix is to
**repair the EXISTING 3a2 path**, not bolt mine on:
1. **Fix `_phase1_build_ats_map.py` to read companies.yaml** (it currently emits a
   23-company, mostly-UNKNOWN map missing TikTok/Airbnb/Nintendo/etc. that have
   working adapters). A complete map is what made 3a2 miss TikTok.
2. **Widen 3a2's selection** to also re-attempt `status='manual-apply'` rows once,
   OR drop the `agent_notes NOT LIKE '%LINKEDIN-BRUTE%'` exclusion on a periodic
   re-sweep, so previously-failed rows get re-checked against a fixed map.
3. My `linkedin_company_ats_resolver.py` can serve as the **reference
   implementation** (correct strict matcher + companies.yaml-direct + blocklist +
   manual-apply handling + per-company timeout) to fold those fixes into 3a2 — or
   replace 3a2 with it. Either way it should run inside weekly_run.sh, not as a
   one-off, so future LinkedIn-stranded rows auto-resolve from their company board.

Bottom line: Recovered 1 stranded LinkedIn row to a real ATS URL (TikTok, back in
the queue) with zero token; the company-board approach is genuinely capped low
here (81/100 cos aren't on our boards + several name-collisions), and the real
recurring win is fixing the STALE map in the existing 3a2 stage, not a new script.
59 residual real companies need the ~$0.50 search key (or new adapters).
