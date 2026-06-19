"""Tests for _workday_runner terminal-state detection (workday-p17 NVIDIA recovery fix).
Pure-logic: FakePage stubs body text + automation-id locators; no live browser."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("wr", str(Path(__file__).parent / "_workday_runner.py"))
wr = importlib.util.module_from_spec(spec); spec.loader.exec_module(wr)


class FakeLoc:
    def __init__(self, n): self._n = n
    def count(self): return self._n

class FakePage:
    def __init__(self, body="", ids=None):
        self._body = body
        self._ids = ids or {}
    def locator(self, sel):
        if sel == "body":
            class B:
                def __init__(s, t): s._t = t
                def text_content(s): return s._t
            return B(self._body)
        # selectors like "[data-automation-id=alreadyAppliedPage]"
        for k, v in self._ids.items():
            if k in sel:
                return FakeLoc(v)
        return FakeLoc(0)


def test_already_applied_by_id():
    p = FakePage(body="Some job", ids={"alreadyAppliedPage": 1})
    assert wr.terminal_state(p) == "already_applied"

def test_already_applied_by_text():
    p = FakePage(body="Technical PM. You've already applied for this job. View My Applications")
    assert wr.terminal_state(p) == "already_applied"

def test_closed_req():
    p = FakePage(body="The page you are looking for doesn't exist. Search for Jobs")
    assert wr.terminal_state(p) == "closed"

def test_closed_req_alt_phrase():
    p = FakePage(body="Requested page not found")
    assert wr.terminal_state(p) == "closed"

def test_none_on_normal_page():
    p = FakePage(body="My Information First Name Last Name", ids={})
    assert wr.terminal_state(p) is None

def test_none_on_signin_page():
    p = FakePage(body="Sign In Email Address Password Create Account")
    assert wr.terminal_state(p) is None


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception as e:
            failed += 1; print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
