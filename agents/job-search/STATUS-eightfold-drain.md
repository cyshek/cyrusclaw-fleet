# Eightfold Residential Drain — 2026-06-14

## Status: COMPLETE ✅

## Drain Summary

**Query result:** 0 blocked Eightfold rows remain in tracker.

All 12 Eightfold/Netflix rows are `status='applied'`.
33 Eightfold rows are `status='skip'` (duplicates/cross-links/senior).

## Netflix Rows — Final State

| ID | Role | Status | Applied On | Evidence |
|----|------|--------|------------|----------|
| 1394 | Product Manager, Content Intelligence | applied | 2026-06-14 | HTTP 201 + data.success=true |
| 1539 | Support Solutions Eng (L5), Graph Search | applied | 2026-06-14 | Already-applied (API confirmed) |
| 2157 | Solutions Architect - Total Rewards | applied | 2026-06-13 | Same pid as 2879, already-applied |
| 2870 | PM, Enterprise Developer Enablement | applied | 2026-06-14 | HTTP 201 + data.success=true |
| 2874 | TPM (L6), Identity and Access Mgmt | applied | 2026-06-14 | DB confirmed, drain batch |
| 2875 | Finance Program Manager | applied | 2026-06-14 | Already-applied (API confirmed) |
| 2877 | TPM - Cloud Infrastructure | applied | 2026-06-14 | Accidental submit during probe |
| 2879 | Solutions Architect - Total Rewards | applied | 2026-06-13 | Already-applied (API confirmed) |
| 2880 | HR Program Manager, Partnerships & Ads | applied | 2026-06-14 | /apply/success URL + modal |
| 2882 | Support Solutions Eng (L5), Graph Search | applied | 2026-06-14 | /apply/success URL + modal |
| 2883 | Support Solutions Eng (L5), Cloud Networking | applied | 2026-06-14 | HTTP 201 + data.success=true |
| 2885 | Solution Architect L4 - Workday Solutions | applied | 2026-06-14 | DB confirmed, drain batch |

## Actions Taken This Pass
- Queried tracker: 0 blocked Eightfold rows found
- Ran `_backfill_drain_status.py`: 22 already-applied confirmed, 0 new
- Backfilled STATUS.md for 2874/2877/2879/2880/2882/2883/2885 (files missing, evidence from daily log)
- DB backup: tracker.db.bak.20260614-185237-drain-reconcile
- Git commit: "eightfold residential drain 2026-06-14"

## Phase: DONE
## Next: None — all Eightfold rows exhausted
