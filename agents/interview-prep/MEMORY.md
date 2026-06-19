# MEMORY.md — interview-prep, durable notes

_Keep this LIGHT. Durable preferences + decisions Cyrus gives you. Prune stale stuff. This is not
a logbook — daily working notes go in `memory/YYYY-MM-DD.md`._

## Origin (2026-06-08)
- Created as a permanent agent at Cyrus's request. Core job: take his **Master Interview Prep
  Guide** (`templates/`), make per-company copies, and fill the `[Fill in here]` spots (Q2 why-this-
  company, Q3 know-the-role/company).
- **SCOPE (current, per Cyrus 2026-06-09 scope-down):** a bundle is **ONLY the two surgical Q2/Q3
  fills + nothing else.** Do NOT append company-specific questions / a "Section 5" / extra
  behavioral/technical/interviewer Qs. The master's own Sections 1–4 are the whole body; I only
  fill the two blanks. (Earlier framing about "adding questions" is superseded — story-sourcing
  rule in AGENTS.md is dormant by default.)
- **Cyrus's #1 standing instruction: HE owns the rules and structure.** Stay light, don't bolt on
  rigid process, shape behavior conversationally with him. This overrides any reflex to add heavy
  machinery.
- Truthful bio/STAR facts always; company-"why" framing may be enthusiastic/inferred.
- Reads job-search's master resume READ-ONLY; never writes other agents' state; single writer of
  own per-company guides only.
- Built by job-search (workspace seed) + main (registration/channel). main owns fleet config.

## Durable technique (distilled from 06-08/06-09 bundles)
- **LEAN-SCOPE BUILD = the standard.** Per bundle: copy BOTH `templates/Master_Interview_Prep_Guide.docx` AND `templates/Shorter_Master_Interview_Prep_Guide.docx` — always from `templates/` (these are the canonical sources, updated 2026-06-17 to include Section 4: Product Thinking + Section 5: Questions for the Interviewer in the master, and Section 3: Product Thinking in the shorter). Never copy from a stale backup or a per-company guide.
  fill Q2+Q3 in the full master copy first, then paste **identical answers** verbatim into the shorter copy.
  Use in-place XML clone-bullet patch (NOT pandoc regenerate). Each of Q2/Q3 = 2 plain bullets, inline-labeled
  (e.g. "**What [Company] does:** …" / "**Why I want this role:** …"), no new sub-headers.
  **Q2/Q3 TONE (updated 2026-06-17):** name the company + role title, show basic homework, keep general and natural — NOT laser-targeted deep dives. "I know what you do and why it fits" not domain-expert-level specificity. Keep it concise: no more than a few sentences per bullet.
  Bundle = 4 files: full guide copy + shorter guide copy + JD + resume.
  ALWAYS verify after: 0 placeholders left, all stories intact, fonts preserved, both docs open clean.
- **TOOLING GOTCHA (recurring, cost me time twice):** heredoc `python3 - <<'PY'` AND the write-tool
  BOTH literalize `\n` inside f-strings / `with` lines → SyntaxError. Fix: write real `.py` files
  with normal multi-line bodies, no inline `\n`. Also: **no `zip` binary on this host** → zip via
  python `zipfile`.
- **Find the RIGHT artifacts, don't assume.** Per-role resumes/JDs live read-only under job-search
  (`projects/job-search/applications/...`). Match by company+role (e.g. New Relic was a *specific*
  PM·Log Management seat, not a generic PM). If no tailored resume exists for a role, bundle the
  master resume and FLAG the gap to Cyrus. If posting/resume can't be found → STOP and ask.

## Nightly auto-scan pipeline (live as of 2026-06-14)
- **Cron:** `interview-prep-nightly-scan` (id `e19d7712`), 2am PST daily, isolated.
- **Pipeline:** `pipeline/nightly_scan.py` → Gmail IMAP scan → dedup (`seen_signals.json`) → tracker.db lookup → Discord notify.
- **Gmail:** `cyshekari@gmail.com`, app password in scanner. Tested working.
- **Google Calendar:** WIRED (2026-06-14). iCal feed URL: `https://calendar.google.com/calendar/ical/cyshekari%40gmail.com/private-3620dae5cb533b6290296e4bce814b22/basic.ics`. `calendar_scanner.py` parses VEVENT blocks, detects interview keywords, looks 14 days ahead.
- **Notify-first:** script pings Cyrus on #interview-agent; he replies `build [company]` to trigger bundle. (Auto-build timer not wired yet — manual confirm for now.)
- **Tracker lookup:** reads job-search's `tracker.db` read-only; matches by company fuzzy + role hint + most-recent tiebreaker per job-search's spec.
- **Interviews table ownership (2026-06-14):** interview-prep owns WRITES to `tracker.db → interviews` table. `roles` table is read-only. On each new signal: insert row (company, role, jd_url, applied_on, interview_type, interview_date) → re-render XLSX via `role-discovery/render_xlsx.py` → post updated XLSX to #job-search. Module: `pipeline/interviews_tracker.py`. Dedup by company+interview_date (no double-inserts).

## ⚠️ FORMATTING GATE — Q2/Q3 bullets MUST have a BOLD inline label (don't let this regress again)
- Each Q2/Q3 bullet leads with an inline label ending in a colon ("**Why do I want to work at X:**",
  "**Why do I want this role:**", "**What does X do:**", "**What is this role:**"). That label MUST be
  its **own bold run**, with the rest of the bullet plain. This is the visual cue that separates the
  TWO bundled questions inside each of Q2/Q3 — Cyrus explicitly cares about it.
- **Regression history (2026-06-11):** the 06-10 builder (`_build_two_bundles.py` old `set_text()`)
  emitted one flat un-bold run per bullet → Mintlify + Podium shipped WITHOUT bold labels while
  New Relic/Datadog had them. Fixed in-place + rebuilt both zips + patched the builder to auto-split
  the label into a bold run. **Verification gate now: after any build, confirm `p.runs[0].bold` is
  True with a colon in it for all 4 Q2/Q3 bullets** (not just "placeholders gone"). A built guide
  with flat Q2/Q3 labels is a FAILED build even if the text is right.
- Also: when a guide docx is re-edited, the **delivered .zip may still hold the OLD docx** — rebuild
  the zip too, and verify the corrected docx is the one INSIDE it.
