# Classifier Rewrite — Deterministic Skip Gates (2026-05-25)

**Policy directive from Cyrus 2026-05-25:** rewrite `role-discovery/jd_llm_classifier.py` to use deterministic skip gates only. Kill the `fit_score < 40` LLM-vibe gate.

## What changed

### `jd_llm_classifier.py`

- **Killed** the `fit_score < 40` skip branch from `maybe_skip()`. `fit_score` is still extracted and stored in `llm_fit_score` for visibility/debugging — it just no longer flips rows.
- **Rewrote** `maybe_skip()` as a 5-gate deterministic pipeline. ANY gate match → `status='skip'` + flag appended.
- **Renamed** the single legacy flag `llm-overreach` into per-gate flags (`senior-title`, `yoe-threshold`, `people-mgr`, `senior-llm`, `non-us`) so we can audit which rule fired.
- **Added** three new helpers: `extract_title_skip()`, `extract_yoe_from_jd_text()`, `detect_non_us_location()`.
- **Threaded** `jd_text` through `maybe_skip()` so JD-based gates (YOE, non-US) can run alongside the LLM signal.
- **Stores** the regex-extracted JD YOE into `llm_yoe_required` when it's stronger than the LLM's value.
- **Updated** the `PROMPT_TEMPLATE` to document that `fit_score` is no longer used as a gate.

### New helper: `extract_title_skip(title) -> kw|None`

Layered logic with target-role carve-out (Cyrus 2026-05-25 PM correction):

1. **HARD blocklist** (any match → skip, word-boundary, case-insensitive):
   `chief, distinguished, fellow, head of, principal, director, svp, evp, vp, senior, sr/sr., staff/staff+, partner, group, lead, mgr`
2. **SOFT 'manager'**: skip only if title does NOT contain a target-role substring (PM/TPM/EPM/PgM/SE/SA/FDE family).
3. Otherwise KEEP.

Order in HARD list matters for which keyword gets reported (e.g. "Chief of Staff" reports `chief`, not `staff`).

#### Target-role allowlist (substrings, case-insensitive)
```
product manager, program manager, project manager,
technical program manager, engineering program manager,
product marketing manager, solutions engineer, solution engineer,
sales engineer, solutions architect, solution architect,
forward deployed engineer, customer engineer,
software engineer, product engineer
```

### New helper: `extract_yoe_from_jd_text(jd) -> int|None`

Scans JD body, returns MAX integer found (capped to 0–24 to avoid junk). Patterns:

```python
r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+|relevant\s+|industry\s+|work\s+|hands[- ]on\s+)?experience\b"
r"\b(?:minimum|at\s+least|requires?|require)\s+(?:of\s+)?(\d{1,2})\+?\s*(?:years?|yrs?)\b"
r"\bYOE\s*[:=>]?\s*(\d{1,2})\b"
r"\b(\d{1,2})\s*[-–to]+\s*(\d{1,2})\+?\s*(?:years?|yrs?)\b"
```

**Deliberately removed** the bare `\b(\d+)\s*years?\b` fallback. Initial test against the Sierra Product Manager JDs returned `jd-yoe:18` because of a founder bio: *"Clay spent 18 years at Google"*. Founder-bio false-positive made the bare fallback unusable; the remaining patterns all require an experience/requirement context word.

