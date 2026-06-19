# Auto-commit: How Agents Should Push to the Fleet Repo

The `bin/git-commit-push.sh` script is the single entry-point all agents should use when they want to record changes in `cyrusclaw-fleet`. It handles staging, author attribution, "nothing to commit" gracefully, and the push.

## Basic usage

```bash
/home/azureuser/.openclaw/workspace/cyrusclaw-fleet/bin/git-commit-push.sh "feat: describe what changed"
```

## Commit as a specific agent

Pass `--agent <name>` to tag the commit with an `openclaw-<name>` author identity. This makes the git log readable at a glance — you can see which agent made each commit.

```bash
/home/azureuser/.openclaw/workspace/cyrusclaw-fleet/bin/git-commit-push.sh \
  --agent making-money \
  "feat: add live-copilot outreach scripts"
```

The commit will be authored by **`openclaw-making-money <openclaw@cyrusclaw-fleet>`**.

## Dry-run (preview only)

Add `--dry-run` to stage and show a diff without committing or pushing. Useful for verifying what will be included before you commit.

```bash
/home/azureuser/.openclaw/workspace/cyrusclaw-fleet/bin/git-commit-push.sh \
  --agent travel \
  --dry-run \
  "chore: sync trip plans"
```

## Combining flags

Order doesn't matter; the message is any positional argument that isn't a flag.

```bash
# All equivalent:
bin/git-commit-push.sh --agent resume-tailor --dry-run "fix: update templates"
bin/git-commit-push.sh --dry-run --agent resume-tailor "fix: update templates"
```

## Graceful no-op

If there are no staged changes the script exits `0` cleanly with a message — safe to call from crons or heartbeats without crashing on clean trees.

## Recommended commit message conventions

| Prefix   | When to use                                  |
|----------|----------------------------------------------|
| `feat:`  | New script, new feature, new output file     |
| `fix:`   | Bug fix in existing code                     |
| `chore:` | Housekeeping, sync, refactor (no behaviour change) |
| `docs:`  | Documentation or markdown only               |
| `data:`  | Data/JSON output updates                     |

## Where agents should copy their files

Each agent has a dedicated directory under `agents/`:

```
agents/
  making-money/   ← /home/azureuser/.openclaw/agents/making-money/workspace/
  resume-tailor/  ← /home/azureuser/.openclaw/agents/resume-tailor/workspace/
  travel/         ← /home/azureuser/.openclaw/agents/travel/workspace/
  job-search/     ← /home/azureuser/.openclaw/agents/job-search/workspace/
  interview-prep/ ← /home/azureuser/.openclaw/agents/interview-prep/workspace/
  ...
```

Copy code files (`*.py`, `*.sh`, `*.yaml`, docs) into the matching `agents/<name>/` subdirectory, **excluding** private files:

- `MEMORY.md`, `HANDOFF.md`, `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`
- `*.db` (databases)
- Credential files, `.env`, tokens

Then run the script to commit and push.

## Example agent cron / heartbeat snippet

```bash
# Copy latest py files and commit
rsync -a --include="*.py" --include="*.sh" --exclude="*" \
  /home/azureuser/.openclaw/agents/making-money/workspace/ \
  /home/azureuser/.openclaw/workspace/cyrusclaw-fleet/agents/making-money/

/home/azureuser/.openclaw/workspace/cyrusclaw-fleet/bin/git-commit-push.sh \
  --agent making-money \
  "chore: sync workspace $(date +%Y-%m-%d)"
```
