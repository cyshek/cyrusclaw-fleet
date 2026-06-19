#!/usr/bin/env python3
"""Tests for _gh_submit.plan_remix_answers — the remix React-Select required-proxy
dropdown recovery pass (2026-06-03).

Covers the Anduril/Swayable/Astranis defense-contractor class: REQUIRED work-auth
/ clearance / export-control / sponsorship dropdowns that render with no
extractable boards-API label, so the dryrun never staged them and emptyRequired
blocked submit. We resolve the question text live, run it through the SAME
truthful resolver the dryrun uses, and commit.

No live browser / LLM: REMIX_SCAN output is stubbed; resolve_field is the real
greenhouse_dryrun one (deterministic) so we assert truthful answers end-to-end.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _gh_submit import plan_remix_answers, DEMO_SKIP_RE  # noqa: E402
from _gh_submit import _affirm_or_sole_option  # noqa: E402
from _gh_submit import plan_multiselect_commit_specs  # noqa: E402
from greenhouse_dryrun import PERSONAL_INFO_PATH, resolve_field  # noqa: E402

PERSONAL = json.loads(PERSONAL_INFO_PATH.read_text())


def _plan(scanned):
    return plan_remix_answers(scanned, PERSONAL, resolve_field=resolve_field)


def test_work_auth_commits_yes():
    r = _plan([{"id": "q1", "label": "Are you legally authorized to work in the US?",
               "options": ["Yes", "No"]}])
    assert r["commit"] == [{"id": "q1", "label": "Yes"}]
    assert r["unresolved"] == []


def test_sponsorship_commits_no_as_pass():
    # 'No' to a sponsorship-NEEDED question is the correct PASS, not a knockout.
    r = _plan([{"id": "q2",
                "label": "Will you now or in the future require visa sponsorship?",
                "options": ["Yes", "No"]}])
    assert r["commit"] == [{"id": "q2", "label": "No"}]
    assert r["unresolved"] == []


def test_itar_us_person_commits_yes():
    r = _plan([{"id": "q3", "label": "Are you a U.S. Person as defined by ITAR/EAR?",
               "options": ["Yes", "No"]}])
    assert r["commit"] == [{"id": "q3", "label": "Yes"}]


def test_deemed_export_affect_inverted_commits_no():
    # REGRESSION (2026-06-05): Pure Storage / Everpure phrases the export-control
    # question INVERTED -- "Does the deemed export rule AFFECT your employment?"
    # For a US citizen the correct answer is NO (the rule does not affect them).
    # The old resolver returned "Yes" for ALL export phrasings -> Pure Storage
    # read it as "needs a deemed-export license" and AUTO-REJECTED 5 real apps.
    # The resolver must detect the inverted polarity and commit "No".
    r = _plan([{"id": "q_de",
                "label": "Does the deemed export rule affect your employment by Pure?",
                "options": ["Yes", "No"]}])
    assert r["commit"] == [{"id": "q_de", "label": "No"}], r
    assert r["unresolved"] == []


def test_require_export_license_inverted_commits_no():
    # Sibling inverted phrasings must also resolve to No for a US citizen.
    for lbl in ("Do you require a deemed export license?",
                "Are you subject to U.S. export controls?",
                "Are you a foreign person under U.S. export regulations?"):
        r = _plan([{"id": "qx", "label": lbl, "options": ["Yes", "No"]}])
        assert r["commit"] == [{"id": "qx", "label": "No"}], (lbl, r)


def test_clearance_eligibility_resolves():
    r = _plan([{"id": "q4", "label": "Clearance Eligibility",
               "options": ["Eligible", "Not Eligible"]}])
    assert r["commit"] and r["commit"][0]["id"] == "q4"
    assert r["commit"][0]["label"] in ("Eligible",)


def test_active_clearance_no():
    r = _plan([{"id": "q5", "label": "Do you currently hold an active TS/SCI clearance?",
               "options": ["Yes", "No"]}])
    assert r["commit"] == [{"id": "q5", "label": "No"}]


def test_us_commute_distance_resolves_yes():
    # Policy change 2026-06-03 (Cyrus): US onsite/commute/relocation is NEVER a
    # knockout — Cyrus relocates anywhere in the USA. A US commuting-distance
    # question now resolves to Yes (was previously surfaced-unresolved).
    # (Non-US location stays a genuine knockout via the classifier, not here.)
    r = _plan([{"id": "q6",
                "label": "Are you within commuting distance to our SF or NY office?",
                "options": ["Yes", "No"]}])
    assert r["commit"] == [{"id": "q6", "label": "Yes"}]
    assert r["unresolved"] == []


def test_skips_blank_label_and_id():
    r = _plan([{"id": "", "label": "Are you authorized to work?", "options": ["Yes", "No"]},
               {"id": "q7", "label": "", "options": ["Yes", "No"]}])
    assert r["commit"] == [] and r["unresolved"] == []


def test_multiple_mixed_batch():
    scanned = [
        {"id": "a", "label": "Are you authorized to work in the United States?",
         "options": ["Yes", "No"]},
        {"id": "b", "label": "Do you require employer sponsorship for a work visa?",
         "options": ["Yes", "No"]},
        {"id": "c", "label": "Some bespoke unmatched question about favorite color?",
         "options": ["Red", "Blue"]},
    ]
    r = _plan(scanned)
    commit_ids = {c["id"]: c["label"] for c in r["commit"]}
    assert commit_ids.get("a") == "Yes"
    assert commit_ids.get("b") == "No"
    assert "c" not in commit_ids
    assert any(u["id"] == "c" for u in r["unresolved"])


def test_demo_skip_re_matches_demographics():
    # Sanity: the regex handed to REMIX_SCAN really does catch demographic labels
    # (those are handled by DECLINE, not by this recovery pass).
    import re
    rx = re.compile(DEMO_SKIP_RE, re.I)
    for lbl in ["Gender", "Race / Ethnicity", "Veteran Status",
                "Disability self-identification", "Preferred pronouns"]:
        assert rx.search(lbl), lbl
    # and does NOT eat a work-auth label
    assert not rx.search("Are you authorized to work in the US?")


def test_itar_us_person_sentence_options_picks_citizen():
    # Astranis-class export-control select: full-sentence options, not Yes/No.
    # US citizen -> must smart-match the citizen option, not fall to noopt.
    opts = ["I am a U.S. Citizen.",
            "I am a lawful permanent resident of the U.S. and Green Card Holder.",
            "I am a refugee under 8 U.S.C. 1157.",
            "None of the above."]
    r = _plan([{"id": "q9",
                "label": "For export-control purposes, are you a U.S. person?",
                "options": opts}])
    assert r["commit"] == [{"id": "q9", "label": "I am a U.S. Citizen."}]
    assert r["unresolved"] == []


# ---- batch4 (2026-06-04): forced-choice consent/affirmation commit ----
# Everlaw/Scopely/NiCE/AppLovin/Lila cohort: dryrun READY but submit bounced on
# emptyRequired because a single-option affirmation SELECT (Everlaw's lone
# "Agree") was never committed live. The recovery pass now force-commits a safe
# forced-choice (sole option, or all-affirmative) even when the resolver has no
# LABEL_RULES match, so emptyRequired clears and submit reaches /confirmation.

def test_everlaw_sole_agree_commits():
    # Everlaw 2759: lone "Agree" affirmation select. With the labeled affirmation
    # text the dryrun resolver (r_answer_yes affirmative-synonym) already resolves
    # it to "Agree"; either path is fine as long as it COMMITS (was empty before).
    r = _plan([{"id": "q_agree",
                "label": "I understand, affirm, and agree to the above.",
                "options": ["Agree"]}])
    assert len(r["commit"]) == 1
    assert r["commit"][0]["id"] == "q_agree"
    assert r["commit"][0]["label"] == "Agree"
    assert r["unresolved"] == []


def test_unlabeled_consent_select_uses_fallback():
    # When the label gives the resolver nothing to match (bespoke confidentiality
    # wording with a lone "Agree"), the forced-choice FALLBACK commits it.
    r = _plan([{"id": "q_cf",
                "label": "Zatproq foobar widget consent paragraph xyzzy.",
                "options": ["Agree"]}])
    assert r["commit"] == [{"id": "q_cf", "label": "Agree", "via": "affirm_or_sole"}]
    assert r["unresolved"] == []


def test_blank_label_sole_option_commits():
    # Blank-label required affirmation select (REMIX_SCAN can't recover label):
    # still force-commit the sole option so emptyRequired clears.
    r = _plan([{"id": "q_blank", "label": "", "options": ["Acknowledge"]}])
    assert r["commit"] == [{"id": "q_blank", "label": "Acknowledge",
                            "via": "affirm_or_sole"}]


def test_blank_label_real_yesno_not_committed():
    # A blank-label select with a REAL Yes/No (negative alternative present) is
    # NOT a forced choice -> never auto-committed (can't honestly answer it).
    r = _plan([{"id": "q_blank2", "label": "", "options": ["Yes", "No"]}])
    assert r["commit"] == []


def test_placeholder_plus_sole_agree_commits():
    r = _plan([{"id": "q_p", "label": "Confidentiality affirmation",
                "options": ["Select...", "Agree"]}])
    assert r["commit"] == [{"id": "q_p", "label": "Agree", "via": "affirm_or_sole"}]


def test_real_yesno_with_label_not_fabricated():
    # A genuinely-unmatched Yes/No biographical question must stay unresolved,
    # NOT be force-committed by the affirmation fallback (no negative tick).
    r = _plan([{"id": "q_bio",
                "label": "Some bespoke unmatched question about favorite color?",
                "options": ["Yes", "No"]}])
    assert r["commit"] == []
    assert any(u["id"] == "q_bio" for u in r["unresolved"])


def test_lone_negative_never_ticked():
    # A lone "Decline"/"No" option is NOT a consent we should tick.
    assert _affirm_or_sole_option(["No"]) is None
    assert _affirm_or_sole_option(["Decline to participate"]) is None


def test_affirm_helper_matrix():
    assert _affirm_or_sole_option(["Agree"]) == "Agree"
    assert _affirm_or_sole_option(["I confirm"]) == "I confirm"
    assert _affirm_or_sole_option(["I accept the terms"]) == "I accept the terms"
    assert _affirm_or_sole_option(["Agree", "I acknowledge"]) == "Agree"
    assert _affirm_or_sole_option(["Eligible", "Not Eligible"]) is None
    assert _affirm_or_sole_option(["Red", "Blue"]) is None
    assert _affirm_or_sole_option([]) is None


def test_remix_scan_keeps_blank_label_controls():
    # REMIX_SCAN must no longer discard a blank-label required select outright
    # (Everlaw-class affirmation controls render with no recoverable label); it
    # only skips a blank-label control that ALSO has no options.
    from pathlib import Path
    src = Path(__file__).with_name("_gh_submit.py").read_text()
    assert "if(label&&demo.test(label))continue" in src
    assert "if(!label&&!opts.length)continue" in src


# ---- 2026-06-04: required MULTI-SELECT force-commit (Raft + multiUnset cohort) ----
# The single-select/affirmation commit pass left required react-select MULTI
# widgets (preSubmitState.multiUnset) uncommitted -> server silently no-ops the
# submit. plan_multiselect_commit_specs builds MULTI_PICK specs ONLY from
# dryrun-RESOLVED values staged in plan['multi_checkboxes']; an unresolved
# multiselect is left alone (row stays banked, never fabricated).

def test_multiselect_commit_uses_resolved_plan_values():
    plan = {"multi_checkboxes": [
        {"id": "question_123[]", "legend_re": "Which products?",
         "values": ["Alpha", "Beta"]},
    ]}
    specs = plan_multiselect_commit_specs(plan, ["question_123[]"])
    assert specs == [{"id": "question_123[]", "label": ["Alpha", "Beta"]}]


def test_multiselect_commit_matches_bare_and_substring_ids():
    # Live hidden-input id may differ from the boards-API plan id by the "[]"
    # suffix or a wrapping prefix; match by bare id / substring either way.
    plan = {"multi_checkboxes": [
        {"id": "question_999", "values": ["X"]},
    ]}
    # multiUnset reports the []-suffixed live id
    assert plan_multiselect_commit_specs(plan, ["question_999[]"]) == \
        [{"id": "question_999[]", "label": ["X"]}]
    # and a prefixed live id still resolves
    assert plan_multiselect_commit_specs(plan, ["job_application_question_999"]) == \
        [{"id": "job_application_question_999", "label": ["X"]}]


def test_multiselect_commit_skips_unresolved():
    # A required multiselect flagged in multiUnset with NO resolved plan entry
    # (Raft's case: dryrun skipped it as unresolved) must NOT be fabricated.
    plan = {"multi_checkboxes": [{"id": "question_111", "values": ["Y"]}]}
    specs = plan_multiselect_commit_specs(plan, ["question_222"])  # different id
    assert specs == []


def test_multiselect_commit_empty_when_no_plan_bucket():
    # Raft itself: plan has no multi_checkboxes at all -> nothing to commit,
    # row stays banked. No crash, empty specs.
    assert plan_multiselect_commit_specs({}, ["question_1"]) == []
    assert plan_multiselect_commit_specs({"multi_checkboxes": None},
                                         ["question_1"]) == []
    assert plan_multiselect_commit_specs(
        {"multi_checkboxes": [{"id": "q", "values": ["A"]}]}, []) == []


def test_multiselect_commit_ignores_placeholder_key_and_empty_values():
    plan = {"multi_checkboxes": [
        {"id": "question_5", "values": []},        # resolved-but-empty -> skip
        {"id": "question_6", "values": ["Z"]},
    ]}
    # the generic 'multi-select' placeholder key (no hidden id) is ignored
    specs = plan_multiselect_commit_specs(
        plan, ["multi-select", "question_5", "question_6"])
    assert specs == [{"id": "question_6", "label": ["Z"]}]


def test_multiselect_commit_no_duplicate_specs():
    plan = {"multi_checkboxes": [{"id": "question_7", "values": ["A", "B"]}]}
    specs = plan_multiselect_commit_specs(plan, ["question_7", "question_7"])
    assert specs == [{"id": "question_7", "label": ["A", "B"]}]


def test_multi_pick_js_scopes_to_own_menu():
    # Anti-collision: MULTI_PICK must resolve options from THIS control's own
    # scoped menu (aria-controls/aria-owns or the wrapping container), not a
    # global option scan that could click a sibling react-select's open menu.
    from pathlib import Path
    src = Path(__file__).with_name("_gh_submit.py").read_text()
    assert "const scopedMenu=()=>" in src
    assert "aria-controls" in src and "aria-owns" in src
    # the submit runner must re-read presubmit state after committing multis
    assert "multiselect_commit" in src
    assert "plan_multiselect_commit_specs(plan, multi_unset)" in src


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