Skip threshold: `>=4`. Stored as `llm_yoe_required` (overwriting LLM's value when stronger).

### New helper: `detect_non_us_location(jd, loc_field) -> reason|None`

Conservative, layered:

1. **Strong exclusive patterns** in loc or JD-head (first 3000 chars): `"UK only"`, `"Remote - EU"`, `"based in London/Berlin/Toronto/Bangalore/..."`, `"must be located in EU/EMEA/APAC/India/Canada"`.
2. **Loc field** non-US city/country wins iff loc has no offsetting US signal.
3. **JD-head** non-US city/country wins iff JD-head AND loc have no offsetting US signal anywhere.

US allowlist covers state names, 2-letter postal codes, major US cities, "United States", "USA", "US Remote", "Remote, US".

JD scan bounded to first 3000 chars to avoid false-positives from deep body text like "the London office" or "global team".

## Retro pass results (2026-05-25 15:11 UTC)

Backup: `tracker.db.bak.20260525-classifier-rewrite` (1327104 bytes).

Pre-pass: 344 open unapplied roles.
Post-pass: 305 open, 39 flipped → skip.

| Gate | Flag | Count | Notes |
|------|------|-------|-------|
| Title blocklist | `senior-title` | 5 | All `title:group` (2) or `title:partner` (3). Includes Apple "Vision Products Group", OpenAI "Partner Operations", Wiz/Intercom "Partner SA/SE", Anduril "Group 5 Mission Autonomy". |
| JD YOE ≥ 4 | `yoe-threshold` | 34 | Mostly `jd-yoe:5` (Tesla, Spot & Tango) and `jd-yoe:10` (Astronomer, Ursus). |
| People-mgr (LLM) | `people-mgr` | 0 | Upstream filters caught these already. |
| Senior (LLM) | `senior-llm` | 0 | Same. |
| Non-US loc | `non-us` | 0 | Upstream pipeline already filters non-US; this is now a safety net for future leaks. |

47/344 rows had no cached JD text → YOE and non-US gates silently abstain for those (cache is populated by `jd_llm_classifier.py` on first classification; older rows pre-date the cache).

## Edge cases hit

- **Founder-bio YOE false-positive** (Sierra "Clay spent 18 years at Google"). Fix: dropped the bare `\d+ years?` fallback. Documented inline.
- **"Chief of Staff" matching `staff`** before `chief`. Fix: reordered HARD list so specific keywords come first.
- **Cyrus's "Product Manager" target roles** false-positive on the `manager` keyword. Fix: target-role carve-out (substring allowlist; HARD keywords still win over carve-out so "Senior Product Manager" still skips).
- **`status` column** stores empty string `''` for open rows, not NULL — `maybe_skip()` checks both via the SELECT.
- **Flag separator mix** in the wild (`,` and `;`). `_merge_flag()` splits on `[;,\s]+` for de-dup but writes back with `;` (matching the existing classifier's convention).

## Unit-test cases (all passing, 44/44)

All of Cyrus's explicit verification list plus extras:

```
'Product Manager'                                  KEEP
'Senior Product Manager'                           SKIP senior
'Technical Program Manager'                        KEEP
'Engineering Manager'                              SKIP manager
'Lead Product Manager'                             SKIP lead
'Group Product Manager'                            SKIP group
'Solutions Engineer'                               KEEP
'Sales Engineer'                                   KEEP
'Partner Solutions Architect'                      SKIP partner
'Customer Success Manager'                         SKIP manager
'Manager, Product Operations'                      SKIP manager
'Program Manager, Strategy'                        KEEP
'Product Marketing Manager'                        KEEP    (err-on-keep per Cyrus)
'Technical Account Manager'                        SKIP manager  (CS track, no target substring)
'Chief of Staff'                                   SKIP chief
'Eng Mgr'                                          SKIP mgr
'Leadership Development Program'                   KEEP    (word-boundary excludes 'Leadership')
```

YOE regex tests:
```
'5+ years of experience'                              -> 5
'experience with cloud platforms (3-5 years preferred)' -> 5
'Minimum 4 years of relevant experience'              -> 4
'Requires 10+ years of industry experience'           -> 10
'YOE: 7'                                              -> 7
'Clay spent 18 years at Google'                       -> None  (false-positive fixed)
'We are a small team'                                 -> None
```

Non-US tests:
```
jd='Based in London, UK', loc=''           -> SKIP
jd='Remote, US', loc=''                    -> KEEP
jd='', loc='Bangalore, India'              -> SKIP
jd='', loc='Toronto, ON'                   -> SKIP
jd='', loc='Austin, TX'                    -> KEEP
jd='Global team with occasional travel to London', loc='San Francisco, CA' -> KEEP
```

## Recommendations for follow-up

1. **Re-run JD fetch + classify for the 47 rows without cached JD** so the YOE/non-US gates can score them. Command: `.venv/bin/python jd_llm_classifier.py --force --limit 50` (start small to confirm).
2. **Monitor `non-us` flag count** on the next weekly crawl. If it's still 0, the upstream adapter filters are doing all the work and this gate stays a defensive backstop. If it starts firing, that's a signal a new ATS slug let non-US roles through.
3. **Decide on `Account Manager` / `Technical Account Manager`** — currently skipped. If those are actually borderline IC roles Cyrus would consider, add `"account manager"` to `TARGET_ROLE_SUBSTRINGS`. (Default: keep as skip; they're CS/sales-adjacent.)
4. **Consider porting `extract_title_skip` to `core.py`** so `inline_submit.pick_batch()` uses the same logic. Currently `core.SENIOR_TITLE_RE` is more conservative (doesn't include bare "senior", "staff", "manager", "lead"). The classifier's stricter blocklist now duplicates work — would be cleaner to share. **Open question for Cyrus before merging.**
5. **Permanent pipeline integration:** the new `maybe_skip()` runs on every fresh classification, so all 5 gates fire on every new role going forward. The retro-pass script (`retro_apply_new_classifier_gates.py`) is a one-shot catch-up; it stays in the tree but isn't wired into `weekly_run.sh`. No follow-up needed there.

## Files touched

- `role-discovery/jd_llm_classifier.py` — full rewrite of `maybe_skip()` + helpers + prompt.
- `role-discovery/retro_apply_new_classifier_gates.py` — new one-shot retro driver.
- `tracker.db.bak.20260525-classifier-rewrite` — pre-rewrite backup (kept).
- `applications/_classifier-rewrite-retro-20260525-151130.json` — retro report (apply mode).
- `TOOLS.md` — updated `## Role discovery pipeline` section.
