"""LABEL_RULES additions for YC-batch custom questions (2026-06-03)."""
import greenhouse_dryrun as g


def test_legal_birth_name_maps_to_full_name():
    assert g.find_resolver(
        "Please provide your full legal birth name (as seen on government-issued ID)"
    ) == "full_name"
    assert g.find_resolver("Full legal name") == "full_name"


def test_mailing_address_maps_to_city_state():
    assert g.find_resolver(
        "Please provide full mailing address (permanent & shipping)"
    ) == "city_state"
    assert g.find_resolver("Permanent address") == "city_state"


def test_job_code_number_maps_to_optional_blank():
    assert g.find_resolver(
        "Please indicate the job code number in the job posting here."
    ) == "optional_blank"


def test_no_regression_plain_identity_fields():
    assert g.find_resolver("First Name") == "first_name"
    assert g.find_resolver("Last Name") == "last_name"
    assert g.find_resolver("City") == "city"
    # 'name' single-word should NOT be hijacked by full-name phrase rules
    assert g.find_resolver("Preferred Name") == "preferred_name"


def test_expected_base_compensation_maps_to_compensation():
    import greenhouse_dryrun as g
    assert g.find_resolver("What is your expected base compensation ?") == "compensation"
    assert g.find_resolver("Expected Salary") == "compensation"
    assert g.find_resolver("Salary Requirement") == "compensation"


def test_annual_compensation_variants_map():
    import greenhouse_dryrun as g
    for l in ["What is your expected annual compensation in USD?",
              "Annual base salary", "Salary range", "Compensation expectations",
              "Target compensation"]:
        assert g.find_resolver(l) == "compensation", l


def test_total_and_abbreviated_comp_variants_map():
    """Cohort-close (2026-06-08, EliseAI 2727 / Dash0 2758 audit).

    The cached EliseAI/Dash0 dryruns proved the comp field already resolves to
    'Open to discuss' (ready_to_submit) — the old "field-walker drops comp"
    block_reason was a misdiagnosis. But a coverage sweep found 2 real MISSes:
    'expected TOTAL compensation' / bare 'total compensation' (no
    'expectations' suffix) and the abbreviated 'comp expectations'/'comp
    range'. These now map; verified via BOTH the GH rules and the Ashby
    combined-rules path (the one EliseAI/Dash0 actually use).
    """
    import greenhouse_dryrun as g
    import ashby_dryrun as a
    newly_covered = [
        "Expected total compensation",
        "Total compensation expectations",
        "What are your comp expectations?",
        "Comp range (USD)",
        "Compensation range you're targeting",
    ]
    for l in newly_covered:
        assert g.find_resolver(l) == "compensation", f"GH miss: {l!r}"
        assert a.find_resolver(l) == "compensation", f"Ashby miss: {l!r}"
    # Regression: the exact EliseAI 2727 / Dash0 comp label still resolves and
    # the resolver yields a non-empty honest value (so it is never an
    # 'absent from plan' blocker again).
    eliseai_label = "Please provide a range of your compensation expectations."
    assert a.find_resolver(eliseai_label) == "compensation"
    status, value, _src = g.RESOLVERS["compensation"]({"preferences": {}}, {})
    assert status == "ok" and value == "Open to discuss"


def test_total_comp_needles_do_not_overmatch_non_comp_labels():
    """Guard: the broad 'total compensation' / 'comp range' needles must not
    swallow unrelated labels (e.g. years-of-experience, work-auth)."""
    import greenhouse_dryrun as g
    assert g.find_resolver("Total years of experience") != "compensation"
    assert g.find_resolver(
        "Are you legally authorized to work in the United States?"
    ) != "compensation"
    assert g.find_resolver("How did you hear about us?") != "compensation"
