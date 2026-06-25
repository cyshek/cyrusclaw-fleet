# SECRETS.md — Credential handling & rotation (trading-bench)

> **The one rule:** secret *values* NEVER go through Discord or any chat channel. Chat history
> is searchable and persistent — a pasted key is a leaked key. Use the secure paths below.
> (This doc closes BACKLOG **L163**. Tooling: `scripts/rotate_secret.sh` + `scripts/verify_secrets.py`.)

## What secrets exist & where they live

| Secret | File | Consumed by | Notes |
|---|---|---|---|
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | workspace `.env` | `runner/broker_alpaca.py` | **Paper** Alpaca. Broker hard-refuses any non-`paper-api.alpaca.markets` host. |
| `APCA_API_BASE_URL` / `APCA_API_DATA_URL` | workspace `.env` | `runner/broker_alpaca.py` | Endpoints, not secrets, but live alongside keys. |
| `FRED_API_KEY` | workspace `.env` | `runner/fred_cache.py`, `runner/polymarket_scanner.py`, `runner/cme_fedwatch.py` | Free FRED key. 32-char lowercase hex. |

- The workspace `.env` is the **single source of truth** for trading-bench credentials.
- Gateway/bot-level secrets (Discord token, proxies, etc.) live separately in
  `/home/azureuser/.openclaw/.env` and are **out of scope** for this workspace — do not move
  trading keys there or vice-versa.

## At-rest posture (verified 2026-06-24)

- `.env` — `600` (owner read/write only), inside a `700` workspace dir, under a `700` `.openclaw`.
- `.gitignore` already excludes `.env`, `.env.*`, `.secrets_drop/`, and `memory/env_backup_*.env`
  (allows only `.env.example`). The workspace is not currently a git repo, but the ignores are
  pre-armed so a future `git init` can never track a secret.
- Loaders use a no-overwrite reader (`if k not in os.environ`) and strip quotes; **nothing logs
  secret values** (`broker_alpaca` explicitly: "never logs secrets").

## How to rotate a key (the secure procedure)

When Alpaca or FRED keys are regenerated, pick ONE intake mode. **Never** send the value in chat,
and **never** pass it as a command-line argument (it leaks into `ps` + shell history).

### Mode 1 — File drop (preferred, best for multiple keys at once)
Cyrus copies a small `KEY=VALUE` file to the secure, gitignored, `700` drop dir over an encrypted
transport (scp/sftp/`tmux` paste into a root shell — anything but chat):

```
# on Cyrus's side, write a temp file then:
scp newkeys.env  azureuser@<vm>:/home/azureuser/.openclaw/agents/trading-bench/workspace/.secrets_drop/incoming.env
```
`newkeys.env` contents (only the keys that changed):
```
APCA_API_KEY_ID=<new id>
APCA_API_SECRET_KEY=<new secret>
```
Then the agent (or Cyrus) runs:
```
scripts/rotate_secret.sh --file
```
This backs up the old `.env` to `memory/env_backup_<ts>.env` (600), merges the new keys into `.env`
atomically (replace-or-append, preserves other keys + 600 perms), **shreds** the drop file, and runs
verification. Nothing is echoed.

### Mode 2 — Hidden terminal prompt (one key, interactive)
On a real TTY (ssh session), no transport needed:
```
scripts/rotate_secret.sh --key APCA_API_SECRET_KEY
# → "Paste new value for APCA_API_SECRET_KEY (hidden, will not echo):"  (read -s; not in history)
```

### Mode 3 — Env-inline (one key, from Cyrus's already-exported shell var)
```
export FRED_API_KEY=...            # in Cyrus's shell; value never on the rotate cmdline
scripts/rotate_secret.sh --key FRED_API_KEY --from-env
```

### After any rotation
- The script auto-runs `scripts/verify_secrets.py` (parse check, paper-host enforced, lengths only).
- For a real Alpaca auth ping: `python3 -m runner.broker_alpaca`.
- If a key was **leaked** (e.g. previously pasted in chat), treat the old one as compromised:
  regenerate in the Alpaca/FRED console so the exposed value is dead, then rotate the new one here.
  (Paper-key rotation-on-leak is otherwise waived per MEMORY.md, but regenerating kills the exposed
  value — cheap and correct.)

## What NOT to do
- ❌ Paste a key into Discord / webchat / any channel (the original L163 incident).
- ❌ `scripts/rotate_secret.sh APCA_API_SECRET_KEY <value>` — values as args leak; the script refuses.
- ❌ `echo KEY=val >> .env` by hand — bypasses backup/atomicity/perms; use the script.
- ❌ Commit `.env`, `.secrets_drop/*`, or `memory/env_backup_*` (already gitignored — keep it that way).
- ❌ Move trading keys into the gateway `.env`, or gateway secrets into the workspace `.env`.

## Files
- `scripts/rotate_secret.sh` — secure intake (file / hidden-TTY / env-inline), atomic `.env` update, backup, shred, verify.
- `scripts/verify_secrets.py` — post-rotation sanity (no values printed).
- `.secrets_drop/` — `700` landing zone for Mode-1 file drops (gitignored; files shredded after ingest).
- `memory/env_backup_<ts>.env` — `600` timestamped backups of the prior `.env`.
