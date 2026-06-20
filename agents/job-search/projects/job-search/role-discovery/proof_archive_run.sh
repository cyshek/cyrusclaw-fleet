#!/usr/bin/env bash
# Proof archive reconciler — runs periodically, idempotent. Picks up new submits,
# copies resume+fields into outputs/proof/, refreshes INDEX.md. Never posts to channel.
set -euo pipefail
cd "$(dirname "$0")"
LOG="proof_archive.log"
{
  echo "=== $(date -u +%FT%TZ) ==="
  python3 proof_archiver.py
} >> "$LOG" 2>&1
