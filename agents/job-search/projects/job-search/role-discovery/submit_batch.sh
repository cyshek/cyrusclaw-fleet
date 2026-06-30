#!/bin/bash
# submit_batch.sh — Submit prepped GH roles and update DB/STATUS.md on success
# Usage: ./submit_batch.sh
# Writes results to /tmp/gh_drain_results.txt

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
VENV=".venv/bin/python"
DB="../tracker.db"
RESULTS="/tmp/gh_drain_results.txt"

echo "=== GH Batch Submit $(date) ===" | tee "$RESULTS"

submit_gh() {
    local role_id="$1"
    local plan_path="$2"
    local company="$3"
    local role_name="$4"
    local ats="$5"

    echo ""
    echo "--- Submitting role $role_id: $company / $role_name ---"

    local slug
    slug=$(python3 -c "import json; d=json.load(open('$plan_path')); print(d['slug'])")
    local workdir
    workdir="$(dirname "$SCRIPT_DIR")/applications/submitted/$slug"

    local result_json
    local exit_code=0

    if [ "$ats" = "greenhouse" ]; then
        # Native GH: use _gh_submit.py <plan_path>
        result_json=$($VENV _gh_submit.py "$plan_path" 2>&1) || exit_code=$?
    else
        # Iframe: use greenhouse_iframe_runner.py --slug <slug>
        result_json=$($VENV greenhouse_iframe_runner.py --slug "$slug" 2>&1) || exit_code=$?
    fi

    # Extract status from output
    local status
    status=$(echo "$result_json" | python3 -c "
import sys, json, re
text = sys.stdin.read()
# Try to find JSON output (last {...} block)
matches = list(re.finditer(r'\{[^{}]*\"status\"[^{}]*\}', text, re.DOTALL))
if matches:
    try:
        d = json.loads(matches[-1].group())
        print(d.get('status', 'unknown'))
        sys.exit(0)
    except:
        pass
# Try full JSON parse
lines = text.strip().split('\n')
for line in reversed(lines):
    try:
        d = json.loads(line)
        if 'status' in d:\n            print(d['status'])\n            sys.exit(0)\n    except:
        pass
# Look for status in output
m = re.search(r'\"status\":\s*\"([^\"]+)\"', text)
if m:\n    print(m.group(1))\nelse:
    print('unknown')
" 2>/dev/null) || status="parse-error"

    echo "  Status: $status"
    echo "  Exit code: $exit_code"

    if [ "$status" = "SUBMITTED" ]; then
        echo "  ✅ SUBMITTED"

        # Extract confirmation URL from result
        local confirm_url
        confirm_url=$(echo "$result_json" | python3 -c "
import sys, json, re
text = sys.stdin.read()
m = re.search(r'\"url\":\s*\"([^\"]+)\"', text)
if m:\n    print(m.group(1))\nelse:
    print('n/a')
" 2>/dev/null) || confirm_url="n/a"

        # Write STATUS.md
        mkdir -p "$workdir"
        cat > "$workdir/STATUS.md" << EOF
STATUS: SUBMITTED
confirmation_url: $confirm_url
submitted_by: auto
resume_attached: true
submitted_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
role_id: $role_id
company: $company
role: $role_name
EOF
        echo "  Wrote STATUS.md"

        # Update tracker DB
        sqlite3 "$DB" "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now') WHERE id=$role_id;"
        echo "  Updated tracker DB"

        echo "SUBMITTED|$company|$role_name|$role_id" >> "$RESULTS"
    else
        echo "  ❌ FAILED: $status"
        echo "FAILED|$company|$role_name|$role_id|$status" >> "$RESULTS"
        # Save debug output
        echo "$result_json" > "/tmp/gh_fail_${role_id}.log"
        echo "  Debug log: /tmp/gh_fail_${role_id}.log"
    fi
}

# Native GH roles
submit_gh 1375 "output/inline-plan-anduril-5142847007.json" "Anduril" "Program Manager - SkillBridge" "greenhouse"
submit_gh 2670 "output/inline-plan-scopely-5222228008.json" "Scopely" "Associate Manager, Product Management" "greenhouse"
submit_gh 3164 "output/inline-plan-sigma-computing-7767726003.json" "Sigma Computing" "Solution Engineer" "greenhouse"
submit_gh 3506 "output/inline-plan-canonical-7490812.json" "Canonical" "Public Cloud Solution Architect" "greenhouse"
submit_gh 3507 "output/inline-plan-canonical-6969562.json" "Canonical" "Ubuntu Sales Engineer" "greenhouse"

# Iframe GH roles
submit_gh 877 "output/inline-plan-stripe-7815794.json" "Stripe" "Collections Program Manager" "greenhouse_iframe"
submit_gh 3021 "output/inline-plan-stripe-7975723.json" "Stripe" "Solutions Architect, AI" "greenhouse_iframe"
submit_gh 3025 "output/inline-plan-stripe-7377101.json" "Stripe" "Technical Solutions Engineer" "greenhouse_iframe"
submit_gh 3105 "output/inline-plan-brex-8443298002.json" "Brex" "Engineering Program Manager, AI" "greenhouse_iframe"
submit_gh 3369 "output/inline-plan-waymo-7922962.json" "Waymo" "Product Manager, Mapping" "greenhouse_iframe"
submit_gh 3371 "output/inline-plan-waymo-7902413.json" "Waymo" "Product Manager, Pickup and Dropoff" "greenhouse_iframe"
submit_gh 3372 "output/inline-plan-waymo-7917617.json" "Waymo" "Program Manager, Mapping Operations" "greenhouse_iframe"
submit_gh 3373 "output/inline-plan-waymo-7939648.json" "Waymo" "Program Manager, Risk & Insurance" "greenhouse_iframe"
submit_gh 3374 "output/inline-plan-waymo-7403855.json" "Waymo" "Technical Program Manager, Onboard Systems" "greenhouse_iframe"
submit_gh 3375 "output/inline-plan-waymo-7733791.json" "Waymo" "TPM, Systems Engineering" "greenhouse_iframe"
submit_gh 3446 "output/inline-plan-ixl-learning-8444833002.json" "IXL Learning" "Product Manager, Digital Marketing" "greenhouse_iframe"
submit_gh 3453 "output/inline-plan-intersystems-7679435003.json" "InterSystems" "Innovation Program Manager" "greenhouse_iframe"
submit_gh 3455 "output/inline-plan-intersystems-7735610003.json" "InterSystems" "Sales Engineer" "greenhouse_iframe"
submit_gh 3456 "output/inline-plan-intersystems-7735588003.json" "InterSystems" "Sales Engineer - Financial Services" "greenhouse_iframe"

echo ""
echo "=== Summary ===" | tee -a "$RESULTS"
echo "Submitted:" | tee -a "$RESULTS"
grep "^SUBMITTED" "$RESULTS" | tee -a /dev/stderr
echo "Failed:" | tee -a "$RESULTS"
grep "^FAILED" "$RESULTS" | tee -a /dev/stderr

echo ""
echo "Done at $(date)"
