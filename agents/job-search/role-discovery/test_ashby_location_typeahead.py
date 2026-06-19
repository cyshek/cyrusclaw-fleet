"""chain_p14 (2026-06-10): Ashby Location typeahead robustness across tenant
DOM variants. Locks the fix for the "Missing entry for required field: Location"
class that bounced 3 rows that PASSED the reCAPTCHA score gate via residential
egress (938 ElevenLabs, 1112 Higharc, 1235 Liquid AI).

Two distinct DOM variants were mishandled:

  A. multi_value_single_select Location SELECT (1112 Higharc, 1235 Liquid AI):
     _ashby_type=ValueSelect, label "Where are you currently located?", discrete
     REGION options (NOT a geo-typeahead). The dryrun resolved value="Kirkland, WA"
     (home city,state) which matched NO option -> choose_select_option returned
     None -> the radio never got picked -> server bounced "Missing Location".
     FIX: a location-REGION ladder in choose_select_option maps a US home
     location to the best US-region option (US + open-to-relocation preferred).

  B. input_text / _ashby_type=Location geo-combobox (938 ElevenLabs):
     _LOCATION_COMBO_FILL_JS logged no-container / no-input because its
     container+input locator was too narrow (required input[role=combobox] and a
     data-field-path tail match). FIX: a broadened locator strategy ladder
     (tail -> location-ish label -> systemfield-location -> location-placeholder
     input) that accepts a bare input[type=text] combobox.

Tests:
  (1) choose_select_option region ladder  -- pure deterministic chooser.
  (2) _choose_location_region_option       -- the helper directly.
  (3) the broadened combobox container/input locator contract against a Fake DOM
      (variant resolution, the no-container fallback path, read-back-verify, and a
      NO-OP / no-false-pick on a standard DOM where the existing path works).
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_ashby_runner", HERE / "_ashby_runner.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


# real option sets captured from the dryrun JSON of the 3 affected rows
HIGHARC_OPTS = ["United States", "Canada", "South or Central America", "Europe", "Other"]
LIQUID_OPTS = [
    "San Francisco / Bay area", "Boston metro area",
    "Other US location (open to relocation)", "Other US location (remote only)",
    "Outside the US (open to relocation)", "Outside the US (remote only)",
]
LOC_LABEL = "Where are you currently located?"
HOME = "Kirkland, WA"  # personal-info.json address.city + state


# ---------------------------------------------------------------------------
# (1) + (2)  pure region-ladder chooser
# ---------------------------------------------------------------------------
def test_higharc_kirkland_maps_to_united_states():
    picked = R.choose_select_option(HOME, HIGHARC_OPTS, LOC_LABEL)
    assert picked == "United States"
    assert picked in HIGHARC_OPTS


def test_liquid_kirkland_maps_to_us_open_to_relocation():
    # US + open to relocation maximizes advancing (relocation never a knockout),
    # and must NEVER pick an "Outside the US" option for a US home.
    picked = R.choose_select_option(HOME, LIQUID_OPTS, LOC_LABEL)
    assert picked == "Other US location (open to relocation)"
    assert "outside the us" not in picked.lower()
    assert picked in LIQUID_OPTS


def test_region_prefers_relocation_open_over_remote_only():
    # Given both "open to relocation" and "remote only" US options, prefer the
    # relocation-open one (maximizes advancing; relocation is never a knockout).
    opts = ["Other US location (remote only)", "Other US location (open to relocation)"]
    picked = R.choose_select_option(HOME, opts, LOC_LABEL)
    assert "open to relocation" in picked.lower()


def test_region_helper_direct_higharc_and_liquid():
    assert R._choose_location_region_option(HOME, HIGHARC_OPTS, LOC_LABEL) == "United States"
    assert R._choose_location_region_option(HOME, LIQUID_OPTS, LOC_LABEL) == \
        "Other US location (open to relocation)"


def test_region_fires_on_options_even_without_location_label():
    # Even if the label is unhelpful, an option set that is clearly regional
    # (>=2 region hints) still triggers the ladder.
    assert R._choose_location_region_option(HOME, HIGHARC_OPTS, "Question 7") == "United States"


def test_region_continents_only_picks_americas_for_us_home():
    opts = ["North America", "South America", "Europe", "Asia", "Africa"]
    picked = R.choose_select_option(HOME, opts, LOC_LABEL)
    assert picked == "North America"


# --- safety / no-false-pick guards ---
def test_foreign_location_never_forced_to_us_option():
    # A non-US home string must NOT be mapped to a US option.
    assert R.choose_select_option("London, UK", LIQUID_OPTS, LOC_LABEL) is None
    assert R.choose_select_option("Toronto, ON", LIQUID_OPTS, LOC_LABEL) is None
    assert R.choose_select_option("Berlin, Germany", HIGHARC_OPTS, LOC_LABEL) is None


def test_explicit_outside_us_want_not_forced_us():
    assert R._choose_location_region_option("Outside the US", LIQUID_OPTS, LOC_LABEL) is None


def test_empty_want_returns_none():
    assert R.choose_select_option("", HIGHARC_OPTS, LOC_LABEL) is None
    assert R._choose_location_region_option("", HIGHARC_OPTS, LOC_LABEL) is None


def test_non_region_select_not_touched_by_region_ladder():
    # An unrelated select (fruit) whose options are NOT regional and whose label
    # is not a location question must NOT get a region pick.
    assert R.choose_select_option(HOME, ["Apple", "Banana", "Cherry"], "favorite fruit?") is None
    assert R._choose_location_region_option(HOME, ["Apple", "Banana"], "favorite fruit?") is None


def test_exact_match_still_wins_over_region_ladder():
    # Regression: if the resolved value DOES match an option (the permissive
    # cohort), the plain ladder must win before the region ladder ever runs.
    assert R.choose_select_option("Canada", HIGHARC_OPTS, LOC_LABEL) == "Canada"
    assert R.choose_select_option("Europe", HIGHARC_OPTS, LOC_LABEL) == "Europe"
    assert R.choose_select_option("Boston metro area", LIQUID_OPTS, LOC_LABEL) == "Boston metro area"


def test_region_ladder_does_not_break_arrangement_doctrine():
    # Cape-class onsite arrangement selects (from the existing suite) must still
    # resolve via the affirmative-office ladder, unaffected by the region ladder.
    cape = [
        "I can work 3 days a week in the NYC office",
        "I can work 3 days a week in the DC office ",
        "I cannot work 3 days a week in either office",
    ]
    picked = R.choose_select_option("Yes", cape,
                                    "Cape is a hybrid work environment with offices in NYC and DC")
    assert picked is not None and "cannot" not in picked.lower() and "office" in picked.lower()


def test_us_option_detector():
    assert R._looks_like_us_option("united states")
    assert R._looks_like_us_option("other us location (open to relocation)")
    assert R._looks_like_us_option("us location")
    assert not R._looks_like_us_option("outside the us (remote only)")
    assert not R._looks_like_us_option("canada")
    assert not R._looks_like_us_option("europe")
    # must not match a stray "us" inside an unrelated word
    assert not R._looks_like_us_option("discuss later")
    assert not R._looks_like_us_option("austin office")  # "us" inside austin


# ---------------------------------------------------------------------------
# (3)  broadened _LOCATION_COMBO_FILL_JS container/input locator contract
#
# The live JS needs a browser; here we re-implement its CONTAINER+INPUT
# resolution decision tree in Python over an in-memory DOM model, faithfully
# mirroring the strategy ladder, and assert the variant cases resolve.
# ---------------------------------------------------------------------------
import re as _re

_LBL_RE = _re.compile(
    r"location|working from|will you be based|are you based|are you located|"
    r"will you work from|where will you be|based out of|where are you|"
    r"currently located|city|country|where do you live", _re.I)
_PH_RE = _re.compile(r"start typing|location|city|town|country|where|address", _re.I)


class FakeInput:
    def __init__(self, role=None, itype="text", placeholder="", aria_label=""):
        self.role = role
        self.type = itype
        self.placeholder = placeholder
        self.aria_label = aria_label

    def is_text_input(self):
        return self.type.lower() not in ("hidden", "checkbox", "radio", "file", "submit", "button")


class FakeFieldContainer:
    """Models one Ashby field container: a data-field-path, an optional <label>,
    and a list of inputs."""
    def __init__(self, field_path, label="", inputs=None):
        self.field_path = field_path
        self.label = label
        self.inputs = inputs or []

    # mirrors comboIn(root): role=combobox -> type=text -> any text input ->
    # placeholder/aria-label location-y text input
    def combo_in(self):
        for i in self.inputs:
            if i.role == "combobox":
                return i
        for i in self.inputs:
            if i.type == "text":
                return i
        for i in self.inputs:
            if i.is_text_input():
                return i
        for i in self.inputs:
            if i.is_text_input() and _PH_RE.search((i.placeholder or "") + " " + (i.aria_label or "")):
                return i
        return None


class FakeComboDOM:
    """Re-implements the JS container-resolution ladder over a list of
    FakeFieldContainers. Returns the resolved (container, input) or
    (None, reason)."""
    def __init__(self, containers):
        self.containers = containers

    def resolve(self, tail):
        # (1) field-path endsWith(tail) AND has a usable input
        for c in self.containers:
            if c.field_path.endswith(tail) and c.combo_in():
                return c, c.combo_in(), None
        # (1b) tail match even without a usable input yet
        for c in self.containers:
            if c.field_path.endswith(tail):
                inp = c.combo_in()
                if inp:
                    return c, inp, None
        # (2) location-ish label AND usable input
        for c in self.containers:
            if c.label and _LBL_RE.search(c.label) and c.combo_in():
                return c, c.combo_in(), None
        # (3) systemfield-location container
        for c in self.containers:
            if c.field_path.endswith("_systemfield_location") and c.combo_in():
                return c, c.combo_in(), None
        # (4) container holding a location-placeholder input
        for c in self.containers:
            for i in c.inputs:
                if i.is_text_input() and _PH_RE.search((i.placeholder or "") + " " + (i.aria_label or "")):
                    return c, i, None
        return None, None, "no-container"


def test_combo_standard_role_combobox_tail_match():
    # The permissive cohort: a role=combobox whose data-field-path ends with the
    # parsed tail. Must resolve via strategy (1), unchanged behavior.
    tail = "6f1b584f-ba7d-47eb-a987-ae7e13a9c5d3"
    dom = FakeComboDOM([
        FakeFieldContainer("40fdd16c-..._" + tail, label="Location",
                           inputs=[FakeInput(role="combobox", placeholder="Start typing...")]),
    ])
    c, inp, reason = dom.resolve(tail)
    assert c is not None and inp is not None and reason is None
    assert inp.role == "combobox"


def test_combo_elevenlabs_variant_bare_text_input_no_role():
    # ElevenLabs 938 variant: the Location combobox is a bare input[type=text]
    # (NO role=combobox) with a "Start typing..." placeholder, label "Location".
    # The OLD locator (role=combobox-only) -> no-input/no-container. The
    # broadened ladder must resolve it via the text-input fallback.
    tail = "6f1b584f-ba7d-47eb-a987-ae7e13a9c5d3"
    dom = FakeComboDOM([
        FakeFieldContainer("40fdd16c-..._" + tail, label="Location",
                           inputs=[FakeInput(role=None, itype="text", placeholder="Start typing...")]),
    ])
    c, inp, reason = dom.resolve(tail)
    assert reason is None and inp is not None
    assert inp.type == "text" and inp.role is None


def test_combo_resolves_by_label_when_tail_mismatch():
    # data-field-path doesn't end with the parsed tail (structure variant), but a
    # container's label reads location-y and it has a usable input.
    dom = FakeComboDOM([
        FakeFieldContainer("some-other-structure-xyz", label="Where are you currently located?",
                           inputs=[FakeInput(role="combobox")]),
    ])
    c, inp, reason = dom.resolve("tail-that-matches-nothing")
    assert reason is None and inp is not None
    assert "located" in c.label.lower()


def test_combo_resolves_by_systemfield_location():
    dom = FakeComboDOM([
        FakeFieldContainer("entry123__systemfield_location", label="",
                           inputs=[FakeInput(itype="text", placeholder="City")]),
    ])
    c, inp, reason = dom.resolve("nope")
    assert reason is None and inp is not None
    assert c.field_path.endswith("_systemfield_location")


def test_combo_resolves_by_placeholder_input_no_label_no_tail():
    # Last-ditch: no tail match, no label, but an input with a location-y
    # placeholder exists somewhere -> strategy (4).
    dom = FakeComboDOM([
        FakeFieldContainer("mystery-field", label="",
                           inputs=[FakeInput(itype="text", placeholder="Start typing your location")]),
    ])
    c, inp, reason = dom.resolve("nope")
    assert reason is None and inp is not None


def test_combo_no_container_when_nothing_matches():
    # A form with only non-location text inputs and no location signals -> the
    # ladder must report no-container (integrity: never grab a random input).
    dom = FakeComboDOM([
        FakeFieldContainer("name-field", label="Full name",
                           inputs=[FakeInput(itype="text", placeholder="Your name")]),
        FakeFieldContainer("email-field", label="Email",
                           inputs=[FakeInput(itype="email", placeholder="you@example.com")]),
    ])
    c, inp, reason = dom.resolve("nope")
    assert c is None and reason == "no-container"


def test_combo_live_js_is_syntactically_present_and_broadened():
    # Guard: the broadened locator markers must be present in the live JS string
    # (catches an accidental revert of the fix).
    js = R._LOCATION_COMBO_FILL_JS
    assert "comboIn" in js
    assert "isTextInput" in js
    assert "_systemfield_location" in js
    assert "PH_RE" in js and "LBL_RE" in js
    # still integrity-guarded: only TYPE + pick, the no-exact-match guard stays
    assert "no-exact-match" in js


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
