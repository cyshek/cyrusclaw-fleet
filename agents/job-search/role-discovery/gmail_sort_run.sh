#!/usr/bin/env bash
# Ongoing inbox sweep: move new application-confirmation + OTP emails into the
# "Job Applications" Gmail label so Cyrus's inbox stays clean. Last few days only
# (idempotent; already-moved mail isn't in the inbox). Never deletes.
set -euo pipefail
cd "$(dirname "$0")"
LOG="gmail_sort.log"
{
  echo "=== $(date -u +%FT%TZ) ==="
  python3 gmail_sort_applications.py --apply --since-days 4
} >> "$LOG" 2>&1
