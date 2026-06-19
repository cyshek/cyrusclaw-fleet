import greenhouse_dryrun as g

P = {"work_authorization": {"security_clearance": "none"}}

def test_clearance_eligibility_picks_eligible_not_hold_not_no():
    f = {"values": [
        {"label": "Yes, I hold an active U.S. security clearance"},
        {"label": "Yes, I am eligible for a U.S. security clearance"},
        {"label": "No"},
    ]}
    st, val, _ = g.r_clearance_eligibility(P, f)
    assert st == "ok"
    assert val == "Yes, I am eligible for a U.S. security clearance"

def test_clearance_level_held_picks_na_never():
    f = {"values": [
        {"label": "N/A - have never held U.S. security clearance"},
        {"label": "Confidential"}, {"label": "Secret"}, {"label": "Top Secret"},
    ]}
    st, val, _ = g.r_clearance_level_held(P, f)
    assert st == "ok"
    assert "never held" in val.lower()

def test_clearance_label_routing_order():
    # eligibility + level routes must win over the generic 'security clearance'
    assert g.find_resolver("CLEARANCE ELIGIBILITY - requires eligibility to obtain and maintain a U.S. security clearance") == "clearance_eligibility"
    assert g.find_resolver("If you have held a U.S. security clearance in the past, what clearance level have you held?") == "clearance_level_held"
    # generic active-clearance question stays on the existing path
    assert g.find_resolver("Do you have an active security clearance?") == "security_clearance"

def test_clearance_eligibility_no_options_fallback():
    st, val, _ = g.r_clearance_eligibility(P, {"values": []})
    assert st == "ok" and "eligible" in val.lower()
