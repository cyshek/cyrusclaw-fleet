# Netflix Eightfold Batch 2 — COMPLETED
Completed: 2026-06-14 ~08:15 UTC

## Results
| ID | Role | PID | Status | enc_id | Evidence |
|----|------|-----|--------|--------|----------|
| 2875 | Finance Program Manager | 790315885533 | ALREADY APPLIED ✅ | 0VjoAA9pq | API 400 "already applied" |
| 2870 | PM Enterprise Developer Enablement | 790313094223 | SUBMITTED ✅ | nOGJgg1Aa | HTTP 201 + data.success=true |
| 1394 | PM Content Intelligence | 790315659551 | SUBMITTED ✅ | 5ajZxxPx2 | HTTP 201 + data.success=true |
| 1539 | SSE L5 Graph Search | 790315245289 | ALREADY APPLIED ✅ | bVb5ggea8 | API 400 "already applied" |
| 2157 | Solutions Architect Total Rewards | 790314061634 | MARKED APPLIED ✅ | same as 2879 | Confirmed already applied 2026-06-13 |

## DB State
All 5 roles: status='applied', applied_by='auto', applied_on='2026-06-14' (2157: 2026-06-13)

## XLSX
620 applied total (render_xlsx.py regenerated)

## Notes
- "Please reload the page" HTTP 400 on first attempt is transient; immediate retry succeeds
- Validation error divs with empty text = normal Eightfold behavior, not actual errors
- Residential proxy at 19223 used for all submits
- Tailored resumes: from applications/queued/ directories
