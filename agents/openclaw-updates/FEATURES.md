# FEATURES.md — openclaw-updates

OpenClaw **runtime / core-product** feature requests this agent is tracking (not per-agent config hacks).
Routed here because openclaw-updates owns the gateway/runtime surface for Cyrus's VM.

ID scheme: `OCFR-NNN` (OpenClaw Feature Request, zero-padded, monotonic). Never reuse a retired number.

Status values: `Filed` → `Acknowledged upstream` → `In progress` → `Shipped` / `Declined` / `Superseded`.

---

## OCFR-001 — Post-turn / session-end "memory-capture hook"

- **Status:** Filed
- **Filed:** 2026-06-08
- **Requested by:** Cyrus (approved 2026-06-08), routed via `main` (`agent:main:main`)
- **Area:** Runtime lifecycle hooks / memory subsystem
- **Upstream issue:** _(none yet — local-only until escalated to github.com/openclaw/openclaw)_

### Problem / motivation
Fleet-wide "log to memory after each interaction" (LOG-EVERY-INTERACTION) is enforced ONLY by
policy + agent discipline — a banner in every agent's AGENTS.md telling it to append to
`memory/YYYY-MM-DD.md` live before ending the turn. There is **no runtime mechanism** that
guarantees it. Confirmed on disk 2026-06-08: zero per-turn/session-end hooks exist (no
`hook`/`postTurn`/`sessionEnd`/`autoLog` in config); the only memory crons are nightly/weekly
DISTILL jobs that promote what's already on disk — they don't capture new conversation. If an
agent skips logging, nothing catches it.

Cyrus's core pain: agents pull STALE context when he returns the next day, because the live
interaction never got written down. He wants capture machine-guaranteed, not discipline-dependent.

### Why a cron can NOT solve this (design constraint)
An isolated/agentTurn cron fires a fresh run with NO access to the originating session's live
transcript — so a "every N min, log the conversation" cron would no-op or hallucinate content it
can't see. The ONLY thing holding the conversation is the live turn itself. Therefore the capture
step MUST run in-turn / at end-of-turn, with access to that turn's transcript. Hence: runtime hook,
not scheduled job.

### The ask (core)
A runtime lifecycle hook that fires at end-of-turn (and/or session-end) WITH access to that turn's
transcript/messages, so a capture step can automatically append a durable note to the agent's
`memory/YYYY-MM-DD.md`. Conceptually a "post-turn hook" the runtime invokes after the agent's turn
completes, passing (or exposing) the turn's content, where a handler summarizes + appends to the
daily memory file.

### Nice-to-haves
- Opt-in / configurable per agent (config flag), not forced globally.
- Configurable handler (built-in "summarize this turn → append to memory/YYYY-MM-DD.md" default,
  with override).
- Companion assertion/verification: "did a log line actually get written for this turn?" — and
  optionally warn if an agent went N turns with real work but no daily-log write.
- Cheap/bounded: shouldn't add a heavy model call to every trivial turn; ideally only fires when the
  turn did real work, or batches.

### Acceptance criteria (rough)
- With the hook enabled on an agent, a substantive turn results in an automatic append to
  `memory/YYYY-MM-DD.md` without the agent having to remember.
- Trivial/NO_REPLY turns don't spam the log.
- Works in-turn (has transcript access); does not rely on an isolated run.

### Context / linkage
- Reconciliation that produced this: `main` + `job-search` verified 2026-06-08 that logging is
  policy+discipline-only, no per-turn machinery. Both agents' `memory/2026-06-08.md` record it.
- Stopgap already in motion (NOT this request, FYI to avoid dup): `job-search` is building an
  isolated staleness-WATCHDOG cron that only checks daily-log file mtime and pings if logging goes
  stale during active hours — deliberately does NOT capture content (avoids the
  isolated-can't-see-transcript trap). Band-aid; THIS feature is the real fix.
- Tracking only — not to be built/shipped today unless assessed trivial.

### Notes / log
- 2026-06-08 — Filed from `main` routing on Cyrus's behalf. Reference handed back: **OCFR-001**.
