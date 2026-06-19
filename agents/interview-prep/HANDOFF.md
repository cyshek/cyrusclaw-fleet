# HANDOFF.md - interview-prep

_Updated 2026-06-17 during fleet hygiene pass._

## Mission

Build lean interview-prep bundles for Cyrus when an interview lands. Use the master guide templates in `templates/`, copy the relevant guide files, and fill only the Q2/Q3 `[Fill in here]` sections by default.

The current scope is intentionally narrow:

- Fill Q2: why this company / why this role.
- Fill Q3: what the company does / what the role is.
- Include the JD and the resume artifact used for that role.
- Preserve Cyrus's existing stories, sections, formatting, and guide structure.

Do not add extra company-specific question sections, coaching sections, behavioral stories, or technical/interviewer questions unless Cyrus explicitly asks for that in the current request.

## Current state

- Active mode: on-demand bundle builder plus notify-first interview signal scanner.
- Default bundle output: full guide copy, shorter guide copy, JD, resume, and zip/package as needed.
- Nightly scan pipeline is live and notify-first; Cyrus confirms before build.
- Blockers: none known.

## Standing approvals and policies

- Auto-run without asking: read job-search artifacts read-only, copy templates into this workspace, fill Q2/Q3, verify document formatting, package bundle outputs.
- Ask first: anything leaving the VM, modifying another agent's state, or expanding scope beyond the lean Q2/Q3 bundle.
- Truthful bio/STAR facts always. Company/role motivation can be enthusiastic and inferred from public/company research.
- Only `main` deletes agents; route deletion requests to `main`.

## Key locations

- Workspace: `/home/azureuser/.openclaw/agents/interview-prep/workspace/`
- Templates: `templates/`
- Per-company outputs: `guides/<company-role>/`
- Daily notes: `memory/YYYY-MM-DD.md`
- Durable memory: `MEMORY.md`
- Pipeline: `pipeline/nightly_scan.py`, `pipeline/gmail_scanner.py`, `pipeline/calendar_scanner.py`, `pipeline/interviews_tracker.py`

## Verification gate for every bundle

- No `[Fill in here]` placeholders remain in the delivered copies.
- Q2/Q3 each have the expected two inline-labeled bullets.
- Bold inline labels are preserved as bold runs.
- Existing stories and guide sections are intact.
- Both document copies open cleanly.
- If a zip is delivered, verify the corrected docs are inside the zip.
