# Fleet github-copilot auth — how it works & how to keep it un-fragile

_Investigated & verified 2026-06-10 (maintenance subagent). No gateway restart, no deletions._

## TL;DR
- Each agent reads its model credential from its **own** `agents/<id>/agent/auth-profiles.json`.
  These are **independent copies**, not a shared file. All 8 currently hold the same
  `github-copilot:github` profile (a `mode:token` `ghu_` GitHub OAuth token) and **all 8 resolve it**
  (verified: `openclaw models auth list --agent <id>` → `github-copilot:github [github-copilot/token]`).
- **Do NOT symlink** the auth files to main's. Proven unsafe from source.
- The credential is **long-lived and stable** (auth-profiles.json hasn't been rewritten since the
  Jun 8 paste even though the provider is "refreshable"), so the copies rarely go stale.
- When the `ghu_` token **is** re-issued, re-auth main once then run **`bin/sync-copilot-auth.sh`**
  to fan it out to every peer safely (backs up each peer's file first; never touches auth-state.json).

## Why symlinks are the WRONG fix (don't re-derive this)
The OpenClaw atomic JSON store (`/usr/lib/node_modules/openclaw/dist/json-files-*.js`):
- **Reads** auth files with `O_NOFOLLOW` → it refuses to follow a symlink at the auth path.
- **Writes** via `tmp` file + `renameSync`, and `renameJsonFileWithFallback` explicitly detects a
  symlink target and `rmSync`s it before renaming.
So a symlinked `auth-profiles.json` would be rejected on read and/or destroyed on first write.
Official guidance (`dist/io-*.js`): _"If you want to share credentials, copy auth-profiles.json
instead of sharing the entire agentDir."_ → **copy, don't link.**

## Why auth-state.json must stay per-agent
`agents/<id>/agent/auth-state.json` is **runtime state**, not credentials: per-agent `lastUsed`,
`errorCount`, `lastFailureAt`, cooldowns. It is rewritten per agent on every use. Sharing it would
cause write contention and cross-agent cooldown bleed. `sync-copilot-auth.sh` never touches it.

## The properly-shared mechanism (sanctioned migration, NOT applied tonight)
github-copilot supports resolving its token from an **env var** and storing a `tokenRef` instead of a
literal token (verified in `dist/extensions/github-copilot/index.js`; env vars, in order:
`COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`). With that, every agent's profile becomes:
```json
{ "type":"token","provider":"github-copilot",
  "tokenRef": { "source":"env", "provider":"env", "id":"COPILOT_GITHUB_TOKEN" } }
```
and the **one** real token lives in `/home/azureuser/.openclaw/.env` (already gateway-loaded).
Refresh once → propagates fleet-wide on next read, no per-file copies at all.

**Why it was NOT done tonight:** converting all 8 *currently-working* agents to tokenRef-env is an
invasive change to a healthy auth path with fleet-wide blast radius if env injection into isolated
cron sessions isn't guaranteed. Per the "don't disrupt in-flight work" rule it was deferred as a
deliberate CHOICE (not a "can't"). **Assumption that, if it breaks, flips this decision:** if the
`ghu_` token starts rotating frequently (so hand-sync becomes a chore) OR a peer auth-fails because
its copy went stale, migrate to tokenRef-env using:
```
# put token in .env first:  COPILOT_GITHUB_TOKEN=ghu_...
for a in main job-search making-money trading-bench travel openclaw-updates resume-tailor interview-prep; do
  openclaw models auth paste-token --provider github-copilot --profile-id github-copilot:github \
    --agent "$a" --secret-input-mode ref   # resolves from COPILOT_GITHUB_TOKEN env, stores tokenRef
done
```
(Verify each agent still resolves the profile afterward; keep .bak copies until confirmed.)

## Quick ops
- Check all 8 resolve:  `for a in main job-search making-money trading-bench travel openclaw-updates resume-tailor interview-prep; do echo -n "$a: "; openclaw models auth list --agent "$a" | grep copilot; done`
- Re-sync after a token refresh:  `bin/sync-copilot-auth.sh --dry-run` then `bin/sync-copilot-auth.sh`
