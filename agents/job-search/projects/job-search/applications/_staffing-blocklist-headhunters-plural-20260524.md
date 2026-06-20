# staffing_blocklist.py — pluralised "headhunters" regex fix

**Date:** 2026-05-24 17:32 UTC
**Origin:** discovered while writing `test_staffing_blocklist.py` unit tests (BACKLOG-style "test coverage" deliverable). A natural fixture company name "Atlas Headhunters" failed to classify as staffing.
**Scope:** one regex character class extended; behaviour-preserving for every prior match.

## The bug

`staffing_blocklist.KEYWORD_PATTERNS` has:
```python
r"\bheadhunt(?:er|ing)\b",
```

This matches `headhunter` (singular) and `headhunting`, but **NOT** the much more common plural `headhunters` as it appears in real firm names ("Atlas Headhunters", "Talent Headhunters Inc", etc.).

Trivially verified:
```
old=False (Atlas Headhunters)
old=True  (Atlas Headhunter)
old=True  (Acme Headhunting Inc)
```

## The fix

Extend the inner non-capture group to include the plural form:
```python
r"\bheadhunt(?:er|ing|ers)\b",
```

Verified after fix:
```
new=True (Atlas Headhunters)
new=True (Atlas Headhunter)
new=True (Acme Headhunting Inc)
```

No existing test/regression touches this regex — the 28-row 2026-05-23 retro pass against tracker.db happened to not include any "Headhunters" names, so the bug slipped through.

## Files

- `_repair/staffing_blocklist.py.candidate` — proposed fix, one-character-class extension
- `test_staffing_blocklist.py` (live, new) — 19-test unittest suite covering normalisation, explicit blocklist, keyword patterns, true negatives, allowlist escape, edge cases (None, whitespace, punctuation), `filter_companies()` partition behaviour, and registry sanity. Includes `@unittest.expectedFailure`-marked `test_pluralised_headhunters_known_bug` that flips to a regular assertion once the candidate is promoted.

## Verification

- **Live module (with candidate NOT applied):** `python -m unittest test_staffing_blocklist` → 19 tests, OK, 1 expected failure. Clean exit 0.
- **Candidate applied via `sys.modules` shim:** same 19 tests → all pass, no expected failures. Clean exit 0.

## Recommend-merge

Yes. One-line, behaviour-preserving for every entry already in tracker.db. Will catch some additional LinkedIn rows on the next crawl when names like "<X> Headhunters" appear.

### Promotion command
```
cp projects/job-search/role-discovery/_repair/staffing_blocklist.py.candidate \
   projects/job-search/role-discovery/staffing_blocklist.py
```

Then update `test_staffing_blocklist.KeywordPatternHits.test_pluralised_headhunters_known_bug` — strip the `@unittest.expectedFailure` decorator and move the assertion into the main `POSITIVES` list.

### Optional retro pass

Once promoted, search tracker.db for rows whose company name contains "Headhunters" but aren't currently flagged `staffing-firm`:
```python
.venv/bin/python -c "
import sqlite3, re
c = sqlite3.connect('projects/job-search/tracker.db')
rx = re.compile(r'\\bheadhunt(?:er|ing|ers)\\b', re.I)
for row in c.execute(\"SELECT id, company, status, flags FROM roles WHERE company LIKE '%Headhunter%'\"):
    print(row)
"
```
If any rows fall out, run a retro flip (with the standard backup-then-write recipe) like the 2026-05-23 staffing_blocklist retro.
