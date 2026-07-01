BUILD BRIEF — YipitData APM guide rebuild (NEW format)

GOAL: Rebuild guides/yipitdata-apm/YipitData_APM_Interview_Prep_Guide.docx on the corrected
canonical template, then rebuild the zip. Preserve styling (black headings).

WORKSPACE: /home/azureuser/.openclaw/agents/interview-prep/workspace
CANONICAL TEMPLATE (build ON this, copy then edit in place — NEVER python-docx from scratch):
  templates/Master_Interview_Prep_Guide.docx  (149 paras; headings BLACK; theme intact)
REFERENCE BUILDER (proven pattern — copy its structure exactly):
  build_src/build_google.py
EXISTING SECTION-6 SOURCE CONTENT (substance to preserve, reformat to new style):
  build_src/yipit_section6.txt

INTERVIEW FACTS (locked):
- YipitData — "Associate Product Manager" (APM), Metrics & Feeds / Public Investor team.
- Recruiter screen with Lorena Gallo (Recruiting Associate). Thu Jul 2, 9:00–9:45 AM PDT, ZOOM
  (https://yipitdata.zoom.us/j/88196594782). 30–45 min. YipitData sent a detailed prep brief; the
  existing Section 6 maps 1:1 to it — preserve that mapping.
- It's a fit + motivation + resume-walkthrough screen (more substantive than pure logistics, but NOT
  a technical/case grilling).
- ⚠️ RESUME TITLE FRAMING: on the resume YipitData has, Cyrus's roles are framed Product Manager /
  Technical Product Manager (internships = "Product Manager Intern"), NOT "TPM". He must walk through
  his resume with THAT product/data-platform framing consistently. Keep this note in the guide.
- Work auth: role offers NO visa sponsorship (US-remote, HQ NYC). Cyrus is US citizen, no sponsorship
  needed — clean answer.
- Honest growth edge: JD wants SQL + Databricks + PySpark. Don't overclaim — candor + hunger to grow.

WHAT TO BUILD (mirror build_google.py exactly):
1. Copy template -> guide path. Backup current guide to /tmp first.
2. Fill Company block ([COMPANY...]) and Role block ([ROLE...]) placeholders, bold-label + plain text:
   - Company block: YipitData = leading alt-data market-research/analytics firm for the disruptive
     economy; raised $475M from Carlyle at $1B+ valuation; top funds + Fortune 500 make high-stakes
     decisions on their data, so DATA QUALITY IS THE PRODUCT. Why: that precision bar is exactly where
     Cyrus does his best work, and the push into AI-powered + programmatic delivery makes it the right
     moment to join.
   - Role block: APM on Metrics & Feeds (Public Investor team) = own metrics publishing quality +
     standards, partner cross-functionally (Data/Eng/Product), scale platform workflows ingestion→
     delivery, leverage AI tools. Why it fits: Cyrus scaled a 0→1 data-validation platform, defined
     metrics standards, drove cross-functional adoption, and has LIVED AI-tool automation — which is
     this role almost verbatim. (Frame with product/data-platform language, not program-management.)
3. Append role-specific section titled:
   "Recruiter Screen Game Plan — Lorena Gallo (Thu Jul 2, 9:00 AM PDT, Zoom)"
   Heading 3 "Say-it-ready answers (bold topic, then the exact line)" — bold-topic + EXACT spoken line
   (quotes) for at least:
   - Walk me through your background / resume (60–90s arc, PRODUCT framing: Amazon Robotics PM intern
     → Microsoft internships ×2 → full-time owning a 0→1 data-validation platform + AI automation)
   - Why YipitData / SpendHound (data IS the product + precision bar + AI-delivery moment)
   - Why leaving Microsoft (want to go deeper on data PRODUCTS; at MSFT data is a means to an end;
     YipitData treats data AS the product — honest + positive, ~30s, never criticize MSFT)
   - What skillset you bring (metrics/feeds quality + cross-functional + platform workflows + AI fluency)
   - SQL / Databricks / PySpark honesty (solid data-platform exp + named Databricks as enterprise
     partner; excited to deepen — candor, no overclaim)
   - Work authorization (US citizen, no sponsorship needed)
   Then Heading 3 sections (bullets) reformatting existing Section-6 substance:
   - "Resume walkthrough — transition points" (the product-framing note + one-line WHY per transition)
   - "Your skillset → the JD" — bullets mapping metrics-quality / cross-functional / platform-workflows
     / AI-agent (39% planning cut, RAG 83% lookup cut) / honest SQL-Databricks growth edge.
   - "Behavioral stories to lead with" — Service Healing/recovery-validation (ownership 0→1), proactive
     resilience 94% (ambiguity/structure), sovereign-cloud $1.5B (cross-functional influence), Power BI
     toil dashboard 140+ teams OR 28%-faster launches (data-driven decision). Bullets, all REUSED, none
     fabricated.
   - "Questions to ask Lorena" — 5 bullets (reuse existing).
   - "Logistics & mindset" — time mgmt (30–45 min, concise+specific), Zoom rules (don't join >5 min
     early; wait 1–3 min if locked out; charged/lit/eye-level/quiet), tone (warm, advocate, thank by
     name, confirm next steps). Bullets.

FORMAT RULES (LOCKED — Cyrus is strict):
- Say-it-ready answers = `**Bold Topic:** "Exact spoken line."` ONLY. No sub-bullets, no scaffolding.
  Bold label is its OWN run, ends with ":".
- NO italic helper/instruction lines anywhere.
- Headings BLACK (copy corrected template; do NOT rebuild from scratch — that regresses to blue).
- Bullets via the same approach as build_google.py.

VERIFY (must all pass, print results):
- 0 placeholders remaining ("[COMPANY", "[ROLE", "[Fill").
- Every say-it topic line: p.runs[0].bold == True AND ends with ":".
- Key facts present: "Lorena", "$475M", "data IS the product" (or "data as the product"),
  "US citizen", "Databricks".
- Headings black. Render to PDF via soffice; confirm pages built.
REBUILD ZIP: guides/yipitdata-apm.zip = guide docx + YipitData_APM_JD.md +
  Cyrus_Shekari_Resume_yipitdata_7892101_v2.pdf. Use python zipfile (NO zip binary).

TOOLING GOTCHAS (CRITICAL):
- heredocs AND write/edit tools literalize \n inside f-strings -> SyntaxError. Write real .py files
  with multi-line bodies on separate physical lines (cat <<'PYEOF' with logic on separate lines, or
  printf '%s\n' line-by-line). Put script in build_src/build_yipit.py.
- python-docx, soffice, pdftoppm, pdfinfo, pdftotext available. NO zip binary.

REPORT BACK (one tight paragraph): files written, para count, verify results, zip contents, judgment calls.
