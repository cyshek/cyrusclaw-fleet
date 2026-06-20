#!/usr/bin/env python3
"""996 / extreme-hours LABEL handling (Cyrus directive 2026-06-08, REVERSED same day).

A "996" / extreme-hours schedule question (e.g. Lance 2594/2595) is DETECTED but
AUTO-ANSWERED AFFIRMATIVELY -- it is NOT banked to Cyrus. Rationale (Cyrus 2026-06-08):
applying != committing; a screening checkbox binds him to nothing; ~99% of apps
auto-reject regardless and the ~1% that reach an interview surface real
hours/comp/expectations THERE, where he decides with full context. So the engine
auto-answers to MAXIMIZE advancing the application (answer_yes) and logs what it
auto-answered, instead of manufacturing a no-stakes "needs Cyrus" decision.

Detection still lives at the single matcher chokepoint greenhouse_dryrun.find_resolver(),
so it covers BOTH Greenhouse and Ashby (Ashby splices into gh.LABEL_RULES and resolves
through the same matcher). The earlier "return None -> bank to Cyrus" behavior was
reversed to "return answer_yes -> auto-answer + audit-log."
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("greenhouse_dryrun", HERE / "greenhouse_dryrun.py")
gh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gh)


def test_bare_996_auto_answers_yes():
    # Reversed behavior: extreme-hours questions auto-answer affirmatively now.
    assert gh.find_resolver("Are you willing to work 996?") == "answer_yes"


def test_996_with_gloss_auto_answers_yes():
    # The gloss contains "6 days a week"; either way (the explicit guard OR the
    # office-attendance rule) the desired outcome is the SAME now: an affirmative.
    label = "Are you comfortable working 996 (9am-9pm, 6 days a week)?"
    assert gh.find_resolver(label) == "answer_yes", (
        "996 label should auto-answer affirmatively to best-advance the application "
        "(applying != committing; the real hours call happens at interview)"
    )


def test_9_9_6_dashed_variants_auto_answer_yes():
    for label in (
        "Comfortable with a 9-9-6 schedule?",
        "This role expects 9am to 9pm, six days a week. OK?",
        "Are you OK with a ~72 hour work week?",
        "Willing to commit to a 6-day work week?",
    ):
        assert gh.find_resolver(label) == "answer_yes", (
            f"extreme-hours label should auto-answer affirmatively: {label!r}"
        )


def test_normal_office_attendance_still_resolves_yes():
    # Regression: ordinary onsite/attendance questions must still resolve to an
    # AFFIRMATIVE office-attendance answer (answer_yes or ack_in_office, both truthful
    # US-onsite affirmatives).
    affirmative = {"answer_yes", "ack_in_office"}
    for label in (
        "Are you able to come into the office 3 days a week?",
        "This role is onsite 4 days per week in our SF office — are you able to?",
    ):
        key = gh.find_resolver(label)
        assert key in affirmative, (
            f"normal office-attendance label should resolve to an affirmative "
            f"({affirmative}), got {key!r} for {label!r}"
        )


def test_detection_predicate_still_fires():
    # The DETECTION is retained (it drives the audit log + is useful), even though the
    # action changed from bank -> auto-answer.
    assert gh._is_extreme_hours_label("willing to work 996")
    assert gh._is_extreme_hours_label("9am-9pm, 6 days a week")
    assert not gh._is_extreme_hours_label("come into the office 3 days a week")


def test_extreme_hours_field_is_flagged_and_resolved():
    # End-to-end through resolve_field: an extreme-hours required question should come
    # back FILLED (not unresolved) AND carry the auto_answered_extreme_hours audit flag.
    personal = {}
    field = {"name": "q_996", "type": "boolean", "values": [
        {"label": "Yes", "value": "1"}, {"label": "No", "value": "0"}]}
    out = gh.resolve_field(personal, "Are you willing to work 996 (9am-9pm, 6 days a week)?",
                           True, field)
    assert out.get("auto_answered_extreme_hours") is True, out
    assert out["status"] == "filled", f"expected filled, got {out['status']!r}: {out}"


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    sys.exit(1 if failed else 0)
