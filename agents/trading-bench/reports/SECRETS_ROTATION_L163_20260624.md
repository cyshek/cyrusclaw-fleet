# SECRETS ROTATION — L163 closed (Discord-free key-drop pattern)

**Date:** 2026-06-24 (PT)
**Item:** BACKLOG L163 — "Migrate secrets out of Discord channel for future key drops."
**Scope guardrails honored:** no runner/strategy/GATE/protected-file edits; no live trades touched; killswitch untouched.

## Why this existed
The original Alpaca key drop pasted the keys into the `#trading-bench` Discord channel, exposing
them in channel history (MEMORY.md: "Alpaca keys in Discord = exposed; write to `.env`, ask Cyrus
to regenerate"). The at-rest storage was already fine; the unsolved gap was the **intake channel**
for the *next* rotation. Discord/chat is not a secrets transport.

## Current state assessed (healthy at rest)
- **Secrets:** workspace `.env` holds `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `APCA_API_BASE_URL`,
  `APCA_API_DATA_URL`, `FRED_API_KEY`. (Gateway/bot secrets live separately in
  `/home/azureuser/.openclaw/.env` — Discord token, proxies, etc. — out of scope, left untouched.)
- **Perms:** `.env` = `600`, workspace dir = `700`, `.openclaw` = `700`. Owner-only throughout.
- **Git:** not a repo; `.gitignore` already excluded `.env`/`.env.*` (allowing `.env.example`).
- **Loaders:** `broker_alpaca.py` / `fred_cache.py` / `cme_fedwatch.py` / `polymarket_scanner.py`
  all use a no-overwrite reader (`if k not in os.environ`) that strips quotes. **No code logs secret
  values** (`broker_alpaca` is explicit: "never logs secrets"). Broker hard-refuses any non-paper host.
- **Verdict:** storage solid; only the rotation *workflow* needed a durable, Discord-free path.

## What was built
1. **`scripts/rotate_secret.sh`** — the designated secure intake. Three modes, value NEVER passed as a
   CLI arg (would leak into `ps`/history):
   - `--file [PATH]` — ingest a `KEY=VALUE` file Cyrus scp/sftp'd into the gitignored `700`
     `.secrets_drop/` dir, then **shred** it. Handles quoted values + spaces around `=`, merges only
     the changed keys.
   - `--key NAME` — hidden TTY prompt (`read -s`), not echoed, not in shell history.
   - `--key NAME --from-env` — read from a var Cyrus already exported in his own shell.
   Every path: backs up the prior `.env` → `memory/env_backup_<ts>.env` (600), writes `.env`
   **atomically** (temp + rename, replace-or-append, preserves other keys), re-asserts `600`, then
   auto-runs verification.
2. **`scripts/verify_secrets.py`** — post-rotation sanity: Alpaca config parses, paper-host enforced,
   key/secret/FRED **lengths only** (no values), lists key names present. Exit non-zero if Alpaca fails.
3. **`.secrets_drop/`** — `700` landing zone for Mode-1 drops (gitignored; drop files shredded after ingest).
4. **`.gitignore` hardened** — added `.secrets_drop/`, `.secrets_drop/**`, `memory/env_backup_*.env`
   so a future `git init` can never track a secret or a backup.
5. **`SECRETS.md`** — the durable procedure doc (what exists, where, the rotate steps, what NOT to do).

## Testing
- **Sandbox end-to-end** (throwaway temp dir, real `.env` never touched):
  - File-drop: rotated 2 keys, preserved others, backed up, shredded drop file, verified. ✅
  - `--from-env`: rotated FRED key from an exported var, value never on cmdline. ✅
  - Rejected a lowercase/malformed key; refuses value-as-arg. ✅
  - `.env` perms stayed `600` across operations. ✅
- **Live, read-only** `verify_secrets.py` against the real `.env`: parses clean, Alpaca key_id 26 /
  secret 44 (correct Alpaca paper shape), paper-host enforced, FRED 32-char. No values printed.

## Operating rule going forward
Next time Alpaca/FRED keys rotate: **do not paste into chat.** Use `scripts/rotate_secret.sh`
(`--file` preferred). If a key was ever exposed in chat, regenerate it in the provider console first
(kills the leaked value), then rotate the new one through the script.

## Files
- `scripts/rotate_secret.sh`, `scripts/verify_secrets.py`, `SECRETS.md`, `.gitignore` (updated),
  `.secrets_drop/` (new, 700).
