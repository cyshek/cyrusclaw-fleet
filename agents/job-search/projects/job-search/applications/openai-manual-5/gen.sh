#!/bin/bash
# Generate 5 tailored OpenAI resumes (JD.md already staged in applications/queued/openai-<uuid>/)
set -uo pipefail
cd /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery
PY=.venv/bin/python
QUEUED=/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued

# role_id | job_uuid | family | title
ROLES=(
"804|d23c6966-e702-4088-860b-0f529745e03c|pm|Product Manager, Self-Serve Business Growth Lead"
"1010|0f4da2b4-df8a-4560-809d-d0a6ac1ad9bc|pm|Product Manager, Personalization"
"797|a4d772fc-1c97-43fd-8241-5e5afdc0ef51|pgm|Program Manager, Partner Operations"
"800|71004494-9a55-4ed5-b458-2ff475f0d881|tpm|Technical Program Manager, Human Data"
"801|9685eb6d-8276-4111-be8c-fd1277ad4555|tpm|Technical Program Manager, Safety Systems Engineering"
)

for entry in "${ROLES[@]}"; do
  IFS='|' read -r rid uuid fam title <<< "$entry"
  outdir="$QUEUED/openai-$uuid"
  echo "=================================================="
  echo "[START] role=$rid $title  (family=$fam)"
  $PY tailor_resume.py --org openai --job-id "$uuid" \
      --family "$fam" --auto-rewrite --max-loops 3 \
      > "$outdir/tailor.log" 2>&1
  rc=$?
  pdf=$(ls -1 "$outdir"/*_v2.pdf 2>/dev/null | head -1)
  if [ -n "$pdf" ]; then
    echo "[OK] role=$rid -> $pdf (rc=$rc)"
  else
    echo "[FAIL] role=$rid rc=$rc -- tail of log:"
    tail -20 "$outdir/tailor.log"
  fi
done
echo "=================================================="
echo "ALL DONE. PDFs:"
for entry in "${ROLES[@]}"; do
  IFS='|' read -r rid uuid fam title <<< "$entry"
  ls -la "$QUEUED/openai-$uuid"/*_v2.pdf 2>/dev/null
done
