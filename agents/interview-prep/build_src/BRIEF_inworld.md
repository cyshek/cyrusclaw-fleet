BUILD BRIEF — Inworld AI Founding SE guide rebuild (NEW format)

GOAL: Rebuild guides/inworld-ai-founding-se/Inworld_AI_Founding_SE_Interview_Prep_Guide.docx
on the corrected canonical template, then rebuild the zip. Preserve styling (black headings).

WORKSPACE: /home/azureuser/.openclaw/agents/interview-prep/workspace
CANONICAL TEMPLATE (build ON this, copy then edit in place — NEVER python-docx from scratch):
  templates/Master_Interview_Prep_Guide.docx  (149 paras; headings BLACK #000; theme intact)
REFERENCE BUILDER (proven pattern — copy its structure exactly):
  build_src/build_google.py
EXISTING SECTION-6 SOURCE CONTENT (substance to preserve, reformat to new style):
  build_src/inworld_section6.txt

INTERVIEW FACTS (locked):
- Inworld AI — "Founding AI Solutions Engineer" — HM screen with Florin Radu (COO).
- Wed Jul 1, 2:00–2:30 PM PDT, Google Meet (meet.google.com/vsa-ztai-fvi). Recruiter: Sadia Fatima.
- This is the DEEP one: SE seat asking 5+ yrs customer-facing + strong Python. Cyrus is a TPM —
  honest stretch. Strategy = sell the intersection (eng/product/stakeholder seam), the hands-on
  building (AI agent on GitHub Copilot, full drill lifecycle), the ambiguity fit (0→1 resilience).
  Be truthful about the SE-years/Python stretch; never inflate. "Truthful + hungry beats inflated."
- Cyrus is in Kirkland WA; JD requires SF Bay Area / South Bay onsite a few days a week — RELOCATION
  is a real question here (unlike Google). Handle honestly: he must decide his stance; in the guide
  give a HONEST location line he can adapt, do NOT fabricate that he's local (he is NOT local to Bay).
  Default spoken line: frame willingness/openness to relocate for the right role IF that's plausible,
  but flag in the guide text that Cyrus must confirm his true relocation stance. Do not invent.
- US citizen, no sponsorship needed (true, reuse).

WHAT TO BUILD (mirror build_google.py exactly):
1. Copy template -> guide path. Backup current guide to /tmp first.
2. Fill the Company block placeholder ([COMPANY...]) and Role block placeholder ([ROLE...]) with
   bold-label + plain spoken text:
   - Company block: Inworld AI = research lab building the world's #1-ranked realtime voice models
     (TTS/STT/LLM Router/Realtime API), powering 100s of millions of users (NVIDIA, Xbox, Niantic),
     $125M+ raised. Why: it's a frontier voice-AI company at the exact 0→1 build phase where Cyrus
     adds the most value, and he wants to be the technical backbone of a revenue team at that seam.
   - Role block: Founding AI Solutions Engineer = the technical backbone of the revenue team at the
     intersection of sales/product/eng — runs technical discovery, POCs, prototypes, owns the
     technical side of deals pre/post-signature, gets customers to production. Why it fits: Cyrus
     lives at the eng/product/stakeholder seam, has run discovery+onboarding+adoption with internal
     "customers," and builds working tools (the Copilot AI agent). Be HONEST that it's a stretch on
     SE years; lead with the intersection + building + ambiguity.
3. Append a role-specific section titled:
   "Round 1 Game Plan — Florin Radu, COO (Wed Jul 1, 2:00 PM PDT, Google Meet)"
   Then a Heading 3 "Say-it-ready answers (bold topic, then the exact line)" with bold-topic +
   EXACT spoken line (in quotes) for at least:
   - Walk me through your background (45s SE-angled: eng/product/stakeholder seam + building)
   - Why Inworld / why this role (intersection + frontier voice AI + build phase)
   - The honest SE-stretch reframe (own the TPM→SE gap, sell the intersection + internal-customers)
   - Hands-on coding / Python (truthful level + anchor on the Copilot AI agent he actually built)
   - Location / relocation (HONEST — Cyrus is in Kirkland, role is Bay Area onsite; give an adaptable
     line AND a bracketed note telling Cyrus to confirm his true stance — do NOT claim he's local)
   - Work authorization (US citizen, no sponsorship)
   - Why leaving Microsoft (0→1 matured to steady-state; he adds most value in the build phase)
   Then Heading 3 sections (bullets) reformatting the existing Section-6 substance:
   - "Inworld product & company cheat sheet (know cold)" — the 6 products, why they win, who buys,
     traction/backing, technical vocab (latency, streaming WebSocket/WebRTC, on-prem/edge, routing,
     quantization, OpenAI-compatible APIs). Each as a tight bullet.
   - "Your stories → what Florin screens for" — map Service Healing data-loss pivot (go deep w/o
     backup), GDOT/discovery (discovery+POC), sovereign-cloud $1.5B (bridge tech+exec), frustrated
     tier-one team (customer empathy), AI agent (can build not just coordinate). Bullets.
   - "Questions to ask Florin (COO lens)" — 5 bullets (reuse existing).
   - "Mindset" — match founder energy, show product curiosity (he tried the Realtime API), be honest
     about the stretch + confident on trajectory, close with intent. Bullets.

FORMAT RULES (LOCKED — Cyrus is strict):
- Say-it-ready answers = `**Bold Topic:** "Exact spoken line."` ONLY. No sub-bullets, no
  "lead with / show homework / don't" scaffolding under them. Bold label is its OWN run, ends with ":".
- NO italic helper/instruction lines anywhere.
- Headings must render BLACK (they will, since you copy the corrected template — do NOT rebuild from
  scratch with python-docx default styles, that regresses to blue).
- Bullets: use the same add-bullet approach as build_google.py.

VERIFY (must all pass, print results):
- 0 placeholders remaining ("[COMPANY", "[ROLE", "[Fill").
- Every say-it topic line: p.runs[0].bold == True AND text ends with ":".
- Key facts present: "Florin", "Realtime API", "GitHub Copilot", "US citizen", "Service Healing".
- Headings black (spot check: no blue). Render to PDF via soffice; confirm pages built.
REBUILD ZIP: guides/inworld-ai-founding-se.zip = guide docx + Inworld_Founding_SE_JD.md +
  Cyrus_Shekari_Resume_ashby-inworld-ai_9aef36c8_v2.pdf. Use python zipfile (NO zip binary on host).

TOOLING GOTCHAS (CRITICAL):
- heredocs AND write/edit tools literalize \n inside f-strings -> SyntaxError. Write real .py files
  with multi-line bodies on genuinely separate physical lines. Proven pattern: cat <<'PYEOF' with
  logic on separate lines, or build the script with printf '%s\n' line-by-line.
- Put your build script in build_src/build_inworld.py.
- python-docx, soffice/libreoffice, pdftoppm, pdfinfo, pdftotext available. NO zip binary.

REPORT BACK (one tight paragraph): files written, para count, verify results (placeholders/bold/
facts/pages), zip contents, and any judgment calls (esp. the relocation line wording).
