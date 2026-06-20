#!/usr/bin/env bash
# sync-agents.sh — copy each agent's workspace into the monorepo, then commit+push
# Safe to run multiple times; skips if nothing changed.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_SRC="/home/azureuser/.openclaw/agents"
AGENTS_DEST="$REPO_DIR/agents"

AGENTS=(
  interview-prep
  job-search
  making-money
  openclaw-updates
  resume-tailor
  trading-bench
  travel
)

echo "[sync-agents] Starting sync at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Sync main's workspace (the repo root itself, minus the monorepo)
MAIN_SRC="/home/azureuser/.openclaw/workspace"
MAIN_DEST="$AGENTS_DEST/main"
mkdir -p "$MAIN_DEST"
rsync -a --delete \
  --exclude='.env' \
  --exclude='*.env' \
  --exclude='.env.*' \
  --exclude='personal-info.json' \
  --exclude='auth-profiles.json' \
  --exclude='auth-state.json' \
  --exclude='*.pdf' \
  --exclude='*.docx' \
  --exclude='tracker.db' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='MEMORY.md' \
  --exclude='MEMORY.md.*' \
  --exclude='HANDOFF.md' \
  --exclude='AGENTS.md' \
  --exclude='AGENTS.md.*' \
  --exclude='SOUL.md' \
  --exclude='IDENTITY.md' \
  --exclude='USER.md' \
  --exclude='TOOLS.md' \
  --exclude='HEARTBEAT.md' \
  --exclude='*.bak*' \
  --exclude='memory/' \
  --exclude='tmp/' \
  --exclude='.tmp/' \
  --exclude='.openclaw/' \
  --exclude='.git/' \
  --exclude='cyrusclaw-fleet/' \
  --exclude='sessions.json' \
  --exclude='*.jsonl' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='env/' \
  --exclude='.DS_Store' \
  --exclude='BACKLOG.md' \
  --exclude='BOOTSTRAP.md' \
  --exclude='GATE.md' \
  --exclude='grind-brief.txt' \
  --exclude='*cookies*' \
  --exclude='*.txt' \
  --exclude='resume_text.txt' \
  --exclude='Cyrus_*' \
  --exclude='state/' \
  --exclude='spotify/' \
  --exclude='data/' \
  --exclude='*_cache/' \
  --filter='protect README.md' \
  "$MAIN_SRC/" "$MAIN_DEST/"
echo "[sync-agents] Synced main"

for agent in "${AGENTS[@]}"; do
  src="$AGENTS_SRC/$agent/workspace"
  dest="$AGENTS_DEST/$agent"

  if [ ! -d "$src" ]; then
    echo "[sync-agents] Skipping $agent — no workspace dir"
    continue
  fi

  mkdir -p "$dest"

  # rsync: mirror src→dest, respect .gitignore-style excludes via --filter
  # Use --delete so removed files don't linger in the repo
  rsync -a --delete \
    --exclude='.env' \
    --exclude='*.env' \
    --exclude='.env.*' \
    --exclude='personal-info.json' \
    --exclude='auth-profiles.json' \
    --exclude='auth-state.json' \
    --exclude='.gmail-app-password' \
    --exclude='.bytedance-password' \
    --exclude='.capsolver-key' \
    --exclude='.tiktok-password' \
    --exclude='.jobright-session' \
    --exclude='*.pdf' \
    --exclude='*.docx' \
    --exclude='tracker.db' \
    --exclude='*.db' \
    --exclude='*.sqlite' \
    --exclude='MEMORY.md' \
    --exclude='HANDOFF.md' \
    --exclude='AGENTS.md' \
    --exclude='SOUL.md' \
    --exclude='IDENTITY.md' \
    --exclude='USER.md' \
    --exclude='TOOLS.md' \
    --exclude='HEARTBEAT.md' \
    --exclude='*.bak*' \
    --exclude='memory/' \
    --exclude='.workday-browser-data/' \
    --exclude='.browser-data/' \
    --exclude='.browser-contexts/' \
    --exclude='sessions.json' \
    --exclude='*.jsonl' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.venv/' \
    --exclude='venv/' \
    --exclude='env/' \
    --exclude='.DS_Store' \
    --exclude='BACKLOG.md' \
    --exclude='BOOTSTRAP.md' \
    --exclude='GATE.md' \
    --exclude='.openclaw/' \
    --exclude='.tmp/' \
    --exclude='.git/' \
    --filter='protect README.md' \
    "$src/" "$dest/"

  echo "[sync-agents] Synced $agent"
done

# Commit + push if there are changes
cd "$REPO_DIR"

git add -A

if git diff --cached --quiet; then
  echo "[sync-agents] No changes to commit."
  exit 0
fi

TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
git commit -m "chore(sync): auto-sync agent workspaces $TIMESTAMP"

git push origin main
echo "[sync-agents] Pushed to GitHub."
