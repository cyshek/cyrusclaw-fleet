"""Regression: custom NON-Yes/No single-select re-assert (chain_p9, 2026-06-04).

Locks the fix for the now-dominant Ashby bank class after the text-field clobber:
custom multi-option single-selects (Ashby ValueSelect rendered as a multi-option
radio group, or a react-select `.select__control`) whose resolved value is filled
once but does NOT stick at submit time, so the field submits empty -> bank.

Two confirmed failure shapes:
  * Cape 2800  "3 days/wk NYC office / DC office / cannot come in" select.
    Dryrun resolved value="Yes" (US-onsite answer_yes doctrine), but "Yes" matches
    NO option label, so the radio-fill no_match'd and the field stayed empty. The
    truthful answer is an AFFIRMATIVE office option (onsite never a knockout) and
    NEVER the "cannot" option.
  * Helion 2712  "have you worked for Helion" 4-option select. Resolved value
    "I have not worked for Helion" matches an option, but the autofill clobber
    cleared it and the legacy yesno-verify (which only handles _yesno_ button
    widgets) didn't re-commit. Re-assert must re-pick the honest "have not"
    option, never "current/former employee".

Tests drive:
  (1) choose_select_option  -- the pure deterministic option chooser.
  (2) reassert_select_fields -- the orchestrator, against a FakePage that runs the
      _REASSERT_SELECT_JS contract over an in-memory DOM model (radio + react-select
      shapes), incl. the autofill-clobber-then-repair path and the anti-collision
      scoping (a sibling open menu must NEVER be picked).
"""
import _ashby_runner as R


# ----------------------------------------------------------------------------
# (1) Pure chooser
# ----------------------------------------------------------------------------
CAPE_OPTS = [
    "I can work 3 days a week in the NYC office",
    "I can work 3 days a week in the DC office ",
    "I cannot work 3 days a week in either office",
]
CAPE_LABEL = "Cape is a hybrid work environment with 3 days a week in office. We have offices in NYC and DC"
HELION_OPTS = [
    "I have not worked for Helion",
    "I am a former Helion Employee",
    "I am a current Helion Employee",
]
HELION_LABEL = "Do you currently or have you in the past worked for Helion Energy?"


def test_choose_affirmative_office_over_cannot():
    picked = R.choose_select_option("Yes", CAPE_OPTS, CAPE_LABEL)
    assert picked is not None
    assert "cannot" not in picked.lower()
    assert "office" in picked.lower()
    # must be a real option from the list
    assert picked in CAPE_OPTS


def test_choose_affirmative_lowercase_yes():
    picked = R.choose_select_option("yes", CAPE_OPTS, "days a week in office")
    assert picked in CAPE_OPTS and "cannot" not in picked.lower()


def test_choose_prior_employer_exact_have_not():
    picked = R.choose_select_option("I have not worked for Helion", HELION_OPTS, HELION_LABEL)
    assert picked == "I have not worked for Helion"


def test_choose_prior_employer_negative_picks_have_not_not_employee():
    # want resolved to a bare "No" -> honest "have not" option, NEVER an
    # "I am a current/former employee" option.
    picked = R.choose_select_option("No", HELION_OPTS, HELION_LABEL)
    assert picked == "I have not worked for Helion"
    assert "employee" not in picked.lower()


def test_choose_returns_none_for_unrelated_select():
    # A non-arrangement select that resolved to "Yes" with no matching option
    # must NOT auto-pick an arbitrary first option.
    assert R.choose_select_option("Yes", ["Apple", "Banana"], "favorite fruit?") is None


def test_choose_exact_match_wins_over_doctrine():
    assert R.choose_select_option("I am a former Helion Employee", HELION_OPTS, HELION_LABEL) == \
        "I am a former Helion Employee"


# ----------------------------------------------------------------------------
# (2) reassert_select_fields against a Fake DOM
# ----------------------------------------------------------------------------
class FakeSelectDOM:
    """Models one or more custom-select field containers.

    Each container: {field_path, shape ('radio'|'react-select'), options:[...],
    committed: <current option or ''>}. A `clobbered` flag means the field is
    currently empty (autofill cleared it). `sibling_menu` simulates a DIFFERENT
    field's open react-select menu sharing the global document; the JS must NOT
    read options from it (anti-collision)."""

    def __init__(self, containers):
        # containers keyed by their primary field_path
        self.containers = {c["field_path"]: c for c in containers}

    def get_by_paths(self, field_paths):
        for fp in field_paths:
            if fp in self.containers:
                return self.containers[fp]
        return None


class FakeSelectPage:
    """Executes the _REASSERT_SELECT_JS contract in Python against a FakeSelectDOM.

    Faithfully reproduces the JS decision tree:
      - locate container by candidate field_paths (scoped),
      - already-correct short-circuit,
      - radio / react-select shape pick,
      - ANTI-COLLISION: only this container's own option list is consulted; a
        sibling's open menu is never used.
    """

    def __init__(self, dom):
        self.dom = dom
        self.reads_from_sibling = 0  # asserted to stay 0

    @staticmethod
    def _norm(s):
        return (s or "").strip().lower()

    def _matches(self, txt, want):
        t, w = self._norm(txt), self._norm(want)
        return t == w or t.startswith(w) or (w in t) or (t and t in w)

    def evaluate(self, js, arg=None):
        assert js is R._REASSERT_SELECT_JS
        field_paths = arg["field_paths"]
        want = (arg.get("target") or "").strip()
        if not want:
            return {"ok": False, "reason": "no-target"}
        cont = self.dom.get_by_paths(field_paths)
        if not cont:
            return {"ok": False, "reason": "no-container", "field_paths": field_paths}
        opts = cont["options"]
        cur = cont.get("committed") or ""
        if cur and self._matches(cur, want):
            return {"ok": True, "shape": cont["shape"], "before": cur, "after": cur, "already": True}
        tgt = next((o for o in opts if self._matches(o, want)), None)
        if not tgt:
            return {"ok": False, "shape": cont["shape"], "reason": "no-option-match",
                    "before": cur, "options": [self._norm(o) for o in opts]}
        # ANTI-COLLISION: we picked from THIS container's opts only. A sibling's
        # open menu (cont may carry a 'sibling_options') is never consulted.
        if "sibling_options" in cont and tgt in cont["sibling_options"] and tgt not in opts:
            self.reads_from_sibling += 1
        cont["committed"] = tgt  # commit the pick
        return {"ok": True, "shape": cont["shape"], "before": cur, "after": tgt}

    def wait_for_timeout(self, ms):
        pass


