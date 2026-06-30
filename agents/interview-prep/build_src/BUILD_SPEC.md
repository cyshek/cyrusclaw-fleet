# BUILD SPEC — New Master Guide structure + Datadog rebuild
Locked with Cyrus 2026-06-29. You are building docx files for an interview-prep bundle.

## Source files (read these for exact wording — DO NOT invent or alter facts/numbers)
- `build_src/master_full.txt` — current master guide, full text (prose stories live here; you will CONVERT them).
- `build_src/structural_bullets.txt` — Cyrus's preferred "Structural Study Guide" bulleted story format (3 projects). THIS is the model for the new story cards. Use its bullets as the authoritative story content.
- Current canonical template: `templates/Master_Interview_Prep_Guide.docx` (already backed up — do NOT touch the .bak files).

## Environment gotchas (from our memory — obey)
- python-docx is installed. NO `zip` binary — zip via python `zipfile`.
- Heredocs/inline f-strings literalize `\n` → SyntaxError. WRITE A REAL `.py` FILE with genuine multi-line bodies (use a text editor / file write, logic on separate physical lines). Run it with `python3 build_new_master.py`.
- Bold runs: every label must be ITS OWN bold run (so `p.runs[0].bold == True`), rest of the paragraph plain.

## TASK 1 — Build new canonical master template → overwrite `templates/Master_Interview_Prep_Guide.docx`
Structure, in order:
1. **Title** "Master Interview Prep Guide" (Heading 1) + one italic "How to use this guide" line: Section 1 = spoken openers (speak, don't recite); Section 2 = story bank as study cards, rehearse from bullets, hit 4 beats and stop; role cheat sheet at end (added per role) = drill morning-of, say each term aloud.
2. **Section 2 heading: "Section 1: Core Questions"** (Heading 2). Under it:
   - Q1 (Heading 3) "Tell me about yourself / Walk me through your background" — KEEP the existing Q1 script prose verbatim from master_full.txt (the "I'm currently a Technical Program Manager..." multi-paragraph answer). Precede with a bold "Script:" line.
   - Q2 (Heading 3) "Q2: The Company — what it is and why you want to be there". One italic helper line: "Say it as ONE spoken answer (what the company is, then why you want in). Filled per role." Then ONE paragraph that is a placeholder: bold run `[COMPANY — what + why]:` followed by plain text `[Fill per role: one-breath answer — what the company is/does, then the specific reason you want to be there. Show basic homework; keep it natural, not a deep-dive recitation.]`
   - Q3 (Heading 3) "Q3: The Role — what it is and why you want it". Italic helper: "Say it as ONE spoken answer (what the role is, then why it's the right next step). Filled per role." Then placeholder paragraph: bold run `[ROLE — what + why]:` + plain `[Fill per role: one-breath answer — what the role actually does day-to-day, then why it's the intersection where you do your best work.]`
   - Q4 (Heading 3) "Q4: Why are you looking to leave Microsoft?" — KEEP existing Q4 script prose verbatim from master_full.txt, preceded by bold "Script:".
   NOTE: the OLD Q2 (what company does / why role) and OLD Q3 (what role is / what company is) are REPLACED by the consolidated Q2 Company / Q3 Role above. Do not keep the old redundant versions.
3. **Section heading "Section 2: Behavioral Story Bank (Study Cards)"** (Heading 2) + italic line: "Rehearse from the bullets — each card is a fact skeleton, not a script. Hit the labeled beats in order and stop. Map any behavioral question to the closest card."
   - Convert the 3 projects in `structural_bullets.txt` into 3 study cards. For EACH card:
     - Heading 3 title (use a clear name + parenthetical of what it maps to), e.g.:
       - "Card 1 — Proactive Resilience Testing Program (0→1, disagreement & pivot)"
       - "Card 2 — GDOT Platform Integration & User Adoption (influence w/o authority)"
       - "Card 3 — Resilience Automation Platform / Self-Service Intake (trade-offs & scale)"
     - One italic "Maps to:" line listing the behavioral Qs it covers. Derive these from the OLD Section 2 prose Qs in master_full.txt (Q1 ambiguous, Q2 disagreement, Q3 didn't-go-as-planned, Q4 automate manual process, Q5 trade-off, Q6 influence w/o authority, Q7 frustrated customer). Card1≈Q1+Q2+complex-issue; Card2≈Q3+Q6+Q7+frustrated-customer+primary-technical-contact; Card3≈Q4+Q5+product-strategy.
     - Phase bullets using `List Bullet` style. Each PHASE LABEL is its own bullet with a bold-run label and NO trailing body (e.g. a bullet whose only run is bold "Situation:"), followed by individual plain bullets for each fact. Phases per card come from structural_bullets.txt headings (Situation / Disagreement & Pivot / Roadblock / Tension & Trade-off / Action Taken / Result). Keep ALL the factual bullets (the <20% Human Investigate rule, Service Healing, 94%/15-of-16, 11 operators, 6 hours→6 minutes, 35%, 45 drills/year, RBAC, node-to-service mapping, etc.). You may lightly tighten wording but keep every number and named system.
4. **Section 3** (Heading 2 "Section 3: Managing Senior / Executive Requests") — KEEP verbatim from master_full.txt (the bullet list of trigger questions + the 3-principle script with De-escalate/Evaluate/Propose). For the three sub-steps, make each step LABEL ("De-escalate and Diagnose:", "Evaluate the Trade-offs:", "Propose a Scoped Solution:") its own bold run at the start of the paragraph, rest plain.
5. **Section 4** (Heading 2 "Section 4: Product Thinking Questions") — KEEP verbatim from master_full.txt: Q1 product vision, Q2 product strategy (make each of the 5 components' lead-in its own bold-run label), Q3 metrics. Preserve all numbers.
6. **Section 5** (Heading 2 "Section 5: Questions for the Interviewer") — KEEP verbatim from master_full.txt (bold "Script:" then the 5 questions as bullets).

Base font Calibri 11. Use real Heading 1/2/3 styles and `List Bullet` for bullets.

## TASK 2 — Rebuild the Datadog bundle on top of the NEW template
Reuse/adapt `bundles/datadog-partner-tse/build_bundle.py` (it has working `clear_paragraph` + bold-label helpers + zip logic). The Datadog-specific content to fill/append (pull exact text from the EXISTING built guide `bundles/datadog-partner-tse/Datadog_Partner_TSE_Interview_Prep_Guide.docx` so nothing is lost):
- Fill Q2 Company block (spoken-ready): Datadog = leading cloud observability platform (metrics, logs, traces, security in one place); why = won the observability consolidation war, integration ecosystem is the growth engine, want to be at that edge.
- Fill Q3 Role block (spoken-ready): Partner TSE = primary technical contact for third-party devs building integrations on the IDP — guide architecture, code reviews vs the Quality Rubric, troubleshoot, surface friction back to product; why = exact intersection of technical depth + external impact where I do my best work.
- Append the existing **Round 1 — Pulkit Chandra** section AND the **Datadog observability cheat sheet**, BUT reformat the cheat sheet into the new bold-term + spoken-aloud style: each entry = a paragraph whose first run is a bold term label ending in colon (e.g. bold "OpenTelemetry (OTEL):") followed by a PLAIN spoken-aloud one-liner you could say in the room. Cover at minimum: Metrics, Logs, Traces/APM, OpenTelemetry/OTEL, Datadog Agent (agent-based vs API-based — make the contrast explicit and crisp), Integration Developer Platform (IDP) / Marketplace, OAuth. Keep the theme-by-theme Round-1 prep + "Questions to ask Pulkit" + Mindset note.
Output: overwrite `bundles/datadog-partner-tse/Datadog_Partner_TSE_Interview_Prep_Guide.docx` and rebuild `bundles/datadog-partner-tse/Datadog_Partner_TSE_PrepBundle.zip` (zip must contain the NEW docx + JD.md + the resume PDF — preserve whatever JD/resume the current zip has).

## VERIFICATION (must pass before reporting done)
Write + run a checker that prints:
- Template: 0 occurrences of the literal "[Fill" placeholders REMAIN? (template SHOULD still have them; Datadog guide should NOT.)
- Datadog guide: confirm `[COMPANY` and `[ROLE` and "[Fill" placeholders are GONE (replaced).
- Datadog guide: for the cheat-sheet entries and the Company/Role blocks, confirm the first run of each is bold and ends with ":" (print PASS/FAIL per check).
- Confirm both docx open cleanly via Document() and report paragraph counts.
- Confirm the zip namelist contains the docx + a JD + a resume.
Report back a SHORT receipt: files written, paragraph counts, all checks PASS/FAIL, and any deviation. Do NOT paste full doc text back.
