"""Regression tests for the Greenhouse Remix-embed form-chrome auto-fill
(chain_015, 2026-05-29).

The newer job-boards.greenhouse.io embed adds two required react-select
typeaheads that are NOT in the boards-api spec: `#country` and
`#candidate-location`. `greenhouse_filler.build_plan` must always emit a
`country_dropdowns` entry for `#country` (label='United States'), and must
add a `#candidate-location` typeahead entry whenever the spec has a
freeform `location` text_field.

Forms that lack these IDs (legacy Greenhouse) gracefully no-op because
`JS_PICK_DROPDOWN_TYPEAHEAD` returns `err: no input` for missing inputs.
"""

import unittest

import greenhouse_filler


def _minimal_spec(extra_fields=None):
    return {
        "role_url": "https://job-boards.greenhouse.io/test/jobs/1",
        "org": "test",
        "job_id": "1",
        "fields": list(extra_fields or []),
    }


class GreenhouseRemixTypeaheadTests(unittest.TestCase):
    def test_always_emits_country_typeahead_when_spec_lacks_country_field(self):
        plan = greenhouse_filler.build_plan(_minimal_spec())
        ids = [d["id"] for d in plan["country_dropdowns"]]
        self.assertIn("country", ids)
        country = next(d for d in plan["country_dropdowns"] if d["id"] == "country")
        self.assertEqual(country["label"], "United States")

    def test_emits_candidate_location_when_text_fields_has_location(self):
        spec = _minimal_spec([
            {
                "id": "location",
                "type": "input_text",
                "value": "Kirkland, WA",
                "required": True,
                "status": "filled",
                "label": "Location",
            },
        ])
        plan = greenhouse_filler.build_plan(spec)
        ids = [d["id"] for d in plan["country_dropdowns"]]
        self.assertIn("candidate-location", ids)
        cl = next(d for d in plan["country_dropdowns"] if d["id"] == "candidate-location")
        self.assertEqual(cl["label"], "Kirkland, WA")
        # The legacy text setter should still run too.
        self.assertEqual(plan["text_fields"].get("location"), "Kirkland, WA")

    def test_no_candidate_location_when_no_location_in_text_fields(self):
        plan = greenhouse_filler.build_plan(_minimal_spec())
        ids = [d["id"] for d in plan["country_dropdowns"]]
        self.assertNotIn("candidate-location", ids)

    def test_country_dedup_when_spec_explicitly_defines_country_question(self):
        # If the boards-api schema already produced a country dropdown
        # entry via the COUNTRY_ID_RE / COUNTRY_LABEL_RE path, the post-loop
        # auto-emit must NOT add a duplicate.
        spec = _minimal_spec([
            {
                "id": "country",
                "type": "multi_value_single_select",
                "value": "Canada",
                "required": True,
                "status": "filled",
                "label": "Country",
                "options": [
                    {"label": "United States", "value": 1},
                    {"label": "Canada", "value": 2},
                    {"label": "Mexico", "value": 3},
                    {"label": "Germany", "value": 4},
                ],
            },
        ])
        plan = greenhouse_filler.build_plan(spec)
        country_entries = [d for d in plan["country_dropdowns"] if d["id"] == "country"]
        self.assertEqual(len(country_entries), 1)
        # And the explicit value wins, not our hard-coded 'United States'.
        self.assertEqual(country_entries[0]["label"], "Canada")


if __name__ == "__main__":
    unittest.main()
