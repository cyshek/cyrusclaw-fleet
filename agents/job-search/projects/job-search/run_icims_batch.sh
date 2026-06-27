#!/bin/bash
# run_icims_batch.sh — serial iCIMS submission batch (AMD, Keysight, SiriusXM)
# Generated 2026-06-26

set -uo pipefail

VENV=role-discovery/.venv/bin/python
LOG=.icims-batch-$(date +%Y%m%d-%H%M%S).log
CDP="http://127.0.0.1:18800"

echo "=== iCIMS BATCH START $(date) ===" | tee -a "$LOG"

submit_role() {
    local id="$1"
    local url="$2"
    local label="$3"

    echo "" | tee -a "$LOG"
    echo "--- [$id] $label ---" | tee -a "$LOG"
    echo "URL: $url" | tee -a "$LOG"

    # Step 1: prep via inline_submit
    echo "PREP..." | tee -a "$LOG"
    prep_out=$($VENV role-discovery/inline_submit.py --role-id "$id" 2>&1)
    prep_exit=$?
    echo "PREP exit=$prep_exit" | tee -a "$LOG"
    echo "$prep_out" | tail -5 >> "$LOG"

    # Step 2: run iCIMS runner
    echo "RUNNING runner..." | tee -a "$LOG"
    runner_out=$($VENV role-discovery/_icims_runner.py --url "$url" --apply --cdp "$CDP" --debug ".icims-debug/$id" 2>&1)
    runner_exit=$?
    echo "RUNNER exit=$runner_exit" | tee -a "$LOG"
    echo "$runner_out" >> "$LOG"

    case "$runner_exit" in
        0)  echo "✅ SUBMITTED [$id] $label" | tee -a "$LOG" ;;
        2)  echo "🚫 HCAPTCHA/AUTH-BLOCKED [$id] $label" | tee -a "$LOG" ;;
        6)  echo "❌ CLOSED [$id] $label" | tee -a "$LOG" ;;
        7)  echo "⚠️ ALREADY-APPLIED [$id] $label" | tee -a "$LOG" ;;
        10) echo "⏰ OTP-TIMEOUT [$id] $label" | tee -a "$LOG" ;;
        *)  echo "❓ EXIT=$runner_exit [$id] $label" | tee -a "$LOG" ;;
    esac

    echo "$runner_exit"
}

# Track hCaptcha hit count for AMD tenant
AMD_HCAPTCHA_COUNT=0
AMD_HCAPTCHA_LIMIT=3

# ===== AMD ×23 =====
echo "" | tee -a "$LOG"
echo "===== AMD ×23 (careers-amd.icims.com) =====" | tee -a "$LOG"

declare -a AMD_IDS=( 3761 3762 3763 3764 3765 3766 3767 3768 3769 3770 3771 3772 3773 3774 3775 3776 3777 3778 3779 3780 3781 3782 3783 )
declare -a AMD_URLS=(
    "https://careers-amd.icims.com/jobs/87205/login"
    "https://careers-amd.icims.com/jobs/87265/login"
    "https://careers-amd.icims.com/jobs/87077/login"
    "https://careers-amd.icims.com/jobs/87117/login"
    "https://careers-amd.icims.com/jobs/86326/login"
    "https://careers-amd.icims.com/jobs/86904/login"
    "https://careers-amd.icims.com/jobs/86949/login"
    "https://careers-amd.icims.com/jobs/86687/login"
    "https://careers-amd.icims.com/jobs/86615/login"
    "https://careers-amd.icims.com/jobs/86479/login"
    "https://canadacareers-amd.icims.com/jobs/86384/login"
    "https://careers-amd.icims.com/jobs/86128/login"
    "https://careers-amd.icims.com/jobs/86406/login"
    "https://careers-amd.icims.com/jobs/79943/login"
    "https://careers-amd.icims.com/jobs/80554/login"
    "https://careers-amd.icims.com/jobs/84726/login"
    "https://careers-amd.icims.com/jobs/86014/login"
    "https://careers-amd.icims.com/jobs/85750/login"
    "https://careers-amd.icims.com/jobs/84929/login"
    "https://careers-amd.icims.com/jobs/84268/login"
    "https://careers-amd.icims.com/jobs/80409/login"
    "https://careers-amd.icims.com/jobs/80071/login"
    "https://careers-amd.icims.com/jobs/80274/login"
)
declare -a AMD_LABELS=(
    "Program Manager"
    "Cluster Applications & Experience Program Manager"
    "Technical Program Manager - Manufacturing Test"
    "Technical Program Manager - Server Customer Escalations"
    "Occupational Health Program Manager"
    "Technical Program Manager, Pre-Silicon Development"
    "Privacy Program Manager"
    "Rack Expansion Program Manager"
    "Program Manager - Value Added Services"
    "Ethics & Compliance Program Manager"
    "Software Solutions Architect"
    "Product Manager - Client Strategy"
    "Customer Program Manager - Rack Scale CPU Solutions"
    "Logistics Principle Program Manager"
    "Technical Program Manager - SOC"
    "Solutions Architect"
    "Enterprise Solutions Product Manager"
    "Technical Program Manager - AI Cluster Validation"
    "Software Program Manager - SoC Diagnostics"
    "Embedded Diagnostics Program Manager"
    "Technical Program Manager - Training at Scale"
    "AI/ML Silicon Verification Solutions Engineer"
    "Customer Solutions Engineer - Hardware Systems"
)

