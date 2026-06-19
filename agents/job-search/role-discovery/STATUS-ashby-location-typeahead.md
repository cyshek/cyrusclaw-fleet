# STATUS — Ashby Location typeahead fix (subagent ashby-location-typeahead-fix)

## ✅ COMPLETE (2026-06-11 ~06:42 PDT)

### Root cause — TWO distinct DOM variants, both mishandled (NOT one bug)

From the cached dryrun GraphQL JSON of the 3 rows:

| Row | Org | Location `type` | `_ashby_type` | Why it failed |
|-----|-----|----------------|---------------|---------------|
| 938 ElevenLabs | elevenlabs | `input_text` | **Location** | Geo-combobox variant. `_LOCATION_COMBO_FILL_JS` container/input locator too narrow (required `input[role=combobox]` + a `data-field-path` tail match). ElevenLabs renders a bare `input[type=text]` ("Start typing…") → logged `no-container`/`no-input`. |
| 1112 Higharc | higharc | **`multi_value_single_select`** | ValueSelect | **NOT a geo-typeahead** — discrete REGION select `[United States, Canada, South or Central America, Europe, Other]`. Dryrun resolved value="Kirkland, WA" → `choose_select_option` found NO match → returned None → radio never picked → server bounced "Missing Location". |
| 1235 Liquid AI | liquid-ai | **`multi_value_single_select`** | ValueSelect | Same as Higharc. Options `[SF/Bay area, Boston metro, Other US location (open to relocation), Other US location (remote only), Outside the US (open to relocation), Outside the US (remote only)]`. "Kirkland, WA" matched nothing → None → bounce. |

### Fix (commit `7d84e9f`, chain_p14)

**File: `_ashby_runner.py`** (2 isolated hunks; staged via `git add -p`, NOT the
other worker's uncommitted chain_p13/p12):

1. **location-REGION ladder** in `choose_select_option` (+ helpers
   `_choose_location_region_option`, `_looks_like_us_option`,
   `_LOCATION_REGION_LABEL_HINTS`, `_REGION_OPTION_HINTS`). When a select is a
   location/region question AND `want` is a US home location that matched no
   option, map to the best US-region option: US + open-to-relocation > other US >
   plain "United States". Never forces a US option for a foreign location
   ("London, UK"/"Toronto, ON" → None); uses a real US-state-code allowlist (so
   ", UK" ≠ US). Fixes **1112 → "United States"**, **1235 → "Other US location
   (open to relocation)"**. Fires AFTER the exact/startswith/substring +
   prior-employer + arrangement ladders (no regression to the permissive cohort).

2. **Broadened `_LOCATION_COMBO_FILL_JS` container/input locator** with a
   strategy ladder: (1) `data-field-path` tail + usable input → (1b) tail only →
   (2) location-ish label + usable input (dropped the role=combobox-only req) →
   (3) `_systemfield_location` container → (4) any input with a location-y
   placeholder/aria-label. `comboIn()` accepts `role=combobox` → `type=text` →
   any text input → placeholder-matched input. Fixes **938 ElevenLabs**. Still
   integrity-guarded (TYPE + option-pick only; `no-exact-match` guard retained).

### Tests — `test_ashby_location_typeahead.py` (NEW, 20 tests)
- Region ladder: Higharc→US, Liquid→US-relocation-open, relocation-open>remote-only,
  continents→Americas, foreign→None, empty→None, non-region→None, exact-match-wins,
  arrangement-doctrine-preserved, US-option detector edge cases.
- Combobox locator contract (Fake DOM mirroring the JS ladder): standard
  role=combobox tail match, ElevenLabs bare-text-input variant, label-fallback on
  tail mismatch, systemfield-location, placeholder-only, no-container integrity
  guard, + a live-JS-marker guard against accidental revert.
- **Full `pytest test_ashby*.py test_gh*.py`: 289 passed / 6 skipped / 5 subtests
  (baseline was 269 → +20 mine, ZERO regressions).**

### Git
- Commit `7d84e9f` — staged ONLY my 2 chain_p14 hunks (verified: 0 chain_p13/p12
  lines in `--cached` diff) + the new test. Other worker's chain_p13/p12 left
  UNCOMMITTED in the working tree (12 lines still in unstaged diff — untouched).
- Secret scan on staged hunks + test: clean (no keys/cookies/proxy creds).
- `.bak`: `_ashby_runner.py.bak.location-typeahead-20260611-063349`.

### Tracker (`tracker.db`, backed up `tracker.db.bak.ashby-location-20260611-064159`)
- 938 / 1112 / 1235: `block_reason` → `ashby-location-typeahead-RESOLVER-BUILT-ready-for-residential-retry (chain_p14 commit 7d84e9f)`; agent_notes appended.
- **NOT marked applied** — `status='blocked'`, `applied_by=NULL` unchanged (no submit happened).

### Ready for residential-retry?
YES — 938/1112/1235 are ready for a residential-egress submit retry under the
browser-worker slot. The parent / a later browser-worker performs the actual
submit (this subagent did NO live browser work, per the one-browser-worker rule).

### Constraints honored
- ⛔ NO live browser submit, NO shared-browser/CDP use. Diagnosis from cached
  dryrun JSON only.
- Did NOT blanket-commit the other worker's chain_p13. Did NOT touch
  SOUL/USER/HEARTBEAT/crons. No Discord posts.
