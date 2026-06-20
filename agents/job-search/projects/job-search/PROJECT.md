# Project: Job Search

**Owner:** Cyrus Shekari
**Status:** Active
**Goal:** Land a great new role.

## What this project is

This is the canonical home for everything related to Cyrus's active job search.
Resume, target company list, per-company research, application drafts, and the
status tracker all live here. Treat this folder as the source of truth.

## Layout

```
projects/job-search/
├── PROJECT.md              ← you are here
├── resume/
│   ├── Cyrus_Shekari_Resume.pdf ← MASTER RESUME — use this as the base
│   └── README.md           ← notes on resume versions / tailoring
├── companies.md            ← target company list (~110 companies)
├── research/               ← one file per company: openings, hiring contacts, notes
│   └── <Company>.md
├── applications/           ← one file per application: tailored resume notes,
│   └── <Company>.md            cover letter draft, status, links
└── tracker.md              ← single-page status board across all companies
```

When you create a per-company file, mirror the company name from `companies.md`
exactly (kebab-case the filename if it has spaces — e.g. `Jane Street` →
`research/jane-street.md`).

## Your job (main agent)

1. **Read the master resume.** Start with `resume/Cyrus_Shekari_Resume.pdf`. Build
   a mental model of Cyrus's strengths, experience, and target roles. Note
   anything ambiguous in `resume/README.md` and ask Cyrus when convenient.
2. **Triage the company list.** Group `companies.md` into clusters (Big Tech,
   AI labs, quant/HFT, fintech, energy, consulting, etc.). Suggest a sensible
   order to attack — probably the highest-fit clusters first.
3. **Per company, work the loop:**
   - Find current openings that match Cyrus's profile (use the browser/web
     search tools; check the company careers page directly).
   - Capture findings in `research/<Company>.md`: relevant role(s), JD link,
     team contacts if findable, application portal link, deadline.
   - Draft a tailored bullet sheet + cover letter in
     `applications/<Company>.md`. **Do not invent experience.** Pull only
     from the actual resume.
   - Update `tracker.md` with the row's status.
4. **Spawn agents as useful.** You're free to create dedicated isolated agents
   via `openclaw agents add` if it helps (e.g. a `job-research` agent that
   only does company research, separate from your main session). The choice
   is yours — don't create agents for the sake of it, but don't be shy
   either.

## Hard rules

- **Never submit an application without explicit approval from Cyrus.**
  Drafting, tailoring, queuing — all fine. Hitting "Submit" on a careers
  portal, sending an email to a recruiter, posting on LinkedIn — these
  require a thumbs-up first. (This matches the workspace red lines:
  "Anything that leaves the machine — ask first.")
- **Never fabricate experience, dates, titles, or projects.** The resume is
  ground truth. If a role asks for something Cyrus doesn't have, say so in
  the application file rather than embellishing.
- **Don't email or message anyone (recruiters, referrers) without approval.**
- Keep credentials/personal data out of any file that could leave the
  machine.

## Cadence

- During heartbeats, you may quietly do background work on this project:
  refresh research for a stale company, check for new openings, polish a
  draft. Log what you did in the daily memory file.
- At most once per day, surface a short status update to Cyrus
  ("3 new openings at Stripe / Anthropic / SpaceX matching your profile —
  want me to draft applications?"). Don't spam.
- If you discover something time-sensitive (a deadline within 48h, a
  warm-intro opportunity), surface it sooner.

## Tracker

`tracker.md` is the single status pane. Update it whenever a company moves
between states. Keep it scannable.

## When the resume changes

If Cyrus drops a new resume version, save it to `resume/` with the
filename Cyrus used (don't overwrite `Cyrus_Shekari_Resume.pdf`), update
`resume/README.md` to point at the new master, and re-tailor any drafts
that are still in queue.
