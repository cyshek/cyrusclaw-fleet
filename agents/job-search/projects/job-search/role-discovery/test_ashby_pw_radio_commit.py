"""Regression: chain_p12 (2026-06-10, Klarity 1434) — labeled-radio single-selects
commit ONLY via a REAL Playwright trusted click, not synthetic events.

Locks the fix for the Klarity-class bank: Ashby `multi_value_single_select`
fields render as a labeled-radio group whose field controller records `savedValue`
(and fires op=ApiSetFormValue) ONLY for a trusted gesture. The synthetic-event
re-pick (_REASSERT_SELECT_JS) returns the DOM .checked but leaves the field
uncommitted, so reassert_select_fields must FALL BACK to _pw_click_radio_option
(page.locator(...).click(force=True)) which lands the value.

Drives:
  (1) _pw_click_radio_option happy path: locates the option input by
      [data-field-path]+label-text, clicks it, verifies committed (checked +
      value/saved set).
  (2) reassert_select_fields fallback: when the synthetic re-pick returns
      ok:False, the real-click fallback fires and the field ends up ok:True with
      committed_via='pw_click'.
"""
import _ashby_runner as R


# ---------------------------------------------------------------------------
# Fake DOM/page that models the Klarity labeled-radio widget for BOTH the
# _REASSERT_SELECT_JS contract and the _pw_click_radio_option contract.
# ---------------------------------------------------------------------------
class FakeLoc:
    def __init__(self, page, sel):
        self.page = page
        self.sel = sel

    def count(self):
        return 1 if self.page._sel_hits(self.sel) else 0

    def scroll_into_view_if_needed(self, timeout=0):
        pass

    @property
    def first(self):
        return self

    def click(self, force=False, timeout=0):
        # a real trusted click commits the matched option in the model
        self.page._do_real_click(self.sel)


class FakeKlarityPage:
    """Models one labeled-radio field container.

    `synthetic_commits` controls whether the _REASSERT_SELECT_JS path "sticks":
    Klarity's real failure is synthetic=False (DOM toggles but savedValue stays
    null) -> the orchestrator must fall back to the real click.
    """

    def __init__(self, field_path, options, target_label, synthetic_commits=False):
        self.field_path = field_path
        self.options = options  # list of label strings
        self.target_label = target_label
        self.synthetic_commits = synthetic_commits
        self.committed = None      # the field-controller savedValue (truth)
        self.real_click_count = 0
        self.synthetic_attempts = 0
        # radio ids mirror Ashby: <formRenderId>_<fieldUuid>-labeled-radio-N
        self._ids = {opt: f"RENDER_{field_path}-labeled-radio-{i}"
                     for i, opt in enumerate(options)}

    # -- _REASSERT_SELECT_JS contract --
    def evaluate(self, js, arg=None):
        if js is R._REASSERT_SELECT_JS:
            self.synthetic_attempts += 1
            if self.synthetic_commits:
                tgt = arg.get("target")
                self.committed = tgt
                return {"ok": True, "shape": "radio", "after": tgt}
            # synthetic path toggles DOM but does NOT commit savedValue
            return {"ok": False, "shape": "radio", "reason": "synthetic-no-commit"}
        # -- _pw_click_radio_option locate eval --
        # arg = {'fps': [...], 'target': '...'} -> return {'ok':True,'rid':...}
        if isinstance(arg, dict) and "fps" in arg and "target" in arg:
            fps = arg["fps"]
            if self.field_path not in fps and not any(
                    str(f).endswith(self.field_path) for f in fps):
                return {"ok": False, "reason": "no-container"}
            t = (arg["target"] or "").strip().lower()
            pick = next((o for o in self.options if o.strip().lower() == t), None) \
                or next((o for o in self.options if t and t in o.strip().lower()), None) \
                or next((o for o in self.options if o.strip().lower() in t), None)
            if not pick:
                return {"ok": False, "reason": "no-option-match", "target": arg["target"]}
            return {"ok": True, "rid": self._ids[pick]}
        # -- _pw_click_radio_option verify eval (arg = radio_id string) --
        if isinstance(arg, str) and arg.startswith("RENDER_"):
            # report committed state for the option whose id == arg
            opt = next((o for o, rid in self._ids.items() if rid == arg), None)
            checked = (opt is not None and self.committed == opt)
            return {"checked": checked, "value": self.committed,
                    "saved": self.committed,
                    "checkedIdx": self.options.index(opt) if (checked and opt in self.options) else -1}
        return None

    # -- locator contract for the real click --
    def locator(self, sel):
        return FakeLoc(self, sel)

    def _sel_hits(self, sel):
        # accept input[id="..."] and label[for="..."] selectors that name a known id
        return any(rid in sel for rid in self._ids.values())

    def _do_real_click(self, sel):
        for opt, rid in self._ids.items():
            if rid in sel:
                self.committed = opt          # trusted click commits savedValue
                self.real_click_count += 1
                return

    def wait_for_timeout(self, ms):
        pass


