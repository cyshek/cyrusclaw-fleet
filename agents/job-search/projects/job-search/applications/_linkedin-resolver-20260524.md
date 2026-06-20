# LinkedIn ATS Resolver — 2026-05-24

## Summary

**Total attempted: 51** (not 191 — see scoping below)
**Resolved: 0**
**Failed: 0** (all HTTP 200)
**Classified: 0** (offsite_unresolved=0, easy_apply=0, **unknown=51**)

## What happened

Ran `linkedin_ats_resolver.py` against all rows matching its WHERE clause:
`source_key LIKE 'linkedin:%' AND status NOT IN ('closed','skip','rejected') AND (flags LIKE '%manual-apply%' OR flags IS NULL)`

That yielded **51 candidate rows**, not 191. Breakdown of the full 191 status=NULL LinkedIn rows in tracker.db:

| Bucket | Count | Notes |
|---|---|---|
| `flags LIKE '%manual-apply%'` (raw, unprocessed) | 51 | the ones this run targeted |
| `flags LIKE '%linkedin-offsite-unresolved%'` (already classified) | ~125 | external ATS exists but hidden behind LinkedIn auth — resolver SKIPS these because they were already processed in a prior run (their flags no longer contain `manual-apply`) |
| `flags LIKE '%linkedin-easy-apply%'` | 0 in status=NULL bucket | already moved to `status='skip'` (now in the 154-row skip bucket) |
| other (e.g. `staffing-firm`) | ~15 | excluded by curation |

So the resolver's scope is "newly inserted manual-apply rows", and on this run there were 51 such rows from the recent weekly crawl.

## All 51 classified as `unknown`

100% of attempted rows returned HTTP 200 but contained **none** of the historical signals:
- No `apply-link-offsite`
- No `apply-link-onsite`
- No `apply-button__offsite`
- No embedded ATS URL

I probed manually (job id 4414137664) against both endpoints:

1. `https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<jid>` — returns 200, 19KB HTML with JD text only. **No apply button, no offsite/onsite signal, no `Apply` text at all.**
2. `https://www.linkedin.com/jobs/view/<jid>` — returns 200, 324KB HTML, contains `contextual-sign-in-modal` but **no** offsite/onsite signal, no Easy Apply text, no ATS URL leak.

**Finding:** LinkedIn appears to have removed the off-site/on-site classification signal from anonymous responses entirely since the resolver was authored (2026-05-23). The classifier is now blind. The resolver does not write anything for `unknown` classification, so the DB is unchanged.

## Breakdown by ATS type

```
Greenhouse: 0
Ashby:      0
Lever:      0
Workday:    0
unknown:    51 (no signal present)
```

## Unresolved list (all 51, by reason)

All 51 rows: `reason='unknown classification - LinkedIn no longer exposes offsite/onsite signal in anonymous HTML'`.

Row IDs (sample): 984, 987, 991, 992, 1001, 1005, 1008, 1010, 1014, 1017, 1020, 1028, 1036, 1039, 1051, 1053, 1076, 1080, 1082, 1090, 1093, 1106, 1109, 1129, 1133, 1141, 1143, 1145, 1154, 1160, 1164, 1166, 1174, 1185, 1190, 1203, 1207, 1213, 1216, 1244, 1253, 1260, 1261, 1263, 1270, 1295, 1299, 1304, 1320, 1324, 1336.

## Backup

`projects/job-search/tracker.db.bak.20260524-linkedin-resolver` (1015808 bytes, written 2026-05-24 19:19 UTC).

## Recommendations

1. **Resolver is dead against current LinkedIn anonymous surface.** The historical signals are gone. Future work needs either:
   - LinkedIn auth cookies (out of scope per task rules — auth/scraping policy)
   - Paid scraping API (money decision — escalate to Cyrus)
   - A new signal: maybe the structured `application/ld+json` JobPosting blob still has `directApply` field? Worth a separate probe.
2. **51 raw LinkedIn rows remain `manual-apply`** — they'll keep getting picked up by future resolver runs but with the same `unknown` outcome until the script is updated.
3. **No DB mutations performed** (all classifications were `unknown`).
4. Suggest updating `MEMORY.md` entry on LinkedIn resolver: signal removal as of 2026-05-24.

## Result JSON

```json
{"attempted": 51, "resolved": 0, "failed": 0, "by_ats": {"greenhouse":0,"ashby":0,"lever":0,"workday":0,"unknown":51}, "report_path": "applications/_linkedin-resolver-20260524.md"}
```
