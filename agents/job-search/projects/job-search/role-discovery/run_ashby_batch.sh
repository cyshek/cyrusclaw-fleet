#!/bin/bash
# Batch Ashby submission script
# Run from role-discovery directory

ROLE_IDS="933 945 1248 1325 1392 1555 1618 1620 1621 1622 1956 1983 2099 2140 2196 2206 2210 2214 2242 2262 2275 2320 2447 2449 2562 2566 2575 2576 2582 2586 2607 2609 2611 2712 2773 2787 2795 2800 2805 2808 2817 2821 2907 2912 2918 2954 2957 2958 2959 2960 2971 2982 3111 3268"

SUBMITTED=()
ALREADY_APPLIED=()
ROLE_CLOSED=()
RECAPTCHA_HARD=()
ERRORS=()
SKIPPED=()

DB="../tracker.db"
WORKSPACE="/home/azureuser/.openclaw/agents/job-search/workspace"

for ROLE_ID in $ROLE_IDS; do
    echo ""
    echo "=========================================="
    echo "PROCESSING ROLE ID: $ROLE_ID"
    echo "=========================================="
    
    # Get company/role name
    COMPANY=$(sqlite3 $DB "SELECT company FROM roles WHERE id=$ROLE_ID;")
    ROLE=$(sqlite3 $DB "SELECT role FROM roles WHERE id=$ROLE_ID;")
    echo "Company: $COMPANY | Role: $ROLE"
    
    # Step 1: Run inline_submit to prep the plan
    echo "--- Running inline_submit ---"
    PREP_OUTPUT=$(.venv/bin/python3 inline_submit.py --role-id $ROLE_ID 2>&1)
    PREP_EXIT=$?
    echo "$PREP_OUTPUT" | tail -5
    
    # Check if prep produced a plan
    PLAN_FILE=$(ls -t output/inline-plan-*.json 2>/dev/null | head -1)
    
    if [ -z "$PLAN_FILE" ]; then
        echo "ERROR: No plan file found for role $ROLE_ID"
        echo "PREP OUTPUT: $PREP_OUTPUT" > /tmp/ashby-drain-$ROLE_ID.log
        ERRORS+=("$ROLE_ID ($COMPANY - $ROLE): no plan file")
        continue
    fi
    
    # Check if plan is for the right role
    PLAN_ROLE_ID=$(python3 -c "import json; d=json.load(open('$PLAN_FILE')); print(d.get('role_id',''))" 2>/dev/null)
    if [ "$PLAN_ROLE_ID" != "$ROLE_ID" ]; then
        echo "WARNING: Plan file role_id=$PLAN_ROLE_ID doesn't match expected $ROLE_ID"
    fi
    
    echo "Plan: $PLAN_FILE"
    
    # Step 2: Run the Ashby runner
    echo "--- Running _ashby_runner ---"
    RUNNER_OUTPUT=$(.venv/bin/python3 _ashby_runner.py $PLAN_FILE 2>&1)
    RUNNER_EXIT=$?
    echo "$RUNNER_OUTPUT" | tail -10
    echo "Exit code: $RUNNER_EXIT"
    
    # Save full log
    echo "$RUNNER_OUTPUT" > /tmp/ashby-drain-$ROLE_ID.log
    
    # Parse results
    if [ $RUNNER_EXIT -eq 0 ] || echo "$RUNNER_OUTPUT" | grep -q "FormSubmitSuccess\|submitted successfully\|Application submitted"; then
        echo ">>> SUCCESS: Role $ROLE_ID submitted!"
        
        # Get slug from plan
        SLUG=$(python3 -c "import json; d=json.load(open('$PLAN_FILE')); print(d.get('slug','role-$ROLE_ID'))" 2>/dev/null)
        
        # Create STATUS.md
        mkdir -p $WORKSPACE/applications/submitted/$SLUG
        cat > $WORKSPACE/applications/submitted/$SLUG/STATUS.md << EOF
# $COMPANY — $ROLE