KLARITY_OPTS = [
    "I am a US Citizen / Green Card Holder",
    "I have an H-1B and will require transfer",
    "I have an H-1B, I-140 approved, and will require transfer",
    "I have OPT from Academics",
]
KLARITY_TARGET = "I am a US Citizen / Green Card Holder"
SF_OPTS = [
    "I am based in San Francisco",
    "I am open to relocating to San Francisco",
    "I am not willing to relocate at this time",
]
SF_TARGET = "I am open to relocating to San Francisco"


# ---------------------------------------------------------------------------
# (1) _pw_click_radio_option happy path
# ---------------------------------------------------------------------------
def test_pw_click_radio_commits_target_option():
    page = FakeKlarityPage("5658b589-ea7a-4582-b9c7-92a4c5809fbd", KLARITY_OPTS, KLARITY_TARGET)
    res = R._pw_click_radio_option(page, ["5658b589-ea7a-4582-b9c7-92a4c5809fbd"], KLARITY_TARGET)
    assert res["ok"] is True, res
    assert page.real_click_count == 1
    assert page.committed == KLARITY_TARGET
    assert res["state"]["checked"] is True
    assert res["state"]["value"] == KLARITY_TARGET


def test_pw_click_radio_no_option_match_returns_not_ok():
    page = FakeKlarityPage("uuid-x", KLARITY_OPTS, KLARITY_TARGET)
    res = R._pw_click_radio_option(page, ["uuid-x"], "Some option that does not exist")
    assert res["ok"] is False
    assert page.real_click_count == 0


def test_pw_click_radio_field_path_tail_match():
    # plan name carries the entry-uuid prefix; field_paths includes the bare uuid
    page = FakeKlarityPage("b4ff3fea-a627-4945-b958-9df48cbc63fd", SF_OPTS, SF_TARGET)
    res = R._pw_click_radio_option(
        page,
        ["537edd32_b4ff3fea-a627-4945-b958-9df48cbc63fd", "b4ff3fea-a627-4945-b958-9df48cbc63fd"],
        SF_TARGET)
    assert res["ok"] is True
    assert page.committed == SF_TARGET


# ---------------------------------------------------------------------------
# (2) reassert_select_fields falls back to the real click when synthetic fails
# ---------------------------------------------------------------------------
def test_reassert_falls_back_to_pw_click_when_synthetic_fails():
    page = FakeKlarityPage("5658b589-ea7a-4582-b9c7-92a4c5809fbd", KLARITY_OPTS,
                           KLARITY_TARGET, synthetic_commits=False)
    radios = [{
        "name": "537edd32_5658b589-ea7a-4582-b9c7-92a4c5809fbd",
        "value": "I am a US Citizen / Green Card Holder",
        "options": KLARITY_OPTS,
        "label": "Do you require sponsorship now or in the future to work in the United States?",
    }]
    res = R.reassert_select_fields(page, radios)
    assert len(res) == 1
    entry = res[0]
    assert entry["ok"] is True, entry
    assert entry.get("committed_via") == "pw_click", entry
    assert page.synthetic_attempts == 1     # synthetic tried first
    assert page.real_click_count == 1       # then real-click fallback
    assert page.committed == KLARITY_TARGET


def test_reassert_no_pw_fallback_when_synthetic_succeeds():
    # if the synthetic path commits, the real click must NOT fire (no double-work)
    page = FakeKlarityPage("5658b589-ea7a-4582-b9c7-92a4c5809fbd", KLARITY_OPTS,
                           KLARITY_TARGET, synthetic_commits=True)
    radios = [{
        "name": "537edd32_5658b589-ea7a-4582-b9c7-92a4c5809fbd",
        "value": "I am a US Citizen / Green Card Holder",
        "options": KLARITY_OPTS,
        "label": "sponsorship",
    }]
    res = R.reassert_select_fields(page, radios)
    assert res[0]["ok"] is True
    assert res[0].get("committed_via") != "pw_click"
    assert page.real_click_count == 0
