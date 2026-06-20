"""Contract tests for the GH education + location typeahead engine fix
(2026-06-08, TOOLS.md NEXT-ENGINE-FIX part (b)).

Background: the GH education panel renders required react-select TYPEAHEADS with
ids school--0/discipline--0/degree--0, and the home location on Remix-embed forms
is the #candidate-location async typeahead (NOT <input id="location">). Neither is
in the boards-api field spec, so the plan never targeted them -> empty ->
emptyRequired -> 'uncertain' (Lila/Schrodinger/Raft/Axon/Figma class). The old
fix was a per-row `--answers typeahead` workaround. plan_education_specs() and
plan_location_typeahead_spec() are the pure (no-browser) helpers that derive the
SEL_TYPEAHEAD specs automatically with truthful canonical values, so main() fills
them with no manual --answers.
"""
import _gh_submit as g


# ---------------------------------------------------------------------------
# Education typeahead specs
# ---------------------------------------------------------------------------

PERSONAL = {
    "education": {
        "school": "University of Houston",
        "degree": "Bachelor of Science",
        "major": "Computer Science",
        "minor": "Mathematics",
        "school_undergrad": "University of Houston",
        "degree_undergrad": "Bachelor's degree",
    }
}


def _by_id(specs):
    return {s["id"]: s for s in specs}


def test_education_specs_from_personal_truthful_values():
    # No plan _education -> fall back to personal-info education.
    specs = _by_id(g.plan_education_specs({}, personal=PERSONAL))
    assert specs["school--0"]["label"] == "University of Houston"
    assert specs["discipline--0"]["label"] == "Computer Science"
    assert specs["degree--0"]["label"] == "Bachelor of Science"
    # exactly the three education fields, nothing fabricated
    assert set(specs) == {"school--0", "discipline--0", "degree--0"}


def test_plan_education_wins_over_personal():
    # The dryrun-resolved education_panel (carried as plan['_education']) takes
    # precedence over personal-info for any present key.
    plan = {"_education": {"school": "MIT", "degree": "Master of Science"}}
    specs = _by_id(g.plan_education_specs(plan, personal=PERSONAL))
    assert specs["school--0"]["label"] == "MIT"            # plan wins
    assert specs["degree--0"]["label"] == "Master of Science"  # plan wins
    # discipline absent from plan -> personal-info fills it (no gap)
    assert specs["discipline--0"]["label"] == "Computer Science"


def test_dryrun_education_panel_key_shapes_map():
    # The dryrun education_panel uses discipline= / degree= keys; make sure they
    # map to discipline--0 / degree--0 (regression: don't only read 'major').
    plan = {"_education": {
        "school": "University of Houston",
        "degree": "Bachelor's degree",
        "discipline": "Computer Science",
    }}
    specs = _by_id(g.plan_education_specs(plan, personal={}))
    assert specs["school--0"]["label"] == "University of Houston"
    assert specs["discipline--0"]["label"] == "Computer Science"
    assert specs["degree--0"]["label"] == "Bachelor's degree"


def test_education_no_values_emits_nothing():
    # No plan education + no personal education -> no specs (never fabricate).
    assert g.plan_education_specs({}, personal={}) == []
    assert g.plan_education_specs({"_education": {}}, personal={"education": {}}) == []


def test_education_blank_values_skipped():
    plan = {"_education": {"school": "  ", "degree": None, "major": "Computer Science"}}
    specs = _by_id(g.plan_education_specs(plan, personal={}))
    # blank/None school+degree dropped; only the real discipline survives
    assert "school--0" not in specs
    assert "degree--0" not in specs
    assert specs["discipline--0"]["label"] == "Computer Science"


# ---------------------------------------------------------------------------
# Location id-mismatch self-heal
# ---------------------------------------------------------------------------

def test_location_typeahead_from_text_fields_dict():
    plan = {"text_fields": {"location": "Kirkland, WA", "first_name": "Cyrus"}}
    spec = g.plan_location_typeahead_spec(plan)
    assert spec == {"id": "candidate-location", "label": "Kirkland, WA"}


def test_location_typeahead_from_text_fields_list_shape():
    # Ashby-style list-of-dicts text_fields shape is flattened correctly.
    plan = {"text_fields": [{"location": "Kirkland, WA"}, {"first_name": "Cyrus"}]}
    spec = g.plan_location_typeahead_spec(plan)
    assert spec["id"] == "candidate-location"
    assert spec["label"] == "Kirkland, WA"


def test_location_skipped_when_already_staged_in_country_dropdowns():
    # greenhouse_filler.build_plan already adds candidate-location to
    # country_dropdowns -> don't double-drive it.
    plan = {
        "text_fields": {"location": "Kirkland, WA"},
        "country_dropdowns": [{"id": "candidate-location", "label": "Kirkland, WA"}],
    }
    assert g.plan_location_typeahead_spec(plan) is None


def test_location_none_when_no_location_value():
    assert g.plan_location_typeahead_spec({"text_fields": {"first_name": "Cyrus"}}) is None
    assert g.plan_location_typeahead_spec({"text_fields": {"location": "   "}}) is None
    assert g.plan_location_typeahead_spec({}) is None


def test_country_typeahead_not_clobbered_by_location_heal():
    # A real country typeahead staged alongside a location value: location heal
    # still emits candidate-location (country is a different id, both wanted).
    plan = {
        "text_fields": {"location": "Kirkland, WA"},
        "country_dropdowns": [{"id": "country", "label": "United States"}],
    }
    spec = g.plan_location_typeahead_spec(plan)
    assert spec == {"id": "candidate-location", "label": "Kirkland, WA"}
