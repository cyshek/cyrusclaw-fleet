#!/bin/bash
# keysight_full_drain.sh - Full Keysight drain: reset pw + apply to 3787/3788
# Called from cron 45min after Auth0 rate-limit clears
set -e
cd /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery

# Load env
export TWOCAPTCHA_API_KEY=$(grep -oP 'TWOCAPTCHA_API_KEY=\K\S+' ~/.bashrc 2>/dev/null || printenv TWOCAPTCHA_API_KEY)
export JOBSEARCH_CDP="http://127.0.0.1:18800"
WS="/home/azureuser/.openclaw/agents/job-search/workspace"
LOG="$WS/keysight_drain_$(date +%Y%m%d_%H%M%S).log"

echo "[keysight_drain] Starting at $(date)" | tee -a "$LOG"

# Step 1: Reset password
echo "[keysight_drain] Step 1: Reset Auth0 password" | tee -a "$LOG"
.venv/bin/python keysight_reset_pw.py >> "$LOG" 2>&1
RC=$?
if [ $RC -ne 0 ]; then
    echo "[keysight_drain] Password reset FAILED (exit $RC)" | tee -a "$LOG"
    # Mark roles blocked
    sqlite3 "$WS/projects/job-search/tracker.db" \
        "UPDATE roles SET status='blocked', block_reason='keysight-auth0-pw-reset-failed' WHERE id IN (3787,3788) AND status='open';"
    exit 1
fi

echo "[keysight_drain] Password reset OK" | tee -a "$LOG"

# Step 2: Re-open roles and drain
echo "[keysight_drain] Step 2: Re-open roles 3787/3788" | tee -a "$LOG"
sqlite3 "$WS/projects/job-search/tracker.db" \
    "UPDATE roles SET status='open', block_reason=NULL WHERE id IN (3787,3788) AND status IN ('open','blocked');"

# Step 3: Run drain
echo "[keysight_drain] Step 3: Run drain" | tee -a "$LOG"
JOBSEARCH_CDP="http://127.0.0.1:18800" \
  TWOCAPTCHA_API_KEY="$TWOCAPTCHA_API_KEY" \
  .venv/bin/python icims_drain3.py --ids 3787,3788 >> "$LOG" 2>&1 || true

echo "[keysight_drain] Done at $(date)" | tee -a "$LOG"
