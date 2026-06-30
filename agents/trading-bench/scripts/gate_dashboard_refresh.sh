#!/usr/bin/env bash
# Regenerate the GATE-tracker dashboard from live DBs. Wired to cron.
set -euo pipefail
cd /home/azureuser/.openclaw/agents/trading-bench/workspace
python3 runner/gate_dashboard.py --out reports/gate_dashboard.html >> reports/_gate_dashboard.log 2>&1
