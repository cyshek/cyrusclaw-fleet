#!/usr/bin/env bash
# bin/git-commit-push.sh — commit all changes and push to main
#
# Usage:
#   ./bin/git-commit-push.sh "your commit message"
#   ./bin/git-commit-push.sh --agent making-money "feat: updated outreach scripts"
#   ./bin/git-commit-push.sh --dry-run "chore: test"
#   ./bin/git-commit-push.sh --agent resume-tailor --dry-run "test"
#
# Flags:
#   --agent <name>   Set git author to openclaw-<name> <openclaw@cyrusclaw-fleet>
#   --dry-run        Stage and show diff, but do not commit or push
#
# Runs from any working directory; always operates on the fleet repo.

set -euo pipefail

FLEET_REPO="/home/azureuser/.openclaw/workspace/cyrusclaw-fleet"
AGENT_NAME=""
DRY_RUN=false
MSG=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      AGENT_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -*)
      echo "Unknown flag: $1" >&2
      exit 1
      ;;
    *)
      MSG="$1"
      shift
      ;;
  esac
done

if [[ -z "$MSG" ]]; then
  MSG="chore: auto-commit"
  echo "No commit message supplied. Using default: $MSG"
fi

# --- Stage all changes ---
echo "→ Staging all changes in $FLEET_REPO..."
git -C "$FLEET_REPO" add -A

# --- Check if there's anything to commit ---
if git -C "$FLEET_REPO" diff --cached --quiet; then
  echo "✓ Nothing to commit (working tree clean)"
  exit 0
fi

# --- Show what would be committed ---
echo "→ Staged changes:"
git -C "$FLEET_REPO" diff --cached --stat

if $DRY_RUN; then
  echo "⚠️  Dry-run mode: stopping before commit. No changes made."
  exit 0
fi

# --- Build author string if --agent was passed ---
GIT_AUTHOR_ARGS=()
if [[ -n "$AGENT_NAME" ]]; then
  AUTHOR_NAME="openclaw-${AGENT_NAME}"
  AUTHOR_EMAIL="openclaw@cyrusclaw-fleet"
  GIT_AUTHOR_ARGS=(
    -c "user.name=${AUTHOR_NAME}"
    -c "user.email=${AUTHOR_EMAIL}"
  )
  echo "→ Committing as: ${AUTHOR_NAME} <${AUTHOR_EMAIL}>"
fi

echo "→ Committing: \"$MSG\""
git -C "$FLEET_REPO" "${GIT_AUTHOR_ARGS[@]}" commit -m "$MSG"

echo "→ Pushing to origin main..."
git -C "$FLEET_REPO" push

echo "✓ Done. Pushed to $(git -C "$FLEET_REPO" remote get-url origin)"
