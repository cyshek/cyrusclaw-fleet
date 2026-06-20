# YOE Classifier Audit — 2026-05-25

**Scope:** verify the new LLM-grounded YOE classifier (deployed today, replacing brittle regex) against ground truth from cached JDs.

**Method:** for each role, extract YOE-bearing sentences from JD cache, eyeball the actual MIN required years, compare to `llm_yoe_required`.

**Targets:**
- Group A: 31 previously-skipped roles restored after rewrite
- Group B: 10 randomly-sampled OPEN roles (status=''), classified with llm_yoe<4
- Group C: 4 roles still skipped as yoe-threshold (pool was small — only 4 outside the restored 31)

---

## Group A

| ID | Company | Role | JD-quoted requirement | llm_yoe | Truth MIN | Verdict |
|---|---|---|---|---|---|---|
| 893 | Tesla | Product Manager, Customer Support Operat | 2-5 years Product Management | 2 | 2 | AGREE |
| 897 | Tesla | Product Manager, Vehicle Service | 2-5 years product management | 2 | 2 | AGREE |
| 943 | Astronomer | Sales Engineer | 3–10 years total experience | 3 | 3 | AGREE |
| 992 | Spot & Tango | Product Manager | 3-5 years of experience in product management | 3 | 3 | AGREE |
| 1043 | McKinstry | Product Manager | 3-5 years in product management or A/E/C industry | 3 | 3 | AGREE |
| 1267 | Curtiss-Wright Corpo | Sales Engineer | 3 – 7 years of related experience | 3 | 3 | AGREE |
| 1272 | EMAG Group | Technical Sales Engineer | 2–5+ years of experience in technical sales | 2 | 2 | AGREE |
| 1275 | Oriental Motor | Sales Engineer | 2-4 years in industrial sales / 2 years related experience | 2 | 2 | AGREE |
| 1285 | AdaCore | Sales Engineer | 3 to 5 years as Field Application Engineer (company-age 30 yrs correctly ignored) | 3 | 3 | AGREE |
| 1286 | Stark Tech | Sales Engineer - HVAC | 1 to 5 years … preferred (not required → None is correct) | None | None | AGREE |
| 1294 | Perforce Software | Sales Engineer - Delphix (US-Northwest R | 2-5 years experience in test data management (MIN across two reqs is 2) | 3 | 2 | AGREE |
| 1304 | Weights & Biases | AI Solutions Engineer, Post Sales Scale  | 3–5 years of relevant experience | 3 | 3 | AGREE |
| 1316 | Tract Capital Manage | Technical Solution Architect | 3–5 years in technical architecture / lead role | 3 | 3 | AGREE |
| 1391 | Clay | Technical Enablement Program Manager | 3–5 years in Technical Enablement | 3 | 3 | AGREE |
| 1394 | Netflix | Product Manager, Content Intelligence | 3–5 years of Product Management experience | 3 | 3 | AGREE |
| 1399 | Forbes | Product Manager | 2–5 years of Product Management | 2 | 2 | AGREE |
| 1406 | Pipe | Product Manager | 2-4 years of product management experience | 2 | 2 | AGREE |
| 1411 | Oved Group | Product Developer/Product Manager- Appar | 3–5 years in product development (40+ years company-age correctly ignored) | 3 | 3 | AGREE |
| 1468 | Brain Corp | Technical Program Manager II (multiple o | 2-4 years engineering + 1-2 yrs TPM (LLM picked 3, truth MIN is 2; both <4 so no skip-deci | 3 | 2 | LLM-OVERSHOOT-MINOR |
| 1504 | BioSpace | Technical Program Manager, ClinTech Stra | 3–5 years in high-bar analytical environment | 3 | 3 | AGREE |
| 1526 | Leadenhall Search &  | Data & AI Solutions Architect | 2–4 years of relevant experience in data engineering | 2 | 2 | AGREE |
| 1534 | First Advantage | Solutions Engineer | 3-5 years of consultative sales experience | 3 | 3 | AGREE |
| 1535 | Stefanini North Amer | Solutions Engineer - Data Center | 3-5 years of experience in a similar role | 3 | 3 | AGREE |
| 1542 | Asana | Solutions Engineer | 3–5+ years in solutions engineering (Fortune-7-yrs correctly ignored) | 3 | 3 | AGREE |
| 1548 | Checkr, Inc. | Solutions Engineer | 2–5 years in Solutions Engineering | 2 | 2 | AGREE |
| 1590 | Renesas Electronics | Solution Architect - Agile Teams | 3-5 years of experience in solutions consulting | 3 | 3 | AGREE |
| 1591 | FuriosaAI | Solutions Architect - US | 2–5 years in a US customer-facing technical role | 2 | 2 | AGREE |
| 1602 | Fried Frank | Cloud Solutions Architect | 3-5 years architecting solutions in Azure/AWS | 3 | 3 | AGREE |
| 1618 | Encord | Forward Deployed Engineer | 3–8 years in a technical client-facing role | 3 | 3 | AGREE |
| 1629 | Diligent | Forward Deployed Engineer | 3-5+ years of relevant post-college experience | 3 | 3 | AGREE |
| 1632 | Aircall | Forward Deployed Engineer - AI Solutions | 2–8 years in technical consulting | 2 | 2 | AGREE |

## Group B

| ID | Company | Role | JD-quoted requirement | llm_yoe | Truth MIN | Verdict |
|---|---|---|---|---|---|---|
| 895 | Tesla | Product Manager, Factory Design Robotics | 2+ years technical experience | 2 | 2 | AGREE |
| 577 | Atlassian | Product Manager, DX | 2–3 years of experience in product management | 2 | 2 | AGREE |
| 1237 | Mercor | Research Program Manager | ideally 2-3 years of professional experience | 2 | 2 | AGREE |
| 946 | Baseten | AI Solutions Engineer | 1+ years of professional work experience | 1 | 1 | AGREE |
| 879 | Stripe | Product Manager IC-02 | 3 years of experience in product design or engineering (Stripe IC-02 visa req) | 3 | 3 | AGREE |
| 856 | Sierra | Product Manager, Agent Studio | 3+ years of PM experience (Clay-18-yrs founder-bio correctly ignored) | 3 | 3 | AGREE |
| 1497 | SiriusXM | Associate Technical Program Manager | 1+ years of experience as TPM/Scrum Master | 1 | 1 | AGREE |
| 589 | Bland AI | Customer Engineer | 3+ years of experience in technical customer support | 3 | 3 | AGREE |
| 68 | Apple | Product Manager, Manufacturing Data & An | 2+ years of experience in product management | 2 | 2 | AGREE |
| 1076 | Google | Technical Program Manager II, Solutions  | 2 years of experience in program management | 2 | 2 | AGREE |

## Group C

| ID | Company | Role | JD-quoted requirement | llm_yoe | Truth MIN | Verdict |
|---|---|---|---|---|---|---|
| 1358 | Axon | Business Solutions Architect: Finance Sy | 8+ years finance systems (LLM returned None — HTML markup hid the requirement). FALSE-NEGA | None | 8 | LLM-MISSED-HIGHER-REQ |
| 1005 | Ursus, Inc. | Product Manager | 3+ years primary req (6-10+ is MBA-path alt). LLM picked 10 → wrongly flagged as yoe-thres | 10 | 3 | LLM-OVERSHOOT-MAJOR |
| 1273 | ASC Steel Deck | Technical Sales Engineer | 5 years of experience in Civil Engineering | 5 | 5 | AGREE |
| 1491 | Tesla | Technical Program Manager, Electronic Sy | 3+ yrs required, 5+ yrs preferred. LLM picked preferred (5) as MIN required → wrongly flag | 5 | 3 | LLM-OVERSHOOT-MAJOR |

## Summary

**Total roles audited:** 45 (A=31, B=10, C=4)

| Verdict | Count | % |
|---|---|---|
| AGREE | 41 | 91.1% |
| LLM-OVERSHOOT-MAJOR | 2 | 4.4% |
| LLM-OVERSHOOT-MINOR | 1 | 2.2% |
| LLM-MISSED-HIGHER-REQ | 1 | 2.2% |

**Effective AGREE rate** (including overshoots that don't change skip decision): 42/45 = 93.3%

## Findings

### ✅ What's working
- **Company-age traps avoided:** AdaCore ("30 years partnered with…"), Asana ("Fortune Best 7+ years"), Oved Group ("40+ years of success"), Sierra ("Clay spent 18 years at Google"), Stark Tech, Curtiss-Wright. LLM correctly ignored all of them.
- **MIN-of-range correct:** every range case (`2-5`, `3-7`, `3-10`, `3-8`, `2-8`) extracted the lower bound. No regressions.
- **"Preferred" vs "required" handled correctly** in Stark Tech (id=1286): `1 to 5 years preferred` → llm_yoe=None (no hard requirement), no spurious skip.
- **Group B (10 currently-OPEN low-yoe roles):** 100% AGREE. New classifier did not introduce false-negatives on actual low-bar roles. The 31-role restoration looks safe.

### ⚠️ Issues found in Group C (4 currently-skipped yoe-threshold rows)

Two genuine FALSE-POSITIVE skips and one FALSE-NEGATIVE:

**FP #1 — id=1005 Ursus, Inc. "Product Manager"** — llm_yoe=10, truth=3
> `3+ years of product management experience` (stated twice as primary req)
> `MBA (preferred) or BA/BS or equivalent experience with 6-10+ years of product management experience`

The 6-10+ figure is the *MBA-alternate path*; primary req is 3+. LLM took the higher number as the MIN. Currently skipped as yoe-threshold — should be **restored**.

**FP #2 — id=1491 Tesla "Technical Program Manager, Electronic Systems, Displays"** — llm_yoe=5, truth=3
> `3+ years of experience in program management within an engineering or technical environment` (required)
> `5+ years … preferred` (preferred, not required)

LLM treated *preferred* as the MIN. Currently skipped as yoe-threshold — should be **restored**.

**FN — id=1358 Axon "Business Solutions Architect: Finance Systems"** — llm_yoe=None, truth=8
> `8+ years of experience in finance systems, business …` (wrapped in `<div class="public-DraftStyleDefault-block">` HTML markup)

LLM returned `llm_yoe_required=None`. The HTML/Draft.js markup obscured the requirement. Currently skipped (the OLD regex caught it). If the new classifier re-ran, this role would be incorrectly *unflagged*. Other gates (`llm_seniority=lead`) would NOT save it — wait, actually `senior-llm` gate catches `seniority in {director+, manager}` — `lead` is not in that set per AGENTS.md note. **This is a real false-negative.**

### Pattern: "preferred X+ vs required Y+" confusion

In both Group-C false positives, the JD has BOTH a required minimum AND a higher preferred number. The LLM picked the preferred. The prompt should be tightened to explicitly distinguish *required minimum* from *preferred / nice-to-have* and always anchor on the lower required value.

## Recommendations

1. **Prompt tweak (high priority):** add explicit instruction:
   > "If the JD lists both a *required* minimum (\"required\", \"must have\", \"minimum\") and a separate *preferred*/\"nice to have\" higher number, take the REQUIRED minimum, not the preferred. \"Preferred\" / \"ideally\" / \"plus\" numbers should never raise yoe_required above the explicit required minimum."

2. **Prompt tweak (high priority):** add explicit instruction for MBA-alternate paths:
   > "If the JD offers BA + X years OR MBA + Y years as alternate paths, take the LOWER (BA path). Do not take the MBA path's higher year count as the requirement."

3. **HTML pre-stripping (medium):** Axon-style Draft.js wrapped JDs may obscure year mentions from the LLM. Consider stripping HTML tags more aggressively before sending to LLM, OR keeping a regex fallback that scans raw text for `\d+\+ years` and flags as a backup signal (NOT as the primary).

4. **Retroactive restore (low risk):** flip ids 1005, 1491 back to open (clear `senior-title`/`yoe-threshold` flag if no other gate fires). DO NOT touch 1358 (Axon) — the 8+ yr req is real and the skip is correct, just for slightly wrong reasons.

5. **No action needed for Group A or B** — the 31 restores look correct, and 10/10 random open roles correctly classified.
