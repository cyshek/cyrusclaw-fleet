#!/usr/bin/env python3
"""Tests for _commit_wd_dropdown (workday-myinfo-fix 2026-06-02).

The My-Information step had two dropdowns that logged a 'picked' but NEVER committed a value
('How did you hear about us?' source + phoneNumber countryPhoneCode), so 'Save and Continue'
bounced with a required-field error and My-Info never advanced (observed live on Philips 1466:
work-exp clean, My-Info stuck). _commit_wd_dropdown is the generic verify-or-retry committer.
These fake-page tests pin the contract: commit-on-first-try, retry-when-no-chip, country-code
defaults to US, abort-after-cap returns False. NO live browser.
"""
import importlib.util, pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


class FakeOption:
    def __init__(self, text, on_click=None):
        self._text = text
        self._on_click = on_click
        self.clicked = False
    def text_content(self):
        return self._text
    def scroll_into_view_if_needed(self, *a, **k):
        return None
    def click(self, *a, **k):
        self.clicked = True
        if self._on_click:
            self._on_click(self._text)


class FakeLocator:
    def __init__(self, n=1):
        self._n = n
    @property
    def first(self):
        return self
    def count(self):
        return self._n
    def click(self, *a, **k):
        return None


class FakeKeyboard:
    def __init__(self):
        self.typed = []
        self.pressed = []
    def type(self, t, *a, **k):
        self.typed.append(t)
    def press(self, k):
        self.pressed.append(k)


class FakePage:
    """Simulates a Workday dropdown. `commit_on` = the option text that flips committed.
    `commit_after` = require N clicks of a committing option before it actually sticks
    (models the no-chip-then-retry case). `kbd_commits` lets ArrowDown+Enter commit."""
    def __init__(self, options, commit_on=None, commit_after=1,
                 ctrl_id="phoneNumber--countryPhoneCode", start_committed=False,
                 kbd_commits=False):
        self._options = options
        self._commit_on = commit_on
        self._commit_after = commit_after
        self._commit_hits = 0
        self._committed = start_committed
        self._ctrl_id = ctrl_id
        self.keyboard = FakeKeyboard()
        self._kbd_commits = kbd_commits

    def _on_click(self, text):
        if self._commit_on and text == self._commit_on:
            self._commit_hits += 1
            if self._commit_hits >= self._commit_after:
                self._committed = True

    def locator(self, sel):
        if sel in ("[data-automation-id=promptOption]", "[role=option]"):
            opts = [FakeOption(t, self._on_click) for t in self._options]
            class L:
                def all(inner):
                    return opts
            return L()
        return FakeLocator(n=1)

    def wait_for_timeout(self, *a, **k):
        return None

    def evaluate(self, js, *a, **k):
        # _find_control -> return ctrl id; _committed -> bool flag; _scroll -> True
        if "scrollIntoView" in js:
            return True
        if "getElementById" in js or "textContent" in js and "selectedItem" in js:
            return self._committed
        if "querySelectorAll('button,input" in js or "cands" in js:
            return self._ctrl_id
        return self._committed


def _press_enter_commits(page):
    # patch keyboard.press to commit when Enter pressed (kbd typeahead path)
    orig = page.keyboard.press
    def press(k):
        orig(k)
        if k == "Enter" and page._kbd_commits:
            page._committed = True
    page.keyboard.press = press


def test_commits_on_first_try():
    page = FakePage(
        options=["Select One", "United States of America (+1)", "Canada (+1)"],
        commit_on="United States of America (+1)", commit_after=1)
    assert wd._commit_wd_dropdown(page, "countryPhoneCode",
                                  "United States of America (+1)",
                                  want_alts=["United States", "+1"]) is True
    assert page._committed is True


def test_retry_on_no_chip_then_commits():
    # First click does NOT commit (no chip); second attempt's click does.
    page = FakePage(
        options=["Select One", "United States of America (+1)"],
        commit_on="United States of America (+1)", commit_after=2)
    assert wd._commit_wd_dropdown(page, "countryPhoneCode",
                                  "United States of America (+1)",
                                  want_alts=["United States", "+1"], cap=3) is True
    assert page._committed is True


def test_country_code_defaults_us_via_contains():
    # want_text exact not present, but a '+1 / United States' contains-match exists.
    page = FakePage(
        options=["Select One", "United States (+1)"],
        commit_on="United States (+1)", commit_after=1)
    assert wd._commit_wd_dropdown(page, "countryPhoneCode",
                                  "United States of America (+1)",
                                  want_alts=["United States", "+1"]) is True


def test_aborts_after_cap_returns_false():
    # No option ever commits via click; keyboard fallback also never commits.
    page = FakePage(options=["Select One", "Foo", "Bar"], commit_on=None)
    _press_enter_commits(page)  # kbd_commits is False -> still no commit
    assert wd._commit_wd_dropdown(page, "countryPhoneCode",
                                  "United States of America (+1)",
                                  want_alts=["United States", "+1"], cap=3) is False
    assert page._committed is False


def test_already_committed_short_circuits():
    page = FakePage(options=[], start_committed=True)
    assert wd._commit_wd_dropdown(page, "countryPhoneCode", "United States") is True


def test_keyboard_typeahead_fallback_commits():
    # click path never commits, but ArrowDown+Enter does.
    page = FakePage(options=["Select One"], commit_on=None, kbd_commits=True)
    _press_enter_commits(page)
    assert wd._commit_wd_dropdown(page, "countryPhoneCode",
                                  "United States of America (+1)",
                                  want_alts=["United States", "+1"], cap=2) is True


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
            except Exception as e:
                fails += 1; print("ERROR", name, repr(e))
    print(f"\n{'ALL GREEN' if not fails else str(fails)+' FAILED'}")
    sys.exit(1 if fails else 0)