AMD_ALL_HCAPTCHA=0

for i in "${!AMD_IDS[@]}"; do
    id="${AMD_IDS[$i]}"
    url="${AMD_URLS[$i]}"
    label="${AMD_LABELS[$i]}"

    exit_code=$(submit_role "$id" "$url" "$label")

    if [ "$exit_code" = "2" ]; then
        AMD_HCAPTCHA_COUNT=$((AMD_HCAPTCHA_COUNT + 1))
        if [ "$AMD_HCAPTCHA_COUNT" -ge "$AMD_HCAPTCHA_LIMIT" ]; then
            echo "" | tee -a "$LOG"
            echo "!!! AMD hCaptcha count=$AMD_HCAPTCHA_COUNT (>= $AMD_HCAPTCHA_LIMIT) — marking remaining AMD roles blocked and stopping AMD batch" | tee -a "$LOG"
            AMD_ALL_HCAPTCHA=1
            # Mark remaining roles blocked
            remaining_start=$((i + 1))
            for j in $(seq $remaining_start $((${#AMD_IDS[@]} - 1))); do
                rem_id="${AMD_IDS[$j]}"
                rem_label="${AMD_LABELS[$j]}"
                echo "SKIP (tenant hcaptcha): [$rem_id] $rem_label" | tee -a "$LOG"
                # Update tracker for remaining
                python3 -c "
import sqlite3, datetime
db = sqlite3.connect('tracker.db')
db.execute(\"UPDATE roles SET status='blocked', block_reason='icims-hcaptcha-no-vendor', agent_notes='AMD tenant hCaptcha: first 3 roles blocked, skipping remainder' WHERE id=?\", ($rem_id,))
db.commit()
db.close()
print('marked blocked: $rem_id')
"
            done
            break
        fi
    fi
    sleep 2
done

echo "" | tee -a "$LOG"
echo "===== KEYSIGHT ×3 (careers-keysight.icims.com) =====" | tee -a "$LOG"

submit_role 3787 "https://careers-keysight.icims.com/jobs/53104/login" "RFuW Field Solutions Engineer"
sleep 2
submit_role 3788 "https://careers-keysight.icims.com/jobs/51760/login" "Solutions Engineer - EDA"
sleep 2
submit_role 3789 "https://careers-keysight.icims.com/jobs/50012/login" "Electro Optical Software Product Manager"

echo "" | tee -a "$LOG"
echo "===== SIRIUSXM ×3 (uscareers-siriusxmradio.icims.com) =====" | tee -a "$LOG"

# SiriusXM: test first one; if hcaptcha block, mark all 3 blocked
sxm_1_exit=$(submit_role 3758 "https://uscareers-siriusxmradio.icims.com/jobs/17396/login" "Technical Program Manager")
sleep 2

if [ "$sxm_1_exit" = "2" ]; then
    echo "SiriusXM first role hCaptcha blocked — marking all 3 blocked" | tee -a "$LOG"
    for id in 3759 3760; do
        python3 -c "
import sqlite3
db = sqlite3.connect('tracker.db')
db.execute(\"UPDATE roles SET status='blocked', block_reason='icims-hcaptcha-no-vendor', agent_notes='SiriusXM tenant hCaptcha: first role blocked, marking remainder' WHERE id=?\", ($id,))
db.commit()
db.close()
print('marked blocked: $id')
"
    done
    echo "SKIP (tenant hcaptcha): [3759] Associate Technical Program Manager" | tee -a "$LOG"
    echo "SKIP (tenant hcaptcha): [3760] Technical Program Manager, Web Commerce & Marketing" | tee -a "$LOG"
else
    submit_role 3759 "https://uscareers-siriusxmradio.icims.com/jobs/17398/login" "Associate Technical Program Manager"
    sleep 2
    submit_role 3760 "https://uscareers-siriusxmradio.icims.com/jobs/17393/login" "Technical Program Manager, Web Commerce & Marketing"
fi

echo "" | tee -a "$LOG"
echo "===== BATCH COMPLETE $(date) =====" | tee -a "$LOG"
echo "Log: $LOG"