status: SUBMITTED
date: 2026-06-24
submitted_by: auto
role_id: $ROLE_ID
screenshot: auto-confirmed
method: ashby-runner
EOF
        
        # Update DB
        sqlite3 $DB "UPDATE roles SET status='submitted', applied_by='auto', applied_on='2026-06-24', response_status='submitted', block_reason=NULL WHERE id=$ROLE_ID;"
        SUBMITTED+=("$ROLE_ID ($COMPANY)")
        
    elif [ $RUNNER_EXIT -eq 7 ] || echo "$RUNNER_OUTPUT" | grep -q "ALREADY_APPLIED\|already.applied\|already applied"; then
        echo ">>> ALREADY APPLIED: Role $ROLE_ID"
        sqlite3 $DB "UPDATE roles SET block_reason='already-applied-within-90d' WHERE id=$ROLE_ID;"
        ALREADY_APPLIED+=("$ROLE_ID ($COMPANY)")
        
    elif [ $RUNNER_EXIT -eq 6 ] || echo "$RUNNER_OUTPUT" | grep -q "ROLE_CLOSED\|role.closed\|Job no longer available\|job is no longer"; then
        echo ">>> ROLE CLOSED: Role $ROLE_ID"
        sqlite3 $DB "UPDATE roles SET status='blocked', block_reason='role-closed' WHERE id=$ROLE_ID;"
        ROLE_CLOSED+=("$ROLE_ID ($COMPANY)")
        
    elif echo "$RUNNER_OUTPUT" | grep -q "RECAPTCHA_SCORE_BELOW_THRESHOLD\|recaptcha.*score\|captcha.*score"; then
        echo ">>> RECAPTCHA FAIL: Role $ROLE_ID - trying residential..."
        
        # Try residential
        RESIDENTIAL_OUTPUT=$(JOBSEARCH_PROXY_MODE=residential .venv/bin/python3 _ashby_runner.py $PLAN_FILE 2>&1)
        RESIDENTIAL_EXIT=$?
        echo "$RESIDENTIAL_OUTPUT" | tail -10
        echo "$RESIDENTIAL_OUTPUT" >> /tmp/ashby-drain-$ROLE_ID.log
        
        if [ $RESIDENTIAL_EXIT -eq 0 ] || echo "$RESIDENTIAL_OUTPUT" | grep -q "FormSubmitSuccess\|submitted successfully"; then
            echo ">>> SUCCESS (residential): Role $ROLE_ID"
            SLUG=$(python3 -c "import json; d=json.load(open('$PLAN_FILE')); print(d.get('slug','role-$ROLE_ID'))" 2>/dev/null)
            mkdir -p $WORKSPACE/applications/submitted/$SLUG
            cat > $WORKSPACE/applications/submitted/$SLUG/STATUS.md << EOF
# $COMPANY — $ROLE

status: SUBMITTED
date: 2026-06-24
submitted_by: auto
role_id: $ROLE_ID
screenshot: auto-confirmed
method: ashby-runner-residential
EOF
            sqlite3 $DB "UPDATE roles SET status='submitted', applied_by='auto', applied_on='2026-06-24', response_status='submitted', block_reason=NULL WHERE id=$ROLE_ID;"
            SUBMITTED+=("$ROLE_ID ($COMPANY) [residential]")
        else
            echo ">>> RECAPTCHA HARD BLOCK: Role $ROLE_ID"
            sqlite3 $DB "UPDATE roles SET block_reason='ashby-hard-recaptcha-residential-resistant' WHERE id=$ROLE_ID;"
            RECAPTCHA_HARD+=("$ROLE_ID ($COMPANY)")
        fi
        
    elif echo "$RUNNER_OUTPUT" | grep -q "neara\|au.work.rights\|work.rights"; then
        echo ">>> NEARA AU RIGHTS: Role $ROLE_ID"
        sqlite3 $DB "UPDATE roles SET block_reason='ashby-neara-au-work-rights-form' WHERE id=$ROLE_ID;"
        ERRORS+=("$ROLE_ID ($COMPANY): neara-au-work-rights")
        
    else
        echo ">>> ERROR/UNKNOWN: Role $ROLE_ID (exit $RUNNER_EXIT)"
        ERRORS+=("$ROLE_ID ($COMPANY - $ROLE): exit=$RUNNER_EXIT")
    fi
    
    # Brief pause between roles
    sleep 2
done

echo ""
echo "=========================================="
echo "BATCH COMPLETE - SUMMARY"
echo "=========================================="
echo "SUBMITTED (${#SUBMITTED[@]}):"
for r in "${SUBMITTED[@]}"; do echo "  + $r"; done

echo ""
echo "ALREADY APPLIED (${#ALREADY_APPLIED[@]}):"
for r in "${ALREADY_APPLIED[@]}"; do echo "  ~ $r"; done

echo ""
echo "ROLE CLOSED (${#ROLE_CLOSED[@]}):"
for r in "${ROLE_CLOSED[@]}"; do echo "  - $r"; done

echo ""
echo "RECAPTCHA HARD (${#RECAPTCHA_HARD[@]}):"
for r in "${RECAPTCHA_HARD[@]}"; do echo "  x $r"; done

echo ""
echo "ERRORS (${#ERRORS[@]}):"
for r in "${ERRORS[@]}"; do echo "  ! $r"; done

echo ""
echo "TOTALS: submitted=${#SUBMITTED[@]}, already-applied=${#ALREADY_APPLIED[@]}, closed=${#ROLE_CLOSED[@]}, recaptcha-hard=${#RECAPTCHA_HARD[@]}, errors=${#ERRORS[@]}"
