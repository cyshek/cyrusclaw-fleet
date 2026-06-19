#!/usr/bin/env python3
"""Tests for pick_workday_source / _source_committed (grind-resolver 2026-06-02 fix).

The old [role=option] exact-text picker logged 'source picked' but never COMMITTED a pill,
causing an EXIT-5 'How Did You Hear About Us is required' loop on every Workday tenant
(verified live on Philips + RBI). These tests pin the new contract with fake pages so the
regression can't silently return.
"""
import importlib.util, pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


class FakeLocator:
    def __init__(self, n=1, text=""):
        self._n = n
        self._text = text
    def __getattr__(self, name):
        def _noop(*a, **k):
            if name in ("count",):
                return self._n
            if name == "all":
                return []
            return None
        return _noop
    @property
    def first(self):
        return self
    def count(self):
        return self._n
    def text_content(self):
        return self._text
    def click(self, *a, **k):
        return None
    def scroll_into_view_if_needed(self, *a, **k):
        return None


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


class FakeKeyboard:
    def __init__(self):
        self.typed = []
    def type(self, t, *a, **k):
        self.typed.append(t)
    def press(self, k):
        pass


class FakePage:
    """Simulates a Workday source multiselect: opening the prompt exposes category+leaf
    options; clicking the leaf flips a 'committed' flag that _source_committed reads."""
    def __init__(self, options, commit_on=None, start_committed=False):
        self._options = options  # list of texts
        self._commit_on = commit_on  # leaf text that commits
        self._committed = start_committed
        self.keyboard = FakeKeyboard()
        self._src_count = 1

    def _on_click(self, text):
        if self._commit_on and text == self._commit_on:
            self._committed = True

    def locator(self, sel):
        if sel == "input#source--source":
            return FakeLocator(n=self._src_count)
        if sel in ("[data-automation-id=promptOption]", "[role=option]"):
            opts = [FakeOption(t, self._on_click) for t in self._options]
            class L:
                def all(inner):
                    return opts
            return L()
        return FakeLocator(n=0)

    def wait_for_timeout(self, *a, **k):
        return None

    def evaluate(self, js, *a, **k):
        # _source_committed scoped check -> our flag
        return self._committed


def test_source_commits_via_category_leaf():
    page = FakePage(
        options=["Career Fair", "Social Media", "LinkedIn", "Indeed", "Website"],
        commit_on="LinkedIn",
    )
    assert wd.pick_workday_source(page) is True
    assert page._committed is True


def test_source_already_selected_short_circuits():
    page = FakePage(options=[], start_committed=True)
    assert wd.pick_workday_source(page) is True


def test_source_no_field_returns_true():
    page = FakePage(options=[])
    page._src_count = 0
    assert wd.pick_workday_source(page) is True


def test_source_never_commits_returns_false():
    # options exist but none ever flip the commit flag -> picker must report failure,
    # not a false 'committed'.
    page = FakePage(options=["Career Fair", "Website"], commit_on=None)
    assert wd.pick_workday_source(page) is False


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)
