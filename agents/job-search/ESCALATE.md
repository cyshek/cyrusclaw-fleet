# ESCALATE.md (workspace root) — pointer

**2026-05-27 09:58 PDT — linkedin_authed_resolver subagent.**

Active escalation: see [ESCALATE-linkedin-authed-resolver.md](ESCALATE-linkedin-authed-resolver.md) — LinkedIn auth (`li_at` cookie) is missing on every browser profile on this VM, blocking the 121-row LinkedIn-stranded queue. Resolver code + tests shipped; live sweep waiting on Cyrus to provision auth (Option A / B / C in the linked doc).

---

## ⚠️ Self-reported mistake (filed in the same turn as fix)

I (the linkedin_authed_resolver subagent) **overwrote a prior `ESCALATE.md` at this path** when I first wrote my linkedin-auth escalation. The previous file was ~10KB and dated 2026-05-27 00:41 PDT — most likely the in-flight Filestack / Option-A escalation context from earlier today (see `STATUS-filestack.md`, `STATUS-filestack-opta.md`, `FILESTACK-DESIGN.md`, `OPTION-A-DESIGN.md` for the related state). The file was untracked in git so I cannot diff or restore it.

Fix:
- Moved my new escalation to `ESCALATE-linkedin-authed-resolver.md` (topic-specific filename).
- This file is now a pointer + apology.
- AGENTS.md guidance: from now on, before any agent writes to workspace-root `ESCALATE.md`, **read it first** and either append-with-divider or pick a topic-specific filename like `ESCALATE-<topic>.md`. I'm noting this in MEMORY.md too.

If the prior contents matter to Cyrus, the most likely recovery vectors are:
1. The originating subagent's session transcript (it should have the full text it wrote).
2. The STATUS-filestack*.md files which were written around the same time and likely cover the same context.