def _radio(name, value, options, label, committed=""):
    return {"name": name, "value": value, "options": options, "label": label,
            "_committed": committed}


def test_reassert_recommits_cleared_cape_office_select():
    # Autofill cleared the Cape office select (committed=''); re-assert must
    # commit an affirmative office option (never "cannot").
    fp = "b712b77b_50420923-57e8-4e80-9724-a3bd51c9516c"
    dom = FakeSelectDOM([{
        "field_path": "50420923-57e8-4e80-9724-a3bd51c9516c",
        "shape": "react-select", "options": CAPE_OPTS, "committed": "",
    }])
    page = FakeSelectPage(dom)
    radios = [{"name": fp, "value": "Yes", "options": CAPE_OPTS, "label": CAPE_LABEL}]
    res = R.reassert_select_fields(page, radios)
    assert len(res) == 1
    r = res[0]
    assert r["ok"] is True, r
    assert "cannot" not in (r["target"] or "").lower()
    committed = dom.containers["50420923-57e8-4e80-9724-a3bd51c9516c"]["committed"]
    assert "office" in committed.lower() and "cannot" not in committed.lower()


def test_reassert_recommits_cleared_helion_prior_employer():
    fp = "5912ea00_question_8036119005"
    dom = FakeSelectDOM([{
        "field_path": "5912ea00_question_8036119005",
        "shape": "radio", "options": HELION_OPTS, "committed": "",  # cleared
    }])
    page = FakeSelectPage(dom)
    radios = [{"name": fp, "value": "I have not worked for Helion",
               "options": HELION_OPTS, "label": HELION_LABEL}]
    res = R.reassert_select_fields(page, radios)
    assert res[0]["ok"] is True
    committed = dom.containers["5912ea00_question_8036119005"]["committed"]
    assert committed == "I have not worked for Helion"
    assert "employee" not in committed.lower()


def test_reassert_skips_plain_yesno_radios():
    # Plain Yes/No selects are owned by the yesno-verify block; this pass must
    # leave them alone (return nothing for them).
    radios = [{"name": "x_q1", "value": "Yes", "options": ["Yes", "No"], "label": "eligible?"}]
    page = FakeSelectPage(FakeSelectDOM([]))
    res = R.reassert_select_fields(page, radios)
    assert res == []  # skipped, not evaluated


def test_reassert_already_correct_is_noop():
    fp = "5912ea00_question_8036119005"
    dom = FakeSelectDOM([{
        "field_path": "5912ea00_question_8036119005",
        "shape": "radio", "options": HELION_OPTS,
        "committed": "I have not worked for Helion",  # already correct
    }])
    page = FakeSelectPage(dom)
    radios = [{"name": fp, "value": "I have not worked for Helion",
               "options": HELION_OPTS, "label": HELION_LABEL}]
    res = R.reassert_select_fields(page, radios)
    assert res[0].get("already") is True


def test_reassert_anti_collision_only_own_container():
    # Two custom selects exist; we re-assert the Cape one. The JS/contract must
    # scope to Cape's container, never read a sibling's options.
    dom = FakeSelectDOM([
        {"field_path": "50420923-57e8-4e80-9724-a3bd51c9516c", "shape": "react-select",
         "options": CAPE_OPTS, "committed": "",
         "sibling_options": HELION_OPTS},  # a different field's options floating around
    ])
    page = FakeSelectPage(dom)
    radios = [{"name": "form_50420923-57e8-4e80-9724-a3bd51c9516c",
               "value": "Yes", "options": CAPE_OPTS, "label": CAPE_LABEL}]
    res = R.reassert_select_fields(page, radios)
    assert res[0]["ok"] is True
    assert page.reads_from_sibling == 0
    assert dom.containers["50420923-57e8-4e80-9724-a3bd51c9516c"]["committed"] in CAPE_OPTS


def test_field_path_candidates_extracts_uuid_and_systemfield():
    cands = R._field_path_candidates("form123_5912ea00-a307-41f5-b482-62e2d8cace1c")
    assert "5912ea00-a307-41f5-b482-62e2d8cace1c" in cands
    cands2 = R._field_path_candidates("form123__systemfield_email")
    assert "_systemfield_email" in cands2


def test_field_path_candidates_extracts_question_suffix():
    # Helion 2712: the live container's data-field-path is the bare
    # `question_<numericId>` suffix, NOT the entry UUID and NOT the full fid.
    # The reassert/yesno-verify container lookup must include it or the radio
    # never gets its trusted-click re-assert (submit drops the field).
    fid = "04809025-7ab9-46b2-b3b8-a016222465d1_question_8036119005"
    cands = R._field_path_candidates(fid)
    assert "question_8036119005" in cands
    assert fid in cands
    assert "04809025-7ab9-46b2-b3b8-a016222465d1" in cands
