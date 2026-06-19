#!/usr/bin/env bash
# bin/git-commit-push.sh — commit all changes and push to main
# Usage: ./bin/git-commit-push.sh "your commit message"
#
# Runs from any working directory; always operates on the fleet repo.

set -e

FLEET_REPO="/home/azureuser/.openclaw/workspace/cyrusclaw-fleet"
MSG="${1:-chore: auto-commit}"

if [ -z "$1" ]; then
  echo "Usage: $0 \"commit message\""
  echo "Using default message: $MSG"
fi

echo "→ Staging all changes in $FLEET_REPO..."
git -C "$FLEET_REPO" add -A

# Check if there's anything to commit
if git -C "$FLEET_REPO" diff --cached --quiet; then
  echo "✓ Nothing to commit (working tree clean)"
  exit 0
fi

echo "→ Committing: \"$MSG\""
git -C "$FLEET_REPO" commit -m "$MSG"

echo "→ Pushing to origin main..."
git -C "$FLEET_REPO" push

echo "✓ Done. Pushed to $(git -C "$FLEET_REPO" remote get-url origin)"
